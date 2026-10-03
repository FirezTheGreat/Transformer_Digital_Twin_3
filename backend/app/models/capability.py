"""Capability Manifest and Operating Tier Contracts."""

from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class CapabilityTier(str, Enum):
    """Hierarchical operational capability tiers."""
    C0_INTEGRITY = "C0"
    C1_ELECTRICAL = "C1"
    C2_THERMAL_DESCRIPTIVE = "C2"
    C3_THERMAL_PREDICTIVE = "C3"
    C4_THERMAL_EXPOSURE = "C4"


class CapabilityItem(BaseModel):
    """Status and prerequisite fulfillment for an individual analytical capability."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(..., description="Whether this capability is currently operational")
    evidence_grade: Literal["A", "B", "C", "U"] = Field(..., description="Evidence grade supporting this capability")
    required_inputs: list[str] = Field(default_factory=list, description="List of required signal IDs or metadata keys")
    missing_inputs: list[str] = Field(default_factory=list, description="List of currently missing or invalid inputs")
    disabled_reason_codes: list[str] = Field(default_factory=list, description="Deterministic reason codes if disabled")
    coverage_pct: float = Field(default=100.0, ge=0.0, le=100.0, description="Temporal data coverage percentage")
    model_status: str = Field(default="NOT_APPLICABLE", description="Underlying model promotion/fallback status")
    extrapolation: bool = Field(default=False, description="Whether current inputs fall outside calibrated training range")


class CapabilityManifest(BaseModel):
    """Dynamic manifest reflecting active capabilities and fallback states."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str = Field(..., description="Transformer asset identifier")
    evaluated_at_utc: datetime = Field(..., description="Timestamp when capability was evaluated in UTC")
    evaluation_window_s: int = Field(default=86400, description="Evaluation window duration in seconds")
    highest_tier: CapabilityTier = Field(..., description="Highest currently supported capability tier (C0–C4)")
    available_signal_ids: list[str] = Field(default_factory=list, description="List of currently active and valid signals")
    verified_metadata_ids: list[str] = Field(default_factory=list, description="List of verified asset profile metadata fields")
    expected_cadence_s: int = Field(default=900, description="Configured telemetry cadence")
    current_freshness_s: float = Field(..., ge=0.0, description="Elapsed seconds since last accepted valid observation")
    capabilities: dict[str, CapabilityItem] = Field(default_factory=dict, description="Map of capability ID to item status")
    schema_version: str = Field(default="1.0.0", description="Contract schema version")
    profile_version: str = Field(default="1.0.0", description="Asset profile version")
    model_version: str = Field(default="uncalibrated", description="Thermal model version")
