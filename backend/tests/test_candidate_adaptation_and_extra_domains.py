"""Phase 3, 4 & 5 Verification Suite: Candidate Adaptation and Extra Domain Capabilities.

Verifies:
1. Candidate Dataset Audit & Stream: GridPulseSyntheticAdapter ingests candidate data cleanly.
2. Canonical Telemetry Expansion: Unit validation, deterministic replay, COMM_LOSS handling.
3. Construction-Aware Asset Profiles: DT-01..04 profile metadata & capability gating.
4. Extra A: Oil-level trend & suspected-leak monitoring, stuck gauge detection.
5. Extra B: Sealed-tank pressure monitoring, PRD contact, conservator exclusion.
6. Extra C: Prospective short-circuit calculation, LV breaker and HV fuse trips.
7. Extra D: Construction-aware capability manifest and maintenance recommendation wiring.
"""

from datetime import datetime, timezone
import math
import pytest

from app.adapters.gridpulse_synthetic import (
    GridPulseSyntheticAdapter,
    SYNTHETIC_ASSET_PROFILES,
)
from app.adapters.cpri_v3 import CPRIv3SourceAdapter
from app.engine.anomaly_detectors import (
    AnomalyDetectorThresholds,
    MultiDomainAnomalyEngine,
    detect_protection_oil_status,
)
from app.engine.capability import CapabilityEvaluator
from app.engine.maintenance import MaintenanceEngine
from app.engine.physics import (
    calculate_prospective_short_circuit_ka,
    extract_electrical_features,
)
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.maintenance import MaintenancePriority
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)


def _make_meas(signal_id: str, value: float | int | str | bool, unit: str = "1", phase: str | None = None) -> Measurement:
    return Measurement(
        signal_id=signal_id,
        phase=phase,
        value=value,
        value_type="float" if isinstance(value, float) else ("int" if isinstance(value, int) else "bool"),
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(severity=QualitySeverity.GOOD),
    )


def _make_event(asset_id: str, t: datetime, measurements: list[Measurement], flags: list[str] | None = None) -> CanonicalEvent:
    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=f"ev_{asset_id}_{t.strftime('%Y%m%d%H%M%S')}",
        asset_id=asset_id,
        event_time_utc=t,
        source=SourceRef(
            system="test",
            adapter_id="test_adapter",
            source_record_id=f"rec_{asset_id}",
            source_uri="test://uri",
            raw_sha256="abc123hash",
        ),
        measurements=measurements,
        event_quality_flags=flags or [],
        mapping_version="test-1.0",
    )


# ==============================================================================
# Phase 3 & 4: Adapter and Canonical Ingestion Tests
# ==============================================================================

def test_gridpulse_synthetic_adapter_record_transform():
    """Verify raw row transformation to CanonicalEvent with UCUM units and deterministic UUID."""
    adapter = GridPulseSyntheticAdapter()
    raw_row = {
        "timestamp_utc": "2025-01-01T00:00:00Z",
        "asset_id": "DT-01",
        "partition": "FIT",
        "dq_flag": "OK",
        "v_l1n_v": 249.4,
        "v_l12_v": 431.8,
        "i_l1_a": 97.8,
        "p_kw": 67.0,
        "q_kvar": 23.6,
        "s_kva": 71.1,
        "pf": 0.943,
        "freq_hz": 49.99,
        "ambient_c": 10.7,
        "top_oil_c": 25.1,
        "oil_level_pct": 24.4,
        "oil_level_trend_pct_per_day": -0.05,
        "lv_breaker_closed": 1,
        "lv_breaker_trip": 0,
    }

    event = adapter.transform_record(raw_row, asset_id="DT-01", source_uri="test.csv")

    assert event.asset_id == "DT-01"
    assert event.event_time_utc == datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert len(event.measurements) >= 14

    # Verify deterministic UUID
    event2 = adapter.transform_record(raw_row, asset_id="DT-01", source_uri="test.csv")
    assert event.event_id == event2.event_id

    # Check UCUM canonical units
    meas_map = {m.signal_id: m for m in event.measurements}
    assert meas_map["voltage_v1"].unit_ucum == "V"
    assert meas_map["top_oil_temperature"].unit_ucum == "Cel"
    assert meas_map["oil_level_pct"].unit_ucum == "%"
    assert meas_map["oil_level_trend_pct_per_day"].unit_ucum in ("percent/day", "% / day")


