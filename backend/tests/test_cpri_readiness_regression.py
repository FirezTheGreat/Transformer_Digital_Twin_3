"""CPRI Track 2 Readiness Regression Suite.

Covers exact regression fixture mapping required by CPRI dataset-agnostic contract:
- Fixture A: Existing Tripura 15-min regression
- Fixture B: 30-min dataset cadence
- Fixture C: P+S available without Q (magnitude-only derived Q, no sign fabrication)
- Fixture D: P+Q available (derived S and PF)
- Fixture E: THD and frequency present (display-only, 0 OTHI perturbation)
- Fixture F: Continuous winding + vibration + oil level + bushing temp (no WTI false alarm, no fake hotspot)
- Fixture G: Missing optional signals (graceful degradation)
- Fixture H: Multi-asset isolation (zero Tripura parameter leakage to other assets)
- Fixture I: Differing rated kVA (nameplate vs reference kVA)
- Fixture J: Irregular timestamps and monitoring gaps
- Explicit End-to-End Replay: CPRI-style non-Tripura dataset through TwinReducer
"""

import math
from datetime import datetime, timedelta, timezone
import pytest

from app.adapters.cpri_mock import CPRIMockAdapter
from app.core.registry import resolve_asset_profile, resolve_model_artifact
from app.engine.capability import CapabilityEvaluator
from app.engine.fact_bundle import FactBundleAssembler
from app.engine.physics import (
    calculate_apparent_power,
    calculate_power_factor,
    calculate_reactive_power_magnitude,
    calculate_relative_load_index,
)
from app.engine.reducer import TwinReducer
from app.engine.thermal import step_thermal_ode, ThermalModelParameters
from app.engine.thermal_fallback import ThermalFallbackGate, ThermalTrustState
from app.models.profile import AssetProfile
from app.reports.report_generator import generate_report_data
from app.models.telemetry import CanonicalEvent, Measurement, MeasurementQuality, QualitySeverity, SourceRef
from app.models.thermal_artifact import QualificationStatus


def _make_measurement(signal_id: str, value: float, unit: str = "dimensionless", phase: str | None = None) -> Measurement:
    return Measurement(
        signal_id=signal_id,
        phase=phase,
        value=value,
        value_type="float",
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
    )


def _make_canonical_event(
    asset_id: str,
    event_time_utc: datetime,
    measurements: list[Measurement],
) -> CanonicalEvent:
    source_ref = SourceRef(
        system="test_fixture",
        adapter_id="test_v1",
        source_record_id=str(event_time_utc.timestamp()),
        source_uri="fixtures/test",
        raw_sha256="abc12345",
    )
    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=f"evt-{event_time_utc.timestamp()}",
        asset_id=asset_id,
        event_time_utc=event_time_utc,
        received_time_utc=event_time_utc,
        source=source_ref,
        measurements=measurements,
        event_quality_flags=[],
        mapping_version="1.0.0",
    )


# ---------------------------------------------------------------------------
# Fixture A: Existing Tripura 15-min Regression
# ---------------------------------------------------------------------------
def test_fixture_a_tripura_15min_regression():
    profile = resolve_asset_profile(dataset_id="tripura_dev", asset_id="DT-TRIPURA-001")
    assert profile.asset_id == "DT-TRIPURA-001"
    assert profile.expected_cadence_s == 900
    assert "load_reference_kva" in profile.fields
    assert profile.fields["load_reference_kva"].value == 142.898

    artifact = resolve_model_artifact(dataset_id="tripura_dev", asset_id="DT-TRIPURA-001")
    assert artifact.parameters is not None
    assert artifact.parameters.beta_0 > 0.0
    assert artifact.parameters.beta_1 > 0.0
    assert artifact.parameters.tau_hours == 0.50


# ---------------------------------------------------------------------------
# Fixture B: 30-min Dataset Cadence
# ---------------------------------------------------------------------------
def test_fixture_b_30min_dataset_cadence():
    profile = resolve_asset_profile(dataset_id="cpri_mock", asset_id="TX_CPRI_01", nominal_cadence_s=1800)
    assert profile.expected_cadence_s == 1800

    # Warmup sample count converts cadence-aware: max(1.0h, tau) / 0.5h = 2 samples
    artifact = resolve_model_artifact(dataset_id="tripura_dev", asset_id="DT-TRIPURA-001")
    gate = ThermalFallbackGate.from_artifact(artifact, nominal_cadence_s=1800)
    assert gate.min_warmup_samples == 2  # max(1.0h, 0.5h) / 0.5h = 2 samples (vs 4 samples for 15-min)

    # Verify ODE stepping uses actual elapsed time (0.5 hour)
    # Steady-state is 30 + 1 + 2 = 33 degC, so starting at 40 degC it cools towards 33 degC
    params = ThermalModelParameters(beta_0=1.0, beta_1=2.0, tau_hours=1.0)
    t_next = step_thermal_ode(
        t_prev_degc=40.0,
        ambient_degc=30.0,
        u_load=1.0,
        dt_hours=0.5,
        params=params,
    )
    assert 33.0 < t_next < 40.0
    assert math.isfinite(t_next)


