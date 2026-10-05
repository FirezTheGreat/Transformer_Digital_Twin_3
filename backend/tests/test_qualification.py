"""Tests for Capability-Specific Thermal Qualification Architecture.

Verifies:
1. Frozen artifact schema v1.2.0 and qualification metadata integrity.
2. Independent qualification dimensions (all 7 dimensions verified).
3. Shadow descriptive mode: continuous ODE stepping and residual computation under DESCRIPTIVE_ONLY.
4. CUSUM accumulator freezing/bypassing when cusum_qualification != QUALIFIED.
5. Anomaly evidence suppression when residual_anomaly_qualification != QUALIFIED.
6. Scenario projection gating based on scenario_qualification.
7. CapabilityEvaluator C2 sub-capability (thermal_residual_shadow) and C3 forecast gating.
8. Hard telemetry failure precedence over qualification states.
"""

from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import pytest

from app.engine.capability import CapabilityEvaluator, evaluate_capabilities
from app.engine.scenario_simulator import ScenarioSimulator
from app.engine.thermal import ThermalModelParameters
from app.engine.thermal_fallback import (
    CUSUMDirection,
    ThermalFallbackGate,
    ThermalFallbackReason,
    ThermalTrustState,
)
from app.models.capability import CapabilityTier
from app.models.scenario import ScenarioRequest
from app.models.telemetry import CanonicalEvent, Measurement, MeasurementQuality, QualitySeverity
from app.models.thermal_artifact import (
    CalibratedThermalModelArtifact,
    QualificationStatus,
    ThermalModelQualification,
)
from app.models.twin_state import ThermalLatentState, TwinState


@pytest.fixture
def calibrated_artifact_path() -> Path:
    p = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "calibrated_thermal_model.json"
    assert p.exists(), f"Calibrated model artifact not found at {p}"
    return p


@pytest.fixture
def loaded_artifact(calibrated_artifact_path: Path) -> CalibratedThermalModelArtifact:
    return CalibratedThermalModelArtifact.load_json(calibrated_artifact_path)


# ==============================================================================
# 1. Artifact Schema & Qualification Metadata Integrity
# ==============================================================================

