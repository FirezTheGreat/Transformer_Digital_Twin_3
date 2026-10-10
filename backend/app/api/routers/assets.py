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

from app.core.registry import CPRI_SYNTHETIC_ASSET_RATINGS, GRIDPULSE_CANDIDATE_ASSETS, resolve_asset_profile, resolve_model_artifact
from app.adapters.gridpulse_synthetic import SYNTHETIC_ASSET_PROFILES
from app.api.deps import (
    AppState,
    get_app_state,
    get_capability_evaluator,
    get_replay_engine,
    get_storage,
)
from app.api.errors import AssetNotFoundException
from app.api.schemas import AssetStateResponse, HistoryResponse
from app.core.checkpoint import compute_twin_state_hash
from app.core.storage import StorageEngine
from app.engine.capability import CapabilityEvaluator
from app.engine.fact_bundle import assemble_fact_bundle
from app.engine.replay import ReplayEngine
from app.models.capability import CapabilityManifest, CapabilityTier
from app.models.twin_state import TwinState

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="List available datasets, transformers, and active selection",
)
async def list_available_assets(
    app_state: AppState = Depends(get_app_state),
    replay_engine: ReplayEngine = Depends(get_replay_engine),
) -> dict[str, Any]:
    """Return inventory of available datasets and assets with current active selection."""
    active_asset = (
        (app_state.current_state.asset_id if app_state.current_state else None)
        or replay_engine.asset_id
        or app_state.settings.default_asset_id
    )
    active_dataset = "gridpulse_synthetic_v1" if active_asset in GRIDPULSE_CANDIDATE_ASSETS else "cpri_v3_0_2"

    return {
        "active_dataset_id": active_dataset,
        "active_asset_id": active_asset,
        "datasets": [
            {
                "dataset_id": "cpri_v3_0_2",
                "name": "CPRI Synthetic Benchmark v3.0.2",
                "status": "BASELINE_ROLLBACK",
                "cadence_seconds": 1800,
                "cadence_label": "30 min",
                "description": "Preserved baseline benchmark dataset and calibrated TX_1000_COMM checkpoint",
                "assets": [
                    {
                        "asset_id": aid,
                        "rated_kva": rating,
                        "promotion_status": "PROMOTED" if aid == "TX_1000_COMM" else "NOT_PROMOTED",
                        "tank_type": "CONSERVATOR",
                        "has_oil_level_gauge": False,
                        "has_pressure_sensor": False,
                    }
                    for aid, rating in CPRI_SYNTHETIC_ASSET_RATINGS.items()
                ],
            },
            {
                "dataset_id": "gridpulse_synthetic_v1",
                "name": "GridPulse Synthetic Benchmark v1.0.0",
                "status": "EVALUATED_CANDIDATE",
                "cadence_seconds": 1800,
                "cadence_label": "30 min",
                "description": "Evaluated candidate dataset (DT-01 promoted, CAL partition replay)",
                "assets": [
                    {
                        "asset_id": aid,
                        "rated_kva": SYNTHETIC_ASSET_PROFILES[aid].rated_kva,
                        "promotion_status": "PROMOTED" if aid == "DT-01" else "NOT_PROMOTED",
                        "tank_type": SYNTHETIC_ASSET_PROFILES[aid].tank_type,
                        "has_oil_level_gauge": SYNTHETIC_ASSET_PROFILES[aid].has_oil_level_gauge,
                        "has_pressure_sensor": SYNTHETIC_ASSET_PROFILES[aid].has_pressure_sensor,
                    }
                    for aid in GRIDPULSE_CANDIDATE_ASSETS
                ],
            },
        ],
    }


def _get_evaluator_for_asset(
    asset_id: str,
    app_state: AppState,
    capability_evaluator: CapabilityEvaluator,
) -> CapabilityEvaluator:
    """Ensure capability evaluator matches target asset's construction profile and promotion."""
    if capability_evaluator.profile is not None and capability_evaluator.profile.asset_id == asset_id:
        return capability_evaluator
    profile = resolve_asset_profile(asset_id=asset_id)
    artifact = resolve_model_artifact(asset_id=asset_id)
    is_promoted = artifact.parameters is not None and artifact.promotion.status == "PROMOTED"
    return CapabilityEvaluator(
        profile=profile,
        expected_cadence_s=profile.expected_cadence_s,
        evaluation_window_s=app_state.settings.evaluation_window_s,
        is_model_promoted=is_promoted,
        qualification=artifact.qualification if is_promoted else None,
        model_version=artifact.model_version if is_promoted else "uncalibrated",
    )


def _get_or_create_asset_state(
    asset_id: str,
    app_state: AppState,
    capability_evaluator: CapabilityEvaluator,
) -> tuple[TwinState, CapabilityManifest, CapabilityEvaluator]:
    """Retrieve active asset state or initialize deterministic baseline state."""
    evaluator = _get_evaluator_for_asset(asset_id, app_state, capability_evaluator)
    if app_state.current_state is not None and app_state.current_state.asset_id == asset_id:
        state = app_state.current_state
        manifest = evaluator.evaluate(state)
        return state, manifest, evaluator

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
    manifest = evaluator.evaluate(state)
    return state, manifest, evaluator


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
    state, manifest, evaluator = _get_or_create_asset_state(asset_id, app_state, capability_evaluator)
    fact_bundle = app_state.latest_fact_bundle
    if fact_bundle is None or fact_bundle.asset_id != asset_id:
        fact_bundle = assemble_fact_bundle(
            state=state,
            capability_evaluator=evaluator,
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
    state, manifest, _ = _get_or_create_asset_state(asset_id, app_state, capability_evaluator)
    return manifest
