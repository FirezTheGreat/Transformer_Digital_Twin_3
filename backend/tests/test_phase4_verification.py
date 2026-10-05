"""Phase 4.5 — Phase 4 Verification & Thermal Model Checkpoint Suite.

Comprehensive deterministic verification of the complete Phase 4 thermal pipeline:
1. First-Order Grey-Box Thermal ODE Engine (app.engine.thermal)
2. Calibration Artifact Integrity & Lockbox Promotion (app.models.thermal_artifact)
3. Runtime Residual, 2-Sided CUSUM & Thermal Fallback Gate (app.engine.thermal_fallback)
4. 2-Hour What-If Scenario Projection Engine (app.engine.scenario_simulator)
5. End-to-End Deterministic Integration: Event -> Reducer -> Capability -> Fallback -> Scenario
"""

from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import pytest
import time

from app.engine.capability import CapabilityEvaluator
from app.engine.physics import extract_electrical_features
from app.engine.reducer import TwinReducer
from app.engine.scenario_simulator import ScenarioSimulator
from app.engine.thermal import (
    ThermalModelParameters,
    analytical_top_oil_solution,
    calculate_steady_state_temp,
    calculate_thermal_residual,
    simulate_thermal_trajectory,
    step_thermal_ode,
)
from app.engine.thermal_fallback import (
    CUSUMDirection,
    ThermalFallbackGate,
    ThermalFallbackReason,
    ThermalRuntimeOutput,
)
from app.models.capability import CapabilityTier
from app.models.profile import AssetProfile, InsulationClass, ProfileVerificationStatus
from app.models.scenario import ScenarioRequest, ScenarioProjectionResult, ThermalTrustState
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)
from app.models.thermal_artifact import CalibratedThermalModelArtifact
from app.models.twin_state import TwinState


# ==============================================================================
# FIXTURES & HELPERS
# ==============================================================================

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
    i_l1: float | None = None,
    i_l2: float | None = None,
    i_l3: float | None = None,
    v_l1: float | None = None,
    v_l2: float | None = None,
    v_l3: float | None = None,
    p_kw: float | None = None,
    q_kvar: float | None = None,
    s_kva: float | None = None,
    pf: float | None = None,
    oti_severity: QualitySeverity = QualitySeverity.GOOD,
) -> CanonicalEvent:
    measurements: list[Measurement] = []
    if oti is not None:
        measurements.append(_make_meas("top_oil_temperature", oti, "Cel", severity=oti_severity))
    if ati is not None:
        measurements.append(_make_meas("ambient_temperature", ati, "Cel"))
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
    if p_kw is not None:
        measurements.append(_make_meas("active_power", p_kw, "kW"))
    if q_kvar is not None:
        measurements.append(_make_meas("reactive_power", q_kvar, "kvar"))
    if s_kva is not None:
        measurements.append(_make_meas("apparent_power", s_kva, "kVA"))
    if pf is not None:
        measurements.append(_make_meas("power_factor", pf, "1"))

    if not measurements:
        measurements.append(_make_meas("heartbeat", 1, "1"))

    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=event_id,
        asset_id=asset_id,
        event_time_utc=event_time,
        source=SourceRef(
            system="SYNTH",
            adapter_id="VERIF",
            source_record_id=f"row_{event_id}",
            source_uri="memory://test",
            raw_sha256="0" * 64,
        ),
        measurements=measurements,
        mapping_version="tripura-map-1.0.0",
    )


@pytest.fixture
def calibrated_artifact_path() -> Path:
    p = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "calibrated_thermal_model.json"
    assert p.exists(), f"Calibrated model artifact not found at {p}"
    return p


@pytest.fixture
def loaded_artifact(calibrated_artifact_path: Path) -> CalibratedThermalModelArtifact:
    return CalibratedThermalModelArtifact.load_json(calibrated_artifact_path)


@pytest.fixture
def default_profile() -> AssetProfile:
    return AssetProfile(
        asset_id="DT-001",
        rated_kva=100.0,
        rated_voltage_hv_v=11000.0,
        rated_voltage_lv_v=230.0,
        cooling_class="ONAN",
        insulation_paper_class=InsulationClass.THERMALLY_UPGRADED,
        profile_status=ProfileVerificationStatus.VERIFIED,
    )


