"""Asset Profile and Transformer Nameplate Configuration Models."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class InsulationClass(str, Enum):
    """Insulation paper thermal upgrade class per IEEE C57.91 / IEC 60076-7."""
    NON_THERMALLY_UPGRADED = "NON_THERMALLY_UPGRADED"
    THERMALLY_UPGRADED = "THERMALLY_UPGRADED"
    UNKNOWN = "UNKNOWN"


class ProfileVerificationStatus(str, Enum):
    """Verification status of asset metadata fields."""
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"


class ProfileField(BaseModel):
    """Metadata field with explicit provenance and verification status."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Any = Field(..., description="Configured or nameplate value")
    unit: str | None = Field(default=None, description="Physical unit if applicable")
    source_document: str = Field(..., description="Document or commissioning report providing the field")
    verified_by: str | None = Field(default=None, description="Entity or operator who verified the value")
    verified_at_utc: datetime | None = Field(default=None, description="Verification timestamp")
    status: ProfileVerificationStatus = Field(default=ProfileVerificationStatus.UNKNOWN, description="Field status")


class AssetProfile(BaseModel):
    """Immutable Asset Profile defining physical parameters and verified limits."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str = Field(..., description="Transformer asset identifier")
    phase_topology: Literal["THREE_PHASE_4W", "THREE_PHASE_3W", "SINGLE_PHASE"] = Field(
        default="THREE_PHASE_4W", description="Transformer winding topology"
    )
    nominal_frequency_hz: float = Field(default=50.0, description="Nominal power system frequency in Hz")
    rated_kva: float | None = Field(default=None, description="Verified rated apparent power in kVA")
    rated_voltage_hv_v: float | None = Field(default=None, description="Rated primary/HV line voltage in V")
    rated_voltage_lv_v: float | None = Field(default=None, description="Rated secondary/LV line-neutral voltage in V")
    cooling_class: str = Field(default="ONAN", description="Cooling class (e.g. ONAN, ONAF)")
    insulation_paper_class: InsulationClass = Field(default=InsulationClass.UNKNOWN, description="Insulation paper class")
    expected_cadence_s: int = Field(default=900, description="Expected nominal telemetry cadence in seconds (e.g. 900 for 15-min)")
    profile_status: ProfileVerificationStatus = Field(default=ProfileVerificationStatus.UNVERIFIED, description="Overall profile status")
    fields: dict[str, ProfileField] = Field(default_factory=dict, description="Detailed field-level provenance map")
    profile_version: str = Field(default="1.0.0", description="Version of the AssetProfile definition")
