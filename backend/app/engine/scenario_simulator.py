"""Phase 4.4 — 2-Hour What-If Scenario Projection Engine.

Implements the deterministic 2-hour forward what-if scenario simulator:
1. Validates current twin/thermal state and scenario assumptions.
2. Gates execution against the thermal capability trust state (disabled in WARMUP or FALLBACK).
3. Projects top-oil temperature forward exactly 8 x 15-minute steps (h = 1..8, Delta_t = 0.25h)
   using the frozen first-order grey-box thermal ODE without future observed OTI feedback.
4. Simulates both the user what-if trajectory and the baseline trajectory (holding current conditions).
5. Computes asymptotic steady-state theta*, empirical 90% block-conformal bounds (W_1..W_8),
   and detects threshold crossings (warning / critical limits) and duration above thresholds.
6. Detects load/ambient extrapolation outside calibrated bounds and applies documented uncertainty widening.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Sequence

from app.engine.thermal import (
    ThermalModelParameters,
    calculate_steady_state_temp,
    step_thermal_ode,
)
from app.engine.thermal_fallback import ThermalTrustState
from app.models.scenario import (
    ScenarioProjectionResult,
    ScenarioProjectionStep,
    ScenarioRequest,
)
from app.models.telemetry import Measurement, QualitySeverity
from app.models.thermal_artifact import (
    CalibratedThermalModelArtifact,
    QualificationStatus,
    ThermalModelQualification,
)
from app.models.twin_state import TwinState


# Default empirical 90% conformal half-widths (W_1..W_8) if artifact not provided
DEFAULT_CONFORMAL_HALF_WIDTHS_DEGC = [
    2.9945, 3.1057, 3.3670, 4.0787, 5.0427, 6.2871, 8.2012, 9.5585
]
EXTRAPOLATION_LOAD_INDEX_THRESHOLD = 1.20
EXTRAPOLATION_AMBIENT_MAX_DEGC = 55.0
EXTRAPOLATION_AMBIENT_MIN_DEGC = -20.0
EXTRAPOLATION_UNCERTAINTY_MULTIPLIER = 1.25


class ScenarioSimulator:
    """Deterministic 2-hour what-if thermal projection engine."""

    def __init__(
        self,
        asset_id: str,
        params: ThermalModelParameters,
        load_driver_reference: float = 153.865,
        load_driver_type: str = "rms_current_a",
        is_model_promoted: bool = True,
        qualification: Optional[ThermalModelQualification] = None,
        conformal_half_widths_degc: Optional[Sequence[float]] = None,
        model_version: str = "greybox_v1_0",
        conformal_quantile_90: float = 5.9891,
    ) -> None:
        self.asset_id = str(asset_id)
        self.params = params
        self.load_driver_reference = max(float(load_driver_reference), 1e-4)
        self.load_driver_type = str(load_driver_type)
        self.is_model_promoted = bool(is_model_promoted)
        self.qualification = qualification
        self.conformal_half_widths = list(
            conformal_half_widths_degc
            if conformal_half_widths_degc and len(conformal_half_widths_degc) == 8
            else DEFAULT_CONFORMAL_HALF_WIDTHS_DEGC
        )
        self.model_version = str(model_version)
        self.conformal_quantile_90 = float(conformal_quantile_90)

    @classmethod
    def from_artifact(
        cls,
        artifact: CalibratedThermalModelArtifact,
        is_model_promoted_override: Optional[bool] = None,
    ) -> ScenarioSimulator:
        """Construct simulator directly from a frozen CalibratedThermalModelArtifact."""
        if artifact.parameters is not None:
            params = ThermalModelParameters(
                beta_0=artifact.parameters.beta_0,
                beta_1=artifact.parameters.beta_1,
                tau_hours=artifact.parameters.tau_hours,
            )
            load_driver_ref = (
                artifact.load_driver_reference_value
                if artifact.load_driver_reference_value is not None
                else 153.865
            )
            load_driver_t = artifact.selected_load_driver or "rms_current_a"
        else:
            params = ThermalModelParameters(beta_0=1.0, beta_1=1.0, tau_hours=1.0)
            load_driver_ref = 100.0
            load_driver_t = "uncalibrated"

        is_promoted = (
            is_model_promoted_override
            if is_model_promoted_override is not None
            else (artifact.promotion.status == "PROMOTED")
        )

        if artifact.parameters is None or artifact.promotion.status == "UNCALIBRATED":
            is_promoted = False
            qualification = None
        elif is_model_promoted_override is True:
            qualification = ThermalModelQualification(
                parameter_interpretability=artifact.qualification.parameter_interpretability if artifact.qualification else QualificationStatus.QUALIFIED,
                forecast_qualification=QualificationStatus.QUALIFIED,
                scenario_qualification=QualificationStatus.QUALIFIED,
                residual_display_qualification=QualificationStatus.QUALIFIED,
                residual_anomaly_qualification=QualificationStatus.QUALIFIED,
                cusum_qualification=QualificationStatus.QUALIFIED,
                maintenance_inference_qualification=QualificationStatus.QUALIFIED,
            )
        elif is_model_promoted_override is False:
            qualification = ThermalModelQualification(
                parameter_interpretability=QualificationStatus.UNVERIFIED,
                forecast_qualification=QualificationStatus.NOT_QUALIFIED,
                scenario_qualification=QualificationStatus.NOT_QUALIFIED,
                residual_display_qualification=QualificationStatus.NOT_QUALIFIED,
                residual_anomaly_qualification=QualificationStatus.NOT_QUALIFIED,
                cusum_qualification=QualificationStatus.DISABLED,
                maintenance_inference_qualification=QualificationStatus.DISABLED,
            )
        else:
            qualification = artifact.qualification

        if artifact.conformal_uncertainty is not None:
            widths = (
                artifact.conformal_uncertainty.horizon_half_widths_degc
                if artifact.conformal_uncertainty.horizon_half_widths_degc
                else DEFAULT_CONFORMAL_HALF_WIDTHS_DEGC
            )
            q90 = artifact.conformal_uncertainty.block_quantile_90 or 5.9891
        else:
            widths = DEFAULT_CONFORMAL_HALF_WIDTHS_DEGC
            q90 = 5.9891

        return cls(
            asset_id=artifact.asset_id,
            params=params,
            load_driver_reference=load_driver_ref,
            load_driver_type=load_driver_t,
            is_model_promoted=is_promoted,
            qualification=qualification,
            conformal_half_widths_degc=widths,
            model_version=artifact.model_version,
            conformal_quantile_90=q90,
        )

    def run_projection(
        self,
        origin_time_utc: datetime,
        origin_top_oil_degc: Optional[float],
        origin_ambient_degc: Optional[float],
        origin_load_value: Optional[float],
        trust_state: ThermalTrustState = ThermalTrustState.MODEL_HEALTHY,
        scenario_request: Optional[ScenarioRequest] = None,
        is_load_value_already_index_u: bool = False,
    ) -> ScenarioProjectionResult:
        """Execute a 2-hour what-if scenario projection from a known forecast origin.

        Args:
            origin_time_utc: Timestamp at forecast origin in UTC.
            origin_top_oil_degc: Observed top-oil temperature at origin (degC).
            origin_ambient_degc: Observed ambient temperature at origin (degC).
            origin_load_value: Observed load at origin (physical value or index u).
            trust_state: Active thermal capability trust state.
            scenario_request: Requested scenario parameters (or default if None).
            is_load_value_already_index_u: True if origin_load_value is already dimensionless u.

        Returns:
            ScenarioProjectionResult: Complete 8-step projection trajectory and diagnostics.
        """
        if origin_time_utc.tzinfo is None:
            origin_time_utc = origin_time_utc.replace(tzinfo=timezone.utc)

        req = scenario_request or ScenarioRequest()

        # 1. Capability & Trust State Gating
        is_enabled = True
        disabled_reason: Optional[str] = None

        is_scenario_qualified = (
            (self.qualification.scenario_qualification == QualificationStatus.QUALIFIED)
            if self.qualification is not None
            else self.is_model_promoted
        )

        if not is_scenario_qualified:
            is_enabled = False
            disabled_reason = "Thermal scenario projection disabled: scenario capability is not qualified."
        elif trust_state == ThermalTrustState.FALLBACK_PERSISTENCE:
            is_enabled = False
            disabled_reason = "Thermal scenario projection disabled: thermal model is in fallback persistence mode."
        elif trust_state == ThermalTrustState.WARMUP:
            is_enabled = False
            disabled_reason = "Thermal scenario projection disabled: thermal model is in warmup phase."
        elif trust_state == ThermalTrustState.SHADOW_DESCRIPTIVE:
            is_enabled = False
            disabled_reason = "Thermal scenario projection disabled: thermal model is operating in shadow descriptive mode."

        # Check telemetry sufficiency at origin
        if (
            origin_top_oil_degc is None
            or origin_ambient_degc is None
            or origin_load_value is None
            or not math.isfinite(origin_top_oil_degc)
            or not math.isfinite(origin_ambient_degc)
            or not math.isfinite(origin_load_value)
        ):
            is_enabled = False
            disabled_reason = disabled_reason or "Thermal scenario projection disabled: missing valid origin telemetry."

        # Compute origin load index u
        if origin_load_value is not None and math.isfinite(origin_load_value):
            if is_load_value_already_index_u:
                origin_u = max(0.0, float(origin_load_value))
            else:
                origin_u = max(0.0, float(origin_load_value) / self.load_driver_reference)
        else:
            origin_u = 0.0

        t_oil_origin = float(origin_top_oil_degc) if (origin_top_oil_degc is not None and math.isfinite(origin_top_oil_degc)) else 0.0
        t_amb_origin = float(origin_ambient_degc) if (origin_ambient_degc is not None and math.isfinite(origin_ambient_degc)) else 0.0

        # Compute scenario inputs
        if req.target_ambient_degc is not None:
            scen_amb = float(req.target_ambient_degc)
        else:
            scen_amb = t_amb_origin + float(req.ambient_delta_degc or 0.0)

        if req.target_load_u is not None:
            scen_u = float(req.target_load_u)
        elif req.target_load_value is not None:
            scen_u = float(req.target_load_value) / self.load_driver_reference
        else:
            scen_u = origin_u * float(req.load_multiplier if req.load_multiplier is not None else 1.0)
        scen_u = max(0.0, scen_u)

        # Extrapolation check
        is_extrapolated = False
        extrap_warnings: List[str] = []
        if scen_u > EXTRAPOLATION_LOAD_INDEX_THRESHOLD:
            is_extrapolated = True
            extrap_warnings.append(
                f"Scenario load index u={scen_u:.2f} exceeds calibrated reference domain (u <= {EXTRAPOLATION_LOAD_INDEX_THRESHOLD:.2f})."
            )
        if scen_amb > EXTRAPOLATION_AMBIENT_MAX_DEGC or scen_amb < EXTRAPOLATION_AMBIENT_MIN_DEGC:
            is_extrapolated = True
            extrap_warnings.append(
                f"Scenario ambient {scen_amb:.1f}°C is outside standard calibrated range [{EXTRAPOLATION_AMBIENT_MIN_DEGC}, {EXTRAPOLATION_AMBIENT_MAX_DEGC}]°C."
            )

        extrap_warning_str = " ".join(extrap_warnings) if extrap_warnings else None
        width_multiplier = EXTRAPOLATION_UNCERTAINTY_MULTIPLIER if is_extrapolated else 1.0

        # If disabled, return early with provenance
        if not is_enabled:
            return ScenarioProjectionResult(
                asset_id=self.asset_id,
                origin_time_utc=origin_time_utc,
                origin_top_oil_degc=round(t_oil_origin, 2),
                origin_ambient_degc=round(t_amb_origin, 2),
                origin_load_u=round(origin_u, 4),
                scenario_ambient_degc=round(scen_amb, 2),
                scenario_load_u=round(scen_u, 4),
                is_enabled=False,
                trust_state=trust_state,
                disabled_reason=disabled_reason,
                is_extrapolated=is_extrapolated,
                extrapolation_warning=extrap_warning_str,
                trajectory=[],
                peak_projected_top_oil_degc=None,
                asymptotic_steady_state_degc=None,
                earliest_warning_crossing_minutes=None,
                earliest_critical_crossing_minutes=None,
                time_above_warning_minutes=0,
                time_above_critical_minutes=0,
                provenance=self._get_provenance(),
            )

        # 2. Execute 8-Step Forward Rollout
        trajectory: List[ScenarioProjectionStep] = []
        current_scen_top_oil = t_oil_origin
        current_base_top_oil = t_oil_origin

        theta_star_scen = calculate_steady_state_temp(scen_amb, scen_u, self.params)

        warning_thresh = req.warning_threshold_degc
        critical_thresh = req.critical_threshold_degc

        earliest_warn_min: Optional[int] = None
        earliest_crit_min: Optional[int] = None
        count_above_warn = 0
        count_above_crit = 0

        dt_step_hours = 0.25

        for h in range(1, req.horizon_steps + 1):
            horizon_min = h * 15
            step_time = origin_time_utc + timedelta(minutes=horizon_min)

            # Integrate what-if scenario ODE
            next_scen_top_oil = step_thermal_ode(
                t_prev_degc=current_scen_top_oil,
                ambient_degc=scen_amb,
                u_load=scen_u,
                dt_hours=dt_step_hours,
                params=self.params,
            )
            current_scen_top_oil = next_scen_top_oil

            # Integrate baseline ODE (current conditions held constant)
            next_base_top_oil = step_thermal_ode(
                t_prev_degc=current_base_top_oil,
                ambient_degc=t_amb_origin,
                u_load=origin_u,
                dt_hours=dt_step_hours,
                params=self.params,
            )
            current_base_top_oil = next_base_top_oil

            # Conformal bounds
            w_h = self.conformal_half_widths[h - 1] * width_multiplier
            c_low = current_scen_top_oil - w_h
            c_high = current_scen_top_oil + w_h

            # Threshold crossing checks
            if warning_thresh is not None and current_scen_top_oil >= warning_thresh:
                count_above_warn += 1
                if earliest_warn_min is None:
                    earliest_warn_min = horizon_min

            if critical_thresh is not None and current_scen_top_oil >= critical_thresh:
                count_above_crit += 1
                if earliest_crit_min is None:
                    earliest_crit_min = horizon_min

            trajectory.append(
                ScenarioProjectionStep(
                    horizon_step=h,
                    horizon_minutes=horizon_min,
                    projected_time_utc=step_time,
                    projected_top_oil_degc=round(current_scen_top_oil, 4),
                    projected_rise_over_ambient_degc=round(current_scen_top_oil - scen_amb, 4),
                    asymptotic_steady_state_degc=round(theta_star_scen, 4),
                    conformal_lower_degc=round(c_low, 4),
                    conformal_upper_degc=round(c_high, 4),
                    conformal_half_width_degc=round(w_h, 4),
                    baseline_top_oil_degc=round(current_base_top_oil, 4),
                    scenario_delta_degc=round(current_scen_top_oil - current_base_top_oil, 4),
                )
            )

        peak_top_oil = max(step.projected_top_oil_degc for step in trajectory)

        return ScenarioProjectionResult(
            asset_id=self.asset_id,
            origin_time_utc=origin_time_utc,
            origin_top_oil_degc=round(t_oil_origin, 2),
            origin_ambient_degc=round(t_amb_origin, 2),
            origin_load_u=round(origin_u, 4),
            scenario_ambient_degc=round(scen_amb, 2),
            scenario_load_u=round(scen_u, 4),
            is_enabled=True,
            trust_state=trust_state,
            disabled_reason=None,
            is_extrapolated=is_extrapolated,
            extrapolation_warning=extrap_warning_str,
            trajectory=trajectory,
            peak_projected_top_oil_degc=round(peak_top_oil, 4),
            asymptotic_steady_state_degc=round(theta_star_scen, 4),
            earliest_warning_crossing_minutes=earliest_warn_min,
            earliest_critical_crossing_minutes=earliest_crit_min,
            time_above_warning_minutes=count_above_warn * 15,
            time_above_critical_minutes=count_above_crit * 15,
            provenance=self._get_provenance(),
        )

    def run_projection_from_twin_state(
        self,
        twin_state: TwinState,
        scenario_request: Optional[ScenarioRequest] = None,
    ) -> ScenarioProjectionResult:
        """Convenience method to execute scenario projection directly from a TwinState."""
        obs = twin_state.current_observations

        m_oil = obs.get("top_oil_temperature") or obs.get("top_oil")
        m_amb = obs.get("ambient_temperature") or obs.get("ambient")

        t_oil = float(m_oil.value) if (m_oil and m_oil.value is not None and m_oil.quality.severity != QualitySeverity.BAD) else None
        t_amb = float(m_amb.value) if (m_amb and m_amb.value is not None and m_amb.quality.severity != QualitySeverity.BAD) else None

        # Load value
        load_val: Optional[float] = None
        is_u = False
        if twin_state.derived_electrical:
            rel_u = (
                getattr(twin_state.derived_electrical, "relative_load_index", None)
                or getattr(twin_state.derived_electrical, "relative_load_index_u", None)
            )
            if rel_u is not None:
                load_val = rel_u
                is_u = True
        if load_val is None:
            m_s = obs.get("apparent_power_total") or obs.get("apparent_power_kva") or obs.get("apparent_power")
            m_i1 = obs.get("current_l1")
            m_i2 = obs.get("current_l2")
            m_i3 = obs.get("current_l3")
            if m_i1 and m_i2 and m_i3 and m_i1.value and m_i2.value and m_i3.value:
                i1, i2, i3 = float(m_i1.value), float(m_i2.value), float(m_i3.value)
                load_val = math.sqrt((i1**2 + i2**2 + i3**2) / 3.0)
            elif m_s and m_s.value is not None:
                load_val = float(m_s.value)

        # Trust state
        model_status = twin_state.thermal_latent.model_status
        if model_status == "WARMUP" or twin_state.thermal_latent.warmup_samples_remaining > 0:
            trust_state = ThermalTrustState.WARMUP
        elif model_status == "FALLBACK_PERSISTENCE" or model_status != "PROMOTED":
            trust_state = ThermalTrustState.FALLBACK_PERSISTENCE
        else:
            trust_state = ThermalTrustState.MODEL_HEALTHY

        return self.run_projection(
            origin_time_utc=twin_state.state_time_utc,
            origin_top_oil_degc=t_oil,
            origin_ambient_degc=t_amb,
            origin_load_value=load_val,
            trust_state=trust_state,
            scenario_request=scenario_request,
            is_load_value_already_index_u=is_u,
        )

    def _get_provenance(self) -> dict[str, Any]:
        """Return provenance metadata."""
        return {
            "model_version": self.model_version,
            "beta_0_degc": self.params.beta_0,
            "beta_1_degc": self.params.beta_1,
            "tau_hours": self.params.tau_hours,
            "load_driver_type": self.load_driver_type,
            "load_driver_reference": self.load_driver_reference,
            "conformal_quantile_90": self.conformal_quantile_90,
            "horizon_half_widths_degc": self.conformal_half_widths,
            "engine": "FirstOrderGreyBoxODEScenarioEngine",
        }
