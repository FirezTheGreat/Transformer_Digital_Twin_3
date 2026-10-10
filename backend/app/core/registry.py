"""Deterministic Asset Profile and Thermal Model Artifact Resolver.

Provides centralized resolution of AssetProfiles and CalibratedThermalModelArtifacts
keyed strictly by (dataset_id, asset_id).

Enforces critical architecture constraints:
- Tripura model constants are NEVER applied to non-Tripura assets.
- Uncalibrated assets receive an explicit UNCALIBRATED artifact with parameters=None.
- Asset profiles reflect actual dataset expectations (e.g. 15-min for Tripura, 30-min for CPRI).
- No silent aliasing to Tripura for new assets or uncalibrated datasets.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from app.adapters.gridpulse_synthetic import SYNTHETIC_ASSET_PROFILES
from app.models.profile import (
    AssetProfile,
    InsulationClass,
    ProfileField,
    ProfileVerificationStatus,
)
from app.models.thermal_artifact import (
    BaselineMetricEntry,
    CalibratedThermalModelArtifact,
    PromotionDecision,
    QualificationStatus,
)

logger = logging.getLogger(__name__)

# Repository root, so artifacts resolve regardless of the server working directory.
_REPO_ROOT = Path(__file__).resolve().parents[3]


CPRI_SYNTHETIC_ASSET_RATINGS: dict[str, float] = {
    "TX_100_RES": 100.0,
    "TX_160_RURAL": 160.0,
    "TX_250_MIX": 250.0,
    "TX_315_RES": 315.0,
    "TX_400_COMM": 400.0,
    "TX_500_RURAL": 500.0,
    "TX_630_MIX": 630.0,
    "TX_1000_COMM": 1000.0,
}

GRIDPULSE_CANDIDATE_ASSETS: tuple[str, ...] = ("DT-01", "DT-02", "DT-03", "DT-04")


def resolve_asset_profile(
    dataset_id: Optional[str] = None,
    asset_id: str = "DT-TRIPURA-001",
    nominal_cadence_s: Optional[int] = None,
    rated_kva: Optional[float] = None,
) -> AssetProfile:
    """Resolve immutable AssetProfile for a given (dataset_id, asset_id)."""
    clean_asset = str(asset_id).strip()
    if dataset_id is not None:
        clean_ds = str(dataset_id).strip()
    elif clean_asset in ("DT-TRIPURA-001", "tripura_dt_01", "TRIPURA_DTR_01"):
        clean_ds = "tripura_dev"
    elif clean_asset in CPRI_SYNTHETIC_ASSET_RATINGS:
        clean_ds = "cpri_v3_0_2"
    elif clean_asset in SYNTHETIC_ASSET_PROFILES or clean_asset in GRIDPULSE_CANDIDATE_ASSETS:
        clean_ds = "gridpulse_synthetic_v1"
    else:
        clean_ds = "unspecified_dataset"

    # GridPulse Synthetic Benchmark candidate assets (DT-01 .. DT-04)
    if clean_asset in SYNTHETIC_ASSET_PROFILES:
        return SYNTHETIC_ASSET_PROFILES[clean_asset]
    if clean_ds.lower() in ("gridpulse_synthetic_v1", "gridpulse_synthetic", "gridpulse") and clean_asset in GRIDPULSE_CANDIDATE_ASSETS:
        if clean_asset in SYNTHETIC_ASSET_PROFILES:
            return SYNTHETIC_ASSET_PROFILES[clean_asset]

    is_tripura = (clean_asset in ("DT-TRIPURA-001", "tripura_dt_01", "TRIPURA_DTR_01")) and (
        clean_ds.lower() in ("tripura", "tripura_dev", "tripura_csv")
    )

    if is_tripura:
        return AssetProfile(
            asset_id=clean_asset,
            phase_topology="THREE_PHASE_4W",
            nominal_frequency_hz=50.0,
            rated_kva=rated_kva,  # Unverified nameplate per Phase 1 unless explicitly passed
            cooling_class="ONAN",
            insulation_paper_class=InsulationClass.UNKNOWN,
            expected_cadence_s=nominal_cadence_s or 900,  # 15 minutes
            profile_status=ProfileVerificationStatus.VERIFIED if rated_kva is not None else ProfileVerificationStatus.UNVERIFIED,
            fields={
                "load_reference_kva": ProfileField(
                    value=142.898,
                    unit="kVA",
                    source_document="Tripura Training FIT P95 Empirical Distribution",
                    status=ProfileVerificationStatus.VERIFIED,
                )
            },
            profile_version="1.0.0",
        )

    # CPRI Synthetic Benchmark v3.0.2 assets
    if clean_asset in CPRI_SYNTHETIC_ASSET_RATINGS:
        cadence = nominal_cadence_s or 1800  # 30 minutes nominal
        rating = rated_kva if rated_kva is not None else CPRI_SYNTHETIC_ASSET_RATINGS[clean_asset]
        return AssetProfile(
            asset_id=clean_asset,
            phase_topology="THREE_PHASE_4W",
            nominal_frequency_hz=50.0,
            rated_kva=rating,
            cooling_class="ONAN",
            insulation_paper_class=InsulationClass.UNKNOWN,
            expected_cadence_s=cadence,
            profile_status=ProfileVerificationStatus.UNVERIFIED,
            fields={
                "declared_rating_kva": ProfileField(
                    value=rating,
                    unit="kVA",
                    source_document="CPRI Synthetic Benchmark v3.0.2 Configuration",
                    status=ProfileVerificationStatus.VERIFIED,
                ),
                # Relative load index basis: the asset's own declared rating, never Tripura's P95 reference
                "load_reference_kva": ProfileField(
                    value=rating,
                    unit="kVA",
                    source_document="CPRI Synthetic Benchmark v3.0.2 Configuration",
                    status=ProfileVerificationStatus.VERIFIED,
                ),
            },
            profile_version="1.0.0",
        )

    # Generic asset (fallback)
    cadence = nominal_cadence_s if nominal_cadence_s is not None else (1800 if "cpri" in clean_ds.lower() else 900)
    profile_status = ProfileVerificationStatus.VERIFIED if rated_kva is not None else ProfileVerificationStatus.UNVERIFIED
    return AssetProfile(
        asset_id=clean_asset,
        phase_topology="THREE_PHASE_4W",
        nominal_frequency_hz=50.0,
        rated_kva=rated_kva,
        cooling_class="ONAN",
        insulation_paper_class=InsulationClass.UNKNOWN,
        expected_cadence_s=cadence,
        profile_status=profile_status,
        fields={},
        profile_version="1.0.0",
    )


def _apply_cpri_test_decision(
    artifact: CalibratedThermalModelArtifact,
    artifact_path: Path,
) -> CalibratedThermalModelArtifact:
    """Apply the standalone TEST promotion decision to a frozen CPRI candidate (in memory only).

    The frozen candidate carries provisional pre-TEST qualifications. Its TEST outcome lives in a
    separate report, bound to the artifact by SHA-256. Runtime must honour that outcome and the
    locked policy that residual anomaly evidence requires a passed signed-bias criterion.
    """
    promotion = artifact.promotion
    test_metrics = artifact.test_metrics
    test_bound = False
    report_path = artifact_path.with_name(f"test_evaluation_report_cpri_{artifact.asset_id.lower()}.json")
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            artifact_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            if report.get("frozen_artifact_sha256") == artifact_hash and report.get("asset_id") == artifact.asset_id:
                promotion = PromotionDecision(**report["promotion_decision"])
                test_metrics = BaselineMetricEntry(**report["primary_model_metrics"])
                test_bound = True
            else:
                logger.warning("TEST report %s is not bound to artifact %s; ignoring it.", report_path, artifact_path)
        except Exception as ex:
            logger.warning("Failed to read TEST report %s: %s", report_path, ex)

    qualification = artifact.qualification
    if test_bound and artifact.parameters and artifact.identifiability and artifact.conformal_uncertainty:
        # Post-TEST: the same locked matrix the full pipeline applies (calibration.derive_qualification_matrix)
        from app.engine.calibration import derive_qualification_matrix

        qualification = derive_qualification_matrix(
            artifact.identifiability, promotion, artifact.conformal_uncertainty, artifact.parameters
        )
    elif (
        qualification is not None
        and promotion.status != "PROMOTED"
        and not promotion.passes_bias_criterion
        and qualification.residual_anomaly_qualification == QualificationStatus.QUALIFIED
    ):
        qualification = qualification.model_copy(
            update={
                "residual_anomaly_qualification": QualificationStatus.NOT_QUALIFIED,
                "dimension_reasons": {
                    **qualification.dimension_reasons,
                    "residual_anomaly_qualification": (
                        "Residual anomaly evidence requires a passed signed-bias criterion; "
                        "candidate is not promoted."
                    ),
                },
            }
        )
    return artifact.model_copy(
        update={"promotion": promotion, "qualification": qualification, "test_metrics": test_metrics}
    )


def _apply_candidate_test_decision(
    artifact: CalibratedThermalModelArtifact,
    artifact_path: Path,
) -> CalibratedThermalModelArtifact:
    """Apply the standalone candidate TEST promotion decision to a frozen candidate (in memory only).

    Binds the artifact to its test_evaluation_report_candidate_{asset_id.lower()}.json by SHA-256 hash.
    Applies qualification matrix: DT-01 qualifies for forecasting & residual anomaly;
    DT-02..DT-04 stay gated (NOT_QUALIFIED) per Phase 6 gates.
    """
    promotion = artifact.promotion
    test_metrics = artifact.test_metrics
    test_bound = False
    clean_id = artifact.asset_id.lower()

    report_candidates = [
        artifact_path.with_name(f"test_evaluation_report_candidate_{clean_id}.json"),
        _REPO_ROOT / "data" / "candidates" / "gridpulse_synthetic_v1" / "artifacts" / f"test_evaluation_report_candidate_{clean_id}.json",
        Path("data/candidates/gridpulse_synthetic_v1/artifacts") / f"test_evaluation_report_candidate_{clean_id}.json",
        Path("/app/data/candidates/gridpulse_synthetic_v1/artifacts") / f"test_evaluation_report_candidate_{clean_id}.json",
    ]
    for report_path in report_candidates:
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
                artifact_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
                if report.get("frozen_artifact_sha256") == artifact_hash and report.get("asset_id") == artifact.asset_id:
                    promotion = PromotionDecision(**report["promotion_decision"])
                    test_metrics = BaselineMetricEntry(**report["primary_model_metrics"])
                    test_bound = True
                    break
                else:
                    logger.warning(
                        "Candidate TEST report %s is not bound to candidate artifact %s; ignoring it.",
                        report_path,
                        artifact_path,
                    )
            except Exception as ex:
                logger.warning("Failed to read candidate TEST report %s: %s", report_path, ex)

    qualification = artifact.qualification
    if test_bound and artifact.parameters and artifact.identifiability and artifact.conformal_uncertainty:
        from app.engine.calibration import derive_qualification_matrix

        qualification = derive_qualification_matrix(
            artifact.identifiability, promotion, artifact.conformal_uncertainty, artifact.parameters
        )
    elif (
        qualification is not None
        and promotion.status != "PROMOTED"
        and qualification.residual_anomaly_qualification == QualificationStatus.QUALIFIED
    ):
        qualification = qualification.model_copy(
            update={
                "residual_anomaly_qualification": QualificationStatus.NOT_QUALIFIED,
                "dimension_reasons": {
                    **qualification.dimension_reasons,
                    "residual_anomaly_qualification": "Candidate model is not promoted.",
                },
            }
        )
    return artifact.model_copy(
        update={"promotion": promotion, "qualification": qualification, "test_metrics": test_metrics}
    )


def resolve_model_artifact(
    dataset_id: Optional[str] = None,
    asset_id: str = "DT-TRIPURA-001",
) -> CalibratedThermalModelArtifact:
    """Resolve frozen calibrated model artifact strictly bound to (dataset_id, asset_id).

    Guarantees that Tripura calibration parameters are never used for other assets.
    """
    clean_asset = str(asset_id).strip()
    if dataset_id is not None:
        clean_ds = str(dataset_id).strip()
    elif clean_asset in ("DT-TRIPURA-001", "tripura_dt_01", "TRIPURA_DTR_01"):
        clean_ds = "tripura_dev"
    elif clean_asset in CPRI_SYNTHETIC_ASSET_RATINGS:
        clean_ds = "cpri_v3_0_2"
    elif clean_asset in GRIDPULSE_CANDIDATE_ASSETS or clean_asset in SYNTHETIC_ASSET_PROFILES:
        clean_ds = "gridpulse_synthetic_v1"
    else:
        clean_ds = "unspecified_dataset"

    # GridPulse Synthetic Candidate asset artifact resolution
    is_candidate_asset = clean_asset in GRIDPULSE_CANDIDATE_ASSETS or clean_asset in SYNTHETIC_ASSET_PROFILES
    is_candidate_dataset = clean_ds.lower() in ("gridpulse_synthetic_v1", "gridpulse_synthetic", "gridpulse")

    if is_candidate_asset or is_candidate_dataset:
        clean_id = clean_asset.lower()
        candidate_paths = [
            Path(f"data/candidates/gridpulse_synthetic_v1/artifacts/calibrated_thermal_model_candidate_{clean_id}.json"),
            _REPO_ROOT / f"data/candidates/gridpulse_synthetic_v1/artifacts/calibrated_thermal_model_candidate_{clean_id}.json",
            Path(f"/app/data/candidates/gridpulse_synthetic_v1/artifacts/calibrated_thermal_model_candidate_{clean_id}.json"),
            Path(f"data/processed/calibrated_thermal_model_candidate_{clean_id}.json"),
            _REPO_ROOT / f"data/processed/calibrated_thermal_model_candidate_{clean_id}.json",
            Path(f"/app/data/processed/calibrated_thermal_model_candidate_{clean_id}.json"),
        ]
        for candidate_path in candidate_paths:
            if candidate_path.exists():
                try:
                    loaded = CalibratedThermalModelArtifact.load_json(candidate_path)
                    if loaded.asset_id == clean_asset and loaded.dataset_id in (
                        "gridpulse_synthetic_v1",
                        "gridpulse_synthetic",
                    ):
                        return _apply_candidate_test_decision(loaded, candidate_path)
                    logger.warning(
                        "Candidate artifact identity mismatch at %s: asset=%s (expected %s), dataset=%s; rejecting.",
                        candidate_path,
                        loaded.asset_id,
                        clean_asset,
                        loaded.dataset_id,
                    )
                except Exception as ex:
                    logger.warning("Failed to load candidate artifact at %s: %s", candidate_path, ex)
                    break

        # Explicit error prevention: do NOT silently fallback to CPRI or Tripura
        logger.error(
            "Candidate artifact for asset %s in dataset %s could not be loaded from %s. Returning uncalibrated candidate artifact.",
            clean_asset,
            clean_ds,
            candidate_paths[0],
        )
        return CalibratedThermalModelArtifact.create_uncalibrated(
            dataset_id="gridpulse_synthetic_v1",
            asset_id=clean_asset,
        )

    is_tripura_asset = clean_asset in ("DT-TRIPURA-001", "tripura_dt_01", "TRIPURA_DTR_01")
    is_tripura_dataset = clean_ds.lower() in ("tripura", "tripura_dev", "tripura_csv")

    if is_tripura_asset and is_tripura_dataset:
        # Load Tripura calibrated artifact if exists on disk
        for candidate_path in [
            Path("data/processed/calibrated_thermal_model.json"),
            _REPO_ROOT / "data/processed/calibrated_thermal_model.json",
            Path("/app/data/processed/calibrated_thermal_model.json"),
        ]:
            if candidate_path.exists():
                try:
                    loaded = CalibratedThermalModelArtifact.load_json(candidate_path)
                    return loaded.model_copy(update={"asset_id": clean_asset, "dataset_id": clean_ds})
                except Exception:
                    break

        from app.api.deps import build_default_model_artifact
        return build_default_model_artifact(dataset_id=clean_ds, asset_id=clean_asset)

    # CPRI asset artifact resolution
    if clean_asset in CPRI_SYNTHETIC_ASSET_RATINGS or "cpri" in clean_ds.lower():
        # Match strictly the target asset's file paths; NEVER borrow another asset's artifact
        candidate_paths = [
            Path(f"data/processed/calibrated_thermal_model_cpri_{clean_asset.lower()}.json"),
            _REPO_ROOT / f"data/processed/calibrated_thermal_model_cpri_{clean_asset.lower()}.json",
            Path(f"/app/data/processed/calibrated_thermal_model_cpri_{clean_asset.lower()}.json"),
        ]
        for candidate_path in candidate_paths:
            if candidate_path.exists():
                try:
                    loaded = CalibratedThermalModelArtifact.load_json(candidate_path)
                    # Explicit identity validation: artifact asset_id and dataset_id must match
                    if loaded.asset_id == clean_asset and loaded.dataset_id in ("cpri_v3_0_2", "cpri_v3"):
                        return _apply_cpri_test_decision(loaded, candidate_path)
                    logger.warning(
                        "CPRI artifact identity mismatch at %s: asset=%s (expected %s), dataset=%s; rejecting.",
                        candidate_path,
                        loaded.asset_id,
                        clean_asset,
                        loaded.dataset_id,
                    )
                except Exception as ex:
                    logger.warning("Failed to load CPRI artifact at %s: %s", candidate_path, ex)
                    break

        return CalibratedThermalModelArtifact.create_uncalibrated(
            dataset_id="cpri_v3_0_2",
            asset_id=clean_asset,
        )

    # Any other asset/dataset combination: MUST NOT reuse Tripura constants
    return CalibratedThermalModelArtifact.create_uncalibrated(
        dataset_id=clean_ds,
        asset_id=clean_asset,
    )
