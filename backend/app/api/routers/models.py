"""Per-asset CPRI thermal model evaluation matrix (read-only).

Every row is resolved through the same registry the runtime uses, so capability flags here match
what the live twin enforces. Metrics come only from frozen artifacts and their hash-bound,
standalone one-shot TEST reports; nothing is recomputed or re-evaluated.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, status

from app.core.registry import CPRI_SYNTHETIC_ASSET_RATINGS, _REPO_ROOT, resolve_model_artifact
from app.models.thermal_artifact import QualificationStatus

router = APIRouter(prefix="/models", tags=["Analytics & Scenarios"])

# Telemetry-driven capabilities: deterministic rules on measured signals, independent of the thermal model.
MONITORING_CAPABILITIES = {
    "telemetry_monitoring": "Measured voltage, current, loading, oil and ambient temperature.",
    "anomaly_detection": "Deterministic detectors on measured telemetry (loading, phase/neutral, voltage/PF/frequency, thermal limits, sensor plausibility).",
    "othi_health_index": "Five-domain gated OTHI from measured evidence.",
    "maintenance_advisories": "Deterministic rule policy (rules.yaml); model-dependent rules stay gated.",
}


def _q(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _evaluation_row(asset_id: str) -> dict[str, Any]:
    processed = _REPO_ROOT / "data" / "processed"
    artifact_path = processed / f"calibrated_thermal_model_cpri_{asset_id.lower()}.json"
    report_path = processed / f"test_evaluation_report_cpri_{asset_id.lower()}.json"
    artifact = resolve_model_artifact(asset_id=asset_id, dataset_id="cpri_v3_0_2")
    fitted = artifact.parameters is not None

    row: dict[str, Any] = {
        "asset_id": asset_id,
        "rated_kva": CPRI_SYNTHETIC_ASSET_RATINGS[asset_id],
        "fit_status": "FROZEN_CANDIDATE" if fitted else "NOT_FITTED",
        "artifact_sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest() if artifact_path.exists() else None,
        "model_version": artifact.model_version if fitted else None,
        "promotion_status": artifact.promotion.status,
        "promotion_reasons": list(artifact.promotion.reasons),
        "test_partition": "UNTOUCHED",
        "test_evaluated_at_utc": None,
        "gates": None,
        "metrics": None,
        "parameters": artifact.parameters.model_dump() if fitted else None,
        "selected_load_driver": artifact.selected_load_driver if fitted else None,
    }

    if fitted and report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("frozen_artifact_sha256") == row["artifact_sha256"]:
            decision = report["promotion_decision"]
            model = report["primary_model_metrics"]
            persistence = report["baseline_metrics"]["persistence"]
            row["test_partition"] = "CONSUMED"
            row["test_evaluated_at_utc"] = report.get("evaluated_at_utc")
            row["gates"] = {
                "mae_improvement": decision["passes_mae_criterion"],
                "signed_bias": decision["passes_bias_criterion"],
                "coverage_band": decision["passes_coverage_criterion"],
                "scenario": decision["passes_scenario_criterion"],
                "identifiability": decision.get("passes_identifiability_criterion"),
            }
            row["metrics"] = {
                "mae_2h_degc": model["mae_degc"],
                "persistence_mae_2h_degc": persistence["mae_degc"],
                "mae_improvement_pct": decision["mae_improvement_pct"],
                "signed_bias_degc": model["bias_degc"],
                "persistence_signed_bias_degc": persistence["bias_degc"],
                "marginal_coverage_90_pct": model.get("marginal_coverage_90_pct"),
                "path_coverage_90_pct": model.get("simultaneous_path_coverage_90_pct"),
            }
        else:
            row["test_partition"] = "REPORT_NOT_BOUND_TO_ARTIFACT"

    qual = artifact.qualification
    reasons = qual.dimension_reasons if qual is not None else {}

    def model_capability(field: str, ok_values: tuple[QualificationStatus, ...]) -> dict[str, Any]:
        if not fitted or qual is None:
            return {"available": False, "reason": "No fitted thermal model for this asset."}
        value = getattr(qual, field)
        return {"available": value in ok_values, "status": _q(value), "reason": reasons.get(field, "")}

    row["capabilities"] = {
        **{k: {"available": True, "status": "OPERATIONAL", "reason": v} for k, v in MONITORING_CAPABILITIES.items()},
        "descriptive_thermal": model_capability(
            "residual_display_qualification", (QualificationStatus.DESCRIPTIVE_ONLY, QualificationStatus.QUALIFIED)
        ),
        "residual_anomaly_evidence": model_capability("residual_anomaly_qualification", (QualificationStatus.QUALIFIED,)),
        "forecasting": model_capability("forecast_qualification", (QualificationStatus.QUALIFIED,)),
        "what_if": model_capability("scenario_qualification", (QualificationStatus.QUALIFIED,)),
    }
    return row


@router.get(
    "/cpri-evaluation",
    status_code=status.HTTP_200_OK,
    summary="Per-asset CPRI thermal model evaluation and capability matrix",
)
async def get_cpri_model_evaluation() -> dict[str, Any]:
    """Return fit, one-shot TEST evaluation, gate outcomes and capability availability for all CPRI assets."""
    return {
        "dataset_id": "cpri_v3_0_2",
        "promotion_policy": {
            "mae_improvement": "2-h trajectory MAE improvement over multi-step persistence >= 5%",
            "signed_bias": "|model bias| <= |persistence bias| + 0.10 degC (residual = observed - predicted)",
            "coverage_band": "TEST empirical 90% marginal coverage within [80%, 98%]",
            "identifiability": "FIT parameters identifiable, not on bounds",
        },
        "assets": [_evaluation_row(a) for a in CPRI_SYNTHETIC_ASSET_RATINGS],
    }
