"""Unit and Integration Tests for Phase 4.2 Thermal Model Calibration Pipeline."""

import math
import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from app.engine.thermal import ThermalModelParameters, step_thermal_ode
from app.engine.calibration import (
    AmbientMedianRiseBaseline,
    PersistenceBaseline,
    ProcessedThermalSeries,
    StaticRobustRegressionBaseline,
    calibrate_block_conformal_uncertainty,
    calculate_huber_delta,
    estimate_fit_residual_scale,
    evaluate_identifiability,
    evaluate_load_driver_candidate_on_fit,
    evaluate_on_test_partition,
    extract_load_driver,
    fit_thermal_model_parameters,
    huber_loss,
    prepare_thermal_series,
    run_full_calibration_pipeline,
    select_best_load_driver_on_fit,
    HUBER_TUNING_CONSTANT_C,
    MIN_CONFORMAL_SCALE_FLOOR_DEGC,
    TAU_MAX_HOURS,
    TAU_MIN_HOURS,
)
from app.models.thermal_artifact import (
    CalibratedThermalModelArtifact,
    ConformalUncertaintyParams,
    PromotionDecision,
    ThermalModelParamsDict,
)


# ---------------------------------------------------------------------------
# Synthetic Dataset Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_partitions() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate synthetic deterministic FIT, CAL, and TEST partitions with ground-truth ODE."""
    np.random.seed(42)
    # Ground truth parameters: beta0=10.0, beta1=35.0, tau=3.0
    true_params = ThermalModelParameters(beta_0=10.0, beta_1=35.0, tau_hours=3.0)

    def make_partition(n_samples: int, start_time: pd.Timestamp) -> pd.DataFrame:
        times = [start_time + pd.Timedelta(minutes=15 * i) for i in range(n_samples)]
        # Ambient temperature diurnal cycle: 20 to 35 deg C
        hours = np.array([t.hour + t.minute / 60.0 for t in times])
        ambients = 25.0 + 7.0 * np.sin(2 * np.pi * (hours - 8.0) / 24.0)

        # Load cycle: 0.2 to 0.9 per-unit
        loads = 0.55 + 0.30 * np.sin(2 * np.pi * (hours - 10.0) / 24.0) + np.random.uniform(-0.05, 0.05, n_samples)
        loads = np.clip(loads, 0.1, 1.0)
        kva = loads * 100.0  # reference 100 kVA

        # Equivalent phase currents around ~140 A full load
        il1 = loads * 140.0 * np.random.uniform(0.95, 1.05, n_samples)
        il2 = loads * 140.0 * np.random.uniform(0.95, 1.05, n_samples)
        il3 = loads * 140.0 * np.random.uniform(0.95, 1.05, n_samples)

        # Simulate true top-oil ODE
        oti = np.zeros(n_samples)
        oti[0] = 45.0
        for i in range(1, n_samples):
            oti[i] = step_thermal_ode(
                t_prev_degc=oti[i - 1],
                ambient_degc=ambients[i],
                u_load=loads[i],
                dt_hours=0.25,
                params=true_params,
            )
        # Add slight observation noise
        oti_obs = np.round(oti + np.random.normal(0, 0.2, n_samples), 1)

        return pd.DataFrame({
            "ts": times,
            "OTI": oti_obs,
            "ATI": np.round(ambients, 1),
            "KVA": np.round(kva, 1),
            "KW": np.round(kva * 0.9, 1),
            "KVAR": np.round(kva * 0.43, 1),
            "IL1": np.round(il1, 1),
            "IL2": np.round(il2, 1),
            "IL3": np.round(il3, 1),
        })

    t0 = pd.Timestamp("2026-01-01 00:00:00", tz="UTC")
    fit_df = make_partition(700, t0)
    t1 = t0 + pd.Timedelta(minutes=15 * 700) + pd.Timedelta(hours=2)
    cal_df = make_partition(200, t1)
    t2 = t1 + pd.Timedelta(minutes=15 * 200) + pd.Timedelta(hours=2)
    test_df = make_partition(200, t2)

    return fit_df, cal_df, test_df


# ---------------------------------------------------------------------------
# 1. Huber Loss & Scale Estimation Tests
# ---------------------------------------------------------------------------

