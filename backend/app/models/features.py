"""Derived Physical and Electrical Features."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DerivedFeatures(BaseModel):
    """Deterministic engineering features derived from valid canonical measurements."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp_utc: datetime = Field(..., description="Timestamp of the feature frame in UTC")
    apparent_power_derived_kva: float | None = Field(default=None, ge=0.0, description="Derived total apparent power sqrt(P^2 + Q^2) in kVA")
    power_factor_derived: float | None = Field(default=None, ge=0.0, le=1.0, description="Derived power factor P / S")
    current_mean_a: float | None = Field(default=None, ge=0.0, description="Mean three-phase RMS current in A")
    current_magnitude_imbalance_pct: float | None = Field(default=None, ge=0.0, description="NEMA current magnitude imbalance percentage")
    voltage_magnitude_imbalance_pct: float | None = Field(default=None, ge=0.0, description="NEMA voltage magnitude imbalance percentage")
    neutral_current_ratio: float | None = Field(default=None, ge=0.0, description="Neutral current ratio In / max(Ieq, floor)")
    pqs_inconsistency: float | None = Field(default=None, ge=0.0, description="P-Q-S inconsistency metric")
    relative_load_index: float | None = Field(default=None, ge=0.0, description="Relative load index u = S / S_ref")
    thermal_residual_degc: float | None = Field(default=None, description="Free-running top-oil residual (T_observed - T_expected) in Cel")
    transform_version: str = Field(default="1.0.0", description="Version of feature transform equations")
