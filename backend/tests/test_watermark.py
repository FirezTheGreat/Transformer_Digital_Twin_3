"""Tests for Watermarking & Late-Event Handling Service.

Verifies Phase 2.3 requirements:
- Watermark advancement based on 10-minute lateness bound
- In-order and in-watermark out-of-order event reordering
- Strict deterministic ordering (event_time_utc ASC, event_id ASC)
- Late events (t < watermark) handled per Option A: stored, flagged with OUT_OF_ORDER & LATE
- Late events do not emit into active stream (no state rewind)
- Preservation of original event timestamps and source provenance
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.core.storage import StorageEngine
from app.core.watermark import WatermarkManager
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)


@pytest.fixture
def storage() -> StorageEngine:
    """In-memory storage fixture."""
    engine = StorageEngine(db_path=":memory:")
    yield engine
    engine.close()


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
            raw_sha256="abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
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


def test_watermark_advancement_in_order() -> None:
    """Verify watermark advances with monotonically increasing events."""
    wm = WatermarkManager(lateness_budget_seconds=600.0)  # 10 mins
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    # Initial state
    assert wm.get_watermark() is None
    assert wm.get_max_event_time() is None

    # Event at t=12:00 -> watermark becomes 11:50
    ev0 = _make_event("e0", t0)
    emitted0 = wm.process_event(ev0)
    assert wm.get_max_event_time() == t0
    assert wm.get_watermark() == t0 - timedelta(minutes=10)
    # ev0 (12:00) > watermark (11:50), so it stays buffered awaiting watermark progression
    assert len(emitted0) == 0
    assert wm.get_buffer_size() == 1

    # Event at t=12:15 -> watermark becomes 12:05 -> ev0 (12:00) <= 12:05, so ev0 is emitted
    ev1 = _make_event("e1", t0 + timedelta(minutes=15))
    emitted1 = wm.process_event(ev1)
    assert wm.get_max_event_time() == t0 + timedelta(minutes=15)
    assert wm.get_watermark() == t0 + timedelta(minutes=5)
    assert len(emitted1) == 1
    assert emitted1[0].event_id == "e0"
    assert wm.get_buffer_size() == 1  # e1 remains buffered


def test_in_window_out_of_order_reordering() -> None:
    """Verify out-of-order events arriving within the 10-minute window are deterministically sorted."""
    wm = WatermarkManager(lateness_budget_seconds=600.0)  # 10 mins
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    # Event at 12:05 arrives first
    ev_05 = _make_event("e_05", t0 + timedelta(minutes=5))
    wm.process_event(ev_05)
    # Watermark is 12:05 - 10 min = 11:55

    # Event at 12:00 arrives second (out-of-order, but 12:00 >= 11:55 watermark, so accepted)
    ev_00 = _make_event("e_00", t0)
    wm.process_event(ev_00)

    # Event at 12:03 arrives third (out-of-order, 12:03 >= 11:55, accepted)
    ev_03 = _make_event("e_03", t0 + timedelta(minutes=3))
    wm.process_event(ev_03)

    assert wm.get_buffer_size() == 3

    # Event at 12:20 arrives -> watermark advances to 12:10 -> drains all 3 buffered events in chronological order
    ev_20 = _make_event("e_20", t0 + timedelta(minutes=20))
    emitted = wm.process_event(ev_20)

    assert len(emitted) == 3
    assert [e.event_id for e in emitted] == ["e_00", "e_03", "e_05"]
    assert emitted[0].event_time_utc == t0
    assert emitted[1].event_time_utc == t0 + timedelta(minutes=3)
    assert emitted[2].event_time_utc == t0 + timedelta(minutes=5)


def test_late_event_option_a_handling(storage: StorageEngine) -> None:
    """Verify Option A: late events (t < watermark) are stored, flagged LATE + OUT_OF_ORDER, and not emitted."""
    wm = WatermarkManager(lateness_budget_seconds=600.0, storage=storage)
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    # Prime watermark with event at 12:30 -> watermark is 12:20
    ev_30 = _make_event("e_30", t0 + timedelta(minutes=30))
    wm.process_event(ev_30)
    assert wm.get_watermark() == t0 + timedelta(minutes=20)

    # Late event arrives at 12:10 (< 12:20 watermark)
    ev_late = _make_event("e_late", t0 + timedelta(minutes=10), val=77.0)
    emitted = wm.process_event(ev_late)

    # MUST NOT be emitted into the active stream (no state rollback)
    assert len(emitted) == 0

    # Must be recorded as late event
    late_events = wm.get_late_events()
    assert len(late_events) == 1
    assert late_events[0].event_id == "e_late"
    assert "OUT_OF_ORDER" in late_events[0].event_quality_flags
    assert "LATE" in late_events[0].event_quality_flags
    assert late_events[0].measurements[0].quality.severity == QualitySeverity.UNCERTAIN

    # Must generate an audit notification
    notifs = wm.get_late_notifications()
    assert len(notifs) == 1
    assert notifs[0]["event_id"] == "e_late"
    assert notifs[0]["action"] == "STORED_AND_FLAGGED_LATE"

    # Must be persisted in DuckDB storage
    stored_ev = storage.get_canonical_event_by_id("e_late")
    assert stored_ev is not None
    assert stored_ev.event_time_utc == t0 + timedelta(minutes=10)
    assert "OUT_OF_ORDER" in stored_ev.event_quality_flags
    assert "LATE" in stored_ev.event_quality_flags
    assert stored_ev.measurements[0].value == 77.0


def test_provenance_and_timestamp_preservation() -> None:
    """Verify late event processing does not alter original source timestamps or provenance."""
    wm = WatermarkManager(lateness_budget_seconds=600.0)
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    # Advance watermark to 12:20
    wm.process_event(_make_event("e_30", t0 + timedelta(minutes=30)))

    # Late event at 12:05
    original_late_time = t0 + timedelta(minutes=5)
    ev_late = _make_event("e_late_5", original_late_time)

    wm.process_event(ev_late)
    late_ev = wm.get_late_events()[0]

    # Timestamp MUST NOT be fabricated/shifted to appear current
    assert late_ev.event_time_utc == original_late_time
    assert late_ev.source.system == "tripura_csv"
    assert late_ev.source.source_record_id == "row_e_late_5"
    assert late_ev.source.raw_sha256 == "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"


def test_deterministic_tie_breaking() -> None:
    """Verify deterministic ordering with identical timestamps uses event_id as secondary key."""
    wm = WatermarkManager(lateness_budget_seconds=600.0)
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    ev_b = _make_event("evt_B", t0)
    ev_a = _make_event("evt_A", t0)
    ev_c = _make_event("evt_C", t0)

    wm.process_events([ev_b, ev_a, ev_c])
    drained = wm.flush()

    assert [e.event_id for e in drained] == ["evt_A", "evt_B", "evt_C"]


def test_batch_flush_drains_all_buffered_events() -> None:
    """Verify flush drains all events in the reordering buffer in deterministic order."""
    wm = WatermarkManager(lateness_budget_seconds=600.0)
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    events = [
        _make_event(f"e_{i}", t0 + timedelta(minutes=i))
        for i in [3, 1, 4, 2, 0]
    ]
    wm.process_events(events)

    assert wm.get_buffer_size() == 5
    drained = wm.flush()
    assert wm.get_buffer_size() == 0
    assert len(drained) == 5
    assert [e.event_id for e in drained] == ["e_0", "e_1", "e_2", "e_3", "e_4"]