def test_huber_loss_properties():
    """Verify Huber loss matches 0.5 * r^2 for small errors and linear for large errors."""
    # Small error <= delta (1.35)
    r_small = np.array([0.5, -0.5])
    loss_small = huber_loss(r_small, delta=1.35)
    assert np.allclose(loss_small, 0.5 * 0.25)

    # Large error > delta
    r_large = np.array([3.0, -3.0])
    loss_large = huber_loss(r_large, delta=1.0)
    # delta * (|r| - 0.5 * delta) = 1.0 * (3.0 - 0.5) = 2.5
    assert np.allclose(loss_large, 2.5)


def test_huber_delta_derived_from_fit_mad(synthetic_partitions):
    """Verify that Huber delta is computed as c * sigma_fit using robust MAD scale."""
    fit_df, _, _ = synthetic_partitions
    series = prepare_thermal_series(fit_df)

    sigma_fit = estimate_fit_residual_scale(series)
    delta = calculate_huber_delta(series)

    assert sigma_fit >= MIN_CONFORMAL_SCALE_FLOOR_DEGC
    assert delta == pytest.approx(HUBER_TUNING_CONSTANT_C * sigma_fit, abs=1e-6)

    # Fitting with delta_huber=None uses dynamic delta
    params, diag = fit_thermal_model_parameters(series, tau_grid_points=10)
    assert diag["huber_delta_degc"] == pytest.approx(delta, abs=1e-4)
    assert diag["fit_sigma_mad_degc"] == pytest.approx(sigma_fit, abs=1e-4)


# ---------------------------------------------------------------------------
# 2. Load Driver Extraction & Pre-Processing
# ---------------------------------------------------------------------------

def test_extract_load_driver_candidates(synthetic_partitions):
    """Verify extraction of apparent power and RMS current."""
    fit_df, _, _ = synthetic_partitions
    kva = extract_load_driver(fit_df, "apparent_power_kva")
    rms_i = extract_load_driver(fit_df, "rms_current_a")

    assert len(kva) == len(fit_df)
    assert len(rms_i) == len(fit_df)
    assert (kva >= 0).all()
    assert (rms_i >= 0).all()


def test_prepare_thermal_series_gap_segmentation():
    """Verify that gaps > max_gap_hours increment segment IDs."""
    times = [
        pd.Timestamp("2026-01-01 00:00:00"),
        pd.Timestamp("2026-01-01 00:15:00"),
        pd.Timestamp("2026-01-01 02:30:00"),  # gap of 2h15m
        pd.Timestamp("2026-01-01 02:45:00"),
    ]
    df = pd.DataFrame({
        "ts": times,
        "OTI": [40.0, 41.0, 38.0, 39.0],
        "ATI": [25.0, 25.0, 24.0, 24.0],
        "KVA": [50.0, 52.0, 48.0, 50.0],
    })
    series = prepare_thermal_series(df, driver_type="apparent_power_kva", max_gap_hours=1.0)
    assert len(series.segment_ids) == 4
    assert series.segment_ids[0] == 0
    assert series.segment_ids[1] == 0
    assert series.segment_ids[2] == 1
    assert series.segment_ids[3] == 1


# ---------------------------------------------------------------------------
# 3. Deterministic Parameter Fitting & Domain Constraints
# ---------------------------------------------------------------------------

def test_fit_thermal_model_parameters(synthetic_partitions):
    """Verify bounded parameter fitting on synthetic partition recovers physical parameters."""
    fit_df, _, _ = synthetic_partitions
    series = prepare_thermal_series(fit_df, driver_type="apparent_power_kva")

    params, diag = fit_thermal_model_parameters(series, tau_grid_points=20)

    # Physical parameter domain constraints [0.5, 24.0] hours
    assert params.beta_0 >= 0.0
    assert params.beta_1 >= 0.0
    assert TAU_MIN_HOURS <= params.tau_hours <= TAU_MAX_HOURS

    # Verify plausible recovery of ground truth (beta0=10, beta1=35, tau=3)
    assert 5.0 <= params.beta_0 <= 20.0
    assert 20.0 <= params.beta_1 <= 50.0
    assert 1.0 <= params.tau_hours <= 6.0
    assert diag["fit_mae_degc"] < 1.5


