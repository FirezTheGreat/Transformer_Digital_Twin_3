"""Unit tests for Phase 1, Substep 1.2 — Chronological Partitioning & Promotion Feasibility."""

from pathlib import Path
import pandas as pd
import pytest
import yaml

from app.adapters.partition_dataset import (
    FeasibilityStatus,
    TripuraChronologicalPartitioner,
    run_partitioning,
)
from app.core.units import validate_unit, canonicalize_unit_code


@pytest.fixture
def raw_data_dir() -> Path:
    p = Path("data/tripura_raw")
    if not p.exists() or not list(p.glob("*.csv")):
        pytest.skip("Raw Tripura dataset not present in data/tripura_raw/")
    return p


@pytest.fixture
def mapping_file() -> Path:
    p = Path("backend/app/adapters/tripura_map.yaml")
    assert p.exists(), "tripura_map.yaml must exist"
    return p


def test_tripura_map_yaml_validity(mapping_file: Path) -> None:
    with open(mapping_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["dataset_name"] == "tripura_distribution_transformer"
    assert data["nominal_sampling_interval_minutes"] == 15.0
    assert "sources" in data

    # Verify that all 5 sources are documented
    expected_sources = {
        "Overview.csv",
        "CurrentVoltage.csv",
        "Power.csv",
        "PowerFactor.csv",
        "TotalPower.csv",
    }
    assert set(data["sources"].keys()) == expected_sources

    # Validate unit codes against Pint registry
    for src_name, src_info in data["sources"].items():
        for col_name, mapping in src_info["mappings"].items():
            unit_str = mapping.get("unit")
            if unit_str and unit_str not in ("dimensionless", "%"):
                # Pint validation
                assert validate_unit(unit_str) is True, f"Invalid unit code: {unit_str} in {col_name}"


def test_partitioning_execution_and_manifest(raw_data_dir: Path, tmp_path: Path, mapping_file: Path) -> None:
    processed_dir = tmp_path / "processed"
    partitioner = TripuraChronologicalPartitioner(
        raw_data_dir=raw_data_dir,
        processed_data_dir=processed_dir,
        mapping_file=mapping_file,
    )
    manifest, fit_df, calib_df, test_df = partitioner.create_chronological_partitions()

    assert manifest.feasibility.status == FeasibilityStatus.PASS
    assert manifest.total_aligned_samples == 18324
    assert len(fit_df) == 10994
    assert len(calib_df) == 3657
    assert len(test_df) == 3659


def test_chronological_order_and_zero_overlap(raw_data_dir: Path, tmp_path: Path, mapping_file: Path) -> None:
    processed_dir = tmp_path / "processed"
    partitioner = TripuraChronologicalPartitioner(
        raw_data_dir=raw_data_dir,
        processed_data_dir=processed_dir,
        mapping_file=mapping_file,
    )
    _, fit_df, calib_df, test_df = partitioner.create_chronological_partitions()

    # Zero overlap in timestamps
    fit_ts = set(fit_df["DeviceTimeStamp"])
    calib_ts = set(calib_df["DeviceTimeStamp"])
    test_ts = set(test_df["DeviceTimeStamp"])

    assert len(fit_ts.intersection(calib_ts)) == 0, "Leakage: Fit and Calib overlap"
    assert len(calib_ts.intersection(test_ts)) == 0, "Leakage: Calib and Test overlap"
    assert len(fit_ts.intersection(test_ts)) == 0, "Leakage: Fit and Test overlap"

    # Chronological monotonic ordering
    assert fit_df["ts"].is_monotonic_increasing
    assert calib_df["ts"].is_monotonic_increasing
    assert test_df["ts"].is_monotonic_increasing


def test_embargo_enforcement(raw_data_dir: Path, tmp_path: Path, mapping_file: Path) -> None:
    processed_dir = tmp_path / "processed"
    partitioner = TripuraChronologicalPartitioner(
        raw_data_dir=raw_data_dir,
        processed_data_dir=processed_dir,
        mapping_file=mapping_file,
    )
    manifest, fit_df, calib_df, test_df = partitioner.create_chronological_partitions()

    # Embargo 1: at least 2 hours between Fit max and Calib min
    fit_max = fit_df["ts"].max()
    calib_min = calib_df["ts"].min()
    embargo_1_gap = calib_min - fit_max
    assert embargo_1_gap >= pd.Timedelta(hours=2), f"Embargo 1 violated: gap is {embargo_1_gap}"

    # Embargo 2: at least 2 hours between Calib max and Test min
    calib_max = calib_df["ts"].max()
    test_min = test_df["ts"].min()
    embargo_2_gap = test_min - calib_max
    assert embargo_2_gap >= pd.Timedelta(hours=2), f"Embargo 2 violated: gap is {embargo_2_gap}"


def test_promotion_feasibility_criteria(raw_data_dir: Path, tmp_path: Path, mapping_file: Path) -> None:
    processed_dir = tmp_path / "processed"
    partitioner = TripuraChronologicalPartitioner(
        raw_data_dir=raw_data_dir,
        processed_data_dir=processed_dir,
        mapping_file=mapping_file,
    )
    manifest, _, _, _ = partitioner.create_chronological_partitions()

    feas = manifest.feasibility
    assert feas.status == FeasibilityStatus.PASS
    assert feas.fit_samples >= 500
    assert feas.fit_span_days >= 7.0
    assert feas.fit_load_cv >= 0.10
    assert feas.fit_load_range_kva >= 10.0
    assert feas.calib_valid_2h_origins >= 30
    assert feas.derived_statistics["passes_min_fit_samples"] is True
    assert feas.derived_statistics["passes_min_fit_days"] is True
    assert feas.derived_statistics["passes_load_variation"] is True
    assert feas.derived_statistics["passes_calib_origins"] is True


def test_partition_reproducibility_and_hashes(raw_data_dir: Path, tmp_path: Path, mapping_file: Path) -> None:
    dir1 = tmp_path / "proc1"
    dir2 = tmp_path / "proc2"

    m1, _, _, _ = TripuraChronologicalPartitioner(raw_data_dir, dir1, mapping_file).create_chronological_partitions()
    m2, _, _, _ = TripuraChronologicalPartitioner(raw_data_dir, dir2, mapping_file).create_chronological_partitions()

    assert m1.partitions["fit"].sha256_hash == m2.partitions["fit"].sha256_hash
    assert m1.partitions["calibration"].sha256_hash == m2.partitions["calibration"].sha256_hash
    assert m1.partitions["test"].sha256_hash == m2.partitions["test"].sha256_hash


def test_deterministic_conflicting_duplicate_retention(raw_data_dir: Path, tmp_path: Path, mapping_file: Path) -> None:
    processed_dir = tmp_path / "processed"
    partitioner = TripuraChronologicalPartitioner(
        raw_data_dir=raw_data_dir,
        processed_data_dir=processed_dir,
        mapping_file=mapping_file,
    )
    manifest, fit_df, calib_df, test_df = partitioner.create_chronological_partitions()

    # Total aligned samples across all 5 CSVs deduplicated with keep-first is exactly 18,324
    assert manifest.total_aligned_samples == 18324
    assert len(fit_df) + len(calib_df) + len(test_df) == 18310  # 18,324 minus 14 samples in the two 2-hour embargo gaps
    assert fit_df["DeviceTimeStamp"].nunique() == len(fit_df)
    assert calib_df["DeviceTimeStamp"].nunique() == len(calib_df)
    assert test_df["DeviceTimeStamp"].nunique() == len(test_df)

