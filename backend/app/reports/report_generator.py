"""Deterministic Report Data Generator & Facts Pipeline (Phase 9.1).

Transforms authoritative immutable FactBundle instances into a unified,
deterministic ReportData structure for downstream JSON, CSV, and PDF exporters.

Architecture Principle:
FactBundle -> Report Generator -> Unified Report Data -> Exporters (JSON / CSV / PDF)
ZERO METRIC RECALCULATION: All values are copied/referenced strictly from FactBundle.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.anomaly import AnomalyEpisode
from app.models.capability import CapabilityManifest
from app.models.fact_bundle import FactBundle
from app.models.features import DerivedFeatures
from app.models.health import OTHIBundle
from app.models.maintenance import MaintenanceRecommendation
from app.models.telemetry import Measurement
from app.models.twin_state import DetectorState, ExposureState, ThermalLatentState


class ReportMetadata(BaseModel):
    """Metadata describing the generated report document."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    report_id: str = Field(..., description="Unique deterministic report identifier")
    schema_version: str = Field(default="1.0.0", description="Report structure schema version")
    generator_version: str = Field(default="1.0.0", description="Report generator software version")
    generated_at_utc: datetime = Field(..., description="Timestamp when report was generated in UTC")
    fact_bundle_id: str = Field(..., description="Source FactBundle identifier")
    bundle_version: str = Field(..., description="Source FactBundle schema version")
    provenance_hash: str = Field(..., description="Provenance SHA-256 hash from source FactBundle")
    state_hash: str = Field(..., description="State checkpoint SHA-256 hash from TwinState")


class AssetIdentity(BaseModel):
    """Asset identification and naming context."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str = Field(..., description="Transformer asset identifier")
    dataset_id: str = Field(..., description="Source dataset identifier")

    @model_validator(mode="before")
    @classmethod
    def _handle_legacy(cls, data: Any) -> Any:
        if isinstance(data, dict) and "dataset_id" not in data:
            data["dataset_id"] = "tripura_dev"
        return data


class ReportTimestamps(BaseModel):
    """State, event watermark, and snapshot timestamps."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    state_time_utc: datetime = Field(..., description="Logical timestamp of the twin state in UTC")
    event_time_watermark_utc: datetime = Field(..., description="Event time watermark in UTC")
    fact_bundle_timestamp_utc: datetime = Field(..., description="Snapshot timestamp of FactBundle in UTC")


class ThermalSummary(BaseModel):
    """Thermal condition summary projected directly from FactBundle without recalculation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    top_oil_observed_degc: float | None = Field(
        default=None, description="Observed top-oil temperature in Cel, or null if unavailable"
    )
    top_oil_expected_degc: float | None = Field(
        default=None, description="One-step expected top-oil temperature from ODE in Cel, or null if unavailable"
    )
    thermal_residual_degc: float | None = Field(
        default=None, description="Top-oil residual (T_observed - T_expected) from derived electrical features"
    )
    last_free_running_top_oil_degc: float | None = Field(
        default=None, description="Continuous free-running ODE state without measurement resets"
    )
    time_constant_tau_hours: float = Field(
        ..., description="Calibrated oil thermal time constant tau in hours"
    )
    warmup_samples_remaining: int = Field(
        ..., description="Warmup samples remaining before residual escalation"
    )
    model_status: str = Field(
        ..., description="Status of thermal ODE model (e.g. PROMOTED, FALLBACK_PERSISTENCE)"
    )
    conformal_interval_lower_degc: float | None = Field(
        default=None, description="Lower 90% empirical conformal bound in Cel"
    )
    conformal_interval_upper_degc: float | None = Field(
        default=None, description="Upper 90% empirical conformal bound in Cel"
    )


class ElectricalSummary(BaseModel):
    """Derived electrical features directly from FactBundle without recalculation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp_utc: datetime = Field(..., description="Timestamp of feature frame in UTC")
    apparent_power_derived_kva: float | None = Field(default=None, description="Apparent power in kVA")
    power_factor_derived: float | None = Field(default=None, description="Power factor P / S")
    current_mean_a: float | None = Field(default=None, description="Mean 3-phase RMS current in A")
    current_magnitude_imbalance_pct: float | None = Field(
        default=None, description="NEMA current magnitude imbalance percentage"
    )
    voltage_magnitude_imbalance_pct: float | None = Field(
        default=None, description="NEMA voltage magnitude imbalance percentage"
    )
    neutral_current_ratio: float | None = Field(default=None, description="Neutral current ratio In / max(Ieq, floor)")
    pqs_inconsistency: float | None = Field(default=None, description="P-Q-S inconsistency metric")
    relative_load_index: float | None = Field(default=None, description="Relative load index u = S / S_ref")
    thermal_residual_degc: float | None = Field(default=None, description="Top-oil residual in Cel")
    transform_version: str = Field(default="1.0.0", description="Version of feature transform equations")


