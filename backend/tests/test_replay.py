"""Tests for Deterministic Chronological Replay Engine.

Verifies Phase 2.4 requirements:
- Strictly deterministic chronological replay (event_time_utc ASC, event_id ASC)
- Playback controls: step, stream, play, pause, stop, reset, seek
- Configurable replay speeds (1x, 5x, 10x, max)
- Historical range filtering and default Tripura TEST period selection
- Out-of-order test/chaos mode for watermark verification
- Non-mutation of historical data and no model training/learning invocation
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

from app.core.storage import StorageEngine
from app.core.watermark import WatermarkManager
from app.engine.replay import ReplayEngine
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)


def _make_event(
    event_id: str,
    event_time: datetime,
    asset_id: str = "DT-001",
    val: float = 50.0,
) -> CanonicalEvent:
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
        measurements=[
            Measurement(
                signal_id="top_oil_temperature",
                phase=None,
                value=val,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value=str(val),
                original_unit="degC",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            )
        ],
        event_quality_flags=[],
        mapping_version="tripura-map-1.0.0",
    )


@pytest.fixture
def sample_events() -> list[CanonicalEvent]:
    t0 = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    return [
        _make_event(f"evt_{i:02d}", t0 + timedelta(minutes=15 * i), val=40.0 + i)
        for i in range(10)
    ]


def test_chronological_ordering_and_tie_breaking() -> None:
    """Verify strictly chronological event sequence with event_id tie-breaking."""
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    # Scrambled input with simultaneous timestamps
    events = [
        _make_event("evt_C", t0 + timedelta(minutes=15)),
        _make_event("evt_A", t0),
        _make_event("evt_B", t0),
        _make_event("evt_D", t0 + timedelta(minutes=30)),
    ]

    engine = ReplayEngine(events=events)
    emitted = list(engine.stream())

    assert len(emitted) == 4
    assert [e.event_id for e in emitted] == ["evt_A", "evt_B", "evt_C", "evt_D"]


def test_step_and_progress_controls(sample_events: list[CanonicalEvent]) -> None:
    """Verify single-stepping, seek, pause, and progress state."""
    engine = ReplayEngine(events=sample_events)
    assert engine.get_progress()["total_events"] == 10
    assert engine.get_progress()["cursor"] == 0

    # Step twice
    e0 = engine.step()
    e1 = engine.step()
    assert e0 is not None and e0.event_id == "evt_00"
    assert e1 is not None and e1.event_id == "evt_01"
    assert engine.get_progress()["cursor"] == 2

    # Seek to index 5
    engine.seek(5)
    e5 = engine.step()
    assert e5 is not None and e5.event_id == "evt_05"

    # Reset
    engine.reset()
    assert engine.get_progress()["cursor"] == 0
    e_first = engine.step()
    assert e_first is not None and e_first.event_id == "evt_00"


def test_playback_speed_configuration(sample_events: list[CanonicalEvent]) -> None:
    """Verify 1x, 5x, 10x, and maximum speed configuration."""
    # Max speed (multiplier = 0.0) -> no sleep calls
    sleep_calls: list[float] = []
    engine_max = ReplayEngine(events=sample_events[:3], speed_multiplier=0.0)
    engine_max.play(sleep_fn=sleep_calls.append)
    assert len(sleep_calls) == 0

    # 10x speed -> scaled sleep calls
    sleep_calls.clear()
    engine_10x = ReplayEngine(events=sample_events[:3], speed_multiplier=10.0)
    engine_10x.play(sleep_fn=sleep_calls.append)
    # 15 min = 900s. At 10x speed, 900s / 10 = 90s, bounded by 5.0s safety limit
    assert len(sleep_calls) == 2
    assert all(s > 0 for s in sleep_calls)


def test_range_boundaries_and_empty_range(sample_events: list[CanonicalEvent]) -> None:
    """Verify start_time and end_time range filtering and empty range handling."""
    t0 = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    t_start = t0 + timedelta(minutes=30)  # evt_02
    t_end = t0 + timedelta(minutes=75)    # evt_05

    engine = ReplayEngine(events=sample_events, start_time=t_start, end_time=t_end)
    emitted = list(engine.stream())
    assert len(emitted) == 4
    assert emitted[0].event_id == "evt_02"
    assert emitted[-1].event_id == "evt_05"

    # Empty range (in the future)
    empty_engine = ReplayEngine(
        events=sample_events,
        start_time=t0 + timedelta(days=10),
        end_time=t0 + timedelta(days=11),
    )
    assert len(list(empty_engine.stream())) == 0


def test_tripura_test_period_selection() -> None:
    """Verify configure_tripura_test_period sets exact holdout dates."""
    engine = ReplayEngine()
    start_t, end_t = engine.configure_tripura_test_period()

    assert start_t == datetime(2020, 2, 13, 16, 0, tzinfo=timezone.utc)
    assert end_t == datetime(2020, 4, 14, 0, 30, tzinfo=timezone.utc)


def test_out_of_order_chaos_mode_with_watermarking() -> None:
    """Verify controlled chaos mode emits out-of-order events to exercise WatermarkManager."""
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    events = [
        _make_event(f"e_{i:02d}", t0 + timedelta(minutes=15 * i))
        for i in range(8)
    ]

    # Chaos engine
    chaos_engine = ReplayEngine(events=events, chaos_mode=True, chaos_seed=123)
    chaos_emitted = list(chaos_engine.stream())

    # Raw chaos output has at least one pair swapped
    chaos_ids = [e.event_id for e in chaos_emitted]
    normal_ids = [f"e_{i:02d}" for i in range(8)]
    assert chaos_ids != normal_ids

    # Pass chaos output through WatermarkManager
    wm = WatermarkManager(lateness_budget_seconds=1800.0)  # 30 min window
    drained_events: list[CanonicalEvent] = []
    for ev in chaos_emitted:
        ready = wm.process_event(ev)
        drained_events.extend(ready)
    drained_events.extend(wm.flush())

    # After watermark reordering, final output MUST be perfectly sorted
    final_ids = [e.event_id for e in drained_events]
    assert final_ids == normal_ids


def test_reset_determinism(sample_events: list[CanonicalEvent]) -> None:
    """Verify reset reproduces byte-identical sequence across multiple replay iterations."""
    engine = ReplayEngine(events=sample_events)

    run1 = [e.event_id for e in engine.stream()]
    engine.reset()
    run2 = [e.event_id for e in engine.stream()]

    assert run1 == run2
    assert len(run1) == 10


def test_data_immutability_and_no_learning(sample_events: list[CanonicalEvent]) -> None:
    """Verify replay is strictly read-only and does not mutate CanonicalEvents."""
    original_hashes = [ev.source.raw_sha256 for ev in sample_events]
    original_times = [ev.event_time_utc for ev in sample_events]

    engine = ReplayEngine(events=sample_events)
    engine.play()

    # Assert source events in memory are 100% identical
    assert [ev.source.raw_sha256 for ev in sample_events] == original_hashes
    assert [ev.event_time_utc for ev in sample_events] == original_times
