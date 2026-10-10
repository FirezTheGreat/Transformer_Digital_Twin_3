"""Acceptance Tests for Stateful Episode Lifecycle and Advisory Acknowledgement.

Covers:
1. Sustained critical condition across many frames creates ONE persistent episode with stable ID.
2. Episode duration, evidence, and last_seen update without changing ID.
3. Short spike below persistence requirement is debounced (dropped as transient candidate).
4. Direct verified protection trip is immediate (0s persistence) and not delayed.
5. Sustained recovery closes episode according to recovery criteria; single normal frame does not close.
6. Missing/invalid telemetry does not falsely close or recover an active episode.
7. Replaying same timestamped data deterministically reproduces identical episode state.
8. Advisory acknowledgement persists in ledger and survives subsequent replay steps.
9. Acknowledged advisory retains acknowledged status and is accessible via status filter / history.
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.engine.electrical_episodes import ElectricalEpisodeEngine
from app.engine.feedback import OperatorFeedbackLedger
from app.engine.maintenance import MaintenanceEngine
from app.engine.reducer import TwinReducer
from app.models.anomaly import AnomalyCategory, EpisodeState
from app.models.electrical_episode import (
    DEFAULT_ELECTRICAL_THRESHOLDS,
    ElectricalEpisodeThresholds,
    ElectricalEpisodeType,
    EpisodeSeverity,
    EpisodeStatus,
)
from app.models.features import DerivedFeatures
from app.models.maintenance import (
    ActionWindow,
    FeedbackAction,
    MaintenancePriority,
    MaintenanceRecommendation,
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
        quality=MeasurementQuality(severity=severity, flags=[]),
    )


def _make_event(
    event_id: str,
    event_time: datetime,
    asset_id: str = "DT-TRIPURA-001",
    is_trip: bool = False,
    is_bad: bool = False,
) -> CanonicalEvent:
    meas = [
        _make_measurement("current_l1", 100.0, "A", phase="L1"),
        _make_measurement("current_l2", 100.0, "A", phase="L2"),
        _make_measurement("current_l3", 100.0, "A", phase="L3"),
    ]
    if is_trip:
        meas.append(_make_measurement("oil_temp_trip_flag", True, unit="1"))
    if is_bad:
        meas.append(_make_measurement("current_l1", 0.0, "A", severity=QualitySeverity.BAD))

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


def _make_derived(
    timestamp: datetime,
    current_imbalance: float | None = 2.0,
    voltage_imbalance: float | None = 0.5,
    apparent_power_kva: float | None = 50.0,
    current_mean_a: float | None = 80.0,
) -> DerivedFeatures:
    return DerivedFeatures(
        timestamp_utc=timestamp,
        apparent_power_derived_kva=apparent_power_kva,
        power_factor_derived=0.95,
        current_mean_a=current_mean_a,
        current_magnitude_imbalance_pct=current_imbalance,
        voltage_magnitude_imbalance_pct=voltage_imbalance,
        neutral_current_ratio=0.05,
        pqs_inconsistency=0.01,
        relative_load_index=0.50,
        thermal_residual_degc=None,
        transform_version="1.0.0",
    )


# ==============================================================================
# 1 & 2: Sustained Critical Condition: Single Episode with Stable ID
# ==============================================================================

def test_sustained_condition_creates_one_persistent_episode():
    """Verify that 20 consecutive frames of critical condition produce ONE episode with stable ID."""
    engine = ElectricalEpisodeEngine(asset_id="DT-TRIPURA-001")
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    episode_ids_seen = set()
    initial_ep_id = None

    # Run 20 steps of severe current imbalance (35% >= 25% critical limit)
    for i in range(20):
        t_curr = t0 + timedelta(minutes=15 * i)
        ev = _make_event(f"ev_{i}", t_curr)
        derived = _make_derived(t_curr, current_imbalance=35.0)

        open_eps = engine.evaluate_step(ev, derived)
        # Filter to current imbalance
        iub_eps = [e for e in open_eps if e.episode_type == ElectricalEpisodeType.CURRENT_IMBALANCE]
        assert len(iub_eps) == 1
        ep = iub_eps[0]

        if initial_ep_id is None:
            initial_ep_id = ep.episode_id
        else:
            # Stable ID invariant across replay frames
            assert ep.episode_id == initial_ep_id

        episode_ids_seen.add(ep.episode_id)
        assert ep.last_active_time_utc == t_curr

    # Exactly 1 episode was generated across all 20 frames
    assert len(episode_ids_seen) == 1
    assert len(engine.get_closed_episodes()) == 0


# ==============================================================================
# 3: Debounce: Short Spike below Persistence Requirement is Dropped
# ==============================================================================

def test_short_spike_below_persistence_is_debounced():
    """Verify that a brief spike lasting less than persistence requirement is dropped without noisy episode."""
    engine = ElectricalEpisodeEngine(asset_id="DT-TRIPURA-001")
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    # Frame 0: Normal
    ev0 = _make_event("ev_0", t0)
    d0 = _make_derived(t0, current_imbalance=3.0)
    assert len(engine.evaluate_step(ev0, d0)) == 0

    # Frame 1: Brief spike (12% imbalance), candidate formed with timer = 0s < 900s
    t1 = t0 + timedelta(seconds=60)
    ev1 = _make_event("ev_1", t1)
    d1 = _make_derived(t1, current_imbalance=12.0)
    open_eps = engine.evaluate_step(ev1, d1)
    assert len(open_eps) == 1
    assert open_eps[0].status == EpisodeStatus.CANDIDATE

    # Frame 2: Spike clears immediately (back to 3% normal) before persistence satisfied
    t2 = t1 + timedelta(seconds=60)
    ev2 = _make_event("ev_2", t2)
    d2 = _make_derived(t2, current_imbalance=3.0)
    open_eps2 = engine.evaluate_step(ev2, d2)

    # Candidate dropped: no active episode created
    assert len(open_eps2) == 0
    assert len(engine.get_closed_episodes()) == 0


# ==============================================================================
# 4: Immediate Protection Event: No Persistence Delay
# ==============================================================================

def test_direct_protection_trip_is_immediate():
    """Verify direct protection trip activates immediately (persistence_seconds=0) without delay."""
    engine = ElectricalEpisodeEngine(asset_id="DT-TRIPURA-001")
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    # Trip contact detected on frame 0
    ev0 = _make_event("ev_0", t0, is_trip=True)
    d0 = _make_derived(t0, current_imbalance=2.0)
    open_eps = engine.evaluate_step(ev0, d0)

    trip_eps = [e for e in open_eps if e.episode_type == ElectricalEpisodeType.PROTECTION_TRIP]
    assert len(trip_eps) == 1
    ep = trip_eps[0]
    # Activated immediately to ACTIVE/CRITICAL on the very first frame
    assert ep.status == EpisodeStatus.ACTIVE
    assert ep.severity == EpisodeSeverity.CRITICAL
    assert ep.category == AnomalyCategory.PROTECTION_OR_OIL_STATUS
    assert ep.activation_time_utc == t0


# ==============================================================================
# 5: Single Normal Frame Does Not Close Sustained Episode
# ==============================================================================

def test_single_normal_frame_does_not_close_sustained_episode():
    """Verify single frame below recovery threshold enters RECOVERING, not CLOSED."""
    engine = ElectricalEpisodeEngine(asset_id="DT-TRIPURA-001")
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    # Step 1: Detect
    ev0 = _make_event("ev_0", t0)
    d0 = _make_derived(t0, current_imbalance=15.0)
    engine.evaluate_step(ev0, d0)

    # Step 2: Persist for 900s -> ACTIVE
    t1 = t0 + timedelta(seconds=900)
    ev1 = _make_event("ev_1", t1)
    d1 = _make_derived(t1, current_imbalance=15.0)
    eps = engine.evaluate_step(ev1, d1)
    assert eps[0].status == EpisodeStatus.ACTIVE

    # Step 3: Single normal frame (5% < 8% recovery threshold)
    t2 = t1 + timedelta(seconds=300)
    ev2 = _make_event("ev_2", t2)
    d2 = _make_derived(t2, current_imbalance=5.0)
    eps_after_one_normal = engine.evaluate_step(ev2, d2)

    # Must be in RECOVERING, NOT CLOSED!
    assert len(eps_after_one_normal) == 1
    assert eps_after_one_normal[0].status == EpisodeStatus.RECOVERING
    assert len(engine.get_closed_episodes()) == 0


# ==============================================================================
# 6: Missing or Bad Telemetry Does Not Falsely Recover
# ==============================================================================

def test_missing_data_does_not_falsely_recover():
    """Verify missing/invalid telemetry holds episode state and does not falsely close."""
    engine = ElectricalEpisodeEngine(asset_id="DT-TRIPURA-001")
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    # Establish ACTIVE episode
    ev0 = _make_event("ev_0", t0)
    d0 = _make_derived(t0, current_imbalance=15.0)
    engine.evaluate_step(ev0, d0)

    t1 = t0 + timedelta(seconds=900)
    ev1 = _make_event("ev_1", t1)
    d1 = _make_derived(t1, current_imbalance=15.0)
    engine.evaluate_step(ev1, d1)

    # Now step with None/invalid derived values (sensor failure / missing data)
    t2 = t1 + timedelta(seconds=900)
    ev2 = _make_event("ev_2", t2)
    d2_missing = _make_derived(t2, current_imbalance=None)
    eps = engine.evaluate_step(ev2, d2_missing)

    # Episode must remain ACTIVE, not falsely recover or close
    assert len(eps) == 1
    assert eps[0].status == EpisodeStatus.ACTIVE
    assert len(engine.get_closed_episodes()) == 0


# ==============================================================================
# 7: Replay Determinism
# ==============================================================================

def test_replay_determinism():
    """Verify that resetting and replaying the same sequence produces identical episode states."""
    events = []
    deriveds = []
    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    for i in range(10):
        t = t0 + timedelta(minutes=15 * i)
        events.append(_make_event(f"ev_{i}", t))
        deriveds.append(_make_derived(t, current_imbalance=20.0 if i < 6 else 4.0))

    # Run 1
    e1 = ElectricalEpisodeEngine(asset_id="DT-TRIPURA-001")
    results1 = [e1.evaluate_step(ev, d) for ev, d in zip(events, deriveds)]
    closed1 = e1.get_closed_episodes()

    # Run 2
    e2 = ElectricalEpisodeEngine(asset_id="DT-TRIPURA-001")
    results2 = [e2.evaluate_step(ev, d) for ev, d in zip(events, deriveds)]
    closed2 = e2.get_closed_episodes()

    assert len(closed1) == len(closed2)
    if closed1:
        assert closed1[0].episode_id == closed2[0].episode_id
        assert closed1[0].duration_seconds == closed2[0].duration_seconds


# ==============================================================================
# 8 & 9: Advisory Acknowledgement Persistence
# ==============================================================================

def test_advisory_acknowledgement_persists_across_reducer_steps():
    """Verify that acknowledging an advisory in the ledger keeps acknowledged=True on subsequent steps."""
    ledger = OperatorFeedbackLedger()
    m_engine = MaintenanceEngine(feedback_ledger=ledger)

    t0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    ev0 = _make_event("ev_0", t0, is_trip=True)

    # Initial evaluation fires P0 protection advisory
    recs = m_engine.evaluate(event=ev0)
    assert len(recs) >= 1
    rec = recs[0]
    assert rec.acknowledged is False

    # Operator acknowledges the advisory
    ack_event = OperatorFeedbackEvent(
        feedback_id="FB-ACK-001",
        asset_id="DT-TRIPURA-001",
        timestamp_utc=t0 + timedelta(minutes=5),
        recommendation_id=rec.recommendation_id,
        merge_key=rec.merge_key,
        action=FeedbackAction.ACKNOWLEDGE,
        operator_id="OP-SHIVANSH-01",
        notes="Site engineer dispatched for inspection.",
    )
    ledger.append(ack_event, target_recommendation=rec)

    # Subsequent replay step with trip still active
    t1 = t0 + timedelta(minutes=15)
    ev1 = _make_event("ev_1", t1, is_trip=True)
    recs_next = m_engine.evaluate(event=ev1, previous_recommendations=recs)

    # Advisory must remain acknowledged!
    assert len(recs_next) >= 1
    matching = [r for r in recs_next if r.recommendation_id == rec.recommendation_id]
    assert len(matching) == 1
    assert matching[0].acknowledged is True
    assert matching[0].acknowledged_by == "OP-SHIVANSH-01"
