"""Phase 5.2 — Two-Sided CUSUM Thermal Residual Drift Tracker.

Implements the deterministic two-sided cumulative sum (CUSUM) residual tracker:
1. Standardizes raw thermal residuals:
       z_k = (r_k - median_cal) / max(scale_cal, sensor_resolution_floor)
   using frozen calibration statistics (with no double scaling).
2. Accumulates directional drift:
       C^+_k = max(0, C^+_{k-1} + z_k - k)
       C^-_k = min(0, C^-_{k-1} + z_k + k)
   with reference allowance k = 0.50 and calibrated decision limit h = 4.50.
3. Enforces strict capability and authority isolation:
   - For unpromoted / unqualified artifacts (Tripura cusum_qualification == DISABLED),
     CUSUM operates in SHADOW_EXPLORATORY mode and emits non-assertive model deviation hypotheses.
   - Never declares a transformer fault, cooling breakdown, or operational alarm without qualification.
4. Gated against thermal warm-up, data gaps (>1.0h), missing telemetry, and fallback persistence.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.thermal_artifact import CalibratedThermalModelArtifact, QualificationStatus


class CUSUMDirection(str, Enum):
    """Direction of persistent thermal residual drift."""
    NORMAL = "NORMAL"
    POSITIVE_SHIFT = "POSITIVE_SHIFT"   # Persistent positive thermal model deviation (observed > model)
    NEGATIVE_SHIFT = "NEGATIVE_SHIFT"   # Persistent negative thermal model deviation (observed < model)


class CUSUMTrustStatus(str, Enum):
    """Authority and execution status of the CUSUM detector."""
    HEALTHY = "HEALTHY"
    WARMUP = "WARMUP"
    FALLBACK = "FALLBACK"
    SHADOW_EXPLORATORY = "SHADOW_EXPLORATORY"  # Active calculation without authoritative alarm capability
    QUALIFIED_ACTIVE = "QUALIFIED_ACTIVE"      # Fully qualified autonomous anomaly detector


class CUSUMStepResult(BaseModel):
    """Deterministic result of one CUSUM step evaluation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    standardized_residual_z: Optional[float] = Field(default=None, description="Standardized residual z-score")
    cusum_pos: float = Field(default=0.0, ge=0.0, description="Positive CUSUM accumulator C+")
    cusum_neg: float = Field(default=0.0, le=0.0, description="Negative CUSUM accumulator C-")
    is_positive_alarm: bool = Field(default=False, description="Whether positive decision limit +h is exceeded")
    is_negative_alarm: bool = Field(default=False, description="Whether negative decision limit -h is exceeded")
    alarm_active: bool = Field(default=False, description="Whether either decision limit is exceeded")
    direction: CUSUMDirection = Field(default=CUSUMDirection.NORMAL, description="Direction of detected drift")
    trust_status: CUSUMTrustStatus = Field(default=CUSUMTrustStatus.SHADOW_EXPLORATORY, description="Detector authority status")