# ==============================================================================
# SECTION 1: FIRST-ORDER GREY-BOX ODE ENGINE
# ==============================================================================

def test_verif_thermal_ode_analytical_equivalence():
    """Verify that discrete stepping matches closed-form analytical solution to machine precision."""
    params = ThermalModelParameters(beta_0=1.0880, beta_1=2.8979, tau_hours=0.5000)
    t_init = 40.0
    t_ambient = 30.0
    u = 0.85
    dt_hours = 0.25  # 15 minutes

    # Analytical steady-state
    theta_star = calculate_steady_state_temp(t_ambient, u, params)
    analytical_result = analytical_top_oil_solution(t_init, t_ambient, u, dt_hours, params)

    # Numerical solver
    numerical_result = step_thermal_ode(
        t_prev_degc=t_init,
        ambient_degc=t_ambient,
        u_load=u,
        dt_hours=dt_hours,
        params=params,
    )

    assert abs(numerical_result - analytical_result) < 1e-12
    assert numerical_result < t_init  # Cooling down towards theta_star
    assert numerical_result > theta_star


def test_verif_thermal_ode_step_invariance_and_determinism():
    """Verify that composing irregular dt steps equals direct analytical propagation."""
    params = ThermalModelParameters(beta_0=1.5, beta_1=3.5, tau_hours=1.2)
    t_init = 25.0
    t_amb = 32.0
    u = 1.10

    # Direct 1-hour step
    t_1hr = step_thermal_ode(t_init, t_amb, u, 1.0, params)

    # 4 irregular steps: 0.1h + 0.4h + 0.2h + 0.3h = 1.0h
    t_step = t_init
    for dt in [0.1, 0.4, 0.2, 0.3]:
        t_step = step_thermal_ode(t_step, t_amb, u, dt, params)

    assert abs(t_1hr - t_step) < 1e-11


def test_verif_thermal_ode_invalid_input_rejection():
    """Verify that parameter bounds and invalid numerical inputs raise ValueError."""
    # Negative beta_0
    with pytest.raises(ValueError, match="beta_0 must be non-negative"):
        ThermalModelParameters(beta_0=-0.01, beta_1=2.0, tau_hours=1.0)

    # Negative beta_1
    with pytest.raises(ValueError, match="beta_1 must be non-negative"):
        ThermalModelParameters(beta_0=1.0, beta_1=-0.01, tau_hours=1.0)

    # Zero or negative tau
    with pytest.raises(ValueError, match="tau_hours must be strictly positive"):
        ThermalModelParameters(beta_0=1.0, beta_1=2.0, tau_hours=0.0)

    # Negative dt
    params = ThermalModelParameters(beta_0=1.0, beta_1=2.0, tau_hours=1.0)
    with pytest.raises(ValueError, match="dt_hours must be non-negative"):
        step_thermal_ode(40.0, 30.0, 1.0, -0.1, params)


def test_verif_thermal_residual_calculation():
    """Verify residual calculation adheres to exact sign convention: observed - expected."""
    # Positive residual: observed hotter than expected
    res_pos = calculate_thermal_residual(observed_top_oil_degc=55.0, expected_top_oil_degc=50.0)
    assert res_pos == 5.0

    # Negative residual: observed cooler than expected
    res_neg = calculate_thermal_residual(observed_top_oil_degc=48.0, expected_top_oil_degc=50.0)
    assert res_neg == -2.0

    # None handling
    assert calculate_thermal_residual(observed_top_oil_degc=None, expected_top_oil_degc=50.0) is None
    assert calculate_thermal_residual(observed_top_oil_degc=50.0, expected_top_oil_degc=None) is None


# ==============================================================================
# SECTION 2: CALIBRATION ARTIFACT & PROMOTION INTEGRITY
# ==============================================================================