def test_fit_thermal_model_determinism(synthetic_partitions):
    """Verify fitting runs deterministically producing exact same parameters."""
    fit_df, _, _ = synthetic_partitions
    series = prepare_thermal_series(fit_df, driver_type="apparent_power_kva")

    p1, d1 = fit_thermal_model_parameters(series, tau_grid_points=15)
    p2, d2 = fit_thermal_model_parameters(series, tau_grid_points=15)

    assert p1.beta_0 == p2.beta_0
    assert p1.beta_1 == p2.beta_1
    assert p1.tau_hours == p2.tau_hours
    assert d1 == d2


# ---------------------------------------------------------------------------
# 4. FIT-Only Rolling-Origin Load Driver Selection (K=5)
# ---------------------------------------------------------------------------

def test_select_best_load_driver_on_fit_k5(synthetic_partitions):
    """Verify rolling-origin comparison with K=5 folds selects a winning driver and freezes it."""
    fit_df, _, _ = synthetic_partitions
    winner, candidates = select_best_load_driver_on_fit(fit_df, n_folds=5)

    assert winner.driver_type in ["apparent_power_kva", "rms_current_a"]
    assert winner.reference_value > 0.0
    assert winner.mean_rolling_mae > 0.0
    assert len(candidates) == 2
    assert "apparent_power_kva" in candidates
    assert "rms_current_a" in candidates
    assert len(candidates["apparent_power_kva"].fold_maes) <= 5


# ---------------------------------------------------------------------------
# 5. Baseline Models
# ---------------------------------------------------------------------------

def test_baseline_models(synthetic_partitions):
    """Verify prediction logic of all 3 baselines."""
    fit_df, _, _ = synthetic_partitions
    fit_series = prepare_thermal_series(fit_df)

    # Persistence
    b1 = PersistenceBaseline()
    step_val = b1.predict_step(45.0)
    assert step_val == 45.0
    traj = b1.predict_trajectory(45.0, horizon_steps=8)
    assert len(traj) == 8
    assert np.all(traj == 45.0)

    # Ambient + Median Rise
    b2 = AmbientMedianRiseBaseline.fit(fit_series)
    assert b2.median_rise_degc > 0.0
    traj2 = b2.predict_trajectory(ambient_origin=30.0, horizon_steps=8)
    assert len(traj2) == 8
    assert np.allclose(traj2, 30.0 + b2.median_rise_degc)

    # Static Robust Regression
    b3 = StaticRobustRegressionBaseline.fit(fit_series)
    assert b3.b0 >= 0.0
    assert b3.b1 >= 0.0
    traj3 = b3.predict_trajectory(ambient_origin=30.0, u_origin=0.8, horizon_steps=8)
    assert len(traj3) == 8
    assert np.allclose(traj3, 30.0 + b3.b0 + b3.b1 * (0.8**2))



# ---------------------------------------------------------------------------
# 6. Identifiability Diagnostics & Boundary Hit Checks
# ---------------------------------------------------------------------------

def test_evaluate_identifiability_pass(synthetic_partitions):
    """Verify identifiability pass on adequate synthetic dataset."""
    fit_df, _, _ = synthetic_partitions
    series = prepare_thermal_series(fit_df)
    params = ThermalModelParameters(beta_0=10.0, beta_1=35.0, tau_hours=3.0)

    report = evaluate_identifiability(series, params, tau_cv=0.15)
    assert report.is_identifiable is True
    assert report.fit_samples_count >= 500
    assert report.fit_span_days >= 7.0
    assert report.boundary_hit is False


def test_evaluate_identifiability_boundary_hit(synthetic_partitions):
    """Verify identifiability fails when parameters sit on artificial boundary."""
    fit_df, _, _ = synthetic_partitions
    series = prepare_thermal_series(fit_df)

    # Boundary cases: beta0=0, tau at lower bound 0.5h, or tau at upper bound 24.0h
    params_bound_low = ThermalModelParameters(beta_0=10.0, beta_1=35.0, tau_hours=0.50)
    report_low = evaluate_identifiability(series, params_bound_low, tau_cv=0.15)
    assert report_low.boundary_hit is True
    assert report_low.is_identifiable is False

    params_bound_high = ThermalModelParameters(beta_0=10.0, beta_1=35.0, tau_hours=24.0)
    report_high = evaluate_identifiability(series, params_bound_high, tau_cv=0.15)
    assert report_high.boundary_hit is True
    assert report_high.is_identifiable is False


