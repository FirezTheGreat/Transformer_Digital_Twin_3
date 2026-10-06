"""Phase 5.3 — Dynamic Synthetic Scenario Injector Test Suite.

Comprehensive tests covering all 5 scenario injectors, temporal boundaries,
ground-truth metadata, determinism, multi-asset isolation, and integration
with the Phase 5.1 ElectricalEpisodeEngine and TwinReducer.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import pytest

from app.engine.electrical_episodes import ElectricalEpisodeEngine
from app.engine.injectors import (
    ScenarioInjectorEngine,
    create_sensor_spike_scenario,
    create_stuck_sensor_scenario,
    create_persistent_bias_scenario,
    create_sustained_overload_scenario,
    create_phase_imbalance_scenario,
)
from app.engine.physics import extract_electrical_features
from app.engine.reducer import TwinReducer
from app.models.anomaly import EpisodeState
from app.models.electrical_episode import ElectricalEpisodeThresholds, ElectricalEpisodeType
from app.models.injector import (
    GroundTruthCondition,
    InjectorScenarioConfig,
    InjectorType,
)
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)


# ---------------------------------------------------------------------------
# Test Fixtures & Utilities
# ---------------------------------------------------------------------------

def _create_source_ref() -> SourceRef:
    return SourceRef(
        system="tripura_csv",
        adapter_id="tripura_v1",
        source_record_id="row_1",
        source_uri="file:///data/test.csv",
        raw_sha256="abcdef1234567890",
    )


def _create_synthetic_event(
    asset_id: str,
    event_time_utc: datetime,
    oti: float = 60.0,
    amb: float = 30.0,
    p_kw: float = 100.0,
    q_kvar: float = 50.0,
    s_kva: float = 111.8034,
    i_l1: float = 50.0,
    i_l2: float = 50.0,
    i_l3: float = 50.0,
    v_l1: float = 230.0,
    v_l2: float = 230.0,
    v_l3: float = 230.0,
    event_id: str | None = None,
) -> CanonicalEvent:
    """Create a standard balanced CanonicalEvent for testing."""
    q_good = MeasurementQuality(severity=QualitySeverity.GOOD)
    measurements = [
        Measurement(
            signal_id="oti_degc",
            value=oti,
            value_type="float",
            unit_ucum="Cel",
            original_name="OTI",
            original_value=str(oti),
            original_unit="degC",
            quality=q_good,
        ),
        Measurement(
            signal_id="ambient_temperature",
            value=amb,
            value_type="float",
            unit_ucum="Cel",
            original_name="Ambient",
            original_value=str(amb),
            original_unit="degC",
            quality=q_good,
        ),
        Measurement(
            signal_id="active_power_total",
            value=p_kw,
            value_type="float",
            unit_ucum="kW",
            original_name="P_tot",
            original_value=str(p_kw),
            original_unit="kW",
            quality=q_good,
        ),
        Measurement(
            signal_id="reactive_power_total",
            value=q_kvar,
            value_type="float",
            unit_ucum="kvar",
            original_name="Q_tot",
            original_value=str(q_kvar),
            original_unit="kvar",
            quality=q_good,
        ),
        Measurement(
            signal_id="apparent_power_total",
            value=s_kva,
            value_type="float",
            unit_ucum="kVA",
            original_name="S_tot",
            original_value=str(s_kva),
            original_unit="kVA",
            quality=q_good,
        ),
        Measurement(
            signal_id="current_l1",
            phase="L1",
            value=i_l1,
            value_type="float",
            unit_ucum="A",
            original_name="I_L1",
            original_value=str(i_l1),
            original_unit="A",
            quality=q_good,
        ),
        Measurement(
            signal_id="current_l2",
            phase="L2",
            value=i_l2,
            value_type="float",
            unit_ucum="A",
            original_name="I_L2",
            original_value=str(i_l2),
            original_unit="A",
            quality=q_good,
        ),
        Measurement(
            signal_id="current_l3",
            phase="L3",
            value=i_l3,
            value_type="float",
            unit_ucum="A",
            original_name="I_L3",
            original_value=str(i_l3),
            original_unit="A",
            quality=q_good,
        ),
        Measurement(
            signal_id="voltage_l1_n",
            phase="L1",
            value=v_l1,
            value_type="float",
            unit_ucum="V",
            original_name="V_L1",
            original_value=str(v_l1),
            original_unit="V",
            quality=q_good,
        ),
        Measurement(
            signal_id="voltage_l2_n",
            phase="L2",
            value=v_l2,
            value_type="float",
            unit_ucum="V",
            original_name="V_L2",
            original_value=str(v_l2),
            original_unit="V",
            quality=q_good,
        ),
        Measurement(
            signal_id="voltage_l3_n",
            phase="L3",
            value=v_l3,
            value_type="float",
            unit_ucum="V",
            original_name="V_L3",
            original_value=str(v_l3),
            original_unit="V",
            quality=q_good,
        ),
    ]
    eid = event_id or f"evt_{int(event_time_utc.timestamp())}"
    return CanonicalEvent(
        event_id=eid,
        asset_id=asset_id,
        event_time_utc=event_time_utc,
        source=_create_source_ref(),
        measurements=measurements,
        mapping_version="1.0.0",
    )


def _get_meas_value(event: CanonicalEvent, signal_id: str) -> float:
    for m in event.measurements:
        if m.signal_id == signal_id:
            return float(m.value)
    raise KeyError(f"Signal {signal_id} not found in event")


# ---------------------------------------------------------------------------
# 1. INJ_SENSOR_SPIKE Tests
# ---------------------------------------------------------------------------

def test_sensor_spike_single_sample():
    """Test single isolated sensor spike on OTI with exact boundary semantics."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 10, 30, tzinfo=timezone.utc)

    events = [
        _create_synthetic_event("TX_01", t0, oti=60.0),
        _create_synthetic_event("TX_01", t1, oti=61.0),
        _create_synthetic_event("TX_01", t2, oti=62.0),
    ]

    # Spike at t1: delta +34.0 (61.0 -> 95.0)
    scenario = create_sensor_spike_scenario(
        scenario_id="spike_01",
        asset_id="TX_01",
        start_time_utc=t1,
        duration_seconds=900.0,  # exactly covers [10:15, 10:30)
        target_signal="oti_degc",
        spike_delta=34.0,
    )

    engine = ScenarioInjectorEngine([scenario])
    inj_events = engine.inject_stream(events)

    assert len(inj_events) == 3

    # t0: unchanged
    ev0, ctx0 = inj_events[0]
    assert _get_meas_value(ev0, "oti_degc") == 60.0
    assert not ctx0.is_injected

    # t1: spiked
    ev1, ctx1 = inj_events[1]
    assert _get_meas_value(ev1, "oti_degc") == 95.0
    assert ctx1.is_injected
    assert "oti_degc" in ctx1.modified_signals
    assert len(ctx1.ground_truth_records) == 1
    gt1 = ctx1.ground_truth_records[0]
    assert gt1.ground_truth_condition == GroundTruthCondition.SENSOR_SPIKE_TRANSIENT
    assert gt1.is_data_quality_anomaly is True
    assert gt1.injection_parameters["spike_delta"] == 34.0

    # Unaffected signals unchanged at t1
    assert _get_meas_value(ev1, "ambient_temperature") == 30.0
    assert _get_meas_value(ev1, "current_l1") == 50.0

    # t2: back to baseline (half-open end)
    ev2, ctx2 = inj_events[2]
    assert _get_meas_value(ev2, "oti_degc") == 62.0
    assert not ctx2.is_injected


