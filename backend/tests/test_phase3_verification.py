"""Phase 3.4 — Phase 3 Verification & Integration Checkpoint Suite.

Comprehensive end-to-end integration tests verifying the full deterministic
runtime pipeline:
CanonicalEvent -> Phase 3.1 Physics -> Phase 3.2 Reducer/Checkpointing -> Phase 3.3 Dynamic Capability.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from app.adapters.tripura import TripuraCSVAdapter
from app.core.checkpoint import CheckpointStore
from app.core.storage import StorageEngine
from app.engine.capability import CapabilityEvaluator, evaluate_capabilities
from app.engine.physics import extract_electrical_features
from app.engine.reducer import TwinReducer
from app.engine.replay import ReplayEngine
from app.models.capability import CapabilityTier
from app.models.profile import AssetProfile, InsulationClass, ProfileField, ProfileVerificationStatus
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)
from app.models.twin_state import TwinState


def _make_meas(
    signal_id: str,
    value: float | int | str | bool,
    unit: str,
    phase: str | None = None,
    severity: QualitySeverity = QualitySeverity.GOOD,
    flags: list[str] | None = None,
) -> Measurement:
    val_type = (
        "bool" if isinstance(value, bool)
        else "int" if isinstance(value, int)
        else "float" if isinstance(value, float)
        else "str"
    )
    return Measurement(
        signal_id=signal_id,
        phase=phase,  # type: ignore[arg-type]
        value=value,
        value_type=val_type,
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(severity=severity, flags=flags or []),
    )


def _make_event(
    event_id: str,
    event_time: datetime,
    asset_id: str = "DT-001",
    oti: float | None = None,
    ati: float | None = None,
    wti: int | None = None,
    p_kw: float | None = None,
    q_kvar: float | None = None,
    s_kva: float | None = None,
    pf: float | None = None,
    i_l1: float | None = None,
    i_l2: float | None = None,
    i_l3: float | None = None,
    v_l1: float | None = None,
    v_l2: float | None = None,
    v_l3: float | None = None,
    i_n: float | None = None,
    oti_severity: QualitySeverity = QualitySeverity.GOOD,
    event_flags: list[str] | None = None,
) -> CanonicalEvent:
    measurements: list[Measurement] = []

    if oti is not None:
        measurements.append(_make_meas("top_oil_temperature", oti, "Cel", severity=oti_severity))
    if ati is not None:
        measurements.append(_make_meas("ambient_temperature", ati, "Cel"))
    if wti is not None:
        measurements.append(_make_meas("winding_temp_alarm_contact", wti, "1"))
    if p_kw is not None:
        measurements.append(_make_meas("active_power", p_kw, "kW"))
    if q_kvar is not None:
        measurements.append(_make_meas("reactive_power", q_kvar, "kvar"))
    if s_kva is not None:
        measurements.append(_make_meas("apparent_power", s_kva, "kVA"))
    if pf is not None:
        measurements.append(_make_meas("power_factor", pf, "1"))
    if i_l1 is not None:
        measurements.append(_make_meas("current", i_l1, "A", phase="L1"))
    if i_l2 is not None:
        measurements.append(_make_meas("current", i_l2, "A", phase="L2"))
    if i_l3 is not None:
        measurements.append(_make_meas("current", i_l3, "A", phase="L3"))
    if v_l1 is not None:
        measurements.append(_make_meas("voltage", v_l1, "V", phase="L1"))
    if v_l2 is not None:
        measurements.append(_make_meas("voltage", v_l2, "V", phase="L2"))
    if v_l3 is not None:
        measurements.append(_make_meas("voltage", v_l3, "V", phase="L3"))
    if i_n is not None:
        measurements.append(_make_meas("neutral_current", i_n, "A"))

    if not measurements:
        measurements.append(_make_meas("heartbeat", 1, "1"))

    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=event_id,
        asset_id=asset_id,
        event_time_utc=event_time,
        source=SourceRef(
            system="synthetic_phase3_test",
            adapter_id="phase3_verif_v1",
            source_record_id=event_id,
            source_uri="memory://synthetic",
            raw_sha256="0" * 64,
        ),
        measurements=measurements,
        event_quality_flags=event_flags or [],
        mapping_version="1.0.0",
    )


@pytest.fixture
def storage() -> StorageEngine:
    return StorageEngine(db_path=":memory:")


@pytest.fixture
def checkpoint_store(storage: StorageEngine) -> CheckpointStore:
    return CheckpointStore(storage)


# =========================================================================
# 1. End-to-End Deterministic Pipeline
# =========================================================================

def test_end_to_end_deterministic_pipeline(checkpoint_store: CheckpointStore) -> None:
    """CanonicalEvent -> Physics -> TwinReducer -> TwinState -> CapabilityEvaluator."""
    reducer = TwinReducer(checkpoint_store=checkpoint_store)
    evaluator = CapabilityEvaluator()

    t0 = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    ev = _make_event(
        "evt_01",
        t0,
        oti=60.0,
        ati=28.0,
        p_kw=45.0,
        q_kvar=15.0,
        s_kva=47.43,
        i_l1=65.0,
        i_l2=64.0,
        i_l3=66.0,
        v_l1=230.0,
        v_l2=231.0,
        v_l3=229.0,
        i_n=2.5,
    )

    state = reducer.reduce(None, ev)
    assert state is not None
    assert state.asset_id == "DT-001"
    assert state.state_sequence == 1
    assert state.state_time_utc == t0
    assert state.derived_electrical is not None
    assert state.derived_electrical.apparent_power_derived_kva == 47.4342
    assert state.derived_electrical.current_magnitude_imbalance_pct is not None
    assert state.derived_electrical.voltage_magnitude_imbalance_pct is not None

    manifest = evaluator.evaluate(state)
    assert manifest.asset_id == "DT-001"
    assert manifest.highest_tier == CapabilityTier.C2_THERMAL_DESCRIPTIVE
    assert manifest.capabilities["C0"].enabled is True
    assert manifest.capabilities["C1"].enabled is True
    assert manifest.capabilities["C2"].enabled is True
    assert manifest.capabilities["C3"].enabled is False  # unpromoted model
    assert manifest.capabilities["C4"].enabled is False


# =========================================================================
# 2. Multi-Event State Progression
# =========================================================================

def test_multi_event_state_progression() -> None:
    """Verify monotonic sequence progression, timestamp tracking, and feature updates."""
    reducer = TwinReducer()
    evaluator = CapabilityEvaluator()

    t0 = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    n_events = 10
    state: TwinState | None = None

    for i in range(n_events):
        ti = t0 + timedelta(minutes=15 * i)
        ev = _make_event(
            f"evt_{i:02d}",
            ti,
            oti=50.0 + i * 0.5,
            ati=25.0 + i * 0.2,
            p_kw=40.0 + i * 1.0,
            q_kvar=10.0 + i * 0.5,
            i_l1=60.0 + i,
            i_l2=61.0 + i,
            i_l3=59.0 + i,
            v_l1=230.0,
            v_l2=230.0,
            v_l3=230.0,
        )
        state = reducer.reduce(state, ev)

        assert state.state_sequence == i + 1
        assert state.state_time_utc == ti
        assert state.last_processed_event_id == f"evt_{i:02d}"
        assert state.current_observations["top_oil_temperature"].value == 50.0 + i * 0.5

        manifest = evaluator.evaluate(state)
        assert manifest.highest_tier == CapabilityTier.C2_THERMAL_DESCRIPTIVE

    assert state.state_sequence == 10


# =========================================================================
# 3. Missing-Data Dynamic Capability Transitions
# =========================================================================

def test_dynamic_missing_data_capability_transitions() -> None:
    """Test Event A (C2) -> Event B (missing top-oil -> C1) -> Event C (C2 restored)."""
    reducer = TwinReducer()
    evaluator = CapabilityEvaluator()

    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    # Event A: Complete telemetry -> C2
    ev_a = _make_event(
        "evt_A",
        t0,
        oti=62.0,
        ati=30.0,
        p_kw=45.0,
        q_kvar=15.0,
        i_l1=65.0,
        i_l2=65.0,
        i_l3=65.0,
        v_l1=230.0,
        v_l2=230.0,
        v_l3=230.0,
    )
    state_a = reducer.reduce(None, ev_a)
    manifest_a = evaluator.evaluate(state_a)
    assert manifest_a.highest_tier == CapabilityTier.C2_THERMAL_DESCRIPTIVE
    assert manifest_a.capabilities["C2"].enabled is True

    # Event B: Top-oil temperature sensor missing -> Downgrades to C1
    ev_b = _make_event(
        "evt_B",
        t0 + timedelta(minutes=15),
        oti=None,  # top oil missing
        ati=30.5,
        p_kw=46.0,
        q_kvar=15.5,
        i_l1=66.0,
        i_l2=66.0,
        i_l3=66.0,
        v_l1=230.0,
        v_l2=230.0,
        v_l3=230.0,
    )
    state_b = reducer.reduce(None, ev_b)
    manifest_b = evaluator.evaluate(state_b)
    # Electrical still active; C2 is disabled
    assert manifest_b.highest_tier == CapabilityTier.C1_ELECTRICAL
    assert manifest_b.capabilities["C1"].enabled is True
    assert manifest_b.capabilities["loading_proxy"].enabled is True
    assert manifest_b.capabilities["C2"].enabled is False
    assert "MISSING_CONTINUOUS_TOP_OIL_TEMPERATURE" in manifest_b.capabilities["C2"].disabled_reason_codes

    # Event C: Top-oil temperature restored -> Returns to C2
    ev_c = _make_event(
        "evt_C",
        t0 + timedelta(minutes=30),
        oti=63.0,  # top oil restored
        ati=31.0,
        p_kw=47.0,
        q_kvar=16.0,
        i_l1=67.0,
        i_l2=67.0,
        i_l3=67.0,
        v_l1=230.0,
        v_l2=230.0,
        v_l3=230.0,
    )
    state_c = reducer.reduce(state_b, ev_c)
    manifest_c = evaluator.evaluate(state_c)
    assert manifest_c.highest_tier == CapabilityTier.C2_THERMAL_DESCRIPTIVE
    assert manifest_c.capabilities["C2"].enabled is True


# =========================================================================
# 4. Bad and Conflicting Data Rejection
# =========================================================================

def test_bad_data_does_not_unlock_capability() -> None:
    """Measurements marked with BAD quality severity must not enable capabilities."""
    reducer = TwinReducer()
    evaluator = CapabilityEvaluator()

    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    ev_bad_oti = _make_event(
        "evt_bad_oti",
        t0,
        oti=65.0,
        oti_severity=QualitySeverity.BAD,
        p_kw=45.0,
        q_kvar=15.0,
        i_l1=65.0,
        i_l2=65.0,
        i_l3=65.0,
        v_l1=230.0,
        v_l2=230.0,
        v_l3=230.0,
    )
    state = reducer.reduce(None, ev_bad_oti)
    manifest = evaluator.evaluate(state)

    # BAD top-oil must prevent C2
    assert manifest.highest_tier == CapabilityTier.C1_ELECTRICAL
    assert manifest.capabilities["C2"].enabled is False
    assert "BAD_QUALITY_TOP_OIL_TEMPERATURE" in manifest.capabilities["C2"].disabled_reason_codes


# =========================================================================
# 5. Late-Event Behavior: Store + Flag, No Rollback
# =========================================================================

def test_late_event_store_and_flag_no_rollback() -> None:
    """Late events arriving behind watermark do not rewind active TwinState."""
    reducer = TwinReducer()

    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    ev0 = _make_event("evt_0", t0, oti=50.0, p_kw=40.0)
    state0 = reducer.reduce(None, ev0)

    # Advance state to t0 + 30 min (watermark = t0 + 20 min)
    t1 = t0 + timedelta(minutes=30)
    ev1 = _make_event("evt_1", t1, oti=55.0, p_kw=45.0)
    state1 = reducer.reduce(state0, ev1)
    assert state1.state_sequence == 2
    assert state1.state_time_utc == t1

    # Late event arriving at t0 + 5 min (< watermark)
    t_late = t0 + timedelta(minutes=5)
    ev_late = _make_event("evt_late", t_late, oti=99.0, p_kw=99.0, event_flags=["OUT_OF_ORDER", "LATE"])
    state_after_late = reducer.reduce(state1, ev_late)

    # Active state must remain at state1 (no rollback)
    assert state_after_late.state_sequence == 2
    assert state_after_late.state_time_utc == t1
    assert state_after_late.current_observations["top_oil_temperature"].value == 55.0
    assert state_after_late.last_processed_event_id == "evt_1"


# =========================================================================
# 6. Pipeline Determinism and State Hash Consistency
# =========================================================================

def test_pipeline_determinism_and_state_hash() -> None:
    """Identical event stream produces bit-for-bit identical state, features, and manifest."""
    t0 = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    events = [
        _make_event(
            f"evt_{i:02d}",
            t0 + timedelta(minutes=15 * i),
            oti=50.0 + i,
            ati=25.0 + i * 0.1,
            p_kw=40.0 + i * 0.5,
            q_kvar=10.0 + i * 0.2,
            i_l1=60.0 + i,
            i_l2=61.0 + i,
            i_l3=59.0 + i,
            v_l1=230.0,
            v_l2=230.0,
            v_l3=230.0,
        )
        for i in range(10)
    ]

    # Run 1
    r1 = TwinReducer()
    e1 = CapabilityEvaluator()
    s1 = r1.reduce_stream(events)
    m1 = e1.evaluate(s1)

    # Run 2
    r2 = TwinReducer()
    e2 = CapabilityEvaluator()
    s2 = r2.reduce_stream(events)
    m2 = e2.evaluate(s2)

    assert s1.state_hash == s2.state_hash
    assert s1.model_dump() == s2.model_dump()
    assert m1.model_dump() == m2.model_dump()


# =========================================================================
# 7. Checkpoint Restore Equivalence
# =========================================================================

def test_checkpoint_restore_equivalence(checkpoint_store: CheckpointStore) -> None:
    """Full stream replay == Checkpoint restore + remaining stream replay."""
    t0 = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    n_events = 20
    split_idx = 10

    events = [
        _make_event(
            f"evt_{i:02d}",
            t0 + timedelta(minutes=15 * i),
            oti=50.0 + i * 0.5,
            ati=25.0 + i * 0.2,
            p_kw=40.0 + i,
            q_kvar=10.0 + i * 0.5,
            i_l1=60.0 + i,
            i_l2=61.0 + i,
            i_l3=59.0 + i,
            v_l1=230.0,
            v_l2=230.0,
            v_l3=230.0,
        )
        for i in range(n_events)
    ]

    # 1. Full replay from beginning
    full_reducer = TwinReducer()
    full_state = full_reducer.reduce_stream(events)
    assert full_state is not None

    # 2. Checkpoint at split_idx
    cp_reducer = TwinReducer(checkpoint_store=checkpoint_store)
    state_at_split = cp_reducer.reduce_stream(events[:split_idx])
    checkpoint_store.save_checkpoint(state_at_split)

    # 3. Restore from checkpoint and continue
    restored_state = checkpoint_store.load_latest_checkpoint("DT-001")
    assert restored_state is not None
    assert restored_state.state_hash == state_at_split.state_hash

    resumed_reducer = TwinReducer()
    resumed_final_state = resumed_reducer.reduce_stream(
        events[split_idx:],
        initial_state=restored_state,
    )

    # 4. Assert exact state and capability equivalence
    assert full_state.state_sequence == resumed_final_state.state_sequence
    assert full_state.state_time_utc == resumed_final_state.state_time_utc
    assert full_state.state_hash == resumed_final_state.state_hash
    assert full_state.model_dump() == resumed_final_state.model_dump()

    evaluator = CapabilityEvaluator()
    m_full = evaluator.evaluate(full_state)
    m_resumed = evaluator.evaluate(resumed_final_state)
    assert m_full.model_dump() == m_resumed.model_dump()


# =========================================================================
# 8. Multi-Asset Isolation
# =========================================================================

def test_multi_asset_isolation() -> None:
    """Interleaved multi-asset events remain completely isolated."""
    reducer_a = TwinReducer()
    reducer_b = TwinReducer()

    t0 = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    ev_a = _make_event("ev_a1", t0, asset_id="DT-001", oti=55.0, p_kw=40.0)
    ev_b = _make_event("ev_b1", t0, asset_id="DT-002", oti=70.0, p_kw=80.0)

    state_a = reducer_a.reduce(None, ev_a)
    state_b = reducer_b.reduce(None, ev_b)

    assert state_a.asset_id == "DT-001"
    assert state_b.asset_id == "DT-002"
    assert state_a.current_observations["top_oil_temperature"].value == 55.0
    assert state_b.current_observations["top_oil_temperature"].value == 70.0

    # Cross-asset reduction attempt must raise ValueError
    with pytest.raises(ValueError, match="Asset mismatch"):
        reducer_a.reduce(state_a, ev_b)


# =========================================================================
# 9. Replay Engine Integration
# =========================================================================

def test_replay_engine_to_phase3_pipeline(storage: StorageEngine) -> None:
    """Historical telemetry stored in DuckDB replayed through the full Phase 3 pipeline."""
    t0 = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    events = [
        _make_event(
            f"evt_{i:02d}",
            t0 + timedelta(minutes=15 * i),
            oti=52.0 + i,
            ati=26.0 + i * 0.2,
            p_kw=42.0 + i,
            q_kvar=12.0 + i * 0.3,
            i_l1=62.0 + i,
            i_l2=63.0 + i,
            i_l3=61.0 + i,
            v_l1=230.0,
            v_l2=230.0,
            v_l3=230.0,
        )
        for i in range(5)
    ]
    storage.insert_canonical_events(events)

    replay = ReplayEngine(storage=storage)
    reducer = TwinReducer()
    evaluator = CapabilityEvaluator()

    state: TwinState | None = None
    count = 0
    for ev in replay.stream():
        state = reducer.reduce(state, ev)
        count += 1

    assert count == 5
    assert state is not None
    assert state.state_sequence == 5
    manifest = evaluator.evaluate(state)
    assert manifest.highest_tier == CapabilityTier.C2_THERMAL_DESCRIPTIVE


# =========================================================================
# 10. Tripura Adapter to Full Phase 3 Pipeline Integration
# =========================================================================

def test_tripura_adapter_to_full_phase3_pipeline() -> None:
    """Real Tripura-shaped telemetry -> Tripura adapter -> Physics -> Reducer -> Capability."""
    adapter = TripuraCSVAdapter()
    reducer = TwinReducer()
    evaluator = CapabilityEvaluator()

    # Multi-source Tripura telemetry records
    overview_raw = {"DeviceTimeStamp": "2026-10-01T00:00", "OTI": "58.0", "ATI": "25.0", "WTI": "0"}
    power_raw = {"DeviceTimeStamp": "2026-10-01T00:00", "KW": "45.2", "KVAR": "15.1", "KVA": "47.6"}
    cv_raw = {
        "DeviceTimeStamp": "2026-10-01T00:00",
        "IL1": "62.0", "IL2": "63.0", "IL3": "61.5",
        "VL1": "230.0", "VL2": "230.5", "VL3": "229.8",
        "INUT": "2.1",
    }
    pf_raw = {"DeviceTimeStamp": "2026-10-01T00:00", "PFL1": "0.95", "PFL2": "0.94", "PFL3": "0.96", "Avg_PF": "0.95", "FRQ": "50.0"}

    events = [
        adapter.transform_record(overview_raw, asset_id="TRIPURA-DT-01"),
        adapter.transform_record(power_raw, asset_id="TRIPURA-DT-01"),
        adapter.transform_record(cv_raw, asset_id="TRIPURA-DT-01"),
        adapter.transform_record(pf_raw, asset_id="TRIPURA-DT-01"),
    ]

    state: TwinState | None = None
    for i, ev in enumerate(events):
        state = reducer.reduce(state, ev)
        # On 3rd event (cv_raw containing IL1..IL3, VL1..VL3), verify electrical imbalance features
        if i == 2:
            assert state.derived_electrical is not None
            assert state.derived_electrical.current_magnitude_imbalance_pct is not None
            assert state.derived_electrical.voltage_magnitude_imbalance_pct is not None

    assert state is not None
    assert state.asset_id == "TRIPURA-DT-01"
    assert state.state_sequence == 4

    manifest = evaluator.evaluate(state)
    assert manifest.highest_tier == CapabilityTier.C2_THERMAL_DESCRIPTIVE
    assert manifest.capabilities["C0"].enabled is True
    assert manifest.capabilities["C1"].enabled is True
    assert manifest.capabilities["C2"].enabled is True
    assert manifest.capabilities["current_imbalance"].enabled is True
    assert manifest.capabilities["voltage_imbalance"].enabled is True
    assert manifest.capabilities["C3"].enabled is False
    assert "MODEL_NOT_PROMOTED" in manifest.capabilities["C3"].disabled_reason_codes


# =========================================================================
# 11. Physical Invariants and Architectural Boundaries Checks
# =========================================================================

def test_physical_invariants_and_architectural_guards() -> None:
    """Verify strictly guarded invariants: WTI contact != Hotspot, unpromoted model != C3."""
    # 1. Discrete WTI contact alone does not satisfy C2
    wti_only_event = _make_event("evt_wti", datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc), wti=0)
    reducer = TwinReducer()
    state_wti = reducer.reduce(None, wti_only_event)
    manifest_wti = evaluate_capabilities(state_wti)
    assert manifest_wti.capabilities["C2"].enabled is False
    assert "DISCRETE_WTI_NOT_SUBSTITUTE_FOR_TOP_OIL" in manifest_wti.capabilities["C2"].disabled_reason_codes

    # 2. Promoted model with missing ambient prevents C3
    no_ambient_event = _make_event(
        "evt_no_amb",
        datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
        oti=60.0,
        p_kw=50.0,
        q_kvar=15.0,
        s_kva=52.2,
    )
    state_no_amb = reducer.reduce(None, no_ambient_event)
    manifest_no_amb = evaluate_capabilities(state_no_amb, model_version="1.0.0", is_model_promoted=True)
    assert manifest_no_amb.capabilities["C3"].enabled is False
    assert "MISSING_AMBIENT_TEMPERATURE" in manifest_no_amb.capabilities["C3"].disabled_reason_codes

    # 3. C4 is disabled when insulation class is unverified
    unverified_profile = AssetProfile(
        asset_id="DT-001",
        insulation_paper_class=InsulationClass.THERMALLY_UPGRADED,
        profile_status=ProfileVerificationStatus.UNVERIFIED,
    )
    all_signals_event = _make_event(
        "evt_all",
        datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc),
        oti=60.0,
        ati=30.0,
        p_kw=50.0,
        q_kvar=15.0,
        s_kva=52.2,
    )
    state_all = reducer.reduce(None, all_signals_event)
    manifest_c4 = evaluate_capabilities(
        state_all,
        profile=unverified_profile,
        model_version="1.0.0",
        is_model_promoted=True,
        hotspot_supported=True,
    )
    assert manifest_c4.highest_tier == CapabilityTier.C3_THERMAL_PREDICTIVE
    assert manifest_c4.capabilities["C4"].enabled is False
    assert "MISSING_VERIFIED_INSULATION_CLASS" in manifest_c4.capabilities["C4"].disabled_reason_codes