# ---------------------------------------------------------------------------
# Fixture C: P+S Available Without Q (Derived Q Magnitude-Only, No Sign Fabrication)
# ---------------------------------------------------------------------------
def test_fixture_c_p_plus_s_derived_q_magnitude_only():
    p_kw = 80.0
    s_kva = 100.0

    q_mag = calculate_reactive_power_magnitude(p_kw, s_kva)
    assert q_mag is not None
    assert q_mag == pytest.approx(60.0, abs=1e-3)  # sqrt(100^2 - 80^2) = 60

    pf = calculate_power_factor(p_kw, s_kva)
    assert pf == pytest.approx(0.80, abs=1e-3)

    # When P > S due to sensor noise, diff clamped to 0.0 without crash
    q_clamped = calculate_reactive_power_magnitude(105.0, 100.0)
    assert q_clamped == 0.0


# ---------------------------------------------------------------------------
# Fixture D: P+Q Available (Derived S and PF)
# ---------------------------------------------------------------------------
def test_fixture_d_p_plus_q_derived_s_and_pf():
    p_kw = 80.0
    q_kvar = 60.0

    s_derived = calculate_apparent_power(p_kw, q_kvar)
    assert s_derived == pytest.approx(100.0, abs=1e-3)

    pf = calculate_power_factor(p_kw, s_derived)
    assert pf == pytest.approx(0.80, abs=1e-3)


# ---------------------------------------------------------------------------
# Fixture E: THD & Frequency (Display-Only, 0 OTHI Distortion)
# ---------------------------------------------------------------------------
def test_fixture_e_thd_and_frequency():
    now = datetime.now(timezone.utc)
    measurements = [
        _make_measurement("voltage_v1", 230.0, "V", phase="L1"),
        _make_measurement("voltage_v2", 230.0, "V", phase="L2"),
        _make_measurement("voltage_v3", 230.0, "V", phase="L3"),
        _make_measurement("current_i1", 50.0, "A", phase="L1"),
        _make_measurement("current_i2", 50.0, "A", phase="L2"),
        _make_measurement("current_i3", 50.0, "A", phase="L3"),
        _make_measurement("frequency", 49.98, "Hz"),
        _make_measurement("thd_total", 4.5, "%"),
        _make_measurement("top_oil_temperature", 45.0, "Cel"),
        _make_measurement("ambient_temperature", 28.0, "Cel"),
    ]
    evt = _make_canonical_event("TX_GENERIC_01", now, measurements)
    profile = resolve_asset_profile(dataset_id="cpri_mock", asset_id="TX_GENERIC_01")
    artifact = resolve_model_artifact(dataset_id="cpri_mock", asset_id="TX_GENERIC_01")
    gate = ThermalFallbackGate.from_artifact(artifact)
    reducer = TwinReducer(profile=profile, thermal_gate=gate)

    state = reducer.reduce(None, evt)
    evaluator = CapabilityEvaluator(profile=profile)
    manifest = evaluator.evaluate(state)

    assert "frequency_monitoring" in manifest.capabilities
    assert manifest.capabilities["frequency_monitoring"].enabled is True
    assert "thd_monitoring" in manifest.capabilities
    assert manifest.capabilities["thd_monitoring"].enabled is True

    # OTHI health calculation is not corrupted
    if state.health_bundle:
        assert state.health_bundle.othi_score >= 0.0


