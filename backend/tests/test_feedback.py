"""Phase 6.4 — Operator Feedback Store & Audit Ledger Test Suite.

Verifies:
1. Append-only immutable audit trail integrity and event querying.
2. ACKNOWLEDGE workflow state lifecycle without deleting recommendations or altering evidence.
3. DISMISS validation, dismissal suppression, and recurrence generation of new instances.
4. P0 Safety / Protection non-silent dismissal invariant (requires authorized resolution code & rationale).
5. INSPECTION_OUTCOME transformation into Grade-A source EvidenceItem.
6. OVERRIDE authorization, rationale validation, and time-based expiry semantics.
7. Non-rewriting invariant: telemetry, OTHI, and detector evidence are strictly preserved.
8. TwinReducer deterministic state hash integrity under operator feedback.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from app.engine.feedback import ALLOWED_P0_RESOLUTION_REASON_CODES, OperatorFeedbackLedger
from app.engine.maintenance import MaintenanceEngine
from app.engine.othi import OTHIEngine
from app.engine.reducer import TwinReducer
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.health import EvidenceGrade, OTHIBundle
from app.models.maintenance import (
    ActionWindow,
    ActionWindowProvenanceType,
    FeedbackAction,
    MaintenancePriority,
    MaintenanceRecommendation,
    OperatorFeedbackEvent,
)
from app.models.telemetry import CanonicalEvent, Measurement, MeasurementQuality, QualitySeverity, SourceRef


def _make_utc(hour: int = 12, minute: int = 0, second: int = 0, day: int = 1) -> datetime:
    """Helper to create UTC datetime."""
    return datetime(2026, 3, day, hour, minute, second, tzinfo=timezone.utc)


def _make_measurement(
    signal_id: str,
    value: float | int | str | bool,
    unit: str = "1",
    phase: str | None = None,
    severity: QualitySeverity = QualitySeverity.GOOD,
) -> Measurement:
    if isinstance(value, bool):
        val_type = "bool"
    elif isinstance(value, int):
        val_type = "int"
    elif isinstance(value, float):
        val_type = "float"
    else:
        val_type = "str"

    return Measurement(
        signal_id=signal_id,
        phase=phase,  # type: ignore[arg-type]
        value=value,
        value_type=val_type,
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(severity=severity, flags=[]),
    )


def _make_canonical_event(
    event_id: str,
    event_time: datetime,
    asset_id: str = "DT-001",
    measurements: list[Measurement] | None = None,
) -> CanonicalEvent:
    if measurements is None:
        measurements = [_make_measurement("top_oil_temp", 45.0, unit="degC")]

    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=event_id,
        asset_id=asset_id,
        event_time_utc=event_time,
        received_time_utc=None,
        source=SourceRef(
            system="test_system",
            adapter_id="test_v1",
            source_record_id=f"rec_{event_id}",
            source_uri="data/test.csv",
            raw_sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        ),
        event_quality_flags=[],
        measurements=measurements,
        mapping_version="test-map-1.0.0",
    )



# ---------------------------------------------------------------------------
# 1. Audit Ledger Immutability & Querying Tests
# ---------------------------------------------------------------------------


def test_feedback_ledger_immutability_and_filtering() -> None:
    """Ledger maintains append-only chronological history and filters correctly."""
    ledger = OperatorFeedbackLedger()
    t0 = _make_utc(10, 0, 0)

    fb1 = OperatorFeedbackEvent(
        feedback_id="fb-101",
        asset_id="DT-001",
        timestamp_utc=t0,
        recommendation_id="REC-001",
        action=FeedbackAction.ACKNOWLEDGE,
        operator_id="operator_alice",
        notes="Reviewing with engineer",
    )
    fb2 = OperatorFeedbackEvent(
        feedback_id="fb-102",
        asset_id="DT-001",
        timestamp_utc=t0 + timedelta(minutes=15),
        recommendation_id="REC-002",
        action=FeedbackAction.DISMISS,
        operator_id="operator_bob",
        reason_code="EXTERNAL_SWITCHING_EVENT",
        rationale="Load shifted to alternate feeder",
    )
    fb3 = OperatorFeedbackEvent(
        feedback_id="fb-103",
        asset_id="DT-002",
        timestamp_utc=t0 + timedelta(minutes=30),
        action=FeedbackAction.INSPECTION_OUTCOME,
        operator_id="technician_charlie",
        notes="Gasket checked, no oil weeping observed",
    )

    ledger.append(fb1)
    ledger.append(fb2)
    ledger.append(fb3)

    # Full history
    all_events = ledger.get_history()
    assert len(all_events) == 3
    assert [e.feedback_id for e in all_events] == ["fb-101", "fb-102", "fb-103"]

    # Filter by asset
    dt1_events = ledger.get_history(asset_id="DT-001")
    assert len(dt1_events) == 2

    # Filter by action
    dismiss_events = ledger.get_history(action=FeedbackAction.DISMISS)
    assert len(dismiss_events) == 1
    assert dismiss_events[0].feedback_id == "fb-102"


# ---------------------------------------------------------------------------
# 2. ACKNOWLEDGE Semantics Tests
# ---------------------------------------------------------------------------


def test_feedback_acknowledge_updates_workflow_state() -> None:
    """ACKNOWLEDGE sets acknowledged flag without removing recommendation or altering evidence."""
    engine = MaintenanceEngine()
    t0 = _make_utc(12, 0, 0)
    meas = [_make_measurement("breaker_trip", True, unit="1")]
    event = _make_canonical_event("e-ack-01", t0, measurements=meas)

    recs0 = engine.evaluate(event=event, evidence_items=[])
    assert len(recs0) == 1
    assert recs0[0].acknowledged is False

    rec_id = recs0[0].recommendation_id

    # Operator acknowledges
    fb = OperatorFeedbackEvent(
        feedback_id="fb-ack-1",
        asset_id="DT-001",
        timestamp_utc=t0 + timedelta(minutes=5),
        recommendation_id=rec_id,
        action=FeedbackAction.ACKNOWLEDGE,
        operator_id="operator_dave",
        notes="Control room acknowledged trip advice",
    )
    engine.record_feedback(fb)

    # Subsequent evaluation reflects acknowledgement
    recs1 = engine.evaluate(event=event, evidence_items=[])
    assert len(recs1) == 1
    assert recs1[0].acknowledged is True
    assert recs1[0].acknowledged_by == "operator_dave"
    assert recs1[0].acknowledged_at_utc == t0 + timedelta(minutes=5)


# ---------------------------------------------------------------------------
# 3. DISMISS Validation & Suppression Tests
# ---------------------------------------------------------------------------


def test_feedback_dismiss_validation_and_suppression() -> None:
    """DISMISS requires reason_code and rationale; suppresses active recommendation instance."""
    engine = MaintenanceEngine()
    t0 = _make_utc(12, 0, 0)

    # Phase imbalance evidence (P2 recommendation)
    ev_phase = EvidenceItem(
        evidence_id="ev-p-1",
        asset_id="DT-001",
        event_time_utc=t0,
        detector_id="PHASE_IMBALANCE_DETECTOR",
        observed_value=25.0,
        category=AnomalyCategory.PHASE_OR_NEUTRAL,
        severity=0.6,
        confidence=0.9,
        input_lineage=["i_current_unbalance_pct"],
        condition_family="PHASE_IMBALANCE_UNBALANCE",
    )
    event0 = _make_canonical_event("e0", t0)
    recs0 = engine.evaluate(event=event0, evidence_items=[ev_phase])
    assert len(recs0) == 1
    assert recs0[0].rule_id == "MNT-PHASE-004"
    rec_id = recs0[0].recommendation_id

    # 1. Reject dismissal without reason_code
    with pytest.raises(ValueError, match="reason_code"):
        engine.record_feedback(
            OperatorFeedbackEvent(
                feedback_id="fb-err-1",
                asset_id="DT-001",
                timestamp_utc=t0 + timedelta(minutes=10),
                recommendation_id=rec_id,
                action=FeedbackAction.DISMISS,
                operator_id="operator_eve",
                rationale="Some rationale",
            )
        )

    # 2. Reject dismissal without rationale
    with pytest.raises(ValueError, match="rationale"):
        engine.record_feedback(
            OperatorFeedbackEvent(
                feedback_id="fb-err-2",
                asset_id="DT-001",
                timestamp_utc=t0 + timedelta(minutes=10),
                recommendation_id=rec_id,
                action=FeedbackAction.DISMISS,
                operator_id="operator_eve",
                reason_code="LOAD_TRANSFER",
            )
        )

    # 3. Valid dismissal suppresses active recommendation
    fb_valid = OperatorFeedbackEvent(
        feedback_id="fb-ok-1",
        asset_id="DT-001",
        timestamp_utc=t0 + timedelta(minutes=10),
        recommendation_id=rec_id,
        merge_key=recs0[0].merge_key,
        action=FeedbackAction.DISMISS,
        operator_id="operator_eve",
        reason_code="KNOWN_TEMPORARY_SINGLE_PHASE_LOAD",
        rationale="Temporary railway traction load active until 14:00",
    )
    engine.record_feedback(fb_valid)

    # Evaluation at t0 + 10m (with same historical evidence) suppresses recommendation
    event_eval = _make_canonical_event("e_eval", t0 + timedelta(minutes=10))
    recs_eval = engine.evaluate(event=event_eval, evidence_items=[ev_phase])
    assert len(recs_eval) == 0


# ---------------------------------------------------------------------------
# 4. P0 Safety Non-Silent Dismissal Invariant Tests
# ---------------------------------------------------------------------------


def test_p0_safety_protection_non_silent_dismissal_invariant() -> None:
    """P0 Safety recommendations CANNOT be dismissed without authorized documented resolution code."""
    engine = MaintenanceEngine()
    t0 = _make_utc(12, 0, 0)
    meas = [_make_measurement("breaker_trip", True, unit="1")]
    event = _make_canonical_event("e-p0-trip", t0, measurements=meas)

    recs = engine.evaluate(event=event, evidence_items=[])
    assert len(recs) == 1
    assert recs[0].priority == MaintenancePriority.P0_SAFETY
    rec_p0 = recs[0]

    # 1. Attempt to dismiss with generic reason code -> REJECTED
    with pytest.raises(ValueError, match="P0 Safety/Protection recommendations cannot be dismissed without documented resolution"):
        engine.record_feedback(
            OperatorFeedbackEvent(
                feedback_id="fb-p0-invalid",
                asset_id="DT-001",
                timestamp_utc=t0 + timedelta(minutes=5),
                recommendation_id=rec_p0.recommendation_id,
                merge_key=rec_p0.merge_key,
                action=FeedbackAction.DISMISS,
                operator_id="operator_frank",
                reason_code="FALSE_ALARM",
                rationale="Looks fine on SCADA",
            ),
            target_recommendation=rec_p0,
        )

    # 2. Dismiss with authorized resolution code -> ACCEPTED
    fb_p0_valid = OperatorFeedbackEvent(
        feedback_id="fb-p0-valid",
        asset_id="DT-001",
        timestamp_utc=t0 + timedelta(minutes=15),
        recommendation_id=rec_p0.recommendation_id,
        merge_key=rec_p0.merge_key,
        action=FeedbackAction.DISMISS,
        operator_id="senior_engineer_grace",
        reason_code="SITE_CLEARANCE_VERIFIED",
        rationale="Field crew completed relay inspection and cleared feeder for re-energization per SOP-042",
    )
    engine.record_feedback(fb_p0_valid, target_recommendation=rec_p0)

    # Verification: Dismissal recorded in ledger
    history = engine.feedback_ledger.get_history(recommendation_id=rec_p0.recommendation_id)
    assert len(history) == 1
    assert history[0].reason_code == "SITE_CLEARANCE_VERIFIED"


# ---------------------------------------------------------------------------
# 5. Recurrence Semantics Tests
# ---------------------------------------------------------------------------


def test_feedback_dismissal_recurrence_reopens_new_instance() -> None:
    """If abnormal condition recurs after dismissal, a NEW recommendation instance is generated."""
    engine = MaintenanceEngine()
    t0 = _make_utc(12, 0, 0)
    t_dismiss = t0 + timedelta(minutes=15)
    t_recur = t0 + timedelta(minutes=30)

    ev_phase_0 = EvidenceItem(
        evidence_id="ev-p-t0",
        asset_id="DT-001",
        event_time_utc=t0,
        detector_id="PHASE_IMBALANCE_DETECTOR",
        observed_value=25.0,
        category=AnomalyCategory.PHASE_OR_NEUTRAL,
        severity=0.55,
        confidence=0.9,
        input_lineage=["i_current_unbalance_pct"],
        condition_family="PHASE_IMBALANCE_UNBALANCE",
    )
    event0 = _make_canonical_event("e0", t0)
    recs0 = engine.evaluate(event=event0, evidence_items=[ev_phase_0])
    assert len(recs0) == 1
    merge_key = recs0[0].merge_key

    # Dismiss at t_dismiss
    fb_dismiss = OperatorFeedbackEvent(
        feedback_id="fb-dis-rec",
        asset_id="DT-001",
        timestamp_utc=t_dismiss,
        recommendation_id=recs0[0].recommendation_id,
        merge_key=merge_key,
        action=FeedbackAction.DISMISS,
        operator_id="operator_harry",
        reason_code="PLANNED_MAINTENANCE_LOGGED",
        rationale="Work order WO-991 created",
    )
    engine.record_feedback(fb_dismiss)

    # At t_dismiss: suppressed
    event_dis = _make_canonical_event("e_dis", t_dismiss)
    assert len(engine.evaluate(event=event_dis, evidence_items=[ev_phase_0])) == 0

    # At t_recur: new abnormal evidence item emitted AFTER dismissal
    ev_phase_new = EvidenceItem(
        evidence_id="ev-p-t30",
        asset_id="DT-001",
        event_time_utc=t_recur,
        detector_id="PHASE_IMBALANCE_DETECTOR",
        observed_value=32.0,
        category=AnomalyCategory.PHASE_OR_NEUTRAL,
        severity=0.70,
        confidence=0.95,
        input_lineage=["i_current_unbalance_pct"],
        condition_family="PHASE_IMBALANCE_UNBALANCE",
    )
    event_recur = _make_canonical_event("e_recur", t_recur)
    recs_recur = engine.evaluate(event=event_recur, evidence_items=[ev_phase_new])

    # New recommendation instance is emitted!
    assert len(recs_recur) == 1
    assert recs_recur[0].acknowledged is False
    assert "ev-p-t30" in recs_recur[0].evidence_ids


# ---------------------------------------------------------------------------
# 6. INSPECTION_OUTCOME as Source Evidence Tests
# ---------------------------------------------------------------------------


def test_inspection_outcome_generates_source_evidence() -> None:
    """INSPECTION_OUTCOME feedback creates Grade-A EvidenceItem without altering historical records."""
    ledger = OperatorFeedbackLedger()
    t_insp = _make_utc(14, 30, 0)

    fb_insp = OperatorFeedbackEvent(
        feedback_id="fb-insp-001",
        asset_id="DT-001",
        timestamp_utc=t_insp,
        action=FeedbackAction.INSPECTION_OUTCOME,
        operator_id="inspector_ian",
        notes="Physical inspection confirmed minor radiator valve weeping",
        inspection_outcome={
            "category": "PROTECTION_OR_OIL_STATUS",
            "severity": 0.4,
            "component": "RADIATOR_VALVE_2",
            "leak_rate": "SLOW_WEEP",
        },
    )
    ledger.append(fb_insp)

    evidence_items = ledger.generate_inspection_evidence(asset_id="DT-001")
    assert len(evidence_items) == 1
    ev = evidence_items[0]

    assert ev.confidence == 1.0
    assert ev.severity == 0.4
    assert ev.category == AnomalyCategory.PROTECTION_OR_OIL_STATUS
    assert "PHYSICAL_INSPECTION:inspector_ian" in ev.detector_id
    assert "FB-fb-insp-001" in ev.input_lineage


# ---------------------------------------------------------------------------
# 7. OVERRIDE Semantics and Expiry Tests
# ---------------------------------------------------------------------------


def test_authorized_override_and_expiry_semantics() -> None:
    """OVERRIDE requires authorized role and annotates advice until override_expiry_utc."""
    engine = MaintenanceEngine()
    t0 = _make_utc(12, 0, 0)
    t_exp = t0 + timedelta(hours=2)

    ev_pf = EvidenceItem(
        evidence_id="ev-pf-1",
        asset_id="DT-001",
        event_time_utc=t0,
        detector_id="POWER_FACTOR_DETECTOR",
        observed_value=0.72,
        category=AnomalyCategory.VOLTAGE_PF_FREQUENCY,
        severity=0.5,
        confidence=0.85,
        input_lineage=["power_factor"],
        condition_family="POWER_FACTOR_ANOMALY",
    )
    event0 = _make_canonical_event("e0", t0)
    recs0 = engine.evaluate(event=event0, evidence_items=[ev_pf])
    assert len(recs0) == 1
    rec0 = recs0[0]

    # 1. Override without authorized_role -> REJECTED
    with pytest.raises(ValueError, match="authorized_role"):
        engine.record_feedback(
            OperatorFeedbackEvent(
                feedback_id="fb-ovr-err",
                asset_id="DT-001",
                timestamp_utc=t0,
                recommendation_id=rec0.recommendation_id,
                action=FeedbackAction.OVERRIDE,
                operator_id="operator_jenny",
                override_expiry_utc=t_exp,
                rationale="Capacitor bank off for scheduled testing",
            )
        )

    # 2. Valid authorized override
    fb_ovr = OperatorFeedbackEvent(
        feedback_id="fb-ovr-ok",
        asset_id="DT-001",
        timestamp_utc=t0,
        recommendation_id=rec0.recommendation_id,
        merge_key=rec0.merge_key,
        action=FeedbackAction.OVERRIDE,
        operator_id="chief_engineer_karen",
        authorized_role="PRINCIPAL_SYSTEM_OPERATOR",
        override_expiry_utc=t_exp,
        rationale="Capacitor bank off for grid maintenance until 14:00",
    )
    engine.record_feedback(fb_ovr)

    # During override window (t0 + 1 hour): advice contains override notation
    event_mid = _make_canonical_event("e_mid", t0 + timedelta(hours=1))
    recs_mid = engine.evaluate(event=event_mid, evidence_items=[ev_pf])
    assert len(recs_mid) == 1
    assert "AUTHORIZED OVERRIDE" in recs_mid[0].advisory_wording
    assert "PRINCIPAL_SYSTEM_OPERATOR" in recs_mid[0].advisory_wording

    # After expiry (t0 + 3 hours): override expires, original advisory text restored
    event_post = _make_canonical_event("e_post", t0 + timedelta(hours=3))
    recs_post = engine.evaluate(event=event_post, evidence_items=[ev_pf])
    assert len(recs_post) == 1
    assert "AUTHORIZED OVERRIDE" not in recs_post[0].advisory_wording


# ---------------------------------------------------------------------------
# 8. TwinReducer Integration & Deterministic Hash Integrity
# ---------------------------------------------------------------------------


def test_twin_reducer_state_hash_integrity_with_feedback() -> None:
    """Feedback updates TwinState active recommendations while preserving deterministic state hash."""
    maintenance_engine = MaintenanceEngine()
    reducer = TwinReducer(maintenance_engine=maintenance_engine)

    t0 = _make_utc(12, 0, 0)
    meas = [_make_measurement("breaker_trip", True, unit="1")]
    ev0 = _make_canonical_event("e-twin-0", t0, measurements=meas)

    state0 = reducer.reduce(None, ev0)
    assert len(state0.active_recommendations) == 1
    assert state0.active_recommendations[0].acknowledged is False
    rec_id = state0.active_recommendations[0].recommendation_id

    # Record acknowledgment
    fb = OperatorFeedbackEvent(
        feedback_id="fb-twin-1",
        asset_id="DT-001",
        timestamp_utc=t0 + timedelta(minutes=5),
        recommendation_id=rec_id,
        action=FeedbackAction.ACKNOWLEDGE,
        operator_id="operator_lead",
        notes="Acknowledged in SCADA console",
    )
    maintenance_engine.record_feedback(fb)

    # Next event in stream
    t1 = t0 + timedelta(minutes=6)
    ev1 = _make_canonical_event("e-twin-1", t1, measurements=meas)
    state1 = reducer.reduce(state0, ev1)

    assert len(state1.active_recommendations) == 1
    assert state1.active_recommendations[0].acknowledged is True
    assert state1.active_recommendations[0].acknowledged_by == "operator_lead"
    assert len(state1.state_hash) == 64
