"""Tests for Phase 9: Report Generator, Facts Pipeline & Structured Exporters (9.1 & 9.2).

Verifies:
1. Fact consistency: Values in ReportData strictly equal corresponding FactBundle values.
2. Zero metric recalculation: All metrics are referenced/copied without re-running physics/OTHI.
3. Missing value preservation: Null/unavailable fields remain strictly None / empty cells.
4. Determinism: Same FactBundle and configuration produce identical ReportData, JSON, and CSV.
5. Input immutability: Input FactBundle is not mutated in any way.
6. JSON Exporter: Full deterministic ReportData serialization with stable key ordering and audit hashes.
7. CSV Exporter: Multi-section engineering CSV with time-series telemetry, anomaly episodes, and recommendations.
8. API Endpoints: GET /v1/reports/summary.json and GET /v1/reports/summary.csv return HTTP 200 with valid content.
"""

from datetime import datetime, timezone
import json
import pytest
from fastapi.testclient import TestClient

from app.api.deps import AppState
from app.core.config import Settings
from app.core.storage import StorageEngine
from app.engine.fact_bundle import assemble_fact_bundle
from app.main import create_app
from app.models.anomaly import AnomalyCategory, AnomalyEpisode, EpisodeState
from app.models.capability import CapabilityItem, CapabilityManifest, CapabilityTier
from app.models.fact_bundle import FactBundle
from app.models.features import DerivedFeatures
from app.models.health import (
    DomainFreshness,
    DomainHealth,
    EvidenceGrade,
    HealthStatus,
    OTHIBundle,
)
from app.models.maintenance import (
    ActionWindow,
    MaintenancePriority,
    MaintenanceRecommendation,
)
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)
from app.models.twin_state import (
    DetectorState,
    ExposureState,
    ThermalLatentState,
    TwinState,
)
from app.reports.exporters import export_report_csv, export_report_json
from app.reports.report_generator import ReportData, generate_report_data


