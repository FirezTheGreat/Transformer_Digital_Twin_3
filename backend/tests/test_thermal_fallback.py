"""Unit and Integration Tests for Phase 4.3 Runtime Residual & Thermal Fallback Gate."""

from datetime import datetime, timezone, timedelta
import pytest
from pathlib import Path

from app.engine.thermal import ThermalModelParameters
from app.engine.thermal_fallback import (
    CUSUMDirection,
    CUSUMTracker,
    ThermalFallbackGate,
    ThermalFallbackReason,
    ThermalTrustState,
)
from app.models.anomaly import AnomalyCategory
from app.models.telemetry import Measurement, MeasurementQuality, QualitySeverity
from app.models.thermal_artifact import CalibratedThermalModelArtifact


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_params() -> ThermalModelParameters:
    return ThermalModelParameters(beta_0=1.0880, beta_1=2.8979, tau_hours=0.50)


@pytest.fixture
def default_gate(default_params) -> ThermalFallbackGate:
    return ThermalFallbackGate(
        asset_id="test_dt_01",
        params=default_params,
        load_driver_type="rms_current_a",
        load_driver_reference=150.0,
        is_model_promoted=True,
        conformal_half_width_1step=2.9945,
        calibration_residual_median=0.20,
        calibration_residual_mad=0.96,
        cusum_decision_limit_h=4.50,
        max_gap_hours=1.0,
        min_warmup_samples=4,
    )


# ---------------------------------------------------------------------------
# 1. CUSUM Unit Tests
# ---------------------------------------------------------------------------

def test_cusum_zero_floor_clamping():
    """Verify CUSUM accumulators do not cross zero floor into wrong sign."""
    tracker = CUSUMTracker(reference_k=0.50, decision_limit_h=4.50, calibration_median=0.0, calibration_mad=1.0)

    # Negative residual on positive accumulator should clamp at 0
    res = tracker.update(residual_degc=-2.0)
    assert res.cusum_pos == 0.0
    assert res.cusum_neg < 0.0

    # Positive residual on negative accumulator should clamp at 0
    tracker.reset()
    res = tracker.update(residual_degc=2.0)
    assert res.cusum_pos > 0.0
    assert res.cusum_neg == 0.0


def test_cusum_positive_drift_escalation():
    """Verify persistent positive residuals accumulate and trip alarm at h."""
    tracker = CUSUMTracker(reference_k=0.50, decision_limit_h=4.0, calibration_median=0.0, calibration_mad=1.0)

    # Standardized residual z = 2.0 / (1.4826 * 1.0) = 1.349
    # Each step adds (1.349 - 0.50) = 0.849 to cusum_pos
    alarm_fired = False
    for i in range(10):
        res = tracker.update(residual_degc=2.0)
        if res.is_positive_alarm:
            alarm_fired = True
            assert res.direction == CUSUMDirection.POSITIVE_SHIFT
            assert res.alarm_active is True
            break

    assert alarm_fired is True


def test_cusum_negative_drift_escalation():
    """Verify persistent negative residuals accumulate and trip negative alarm."""
    tracker = CUSUMTracker(reference_k=0.50, decision_limit_h=4.0, calibration_median=0.0, calibration_mad=1.0)

    alarm_fired = False
    for i in range(10):
        res = tracker.update(residual_degc=-2.5)
        if res.is_negative_alarm:
            alarm_fired = True
            assert res.direction == CUSUMDirection.NEGATIVE_SHIFT
            assert res.alarm_active is True
            break

    assert alarm_fired is True


def test_cusum_warmup_and_fallback_suppression():
    """Verify CUSUM does not accumulate during warm-up or fallback."""
    tracker = CUSUMTracker(reference_k=0.50, decision_limit_h=4.0)

    # Warm-up step
    res_warm = tracker.update(residual_degc=5.0, is_warmup=True)
    assert res_warm.cusum_pos == 0.0
    assert res_warm.alarm_active is False

    # Fallback step
    res_fall = tracker.update(residual_degc=5.0, is_fallback=True)
    assert res_fall.cusum_pos == 0.0
    assert res_fall.alarm_active is False


# ---------------------------------------------------------------------------
# 2. Thermal Runtime Evaluator & Warm-up Tests
# ---------------------------------------------------------------------------

