"""Reports Router for Structured JSON, CSV, and WeasyPrint PDF Exports (Phase 9.3).

Provides machine-readable and audit report endpoints:
- GET /v1/reports/summary.json: Full structured ReportData JSON payload.
- GET /v1/reports/summary.csv: Tabular engineering and audit CSV document.
- GET /v1/reports/summary.pdf: High-fidelity engineering audit PDF document.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status

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


@router.get(
    "/summary.json",
    status_code=status.HTTP_200_OK,
    summary="Export complete authoritative digital twin report in JSON format",
    response_description="Deterministic structured JSON report",
)
async def get_summary_json(
    asset_id: Optional[str] = Query(default=None, description="Asset ID (defaults to active asset)"),
    app_state: AppState = Depends(get_app_state),
    capability_evaluator: CapabilityEvaluator = Depends(get_capability_evaluator),
) -> Response:
    """Serialize the authoritative ReportData into deterministic JSON with zero metric recalculation."""
    target_asset = asset_id or app_state.settings.default_asset_id
    bundle = _resolve_fact_bundle(target_asset, app_state, capability_evaluator)
    report_data = generate_report_data(bundle)
    json_output = export_report_json(report_data)

    return Response(
        content=json_output,
        media_type="application/json",
        headers={
            "Content-Disposition": f'inline; filename="summary_{target_asset}.json"',
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
    limit: int = Query(default=500, ge=1, le=5000, description="Max historical telemetry events to include"),
    app_state: AppState = Depends(get_app_state),
    storage: StorageEngine = Depends(get_storage),
    capability_evaluator: CapabilityEvaluator = Depends(get_capability_evaluator),
) -> Response:
    """Serialize the authoritative ReportData and temporal telemetry into deterministic tabular CSV."""
    target_asset = asset_id or app_state.settings.default_asset_id
    bundle = _resolve_fact_bundle(target_asset, app_state, capability_evaluator)
    report_data = generate_report_data(bundle)

    # Query historical events from storage for time-series section
    historical_events = storage.get_canonical_events(
        asset_id=target_asset,
        limit=limit,
        order_asc=True,
    )

    csv_output = export_report_csv(report_data, historical_events=historical_events)

    return Response(
        content=csv_output,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="summary_{target_asset}.csv"',
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
    limit: int = Query(default=500, ge=1, le=5000, description="Max historical telemetry events for trend charts"),
    app_state: AppState = Depends(get_app_state),
    storage: StorageEngine = Depends(get_storage),
    capability_evaluator: CapabilityEvaluator = Depends(get_capability_evaluator),
) -> Response:
    """Render authoritative ReportData into deterministic audit PDF with zero metric recalculation."""
    target_asset = asset_id or app_state.settings.default_asset_id
    bundle = _resolve_fact_bundle(target_asset, app_state, capability_evaluator)
    report_data = generate_report_data(bundle)

    # Query historical events for trend charts
    historical_events = storage.get_canonical_events(
        asset_id=target_asset,
        limit=limit,
        order_asc=True,
    )

    pdf_bytes, renderer_used = render_report_pdf(report_data, historical_events=historical_events)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="summary_{target_asset}.pdf"',
            "X-Report-Renderer": renderer_used,
        },
    )