class ReportData(BaseModel):
    """Unified deterministic report data contract.
    
    Serves as the single authoritative source of truth for all downstream report
    renderers (JSON, CSV, PDF). Guaranteed identical for identical FactBundle inputs.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: ReportMetadata = Field(..., description="Report generation and provenance metadata")
    asset: AssetIdentity = Field(..., description="Asset identity details")
    timestamps: ReportTimestamps = Field(..., description="Synchronized state and watermark timestamps")
    current_observations: dict[str, Measurement] = Field(
        default_factory=dict, description="Current valid physical measurements by signal ID"
    )
    thermal: ThermalSummary = Field(..., description="Thermal state and latent ODE parameters")
    electrical: ElectricalSummary | None = Field(
        default=None, description="Derived electrical features, or null if uncomputed"
    )
    health: OTHIBundle = Field(..., description="Domain health breakdown, evidence grades, and gated OTHI")
    capabilities: CapabilityManifest = Field(..., description="Active capability tier manifest")
    open_episodes: list[AnomalyEpisode] = Field(
        default_factory=list, description="Currently active anomaly episodes"
    )
    active_recommendations: list[MaintenanceRecommendation] = Field(
        default_factory=list, description="Active prioritized maintenance recommendations"
    )
    exposure: ExposureState = Field(..., description="Cumulative thermal exposure and equivalent aging state")
    detectors: DetectorState = Field(..., description="Detector and CUSUM accumulator state")
    versions: dict[str, str] = Field(
        default_factory=dict, description="Component, schema, and rule version dictionary"
    )
    state_sequence: int = Field(..., description="Monotonically increasing state transition counter")
    last_processed_event_id: str = Field(..., description="ID of last processed canonical event")
    provenance_hash: str = Field(..., description="SHA-256 provenance hash from source FactBundle")
    state_hash: str = Field(..., description="SHA-256 state checkpoint hash from TwinState")


def generate_report_data(
    fact_bundle: FactBundle,
    report_id: str | None = None,
    dataset_id: str | None = None,
    generated_at_utc: datetime | None = None,
    schema_version: str = "1.0.0",
    generator_version: str = "1.0.0",
) -> ReportData:
    """Transform an authoritative immutable FactBundle into a deterministic ReportData structure.
    
    Pure function with zero side effects:
    - Does NOT recalculate any engineering metric (OTHI, residual, severity, CUSUM, etc.)
    - Does NOT access databases, networks, or local filesystem
    - Does NOT mutate the input FactBundle
    - Preserves all unavailable / None fields explicitly
    - Guarantees exact determinism given identical inputs
    
    Args:
        fact_bundle: Authoritative immutable snapshot.
        report_id: Optional custom report identifier; defaults to deterministic `rep-{asset_id}-{seq:06d}`.
        generated_at_utc: Optional report generation timestamp; defaults to `fact_bundle.timestamp_utc`.
        schema_version: Report schema version string.
        generator_version: Generator engine version string.
        
    Returns:
        ReportData: Fully populated, immutable report structure.
    """
    state = fact_bundle.twin_state
    effective_gen_time = generated_at_utc or fact_bundle.timestamp_utc
    effective_report_id = report_id or f"rep-{fact_bundle.asset_id}-{state.state_sequence:06d}"

    # Extract observed top-oil temperature directly if available in current_observations
    top_oil_obs_val: float | None = None
    if "top_oil_temperature" in state.current_observations:
        raw_val = state.current_observations["top_oil_temperature"].value
        if isinstance(raw_val, (int, float)):
            top_oil_obs_val = float(raw_val)

    # Copy thermal latent values without recalculation
    tl = state.thermal_latent
    thermal_residual = (
        state.derived_electrical.thermal_residual_degc
        if state.derived_electrical is not None
        else None
    )

    thermal_summary = ThermalSummary(
        top_oil_observed_degc=top_oil_obs_val,
        top_oil_expected_degc=tl.top_oil_expected_degc,
        thermal_residual_degc=thermal_residual,
        last_free_running_top_oil_degc=tl.last_free_running_top_oil_degc,
        time_constant_tau_hours=tl.time_constant_tau_hours,
        warmup_samples_remaining=tl.warmup_samples_remaining,
        model_status=tl.model_status,
        conformal_interval_lower_degc=tl.conformal_interval_lower_degc,
        conformal_interval_upper_degc=tl.conformal_interval_upper_degc,
    )

    # Copy derived electrical features if present
    electrical_summary: ElectricalSummary | None = None
    if state.derived_electrical is not None:
        de = state.derived_electrical
        electrical_summary = ElectricalSummary(
            timestamp_utc=de.timestamp_utc,
            apparent_power_derived_kva=de.apparent_power_derived_kva,
            power_factor_derived=de.power_factor_derived,
            current_mean_a=de.current_mean_a,
            current_magnitude_imbalance_pct=de.current_magnitude_imbalance_pct,
            voltage_magnitude_imbalance_pct=de.voltage_magnitude_imbalance_pct,
            neutral_current_ratio=de.neutral_current_ratio,
            pqs_inconsistency=de.pqs_inconsistency,
            relative_load_index=de.relative_load_index,
            thermal_residual_degc=de.thermal_residual_degc,
            transform_version=de.transform_version,
        )

    # Build report metadata
    metadata = ReportMetadata(
        report_id=effective_report_id,
        schema_version=schema_version,
        generator_version=generator_version,
        generated_at_utc=effective_gen_time,
        fact_bundle_id=fact_bundle.fact_bundle_id,
        bundle_version=fact_bundle.bundle_version,
        provenance_hash=fact_bundle.provenance_hash,
        state_hash=state.state_hash,
    )

    # Build report timestamps
    timestamps = ReportTimestamps(
        state_time_utc=state.state_time_utc,
        event_time_watermark_utc=state.event_time_watermark_utc,
        fact_bundle_timestamp_utc=fact_bundle.timestamp_utc,
    )

    # Construct unified immutable ReportData
    resolved_ds = (
        dataset_id
        or state.versions.get("dataset_id")
        or ("gridpulse_synthetic_v1" if fact_bundle.asset_id in ("DT-01", "DT-02", "DT-03", "DT-04")
            else "cpri_v3_0_2" if fact_bundle.asset_id.startswith("TX_")
            else "tripura_dev" if fact_bundle.asset_id in ("DT-TRIPURA-001", "tripura_dt_01")
            else "unspecified_dataset")
    )

    return ReportData(
        metadata=metadata,
        asset=AssetIdentity(asset_id=fact_bundle.asset_id, dataset_id=resolved_ds),
        timestamps=timestamps,
        current_observations=dict(state.current_observations),
        thermal=thermal_summary,
        electrical=electrical_summary,
        health=fact_bundle.health,
        capabilities=fact_bundle.capabilities,
        open_episodes=list(fact_bundle.open_episodes),
        active_recommendations=list(fact_bundle.active_recommendations),
        exposure=state.exposure_state,
        detectors=state.detector_state,
        versions=dict(state.versions),
        state_sequence=state.state_sequence,
        last_processed_event_id=state.last_processed_event_id,
        provenance_hash=fact_bundle.provenance_hash,
        state_hash=state.state_hash,
    )


__all__ = [
    "ReportMetadata",
    "AssetIdentity",
    "ReportTimestamps",
    "ThermalSummary",
    "ElectricalSummary",
    "ReportData",
    "generate_report_data",
]
