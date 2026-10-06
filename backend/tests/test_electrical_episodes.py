"""Comprehensive deterministic test suite for Phase 5.1 Stateful Electrical Episode Engine.

Verifies:
1. Basic FSM Lifecycle (NORMAL -> CANDIDATE -> ACTIVE -> RECOVERING -> CLOSED).
2. Hysteresis & Anti-Chatter (T_on vs T_off, bounce during recovery).
3. Deterministic Severity Transitions (WARNING vs CRITICAL escalation).
4. Quality Gating (BAD/missing inputs do not create false asset episodes).
5. Low Power Factor Isolation (suppression when unloaded S < 10 kVA).
6. PQS Inconsistency Semantic Isolation (strictly DATA_QUALITY, not transformer fault).
7. Neutral Current Ratio Validity Floors (suppression when unloaded).
8. Deterministic Recurrence Tracking (separated episodes increment recurrence).
9. Elapsed-Time Timing & Gap Handling.
10. Checkpoint & Restart State Equivalence.
11. TwinReducer Integration & Replay Determinism.
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.engine.electrical_episodes import ElectricalEpisodeEngine
from app.engine.reducer import TwinReducer
from app.models.anomaly import AnomalyCategory, EpisodeState
from app.models.electrical_episode import (
    DEFAULT_ELECTRICAL_THRESHOLDS,
    ElectricalEpisodeThresholds,
    ElectricalEpisodeType,
    EpisodeSeverity,
    EpisodeStatus,
    EvidenceGrade,
)
from app.models.features import DerivedFeatures
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)


def _make_measurement(
    signal_id: str,
    value: float,
    unit: str = "A",
    phase: str | None = None,
    severity: QualitySeverity = QualitySeverity.GOOD,
) -> Measurement:
    return Measurement(
        signal_id=signal_id,
        phase=phase,  # type: ignore[arg-type]
        value=value,
        value_type="float",
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(severity=severity, flags=[]),
    )


def _make_event(
    event_id: str,
    event_time: datetime,
    asset_id: str = "tripura_dt_01",
    severity: QualitySeverity = QualitySeverity.GOOD,
) -> CanonicalEvent:
    measurements = [
        _make_measurement("current_l1", 100.0, "A", phase="L1", severity=severity),
        _make_measurement("current_l2", 100.0, "A", phase="L2", severity=severity),
        _make_measurement("current_l3", 100.0, "A", phase="L3", severity=severity),
        _make_measurement("voltage_l1", 230.0, "V", phase="L1", severity=severity),
        _make_measurement("voltage_l2", 230.0, "V", phase="L2", severity=severity),
        _make_measurement("voltage_l3", 230.0, "V", phase="L3", severity=severity),
    ]
    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=event_id,
        asset_id=asset_id,
        event_time_utc=event_time,
        received_time_utc=None,
        source=SourceRef(
            system="tripura_csv",
            adapter_id="tripura_v1",
            source_record_id=f"row_{event_id}",
            source_uri="data/test.csv",
            raw_sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        ),
        measurements=measurements,
        event_quality_flags=[],
        mapping_version="tripura-map-1.0.0",
    )


def _make_derived(
    timestamp: datetime,
    current_imbalance: float | None = 2.0,
    voltage_imbalance: float | None = 0.5,
    neutral_ratio: float | None = 0.05,
    power_factor: float | None = 0.95,
    pqs_inconsistency: float | None = 0.01,
    apparent_power_kva: float | None = 50.0,
    current_mean_a: float | None = 80.0,
) -> DerivedFeatures:
    return DerivedFeatures(
        timestamp_utc=timestamp,
        apparent_power_derived_kva=apparent_power_kva,
        power_factor_derived=power_factor,
        current_mean_a=current_mean_a,
        current_magnitude_imbalance_pct=current_imbalance,
        voltage_magnitude_imbalance_pct=voltage_imbalance,
        neutral_current_ratio=neutral_ratio,
        pqs_inconsistency=pqs_inconsistency,
        relative_load_index=apparent_power_kva / 142.898 if apparent_power_kva else None,
        thermal_residual_degc=None,
        transform_version="1.0.0",
    )


# ---------------------------------------------------------------------------
# 1. Basic FSM Lifecycle Test
# ---------------------------------------------------------------------------

def test_basic_lifecycle_current_imbalance():
    """Verify NORMAL -> CANDIDATE -> ACTIVE -> RECOVERING -> CLOSED lifecycle."""
    engine = ElectricalEpisodeEngine(asset_id="tripura_dt_01")
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    # Step 1: Normal input (imbalance = 3.0% < 10.0%) -> No episode
    ev1 = _make_event("ev_1", t0)
    d1 = _make_derived(t0, current_imbalance=3.0)
    open_eps = engine.evaluate_step(ev1, d1)
    assert len(open_eps) == 0
    assert len(engine.get_closed_episodes()) == 0

    # Step 2: 10:15 - Condition detected (imbalance = 12.0% >= 10.0% warning threshold)
    # Becomes CANDIDATE because persistence requirement (900s) is not yet met
    t1 = t0 + timedelta(minutes=15)
    ev2 = _make_event("ev_2", t1)
    d2 = _make_derived(t1, current_imbalance=12.0)
    open_eps = engine.evaluate_step(ev2, d2)
    assert len(open_eps) == 1
    ep = open_eps[0]
    assert ep.episode_type == ElectricalEpisodeType.CURRENT_IMBALANCE
    assert ep.status == EpisodeStatus.CANDIDATE
    assert ep.severity == EpisodeSeverity.WARNING
    assert ep.recurrence_count == 1
    assert ep.activation_time_utc is None

    # Step 3: 10:30 - Condition persists (imbalance = 14.0%) for 15 min (900s dt)
    # Transitions from CANDIDATE to ACTIVE
    t2 = t1 + timedelta(minutes=15)
    ev3 = _make_event("ev_3", t2)
    d3 = _make_derived(t2, current_imbalance=14.0)
    open_eps = engine.evaluate_step(ev3, d3)
    assert len(open_eps) == 1
    ep = open_eps[0]
    assert ep.status == EpisodeStatus.ACTIVE
    assert ep.activation_time_utc == t2
    assert ep.peak_value == 14.0
    assert ep.duration_seconds == 900.0  # from 10:15 to 10:30 is 15m = 900s

    # Step 4: 10:45 - Condition continues (imbalance = 13.0%)
    t3 = t2 + timedelta(minutes=15)
    ev4 = _make_event("ev_4", t3)
    d4 = _make_derived(t3, current_imbalance=13.0)
    open_eps = engine.evaluate_step(ev4, d4)
    assert len(open_eps) == 1
    assert open_eps[0].status == EpisodeStatus.ACTIVE
    assert open_eps[0].peak_value == 14.0

    # Step 5: 11:00 - Condition drops below recovery threshold (imbalance = 5.0% < 8.0%)
    # Enters RECOVERING state (recovery timer started)
    t4 = t3 + timedelta(minutes=15)
    ev5 = _make_event("ev_5", t4)
    d5 = _make_derived(t4, current_imbalance=5.0)
    open_eps = engine.evaluate_step(ev5, d5)
    assert len(open_eps) == 1
    ep = open_eps[0]
    assert ep.status == EpisodeStatus.RECOVERING
    assert ep.recovery_start_time_utc == t4

    # Step 6: 11:15 - Condition remains recovered for full recovery duration (15m = 900s)
    # Transitions to CLOSED and moves to closed_episodes
    t5 = t4 + timedelta(minutes=15)
    ev6 = _make_event("ev_6", t5)
    d6 = _make_derived(t5, current_imbalance=4.0)
    open_eps = engine.evaluate_step(ev6, d6)
    assert len(open_eps) == 0
    closed_eps = engine.get_closed_episodes()
    assert len(closed_eps) == 1
    c_ep = closed_eps[0]
    assert c_ep.status == EpisodeStatus.CLOSED
    assert c_ep.closed_time_utc == t5
    assert c_ep.peak_value == 14.0
    assert c_ep.duration_seconds == 3600.0  # 10:15 to 11:15 = 1 hour


# ---------------------------------------------------------------------------
# 2. Hysteresis and Anti-Chatter Test
# ---------------------------------------------------------------------------

def test_hysteresis_and_recovery_chatter_prevention():
    """Verify that fluctuating within the hysteresis band (8.0% - 10.0%) does not flap."""
    engine = ElectricalEpisodeEngine(asset_id="tripura_dt_01")
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Activate episode
    engine.evaluate_step(_make_event("e1", t0), _make_derived(t0, current_imbalance=12.0))
    t1 = t0 + timedelta(minutes=15)
    engine.evaluate_step(_make_event("e2", t1), _make_derived(t1, current_imbalance=12.0))
    assert engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE].status == EpisodeStatus.ACTIVE

    # 2. Value drops to 9.0% (between T_off=8.0% and T_on=10.0%) -> Remains ACTIVE (not RECOVERING)
    t2 = t1 + timedelta(minutes=15)
    engine.evaluate_step(_make_event("e3", t2), _make_derived(t2, current_imbalance=9.0))
    assert engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE].status == EpisodeStatus.ACTIVE

    # 3. Value drops to 6.0% (< T_off=8.0%) -> Enters RECOVERING
    t3 = t2 + timedelta(minutes=15)
    engine.evaluate_step(_make_event("e4", t3), _make_derived(t3, current_imbalance=6.0))
    assert engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE].status == EpisodeStatus.RECOVERING

    # 4. Value bounces back to 11.0% (> T_on=10.0%) before recovery timer completes ->
    # Anti-chatter: returns directly to ACTIVE without closing or creating a new episode
    t4 = t3 + timedelta(minutes=5)
    engine.evaluate_step(_make_event("e5", t4), _make_derived(t4, current_imbalance=11.0))
    assert engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE].status == EpisodeStatus.ACTIVE
    assert engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE].recovery_start_time_utc is None
    assert len(engine.get_closed_episodes()) == 0


# ---------------------------------------------------------------------------
# 3. Severity Transitions Test (WARNING -> CRITICAL)
# ---------------------------------------------------------------------------

def test_severity_escalation_voltage_imbalance():
    """Verify deterministic escalation from WARNING (2.0%) to CRITICAL (5.0%)."""
    engine = ElectricalEpisodeEngine(asset_id="tripura_dt_01")
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    # Warning activation (voltage imbalance = 2.5% >= 2.0%)
    engine.evaluate_step(_make_event("e1", t0), _make_derived(t0, voltage_imbalance=2.5))
    t1 = t0 + timedelta(minutes=15)
    engine.evaluate_step(_make_event("e2", t1), _make_derived(t1, voltage_imbalance=2.5))
    ep = engine.active_episodes[ElectricalEpisodeType.VOLTAGE_IMBALANCE]
    assert ep.status == EpisodeStatus.ACTIVE
    assert ep.severity == EpisodeSeverity.WARNING

    # Escalation to CRITICAL (voltage imbalance = 5.5% >= 5.0%)
    t2 = t1 + timedelta(minutes=15)
    engine.evaluate_step(_make_event("e3", t2), _make_derived(t2, voltage_imbalance=5.5))
    ep = engine.active_episodes[ElectricalEpisodeType.VOLTAGE_IMBALANCE]
    assert ep.status == EpisodeStatus.ACTIVE
    assert ep.severity == EpisodeSeverity.CRITICAL
    assert ep.peak_severity == EpisodeSeverity.CRITICAL
    assert ep.peak_value == 5.5


# ---------------------------------------------------------------------------
# 4. Low Power Factor Isolation Test (Unloaded Suppression)
# ---------------------------------------------------------------------------

def test_low_power_factor_unloaded_suppression():
    """Verify low PF under light load (S < 10 kVA) is suppressed, but triggers under active load."""
    engine = ElectricalEpisodeEngine(asset_id="tripura_dt_01")
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Low PF (0.60) when transformer is idle / unloaded (S = 4.0 kVA < 10.0 kVA floor)
    # Must NOT trigger any episode because magnetizing current naturally has low PF!
    engine.evaluate_step(
        _make_event("e1", t0),
        _make_derived(t0, power_factor=0.60, apparent_power_kva=4.0),
    )
    t1 = t0 + timedelta(minutes=15)
    engine.evaluate_step(
        _make_event("e2", t1),
        _make_derived(t1, power_factor=0.60, apparent_power_kva=4.0),
    )
    assert ElectricalEpisodeType.LOW_POWER_FACTOR not in engine.active_episodes

    # 2. Low PF (0.70 <= 0.80 warning) under active load (S = 45.0 kVA >= 10.0 kVA) -> Triggers episode
    t2 = t1 + timedelta(minutes=15)
    engine.evaluate_step(
        _make_event("e3", t2),
        _make_derived(t2, power_factor=0.70, apparent_power_kva=45.0),
    )
    t3 = t2 + timedelta(minutes=15)
    engine.evaluate_step(
        _make_event("e4", t3),
        _make_derived(t3, power_factor=0.70, apparent_power_kva=45.0),
    )
    assert ElectricalEpisodeType.LOW_POWER_FACTOR in engine.active_episodes
    ep = engine.active_episodes[ElectricalEpisodeType.LOW_POWER_FACTOR]
    assert ep.status == EpisodeStatus.ACTIVE
    assert ep.severity == EpisodeSeverity.WARNING


# ---------------------------------------------------------------------------
# 5. P-Q-S Inconsistency Semantic Isolation Test (Data Quality vs Fault)
# ---------------------------------------------------------------------------

def test_pqs_inconsistency_semantic_isolation():
    """Verify PQS inconsistency is strictly categorized as DATA_QUALITY / measurement discrepancy."""
    engine = ElectricalEpisodeEngine(asset_id="tripura_dt_01")
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    # Persistent PQS inconsistency (0.25 >= 0.15 warning threshold)
    engine.evaluate_step(_make_event("e1", t0), _make_derived(t0, pqs_inconsistency=0.25))
    t1 = t0 + timedelta(minutes=15)
    engine.evaluate_step(_make_event("e2", t1), _make_derived(t1, pqs_inconsistency=0.25))

    ep = engine.active_episodes[ElectricalEpisodeType.PQS_INCONSISTENCY]
    assert ep.status == EpisodeStatus.ACTIVE
    assert ep.category == AnomalyCategory.DATA_QUALITY
    assert ep.evidence_grade == EvidenceGrade.GRADE_B_DATA_QUALITY

    # Assert hypotheses point to instrumentation, NOT transformer internal fault
    for hyp in ep.hypothesis_codes:
        assert "TRANSFORMER_FAULT" not in hyp
        assert "CORE_DAMAGE" not in hyp
        assert "WINDING_BREAKDOWN" not in hyp
    assert "INSTRUMENTATION_CALIBRATION_MISMATCH" in ep.hypothesis_codes


# ---------------------------------------------------------------------------
# 6. Neutral Current Ratio Validity Floor Test
# ---------------------------------------------------------------------------

def test_neutral_current_ratio_validity_floor():
    """Verify neutral current ratio is suppressed when mean current is below noise floor (5A)."""
    engine = ElectricalEpisodeEngine(asset_id="tripura_dt_01")
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    # High neutral ratio (0.50) but mean current is 2.0A (< 5.0A floor) -> Suppressed
    engine.evaluate_step(
        _make_event("e1", t0),
        _make_derived(t0, neutral_ratio=0.50, current_mean_a=2.0),
    )
    t1 = t0 + timedelta(minutes=15)
    engine.evaluate_step(
        _make_event("e2", t1),
        _make_derived(t1, neutral_ratio=0.50, current_mean_a=2.0),
    )
    assert ElectricalEpisodeType.NEUTRAL_CURRENT_RATIO not in engine.active_episodes


# ---------------------------------------------------------------------------
# 7. Quality Gating Test
# ---------------------------------------------------------------------------

def test_quality_gating_bad_telemetry_no_false_episodes():
    """Verify missing or non-finite features do not trigger false candidate episodes."""
    engine = ElectricalEpisodeEngine(asset_id="tripura_dt_01")
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    # Derived features with None values (due to BAD or missing raw measurements)
    d_bad = DerivedFeatures(
        timestamp_utc=t0,
        apparent_power_derived_kva=None,
        power_factor_derived=None,
        current_mean_a=None,
        current_magnitude_imbalance_pct=None,
        voltage_magnitude_imbalance_pct=None,
        neutral_current_ratio=None,
        pqs_inconsistency=None,
        relative_load_index=None,
        thermal_residual_degc=None,
        transform_version="1.0.0",
    )
    open_eps = engine.evaluate_step(_make_event("e1", t0, severity=QualitySeverity.BAD), d_bad)
    assert len(open_eps) == 0


# ---------------------------------------------------------------------------
# 8. Deterministic Recurrence Tracking Test
# ---------------------------------------------------------------------------

def test_recurrence_tracking_multiple_episodes():
    """Verify multiple separated episodes increment the recurrence counter deterministically."""
    engine = ElectricalEpisodeEngine(asset_id="tripura_dt_01")
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    # Episode 1: 10:00 -> 11:00
    engine.evaluate_step(_make_event("e1", t0), _make_derived(t0, current_imbalance=15.0))
    engine.evaluate_step(_make_event("e2", t0 + timedelta(minutes=15)), _make_derived(t0 + timedelta(minutes=15), current_imbalance=15.0))
    assert engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE].recurrence_count == 1

    # Recover Episode 1: 11:00 -> 11:15
    engine.evaluate_step(_make_event("e3", t0 + timedelta(minutes=30)), _make_derived(t0 + timedelta(minutes=30), current_imbalance=5.0))
    engine.evaluate_step(_make_event("e4", t0 + timedelta(minutes=45)), _make_derived(t0 + timedelta(minutes=45), current_imbalance=5.0))
    assert len(engine.get_closed_episodes()) == 1
    assert engine.get_closed_episodes()[0].recurrence_count == 1

    # Episode 2 (Separated occurrence at 14:00)
    t_ep2 = datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
    engine.evaluate_step(_make_event("e5", t_ep2), _make_derived(t_ep2, current_imbalance=16.0))
    engine.evaluate_step(_make_event("e6", t_ep2 + timedelta(minutes=15)), _make_derived(t_ep2 + timedelta(minutes=15), current_imbalance=16.0))
    assert engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE].recurrence_count == 2


# ---------------------------------------------------------------------------
# 9. Transient Non-Persisting Spike Test
# ---------------------------------------------------------------------------

def test_transient_spike_does_not_become_active_or_increment_recurrence():
    """Verify single-frame transient spike is dropped without becoming ACTIVE or incrementing recurrence."""
    engine = ElectricalEpisodeEngine(asset_id="tripura_dt_01")
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    # Single spike at 10:00 -> CANDIDATE
    engine.evaluate_step(_make_event("e1", t0), _make_derived(t0, current_imbalance=15.0))
    assert len(engine.active_episodes) == 1
    assert engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE].status == EpisodeStatus.CANDIDATE

    # Clears at 10:15 before persistence is met -> Dropped
    t1 = t0 + timedelta(minutes=15)
    engine.evaluate_step(_make_event("e2", t1), _make_derived(t1, current_imbalance=4.0))
    assert len(engine.active_episodes) == 0
    assert len(engine.get_closed_episodes()) == 0
    assert engine.recurrence_counts.get(ElectricalEpisodeType.CURRENT_IMBALANCE, 0) == 0


# ---------------------------------------------------------------------------
# 10. Gap Handling Test
# ---------------------------------------------------------------------------

def test_monitoring_gap_freezes_active_episode():
    """Verify long gap (>1.0h) flags is_monitoring_gap on active episodes and resets candidate."""
    engine = ElectricalEpisodeEngine(asset_id="tripura_dt_01", max_gap_seconds=3600.0)
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    # Activate episode at 10:00 - 10:15
    engine.evaluate_step(_make_event("e1", t0), _make_derived(t0, current_imbalance=15.0))
    engine.evaluate_step(_make_event("e2", t0 + timedelta(minutes=15)), _make_derived(t0 + timedelta(minutes=15), current_imbalance=15.0))
    assert engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE].status == EpisodeStatus.ACTIVE

    # Gap of 3 hours until 13:15
    t_gap = t0 + timedelta(hours=3, minutes=15)
    engine.evaluate_step(_make_event("e3", t_gap), _make_derived(t_gap, current_imbalance=15.0))
    assert engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE].is_monitoring_gap is True


# ---------------------------------------------------------------------------
# 11. Checkpoint and State Restoration Test
# ---------------------------------------------------------------------------

def test_checkpoint_state_restoration_equivalence():
    """Verify get_state() and load_state() produce 100% equivalent behavior."""
    engine1 = ElectricalEpisodeEngine(asset_id="tripura_dt_01")
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    engine1.evaluate_step(_make_event("e1", t0), _make_derived(t0, current_imbalance=15.0))
    t1 = t0 + timedelta(minutes=15)
    engine1.evaluate_step(_make_event("e2", t1), _make_derived(t1, current_imbalance=15.0))

    # Export state checkpoint
    chk = engine1.get_state()

    # Create new engine and restore
    engine2 = ElectricalEpisodeEngine(asset_id="tripura_dt_01")
    engine2.load_state(chk)

    assert len(engine2.active_episodes) == len(engine1.active_episodes)
    assert engine2.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE].status == EpisodeStatus.ACTIVE
    assert engine2.recurrence_counts == engine1.recurrence_counts
    assert engine2.persistence_timers == engine1.persistence_timers


# ---------------------------------------------------------------------------
# 12. TwinReducer Integration Test
# ---------------------------------------------------------------------------

def test_twin_reducer_electrical_episodes_integration():
    """Verify TwinReducer steps ElectricalEpisodeEngine and populates TwinState.open_episodes."""
    ep_engine = ElectricalEpisodeEngine(asset_id="DT-001")
    reducer = TwinReducer(episode_engine=ep_engine)

    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    ev1 = _make_event("ev_1", t0, asset_id="DT-001")

    # Step 1
    state1 = reducer.reduce(None, ev1)
    assert state1.state_sequence == 1
    assert len(state1.open_episodes) == 0  # Imbalance is 0 on balanced event

    # Send unbalanced event
    t1 = t0 + timedelta(minutes=15)
    measurements_unbal = [
        _make_measurement("current_l1", 150.0, "A", phase="L1"),
        _make_measurement("current_l2", 50.0, "A", phase="L2"),
        _make_measurement("current_l3", 50.0, "A", phase="L3"),
        _make_measurement("voltage_l1", 230.0, "V", phase="L1"),
        _make_measurement("voltage_l2", 230.0, "V", phase="L2"),
        _make_measurement("voltage_l3", 230.0, "V", phase="L3"),
    ]
    ev2 = CanonicalEvent(
        schema_version="1.0.0",
        event_id="ev_2",
        asset_id="DT-001",
        event_time_utc=t1,
        received_time_utc=None,
        source=ev1.source,
        measurements=measurements_unbal,
        event_quality_flags=[],
        mapping_version="tripura-map-1.0.0",
    )
    state2 = reducer.reduce(state1, ev2)
    assert len(state2.open_episodes) == 1
    assert state2.open_episodes[0].state == EpisodeState.WATCH  # Candidate

    # Step again with unbalance to activate
    t2 = t1 + timedelta(minutes=15)
    ev3 = CanonicalEvent(
        schema_version="1.0.0",
        event_id="ev_3",
        asset_id="DT-001",
        event_time_utc=t2,
        received_time_utc=None,
        source=ev1.source,
        measurements=measurements_unbal,
        event_quality_flags=[],
        mapping_version="tripura-map-1.0.0",
    )
    state3 = reducer.reduce(state2, ev3)
    assert len(state3.open_episodes) == 1
    assert state3.open_episodes[0].state in (EpisodeState.WARNING, EpisodeState.CRITICAL)
    assert "CURRENT_IMBALANCE" in state3.detector_state.persistence_timers


# ---------------------------------------------------------------------------
# 13. Exact Semantic Recovery & Transient Re-Excursion Tests
# ---------------------------------------------------------------------------

def test_exact_transient_recovery_and_re_excursion_semantics():
    """Verify exact timeline:
    09:45 ABNORMAL -> CANDIDATE
    10:00 ABNORMAL -> ACTIVE (Episode 1)
    10:15 NORMAL   -> Begins RECOVERING
    10:30 ABNORMAL -> Cancels recovery, returns to ACTIVE (Same Episode, no new recurrence)
    10:45 ABNORMAL -> Continues ACTIVE
    11:00 ABNORMAL -> Continues ACTIVE
    """
    engine = ElectricalEpisodeEngine(asset_id="tripura_dt_01")
    t_start = datetime(2026, 1, 1, 9, 45, 0, tzinfo=timezone.utc)

    # 09:45 ABNORMAL (15.0%) -> CANDIDATE
    engine.evaluate_step(_make_event("e0", t_start), _make_derived(t_start, current_imbalance=15.0))
    assert engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE].status == EpisodeStatus.CANDIDATE

    # 10:00 ABNORMAL (15.0%) -> ACTIVE
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    engine.evaluate_step(_make_event("e1", t0), _make_derived(t0, current_imbalance=15.0))
    ep_1000 = engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE]
    assert ep_1000.status == EpisodeStatus.ACTIVE
    initial_ep_id = ep_1000.episode_id
    assert ep_1000.recurrence_count == 1

    # 1. 10:15 NORMAL (4.0% < 8.0%) -> Begins recovery (status = RECOVERING)
    t1 = t0 + timedelta(minutes=15)
    engine.evaluate_step(_make_event("e2", t1), _make_derived(t1, current_imbalance=4.0))
    ep_1015 = engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE]
    assert ep_1015.status == EpisodeStatus.RECOVERING
    assert ep_1015.recovery_start_time_utc == t1
    assert ep_1015.episode_id == initial_ep_id

    # 2. 10:30 ABNORMAL (14.0% >= 10.0%) -> Cancels recovery, returns to ACTIVE
    t2 = t1 + timedelta(minutes=15)
    engine.evaluate_step(_make_event("e3", t2), _make_derived(t2, current_imbalance=14.0))
    ep_1030 = engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE]
    assert ep_1030.status == EpisodeStatus.ACTIVE
    assert ep_1030.recovery_start_time_utc is None

    # 3. Original episode remains the same episode
    assert ep_1030.episode_id == initial_ep_id
    assert ep_1030.start_time_utc == t_start

    # 4. Recurrence is NOT incremented
    assert ep_1030.recurrence_count == 1
    assert engine.recurrence_counts[ElectricalEpisodeType.CURRENT_IMBALANCE] == 1

    # 5. Episode remains active through 10:45 and 11:00
    t3 = t2 + timedelta(minutes=15)
    engine.evaluate_step(_make_event("e4", t3), _make_derived(t3, current_imbalance=13.0))
    t4 = t3 + timedelta(minutes=15)
    engine.evaluate_step(_make_event("e5", t4), _make_derived(t4, current_imbalance=12.0))
    ep_1100 = engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE]
    assert ep_1100.status == EpisodeStatus.ACTIVE
    assert ep_1100.episode_id == initial_ep_id
    assert ep_1100.recurrence_count == 1
    assert len(engine.get_closed_episodes()) == 0


def test_exact_continuous_recovery_closure_semantics():
    """Verify exact continuous recovery closure timeline:
    09:45 ABNORMAL -> CANDIDATE
    10:00 ABNORMAL -> ACTIVE
    10:15 NORMAL   -> Begins RECOVERING
    10:30 NORMAL   -> Recovery duration (15m = 900s) satisfied -> CLOSES episode
    """
    engine = ElectricalEpisodeEngine(asset_id="tripura_dt_01")
    t_start = datetime(2026, 1, 1, 9, 45, 0, tzinfo=timezone.utc)
    t0 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)

    # 09:45 -> 10:00 -> ACTIVE
    engine.evaluate_step(_make_event("e0", t_start), _make_derived(t_start, current_imbalance=15.0))
    engine.evaluate_step(_make_event("e1", t0), _make_derived(t0, current_imbalance=15.0))
    assert engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE].status == EpisodeStatus.ACTIVE

    # 10:15 NORMAL (4.0%) -> Begins recovery
    t1 = t0 + timedelta(minutes=15)
    engine.evaluate_step(_make_event("e2", t1), _make_derived(t1, current_imbalance=4.0))
    assert engine.active_episodes[ElectricalEpisodeType.CURRENT_IMBALANCE].status == EpisodeStatus.RECOVERING

    # 10:30 NORMAL (4.0%) -> 15 min continuous clean operation -> CLOSES episode
    t2 = t1 + timedelta(minutes=15)
    open_eps = engine.evaluate_step(_make_event("e3", t2), _make_derived(t2, current_imbalance=4.0))
    assert len(open_eps) == 0
    assert len(engine.get_closed_episodes()) == 1
    closed_ep = engine.get_closed_episodes()[0]
    assert closed_ep.status == EpisodeStatus.CLOSED
    assert closed_ep.closed_time_utc == t2
    assert closed_ep.recurrence_count == 1