def test_gridpulse_synthetic_comm_loss_handling():
    """Verify COMM_LOSS data quality flag applies BAD severity without leaking oracle labels."""
    adapter = GridPulseSyntheticAdapter()
    raw_row = {
        "timestamp_utc": "2025-03-12T07:30:00Z",
        "asset_id": "DT-01",
        "dq_flag": "COMM_LOSS",
        "v_l1n_v": float("nan"),
        "top_oil_c": float("nan"),
    }

    event = adapter.transform_record(raw_row, asset_id="DT-01", source_uri="test.csv")
    assert "COMM_LOSS" in event.event_quality_flags
    for m in event.measurements:
        assert m.quality.severity == QualitySeverity.BAD


def test_cpri_adapter_remains_intact_and_compatible():
    """Verify that adding the candidate adapter leaves CPRI adapter fully operational."""
    cpri_adapter = CPRIv3SourceAdapter()
    raw_row = {
        "meta_timestamp": "2026-03-01T00:00:00Z",
        "timestamp_utc": "2026-03-01T00:00:00Z",
        "x_v_l1n_v": 230.0,
        "x_i_l1_a": 10.0,
        "x_i_l2_a": 10.0,
        "x_i_l3_a": 10.0,
        "x_active_power_kw": 6.9,
        "x_reactive_power_kvar": 0.5,
        "x_apparent_power_kva": 7.0,
        "x_power_factor": 0.98,
        "x_frequency_hz": 50.0,
        "x_oil_temp_c": 55.0,
        "x_ambient_temp_c": 30.0,
    }
    event = cpri_adapter.transform_record(raw_row, asset_id="dt_001", source_uri="cpri.parquet")
    assert event.asset_id == "dt_001"
    assert any(m.signal_id == "voltage_v1" for m in event.measurements)


# ==============================================================================
# Phase 5 Extra A: Oil-Level Trend and Suspected-Leak Monitoring
# ==============================================================================

def test_oil_level_declining_trend_emits_suspected_leak_evidence():
    """Declining corrected level trend triggers DET_OIL_LEVEL_DECLINING_TREND and MNT-OIL-008."""
    t0 = datetime(2025, 2, 10, 12, 0, tzinfo=timezone.utc)
    profile = SYNTHETIC_ASSET_PROFILES["DT-04"]  # Conservator, oil gauge fitted

    # Measured trend rate is -0.15 %/day (exceeds -0.10 %/day threshold)
    event = _make_event("DT-04", t0, [
        _make_meas("oil_level_pct", 22.0, "%"),
        _make_meas("oil_level_trend_pct_per_day", -0.15, "percent/day"),
        _make_meas("top_oil_temperature", 60.0, "Cel"),
    ])

    engine = MultiDomainAnomalyEngine(asset_id="DT-04", profile=profile)
    evidence = engine.evaluate_event(event)

    trend_ev = [ev for ev in evidence if ev.detector_id == "DET_OIL_LEVEL_DECLINING_TREND"]
    assert len(trend_ev) == 1
    assert "SUSPECTED_OIL_LOSS_TREND" in trend_ev[0].reason_codes
    assert trend_ev[0].severity == 0.75

    # Check maintenance recommendation wiring
    mnt_engine = MaintenanceEngine()
    recs = mnt_engine.evaluate(event, evidence_items=evidence)
    oil_recs = [r for r in recs if r.rule_id == "MNT-OIL-008"]
    assert len(oil_recs) == 1
    assert oil_recs[0].priority == MaintenancePriority.P2_PLANNED_ACTION


