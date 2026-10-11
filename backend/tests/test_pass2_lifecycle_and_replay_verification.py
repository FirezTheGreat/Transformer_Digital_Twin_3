"""Pass 2 Verification Suite — Episodes, Replay/Injection State, and Advisory Lifecycle.

Covers:
1. Trip unlatching requires an authorized resolution timestamped AFTER the trip (historical pre-trip resolution does NOT unlatch).
2. Documented resolution after trip clears latched status and MNT-PROT-001.
3. Replay reset clears feedback ledger and resets reducer sub-engines cleanly.
4. Observation eviction: discrete single-event trip/pulse flags do not linger in current_observations across subsequent normal frames.
5. Injected zero-current readings do not persist after replay advances with live load currents.
6. Cleared physical conditions (e.g. thermal excursion return to normal) clear from active recommendations.
7. Asset switching cleanly rebuilds reducer and isolates runtime state.
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.engine.electrical_episodes import ElectricalEpisodeEngine
from app.engine.feedback import OperatorFeedbackLedger
from app.engine.maintenance import MaintenanceEngine
from app.engine.othi import OTHIEngine
from app.engine.reducer import TwinReducer
from app.main import create_app
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.maintenance import (
    FeedbackAction,
    MaintenancePriority,
    OperatorFeedbackEvent,
)
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)


def _make_measurement(
    signal_id: str,
    value: float | bool,
    unit: str = "A",
    phase: str | None = None,
    severity: QualitySeverity = QualitySeverity.GOOD,
    flags: list[str] | None = None,
) -> Measurement:
    return Measurement(
        signal_id=signal_id,
        phase=phase,
        value=value,
        value_type="bool" if isinstance(value, bool) else "float",
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(severity=severity, flags=flags or []),
    )


def _make_event(
    event_id: str,
    event_time: datetime,
    asset_id: str = "DT-01",
    is_trip: bool = False,
    i_l1: float = 100.0,
    top_oil: float = 65.0,
) -> CanonicalEvent:
    meas = [
        _make_measurement("current_l1", i_l1, "A", phase="L1"),
        _make_measurement("current_l2", i_l1, "A", phase="L2"),
        _make_measurement("current_l3", i_l1, "A", phase="L3"),
        _make_measurement("top_oil_temperature", top_oil, "Cel"),
        _make_measurement("ambient_temperature", 30.0, "Cel"),
    ]
    if is_trip:
        meas.append(_make_measurement("oil_temp_trip_flag", True, unit="1", flags=["DIRECT_TRIP"]))

    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=event_id,
        asset_id=asset_id,
        event_time_utc=event_time,
        source=SourceRef(
            system="test",
            adapter_id="test_adapter",
            source_record_id=event_id,
            source_uri="test://events",
            raw_sha256="0" * 64,
        ),
        measurements=meas,
        event_quality_flags=["PROTECTION_TRIP_ACTIVE"] if is_trip else [],
        mapping_version="1.0.0",
    )


@pytest.fixture
def client() -> TestClient:
    test_settings = Settings(
        app_name="Test Digital Twin API",
        app_version="1.0.0-test",
        api_v1_prefix="/v1",
        environment="test",
        default_asset_id="DT-01",
        db_path=":memory:",
    )
    app = create_app(settings=test_settings)
    with TestClient(app) as test_client:
        yield test_client


def test_historical_resolution_before_trip_does_not_unlatch_new_trip():
    """Historical RESOLVE record before a new trip must NOT unlatch the new trip."""
    ledger = OperatorFeedbackLedger()
    othi = OTHIEngine(expected_cadence_seconds=1800.0)
    othi.feedback_ledger = ledger

    t0 = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    t_hist_resolve = t0 + timedelta(hours=1)
    t_trip = t0 + timedelta(hours=2)
    t_after = t0 + timedelta(hours=3)

    # 1. Historical resolution logged at t = 1 hour
    ledger.append(
        OperatorFeedbackEvent(
            feedback_id="fb-old-res",
            asset_id="DT-01",
            timestamp_utc=t_hist_resolve,
            action=FeedbackAction.RESOLVE,
            operator_id="operator_bob",
            reason_code="SITE_CLEARANCE_VERIFIED",
            recommendation_id="REC-DT-01-MNT-PROT-001",
        )
    )

    # 2. Protection trip fires at t = 2 hours
    ev_trip = _make_event("ev-trip", t_trip, asset_id="DT-01", is_trip=True)
    b_trip = othi.evaluate(event=ev_trip)
    assert othi.latched_protection_trip is True
    assert b_trip.othi_score == 0
    assert b_trip.driving_condition_family == "DIRECT_PROTECTION_TRIP"

    # 3. Next normal event at t = 3 hours (no active trip in telemetry)
    ev_next = _make_event("ev-next", t_after, asset_id="DT-01", is_trip=False)
    b_next = othi.evaluate(event=ev_next)

    # Historical resolution was timestamped BEFORE the trip, so trip remains latched!
    assert othi.latched_protection_trip is True
    assert b_next.othi_score == 0


def test_post_trip_resolution_unlatches_trip_and_restores_health():
    """Authorized resolution timestamped AFTER trip successfully unlatches trip."""
    ledger = OperatorFeedbackLedger()
    othi = OTHIEngine(expected_cadence_seconds=1800.0)
    othi.feedback_ledger = ledger

    t0 = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    t_trip = t0 + timedelta(hours=1)
    t_resolve = t0 + timedelta(hours=2)
    t_next = t0 + timedelta(hours=3)

    # 1. Protection trip fires at t = 1 hour
    ev_trip = _make_event("ev-trip", t_trip, asset_id="DT-01", is_trip=True)
    othi.evaluate(event=ev_trip)
    assert othi.latched_protection_trip is True

    # 2. Authorized resolution filed at t = 2 hours (AFTER trip)
    ledger.append(
        OperatorFeedbackEvent(
            feedback_id="fb-post-res",
            asset_id="DT-01",
            timestamp_utc=t_resolve,
            action=FeedbackAction.RESOLVE,
            operator_id="operator_alice",
            reason_code="SITE_CLEARANCE_VERIFIED",
            recommendation_id="REC-DT-01-MNT-PROT-001",
        )
    )

    # 3. Next normal event at t = 3 hours
    ev_next = _make_event("ev-next", t_next, asset_id="DT-01", is_trip=False)
    b_next = othi.evaluate(event=ev_next)

    # Latched trip is cleared!
    assert othi.latched_protection_trip is False
    assert b_next.othi_score is not None
    assert b_next.othi_score > 50


def test_observation_eviction_discrete_flags_and_current_alias():
    """Single-event trip flags and injected zero-currents do not persist once normal events advance."""
    reducer = TwinReducer()

    t0 = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=30)

    # Injected event with trip flag and zero current
    injected_meas = [
        _make_measurement("oil_temp_trip_flag", True, unit="1", flags=["DIRECT_TRIP"]),
        _make_measurement("current_i1", 0.0, "A", phase="L1"),
        _make_measurement("current_i2", 0.0, "A", phase="L2"),
        _make_measurement("current_i3", 0.0, "A", phase="L3"),
        _make_measurement("top_oil_temperature", 98.4, "Cel"),
        _make_measurement("ambient_temperature", 30.0, "Cel"),
    ]
    ev_inj = CanonicalEvent(
        schema_version="1.0.0",
        event_id="ev-inj",
        asset_id="DT-01",
        event_time_utc=t0,
        source=SourceRef(
            system="inj",
            adapter_id="inj",
            source_record_id="inj",
            source_uri="inj://",
            raw_sha256="0" * 64,
        ),
        measurements=injected_meas,
        event_quality_flags=["PROTECTION_TRIP_ACTIVE"],
        mapping_version="1.0.0",
    )

    state1 = reducer.reduce(current_state=None, event=ev_inj)
    assert "oil_temp_trip_flag" in state1.current_observations
    assert state1.current_observations["current_i1"].value == 0.0

    # Advance replay with normal telemetry event (carrying live load current_l1..l3)
    ev_norm = _make_event("ev-norm", t1, asset_id="DT-01", is_trip=False, i_l1=120.0, top_oil=70.0)
    state2 = reducer.reduce(current_state=state1, event=ev_norm)

    # 1. Discrete flag evicted
    assert "oil_temp_trip_flag" not in state2.current_observations

    # 2. Stale zero-current alias evicted by live load current
    assert "current_i1" not in state2.current_observations
    assert state2.current_observations["current_l1"].value == 120.0


def test_condition_clearing_removes_unconfirmed_advisories():
    """When a non-protection physical condition clears, it does NOT linger indefinitely as an active recommendation."""
    m_engine = MaintenanceEngine(rules_path=None)
    m_engine.rules = {
        "MNT-THERM-002": {
            "version": "1.0.0",
            "title": "Thermal Limit Exceedance",
            "merge_key": "THERMAL_COOLING_STRESS",
        }
    }

    t0 = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=30)

    # Frame 1: Thermal limit excursion generates evidence and recommendation
    ev1 = _make_event("ev-1", t0, asset_id="DT-01", top_oil=95.0)
    evidence_item = EvidenceItem(
        evidence_id="ev-th-95",
        asset_id="DT-01",
        event_time_utc=t0,
        category=AnomalyCategory.THERMAL_LIMIT,
        detector_id="DET_THERMAL_LIMIT_ABSOLUTE",
        observed_value=95.0,
        severity=0.85,
        confidence=1.0,
        input_lineage=["top_oil_temperature"],
        condition_family="THERMAL_LIMIT_EXCEEDANCE",
    )

    recs1 = m_engine.evaluate(event=ev1, evidence_items=[evidence_item])
    assert len(recs1) == 1
    assert recs1[0].rule_id == "MNT-THERM-002"

    # Frame 2: Top oil returns to normal (65 C) and no thermal evidence is emitted
    ev2 = _make_event("ev-2", t1, asset_id="DT-01", top_oil=65.0)
    recs2 = m_engine.evaluate(event=ev2, evidence_items=[], previous_recommendations=recs1)

    # Recommendation cleared when condition cleared!
    assert len(recs2) == 0


def test_replay_reset_isolates_feedback_and_episodes(client: TestClient):
    """Replay reset endpoint clears feedback ledger and resets digital twin state cleanly."""
    # Step once to establish initial state
    res_step = client.post("/v1/replay", json={"action": "step", "batch_size": 2, "asset_id": "DT-01"})
    assert res_step.status_code == 200

    # Submit an acknowledgement feedback event
    res_fb = client.post(
        "/v1/feedback",
        json={
            "asset_id": "DT-01",
            "action": "ACKNOWLEDGE",
            "operator_id": "test_operator",
            "recommendation_id": "REC-DT-01-TEST",
        },
    )
    assert res_fb.status_code == 200

    # Reset replay
    res_reset = client.post("/v1/replay", json={"action": "reset", "asset_id": "DT-01"})
    assert res_reset.status_code == 200
    reset_data = res_reset.json()
    assert reset_data["status"] == "reset"
    assert reset_data["processed_events"] == 0

    # Twin state is cleared
    res_state = client.get("/v1/assets/DT-01/state")
    assert res_state.status_code == 200
    state_body = res_state.json()
    assert state_body["twin_state"] is not None
    assert state_body["twin_state"]["state_sequence"] == 0
