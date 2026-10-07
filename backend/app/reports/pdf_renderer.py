"""PDF Report Renderer for Transformer Digital Twin (Phase 9.3).

Primary Renderer: WeasyPrint (Standard compliant HTML5/CSS3 Paged Media engine).
Fallback Engine: xhtml2pdf (Documented developer fallback for Windows environments lacking native GTK/Pango C libraries).

Zero Metric Recalculation: Pure presentation transformation consuming authoritative
ReportData and StorageEngine historical events.
"""

from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Any, Dict, Sequence, Tuple

import jinja2

from app.models.telemetry import CanonicalEvent
from app.reports.charts import (
    generate_current_balance_chart,
    generate_electrical_trend_chart,
    generate_thermal_trend_chart,
)
from app.reports.report_generator import ReportData

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"
PRIMARY_RENDERER = "weasyprint"
FALLBACK_RENDERER = "xhtml2pdf"


def _get_jinja_env() -> jinja2.Environment:
    """Initialize Jinja2 Environment with autoescape and template loaders."""
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
    )


def render_report_html(
    report_data: ReportData,
    historical_events: Sequence[CanonicalEvent] | None = None,
) -> str:
    """Render the Jinja2 HTML template with ReportData and trend chart data URIs."""
    env = _get_jinja_env()
    template = env.get_template("summary_report.html")

    # Generate charts if historical events are provided
    events = historical_events or []
    charts = {
        "thermal_chart": generate_thermal_trend_chart(events) if events else None,
        "electrical_chart": generate_electrical_trend_chart(events) if events else None,
        "current_chart": generate_current_balance_chart(events) if events else None,
    }

    return template.render(
        report=report_data,
        charts=charts,
    )


def get_pdf_renderer_status() -> Dict[str, Any]:
    """Inspect and report the runtime availability of the primary WeasyPrint engine."""
    weasyprint_available = False
    error_detail = None
    try:
        import weasyprint  # noqa: F401
        # Check if native C libraries load
        from weasyprint.text.ffi import pango  # noqa: F401
        weasyprint_available = True
    except Exception as exc:
        error_detail = str(exc)

    return {
        "primary_renderer": PRIMARY_RENDERER,
        "primary_available": weasyprint_available,
        "error_detail": error_detail,
        "fallback_renderer": FALLBACK_RENDERER,
    }


def render_report_pdf(
    report_data: ReportData,
    historical_events: Sequence[CanonicalEvent] | None = None,
    strict_primary: bool = False,
) -> Tuple[bytes, str]:
    """Render ReportData into high-fidelity PDF bytes using WeasyPrint as primary engine.

    Args:
        report_data: Authoritative ReportData instance.
        historical_events: Optional list of chronological historical CanonicalEvents.
        strict_primary: If True, raises RuntimeError if WeasyPrint native engine cannot execute.

    Returns:
        Tuple[bytes, str]: Binary PDF content and the renderer name ('weasyprint' or 'xhtml2pdf').

    Raises:
        RuntimeError: If strict_primary=True and WeasyPrint fails or if all renderers fail.
    """
    html_content = render_report_html(report_data, historical_events)

    # 1. Primary path: WeasyPrint
    try:
        import weasyprint
        pdf_bytes = weasyprint.HTML(string=html_content).write_pdf()
        if pdf_bytes:
            return bytes(pdf_bytes), PRIMARY_RENDERER
    except Exception as exc:
        if strict_primary or os.environ.get("STRICT_WEASYPRINT", "").lower() in ("1", "true"):
            raise RuntimeError(
                f"Primary PDF renderer '{PRIMARY_RENDERER}' failed to execute: {exc}. "
                "Ensure native GTK3/Pango C libraries are installed in the operating environment."
            ) from exc
        logger.warning(
            "Primary renderer '%s' failed due to missing system runtime (%s). "
            "Using development fallback '%s'.",
            PRIMARY_RENDERER,
            exc,
            FALLBACK_RENDERER,
        )

    # 2. Documented development / environment compatibility fallback
    try:
        from xhtml2pdf import pisa

        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(
            src=html_content,
            dest=pdf_buffer,
            encoding="utf-8",
        )

        if pisa_status.err:
            raise RuntimeError(f"PDF rendering error in {FALLBACK_RENDERER}: {pisa_status.err}")

        return pdf_buffer.getvalue(), FALLBACK_RENDERER
    except Exception as fallback_exc:
        raise RuntimeError(
            f"All PDF renderers failed. Primary ({PRIMARY_RENDERER}) and fallback ({FALLBACK_RENDERER}) "
            f"encountered errors: {fallback_exc}"
        ) from fallback_exc


__all__ = [
    "PRIMARY_RENDERER",
    "FALLBACK_RENDERER",
    "get_pdf_renderer_status",
    "render_report_html",
    "render_report_pdf",
]

