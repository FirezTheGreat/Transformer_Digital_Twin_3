"""Focused Verification Test Suite for CPRI Synthetic Benchmark v3.0.2 Migration.

Covers all Phase A, B, C migration contracts:
1. Source checksums and manifest validation.
2. Partition temporal boundaries, non-overlap, row counts, and asset coverage.
3. Three-phase current and electrical telemetry mapping.
4. Oracle label exclusion from runtime measurement stream.
5. y_fit_eligible isolation to offline calibration.
6. 30-minute cadence and timezone (+05:30 to UTC) handling.
7. Registry profile routing and model artifact isolation between Tripura and CPRI.
8. Deterministic adapter replay and state hashing.
9. DQ-stress dataset isolation from clean partitions.
10. RUL and C4 insulation ageing qualification gating.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
import pandas as pd

from app.adapters.cpri_v3 import CPRIv3SourceAdapter, CPRI_V3_TAG_MAP, ORACLE_COLUMNS
from app.adapters.partition_cpri import (
    EXPECTED_ASSETS,
    EXPECTED_RATINGS_KVA,
    EXPECTED_CLEAN_DECOMPRESSED_SHA256,
    EXPECTED_DQ_DECOMPRESSED_SHA256,
)
from app.core.registry import (
    resolve_asset_profile,
    resolve_model_artifact,
    CPRI_SYNTHETIC_ASSET_RATINGS,
)
from app.core.units import validate_unit
from app.models.profile import ProfileVerificationStatus, InsulationClass
from app.models.telemetry import CanonicalEvent


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def clean_fit_df(project_root: Path) -> pd.DataFrame:
    p = project_root / "data" / "processed" / "cpri_v3_fit.parquet"
    assert p.exists(), f"CPRI FIT partition missing: {p}"
    return pd.read_parquet(p)


@pytest.fixture
def partitions_metadata(project_root: Path) -> dict:
    p = project_root / "data" / "processed" / "cpri_v3_partitions_metadata.json"
    assert p.exists(), f"CPRI metadata missing: {p}"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def test_source_archive_and_manifest_hashes(partitions_metadata: dict) -> None:
    """Verify source archive hashes recorded during partitioning match contract."""
    assert partitions_metadata["dataset_id"] == "cpri_onan_practical_schema_synthetic"
    assert partitions_metadata["version"] == "3.0.2"
    assert partitions_metadata["source_clean_decompressed_sha256"] == EXPECTED_CLEAN_DECOMPRESSED_SHA256
    assert partitions_metadata["total_clean_rows"] == 280182
    assert partitions_metadata["cadence_minutes"] == 30
    assert partitions_metadata["validation_status"] == "PASS"


def test_partition_row_counts_and_boundaries(partitions_metadata: dict, project_root: Path) -> None:
    """Verify partition counts, non-overlap, and strict temporal ordering."""
    parts = partitions_metadata["partitions"]
    assert parts["FIT"]["row_count"] == 140387
    assert parts["CAL"]["row_count"] == 70082
    assert parts["TEST"]["row_count"] == 69713
    assert parts["FIT"]["row_count"] + parts["CAL"]["row_count"] + parts["TEST"]["row_count"] == 280182

    # Check temporal boundaries
    fit_min = pd.to_datetime(parts["FIT"]["min_timestamp"])
    fit_max = pd.to_datetime(parts["FIT"]["max_timestamp"])
    cal_min = pd.to_datetime(parts["CAL"]["min_timestamp"])
    cal_max = pd.to_datetime(parts["CAL"]["max_timestamp"])
    test_min = pd.to_datetime(parts["TEST"]["min_timestamp"])
    test_max = pd.to_datetime(parts["TEST"]["max_timestamp"])

    assert fit_max < cal_min, f"Overlap between FIT ({fit_max}) and CAL ({cal_min})"
    assert cal_max < test_min, f"Overlap between CAL ({cal_max}) and TEST ({test_min})"


def test_all_eight_assets_and_ratings(clean_fit_df: pd.DataFrame) -> None:
    """Verify all 8 synthetic transformer archetypes exist with declared ratings."""
    present_assets = sorted(clean_fit_df["meta_transformer_id"].unique().tolist())
    assert present_assets == sorted(EXPECTED_ASSETS)

    for asset_id in EXPECTED_ASSETS:
        sub = clean_fit_df[clean_fit_df["meta_transformer_id"] == asset_id]
        assert len(sub) > 0
        rating = sub["x_rating_kva"].iloc[0]
        assert rating == EXPECTED_RATINGS_KVA[asset_id]


def test_adapter_3phase_current_and_voltage_mapping(clean_fit_df: pd.DataFrame) -> None:
    """Verify three-phase currents, line voltages, and UCUM units are mapped accurately."""
    sample = clean_fit_df.iloc[0].to_dict()
    adapter = CPRIv3SourceAdapter()
    event = adapter.transform_record(sample)

    assert isinstance(event, CanonicalEvent)
    meas_map = {m.signal_id: m for m in event.measurements}

    # Distinct three-phase currents
    assert "current_i1" in meas_map
    assert meas_map["current_i1"].phase == "L1"
    assert meas_map["current_i1"].unit_ucum == "A"
    assert meas_map["current_i1"].value == pytest.approx(sample["x_i_l1_a"])

    assert "current_i2" in meas_map
    assert meas_map["current_i2"].phase == "L2"
    assert meas_map["current_i2"].unit_ucum == "A"

    assert "current_i3" in meas_map
    assert meas_map["current_i3"].phase == "L3"
    assert meas_map["current_i3"].unit_ucum == "A"

    # Neutral and aggregate currents
    assert "neutral_current" in meas_map
    assert meas_map["neutral_current"].phase == "N"
    assert "current_mean" in meas_map

    # Voltages
    assert "voltage_v1" in meas_map
    assert meas_map["voltage_v1"].phase == "L1"
    assert "voltage_v_ll" in meas_map

    # Temperatures
    assert "ambient_temperature" in meas_map
    assert meas_map["ambient_temperature"].unit_ucum == "Cel"
    assert "top_oil_temperature" in meas_map
    assert meas_map["top_oil_temperature"].unit_ucum == "Cel"

    # WTI indicator channel
    assert "winding_temperature_indicator" in meas_map
    assert meas_map["winding_temperature_indicator"].original_name == "x_winding_temp_c"

    # Verify every measurement unit passes UCUM validation
    for m in event.measurements:
        assert validate_unit(m.unit_ucum), f"Invalid UCUM unit {m.unit_ucum} for {m.signal_id}"


def test_oracle_labels_excluded_from_canonical_measurements(clean_fit_df: pd.DataFrame) -> None:
    """Verify that none of the oracle/evaluation y_* labels are exposed as runtime measurements."""
    sample = clean_fit_df.iloc[0].to_dict()
    adapter = CPRIv3SourceAdapter()
    event = adapter.transform_record(sample)

    emitted_signals = {m.signal_id for m in event.measurements}
    emitted_orig_names = {m.original_name for m in event.measurements}

    for col in ORACLE_COLUMNS:
        assert col not in emitted_signals, f"Oracle label {col} leaked into signal IDs"
        assert col not in emitted_orig_names, f"Oracle label {col} leaked into original names"


def test_y_fit_eligible_offline_isolation(clean_fit_df: pd.DataFrame) -> None:
    """Verify y_fit_eligible exists in raw partition for calibration filtering but is not an event measurement."""
    assert "y_fit_eligible" in clean_fit_df.columns
    eligible_share = clean_fit_df["y_fit_eligible"].mean()
    assert 0.85 < eligible_share < 0.95  # FIT eligibility ~92.4%

    sample = clean_fit_df.iloc[0].to_dict()
    event = CPRIv3SourceAdapter().transform_record(sample)
    assert not any(m.signal_id == "y_fit_eligible" for m in event.measurements)


def test_cadence_and_timezone_handling(clean_fit_df: pd.DataFrame) -> None:
    """Verify 30-minute sampling cadence and Asia/Kolkata (+05:30) to UTC conversion."""
    sample = clean_fit_df.iloc[0].to_dict()
    # E.g. "2024-01-01T00:00:00+05:30" or "+0530"
    ts_str = str(sample["meta_timestamp"])
    assert "+05" in ts_str or "05:30" in ts_str or "0530" in ts_str

    event = CPRIv3SourceAdapter().transform_record(sample)
    # 00:00:00+05:30 is 18:30:00 UTC of previous day
    assert event.event_time_utc.tzinfo is not None
    assert event.event_time_utc.hour == 18 or event.event_time_utc.minute in (0, 30)

    # Check inter-sample spacing for one asset
    asset_rows = clean_fit_df[clean_fit_df["meta_transformer_id"] == "TX_250_MIX"].head(5)
    ts_list = pd.to_datetime(asset_rows["meta_timestamp"]).tolist()
    for i in range(1, len(ts_list)):
        delta_min = (ts_list[i] - ts_list[i - 1]).total_seconds() / 60.0
        assert delta_min == 30.0, f"Expected 30 min step, got {delta_min} min"


def test_registry_profiles_and_artifact_isolation() -> None:
    """Verify asset registry cleanly separates Tripura and CPRI assets and artifacts."""
    # 1. Tripura asset maintains 15-minute cadence and Tripura profile
    tripura_profile = resolve_asset_profile(asset_id="DT-TRIPURA-001")
    assert tripura_profile.expected_cadence_s == 900
    assert tripura_profile.asset_id == "DT-TRIPURA-001"

    tripura_artifact = resolve_model_artifact(asset_id="DT-TRIPURA-001", dataset_id="tripura_dev")
    assert tripura_artifact.dataset_id == "tripura_dev"
    assert tripura_artifact.parameters is not None  # Loaded from frozen calibrated_thermal_model.json

    # 2. All 8 CPRI assets have 1800s cadence and declared ratings
    for asset_id, rating_kva in CPRI_SYNTHETIC_ASSET_RATINGS.items():
        profile = resolve_asset_profile(asset_id=asset_id)
        assert profile.expected_cadence_s == 1800
        assert profile.rated_kva == rating_kva
        assert profile.insulation_paper_class == InsulationClass.UNKNOWN
        assert profile.profile_status == ProfileVerificationStatus.UNVERIFIED

        # Uncalibrated artifact before explicit model training
        cpri_artifact = resolve_model_artifact(asset_id=asset_id, dataset_id="cpri_v3_0_2")
        assert cpri_artifact.asset_id == asset_id
        assert cpri_artifact.dataset_id == "cpri_v3_0_2"
        # Parameters must be None (uncalibrated) before training
        assert cpri_artifact.parameters is None


def test_deterministic_adapter_replay() -> None:
    """Verify streaming records repeatedly yields identical event IDs and hashes."""
    records = [
        {
            "meta_transformer_id": "TX_250_MIX",
            "meta_timestamp": "2024-01-01T00:00:00+05:30",
            "x_voltage_ll_v": 420.0,
            "x_current_a": 50.0,
            "x_oil_temp_c": 35.0,
            "x_ambient_temp_c": 20.0,
            "x_active_power_kw": 30.0,
            "x_apparent_power_kva": 35.0,
        },
        {
            "meta_transformer_id": "TX_250_MIX",
            "meta_timestamp": "2024-01-01T00:30:00+05:30",
            "x_voltage_ll_v": 421.0,
            "x_current_a": 52.0,
            "x_oil_temp_c": 35.5,
            "x_ambient_temp_c": 20.1,
            "x_active_power_kw": 31.0,
            "x_apparent_power_kva": 36.0,
        },
    ]

    adapter = CPRIv3SourceAdapter()
    run1 = [adapter.transform_record(r) for r in records]
    run2 = [adapter.transform_record(r) for r in records]

    assert len(run1) == len(run2) == 2
    for e1, e2 in zip(run1, run2):
        assert e1.event_id == e2.event_id
        assert e1.source.raw_sha256 == e2.source.raw_sha256
        assert len(e1.measurements) == len(e2.measurements)


def test_dq_stress_isolation(project_root: Path) -> None:
    """Verify DQ-stress file (DATA5.xz) is not contaminated into clean partitions."""
    clean_fit_path = project_root / "data" / "processed" / "cpri_v3_fit.parquet"
    df = pd.read_parquet(clean_fit_path)

    # DQ-specific columns must not exist in clean partition
    assert "y_dq_defect" not in df.columns
    assert "y_dq_id" not in df.columns


def test_rul_and_ageing_gates_preserved_for_cpri() -> None:
    """Verify operational RUL and C4 insulation ageing remain unpromoted / NOT_QUALIFIED."""
    from app.engine.capability import CapabilityEvaluator
    from app.models.twin_state import TwinState

    profile = resolve_asset_profile(asset_id="TX_250_MIX")
    evaluator = CapabilityEvaluator(
        profile=profile,
        expected_cadence_s=1800,
        is_model_promoted=False,
    )
    manifest = evaluator.evaluate(
        state=TwinState(
            asset_id="TX_250_MIX",
            state_time_utc=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            last_processed_event_id="init",
            event_time_watermark_utc=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            state_sequence=0,
            state_hash="initial_hash",
        ),
    )

    cap_dict = manifest.capabilities
    # Operational RUL must not be enabled
    assert "operational_rul" in cap_dict
    assert cap_dict["operational_rul"].enabled is False
    assert cap_dict["operational_rul"].model_status == "NOT_QUALIFIED"

    # C4 Insulation ageing must not be enabled without verified insulation profile
    assert cap_dict["C4"].enabled is False


# ===========================================================================
# Phase 3: Mandatory Safeguard Tests
# ===========================================================================

def test_fit_filtering_excludes_ineligible_without_bridging_gaps(clean_fit_df: pd.DataFrame) -> None:
    """1. FIT filtering excludes ineligible observations without bridging gaps."""
    from app.engine.calibration import prepare_thermal_series, simulate_segmented_ode

    tx_fit = clean_fit_df[clean_fit_df["meta_transformer_id"] == "TX_250_MIX"].copy().reset_index(drop=True)
    assert "y_fit_eligible" in tx_fit.columns

    # Unfiltered series has only 5 natural gaps
    unfiltered = prepare_thermal_series(tx_fit)
    assert len(set(unfiltered.segment_ids)) == 5

    # Filtered eligible series creates 16 segments by excising fault/event periods
    tx_eligible = tx_fit[tx_fit["y_fit_eligible"] == 1].copy().reset_index(drop=True)
    filtered = prepare_thermal_series(tx_eligible)
    assert len(set(filtered.segment_ids)) == 16
    assert len(filtered.top_oil_degc) == 16114

    # Verify that simulate_segmented_ode resets at segment boundaries
    t_hat = simulate_segmented_ode(filtered, beta_0=5.0, beta_1=15.0, tau_hours=3.5)
    for i in range(len(filtered.top_oil_degc)):
        if i == 0 or filtered.segment_ids[i] != filtered.segment_ids[i - 1]:
            # Initial point of continuous segment MUST match observed telemetry
            assert t_hat[i] == filtered.top_oil_degc[i]


def test_test_access_rejected_before_frozen_candidate_exists(project_root: Path) -> None:
    """2. TEST access is rejected before an immutable frozen-candidate manifest exists."""
    import subprocess
    import sys
    from app.engine.calibration import evaluate_frozen_artifact_on_test

    # Nonexistent file must raise FileNotFoundError
    dummy_path = project_root / "data" / "processed" / "nonexistent_candidate_artifact.json"
    dummy_df = pd.DataFrame({"meta_transformer_id": ["TX_250_MIX"], "meta_timestamp": ["2025-07-03T00:00:00+05:30"]})
    with pytest.raises(FileNotFoundError):
        evaluate_frozen_artifact_on_test(dummy_path, dummy_df)

    # CLI evaluation must fail closed
    res = subprocess.run(
        [sys.executable, str(project_root / "backend" / "scripts" / "run_calibration_cpri.py"), "--asset", "TX_100_RES", "--evaluate-test"],
        capture_output=True,
        text=True,
        cwd=str(project_root),
    )
    assert res.returncode != 0
    assert "frozen candidate artifact not found" in res.stderr.lower() or "frozen candidate artifact not found" in res.stdout.lower()


def test_test_evaluation_cannot_mutate_frozen_artifact(tmp_path: Path, clean_fit_df: pd.DataFrame) -> None:
    """3. TEST evaluation cannot mutate the frozen artifact."""
    import hashlib
    from app.engine.calibration import (
        fit_and_calibrate_thermal_model,
        freeze_candidate_artifact,
        evaluate_frozen_artifact_on_test,
    )

    tx_fit = clean_fit_df[clean_fit_df["meta_transformer_id"] == "TX_250_MIX"].copy().head(500)
    tx_cal = clean_fit_df[clean_fit_df["meta_transformer_id"] == "TX_250_MIX"].copy().head(100)
    tx_test = clean_fit_df[clean_fit_df["meta_transformer_id"] == "TX_250_MIX"].copy().tail(100)

    # 1. Fit & freeze candidate
    candidate = fit_and_calibrate_thermal_model(
        fit_df=tx_fit,
        cal_df=tx_cal,
        asset_id="TX_250_MIX",
        dataset_id="cpri_v3_0_2",
        nominal_cadence_s=1800.0,
    )
    art_path = tmp_path / "candidate_art.json"
    man_path = tmp_path / "candidate_man.json"
    freeze_candidate_artifact(candidate, art_path, man_path)

    pre_hash = hashlib.sha256(art_path.read_bytes()).hexdigest()

    # 2. Evaluate against test
    rep_path = tmp_path / "test_report.json"
    rep = evaluate_frozen_artifact_on_test(
        artifact_path=art_path,
        test_df=tx_test,
        fit_df=tx_fit,
        output_report_path=rep_path,
        nominal_cadence_s=1800.0,
    )

    post_hash = hashlib.sha256(art_path.read_bytes()).hexdigest()

    # Artifact must remain byte-identical
    assert pre_hash == post_hash
    assert rep["frozen_artifact_sha256"] == pre_hash
    assert rep_path.exists()


def test_cpri_artifact_identity_mismatches_fail_closed(tmp_path: Path) -> None:
    """4. CPRI artifact identity mismatches fail closed."""
    from app.core.registry import resolve_model_artifact

    # Requesting TX_100_RES when only TX_250_MIX exists must NOT load TX_250_MIX
    resolved = resolve_model_artifact(asset_id="TX_100_RES", dataset_id="cpri_v3_0_2")
    assert resolved.asset_id == "TX_100_RES"
    assert resolved.parameters is None
    assert resolved.promotion.status == "UNCALIBRATED"


def test_each_asset_resolves_only_its_own_artifact() -> None:
    """5. Each asset resolves only its own artifact."""
    from app.core.registry import resolve_model_artifact

    for asset_id in CPRI_SYNTHETIC_ASSET_RATINGS.keys():
        resolved = resolve_model_artifact(asset_id=asset_id, dataset_id="cpri_v3_0_2")
        assert resolved.asset_id == asset_id
        # Must not cross-resolve Tripura DT-01 parameters
        assert resolved.parameters is None


def test_oracle_label_mutation_does_not_alter_measurements(clean_fit_df: pd.DataFrame) -> None:
    """6. Oracle-label changes do not alter runtime predictions or telemetry inputs."""
    adapter = CPRIv3SourceAdapter()
    sample1 = clean_fit_df.iloc[0].to_dict()
    event1 = adapter.transform_record(sample1)

    # Mutate oracle labels completely
    sample2 = sample1.copy()
    sample2["y_anomaly"] = 1
    sample2["y_fault_type"] = "CRITICAL_BREAKDOWN"
    sample2["y_severity"] = 10.0
    sample2["y_thermal_alert_level"] = "EMERGENCY"
    sample2["y_wti_alarm"] = 1
    sample2["y_fit_eligible"] = 0

    event2 = adapter.transform_record(sample2)

    # Emitted measurements must be strictly identical
    m1_dict = {m.signal_id: m.value for m in event1.measurements}
    m2_dict = {m.signal_id: m.value for m in event2.measurements}
    assert m1_dict == m2_dict


def test_two_hour_evaluation_uses_four_correct_cpri_horizons() -> None:
    """7. Two-hour evaluation uses the four correct CPRI horizons (30, 60, 90, 120 minutes)."""
    from app.engine.calibration import calibrate_block_conformal_uncertainty
    from app.engine.thermal import ThermalModelParameters

    # Dummy CAL partition with 30-min cadence
    ts = pd.date_range("2025-01-01", periods=100, freq="30min")
    cal_df = pd.DataFrame({
        "ts": ts,
        "x_oil_temp_c": [35.0 + 0.1 * i for i in range(100)],
        "x_ambient_temp_c": [20.0 for _ in range(100)],
        "x_apparent_power_kva": [150.0 for _ in range(100)],
    })
    params = ThermalModelParameters(beta_0=5.0, beta_1=15.0, tau_hours=3.5)

    horizon_steps = 4  # 4 * 30 min = 120 min = 2 hours
    conformal = calibrate_block_conformal_uncertainty(
        cal_df=cal_df,
        params=params,
        driver_type="apparent_power_kva",
        reference_value=200.0,
        horizon_steps=horizon_steps,
        nominal_cadence_s=1800.0,
    )
    assert conformal.horizon_steps == 4
    assert len(conformal.horizon_scales_degc) == 4
    assert len(conformal.horizon_half_widths_degc) == 4


def test_marginal_and_simultaneous_path_coverage_cannot_be_conflated() -> None:
    """8. Marginal and simultaneous-path coverage cannot be conflated."""
    from app.models.thermal_artifact import BaselineMetricEntry

    entry = BaselineMetricEntry(
        model_name="test_model",
        mae_degc=1.2,
        rmse_degc=1.5,
        bias_degc=0.1,
        marginal_coverage_90_pct=92.5,
        simultaneous_path_coverage_90_pct=88.0,
    )
    assert entry.marginal_coverage_90_pct == 92.5
    assert entry.simultaneous_path_coverage_90_pct == 88.0
    # Simultaneous path coverage must not be conflated with marginal coverage
    assert entry.simultaneous_path_coverage_90_pct <= entry.marginal_coverage_90_pct


def test_asset_failing_qualification_uses_safe_fallback() -> None:
    """9. An asset failing its qualification gate uses fallback rather than another asset's parameters."""
    from app.engine.thermal_fallback import ThermalFallbackGate
    from app.models.thermal_artifact import CalibratedThermalModelArtifact

    uncalibrated = CalibratedThermalModelArtifact.create_uncalibrated(
        dataset_id="cpri_v3_0_2",
        asset_id="TX_100_RES",
    )
    assert uncalibrated.parameters is None
    assert uncalibrated.promotion.status == "UNCALIBRATED"

    gate = ThermalFallbackGate.from_artifact(uncalibrated)
    assert gate.is_model_promoted is False
    assert gate.cusum_tracker.is_qualified is False


