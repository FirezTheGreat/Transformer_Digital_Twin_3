"""Telemetry Ingestion Router (Phase 7.2).

Provides POST /v1/telemetry endpoint for ingesting single or batch telemetry frames
and CanonicalEvents into the deterministic storage and digital twin state reducer.
"""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    AppState,
    get_app_state,
    get_capability_evaluator,
    get_reducer,
    get_storage,
)
from app.api.errors import ValidationException
from app.api.schemas import TelemetryIngestionRequest, TelemetryIngestionResponse
from app.core.storage import StorageEngine
from app.engine.capability import CapabilityEvaluator
from app.engine.fact_bundle import assemble_fact_bundle
from app.engine.reducer import TwinReducer
from app.models.telemetry import CanonicalEvent, RawTelemetryFrame

router = APIRouter(prefix="", tags=["Telemetry"])


@router.post(
    "/telemetry",
    response_model=TelemetryIngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest single telemetry frame or batch",
    description=(
        "Ingests incoming CanonicalEvents or RawTelemetryFrames. Validates schema, "
        "persists to temporal DuckDB/Parquet storage, executes the deterministic "
        "state transition reducer F(TwinState_{t-1}, Event_t) -> TwinState_t, and "
        "updates the active FactBundle."
    ),
)
async def ingest_telemetry(
    payload: TelemetryIngestionRequest,
    app_state: AppState = Depends(get_app_state),
    storage: StorageEngine = Depends(get_storage),
    reducer: TwinReducer = Depends(get_reducer),
    capability_evaluator: CapabilityEvaluator = Depends(get_capability_evaluator),
) -> TelemetryIngestionResponse:
    """Ingest single or batch telemetry events and update digital twin state."""
    events_to_process: list[CanonicalEvent] = []

    # Collect single or batch CanonicalEvents
    if payload.event is not None:
        events_to_process.append(payload.event)
    if payload.events:
        events_to_process.extend(payload.events)

    # Ingest RawTelemetryFrames if provided
    raw_frames: list[RawTelemetryFrame] = []
    if payload.frame is not None:
        raw_frames.append(payload.frame)
    if payload.frames:
        raw_frames.extend(payload.frames)

    if raw_frames:
        storage.insert_raw_frames(raw_frames)

    if not events_to_process and not raw_frames:
        raise ValidationException(
            message="No valid telemetry frames or CanonicalEvents provided in request body.",
            details={"payload": payload.model_dump(exclude_none=True)},
        )

    # Determine target asset ID
    target_asset_id = payload.asset_id
    if not target_asset_id:
        if events_to_process:
            target_asset_id = events_to_process[0].asset_id
        elif raw_frames:
            target_asset_id = app_state.settings.default_asset_id
        else:
            target_asset_id = app_state.settings.default_asset_id

    # Sort events chronologically to preserve determinism
    events_to_process.sort(key=lambda e: (e.event_time_utc, e.event_id))

    # Persist CanonicalEvents in storage
    if events_to_process:
        storage.insert_canonical_events(events_to_process)

    # Execute state transitions sequentially
    current_state = app_state.current_state
    for ev in events_to_process:
        current_state = reducer.reduce(current_state=current_state, event=ev)

    # Assemble updated FactBundle and update application state
    if current_state is not None:
        manifest = capability_evaluator.evaluate(current_state)
        fact_bundle = assemble_fact_bundle(
            state=current_state,
            capability_evaluator=capability_evaluator,
            capabilities=manifest,
        )
        app_state.update_state(current_state, fact_bundle)

    return TelemetryIngestionResponse(
        status="accepted",
        ingested_count=len(events_to_process) + len(raw_frames),
        asset_id=target_asset_id,
        latest_state_sequence=current_state.state_sequence if current_state else None,
        latest_state_hash=current_state.state_hash if current_state else None,
        latest_watermark_utc=current_state.event_time_watermark_utc if current_state else None,
    )
