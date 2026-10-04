"""Unit tests for Phase 1, Substep 1.1 — Dataset Schema & Integrity Audit."""

from pathlib import Path
import pytest

from app.adapters.audit_dataset import (
    DatasetAuditReport,
    TripuraDatasetAuditor,
    run_and_save_audit,
)


@pytest.fixture
def raw_data_dir() -> Path:
    p = Path("data/tripura_raw")
    if not p.exists() or not list(p.glob("*.csv")):
        pytest.skip("Raw Tripura dataset not present in data/tripura_raw/")
    return p


def test_audit_runs_successfully(raw_data_dir: Path) -> None:
    auditor = TripuraDatasetAuditor(raw_data_dir)
    report = auditor.run_audit()

    assert isinstance(report, DatasetAuditReport)
    assert len(report.files_audited) == 5
    assert set(report.files_audited) == {
        "CurrentVoltage.csv",
        "Overview.csv",
        "Power.csv",
        "PowerFactor.csv",
        "TotalPower.csv",
    }
    assert report.total_file_size_bytes > 5_000_000


def test_audit_file_level_metadata(raw_data_dir: Path) -> None:
    auditor = TripuraDatasetAuditor(raw_data_dir)
    report = auditor.run_audit()

    # Overview.csv check
    ov = report.file_audits["Overview.csv"]
    assert ov.row_count > 20000
    assert ov.column_count == 8
    assert "OTI" in ov.columns
    assert "ATI" in ov.columns
    assert ov.sampling_median_min == 15.0
    assert ov.total_duplicate_timestamps > 0

    # CurrentVoltage.csv check
    cv = report.file_audits["CurrentVoltage.csv"]
    assert cv.row_count > 19000
    assert cv.column_count == 11
    assert "VL1" in cv.columns
    assert "IL1" in cv.columns
    assert "INUT" in cv.columns

    # Check cross-file alignment
    assert report.cross_file_common_timestamps > 18000
    assert report.cross_file_union_timestamps > report.cross_file_common_timestamps


def test_thermal_feasibility_verdict(raw_data_dir: Path) -> None:
    auditor = TripuraDatasetAuditor(raw_data_dir)
    report = auditor.run_audit()

    tf = report.thermal_feasibility
    assert tf is not None
    assert tf.has_top_oil_signal is True
    assert tf.has_ambient_signal is True
    assert tf.has_load_driver is True
    assert tf.total_valid_thermal_points >= 500
    assert tf.continuous_blocks_ge_7d >= 1
    assert tf.continuous_blocks_ge_500pts >= 1
    assert tf.max_continuous_block_days >= 7.0
    assert tf.feasible_for_greybox_calibration is True


def test_markdown_report_generation(raw_data_dir: Path, tmp_path: Path) -> None:
    out_md = tmp_path / "TRIPURA_AUDIT_TEST.md"
    report = run_and_save_audit(raw_dir=raw_data_dir, output_md_path=out_md)

    assert out_md.exists()
    content = out_md.read_text(encoding="utf-8")
    assert "# Tripura Distribution Transformer Dataset — Schema & Physical Integrity Audit" in content
    assert "PREREQUISITE DATA-VOLUME & CALIBRATION FEASIBILITY: PASS" in content
    assert "CurrentVoltage.csv" in content
    assert "Overview.csv" in content
    assert "Unresolved Questions" in content
