"""Phase 5.1 — Electrical Anomaly Episode Data Models & Contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.anomaly import AnomalyCategory, AnomalyEpisode, EpisodeState, EvidenceItem


class ElectricalEpisodeType(str, Enum):
    """The 5 canonical electrical abnormal conditions tracked as temporal episodes."""
    CURRENT_IMBALANCE = "CURRENT_IMBALANCE"
    VOLTAGE_IMBALANCE = "VOLTAGE_IMBALANCE"
    NEUTRAL_CURRENT_RATIO = "NEUTRAL_CURRENT_RATIO"
    LOW_POWER_FACTOR = "LOW_POWER_FACTOR"
    PQS_INCONSISTENCY = "PQS_INCONSISTENCY"


class EpisodeSeverity(str, Enum):
    """Deterministic severity levels for electrical episodes."""
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class EpisodeStatus(str, Enum):
    """FSM lifecycle status of an individual episode."""
    CANDIDATE = "CANDIDATE"      # Condition detected, accumulating persistence timer
    ACTIVE = "ACTIVE"            # Persisted >= configured threshold, actively monitored
    RECOVERING = "RECOVERING"    # Below recovery threshold T_off, cooling down
    CLOSED = "CLOSED"            # Recovery period completed, finalized and archived


class EvidenceGrade(str, Enum):
    """Evidence grading reflecting physical verification vs data quality."""
    GRADE_A_PHYSICAL = "GRADE_A_PHYSICAL"        # Direct physical electrical measurement excursion
    GRADE_B_DATA_QUALITY = "GRADE_B_DATA_QUALITY"  # Instrumentation/meter inconsistency evidence
    GRADE_C_ASSUMPTION = "GRADE_C_ASSUMPTION"      # Engineering assumption / unrated threshold


class ElectricalEpisodeThresholds(BaseModel):
    """Configurable engineering/demo thresholds with explicit assumption labels."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    warning_threshold: float = Field(..., description="Activation threshold T_on for WARNING severity")
    critical_threshold: float = Field(..., description="Escalation threshold for CRITICAL severity")
    recovery_threshold: float = Field(..., description="Deactivation threshold T_off for recovery (hysteresis)")
    min_load_kva: float = Field(default=0.0, ge=0.0, description="Minimum apparent power kVA required to evaluate condition")
    min_current_a: float = Field(default=0.0, ge=0.0, description="Minimum mean phase current A required to evaluate condition")
    persistence_seconds: float = Field(default=900.0, ge=0.0, description="Required continuous duration in seconds before becoming ACTIVE")
    recovery_seconds: float = Field(default=900.0, ge=0.0, description="Required continuous clean duration in seconds before CLOSING")
    threshold_provenance: str = Field(
        default="CONFIGURED_ENGINEERING_ASSUMPTION",
        description="Explicit provenance label distinguishing assumptions from verified nameplate/standards",
    )


# ---------------------------------------------------------------------------
# Default Configured Engineering Thresholds (CONFIGURED / ASSUMPTIONS)
# ---------------------------------------------------------------------------
DEFAULT_ELECTRICAL_THRESHOLDS: Dict[ElectricalEpisodeType, ElectricalEpisodeThresholds] = {
    ElectricalEpisodeType.CURRENT_IMBALANCE: ElectricalEpisodeThresholds(
        warning_threshold=10.0,   # 10% NEMA current imbalance
        critical_threshold=25.0,  # 25% severe unbalance
        recovery_threshold=8.0,   # 8% recovery hysteresis (T_off < T_on)
        min_current_a=5.0,        # Suppress when unloaded / noise floor < 5A
        persistence_seconds=900.0,
        recovery_seconds=900.0,
        threshold_provenance="CONFIGURED_ENGINEERING_ASSUMPTION (NEMA MG-1 Derived Guideline)",
    ),
    ElectricalEpisodeType.VOLTAGE_IMBALANCE: ElectricalEpisodeThresholds(
        warning_threshold=2.0,    # 2% NEMA voltage unbalance
        critical_threshold=5.0,   # 5% severe voltage unbalance
        recovery_threshold=1.5,   # 1.5% recovery hysteresis
        min_load_kva=0.0,
        persistence_seconds=900.0,
        recovery_seconds=900.0,
        threshold_provenance="CONFIGURED_ENGINEERING_ASSUMPTION (IEEE/NEMA Guideline)",
    ),
    ElectricalEpisodeType.NEUTRAL_CURRENT_RATIO: ElectricalEpisodeThresholds(
        warning_threshold=0.30,   # 30% In / Ieq
        critical_threshold=0.60,  # 60% severe neutral return current
        recovery_threshold=0.20,  # 20% recovery hysteresis
        min_current_a=5.0,        # Denominator validity floor
        persistence_seconds=900.0,
        recovery_seconds=900.0,
        threshold_provenance="CONFIGURED_ENGINEERING_ASSUMPTION",
    ),
    ElectricalEpisodeType.LOW_POWER_FACTOR: ElectricalEpisodeThresholds(
        warning_threshold=0.80,   # PF <= 0.80 under load
        critical_threshold=0.65,  # PF <= 0.65 under load
        recovery_threshold=0.85,  # PF > 0.85 recovery
        min_load_kva=10.0,        # CRITICAL: only evaluate when S >= 10 kVA; suppress on unloaded magnetizing current
        persistence_seconds=900.0,
        recovery_seconds=900.0,
        threshold_provenance="CONFIGURED_ENGINEERING_ASSUMPTION (Grid Interconnection Standard Guideline)",
    ),
    ElectricalEpisodeType.PQS_INCONSISTENCY: ElectricalEpisodeThresholds(
        warning_threshold=0.15,   # 15% discrepancy |S^2 - (P^2 + Q^2)| / S^2
        critical_threshold=0.35,  # 35% severe discrepancy
        recovery_threshold=0.08,  # 8% recovery hysteresis
        min_load_kva=5.0,         # Minimum 5 kVA to avoid zero-division noise
        persistence_seconds=900.0,
        recovery_seconds=900.0,
        threshold_provenance="CONFIGURED_ENGINEERING_ASSUMPTION (Measurement Consistency Check — NOT Transformer Fault)",
    ),
}


