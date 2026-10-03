"""Maintenance Policy, Rule Recommendations, and Operator Feedback Contracts."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class MaintenancePriority(str, Enum):
    """Urgency priority tiers for maintenance recommendations."""
    P0_SAFETY = "P0"
    P1_URGENT_INSPECTION = "P1"
    P2_PLANNED_ACTION = "P2"
    P3_MONITOR = "P3"
    P4_DATA_OR_MODEL = "P4"


class ActionWindow(str, Enum):
    """Qualitative urgency action windows."""
    IMMEDIATE = "IMMEDIATE"
    WITHIN_24H = "WITHIN_24H"
    NEXT_AUTHORIZED_MAINTENANCE_WINDOW = "NEXT_AUTHORIZED_MAINTENANCE_WINDOW"
    MONITOR = "MONITOR"
    MODEL_REVIEW = "MODEL_REVIEW"


class MaintenanceRecommendation(BaseModel):
    """Deterministic, rule-generated advisory maintenance action."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str = Field(..., description="Unique recommendation ID")
    rule_id: str = Field(..., description="Rule ID from rules.yaml (e.g. MNT-PROT-001)")
    rule_version: str = Field(default="1.0.0", description="Version of the triggering maintenance rule")
    title: str = Field(..., description="Concise recommendation title")
    priority: MaintenancePriority = Field(..., description="Priority tier (P0–P4)")
    priority_label: str = Field(..., description="Descriptive priority label (e.g. 'P0 SAFETY')")
    action_window: ActionWindow = Field(..., description="Qualitative action timeframe")
    advisory_wording: str = Field(..., description="Safe, standardized human-readable advisory text")
    rationale: str = Field(..., description="Detailed engineering rationale")
    evidence_ids: list[str] = Field(default_factory=list, description="IDs of triggering evidence items")
    source_reference: str = Field(..., description="Standard, guideline, or operating procedure citation")
    merge_key: str = Field(..., description="Grouping key for conflict resolution and deduplication")
    created_at_utc: datetime = Field(..., description="Emission timestamp in UTC")
    acknowledged: bool = Field(default=False, description="Whether an operator has acknowledged this advice")
    acknowledged_at_utc: datetime | None = Field(default=None, description="Operator acknowledgment timestamp")
    acknowledged_by: str | None = Field(default=None, description="Operator ID who acknowledged")


class FeedbackAction(str, Enum):
    """Allowed operator feedback actions."""
    ACKNOWLEDGE = "ACKNOWLEDGE"
    DISMISS = "DISMISS"
    INSPECTION_RECORDED = "INSPECTION_RECORDED"
    OVERRIDE = "OVERRIDE"


class OperatorFeedbackEvent(BaseModel):
    """Immutable human-in-the-loop operator feedback event."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    feedback_id: str = Field(..., description="Unique feedback event UUID")
    asset_id: str = Field(..., description="Transformer asset identifier")
    timestamp_utc: datetime = Field(..., description="Action timestamp in UTC")
    recommendation_id: str | None = Field(default=None, description="Linked recommendation ID if applicable")
    action: FeedbackAction = Field(..., description="Operator decision action")
    operator_id: str = Field(..., description="Authenticated or demo operator username/ID")
    notes: str | None = Field(default=None, description="Operator explanation or physical inspection findings")
    inspection_outcome: dict[str, Any] | None = Field(default=None, description="Structured physical inspection findings")
