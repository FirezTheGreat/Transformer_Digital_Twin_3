"""Unit and Verification Tests for Phase 4.1 First-Order Grey-Box Thermal ODE Engine."""

import math
import pytest

from app.engine.thermal import (
    ThermalModelParameters,
    calculate_steady_state_temp,
    step_thermal_ode,
    analytical_top_oil_solution,
    simulate_thermal_trajectory,
    calculate_thermal_residual,
)


@pytest.fixture
def default_params() -> ThermalModelParameters:
    """Standard verified physical parameters for distribution transformer thermal model."""
    return ThermalModelParameters(
        beta_0=10.0,      # 10.0 degC no-load rise
        beta_1=35.0,      # 35.0 degC full-load rise at u=1.0
        tau_hours=3.0,    # 3.0 hours oil thermal time constant
    )


# ---------------------------------------------------------------------------
# 1. Parameter Constraints & Validation
# ---------------------------------------------------------------------------

def test_valid_parameters():
    """Verify initialization of valid thermal model parameters."""
    p = ThermalModelParameters(beta_0=0.0, beta_1=40.0, tau_hours=2.5)
    assert p.beta_0 == 0.0
    assert p.beta_1 == 40.0
    assert p.tau_hours == 2.5


def test_parameter_bounds_negative_beta0():
    """Verify rejection of negative beta_0."""
    with pytest.raises(ValueError, match="beta_0 must be non-negative"):
        ThermalModelParameters(beta_0=-0.1, beta_1=30.0, tau_hours=3.0)


def test_parameter_bounds_negative_beta1():
    """Verify rejection of negative beta_1."""
    with pytest.raises(ValueError, match="beta_1 must be non-negative"):
        ThermalModelParameters(beta_0=10.0, beta_1=-1.0, tau_hours=3.0)


def test_parameter_bounds_zero_or_negative_tau():
    """Verify rejection of zero or negative tau."""
    with pytest.raises(ValueError, match="tau_hours must be strictly positive"):
        ThermalModelParameters(beta_0=10.0, beta_1=30.0, tau_hours=0.0)

    with pytest.raises(ValueError, match="tau_hours must be strictly positive"):
        ThermalModelParameters(beta_0=10.0, beta_1=30.0, tau_hours=-2.0)


def test_parameter_bounds_non_finite():
    """Verify rejection of NaN and Inf parameter values."""
    with pytest.raises(ValueError, match="beta_0 must be a finite float"):
        ThermalModelParameters(beta_0=float("nan"), beta_1=30.0, tau_hours=3.0)

    with pytest.raises(ValueError, match="beta_1 must be a finite float"):
        ThermalModelParameters(beta_0=10.0, beta_1=float("inf"), tau_hours=3.0)

    with pytest.raises(ValueError, match="tau_hours must be a finite float"):
        ThermalModelParameters(beta_0=10.0, beta_1=30.0, tau_hours=float("nan"))


# ---------------------------------------------------------------------------
# 2. Steady-State Asymptotic Temperature
# ---------------------------------------------------------------------------

def test_steady_state_calculation_zero_load(default_params):
    """At zero load (u=0), theta* = T_a + beta_0."""
    theta_star = calculate_steady_state_temp(ambient_degc=25.0, u_load=0.0, params=default_params)
    assert theta_star == pytest.approx(35.0, abs=1e-6)


def test_steady_state_calculation_rated_load(default_params):
    """At rated load (u=1), theta* = T_a + beta_0 + beta_1."""
    theta_star = calculate_steady_state_temp(ambient_degc=30.0, u_load=1.0, params=default_params)
    assert theta_star == pytest.approx(75.0, abs=1e-6)


def test_steady_state_calculation_squared_drive(default_params):
    """At half load (u=0.5), load rise scales with u^2 = 0.25."""
    # theta* = 20.0 + 10.0 + 35.0 * 0.25 = 38.75
    theta_star = calculate_steady_state_temp(ambient_degc=20.0, u_load=0.5, params=default_params)
    assert theta_star == pytest.approx(38.75, abs=1e-6)


