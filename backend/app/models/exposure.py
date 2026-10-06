"""Phase 6.2 — Thermal Exposure and Standards-Derived Ageing Data Contracts.

Defines:
1. InsulationProfile enum (UNKNOWN, CELLULOSIC_NON_THERMALLY_UPGRADED, CELLULOSIC_THERMALLY_UPGRADED, etc.)
2. AgeingStandardMetadata for explicit standard and profile tracking (e.g. IEEE Std C57.91-2011 / IEC 60076-7:2018)
3. TemperatureBandExposure for tracking time-in-temperature bands
4. ObservedThermalExposure for top-oil exposure, degree-hours, and telemetry gaps
5. StandardsAgeingResult for gated relative ageing rate (F_AA or V) and equivalent ageing hours (L_eq)
6. ThermalExposureBundle as the complete exposure and ageing assessment
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class InsulationProfile(str, Enum):
    """Insulation system thermal upgrade profile per IEEE C57.91 / IEC 60076-7."""
    UNKNOWN = "UNKNOWN"
    CELLULOSIC_NON_THERMALLY_UPGRADED = "CELLULOSIC_NON_THERMALLY_UPGRADED"
    CELLULOSIC_THERMALLY_UPGRADED = "CELLULOSIC_THERMALLY_UPGRADED"
    HIGH_TEMPERATURE_OR_HYBRID = "HIGH_TEMPERATURE_OR_HYBRID"
    OTHER_UNSUPPORTED = "OTHER_UNSUPPORTED"


class AgeingStandardMetadata(BaseModel):
    """Explicit standard edition and thermal ageing equation metadata."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    standard_id: str = Field(..., description="Canonical standard identifier (e.g. IEEE_C57_91_2011, IEC_60076_7_2018)")
    edition: str = Field(..., description="Standard edition or publication year (e.g. '2011', '2018')")
    profile_id: str = Field(..., description="Associated insulation profile identifier")
    reference_temp_c: float = Field(..., description="Reference temperature in Cel where relative ageing rate is 1.0")
    formula_name: str = Field(..., description="Ageing equation name (e.g. 'IEEE_Arrhenius_15000', 'IEC_Half_Life_6C')")


class TemperatureBandExposure(BaseModel):
    """Accumulated duration in a specific temperature threshold band."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    band_name: str = Field(..., description="Name of temperature band (e.g. 'T_gt_85C', 'T_gt_95C', 'T_gt_105C')")
    threshold_c: float = Field(..., description="Lower threshold of the band in degrees Cel")
    duration_seconds: float = Field(default=0.0, ge=0.0, description="Accumulated duration in seconds")
    duration_hours: float = Field(default=0.0, ge=0.0, description="Accumulated duration in hours")
    percentage_of_monitored_time: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Percentage of total valid monitored time"
    )


class ObservedThermalExposure(BaseModel):
    """Observed top-oil thermal stress metrics over the observed telemetry window."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str = Field(..., description="Asset identifier")
    first_timestamp_utc: Optional[datetime] = Field(default=None, description="Start of observed window")
    last_timestamp_utc: Optional[datetime] = Field(default=None, description="End of observed window")
    total_monitored_seconds: float = Field(default=0.0, ge=0.0, description="Total valid monitored time in seconds")
    total_monitored_hours: float = Field(default=0.0, ge=0.0, description="Total valid monitored time in hours")
    total_gap_seconds: float = Field(default=0.0, ge=0.0, description="Total duration of telemetry coverage gaps")
    valid_sample_count: int = Field(default=0, ge=0, description="Count of valid top-oil observations integrated")
    peak_top_oil_temp_c: Optional[float] = Field(default=None, description="Maximum observed top-oil temperature in Cel")
    mean_top_oil_temp_c: Optional[float] = Field(default=None, description="Time-weighted average top-oil temperature in Cel")
    degree_hours_above_85c: float = Field(default=0.0, ge=0.0, description="Degree-hours above 85 Cel")
    degree_hours_above_95c: float = Field(default=0.0, ge=0.0, description="Degree-hours above 95 Cel")
    degree_hours_above_105c: float = Field(default=0.0, ge=0.0, description="Degree-hours above 105 Cel")
    bands: Dict[str, TemperatureBandExposure] = Field(
        default_factory=dict, description="Time-in-band breakdown across configured thresholds"
    )
    is_valid: bool = Field(default=False, description="True if at least one valid top-oil observation was recorded")


class StandardsAgeingResult(BaseModel):
    """Gated standards-derived equivalent thermal ageing assessment."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    is_enabled: bool = Field(..., description="True if standards-derived ageing is enabled and active")
    gate_reason: Optional[str] = Field(default=None, description="Reason if standards ageing is gated or suppressed")
    insulation_profile: InsulationProfile = Field(
        default=InsulationProfile.UNKNOWN, description="Insulation thermal upgrade profile"
    )
    standard_metadata: Optional[AgeingStandardMetadata] = Field(
        default=None, description="Explicit standard and equation metadata"
    )
    hotspot_source: Literal["DIRECT_MEASUREMENT", "PROMOTED_MODEL", "UNAVAILABLE"] = Field(
        default="UNAVAILABLE", description="Source of winding hot-spot temperature"
    )
    equivalent_ageing_hours: Optional[float] = Field(
        default=None, ge=0.0, description="Cumulative thermal equivalent ageing hours (L_eq)"
    )
    average_relative_ageing_rate: Optional[float] = Field(
        default=None, ge=0.0, description="Average relative ageing rate over the observed window (F_AA or V)"
    )
    current_relative_ageing_rate: Optional[float] = Field(
        default=None, ge=0.0, description="Instantaneous relative ageing rate at current step"
    )
    peak_hotspot_temp_c: Optional[float] = Field(
        default=None, description="Maximum observed or modeled hot-spot temperature in Cel"
    )
    observed_interval_hours: Optional[float] = Field(
        default=None, ge=0.0, description="Hours of hot-spot exposure integrated"
    )


class ThermalExposureBundle(BaseModel):
    """Complete Thermal Exposure & Standards-Derived Ageing Assessment Bundle."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str = Field(..., description="Asset identifier")
    timestamp_utc: datetime = Field(..., description="Evaluation timestamp in UTC")
    observed_exposure: ObservedThermalExposure = Field(..., description="Observed top-oil exposure and degree-hours")
    standards_ageing: StandardsAgeingResult = Field(..., description="Gated standards-derived ageing result")
    whole_life_rul_supported: bool = Field(
        default=False, description="Explicit flag: whole-life RUL is NOT supported by the digital twin"
    )
    failure_probability_supported: bool = Field(
        default=False, description="Explicit flag: failure probability is NOT supported by the digital twin"
    )
