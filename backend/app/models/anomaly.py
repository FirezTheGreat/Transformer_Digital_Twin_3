"""Anomaly Evidence Items and Episode State Machine Models."""

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class AnomalyCategory(str, Enum):
    """The 8 canonical operator-facing anomaly evidence categories."""
    DATA_QUALITY = "DATA_QUALITY"
    SENSOR_PLAUSIBILITY = "SENSOR_PLAUSIBILITY"
    THERMAL_DEVIATION = "THERMAL_DEVIATION"
    THERMAL_LIMIT = "THERMAL_LIMIT"
    LOADING = "LOADING"
    PHASE_OR_NEUTRAL = "PHASE_OR_NEUTRAL"
    VOLTAGE_PF_FREQUENCY = "VOLTAGE_PF_FREQUENCY"
    PROTECTION_OR_OIL_STATUS = "PROTECTION_OR_OIL_STATUS"


class EpisodeState(str, Enum):
    """The 6 exact frozen states of the episode lifecycle FSM."""
    NORMAL = "NORMAL"
    WATCH = "WATCH"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    RECOVERING = "RECOVERING"
    CLOSED = "CLOSED"


class EvidenceItem(BaseModel):
    """Individual typed evidence item emitted by a detector."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(..., description="Unique deterministic evidence ID")
    asset_id: str = Field(..., description="Transformer asset identifier")
    event_time_utc: datetime = Field(..., description="Timestamp of the triggering event in UTC")
    category: AnomalyCategory = Field(..., description="One of the 8 canonical categories")
    detector_id: str = Field(..., description="ID of the detector that generated this evidence")
    observed_value: Any = Field(..., description="Observed measurement or feature value")
    expected_value: Any | None = Field(default=None, description="Expected value or baseline if applicable")
    unit: str | None = Field(default=None, description="Physical unit of observed/expected values")
    threshold_or_band: str | None = Field(default=None, description="Configured limit, band, or decision threshold")
    direction: str | None = Field(default=None, description="Deviation direction (e.g. HIGH, LOW, POSITIVE_SHIFT)")
    severity: float = Field(..., ge=0.0, le=1.0, description="Normalized severity score in [0.0, 1.0]")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detector confidence in [0.0, 1.0]")
    input_lineage: list[str] = Field(default_factory=list, description="IDs of source measurements/events used")
    reason_codes: list[str] = Field(default_factory=list, description="Deterministic reason codes")
    hypothesis_codes: list[str] = Field(default_factory=list, description="Non-assertive possible explanatory hypotheses")
    condition_family: str | None = Field(default=None, description="Condition family grouping for multi-domain deduplication")
    domain: str | None = Field(default=None, description="Canonical OTHI domain if applicable")
    derivation_type: str = Field(default="DIRECT_OBSERVATION", description="Derivation type (DIRECT_OBSERVATION, DERIVED_FEATURE, MODEL_DERIVED, PROTECTION_DISCRETE, OPERATOR_ACTION)")
    upstream_evidence_ids: list[str] = Field(default_factory=list, description="IDs of upstream evidence items in causal/derivation graph")
    rule_or_model_version: str = Field(default="1.0.0", description="Version of emitting rule or engine")


class AnomalyEpisode(BaseModel):
    """Stateful operational anomaly incident tracked across time."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    episode_id: str = Field(..., description="Unique episode identifier")
    asset_id: str = Field(..., description="Transformer asset identifier")
    state: EpisodeState = Field(..., description="Current FSM state of the episode")
    category: AnomalyCategory = Field(..., description="Primary anomaly category driving this incident")
    severity_score: float = Field(..., ge=0.0, le=1.0, description="Highest active severity in [0.0, 1.0]")
    start_time_utc: datetime = Field(..., description="Initial detection timestamp in UTC")
    last_seen_time_utc: datetime = Field(..., description="Most recent evidence timestamp in UTC")
    recovery_start_time_utc: datetime | None = Field(default=None, description="Timestamp when recovery criteria were first met")
    closed_time_utc: datetime | None = Field(default=None, description="Timestamp when episode was formally closed")
    evidence_ids: list[str] = Field(default_factory=list, description="All evidence item IDs associated with this episode")
    is_monitoring_gap: bool = Field(default=False, description="Whether this episode is currently frozen due to a data gap")
    primary_reason: str = Field(..., description="Human-readable primary cause description")
    hypothesis_codes: list[str] = Field(default_factory=list, description="Accumulated hypotheses")