def test_evaluate_identifiability_instability_gate(synthetic_partitions):
    """Verify identifiability fails when tau CV exceeds the 0.60 engineering threshold."""
    fit_df, _, _ = synthetic_partitions
    series = prepare_thermal_series(fit_df)
    params = ThermalModelParameters(beta_0=10.0, beta_1=35.0, tau_hours=3.0)

    report = evaluate_identifiability(series, params, tau_cv=0.75)
    assert report.is_identifiable is False
    assert any("Parameter instability" in msg for msg in report.diagnostic_messages)


# ---------------------------------------------------------------------------
# 7. Block-Conformal Uncertainty Calibration on CAL
# ---------------------------------------------------------------------------

def test_calibrate_block_conformal_uncertainty(synthetic_partitions):
    """Verify empirical 90% block-conformal calibration on CAL partition."""
    _, cal_df, _ = synthetic_partitions
    params = ThermalModelParameters(beta_0=10.0, beta_1=35.0, tau_hours=3.0)

    conformal = calibrate_block_conformal_uncertainty(
        cal_df=cal_df,
        params=params,
        driver_type="apparent_power_kva",
        reference_value=100.0,
        horizon_steps=8,
    )

    assert conformal.horizon_steps == 8
    assert len(conformal.horizon_scales_degc) == 8
    assert len(conformal.horizon_half_widths_degc) == 8
    assert conformal.block_quantile_90 >= 1.0
    # Every horizon scale must meet or exceed the 0.50 deg C resolution floor
    assert all(s >= MIN_CONFORMAL_SCALE_FLOOR_DEGC for s in conformal.horizon_scales_degc)
    assert all(w > 0.0 for w in conformal.horizon_half_widths_degc)
    assert conformal.calibration_residual_mad > 0.0


def test_conformal_scale_floor_enforcement():
    """Verify that conformal horizon scale never drops below 0.50 deg C even with zero noise."""
    times = [pd.Timestamp("2026-01-01") + pd.Timedelta(minutes=15 * i) for i in range(20)]
    # Perfectly flat constant temperatures
    cal_df = pd.DataFrame({
        "ts": times,
        "OTI": [50.0] * 20,
        "ATI": [30.0] * 20,
        "KVA": [50.0] * 20,
    })
    params = ThermalModelParameters(beta_0=20.0, beta_1=0.0, tau_hours=3.0)

    conformal = calibrate_block_conformal_uncertainty(
        cal_df=cal_df,
        params=params,
        driver_type="apparent_power_kva",
        reference_value=50.0,
        horizon_steps=8,
    )

    assert all(s >= 0.50 for s in conformal.horizon_scales_degc)


# ---------------------------------------------------------------------------
# 8. TEST Holdout Evaluation & Locked Promotion
# ---------------------------------------------------------------------------

def test_evaluate_on_test_partition(synthetic_partitions):
    """Verify holdout evaluation and promotion rule checks on TEST partition."""
    fit_df, cal_df, test_df = synthetic_partitions
    params = ThermalModelParameters(beta_0=10.0, beta_1=35.0, tau_hours=3.0)

    conformal = calibrate_block_conformal_uncertainty(
        cal_df=cal_df,
        params=params,
        driver_type="apparent_power_kva",
        reference_value=100.0,
    )

    fit_series = prepare_thermal_series(fit_df)
    baselines = {
        "persistence": PersistenceBaseline(),
        "ambient_median_rise": AmbientMedianRiseBaseline.fit(fit_series),
        "static_robust_regression": StaticRobustRegressionBaseline.fit(fit_series),
    }

    model_metrics, b_metrics, decision, horizon_breakdown, sec_diag = evaluate_on_test_partition(
        test_df=test_df,
        params=params,
        conformal=conformal,
        baselines=baselines,
        driver_type="apparent_power_kva",
        reference_value=100.0,
    )

    assert model_metrics.mae_degc > 0.0
    assert "persistence" in b_metrics
    assert decision.status in ["PROMOTED", "NOT_PROMOTED"]
    assert len(decision.reasons) > 0
    assert len(horizon_breakdown) == 8
    assert "greybox_mae_degc" in sec_diag


