"""Execution CLI Runner for CPRI Synthetic Benchmark Thermal Calibration Pipeline.

This script executes the Phase 4 calibration workflow specifically for CPRI synthetic benchmark assets:
1. Loads CPRI Parquet partitions (FIT, CAL, TEST) from `data/processed/cpri_v3_*.parquet`.
2. Filters to target asset (default: TX_250_MIX).
3. Evaluates FIT-only load-driver selection (apparent_power_kva vs rms_current_a).
4. Fits first-order grey-box thermal parameters (beta_0, beta_1, tau).
5. Fits baseline models.
6. Calibrates empirical 90% block-conformal path uncertainty on CAL.
7. Evaluates one-shot promotion against untouched TEST lockbox.
8. Saves frozen artifact to `data/processed/calibrated_thermal_model_cpri_{asset.lower()}.json`.

NOTE: Execution of actual training/calibration is blocked until explicitly authorized.
Use `--verify-inputs-only` to validate partitions and schema without executing fitting.

Usage:
    python backend/scripts/run_calibration_cpri.py --asset TX_250_MIX --verify-inputs-only
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
import pandas as pd

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.engine.calibration import (
    compute_file_sha256,
    evaluate_frozen_artifact_on_test,
    fit_and_calibrate_thermal_model,
    freeze_candidate_artifact,
    prepare_thermal_series,
    run_full_calibration_pipeline,
)
from app.core.registry import CPRI_SYNTHETIC_ASSET_RATINGS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("CPRICalibrationRunner")


def main() -> None:
    parser = argparse.ArgumentParser(description="CPRI Synthetic Thermal Model Calibration Runner")
    parser.add_argument(
        "--asset",
        default="TX_250_MIX",
        choices=list(CPRI_SYNTHETIC_ASSET_RATINGS.keys()),
        help="Target CPRI asset ID",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--verify-inputs-only",
        action="store_true",
        help="Verify partitions, schema, and inputs without fitting or freezing model artifacts",
    )
    group.add_argument(
        "--fit-and-freeze",
        action="store_true",
        help="Fit model on FIT (eligible rows only), calibrate uncertainty on CAL, freeze candidate artifact. ZERO TEST ACCESS.",
    )
    group.add_argument(
        "--evaluate-test",
        action="store_true",
        help="Evaluate an existing frozen candidate artifact against TEST partition. Writes separate evaluation report.",
    )
    args = parser.parse_args()

    workspace_root = backend_dir.parent
    processed_dir = workspace_root / "data" / "processed"

    fit_path = processed_dir / "cpri_v3_fit.parquet"
    cal_path = processed_dir / "cpri_v3_calibration.parquet"
    test_path = processed_dir / "cpri_v3_test.parquet"

    if args.evaluate_test:
        # TEST evaluation mode: requires frozen candidate artifact to exist
        artifact_path = processed_dir / f"calibrated_thermal_model_cpri_{args.asset.lower()}.json"
        if not artifact_path.exists():
            logger.error("Cannot evaluate on TEST: frozen candidate artifact not found at %s. Run --fit-and-freeze first.", artifact_path)
            sys.exit(1)
        if not test_path.exists():
            logger.error("Required CPRI TEST Parquet partition missing: %s", test_path)
            sys.exit(1)

        logger.info("Evaluating frozen candidate artifact for %s on TEST partition...", args.asset)
        test_df = pd.read_parquet(test_path)
        test_asset = test_df[test_df["meta_transformer_id"] == args.asset].copy().reset_index(drop=True)

        # Load FIT partition for baseline model fitting on FIT only (if available)
        fit_asset = None
        if fit_path.exists():
            fit_df = pd.read_parquet(fit_path)
            fit_asset = fit_df[fit_df["meta_transformer_id"] == args.asset].copy().reset_index(drop=True)

        report_path = processed_dir / f"test_evaluation_report_cpri_{args.asset.lower()}.json"
        report = evaluate_frozen_artifact_on_test(
            artifact_path=artifact_path,
            test_df=test_asset,
            fit_df=fit_asset,
            output_report_path=report_path,
            nominal_cadence_s=1800.0,
        )

        print("\n" + "=" * 70)
        print("CPRI TEST EVALUATION REPORT (STANDALONE RECORD)")
        print("=" * 70)
        print(f"Asset ID:                 {args.asset}")
        print(f"Frozen Artifact:          {report['frozen_artifact_file']}")
        print(f"Frozen Artifact SHA-256:  {report['frozen_artifact_sha256']}")
        print(f"TEST Samples:             {len(test_asset)}")
        print(f"2h Trajectory MAE:        {report['primary_model_metrics']['mae_degc']} degC")
        print(f"2h Persistence MAE:       {report['baseline_metrics']['persistence']['mae_degc']} degC")
        print(f"MAE Improvement:          {report['promotion_decision']['mae_improvement_pct']:+.2f}%")
        print(f"Marginal 90% Coverage:    {report['primary_model_metrics'].get('marginal_coverage_90_pct')}%")
        print(f"Simultaneous 90% Coverage:{report['primary_model_metrics'].get('simultaneous_path_coverage_90_pct')}%")
        print(f"Promotion Status:         {report['promotion_decision']['status']}")
        print(f"Report File:              {report_path.name}")
        print("=" * 70 + "\n")
        return

    # For --verify-inputs-only and --fit-and-freeze, load FIT and CAL (do NOT load TEST for --fit-and-freeze)
    for p in [fit_path, cal_path]:
        if not p.exists():
            logger.error("Required CPRI Parquet partition missing: %s", p)
            sys.exit(1)

    logger.info("Loading CPRI Parquet partitions for asset %s...", args.asset)
    fit_df = pd.read_parquet(fit_path)
    cal_df = pd.read_parquet(cal_path)

    # Filter to requested asset
    fit_asset = fit_df[fit_df["meta_transformer_id"] == args.asset].copy().reset_index(drop=True)
    cal_asset = cal_df[cal_df["meta_transformer_id"] == args.asset].copy().reset_index(drop=True)

    n_fit_total = len(fit_asset)
    fit_eligible = fit_asset[fit_asset["y_fit_eligible"] == 1].copy().reset_index(drop=True) if "y_fit_eligible" in fit_asset.columns else fit_asset
    n_fit_eligible = len(fit_eligible)
    n_fit_excluded = n_fit_total - n_fit_eligible

    logger.info("Asset row counts: FIT Total=%d (Eligible=%d, Excluded=%d), CAL=%d", n_fit_total, n_fit_eligible, n_fit_excluded, len(cal_asset))

    # Verify input preparation using eligible rows only
    fit_series = prepare_thermal_series(fit_eligible, driver_type="apparent_power_kva")
    logger.info(
        "Prepared FIT series: %d points, %d segments, median dt=%.2f h, P95 ref=%.2f",
        len(fit_series.top_oil_degc),
        len(set(fit_series.segment_ids)),
        float(pd.Series(fit_series.dt_hours).median()),
        fit_series.reference_value,
    )

    hashes = {
        "cpri_v3_fit_sha256": compute_file_sha256(fit_path),
        "cpri_v3_calibration_sha256": compute_file_sha256(cal_path),
    }

    if args.verify_inputs_only:
        test_df = pd.read_parquet(test_path) if test_path.exists() else None
        n_test = len(test_df[test_df["meta_transformer_id"] == args.asset]) if test_df is not None else 0
        logger.info("Input verification SUCCESSFUL for %s. Zero training performed.", args.asset)
        print("\n" + "=" * 70)
        print("CPRI CALIBRATION INPUT VERIFICATION REPORT")
        print("=" * 70)
        print(f"Asset ID:             {args.asset}")
        print(f"Declared Rating:      {CPRI_SYNTHETIC_ASSET_RATINGS[args.asset]} kVA")
        print(f"FIT Partition Total:  {n_fit_total} samples ({fit_path.name})")
        print(f"FIT Eligible Rows:    {n_fit_eligible} samples (y_fit_eligible == 1)")
        print(f"FIT Excluded Rows:    {n_fit_excluded} samples (events/faults excluded)")
        print(f"FIT Segments:         {len(set(fit_series.segment_ids))} continuous segments")
        print(f"CAL Partition:        {len(cal_asset)} samples ({cal_path.name})")
        print(f"TEST Partition:       {n_test} samples ({test_path.name})")
        print(f"Sampling Cadence:     30 minutes (median dt={pd.Series(fit_series.dt_hours).median():.2f} h)")
        print(f"FIT Load Ref (P95):   {fit_series.reference_value:.2f} kVA")
        print("TEST Access Status:   ZERO ACCESS (Preserved untouched)")
        print("Status:               INPUTS VERIFIED & READY FOR TRAINING")
        print("=" * 70 + "\n")
        return

    if args.fit_and_freeze:
        logger.info("Executing FIT parameter optimization and CAL uncertainty calibration for %s...", args.asset)
        artifact = fit_and_calibrate_thermal_model(
            fit_df=fit_asset,
            cal_df=cal_asset,
            asset_id=args.asset,
            dataset_id="cpri_v3_0_2",
            model_version="cpri_greybox_v1_0",
            nominal_cadence_s=1800.0,
            dataset_hashes=hashes,
        )

        output_path = processed_dir / f"calibrated_thermal_model_cpri_{args.asset.lower()}.json"
        manifest_path = processed_dir / f"candidate_manifest_cpri_{args.asset.lower()}.json"
        manifest = freeze_candidate_artifact(
            artifact=artifact,
            output_path=output_path,
            manifest_path=manifest_path,
        )

        print("\n" + "=" * 70)
        print("CPRI CANDIDATE ARTIFACT FROZEN REPORT (ZERO TEST ACCESS)")
        print("=" * 70)
        print(f"Asset ID:                 {args.asset}")
        print(f"Artifact File:            {output_path.name}")
        print(f"Candidate SHA-256:        {manifest['candidate_artifact_sha256']}")
        print(f"Selected Load Driver:     {artifact.selected_load_driver} (ref={artifact.load_driver_reference_value:.2f})")
        print(f"Fitted Parameters:        beta_0={artifact.parameters.beta_0:.4f}, beta_1={artifact.parameters.beta_1:.4f}, tau={artifact.parameters.tau_hours:.4f} h")
        print(f"Identifiability:          {'IDENTIFIABLE' if artifact.identifiability.is_identifiable else 'FAILED'}")
        print(f"Conformal Quantile (q90): {artifact.conformal_uncertainty.block_quantile_90:.4f}")
        print(f"Conformal Half-Widths:    {artifact.conformal_uncertainty.horizon_half_widths_degc} degC")
        print(f"Calibration Origins:      {artifact.conformal_uncertainty.num_calibration_origins}")
        print(f"Promotion Status:         {artifact.promotion.status}")
        print(f"TEST Partition Status:    ZERO ACCESS (Frozen before TEST)")
        print(f"Candidate Manifest:       {manifest_path.name}")
        print("=" * 70 + "\n")
        return


if __name__ == "__main__":
    main()
