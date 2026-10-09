"""Phase 6.5 / Batch 4 — Deterministic Review Flag Workflow Contracts.

REVIEW FLAG — Observed behaviour warrants human review; the available evidence
does not support a qualified anomaly conclusion.

Maintains four strictly independent dimensions:
1. Condition: NORMAL / INSUFFICIENT_EVIDENCE / QUALIFIED_ANOMALY / PROTECTION_EVENT
2. Observability: CURRENT / DEGRADED / STALE / CONFLICTING
3. Review Lifecycle: OPEN / CLEARING / CLOSED / SUPERSEDED
4. Human Workflow: UNACKNOWLEDGED / ACKNOWLEDGED / DISMISSED
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ConditionState(str, Enum):
    """Underlying physical condition state."""
    NORMAL = "NORMAL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    QUALIFIED_ANOMALY = "QUALIFIED_ANOMALY"
    PROTECTION_EVENT = "PROTECTION_EVENT"


class ObservabilityState(str, Enum):
    """Telemetry availability and consistency state."""
    CURRENT = "CURRENT"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    CONFLICTING = "CONFLICTING"


class ReviewLifecycleState(str, Enum):
    """Deterministic physical evidence lifecycle state."""
    OPEN = "OPEN"
    CLEARING = "CLEARING"
    CLOSED = "CLOSED"
    SUPERSEDED = "SUPERSEDED"


class HumanWorkflowState(str, Enum):
    """Independent human workflow acknowledgment state."""
    UNACKNOWLEDGED = "UNACKNOWLEDGED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    DISMISSED = "DISMISSED"


class ReviewConditionFamily(str, Enum):
    """Eligible condition families backed by engineering evidence."""
    SENSOR_INCONSISTENCY = "SENSOR_INCONSISTENCY"
    ENGINEERING_PLAUSIBILITY = "ENGINEERING_PLAUSIBILITY"
    THERMAL_BEHAVIOUR_UNVERIFIED = "THERMAL_BEHAVIOUR_UNVERIFIED"
    ELECTRICAL_UNBALANCE_ADVISORY = "ELECTRICAL_UNBALANCE_ADVISORY"
    OPERATOR_INVESTIGATION = "OPERATOR_INVESTIGATION"


class ReviewFlagRecord(BaseModel):
    """Deterministic, immutable-versioned Review Flag record."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    review_id: str = Field(..., description="Deterministic review identifier (asset + condition_family + target)")
    asset_id: str = Field(..., description="Asset identifier")
    condition_family: ReviewConditionFamily = Field(..., description="Condition family")
    target: str = Field(..., description="Target subsystem, sensor, or component")
    condition: ConditionState = Field(default=ConditionState.INSUFFICIENT_EVIDENCE, description="Underlying condition state")
    observability: ObservabilityState = Field(default=ObservabilityState.CURRENT, description="Telemetry observability state")
    lifecycle_state: ReviewLifecycleState = Field(default=ReviewLifecycleState.OPEN, description="Physical evidence lifecycle state")
    workflow_state: HumanWorkflowState = Field(default=HumanWorkflowState.UNACKNOWLEDGED, description="Human workflow acknowledgment state")
    revision: int = Field(default=1, ge=1, description="Monotonically increasing record revision counter")
    created_event_time_utc: datetime = Field(..., description="Event timestamp when review was opened in UTC")
    last_updated_event_time_utc: datetime = Field(..., description="Event timestamp of latest transition in UTC")
    logical_stream_position: int = Field(default=0, ge=0, description="Canonical stream sequence position")
    supporting_evidence_ids: list[str] = Field(default_factory=list, description="IDs of underlying supporting EvidenceItems")
    policy_version: str = Field(default="review_flag_v1_0", description="Version of Review Flag policy")
    actor_id: Optional[str] = Field(default=None, description="Operator or automated actor ID responsible for latest mutation")
    rationale: Optional[str] = Field(default=None, description="Human explanation or engineering notes")
    resolution_reason: Optional[str] = Field(default=None, description="Documented reason for closing review")
    superseded_by_anomaly_id: Optional[str] = Field(default=None, description="Anomaly episode ID if superseded by a qualified conclusion")
    idempotency_key: Optional[str] = Field(default=None, description="Idempotency key from mutation request")


class ResidualTriggerPolicy(BaseModel):
    """Formal qualification policy artifact for automatic residual-triggered Review Flags.

    Per Section 7 of CPRI brief:
    Automatic flags based on unqualified/shadow residuals are disabled by default.
    Promotion is permitted only when all 5 gates pass:
    (a) Candidate rule selected using FIT/CAL only and versioned as separate policy artifact;
    (b) CAL has >= 21 eligible benign asset-days per enabled asset;
    (c) Predefined challenge cases pass without unacceptable missed events, delay, fragmentation;
    (d) Workload budget is met (<= 1 unmatched flag per 7 eligible asset-days);
    (e) Sealed TEST evaluation passes once and not used for tuning.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = Field(..., description="Unique policy identifier")
    policy_version: str = Field(default="residual_flag_v1_0", description="Policy semantic version")
    threshold_sigma: float = Field(default=3.0, gt=0.0, description="Standardized residual excursion threshold")
    persistence_steps: int = Field(default=3, ge=1, description="Required consecutive observation persistence")
    benign_cal_asset_days: float = Field(default=0.0, ge=0.0, description="Evaluated benign CAL asset-days")
    min_benign_cal_asset_days_required: float = Field(default=21.0, description="Minimum required benign CAL asset-days (>=21.0)")
    unmatched_flags_per_7_asset_days: float = Field(default=0.0, ge=0.0, description="Observed unmatched flag rate per 7 asset-days")
    max_workload_budget_per_7_asset_days: float = Field(default=1.0, description="Maximum allowable unmatched flags per 7 asset-days (<=1.0)")
    challenge_cases_passed: bool = Field(default=False, description="Whether synthetic challenge cases passed")
    sealed_test_passed: bool = Field(default=False, description="Whether sealed TEST evaluation passed")
    is_qualified: bool = Field(default=False, description="Whether automatic residual-triggered review flags are qualified and authorized")
    gate_failure_reasons: list[str] = Field(default_factory=list, description="List of reasons if promotion gate failed")
