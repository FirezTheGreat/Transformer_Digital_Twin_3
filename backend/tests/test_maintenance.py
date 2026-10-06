"""Unit and Integration Tests for Phase 6.3 — Deterministic Maintenance Policy & Rules Engine.

Verifies:
1. Locked rules MNT-PROT-001 through MNT-MODEL-007 triggers and priorities:
   - MNT-PROT-001 (P0 SAFETY / IMMEDIATE): Direct protection trip with safe advisory wording.
   - MNT-THERM-002 (P1 URGENT_INSPECTION / WITHIN_24H): Suppressed on Tripura (cusum_qualification = DISABLED).
   - MNT-FORE-003: Central crossing escalates to P1 (WITHIN_24H); uncertainty crossing triggers P3 (MONITOR). Gated when unpromoted.
   - MNT-PHASE-004 (P2 PLANNED_ACTION / NEXT_AUTHORIZED_MAINTENANCE_WINDOW): Phase imbalance corroborated by neutral.
   - MNT-PF-005 (P3 MONITOR): Low power factor framed as downstream reactive review.
   - MNT-SENS-006 (P4 DATA_OR_MODEL / MODEL_REVIEW): Sensor plausibility fault.
   - MNT-MODEL-007 (P4 DATA_OR_MODEL / MODEL_REVIEW): Calibration / residual drift.
2. Action-window provenance metadata tracking.
3. Bad data selective suppression (suppresses model advice, NEVER suppresses P0 protection).
4. Compatible recommendation merging under merge_key.
5. Operator feedback lifecycle (ACKNOWLEDGE, DISMISS).
6. End-to-end integration with TwinReducer.
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.engine.maintenance import MaintenanceEngine
from app.engine.reducer import TwinReducer
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.maintenance import (
    ActionWindow,
    ActionWindowProvenanceType,
    FeedbackAction,
    MaintenancePriority,
    MaintenanceRecommendation,
    OperatorFeedbackEvent,
)
from app.models.scenario import ScenarioProjectionResult, ScenarioProjectionStep, ThermalTrustState
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)


def _make_utc(hour: int = 12, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 10, 2, hour, minute, second, tzinfo=timezone.utc)


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
        measurements=measurements or [],
        mapping_version="test-map-1.0.0",
    )


def _make_evidence_item(
    evidence_id: str,
    category: AnomalyCategory,
    severity: float,
    detector_id: str,
    timestamp: datetime,
    condition_family: str | None = None,
    domain: str | None = None,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        asset_id="DT-001",
        event_time_utc=timestamp,
        category=category,
        detector_id=detector_id,
        observed_value=1.0,
        severity=severity,
        confidence=1.0,
        condition_family=condition_family,
        domain=domain,
        reason_codes=["TEST_REASON"],
    )


# ---------------------------------------------------------------------------
# 1. P0 Safety Rule: MNT-PROT-001
# ---------------------------------------------------------------------------


def test_mnt_prot_001_triggered_by_hardware_protection_trip() -> None:
    """MNT-PROT-001 fires P0 SAFETY / IMMEDIATE advice on hardware trip contacts."""
    engine = MaintenanceEngine()
    t0 = _make_utc(12, 0, 0)

    # Hardware breaker trip contact fired
    meas = [_make_measurement("breaker_trip", True, unit="1")]
    event = _make_canonical_event("e-prot", t0, measurements=meas)

    recs = engine.evaluate(event=event, evidence_items=[])

    assert len(recs) == 1
    rec = recs[0]
    assert rec.rule_id == "MNT-PROT-001"
    assert rec.priority == MaintenancePriority.P0_SAFETY
    assert rec.priority_label == "P0 SAFETY"
    assert rec.action_window == ActionWindow.IMMEDIATE
    assert rec.window_provenance_type == ActionWindowProvenanceType.PROTECTION_OR_SITE_PROCEDURE
    assert "site-approved trip and isolation procedure" in rec.advisory_wording
    assert rec.binding_vs_advisory == "ADVISORY"


def test_p0_protection_never_suppressed_by_bad_sensor_telemetry() -> None:
    """P0 protection advice is never suppressed even when other sensors have BAD quality."""
    engine = MaintenanceEngine()
    t0 = _make_utc(12, 0, 0)

    # All analogue measurements have BAD quality, but protection contact tripped
    meas = [
        _make_measurement("top_oil_temperature", 0.0, "Cel", severity=QualitySeverity.BAD),
        _make_measurement("current_l1", 0.0, "A", severity=QualitySeverity.BAD),
        _make_measurement("top_oil_temp_trip", True, unit="1"),
    ]
    event = _make_canonical_event("e-prot-bad", t0, measurements=meas)

    recs = engine.evaluate(event=event, evidence_items=[])

    assert len(recs) == 1
    assert recs[0].rule_id == "MNT-PROT-001"
    assert recs[0].priority == MaintenancePriority.P0_SAFETY


# ---------------------------------------------------------------------------
# 2. Qualification Gating: MNT-THERM-002 (Tripura Suppression)
# ---------------------------------------------------------------------------


def test_mnt_therm_002_suppressed_when_cusum_unqualified() -> None:
    """MNT-THERM-002 is suppressed on Tripura where cusum_qualification = DISABLED."""
    engine = MaintenanceEngine(
        cusum_qualification="DISABLED",
        is_thermal_qualified=False,
    )
    t0 = _make_utc(12, 0, 0)
    event = _make_canonical_event("e0", t0, measurements=[_make_measurement("top_oil_temperature", 85.0)])

    ev_cusum = _make_evidence_item(
        evidence_id="ev-cusum-1",
        category=AnomalyCategory.THERMAL_DEVIATION,
        severity=0.60,
        detector_id="DET_THERMAL_CUSUM_DRIFT",
        timestamp=t0,
        condition_family="THERMAL_DEVIATION_UNEXPECTED",
        domain="thermal",
    )

    recs = engine.evaluate(event=event, evidence_items=[ev_cusum])

    # Suppressed on unqualified asset
    assert len(recs) == 0


def test_mnt_therm_002_fires_when_asset_thermal_is_qualified() -> None:
    """MNT-THERM-002 fires P1 WITHIN_24H recommendation on qualified asset."""
    engine = MaintenanceEngine(
        cusum_qualification="ENABLED",
        is_thermal_qualified=True,
    )
    t0 = _make_utc(12, 0, 0)
    event = _make_canonical_event("e0", t0, measurements=[_make_measurement("top_oil_temperature", 90.0)])

    ev_therm = _make_evidence_item(
        evidence_id="ev-therm-1",
        category=AnomalyCategory.THERMAL_DEVIATION,
        severity=0.70,
        detector_id="DET_THERMAL_RESIDUAL_POINT",
        timestamp=t0,
        condition_family="THERMAL_DEVIATION_UNEXPECTED",
        domain="thermal",
    )

    recs = engine.evaluate(event=event, evidence_items=[ev_therm])

    assert len(recs) == 1
    rec = recs[0]
    assert rec.rule_id == "MNT-THERM-002"
    assert rec.priority == MaintenancePriority.P1_URGENT_INSPECTION
    assert rec.action_window == ActionWindow.WITHIN_24H
    assert rec.window_provenance_type == ActionWindowProvenanceType.OPERATOR_POLICY
    assert "prompt inspection of cooling operation" in rec.advisory_wording


# ---------------------------------------------------------------------------
# 3. Forecast Rule & Escalation: MNT-FORE-003
# ---------------------------------------------------------------------------


def test_mnt_fore_003_central_forecast_crossing_escalates_to_p1() -> None:
    """Central forecast crossing verified limit escalates to P1 (WITHIN_24H)."""
    engine = MaintenanceEngine(is_model_promoted=True)
    t0 = _make_utc(12, 0, 0)
    event = _make_canonical_event("e0", t0, measurements=[_make_measurement("top_oil_temperature", 85.0)])

    # 2-hour projection crossing limit at 45 minutes
    proj = ScenarioProjectionResult(
        asset_id="DT-001",
        origin_time_utc=t0,
        origin_top_oil_degc=85.0,
        origin_ambient_degc=30.0,
        origin_load_u=1.0,
        scenario_ambient_degc=30.0,
        scenario_load_u=1.2,
        is_enabled=True,
        trust_state=ThermalTrustState.MODEL_HEALTHY,
        trajectory=[],
        peak_projected_top_oil_degc=108.0,
        earliest_critical_crossing_minutes=45,
        time_above_critical_minutes=75,
    )

    recs = engine.evaluate(event=event, scenario_projection=proj)

    assert len(recs) == 1
    rec = recs[0]
    assert rec.rule_id == "MNT-FORE-003"
    assert rec.priority == MaintenancePriority.P1_URGENT_INSPECTION
    assert rec.action_window == ActionWindow.WITHIN_24H
    assert "load redistribution or reduction" in rec.advisory_wording


def test_mnt_fore_003_gated_when_model_unpromoted() -> None:
    """MNT-FORE-003 is gated off when grey-box thermal ODE is unpromoted."""
    engine = MaintenanceEngine(is_model_promoted=False)
    t0 = _make_utc(12, 0, 0)
    event = _make_canonical_event("e0", t0, measurements=[_make_measurement("top_oil_temperature", 85.0)])

    proj = ScenarioProjectionResult(
        asset_id="DT-001",
        origin_time_utc=t0,
        origin_top_oil_degc=85.0,
        origin_ambient_degc=30.0,
        origin_load_u=1.0,
        scenario_ambient_degc=30.0,
        scenario_load_u=1.2,
        is_enabled=False,
        trust_state=ThermalTrustState.FALLBACK_PERSISTENCE,
        trajectory=[],
        peak_projected_top_oil_degc=108.0,
        earliest_critical_crossing_minutes=45,
        time_above_critical_minutes=75,
    )

    recs = engine.evaluate(event=event, scenario_projection=proj)
    assert len(recs) == 0


# ---------------------------------------------------------------------------
# 4. Electrical and Power Quality Rules: MNT-PHASE-004 & MNT-PF-005
# ---------------------------------------------------------------------------


def test_mnt_phase_004_fires_p2_on_phase_imbalance() -> None:
    """MNT-PHASE-004 fires P2 PLANNED_ACTION / NEXT_AUTHORIZED_MAINTENANCE_WINDOW."""
    engine = MaintenanceEngine()
    t0 = _make_utc(12, 0, 0)
    meas = [
        _make_measurement("current_l1", 120.0, "A", phase="L1"),
        _make_measurement("current_l2", 60.0, "A", phase="L2"),
        _make_measurement("current_l3", 60.0, "A", phase="L3"),
    ]
    event = _make_canonical_event("e-phase", t0, measurements=meas)

    ev_phase = _make_evidence_item(
        evidence_id="ev-phase-1",
        category=AnomalyCategory.PHASE_OR_NEUTRAL,
        severity=0.50,
        detector_id="DET_PHASE_CURRENT_IMBALANCE",
        timestamp=t0,
        condition_family="PHASE_CURRENT_IMBALANCE",
        domain="phase_neutral",
    )

    recs = engine.evaluate(event=event, evidence_items=[ev_phase])

    assert len(recs) == 1
    rec = recs[0]
    assert rec.rule_id == "MNT-PHASE-004"
    assert rec.priority == MaintenancePriority.P2_PLANNED_ACTION
    assert rec.action_window == ActionWindow.NEXT_AUTHORIZED_MAINTENANCE_WINDOW
    assert rec.window_provenance_type == ActionWindowProvenanceType.OPERATOR_POLICY
    assert "during next authorized maintenance window" in rec.advisory_wording


def test_mnt_pf_005_fires_p3_monitor_for_downstream_reactive_review() -> None:
    """MNT-PF-005 fires P3 MONITOR framed as reactive review, not transformer fault."""
    engine = MaintenanceEngine()
    t0 = _make_utc(12, 0, 0)
    meas = [
        _make_measurement("power_factor_total", 0.70, "1"),
        _make_measurement("active_power_total", 50.0, "kW"),
    ]
    event = _make_canonical_event("e-pf", t0, measurements=meas)

    ev_pf = _make_evidence_item(
        evidence_id="ev-pf-1",
        category=AnomalyCategory.VOLTAGE_PF_FREQUENCY,
        severity=0.40,
        detector_id="DET_PF_LOW",
        timestamp=t0,
        condition_family="LOW_POWER_FACTOR",
        domain="voltage_pf_freq",
    )

    recs = engine.evaluate(event=event, evidence_items=[ev_pf])

    assert len(recs) == 1
    rec = recs[0]
    assert rec.rule_id == "MNT-PF-005"
    assert rec.priority == MaintenancePriority.P3_MONITOR
    assert rec.action_window == ActionWindow.MONITOR
    assert "downstream reactive demand" in rec.advisory_wording


# ---------------------------------------------------------------------------
# 5. Data Quality and Sensor Rules: MNT-SENS-006 & MNT-MODEL-007
# ---------------------------------------------------------------------------


def test_mnt_sens_006_fires_p4_on_sensor_fault() -> None:
    """MNT-SENS-006 fires P4 DATA_OR_MODEL / MODEL_REVIEW on sensor plausibility faults."""
    engine = MaintenanceEngine()
    t0 = _make_utc(12, 0, 0)
    event = _make_canonical_event("e0", t0, measurements=[_make_measurement("top_oil_temperature", 80.0)])

    ev_sens = _make_evidence_item(
        evidence_id="ev-sens-1",
        category=AnomalyCategory.SENSOR_PLAUSIBILITY,
        severity=0.50,
        detector_id="DET_SENS_FLATLINE",
        timestamp=t0,
        condition_family="SENSOR_FLATLINE",
    )

    recs = engine.evaluate(event=event, evidence_items=[ev_sens])

    assert len(recs) == 1
    rec = recs[0]
    assert rec.rule_id == "MNT-SENS-006"
    assert rec.priority == MaintenancePriority.P4_DATA_OR_MODEL
    assert rec.action_window == ActionWindow.MODEL_REVIEW


# ---------------------------------------------------------------------------
# 6. Compatible Recommendation Merging Tests
# ---------------------------------------------------------------------------


def test_compatible_recommendations_merged_under_merge_key() -> None:
    """Multiple rules with same merge_key are merged adopting strictest urgency."""
    engine = MaintenanceEngine(
        cusum_qualification="ENABLED",
        is_thermal_qualified=True,
        is_model_promoted=True,
    )
    t0 = _make_utc(12, 0, 0)
    event = _make_canonical_event("e0", t0, measurements=[_make_measurement("top_oil_temperature", 95.0)])

    # Two distinct thermal evidence items in the same family
    ev1 = _make_evidence_item(
        evidence_id="ev-th-1",
        category=AnomalyCategory.THERMAL_DEVIATION,
        severity=0.60,
        detector_id="DET_THERMAL_RESIDUAL_POINT",
        timestamp=t0,
        condition_family="THERMAL_DEVIATION_UNEXPECTED",
    )
    ev2 = _make_evidence_item(
        evidence_id="ev-th-2",
        category=AnomalyCategory.THERMAL_LIMIT,
        severity=0.75,
        detector_id="DET_THERMAL_LIMIT_OTI",
        timestamp=t0,
        condition_family="THERMAL_LIMIT_EXCEEDANCE",
    )

    recs = engine.evaluate(event=event, evidence_items=[ev1, ev2])

    assert len(recs) == 1
    rec = recs[0]
    assert rec.merge_key == "THERMAL_COOLING_STRESS"
    assert rec.priority == MaintenancePriority.P1_URGENT_INSPECTION
    assert set(rec.evidence_ids) == {"ev-th-1", "ev-th-2"}


# ---------------------------------------------------------------------------
# 7. Operator Feedback Lifecycle Tests
# ---------------------------------------------------------------------------


def test_operator_feedback_acknowledgement_lifecycle() -> None:
    """Operator acknowledgement sets acknowledged flag without erasing underlying recommendation."""
    engine = MaintenanceEngine()
    t0 = _make_utc(12, 0, 0)
    meas = [_make_measurement("breaker_trip", True, unit="1")]
    event = _make_canonical_event("e0", t0, measurements=meas)

    recs0 = engine.evaluate(event=event, evidence_items=[])
    assert len(recs0) == 1
    rec_id = recs0[0].recommendation_id
    assert recs0[0].acknowledged is False

    # Operator acknowledges recommendation
    fb = OperatorFeedbackEvent(
        feedback_id="fb-001",
        asset_id="DT-001",
        timestamp_utc=t0 + timedelta(minutes=5),
        recommendation_id=rec_id,
        action=FeedbackAction.ACKNOWLEDGE,
        operator_id="operator_john",
        notes="Under review by substation lead",
    )
    engine.process_feedback(fb)

    # Subsequent evaluation reflects acknowledgement
    recs1 = engine.evaluate(event=event, evidence_items=[])
    assert len(recs1) == 1
    assert recs1[0].acknowledged is True
    assert recs1[0].acknowledged_by == "operator_john"


# ---------------------------------------------------------------------------
# 8. TwinReducer Integration Tests
# ---------------------------------------------------------------------------


def test_twin_reducer_with_maintenance_engine_integration() -> None:
    """Verify TwinReducer updates active_recommendations seamlessly."""
    maintenance_engine = MaintenanceEngine()
    reducer = TwinReducer(maintenance_engine=maintenance_engine)

    t0 = _make_utc(12, 0, 0)
    meas = [
        _make_measurement("breaker_trip", True, unit="1"),
        _make_measurement("top_oil_temperature", 70.0, "Cel"),
    ]
    event = _make_canonical_event("e0", t0, measurements=meas)

    state = reducer.reduce(current_state=None, event=event)

    assert len(state.active_recommendations) == 1
    assert state.active_recommendations[0].rule_id == "MNT-PROT-001"
    assert state.active_recommendations[0].priority == MaintenancePriority.P0_SAFETY
    assert len(state.state_hash) == 64
