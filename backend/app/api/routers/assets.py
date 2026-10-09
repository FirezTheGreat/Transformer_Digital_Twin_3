"""Asset State, History, and Capability Endpoints (Phase 7.2).

Provides:
- GET /v1/assets/{asset_id}/state: Active state vector and capability tier.
- GET /v1/assets/{asset_id}/history: Historical telemetry and events query.
- GET /v1/assets/{asset_id}/capabilities: Dynamic C0–C4 capability tier manifest.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    AppState,
    get_app_state,
    get_capability_evaluator,
    get_storage,
)
from app.api.errors import AssetNotFoundException
from app.api.schemas import AssetStateResponse, HistoryResponse
from app.core.checkpoint import compute_twin_state_hash
from app.core.storage import StorageEngine
from app.engine.capability import CapabilityEvaluator
from app.engine.fact_bundle import assemble_fact_bundle
from app.models.capability import CapabilityManifest, CapabilityTier
from app.models.twin_state import TwinState

router = APIRouter(prefix="/assets", tags=["Assets"])


def _get_or_create_asset_state(
    asset_id: str,
    app_state: AppState,
    capability_evaluator: CapabilityEvaluator,
) -> tuple[TwinState, CapabilityManifest]:
    """Retrieve active asset state or initialize deterministic baseline state."""
    if app_state.current_state is not None and app_state.current_state.asset_id == asset_id:
        state = app_state.current_state
        manifest = capability_evaluator.evaluate(state)
        return state, manifest

    # Build initial baseline state for asset
    epoch_time = datetime(1970, 1, 1, tzinfo=timezone.utc)
    base_state = TwinState(
        asset_id=asset_id,
        state_time_utc=epoch_time,
        last_processed_event_id="initial",
        event_time_watermark_utc=epoch_time,
        state_sequence=0,
        state_hash="",
    )
    computed_hash = compute_twin_state_hash(base_state.model_dump())
    state = base_state.model_copy(update={"state_hash": computed_hash})
    manifest = capability_evaluator.evaluate(state)
    return state, manifest


@router.get(
    "/{asset_id}/state",
    response_model=AssetStateResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current digital twin state and active capability tier",
)
async def get_asset_state(
    asset_id: str,
    app_state: AppState = Depends(get_app_state),
    capability_evaluator: CapabilityEvaluator = Depends(get_capability_evaluator),
) -> AssetStateResponse:
    """Fetch the latest state vector, active capability tier, and FactBundle for asset."""
    state, manifest = _get_or_create_asset_state(asset_id, app_state, capability_evaluator)
    fact_bundle = app_state.latest_fact_bundle
    if fact_bundle is None or fact_bundle.asset_id != asset_id:
        fact_bundle = assemble_fact_bundle(
            state=state,
            capability_evaluator=capability_evaluator,
            capabilities=manifest,
        )

    return AssetStateResponse(
        asset_id=asset_id,
        state_time_utc=state.state_time_utc,
        highest_tier=manifest.highest_tier,
        twin_state=state,
        fact_bundle=fact_bundle,
    )


@router.get(
    "/{asset_id}/history",
    response_model=HistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query historical canonical telemetry events",
)
async def get_asset_history(
    asset_id: str,
    start_time: datetime | None = Query(default=None, description="Start timestamp filter in UTC"),
    end_time: datetime | None = Query(default=None, description="End timestamp filter in UTC"),
    limit: int = Query(default=500, ge=1, le=5000, description="Max number of events to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    order_asc: bool = Query(default=True, description="Sort order: True for ascending (default), False for descending"),
    storage: StorageEngine = Depends(get_storage),
) -> HistoryResponse:
    """Query chronological historical telemetry events from temporal storage."""
    events = storage.get_canonical_events(
        asset_id=asset_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=offset,
        order_asc=order_asc,
    )

    return HistoryResponse(
        asset_id=asset_id,
        start_time_utc=start_time,
        end_time_utc=end_time,
        event_count=len(events),
        events=events,
    )


@router.get(
    "/{asset_id}/capabilities",
    response_model=CapabilityManifest,
    status_code=status.HTTP_200_OK,
    summary="Get active C0-C4 capability tiers and fallback reason codes",
)
async def get_asset_capabilities(
    asset_id: str,
    app_state: AppState = Depends(get_app_state),
    capability_evaluator: CapabilityEvaluator = Depends(get_capability_evaluator),
) -> CapabilityManifest:
    """Return dynamic capability manifest with active operational tiers and fallback codes."""
    state, manifest = _get_or_create_asset_state(asset_id, app_state, capability_evaluator)
    return manifest