def test_warmup_progression_and_state_transitions(default_gate):
    """Verify warm-up period decrements and transitions to MODEL_HEALTHY."""
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Step 1: Initial state initialization (warm-up sample 1 of 4)
    out1 = default_gate.evaluate_step(
        event_time_utc=t0,
        top_oil_obs=45.0,
        ambient_obs=25.0,
        load_obs=100.0,
    )
    assert out1.trust_state == ThermalTrustState.WARMUP
    assert out1.is_warmup is True
    assert out1.what_if_enabled is False
    assert out1.free_running_top_oil_degc == 45.0
    assert out1.warmup_samples_remaining == 3

    # Steps 2-4: Remaining warm-up samples
    for i in range(1, 4):
        t_step = t0 + timedelta(minutes=15 * i)
        out = default_gate.evaluate_step(
            event_time_utc=t_step,
            top_oil_obs=45.2,
            ambient_obs=25.0,
            load_obs=100.0,
        )
        assert out.trust_state == ThermalTrustState.WARMUP
        assert out.is_warmup is True

    # Step 5: Warm-up complete -> MODEL_HEALTHY
    t_ready = t0 + timedelta(minutes=15 * 4)
    out_ready = default_gate.evaluate_step(
        event_time_utc=t_ready,
        top_oil_obs=45.5,
        ambient_obs=25.0,
        load_obs=100.0,
    )
    assert out_ready.trust_state == ThermalTrustState.MODEL_HEALTHY
    assert out_ready.is_warmup is False
    assert out_ready.what_if_enabled is True
    assert out_ready.warmup_samples_remaining == 0


def test_free_running_ode_continuity_without_resets(default_gate):
    """Verify ODE steps continuously from prior free-running state rather than resetting to observed OTI."""
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Step 1: Init at 40.0 C
    default_gate.evaluate_step(t0, top_oil_obs=40.0, ambient_obs=25.0, load_obs=150.0)

    # Step 2: Observed top-oil has an artificial spike to 60.0 C, but physics ODE should advance smoothly
    t1 = t0 + timedelta(minutes=15)
    out2 = default_gate.evaluate_step(t1, top_oil_obs=60.0, ambient_obs=25.0, load_obs=150.0)

    # Steady state for 25 + 1.088 + 2.8979*(1.0)^2 = 28.98 C
    # Free-running ODE should transition toward 28.98 C, NOT jump to 60.0 C
    assert out2.free_running_top_oil_degc < 45.0
    assert out2.thermal_residual_degc > 15.0  # Big residual accurately tracked


# ---------------------------------------------------------------------------
# 3. Fallback Protection Gate Triggers
# ---------------------------------------------------------------------------

def test_fallback_on_unpromoted_model(default_params):
    """Verify fallback gate activates when model is unpromoted."""
    unpromoted_gate = ThermalFallbackGate(
        asset_id="test_unpromoted",
        params=default_params,
        is_model_promoted=False,
    )
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    out = unpromoted_gate.evaluate_step(t0, top_oil_obs=45.0, ambient_obs=25.0, load_obs=100.0)

    assert out.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE
    assert out.is_fallback_active is True
    assert ThermalFallbackReason.UNPROMOTED_MODEL in out.fallback_reasons
    assert out.what_if_enabled is False
    assert out.expected_top_oil_degc == 45.0  # Persistence fallback


def test_fallback_on_missing_or_bad_telemetry(default_gate):
    """Verify missing or BAD telemetry triggers appropriate fallback reasons."""
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Missing ambient temperature
    out_no_amb = default_gate.evaluate_step(t0, top_oil_obs=45.0, ambient_obs=None, load_obs=100.0)
    assert out_no_amb.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE
    assert ThermalFallbackReason.MISSING_AMBIENT in out_no_amb.fallback_reasons

    # BAD quality measurement
    bad_m = Measurement(
        signal_id="top_oil_temperature",
        value=45.0,
        value_type="float",
        unit_ucum="Cel",
        original_name="OTI",
        original_value="45.0",
        original_unit="degC",
        quality=MeasurementQuality(severity=QualitySeverity.BAD, flags=["OUT_OF_RANGE"]),
    )
    out_bad = default_gate.evaluate_step(t0, top_oil_obs=bad_m, ambient_obs=25.0, load_obs=100.0)
    assert out_bad.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE
    assert ThermalFallbackReason.MISSING_TOP_OIL in out_bad.fallback_reasons


def test_fallback_on_physical_impossibility(default_gate):
    """Verify physically impossible top-oil (e.g. 15 C colder than ambient) triggers fallback and evidence."""
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    # Ambient 35.0 C, Top-oil 15.0 C (delta -20 C)
    out = default_gate.evaluate_step(t0, top_oil_obs=15.0, ambient_obs=35.0, load_obs=100.0)

    assert out.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE
    assert ThermalFallbackReason.PHYSICAL_IMPOSSIBILITY in out.fallback_reasons
    assert len(out.emitted_evidence) == 1
    ev = out.emitted_evidence[0]
    assert ev.category == AnomalyCategory.SENSOR_PLAUSIBILITY
    assert "TOP_OIL_TEMPERATURE_PHYSICALLY_IMPOSSIBLE" in ev.reason_codes


# ---------------------------------------------------------------------------
# 4. Long Gap Handling & Reversibility
# ---------------------------------------------------------------------------