class CUSUMConfig(BaseModel):
    """Configuration and calibration parameters for the two-sided CUSUM tracker."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    reference_k: float = Field(default=0.50, gt=0.0, description="Reference allowance parameter k (half-sigma shift)")
    decision_limit_h: float = Field(default=4.50, gt=0.0, description="Decision threshold limit h (standardized units)")
    calibration_median: float = Field(default=0.2062, description="Empirical median of calibration residuals (degC)")
    calibration_scale_mad: float = Field(default=0.9613, gt=0.0, description="Empirical 1.4826*MAD robust scale of calibration residuals (degC)")
    sensor_resolution_floor: float = Field(default=0.50, gt=0.0, description="Measurement resolution floor (degC) preventing division by near-zero")
    is_qualified: bool = Field(default=False, description="Whether CUSUM capability is formally validated and qualified")


class TwoSidedCUSUMTracker:
    """Stateful deterministic two-sided CUSUM residual drift evaluator."""

    def __init__(
        self,
        reference_k: float = 0.50,
        decision_limit_h: float = 4.50,
        calibration_median: float = 0.2062,
        calibration_mad: float = 0.9613,
        sensor_resolution_floor: float = 0.50,
        is_qualified: bool = True,
    ) -> None:
        self.k = float(reference_k)
        self.h = float(decision_limit_h)
        self.calibration_median = float(calibration_median)
        self.calibration_mad = float(calibration_mad)
        self.sensor_resolution_floor = float(sensor_resolution_floor)
        self.is_qualified = bool(is_qualified)

        # Scale calculation: robust scale (already 1.4826*MAD from CAL) bounded by resolution floor
        # IMPORTANT: No double multiplication of 1.4826
        self.scale = max(self.calibration_mad, self.sensor_resolution_floor)

        # State accumulators
        self.cusum_pos: float = 0.0
        self.cusum_neg: float = 0.0
        self.samples_tracked: int = 0
        self.last_step_result: Optional[CUSUMStepResult] = None

    @classmethod
    def from_artifact(
        cls,
        artifact: CalibratedThermalModelArtifact,
        decision_limit_h: float = 4.50,
        reference_k: float = 0.50,
    ) -> TwoSidedCUSUMTracker:
        """Construct tracker directly from a frozen CalibratedThermalModelArtifact."""
        unc = artifact.conformal_uncertainty
        med = unc.calibration_residual_median if unc.calibration_residual_median is not None else 0.0
        mad = unc.calibration_residual_mad if unc.calibration_residual_mad is not None else 1.0

        is_promoted = getattr(artifact.promotion, "status", None) == "PROMOTED"
        is_qual = False
        if is_promoted and artifact.qualification is not None:
            is_qual = (artifact.qualification.cusum_qualification == QualificationStatus.QUALIFIED)

        return cls(
            reference_k=reference_k,
            decision_limit_h=decision_limit_h,
            calibration_median=med,
            calibration_mad=mad,
            sensor_resolution_floor=0.50,
            is_qualified=is_qual,
        )

    def reset(self) -> None:
        """Reset CUSUM accumulators to zero (e.g. on monitoring gaps or re-initialization)."""
        self.cusum_pos = 0.0
        self.cusum_neg = 0.0
        self.samples_tracked = 0
        self.last_step_result = None

    def update(
        self,
        residual_degc: Optional[float],
        is_warmup: bool = False,
        is_fallback: bool = False,
        is_gap: bool = False,
    ) -> CUSUMStepResult:
        """Evaluate one discrete thermal residual observation.

        Args:
            residual_degc: Observed minus expected top-oil temperature (degC), or None if invalid.
            is_warmup: True if model is in warm-up (no accumulator escalation).
            is_fallback: True if thermal model is in fallback persistence mode.
            is_gap: True if monitoring gap exceeded (triggers accumulator reset).

        Returns:
            CUSUMStepResult: Updated state and drift evaluation.
        """
        if is_gap:
            self.reset()

        if is_fallback or residual_degc is None or not math.isfinite(residual_degc):
            # Fallback or invalid input: CUSUM paused / disabled
            res = CUSUMStepResult(
                standardized_residual_z=None,
                cusum_pos=round(self.cusum_pos, 4),
                cusum_neg=round(self.cusum_neg, 4),
                is_positive_alarm=False,
                is_negative_alarm=False,
                alarm_active=False,
                direction=CUSUMDirection.NORMAL,
                trust_status=CUSUMTrustStatus.FALLBACK if is_fallback else CUSUMTrustStatus.SHADOW_EXPLORATORY,
            )
            self.last_step_result = res
            return res

        # 1. Standardize residual z = (r - median) / scale
        z = (float(residual_degc) - self.calibration_median) / self.scale

        if is_warmup:
            # During warm-up, compute z but do not escalate accumulators
            res = CUSUMStepResult(
                standardized_residual_z=round(z, 4),
                cusum_pos=round(self.cusum_pos, 4),
                cusum_neg=round(self.cusum_neg, 4),
                is_positive_alarm=False,
                is_negative_alarm=False,
                alarm_active=False,
                direction=CUSUMDirection.NORMAL,
                trust_status=CUSUMTrustStatus.WARMUP,
            )
            self.last_step_result = res
            return res

        if not self.is_qualified:
            # When CUSUM is unqualified or disabled, both positive and negative accumulators
            # remain strictly 0.0 across all updates, and no alarm may ever trip.
            self.cusum_pos = 0.0
            self.cusum_neg = 0.0
            self.samples_tracked += 1
            res = CUSUMStepResult(
                standardized_residual_z=round(z, 4),
                cusum_pos=0.0,
                cusum_neg=0.0,
                is_positive_alarm=False,
                is_negative_alarm=False,
                alarm_active=False,
                direction=CUSUMDirection.NORMAL,
                trust_status=CUSUMTrustStatus.SHADOW_EXPLORATORY,
            )
            self.last_step_result = res
            return res

        # 2. Two-sided CUSUM updates with zero-clamping
        self.cusum_pos = max(0.0, self.cusum_pos + z - self.k)
        self.cusum_neg = min(0.0, self.cusum_neg + z + self.k)
        self.samples_tracked += 1

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

        trust = CUSUMTrustStatus.QUALIFIED_ACTIVE

        res = CUSUMStepResult(
            standardized_residual_z=round(z, 4),
            cusum_pos=round(self.cusum_pos, 4),
            cusum_neg=round(self.cusum_neg, 4),
            is_positive_alarm=is_pos_alarm,
            is_negative_alarm=is_neg_alarm,
            alarm_active=alarm_active,
            direction=direction,
            trust_status=trust,
        )
        self.last_step_result = res
        return res

    def create_evidence_item(
        self,
        event_time_utc: datetime,
        asset_id: str,
        observed_top_oil: float,
        expected_top_oil: float,
        step_result: CUSUMStepResult,
        evidence_counter: int = 1,
    ) -> Optional[EvidenceItem]:
        """Generate structured evidence item adhering strictly to capability authority.

        If CUSUM is disabled or unqualified, never emits anomaly evidence.
        """
        if not self.is_qualified or not step_result.alarm_active:
            return None

        dir_str = "POSITIVE_SHIFT" if step_result.direction == CUSUMDirection.POSITIVE_SHIFT else "NEGATIVE_SHIFT"
        sev = min(1.0, 0.50 + 0.50 * max(abs(step_result.cusum_pos), abs(step_result.cusum_neg)) / (self.h * 2.0))

        if self.is_qualified:
            reason_codes = ["CUSUM_RESIDUAL_DRIFT_DETECTED"]
            hypotheses = [
                "POSSIBLE_COOLING_DEGRADATION" if step_result.direction == CUSUMDirection.POSITIVE_SHIFT else "POSSIBLE_OVERCOOLING_OR_SENSOR_BIAS",
                "POSSIBLE_SENSOR_BIAS",
                "MODEL_MISSPECIFICATION_POSSIBLE",
            ]
            confidence = 0.85
        else:
            # SHADOW_EXPLORATORY: Strictly non-assertive model deviation hypothesis
            reason_codes = ["PERSISTENT_MODEL_DEVIATION_HYPOTHESIS"]
            hypotheses = [
                "MODEL_MISSPECIFICATION_POSSIBLE",
                "SENSOR_BIAS_POSSIBLE",
                "ENVIRONMENTAL_INPUT_MISMATCH",
                "POSSIBLE_THERMAL_BEHAVIOUR_CHANGE",
            ]
            confidence = 0.50

        ev_id = f"ev_{asset_id}_cusum_{event_time_utc.strftime('%Y%m%d%H%M%S')}_{evidence_counter}"

        return EvidenceItem(
            evidence_id=ev_id,
            asset_id=asset_id,
            event_time_utc=event_time_utc,
            category=AnomalyCategory.THERMAL_DEVIATION,
            detector_id="thermal_cusum_drift_tracker",
            observed_value=round(observed_top_oil, 4),
            expected_value=round(expected_top_oil, 4),
            unit="Cel",
            threshold_or_band=f"+/-{self.h:.2f} standardized sigma (k={self.k:.2f})",
            direction=dir_str,
            severity=round(sev, 2),
            confidence=confidence,
            input_lineage=["top_oil_temperature", "ambient_temperature", "load_driver"],
            reason_codes=reason_codes,
            hypothesis_codes=hypotheses,
        )


# Alias for backward compatibility with thermal_fallback.py
CUSUMTracker = TwoSidedCUSUMTracker
