"""Phase 6.4 — Operator Feedback Store & Audit Ledger.

Implements:
1. Append-only, immutable operator feedback audit stream (`OperatorFeedbackLedger`).
2. Strict feedback action semantics:
   - `ACKNOWLEDGE`: Workflow state update only; recommendation remains active with acknowledged metadata.
   - `DISMISS`: Dismisses specific recommendation instance; requires actor, reason_code, and rationale.
     Recurrence of condition after dismissal emits a new recommendation instance.
   - `INSPECTION_OUTCOME`: Records physical inspection findings as new Grade A source evidence.
   - `OVERRIDE`: Authorized advisory override requiring authorized role, rationale, and expiry timestamp.
3. Safety Invariants:
   - P0 Safety / Protection recommendations CANNOT be dismissed without documented resolution.
   - Historical telemetry, derived features, evidence items, and calculated OTHI records are NEVER rewritten.
   - Feedback does not trigger online model retraining or threshold modifications.
"""

from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional, Sequence, Set
import uuid

from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.health import EvidenceGrade
from app.models.maintenance import (
    FeedbackAction,
    MaintenancePriority,
    MaintenanceRecommendation,
    OperatorFeedbackEvent,
)


# Documented resolution codes allowed for resolving P0 safety/protection items
ALLOWED_P0_RESOLUTION_REASON_CODES: Set[str] = {
    "SITE_CLEARANCE_VERIFIED",
    "SAFETY_PROCEDURE_COMPLETED",
    "TRIP_RESOLVED_AND_RESET",
    "DOCUMENTED_RESOLUTION",
    "FIELD_INSPECTION_CLEARED",
}