# ---------------------------------------------------------------------------
# 2. INJ_STUCK_SENSOR Tests
# ---------------------------------------------------------------------------

def test_stuck_sensor_latches_last_value():
    """Test stuck sensor freezes at the last observed value during injection window."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 10, 30, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 1, 10, 45, tzinfo=timezone.utc)

    # Base values: 60 -> 63 -> 65 -> 67
    events = [
        _create_synthetic_event("TX_01", t0, oti=60.0),
        _create_synthetic_event("TX_01", t1, oti=63.0),
        _create_synthetic_event("TX_01", t2, oti=65.0),
        _create_synthetic_event("TX_01", t3, oti=67.0),
    ]

    # Stuck from t1 to t3 (covering t1 and t2)
    scenario = create_stuck_sensor_scenario(
        scenario_id="stuck_01",
        asset_id="TX_01",
        start_time_utc=t1,
        duration_seconds=1800.0,  # [10:15, 10:45)
        target_signal="oti_degc",
    )

    engine = ScenarioInjectorEngine([scenario])
    inj_events = engine.inject_stream(events)

    # t0: 60.0
    assert _get_meas_value(inj_events[0][0], "oti_degc") == 60.0

    # t1: frozen at 63.0 (first value during stuck)
    assert _get_meas_value(inj_events[1][0], "oti_degc") == 63.0
    assert inj_events[1][1].is_injected
    assert inj_events[1][1].ground_truth_records[0].ground_truth_condition == GroundTruthCondition.STUCK_SENSOR

    # t2: frozen at 63.0 (instead of base 65.0)
    assert _get_meas_value(inj_events[2][0], "oti_degc") == 63.0
    assert inj_events[2][1].is_injected

    # t3: released back to base 67.0
    assert _get_meas_value(inj_events[3][0], "oti_degc") == 67.0
    assert not inj_events[3][1].is_injected


# ---------------------------------------------------------------------------
# 3. INJ_PERSISTENT_BIAS Tests
# ---------------------------------------------------------------------------

def test_persistent_bias_signed_offset():
    """Test persistent sensor bias adds exact signed delta."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 10, 30, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 1, 10, 45, tzinfo=timezone.utc)

    # Base values: 60, 61, 62, 63
    events = [
        _create_synthetic_event("TX_01", t0, oti=60.0),
        _create_synthetic_event("TX_01", t1, oti=61.0),
        _create_synthetic_event("TX_01", t2, oti=62.0),
        _create_synthetic_event("TX_01", t3, oti=63.0),
    ]

    # Bias +5.0 degC between t1 and t3
    scenario = create_persistent_bias_scenario(
        scenario_id="bias_01",
        asset_id="TX_01",
        start_time_utc=t1,
        duration_seconds=1800.0,
        target_signal="oti_degc",
        bias_delta=5.0,
    )

    engine = ScenarioInjectorEngine([scenario])
    inj = engine.inject_stream(events)

    assert _get_meas_value(inj[0][0], "oti_degc") == 60.0
    assert _get_meas_value(inj[1][0], "oti_degc") == 66.0  # 61 + 5
    assert _get_meas_value(inj[2][0], "oti_degc") == 67.0  # 62 + 5
    assert _get_meas_value(inj[3][0], "oti_degc") == 63.0  # restored

    gt = inj[1][1].ground_truth_records[0]
    assert gt.ground_truth_condition == GroundTruthCondition.PERSISTENT_SENSOR_BIAS
    assert gt.injection_parameters["bias_delta"] == 5.0
    assert gt.is_data_quality_anomaly is True