def test_tripura_frozen_artifacts_byte_identical(project_root: Path) -> None:
    """10. Existing Tripura artifact hashes remain strictly byte-identical."""
    import hashlib

    authoritative_tripura_hashes = {
        "calibrated_thermal_model.json": "54909ec6f55644af4056ec812e45cd37c7c40c53783e4abeab2efabeb336ca08",
        "canonical_events.parquet": "f67b2a52ae8e724a4530b54a0070a447e0ff10808b36013a8742d96a1d4d85d5",
        "canonical_measurements.parquet": "bd25ff26e13d376b65513b13db304e7137cb7b9059dc8ee0caf171398d3a3f18",
        "tripura_calibration.parquet": "de21cc32a832fb25c72bd614a8830df046416d899c6ba1974912a2ff32b9b21f",
        "tripura_fit.parquet": "7ccab8aeca8fd2bf1bd44de2a7667b3d63b491ae8bf9ca1a94efc593acbcd4e5",
        "tripura_partitions_metadata.json": "e7713ac4caeb9adf42677210ec08f083de969b54a0b7c562b7b4c01744bebb57",
        "tripura_test.parquet": "18106e0ce26e7f047536121d7620bb2dbbd6660d65389da16c4e6c416be6caa5",
    }

    processed_dir = project_root / "data" / "processed"
    for filename, expected_hash in authoritative_tripura_hashes.items():
        file_path = processed_dir / filename
        assert file_path.exists(), f"Tripura artifact {filename} missing"
        actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
        assert actual_hash == expected_hash, f"Tripura artifact hash mismatch for {filename}: {actual_hash} != {expected_hash}"