class OperatorFeedbackLedger:
    """Thread-safe, append-only immutable audit ledger for human-in-the-loop operator feedback."""

    def __init__(self) -> None:
        """Initialize empty feedback ledger."""
        self._lock = threading.Lock()
        self._events: List[OperatorFeedbackEvent] = []

    def append(
        self,
        event: OperatorFeedbackEvent,
        target_recommendation: Optional[MaintenanceRecommendation] = None,
    ) -> OperatorFeedbackEvent:
        """Validate and append an immutable OperatorFeedbackEvent to the ledger.

        Args:
            event: The incoming feedback event.
            target_recommendation: Optional recommendation instance being acted upon (used for P0 safety checks).

        Returns:
            The recorded OperatorFeedbackEvent.

        Raises:
            ValueError: If validation fails or safety invariants are violated.
        """
        # Ensure UTC timezone
        ts = event.timestamp_utc
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        # 1. Action Validation
        action_val = event.action.value if hasattr(event.action, "value") else str(event.action)

        if action_val == "ACKNOWLEDGE":
            if not event.recommendation_id and not event.merge_key and not event.review_id:
                raise ValueError("ACKNOWLEDGE action requires recommendation_id, merge_key, or review_id.")

        elif action_val == "DISMISS":
            actor = event.actor_id or event.operator_id
            if not actor:
                raise ValueError("DISMISS action requires an authenticated operator/actor ID.")
            if not event.reason_code and not event.review_id:
                raise ValueError("DISMISS action requires a structured reason_code.")
            rationale = event.rationale or event.notes
            if not rationale or not rationale.strip():
                raise ValueError("DISMISS action requires a documented rationale/explanation.")

            # Safety Invariant: P0 Safety/Protection cannot be dismissed without documented resolution
            is_p0 = False
            if target_recommendation is not None:
                if target_recommendation.priority == MaintenancePriority.P0_SAFETY or target_recommendation.rule_id == "MNT-PROT-001":
                    is_p0 = True
            elif event.merge_key == "PROTECTION_TRIP_FOLLOWUP" or (event.recommendation_id and "MNT-PROT-001" in event.recommendation_id):
                is_p0 = True

            if is_p0:
                if event.reason_code not in ALLOWED_P0_RESOLUTION_REASON_CODES:
                    raise ValueError(
                        f"P0 Safety/Protection recommendations cannot be dismissed without documented resolution. "
                        f"Reason code '{event.reason_code}' is not an authorized resolution code ({ALLOWED_P0_RESOLUTION_REASON_CODES})."
                    )

        elif action_val in ("RESOLVE", "REOPEN"):
            if not event.review_id and not event.recommendation_id and not event.merge_key:
                raise ValueError(f"{action_val} action requires review_id, recommendation_id, or merge_key.")

        elif action_val in ("INSPECTION_OUTCOME", "INSPECTION_RECORDED"):
            has_notes = event.notes and event.notes.strip()
            has_outcome_dict = event.inspection_outcome is not None and len(event.inspection_outcome) > 0
            if not has_notes and not has_outcome_dict:
                raise ValueError("INSPECTION_OUTCOME requires physical inspection findings in notes or inspection_outcome.")

        elif action_val == "OVERRIDE":
            if not event.authorized_role:
                raise ValueError("OVERRIDE action requires an authorized_role (e.g. LEAD_ENGINEER, SUBSTATION_SUPERVISOR).")
            rationale = event.rationale or event.notes
            if not rationale or not rationale.strip():
                raise ValueError("OVERRIDE action requires an explicit engineering rationale.")
            if not event.override_expiry_utc:
                raise ValueError("OVERRIDE action requires an override_expiry_utc timestamp.")

        with self._lock:
            self._events.append(event)

        return event

    def get_history(
        self,
        asset_id: Optional[str] = None,
        recommendation_id: Optional[str] = None,
        action: Optional[FeedbackAction] = None,
    ) -> List[OperatorFeedbackEvent]:
        """Retrieve full chronological feedback history with optional filtering."""
        with self._lock:
            events = list(self._events)

        filtered = events
        if asset_id is not None:
            filtered = [e for e in filtered if e.asset_id == asset_id]
        if recommendation_id is not None:
            filtered = [e for e in filtered if e.recommendation_id == recommendation_id]
        if action is not None:
            act_val = action.value if hasattr(action, "value") else str(action)
            filtered = [
                e
                for e in filtered
                if (e.action.value if hasattr(e.action, "value") else str(e.action)) == act_val
            ]

        return filtered

    def _extract_keys(self, ev: OperatorFeedbackEvent) -> List[str]:
        """Extract all candidate lookup keys (recommendation_id, rule_id, merge_key) for an event."""
        keys: List[str] = []
        if ev.recommendation_id:
            keys.append(ev.recommendation_id)
            # Match rule ID substring e.g. "REC-DT-001-MNT-PROT-001-1772366400" -> "MNT-PROT-001"
            parts = ev.recommendation_id.split("-")
            for i in range(len(parts) - 2):
                candidate_rule = f"{parts[i]}-{parts[i+1]}-{parts[i+2]}"
                if candidate_rule.startswith("MNT-"):
                    keys.append(candidate_rule)
        if ev.merge_key:
            keys.append(ev.merge_key)
        return keys

    def get_active_acknowledgements(self, asset_id: str) -> Dict[str, OperatorFeedbackEvent]:
        """Get latest active acknowledgement event mapped by target ID (recommendation_id, rule_id, merge_key)."""
        history = self.get_history(asset_id=asset_id)
        acks: Dict[str, OperatorFeedbackEvent] = {}
        for ev in history:
            act_val = ev.action.value if hasattr(ev.action, "value") else str(ev.action)
            if act_val == "ACKNOWLEDGE":
                for k in self._extract_keys(ev):
                    acks[k] = ev
        return acks

    def get_active_dismissals(self, asset_id: str) -> Dict[str, OperatorFeedbackEvent]:
        """Get latest active dismissal event mapped by target ID (recommendation_id, rule_id, merge_key)."""
        history = self.get_history(asset_id=asset_id)
        dismissals: Dict[str, OperatorFeedbackEvent] = {}
        for ev in history:
            act_val = ev.action.value if hasattr(ev.action, "value") else str(ev.action)
            if act_val == "DISMISS":
                for k in self._extract_keys(ev):
                    dismissals[k] = ev
        return dismissals

    def get_active_overrides(
        self, asset_id: str, current_time: datetime
    ) -> Dict[str, OperatorFeedbackEvent]:
        """Get active unexpired override events mapped by target ID."""
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        history = self.get_history(asset_id=asset_id)
        overrides: Dict[str, OperatorFeedbackEvent] = {}
        for ev in history:
            act_val = ev.action.value if hasattr(ev.action, "value") else str(ev.action)
            if act_val == "OVERRIDE":
                if ev.override_expiry_utc is not None:
                    exp = ev.override_expiry_utc
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    if exp >= current_time:
                        for k in self._extract_keys(ev):
                            overrides[k] = ev
        return overrides


    def generate_inspection_evidence(
        self, asset_id: str, as_of_time: Optional[datetime] = None
    ) -> List[EvidenceItem]:
        """Generate structured Grade-A EvidenceItems from recorded physical inspections.

        Args:
            asset_id: Transformer asset ID.
            as_of_time: Optional upper bound filter timestamp.

        Returns:
            List[EvidenceItem]: Structured physical inspection evidence.
        """
        history = self.get_history(asset_id=asset_id)
        evidence: List[EvidenceItem] = []

        for ev in history:
            act_val = ev.action.value if hasattr(ev.action, "value") else str(ev.action)
            if act_val in ("INSPECTION_OUTCOME", "INSPECTION_RECORDED"):
                ev_time = ev.timestamp_utc
                if as_of_time is not None:
                    cutoff = as_of_time if as_of_time.tzinfo else as_of_time.replace(tzinfo=timezone.utc)
                    ev_t = ev_time if ev_time.tzinfo else ev_time.replace(tzinfo=timezone.utc)
                    if ev_t > cutoff:
                        continue

                outcome_dict = ev.inspection_outcome or {}
                notes = ev.notes or outcome_dict.get("summary", "Physical site inspection recorded")
                severity = float(outcome_dict.get("severity", 0.0))
                category_str = outcome_dict.get("category", "PROTECTION_OR_OIL_STATUS")

                try:
                    cat = AnomalyCategory(category_str)
                except ValueError:
                    cat = AnomalyCategory.PROTECTION_OR_OIL_STATUS

                ev_item = EvidenceItem(
                    evidence_id=f"EV-INSP-{ev.feedback_id[:8]}",
                    asset_id=asset_id,
                    event_time_utc=ev_time,
                    category=cat,
                    detector_id=f"PHYSICAL_INSPECTION:{ev.operator_id}",
                    observed_value=notes,
                    severity=min(1.0, max(0.0, severity)),
                    confidence=1.0,
                    input_lineage=["PHYSICAL_INSPECTION_LOG", f"FB-{ev.feedback_id}"],
                    condition_family="PHYSICAL_INSPECTION",
                    derivation_type="OPERATOR_ACTION",
                    reason_codes=["PHYSICAL_INSPECTION_OUTCOME"],
                )
                evidence.append(ev_item)

        return evidence

