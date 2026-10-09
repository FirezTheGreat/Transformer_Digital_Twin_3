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

from pathlib import Path
from typing import Optional

from app.models.profile import (
    AssetProfile,
    InsulationClass,
    ProfileField,
    ProfileVerificationStatus,
)
from app.models.thermal_artifact import (
    CalibratedThermalModelArtifact,
)


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
    else:
        clean_ds = "unspecified_dataset"

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
                )
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
    else:
        clean_ds = "unspecified_dataset"

    is_tripura_asset = clean_asset in ("DT-TRIPURA-001", "tripura_dt_01", "TRIPURA_DTR_01")
    is_tripura_dataset = clean_ds.lower() in ("tripura", "tripura_dev", "tripura_csv")

    if is_tripura_asset and is_tripura_dataset:
        # Load Tripura calibrated artifact if exists on disk
        for candidate_path in [
            Path("data/processed/calibrated_thermal_model.json"),
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
            Path(f"/app/data/processed/calibrated_thermal_model_cpri_{clean_asset.lower()}.json"),
        ]
        for candidate_path in candidate_paths:
            if candidate_path.exists():
                try:
                    loaded = CalibratedThermalModelArtifact.load_json(candidate_path)
                    # Explicit identity validation: artifact asset_id and dataset_id must match
                    if loaded.asset_id == clean_asset and loaded.dataset_id in ("cpri_v3_0_2", "cpri_v3"):
                        return loaded
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