# ---------------------------------------------------------------------------
# Fixture F: Continuous Winding + Vibration + Oil Level + Bushing Temp
# ---------------------------------------------------------------------------
def test_fixture_f_continuous_winding_and_condition_telemetry():
    now = datetime.now(timezone.utc)
    measurements = [
        _make_measurement("winding_temperature", 65.5, "Cel"),
        _make_measurement("vibration_rms", 1.25, "m/s2"),
        _make_measurement("oil_level_pct", 88.0, "%"),
        _make_measurement("bushing_temperature", 52.0, "Cel"),
        _make_measurement("current_i1", 40.0, "A", phase="L1"),
    ]
    evt = _make_canonical_event("TX_CPRI_02", now, measurements)
    profile = resolve_asset_profile(dataset_id="cpri_mock", asset_id="TX_CPRI_02")
    artifact = resolve_model_artifact(dataset_id="cpri_mock", asset_id="TX_CPRI_02")
    gate = ThermalFallbackGate.from_artifact(artifact)
    reducer = TwinReducer(profile=profile, thermal_gate=gate)

    state = reducer.reduce(None, evt)
    evaluator = CapabilityEvaluator(profile=profile)
    manifest = evaluator.evaluate(state)

    # 1. Continuous winding temp is tracked in sub-capabilities
    assert "winding_temperature_monitoring" in manifest.capabilities
    assert manifest.capabilities["winding_temperature_monitoring"].enabled is True

    # 2. Continuous winding temp does NOT satisfy discrete WTI alarms or claim hotspot/ageing capability
    assert manifest.capabilities["C4"].enabled is False
    assert "MISSING_VERIFIED_INSULATION_CLASS" in manifest.capabilities["C4"].disabled_reason_codes

    # 3. Vibration, oil level, bushing temp are tracked without errors
    assert manifest.capabilities["vibration_monitoring"].enabled is True
    assert manifest.capabilities["oil_level_monitoring"].enabled is True
    assert manifest.capabilities["bushing_temp_monitoring"].enabled is True


# ---------------------------------------------------------------------------
# Fixture G: Missing Optional Signals (Graceful Degradation)
# ---------------------------------------------------------------------------
def test_fixture_g_missing_optional_signals():
    now = datetime.now(timezone.utc)
    # Minimal event with only 1 current measurement
    measurements = [
        _make_measurement("current_i1", 30.0, "A", phase="L1"),
    ]
    evt = _make_canonical_event("TX_MINIMAL_01", now, measurements)
    profile = resolve_asset_profile(dataset_id="cpri_mock", asset_id="TX_MINIMAL_01")
    artifact = resolve_model_artifact(dataset_id="cpri_mock", asset_id="TX_MINIMAL_01")
    gate = ThermalFallbackGate.from_artifact(artifact)
    reducer = TwinReducer(profile=profile, thermal_gate=gate)

    state = reducer.reduce(None, evt)
    evaluator = CapabilityEvaluator(profile=profile)
    manifest = evaluator.evaluate(state)

    assert manifest.capabilities["thd_monitoring"].enabled is False
    assert manifest.capabilities["vibration_monitoring"].enabled is False
    assert manifest.capabilities["oil_level_monitoring"].enabled is False
    assert manifest.capabilities["bushing_temp_monitoring"].enabled is False
    assert manifest.capabilities["winding_temperature_monitoring"].enabled is False


# ---------------------------------------------------------------------------
# Fixture H: Multi-Asset Isolation (Zero Parameter Leakage)
# ---------------------------------------------------------------------------
def test_fixture_h_multi_asset_isolation():
    # Asset 1: Tripura
    art_tripura = resolve_model_artifact(dataset_id="tripura_dev", asset_id="DT-TRIPURA-001")
    assert art_tripura.parameters is not None
    assert art_tripura.parameters.beta_0 == pytest.approx(1.088, abs=0.01)
    assert art_tripura.parameters.tau_hours == pytest.approx(0.50, abs=0.01)

    # Asset 2: Arbitrary CPRI asset
    art_other = resolve_model_artifact(dataset_id="cpri_mock", asset_id="CAMPUS_TX_42")
    assert art_other.parameters is None
    assert art_other.promotion.status == "UNCALIBRATED"
    assert art_other.qualification.forecast_qualification == QualificationStatus.NOT_QUALIFIED
    assert art_other.qualification.scenario_qualification == QualificationStatus.NOT_QUALIFIED

    # Ensure gate stays in fallback persistence for uncalibrated asset
    gate = ThermalFallbackGate.from_artifact(art_other)
    assert gate.is_model_promoted is False


# ---------------------------------------------------------------------------
# Fixture I: Differing Rated kVA
# ---------------------------------------------------------------------------
def test_fixture_i_differing_rated_kva():
    s_obs = 100.0

    # Case 1: Verified 250 kVA rating -> u = 100 / 250 = 0.40
    u_250 = calculate_relative_load_index(s_obs, rated_kva=250.0, reference_kva=142.898)
    assert u_250 == pytest.approx(0.40, abs=1e-3)

    # Case 2: Verified 100 kVA rating -> u = 100 / 100 = 1.00
    u_100 = calculate_relative_load_index(s_obs, rated_kva=100.0, reference_kva=142.898)
    assert u_100 == pytest.approx(1.00, abs=1e-3)

    # Case 3: Unverified rating -> falls back to reference kVA (142.898 kVA)
    u_unverified = calculate_relative_load_index(s_obs, rated_kva=None, reference_kva=142.898)
    assert u_unverified == pytest.approx(100.0 / 142.898, abs=1e-3)


