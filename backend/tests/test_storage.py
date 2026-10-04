"""Tests for Storage Engine & Temporal Queries (DuckDB + Parquet).

Verifies Phase 2.2 requirements:
- ACID-like local storage semantics and fast batch ingestion (>= 500 events/sec)
- Union-of-events preservation across sparse/partial telemetry streams
- Model-specific complete-case analytical views
- Temporal ordering, range filtering, and sliding-window aggregations
- Full provenance and measurement quality roundtrip
- Parquet export and import reproducibility
"""

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

from app.core.storage import StorageEngine
from app.models.features import DerivedFeatures
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    RawTelemetryFrame,
    SourceRef,
)


@pytest.fixture
def storage() -> StorageEngine:
    """In-memory StorageEngine fixture."""
    engine = StorageEngine(db_path=":memory:")
    yield engine
    engine.close()


def _make_event(
    event_id: str,
    asset_id: str,
    event_time: datetime,
    measurements: list[Measurement],
    received_time: datetime | None = None,
    quality_flags: list[str] | None = None,
) -> CanonicalEvent:
    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=event_id,
        asset_id=asset_id,
        event_time_utc=event_time,
        received_time_utc=received_time,
        source=SourceRef(
            system="tripura_csv",
            adapter_id="tripura_v1",
            source_record_id=f"rec_{event_id}",
            source_uri="data/tripura_raw/test.csv",
            raw_sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        ),
        measurements=measurements,
        event_quality_flags=quality_flags or [],
        mapping_version="tripura-map-1.0.0",
    )


def test_storage_initialization_and_schema(storage: StorageEngine) -> None:
    """Verify tables and indexes exist on initialization."""
    assert storage.get_event_count() == 0
    assert storage.get_measurement_count() == 0
    t_min, t_max = storage.get_time_bounds("DT-001")
    assert t_min is None
    assert t_max is None


def test_raw_frames_insertion_and_retrieval(storage: StorageEngine) -> None:
    """Verify raw telemetry frames insert and storage integrity."""
    t0 = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    frames = [
        RawTelemetryFrame(
            raw_id=f"raw_{i}",
            source_system="tripura_csv",
            received_time_utc=t0 + timedelta(minutes=15 * i),
            raw_payload={"colA": i * 1.5, "colB": "ok"},
            raw_sha256=f"hash_{i}",
        )
        for i in range(10)
    ]
    inserted = storage.insert_raw_frames(frames)
    assert inserted == 10

    # Query directly from raw_frames
    df = storage._con.execute("SELECT * FROM raw_frames ORDER BY raw_id").df()
    assert len(df) == 10
    assert df.iloc[0]["raw_id"] == "raw_0"
    assert df.iloc[0]["source_system"] == "tripura_csv"


def test_canonical_events_and_measurements_roundtrip(storage: StorageEngine) -> None:
    """Verify CanonicalEvents and all nested Measurement fields survive storage and retrieval."""
    base_time = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    rx_time = datetime(2026, 10, 1, 12, 0, 5, tzinfo=timezone.utc)

    m1 = Measurement(
        signal_id="top_oil_temperature",
        phase=None,
        value=65.5,
        value_type="float",
        unit_ucum="Cel",
        original_name="OTI",
        original_value="65.5",
        original_unit="degC",
        quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=["INITIAL_CALIBRATION"]),
    )
    m2 = Measurement(
        signal_id="current_l1",
        phase="L1",
        value=120.0,
        value_type="float",
        unit_ucum="A",
        original_name="Current_R",
        original_value="120",
        original_unit="A",
        quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
    )

    ev = _make_event(
        event_id="evt_001",
        asset_id="DT-001",
        event_time=base_time,
        measurements=[m1, m2],
        received_time=rx_time,
        quality_flags=["VALIDATED"],
    )

    storage.insert_canonical_events([ev])

    assert storage.get_event_count("DT-001") == 1
    assert storage.get_measurement_count("DT-001") == 2

    retrieved = storage.get_canonical_events("DT-001")
    assert len(retrieved) == 1
    r_ev = retrieved[0]

    assert r_ev.event_id == "evt_001"
    assert r_ev.asset_id == "DT-001"
    assert r_ev.event_time_utc == base_time
    assert r_ev.received_time_utc == rx_time
    assert r_ev.source.system == "tripura_csv"
    assert r_ev.event_quality_flags == ["VALIDATED"]
    assert len(r_ev.measurements) == 2

    # Check measurement fidelity
    oti_m = next(m for m in r_ev.measurements if m.signal_id == "top_oil_temperature")
    assert oti_m.value == 65.5
    assert oti_m.unit_ucum == "Cel"
    assert oti_m.quality.severity == QualitySeverity.GOOD
    assert oti_m.quality.flags == ["INITIAL_CALIBRATION"]

    i_m = next(m for m in r_ev.measurements if m.signal_id == "current_l1")
    assert i_m.value == 120.0
    assert i_m.phase == "L1"


