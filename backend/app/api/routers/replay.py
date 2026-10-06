from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    AppState,
    get_app_state,
    get_capability_evaluator,
    get_reducer,
    get_replay_engine,
    get_storage,
)
from app.api.errors import ReplayException
from app.api.schemas import ReplayControlRequest, ReplayStatusResponse
from app.core.storage import StorageEngine
from app.engine.capability import CapabilityEvaluator
from app.engine.fact_bundle import assemble_fact_bundle
from app.engine.reducer import TwinReducer
from app.engine.replay import ReplayEngine
from app.models.capability import CapabilityTier

router = APIRouter(prefix="", tags=["Replay"])


@router.post(
    "/replay",
    response_model=ReplayStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Control deterministic chronological replay",
    description=(
        "Controls historical replay playback. Actions: 'start', 'step', 'pause', "
        "'resume', 'reset', 'seek'. Advancing replay steps events sequentially into "
        "the state transition reducer and updates active twin state and FactBundle."
    ),
)
async def control_replay(
    payload: ReplayControlRequest,
    app_state: AppState = Depends(get_app_state),
    storage: StorageEngine = Depends(get_storage),
    reducer: TwinReducer = Depends(get_reducer),
    replay_engine: ReplayEngine = Depends(get_replay_engine),
    capability_evaluator: CapabilityEvaluator = Depends(get_capability_evaluator),
) -> ReplayStatusResponse:
    """Execute playback action on the deterministic replay engine."""
    action = payload.action

    # Ensure events are populated from storage if empty
    if not replay_engine._events and storage is not None:
        replay_engine.load_from_storage()

    # Configure time bounds if requested
    if payload.start_time_utc is not None or payload.end_time_utc is not None:
        replay_engine.start_time = payload.start_time_utc
        replay_engine.end_time = payload.end_time_utc
        replay_engine.load_from_storage()

    # Configure speed multiplier
    replay_engine.speed_multiplier = payload.speed_multiplier

    if action == "start":
        replay_engine.reset()
        replay_engine._is_running = True
        replay_engine._is_paused = False

    elif action == "pause":
        replay_engine.pause()

    elif action == "resume":
        replay_engine._is_paused = False
        replay_engine._is_running = True

    elif action == "reset":
        replay_engine.reset()
        app_state.current_state = None
        app_state.latest_fact_bundle = None

    elif action == "seek":
        if payload.seek_position is not None:
            if payload.seek_position < 0 or payload.seek_position > len(replay_engine._events):
                raise ReplayException(
                    message=f"Invalid seek position: {payload.seek_position}",
                    details={"total_events": len(replay_engine._events)},
                )
            replay_engine.seek(payload.seek_position)
        elif payload.start_time_utc is not None:
            replay_engine.seek_time(payload.start_time_utc)
        else:
            raise ReplayException(
                message="Seek action requires either seek_position or start_time_utc.",
            )

    elif action == "step":
        stepped_events: list[CanonicalEvent] = []
        for _ in range(payload.batch_size):
            ev = replay_engine.step()
            if ev is None:
                break
            stepped_events.append(ev)

        current_state = app_state.current_state
        for ev in stepped_events:
            current_state = reducer.reduce(current_state=current_state, event=ev)

        if current_state is not None:
            manifest = capability_evaluator.evaluate(current_state)
            fact_bundle = assemble_fact_bundle(
                state=current_state,
                capability_evaluator=capability_evaluator,
                capabilities=manifest,
            )
            app_state.update_state(current_state, fact_bundle)

    progress = replay_engine.get_progress()
    current_state = app_state.current_state

    # Determine status label
    if progress["is_running"]:
        status_label = "running"
    elif progress["is_paused"]:
        status_label = "paused"
    elif progress["is_finished"] and progress["total_events"] > 0:
        status_label = "completed"
    elif progress["cursor"] == 0:
        status_label = "reset"
    else:
        status_label = "idle"

    current_time_str = progress.get("current_event_time")
    curr_dt = datetime.fromisoformat(current_time_str) if current_time_str else None

    highest_tier = (
        app_state.latest_fact_bundle.capabilities.highest_tier
        if app_state.latest_fact_bundle
        else (CapabilityTier.C0_INTEGRITY if current_state else None)
    )

    return ReplayStatusResponse(
        status=status_label,
        current_time_utc=curr_dt,
        speed_multiplier=progress["speed_multiplier"],
        processed_events=progress["cursor"],
        total_events=progress["total_events"],
        is_completed=progress["is_finished"],
        current_state_sequence=current_state.state_sequence if current_state else None,
        highest_tier=highest_tier,
    )
