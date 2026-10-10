"""Candidate Synthetic Dataset (gridpulse_synthetic_v1) Evaluation & Promotion Runner.

Executes Phase 6 of the GridPulse Master Execution Plan:
1. Respects strict chronological FIT -> CAL -> FREEZE -> TEST discipline.
2. Fits first-order grey-box thermal ODE parameters (beta_0, beta_1, tau) on FIT partition only.
3. Calibrates 90% block-conformal trajectory uncertainty bands on CAL partition only.
4. Freezes candidate model artifacts and generates immutable candidate manifests with SHA-256 checksums.
5. Evaluates frozen candidate artifacts on untouched holdout TEST partition (36 days, 1,728 samples per asset).
6. Compares 2-hour multi-step trajectory against baselines (Persistence, Ambient Median Rise, Static Robust Regression).
7. Evaluates multi-domain anomaly detectors across the TEST partition against ground-truth scenarios.
8. Generates comprehensive per-asset and aggregate promotion evaluation reports.
9. Outputs formal promotion recommendation (PROMOTE / DO_NOT_PROMOTE / INSUFFICIENT_EVIDENCE).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.adapters.gridpulse_synthetic import (
    GridPulseSyntheticAdapter,
    SYNTHETIC_ASSET_PROFILES,
)
from app.engine.anomaly_detectors import MultiDomainAnomalyEngine
from app.engine.calibration import (
    compute_file_sha256,
    evaluate_frozen_artifact_on_test,
    fit_and_calibrate_thermal_model,
    freeze_candidate_artifact,
)
from app.models.profile import AssetProfile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("CandidateEvaluationRunner")

CANDIDATE_ASSET_IDS = ["DT-01", "DT-02", "DT-03", "DT-04"]


def prepare_candidate_dataframe(df_raw: pd.DataFrame, asset_id: str) -> pd.DataFrame:
    """Prepare candidate asset DataFrame with canonical columns required by calibration engine."""
    df_asset = df_raw[df_raw["asset_id"] == asset_id].copy()
    df_asset["ts"] = df_asset["timestamp_utc"]
    df_asset["OTI"] = df_asset["top_oil_c"]
    df_asset["ATI"] = df_asset["ambient_c"]
    df_asset["KVA"] = df_asset["s_kva"]
    df_asset["IL1"] = df_asset["i_l1_a"]
    df_asset["IL2"] = df_asset["i_l2_a"]
    df_asset["IL3"] = df_asset["i_l3_a"]
    df_asset["y_fit_eligible"] = (df_asset["dq_flag"] == "OK").astype(int)
    return df_asset.sort_values("ts").reset_index(drop=True)


def evaluate_asset_anomalies_on_test(
    df_asset: pd.DataFrame,
    asset_id: str,
    profile: AssetProfile,
) -> Dict[str, Any]:
    """Evaluate multi-domain anomaly detectors over the holdout TEST partition."""
    adapter = GridPulseSyntheticAdapter()
    engine = MultiDomainAnomalyEngine(asset_id=asset_id, profile=profile)
    test_df = df_asset[df_asset["partition"] == "TEST"].copy()
    test_records = test_df.to_dict(orient="records")
    total_test_events = len(test_records)
    detected_episodes: List[Dict[str, Any]] = []
    detector_counts: Dict[str, int] = {}

    for row in test_records:
        event = adapter.transform_record(
            raw_record=row,
            asset_id=asset_id,
            source_uri="gridpulse_synthetic_30min.csv",
        )
        evidence_items = engine.evaluate_event(event)
        for ev in evidence_items:
            det_id = ev.detector_id
            detector_counts[det_id] = detector_counts.get(det_id, 0) + 1
            detected_episodes.append({
                "timestamp": event.event_time_utc.isoformat(),
                "detector_id": det_id,
                "severity": ev.severity,
                "reason_codes": ev.reason_codes,
            })

    days_in_test = total_test_events / 48.0 if total_test_events > 0 else 36.0
    return {
        "asset_id": asset_id,
        "total_test_events": total_test_events,
        "test_days": round(days_in_test, 2),
        "total_detections": len(detected_episodes),
        "detector_counts": detector_counts,
        "detections_per_day": round(len(detected_episodes) / max(1.0, days_in_test), 3),
    }


def run_evaluation_for_asset(
    df_candidate: pd.DataFrame,
    asset_id: str,
    output_dir: Path,
    dataset_id: str = "gridpulse_synthetic_v1",
) -> Dict[str, Any]:
    """Execute complete Phase 6 evaluation for a single candidate asset."""
    logger.info("=================================================================")
    logger.info("Executing Phase 6 Evaluation for Candidate Asset: %s", asset_id)
    logger.info("=================================================================")

    df_asset = prepare_candidate_dataframe(df_candidate, asset_id)
    profile = SYNTHETIC_ASSET_PROFILES[asset_id]

    fit_df = df_asset[df_asset["partition"] == "FIT"].reset_index(drop=True)
    cal_df = df_asset[df_asset["partition"] == "CAL"].reset_index(drop=True)
    test_df = df_asset[df_asset["partition"] == "TEST"].reset_index(drop=True)

    logger.info("Partitions for %s: FIT=%d rows, CAL=%d rows, TEST=%d rows", asset_id, len(fit_df), len(cal_df), len(test_df))

    # Stage 1 & 2: Fit model on FIT and calibrate on CAL (Zero TEST access)
    artifact = fit_and_calibrate_thermal_model(
        fit_df=fit_df,
        cal_df=cal_df,
        asset_id=asset_id,
        dataset_id=dataset_id,
        model_version=f"candidate_{asset_id.lower()}_v1_0",
        nominal_cadence_s=1800.0,
    )

    # Stage 3: Freeze candidate artifact and manifest
    output_dir.mkdir(parents=True, exist_ok=True)
    frozen_artifact_path = output_dir / f"calibrated_thermal_model_candidate_{asset_id.lower()}.json"
    manifest_path = output_dir / f"candidate_manifest_{asset_id.lower()}.json"
    manifest = freeze_candidate_artifact(artifact, frozen_artifact_path, manifest_path=manifest_path)
    artifact_hash = manifest["candidate_artifact_sha256"]

    # Stage 4: One-shot holdout evaluation on untouched TEST partition
    test_report_path = output_dir / f"test_evaluation_report_candidate_{asset_id.lower()}.json"
    report = evaluate_frozen_artifact_on_test(
        artifact_path=frozen_artifact_path,
        test_df=test_df,
        fit_df=fit_df,
        output_report_path=test_report_path,
        nominal_cadence_s=1800.0,
    )

    # Stage 5: Anomaly detector evaluation across TEST partition
    anomaly_results = evaluate_asset_anomalies_on_test(df_asset, asset_id, profile)

    decision = report["promotion_decision"]
    primary_metrics = report["primary_model_metrics"]
    persistence_metrics = report["baseline_metrics"]["persistence"]

    asset_summary = {
        "asset_id": asset_id,
        "rated_kva": profile.rated_kva,
        "tank_type": profile.tank_type,
        "artifact_file": frozen_artifact_path.name,
        "artifact_sha256": artifact_hash,
        "report_file": test_report_path.name,
        "report_sha256": compute_file_sha256(test_report_path),
        "selected_load_driver": artifact.selected_load_driver,
        "parameters": artifact.parameters.model_dump() if artifact.parameters else None,
        "identifiability": {
            "is_identifiable": artifact.identifiability.is_identifiable,
            "boundary_hit": artifact.identifiability.boundary_hit,
            "tau_cv": artifact.identifiability.tau_cv_across_folds,
        },
        "test_metrics": {
            "model_mae_2h_degc": primary_metrics["mae_degc"],
            "persistence_mae_2h_degc": persistence_metrics["mae_degc"],
            "mae_improvement_pct": decision["mae_improvement_pct"],
            "model_bias_2h_degc": primary_metrics["bias_degc"],
            "persistence_bias_2h_degc": persistence_metrics["bias_degc"],
            "conformal_90_coverage_pct": primary_metrics.get("simultaneous_path_coverage_90_pct"),
            "conformal_marginal_coverage_pct": primary_metrics.get("marginal_coverage_90_pct"),
            "mean_band_width_degc": primary_metrics.get("mean_width_degc"),
        },
        "promotion_decision": {
            "status": decision["status"],
            "all_criteria_met": decision["all_criteria_met"],
            "passes_mae": decision["passes_mae_criterion"],
            "passes_bias": decision["passes_bias_criterion"],
            "passes_coverage": decision["passes_coverage_criterion"],
            "passes_scenario": decision["passes_scenario_criterion"],
            "passes_identifiability": decision.get("passes_identifiability_criterion"),
            "reasons": decision["reasons"],
        },
        "anomaly_evaluation": anomaly_results,
    }

    return asset_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="GridPulse Candidate Synthetic Dataset Evaluation Runner (Phase 6)")
    parser.add_argument("--asset", default="ALL", choices=["ALL"] + CANDIDATE_ASSET_IDS, help="Target asset ID")
    parser.add_argument(
        "--csv-path",
        default=str(backend_dir.parent / "data" / "candidates" / "gridpulse_synthetic_v1" / "gridpulse_synthetic_30min.csv"),
        help="Path to candidate CSV file",
    )
    parser.add_argument(
        "--output-dir",
        default=str(backend_dir.parent / "data" / "candidates" / "gridpulse_synthetic_v1" / "artifacts"),
        help="Directory to store candidate artifacts and evaluation reports",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        logger.error("Candidate CSV not found at: %s", csv_path)
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading candidate dataset from %s...", csv_path)
    df_raw = pd.read_csv(csv_path, low_memory=False)
    csv_hash = compute_file_sha256(csv_path)
    logger.info("Loaded candidate dataset: %d rows, SHA-256=%s", len(df_raw), csv_hash)

    target_assets = CANDIDATE_ASSET_IDS if args.asset == "ALL" else [args.asset]
    results: List[Dict[str, Any]] = []

    for asset_id in target_assets:
        asset_summary = run_evaluation_for_asset(df_raw, asset_id, output_dir)
        results.append(asset_summary)

    # Compile aggregate matrix and overall promotion recommendation
    overall_promoted_count = sum(1 for r in results if r["promotion_decision"]["status"] == "PROMOTED")
    all_identifiable = all(r["identifiability"]["is_identifiable"] for r in results)
    avg_mae_improvement = np.mean([r["test_metrics"]["mae_improvement_pct"] for r in results])
    avg_model_mae = np.mean([r["test_metrics"]["model_mae_2h_degc"] for r in results])
    avg_persistence_mae = np.mean([r["test_metrics"]["persistence_mae_2h_degc"] for r in results])

    recommendation = "PROMOTE" if overall_promoted_count == len(results) else ("DO_NOT_PROMOTE" if overall_promoted_count == 0 else "PARTIAL_PROMOTE_RECOMMEND_REVIEW")

    aggregate_summary = {
        "evaluation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_dataset_file": csv_path.name,
        "candidate_dataset_sha256": csv_hash,
        "evaluated_assets_count": len(results),
        "promoted_assets_count": overall_promoted_count,
        "all_parameters_identifiable": all_identifiable,
        "aggregate_metrics": {
            "mean_model_mae_2h_degc": round(float(avg_model_mae), 4),
            "mean_persistence_mae_2h_degc": round(float(avg_persistence_mae), 4),
            "mean_mae_improvement_pct": round(float(avg_mae_improvement), 2),
        },
        "overall_recommendation": recommendation,
        "per_asset_results": results,
    }

    summary_file = output_dir / "candidate_phase6_evaluation_summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(aggregate_summary, f, indent=2)

    logger.info("Saved Phase 6 Candidate Evaluation Summary to %s", summary_file)

    # Print summary table
    print("\n" + "=" * 90)
    print("PHASE 6 CANDIDATE EVALUATION MATRIX & PROMOTION AUDIT")
    print("=" * 90)
    print(f"{'Asset ID':<10} | {'Rating':<8} | {'Driver':<18} | {'Model MAE':<10} | {'Pers. MAE':<10} | {'Imprv %':<8} | {'Bias (C)':<9} | {'Status':<12}")
    print("-" * 90)
    for r in results:
        tm = r["test_metrics"]
        print(
            f"{r['asset_id']:<10} | "
            f"{r['rated_kva']:<5} kVA | "
            f"{r['selected_load_driver']:<18} | "
            f"{tm['model_mae_2h_degc']:<10.4f} | "
            f"{tm['persistence_mae_2h_degc']:<10.4f} | "
            f"{tm['mae_improvement_pct']:<7.2f}% | "
            f"{tm['model_bias_2h_degc']:<+8.3f} | "
            f"{r['promotion_decision']['status']:<12}"
        )
    print("=" * 90)
    print(f"OVERALL RECOMMENDATION: {recommendation}")
    print(f"Summary JSON: {summary_file}")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    main()