def test_union_of_events_preservation(storage: StorageEngine) -> None:
    """Verify union-of-events: sparse timestamps with partial signals are preserved without global discard."""
    t0 = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)

    # Event 1: has only electrical current (e.g. from CurrentVoltage stream)
    ev1 = _make_event(
        event_id="evt_curr_only",
        asset_id="DT-001",
        event_time=t0,
        measurements=[
            Measurement(
                signal_id="current_l1",
                phase="L1",
                value=50.0,
                value_type="float",
                unit_ucum="A",
                original_name="Current_R",
                original_value="50.0",
                original_unit="A",
            )
        ],
    )

    # Event 2: has only top oil temperature (e.g. from Overview stream)
    ev2 = _make_event(
        event_id="evt_oti_only",
        asset_id="DT-001",
        event_time=t0 + timedelta(minutes=15),
        measurements=[
            Measurement(
                signal_id="top_oil_temperature",
                phase=None,
                value=58.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="58.0",
                original_unit="degC",
            )
        ],
    )

    # Event 3: has both
    ev3 = _make_event(
        event_id="evt_both",
        asset_id="DT-001",
        event_time=t0 + timedelta(minutes=30),
        measurements=[
            Measurement(
                signal_id="current_l1",
                phase="L1",
                value=55.0,
                value_type="float",
                unit_ucum="A",
                original_name="Current_R",
                original_value="55.0",
                original_unit="A",
            ),
            Measurement(
                signal_id="top_oil_temperature",
                phase=None,
                value=60.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="60.0",
                original_unit="degC",
            ),
        ],
    )

    storage.insert_canonical_events([ev1, ev2, ev3])

    # Canonical storage must retain all 3 events (no global dropping)
    assert storage.get_event_count("DT-001") == 3
    assert storage.get_measurement_count("DT-001") == 4

    all_events = storage.get_canonical_events("DT-001")
    assert len(all_events) == 3