# ---------------------------------------------------------------------------
# 4. INJ_SUSTAINED_OVERLOAD Tests
# ---------------------------------------------------------------------------

def test_sustained_overload_electrical_consistency():
    """Test sustained overload scales electrical drivers without directly manipulating temperature."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc)

    events = [
        _create_synthetic_event(
            "TX_01",
            t0,
            oti=60.0,
            amb=30.0,
            p_kw=100.0,
            q_kvar=50.0,
            s_kva=111.8034,
            i_l1=50.0,
            i_l2=50.0,
            i_l3=50.0,
            v_l1=230.0,
        ),
        _create_synthetic_event(
            "TX_01",
            t1,
            oti=60.0,
            amb=30.0,
            p_kw=100.0,
            q_kvar=50.0,
            s_kva=111.8034,
            i_l1=50.0,
            i_l2=50.0,
            i_l3=50.0,
            v_l1=230.0,
        ),
    ]

    # Scale load by 1.50x at t1
    scenario = create_sustained_overload_scenario(
        scenario_id="overload_01",
        asset_id="TX_01",
        start_time_utc=t1,
        duration_seconds=900.0,
        load_multiplier=1.50,
    )

    engine = ScenarioInjectorEngine([scenario])
    inj = engine.inject_stream(events)

    ev1, ctx1 = inj[1]
    assert ctx1.is_injected
    gt1 = ctx1.ground_truth_records[0]
    assert gt1.ground_truth_condition == GroundTruthCondition.SUSTAINED_ELECTRICAL_OVERLOAD
    assert gt1.is_data_quality_anomaly is False

    # Power and currents scaled by 1.50x
    assert _get_meas_value(ev1, "active_power_total") == 150.0
    assert _get_meas_value(ev1, "reactive_power_total") == 75.0
    assert _get_meas_value(ev1, "apparent_power_total") == round(111.8034 * 1.50, 4)
    assert _get_meas_value(ev1, "current_l1") == 75.0
    assert _get_meas_value(ev1, "current_l2") == 75.0
    assert _get_meas_value(ev1, "current_l3") == 75.0

    # Voltages and temperatures NOT modified
    assert _get_meas_value(ev1, "voltage_l1_n") == 230.0
    assert _get_meas_value(ev1, "oti_degc") == 60.0
    assert _get_meas_value(ev1, "ambient_temperature") == 30.0

    # Downstream feature extraction reflects increased apparent power and load index
    feat0 = extract_electrical_features(inj[0][0])
    feat1 = extract_electrical_features(ev1)
    assert feat0.apparent_power_derived_kva == 111.8034
    assert feat1.apparent_power_derived_kva == round(111.8034 * 1.50, 4)
    assert feat1.relative_load_index is not None and feat1.relative_load_index > (feat0.relative_load_index or 0.0)


# ---------------------------------------------------------------------------
# 5. INJ_PHASE_IMBALANCE Tests
# ---------------------------------------------------------------------------

def test_phase_imbalance_modifies_underlying_phase_current():
    """Test phase imbalance modifies phase current and derived % IUB is naturally computed."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc)

    # Balanced 50A, 50A, 50A
    events = [
        _create_synthetic_event("TX_01", t0, i_l1=50.0, i_l2=50.0, i_l3=50.0),
        _create_synthetic_event("TX_01", t1, i_l1=50.0, i_l2=50.0, i_l3=50.0),
    ]

    # Imbalance: scale L1 by 2.0x (to 100A)
    scenario = create_phase_imbalance_scenario(
        scenario_id="imb_01",
        asset_id="TX_01",
        start_time_utc=t1,
        duration_seconds=900.0,
        target_phase="L1",
        phase_multiplier=2.0,
    )

    engine = ScenarioInjectorEngine([scenario])
    inj = engine.inject_stream(events)

    ev1, ctx1 = inj[1]
    assert ctx1.is_injected
    assert _get_meas_value(ev1, "current_l1") == 100.0
    assert _get_meas_value(ev1, "current_l2") == 50.0  # untouched
    assert _get_meas_value(ev1, "current_l3") == 50.0  # untouched

    # Derived electrical features naturally compute % IUB
    feat0 = extract_electrical_features(inj[0][0])
    feat1 = extract_electrical_features(ev1)
    assert feat0.current_magnitude_imbalance_pct == 0.0
    # Mean I = (100 + 50 + 50) / 3 = 66.6667
    # Max dev = 100 - 66.6667 = 33.3333
    # % IUB = 100 * (33.3333 / 66.6667) = 50.0%
    assert feat1.current_magnitude_imbalance_pct == 50.0


