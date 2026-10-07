"""End-to-End Regression Test Suite for Static Edge-Case Fixtures (Phase 10.1).

Verifies that the production pipeline correctly processes the four authoritative
static error and edge-case regression fixtures:
1. fixture_scale_error
2. fixture_timestamp_gaps
3. fixture_conflicting_duplicates
4. fixture_direct_protection_trip

Flow verified:
Fixture -> Ingestion/Storage -> Canonical Telemetry -> Reducer -> Anomaly/Evidence -> OTHI -> Maintenance -> FactBundle -> ReportData.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from app.adapters.fixtures_loader import StaticFixture, load_fixture
from app.core.storage import StorageEngine
from app.engine.anomaly_detectors import MultiDomainAnomalyEngine
from app.engine.capability import CapabilityEvaluator
from app.engine.electrical_episodes import ElectricalEpisodeEngine
from app.engine.exposure import ThermalExposureEngine
from app.engine.fact_bundle import assemble_fact_bundle
from app.engine.maintenance import MaintenanceEngine
from app.engine.othi import OTHIEngine
from app.engine.reducer import TwinReducer
from app.engine.replay import ReplayEngine
from app.models.capability import CapabilityTier
from app.models.health import DomainFreshness, HealthStatus
from app.models.maintenance import ActionWindow, MaintenancePriority
from app.models.telemetry import QualitySeverity
from app.models.twin_state import TwinState
from app.reports.exporters import export_report_csv, export_report_json
from app.reports.pdf_renderer import render_report_pdf
from app.reports.report_generator import generate_report_data


@pytest.fixture
def fixtures_dir() -> Path:
    """Resolve fixtures directory path."""
    p = Path("fixtures")
    if not p.exists():
        p = Path(__file__).resolve().parent.parent.parent.parent / "fixtures"
    assert p.exists(), f"Fixtures directory not found: {p}"
    return p


def _build_production_reducer(asset_id: str) -> TwinReducer:
    """Instantiate a real, unmocked TwinReducer with all canonical domain engines."""
    return TwinReducer(
        episode_engine=ElectricalEpisodeEngine(asset_id=asset_id),
        anomaly_engine=MultiDomainAnomalyEngine(asset_id=asset_id),
        othi_engine=OTHIEngine(),
        exposure_engine=ThermalExposureEngine(asset_id=asset_id),
        maintenance_engine=MaintenanceEngine(),
    )


# ==============================================================================
# 1. fixture_scale_error
# ==============================================================================

def test_fixture_scale_error_end_to_end(fixtures_dir: Path) -> None:
    """Verify transducer scale/gain error handling end-to-end without fabricating false grid faults."""
    fix = load_fixture("fixture_scale_error", fixtures_dir=fixtures_dir)
    assert fix.category == "scale_error"
    assert len(fix.events) == 1

    event = fix.events[0]
    assert event.asset_id == "TX_MOCK_STATIC_01"
    assert "CONTAINS_BAD_MEASUREMENT" in event.event_quality_flags

    # Verify input measurement scale error characteristics
    v1_meas = next(m for m in event.measurements if m.signal_id == "voltage_v1")
    assert v1_meas.value == 0.24
    assert v1_meas.quality.severity == QualitySeverity.BAD
    assert "OUT_OF_RANGE" in v1_meas.quality.flags
    assert "SCALE_ERROR" in v1_meas.quality.flags

    # 1. Ingest into clean StorageEngine
    storage = StorageEngine(db_path=":memory:")
    inserted = storage.insert_canonical_events(fix.events)
    assert inserted == 1

    # 2. Stateful Reduction
    reducer = _build_production_reducer(asset_id=fix.target_asset_id)
    state = reducer.reduce(None, event)

    assert state.state_sequence == 1
    assert state.last_processed_event_id == "evt_scale_err_001"
    assert len(state.state_hash) == 64

    # 3. Feature extraction & capability impact: no false physical grid fault fabricated
    assert state.derived_electrical is not None
    assert state.derived_electrical.voltage_magnitude_imbalance_pct is None

    evaluator = CapabilityEvaluator()
    manifest = evaluator.evaluate(state)
    assert manifest.highest_tier == CapabilityTier.C0_INTEGRITY
    assert manifest.capabilities["voltage_imbalance"].enabled is False

    # 4. Maintenance policy: sensor plausibility rule triggered
    assert len(state.active_recommendations) >= 1
    sensor_rec = next((r for r in state.active_recommendations if "MNT-SENS" in r.rule_id), None)
    assert sensor_rec is not None
    assert sensor_rec.priority == MaintenancePriority.P4_DATA_OR_MODEL
    assert sensor_rec.action_window == ActionWindow.MODEL_REVIEW

    # 5. FactBundle and Reports Assembly
    bundle = assemble_fact_bundle(state=state, capabilities=manifest, capability_evaluator=evaluator)
    assert bundle.provenance_hash is not None
    report_data = generate_report_data(bundle)
    assert report_data.asset.asset_id == "TX_MOCK_STATIC_01"

    storage.close()


# ==============================================================================
# 2. fixture_timestamp_gaps
# ==============================================================================

def test_fixture_timestamp_gaps_end_to_end(fixtures_dir: Path) -> None:
    """Verify cadence monitoring, stale domain gating, and gap recovery without interpolation."""
    fix = load_fixture("fixture_timestamp_gaps", fixtures_dir=fixtures_dir)
    assert fix.category == "timestamp_gaps"
    assert len(fix.events) == 3

    evt1, evt2, evt3 = fix.events
    assert (evt2.event_time_utc - evt1.event_time_utc).total_seconds() == 900.0  # 15 min nominal
    assert (evt3.event_time_utc - evt2.event_time_utc).total_seconds() == 14400.0  # 4-hour dropout gap
    assert "GAP_BEFORE" in evt3.event_quality_flags

    # 1. Clean Storage Ingestion & Replay
    storage = StorageEngine(db_path=":memory:")
    storage.insert_canonical_events(fix.events)

    replay = ReplayEngine(storage=storage, asset_id=fix.target_asset_id, speed_multiplier=0.0)
    replayed = list(replay.stream())
    assert len(replayed) == 3

    # 2. Sequential Stateful Reduction
    reducer = _build_production_reducer(asset_id=fix.target_asset_id)
    evaluator = CapabilityEvaluator()

    state = None
    for ev in replayed:
        state = reducer.reduce(state, ev)

    assert state.state_sequence == 3
    assert state.last_processed_event_id == "evt_gap_003"
    assert len(state.state_hash) == 64

    # 3. Verification of capability and freshness after gap recovery
    manifest = evaluator.evaluate(state)
    assert manifest.capabilities["C2"].enabled is True
    assert manifest.capabilities["C3"].enabled is False  # Model unpromoted / unverified

    assert state.health_bundle is not None
    assert state.health_bundle.is_gated is True
    assert state.health_bundle.domains["thermal"].freshness == DomainFreshness.CURRENT

    # 4. FactBundle and Reports Assembly
    bundle = assemble_fact_bundle(state=state, capabilities=manifest, capability_evaluator=evaluator)
    report_data = generate_report_data(bundle)
    assert report_data.thermal.top_oil_observed_degc == 48.0

    storage.close()


# ==============================================================================
# 3. fixture_conflicting_duplicates
# ==============================================================================

def test_fixture_conflicting_duplicates_end_to_end(fixtures_dir: Path) -> None:
    """Verify quarantine of conflicting concurrent telemetry without silent primary corruption."""
    fix = load_fixture("fixture_conflicting_duplicates", fixtures_dir=fixtures_dir)
    assert fix.category == "conflicting_duplicates"
    assert len(fix.events) == 2

    evt_a, evt_b = fix.events
    assert evt_a.event_time_utc == evt_b.event_time_utc
    assert evt_a.asset_id == evt_b.asset_id
    assert "CONFLICT" in evt_b.event_quality_flags
    assert "QUARANTINED" in evt_b.event_quality_flags

    # 1. Clean Storage Ingestion
    storage = StorageEngine(db_path=":memory:")
    storage.insert_canonical_events(fix.events)

    # 2. Sequential Stateful Reduction
    reducer = _build_production_reducer(asset_id=fix.target_asset_id)
    evaluator = CapabilityEvaluator()

    state_1 = reducer.reduce(None, evt_a)
    assert state_1.state_sequence == 1
    assert state_1.last_processed_event_id == "evt_conflict_001_primary"

    state_2 = reducer.reduce(state_1, evt_b)
    assert state_2.state_sequence == 2
    assert state_2.last_processed_event_id == "evt_conflict_001_secondary"
    assert len(state_2.state_hash) == 64

    # 3. Sensor maintenance advisory triggered for conflicting/bad measurement
    assert any("MNT-SENS" in r.rule_id for r in state_2.active_recommendations)

    # 4. FactBundle and Reports Assembly
    manifest = evaluator.evaluate(state_2)
    bundle = assemble_fact_bundle(state=state_2, capabilities=manifest, capability_evaluator=evaluator)
    assert bundle.provenance_hash is not None

    storage.close()


# ==============================================================================
# 4. fixture_direct_protection_trip
# ==============================================================================

def test_fixture_direct_protection_trip_end_to_end(fixtures_dir: Path) -> None:
    """Verify decisive single-step critical escalation and P0 emergency dispatch advice."""
    fix = load_fixture("fixture_direct_protection_trip", fixtures_dir=fixtures_dir)
    assert fix.category == "direct_protection_trip"
    assert len(fix.events) == 2

    pre_evt, trip_evt = fix.events
    assert "DIRECT_PROTECTION_TRIP" in trip_evt.event_quality_flags

    # 1. Clean Storage Ingestion
    storage = StorageEngine(db_path=":memory:")
    storage.insert_canonical_events(fix.events)

    # 2. Sequential Stateful Reduction
    reducer = _build_production_reducer(asset_id=fix.target_asset_id)
    evaluator = CapabilityEvaluator()

    # Step 1: Pre-trip nominal state
    state_pre = reducer.reduce(None, pre_evt)
    assert state_pre.state_sequence == 1
    assert state_pre.health_bundle is not None
    assert state_pre.health_bundle.domains["oil_protection"].severity == 0.0

    # Step 2: Instantaneous trip event
    state_trip = reducer.reduce(state_pre, trip_evt)
    assert state_trip.state_sequence == 2
    assert state_trip.last_processed_event_id == "evt_trip_002_trip"
    assert len(state_trip.state_hash) == 64

    # 3. Decisive single-step critical health escalation
    assert state_trip.health_bundle is not None
    assert state_trip.health_bundle.domains["oil_protection"].status == HealthStatus.CRITICAL
    assert state_trip.health_bundle.domains["oil_protection"].severity == 1.0
    assert state_trip.health_bundle.domains["thermal"].status == HealthStatus.CRITICAL

    # 4. Immediate P0 emergency dispatch recommendation
    p0_recs = [r for r in state_trip.active_recommendations if r.priority == MaintenancePriority.P0_SAFETY]
    assert len(p0_recs) >= 1
    p0_rec = p0_recs[0]
    assert p0_rec.action_window == ActionWindow.IMMEDIATE
    assert "MNT-PROT-001" in p0_rec.rule_id
    assert "Protection Contact Trip Action" in p0_rec.title

    # 5. FactBundle and Reports Assembly
    manifest = evaluator.evaluate(state_trip)
    bundle = assemble_fact_bundle(state=state_trip, capabilities=manifest, capability_evaluator=evaluator)
    report_data = generate_report_data(bundle)

    assert report_data.active_recommendations[0].priority == MaintenancePriority.P0_SAFETY
    assert report_data.active_recommendations[0].action_window == ActionWindow.IMMEDIATE

    # Verify JSON and CSV export generation from trip state
    json_out = export_report_json(report_data)
    assert "MNT-PROT-001" in json_out
    assert "P0" in json_out

    csv_out = export_report_csv(report_data, historical_events=fix.events)
    assert "MNT-PROT-001" in csv_out
    assert "TX_MOCK_STATIC_01" in csv_out

    storage.close()


# ==============================================================================
# 5. Determinism Verification Across All Four Fixtures
# ==============================================================================

@pytest.mark.parametrize(
    "fixture_name",
    [
        "fixture_scale_error",
        "fixture_timestamp_gaps",
        "fixture_conflicting_duplicates",
        "fixture_direct_protection_trip",
    ],
)
def test_fixture_determinism_across_repeated_runs(fixture_name: str, fixtures_dir: Path) -> None:
    """Verify that replaying each static fixture twice from clean state produces identical results."""
    fix = load_fixture(fixture_name, fixtures_dir=fixtures_dir)

    def _execute_run() -> dict:
        storage = StorageEngine(db_path=":memory:")
        storage.insert_canonical_events(fix.events)
        replay = ReplayEngine(storage=storage, asset_id=fix.target_asset_id, speed_multiplier=0.0)

        reducer = _build_production_reducer(asset_id=fix.target_asset_id)
        evaluator = CapabilityEvaluator()

        state: TwinState | None = None
        for ev in replay.stream():
            state = reducer.reduce(state, ev)

        assert state is not None
        manifest = evaluator.evaluate(state)
        bundle = assemble_fact_bundle(state=state, capabilities=manifest, capability_evaluator=evaluator)
        report_data = generate_report_data(bundle)

        json_text = export_report_json(report_data)
        csv_text = export_report_csv(report_data, historical_events=fix.events)
        storage.close()

        return {
            "state_sequence": state.state_sequence,
            "state_hash": state.state_hash,
            "provenance_hash": bundle.provenance_hash,
            "recs_count": len(state.active_recommendations),
            "episodes_count": len(state.open_episodes),
            "json_payload": json_text,
            "csv_payload": csv_text,
        }

    run_1 = _execute_run()
    run_2 = _execute_run()

    assert run_1["state_sequence"] == run_2["state_sequence"]
    assert run_1["state_hash"] == run_2["state_hash"]
    assert run_1["provenance_hash"] == run_2["provenance_hash"]
    assert run_1["recs_count"] == run_2["recs_count"]
    assert run_1["episodes_count"] == run_2["episodes_count"]
    assert run_1["json_payload"] == run_2["json_payload"]
    assert run_1["csv_payload"] == run_2["csv_payload"]
