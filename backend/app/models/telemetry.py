"""Canonical Telemetry, Source Envelope, and Ingestion Contracts."""

from datetime import datetime
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.units import validate_unit, canonicalize_unit_code


class QualitySeverity(str, Enum):
    """Quality severity classification conforming to OPC UA / canonical contract."""
    GOOD = "GOOD"
    UNCERTAIN = "UNCERTAIN"
    BAD = "BAD"


class SourceRef(BaseModel):
    """Provenance and origin metadata for raw and canonical events."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    system: str = Field(..., description="Source system identifier, e.g. 'tripura_csv' or 'cpri_mock'")
    adapter_id: str = Field(..., description="Adapter instance identifier, e.g. 'tripura_v1'")
    source_record_id: str = Field(..., description="Unique ID within source system, e.g. row number or tag")
    source_uri: str = Field(..., description="Relative or absolute URI of the source artifact")
    raw_sha256: str = Field(..., description="SHA-256 hash of the raw record bytes or payload")


class MeasurementQuality(BaseModel):
    """Quality status and diagnostics for an individual measurement."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: QualitySeverity = Field(default=QualitySeverity.GOOD, description="Quality severity level")
    flags: list[str] = Field(default_factory=list, description="Specific quality flags (e.g. MISSING, OUT_OF_RANGE, STALE)")
    source_code: str | None = Field(default=None, description="Original source quality or status code if provided")


class Measurement(BaseModel):
    """Typed canonical measurement observation."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    signal_id: str = Field(..., description="Canonical signal ID from measurement registry")
    phase: Literal["L1", "L2", "L3", "N", "L1_L2", "L2_L3", "L3_L1"] | None = Field(
        default=None, description="Electrical phase or line-to-line association"
    )
    value: float | int | str | bool = Field(..., description="Normalized measurement value")
    value_type: Literal["float", "int", "str", "bool"] = Field(..., description="Data type of value")
    unit_ucum: str = Field(..., description="Canonical UCUM unit code")
    original_name: str = Field(..., description="Source column header or tag name")
    original_value: str = Field(..., description="Raw value string before normalization")
    original_unit: str = Field(..., description="Raw unit string reported by source")
    quality: MeasurementQuality = Field(default_factory=MeasurementQuality, description="Measurement quality record")

    @field_validator("unit_ucum")
    @classmethod
    def check_unit(cls, v: str) -> str:
        canon = canonicalize_unit_code(v)
        if not validate_unit(canon):
            raise ValueError(f"Invalid or unrecognized UCUM unit: '{v}' (canonical: '{canon}')")
        return canon


class CanonicalEvent(BaseModel):
    """Immutable Canonical Telemetry Event Envelope."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(default="1.0.0", description="Contract schema version")
    event_id: str = Field(..., description="Stable deterministic event UUID v5 or source-derived ID")
    asset_id: str = Field(..., description="Transformer asset identifier")
    event_time_utc: datetime = Field(..., description="Physical timestamp when the event occurred in UTC")
    received_time_utc: datetime = Field(..., description="Ingest timestamp when the event reached the twin in UTC")
    source: SourceRef = Field(..., description="Provenance information")
    measurements: list[Measurement] = Field(..., min_length=1, description="List of canonical measurements")
    event_quality_flags: list[str] = Field(default_factory=list, description="Envelope-level quality flags")
    mapping_version: str = Field(..., description="Adapter tag mapping version string")


class RawTelemetryFrame(BaseModel):
    """Raw ingested record prior to canonicalization."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_id: str = Field(..., description="Deterministic record ID")
    source_system: str = Field(..., description="Source system origin")
    received_time_utc: datetime = Field(..., description="Ingest timestamp in UTC")
    raw_payload: dict[str, Any] = Field(..., description="Unmodified raw record key-value payload")
    raw_sha256: str = Field(..., description="SHA-256 hash of the raw record")