# ---------------------------------------------------------------------------
# 6. General Engine Tests (Determinism, Isolation, Immutability, Validation)
# ---------------------------------------------------------------------------

def test_engine_determinism():
    """Test identical input events + scenario produces identical output."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    events = [_create_synthetic_event("TX_01", t0 + timedelta(minutes=15 * i)) for i in range(10)]

    scenario = create_phase_imbalance_scenario(
        scenario_id="imb_det",
        asset_id="TX_01",
        start_time_utc=t0 + timedelta(minutes=30),
        duration_seconds=1800.0,
        target_phase="L1",
        phase_multiplier=2.5,
    )

    engine1 = ScenarioInjectorEngine([scenario])
    engine2 = ScenarioInjectorEngine([scenario])

    res1 = engine1.inject_stream(events)
    res2 = engine2.inject_stream(events)

    for (ev1, ctx1), (ev2, ctx2) in zip(res1, res2):
        assert ev1.model_dump() == ev2.model_dump()
        assert ctx1.model_dump() == ctx2.model_dump()


def test_input_immutability():
    """Verify original CanonicalEvents and measurements are not mutated in-place."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    original_event = _create_synthetic_event("TX_01", t0, oti=60.0)
    original_dump = copy.deepcopy(original_event.model_dump())

    scenario = create_sensor_spike_scenario(
        scenario_id="spike_imm",
        asset_id="TX_01",
        start_time_utc=t0,
        duration_seconds=900.0,
        target_signal="oti_degc",
        spike_delta=25.0,
    )

    engine = ScenarioInjectorEngine([scenario])
    mod_event, ctx = engine.inject_event(original_event)

    assert _get_meas_value(mod_event, "oti_degc") == 85.0
    assert original_event.model_dump() == original_dump
    assert _get_meas_value(original_event, "oti_degc") == 60.0