@pytest.fixture
def sample_fact_bundle() -> FactBundle:
    """Construct a rich, fully populated sample FactBundle fixture."""
    now = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)

    # Observations
    obs = {
        "top_oil_temperature": Measurement(
            signal_id="top_oil_temperature",
            value=68.4,
            value_type="float",
            unit_ucum="Cel",
            original_name="OTI_Temp",
            original_value="68.4",
            original_unit="degC",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
        ),
        "ambient_temperature": Measurement(
            signal_id="ambient_temperature",
            value=31.2,
            value_type="float",
            unit_ucum="Cel",
            original_name="Amb_Temp",
            original_value="31.2",
            original_unit="degC",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
        ),
        "active_power_total_w": Measurement(
            signal_id="active_power_total_w",
            value=185000.0,
            value_type="float",
            unit_ucum="W",
            original_name="Active_P",
            original_value="185.0",
            original_unit="kW",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
        ),
        "reactive_power_total_var": Measurement(
            signal_id="reactive_power_total_var",
            value=86000.0,
            value_type="float",
            unit_ucum="var",
            original_name="Reactive_Q",
            original_value="86.0",
            original_unit="kvar",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
        ),
        "current_l1": Measurement(
            signal_id="current_l1",
            value=115.4,
            value_type="float",
            unit_ucum="A",
            original_name="I_L1",
            original_value="115.4",
            original_unit="A",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
        ),
        "current_l2": Measurement(
            signal_id="current_l2",
            value=112.1,
            value_type="float",
            unit_ucum="A",
            original_name="I_L2",
            original_value="112.1",
            original_unit="A",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
        ),
        "current_l3": Measurement(
            signal_id="current_l3",
            value=110.8,
            value_type="float",
            unit_ucum="A",
            original_name="I_L3",
            original_value="110.8",
            original_unit="A",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
        ),
        "voltage_l1_n": Measurement(
            signal_id="voltage_l1_n",
            value=231.5,
            value_type="float",
            unit_ucum="V",
            original_name="V_L1_N",
            original_value="231.5",
            original_unit="V",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
        ),
        "voltage_l2_n": Measurement(
            signal_id="voltage_l2_n",
            value=229.8,
            value_type="float",
            unit_ucum="V",
            original_name="V_L2_N",
            original_value="229.8",
            original_unit="V",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
        ),
        "voltage_l3_n": Measurement(
            signal_id="voltage_l3_n",
            value=230.2,
            value_type="float",
            unit_ucum="V",
            original_name="V_L3_N",
            original_value="230.2",
            original_unit="V",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
        ),
        "neutral_current": Measurement(
            signal_id="neutral_current",
            value=4.6,
            value_type="float",
            unit_ucum="A",
            original_name="I_N",
            original_value="4.6",
            original_unit="A",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
        ),
        "frequency_hz": Measurement(
            signal_id="frequency_hz",
            value=49.98,
            value_type="float",
            unit_ucum="Hz",
            original_name="Freq",
            original_value="49.98",
            original_unit="Hz",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
        ),
    }

    # Derived Electrical
    derived = DerivedFeatures(
        timestamp_utc=now,
        apparent_power_derived_kva=204.5,
        power_factor_derived=0.905,
        current_mean_a=112.77,
        current_magnitude_imbalance_pct=2.33,
        voltage_magnitude_imbalance_pct=0.43,
        neutral_current_ratio=0.04,
        pqs_inconsistency=0.01,
        relative_load_index=0.82,
        thermal_residual_degc=2.5,
        transform_version="1.0.0",
    )

    # Thermal Latent
    thermal_latent = ThermalLatentState(
        top_oil_expected_degc=65.9,
        last_free_running_top_oil_degc=65.8,
        time_constant_tau_hours=3.5,
        warmup_samples_remaining=0,
        model_status="PROMOTED",
        conformal_interval_lower_degc=62.4,
        conformal_interval_upper_degc=69.4,
    )

    # Detector State
    detectors = DetectorState(
        cusum_pos=1.45,
        cusum_neg=0.0,
        cusum_alarm_active=False,
        persistence_timers={"CUSUM_DRIFT": 1800.0},
        cooldown_timers={},
    )

    # Episodes
    episodes = [
        AnomalyEpisode(
            episode_id="ep-tripura_dt_01-001",
            asset_id="tripura_dt_01",
            state=EpisodeState.WATCH,
            category=AnomalyCategory.THERMAL_DEVIATION,
            severity_score=0.45,
            start_time_utc=now,
            last_seen_time_utc=now,
            evidence_ids=["ev-001"],
            primary_reason="Top-oil temperature positive CUSUM residual drift",
            hypothesis_codes=["H_AMBIENT_SURGE", "H_RADIATOR_FOULING"],
        )
    ]

    # Recommendations
    recommendations = [
        MaintenanceRecommendation(
            recommendation_id="rec-tripura_dt_01-001",
            rule_id="MNT-THRM-001",
            rule_version="1.0.0",
            title="Inspect Radiator Convection & Oil Level",
            priority=MaintenancePriority.P3_MONITOR,
            priority_label="P3 MONITOR",
            action_window=ActionWindow.MONITOR,
            advisory_wording="Monitor radiator temperature gradient and verify oil level during scheduled rounds.",
            rationale="Persistent positive thermal residual indicates minor dissipation degradation.",
            source_reference="IEEE C57.91-2011 Clause 7",
            merge_key="THRM_DISSIPATION",
            created_at_utc=now,
        )
    ]

    # Health
    domains = {
        "thermal": DomainHealth(
            domain_name="thermal",
            severity=0.45,
            status=HealthStatus.WATCH,
            details="Thermal residual drift observed",
            freshness=DomainFreshness.CURRENT,
        ),
        "loading": DomainHealth(
            domain_name="loading",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Loading within normal parameters",
            freshness=DomainFreshness.CURRENT,
        ),
        "phase_neutral": DomainHealth(
            domain_name="phase_neutral",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Balanced 3-phase loading",
            freshness=DomainFreshness.CURRENT,
        ),
        "voltage_pf_freq": DomainHealth(
            domain_name="voltage_pf_freq",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Voltage & PF compliant",
            freshness=DomainFreshness.CURRENT,
        ),
        "oil_protection": DomainHealth(
            domain_name="oil_protection",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="No protection trip alarms",
            freshness=DomainFreshness.CURRENT,
        ),
    }

    health = OTHIBundle(
        asset_id="tripura_dt_01",
        timestamp_utc=now,
        othi_score=85,
        raw_othi=85,
        status=HealthStatus.WATCH,
        raw_status=HealthStatus.WATCH,
        operational_status=HealthStatus.WATCH,
        evidence_grade=EvidenceGrade.B,
        driving_domain="thermal",
        driving_condition_family="THERMAL_RESIDUAL",
        base_penalty=0.45,
        secondary_penalty=0.0,
        total_penalty=0.45,
        is_gated=False,
        gate_reason=None,
        available_domains=["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"],
        current_domains=["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"],
        stale_domains=[],
        domains=domains,
    )

    # State
    state = TwinState(
        asset_id="tripura_dt_01",
        state_time_utc=now,
        last_processed_event_id="evt-100",
        event_time_watermark_utc=now,
        state_sequence=42,
        current_observations=obs,
        derived_electrical=derived,
        thermal_latent=thermal_latent,
        detector_state=detectors,
        open_episodes=episodes,
        health_bundle=health,
        exposure_state=ExposureState(time_above_bands_s={"65C": 3600.0}, is_ageing_enabled=False),
        active_recommendations=recommendations,
        versions={"schema": "1.0.0", "model": "tripura_ode_v1"},
        state_hash="sha256_mock_state_hash",
    )

    # Capabilities
    capabilities = CapabilityManifest(
        asset_id="tripura_dt_01",
        evaluated_at_utc=now,
        highest_tier=CapabilityTier.C3_THERMAL_PREDICTIVE,
        available_signal_ids=["top_oil_temperature", "ambient_temperature", "active_power_total_w"],
        verified_metadata_ids=["cooling_class"],
        current_freshness_s=12.0,
        capabilities={
            "C0": CapabilityItem(enabled=True, evidence_grade="A"),
            "C1": CapabilityItem(enabled=True, evidence_grade="A"),
            "C2": CapabilityItem(enabled=True, evidence_grade="A"),
            "C3": CapabilityItem(enabled=True, evidence_grade="B"),
            "C4": CapabilityItem(enabled=False, evidence_grade="U", disabled_reason_codes=["HOTSPOT_UNAVAILABLE"]),
        },
    )

    return assemble_fact_bundle(
        state=state,
        capabilities=capabilities,
        bundle_id="fb-tripura_dt_01-000042",
    )