def test_long_gap_sequence_termination_and_reinitialization(default_gate):
    """Verify gaps > max_gap_hours terminate residual sequence and restart warm-up."""
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # 5 normal steps to exit warm-up
    for i in range(5):
        t_step = t0 + timedelta(minutes=15 * i)
        default_gate.evaluate_step(t_step, top_oil_obs=45.0, ambient_obs=25.0, load_obs=100.0)

    # Now create a 3-hour gap
    t_gap = t0 + timedelta(hours=4)
    out_gap = default_gate.evaluate_step(t_gap, top_oil_obs=50.0, ambient_obs=25.0, load_obs=100.0)

    assert ThermalFallbackReason.MONITORING_GAP_EXCEEDED in out_gap.fallback_reasons
    assert out_gap.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE

    # Next regular step resumes into WARMUP
    t_resume = t_gap + timedelta(minutes=15)
    out_resume = default_gate.evaluate_step(t_resume, top_oil_obs=50.2, ambient_obs=25.0, load_obs=100.0)
    assert out_resume.trust_state == ThermalTrustState.WARMUP
    assert out_resume.is_warmup is True
    assert out_resume.warmup_samples_remaining == default_gate.min_warmup_samples - 1


# ---------------------------------------------------------------------------
# 5. Anomaly Evidence & CUSUM Alarm Generation
# ---------------------------------------------------------------------------

def test_cusum_alarm_generates_structured_evidence(default_gate):
    """Verify sustained positive thermal bias triggers CUSUM alarm and emits structured EvidenceItem."""
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # 4 warmup steps
    for i in range(4):
        t_step = t0 + timedelta(minutes=15 * i)
        default_gate.evaluate_step(t_step, top_oil_obs=40.0, ambient_obs=25.0, load_obs=100.0)

    # Induce large sustained positive residual for 10 steps
    evidence_emitted = None
    for i in range(4, 15):
        t_step = t0 + timedelta(minutes=15 * i)
        out = default_gate.evaluate_step(t_step, top_oil_obs=65.0, ambient_obs=25.0, load_obs=50.0)
        if out.cusum_alarm_active:
            assert len(out.emitted_evidence) >= 1
            evidence_emitted = out.emitted_evidence[0]
            break

    assert evidence_emitted is not None
    assert evidence_emitted.category == AnomalyCategory.THERMAL_DEVIATION
    assert evidence_emitted.detector_id == "thermal_cusum_drift"
    assert evidence_emitted.direction == "POSITIVE_SHIFT"
    assert "CUSUM_RESIDUAL_DRIFT_DETECTED" in evidence_emitted.reason_codes
    assert "POSSIBLE_COOLING_DEGRADATION" in evidence_emitted.hypothesis_codes
    assert "MODEL_MISSPECIFICATION_POSSIBLE" in evidence_emitted.hypothesis_codes


# ---------------------------------------------------------------------------
# 6. Artifact Construction & Determinism
# ---------------------------------------------------------------------------

def test_gate_instantiation_from_calibrated_artifact(tmp_path):
    """Verify gate initializes properly from CalibratedThermalModelArtifact contract."""
    artifact_path = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "calibrated_thermal_model.json"
    if not artifact_path.exists():
        pytest.skip("Calibrated thermal model artifact not present on disk.")

    artifact = CalibratedThermalModelArtifact.load_json(artifact_path)
    gate = ThermalFallbackGate.from_artifact(artifact, is_model_promoted_override=True)

    assert gate.asset_id == artifact.asset_id
    assert gate.params.beta_0 == pytest.approx(artifact.parameters.beta_0, abs=1e-4)
    assert gate.params.beta_1 == pytest.approx(artifact.parameters.beta_1, abs=1e-4)
    assert gate.params.tau_hours == pytest.approx(artifact.parameters.tau_hours, abs=1e-4)
    assert gate.load_driver_type == artifact.selected_load_driver


def test_deterministic_execution_replay(default_params):
    """Verify exact identical outputs across two separate gate runs on identical input streams."""
    gate1 = ThermalFallbackGate("dt_01", default_params, min_warmup_samples=4)
    gate2 = ThermalFallbackGate("dt_01", default_params, min_warmup_samples=4)

    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    inputs = [
        (t0 + timedelta(minutes=15 * i), 40.0 + 0.2 * i, 25.0 + 0.1 * i, 100.0 + 2.0 * i)
        for i in range(10)
    ]

    outputs1 = [gate1.evaluate_step(*inp) for inp in inputs]
    outputs2 = [gate2.evaluate_step(*inp) for inp in inputs]

    for o1, o2 in zip(outputs1, outputs2):
        assert o1.trust_state == o2.trust_state
        assert o1.expected_top_oil_degc == o2.expected_top_oil_degc
        assert o1.thermal_residual_degc == o2.thermal_residual_degc
        assert o1.cusum_pos == o2.cusum_pos
        assert o1.cusum_neg == o2.cusum_neg
        assert o1.cusum_alarm_active == o2.cusum_alarm_active
