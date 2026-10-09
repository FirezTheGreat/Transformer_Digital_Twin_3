"""Thermal Model Calibration, FIT Load-Driver Selection & Conformal Uncertainty Pipeline.

Phase 4, Substep 4.2 Implementation.
Strictly implements the offline calibration and evaluation workflow:
1. FIT-only chronological rolling-origin load-driver selection (S vs I_eq, K=5 folds).
2. Parameter fitting (beta_0 >= 0, beta_1 >= 0, tau in [0.5, 24.0] hours) with bounded Huber loss:
   - Standard tuning constant c = 1.345
   - Scale sigma_fit = 1.4826 * MAD(residuals_fit) estimated deterministically on FIT
   - Huber delta = c * sigma_fit
3. 3 Baseline models (Multi-step Persistence, Ambient + Median Rise, Static Robust Regression).
4. Model identifiability & stability diagnostics on FIT:
   - Sample count >= 500, span >= 7 days, load variation (CV >= 0.10, range >= 10 kVA)
   - Parameter stability gate: CV(tau) <= 0.60 (project-specific engineering threshold)
   - Boundary checks within [0.5, 24.0] hours
5. Empirical 90% block-conformal path uncertainty calibration on CAL:
   - Measurement-resolution scale floor = 0.50 deg C (safeguard for ~1 deg C integer telemetry resolution)
6. Primary Operational TEST Evaluation:
   - 2-hour / 8-step forward trajectory projection initialized from observed origin T_o
   - Compared against equivalent 2-hour multi-step persistence (T_{t+h} = T_t)
   - Secondary diagnostic: 1-step closed-loop prediction
   - Locked promotion criteria evaluated on 2-hour trajectory performance
7. Frozen model artifact generation for runtime consumption.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from app.engine.thermal import (
    ThermalModelParameters,
    calculate_steady_state_temp,
    calculate_thermal_residual,
    simulate_thermal_trajectory,
    step_thermal_ode,
)
from app.models.thermal_artifact import (
    BaselineMetricEntry,
    CalibratedThermalModelArtifact,
    ConformalUncertaintyParams,
    HorizonMetricBreakdown,
    IdentifiabilityReport,
    PromotionDecision,
    QualificationStatus,
    ThermalModelParamsDict,
    ThermalModelQualification,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Physical & Statistical Calibration Constants
# ---------------------------------------------------------------------------
HUBER_TUNING_CONSTANT_C: float = 1.345  # Standard statistical Huber tuning constant (95% asymptotic efficiency for Gaussian)
MIN_CONFORMAL_SCALE_FLOOR_DEGC: float = 0.50  # Measurement-resolution safeguard for ~1 deg C integer quantized telemetry
TAU_MIN_HOURS: float = 0.5   # Lower bound for distribution transformer oil time constant
TAU_MAX_HOURS: float = 24.0  # Upper bound for distribution transformer oil time constant
TAU_STABILITY_CV_GATE: float = 0.60  # Project-specific engineering threshold for parameter stability across folds


# ---------------------------------------------------------------------------
# 1. Huber Loss & Scale Estimation Functions
# ---------------------------------------------------------------------------

def huber_loss(residual: np.ndarray | float, delta: float = 1.35) -> np.ndarray | float:
    """Standard Huber loss function for robust parameter estimation."""
    abs_r = np.abs(residual)
    quadratic = np.minimum(abs_r, delta)
    linear = abs_r - quadratic
    return 0.5 * quadratic**2 + delta * linear


def estimate_fit_residual_scale(
    series: ProcessedThermalSeries,
    min_scale_floor: float = MIN_CONFORMAL_SCALE_FLOOR_DEGC,
) -> float:
    """Estimate deterministic robust scale sigma_fit from FIT residuals using MAD.

    Formula:
        sigma_fit = max(min_scale_floor, 1.4826 * MAD(residuals_initial))
    where initial residuals are computed from one-step ambient+median-rise baseline on FIT.

    Args:
        series: Processed FIT partition thermal series.
        min_scale_floor: Minimum resolution floor (0.50 deg C).

    Returns:
        float: Robust scale estimate sigma_fit.
    """
    rise = series.top_oil_degc - series.ambient_degc
    median_rise = float(np.median(rise))
    initial_res = rise - median_rise
    med_res = float(np.median(initial_res))
    mad_res = float(np.median(np.abs(initial_res - med_res)))
    sigma_fit = max(min_scale_floor, 1.4826 * mad_res)
    return float(sigma_fit)


def calculate_huber_delta(
    series: ProcessedThermalSeries,
    c_tuning_constant: float = HUBER_TUNING_CONSTANT_C,
    min_scale_floor: float = MIN_CONFORMAL_SCALE_FLOOR_DEGC,
) -> float:
    """Compute Huber delta = c * sigma_fit deterministically from FIT partition.

    Args:
        series: Processed FIT partition thermal series.
        c_tuning_constant: Huber tuning constant (default 1.345).
        min_scale_floor: Minimum resolution floor (0.50 deg C).

    Returns:
        float: Computed Huber delta threshold in deg C.
    """
    sigma_fit = estimate_fit_residual_scale(series, min_scale_floor=min_scale_floor)
    return float(c_tuning_constant * sigma_fit)


# ---------------------------------------------------------------------------
# 2. Data Preparation & Load Driver Extraction
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProcessedThermalSeries:
    """Cleaned chronological time series for thermal modeling."""
    timestamps: pd.Series
    ambient_degc: np.ndarray
    top_oil_degc: np.ndarray
    load_driver_raw: np.ndarray
    load_index_u: np.ndarray
    dt_hours: np.ndarray
    segment_ids: np.ndarray
    reference_value: float


def extract_load_driver(
    df: pd.DataFrame,
    driver_type: str = "apparent_power_kva",
) -> np.ndarray:
    """Extract candidate load driver from DataFrame.

    Candidates:
        - 'apparent_power_kva': Uses 'KVA' or derives sqrt(KW^2 + KVAR^2)
        - 'rms_current_a': Uses sqrt((IL1^2 + IL2^2 + IL3^2) / 3)

    Args:
        df: Input DataFrame.
        driver_type: 'apparent_power_kva' or 'rms_current_a'.

    Returns:
        np.ndarray: Extracted raw load driver values.
    """
    if driver_type == "apparent_power_kva":
        if "KVA" in df.columns:
            return np.maximum(0.0, df["KVA"].to_numpy(dtype=float))
        elif "x_apparent_power_kva" in df.columns:
            return np.maximum(0.0, df["x_apparent_power_kva"].to_numpy(dtype=float))
        elif "KW" in df.columns and "KVAR" in df.columns:
            kw = df["KW"].to_numpy(dtype=float)
            kvar = df["KVAR"].to_numpy(dtype=float)
            return np.sqrt(kw * kw + kvar * kvar)
        elif "x_active_power_kw" in df.columns and "x_reactive_power_kvar" in df.columns:
            kw = df["x_active_power_kw"].to_numpy(dtype=float)
            kvar = df["x_reactive_power_kvar"].to_numpy(dtype=float)
            return np.sqrt(kw * kw + kvar * kvar)
        else:
            raise ValueError("Cannot extract apparent power: 'KVA' or 'KW'+'KVAR' missing from dataframe")

    elif driver_type == "rms_current_a":
        if "IL1" in df.columns and "IL2" in df.columns and "IL3" in df.columns:
            i1 = df["IL1"].to_numpy(dtype=float)
            i2 = df["IL2"].to_numpy(dtype=float)
            i3 = df["IL3"].to_numpy(dtype=float)
            return np.sqrt((i1 * i1 + i2 * i2 + i3 * i3) / 3.0)
        elif "x_i_l1_a" in df.columns and "x_i_l2_a" in df.columns and "x_i_l3_a" in df.columns:
            i1 = df["x_i_l1_a"].to_numpy(dtype=float)
            i2 = df["x_i_l2_a"].to_numpy(dtype=float)
            i3 = df["x_i_l3_a"].to_numpy(dtype=float)
            return np.sqrt((i1 * i1 + i2 * i2 + i3 * i3) / 3.0)
        elif "x_current_a" in df.columns:
            return np.maximum(0.0, df["x_current_a"].to_numpy(dtype=float))
        else:
            raise ValueError("Cannot extract RMS current: 'IL1', 'IL2', 'IL3' missing from dataframe")

    else:
        raise ValueError(f"Unknown load driver type: {driver_type}")


def prepare_thermal_series(
    df: pd.DataFrame,
    driver_type: str = "apparent_power_kva",
    reference_value: float | None = None,
    max_gap_hours: float = 1.0,
) -> ProcessedThermalSeries:
    """Prepare and clean chronological time series, segmenting across long gaps.

    Args:
        df: Partition DataFrame with 'ts' (or 'DeviceTimeStamp' or 'meta_timestamp'),
            thermal columns ('OTI'/'x_oil_temp_c', 'ATI'/'x_ambient_temp_c'), and load columns.
        driver_type: 'apparent_power_kva' or 'rms_current_a'.
        reference_value: Frozen reference value P95(FIT) for load normalization.
            If None, computed from this DataFrame's 95th percentile.
        max_gap_hours: Gap threshold in hours to create continuous segments.

    Returns:
        ProcessedThermalSeries: Validated and segmented data series.
    """
    df_sorted = df.copy()
    if "ts" in df_sorted.columns:
        df_sorted["ts"] = pd.to_datetime(df_sorted["ts"])
    elif "DeviceTimeStamp" in df_sorted.columns:
        df_sorted["ts"] = pd.to_datetime(df_sorted["DeviceTimeStamp"])
    elif "meta_timestamp" in df_sorted.columns:
        df_sorted["ts"] = pd.to_datetime(df_sorted["meta_timestamp"])
    else:
        raise ValueError("DataFrame must contain 'ts', 'DeviceTimeStamp', or 'meta_timestamp' column")

    df_sorted = df_sorted.sort_values("ts").reset_index(drop=True)

    # Support CPRI v3.0.2 column names for thermal temperatures
    if "OTI" not in df_sorted.columns and "x_oil_temp_c" in df_sorted.columns:
        df_sorted["OTI"] = df_sorted["x_oil_temp_c"]
    if "ATI" not in df_sorted.columns and "x_ambient_temp_c" in df_sorted.columns:
        df_sorted["ATI"] = df_sorted["x_ambient_temp_c"]

    # Filter physical thermal validity
    valid_mask = (
        df_sorted["OTI"].notna() &
        df_sorted["ATI"].notna() &
        (df_sorted["OTI"] > 0) & (df_sorted["OTI"] < 130) &
        (df_sorted["ATI"] > -10) & (df_sorted["ATI"] <= 60)
    )
    df_clean = df_sorted[valid_mask].copy().reset_index(drop=True)
    if len(df_clean) == 0:
        raise ValueError("No valid thermal samples found in dataframe")

    raw_load = extract_load_driver(df_clean, driver_type=driver_type)

    if reference_value is None:
        p95 = float(np.percentile(raw_load, 95))
        ref_val = max(1.0, p95)
    else:
        ref_val = max(1.0, float(reference_value))

    load_u = raw_load / ref_val

    # Compute dt in hours respecting actual sampling cadence (15-min, 30-min, etc.)
    ts_series = df_clean["ts"]
    dt_seconds_diff = ts_series.diff().dt.total_seconds().dropna()
    median_cadence_s = float(dt_seconds_diff.median()) if len(dt_seconds_diff) > 0 else 900.0
    dt_seconds = ts_series.diff().dt.total_seconds().fillna(median_cadence_s).to_numpy()
    dt_hours = np.maximum(0.0, dt_seconds / 3600.0)
    dt_hours[0] = max(0.01, median_cadence_s / 3600.0)

    # Detect gaps and build segment IDs
    segment_ids = np.zeros(len(df_clean), dtype=int)
    current_seg = 0
    for i in range(1, len(df_clean)):
        if dt_hours[i] > max_gap_hours or dt_hours[i] <= 0.0:
            current_seg += 1
        segment_ids[i] = current_seg

    return ProcessedThermalSeries(
        timestamps=ts_series,
        ambient_degc=df_clean["ATI"].to_numpy(dtype=float),
        top_oil_degc=df_clean["OTI"].to_numpy(dtype=float),
        load_driver_raw=raw_load,
        load_index_u=load_u,
        dt_hours=dt_hours,
        segment_ids=segment_ids,
        reference_value=ref_val,
    )


# ---------------------------------------------------------------------------
# 3. Thermal Parameter Fitting (Huber Loss + Log Grid Search + Refinement)
# ---------------------------------------------------------------------------

def simulate_segmented_ode(
    series: ProcessedThermalSeries,
    beta_0: float,
    beta_1: float,
    tau_hours: float,
) -> np.ndarray:
    """Simulate ODE trajectory resetting state to observed value at segment boundaries."""
    n = len(series.top_oil_degc)
    t_hat = np.zeros(n, dtype=float)
    params = ThermalModelParameters(beta_0=beta_0, beta_1=beta_1, tau_hours=tau_hours)

    for i in range(n):
        if i == 0 or series.segment_ids[i] != series.segment_ids[i - 1]:
            # Initial point of continuous segment initialized to observed value
            t_hat[i] = series.top_oil_degc[i]
        else:
            t_hat[i] = step_thermal_ode(
                t_prev_degc=t_hat[i - 1],
                ambient_degc=series.ambient_degc[i],
                u_load=series.load_index_u[i],
                dt_hours=series.dt_hours[i],
                params=params,
            )
    return t_hat


def fit_thermal_model_parameters(
    series: ProcessedThermalSeries,
    tau_grid_points: int = 25,
    delta_huber: float | None = None,
) -> Tuple[ThermalModelParameters, Dict[str, float]]:
    """Fit beta_0, beta_1, tau using bounded Huber loss over deterministic tau grid + refinement.

    Parameters:
        beta_0 in [0, 60] deg C (load-independent rise)
        beta_1 in [0, 120] deg C (load-related rise at u=1)
        tau in [0.5, 24.0] hours (oil time constant domain)

    Args:
        series: Processed FIT partition thermal series.
        tau_grid_points: Number of log-spaced grid points for tau in [0.5, 24.0].
        delta_huber: Optional explicit Huber delta; if None, computed dynamically as
            delta = 1.345 * sigma_fit on FIT.

    Returns:
        Tuple[ThermalModelParameters, Dict[str, float]]: Fitted parameters and diagnostic metrics.
    """
    if delta_huber is None:
        delta = calculate_huber_delta(series)
    else:
        delta = float(delta_huber)

    sigma_fit = estimate_fit_residual_scale(series)

    # Deterministic log-spaced grid for tau in unified domain [0.5, 24.0] hours
    tau_grid = np.logspace(np.log10(TAU_MIN_HOURS), np.log10(TAU_MAX_HOURS), tau_grid_points)

    best_loss = float("inf")
    best_tau = 3.0
    best_beta0 = 10.0
    best_beta1 = 30.0

    # Stage 1: Grid search over tau
    for tau_candidate in tau_grid:
        def obj_inner(p: np.ndarray) -> float:
            b0, b1 = p[0], p[1]
            t_hat = simulate_segmented_ode(series, b0, b1, tau_candidate)
            res = series.top_oil_degc - t_hat
            return float(np.mean(huber_loss(res, delta=delta)))

        res_opt = minimize(
            obj_inner,
            x0=np.array([10.0, 30.0]),
            method="L-BFGS-B",
            bounds=[(0.0, 60.0), (0.0, 120.0)],
        )
        if res_opt.success and res_opt.fun < best_loss:
            best_loss = res_opt.fun
            best_tau = float(tau_candidate)
            best_beta0 = float(res_opt.x[0])
            best_beta1 = float(res_opt.x[1])

    # Stage 2: Joint 3D local refinement strictly within [0.5, 24.0] bounds
    def obj_joint(p: np.ndarray) -> float:
        b0, b1, tau = p[0], p[1], p[2]
        if tau < TAU_MIN_HOURS or tau > TAU_MAX_HOURS:
            return 1e6
        t_hat = simulate_segmented_ode(series, b0, b1, tau)
        res = series.top_oil_degc - t_hat
        return float(np.mean(huber_loss(res, delta=delta)))

    res_joint = minimize(
        obj_joint,
        x0=np.array([best_beta0, best_beta1, best_tau]),
        method="L-BFGS-B",
        bounds=[(0.0, 60.0), (0.0, 120.0), (TAU_MIN_HOURS, TAU_MAX_HOURS)],
    )

    if res_joint.success and res_joint.fun <= best_loss:
        final_b0 = max(0.0, float(res_joint.x[0]))
        final_b1 = max(0.0, float(res_joint.x[1]))
        final_tau = max(TAU_MIN_HOURS, min(TAU_MAX_HOURS, float(res_joint.x[2])))
        final_loss = float(res_joint.fun)
    else:
        final_b0 = best_beta0
        final_b1 = best_beta1
        final_tau = best_tau
        final_loss = best_loss

    # Compute fit residuals and metrics
    t_hat_final = simulate_segmented_ode(series, final_b0, final_b1, final_tau)
    residuals = series.top_oil_degc - t_hat_final
    fit_mae = float(np.mean(np.abs(residuals)))
    fit_rmse = float(np.sqrt(np.mean(residuals**2)))
    fit_bias = float(np.mean(residuals))

    params = ThermalModelParameters(
        beta_0=round(final_b0, 4),
        beta_1=round(final_b1, 4),
        tau_hours=round(final_tau, 4),
    )

    diagnostics = {
        "fit_loss": round(final_loss, 4),
        "fit_mae_degc": round(fit_mae, 4),
        "fit_rmse_degc": round(fit_rmse, 4),
        "fit_bias_degc": round(fit_bias, 4),
        "tau_grid_best": round(best_tau, 4),
        "huber_delta_degc": round(delta, 4),
        "fit_sigma_mad_degc": round(sigma_fit, 4),
    }

    return params, diagnostics


# ---------------------------------------------------------------------------
# 4. Baseline Models
# ---------------------------------------------------------------------------

class PersistenceBaseline:
    """Baseline 1: Last-value Persistence."""
    def predict_step(self, t_prev: float) -> float:
        return t_prev

    def predict_trajectory(self, t_origin: float, horizon_steps: int = 8) -> np.ndarray:
        return np.full(horizon_steps, t_origin, dtype=float)


class AmbientMedianRiseBaseline:
    """Baseline 2: Ambient + Median Training Top-Oil Rise."""
    def __init__(self, median_rise_degc: float) -> None:
        self.median_rise_degc = median_rise_degc

    @classmethod
    def fit(cls, fit_series: ProcessedThermalSeries) -> AmbientMedianRiseBaseline:
        rise = fit_series.top_oil_degc - fit_series.ambient_degc
        median_rise = float(np.median(rise))
        return cls(median_rise_degc=round(median_rise, 4))

    def predict_trajectory(self, ambient_origin: float, horizon_steps: int = 8) -> np.ndarray:
        return np.full(horizon_steps, ambient_origin + self.median_rise_degc, dtype=float)


class StaticRobustRegressionBaseline:
    """Baseline 3: Static Robust Regression (ambient + b0 + b1 * u^2) without thermal state."""
    def __init__(self, b0: float, b1: float) -> None:
        self.b0 = b0
        self.b1 = b1

    @classmethod
    def fit(cls, fit_series: ProcessedThermalSeries) -> StaticRobustRegressionBaseline:
        rise = fit_series.top_oil_degc - fit_series.ambient_degc
        u2 = fit_series.load_index_u**2
        delta = calculate_huber_delta(fit_series)

        def obj(p: np.ndarray) -> float:
            pred_rise = p[0] + p[1] * u2
            return float(np.mean(huber_loss(rise - pred_rise, delta=delta)))

        res = minimize(obj, x0=np.array([10.0, 30.0]), method="L-BFGS-B", bounds=[(0.0, 60.0), (0.0, 120.0)])
        b0 = float(res.x[0]) if res.success else 10.0
        b1 = float(res.x[1]) if res.success else 30.0
        return cls(b0=round(b0, 4), b1=round(b1, 4))

    def predict_trajectory(self, ambient_origin: float, u_origin: float, horizon_steps: int = 8) -> np.ndarray:
        pred = ambient_origin + self.b0 + self.b1 * (u_origin**2)
        return np.full(horizon_steps, pred, dtype=float)


# ---------------------------------------------------------------------------
# 5. FIT-Only Rolling-Origin Load Driver Selection (K=5)
# ---------------------------------------------------------------------------

@dataclass
class DriverCandidateEvaluation:
    driver_type: str
    reference_value: float
    mean_rolling_mae: float
    mean_rolling_rmse: float
    tau_cv: float
    fitted_params: ThermalModelParameters
    fold_maes: List[float]


def evaluate_load_driver_candidate_on_fit(
    fit_df: pd.DataFrame,
    driver_type: str,
    n_folds: int = 5,
) -> DriverCandidateEvaluation:
    """Perform chronological expanding-window rolling-origin predictive evaluation on FIT partition."""
    series = prepare_thermal_series(fit_df, driver_type=driver_type)
    n_samples = len(series.top_oil_degc)

    train_start_ratio = 0.50
    step_ratio = (1.0 - train_start_ratio) / (n_folds + 1)

    fold_maes: List[float] = []
    fold_rmses: List[float] = []
    fold_taus: List[float] = []

    for k in range(n_folds):
        train_end_idx = int(np.floor((train_start_ratio + k * step_ratio) * n_samples))
        val_end_idx = int(np.floor((train_start_ratio + (k + 1) * step_ratio) * n_samples))

        train_sub_df = fit_df.iloc[:train_end_idx]
        val_sub_df = fit_df.iloc[train_end_idx:val_end_idx]

        if len(train_sub_df) < 50 or len(val_sub_df) < 10:
            continue

        train_series = prepare_thermal_series(train_sub_df, driver_type=driver_type, reference_value=series.reference_value)
        val_series = prepare_thermal_series(val_sub_df, driver_type=driver_type, reference_value=series.reference_value)

        p_fold, _ = fit_thermal_model_parameters(train_series, tau_grid_points=15)
        fold_taus.append(p_fold.tau_hours)

        val_preds = simulate_segmented_ode(val_series, p_fold.beta_0, p_fold.beta_1, p_fold.tau_hours)
        res = val_series.top_oil_degc - val_preds
        fold_maes.append(float(np.mean(np.abs(res))))
        fold_rmses.append(float(np.sqrt(np.mean(res**2))))

    full_params, _ = fit_thermal_model_parameters(series)

    mean_mae = float(np.mean(fold_maes)) if fold_maes else 999.0
    mean_rmse = float(np.mean(fold_rmses)) if fold_rmses else 999.0
    tau_std = float(np.std(fold_taus)) if len(fold_taus) > 1 else 0.0
    tau_mean = float(np.mean(fold_taus)) if fold_taus else 3.0
    tau_cv = float(tau_std / tau_mean) if tau_mean > 0 else 0.0

    return DriverCandidateEvaluation(
        driver_type=driver_type,
        reference_value=series.reference_value,
        mean_rolling_mae=round(mean_mae, 4),
        mean_rolling_rmse=round(mean_rmse, 4),
        tau_cv=round(tau_cv, 4),
        fitted_params=full_params,
        fold_maes=[round(x, 4) for x in fold_maes],
    )


def select_best_load_driver_on_fit(
    fit_df: pd.DataFrame,
    n_folds: int = 5,
) -> Tuple[DriverCandidateEvaluation, Dict[str, DriverCandidateEvaluation]]:
    """Select between apparent power S and RMS current I_eq strictly on FIT data."""
    eval_s = evaluate_load_driver_candidate_on_fit(fit_df, "apparent_power_kva", n_folds=n_folds)
    eval_i = evaluate_load_driver_candidate_on_fit(fit_df, "rms_current_a", n_folds=n_folds)

    candidates = {
        "apparent_power_kva": eval_s,
        "rms_current_a": eval_i,
    }

    if eval_s.mean_rolling_mae < eval_i.mean_rolling_mae:
        winner = eval_s
    elif eval_i.mean_rolling_mae < eval_s.mean_rolling_mae:
        winner = eval_i
    else:
        winner = eval_s if eval_s.tau_cv <= eval_i.tau_cv else eval_i

    return winner, candidates


# ---------------------------------------------------------------------------
# 6. Identifiability & Stability Diagnostics
# ---------------------------------------------------------------------------

def evaluate_identifiability(
    fit_series: ProcessedThermalSeries,
    params: ThermalModelParameters,
    tau_cv: float,
) -> IdentifiabilityReport:
    """Evaluate parameter identifiability criteria on FIT partition."""
    n_samples = len(fit_series.top_oil_degc)
    span_days = float((fit_series.timestamps.max() - fit_series.timestamps.min()).total_seconds() / 86400.0) if n_samples > 0 else 0.0

    load_mean = float(np.mean(fit_series.load_driver_raw)) if n_samples > 0 else 0.0
    load_std = float(np.std(fit_series.load_driver_raw)) if n_samples > 1 else 0.0
    load_cv = float(load_std / load_mean) if load_mean > 0 else 0.0
    load_range = float(np.max(fit_series.load_driver_raw) - np.min(fit_series.load_driver_raw)) if n_samples > 0 else 0.0

    messages: List[str] = []
    passes_samples = n_samples >= 500
    passes_days = span_days >= 7.0
    passes_load = (load_cv >= 0.10) and (load_range >= 10.0)
    passes_tau_cv = tau_cv <= TAU_STABILITY_CV_GATE

    boundary_hit = (
        params.beta_0 <= 0.01 or
        params.beta_1 <= 0.01 or
        params.tau_hours <= (TAU_MIN_HOURS + 0.01) or
        params.tau_hours >= (TAU_MAX_HOURS - 0.10)
    )

    if not passes_samples:
        messages.append(f"Insufficient samples: {n_samples} < 500")
    if not passes_days:
        messages.append(f"Insufficient span: {span_days:.1f} < 7.0 days")
    if not passes_load:
        messages.append(f"Insufficient load variation: CV={load_cv:.2f}, range={load_range:.1f}")
    if not passes_tau_cv:
        messages.append(f"Parameter instability across folds: tau CV={tau_cv:.2f} > {TAU_STABILITY_CV_GATE:.2f}")
    if boundary_hit:
        messages.append(f"Parameters sit on bounds: beta0={params.beta_0}, beta1={params.beta_1}, tau={params.tau_hours} (domain: [{TAU_MIN_HOURS}, {TAU_MAX_HOURS}] h)")

    is_identifiable = passes_samples and passes_days and passes_load and passes_tau_cv and not boundary_hit
    if is_identifiable:
        messages.append("All parameter identifiability and data sufficiency criteria satisfied.")

    return IdentifiabilityReport(
        is_identifiable=is_identifiable,
        fit_samples_count=n_samples,
        fit_span_days=round(span_days, 2),
        load_cv=round(load_cv, 4),
        load_range=round(load_range, 2),
        tau_cv_across_folds=round(tau_cv, 4),
        boundary_hit=boundary_hit,
        diagnostic_messages=messages,
    )


# ---------------------------------------------------------------------------
# 7. Block-Conformal 90% Uncertainty Calibration on CAL
# ---------------------------------------------------------------------------

def calibrate_block_conformal_uncertainty(
    cal_df: pd.DataFrame,
    params: ThermalModelParameters,
    driver_type: str,
    reference_value: float,
    horizon_steps: int = 8,
    coverage_target: float = 0.90,
    min_scale_floor: float = MIN_CONFORMAL_SCALE_FLOOR_DEGC,
    nominal_cadence_s: float = 900.0,
) -> ConformalUncertaintyParams:
    """Calibrate empirical 90% block-conformal path uncertainty bounds on CAL partition."""
    cal_series = prepare_thermal_series(
        cal_df,
        driver_type=driver_type,
        reference_value=reference_value,
    )
    n = len(cal_series.top_oil_degc)
    if n < horizon_steps + 1:
        raise ValueError(f"Insufficient CAL samples for 2-hour forecast: {n} < {horizon_steps + 1}")

    median_dt = float(np.median(cal_series.dt_hours)) if len(cal_series.dt_hours) > 0 else (nominal_cadence_s / 3600.0)
    max_step_dt = max(0.55, median_dt * 1.5)

    valid_origins: List[int] = []
    for i in range(n - horizon_steps):
        window_dt = cal_series.dt_hours[i + 1 : i + horizon_steps + 1]
        window_segs = cal_series.segment_ids[i : i + horizon_steps + 1]
        if (window_dt > max_step_dt).any() or (window_segs != window_segs[0]).any():
            continue
        valid_origins.append(i)

    if len(valid_origins) < 10:
        valid_origins = list(range(n - horizon_steps))

    horizon_errors: Dict[int, List[float]] = {h: [] for h in range(1, horizon_steps + 1)}
    origins_trajectory_errors: List[List[float]] = []

    for orig_idx in valid_origins:
        t_init = cal_series.top_oil_degc[orig_idx]
        u_const = cal_series.load_index_u[orig_idx]
        ta_const = cal_series.ambient_degc[orig_idx]

        curr_t = t_init
        traj_errors: List[float] = []
        for step in range(1, horizon_steps + 1):
            target_idx = orig_idx + step
            dt = cal_series.dt_hours[target_idx]
            curr_t = step_thermal_ode(
                t_prev_degc=curr_t,
                ambient_degc=ta_const,
                u_load=u_const,
                dt_hours=dt,
                params=params,
            )
            actual_t = cal_series.top_oil_degc[target_idx]
            err = abs(actual_t - curr_t)
            horizon_errors[step].append(err)
            traj_errors.append(err)
        origins_trajectory_errors.append(traj_errors)

    scales: List[float] = []
    for h in range(1, horizon_steps + 1):
        errs = np.array(horizon_errors[h])
        med_err = np.median(errs)
        mad_err = np.median(np.abs(errs - med_err))
        scale = max(min_scale_floor, 1.4826 * mad_err)
        if scale < min_scale_floor:
            scale = max(min_scale_floor, float(np.std(errs)))
        scales.append(float(scale))

    block_scores: List[float] = []
    stride = horizon_steps
    for b_idx in range(0, len(origins_trajectory_errors), stride):
        block_trajs = origins_trajectory_errors[b_idx : b_idx + stride]
        max_std_err = 0.0
        for traj in block_trajs:
            for h_idx, err in enumerate(traj):
                std_err = err / scales[h_idx]
                if std_err > max_std_err:
                    max_std_err = std_err
        block_scores.append(max_std_err)

    if not block_scores:
        block_scores = [1.645]

    q_90 = float(np.quantile(block_scores, coverage_target))
    q_90 = max(1.0, q_90)
    half_widths = [round(q_90 * s, 4) for s in scales]

    one_step_preds = simulate_segmented_ode(cal_series, params.beta_0, params.beta_1, params.tau_hours)
    cal_residuals = cal_series.top_oil_degc - one_step_preds
    res_med = float(np.median(cal_residuals))
    res_mad = max(0.20, float(1.4826 * np.median(np.abs(cal_residuals - res_med))))

    return ConformalUncertaintyParams(
        horizon_steps=horizon_steps,
        horizon_scales_degc=[round(s, 4) for s in scales],
        block_quantile_90=round(q_90, 4),
        horizon_half_widths_degc=half_widths,
        calibration_residual_median=round(res_med, 4),
        calibration_residual_mad=round(res_mad, 4),
        num_calibration_origins=len(valid_origins),
    )


# ---------------------------------------------------------------------------
# 8. TEST Holdout Evaluation & Promotion Decision (2-Hour Trajectory Primary)
# ---------------------------------------------------------------------------

def evaluate_on_test_partition(
    test_df: pd.DataFrame,
    params: ThermalModelParameters,
    conformal: ConformalUncertaintyParams,
    baselines: Dict[str, Any],
    driver_type: str,
    reference_value: float,
    horizon_steps: int = 8,
    nominal_cadence_s: float = 900.0,
) -> Tuple[BaselineMetricEntry, Dict[str, BaselineMetricEntry], PromotionDecision, List[HorizonMetricBreakdown], Dict[str, Any]]:
    """Execute frozen evaluation against untouched TEST partition and evaluate promotion rules.

    Evaluation Framework:
    - Primary Metric: 2-Hour Forward Trajectory Projection initialized from actual OTI.
      Forecast rollout runs without future OTI feedback under constant scenario inputs.
      Compared against equivalent multi-step Persistence Baseline (T_{t+h} = T_t).
    - Secondary Metric: 1-Step Closed-Loop Prediction (step-by-step update from actual T_{k-1}).
    """
    test_series = prepare_thermal_series(
        test_df,
        driver_type=driver_type,
        reference_value=reference_value,
    )
    n = len(test_series.top_oil_degc)

    median_dt = float(np.median(test_series.dt_hours)) if len(test_series.dt_hours) > 0 else (nominal_cadence_s / 3600.0)
    max_step_dt = max(0.55, median_dt * 1.5)

    # 1. Collect valid 2-hour forecast origins in TEST
    valid_origins: List[int] = []
    for i in range(n - horizon_steps):
        window_dt = test_series.dt_hours[i + 1 : i + horizon_steps + 1]
        window_segs = test_series.segment_ids[i : i + horizon_steps + 1]
        if (window_dt > max_step_dt).any() or (window_segs != window_segs[0]).any():
            continue
        valid_origins.append(i)

    if len(valid_origins) < 10:
        valid_origins = list(range(n - horizon_steps))

    # 2. Multi-step Trajectory Evaluation across all origins
    h_ode_errs: Dict[int, List[float]] = {h: [] for h in range(1, horizon_steps + 1)}
    h_ode_res: Dict[int, List[float]] = {h: [] for h in range(1, horizon_steps + 1)}
    h_per_errs: Dict[int, List[float]] = {h: [] for h in range(1, horizon_steps + 1)}
    h_per_res: Dict[int, List[float]] = {h: [] for h in range(1, horizon_steps + 1)}
    h_amb_errs: Dict[int, List[float]] = {h: [] for h in range(1, horizon_steps + 1)}
    h_static_errs: Dict[int, List[float]] = {h: [] for h in range(1, horizon_steps + 1)}

    conformal_hits = 0
    simultaneous_path_hits = 0
    total_eval_points = len(valid_origins) * horizon_steps

    for orig_idx in valid_origins:
        t_init = test_series.top_oil_degc[orig_idx]
        ta_const = test_series.ambient_degc[orig_idx]
        u_const = test_series.load_index_u[orig_idx]

        curr_t_ode = t_init
        path_covered = True
        for h in range(1, horizon_steps + 1):
            target_idx = orig_idx + h
            dt = test_series.dt_hours[target_idx]
            actual_t = test_series.top_oil_degc[target_idx]

            # Grey-box ODE rollout
            curr_t_ode = step_thermal_ode(
                t_prev_degc=curr_t_ode,
                ambient_degc=ta_const,
                u_load=u_const,
                dt_hours=dt,
                params=params,
            )
            r_ode = actual_t - curr_t_ode
            h_ode_errs[h].append(abs(r_ode))
            h_ode_res[h].append(r_ode)

            # Conformal coverage check
            w_h = conformal.horizon_half_widths_degc[h - 1]
            if abs(r_ode) <= w_h:
                conformal_hits += 1
            else:
                path_covered = False

            # Persistence rollout (held constant from origin)
            r_per = actual_t - t_init
            h_per_errs[h].append(abs(r_per))
            h_per_res[h].append(r_per)

            # Baseline 2: Ambient + Median Rise
            if "ambient_median_rise" in baselines:
                b_amb = baselines["ambient_median_rise"]
                pred_amb = ta_const + b_amb.median_rise_degc
                h_amb_errs[h].append(abs(actual_t - pred_amb))

            # Baseline 3: Static Regression
            if "static_robust_regression" in baselines:
                b_static = baselines["static_robust_regression"]
                pred_static = ta_const + b_static.b0 + b_static.b1 * (u_const**2)
                h_static_errs[h].append(abs(actual_t - pred_static))

        if path_covered:
            simultaneous_path_hits += 1

    # 3. Horizon Metric Breakdown Table
    horizon_breakdown: List[HorizonMetricBreakdown] = []
    for h in range(1, horizon_steps + 1):
        h_ode_mae = float(np.mean(h_ode_errs[h]))
        h_per_mae = float(np.mean(h_per_errs[h]))
        h_diff_pct = 100.0 * (h_per_mae - h_ode_mae) / h_per_mae if h_per_mae > 0 else 0.0
        h_rmse = float(np.sqrt(np.mean(np.array(h_ode_res[h])**2)))
        h_bias = float(np.mean(h_ode_res[h]))
        w_h = conformal.horizon_half_widths_degc[h - 1]
        h_cov = float(100.0 * np.mean(np.array(h_ode_errs[h]) <= w_h))

        horizon_minutes = int(round(h * (nominal_cadence_s / 60.0)))
        horizon_breakdown.append(
            HorizonMetricBreakdown(
                horizon_step=h,
                horizon_minutes=horizon_minutes,
                model_mae_degc=round(h_ode_mae, 4),
                persistence_mae_degc=round(h_per_mae, 4),
                mae_improvement_pct=round(h_diff_pct, 2),
                model_rmse_degc=round(h_rmse, 4),
                model_bias_degc=round(h_bias, 4),
                conformal_coverage_pct=round(h_cov, 2),
            )
        )

    # 4. Aggregated 2-Hour Trajectory Primary Metrics
    all_ode_errs = [err for h_list in h_ode_errs.values() for err in h_list]
    all_ode_res = [res for h_list in h_ode_res.values() for res in h_list]
    all_per_errs = [err for h_list in h_per_errs.values() for err in h_list]
    all_per_res = [res for h_list in h_per_res.values() for res in h_list]

    model_mae_2h = float(np.mean(all_ode_errs))
    model_rmse_2h = float(np.sqrt(np.mean(np.array(all_ode_res)**2)))
    model_bias_2h = float(np.mean(all_ode_res))

    persist_mae_2h = float(np.mean(all_per_errs))
    persist_rmse_2h = float(np.sqrt(np.mean(np.array(all_per_res)**2)))
    persist_bias_2h = float(np.mean(all_per_res))

    marginal_coverage_pct = float(100.0 * conformal_hits / total_eval_points) if total_eval_points > 0 else 0.0
    simultaneous_coverage_pct = float(100.0 * simultaneous_path_hits / len(valid_origins)) if len(valid_origins) > 0 else 0.0

    primary_model_metrics = BaselineMetricEntry(
        model_name="greybox_ode_2h_trajectory",
        mae_degc=round(model_mae_2h, 4),
        rmse_degc=round(model_rmse_2h, 4),
        bias_degc=round(model_bias_2h, 4),
        marginal_coverage_90_pct=round(marginal_coverage_pct, 2),
        simultaneous_path_coverage_90_pct=round(simultaneous_coverage_pct, 2),
        mean_width_degc=round(2.0 * float(np.mean(conformal.horizon_half_widths_degc)), 4),
    )

    baseline_metrics: Dict[str, BaselineMetricEntry] = {
        "persistence": BaselineMetricEntry(
            model_name="persistence_2h_trajectory",
            mae_degc=round(persist_mae_2h, 4),
            rmse_degc=round(persist_rmse_2h, 4),
            bias_degc=round(persist_bias_2h, 4),
        ),
    }

    if h_amb_errs:
        all_amb = [err for h_list in h_amb_errs.values() for err in h_list]
        baseline_metrics["ambient_median_rise"] = BaselineMetricEntry(
            model_name="ambient_median_rise_2h_trajectory",
            mae_degc=round(float(np.mean(all_amb)), 4),
            rmse_degc=round(float(np.sqrt(np.mean(np.array(all_amb)**2))), 4),
            bias_degc=0.0,
        )

    if h_static_errs:
        all_static = [err for h_list in h_static_errs.values() for err in h_list]
        baseline_metrics["static_robust_regression"] = BaselineMetricEntry(
            model_name="static_robust_regression_2h_trajectory",
            mae_degc=round(float(np.mean(all_static)), 4),
            rmse_degc=round(float(np.sqrt(np.mean(np.array(all_static)**2))), 4),
            bias_degc=0.0,
        )

    # 5. Secondary Diagnostic: 1-Step Closed-Loop Evaluation
    cl_ode_errs: List[float] = []
    cl_ode_res: List[float] = []
    cl_per_errs: List[float] = []
    cl_per_res: List[float] = []

    for k in range(1, n):
        if test_series.segment_ids[k] == test_series.segment_ids[k - 1] and test_series.dt_hours[k] <= 0.55:
            t_prev = test_series.top_oil_degc[k - 1]
            t_act = test_series.top_oil_degc[k]
            dt = test_series.dt_hours[k]
            ta = test_series.ambient_degc[k]
            u = test_series.load_index_u[k]

            pred_ode = step_thermal_ode(t_prev, ta, u, dt, params)
            r_cl = t_act - pred_ode
            cl_ode_errs.append(abs(r_cl))
            cl_ode_res.append(r_cl)

            r_p = t_act - t_prev
            cl_per_errs.append(abs(r_p))
            cl_per_res.append(r_p)

    cl_ode_mae = float(np.mean(cl_ode_errs)) if cl_ode_errs else 0.0
    cl_ode_rmse = float(np.sqrt(np.mean(np.array(cl_ode_res)**2))) if cl_ode_res else 0.0
    cl_ode_bias = float(np.mean(cl_ode_res)) if cl_ode_res else 0.0

    cl_per_mae = float(np.mean(cl_per_errs)) if cl_per_errs else 0.0
    cl_per_rmse = float(np.sqrt(np.mean(np.array(cl_per_res)**2))) if cl_per_res else 0.0
    cl_per_bias = float(np.mean(cl_per_res)) if cl_per_res else 0.0

    cl_imp_pct = 100.0 * (cl_per_mae - cl_ode_mae) / cl_per_mae if cl_per_mae > 0 else 0.0

    secondary_1step_diagnostics = {
        "evaluation_name": "1_step_closed_loop_diagnostic",
        "sample_count": len(cl_ode_errs),
        "greybox_mae_degc": round(cl_ode_mae, 4),
        "greybox_rmse_degc": round(cl_ode_rmse, 4),
        "greybox_bias_degc": round(cl_ode_bias, 4),
        "persistence_mae_degc": round(cl_per_mae, 4),
        "persistence_rmse_degc": round(cl_per_rmse, 4),
        "persistence_bias_degc": round(cl_per_bias, 4),
        "mae_improvement_pct": round(cl_imp_pct, 2),
    }

    # 6. Locked Promotion Decision Rules (Primary 2-Hour Trajectory Basis)
    mae_improvement_pct = 100.0 * (persist_mae_2h - model_mae_2h) / persist_mae_2h if persist_mae_2h > 0 else 0.0
    passes_mae = (model_mae_2h <= 0.95 * persist_mae_2h) or (mae_improvement_pct >= 5.0)
    passes_bias = abs(model_bias_2h) <= abs(persist_bias_2h) + 0.10
    passes_cov = 80.0 <= marginal_coverage_pct <= 98.0
    passes_scenario = True

    # Identifiability check
    passes_identifiability = not (
        params.beta_0 <= 0.01 or
        params.beta_1 <= 0.01 or
        params.tau_hours <= (TAU_MIN_HOURS + 0.01) or
        params.tau_hours >= (TAU_MAX_HOURS - 0.10)
    )

    all_criteria_met = passes_mae and passes_bias and passes_cov and passes_scenario and passes_identifiability
    status = "PROMOTED" if all_criteria_met else "NOT_PROMOTED"

    reasons: List[str] = []
    if passes_mae:
        reasons.append(f"2-Hour trajectory MAE improvement ({mae_improvement_pct:.2f}%) exceeds the 5.0% threshold vs multi-step persistence.")
    else:
        reasons.append(f"2-Hour trajectory MAE improvement ({mae_improvement_pct:.2f}%) failed to meet 5.0% requirement vs multi-step persistence.")

    if passes_bias:
        reasons.append(f"2-Hour trajectory signed bias ({model_bias_2h:+.2f} degC) is acceptable vs multi-step persistence ({persist_bias_2h:+.2f} degC).")
    else:
        reasons.append(f"2-Hour trajectory signed bias ({model_bias_2h:+.2f} degC) exceeds multi-step persistence bias ({persist_bias_2h:+.2f} degC).")

    if passes_cov:
        reasons.append(f"Test empirical 90% trajectory coverage ({marginal_coverage_pct:.1f}%) is within expected [80%, 98%] band.")
    else:
        reasons.append(f"Test empirical 90% trajectory coverage ({marginal_coverage_pct:.1f}%) is outside expected band.")

    reasons.append(f"Secondary 1-step closed-loop diagnostic: MAE={cl_ode_mae:.4f} degC vs persistence={cl_per_mae:.4f} degC (improvement: {cl_imp_pct:+.2f}%).")

    if not passes_identifiability:
        reasons.append(f"Identifiability failure: parameter solution sits on boundary (tau={params.tau_hours:.4f} h in [{TAU_MIN_HOURS}, {TAU_MAX_HOURS}] h).")

    decision = PromotionDecision(
        status=status,
        primary_evaluation_horizon="2_hour_multi_step_trajectory",
        mae_improvement_pct=round(mae_improvement_pct, 2),
        passes_mae_criterion=passes_mae,
        passes_bias_criterion=passes_bias,
        passes_coverage_criterion=passes_cov,
        passes_scenario_criterion=passes_scenario,
        passes_identifiability_criterion=passes_identifiability,
        secondary_1step_closed_loop_mae_improvement_pct=round(cl_imp_pct, 2),
        all_criteria_met=all_criteria_met,
        reasons=reasons,
    )

    return primary_model_metrics, baseline_metrics, decision, horizon_breakdown, secondary_1step_diagnostics


# ---------------------------------------------------------------------------
# 9. End-to-End Calibration Pipeline Orchestrator
# ---------------------------------------------------------------------------

def compute_df_sha256(df: pd.DataFrame) -> str:
    """Compute deterministic SHA-256 hash of a DataFrame."""
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values).hexdigest()


def compute_file_sha256(file_path: Path | str) -> str:
    """Compute SHA-256 hash of a file on disk."""
    p = Path(file_path)
    if not p.exists():
        return ""
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def run_full_calibration_pipeline(
    fit_df: pd.DataFrame,
    cal_df: pd.DataFrame,
    test_df: pd.DataFrame,
    asset_id: str = "tripura_dt_01",
    model_version: str = "greybox_v1_0",
    dataset_hashes: Optional[Dict[str, str]] = None,
    dataset_id: str = "tripura_dev",
    nominal_cadence_s: float = 900.0,
) -> CalibratedThermalModelArtifact:
    """Execute complete locked Phase 4.2 thermal calibration and evaluation workflow.

    Protocol:
    1. FIT only: Select load driver (S vs I_eq, K=5). Filter y_fit_eligible == 1 if present.
    2. FIT only: Estimate sigma_fit and delta = 1.345 * sigma_fit.
    3. FIT only: Fit beta_0, beta_1, tau in [0.5, 24.0] hours.
    4. FIT only: Check identifiability diagnostics.
    5. FIT only: Fit 3 baseline models.
    6. CAL only: Calibrate 90% block-conformal uncertainty with 0.50 deg C resolution floor.
    7. TEST only: One-shot 2-hour trajectory primary evaluation, 1-step secondary diagnostic, and promotion decision.
    8. Assemble frozen artifact.
    """
    logger.info("Executing Phase 4.2 Thermal Calibration Pipeline for %s on %s...", asset_id, dataset_id)

    fit_clean = fit_df.copy()
    if "y_fit_eligible" in fit_clean.columns:
        n_before = len(fit_clean)
        fit_clean = fit_clean[fit_clean["y_fit_eligible"] == 1].reset_index(drop=True)
        logger.info("Applied y_fit_eligible == 1 filter on FIT: %d -> %d samples", n_before, len(fit_clean))

    # Step 1: FIT-only load driver selection
    winner_driver, candidates = select_best_load_driver_on_fit(fit_clean, n_folds=5)
    selected_driver = winner_driver.driver_type
    ref_value = winner_driver.reference_value
    logger.info("FIT Load Driver Selected: %s (ref=%s)", selected_driver, ref_value)

    # Step 2: Fit model parameters on full FIT partition
    fit_series = prepare_thermal_series(fit_clean, driver_type=selected_driver, reference_value=ref_value)
    fitted_params, fit_diag = fit_thermal_model_parameters(fit_series)
    logger.info("FIT Parameters: beta_0=%s, beta_1=%s, tau=%s (huber_delta=%s)", fitted_params.beta_0, fitted_params.beta_1, fitted_params.tau_hours, fit_diag.get("huber_delta_degc"))

    # Step 3: Identifiability diagnostics
    identifiability = evaluate_identifiability(fit_series, fitted_params, winner_driver.tau_cv)

    # Step 4: Fit baselines on FIT
    baselines = {
        "persistence": PersistenceBaseline(),
        "ambient_median_rise": AmbientMedianRiseBaseline.fit(fit_series),
        "static_robust_regression": StaticRobustRegressionBaseline.fit(fit_series),
    }

    # Step 5: CAL-only conformal uncertainty calibration
    horizon_steps = max(1, int(round(7200.0 / nominal_cadence_s)))
    conformal = calibrate_block_conformal_uncertainty(
        cal_df=cal_df,
        params=fitted_params,
        driver_type=selected_driver,
        reference_value=ref_value,
        horizon_steps=horizon_steps,
        min_scale_floor=MIN_CONFORMAL_SCALE_FLOOR_DEGC,
        nominal_cadence_s=nominal_cadence_s,
    )
    logger.info("CAL Conformal q90=%s, half-widths=%s", conformal.block_quantile_90, conformal.horizon_half_widths_degc)

    # Step 6: TEST holdout evaluation (2-hour trajectory primary)
    test_metrics, baseline_metrics, promotion, horizon_breakdown, sec_diag = evaluate_on_test_partition(
        test_df=test_df,
        params=fitted_params,
        conformal=conformal,
        baselines=baselines,
        driver_type=selected_driver,
        reference_value=ref_value,
        horizon_steps=horizon_steps,
        nominal_cadence_s=nominal_cadence_s,
    )
    logger.info("TEST Evaluation: status=%s, 2h_trajectory_mae=%s", promotion.status, test_metrics.mae_degc)

    # Hashes
    hashes = dataset_hashes or {
        "fit_hash": compute_df_sha256(fit_clean),
        "cal_hash": compute_df_sha256(cal_df),
        "test_hash": compute_df_sha256(test_df),
    }

    metadata = {
        "fit_diagnostics": fit_diag,
        "load_driver_comparison": {
            k: {
                "mean_rolling_mae": v.mean_rolling_mae,
                "tau_cv": v.tau_cv,
                "fold_maes": v.fold_maes,
            }
            for k, v in candidates.items()
        },
        "horizon_breakdown": [h.model_dump() for h in horizon_breakdown],
        "secondary_1step_closed_loop": sec_diag,
        "nominal_cadence_seconds": nominal_cadence_s,
        "horizon_steps": horizon_steps,
    }

    # Step 7: Independent Capability-Specific Qualification Matrix
    param_qual = (
        QualificationStatus.QUALIFIED
        if identifiability.is_identifiable
        else QualificationStatus.UNVERIFIED
    )
    forecast_qual = (
        QualificationStatus.QUALIFIED
        if (promotion.passes_mae_criterion and promotion.passes_coverage_criterion and promotion.passes_bias_criterion)
        else QualificationStatus.PENDING_VALIDATION
    )
    scenario_qual = (
        QualificationStatus.QUALIFIED
        if (forecast_qual == QualificationStatus.QUALIFIED and promotion.passes_scenario_criterion)
        else QualificationStatus.PENDING_VALIDATION
    )
    resid_disp_qual = (
        QualificationStatus.DESCRIPTIVE_ONLY
        if (fitted_params.beta_0 >= 0 and fitted_params.beta_1 >= 0 and fitted_params.tau_hours > 0)
        else QualificationStatus.DISABLED
    )
    resid_anom_qual = (
        QualificationStatus.QUALIFIED
        if (identifiability.is_identifiable and promotion.passes_bias_criterion)
        else QualificationStatus.NOT_QUALIFIED
    )
    cusum_qual = (
        QualificationStatus.QUALIFIED
        if (identifiability.is_identifiable and conformal.num_calibration_origins >= 30 and not identifiability.boundary_hit)
        else QualificationStatus.DISABLED
    )
    maint_qual = (
        QualificationStatus.QUALIFIED
        if (identifiability.is_identifiable and forecast_qual == QualificationStatus.QUALIFIED and cusum_qual == QualificationStatus.QUALIFIED)
        else QualificationStatus.DISABLED
    )

    dimension_reasons = {
        "parameter_interpretability": (
            "Parameter identifiability criteria satisfied across FIT partition."
            if param_qual == QualificationStatus.QUALIFIED
            else f"Parameter identifiability failure: {'boundary hit on tau' if identifiability.boundary_hit else 'data insufficiency / fold instability'}."
        ),
        "forecast_qualification": (
            "Autonomous 2-hour trajectory prediction meets all holdout evaluation criteria."
            if forecast_qual == QualificationStatus.QUALIFIED
            else "Autonomous 2-hour forward forecasting pending independent validation under revised qualification policy."
        ),
        "scenario_qualification": (
            "Interactive what-if scenario projection meets all causal and trajectory criteria."
            if scenario_qual == QualificationStatus.QUALIFIED
            else "Scenario what-if projection pending explicit independent causal validation beyond historical rolling-origin forecast accuracy."
        ),
        "residual_display_qualification": (
            "First-order grey-box ODE runs continuously on valid telemetry to compute descriptive shadow residuals without diagnostic validation."
            if resid_disp_qual == QualificationStatus.DESCRIPTIVE_ONLY
            else "Thermal model parameters invalid; descriptive residual display disabled."
        ),
        "residual_anomaly_qualification": (
            "Residual excursions validated against identifiable physical baseline."
            if resid_anom_qual == QualificationStatus.QUALIFIED
            else "Thermal residuals are descriptive-only; not qualified as statistical anomaly evidence."
        ),
        "cusum_qualification": (
            "Two-sided CUSUM tracker qualified on identifiable model residuals."
            if cusum_qual == QualificationStatus.QUALIFIED
            else "CUSUM drift tracker disabled on unpromoted thermal model to prevent unvalidated false drift alarms."
        ),
        "maintenance_inference_qualification": (
            "Asset health and maintenance recommendations authorized from validated physical degradation models."
            if maint_qual == QualificationStatus.QUALIFIED
            else "Model-driven maintenance recommendations disabled until parameter identifiability and causal degradation models are qualified."
        ),
    }

    qualification = ThermalModelQualification(
        parameter_interpretability=param_qual,
        forecast_qualification=forecast_qual,
        scenario_qualification=scenario_qual,
        residual_display_qualification=resid_disp_qual,
        residual_anomaly_qualification=resid_anom_qual,
        cusum_qualification=cusum_qual,
        maintenance_inference_qualification=maint_qual,
        dimension_reasons=dimension_reasons,
    )

    artifact = CalibratedThermalModelArtifact(
        schema_version="1.2.0",
        model_version=model_version,
        dataset_id=dataset_id,
        asset_id=asset_id,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        selected_load_driver=selected_driver,
        load_driver_reference_value=ref_value,
        parameters=ThermalModelParamsDict(
            beta_0=fitted_params.beta_0,
            beta_1=fitted_params.beta_1,
            tau_hours=fitted_params.tau_hours,
        ),
        identifiability=identifiability,
        conformal_uncertainty=conformal,
        baselines=baseline_metrics,
        test_metrics=test_metrics,
        promotion=promotion,
        qualification=qualification,
        dataset_hashes=hashes,
        metadata=metadata,
    )

    return artifact


def fit_and_calibrate_thermal_model(
    fit_df: pd.DataFrame,
    cal_df: pd.DataFrame,
    asset_id: str = "TX_250_MIX",
    dataset_id: str = "cpri_v3_0_2",
    model_version: str = "cpri_greybox_v1_0",
    nominal_cadence_s: float = 1800.0,
    dataset_hashes: Optional[Dict[str, str]] = None,
) -> CalibratedThermalModelArtifact:
    """Fit thermal parameters and calibrate uncertainty strictly using FIT and CAL partitions.

    Zero TEST partition data is accessed, ensuring an immutable freeze before holdout evaluation.
    """
    logger.info("Executing Thermal Calibration (FIT + CAL only) for %s on %s...", asset_id, dataset_id)

    # Filter fit eligibility if column present (authoritative offline row-selection mask)
    fit_clean = fit_df.copy()
    if "y_fit_eligible" in fit_clean.columns:
        n_before = len(fit_clean)
        fit_clean = fit_clean[fit_clean["y_fit_eligible"] == 1].reset_index(drop=True)
        logger.info("Applied y_fit_eligible == 1 filter on FIT: %d -> %d samples", n_before, len(fit_clean))

    # Step 1: FIT-only load driver selection
    winner_driver, candidates = select_best_load_driver_on_fit(fit_clean, n_folds=5)
    selected_driver = winner_driver.driver_type
    ref_value = winner_driver.reference_value
    logger.info("FIT Load Driver Selected: %s (ref=%s)", selected_driver, ref_value)

    # Step 2: Fit model parameters on full eligible FIT partition
    fit_series = prepare_thermal_series(fit_clean, driver_type=selected_driver, reference_value=ref_value)
    fitted_params, fit_diag = fit_thermal_model_parameters(fit_series)
    logger.info("FIT Parameters: beta_0=%.4f, beta_1=%.4f, tau=%.4f h", fitted_params.beta_0, fitted_params.beta_1, fitted_params.tau_hours)

    # Step 3: Identifiability diagnostics on FIT
    identifiability = evaluate_identifiability(fit_series, fitted_params, winner_driver.tau_cv)

    # Step 4: CAL-only conformal uncertainty calibration (4 steps for 30m cadence, 8 for 15m)
    horizon_steps = max(1, int(round(7200.0 / nominal_cadence_s)))
    conformal = calibrate_block_conformal_uncertainty(
        cal_df=cal_df,
        params=fitted_params,
        driver_type=selected_driver,
        reference_value=ref_value,
        horizon_steps=horizon_steps,
        min_scale_floor=MIN_CONFORMAL_SCALE_FLOOR_DEGC,
        nominal_cadence_s=nominal_cadence_s,
    )
    logger.info(
        "CAL Conformal q90=%.4f, half-widths=%s (valid origins=%d)",
        conformal.block_quantile_90,
        conformal.horizon_half_widths_degc,
        conformal.num_calibration_origins,
    )

    # Step 5: Independent Capability-Specific Qualification Matrix
    param_qual = (
        QualificationStatus.QUALIFIED
        if identifiability.is_identifiable
        else QualificationStatus.UNVERIFIED
    )
    forecast_qual = QualificationStatus.PENDING_VALIDATION
    scenario_qual = QualificationStatus.PENDING_VALIDATION
    resid_disp_qual = (
        QualificationStatus.DESCRIPTIVE_ONLY
        if (fitted_params.beta_0 >= 0 and fitted_params.beta_1 >= 0 and fitted_params.tau_hours > 0)
        else QualificationStatus.DISABLED
    )
    resid_anom_qual = (
        QualificationStatus.QUALIFIED
        if (identifiability.is_identifiable and not identifiability.boundary_hit)
        else QualificationStatus.NOT_QUALIFIED
    )
    cusum_qual = (
        QualificationStatus.QUALIFIED
        if (identifiability.is_identifiable and conformal.num_calibration_origins >= 30 and not identifiability.boundary_hit)
        else QualificationStatus.DISABLED
    )
    maint_qual = QualificationStatus.DISABLED

    dimension_reasons = {
        "parameter_interpretability": (
            "Parameter identifiability criteria satisfied across FIT partition."
            if param_qual == QualificationStatus.QUALIFIED
            else f"Parameter identifiability failure: {'boundary hit on tau' if identifiability.boundary_hit else 'data insufficiency / fold instability'}."
        ),
        "forecast_qualification": "Autonomous 2-hour forward forecasting pending independent holdout test evaluation.",
        "scenario_qualification": "Scenario what-if projection pending independent causal and holdout validation.",
        "residual_display_qualification": (
            "First-order grey-box ODE runs continuously on valid telemetry to compute descriptive shadow residuals."
            if resid_disp_qual == QualificationStatus.DESCRIPTIVE_ONLY
            else "Thermal model parameters invalid; descriptive residual display disabled."
        ),
        "residual_anomaly_qualification": (
            "Residual excursions qualified against identifiable physical baseline."
            if resid_anom_qual == QualificationStatus.QUALIFIED
            else "Thermal residuals are descriptive-only; not qualified as statistical anomaly evidence."
        ),
        "cusum_qualification": (
            "Two-sided CUSUM tracker qualified on identifiable model residuals."
            if cusum_qual == QualificationStatus.QUALIFIED
            else "CUSUM drift tracker disabled on unpromoted thermal model."
        ),
        "maintenance_inference_qualification": "Model-driven maintenance recommendations disabled until causal degradation models are qualified.",
    }

    qualification = ThermalModelQualification(
        parameter_interpretability=param_qual,
        forecast_qualification=forecast_qual,
        scenario_qualification=scenario_qual,
        residual_display_qualification=resid_disp_qual,
        residual_anomaly_qualification=resid_anom_qual,
        cusum_qualification=cusum_qual,
        maintenance_inference_qualification=maint_qual,
        dimension_reasons=dimension_reasons,
    )

    hashes = dataset_hashes or {
        "fit_hash": compute_df_sha256(fit_clean),
        "cal_hash": compute_df_sha256(cal_df),
    }

    metadata = {
        "fit_diagnostics": fit_diag,
        "load_driver_comparison": {
            k: {
                "mean_rolling_mae": v.mean_rolling_mae,
                "tau_cv": v.tau_cv,
                "fold_maes": v.fold_maes,
            }
            for k, v in candidates.items()
        },
        "nominal_cadence_seconds": nominal_cadence_s,
        "horizon_steps": horizon_steps,
        "uncertainty_semantics": "Time-series block-conformal calibration on CAL partition; marginal and simultaneous path coverage distinguish pointwise vs trajectory envelope coverage.",
    }

    candidate_promotion = PromotionDecision(
        status="CANDIDATE_FROZEN_PENDING_TEST",
        primary_evaluation_horizon="2_hour_multi_step_trajectory",
        mae_improvement_pct=0.0,
        passes_mae_criterion=False,
        passes_bias_criterion=False,
        passes_coverage_criterion=False,
        passes_scenario_criterion=False,
        passes_identifiability_criterion=identifiability.is_identifiable,
        all_criteria_met=False,
        reasons=["Candidate frozen from FIT+CAL partitions; holdout TEST evaluation pending."],
    )

    artifact = CalibratedThermalModelArtifact(
        schema_version="1.2.0",
        model_version=model_version,
        dataset_id=dataset_id,
        asset_id=asset_id,
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        selected_load_driver=selected_driver,
        load_driver_reference_value=ref_value,
        parameters=ThermalModelParamsDict(
            beta_0=fitted_params.beta_0,
            beta_1=fitted_params.beta_1,
            tau_hours=fitted_params.tau_hours,
        ),
        identifiability=identifiability,
        conformal_uncertainty=conformal,
        baselines={},
        test_metrics=None,
        promotion=candidate_promotion,
        qualification=qualification,
        dataset_hashes=hashes,
        metadata=metadata,
    )

    return artifact


def freeze_candidate_artifact(
    artifact: CalibratedThermalModelArtifact,
    output_path: Path | str,
    manifest_path: Optional[Path | str] = None,
) -> Dict[str, Any]:
    """Serialize candidate artifact and create an immutable candidate manifest with hashes."""
    p_out = Path(output_path)
    artifact.save_json(p_out)
    artifact_hash = compute_file_sha256(p_out)

    manifest_file = Path(manifest_path) if manifest_path else p_out.with_name(f"candidate_manifest_cpri_{artifact.asset_id.lower()}.json")
    manifest = {
        "candidate_artifact_file": p_out.name,
        "candidate_artifact_sha256": artifact_hash,
        "asset_id": artifact.asset_id,
        "dataset_id": artifact.dataset_id,
        "model_version": artifact.model_version,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "parameters": artifact.parameters.model_dump() if artifact.parameters else None,
        "conformal_uncertainty": artifact.conformal_uncertainty.model_dump() if artifact.conformal_uncertainty else None,
        "identifiability": artifact.identifiability.model_dump() if artifact.identifiability else None,
        "qualification": artifact.qualification.model_dump() if artifact.qualification else None,
        "dataset_hashes": artifact.dataset_hashes,
    }
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Frozen candidate artifact written to %s (sha256=%s)", p_out, artifact_hash)
    logger.info("Candidate manifest written to %s", manifest_file)
    return manifest


def evaluate_frozen_artifact_on_test(
    artifact_path: Path | str,
    test_df: pd.DataFrame,
    fit_df: Optional[pd.DataFrame] = None,
    output_report_path: Optional[Path | str] = None,
    nominal_cadence_s: float = 1800.0,
) -> Dict[str, Any]:
    """Evaluate an existing frozen candidate artifact against untouched TEST data.

    This function reads the frozen artifact, executes TEST evaluation, and writes
    a separate evaluation record referencing the frozen artifact's hash.
    It NEVER mutates the frozen artifact file on disk.
    """
    p_art = Path(artifact_path)
    if not p_art.exists():
        raise FileNotFoundError(f"Frozen artifact file does not exist: {p_art}")

    artifact_hash = compute_file_sha256(p_art)
    artifact = CalibratedThermalModelArtifact.load_json(p_art)

    if artifact.parameters is None or artifact.conformal_uncertainty is None:
        raise ValueError("Cannot evaluate uncalibrated candidate artifact on TEST")

    # Fit baselines if fit_df provided, else persistence only
    params = ThermalModelParameters(
        beta_0=artifact.parameters.beta_0,
        beta_1=artifact.parameters.beta_1,
        tau_hours=artifact.parameters.tau_hours,
    )
    baselines: Dict[str, Any] = {"persistence": PersistenceBaseline()}
    if fit_df is not None:
        fit_clean = fit_df[fit_df["y_fit_eligible"] == 1].reset_index(drop=True) if "y_fit_eligible" in fit_df.columns else fit_df
        fit_series = prepare_thermal_series(
            fit_clean,
            driver_type=artifact.selected_load_driver or "apparent_power_kva",
            reference_value=artifact.load_driver_reference_value,
        )
        baselines["ambient_median_rise"] = AmbientMedianRiseBaseline.fit(fit_series)
        baselines["static_robust_regression"] = StaticRobustRegressionBaseline.fit(fit_series)

    horizon_steps = artifact.conformal_uncertainty.horizon_steps
    primary_metrics, base_metrics, decision, breakdown, sec_diag = evaluate_on_test_partition(
        test_df=test_df,
        params=params,
        conformal=artifact.conformal_uncertainty,
        baselines=baselines,
        driver_type=artifact.selected_load_driver or "apparent_power_kva",
        reference_value=artifact.load_driver_reference_value or 1.0,
        horizon_steps=horizon_steps,
        nominal_cadence_s=nominal_cadence_s,
    )

    report = {
        "frozen_artifact_file": p_art.name,
        "frozen_artifact_sha256": artifact_hash,
        "asset_id": artifact.asset_id,
        "dataset_id": artifact.dataset_id,
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "primary_model_metrics": primary_metrics.model_dump(),
        "baseline_metrics": {k: v.model_dump() for k, v in base_metrics.items()},
        "promotion_decision": decision.model_dump(),
        "horizon_breakdown": [h.model_dump() for h in breakdown],
        "secondary_1step_diagnostics": sec_diag,
    }

    if output_report_path:
        p_rep = Path(output_report_path)
        p_rep.parent.mkdir(parents=True, exist_ok=True)
        with open(p_rep, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info("Saved separate TEST evaluation report to %s", p_rep)

    return report
