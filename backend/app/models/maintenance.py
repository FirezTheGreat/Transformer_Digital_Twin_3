"""Maintenance Policy, Rule Recommendations, and Operator Feedback Contracts."""

from datetime import datetime
from enum import Enum
from typing import Any, List, Literal, Optional
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


class ActionWindowProvenanceType(str, Enum):
    """Auditable provenance source type for maintenance action windows."""
    APPLICABLE_STANDARD_OR_GUIDE = "APPLICABLE_STANDARD_OR_GUIDE"
    MANUFACTURER_REQUIREMENT = "MANUFACTURER_REQUIREMENT"
    PROTECTION_OR_SITE_PROCEDURE = "PROTECTION_OR_SITE_PROCEDURE"
    OPERATOR_POLICY = "OPERATOR_POLICY"
    ENGINEERING_POLICY = "ENGINEERING_POLICY"
    DEMO_DEFAULT = "DEMO_DEFAULT"


class MaintenanceRecommendation(BaseModel):
    """Deterministic, rule-generated advisory maintenance action."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str = Field(..., description="Unique recommendation ID")
    rule_id: str = Field(..., description="Primary rule ID from rules.yaml (e.g. MNT-PROT-001)")
    rule_version: str = Field(default="1.0.0", description="Version of the triggering maintenance rule")
    title: str = Field(..., description="Concise recommendation title")
    priority: MaintenancePriority = Field(..., description="Priority tier (P0–P4)")
    priority_label: str = Field(..., description="Descriptive priority label (e.g. 'P0 SAFETY')")
    action_window: ActionWindow = Field(..., description="Qualitative action timeframe")
    window_provenance_type: ActionWindowProvenanceType = Field(
        default=ActionWindowProvenanceType.ENGINEERING_POLICY,
        description="Auditable source category for the action window",
    )
    window_source_reference: str = Field(
        default="Engineering maintenance policy default",
        description="Specific document, standard clause, or operating policy citation",
    )
    advisory_wording: str = Field(..., description="Safe, standardized human-readable advisory text")
    rationale: str = Field(..., description="Detailed engineering rationale")
    evidence_ids: List[str] = Field(default_factory=list, description="IDs of triggering evidence items")
    source_reference: str = Field(..., description="Standard, guideline, or operating procedure citation")
    merge_key: str = Field(..., description="Grouping key for conflict resolution and deduplication")
    supporting_rule_ids: List[str] = Field(
        default_factory=list, description="All rule IDs that contributed to this merged recommendation"
    )
    consequence_class: Optional[str] = Field(
        default=None, description="Consequence classification (e.g. SAFETY_CRITICAL, THERMAL_STRESS)"
    )
    binding_vs_advisory: Literal["BINDING", "ADVISORY"] = Field(
        default="ADVISORY", description="Whether action is binding site procedure or advisory decision support"
    )
    approved_by: Optional[str] = Field(
        default=None, description="Designated role or standard authority that approved the rule policy"
    )
    source_version: Optional[str] = Field(default="1.0.0", description="Version of source policy document")
    created_at_utc: datetime = Field(..., description="Emission timestamp in UTC")
    acknowledged: bool = Field(default=False, description="Whether an operator has acknowledged this advice")
    acknowledged_at_utc: Optional[datetime] = Field(default=None, description="Operator acknowledgment timestamp")
    acknowledged_by: Optional[str] = Field(default=None, description="Operator ID who acknowledged")


class FeedbackAction(str, Enum):
    """Allowed operator feedback actions."""
    ACKNOWLEDGE = "ACKNOWLEDGE"
    DISMISS = "DISMISS"
    INSPECTION_OUTCOME = "INSPECTION_OUTCOME"
    INSPECTION_RECORDED = "INSPECTION_RECORDED"  # Backward-compatibility alias
    OVERRIDE = "OVERRIDE"


class OperatorFeedbackEvent(BaseModel):
    """Immutable human-in-the-loop operator feedback event."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    feedback_id: str = Field(..., description="Unique feedback event UUID")
    asset_id: str = Field(..., description="Transformer asset identifier")
    timestamp_utc: datetime = Field(..., description="Action timestamp in UTC")
    recommendation_id: Optional[str] = Field(default=None, description="Linked recommendation ID if applicable")
    merge_key: Optional[str] = Field(default=None, description="Linked merge_key or condition family if applicable")
    action: FeedbackAction = Field(..., description="Operator decision action")
    operator_id: str = Field(..., description="Authenticated or demo operator username/ID")
    actor_id: Optional[str] = Field(default=None, description="Optional actor identifier alias")
    reason_code: Optional[str] = Field(default=None, description="Structured dismissal or override reason code")
    notes: Optional[str] = Field(default=None, description="Operator explanation or physical inspection findings")
    rationale: Optional[str] = Field(default=None, description="Detailed engineering rationale for dismissal or override")
    inspection_outcome: Optional[dict[str, Any]] = Field(default=None, description="Structured physical inspection findings")
    authorized_role: Optional[str] = Field(default=None, description="Role of operator if performing an authorized override")
    override_expiry_utc: Optional[datetime] = Field(default=None, description="Expiry timestamp for advisory override")