def test_steady_state_invalid_inputs(default_params):
    """Verify rejection of invalid ambient or load values."""
    with pytest.raises(ValueError, match="u_load must be non-negative"):
        calculate_steady_state_temp(ambient_degc=25.0, u_load=-0.2, params=default_params)

    with pytest.raises(ValueError, match="ambient_degc must be finite"):
        calculate_steady_state_temp(ambient_degc=float("nan"), u_load=0.5, params=default_params)


# ---------------------------------------------------------------------------
# 3. Analytical Constant-Drive Response (< 0.1 degC match requirement)
# ---------------------------------------------------------------------------

def test_analytical_vs_discrete_stepping_constant_drive(default_params):
    """Verify numerical stepping matches continuous analytical solution within < 0.1 degC."""
    t_init = 40.0
    ambient = 28.0
    u_load = 0.8
    total_hours = 6.0
    dt = 0.25  # 15-minute intervals (24 steps)
    n_steps = int(total_hours / dt)

    # Compute continuous analytical ground truth at t = 6.0 hours
    analytical_final = analytical_top_oil_solution(
        t_init_degc=t_init,
        ambient_degc=ambient,
        u_load=u_load,
        t_elapsed_hours=total_hours,
        params=default_params,
    )

    # Simulate via discrete stepping
    trajectory = simulate_thermal_trajectory(
        t_init_degc=t_init,
        ambient_series=[ambient] * n_steps,
        u_load_series=[u_load] * n_steps,
        dt_series_hours=dt,
        params=default_params,
    )
    discrete_final = trajectory[-1]

    # Verify requirement: discrepancy < 0.1 degC (in fact, exact within numerical precision)
    discrepancy = abs(discrete_final - analytical_final)
    assert discrepancy < 0.1
    assert discrepancy < 1e-9


# ---------------------------------------------------------------------------
# 4. Step-Response Behavior & Time-Constant Characteristics
# ---------------------------------------------------------------------------

def test_step_response_tau_percentages(default_params):
    """Verify exponential step response characteristic at 1*tau, 3*tau, and 5*tau."""
    t_init = 30.0
    ambient = 30.0
    u_load = 1.0
    tau = default_params.tau_hours  # 3.0 hours

    # theta* = 30 + 10 + 35 = 75.0 degC
    # Total rise = 75 - 30 = 45.0 degC
    theta_star = 75.0
    total_delta = theta_star - t_init

    # At t = 1 * tau: (1 - 1/e) ~ 63.212%
    t_1tau = analytical_top_oil_solution(t_init, ambient, u_load, 1.0 * tau, default_params)
    rise_pct_1tau = (t_1tau - t_init) / total_delta
    assert rise_pct_1tau == pytest.approx(1.0 - math.exp(-1.0), abs=1e-5)
    assert abs(rise_pct_1tau - 0.63212) < 1e-3

    # At t = 3 * tau: (1 - e^-3) ~ 95.021%
    t_3tau = analytical_top_oil_solution(t_init, ambient, u_load, 3.0 * tau, default_params)
    rise_pct_3tau = (t_3tau - t_init) / total_delta
    assert rise_pct_3tau == pytest.approx(1.0 - math.exp(-3.0), abs=1e-5)
    assert abs(rise_pct_3tau - 0.95021) < 1e-3

    # At t = 5 * tau: (1 - e^-5) ~ 99.326%
    t_5tau = analytical_top_oil_solution(t_init, ambient, u_load, 5.0 * tau, default_params)
    rise_pct_5tau = (t_5tau - t_init) / total_delta
    assert rise_pct_5tau == pytest.approx(1.0 - math.exp(-5.0), abs=1e-5)
    assert abs(rise_pct_5tau - 0.99326) < 1e-3


# ---------------------------------------------------------------------------
# 5. Irregular Time Intervals & Additivity
# ---------------------------------------------------------------------------

