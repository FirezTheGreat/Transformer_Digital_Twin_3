"""Stateful Digital Twin Representation and State Vector Models."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.models.telemetry import Measurement
from app.models.features import DerivedFeatures
from app.models.anomaly import AnomalyEpisode
from app.models.health import OTHIBundle
from app.models.maintenance import MaintenanceRecommendation


class ThermalLatentState(BaseModel):
    """Internal latent state of the grey-box thermal ODE."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    top_oil_expected_degc: float | None = Field(default=None, description="One-step expected top-oil temperature in Cel")
    last_free_running_top_oil_degc: float | None = Field(default=None, description="Continuous free-running ODE state without measurement resets")
    time_constant_tau_hours: float = Field(default=3.0, gt=0.0, description="Calibrated oil thermal time constant tau in hours")
    warmup_samples_remaining: int = Field(default=0, ge=0, description="Warmup samples remaining before residual escalation")
    model_status: str = Field(default="PROMOTED", description="Status of grey-box model (e.g. PROMOTED, FALLBACK_PERSISTENCE)")
    conformal_interval_lower_degc: float | None = Field(default=None, description="Lower 90% empirical conformal bound")
    conformal_interval_upper_degc: float | None = Field(default=None, description="Upper 90% empirical conformal bound")


class DetectorState(BaseModel):
    """Stateful accumulators for statistical and anomaly detectors."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    cusum_pos: float = Field(default=0.0, ge=0.0, description="Positive standardized residual CUSUM accumulator")
    cusum_neg: float = Field(default=0.0, le=0.0, description="Negative standardized residual CUSUM accumulator")
    cusum_alarm_active: bool = Field(default=False, description="Whether CUSUM decision limit h is currently tripped")
    persistence_timers: dict[str, float] = Field(default_factory=dict, description="Active anomaly persistence duration counters in seconds")
    cooldown_timers: dict[str, float] = Field(default_factory=dict, description="Recovery hysteresis duration counters in seconds")


class ExposureState(BaseModel):
    """Cumulative thermal exposure and equivalent aging hours."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    time_above_bands_s: dict[str, float] = Field(default_factory=dict, description="Seconds spent above temperature threshold bands")
    equivalent_ageing_hours: float | None = Field(default=None, ge=0.0, description="Cumulative equivalent aging hours Leq if enabled, else null")
    is_ageing_enabled: bool = Field(default=False, description="True only when verified insulation class & hot-spot exist")


class TwinState(BaseModel):
    """Complete synchronized deterministic state representation of the transformer."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str = Field(..., description="Transformer asset identifier")
    state_time_utc: datetime = Field(..., description="Logical timestamp of the twin state in UTC")
    last_processed_event_id: str = Field(..., description="ID of the last canonical event reduced into state")
    event_time_watermark_utc: datetime = Field(..., description="Current event-time watermark timestamp in UTC")
    state_sequence: int = Field(..., ge=0, description="Monotonically increasing state transition counter")
    current_observations: dict[str, Measurement] = Field(default_factory=dict, description="Most recent valid observations by signal ID")
    derived_electrical: DerivedFeatures | None = Field(default=None, description="Derived electrical features")
    thermal_latent: ThermalLatentState = Field(default_factory=ThermalLatentState, description="Thermal grey-box ODE state")
    detector_state: DetectorState = Field(default_factory=DetectorState, description="Detector and CUSUM accumulators")
    open_episodes: list[AnomalyEpisode] = Field(default_factory=list, description="Currently active and recovering anomaly episodes")
    health_bundle: OTHIBundle | None = Field(default=None, description="Current operational health index assessment")
    exposure_state: ExposureState = Field(default_factory=ExposureState, description="Cumulative exposure state")
    active_recommendations: list[MaintenanceRecommendation] = Field(default_factory=list, description="Active advisory maintenance recommendations")
    versions: dict[str, str] = Field(default_factory=dict, description="Versions of schema, profile, model, and rules")
    state_hash: str = Field(..., description="Deterministic SHA-256 state checkpoint hash")
