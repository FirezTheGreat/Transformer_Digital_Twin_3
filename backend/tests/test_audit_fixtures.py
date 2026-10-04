"""Unit tests for Phase 1, Substep 1.3 — Static Error & Edge-Case Fixtures Synthesis."""

from pathlib import Path
import json
import pytest

from app.adapters.fixtures_loader import StaticFixtureLoader, load_fixture
from app.models.telemetry import CanonicalEvent, QualitySeverity


@pytest.fixture
def fixtures_dir() -> Path:
    p = Path("fixtures")
    assert p.exists(), "fixtures directory must exist"
    return p


def test_load_all_fixtures_successfully(fixtures_dir: Path) -> None:
    loader = StaticFixtureLoader(fixtures_dir=fixtures_dir)
    all_fixtures = loader.load_all_fixtures()

    expected_ids = {
        "fixture_scale_error",
        "fixture_timestamp_gaps",
        "fixture_conflicting_duplicates",
        "fixture_direct_protection_trip",
    }
    assert set(all_fixtures.keys()) == expected_ids

    for fix_id, fix in all_fixtures.items():
        assert fix.is_synthetic is True
        assert len(fix.events) >= 1
        for evt in fix.events:
            assert isinstance(evt, CanonicalEvent)
            assert evt.schema_version == "1.0.0"
            assert len(evt.measurements) >= 1


def test_scale_error_fixture_characteristics(fixtures_dir: Path) -> None:
    fix = load_fixture("fixture_scale_error", fixtures_dir=fixtures_dir)
    assert fix.category == "scale_error"
    assert fix.expected_behavior.expected_severity == "BAD"
    assert fix.expected_behavior.quarantine_measurement is True

    evt = fix.events[0]
    bad_meas = [m for m in evt.measurements if m.quality.severity == QualitySeverity.BAD]
    assert len(bad_meas) == 1
    assert bad_meas[0].signal_id == "voltage_v1"
    assert bad_meas[0].value == 0.24  # 0.240 kV mistakenly normalized or recorded
    assert "OUT_OF_RANGE" in bad_meas[0].quality.flags
    assert "SCALE_ERROR" in bad_meas[0].quality.flags


def test_timestamp_gap_fixture_characteristics(fixtures_dir: Path) -> None:
    fix = load_fixture("fixture_timestamp_gaps", fixtures_dir=fixtures_dir)
    assert fix.category == "timestamp_gaps"
    assert len(fix.events) == 3

    evt1, evt2, evt3 = fix.events
    delta_1_2 = evt2.event_time_utc - evt1.event_time_utc
    delta_2_3 = evt3.event_time_utc - evt2.event_time_utc

    assert delta_1_2.total_seconds() == 900.0  # 15 minutes
    assert delta_2_3.total_seconds() == 14400.0  # 4 hours gap (unnotified dropout)

    # Recovery event has GAP_BEFORE flag
    assert "GAP_BEFORE" in evt3.event_quality_flags
    for m in evt3.measurements:
        assert m.quality.severity == QualitySeverity.UNCERTAIN
        assert "GAP_BEFORE" in m.quality.flags


def test_conflicting_duplicates_fixture_characteristics(fixtures_dir: Path) -> None:
    fix = load_fixture("fixture_conflicting_duplicates", fixtures_dir=fixtures_dir)
    assert fix.category == "conflicting_duplicates"
    assert len(fix.events) == 2

    evt_a, evt_b = fix.events
    # Both events share exact same timestamp and asset ID
    assert evt_a.asset_id == evt_b.asset_id
    assert evt_a.event_time_utc == evt_b.event_time_utc
    assert evt_a.event_id != evt_b.event_id  # Distinct event records

    # Measurements differ
    val_a = {m.signal_id: m.value for m in evt_a.measurements}
    val_b = {m.signal_id: m.value for m in evt_b.measurements}
    assert val_a != val_b

    # Second conflicting event is explicitly flagged CONFLICT with BAD severity
    assert "CONFLICT" in evt_b.event_quality_flags
    assert "QUARANTINED" in evt_b.event_quality_flags
    for m in evt_b.measurements:
        assert m.quality.severity == QualitySeverity.BAD
        assert "CONFLICT" in m.quality.flags


def test_direct_protection_trip_fixture_characteristics(fixtures_dir: Path) -> None:
    fix = load_fixture("fixture_direct_protection_trip", fixtures_dir=fixtures_dir)
    assert fix.category == "direct_protection_trip"
    assert len(fix.events) == 2

    pre_evt, trip_evt = fix.events

    # Pre-trip: healthy voltage, load current, flags 0
    pre_meas = {m.signal_id: m.value for m in pre_evt.measurements}
    assert pre_meas["current_i1"] > 50.0
    assert pre_meas["oil_temp_trip_flag"] == 0
    assert pre_meas["magnetic_oil_gauge_alarm_flag"] == 0

    # Trip event: breaker opened (current=0), discrete contacts energized (trip=1, low oil=1)
    trip_meas = {m.signal_id: m.value for m in trip_evt.measurements}
    assert trip_meas["current_i1"] == 0.0
    assert trip_meas["oil_temp_trip_flag"] == 1
    assert trip_meas["magnetic_oil_gauge_alarm_flag"] == 1
    assert "DIRECT_PROTECTION_TRIP" in trip_evt.event_quality_flags


def test_fixtures_isolated_from_real_data(fixtures_dir: Path) -> None:
    loader = StaticFixtureLoader(fixtures_dir=fixtures_dir)
    all_fixtures = loader.load_all_fixtures()

    # Verify that mockFactBundle is separate from static error fixtures
    mock_bundle_path = fixtures_dir / "mockFactBundle.json"
    assert mock_bundle_path.exists()

    # Verify fixture IDs are not present in processed partition metadata
    meta_path = Path("data/processed/tripura_partitions_metadata.json")
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        for fix_id in all_fixtures:
            assert fix_id not in json.dumps(manifest)
