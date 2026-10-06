"""Pydantic API Schema Foundation and Route Contracts (Phase 7.2).

Provides request and response models for telemetry ingestion, replay control,
asset state, historical queries, and dynamic capability tier manifests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.models.capability import CapabilityManifest, CapabilityTier
from app.models.fact_bundle import FactBundle
from app.models.telemetry import CanonicalEvent, RawTelemetryFrame
from app.models.twin_state import TwinState


class ErrorBody(BaseModel):
    """Detailed error object structure."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str = Field(..., description="Machine-readable deterministic error code")
    message: str = Field(..., description="Human-readable explanation of error")
    details: Any = Field(default_factory=dict, description="Structured error context or field diagnostics")
    timestamp_utc: str = Field(..., description="UTC ISO 8601 timestamp of error occurrence")


class ErrorResponse(BaseModel):
    """Standardized error envelope returned on all 4xx and 5xx responses."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    error: ErrorBody = Field(..., description="Error detail payload")


class HealthCheckResponse(BaseModel):
    """Application health and status summary response."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str = Field(default="ok", description="Application operational status (e.g. ok, degraded)")
    app_name: str = Field(..., description="Digital Twin application name")
    version: str = Field(..., description="Application semantic version")
    environment: str = Field(..., description="Deployment environment (development, test, production)")
    timestamp_utc: datetime = Field(..., description="Current server UTC timestamp")
    default_asset_id: str = Field(..., description="Configured default asset identifier")
    is_ready: bool = Field(default=True, description="Whether core engines and storage are initialized")
    details: dict[str, Any] = Field(default_factory=dict, description="Subsystem health statuses")


class TelemetryIngestionRequest(BaseModel):
    """Flexible ingestion payload accepting single frames, canonical events, or batches."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    event: CanonicalEvent | None = Field(default=None, description="Single CanonicalEvent to ingest")
    events: list[CanonicalEvent] = Field(default_factory=list, description="Batch of CanonicalEvents to ingest")
    frame: RawTelemetryFrame | None = Field(default=None, description="Single RawTelemetryFrame to canonicalize and ingest")
    frames: list[RawTelemetryFrame] = Field(default_factory=list, description="Batch of RawTelemetryFrames to canonicalize and ingest")
    asset_id: str | None = Field(default=None, description="Optional target asset ID override")


class TelemetryIngestionResponse(BaseModel):
    """Response returned upon successful telemetry ingestion."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str = Field(default="accepted", description="Ingestion status (e.g. accepted)")
    ingested_count: int = Field(..., ge=0, description="Total number of events ingested and reduced")
    asset_id: str = Field(..., description="Target transformer asset identifier")
    latest_state_sequence: int | None = Field(default=None, description="Latest monotonic state sequence number")
    latest_state_hash: str | None = Field(default=None, description="Latest state vector SHA-256 hash")
    latest_watermark_utc: datetime | None = Field(default=None, description="Latest event-time watermark in UTC")


class ReplayControlRequest(BaseModel):
    """Deterministic chronological replay control request."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Literal["start", "pause", "resume", "step", "reset", "seek"] = Field(
        default="step",
        description="Replay playback control action",
    )
    speed_multiplier: float = Field(
        default=1.0,
        ge=0.0,
        description="Replay speed multiplier (0.0 = max speed, 1.0 = real-time, 5.0 = 5x)",
    )
    batch_size: int = Field(
        default=1,
        ge=1,
        le=5000,
        description="Number of events to advance per step action",
    )
    start_time_utc: datetime | None = Field(
        default=None,
        description="Optional start boundary filter in UTC",
    )
    end_time_utc: datetime | None = Field(
        default=None,
        description="Optional end boundary filter in UTC",
    )
    seek_position: int | None = Field(
        default=None,
        ge=0,
        description="Target event index position for seek action",
    )
    asset_id: str | None = Field(
        default=None,
        description="Target transformer asset identifier",
    )


class ReplayStatusResponse(BaseModel):
    """Replay engine status and playback position."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str = Field(..., description="Playback status (idle, running, paused, completed, reset)")
    current_time_utc: datetime | None = Field(default=None, description="Current replay timestamp in UTC")
    speed_multiplier: float = Field(..., description="Active replay speed multiplier")
    processed_events: int = Field(..., ge=0, description="Number of events replayed so far")
    total_events: int = Field(..., ge=0, description="Total number of events in replay queue")
    is_completed: bool = Field(..., description="True if replay queue has been exhausted")
    current_state_sequence: int | None = Field(default=None, description="Current twin state sequence")
    highest_tier: CapabilityTier | None = Field(default=None, description="Current highest operational capability tier")


class AssetStateResponse(BaseModel):
    """Current state vector and capability tier response."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str = Field(..., description="Transformer asset identifier")
    state_time_utc: datetime = Field(..., description="Timestamp of the twin state in UTC")
    highest_tier: CapabilityTier = Field(..., description="Highest currently operational capability tier")
    twin_state: TwinState = Field(..., description="Complete snapshot of the stateful digital twin")
    fact_bundle: FactBundle | None = Field(default=None, description="Unified immutable FactBundle snapshot")


class HistoryResponse(BaseModel):
    """Historical telemetry query response."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str = Field(..., description="Transformer asset identifier")
    start_time_utc: datetime | None = Field(default=None, description="Query start timestamp filter in UTC")
    end_time_utc: datetime | None = Field(default=None, description="Query end timestamp filter in UTC")
    event_count: int = Field(..., ge=0, description="Number of historical events returned")
    events: list[CanonicalEvent] = Field(default_factory=list, description="List of chronologically sorted CanonicalEvents")


class OperatorFeedbackRequest(BaseModel):
    """Operator feedback submission payload."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_id: str = Field(..., description="Transformer asset identifier")
    action: str = Field(..., description="Operator decision action (ACKNOWLEDGE, DISMISS, INSPECTION_OUTCOME, OVERRIDE)")
    operator_id: str = Field(..., description="Authenticated or demo operator username/ID")
    feedback_id: str | None = Field(default=None, description="Optional client-provided feedback event UUID")
    timestamp_utc: datetime | None = Field(default=None, description="Optional action timestamp in UTC")
    recommendation_id: str | None = Field(default=None, description="Linked recommendation ID if applicable")
    merge_key: str | None = Field(default=None, description="Linked merge_key or condition family if applicable")
    actor_id: str | None = Field(default=None, description="Optional actor identifier alias")
    reason_code: str | None = Field(default=None, description="Structured dismissal or override reason code")
    notes: str | None = Field(default=None, description="Operator explanation or physical inspection findings")
    rationale: str | None = Field(default=None, description="Detailed engineering rationale for dismissal or override")
    inspection_outcome: dict[str, Any] | None = Field(default=None, description="Structured physical inspection findings")
    authorized_role: str | None = Field(default=None, description="Role of operator if performing an authorized override")
    override_expiry_utc: datetime | None = Field(default=None, description="Expiry timestamp for advisory override")

