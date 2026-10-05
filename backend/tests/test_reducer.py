"""Tests for Stateful Twin Reducer and Checkpointing Engine.

Verifies Phase 3.2 requirements:
- Deterministic state transition F(TwinState_{t-1}, CanonicalEvent_t) -> TwinState_t
- Sequential progression, state sequence increment, and deterministic SHA-256 state hashes
- Option A late-event non-rollback invariant
- Missing-measurement non-imputation (never invent values)
- Checkpoint saving, integrity verification, and restoration
- Equivalence: Full replay == Checkpoint restore + remaining replay
- Asset isolation and corrupted checkpoint failure detection
- Tripura adapter end-to-end integration
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from app.adapters.tripura import TripuraCSVAdapter
from app.core.checkpoint import CheckpointStore, compute_twin_state_hash
from app.core.storage import StorageEngine
from app.engine.reducer import TwinReducer
from app.models.profile import AssetProfile
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)
from app.models.twin_state import TwinState


@pytest.fixture
def storage(tmp_path: Path) -> StorageEngine:
    """In-memory or temporary DuckDB storage engine."""
    db_file = tmp_path / "test_reducer.duckdb"
    engine = StorageEngine(db_path=db_file)
    yield engine
    engine.close()


@pytest.fixture
def checkpoint_store(storage: StorageEngine) -> CheckpointStore:
    return CheckpointStore(storage=storage)


def _make_measurement(
    signal_id: str,
    value: float,
    unit: str,
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
    asset_id: str = "DT-001",
    oti: float = 55.0,
    ati: float = 25.0,
    i_l1: float = 100.0,
    p_kw: float = 60.0,
    q_kvar: float = 40.0,
    quality_flags: list[str] | None = None,
) -> CanonicalEvent:
    measurements = [
        _make_measurement("top_oil_temperature", oti, "Cel"),
        _make_measurement("ambient_temperature", ati, "Cel"),
        _make_measurement("current_l1", i_l1, "A", phase="L1"),
        _make_measurement("active_power_total", p_kw, "kW"),
        _make_measurement("reactive_power_total", q_kvar, "kvar"),
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
            source_uri="data/tripura_raw/test.csv",
            raw_sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        ),
        measurements=measurements,
        event_quality_flags=quality_flags or [],
        mapping_version="tripura-map-1.0.0",
    )


def test_first_event_initializes_twin_state() -> None:
    """Verify first event creates correct initial TwinState."""
    reducer = TwinReducer()
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    ev0 = _make_event("evt_001", t0, asset_id="DT-001", oti=60.0, ati=28.0)

    state = reducer.reduce(None, ev0)

    assert state.asset_id == "DT-001"
    assert state.state_sequence == 1
    assert state.state_time_utc == t0
    assert state.last_processed_event_id == "evt_001"
    assert "top_oil_temperature" in state.current_observations
    assert state.current_observations["top_oil_temperature"].value == 60.0
    assert state.derived_electrical is not None
    assert state.derived_electrical.apparent_power_derived_kva is not None
    assert len(state.state_hash) == 64  # Valid SHA-256


def test_sequential_state_progression() -> None:
    """Verify sequential events update state, increment counter, and maintain latest observations."""
    reducer = TwinReducer()
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    ev0 = _make_event("e0", t0, oti=50.0)
    ev1 = _make_event("e1", t0 + timedelta(minutes=15), oti=52.5)
    ev2 = _make_event("e2", t0 + timedelta(minutes=30), oti=56.0)

    state0 = reducer.reduce(None, ev0)
    assert state0.state_sequence == 1
    assert state0.current_observations["top_oil_temperature"].value == 50.0

    state1 = reducer.reduce(state0, ev1)
    assert state1.state_sequence == 2
    assert state1.current_observations["top_oil_temperature"].value == 52.5
    assert state1.last_processed_event_id == "e1"

    state2 = reducer.reduce(state1, ev2)
    assert state2.state_sequence == 3
    assert state2.current_observations["top_oil_temperature"].value == 56.0
    assert state2.last_processed_event_id == "e2"


def test_state_hash_determinism() -> None:
    """Verify exact reproducibility: identical event stream produces identical state hash."""
    reducer = TwinReducer()
    t0 = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)

    events = [
        _make_event(f"e_{i}", t0 + timedelta(minutes=15 * i), oti=50.0 + i)
        for i in range(10)
    ]

    state_run1 = reducer.reduce_stream(events)
    state_run2 = reducer.reduce_stream(events)

    assert state_run1 is not None and state_run2 is not None
    assert state_run1.state_hash == state_run2.state_hash
    assert state_run1.state_sequence == 10
    assert state_run2.state_sequence == 10


def test_missing_measurements_not_invented() -> None:
    """Verify missing measurements remain None and are not forward-filled or synthesized."""
    reducer = TwinReducer()
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    # Event with only electrical current (no temperature measurements)
    meas = [_make_measurement("current_l1", 80.0, "A", phase="L1")]
    ev = CanonicalEvent(
        schema_version="1.0.0",
        event_id="e_curr_only",
        asset_id="DT-001",
        event_time_utc=t0,
        received_time_utc=None,
        source=SourceRef(
            system="tripura_csv", adapter_id="v1", source_record_id="r1", source_uri="u", raw_sha256="s"
        ),
        measurements=meas,
        event_quality_flags=[],
        mapping_version="map-1.0.0",
    )

    state = reducer.reduce(None, ev)

    # Temperature was NOT observed, so it MUST NOT be in observations or derived features
    assert "top_oil_temperature" not in state.current_observations
    assert state.derived_electrical is not None
    assert state.derived_electrical.voltage_magnitude_imbalance_pct is None
    assert state.derived_electrical.apparent_power_derived_kva is None


def test_late_event_does_not_rewind_active_state() -> None:
    """Verify Option A: late event behind watermark does NOT rewind active TwinState."""
    reducer = TwinReducer()
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    # State advanced to 12:30 -> watermark is 12:20
    ev_30 = _make_event("e_30", t0 + timedelta(minutes=30), oti=65.0)
    state_current = reducer.reduce(None, ev_30)
    hash_before = state_current.state_hash

    # Late event arrives at 12:10 (< 12:20 watermark) with LATE flag
    ev_late = _make_event(
        "e_late",
        t0 + timedelta(minutes=10),
        oti=99.0,
        quality_flags=["OUT_OF_ORDER", "LATE"],
    )

    state_after = reducer.reduce(state_current, ev_late)

    # State MUST be completely unchanged (no rollback)
    assert state_after.state_sequence == state_current.state_sequence
    assert state_after.last_processed_event_id == "e_30"
    assert state_after.state_hash == hash_before
    assert state_after.current_observations["top_oil_temperature"].value == 65.0


def test_asset_isolation() -> None:
    """Verify attempting to reduce an event from a different asset raises ValueError."""
    reducer = TwinReducer()
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    ev_asset1 = _make_event("e1", t0, asset_id="DT-001")
    ev_asset2 = _make_event("e2", t0 + timedelta(minutes=15), asset_id="DT-002")

    state = reducer.reduce(None, ev_asset1)
    with pytest.raises(ValueError, match="Asset mismatch"):
        reducer.reduce(state, ev_asset2)


def test_checkpoint_save_load_roundtrip(checkpoint_store: CheckpointStore) -> None:
    """Verify checkpoint serialization and lossless model reconstruction."""
    reducer = TwinReducer()
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    ev0 = _make_event("e0", t0, oti=62.0, ati=30.0)

    state = reducer.reduce(None, ev0)
    cid = checkpoint_store.save_checkpoint(state)

    assert cid.startswith("chk_DT-001_")
    assert checkpoint_store.get_checkpoint_count("DT-001") == 1

    restored = checkpoint_store.load_latest_checkpoint("DT-001")
    assert restored is not None
    assert restored.asset_id == state.asset_id
    assert restored.state_sequence == state.state_sequence
    assert restored.state_time_utc == state.state_time_utc
    assert restored.state_hash == state.state_hash
    assert restored.last_processed_event_id == state.last_processed_event_id
    assert restored.current_observations["top_oil_temperature"].value == 62.0


def test_restore_plus_replay_equals_full_replay(checkpoint_store: CheckpointStore) -> None:
    """Verify equivalence: Full replay == Checkpoint restore + remaining replay."""
    t0 = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    n_events = 20
    split_idx = 10

    events = [
        _make_event(f"evt_{i:02d}", t0 + timedelta(minutes=15 * i), oti=50.0 + i)
        for i in range(n_events)
    ]

    # 1. Full replay from beginning
    full_reducer = TwinReducer()
    final_full_state = full_reducer.reduce_stream(events)
    assert final_full_state is not None

    # 2. Checkpoint at split_idx
    cp_reducer = TwinReducer(checkpoint_store=checkpoint_store, checkpoint_cadence_events=split_idx)
    state_at_10 = cp_reducer.reduce_stream(events[:split_idx])
    assert state_at_10 is not None

    # Save checkpoint explicitly
    checkpoint_store.save_checkpoint(state_at_10)

    # 3. Restore from checkpoint and process remaining events
    restored_state = checkpoint_store.load_latest_checkpoint("DT-001")
    assert restored_state is not None
    assert restored_state.state_hash == state_at_10.state_hash

    resume_reducer = TwinReducer()
    final_resumed_state = resume_reducer.reduce_stream(events[split_idx:], initial_state=restored_state)

    # 4. Assert exact equivalence of final state
    assert final_resumed_state is not None
    assert final_resumed_state.state_sequence == final_full_state.state_sequence
    assert final_resumed_state.state_time_utc == final_full_state.state_time_utc
    assert final_resumed_state.last_processed_event_id == final_full_state.last_processed_event_id
    assert final_resumed_state.state_hash == final_full_state.state_hash


def test_corrupted_checkpoint_fails_clearly(storage: StorageEngine, checkpoint_store: CheckpointStore) -> None:
    """Verify tampered or corrupted checkpoint JSON fails hash validation clearly."""
    reducer = TwinReducer()
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    ev0 = _make_event("e0", t0, oti=60.0)

    state = reducer.reduce(None, ev0)
    cid = checkpoint_store.save_checkpoint(state)

    # Tamper with checkpoint JSON directly in storage
    storage._con.execute(
        "UPDATE twin_checkpoints SET state_json = replace(state_json, '60.0', '999.0') WHERE checkpoint_id = ?",
        [cid],
    )

    with pytest.raises(ValueError, match="Checkpoint integrity verification failed"):
        checkpoint_store.load_latest_checkpoint("DT-001")


def test_tripura_adapter_end_to_end_reducer_integration(checkpoint_store: CheckpointStore) -> None:
    """Verify reducer and checkpointing against real-shaped Tripura adapter records."""
    adapter = TripuraCSVAdapter()
    t0 = datetime(2020, 3, 1, 12, 0, tzinfo=timezone.utc)

    records = [
        {
            "DeviceTimeStamp": (t0 + timedelta(minutes=15 * i)).strftime("%Y-%m-%d %H:%M:%S"),
            "OTI": f"{55.0 + i * 0.5:.1f}",
            "ATI": f"{27.0 + (i % 5) * 0.2:.1f}",
            "IL1": "45.0",
            "IL2": "46.0",
            "IL3": "44.0",
            "VL1": "230.0",
            "VL2": "231.0",
            "VL3": "229.0",
            "KW": "35.0",
            "KVAR": "15.0",
        }
        for i in range(15)
    ]

    events = [adapter.transform_record(r, asset_id="DT-001") for r in records]

    reducer = TwinReducer(checkpoint_store=checkpoint_store, checkpoint_cadence_events=5)
    final_state = reducer.reduce_stream(events)

    assert final_state is not None
    assert final_state.state_sequence == 15
    assert final_state.current_observations["top_oil_temperature"].value == pytest.approx(55.0 + 14 * 0.5, rel=1e-3)
    assert checkpoint_store.get_checkpoint_count("DT-001") >= 3
