"""Unit and Integration Tests for Phase 4.4 2-Hour What-If Scenario Projection Engine."""

import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from app.engine.thermal import ThermalModelParameters
from app.engine.thermal_fallback import ThermalTrustState
from app.engine.scenario_simulator import (
    DEFAULT_CONFORMAL_HALF_WIDTHS_DEGC,
    EXTRAPOLATION_LOAD_INDEX_THRESHOLD,
    EXTRAPOLATION_UNCERTAINTY_MULTIPLIER,
    ScenarioSimulator,
)
from app.models.scenario import ScenarioRequest, ScenarioProjectionResult
from app.models.thermal_artifact import CalibratedThermalModelArtifact
from app.models.twin_state import TwinState, ThermalLatentState
from app.models.features import DerivedFeatures
from app.models.telemetry import Measurement, MeasurementQuality, QualitySeverity


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_params() -> ThermalModelParameters:
    return ThermalModelParameters(beta_0=1.0880, beta_1=2.8979, tau_hours=0.50)


@pytest.fixture
def default_simulator(default_params) -> ScenarioSimulator:
    return ScenarioSimulator(
        asset_id="test_transformer_01",
        params=default_params,
        load_driver_reference=150.0,
        load_driver_type="rms_current_a",
        is_model_promoted=True,
    )


# ---------------------------------------------------------------------------
# 1. 2-Hour Trajectory Projection Tests (8 x 15-minute steps)
# ---------------------------------------------------------------------------

def test_valid_2hour_projection_step_structure(default_simulator):
    """Verify projection produces exactly 8 x 15-min steps spanning 15m to 120m."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    req = ScenarioRequest(target_load_u=0.80, target_ambient_degc=30.0)

    res = default_simulator.run_projection(
        origin_time_utc=t0,
        origin_top_oil_degc=45.0,
        origin_ambient_degc=25.0,
        origin_load_value=100.0,
        trust_state=ThermalTrustState.MODEL_HEALTHY,
        scenario_request=req,
    )

    assert res.is_enabled is True
    assert res.disabled_reason is None
    assert len(res.trajectory) == 8

    # Verify each step
    for i, step in enumerate(res.trajectory):
        h = i + 1
        expected_min = h * 15
        expected_time = t0 + timedelta(minutes=expected_min)

        assert step.horizon_step == h
        assert step.horizon_minutes == expected_min
        assert step.projected_time_utc == expected_time
        assert step.conformal_lower_degc < step.projected_top_oil_degc < step.conformal_upper_degc
        assert step.conformal_half_width_degc == DEFAULT_CONFORMAL_HALF_WIDTHS_DEGC[i]


def test_monotonic_approach_to_scenario_steady_state(default_simulator):
    """Verify step trajectory approaches theoretical steady-state theta* monotonically."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    # Origin top-oil 40 C, Scenario: Ambient 30 C, u=1.0 -> theta* = 30 + 1.088 + 2.8979*(1)^2 = 33.9859 C
    # Since origin (40 C) > theta* (33.99 C), temperatures should decrease monotonically toward theta*
    req = ScenarioRequest(target_load_u=1.0, target_ambient_degc=30.0)

    res = default_simulator.run_projection(
        origin_time_utc=t0,
        origin_top_oil_degc=40.0,
        origin_ambient_degc=30.0,
        origin_load_value=150.0,
        scenario_request=req,
    )

    theta_star = 30.0 + 1.0880 + 2.8979 * (1.0**2)
    assert res.asymptotic_steady_state_degc == pytest.approx(theta_star, abs=1e-3)

    temps = [step.projected_top_oil_degc for step in res.trajectory]
    for i in range(len(temps) - 1):
        assert temps[i] > temps[i + 1]  # Monotonically cooling toward steady state

    # At 2 hours (4 x tau for tau=0.5h), state should be within ~2% of steady state
    assert temps[-1] == pytest.approx(theta_star, abs=0.20)


# ---------------------------------------------------------------------------
# 2. Scenario Multiplier and Delta Inputs
# ---------------------------------------------------------------------------

