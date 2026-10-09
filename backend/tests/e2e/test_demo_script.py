"""Automated Regression Test for Hackathon Demonstration Script (Phase 10.3).

Verifies that demo_script.py runs deterministically from a clean state,
executing all 7 stages through the unmocked pipeline without bypassing any
capability or safety gates.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from demo_script import run_hackathon_demo


def test_hackathon_demo_end_to_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that the one-command hackathon demonstration runs cleanly end-to-end."""
    # Write the PDF to a temp dir so the tracked demo_audit_report.pdf is never overwritten by tests
    monkeypatch.setenv("DEMO_REPORT_PATH", str(tmp_path / "demo_audit_report.pdf"))
    results = run_hackathon_demo()

    # Verify Stage 1: Baseline
    assert results["stage_1_baseline"]["status"] == "PASS"
    assert results["stage_1_baseline"]["seq"] == 4

    # Verify Stage 2: Sensor Quality
    assert results["stage_2_sensor_spike"]["status"] == "PASS"
    assert results["stage_2_sensor_spike"]["detected"] is True
    assert results["stage_2_sensor_spike"]["recommendation"] == "MNT-SENS-006"

    # Verify Stage 3: Sustained Overload
    assert results["stage_3_overload"]["status"] == "PASS"
    assert results["stage_3_overload"]["load_index"] > 1.00
    assert results["stage_3_overload"]["domain_status"] in ("WARNING", "CRITICAL")

    # Verify Stage 4: Multi-Domain Corroboration
    assert results["stage_4_corroboration"]["status"] == "PASS"
    assert results["stage_4_corroboration"]["evidence_grade"] in ("A", "B", "C", "U")

    # Verify Stage 5: What-If Gating
    assert results["stage_5_what_if"]["status"] == "PASS"
    # Capability gate must be honored (withheld/gated for unpromoted model)
    assert results["stage_5_what_if"]["is_enabled"] is False
    assert "disabled" in results["stage_5_what_if"]["reason"].lower()

    # Verify Stage 6: Operator Feedback
    assert results["stage_6_feedback"]["status"] == "PASS"
    assert results["stage_6_feedback"]["action"] == "ACKNOWLEDGE"
    assert results["stage_6_feedback"]["recorded"] is True

    # Verify Stage 7: PDF Audit Export
    assert results["stage_7_pdf"]["status"] == "PASS"
    assert results["stage_7_pdf"]["pdf_size"] > 1000
    pdf_path = Path(results["stage_7_pdf"]["path"])
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 1000