# ---------------------------------------------------------------------------
# 9. Full End-to-End Calibration Pipeline & Artifact Roundtrip
# ---------------------------------------------------------------------------

def test_run_full_calibration_pipeline_and_json_roundtrip(synthetic_partitions, tmp_path):
    """Verify full calibration orchestrator and artifact serialization / deserialization."""
    fit_df, cal_df, test_df = synthetic_partitions

    artifact = run_full_calibration_pipeline(
        fit_df=fit_df,
        cal_df=cal_df,
        test_df=test_df,
        asset_id="test_transformer_01",
        model_version="test_v1",
    )

    assert isinstance(artifact, CalibratedThermalModelArtifact)
    assert artifact.asset_id == "test_transformer_01"
    assert artifact.selected_load_driver in ["apparent_power_kva", "rms_current_a"]
    assert artifact.parameters.beta_0 >= 0.0
    assert artifact.parameters.beta_1 >= 0.0
    assert TAU_MIN_HOURS <= artifact.parameters.tau_hours <= TAU_MAX_HOURS

    # Save to disk and reload
    artifact_path = tmp_path / "calibrated_model.json"
    artifact.save_json(artifact_path)
    assert artifact_path.exists()

    loaded_artifact = CalibratedThermalModelArtifact.load_json(artifact_path)
    assert loaded_artifact.asset_id == artifact.asset_id
    assert loaded_artifact.parameters == artifact.parameters
    assert loaded_artifact.conformal_uncertainty == artifact.conformal_uncertainty
    assert loaded_artifact.promotion.status == artifact.promotion.status
    assert loaded_artifact.schema_version == "1.1.0"
    assert loaded_artifact.promotion.primary_evaluation_horizon == "2_hour_multi_step_trajectory"
    assert "horizon_breakdown" in loaded_artifact.metadata
    assert "secondary_1step_closed_loop" in loaded_artifact.metadata
    assert len(loaded_artifact.metadata["horizon_breakdown"]) == 8


# ---------------------------------------------------------------------------
# 10. Multi-Step 2-Hour Trajectory vs 1-Step Diagnostic Tests
# ---------------------------------------------------------------------------

def test_multi_step_trajectory_evaluation_semantics(synthetic_partitions):
    """Verify 2-hour trajectory evaluation computes per-horizon metrics and aggregates correctly."""
    fit_df, cal_df, test_df = synthetic_partitions
    params = ThermalModelParameters(beta_0=10.0, beta_1=35.0, tau_hours=3.0)

    conformal = calibrate_block_conformal_uncertainty(
        cal_df=cal_df,
        params=params,
        driver_type="apparent_power_kva",
        reference_value=100.0,
        horizon_steps=8,
    )

    fit_series = prepare_thermal_series(fit_df)
    baselines = {
        "persistence": PersistenceBaseline(),
        "ambient_median_rise": AmbientMedianRiseBaseline.fit(fit_series),
        "static_robust_regression": StaticRobustRegressionBaseline.fit(fit_series),
    }

    model_metrics, b_metrics, decision, horizon_breakdown, sec_diag = evaluate_on_test_partition(
        test_df=test_df,
        params=params,
        conformal=conformal,
        baselines=baselines,
        driver_type="apparent_power_kva",
        reference_value=100.0,
        horizon_steps=8,
    )

    # Primary evaluation should be 2-hour trajectory
    assert decision.primary_evaluation_horizon == "2_hour_multi_step_trajectory"
    assert decision.secondary_1step_closed_loop_mae_improvement_pct is not None
    assert len(horizon_breakdown) == 8

    # Check each horizon step h=1..8
    for i, h_info in enumerate(horizon_breakdown):
        assert h_info.horizon_step == i + 1
        assert h_info.horizon_minutes == (i + 1) * 15
        assert h_info.model_mae_degc >= 0.0
        assert h_info.model_rmse_degc >= 0.0
        assert h_info.persistence_mae_degc >= 0.0

    # Baselines all evaluated
    assert "persistence" in b_metrics
    assert "ambient_median_rise" in b_metrics
    assert "static_robust_regression" in b_metrics