def test_multi_asset_isolation():
    """Ensure injection for TX_01 does not affect TX_02."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    ev_tx1 = _create_synthetic_event("TX_01", t0, oti=60.0)
    ev_tx2 = _create_synthetic_event("TX_02", t0, oti=60.0)

    scenario = create_sensor_spike_scenario(
        scenario_id="spike_tx1",
        asset_id="TX_01",
        start_time_utc=t0,
        duration_seconds=900.0,
        target_signal="oti_degc",
        spike_delta=30.0,
    )

    engine = ScenarioInjectorEngine([scenario])
    mod_tx1, ctx_tx1 = engine.inject_event(ev_tx1)
    mod_tx2, ctx_tx2 = engine.inject_event(ev_tx2)

    assert ctx_tx1.is_injected
    assert _get_meas_value(mod_tx1, "oti_degc") == 90.0

    assert not ctx_tx2.is_injected
    assert _get_meas_value(mod_tx2, "oti_degc") == 60.0


def test_invalid_config_rejection():
    """Verify improper scenario configurations raise descriptive ValueErrors."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    # 1. Missing end time and duration
    with pytest.raises(ValueError, match="must specify either 'end_time_utc' or 'duration_seconds'"):
        InjectorScenarioConfig(
            scenario_id="bad_01",
            scenario_type=InjectorType.INJ_SENSOR_SPIKE,
            asset_id="TX_01",
            start_time_utc=t0,
            target_signal="oti_degc",
            spike_delta=10.0,
        )

    # 2. End time <= start time
    with pytest.raises(ValueError, match="must be strictly greater than start_time_utc"):
        InjectorScenarioConfig(
            scenario_id="bad_02",
            scenario_type=InjectorType.INJ_SENSOR_SPIKE,
            asset_id="TX_01",
            start_time_utc=t0,
            end_time_utc=t0,
            target_signal="oti_degc",
            spike_delta=10.0,
        )

    # 3. Missing target_signal for sensor spike
    with pytest.raises(ValueError, match="requires 'target_signal'"):
        InjectorScenarioConfig(
            scenario_id="bad_03",
            scenario_type=InjectorType.INJ_SENSOR_SPIKE,
            asset_id="TX_01",
            start_time_utc=t0,
            duration_seconds=900.0,
            spike_delta=10.0,
        )


# ---------------------------------------------------------------------------
# 7. Integration Tests (Phase 5.1 Episode Engine & TwinReducer)
# ---------------------------------------------------------------------------

