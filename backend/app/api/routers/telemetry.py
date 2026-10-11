"""Telemetry Ingestion Router (Phase 7.2).

Provides POST /v1/telemetry endpoint for ingesting single or batch telemetry frames
and CanonicalEvents into the deterministic storage and digital twin state reducer.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
from app.core.registry import CPRI_SYNTHETIC_ASSET_RATINGS, GRIDPULSE_CANDIDATE_ASSETS
from app.core.storage import StorageEngine
from app.engine.capability import CapabilityEvaluator
from app.engine.fact_bundle import assemble_fact_bundle
from app.engine.reducer import TwinReducer
from app.engine.replay import OPERATOR_INJECTED_FLAG
from app.models.telemetry import CanonicalEvent, RawTelemetryFrame

router = APIRouter(prefix="", tags=["Telemetry"])

# Assets whose telemetry comes from a dataset replay; out-of-band events must align with that replay
REPLAY_DATASET_ASSETS: frozenset[str] = frozenset({*CPRI_SYNTHETIC_ASSET_RATINGS, *GRIDPULSE_CANDIDATE_ASSETS})


def _utc(t: datetime) -> datetime:
    return t if t.tzinfo is not None else t.replace(tzinfo=timezone.utc)


def _align_with_active_replay(
    app_state: AppState,
    asset_id: str,
    events: list[CanonicalEvent],
) -> list[CanonicalEvent]:
    """Keep out-of-band events (e.g. an injected trip) consistent with an active dataset replay.

    The reducer discards any event older than the twin watermark. An injected event stamped outside
    the replay timeline (e.g. wall-clock time) would push the watermark past every remaining replay
    frame, silently freezing the twin, and with it a protection-trip OTHI of 0, for the rest of the run.
    Such events are rejected; accepted ones are flagged so they are never replayed as dataset telemetry.
    """
    replay = app_state.replay_engine
    replay_loaded = replay is not None and replay.asset_id == asset_id and bool(replay._events)
    if not events or not (replay_loaded or asset_id in REPLAY_DATASET_ASSETS):
        return events

    if not replay_loaded:
        raise ValidationException(
            message=f"Replay timeline for asset {asset_id} is not loaded; start its replay before injecting telemetry.",
            details={"asset_id": asset_id},
        )

    first = _utc(replay._events[0].event_time_utc)
    state = app_state.current_state
    if (state is None or state.asset_id != asset_id) and any(_utc(ev.event_time_utc) > first for ev in events):
        # With no frame processed yet, an event later than the first replay frame would make the
        # reducer discard every replay frame before it.
        raise ValidationException(
            message=f"Step the replay for asset {asset_id} before injecting telemetry later than its first frame.",
            details={"asset_id": asset_id, "replay_start_utc": first.isoformat()},
        )

    last = _utc(replay._events[-1].event_time_utc)
    profile = getattr(app_state.reducer, "profile", None) if app_state.reducer else None
    cadence = timedelta(seconds=(profile.expected_cadence_s if profile and profile.expected_cadence_s else 1800))
    outside = [
        ev.event_id for ev in events if not (first - cadence <= _utc(ev.event_time_utc) <= last + cadence)
    ]
    if outside:
        raise ValidationException(
            message=(
                f"Injected event time is outside the replay timeline for asset {asset_id} "
                f"({first.isoformat()} .. {last.isoformat()}); stamp it relative to the twin watermark."
            ),
            details={"event_ids": outside, "replay_start_utc": first.isoformat(), "replay_end_utc": last.isoformat()},
        )

    return [
        ev
        if OPERATOR_INJECTED_FLAG in ev.event_quality_flags
        else ev.model_copy(update={"event_quality_flags": [*ev.event_quality_flags, OPERATOR_INJECTED_FLAG]})
        for ev in events
    ]


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

    events_to_process = _align_with_active_replay(app_state, target_asset_id, events_to_process)

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
