"""Reports Router for Structured JSON, CSV, and WeasyPrint PDF Exports (Phase 9.3).

Provides machine-readable and audit report endpoints:
- GET /v1/reports/summary.json: Full structured ReportData JSON payload.
- GET /v1/reports/summary.csv: Tabular engineering and audit CSV document.
- GET /v1/reports/summary.pdf: High-fidelity engineering audit PDF document.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import (
    AppState,
    get_app_state,
    get_capability_evaluator,
    get_storage,
)
from app.core.checkpoint import compute_twin_state_hash
from app.core.storage import StorageEngine
from app.engine.capability import CapabilityEvaluator
from app.engine.fact_bundle import assemble_fact_bundle
from app.models.capability import CapabilityManifest
from app.models.fact_bundle import FactBundle
from app.models.twin_state import TwinState
from app.reports.exporters import export_report_csv, export_report_json
from app.reports.pdf_renderer import render_report_pdf
from app.reports.report_generator import generate_report_data

router = APIRouter(prefix="/reports", tags=["Reports"])


def _resolve_fact_bundle(
    asset_id: str,
    app_state: AppState,
    capability_evaluator: CapabilityEvaluator,
) -> FactBundle:
    """Resolve or assemble authoritative FactBundle for target asset."""
    if (
        app_state.latest_fact_bundle is not None
        and app_state.latest_fact_bundle.asset_id == asset_id
    ):
        return app_state.latest_fact_bundle

    if (
        app_state.current_state is not None
        and app_state.current_state.asset_id == asset_id
    ):
        state = app_state.current_state
        manifest = capability_evaluator.evaluate(state)
        return assemble_fact_bundle(
            state=state,
            capability_evaluator=capability_evaluator,
            capabilities=manifest,
        )

    # Initialize deterministic baseline snapshot if asset state has not yet processed events
    now = datetime.now(timezone.utc)
    base_state = TwinState(
        asset_id=asset_id,
        state_time_utc=now,
        last_processed_event_id="initial",
        event_time_watermark_utc=now,
        state_sequence=0,
        state_hash="",
    )
    computed_hash = compute_twin_state_hash(base_state.model_dump())
    state = base_state.model_copy(update={"state_hash": computed_hash})
    manifest = capability_evaluator.evaluate(state)
    return assemble_fact_bundle(
        state=state,
        capability_evaluator=capability_evaluator,
        capabilities=manifest,
    )


def _resolve_report_bundle(
    asset_id: Optional[str],
    checkpoint_id: Optional[str],
    app_state: AppState,
    capability_evaluator: CapabilityEvaluator,
    storage: StorageEngine,
) -> tuple[str, FactBundle, Optional[datetime]]:
    """Resolve target asset, authoritative FactBundle, and optional checkpoint state time.

    If checkpoint_id is provided:
    - Loads checkpoint record from storage.
    - Raises HTTP 404 if checkpoint is not found.
    - Validates asset ownership: raises HTTP 400 if asset_id is specified and does not match checkpoint asset.
    - Reconstructs point-in-time TwinState.
    - Evaluates capability manifest against reconstructed state with active engine rules.
    - Assembles deterministic FactBundle.
    - Returns (target_asset, bundle, state_time_utc).

    If checkpoint_id is None:
    - Resolves live state or baseline snapshot for target_asset.
    - Returns (target_asset, bundle, None).
    """
    if checkpoint_id:
        row = storage.get_checkpoint_by_id(checkpoint_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Checkpoint '{checkpoint_id}' not found",
            )
        checkpoint_asset = row["asset_id"]
        if asset_id is not None and checkpoint_asset != asset_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Checkpoint '{checkpoint_id}' belongs to asset '{checkpoint_asset}', not '{asset_id}'",
            )
        target_asset = checkpoint_asset
        twin_state = TwinState.model_validate_json(row["state_json"])
        manifest = capability_evaluator.evaluate(twin_state)
        bundle = assemble_fact_bundle(
            state=twin_state,
            capability_evaluator=capability_evaluator,
            capabilities=manifest,
        )
        return target_asset, bundle, twin_state.state_time_utc

    target_asset = asset_id or app_state.settings.default_asset_id
    bundle = _resolve_fact_bundle(target_asset, app_state, capability_evaluator)
    return target_asset, bundle, None


@router.get(
    "/runs",
    status_code=status.HTTP_200_OK,
    summary="List available persisted checkpoints / historical runs",
    response_description="List of checkpoint run metadata",
)
async def list_runs(
    asset_id: Optional[str] = Query(default=None, description="Filter by asset ID (defaults to all)"),
    limit: int = Query(default=100, ge=1, le=500, description="Max runs to return"),
    storage: StorageEngine = Depends(get_storage),
) -> list[dict[str, Any]]:
    """Return available persisted twin state checkpoints for historical analysis.

    Each record represents a verified persisted point-in-time snapshot with sequence,
    hash, and timestamp metadata.
    """
    return storage.get_checkpoints(asset_id=asset_id, limit=limit)


@router.get(
    "/summary.json",
    status_code=status.HTTP_200_OK,
    summary="Export complete authoritative digital twin report in JSON format",
    response_description="Deterministic structured JSON report",
)
async def get_summary_json(
    asset_id: Optional[str] = Query(default=None, description="Asset ID (defaults to active asset)"),
    checkpoint_id: Optional[str] = Query(default=None, description="Checkpoint ID for historical run"),
    app_state: AppState = Depends(get_app_state),
    capability_evaluator: CapabilityEvaluator = Depends(get_capability_evaluator),
    storage: StorageEngine = Depends(get_storage),
) -> Response:
    """Serialize the ReportData for either the live state or a historic checkpoint.

    When checkpoint_id is provided, state is reconstructed from the persisted
    point-in-time checkpoint snapshot. Re-evaluating capabilities evaluates the snapshot
    state directly with current rules; full historical telemetry is not recreated by this call.
    When omitted, the current live asset state is used.
    """
    target_asset, bundle, _ = _resolve_report_bundle(
        asset_id=asset_id,
        checkpoint_id=checkpoint_id,
        app_state=app_state,
        capability_evaluator=capability_evaluator,
        storage=storage,
    )
    report_data = generate_report_data(bundle)
    json_output = export_report_json(report_data)

    filename = f"summary_{target_asset}{'_' + checkpoint_id if checkpoint_id else ''}.json"
    return Response(
        content=json_output,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/summary.csv",
    status_code=status.HTTP_200_OK,
    summary="Export tabular digital twin state and historical telemetry in CSV format",
    response_description="Deterministic CSV report with time-series, episodes, and recommendations",
)
async def get_summary_csv(
    asset_id: Optional[str] = Query(default=None, description="Asset ID (defaults to active asset)"),
    checkpoint_id: Optional[str] = Query(default=None, description="Checkpoint ID for historical run"),
    limit: int = Query(default=500, ge=1, le=5000, description="Max historical telemetry events to include"),
    app_state: AppState = Depends(get_app_state),
    storage: StorageEngine = Depends(get_storage),
    capability_evaluator: CapabilityEvaluator = Depends(get_capability_evaluator),
) -> Response:
    """Serialize the authoritative ReportData and temporal telemetry into deterministic tabular CSV.

    When checkpoint_id is provided, state is reconstructed from the persisted point-in-time
    snapshot and historical telemetry is queried from canonical events up to that snapshot watermark.
    """
    target_asset, bundle, checkpoint_time = _resolve_report_bundle(
        asset_id=asset_id,
        checkpoint_id=checkpoint_id,
        app_state=app_state,
        capability_evaluator=capability_evaluator,
        storage=storage,
    )
    report_data = generate_report_data(bundle)

    # Query historical events from storage for time-series section
    historical_events = storage.get_canonical_events(
        asset_id=target_asset,
        end_time=checkpoint_time,
        limit=limit,
        order_asc=True,
    )

    csv_output = export_report_csv(report_data, historical_events=historical_events)

    filename = f"summary_{target_asset}{'_' + checkpoint_id if checkpoint_id else ''}.csv"
    return Response(
        content=csv_output,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get(
    "/summary.pdf",
    status_code=status.HTTP_200_OK,
    summary="Export multi-page engineering audit report in PDF format",
    response_description="Deterministic audit PDF with telemetry trends, OTHI assessment, and SHA-256 state footer",
)
async def get_summary_pdf(
    asset_id: Optional[str] = Query(default=None, description="Asset ID (defaults to active asset)"),
    checkpoint_id: Optional[str] = Query(default=None, description="Checkpoint ID for historical run"),
    limit: int = Query(default=500, ge=1, le=5000, description="Max historical telemetry events for trend charts"),
    app_state: AppState = Depends(get_app_state),
    storage: StorageEngine = Depends(get_storage),
    capability_evaluator: CapabilityEvaluator = Depends(get_capability_evaluator),
) -> Response:
    """Render authoritative ReportData into deterministic audit PDF with zero metric recalculation.

    When checkpoint_id is provided, state is reconstructed from the persisted point-in-time
    snapshot and trend charts are generated from canonical events up to that snapshot watermark.
    """
    target_asset, bundle, checkpoint_time = _resolve_report_bundle(
        asset_id=asset_id,
        checkpoint_id=checkpoint_id,
        app_state=app_state,
        capability_evaluator=capability_evaluator,
        storage=storage,
    )
    report_data = generate_report_data(bundle)

    # Query historical events for trend charts
    historical_events = storage.get_canonical_events(
        asset_id=target_asset,
        end_time=checkpoint_time,
        limit=limit,
        order_asc=True,
    )

    pdf_bytes, renderer_used = render_report_pdf(report_data, historical_events=historical_events)

    filename = f"summary_{target_asset}{'_' + checkpoint_id if checkpoint_id else ''}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "X-Report-Renderer": renderer_used,
        },
    )

