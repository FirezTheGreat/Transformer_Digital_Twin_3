"""Phase 4.4 — 2-Hour What-If Scenario Projection Models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ThermalTrustState(str, Enum):
    """Operational capability trust states for the thermal model."""
    MODEL_HEALTHY = "MODEL_HEALTHY"
    SHADOW_DESCRIPTIVE = "SHADOW_DESCRIPTIVE"
    WARMUP = "WARMUP"
    FALLBACK_PERSISTENCE = "FALLBACK_PERSISTENCE"


class ScenarioRequest(BaseModel):
    """Input parameters for a hypothetical 2-hour what-if scenario."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_load_u: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Hypothetical load index u (e.g. 0.80 for 80% reference load). Overrides load_multiplier if set.",
    )
    load_multiplier: Optional[float] = Field(
        default=1.0,
        ge=0.0,
        description="Multiplier applied to current observed load index (e.g. 1.20 for +20% load step).",
    )
    target_load_value: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Hypothetical raw load driver value in physical units (e.g. Amperes or kVA).",
    )
    target_ambient_degc: Optional[float] = Field(
        default=None,
        ge=-40.0,
        le=70.0,
        description="Hypothetical ambient temperature in degC. Overrides ambient_delta_degc if set.",
    )
    ambient_delta_degc: Optional[float] = Field(
        default=0.0,
        ge=-30.0,
        le=30.0,
        description="Temperature delta added to current observed ambient in degC (e.g. +5.0 degC heatwave).",
    )
    warning_threshold_degc: Optional[float] = Field(
        default=85.0,
        description="Top-oil temperature threshold for warning limit crossing detection in degC.",
    )
    critical_threshold_degc: Optional[float] = Field(
        default=95.0,
        description="Top-oil temperature threshold for critical limit crossing detection in degC.",
    )
    horizon_steps: int = Field(
        default=8,
        ge=1,
        le=8,
        description="Requested projection steps; capped at the model's calibrated 2-hour steps (8 x 15 min or 4 x 30 min).",
    )


class ScenarioProjectionStep(BaseModel):
    """Individual 15-minute step in the 2-hour forward projection trajectory."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    horizon_step: int = Field(..., ge=1, le=8, description="Step index h in 1..8")
    horizon_minutes: int = Field(..., description="Elapsed minutes from forecast origin (15..120)")
    projected_time_utc: datetime = Field(..., description="Timestamp of the projected step in UTC")
    projected_top_oil_degc: float = Field(..., description="Projected top-oil temperature in degC")
    projected_rise_over_ambient_degc: float = Field(..., description="Projected top-oil rise over scenario ambient in degC")
    asymptotic_steady_state_degc: float = Field(..., description="Asymptotic steady-state top-oil temperature theta* under scenario drive in degC")
    conformal_lower_degc: float = Field(..., description="Lower empirical 90% conformal bound in degC")
    conformal_upper_degc: float = Field(..., description="Upper empirical 90% conformal bound in degC")
    conformal_half_width_degc: float = Field(..., description="Empirical conformal half-width W_h in degC")
    baseline_top_oil_degc: Optional[float] = Field(default=None, description="Projected top-oil under baseline (unmodified) operating conditions in degC")
    scenario_delta_degc: Optional[float] = Field(default=None, description="What-if projected top-oil minus baseline projected top-oil in degC")


class ScenarioProjectionResult(BaseModel):
    """Complete structured response for a 2-hour what-if scenario projection."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str = Field(..., description="Transformer asset identifier")
    origin_time_utc: datetime = Field(..., description="Forecast origin timestamp in UTC")
    origin_top_oil_degc: float = Field(..., description="Top-oil temperature at forecast origin in degC")
    origin_ambient_degc: float = Field(..., description="Ambient temperature at forecast origin in degC")
    origin_load_u: float = Field(..., description="Load index at forecast origin")
    scenario_ambient_degc: float = Field(..., description="Assumed constant ambient temperature for the scenario in degC")
    scenario_load_u: float = Field(..., description="Assumed constant load index for the scenario")
    is_enabled: bool = Field(..., description="Whether scenario projection is enabled under current capability/trust state")
    trust_state: ThermalTrustState = Field(..., description="Active thermal model capability trust state at forecast origin")
    disabled_reason: Optional[str] = Field(default=None, description="Explicit explanation when scenario projection is disabled")
    is_extrapolated: bool = Field(default=False, description="Whether scenario inputs exceed the calibrated operating domain")
    extrapolation_warning: Optional[str] = Field(default=None, description="Warning message describing extrapolation conditions if applicable")
    trajectory: List[ScenarioProjectionStep] = Field(default_factory=list, description="8-step forward projection trajectory")
    peak_projected_top_oil_degc: Optional[float] = Field(default=None, description="Peak top-oil temperature across the 2-hour projection in degC")
    asymptotic_steady_state_degc: Optional[float] = Field(default=None, description="Long-run steady-state top-oil temperature under scenario drive in degC")
    earliest_warning_crossing_minutes: Optional[int] = Field(default=None, description="Minutes to earliest warning threshold crossing, or null if none")
    earliest_critical_crossing_minutes: Optional[int] = Field(default=None, description="Minutes to earliest critical threshold crossing, or null if none")
    time_above_warning_minutes: int = Field(default=0, ge=0, description="Total projected duration above warning threshold within 2-hour window in minutes")
    time_above_critical_minutes: int = Field(default=0, ge=0, description="Total projected duration above critical threshold within 2-hour window in minutes")
    provenance: dict[str, Any] = Field(default_factory=dict, description="Provenance metadata including model version, parameters, and conformal bounds")
