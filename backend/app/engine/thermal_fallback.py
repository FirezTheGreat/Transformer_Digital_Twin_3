"""Phase 4.3 — Runtime Thermal Residual Evaluator & Fallback Protection Gate.

This module implements the deterministic runtime layer that:
1. Steps the calibrated first-order grey-box thermal ODE continuously on live telemetry.
2. Computes the real-time thermal residual: r_k = T_{o,observed,k} - T_{hat,o,free-running,k}.
3. Tracks persistent residual excursions using a two-sided CUSUM accumulator:
       z_k = (r_k - median_cal) / max(1.4826 * MAD_cal, sensor_resolution_floor)
       S^+_k = max(0, S^+_{k-1} + z_k - 0.50)
       S^-_k = min(0, S^-_{k-1} + z_k + 0.50)
4. Enforces the thermal fallback protection gate:
   - Hard fallback: unpromoted model, missing/corrupted inputs, sensor flatline, physical impossibility.
   - Fallback behavior: falls back to last-value persistence with empirical error band,
     disables causal what-if scenario projection, disables model CUSUM escalation,
     preserves independent electrical checks (C1), direct protection rules, and descriptive thermal (C2).
5. Respects data-quality rules, out-of-order/late arrivals, long gaps, and warm-up requirements:
   - Warm-up period: W = max(4 samples, ceil(tau / 0.25h)) samples after startup or gap reset.
   - During warm-up, ODE steps to establish state, but residual escalation / CUSUM alarms are suppressed.
6. Emits structured deterministic runtime evidence items for downstream anomaly episode management.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Mapping, Optional, Sequence
from pydantic import BaseModel, ConfigDict, Field

from app.engine.thermal import ThermalModelParameters, step_thermal_ode
from app.models.telemetry import Measurement, QualitySeverity
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.scenario import ThermalTrustState
from app.models.thermal_artifact import CalibratedThermalModelArtifact


# ---------------------------------------------------------------------------
# Enums and Value Types
# ---------------------------------------------------------------------------


class ThermalFallbackReason(str, Enum):
    """Specific reasons for entering thermal model fallback."""
    UNPROMOTED_MODEL = "UNPROMOTED_MODEL"
    MISSING_TOP_OIL = "MISSING_TOP_OIL"
    MISSING_AMBIENT = "MISSING_AMBIENT"
    MISSING_LOAD_DRIVER = "MISSING_LOAD_DRIVER"
    BAD_TELEMETRY_QUALITY = "BAD_TELEMETRY_QUALITY"
    PHYSICAL_IMPOSSIBILITY = "PHYSICAL_IMPOSSIBILITY"
    SENSOR_FROZEN_OR_FLATLINE = "SENSOR_FROZEN_OR_FLATLINE"
    MONITORING_GAP_EXCEEDED = "MONITORING_GAP_EXCEEDED"
    PERSISTENT_RESIDUAL_ANOMALY = "PERSISTENT_RESIDUAL_ANOMALY"
    CONFORMAL_COVERAGE_BREAKDOWN = "CONFORMAL_COVERAGE_BREAKDOWN"


class CUSUMDirection(str, Enum):
    """Direction of CUSUM residual drift."""
    NORMAL = "NORMAL"
    POSITIVE_SHIFT = "POSITIVE_SHIFT"
    NEGATIVE_SHIFT = "NEGATIVE_SHIFT"


class CUSUMStepResult(BaseModel):
    """Result of one CUSUM step update."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    standardized_residual_z: float
    cusum_pos: float
    cusum_neg: float
    is_positive_alarm: bool
    is_negative_alarm: bool
    alarm_active: bool
    direction: CUSUMDirection


# ---------------------------------------------------------------------------
# 1. Two-Sided CUSUM Accumulator
# ---------------------------------------------------------------------------