# ==============================================================================
# 1. Fact Consistency Tests (Phase 9.1)
# ==============================================================================

def test_report_fact_consistency_with_fact_bundle(sample_fact_bundle: FactBundle) -> None:
    """Verify all report fields match FactBundle exactly without deviation."""
    report = generate_report_data(sample_fact_bundle)

    # Metadata & Identity
    assert report.asset.asset_id == "tripura_dt_01"
    assert report.metadata.fact_bundle_id == sample_fact_bundle.fact_bundle_id
    assert report.metadata.provenance_hash == sample_fact_bundle.provenance_hash
    assert report.metadata.state_hash == sample_fact_bundle.twin_state.state_hash

    # Timestamps
    assert report.timestamps.state_time_utc == sample_fact_bundle.twin_state.state_time_utc
    assert report.timestamps.event_time_watermark_utc == sample_fact_bundle.twin_state.event_time_watermark_utc
    assert report.timestamps.fact_bundle_timestamp_utc == sample_fact_bundle.timestamp_utc

    # Thermal
    assert report.thermal.top_oil_observed_degc == 68.4
    assert report.thermal.top_oil_expected_degc == 65.9
    assert report.thermal.thermal_residual_degc == 2.5
    assert report.thermal.time_constant_tau_hours == 3.5
    assert report.thermal.model_status == "PROMOTED"
    assert report.thermal.conformal_interval_lower_degc == 62.4
    assert report.thermal.conformal_interval_upper_degc == 69.4

    # Electrical
    assert report.electrical is not None
    assert report.electrical.apparent_power_derived_kva == 204.5
    assert report.electrical.power_factor_derived == 0.905
    assert report.electrical.current_mean_a == 112.77
    assert report.electrical.relative_load_index == 0.82

    # Health & OTHI
    assert report.health.othi_score == 85
    assert report.health.status == HealthStatus.WATCH
    assert report.health.evidence_grade == EvidenceGrade.B
    assert report.health.driving_domain == "thermal"
    assert report.health.domains["thermal"].status == HealthStatus.WATCH
    assert report.health.domains["thermal"].severity == 0.45

    # Episodes & Recommendations
    assert len(report.open_episodes) == 1
    assert report.open_episodes[0].episode_id == "ep-tripura_dt_01-001"
    assert len(report.active_recommendations) == 1
    assert report.active_recommendations[0].recommendation_id == "rec-tripura_dt_01-001"
    assert report.active_recommendations[0].priority == MaintenancePriority.P3_MONITOR

    # Capabilities
    assert report.capabilities.highest_tier == CapabilityTier.C3_THERMAL_PREDICTIVE
    assert report.capabilities.capabilities["C4"].enabled is False


def test_report_does_not_recalculate_metrics(sample_fact_bundle: FactBundle) -> None:
    """Verify report strictly copies values even if arbitrary values are injected in bundle."""
    modified_state = sample_fact_bundle.twin_state.model_copy(
        update={
            "derived_electrical": sample_fact_bundle.twin_state.derived_electrical.model_copy(
                update={"relative_load_index": 9.99, "thermal_residual_degc": -12.3}
            ),
            "thermal_latent": sample_fact_bundle.twin_state.thermal_latent.model_copy(
                update={"top_oil_expected_degc": 44.4}
            ),
        }
    )
    custom_bundle = sample_fact_bundle.model_copy(update={"twin_state": modified_state})

    report = generate_report_data(custom_bundle)

    assert report.electrical is not None
    assert report.electrical.relative_load_index == 9.99
    assert report.electrical.thermal_residual_degc == -12.3
    assert report.thermal.top_oil_expected_degc == 44.4