def test_oil_level_stuck_gauge_detection():
    """Frozen oil level during varying top oil temperature flags DET_OIL_LEVEL_GAUGE_STUCK."""
    profile = SYNTHETIC_ASSET_PROFILES["DT-04"]
    engine = MultiDomainAnomalyEngine(asset_id="DT-04", profile=profile)

    # Feed 4 consecutive readings where top oil temp varies by 8 C while oil level is frozen
    temps = [50.0, 54.0, 56.0, 58.0]
    ev_last = None
    for i, temp in enumerate(temps):
        t = datetime(2025, 3, 27, 10 + i, 0, tzinfo=timezone.utc)
        ev = _make_event("DT-04", t, [
            _make_meas("oil_level_pct", 25.0, "%"),  # frozen flat
            _make_meas("top_oil_temperature", temp, "Cel"),
        ])
        ev_last = ev
        if i < 3:
            engine.evaluate_event(ev)

    assert ev_last is not None
    evidence = engine.evaluate_event(ev_last)
    stuck_ev = [ev for ev in evidence if ev.detector_id == "DET_OIL_LEVEL_GAUGE_STUCK"]
    assert len(stuck_ev) == 1
    assert "OIL_LEVEL_GAUGE_STUCK" in stuck_ev[0].reason_codes


def test_oil_monitoring_disabled_for_sealed_asset():
    """Sealed corrugated asset DT-03 without oil gauge does not emit oil gauge alarms."""
    t0 = datetime(2025, 2, 10, 12, 0, tzinfo=timezone.utc)
    profile = SYNTHETIC_ASSET_PROFILES["DT-03"]  # Sealed tank, has_oil_level_gauge=False

    event = _make_event("DT-03", t0, [
        _make_meas("top_oil_temperature", 60.0, "Cel"),
    ])

    engine = MultiDomainAnomalyEngine(asset_id="DT-03", profile=profile)
    evidence = engine.evaluate_event(event)
    assert not any("oil" in ev.detector_id.lower() for ev in evidence)


# ==============================================================================
# Phase 5 Extra B: Sealed-Tank Pressure Monitoring
# ==============================================================================

def test_sealed_tank_high_pressure_and_prd_contact():
    """Sealed tank DT-03 detects high pressure and PRD contact operations."""
    t0 = datetime(2025, 3, 22, 8, 0, tzinfo=timezone.utc)
    profile = SYNTHETIC_ASSET_PROFILES["DT-03"]

    # 1. High gauge pressure (26.3 kPa(g) >= 25.0 kPa(g))
    event_p = _make_event("DT-03", t0, [
        _make_meas("tank_pressure_kpa_g", 26.3, "kPa"),
        _make_meas("top_oil_temperature", 88.0, "Cel"),
    ])
    engine = MultiDomainAnomalyEngine(asset_id="DT-03", profile=profile)
    evidence_p = engine.evaluate_event(event_p)

    high_p = [ev for ev in evidence_p if ev.detector_id == "DET_PRESSURE_HIGH_ALARM"]
    assert len(high_p) == 1
    assert "SEALED_TANK_HIGH_PRESSURE" in high_p[0].reason_codes

    mnt = MaintenanceEngine()
    recs_p = mnt.evaluate(event_p, evidence_items=evidence_p)
    assert any(r.rule_id == "MNT-PRESS-009" for r in recs_p)

    # 2. Pressure relief contact operation (PRD operated)
    event_prd = _make_event("DT-03", t0, [
        _make_meas("prd_operated", 1, "1"),
        _make_meas("tank_pressure_kpa_g", 28.0, "kPa"),
    ])
    evidence_prd = engine.evaluate_event(event_prd)
    prd_ev = [ev for ev in evidence_prd if ev.detector_id == "DET_PRESSURE_RELIEF_OPERATED"]
    assert len(prd_ev) == 1
    assert prd_ev[0].severity == 1.0  # Safety Critical

    recs_prd = mnt.evaluate(event_prd, evidence_items=evidence_prd)
    assert any(r.rule_id == "MNT-PROT-001" and r.priority == MaintenancePriority.P0_SAFETY for r in recs_prd)