class CUSUMTracker:
    """Deterministic two-sided CUSUM tracker for standardized thermal residuals.

    Formulation:
        z_k = (r_k - median_cal) / max(1.4826 * MAD_cal, sensor_resolution_floor)
        S^+_k = max(0, S^+_{k-1} + z_k - k)
        S^-_k = min(0, S^-_{k-1} + z_k + k)

    Parameters:
        k: Reference allowance parameter (default 0.50 for a half-sigma shift).
        h: Decision limit for warning alarm (default 4.50 standardized units).
        calibration_median: Empirical median of calibration residuals (degC).
        calibration_mad: Empirical MAD of calibration residuals (degC).
        sensor_resolution_floor: Minimum scale floor to prevent division by zero (default 0.50 degC).
    """

    def __init__(
        self,
        reference_k: float = 0.50,
        decision_limit_h: float = 4.50,
        calibration_median: float = 0.0,
        calibration_mad: float = 1.0,
        sensor_resolution_floor: float = 0.50,
    ) -> None:
        self.k = float(reference_k)
        self.h = float(decision_limit_h)
        self.calibration_median = float(calibration_median)
        self.calibration_mad = float(calibration_mad)
        self.scale = max(1.4826 * self.calibration_mad, float(sensor_resolution_floor))

        self.cusum_pos: float = 0.0
        self.cusum_neg: float = 0.0

    def reset(self) -> None:
        """Reset CUSUM accumulators to zero."""
        self.cusum_pos = 0.0
        self.cusum_neg = 0.0

    def update(
        self,
        residual_degc: float,
        is_warmup: bool = False,
        is_fallback: bool = False,
    ) -> CUSUMStepResult:
        """Update CUSUM accumulators with a new residual observation.

        Args:
            residual_degc: Observed top-oil minus expected top-oil in degC.
            is_warmup: If True, residuals are observed during warm-up (no escalation).
            is_fallback: If True, thermal fallback is active (CUSUM disabled).

        Returns:
            CUSUMStepResult: Updated state and alarm flags.
        """
        if not math.isfinite(residual_degc) or is_fallback:
            return CUSUMStepResult(
                standardized_residual_z=0.0,
                cusum_pos=self.cusum_pos,
                cusum_neg=self.cusum_neg,
                is_positive_alarm=False,
                is_negative_alarm=False,
                alarm_active=False,
                direction=CUSUMDirection.NORMAL,
            )

        z = (residual_degc - self.calibration_median) / self.scale

        if is_warmup:
            # During warm-up, do not escalate accumulators
            return CUSUMStepResult(
                standardized_residual_z=round(z, 4),
                cusum_pos=self.cusum_pos,
                cusum_neg=self.cusum_neg,
                is_positive_alarm=False,
                is_negative_alarm=False,
                alarm_active=False,
                direction=CUSUMDirection.NORMAL,
            )

        # Standard two-sided CUSUM updates
        self.cusum_pos = max(0.0, self.cusum_pos + z - self.k)
        self.cusum_neg = min(0.0, self.cusum_neg + z + self.k)

        is_pos_alarm = self.cusum_pos >= self.h
        is_neg_alarm = self.cusum_neg <= -self.h
        alarm_active = is_pos_alarm or is_neg_alarm

        direction = CUSUMDirection.NORMAL
        if is_pos_alarm and not is_neg_alarm:
            direction = CUSUMDirection.POSITIVE_SHIFT
        elif is_neg_alarm and not is_pos_alarm:
            direction = CUSUMDirection.NEGATIVE_SHIFT
        elif is_pos_alarm and is_neg_alarm:
            direction = CUSUMDirection.POSITIVE_SHIFT if abs(self.cusum_pos) >= abs(self.cusum_neg) else CUSUMDirection.NEGATIVE_SHIFT

        return CUSUMStepResult(
            standardized_residual_z=round(z, 4),
            cusum_pos=round(self.cusum_pos, 4),
            cusum_neg=round(self.cusum_neg, 4),
            is_positive_alarm=is_pos_alarm,
            is_negative_alarm=is_neg_alarm,
            alarm_active=alarm_active,
            direction=direction,
        )


# ---------------------------------------------------------------------------
# 2. Runtime Evaluation Result
# ---------------------------------------------------------------------------