def test_integration_phase_imbalance_episode_lifecycle():
    """End-to-End Test:

    Base telemetry -> Inject INJ_PHASE_IMBALANCE -> TwinReducer with ElectricalEpisodeEngine
    Verify full lifecycle: NORMAL -> CANDIDATE -> ACTIVE -> RECOVERING -> CLOSED.
    """
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    # 12 steps of 15-minute telemetry (3 hours total)
    # Steps:
    # 0, 1: Normal (10:00, 10:15)
    # 2, 3, 4, 5: Imbalance active (10:30, 10:45, 11:00, 11:15) (1 hour duration)
    # 6, 7, 8, 9, 10, 11: Normal (11:30 to 12:45)
    base_events = [
        _create_synthetic_event("TX_01", t0 + timedelta(minutes=15 * i), i_l1=50.0, i_l2=50.0, i_l3=50.0)
        for i in range(12)
    ]

    scenario = create_phase_imbalance_scenario(
        scenario_id="e2e_imb",
        asset_id="TX_01",
        start_time_utc=t0 + timedelta(minutes=30),  # 10:30
        duration_seconds=3600.0,                    # 1 hour -> [10:30, 11:30)
        target_phase="L1",
        phase_multiplier=2.5,                       # 50A -> 125A -> ~50% IUB
    )

    injector = ScenarioInjectorEngine([scenario])
    injected_events = injector.inject_events_only(base_events)

    thresholds = {
        ElectricalEpisodeType.CURRENT_IMBALANCE: ElectricalEpisodeThresholds(
            warning_threshold=10.0,
            critical_threshold=25.0,
            recovery_threshold=5.0,
            persistence_seconds=900.0,  # 1 step (15 min) persistence to become ACTIVE
            recovery_seconds=900.0,     # 1 step (15 min) clean to close
        )
    }
    episode_engine = ElectricalEpisodeEngine(asset_id="TX_01", thresholds=thresholds)
    reducer = TwinReducer(episode_engine=episode_engine)

    states = []
    current_state = None
    for ev in injected_events:
        current_state = reducer.reduce(current_state, ev)
        states.append(current_state)

    # Check episode lifecycle from TwinState snapshots:
    # Step 0 (10:00): Normal (0% IUB)
    assert states[0].derived_electrical.current_magnitude_imbalance_pct == 0.0
    assert len(states[0].open_episodes) == 0

    # Step 1 (10:15): Normal
    assert len(states[1].open_episodes) == 0

    # Step 2 (10:30): First abnormal observation (~66.7% IUB) -> CANDIDATE (mapped to WATCH in AnomalyEpisode)
    assert states[2].derived_electrical.current_magnitude_imbalance_pct == 66.6667
    assert len(states[2].open_episodes) == 1
    assert states[2].open_episodes[0].state == EpisodeState.WATCH

    # Step 3 (10:45): Abnormal persisted 15 min -> ACTIVE (mapped to CRITICAL in AnomalyEpisode)
    assert len(states[3].open_episodes) == 1
    assert states[3].open_episodes[0].state == EpisodeState.CRITICAL

    # Step 4 (11:00): Still ACTIVE
    assert len(states[4].open_episodes) == 1
    assert states[4].open_episodes[0].state == EpisodeState.CRITICAL

    # Step 5 (11:15): Still ACTIVE
    assert len(states[5].open_episodes) == 1
    assert states[5].open_episodes[0].state == EpisodeState.CRITICAL

    # Step 6 (11:30): First clean observation (0% IUB) -> RECOVERING
    assert states[6].derived_electrical.current_magnitude_imbalance_pct == 0.0
    assert len(states[6].open_episodes) == 1
    assert states[6].open_episodes[0].state == EpisodeState.RECOVERING

    # Step 7 (11:45): Clean for 15 min -> CLOSED (removed from open_episodes, present in closed_episodes)
    assert len(states[7].open_episodes) == 0
    assert len(episode_engine.closed_episodes) == 1
    closed_ep = episode_engine.closed_episodes[0]
    assert closed_ep.status.value == "CLOSED"
    assert closed_ep.duration_seconds is not None and closed_ep.duration_seconds >= 3600.0