def test_complete_case_matrix_filtering(storage: StorageEngine) -> None:
    """Verify model-specific complete-case analytical view filters correctly.

    A thermal model requiring [top_oil_temperature, ambient_temperature] must only receive
    rows where BOTH are present, without affecting storage or other queries.
    """
    t0 = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)

    events = [
        # t=0: has OTI and ATI -> complete for thermal
        _make_event(
            "e0", "DT-001", t0,
            [
                Measurement(signal_id="top_oil_temperature", value=50.0, value_type="float", unit_ucum="Cel", original_name="OTI", original_value="50", original_unit="degC"),
                Measurement(signal_id="ambient_temperature", value=25.0, value_type="float", unit_ucum="Cel", original_name="ATI", original_value="25", original_unit="degC"),
            ]
        ),
        # t=15: has only OTI -> incomplete for thermal
        _make_event(
            "e1", "DT-001", t0 + timedelta(minutes=15),
            [
                Measurement(signal_id="top_oil_temperature", value=52.0, value_type="float", unit_ucum="Cel", original_name="OTI", original_value="52", original_unit="degC"),
            ]
        ),
        # t=30: has OTI, ATI, and active_power -> complete for thermal
        _make_event(
            "e2", "DT-001", t0 + timedelta(minutes=30),
            [
                Measurement(signal_id="top_oil_temperature", value=55.0, value_type="float", unit_ucum="Cel", original_name="OTI", original_value="55", original_unit="degC"),
                Measurement(signal_id="ambient_temperature", value=26.0, value_type="float", unit_ucum="Cel", original_name="ATI", original_value="26", original_unit="degC"),
                Measurement(signal_id="active_power_total", value=100.0, value_type="float", unit_ucum="kW", original_name="P", original_value="100", original_unit="kW"),
            ]
        ),
    ]
    storage.insert_canonical_events(events)

    # Query complete case for [top_oil_temperature, ambient_temperature]
    thermal_df = storage.get_complete_case_matrix(
        asset_id="DT-001",
        required_signals=["top_oil_temperature", "ambient_temperature"],
    )

    # Exactly 2 complete timestamps (t=0 and t=30), t=15 excluded
    assert len(thermal_df) == 2
    assert "top_oil_temperature" in thermal_df.columns
    assert "ambient_temperature" in thermal_df.columns
    assert thermal_df.iloc[0]["top_oil_temperature"] == 50.0
    assert thermal_df.iloc[0]["ambient_temperature"] == 25.0
    assert thermal_df.iloc[1]["top_oil_temperature"] == 55.0
    assert thermal_df.iloc[1]["ambient_temperature"] == 26.0

    # Complete case for electrical [active_power_total]
    elec_df = storage.get_complete_case_matrix(
        asset_id="DT-001",
        required_signals=["active_power_total"],
    )
    assert len(elec_df) == 1
    assert elec_df.iloc[0]["active_power_total"] == 100.0


def test_temporal_range_queries_and_ordering(storage: StorageEngine) -> None:
    """Verify time range filtering, pagination, and deterministic ordering."""
    base = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    events = [
        _make_event(
            f"evt_{i:03d}",
            "DT-001",
            base + timedelta(minutes=15 * i),
            [
                Measurement(
                    signal_id="top_oil_temperature",
                    value=40.0 + i,
                    value_type="float",
                    unit_ucum="Cel",
                    original_name="OTI",
                    original_value=str(40.0 + i),
                    original_unit="degC",
                )
            ],
        )
        for i in range(20)
    ]
    storage.insert_canonical_events(events)

    # Query range from index 5 to 10 inclusive (6 events)
    t_start = base + timedelta(minutes=15 * 5)
    t_end = base + timedelta(minutes=15 * 10)
    range_events = storage.get_canonical_events("DT-001", start_time=t_start, end_time=t_end)
    assert len(range_events) == 6
    assert range_events[0].event_id == "evt_005"
    assert range_events[-1].event_id == "evt_010"

    # Test pagination (limit 3, offset 2)
    paginated = storage.get_canonical_events(
        "DT-001",
        start_time=t_start,
        end_time=t_end,
        limit=3,
        offset=2,
    )
    assert len(paginated) == 3
    assert paginated[0].event_id == "evt_007"
    assert paginated[1].event_id == "evt_008"
    assert paginated[2].event_id == "evt_009"

    # Test reverse order
    desc_events = storage.get_canonical_events(
        "DT-001",
        start_time=t_start,
        end_time=t_end,
        order_asc=False,
    )
    assert desc_events[0].event_id == "evt_010"
    assert desc_events[-1].event_id == "evt_005"


def test_sliding_window_aggregations(storage: StorageEngine) -> None:
    """Verify sliding-window SQL time_bucket aggregates."""
    t0 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
    # Generate 12 samples at 5-minute intervals spanning one hour
    events = [
        _make_event(
            f"e_{i}",
            "DT-001",
            t0 + timedelta(minutes=5 * i),
            [
                Measurement(
                    signal_id="current_l1",
                    value=10.0 + i,
                    value_type="float",
                    unit_ucum="A",
                    original_name="I",
                    original_value=str(10.0 + i),
                    original_unit="A",
                )
            ],
        )
        for i in range(12)
    ]
    storage.insert_canonical_events(events)

    # 15-minute window aggregates -> 4 windows
    agg_df = storage.get_sliding_window_aggregates(
        asset_id="DT-001",
        signal_id="current_l1",
        window_interval="15 minutes",
    )
    assert len(agg_df) == 4
    # First window has i=0 (10), i=1 (11), i=2 (12) -> count 3, min 10, max 12, mean 11
    row0 = agg_df.iloc[0]
    assert row0["sample_count"] == 3
    assert row0["min_value"] == 10.0
    assert row0["max_value"] == 12.0
    assert row0["mean_value"] == 11.0