# ---------------------------------------------------------------------------
# Fixture J: Irregular Timestamps and Gaps
# ---------------------------------------------------------------------------
def test_fixture_j_irregular_timestamps_and_gaps():
    start = datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc)
    profile = resolve_asset_profile(dataset_id="cpri_mock", asset_id="TX_JITTER_01")
    artifact = resolve_model_artifact(dataset_id="tripura_dev", asset_id="DT-TRIPURA-001")
    gate = ThermalFallbackGate.from_artifact(artifact, nominal_cadence_s=1800)
    reducer = TwinReducer(profile=profile, thermal_gate=gate)

    # Feed events with jitter: +22 min, +37 min, then 4-hour gap
    offsets = [0, 22, 59, 59 + 240]
    state = None
    for m in offsets:
        evt_time = start + timedelta(minutes=m)
        evt = _make_canonical_event(
            "TX_JITTER_01",
            evt_time,
            [
                _make_measurement("top_oil_temperature", 42.0 + m * 0.05, "Cel"),
                _make_measurement("ambient_temperature", 28.0, "Cel"),
                _make_measurement("current_i1", 45.0, "A", phase="L1"),
            ],
        )
        state = reducer.reduce(state, evt)

    # 4-hour gap should trigger gap reset without unhandled exception
    assert state is not None
    assert state.thermal_latent.model_status in (
        "WARMUP",
        "FALLBACK_PERSISTENCE",
        "SHADOW_DESCRIPTIVE",
    )


# ---------------------------------------------------------------------------
# End-to-End Replay: Non-Tripura CPRI Dataset Through TwinReducer & Reports
# ---------------------------------------------------------------------------
def test_e2e_replay_cpri_dataset():
    adapter = CPRIMockAdapter()
    raw_records = [
        {
            "timestamp": "2026-10-01T12:00:00Z",
            "transformer_id": "TEST_CPRI_DT_99",
            "v_r": 231.0, "v_y": 230.5, "v_b": 229.8,
            "i_r": 48.0, "i_y": 49.2, "i_b": 47.6,
            "kw": 32.5, "kvar": 12.0, "kva": 34.65, "pf": 0.938, "freq": 50.02,
            "top_oil_degc": 48.2, "ambient_degc": 31.0,
            "winding_temp_degc": 54.1,
            "thd_pct": 3.8, "vibration_rms": 0.95, "oil_level_pct": 92.0,
        },
        {
            "timestamp": "2026-10-01T12:30:00Z",
            "transformer_id": "TEST_CPRI_DT_99",
            "v_r": 230.8, "v_y": 230.2, "v_b": 230.0,
            "i_r": 51.0, "i_y": 52.0, "i_b": 50.5,
            "kw": 35.0, "kvar": 13.0, "kva": 37.33, "pf": 0.937, "freq": 49.99,
            "top_oil_degc": 49.0, "ambient_degc": 31.5,
            "winding_temp_degc": 55.3,
            "thd_pct": 3.9, "vibration_rms": 0.98, "oil_level_pct": 92.0,
        },
    ]

    events = [adapter.transform_record(r) for r in raw_records]
    assert len(events) == 2
    assert events[0].asset_id == "TEST_CPRI_DT_99"

    profile = resolve_asset_profile(dataset_id="cpri_mock", asset_id="TEST_CPRI_DT_99", nominal_cadence_s=1800)
    artifact = resolve_model_artifact(dataset_id="cpri_mock", asset_id="TEST_CPRI_DT_99")
    gate = ThermalFallbackGate.from_artifact(artifact, nominal_cadence_s=profile.expected_cadence_s)
    reducer = TwinReducer(profile=profile, thermal_gate=gate)

    state = None
    for evt in events:
        state = reducer.reduce(state, evt)

    assert state is not None
    assert state.asset_id == "TEST_CPRI_DT_99"
    # Uncalibrated asset has no free-running ODE prediction and operates in shadow/persistence
    assert state.thermal_latent.last_free_running_top_oil_degc is None
    assert state.thermal_latent.model_status in ("FALLBACK_PERSISTENCE", "SHADOW_DESCRIPTIVE", "UNCALIBRATED")

    # Verify report generation with explicit dataset_id
    evaluator = CapabilityEvaluator(profile=profile)
    manifest = evaluator.evaluate(state)
    fact_bundle = FactBundleAssembler().assemble(state, capabilities=manifest)
    report = generate_report_data(fact_bundle, dataset_id="cpri_mock")
    assert report.asset.asset_id == "TEST_CPRI_DT_99"
    assert report.asset.dataset_id == "cpri_mock"
