"""First-Order Grey-Box Differential Thermal ODE Engine.

Implements the locked first-order thermal differential model:
    theta*_k = T_{a,k} + beta_0 + beta_1 * u_k^2
    alpha_k = 1 - exp(-Delta_t_k / tau)
    T_hat_{o,k} = T_hat_{o,k-1} + alpha_k * (theta*_k - T_hat_{o,k-1})

Where:
    - beta_0 >= 0: Fitted load-independent top-oil rise over ambient (degC)
    - beta_1 >= 0: Fitted load-related top-oil rise at rated/reference load u = 1.0 (degC)
    - tau > 0: Effective oil thermal time constant (hours)
    - u_k >= 0: Dimensionless relative load index (S / S_rated or S / S_ref)
    - Delta_t_k >= 0: Elapsed time interval (hours)
    - T_{a,k}: Ambient temperature (degC)

This module provides pure mathematical functions for state simulation, single-step
transitions, analytical solutions, and input validation without performing calibration
or parameter fitting.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class ThermalModelParameters:
    """Parameters for the first-order grey-box transformer thermal model.

    Attributes:
        beta_0: Load-independent temperature rise above ambient (degC), >= 0.0.
        beta_1: Load-related temperature rise at rated load u=1.0 (degC), >= 0.0.
        tau_hours: Oil thermal time constant (hours), > 0.0.
    """
    beta_0: float
    beta_1: float
    tau_hours: float

    def __post_init__(self) -> None:
        """Validate parameter physical constraints."""
        if not math.isfinite(self.beta_0):
            raise ValueError(f"beta_0 must be a finite float, got {self.beta_0}")
        if self.beta_0 < 0.0:
            raise ValueError(f"beta_0 must be non-negative (>= 0.0), got {self.beta_0}")

        if not math.isfinite(self.beta_1):
            raise ValueError(f"beta_1 must be a finite float, got {self.beta_1}")
        if self.beta_1 < 0.0:
            raise ValueError(f"beta_1 must be non-negative (>= 0.0), got {self.beta_1}")

        if not math.isfinite(self.tau_hours):
            raise ValueError(f"tau_hours must be a finite float, got {self.tau_hours}")
        if self.tau_hours <= 0.0:
            raise ValueError(f"tau_hours must be strictly positive (> 0.0), got {self.tau_hours}")


def calculate_steady_state_temp(
    ambient_degc: float,
    u_load: float,
    params: ThermalModelParameters,
) -> float:
    """Calculate asymptotic steady-state top-oil temperature theta*.

    Formula:
        theta* = T_a + beta_0 + beta_1 * u^2

    Args:
        ambient_degc: Ambient temperature in degC.
        u_load: Dimensionless load index (>= 0.0).
        params: Validated thermal model parameters.

    Returns:
        float: Asymptotic steady-state top-oil temperature in degC.

    Raises:
        ValueError: If inputs are non-finite or load is negative.
    """
    if not math.isfinite(ambient_degc):
        raise ValueError(f"ambient_degc must be finite, got {ambient_degc}")
    if not math.isfinite(u_load):
        raise ValueError(f"u_load must be finite, got {u_load}")
    if u_load < 0.0:
        raise ValueError(f"u_load must be non-negative (>= 0.0), got {u_load}")

    return ambient_degc + params.beta_0 + params.beta_1 * (u_load * u_load)


def step_thermal_ode(
    t_prev_degc: float,
    ambient_degc: float,
    u_load: float,
    dt_hours: float,
    params: ThermalModelParameters,
) -> float:
    """Perform one discrete first-order ODE integration step for irregular dt.

    Formula:
        theta*_k = T_{a,k} + beta_0 + beta_1 * u_k^2
        alpha_k = 1 - exp(-dt / tau)
        T_hat_{o,k} = T_hat_{o,k-1} + alpha_k * (theta*_k - T_hat_{o,k-1})

    Args:
        t_prev_degc: Prior top-oil temperature estimate T_hat_{o,k-1} in degC.
        ambient_degc: Current ambient temperature T_{a,k} in degC.
        u_load: Current dimensionless load index u_k (>= 0.0).
        dt_hours: Elapsed time interval Delta_t in hours (>= 0.0).
        params: Validated thermal model parameters.

    Returns:
        float: Updated top-oil temperature estimate T_hat_{o,k} in degC.

    Raises:
        ValueError: If inputs are invalid, non-finite, or dt < 0.
    """
    if not math.isfinite(t_prev_degc):
        raise ValueError(f"t_prev_degc must be finite, got {t_prev_degc}")
    if not math.isfinite(dt_hours):
        raise ValueError(f"dt_hours must be finite, got {dt_hours}")
    if dt_hours < 0.0:
        raise ValueError(f"dt_hours must be non-negative (>= 0.0), got {dt_hours}")

    # If elapsed time is zero, state does not change
    if dt_hours == 0.0:
        return t_prev_degc

    theta_star = calculate_steady_state_temp(ambient_degc, u_load, params)

    # Compute exponential transition factor alpha
    # Use -expm1(-dt / tau) for high numerical accuracy when dt / tau is small
    alpha = -math.expm1(-dt_hours / params.tau_hours)

    # Discrete step update: T_k = T_{k-1} + alpha * (theta* - T_{k-1})
    t_next = t_prev_degc + alpha * (theta_star - t_prev_degc)
    return t_next


def analytical_top_oil_solution(
    t_init_degc: float,
    ambient_degc: float,
    u_load: float,
    t_elapsed_hours: float,
    params: ThermalModelParameters,
) -> float:
    """Calculate exact closed-form continuous analytical solution under constant drive.

    Formula:
        theta* = T_a + beta_0 + beta_1 * u^2
        T_o(t) = theta* + (T_{o,0} - theta*) * exp(-t / tau)

    Args:
        t_init_degc: Initial top-oil temperature T_{o,0} at t=0 in degC.
        ambient_degc: Constant ambient temperature in degC.
        u_load: Constant dimensionless load index (>= 0.0).
        t_elapsed_hours: Total elapsed time t in hours (>= 0.0).
        params: Validated thermal model parameters.

    Returns:
        float: Exact analytical top-oil temperature at time t in degC.

    Raises:
        ValueError: If inputs are invalid, non-finite, or elapsed time < 0.
    """
    if not math.isfinite(t_init_degc):
        raise ValueError(f"t_init_degc must be finite, got {t_init_degc}")
    if not math.isfinite(t_elapsed_hours):
        raise ValueError(f"t_elapsed_hours must be finite, got {t_elapsed_hours}")
    if t_elapsed_hours < 0.0:
        raise ValueError(f"t_elapsed_hours must be non-negative (>= 0.0), got {t_elapsed_hours}")

    if t_elapsed_hours == 0.0:
        return t_init_degc

    theta_star = calculate_steady_state_temp(ambient_degc, u_load, params)
    decay = math.exp(-t_elapsed_hours / params.tau_hours)
    return theta_star + (t_init_degc - theta_star) * decay


def simulate_thermal_trajectory(
    t_init_degc: float,
    ambient_series: Sequence[float],
    u_load_series: Sequence[float],
    dt_series_hours: Sequence[float] | float,
    params: ThermalModelParameters,
) -> list[float]:
    """Simulate top-oil temperature trajectory over a sequence of time steps.

    Args:
        t_init_degc: Initial top-oil temperature at t=0 in degC.
        ambient_series: Sequence of ambient temperatures T_{a,k} for k=1..N.
        u_load_series: Sequence of load indices u_k for k=1..N.
        dt_series_hours: Either a sequence of interval durations dt_k for k=1..N,
            or a scalar constant interval duration dt in hours.
        params: Validated thermal model parameters.

    Returns:
        list[float]: Trajectory of estimated top-oil temperatures [T_hat_{o,1}, ..., T_hat_{o,N}].

    Raises:
        ValueError: If series lengths do not match or inputs are invalid.
    """
    n_steps = len(ambient_series)
    if len(u_load_series) != n_steps:
        raise ValueError(
            f"Length mismatch: ambient_series has {n_steps} elements, "
            f"u_load_series has {len(u_load_series)} elements"
        )

    if isinstance(dt_series_hours, (int, float)):
        dts = [float(dt_series_hours)] * n_steps
    else:
        if len(dt_series_hours) != n_steps:
            raise ValueError(
                f"Length mismatch: ambient_series has {n_steps} elements, "
                f"dt_series_hours has {len(dt_series_hours)} elements"
            )
        dts = list(dt_series_hours)

    trajectory: list[float] = []
    current_temp = t_init_degc

    for k in range(n_steps):
        current_temp = step_thermal_ode(
            t_prev_degc=current_temp,
            ambient_degc=ambient_series[k],
            u_load=u_load_series[k],
            dt_hours=dts[k],
            params=params,
        )
        trajectory.append(current_temp)

    return trajectory


def calculate_thermal_residual(
    observed_top_oil_degc: float | None,
    expected_top_oil_degc: float | None,
) -> float | None:
    """Calculate raw thermal residual: observed minus expected top-oil temperature.

    Formula:
        residual = T_{o,observed} - T_{o,expected}

    Args:
        observed_top_oil_degc: Observed top-oil temperature in degC (or None).
        expected_top_oil_degc: Model-expected top-oil temperature in degC (or None).

    Returns:
        float | None: Residual in degC, or None if either input is None or non-finite.
    """
    if observed_top_oil_degc is None or expected_top_oil_degc is None:
        return None
    if not math.isfinite(observed_top_oil_degc) or not math.isfinite(expected_top_oil_degc):
        return None
    return round(observed_top_oil_degc - expected_top_oil_degc, 4)