def test_derived_features_insertion_and_retrieval(storage: StorageEngine) -> None:
    """Verify DerivedFeatures storage and temporal range queries."""
    t0 = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
    features = [
        DerivedFeatures(
            timestamp_utc=t0 + timedelta(minutes=15 * i),
            apparent_power_derived_kva=100.0 + i * 5,
            power_factor_derived=0.95,
            current_mean_a=50.0,
            current_magnitude_imbalance_pct=1.2,
            voltage_magnitude_imbalance_pct=0.5,
            neutral_current_ratio=0.08,
            pqs_inconsistency=0.01,
            relative_load_index=0.8,
            thermal_residual_degc=1.5,
            transform_version="1.0.0",
        )
        for i in range(5)
    ]
    inserted = storage.insert_derived_features(features)
    assert inserted == 5

    df = storage.get_derived_features_df()
    assert len(df) == 5
    assert df.iloc[0]["apparent_power_derived_kva"] == 100.0
    assert df.iloc[0]["power_factor_derived"] == 0.95


def test_ingestion_throughput_performance(storage: StorageEngine) -> None:
    """Verify fast append throughput >= 500 events/sec requirement."""
    t0 = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
    n_events = 1000

    events = [
        _make_event(
            f"perf_evt_{i}",
            "DT-001",
            t0 + timedelta(minutes=15 * i),
            [
                Measurement(
                    signal_id="top_oil_temperature",
                    value=60.0 + (i % 20),
                    value_type="float",
                    unit_ucum="Cel",
                    original_name="OTI",
                    original_value=str(60.0 + (i % 20)),
                    original_unit="degC",
                ),
                Measurement(
                    signal_id="current_l1",
                    phase="L1",
                    value=100.0 + (i % 50),
                    value_type="float",
                    unit_ucum="A",
                    original_name="Current_R",
                    original_value=str(100.0 + (i % 50)),
                    original_unit="A",
                ),
            ],
        )
        for i in range(n_events)
    ]

    t_start = time.perf_counter()
    inserted = storage.insert_canonical_events(events)
    t_elapsed = time.perf_counter() - t_start

    assert inserted == n_events
    rate = n_events / t_elapsed
    print(f"\nThroughput: {rate:.1f} events/sec ({n_events} in {t_elapsed:.3f}s)")
    assert rate >= 500.0, f"Throughput {rate:.1f} events/sec below 500 events/sec target"


def test_parquet_export_and_import(tmp_path: Path) -> None:
    """Verify table export to Parquet and import into a new StorageEngine instance."""
    db1 = StorageEngine(db_path=":memory:")
    t0 = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    ev = _make_event(
        "evt_pq_1",
        "DT-001",
        t0,
        [
            Measurement(
                signal_id="top_oil_temperature",
                value=72.5,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="72.5",
                original_unit="degC",
            )
        ],
    )
    db1.insert_canonical_events([ev])

    events_pq = tmp_path / "canonical_events.parquet"
    meas_pq = tmp_path / "canonical_measurements.parquet"

    db1.export_table_to_parquet("canonical_events", events_pq)
    db1.export_table_to_parquet("canonical_measurements", meas_pq)
    db1.close()

    assert events_pq.exists()
    assert meas_pq.exists()

    # Import into new storage engine
    db2 = StorageEngine(db_path=":memory:")
    db2.import_from_parquet("canonical_events", events_pq)
    db2.import_from_parquet("canonical_measurements", meas_pq)

    assert db2.get_event_count("DT-001") == 1
    assert db2.get_measurement_count("DT-001") == 1

    retrieved = db2.get_canonical_events("DT-001")
    assert len(retrieved) == 1
    assert retrieved[0].event_id == "evt_pq_1"
    assert retrieved[0].measurements[0].value == 72.5
    db2.close()