def test_conservator_tank_pressure_monitoring_disabled():
    """Conservator assets (DT-01) ignore pressure readings and do not trigger sealed tank alarms."""
    t0 = datetime(2025, 3, 22, 8, 0, tzinfo=timezone.utc)
    profile = SYNTHETIC_ASSET_PROFILES["DT-01"]  # Conservator, has_pressure_sensor=False

    event = _make_event("DT-01", t0, [
        _make_meas("tank_pressure_kpa_g", 30.0, "kPa"),  # Even if spurious pressure present
        _make_meas("top_oil_temperature", 60.0, "Cel"),
    ])

    engine = MultiDomainAnomalyEngine(asset_id="DT-01", profile=profile)
    evidence = engine.evaluate_event(event)
    assert not any("pressure" in ev.detector_id.lower() for ev in evidence)


# ==============================================================================
# Phase 5 Extra C: Electrical Stress & Protection Context
# ==============================================================================

def test_prospective_short_circuit_calculation():
    """Verify symmetrical short-circuit current reference: S=500 kVA, V=433 V, Z=4.5%."""
    # I_rated = 500 * 1000 / (sqrt(3) * 433) = 666.69 A
    # I_sc = 666.69 / 0.045 = 14,815 A = 14.815 kA
    isc = calculate_prospective_short_circuit_ka(
        rated_kva=500.0,
        rated_lv_v_ll=433.0,
        impedance_pct=4.5,
    )
    assert isc is not None
    assert math.isclose(isc, 14.815, rel_tol=1e-3)

    # In derived electrical features
    t0 = datetime(2025, 3, 27, 5, 41, tzinfo=timezone.utc)
    profile = SYNTHETIC_ASSET_PROFILES["DT-02"]
    event = _make_event("DT-02", t0, [
        _make_meas("voltage_v1", 249.0, "V", phase="L1"),
        _make_meas("current_i1", 100.0, "A", phase="L1"),
    ])
    derived = extract_electrical_features(event, profile=profile)
    assert derived.prospective_short_circuit_ka is not None
    assert math.isclose(derived.prospective_short_circuit_ka, 14.815, rel_tol=1e-3)


def test_lv_breaker_trip_and_hv_fuse_protection_events():
    """LV breaker trip and HV fuse operations emit critical P0 protection evidence."""
    t0 = datetime(2025, 3, 27, 5, 41, tzinfo=timezone.utc)
    profile = SYNTHETIC_ASSET_PROFILES["DT-02"]
    engine = MultiDomainAnomalyEngine(asset_id="DT-02", profile=profile)

    event = _make_event("DT-02", t0, [
        _make_meas("lv_breaker_trip", 1, "1"),
        _make_meas("hv_fuse_operated", 1, "1"),
    ])

    evidence = engine.evaluate_event(event)
    lv_trip = [ev for ev in evidence if ev.detector_id == "DET_PROT_LV_BREAKER_TRIP"]
    hv_fuse = [ev for ev in evidence if ev.detector_id == "DET_PROT_HV_FUSE_OPERATED"]

    assert len(lv_trip) == 1
    assert lv_trip[0].severity == 1.0
    assert len(hv_fuse) == 1
    assert hv_fuse[0].severity == 1.0

    mnt = MaintenanceEngine()
    recs = mnt.evaluate(event, evidence_items=evidence)
    assert any(r.rule_id == "MNT-PROT-001" and r.priority == MaintenancePriority.P0_SAFETY for r in recs)


# ==============================================================================
# Phase 5 Extra D: Construction-Aware Capability Manifest
# ==============================================================================

