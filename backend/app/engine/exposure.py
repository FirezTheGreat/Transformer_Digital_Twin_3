"""Phase 6.2 — Gated Thermal Exposure and Standards-Derived Ageing Engine.

Implements:
1. Observed top-oil thermal exposure and time-in-band integration (always available when valid To exists).
2. Degree-hours integration above configured thresholds (85C, 95C, 105C).
3. Telemetry gap detection and coverage tracking.
4. Capability-specific gating: direct hot-spot vs model-derived hot-spot (decoupled from C3 model promotion).
5. Standards-derived equivalent ageing hours (L_eq) and relative ageing rate (F_AA or V):
   - IEEE Std C57.91-2011 / 2025 Arrhenius equation for thermally upgraded paper.
   - IEC 60076-7:2018 relative ageing rate equation for non-upgraded paper.
6. Insulation profile requirements (UNKNOWN, CELLULOSIC_NON_THERMALLY_UPGRADED, CELLULOSIC_THERMALLY_UPGRADED, etc.).
7. Strict isolation of discrete binary WTI alarm/trip contacts from continuous hot-spot measurements.
8. Explicit standards and edition metadata tracking.
9. Strict preservation of project exclusions (whole-life RUL and failure probability are unsupported).
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Dict, List, Literal, Optional, Sequence, Set, Tuple

from app.models.exposure import (
    AgeingStandardMetadata,
    InsulationProfile,
    ObservedThermalExposure,
    StandardsAgeingResult,
    TemperatureBandExposure,
    ThermalExposureBundle,
)
from app.models.telemetry import CanonicalEvent, Measurement, QualitySeverity


# Discrete binary alarm/trip signal IDs that must never be used as continuous temperature
DISCRETE_PROTECTION_SIGNALS: Set[str] = {
    "top_oil_temp_trip",
    "top_oil_temp_alarm",
    "winding_temp_alarm",
    "winding_temp_trip",
    "breaker_trip",
    "magnetic_oil_gauge_alarm",
    "buchholz_alarm",
    "buchholz_trip",
}

# Standard continuous hot-spot measurement signal IDs
CONTINUOUS_HOTSPOT_SIGNALS: Sequence[str] = (
    "winding_temperature_hotspot",
    "winding_temperature_direct",
    "hotspot_temperature",
    "optical_hotspot_temperature",
    "direct_hotspot_degc",
)

# Standard continuous top-oil measurement signal IDs
TOP_OIL_SIGNALS: Sequence[str] = (
    "top_oil_temperature",
    "top_oil_temp_degc",
    "top_oil_degc",
    "top_oil_temp",
)



def compute_relative_ageing_rate(
    hotspot_temp_c: float,
    profile: InsulationProfile,
    standard_id: Optional[str] = None,
) -> Tuple[float, AgeingStandardMetadata]:
    """Calculate instantaneous relative ageing rate (F_AA or V) per applicable standard.

    Formulas:
    1. Thermally upgraded paper (IEEE Std C57.91-2011 Arrhenius formulation, Ref: 110 Cel / 383 K):
       F_AA = exp(15000 / 383 - 15000 / (theta_HS + 273))

    2. Non-thermally upgraded paper (IEC 60076-7:2018 / IEEE half-life formulation, Ref: 98 Cel):
       V = 2 ^ ((theta_HS - 98) / 6)

    Args:
        hotspot_temp_c: Continuous winding hot-spot temperature in degrees Celsius.
        profile: Verified insulation profile.
        standard_id: Optional explicit standard identifier override.

    Returns:
        Tuple of (relative_ageing_rate, AgeingStandardMetadata).

    Raises:
        ValueError: If profile is UNKNOWN or unsupported.
    """
    if profile == InsulationProfile.CELLULOSIC_THERMALLY_UPGRADED:
        # Reference temperature: 110 Cel (383 K)
        # Formula: F_AA = exp(15000 / 383 - 15000 / (theta_HS + 273))
        # Note: at theta_HS = 110, exp(0) = 1.0.
        theta_k = hotspot_temp_c + 273.0
        if theta_k <= 0:
            rate = 0.0
        else:
            exponent = (15000.0 / 383.0) - (15000.0 / theta_k)
            # Clamp exponent to prevent extreme floating point overflow/underflow
            clamped_exp = max(-20.0, min(20.0, exponent))
            rate = math.exp(clamped_exp)

        meta = AgeingStandardMetadata(
            standard_id=standard_id or "IEEE_C57_91_2011",
            edition="2011",
            profile_id=profile.value,
            reference_temp_c=110.0,
            formula_name="IEEE_Arrhenius_15000",
        )
        return rate, meta

    elif profile == InsulationProfile.CELLULOSIC_NON_THERMALLY_UPGRADED:
        # Reference temperature: 98 Cel
        # Formula: V = 2 ^ ((theta_HS - 98) / 6)
        # Note: at theta_HS = 98, 2^0 = 1.0; at 104, 2^1 = 2.0; at 110, 2^2 = 4.0.
        power = (hotspot_temp_c - 98.0) / 6.0
        clamped_power = max(-20.0, min(20.0, power))
        rate = math.pow(2.0, clamped_power)

        meta = AgeingStandardMetadata(
            standard_id=standard_id or "IEC_60076_7_2018",
            edition="2018",
            profile_id=profile.value,
            reference_temp_c=98.0,
            formula_name="IEC_Half_Life_6C",
        )
        return rate, meta

    else:
        raise ValueError(
            f"Cannot compute relative ageing rate for unsupported insulation profile: {profile.value}"
        )


class ThermalExposureEngine:
    """Stateful Engine for Gated Thermal Exposure & Standards-Derived Ageing."""

    def __init__(
        self,
        asset_id: str,
        insulation_profile: InsulationProfile = InsulationProfile.UNKNOWN,
        max_gap_seconds: float = 7200.0,  # 2 hours max gap before breaking continuous integration
        standard_id: Optional[str] = None,
    ) -> None:
        """Initialize ThermalExposureEngine.

        Args:
            asset_id: Transformer asset identifier.
            insulation_profile: Verified asset insulation profile (default UNKNOWN).
            max_gap_seconds: Max allowable telemetry interval before logging a coverage gap.
            standard_id: Optional explicit standard identifier.
        """
        self.asset_id = asset_id
        self.insulation_profile = insulation_profile
        self.max_gap_seconds = max_gap_seconds
        self.standard_id = standard_id

        # Stateful accumulators for observed top-oil exposure
        self.first_timestamp_utc: Optional[datetime] = None
        self.last_timestamp_utc: Optional[datetime] = None
        self.total_monitored_seconds: float = 0.0
        self.total_gap_seconds: float = 0.0
        self.valid_sample_count: int = 0
        self.peak_top_oil_temp_c: Optional[float] = None
        self.weighted_temp_sum: float = 0.0  # sum(T_o * dt) for time-weighted mean

        # Threshold band accumulators in seconds
        self.band_durations_s: Dict[str, float] = {
            "T_gt_85C": 0.0,
            "T_gt_95C": 0.0,
            "T_gt_105C": 0.0,
        }

        # Degree-hour accumulators
        self.degree_hours_85: float = 0.0
        self.degree_hours_95: float = 0.0
        self.degree_hours_105: float = 0.0

        # Stateful accumulators for standards-derived ageing
        self.equivalent_ageing_hours: float = 0.0
        self.hotspot_integrated_seconds: float = 0.0
        self.peak_hotspot_temp_c: Optional[float] = None
        self.last_relative_ageing_rate: Optional[float] = None
        self.last_standard_metadata: Optional[AgeingStandardMetadata] = None

    def _extract_top_oil_measurement(self, event: CanonicalEvent) -> Optional[float]:
        """Extract continuous top-oil temperature from event, rejecting discrete binary contacts."""
        for m in event.measurements:
            if m.signal_id in TOP_OIL_SIGNALS:
                if m.signal_id in DISCRETE_PROTECTION_SIGNALS:
                    continue
                if m.quality.severity != QualitySeverity.BAD and isinstance(m.value, (int, float)):
                    val = float(m.value)
                    # Plausibility sanity check (-40 Cel to +180 Cel)
                    if -40.0 <= val <= 180.0:
                        return val
        return None

    def _extract_direct_hotspot_measurement(self, event: CanonicalEvent) -> Optional[float]:
        """Extract direct continuous hot-spot temperature, strictly ignoring discrete alarms."""
        for m in event.measurements:
            if m.signal_id in CONTINUOUS_HOTSPOT_SIGNALS:
                if m.signal_id in DISCRETE_PROTECTION_SIGNALS:
                    continue
                if m.quality.severity != QualitySeverity.BAD and isinstance(m.value, (int, float)):
                    val = float(m.value)
                    if -40.0 <= val <= 250.0:
                        return val
        return None

    def step(
        self,
        event: CanonicalEvent,
        modeled_hotspot_degc: Optional[float] = None,
        is_model_promoted: bool = False,
    ) -> ThermalExposureBundle:
        """Process incoming canonical event and update cumulative thermal exposure.

        Args:
            event: Incoming canonical telemetry event.
            modeled_hotspot_degc: Modeled hot-spot from grey-box ODE if available.
            is_model_promoted: Whether the grey-box thermal model is promoted (C3_predictive = ENABLED).

        Returns:
            ThermalExposureBundle: Complete exposure and standards-derived ageing state.
        """
        current_time = event.event_time_utc
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        top_oil = self._extract_top_oil_measurement(event)
        direct_hotspot = self._extract_direct_hotspot_measurement(event)

        # 1. Compute delta time dt in seconds
        dt_s = 0.0
        is_gap = False

        if self.last_timestamp_utc is not None:
            raw_dt = (current_time - self.last_timestamp_utc).total_seconds()
            if raw_dt < 0.0:
                # Late/reordered event: do not step backwards in cumulative time
                dt_s = 0.0
            elif raw_dt > self.max_gap_seconds:
                # Telemetry coverage gap: log gap duration without accumulating thermal stress
                self.total_gap_seconds += raw_dt
                is_gap = True
                dt_s = 0.0
            else:
                dt_s = raw_dt
        else:
            self.first_timestamp_utc = current_time

        # Update timestamp tracking
        if self.last_timestamp_utc is None or current_time > self.last_timestamp_utc:
            self.last_timestamp_utc = current_time

        # 2. Integrate Observed Top-Oil Exposure (Always available if top_oil is valid)
        if top_oil is not None:
            self.valid_sample_count += 1
            if self.peak_top_oil_temp_c is None or top_oil > self.peak_top_oil_temp_c:
                self.peak_top_oil_temp_c = top_oil

            if dt_s > 0.0 and not is_gap:
                self.total_monitored_seconds += dt_s
                self.weighted_temp_sum += top_oil * dt_s

                # Update temperature threshold band durations
                if top_oil > 85.0:
                    self.band_durations_s["T_gt_85C"] += dt_s
                    self.degree_hours_85 += (top_oil - 85.0) * (dt_s / 3600.0)

                if top_oil > 95.0:
                    self.band_durations_s["T_gt_95C"] += dt_s
                    self.degree_hours_95 += (top_oil - 95.0) * (dt_s / 3600.0)

                if top_oil > 105.0:
                    self.band_durations_s["T_gt_105C"] += dt_s
                    self.degree_hours_105 += (top_oil - 105.0) * (dt_s / 3600.0)

        # Compute summary top-oil statistics
        total_monitored_hours = self.total_monitored_seconds / 3600.0
        mean_top_oil = (
            (self.weighted_temp_sum / self.total_monitored_seconds)
            if self.total_monitored_seconds > 0.0
            else self.peak_top_oil_temp_c
        )

        bands: Dict[str, TemperatureBandExposure] = {}
        for band_name, threshold in [("T_gt_85C", 85.0), ("T_gt_95C", 95.0), ("T_gt_105C", 105.0)]:
            dur_s = self.band_durations_s[band_name]
            dur_h = dur_s / 3600.0
            pct = (
                (dur_s / self.total_monitored_seconds * 100.0)
                if self.total_monitored_seconds > 0.0
                else 0.0
            )
            bands[band_name] = TemperatureBandExposure(
                band_name=band_name,
                threshold_c=threshold,
                duration_seconds=dur_s,
                duration_hours=dur_h,
                percentage_of_monitored_time=pct,
            )

        observed_exposure = ObservedThermalExposure(
            asset_id=self.asset_id,
            first_timestamp_utc=self.first_timestamp_utc,
            last_timestamp_utc=self.last_timestamp_utc,
            total_monitored_seconds=self.total_monitored_seconds,
            total_monitored_hours=total_monitored_hours,
            total_gap_seconds=self.total_gap_seconds,
            valid_sample_count=self.valid_sample_count,
            peak_top_oil_temp_c=self.peak_top_oil_temp_c,
            mean_top_oil_temp_c=mean_top_oil,
            degree_hours_above_85c=self.degree_hours_85,
            degree_hours_above_95c=self.degree_hours_95,
            degree_hours_above_105c=self.degree_hours_105,
            bands=bands,
            is_valid=(self.valid_sample_count > 0),
        )

        # 3. Evaluate Standards-Derived Ageing & Capability Gating
        is_ageing_enabled = False
        gate_reason: Optional[str] = None
        hotspot_source: Literal["DIRECT_MEASUREMENT", "PROMOTED_MODEL", "UNAVAILABLE"] = "UNAVAILABLE"
        active_hotspot: Optional[float] = None

        if self.insulation_profile == InsulationProfile.UNKNOWN:
            gate_reason = "Insulation profile is UNKNOWN; standards-derived ageing requires verified insulation class."
        elif self.insulation_profile == InsulationProfile.OTHER_UNSUPPORTED:
            gate_reason = "Insulation profile is unsupported for standards-derived ageing calculation."
        elif self.insulation_profile == InsulationProfile.HIGH_TEMPERATURE_OR_HYBRID:
            gate_reason = "High-temperature/hybrid insulation requires verified manufacturer thermal profile."
        else:
            # Insulation profile is verified (THERMALLY_UPGRADED or NON_THERMALLY_UPGRADED)
            # Check for direct continuous hot-spot telemetry first (decoupled from model promotion)
            if direct_hotspot is not None:
                is_ageing_enabled = True
                hotspot_source = "DIRECT_MEASUREMENT"
                active_hotspot = direct_hotspot
            elif is_model_promoted and modeled_hotspot_degc is not None:
                is_ageing_enabled = True
                hotspot_source = "PROMOTED_MODEL"
                active_hotspot = modeled_hotspot_degc
            else:
                is_ageing_enabled = False
                hotspot_source = "UNAVAILABLE"
                gate_reason = (
                    "Direct hot-spot measurement unavailable and thermal model unpromoted for predictive hot-spot estimation."
                )

        # Integrate standards ageing if enabled
        current_rate: Optional[float] = None
        std_metadata: Optional[AgeingStandardMetadata] = None

        if is_ageing_enabled and active_hotspot is not None:
            if self.peak_hotspot_temp_c is None or active_hotspot > self.peak_hotspot_temp_c:
                self.peak_hotspot_temp_c = active_hotspot

            rate, meta = compute_relative_ageing_rate(
                hotspot_temp_c=active_hotspot,
                profile=self.insulation_profile,
                standard_id=self.standard_id,
            )
            current_rate = rate
            self.last_relative_ageing_rate = rate
            self.last_standard_metadata = meta
            std_metadata = meta

            if dt_s > 0.0 and not is_gap:
                dt_hours = dt_s / 3600.0
                self.equivalent_ageing_hours += rate * dt_hours
                self.hotspot_integrated_seconds += dt_s

        hotspot_hours = self.hotspot_integrated_seconds / 3600.0
        avg_rate = (
            (self.equivalent_ageing_hours / hotspot_hours)
            if hotspot_hours > 0.0
            else current_rate
        )

        standards_ageing = StandardsAgeingResult(
            is_enabled=is_ageing_enabled,
            gate_reason=gate_reason,
            insulation_profile=self.insulation_profile,
            standard_metadata=std_metadata or self.last_standard_metadata,
            hotspot_source=hotspot_source,
            equivalent_ageing_hours=self.equivalent_ageing_hours if is_ageing_enabled else None,
            average_relative_ageing_rate=avg_rate if is_ageing_enabled else None,
            current_relative_ageing_rate=current_rate if is_ageing_enabled else None,
            peak_hotspot_temp_c=self.peak_hotspot_temp_c if is_ageing_enabled else None,
            observed_interval_hours=hotspot_hours if is_ageing_enabled else None,
        )

        return ThermalExposureBundle(
            asset_id=self.asset_id,
            timestamp_utc=current_time,
            observed_exposure=observed_exposure,
            standards_ageing=standards_ageing,
            whole_life_rul_supported=False,
            failure_probability_supported=False,
        )
