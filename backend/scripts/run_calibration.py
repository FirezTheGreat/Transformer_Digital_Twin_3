"""Execution CLI Runner for Phase 4.2 Thermal Model Calibration & Evaluation Pipeline.

This script executes the complete, frozen Phase 4.2 calibration workflow:
1. Loads Tripura Parquet partitions (FIT, CAL, TEST).
2. Performs FIT-only load-driver selection (S vs I_eq).
3. Fits first-order grey-box thermal parameters (beta_0, beta_1, tau).
4. Fits 3 baseline models (Persistence, Ambient + Median Rise, Static Robust Regression).
5. Calibrates empirical 90% block-conformal path uncertainty on CAL.
6. Evaluates one-shot promotion against untouched TEST lockbox.
7. Saves the frozen artifact to `data/processed/calibrated_thermal_model.json`.

Usage:
    python backend/scripts/run_calibration.py
    python -m backend.scripts.run_calibration
"""

import logging
import sys
from pathlib import Path
import pandas as pd

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.engine.calibration import (
    compute_file_sha256,
    run_full_calibration_pipeline,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("ThermalCalibration")


def main() -> None:
    workspace_root = backend_dir.parent
    processed_dir = workspace_root / "data" / "processed"

    fit_path = processed_dir / "tripura_fit.parquet"
    cal_path = processed_dir / "tripura_calibration.parquet"
    test_path = processed_dir / "tripura_test.parquet"

    if not fit_path.exists() or not cal_path.exists() or not test_path.exists():
        logger.error("Required Parquet partitions missing in %s", processed_dir)
        sys.exit(1)

    logger.info("Loading Parquet partitions...")
    fit_df = pd.read_parquet(fit_path)
    cal_df = pd.read_parquet(cal_path)
    test_df = pd.read_parquet(test_path)

    hashes = {
        "tripura_fit_sha256": compute_file_sha256(fit_path),
        "tripura_calibration_sha256": compute_file_sha256(cal_path),
        "tripura_test_sha256": compute_file_sha256(test_path),
    }

    logger.info("Dataset Parquet Hashes:")
    for k, v in hashes.items():
        logger.info("  %s: %s", k, v)

    artifact = run_full_calibration_pipeline(
        fit_df=fit_df,
        cal_df=cal_df,
        test_df=test_df,
        asset_id="tripura_dt_01",
        model_version="greybox_v1_0",
        dataset_hashes=hashes,
    )

    output_path = processed_dir / "calibrated_thermal_model.json"
    artifact.save_json(output_path)
    logger.info("Saved frozen calibrated thermal model artifact to %s", output_path)

    print("\n" + "=" * 78)
    print("PHASE 4.2 THERMAL CALIBRATION & PROMOTION SUMMARY REPORT")
    print("=" * 78)
    print(f"Asset ID:                  {artifact.asset_id}")
    print(f"Model Version:             {artifact.model_version}")
    print(f"Selected Load Driver:      {artifact.selected_load_driver} (P95 Ref: {artifact.load_driver_reference_value:.2f})")
    print(f"Fitted Parameters:         beta_0 = {artifact.parameters.beta_0:.4f} °C, beta_1 = {artifact.parameters.beta_1:.4f} °C, tau = {artifact.parameters.tau_hours:.4f} h")
    print(f"Parameter Identifiability: {'PASS' if artifact.identifiability.is_identifiable else 'FAIL'}")
    print(f"Conformal Uncertainty:     q_90 = {artifact.conformal_uncertainty.block_quantile_90:.4f}, W_1 = {artifact.conformal_uncertainty.horizon_half_widths_degc[0]:.2f} °C, W_8 = {artifact.conformal_uncertainty.horizon_half_widths_degc[-1]:.2f} °C")
    print("-" * 78)
    print(f"PRIMARY TEST EVALUATION:   2-Hour / 8-Step Conditional Forward Trajectory")
    print(f"  Grey-Box ODE Trajectory MAE:     {artifact.test_metrics.mae_degc:.4f} °C  (RMSE: {artifact.test_metrics.rmse_degc:.4f} °C, Bias: {artifact.test_metrics.bias_degc:+.4f} °C)")
    print(f"  Persistence Trajectory MAE:      {artifact.baselines['persistence'].mae_degc:.4f} °C" if "persistence" in artifact.baselines else "")
    print(f"  Ambient+Rise Trajectory MAE:     {artifact.baselines['ambient_median_rise'].mae_degc:.4f} °C" if "ambient_median_rise" in artifact.baselines else "")
    print(f"  Static Regr Trajectory MAE:      {artifact.baselines['static_robust_regression'].mae_degc:.4f} °C" if "static_robust_regression" in artifact.baselines else "")
    print(f"  2-Hour Trajectory Improvement:   {artifact.promotion.mae_improvement_pct:+.2f}% vs Persistence")
    print(f"  Test 90% Conformal Coverage:     {artifact.test_metrics.marginal_coverage_90_pct:.2f}%")
    print("-" * 78)
    if artifact.metadata and "secondary_1step_closed_loop" in artifact.metadata:
        sec = artifact.metadata["secondary_1step_closed_loop"]
        print(f"SECONDARY SANITY CHECK:    1-Step (15-min) Closed-Loop Prediction")
        print(f"  Grey-Box ODE 1-Step MAE:         {sec.get('greybox_1step_mae_degc', 0.0):.4f} °C  (RMSE: {sec.get('greybox_1step_rmse_degc', 0.0):.4f} °C, Bias: {sec.get('greybox_1step_bias_degc', 0.0):+.4f} °C)")
        print(f"  Persistence 1-Step MAE:          {sec.get('persistence_1step_mae_degc', 0.0):.4f} °C")
        print(f"  1-Step MAE Improvement:          {sec.get('mae_improvement_pct', 0.0):+.2f}%")
    print("-" * 78)
    if artifact.metadata and "horizon_breakdown" in artifact.metadata:
        print("HORIZON BREAKDOWN (h = 1..8 steps / 15..120 min):")
        print(f"  {'Horizon':<10} | {'Grey-Box MAE':<14} | {'Persist MAE':<14} | {'Diff (°C)':<12} | {'Improvement':<12}")
        for h_info in artifact.metadata["horizon_breakdown"]:
            h = h_info["horizon_step"]
            g_mae = h_info["mae_degc"]
            p_mae = h_info["persistence_mae_degc"]
            diff = g_mae - p_mae
            imp = ((p_mae - g_mae) / p_mae) * 100 if p_mae > 0 else 0.0
            print(f"  h={h:<8} | {g_mae:<14.4f} | {p_mae:<14.4f} | {diff:<+12.4f} | {imp:<+11.2f}%")
    print("-" * 78)
    print(f"PROMOTION DECISION:        {artifact.promotion.status}")
    print("Criteria Details:")
    for reason in artifact.promotion.reasons:
        print(f"  - {reason}")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