def test_verif_calibration_artifact_schema_and_metadata(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that the frozen calibration artifact satisfies all schema & lockbox requirements."""
    # 1. Model version & identity
    assert loaded_artifact.schema_version == "1.2.0"
    assert loaded_artifact.model_version == "greybox_v1_0"

    # 2. Dataset provenance
    assert loaded_artifact.selected_load_driver == "rms_current_a"
    assert loaded_artifact.load_driver_reference_value == pytest.approx(153.865, rel=1e-3)
    assert "tripura_fit_sha256" in loaded_artifact.dataset_hashes
    assert "tripura_calibration_sha256" in loaded_artifact.dataset_hashes
    assert "tripura_test_sha256" in loaded_artifact.dataset_hashes

    # 3. Parameters are non-negative and positive tau
    assert loaded_artifact.parameters.beta_0 >= 0.0
    assert loaded_artifact.parameters.beta_1 >= 0.0
    assert loaded_artifact.parameters.tau_hours > 0.0

    # 4. Multi-step test metrics demonstrate outperformance over persistence
    assert loaded_artifact.promotion.passes_mae_criterion is True
    assert loaded_artifact.promotion.mae_improvement_pct >= 5.0  # Required >= 5% (observed 18.59%)

    # 5. Marginal conformal coverage on TEST is within the [80%, 98%] nominal band
    assert loaded_artifact.promotion.passes_coverage_criterion is True
    assert loaded_artifact.promotion.passes_scenario_criterion is True

    # 6. Conformal path quantiles cover all 8 horizons with half-widths >= 0.50 C
    assert len(loaded_artifact.conformal_uncertainty.horizon_half_widths_degc) == 8
    for w in loaded_artifact.conformal_uncertainty.horizon_half_widths_degc:
        assert w >= 0.50


# ==============================================================================
# SECTION 3: RUNTIME RESIDUAL, CUSUM & FALLBACK GATE
# ==============================================================================

def test_verif_fallback_unpromoted_model_trip(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that an unpromoted model artifact immediately trips fallback gate."""
    # Load directly without promotion override
    gate = ThermalFallbackGate.from_artifact(loaded_artifact, is_model_promoted_override=False)
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    out = gate.evaluate_step(
        event_time_utc=t0,
        top_oil_obs=45.0,
        ambient_obs=28.0,
        load_obs=100.0,
    )
    assert out.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE
    assert out.is_fallback_active is True
    assert ThermalFallbackReason.UNPROMOTED_MODEL in out.fallback_reasons
    assert out.what_if_enabled is False


def test_verif_fallback_warmup_progression(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify deterministic warm-up progression: WARMUP for W samples then MODEL_HEALTHY."""
    gate = ThermalFallbackGate.from_artifact(loaded_artifact, is_model_promoted_override=True)
    assert gate.min_warmup_samples == max(4, math.ceil(loaded_artifact.parameters.tau_hours / 0.25))

    start_time = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # First W samples: initialization & warmup
    for i in range(1, gate.min_warmup_samples + 1):
        t = start_time + timedelta(minutes=15 * (i - 1))
        out = gate.evaluate_step(
            event_time_utc=t,
            top_oil_obs=45.0,
            ambient_obs=28.0,
            load_obs=100.0,
        )
        assert out.trust_state == ThermalTrustState.WARMUP
        assert out.is_warmup is True
        assert out.what_if_enabled is False

    # Post-warmup sample (sample W + 1): MODEL_HEALTHY
    t_post = start_time + timedelta(minutes=15 * gate.min_warmup_samples)
    out_healthy = gate.evaluate_step(
        event_time_utc=t_post,
        top_oil_obs=45.0,
        ambient_obs=28.0,
        load_obs=100.0,
    )
    assert out_healthy.trust_state == ThermalTrustState.MODEL_HEALTHY
    assert out_healthy.is_warmup is False
    assert out_healthy.what_if_enabled is True


def test_verif_fallback_long_gap_reset(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that a time gap > 1.0 hour forces a sequence termination and warm-up reset."""
    gate = ThermalFallbackGate.from_artifact(loaded_artifact, is_model_promoted_override=True)
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Bring to MODEL_HEALTHY (5 samples)
    for i in range(5):
        gate.evaluate_step(
            event_time_utc=t0 + timedelta(minutes=15 * i),
            top_oil_obs=42.0,
            ambient_obs=30.0,
            load_obs=100.0,
        )
    assert gate.warmup_samples_remaining == 0

    # Sudden 2-hour gap: trips to FALLBACK_PERSISTENCE with MONITORING_GAP_EXCEEDED on the gap step
    t_after_gap = t0 + timedelta(minutes=60 + 120)
    out_gap = gate.evaluate_step(
        event_time_utc=t_after_gap,
        top_oil_obs=44.0,
        ambient_obs=30.0,
        load_obs=100.0,
    )

    assert out_gap.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE
    assert ThermalFallbackReason.MONITORING_GAP_EXCEEDED in out_gap.fallback_reasons

    # Next regular step (15 min after gap): resumes into WARMUP
    t_resume = t_after_gap + timedelta(minutes=15)
    out_resume = gate.evaluate_step(
        event_time_utc=t_resume,
        top_oil_obs=44.0,
        ambient_obs=30.0,
        load_obs=100.0,
    )
    assert out_resume.trust_state == ThermalTrustState.WARMUP
    assert out_resume.is_warmup is True


def test_verif_fallback_telemetry_corruption_immediate_trip(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that corrupted/missing/physically impossible telemetry immediately trips hard fallback."""
    gate = ThermalFallbackGate.from_artifact(loaded_artifact, is_model_promoted_override=True)
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Bring to operational (5 samples)
    for i in range(5):
        gate.evaluate_step(
            event_time_utc=t0 + timedelta(minutes=15 * i),
            top_oil_obs=42.0,
            ambient_obs=30.0,
            load_obs=100.0,
        )

    # 1. Missing Top-Oil Temperature
    t1 = t0 + timedelta(minutes=75)
    out_no_oti = gate.evaluate_step(
        event_time_utc=t1,
        top_oil_obs=None,
        ambient_obs=30.0,
        load_obs=100.0,
    )
    assert out_no_oti.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE
    assert out_no_oti.is_fallback_active is True
    assert ThermalFallbackReason.MISSING_TOP_OIL in out_no_oti.fallback_reasons

    # Reset
    gate.reset()
    for i in range(5):
        gate.evaluate_step(
            event_time_utc=t0 + timedelta(minutes=15 * i),
            top_oil_obs=42.0,
            ambient_obs=30.0,
            load_obs=100.0,
        )

    # 2. Physical Impossibility: T_oil < T_ambient - 10 deg C
    t2 = t0 + timedelta(minutes=75)
    out_phys = gate.evaluate_step(
        event_time_utc=t2,
        top_oil_obs=20.0,
        ambient_obs=35.0,
        load_obs=80.0,
    )
    assert out_phys.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE
    assert ThermalFallbackReason.PHYSICAL_IMPOSSIBILITY in out_phys.fallback_reasons


def test_verif_fallback_cusum_drift_escalation(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that sustained positive thermal bias escalates CUSUM accumulator and emits evidence."""
    gate = ThermalFallbackGate.from_artifact(loaded_artifact, is_model_promoted_override=True)
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Complete warm-up (5 samples)
    for i in range(5):
        gate.evaluate_step(
            event_time_utc=t0 + timedelta(minutes=15 * i),
            top_oil_obs=35.0,
            ambient_obs=30.0,
            load_obs=80.0,
        )

    # Inject persistent +12 C thermal bias over 10 consecutive samples
    alarm_fired = False
    evidence_generated = False
    for i in range(5, 15):
        t = t0 + timedelta(minutes=15 * i)
        # Model expects ~35 C, actual is 48 C (+13 C residual)
        out = gate.evaluate_step(
            event_time_utc=t,
            top_oil_obs=48.0,
            ambient_obs=30.0,
            load_obs=80.0,
        )
        if out.cusum_alarm_active:
            alarm_fired = True
            assert out.cusum_direction == CUSUMDirection.POSITIVE_SHIFT
        if len(out.emitted_evidence) > 0:
            evidence_generated = True

    assert alarm_fired, "CUSUM positive drift failed to fire alarm"
    assert evidence_generated, "CUSUM drift alarm failed to generate structured evidence"


# ==============================================================================
# SECTION 4: 2-HOUR WHAT-IF SCENARIO PROJECTION ENGINE
# ==============================================================================

def test_verif_scenario_projection_exact_horizons(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that scenario simulator produces exactly 8 x 15-min horizons with correct step intervals."""
    simulator = ScenarioSimulator.from_artifact(loaded_artifact, is_model_promoted_override=True)
    origin_time = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    request = ScenarioRequest(
        load_multiplier=1.20,
        ambient_delta_degc=3.0,
    )

    result = simulator.run_projection(
        origin_time_utc=origin_time,
        origin_top_oil_degc=55.0,
        origin_ambient_degc=32.0,
        origin_load_value=115.0,
        trust_state=ThermalTrustState.MODEL_HEALTHY,
        scenario_request=request,
    )

    assert result.is_enabled is True
    assert len(result.trajectory) == 8

    # Verify time steps: 15, 30, 45, 60, 75, 90, 105, 120 minutes
    expected_times = [15, 30, 45, 60, 75, 90, 105, 120]
    for step, exp_min in zip(result.trajectory, expected_times):
        assert step.horizon_step == exp_min // 15
        assert step.horizon_minutes == exp_min
        assert step.projected_time_utc == origin_time + timedelta(minutes=exp_min)
        assert step.projected_top_oil_degc > 0.0
        assert step.projected_rise_over_ambient_degc > 0.0
        assert step.conformal_lower_degc <= step.projected_top_oil_degc <= step.conformal_upper_degc


def test_verif_scenario_open_loop_no_future_oti_feedback(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that what-if projection is strictly open-loop from origin state without future OTI."""
    simulator = ScenarioSimulator.from_artifact(loaded_artifact, is_model_promoted_override=True)
    origin_time = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    # Initial state
    t_oil_0 = 45.0
    t_amb_0 = 30.0
    load_0 = loaded_artifact.load_driver_reference_value * 0.50  # u_0 = 0.50

    # Step change in scenario to load_multiplier = 2.0 (u = 1.0)
    request = ScenarioRequest(load_multiplier=2.0)
    result = simulator.run_projection(
        origin_time_utc=origin_time,
        origin_top_oil_degc=t_oil_0,
        origin_ambient_degc=t_amb_0,
        origin_load_value=load_0,
        trust_state=ThermalTrustState.MODEL_HEALTHY,
        scenario_request=request,
    )

    # Manually compute open-loop trajectory using step_thermal_ode
    u_scen = 1.0
    expected_traj = []
    current_t = t_oil_0
    params = ThermalModelParameters(
        beta_0=loaded_artifact.parameters.beta_0,
        beta_1=loaded_artifact.parameters.beta_1,
        tau_hours=loaded_artifact.parameters.tau_hours,
    )
    for _ in range(8):
        current_t = step_thermal_ode(current_t, t_amb_0, u_scen, 0.25, params)
        expected_traj.append(current_t)

    actual_traj = [step.projected_top_oil_degc for step in result.trajectory]
    for act, exp in zip(actual_traj, expected_traj):
        assert abs(act - exp) < 1e-3


def test_verif_scenario_extrapolation_and_threshold_crossing(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify extrapolation widening and threshold-crossing detection."""
    simulator = ScenarioSimulator.from_artifact(loaded_artifact, is_model_promoted_override=True)
    origin_time = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    # Overloaded scenario with heatwave: u = 1.44 (> 1.20 threshold), ambient +20 C => theta* = 62.1 C
    request = ScenarioRequest(
        target_load_u=1.44,
        ambient_delta_degc=20.0,
        warning_threshold_degc=50.0,
        critical_threshold_degc=60.0,
    )
    result = simulator.run_projection(
        origin_time_utc=origin_time,
        origin_top_oil_degc=45.0,
        origin_ambient_degc=35.0,
        origin_load_value=120.0,
        trust_state=ThermalTrustState.MODEL_HEALTHY,
        scenario_request=request,
    )

    assert result.is_enabled is True
    assert result.is_extrapolated is True
    assert result.extrapolation_warning is not None

    # Uncertainty half-width should be widened by 1.25x
    base_w1 = loaded_artifact.conformal_uncertainty.horizon_half_widths_degc[0]
    actual_w1 = result.trajectory[0].conformal_half_width_degc
    assert actual_w1 == pytest.approx(base_w1 * 1.25, rel=1e-3)

    # Threshold crossings should be detected (warming up towards 62.1 C)
    assert result.peak_projected_top_oil_degc is not None
    assert result.peak_projected_top_oil_degc > 50.0
    assert result.time_above_warning_minutes > 0


def test_verif_scenario_gating_disabled_under_fallback(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that what-if projection is disabled when thermal model is in WARMUP or FALLBACK."""
    simulator = ScenarioSimulator.from_artifact(loaded_artifact, is_model_promoted_override=True)
    origin_time = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    # 1. WARMUP
    res_warmup = simulator.run_projection(
        origin_time_utc=origin_time,
        origin_top_oil_degc=50.0,
        origin_ambient_degc=30.0,
        origin_load_value=100.0,
        scenario_request=ScenarioRequest(load_multiplier=1.1),
        trust_state=ThermalTrustState.WARMUP,
    )
    assert res_warmup.is_enabled is False
    assert len(res_warmup.trajectory) == 0
    assert "warmup" in res_warmup.disabled_reason.lower()

    # 2. FALLBACK_PERSISTENCE
    res_fallback = simulator.run_projection(
        origin_time_utc=origin_time,
        origin_top_oil_degc=50.0,
        origin_ambient_degc=30.0,
        origin_load_value=100.0,
        scenario_request=ScenarioRequest(load_multiplier=1.1),
        trust_state=ThermalTrustState.FALLBACK_PERSISTENCE,
    )
    assert res_fallback.is_enabled is False
    assert len(res_fallback.trajectory) == 0
    assert "fallback" in res_fallback.disabled_reason.lower()


# ==============================================================================
# SECTION 5: END-TO-END PIPELINE & CONFINEMENT INTEGRATION
# ==============================================================================

def test_verif_end_to_end_pipeline_and_capability_confinement(
    loaded_artifact: CalibratedThermalModelArtifact,
    default_profile: AssetProfile,
):
    """Verify full deterministic pipeline:
    CanonicalEvent -> TwinReducer -> CapabilityEvaluator -> ThermalFallbackGate -> ScenarioSimulator
    and assert that thermal fallback NEVER impacts electrical/data capabilities.
    """
    reducer = TwinReducer()
    cap_evaluator = CapabilityEvaluator(profile=default_profile)
    fallback_gate = ThermalFallbackGate.from_artifact(loaded_artifact, is_model_promoted_override=True)
    simulator = ScenarioSimulator.from_artifact(loaded_artifact, is_model_promoted_override=True)

    current_state: TwinState | None = None
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Sequence of 5 nominal events (0, 15, 30, 45, 60 mins)
    for i in range(5):
        event_time = t0 + timedelta(minutes=15 * i)
        event = _make_event(
            event_id=f"EVT-{i:03d}",
            event_time=event_time,
            oti=45.0 + i * 0.2,
            ati=28.0,
            i_l1=100.0,
            i_l2=101.0,
            i_l3=99.0,
            v_l1=230.0,
            v_l2=231.0,
            v_l3=229.0,
            p_kw=69.0,
            q_kvar=10.0,
            s_kva=70.0,
            pf=0.98,
        )

        # 1. Physics & Reducer
        current_state = reducer.reduce(current_state, event)

        # 2. Capability Evaluator
        cap_manifest = cap_evaluator.evaluate(current_state, event.event_time_utc)

        # 3. Fallback Gate
        top_oil_val = current_state.current_observations["top_oil_temperature"].value if "top_oil_temperature" in current_state.current_observations else None
        ambient_val = current_state.current_observations["ambient_temperature"].value if "ambient_temperature" in current_state.current_observations else None
        load_val = current_state.derived_electrical.current_mean_a if current_state.derived_electrical else None

        fb_out = fallback_gate.evaluate_step(
            event_time_utc=event.event_time_utc,
            top_oil_obs=top_oil_val,
            ambient_obs=ambient_val,
            load_obs=load_val,
        )

        # C0 and C1 must be fully ACTIVE
        assert cap_manifest.capabilities["C0"].enabled is True
        assert cap_manifest.capabilities["C1"].enabled is True
        assert cap_manifest.highest_tier in (CapabilityTier.C1_ELECTRICAL, CapabilityTier.C2_THERMAL_DESCRIPTIVE, CapabilityTier.C3_THERMAL_PREDICTIVE)

    # After 5 steps, fallback gate is MODEL_HEALTHY
    assert fb_out.trust_state == ThermalTrustState.MODEL_HEALTHY

    # 4. Run Scenario Projection from active TwinState
    scen_result = simulator.run_projection_from_twin_state(
        twin_state=current_state,
        scenario_request=ScenarioRequest(load_multiplier=1.15, ambient_delta_degc=2.0),
    )
    assert scen_result.is_enabled is True
    assert len(scen_result.trajectory) == 8
    assert scen_result.trajectory[7].projected_top_oil_degc > 0.0

    # Now simulate a sudden corrupted/missing OTI event at minute 75
    corrupt_time = t0 + timedelta(minutes=75)
    corrupt_event = _make_event(
        event_id="EVT-005",
        event_time=corrupt_time,
        oti=None,  # Missing OTI
        ati=28.0,
        i_l1=100.0,
        i_l2=101.0,
        i_l3=99.0,
        v_l1=230.0,
        v_l2=231.0,
        v_l3=229.0,
        p_kw=69.0,
        q_kvar=10.0,
        s_kva=70.0,
        pf=0.98,
    )

    current_state = reducer.reduce(current_state, corrupt_event)
    cap_manifest = cap_evaluator.evaluate(current_state, corrupt_event.event_time_utc)

    # In current_observations, "top_oil_temperature" won't be in the corrupt event
    top_oil_obs_corrupt = next((m for m in corrupt_event.measurements if m.signal_id == "top_oil_temperature"), None)
    ambient_obs_corrupt = next((m for m in corrupt_event.measurements if m.signal_id == "ambient_temperature"), None)
    load_obs_corrupt = current_state.derived_electrical.current_mean_a if current_state.derived_electrical else None

    fb_out_corrupt = fallback_gate.evaluate_step(
        event_time_utc=corrupt_event.event_time_utc,
        top_oil_obs=top_oil_obs_corrupt,
        ambient_obs=ambient_obs_corrupt,
        load_obs=load_obs_corrupt,
    )

    # Verify Fallback Gate trips to FALLBACK_PERSISTENCE
    assert fb_out_corrupt.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE

    # Verify Scenario Projection is cleanly disabled
    scen_result_corrupt = simulator.run_projection(
        origin_time_utc=corrupt_event.event_time_utc,
        origin_top_oil_degc=None,
        origin_ambient_degc=28.0,
        origin_load_value=100.0,
        trust_state=fb_out_corrupt.trust_state,
        scenario_request=ScenarioRequest(load_multiplier=1.15),
    )
    assert scen_result_corrupt.is_enabled is False
    assert "fallback" in scen_result_corrupt.disabled_reason.lower()

    # CRITICAL INVARIANT: Electrical & Data Integrity capabilities REMAIN 100% ACTIVE!
    assert cap_manifest.capabilities["C0"].enabled is True
    assert cap_manifest.capabilities["C1"].enabled is True
    assert current_state.derived_electrical.current_mean_a == pytest.approx(100.0, rel=1e-2)


def test_verif_scenario_projection_latency_performance(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that deterministic 8-step scenario projection runs well within the 5 ms budget."""
    simulator = ScenarioSimulator.from_artifact(loaded_artifact, is_model_promoted_override=True)
    origin_time = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    request = ScenarioRequest(load_multiplier=1.2, ambient_delta_degc=3.0)

    # Warm-up call
    simulator.run_projection(
        origin_time_utc=origin_time,
        origin_top_oil_degc=50.0,
        origin_ambient_degc=30.0,
        origin_load_value=120.0,
        trust_state=ThermalTrustState.MODEL_HEALTHY,
        scenario_request=request,
    )

    # Benchmark 50 consecutive runs
    n_runs = 50
    t_start = time.perf_counter()
    for _ in range(n_runs):
        res = simulator.run_projection(
            origin_time_utc=origin_time,
            origin_top_oil_degc=50.0,
            origin_ambient_degc=30.0,
            origin_load_value=120.0,
            trust_state=ThermalTrustState.MODEL_HEALTHY,
            scenario_request=request,
        )
        assert res.is_enabled is True
    t_total = time.perf_counter() - t_start
    avg_latency_ms = (t_total / n_runs) * 1000.0

    # Strict SLA: < 5 ms per projection (typically < 0.1 ms in pure Python)
    assert avg_latency_ms < 5.0, f"Scenario projection average latency was {avg_latency_ms:.3f} ms (expected < 5.0 ms)"