def test_load_multiplier_and_ambient_delta(default_simulator):
    """Verify relative load multiplier (+20%) and ambient delta (+5 C) apply correctly."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    # Origin: Ambient 25 C, Load 75 A -> u = 75/150 = 0.50
    # Request: load_multiplier=1.20 -> scenario u = 0.60; ambient_delta=+5.0 -> scenario amb = 30.0 C
    req = ScenarioRequest(load_multiplier=1.20, ambient_delta_degc=5.0)

    res = default_simulator.run_projection(
        origin_time_utc=t0,
        origin_top_oil_degc=35.0,
        origin_ambient_degc=25.0,
        origin_load_value=75.0,
        scenario_request=req,
    )

    assert res.scenario_ambient_degc == 30.0
    assert res.scenario_load_u == pytest.approx(0.60, abs=1e-4)
    assert res.origin_load_u == pytest.approx(0.50, abs=1e-4)

    # Baseline trajectory should simulate under (25 C, u=0.50), what-if under (30 C, u=0.60)
    for step in res.trajectory:
        assert step.projected_top_oil_degc > step.baseline_top_oil_degc
        assert step.scenario_delta_degc == pytest.approx(
            step.projected_top_oil_degc - step.baseline_top_oil_degc, abs=1e-3
        )


# ---------------------------------------------------------------------------
# 3. Threshold Crossing Detection & Duration Above Threshold
# ---------------------------------------------------------------------------

def test_threshold_crossing_and_time_above_threshold(default_simulator):
    """Verify detection of warning and critical threshold crossings and time above threshold."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    # Origin: 48.0 C, Target ambient 45.0 C, Target load u=1.80
    # theta* = 45.0 + 1.088 + 2.8979*(1.8^2) = 55.48 C
    # Warning limit: 50.0 C, Critical limit: 52.0 C
    req = ScenarioRequest(
        target_load_u=1.80,
        target_ambient_degc=45.0,
        warning_threshold_degc=50.0,
        critical_threshold_degc=52.0,
    )

    res = default_simulator.run_projection(
        origin_time_utc=t0,
        origin_top_oil_degc=48.0,
        origin_ambient_degc=30.0,
        origin_load_value=150.0,
        scenario_request=req,
    )

    assert res.earliest_warning_crossing_minutes is not None
    assert res.earliest_critical_crossing_minutes is not None
    assert res.earliest_warning_crossing_minutes <= res.earliest_critical_crossing_minutes
    assert res.time_above_warning_minutes > 0
    assert res.time_above_critical_minutes > 0
    assert res.time_above_warning_minutes >= res.time_above_critical_minutes


def test_no_threshold_crossings_when_below_limits(default_simulator):
    """Verify crossing times are null and duration is 0 when limits are never crossed."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    req = ScenarioRequest(
        target_load_u=0.50,
        target_ambient_degc=25.0,
        warning_threshold_degc=85.0,
        critical_threshold_degc=95.0,
    )

    res = default_simulator.run_projection(
        origin_time_utc=t0,
        origin_top_oil_degc=40.0,
        origin_ambient_degc=25.0,
        origin_load_value=75.0,
        scenario_request=req,
    )

    assert res.earliest_warning_crossing_minutes is None
    assert res.earliest_critical_crossing_minutes is None
    assert res.time_above_warning_minutes == 0
    assert res.time_above_critical_minutes == 0


# ---------------------------------------------------------------------------
# 4. Extrapolation Handling & Uncertainty Widening (FR-THERM-013)
# ---------------------------------------------------------------------------

def test_extrapolation_detection_and_uncertainty_widening(default_simulator):
    """Verify scenarios outside calibrated domain set extrapolation flag and widen conformal band."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    # Requested load index u=1.50 > 1.20
    req = ScenarioRequest(target_load_u=1.50, target_ambient_degc=25.0)

    res = default_simulator.run_projection(
        origin_time_utc=t0,
        origin_top_oil_degc=45.0,
        origin_ambient_degc=25.0,
        origin_load_value=150.0,
        scenario_request=req,
    )

    assert res.is_extrapolated is True
    assert res.extrapolation_warning is not None
    assert "exceeds calibrated reference domain" in res.extrapolation_warning

    # Check that conformal half-widths are widened by 1.25x
    for i, step in enumerate(res.trajectory):
        expected_w = DEFAULT_CONFORMAL_HALF_WIDTHS_DEGC[i] * EXTRAPOLATION_UNCERTAINTY_MULTIPLIER
        assert step.conformal_half_width_degc == pytest.approx(expected_w, abs=1e-4)


