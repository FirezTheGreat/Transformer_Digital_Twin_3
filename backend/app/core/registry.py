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

    # Generic asset (CPRI or other)
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

    # Any other asset/dataset combination: MUST NOT reuse Tripura constants
    return CalibratedThermalModelArtifact.create_uncalibrated(
        dataset_id=clean_ds,
        asset_id=clean_asset,
    )