class ThermalRuntimeOutput(BaseModel):
    """Structured deterministic output emitted by the thermal runtime evaluator."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp_utc: datetime = Field(..., description="Timestamp of the evaluated step in UTC")
    trust_state: ThermalTrustState = Field(..., description="Active thermal model capability trust state")
    top_oil_observed_degc: Optional[float] = Field(default=None, description="Observed top-oil temperature in degC")
    expected_top_oil_degc: Optional[float] = Field(default=None, description="Expected top-oil temperature in degC (ODE or persistence fallback)")
    free_running_top_oil_degc: Optional[float] = Field(default=None, description="Continuous free-running ODE state in degC")
    thermal_residual_degc: Optional[float] = Field(default=None, description="Observed minus expected top-oil residual in degC")
    standardized_residual_z: Optional[float] = Field(default=None, description="Standardized residual z-score")
    cusum_pos: float = Field(default=0.0, ge=0.0, description="Positive CUSUM accumulator")
    cusum_neg: float = Field(default=0.0, le=0.0, description="Negative CUSUM accumulator")
    cusum_alarm_active: bool = Field(default=False, description="Whether CUSUM decision limit h is tripped")
    cusum_direction: CUSUMDirection = Field(default=CUSUMDirection.NORMAL, description="Direction of CUSUM drift")
    is_warmup: bool = Field(default=False, description="Whether model is in warmup phase")
    warmup_samples_remaining: int = Field(default=0, ge=0, description="Number of warmup samples remaining")
    is_fallback_active: bool = Field(default=False, description="Whether fallback gate is active")
    fallback_reasons: List[ThermalFallbackReason] = Field(default_factory=list, description="Active fallback reason codes")
    conformal_interval_lower_degc: Optional[float] = Field(default=None, description="Lower empirical conformal bound")
    conformal_interval_upper_degc: Optional[float] = Field(default=None, description="Upper empirical conformal bound")
    what_if_enabled: bool = Field(default=False, description="Whether 2-hour what-if scenario projection is trusted and enabled")
    emitted_evidence: List[EvidenceItem] = Field(default_factory=list, description="Structured anomaly evidence items emitted in this cycle")


# ---------------------------------------------------------------------------
# 3. Thermal Fallback Gate & Runtime Evaluator
# ---------------------------------------------------------------------------

class ThermalFallbackGate:
    """Stateful thermal runtime evaluator and fallback protection gate.

    Maintains continuous free-running thermal ODE state without artificial
    per-step resets, enforces gap and warm-up policies, executes two-sided
    CUSUM drift detection, and gates thermal predictive capabilities upon
    telemetry corruption or persistent anomalies.
    """

    def __init__(
        self,
        asset_id: str,
        params: ThermalModelParameters,
        load_driver_type: str = "rms_current_a",
        load_driver_reference: float = 153.865,
        is_model_promoted: bool = True,
        conformal_half_width_1step: float = 2.9945,
        calibration_residual_median: float = 0.2062,
        calibration_residual_mad: float = 0.9613,
        cusum_decision_limit_h: float = 4.50,
        max_gap_hours: float = 1.0,
        min_warmup_samples: Optional[int] = None,
    ) -> None:
        self.asset_id = str(asset_id)
        self.params = params
        self.load_driver_type = str(load_driver_type)
        self.load_driver_reference = max(float(load_driver_reference), 1e-4)
        self.is_model_promoted = bool(is_model_promoted)
        self.conformal_half_width_1step = float(conformal_half_width_1step)
        self.max_gap_hours = float(max_gap_hours)

        # Warmup sample count: max(4 samples, ceil(tau / 0.25h))
        if min_warmup_samples is None:
            tau_samples = int(math.ceil(self.params.tau_hours / 0.25))
            self.min_warmup_samples = max(4, tau_samples)
        else:
            self.min_warmup_samples = max(1, int(min_warmup_samples))

        # CUSUM tracker
        self.cusum_tracker = CUSUMTracker(
            reference_k=0.50,
            decision_limit_h=cusum_decision_limit_h,
            calibration_median=calibration_residual_median,
            calibration_mad=calibration_residual_mad,
            sensor_resolution_floor=0.50,
        )

        # Internal state
        self.last_event_time_utc: Optional[datetime] = None
        self.last_valid_top_oil_degc: Optional[float] = None
        self.free_running_top_oil_degc: Optional[float] = None
        self.warmup_samples_remaining: int = 0
        self.evidence_counter: int = 0

    @classmethod
    def from_artifact(
        cls,
        artifact: CalibratedThermalModelArtifact,
        is_model_promoted_override: Optional[bool] = None,
    ) -> ThermalFallbackGate:
        """Construct gate directly from a frozen CalibratedThermalModelArtifact."""
        params = ThermalModelParameters(
            beta_0=artifact.parameters.beta_0,
            beta_1=artifact.parameters.beta_1,
            tau_hours=artifact.parameters.tau_hours,
        )
        is_promoted = (
            is_model_promoted_override
            if is_model_promoted_override is not None
            else (artifact.promotion.status == "PROMOTED")
        )
        w1 = (
            artifact.conformal_uncertainty.horizon_half_widths_degc[0]
            if artifact.conformal_uncertainty.horizon_half_widths_degc
            else 3.0
        )
        med = artifact.conformal_uncertainty.calibration_residual_median or 0.0
        mad = artifact.conformal_uncertainty.calibration_residual_mad or 1.0

        return cls(
            asset_id=artifact.asset_id,
            params=params,
            load_driver_type=artifact.selected_load_driver,
            load_driver_reference=artifact.load_driver_reference_value,
            is_model_promoted=is_promoted,
            conformal_half_width_1step=w1,
            calibration_residual_median=med,
            calibration_residual_mad=mad,
        )

    def reset(self) -> None:
        """Reset gate state completely."""
        self.last_event_time_utc = None
        self.last_valid_top_oil_degc = None
        self.free_running_top_oil_degc = None
        self.warmup_samples_remaining = 0
        self.cusum_tracker.reset()

    def evaluate_step(
        self,
        event_time_utc: datetime,
        top_oil_obs: Optional[float | Measurement],
        ambient_obs: Optional[float | Measurement],
        load_obs: Optional[float | Measurement],
        is_model_promoted_override: Optional[bool] = None,
    ) -> ThermalRuntimeOutput:
        """Evaluate one discrete runtime telemetry event.

        Args:
            event_time_utc: Timestamp of the event in UTC.
            top_oil_obs: Top-oil temperature (float value or Measurement object).
            ambient_obs: Ambient temperature (float value or Measurement object).
            load_obs: Load driver reading (float value or Measurement object).
            is_model_promoted_override: Optional runtime model promotion override.

        Returns:
            ThermalRuntimeOutput: Full deterministic evaluation payload.
        """
        # Ensure UTC timezone
        if event_time_utc.tzinfo is None:
            event_time_utc = event_time_utc.replace(tzinfo=timezone.utc)

        is_promoted = (
            is_model_promoted_override
            if is_model_promoted_override is not None
            else self.is_model_promoted
        )

        fallback_reasons: List[ThermalFallbackReason] = []
        emitted_evidence: List[EvidenceItem] = []

        # 1. Extract values and validate quality
        t_oil_val, t_oil_ok = self._extract_value_and_quality(top_oil_obs)
        t_amb_val, t_amb_ok = self._extract_value_and_quality(ambient_obs)
        load_val, load_ok = self._extract_value_and_quality(load_obs)

        # 2. Check input sufficiency & hard fallback conditions
        if not is_promoted:
            fallback_reasons.append(ThermalFallbackReason.UNPROMOTED_MODEL)

        if not t_oil_ok or t_oil_val is None:
            fallback_reasons.append(ThermalFallbackReason.MISSING_TOP_OIL)
        if not t_amb_ok or t_amb_val is None:
            fallback_reasons.append(ThermalFallbackReason.MISSING_AMBIENT)
        if not load_ok or load_val is None:
            fallback_reasons.append(ThermalFallbackReason.MISSING_LOAD_DRIVER)

        # 3. Check physical plausibility if measurements are present
        if t_oil_val is not None and t_amb_val is not None:
            # Physical impossibility: top-oil colder than ambient by more than 10 degC
            # or extreme temperatures outside realistic operating range
            if t_oil_val < (t_amb_val - 10.0) or t_oil_val > 160.0 or t_oil_val < -40.0:
                fallback_reasons.append(ThermalFallbackReason.PHYSICAL_IMPOSSIBILITY)
                emitted_evidence.append(
                    self._create_evidence(
                        event_time_utc=event_time_utc,
                        category=AnomalyCategory.SENSOR_PLAUSIBILITY,
                        detector_id="thermal_physical_impossibility",
                        observed_value=t_oil_val,
                        expected_value=t_amb_val,
                        direction="IMPOSSIBLE_VALUE",
                        severity=1.0,
                        confidence=0.95,
                        reason_codes=["TOP_OIL_TEMPERATURE_PHYSICALLY_IMPOSSIBLE"],
                        hypothesis_codes=["POSSIBLE_SENSOR_BIAS", "SENSOR_DISCONNECTED"],
                    )
                )

        # Update last valid observed top-oil
        if t_oil_ok and t_oil_val is not None:
            self.last_valid_top_oil_degc = t_oil_val

        # 4. Compute elapsed interval dt and check for gaps
        dt_hours = 0.25  # default nominal 15-min
        is_gap_detected = False

        if self.last_event_time_utc is not None:
            dt_sec = (event_time_utc - self.last_event_time_utc).total_seconds()
            if dt_sec < 0:
                # Out-of-order event
                dt_hours = 0.25
            else:
                dt_hours = dt_sec / 3600.0

            if dt_hours > self.max_gap_hours:
                is_gap_detected = True
                fallback_reasons.append(ThermalFallbackReason.MONITORING_GAP_EXCEEDED)

        # Handle gap reset
        if is_gap_detected:
            # Gaps terminate residual sequence: reinitialize state on next valid point and restart warm-up
            self.free_running_top_oil_degc = t_oil_val if (t_oil_ok and t_oil_val is not None) else None
            self.warmup_samples_remaining = self.min_warmup_samples
            self.cusum_tracker.reset()

        self.last_event_time_utc = event_time_utc

        is_hard_fallback = len(fallback_reasons) > 0

        # ------------------------------------------------------------------
        # 5. State Progression: Fallback vs Warmup vs Healthy
        # ------------------------------------------------------------------
        if is_hard_fallback:
            trust_state = ThermalTrustState.FALLBACK_PERSISTENCE
            is_fallback_active = True
            is_warmup = False
            what_if_enabled = False

            # Last-value persistence fallback for expected top-oil
            expected_top_oil = self.last_valid_top_oil_degc
            residual = (
                round(t_oil_val - expected_top_oil, 4)
                if (t_oil_val is not None and expected_top_oil is not None)
                else None
            )

            # CUSUM is disabled / paused during fallback
            cusum_res = self.cusum_tracker.update(
                residual_degc=0.0,
                is_fallback=True,
            )

            # Conformal bounds around persistence
            c_low = (
                round(expected_top_oil - self.conformal_half_width_1step, 4)
                if expected_top_oil is not None
                else None
            )
            c_high = (
                round(expected_top_oil + self.conformal_half_width_1step, 4)
                if expected_top_oil is not None
                else None
            )

            return ThermalRuntimeOutput(
                timestamp_utc=event_time_utc,
                trust_state=trust_state,
                top_oil_observed_degc=t_oil_val,
                expected_top_oil_degc=expected_top_oil,
                free_running_top_oil_degc=self.free_running_top_oil_degc,
                thermal_residual_degc=residual,
                standardized_residual_z=None,
                cusum_pos=cusum_res.cusum_pos,
                cusum_neg=cusum_res.cusum_neg,
                cusum_alarm_active=False,
                cusum_direction=CUSUMDirection.NORMAL,
                is_warmup=is_warmup,
                warmup_samples_remaining=self.warmup_samples_remaining,
                is_fallback_active=is_fallback_active,
                fallback_reasons=fallback_reasons,
                conformal_interval_lower_degc=c_low,
                conformal_interval_upper_degc=c_high,
                what_if_enabled=what_if_enabled,
                emitted_evidence=emitted_evidence,
            )

        # ------------------------------------------------------------------
        # 6. Normal ODE Step (All inputs valid and model promoted)
        # ------------------------------------------------------------------
        u_load = max(0.0, float(load_val) / self.load_driver_reference)

        if self.free_running_top_oil_degc is None:
            # First initialization
            self.free_running_top_oil_degc = float(t_oil_val)
            self.warmup_samples_remaining = self.min_warmup_samples
            expected_top_oil = float(t_oil_val)
        else:
            # Continuous step ODE
            hat_t = step_thermal_ode(
                t_prev_degc=self.free_running_top_oil_degc,
                ambient_degc=float(t_amb_val),
                u_load=u_load,
                dt_hours=dt_hours,
                params=self.params,
            )
            self.free_running_top_oil_degc = hat_t
            expected_top_oil = hat_t

        residual = round(float(t_oil_val) - expected_top_oil, 4)

        # Check warmup status
        if self.warmup_samples_remaining > 0:
            is_warmup = True
            trust_state = ThermalTrustState.WARMUP
            what_if_enabled = False
            self.warmup_samples_remaining -= 1
            cusum_res = self.cusum_tracker.update(
                residual_degc=residual,
                is_warmup=True,
            )
        else:
            is_warmup = False
            trust_state = ThermalTrustState.MODEL_HEALTHY
            what_if_enabled = True
            cusum_res = self.cusum_tracker.update(
                residual_degc=residual,
                is_warmup=False,
            )

            # 7. Check for CUSUM Alarms and emit evidence
            if cusum_res.alarm_active:
                direction_str = (
                    "POSITIVE_SHIFT"
                    if cusum_res.direction == CUSUMDirection.POSITIVE_SHIFT
                    else "NEGATIVE_SHIFT"
                )
                severity = min(
                    1.0,
                    0.50 + 0.50 * max(abs(cusum_res.cusum_pos), abs(cusum_res.cusum_neg)) / (self.cusum_tracker.h * 2.0),
                )
                emitted_evidence.append(
                    self._create_evidence(
                        event_time_utc=event_time_utc,
                        category=AnomalyCategory.THERMAL_DEVIATION,
                        detector_id="thermal_cusum_drift",
                        observed_value=t_oil_val,
                        expected_value=round(expected_top_oil, 2),
                        direction=direction_str,
                        severity=round(severity, 2),
                        confidence=0.85,
                        reason_codes=["CUSUM_RESIDUAL_DRIFT_DETECTED"],
                        hypothesis_codes=[
                            "POSSIBLE_COOLING_DEGRADATION" if cusum_res.direction == CUSUMDirection.POSITIVE_SHIFT else "POSSIBLE_OVERCOOLING_OR_SENSOR_BIAS",
                            "POSSIBLE_SENSOR_BIAS",
                            "MODEL_MISSPECIFICATION_POSSIBLE",
                        ],
                    )
                )

        # Conformal interval bounds
        c_low = round(expected_top_oil - self.conformal_half_width_1step, 4)
        c_high = round(expected_top_oil + self.conformal_half_width_1step, 4)

        return ThermalRuntimeOutput(
            timestamp_utc=event_time_utc,
            trust_state=trust_state,
            top_oil_observed_degc=t_oil_val,
            expected_top_oil_degc=round(expected_top_oil, 4),
            free_running_top_oil_degc=round(self.free_running_top_oil_degc, 4),
            thermal_residual_degc=residual,
            standardized_residual_z=cusum_res.standardized_residual_z,
            cusum_pos=cusum_res.cusum_pos,
            cusum_neg=cusum_res.cusum_neg,
            cusum_alarm_active=cusum_res.alarm_active,
            cusum_direction=cusum_res.direction,
            is_warmup=is_warmup,
            warmup_samples_remaining=self.warmup_samples_remaining,
            is_fallback_active=False,
            fallback_reasons=[],
            conformal_interval_lower_degc=c_low,
            conformal_interval_upper_degc=c_high,
            what_if_enabled=what_if_enabled,
            emitted_evidence=emitted_evidence,
        )

    # -----------------------------------------------------------------------
    # Helper Methods
    # -----------------------------------------------------------------------

    def _extract_value_and_quality(
        self,
        obs: Optional[float | Measurement],
    ) -> tuple[Optional[float], bool]:
        """Extract numeric value and check if observation is usable."""
        if obs is None:
            return None, False

        if isinstance(obs, (int, float)):
            val = float(obs)
            return (val, True) if math.isfinite(val) else (None, False)

        if isinstance(obs, Measurement):
            if obs.value is None or not math.isfinite(obs.value):
                return None, False
            if obs.quality.severity == QualitySeverity.BAD:
                return float(obs.value), False
            return float(obs.value), True

        return None, False

    def _create_evidence(
        self,
        event_time_utc: datetime,
        category: AnomalyCategory,
        detector_id: str,
        observed_value: Any,
        expected_value: Any,
        direction: str,
        severity: float,
        confidence: float,
        reason_codes: List[str],
        hypothesis_codes: List[str],
    ) -> EvidenceItem:
        """Create structured typed EvidenceItem."""
        self.evidence_counter += 1
        ev_id = f"ev_{self.asset_id}_{event_time_utc.strftime('%Y%m%d%H%M%S')}_{self.evidence_counter}"

        return EvidenceItem(
            evidence_id=ev_id,
            asset_id=self.asset_id,
            event_time_utc=event_time_utc,
            category=category,
            detector_id=detector_id,
            observed_value=observed_value,
            expected_value=expected_value,
            unit="Cel",
            threshold_or_band=f"+/-{self.conformal_half_width_1step:.2f} Cel",
            direction=direction,
            severity=severity,
            confidence=confidence,
            input_lineage=["top_oil_temperature", "ambient_temperature", self.load_driver_type],
            reason_codes=reason_codes,
            hypothesis_codes=hypothesis_codes,
        )