# ---------------------------------------------------------------------------
# 5. Capability Trust State & Fallback Gating
# ---------------------------------------------------------------------------

def test_gating_disabled_in_warmup_state(default_simulator):
    """Verify scenario projection is disabled when thermal model is in WARMUP."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    res = default_simulator.run_projection(
        origin_time_utc=t0,
        origin_top_oil_degc=45.0,
        origin_ambient_degc=25.0,
        origin_load_value=100.0,
        trust_state=ThermalTrustState.WARMUP,
    )

    assert res.is_enabled is False
    assert "warmup phase" in res.disabled_reason
    assert len(res.trajectory) == 0


def test_gating_disabled_in_fallback_persistence_state(default_simulator):
    """Verify scenario projection is disabled when thermal model is in FALLBACK_PERSISTENCE."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    res = default_simulator.run_projection(
        origin_time_utc=t0,
        origin_top_oil_degc=45.0,
        origin_ambient_degc=25.0,
        origin_load_value=100.0,
        trust_state=ThermalTrustState.FALLBACK_PERSISTENCE,
    )

    assert res.is_enabled is False
    assert "fallback persistence mode" in res.disabled_reason
    assert len(res.trajectory) == 0


def test_gating_disabled_on_missing_origin_telemetry(default_simulator):
    """Verify scenario projection is disabled if origin telemetry is missing."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    res = default_simulator.run_projection(
        origin_time_utc=t0,
        origin_top_oil_degc=None,
        origin_ambient_degc=25.0,
        origin_load_value=100.0,
    )

    assert res.is_enabled is False
    assert "missing valid origin telemetry" in res.disabled_reason


# ---------------------------------------------------------------------------
# 6. TwinState Integration & Artifact Construction
# ---------------------------------------------------------------------------

def test_run_projection_from_twin_state(default_params):
    """Verify execution directly from a valid TwinState object."""
    simulator = ScenarioSimulator(
        asset_id="dt_twin_01",
        params=default_params,
        load_driver_reference=150.0,
        is_model_promoted=True,
    )

    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    twin_state = TwinState(
        asset_id="dt_twin_01",
        state_time_utc=t0,
        last_processed_event_id="evt_01",
        event_time_watermark_utc=t0,
        state_sequence=10,
        current_observations={
            "top_oil_temperature": Measurement(
                signal_id="top_oil_temperature",
                value=48.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="48.0",
                original_unit="degC",
            ),
            "ambient_temperature": Measurement(
                signal_id="ambient_temperature",
                value=26.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="ATI",
                original_value="26.0",
                original_unit="degC",
            ),
        },
        derived_electrical=DerivedFeatures(
            timestamp_utc=t0,
            relative_load_index=0.75,
        ),
        thermal_latent=ThermalLatentState(
            model_status="PROMOTED",
            warmup_samples_remaining=0,
        ),
        state_hash="dummy_hash",
    )

    req = ScenarioRequest(target_load_u=0.90)
    res = simulator.run_projection_from_twin_state(twin_state, req)

    assert res.is_enabled is True
    assert res.origin_top_oil_degc == 48.0
    assert res.origin_ambient_degc == 26.0
    assert res.origin_load_u == 0.75
    assert res.scenario_load_u == 0.90
    assert len(res.trajectory) == 8


def test_from_artifact_and_execution_speed():
    """Verify fast (< 5ms) deterministic execution when constructed from artifact."""
    artifact_path = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "calibrated_thermal_model.json"
    if not artifact_path.exists():
        pytest.skip("Calibrated thermal model artifact not present on disk.")

    artifact = CalibratedThermalModelArtifact.load_json(artifact_path)
    sim = ScenarioSimulator.from_artifact(artifact, is_model_promoted_override=True)

    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    req = ScenarioRequest(target_load_u=0.85, target_ambient_degc=32.0)

    # Benchmark execution time
    start = time.perf_counter()
    res = sim.run_projection(
        origin_time_utc=t0,
        origin_top_oil_degc=46.5,
        origin_ambient_degc=28.0,
        origin_load_value=120.0,
        scenario_request=req,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert res.is_enabled is True
    assert len(res.trajectory) == 8
    assert elapsed_ms < 5.0  # Fast deterministic scenario projection