def test_frozen_artifact_qualification_metadata(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that the frozen Tripura artifact adheres to schema v1.2.0 with exact qualification states."""
    assert loaded_artifact.schema_version == "1.2.0"
    assert loaded_artifact.asset_id == "tripura_dt_01"
    assert loaded_artifact.promotion.status == "NOT_PROMOTED"

    # Verify all 7 qualification dimensions are explicitly present and match expected state
    q = loaded_artifact.qualification
    assert q is not None
    assert q.parameter_interpretability == QualificationStatus.UNVERIFIED
    assert q.forecast_qualification == QualificationStatus.PENDING_VALIDATION
    assert q.scenario_qualification == QualificationStatus.PENDING_VALIDATION
    assert q.residual_display_qualification == QualificationStatus.DESCRIPTIVE_ONLY
    assert q.residual_anomaly_qualification == QualificationStatus.NOT_QUALIFIED
    assert q.cusum_qualification == QualificationStatus.DISABLED
    assert q.maintenance_inference_qualification == QualificationStatus.DISABLED

    # Verify promotion reasons and notes are preserved
    assert len(loaded_artifact.promotion.reasons) >= 1
    assert any("boundary" in reason.lower() for reason in loaded_artifact.promotion.reasons)

    # Verify deterministic dimension_reasons dictionary is populated for all 7 dimensions
    reasons = q.dimension_reasons
    assert len(reasons) == 7
    for dim in [
        "parameter_interpretability",
        "forecast_qualification",
        "scenario_qualification",
        "residual_display_qualification",
        "residual_anomaly_qualification",
        "cusum_qualification",
        "maintenance_inference_qualification",
    ]:
        assert dim in reasons
        assert len(reasons[dim]) > 10
        assert q.get_reason(dim) == reasons[dim]


def test_predictive_evidence_vs_causal_identifiability_separation(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that predictive accuracy evidence does NOT imply physical identifiability or causal trust."""
    # 1. Predictive performance evidence is verified and present
    assert loaded_artifact.test_metrics.mae_degc == 1.6527
    assert loaded_artifact.baselines["persistence"].mae_degc == 2.0300
    assert loaded_artifact.promotion.mae_improvement_pct == pytest.approx(18.59, abs=0.05)
    assert loaded_artifact.test_metrics.marginal_coverage_90_pct == pytest.approx(97.33, abs=0.05)

    # 2. Yet Physical Identifiability is UNVERIFIED due to tau hitting lower bound
    assert loaded_artifact.parameters.tau_hours == 0.5000
    assert loaded_artifact.identifiability.boundary_hit is True
    assert loaded_artifact.identifiability.is_identifiable is False
    assert loaded_artifact.qualification.parameter_interpretability == QualificationStatus.UNVERIFIED

    # 3. And Causal / Anomaly / Maintenance Trust are explicitly NOT QUALIFIED or DISABLED
    assert loaded_artifact.qualification.residual_anomaly_qualification == QualificationStatus.NOT_QUALIFIED
    assert loaded_artifact.qualification.cusum_qualification == QualificationStatus.DISABLED
    assert loaded_artifact.qualification.maintenance_inference_qualification == QualificationStatus.DISABLED


def test_artifact_historical_integrity_invariants(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that historical calibration values, parameters, hashes, and promotion status are unchanged."""
    assert loaded_artifact.parameters.beta_0 == 1.0880
    assert loaded_artifact.parameters.beta_1 == 2.8979
    assert loaded_artifact.parameters.tau_hours == 0.5000
    assert loaded_artifact.selected_load_driver == "rms_current_a"
    assert loaded_artifact.load_driver_reference_value == pytest.approx(153.8652, abs=1e-3)
    assert loaded_artifact.promotion.status == "NOT_PROMOTED"

    # Dataset hashes
    hashes = loaded_artifact.dataset_hashes
    assert "tripura_fit_sha256" in hashes and len(hashes["tripura_fit_sha256"]) == 64
    assert "tripura_calibration_sha256" in hashes and len(hashes["tripura_calibration_sha256"]) == 64
    assert "tripura_test_sha256" in hashes and len(hashes["tripura_test_sha256"]) == 64


# ==============================================================================
# 2. Shadow Descriptive Mode (Continuous ODE Stepping & Residual Display)
# ==============================================================================

def test_shadow_descriptive_continuous_ode_stepping(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that under DESCRIPTIVE_ONLY, the gate steps the ODE continuously and produces shadow residuals."""
    gate = ThermalFallbackGate.from_artifact(loaded_artifact)
    t0 = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    # 1. Warm-up steps
    for i in range(gate.min_warmup_samples):
        out = gate.evaluate_step(
            event_time_utc=t0 + timedelta(minutes=15 * i),
            top_oil_obs=45.0 + i * 0.5,
            ambient_obs=28.0,
            load_obs=100.0,
        )
        assert out.trust_state == ThermalTrustState.WARMUP
        assert out.is_warmup is True
        assert out.is_fallback_active is False

    # 2. Post-warmup step: transitions to SHADOW_DESCRIPTIVE (not FALLBACK_PERSISTENCE!)
    t_post = t0 + timedelta(minutes=15 * gate.min_warmup_samples)
    out_post = gate.evaluate_step(
        event_time_utc=t_post,
        top_oil_obs=48.0,
        ambient_obs=28.0,
        load_obs=100.0,
    )

    assert out_post.trust_state == ThermalTrustState.SHADOW_DESCRIPTIVE
    assert out_post.is_fallback_active is False
    assert out_post.is_warmup is False
    assert out_post.free_running_top_oil_degc is not None
    assert out_post.expected_top_oil_degc is not None
    assert out_post.thermal_residual_degc is not None
    # Shadow residual is computed: observed - expected
    assert out_post.thermal_residual_degc == round(48.0 - out_post.expected_top_oil_degc, 4)
    # What-if scenario projection is NOT enabled in shadow descriptive mode
    assert out_post.what_if_enabled is False


# ==============================================================================
# 3. CUSUM Accumulator Freezing & Anomaly Suppression
# ==============================================================================

def test_cusum_freezing_and_evidence_suppression(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that when cusum_qualification=DISABLED and residual_anomaly_qualification=NOT_QUALIFIED,
    large persistent residuals do NOT trip CUSUM alarms or emit thermal deviation evidence."""
    gate = ThermalFallbackGate.from_artifact(loaded_artifact)
    t0 = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    # Run through warmup
    for i in range(gate.min_warmup_samples):
        gate.evaluate_step(
            event_time_utc=t0 + timedelta(minutes=15 * i),
            top_oil_obs=45.0,
            ambient_obs=28.0,
            load_obs=100.0,
        )

    # Inject large anomalous temperature (+15 degC above expected) for 10 steps
    for step in range(10):
        t = t0 + timedelta(minutes=15 * (gate.min_warmup_samples + step))
        out = gate.evaluate_step(
            event_time_utc=t,
            top_oil_obs=65.0,
            ambient_obs=28.0,
            load_obs=100.0,
        )
        assert out.trust_state == ThermalTrustState.SHADOW_DESCRIPTIVE
        # CUSUM accumulators must remain frozen at 0
        assert out.cusum_pos == 0.0
        assert out.cusum_neg == 0.0
        assert out.cusum_alarm_active is False
        assert out.standardized_residual_z is None
        # No thermal deviation evidence emitted
        assert len(out.emitted_evidence) == 0


# ==============================================================================
# 4. Scenario Simulator Qualification Gating
# ==============================================================================

def test_scenario_simulator_qualification_gating(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify scenario simulator behavior with PENDING_VALIDATION vs QUALIFIED scenario qualification."""
    # 1. With frozen artifact (scenario_qualification = PENDING_VALIDATION)
    sim = ScenarioSimulator.from_artifact(loaded_artifact)
    t0 = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    res = sim.run_projection(
        origin_time_utc=t0,
        origin_top_oil_degc=48.0,
        origin_ambient_degc=28.0,
        origin_load_value=100.0,
        trust_state=ThermalTrustState.SHADOW_DESCRIPTIVE,
    )
    assert res.is_enabled is False
    assert "not qualified" in res.disabled_reason.lower() or "shadow descriptive" in res.disabled_reason.lower()

    # 2. With qualified override
    sim_qualified = ScenarioSimulator.from_artifact(loaded_artifact, is_model_promoted_override=True)
    res_qualified = sim_qualified.run_projection(
        origin_time_utc=t0,
        origin_top_oil_degc=48.0,
        origin_ambient_degc=28.0,
        origin_load_value=100.0,
        trust_state=ThermalTrustState.MODEL_HEALTHY,
    )
    assert res_qualified.is_enabled is True
    assert len(res_qualified.trajectory) == 8


# ==============================================================================
# 5. Hard Telemetry Failure Overrides
# ==============================================================================

def test_hard_telemetry_failure_overrides_qualification(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify that telemetry corruption, bad quality, physical impossibility, or monitoring gaps
    immediately trip FALLBACK_PERSISTENCE regardless of qualification status."""
    gate = ThermalFallbackGate.from_artifact(loaded_artifact)
    t0 = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    # 1. Missing Top-Oil
    out_no_oti = gate.evaluate_step(
        event_time_utc=t0,
        top_oil_obs=None,
        ambient_obs=28.0,
        load_obs=100.0,
    )
    assert out_no_oti.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE
    assert ThermalFallbackReason.MISSING_TOP_OIL in out_no_oti.fallback_reasons

    # 2. Physical impossibility (top-oil colder than ambient by > 10 degC)
    out_impossible = gate.evaluate_step(
        event_time_utc=t0 + timedelta(minutes=15),
        top_oil_obs=15.0,
        ambient_obs=35.0,
        load_obs=100.0,
    )
    assert out_impossible.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE
    assert ThermalFallbackReason.PHYSICAL_IMPOSSIBILITY in out_impossible.fallback_reasons

    # 3. Bad Quality Measurement
    bad_oti = Measurement(
        signal_id="top_oil_temperature",
        value=50.0,
        value_type="float",
        unit_ucum="Cel",
        original_name="oti",
        original_value="50.0",
        original_unit="Cel",
        quality=MeasurementQuality(severity=QualitySeverity.BAD, flags=["SENSOR_FAILURE"]),
    )
    out_bad_quality = gate.evaluate_step(
        event_time_utc=t0 + timedelta(minutes=30),
        top_oil_obs=bad_oti,
        ambient_obs=28.0,
        load_obs=100.0,
    )
    assert out_bad_quality.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE
    assert ThermalFallbackReason.MISSING_TOP_OIL in out_bad_quality.fallback_reasons


# ==============================================================================
# 6. Capability Manifest Integration (C2 Shadow vs C3 Forecast)
# ==============================================================================

def test_capability_evaluator_with_qualification(loaded_artifact: CalibratedThermalModelArtifact):
    """Verify CapabilityEvaluator correctly exposes C2:thermal_residual_shadow and gates C3."""
    now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    obs = {
        "top_oil_temperature": Measurement(
            signal_id="top_oil_temperature",
            value=52.0,
            value_type="float",
            unit_ucum="Cel",
            original_name="oti",
            original_value="52.0",
            original_unit="Cel",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD),
        ),
        "ambient_temperature": Measurement(
            signal_id="ambient_temperature",
            value=28.0,
            value_type="float",
            unit_ucum="Cel",
            original_name="ati",
            original_value="28.0",
            original_unit="Cel",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD),
        ),
        "apparent_power": Measurement(
            signal_id="apparent_power",
            value=45.0,
            value_type="float",
            unit_ucum="kVA",
            original_name="s",
            original_value="45.0",
            original_unit="kVA",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD),
        ),
    }

    state = TwinState(
        asset_id="tripura_dt_01",
        state_time_utc=now,
        last_processed_event_id="evt_001",
        event_time_watermark_utc=now,
        state_sequence=1,
        current_observations=obs,
        thermal_latent=ThermalLatentState(
            model_status="DESCRIPTIVE_ONLY",
            last_free_running_top_oil_degc=51.8,
            top_oil_expected_degc=51.8,
        ),
        exposure_state={"time_above_bands_s": {}, "equivalent_ageing_hours": None, "is_ageing_enabled": False},
        state_hash="dummy_hash",
    )

    manifest = evaluate_capabilities(
        state=state,
        model_version=loaded_artifact.model_version,
        is_model_promoted=False,
        qualification=loaded_artifact.qualification,
    )

    # Highest tier is C2_THERMAL_DESCRIPTIVE
    assert manifest.highest_tier == CapabilityTier.C2_THERMAL_DESCRIPTIVE
    assert manifest.capabilities["C0"].enabled is True
    assert manifest.capabilities["C1"].enabled is True
    assert manifest.capabilities["C2"].enabled is True
    assert manifest.capabilities["top_oil_monitoring"].enabled is True

    # Sub-capability thermal_residual_shadow is enabled with B grade (descriptive shadow)
    assert manifest.capabilities["thermal_residual_shadow"].enabled is True
    assert manifest.capabilities["thermal_residual_shadow"].evidence_grade == "B"
    assert manifest.capabilities["thermal_residual_shadow"].model_status == "DESCRIPTIVE_ONLY"

    # C3 is disabled because forecast_qualification is PENDING_VALIDATION
    assert manifest.capabilities["C3"].enabled is False
    assert "MODEL_NOT_PROMOTED" in manifest.capabilities["C3"].disabled_reason_codes