def test_report_preserves_missing_and_none_values() -> None:
    """Verify missing/null values remain None and are never replaced by defaults/zeros."""
    now = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)

    minimal_state = TwinState(
        asset_id="tripura_dt_01",
        state_time_utc=now,
        last_processed_event_id="initial",
        event_time_watermark_utc=now,
        state_sequence=1,
        current_observations={},
        derived_electrical=None,
        thermal_latent=ThermalLatentState(
            top_oil_expected_degc=None,
            last_free_running_top_oil_degc=None,
            conformal_interval_lower_degc=None,
            conformal_interval_upper_degc=None,
        ),
        detector_state=DetectorState(),
        open_episodes=[],
        health_bundle=None,
        exposure_state=ExposureState(equivalent_ageing_hours=None, is_ageing_enabled=False),
        active_recommendations=[],
        versions={},
        state_hash="sha256_minimal",
    )

    minimal_manifest = CapabilityManifest(
        asset_id="tripura_dt_01",
        evaluated_at_utc=now,
        highest_tier=CapabilityTier.C0_INTEGRITY,
        available_signal_ids=[],
        verified_metadata_ids=[],
        current_freshness_s=0.0,
        capabilities={},
    )

    bundle = assemble_fact_bundle(
        state=minimal_state,
        capabilities=minimal_manifest,
        bundle_id="fb-tripura_dt_01-minimal",
    )

    report = generate_report_data(bundle)

    assert report.thermal.top_oil_observed_degc is None
    assert report.thermal.top_oil_expected_degc is None
    assert report.thermal.thermal_residual_degc is None
    assert report.thermal.conformal_interval_lower_degc is None
    assert report.thermal.conformal_interval_upper_degc is None
    assert report.electrical is None
    assert report.exposure.equivalent_ageing_hours is None
    assert len(report.open_episodes) == 0
    assert len(report.active_recommendations) == 0


def test_report_generation_determinism(sample_fact_bundle: FactBundle) -> None:
    """Verify repeated execution on identical FactBundle yields identical ReportData."""
    fixed_time = datetime(2026, 10, 8, 14, 30, 0, tzinfo=timezone.utc)

    report_1 = generate_report_data(
        sample_fact_bundle,
        report_id="rep-tripura_dt_01-001",
        generated_at_utc=fixed_time,
    )
    report_2 = generate_report_data(
        sample_fact_bundle,
        report_id="rep-tripura_dt_01-001",
        generated_at_utc=fixed_time,
    )

    assert report_1.model_dump() == report_2.model_dump()
    assert report_1 == report_2


def test_input_fact_bundle_immutability(sample_fact_bundle: FactBundle) -> None:
    """Verify input FactBundle is strictly untouched and immutable."""
    bundle_dump_before = sample_fact_bundle.model_dump()

    _ = generate_report_data(sample_fact_bundle)

    bundle_dump_after = sample_fact_bundle.model_dump()
    assert bundle_dump_before == bundle_dump_after


# ==============================================================================
# 2. Structured JSON Export Tests (Phase 9.2)
# ==============================================================================

def test_export_report_json_structure_and_values(sample_fact_bundle: FactBundle) -> None:
    """Verify export_report_json serializes full ReportData with exact values and sorted keys."""
    report = generate_report_data(sample_fact_bundle)
    json_str = export_report_json(report)

    # Must parse as valid JSON
    parsed = json.loads(json_str)

    # Top level structure
    assert "metadata" in parsed
    assert "asset" in parsed
    assert "timestamps" in parsed
    assert "thermal" in parsed
    assert "electrical" in parsed
    assert "health" in parsed
    assert "capabilities" in parsed
    assert "open_episodes" in parsed
    assert "active_recommendations" in parsed
    assert "provenance_hash" in parsed
    assert "state_hash" in parsed

    # Exact field assertions
    assert parsed["asset"]["asset_id"] == "tripura_dt_01"
    assert parsed["thermal"]["top_oil_observed_degc"] == 68.4
    assert parsed["thermal"]["top_oil_expected_degc"] == 65.9
    assert parsed["thermal"]["thermal_residual_degc"] == 2.5
    assert parsed["health"]["othi_score"] == 85
    assert parsed["health"]["evidence_grade"] == "B"
    assert parsed["metadata"]["provenance_hash"] == sample_fact_bundle.provenance_hash
    assert parsed["metadata"]["state_hash"] == sample_fact_bundle.twin_state.state_hash

    # Repeated export determinism
    json_str_2 = export_report_json(report)
    assert json_str == json_str_2