def test_overlapping_scenarios():
    """Verify multiple active scenarios on different signals execute deterministically."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    ev = _create_synthetic_event("TX_01", t0, oti=60.0, amb=30.0)

    # Scenario 1: Spike on OTI (+15)
    s1 = create_sensor_spike_scenario("s1", "TX_01", t0, "oti_degc", spike_delta=15.0, duration_seconds=900.0)
    # Scenario 2: Bias on Ambient (+5)
    s2 = create_persistent_bias_scenario("s2", "TX_01", t0, "ambient_temperature", bias_delta=5.0, duration_seconds=900.0)

    engine = ScenarioInjectorEngine([s1, s2])
    inj_ev, ctx = engine.inject_event(ev)

    assert ctx.is_injected
    assert len(ctx.active_scenario_ids) == 2
    assert "s1" in ctx.active_scenario_ids and "s2" in ctx.active_scenario_ids
    assert _get_meas_value(inj_ev, "oti_degc") == 75.0
    assert _get_meas_value(inj_ev, "ambient_temperature") == 35.0


def test_stuck_sensor_explicit_fixed_value():
    """Verify stuck sensor with explicit stuck_value overrides observed value."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    ev = _create_synthetic_event("TX_01", t0, oti=60.0)

    scenario = create_stuck_sensor_scenario(
        "stuck_fixed",
        "TX_01",
        t0,
        target_signal="oti_degc",
        duration_seconds=900.0,
        stuck_value=72.5,
    )

    engine = ScenarioInjectorEngine([scenario])
    inj_ev, ctx = engine.inject_event(ev)

    assert _get_meas_value(inj_ev, "oti_degc") == 72.5
    assert ctx.is_injected


def test_phase_imbalance_additive_delta():
    """Verify phase imbalance with additive delta (phase_delta_a)."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    ev = _create_synthetic_event("TX_01", t0, i_l1=50.0, i_l2=50.0, i_l3=50.0)

    scenario = create_phase_imbalance_scenario(
        "imb_add",
        "TX_01",
        t0,
        target_phase="L2",
        phase_delta_a=30.0,  # 50A -> 80A
        duration_seconds=900.0,
    )

    engine = ScenarioInjectorEngine([scenario])
    inj_ev, ctx = engine.inject_event(ev)

    assert _get_meas_value(inj_ev, "current_l1") == 50.0
    assert _get_meas_value(inj_ev, "current_l2") == 80.0
    assert _get_meas_value(inj_ev, "current_l3") == 50.0


def test_sustained_overload_thermal_pipeline_response():
    """Verify sustained electrical overload increases thermal ODE response without directly editing temperature."""
    from app.engine.thermal import ThermalModelParameters, step_thermal_ode

    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc)

    base_ev0 = _create_synthetic_event("TX_01", t0, oti=60.0, amb=30.0, s_kva=100.0)
    base_ev1 = _create_synthetic_event("TX_01", t1, oti=60.0, amb=30.0, s_kva=100.0)

    # 1.50x load overload applied at t1
    scenario = create_sustained_overload_scenario(
        "overload_therm", "TX_01", start_time_utc=t1, duration_seconds=900.0, load_multiplier=1.50
    )
    injector = ScenarioInjectorEngine([scenario])
    injected_events = injector.inject_events_only([base_ev0, base_ev1])

    # Extract features
    feat_base = extract_electrical_features(base_ev1)
    feat_inj = extract_electrical_features(injected_events[1])

    # Observed OTI remains 60.0 (untouched by injector)
    assert _get_meas_value(injected_events[1], "oti_degc") == 60.0

    # Load driver increased naturally
    assert (feat_inj.apparent_power_derived_kva or 0.0) > (feat_base.apparent_power_derived_kva or 0.0)

    # Stepping calibrated thermal ODE with baseline vs injected load
    params = ThermalModelParameters(beta_0=1.088, beta_1=2.8979, tau_hours=0.50)
    dt_hours = 0.25  # 15 minutes

    u_base = (feat_base.relative_load_index or 0.70)
    u_inj = (feat_inj.relative_load_index or 0.70)

    t_next_base = step_thermal_ode(t_prev_degc=60.0, ambient_degc=30.0, u_load=u_base, dt_hours=dt_hours, params=params)
    t_next_inj = step_thermal_ode(t_prev_degc=60.0, ambient_degc=30.0, u_load=u_inj, dt_hours=dt_hours, params=params)

    # Injected load produces higher projected temperature and higher steady-state rise
    assert t_next_inj > t_next_base