def test_irregular_dt_trajectory_composition(default_params):
    """Verify that stepping across arbitrary partitions of time yields the exact same state."""
    t_init = 45.0
    ambient = 32.0
    u_load = 0.75

    # Irregular intervals summing to 5.0 hours
    irregular_dts = [0.1, 0.25, 0.4, 0.75, 1.5, 0.5, 0.5]
    assert sum(irregular_dts) == pytest.approx(4.0, abs=1e-9)

    # Step through irregular intervals
    trajectory = simulate_thermal_trajectory(
        t_init_degc=t_init,
        ambient_series=[ambient] * len(irregular_dts),
        u_load_series=[u_load] * len(irregular_dts),
        dt_series_hours=irregular_dts,
        params=default_params,
    )
    final_irregular = trajectory[-1]

    # Single lump step of total elapsed time (4.0 hours)
    single_step = step_thermal_ode(
        t_prev_degc=t_init,
        ambient_degc=ambient,
        u_load=u_load,
        dt_hours=sum(irregular_dts),
        params=default_params,
    )

    assert final_irregular == pytest.approx(single_step, abs=1e-10)


def test_zero_dt_no_change(default_params):
    """When dt = 0.0, the state does not change."""
    t_prev = 52.3
    t_next = step_thermal_ode(
        t_prev_degc=t_prev,
        ambient_degc=35.0,
        u_load=1.2,
        dt_hours=0.0,
        params=default_params,
    )
    assert t_next == t_prev


def test_negative_dt_rejection(default_params):
    """Rejection of negative dt."""
    with pytest.raises(ValueError, match="dt_hours must be non-negative"):
        step_thermal_ode(
            t_prev_degc=50.0,
            ambient_degc=30.0,
            u_load=1.0,
            dt_hours=-0.25,
            params=default_params,
        )


# ---------------------------------------------------------------------------
# 6. Determinism
# ---------------------------------------------------------------------------

def test_determinism(default_params):
    """Verify exact bit-for-bit repeatability across multiple runs."""
    ambients = [25.0 + i * 0.5 for i in range(20)]
    loads = [0.3 + (i % 5) * 0.2 for i in range(20)]
    dts = [0.25] * 20

    run1 = simulate_thermal_trajectory(35.0, ambients, loads, dts, default_params)
    run2 = simulate_thermal_trajectory(35.0, ambients, loads, dts, default_params)

    assert run1 == run2


# ---------------------------------------------------------------------------
# 7. Numerical Stability & Residual Calculation
# ---------------------------------------------------------------------------

def test_large_dt_asymptotic_convergence(default_params):
    """Extremely large dt smoothly converges to theta* without overflow."""
    ambient = 25.0
    u_load = 1.0
    theta_star = calculate_steady_state_temp(ambient, u_load, default_params)

    t_next = step_thermal_ode(
        t_prev_degc=20.0,
        ambient_degc=ambient,
        u_load=u_load,
        dt_hours=1000.0,  # >> tau
        params=default_params,
    )
    assert t_next == pytest.approx(theta_star, abs=1e-10)


def test_thermal_residual_calculation():
    """Verify thermal residual calculation and None handling."""
    assert calculate_thermal_residual(65.4321, 60.1234) == pytest.approx(5.3087, abs=1e-4)
    assert calculate_thermal_residual(None, 60.0) is None
    assert calculate_thermal_residual(65.0, None) is None
    assert calculate_thermal_residual(None, None) is None
    assert calculate_thermal_residual(float("nan"), 50.0) is None
    assert calculate_thermal_residual(50.0, float("inf")) is None


def test_trajectory_length_mismatch(default_params):
    """Verify rejection when trajectory series lengths do not match."""
    with pytest.raises(ValueError, match="Length mismatch"):
        simulate_thermal_trajectory(
            t_init_degc=30.0,
            ambient_series=[25.0, 26.0],
            u_load_series=[0.5],
            dt_series_hours=0.25,
            params=default_params,
        )

    with pytest.raises(ValueError, match="Length mismatch"):
        simulate_thermal_trajectory(
            t_init_degc=30.0,
            ambient_series=[25.0, 26.0],
            u_load_series=[0.5, 0.6],
            dt_series_hours=[0.25],
            params=default_params,
        )