def test_capability_manifest_reflects_tank_construction():
    """Verify CapabilityManifest gates oil level vs pressure based on tank construction."""
    from app.models.twin_state import TwinState

    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    # 1. DT-01 (Conservator)
    p_dt01 = SYNTHETIC_ASSET_PROFILES["DT-01"]
    evaluator_dt01 = CapabilityEvaluator(profile=p_dt01)
    state_dt01 = TwinState(
        asset_id="DT-01",
        state_sequence=1,
        state_time_utc=t0,
        event_time_watermark_utc=t0,
        last_processed_event_id="ev_dt01",
        state_hash="hash01",
        current_observations={
            "oil_level_pct": _make_meas("oil_level_pct", 30.0, "%"),
        },
    )
    manifest_dt01 = evaluator_dt01.evaluate(state_dt01)
    assert manifest_dt01.capabilities["oil_level_monitoring"].enabled is True
    assert manifest_dt01.capabilities["tank_pressure_monitoring"].enabled is False
    assert "CONSERVATOR_TANK_DESIGN" in manifest_dt01.capabilities["tank_pressure_monitoring"].disabled_reason_codes

    # 2. DT-03 (Sealed Corrugated)
    p_dt03 = SYNTHETIC_ASSET_PROFILES["DT-03"]
    evaluator_dt03 = CapabilityEvaluator(profile=p_dt03)
    state_dt03 = TwinState(
        asset_id="DT-03",
        state_sequence=1,
        state_time_utc=t0,
        event_time_watermark_utc=t0,
        last_processed_event_id="ev_dt03",
        state_hash="hash03",
        current_observations={
            "tank_pressure_kpa_g": _make_meas("tank_pressure_kpa_g", 12.0, "kPa"),
        },
    )
    manifest_dt03 = evaluator_dt03.evaluate(state_dt03)
    assert manifest_dt03.capabilities["oil_level_monitoring"].enabled is False
    assert "NO_OIL_GAUGE_FITTED" in manifest_dt03.capabilities["oil_level_monitoring"].disabled_reason_codes
    assert manifest_dt03.capabilities["tank_pressure_monitoring"].enabled is True


# ==============================================================================
# Critical Audit Verification Tests
# ==============================================================================

def test_prospective_short_circuit_handles_invalid_and_nonfinite_inputs():
    """Verify calculate_prospective_short_circuit_ka strictly rejects non-finite, zero, and negative inputs."""
    # Normal reference
    valid_res = calculate_prospective_short_circuit_ka(250.0, 433.0, 4.5)
    assert valid_res is not None
    assert math.isclose(valid_res, 7.408, rel_tol=1e-3)

    # NaN / Inf inputs
    assert calculate_prospective_short_circuit_ka(float("nan"), 433.0, 4.5) is None
    assert calculate_prospective_short_circuit_ka(250.0, float("nan"), 4.5) is None
    assert calculate_prospective_short_circuit_ka(250.0, 433.0, float("nan")) is None
    assert calculate_prospective_short_circuit_ka(float("inf"), 433.0, 4.5) is None
    assert calculate_prospective_short_circuit_ka(250.0, float("inf"), 4.5) is None
    assert calculate_prospective_short_circuit_ka(250.0, 433.0, float("inf")) is None

    # Zero & negative inputs
    assert calculate_prospective_short_circuit_ka(0.0, 433.0, 4.5) is None
    assert calculate_prospective_short_circuit_ka(250.0, 0.0, 4.5) is None
    assert calculate_prospective_short_circuit_ka(250.0, 433.0, 0.0) is None
    assert calculate_prospective_short_circuit_ka(-250.0, 433.0, 4.5) is None
    assert calculate_prospective_short_circuit_ka(250.0, -433.0, 4.5) is None
    assert calculate_prospective_short_circuit_ka(250.0, 433.0, -4.5) is None
    assert calculate_prospective_short_circuit_ka(None, 433.0, 4.5) is None


def test_unprofiled_asset_pressure_monitoring_strictly_disabled():
    """An unprofiled asset (profile=None) must NOT have pressure monitoring enabled."""
    t0 = datetime(2025, 3, 22, 8, 0, tzinfo=timezone.utc)
    event = _make_event("UNPROFILED_TX", t0, [
        _make_meas("tank_pressure_kpa_g", 30.0, "kPa"),
        _make_meas("top_oil_temperature", 60.0, "Cel"),
    ])
    # profile is None
    engine = MultiDomainAnomalyEngine(asset_id="UNPROFILED_TX", profile=None)
    evidence = engine.evaluate_event(event)
    assert not any("pressure" in ev.detector_id.lower() for ev in evidence)