class ElectricalEpisode(BaseModel):
    """Deterministic stateful temporal representation of an electrical abnormal condition."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    episode_id: str = Field(..., description="Unique deterministic episode identifier")
    asset_id: str = Field(..., description="Transformer asset identifier")
    episode_type: ElectricalEpisodeType = Field(..., description="Specific electrical condition type")
    category: AnomalyCategory = Field(..., description="Canonical operator category")
    status: EpisodeStatus = Field(..., description="Current FSM lifecycle status")
    severity: EpisodeSeverity = Field(..., description="Current severity level (WARNING or CRITICAL)")
    start_time_utc: datetime = Field(..., description="Initial detection timestamp in UTC")
    activation_time_utc: Optional[datetime] = Field(default=None, description="Timestamp when persistence requirement was satisfied")
    last_active_time_utc: datetime = Field(..., description="Most recent timestamp where condition was active/evaluated")
    recovery_start_time_utc: Optional[datetime] = Field(default=None, description="Timestamp when condition dropped below recovery threshold")
    closed_time_utc: Optional[datetime] = Field(default=None, description="Timestamp when episode formally closed")
    duration_seconds: float = Field(default=0.0, ge=0.0, description="Total elapsed duration in seconds")
    peak_value: float = Field(..., description="Worst/peak observed feature value during this episode")
    peak_severity: EpisodeSeverity = Field(..., description="Worst severity level reached during this episode")
    initial_value: float = Field(..., description="Observed feature value at initial detection")
    last_observed_value: float = Field(..., description="Most recently observed feature value")
    recurrence_count: int = Field(default=1, ge=1, description="Recurrence index for this episode type on this asset")
    evidence_grade: EvidenceGrade = Field(..., description="Evidence classification grade")
    primary_reason: str = Field(..., description="Deterministic human-readable primary cause description")
    hypothesis_codes: List[str] = Field(default_factory=list, description="Non-assertive possible explanatory hypotheses")
    evidence_items: List[EvidenceItem] = Field(default_factory=list, description="Associated structured evidence items")
    is_monitoring_gap: bool = Field(default=False, description="Whether episode was frozen across a data gap")

    def to_anomaly_episode(self) -> AnomalyEpisode:
        """Convert to canonical AnomalyEpisode model for TwinState integration."""
        state_map = {
            EpisodeStatus.CANDIDATE: EpisodeState.WATCH,
            EpisodeStatus.ACTIVE: EpisodeState.CRITICAL if self.severity == EpisodeSeverity.CRITICAL else EpisodeState.WARNING,
            EpisodeStatus.RECOVERING: EpisodeState.RECOVERING,
            EpisodeStatus.CLOSED: EpisodeState.CLOSED,
        }
        sev_score = 0.90 if self.severity == EpisodeSeverity.CRITICAL else (0.50 if self.severity == EpisodeSeverity.WARNING else 0.0)

        return AnomalyEpisode(
            episode_id=self.episode_id,
            asset_id=self.asset_id,
            state=state_map.get(self.status, EpisodeState.WATCH),
            category=self.category,
            severity_score=sev_score,
            start_time_utc=self.start_time_utc,
            last_seen_time_utc=self.last_active_time_utc,
            recovery_start_time_utc=self.recovery_start_time_utc,
            closed_time_utc=self.closed_time_utc,
            evidence_ids=[e.evidence_id for e in self.evidence_items],
            is_monitoring_gap=self.is_monitoring_gap,
            primary_reason=self.primary_reason,
            hypothesis_codes=self.hypothesis_codes,
        )


class ElectricalEpisodeState(BaseModel):
    """Serializable snapshot of the electrical episode engine state for checkpointing and replay."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str
    active_episodes: Dict[str, ElectricalEpisode] = Field(default_factory=dict)
    closed_episodes: List[ElectricalEpisode] = Field(default_factory=list)
    recurrence_counts: Dict[str, int] = Field(default_factory=dict)
    persistence_timers: Dict[str, float] = Field(default_factory=dict)
    recovery_timers: Dict[str, float] = Field(default_factory=dict)
    last_event_time_utc: Optional[datetime] = None