def test_export_report_json_preserves_nulls() -> None:
    """Verify export_report_json preserves null fields as JSON null rather than defaults."""
    now = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
    minimal_state = TwinState(
        asset_id="tripura_dt_01",
        state_time_utc=now,
        last_processed_event_id="init",
        event_time_watermark_utc=now,
        state_sequence=0,
        current_observations={},
        derived_electrical=None,
        state_hash="sha256_mock",
    )
    bundle = assemble_fact_bundle(
        state=minimal_state,
        capabilities=CapabilityManifest(
            asset_id="tripura_dt_01",
            evaluated_at_utc=now,
            highest_tier=CapabilityTier.C0_INTEGRITY,
            current_freshness_s=0.0,
        ),
        bundle_id="fb-nulls",
    )

    report = generate_report_data(bundle)
    parsed = json.loads(export_report_json(report))

    assert parsed["thermal"]["top_oil_observed_degc"] is None
    assert parsed["thermal"]["top_oil_expected_degc"] is None
    assert parsed["electrical"] is None


# ==============================================================================
# 3. Structured CSV Export Tests (Phase 9.2)
# ==============================================================================

def test_export_report_csv_structure_and_sections(sample_fact_bundle: FactBundle) -> None:
    """Verify export_report_csv generates valid, multi-section tabular engineering document."""
    report = generate_report_data(sample_fact_bundle)

    # Create dummy historical event
    now = datetime(2026, 10, 8, 11, 45, 0, tzinfo=timezone.utc)
    hist_event = CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt-099",
        asset_id="tripura_dt_01",
        event_time_utc=now,
        source=SourceRef(
            system="SCADA",
            adapter_id="tripura_csv",
            source_record_id="rec-99",
            source_uri="file://telemetry.csv",
            raw_sha256="sha256_raw_99",
        ),
        measurements=[
            Measurement(
                signal_id="top_oil_temperature",
                value=67.8,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="67.8",
                original_unit="degC",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
            Measurement(
                signal_id="ambient_temperature",
                value=30.5,
                value_type="float",
                unit_ucum="Cel",
                original_name="ATI",
                original_value="30.5",
                original_unit="degC",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
        ],
        mapping_version="1.0.0",
    )

    csv_text = export_report_csv(report, historical_events=[hist_event])

    # Section Headers
    assert "# SECTION: METADATA_AND_PROVENANCE" in csv_text
    assert "# SECTION: TIME_SERIES_TELEMETRY" in csv_text
    assert "# SECTION: ANOMALY_EPISODES" in csv_text
    assert "# SECTION: MAINTENANCE_RECOMMENDATIONS" in csv_text

    # Values in CSV
    assert "tripura_dt_01" in csv_text
    assert "68.4" in csv_text
    assert "65.9" in csv_text
    assert "rec-tripura_dt_01-001" in csv_text
    assert "ep-tripura_dt_01-001" in csv_text
    assert "HISTORICAL_EVENT" in csv_text
    assert "CURRENT_STATE_SNAPSHOT" in csv_text
    assert "sha256_raw_99" in csv_text

    # Repeated serialization determinism
    csv_text_2 = export_report_csv(report, historical_events=[hist_event])
    assert csv_text == csv_text_2


# ==============================================================================
# 4. API Endpoints Integration Tests (Phase 9.2)
# ==============================================================================

@pytest.fixture
def test_app_client(sample_fact_bundle: FactBundle) -> TestClient:
    """Construct TestClient initialized with sample AppState and storage."""
    settings = Settings(
        default_asset_id="tripura_dt_01",
        db_path=":memory:",
    )
    storage = StorageEngine(db_path=":memory:")

    app_state = AppState(
        settings=settings,
        storage=storage,
        current_state=sample_fact_bundle.twin_state,
        latest_fact_bundle=sample_fact_bundle,
    )

    app = create_app(settings=settings, app_state=app_state)
    return TestClient(app)


def test_api_get_summary_json(test_app_client: TestClient, sample_fact_bundle: FactBundle) -> None:
    """Test GET /v1/reports/summary.json returns HTTP 200 with full ReportData payload."""
    response = test_app_client.get("/v1/reports/summary.json?asset_id=tripura_dt_01")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert "summary_tripura_dt_01.json" in response.headers.get("content-disposition", "")

    data = response.json()
    assert data["asset"]["asset_id"] == "tripura_dt_01"
    assert data["thermal"]["top_oil_observed_degc"] == 68.4
    assert data["thermal"]["top_oil_expected_degc"] == 65.9
    assert data["health"]["othi_score"] == 85
    assert data["health"]["evidence_grade"] == "B"
    assert data["metadata"]["provenance_hash"] == sample_fact_bundle.provenance_hash


def test_api_get_summary_csv(test_app_client: TestClient) -> None:
    """Test GET /v1/reports/summary.csv returns HTTP 200 with text/csv payload."""
    response = test_app_client.get("/v1/reports/summary.csv?asset_id=tripura_dt_01")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "summary_tripura_dt_01.csv" in response.headers.get("content-disposition", "")

    csv_text = response.text
    assert "# SECTION: METADATA_AND_PROVENANCE" in csv_text
    assert "# SECTION: TIME_SERIES_TELEMETRY" in csv_text
    assert "tripura_dt_01" in csv_text
    assert "CURRENT_STATE_SNAPSHOT" in csv_text
    assert "rec-tripura_dt_01-001" in csv_text


# ==============================================================================
# 5. WeasyPrint / PDF Renderer Tests (Phase 9.3)
# ==============================================================================

from app.reports.charts import (
    generate_current_balance_chart,
    generate_electrical_trend_chart,
    generate_thermal_trend_chart,
)
from app.reports.pdf_renderer import render_report_html, render_report_pdf


def test_chart_generation_with_and_without_events() -> None:
    """Verify charts return None for empty event lists and valid base64 data URIs for events."""
    # Empty events -> None
    assert generate_thermal_trend_chart([]) is None
    assert generate_electrical_trend_chart([]) is None
    assert generate_current_balance_chart([]) is None

    # Populated events
    now = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
    events = [
        CanonicalEvent(
            schema_version="1.0.0",
            event_id=f"evt-{i}",
            asset_id="tripura_dt_01",
            event_time_utc=now,
            source=SourceRef(
                system="SCADA",
                adapter_id="tripura",
                source_record_id=f"r-{i}",
                source_uri="uri",
                raw_sha256="sha256",
            ),
            measurements=[
                Measurement(
                    signal_id="top_oil_temperature",
                    value=65.0 + i,
                    value_type="float",
                    unit_ucum="Cel",
                    original_name="OTI",
                    original_value=str(65.0 + i),
                    original_unit="degC",
                ),
                Measurement(
                    signal_id="ambient_temperature",
                    value=30.0,
                    value_type="float",
                    unit_ucum="Cel",
                    original_name="ATI",
                    original_value="30.0",
                    original_unit="degC",
                ),
                Measurement(
                    signal_id="active_power_total_w",
                    value=150000.0,
                    value_type="float",
                    unit_ucum="W",
                    original_name="P",
                    original_value="150.0",
                    original_unit="kW",
                ),
                Measurement(
                    signal_id="reactive_power_total_var",
                    value=50000.0,
                    value_type="float",
                    unit_ucum="var",
                    original_name="Q",
                    original_value="50.0",
                    original_unit="kvar",
                ),
                Measurement(
                    signal_id="current_l1",
                    value=100.0,
                    value_type="float",
                    unit_ucum="A",
                    original_name="I1",
                    original_value="100.0",
                    original_unit="A",
                ),
                Measurement(
                    signal_id="current_l2",
                    value=98.0,
                    value_type="float",
                    unit_ucum="A",
                    original_name="I2",
                    original_value="98.0",
                    original_unit="A",
                ),
                Measurement(
                    signal_id="current_l3",
                    value=102.0,
                    value_type="float",
                    unit_ucum="A",
                    original_name="I3",
                    original_value="102.0",
                    original_unit="A",
                ),
            ],
            mapping_version="1.0.0",
        )
        for i in range(5)
    ]

    thermal_chart = generate_thermal_trend_chart(events)
    assert thermal_chart is not None
    assert thermal_chart.startswith("data:image/png;base64,")

    elec_chart = generate_electrical_trend_chart(events)
    assert elec_chart is not None
    assert elec_chart.startswith("data:image/png;base64,")

    curr_chart = generate_current_balance_chart(events)
    assert curr_chart is not None
    assert curr_chart.startswith("data:image/png;base64,")


def test_render_report_html_content_and_sections(sample_fact_bundle: FactBundle) -> None:
    """Verify HTML template renders all required sections, values, and audit footers."""
    report = generate_report_data(sample_fact_bundle)
    html = render_report_html(report)

    # Asset and Report Info
    assert "tripura_dt_01" in html
    assert "DIGITAL TWIN AUDIT REPORT" in html

    # Section 1: Executive Summary
    assert "OPERATIONAL HEALTH INDEX" in html
    assert "85" in html
    assert "GRADE B" in html
    assert "68.4 °C" in html
    assert "65.9 °C" in html
    assert "204.5 kVA" in html

    # Section 2: Engineering State Assessment
    assert "Thermal Dynamics &amp; Latent State" in html or "Thermal Dynamics & Latent State" in html
    assert "3.50 hours" in html
    assert "PROMOTED" in html
    assert "Electrical Measurements &amp; Features" in html or "Electrical Measurements & Features" in html
    assert "185.0 kW" in html
    assert "86.0 kvar" in html
    assert "0.905" in html
    assert "2.33 % (NEMA)" in html

    # Section 3: OTHI Multi-Domain Breakdown
    assert "MULTI-DOMAIN HEALTH BREAKDOWN" in html
    assert "thermal" in html
    assert "loading" in html
    assert "phase_neutral" in html
    assert "voltage_pf_freq" in html
    assert "oil_protection" in html

    # Section 4: Anomaly Episodes
    assert "ep-tripura_dt_01-001" in html
    assert "Top-oil temperature positive CUSUM residual drift" in html

    # Section 5: Maintenance Action Plan
    assert "rec-tripura_dt_01-001" in html
    assert "Inspect Radiator Convection &amp; Oil Level" in html or "Inspect Radiator Convection & Oil Level" in html
    assert "IEEE C57.91-2011 Clause 7" in html

    # Section 7: Standards & Citations
    assert "IEEE C57.91-2011" in html
    assert "IEC 60076-7" in html

    # Audit Footers
    assert sample_fact_bundle.twin_state.state_hash in html
    assert sample_fact_bundle.provenance_hash in html


def test_render_report_html_unavailable_othi() -> None:
    """Verify HTML template handles gated/unavailable OTHI honestly without fabricating 0 or 100."""
    now = datetime(2026, 10, 8, 12, 0, 0, tzinfo=timezone.utc)
    minimal_state = TwinState(
        asset_id="tripura_dt_01",
        state_time_utc=now,
        last_processed_event_id="init",
        event_time_watermark_utc=now,
        state_sequence=0,
        current_observations={},
        derived_electrical=None,
        state_hash="sha256_mock_hash",
    )
    bundle = assemble_fact_bundle(
        state=minimal_state,
        capabilities=CapabilityManifest(
            asset_id="tripura_dt_01",
            evaluated_at_utc=now,
            highest_tier=CapabilityTier.C0_INTEGRITY,
            current_freshness_s=0.0,
        ),
        bundle_id="fb-unavailable-test",
    )

    report = generate_report_data(bundle)
    html = render_report_html(report)

    assert "UNAVAILABLE" in html
    # Ensure neither 0/100 nor 100/100 is presented as the health score
    assert "0/100" not in html
    assert "100/100" not in html


def test_render_report_pdf_binary_format(sample_fact_bundle: FactBundle) -> None:
    """Verify render_report_pdf produces valid binary PDF content."""
    report = generate_report_data(sample_fact_bundle)
    pdf_bytes, renderer_used = render_report_pdf(report)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000  # PDF should be substantial
    assert pdf_bytes.startswith(b"%PDF-")  # Standard PDF magic header
    assert b"%%EOF" in pdf_bytes  # Standard PDF EOF marker
    assert renderer_used in ("weasyprint", "xhtml2pdf")


def test_api_get_summary_pdf(test_app_client: TestClient) -> None:
    """Test GET /v1/reports/summary.pdf returns HTTP 200 with valid application/pdf binary content."""
    response = test_app_client.get("/v1/reports/summary.pdf?asset_id=tripura_dt_01")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert 'summary_tripura_dt_01.pdf' in response.headers.get("content-disposition", "")
    assert "x-report-renderer" in response.headers

    pdf_content = response.content
    assert pdf_content.startswith(b"%PDF-")
    assert len(pdf_content) > 1000


def test_pdf_renderer_primary_specification(sample_fact_bundle: FactBundle) -> None:
    """Verify that WeasyPrint is explicitly declared as the primary specification renderer."""
    from app.reports.pdf_renderer import PRIMARY_RENDERER, FALLBACK_RENDERER, get_pdf_renderer_status

    assert PRIMARY_RENDERER == "weasyprint"
    assert FALLBACK_RENDERER == "xhtml2pdf"

    status = get_pdf_renderer_status()
    assert status["primary_renderer"] == "weasyprint"
    assert status["fallback_renderer"] == "xhtml2pdf"


def test_pdf_renderer_executes_weasyprint_when_available(sample_fact_bundle: FactBundle, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that when WeasyPrint is available, it is invoked directly and returns as primary."""
    import sys
    from unittest.mock import MagicMock

    report = generate_report_data(sample_fact_bundle)

    mock_weasyprint = MagicMock()
    mock_html_instance = MagicMock()
    mock_html_instance.write_pdf.return_value = b"%PDF-1.4 Mocked WeasyPrint Output %%EOF"
    mock_weasyprint.HTML.return_value = mock_html_instance

    monkeypatch.setitem(sys.modules, "weasyprint", mock_weasyprint)

    pdf_bytes, renderer_used = render_report_pdf(report)
    assert renderer_used == "weasyprint"
    assert pdf_bytes == b"%PDF-1.4 Mocked WeasyPrint Output %%EOF"
    mock_weasyprint.HTML.assert_called_once()
    mock_html_instance.write_pdf.assert_called_once()


# ==============================================================================
# 6. Checkpoint Report & Historical Runs Tests
# ==============================================================================

@pytest.fixture
def test_app_with_checkpoint(sample_fact_bundle: FactBundle) -> tuple[TestClient, str, str]:
    """Client with a pre-saved checkpoint and known ID."""
    from app.core.checkpoint import CheckpointStore

    settings = Settings(
        default_asset_id="tripura_dt_01",
        db_path=":memory:",
    )
    storage = StorageEngine(db_path=":memory:")
    chk_store = CheckpointStore(storage)
    cid = chk_store.save_checkpoint(sample_fact_bundle.twin_state)

    app_state = AppState(
        settings=settings,
        storage=storage,
        current_state=sample_fact_bundle.twin_state,
        latest_fact_bundle=sample_fact_bundle,
    )

    app = create_app(settings=settings, app_state=app_state)
    return TestClient(app), cid, sample_fact_bundle.twin_state.asset_id


def test_api_checkpoint_reports_success(test_app_with_checkpoint: tuple[TestClient, str, str]) -> None:
    """Verify JSON, CSV, and PDF exports all succeed with valid checkpoint_id and consistent filename."""
    client, cid, asset_id = test_app_with_checkpoint

    # JSON export
    resp_json = client.get(f"/v1/reports/summary.json?checkpoint_id={cid}")
    assert resp_json.status_code == 200
    assert resp_json.headers["content-type"] == "application/json"
    assert f"summary_{asset_id}_{cid}.json" in resp_json.headers.get("content-disposition", "")
    data = resp_json.json()
    assert data["asset"]["asset_id"] == asset_id
    assert data["metadata"]["state_hash"] != ""

    # CSV export
    resp_csv = client.get(f"/v1/reports/summary.csv?checkpoint_id={cid}")
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert f"summary_{asset_id}_{cid}.csv" in resp_csv.headers.get("content-disposition", "")
    assert "# SECTION: METADATA_AND_PROVENANCE" in resp_csv.text

    # PDF export
    resp_pdf = client.get(f"/v1/reports/summary.pdf?checkpoint_id={cid}")
    assert resp_pdf.status_code == 200
    assert resp_pdf.headers["content-type"] == "application/pdf"
    assert f"summary_{asset_id}_{cid}.pdf" in resp_pdf.headers.get("content-disposition", "")
    assert resp_pdf.content.startswith(b"%PDF-")


def test_api_checkpoint_missing_returns_404(test_app_with_checkpoint: tuple[TestClient, str, str]) -> None:
    """Verify non-existent checkpoint IDs return HTTP 404, not unhandled 500, across all formats."""
    client, _, _ = test_app_with_checkpoint
    fake_cid = "chk_nonexistent_999999"

    for ext in ("json", "csv", "pdf"):
        resp = client.get(f"/v1/reports/summary.{ext}?checkpoint_id={fake_cid}")
        assert resp.status_code == 404
        error_payload = resp.json()
        assert "error" in error_payload
        assert error_payload["error"]["code"] == "NOT_FOUND"
        assert fake_cid in error_payload["error"]["message"]


def test_api_checkpoint_asset_mismatch_returns_400(test_app_with_checkpoint: tuple[TestClient, str, str]) -> None:
    """Verify mismatched asset_id and checkpoint_id returns HTTP 400 to prevent cross-asset reports."""
    client, cid, _ = test_app_with_checkpoint
    wrong_asset = "other_asset_99"

    for ext in ("json", "csv", "pdf"):
        resp = client.get(f"/v1/reports/summary.{ext}?asset_id={wrong_asset}&checkpoint_id={cid}")
        assert resp.status_code == 400
        error_payload = resp.json()
        assert "error" in error_payload
        assert error_payload["error"]["code"] == "BAD_REQUEST"
        assert "belongs to asset" in error_payload["error"]["message"]


def test_api_list_runs_endpoint(test_app_with_checkpoint: tuple[TestClient, str, str]) -> None:
    """Verify GET /v1/reports/runs returns genuine checkpoint run records."""
    client, cid, asset_id = test_app_with_checkpoint

    # List all runs
    resp = client.get("/v1/reports/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) >= 1
    target = next((r for r in runs if r["checkpoint_id"] == cid), None)
    assert target is not None
    assert target["asset_id"] == asset_id
    assert "state_sequence" in target
    assert "state_hash" in target
    assert "state_time_utc" in target

    # Filter matching asset
    resp_match = client.get(f"/v1/reports/runs?asset_id={asset_id}")
    assert resp_match.status_code == 200
    assert len(resp_match.json()) >= 1

    # Filter non-matching asset
    resp_nomatch = client.get("/v1/reports/runs?asset_id=nonexistent_asset")
    assert resp_nomatch.status_code == 200
    assert len(resp_nomatch.json()) == 0