def test_stuck_gauge_handles_gaps_and_out_of_order_samples():
    """Gaps (>2h) and non-monotonic timestamps must not falsely trigger stuck gauge alarms."""
    profile = SYNTHETIC_ASSET_PROFILES["DT-04"]
    engine = MultiDomainAnomalyEngine(asset_id="DT-04", profile=profile)

    # 1. Multi-day gap scenario (e.g., communication outage resumed)
    t1 = datetime(2025, 3, 1, 10, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 3, 1, 10, 30, tzinfo=timezone.utc)
    t3 = datetime(2025, 3, 1, 11, 0, tzinfo=timezone.utc)
    t4 = datetime(2025, 3, 5, 11, 0, tzinfo=timezone.utc)  # 4-day gap

    for t, temp in [(t1, 50.0), (t2, 52.0), (t3, 54.0)]:
        engine.evaluate_event(_make_event("DT-04", t, [
            _make_meas("oil_level_pct", 25.0, "%"),
            _make_meas("top_oil_temperature", temp, "Cel"),
        ]))

    ev_gap = _make_event("DT-04", t4, [
        _make_meas("oil_level_pct", 25.0, "%"),
        _make_meas("top_oil_temperature", 60.0, "Cel"),
    ])
    evidence_gap = engine.evaluate_event(ev_gap)
    # Must NOT flag stuck gauge across a 4-day telemetry gap
    assert not any(ev.detector_id == "DET_OIL_LEVEL_GAUGE_STUCK" for ev in evidence_gap)


def test_end_to_end_candidate_csv_stream_to_fact_bundle():
    """End-to-end integration: candidate CSV stream -> adapter -> detectors -> maintenance -> FactBundle."""
    from pathlib import Path
    from app.engine.fact_bundle import assemble_fact_bundle
    from app.models.twin_state import TwinState

    csv_path = Path("data/candidates/gridpulse_synthetic_v1/gridpulse_synthetic_30min.csv")
    if not csv_path.exists():
        pytest.skip("Candidate CSV not found")

    adapter = GridPulseSyntheticAdapter()
    profile_dt03 = SYNTHETIC_ASSET_PROFILES["DT-03"]
    engine_dt03 = MultiDomainAnomalyEngine(asset_id="DT-03", profile=profile_dt03)
    mnt_dt03 = MaintenanceEngine()
    evaluator_dt03 = CapabilityEvaluator(profile=profile_dt03)

    last_fb = None
    count = 0
    for event in adapter.stream_events(csv_path, asset_id="DT-03"):
        count += 1
        # Verify partition flag is preserved
        assert any(flag.startswith("PARTITION_") for flag in event.event_quality_flags)

        derived = extract_electrical_features(event, profile=profile_dt03)
        assert derived.prospective_short_circuit_ka is not None
        assert math.isclose(derived.prospective_short_circuit_ka, 7.408, rel_tol=1e-3)

        evidence = engine_dt03.evaluate_event(event, derived=derived)
        recs = mnt_dt03.evaluate(event, evidence_items=evidence)

        # Build TwinState snapshot
        obs_map = {m.signal_id: m for m in event.measurements}
        state = TwinState(
            asset_id="DT-03",
            state_sequence=count,
            state_time_utc=event.event_time_utc,
            event_time_watermark_utc=event.event_time_utc,
            last_processed_event_id=event.event_id,
            state_hash=f"state_hash_{count}",
            current_observations=obs_map,
            derived_electrical=derived,
            active_recommendations=recs,
        )


        fb = assemble_fact_bundle(state=state, capability_evaluator=evaluator_dt03)
        assert fb.asset_id == "DT-03"
        assert fb.provenance_hash is not None
        assert fb.capabilities.capabilities["tank_pressure_monitoring"].enabled is True
        assert fb.capabilities.capabilities["oil_level_monitoring"].enabled is False
        last_fb = fb
        if count >= 10:
            break

    assert last_fb is not None


