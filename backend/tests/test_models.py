"""Unit test suite for canonical Pydantic v2 data models and contracts."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.models import (
    ActionWindow,
    AnomalyCategory,
    AnomalyEpisode,
    AssetProfile,
    CanonicalEvent,
    CapabilityItem,
    CapabilityManifest,
    CapabilityTier,
    DerivedFeatures,
    DetectorState,
    DomainHealth,
    EpisodeState,
    EvidenceGrade,
    EvidenceItem,
    ExposureState,
    FactBundle,
    FeedbackAction,
    HealthStatus,
    InsulationClass,
    MaintenancePriority,
    MaintenanceRecommendation,
    Measurement,
    MeasurementQuality,
    OperatorFeedbackEvent,
    OTHIBundle,
    ProfileVerificationStatus,
    QualitySeverity,
    RawTelemetryFrame,
    SourceRef,
    ThermalLatentState,
    TwinState,
)


def sample_utc_time() -> datetime:
    return datetime(2026, 10, 4, 12, 0, 0, tzinfo=timezone.utc)


def test_measurement_and_canonical_event_valid() -> None:
    """Verify CanonicalEvent and Measurement valid creation and serialization."""
    source = SourceRef(
        system="tripura_csv",
        adapter_id="tripura_v1",
        source_record_id="row-100",
        source_uri="data/tripura_raw/data.csv",
        raw_sha256="abcdef1234567890",
    )
    measurement = Measurement(
        signal_id="top_oil_temperature",
        phase=None,
        value=65.4,
        value_type="float",
        unit_ucum="Cel",
        original_name="OTI",
        original_value="65.4",
        original_unit="degC",
        quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
    )
    event = CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt-001",
        asset_id="DT-001",
        event_time_utc=sample_utc_time(),
        received_time_utc=sample_utc_time(),
        source=source,
        measurements=[measurement],
        event_quality_flags=[],
        mapping_version="tripura-map-1.0.0",
    )

    assert event.event_id == "evt-001"
    assert event.measurements[0].unit_ucum == "Cel"
    
    # Test JSON round-trip
    json_data = event.model_dump_json()
    loaded_event = CanonicalEvent.model_validate_json(json_data)
    assert loaded_event == event


def test_measurement_invalid_unit_raises() -> None:
    """Verify Measurement rejects invalid or unknown UCUM units."""
    with pytest.raises(ValidationError):
        Measurement(
            signal_id="top_oil_temperature",
            value=65.4,
            value_type="float",
            unit_ucum="not_a_valid_unit_xyz",
            original_name="OTI",
            original_value="65.4",
            original_unit="degC",
        )


def test_immutability_frozen_models() -> None:
    """Verify that models are immutable and forbid field mutation."""
    measurement = Measurement(
        signal_id="voltage_l1_n",
        phase="L1",
        value=230.0,
        value_type="float",
        unit_ucum="V",
        original_name="V1",
        original_value="230.0",
        original_unit="V",
    )
    with pytest.raises(ValidationError):
        # Trying to mutate a frozen model
        measurement.value = 240.0  # type: ignore


def test_forbid_extra_fields() -> None:
    """Verify that extra undocumented fields are forbidden."""
    with pytest.raises(ValidationError):
        SourceRef(
            system="tripura_csv",
            adapter_id="tripura_v1",
            source_record_id="row-1",
            source_uri="data.csv",
            raw_sha256="abc",
            unsupported_extra_field="error",  # type: ignore
        )


def test_asset_profile_and_insulation_classes() -> None:
    """Verify AssetProfile creation and enum bounds."""
    profile = AssetProfile(
        asset_id="DT-001",
        phase_topology="THREE_PHASE_4W",
        nominal_frequency_hz=50.0,
        rated_kva=100.0,
        cooling_class="ONAN",
        insulation_paper_class=InsulationClass.NON_THERMALLY_UPGRADED,
        profile_status=ProfileVerificationStatus.VERIFIED,
    )
    assert profile.rated_kva == 100.0
    assert profile.insulation_paper_class == InsulationClass.NON_THERMALLY_UPGRADED


def test_capability_manifest_and_tiers() -> None:
    """Verify CapabilityManifest tiers and capability items."""
    item = CapabilityItem(
        enabled=True,
        evidence_grade="A",
        required_inputs=["top_oil_temperature", "ambient_temperature"],
        missing_inputs=[],
        disabled_reason_codes=[],
        coverage_pct=100.0,
        model_status="PROMOTED",
        extrapolation=False,
    )
    manifest = CapabilityManifest(
        asset_id="DT-001",
        evaluated_at_utc=sample_utc_time(),
        highest_tier=CapabilityTier.C3_THERMAL_PREDICTIVE,
        available_signal_ids=["top_oil_temperature", "ambient_temperature", "current_l1"],
        current_freshness_s=30.0,
        capabilities={"thermal_predictive": item},
    )
    assert manifest.highest_tier == CapabilityTier.C3_THERMAL_PREDICTIVE
    assert manifest.capabilities["thermal_predictive"].enabled is True


def test_derived_features_bounds() -> None:
    """Verify DerivedFeatures constraints."""
    features = DerivedFeatures(
        timestamp_utc=sample_utc_time(),
        apparent_power_derived_kva=50.0,
        power_factor_derived=0.92,
        current_mean_a=75.0,
        current_magnitude_imbalance_pct=4.5,
        voltage_magnitude_imbalance_pct=1.2,
        neutral_current_ratio=0.08,
        pqs_inconsistency=0.01,
        relative_load_index=0.75,
        thermal_residual_degc=1.5,
    )
    assert features.power_factor_derived == 0.92

    # Power factor cannot exceed 1.0
    with pytest.raises(ValidationError):
        DerivedFeatures(
            timestamp_utc=sample_utc_time(),
            power_factor_derived=1.5,
        )


def test_evidence_item_and_episode_states() -> None:
    """Verify EvidenceItem and exact 6-state Episode FSM bounds."""
    evidence = EvidenceItem(
        evidence_id="ev-001",
        asset_id="DT-001",
        event_time_utc=sample_utc_time(),
        category=AnomalyCategory.THERMAL_DEVIATION,
        detector_id="cusum_thermal_detector",
        observed_value=78.2,
        expected_value=72.0,
        unit="Cel",
        threshold_or_band="h=3.5",
        direction="POSITIVE_SHIFT",
        severity=0.65,
        confidence=0.9,
        input_lineage=["evt-001"],
        reason_codes=["CUSUM_POSITIVE_DRIFT"],
        hypothesis_codes=["POSSIBLE_COOLING_DEGRADATION"],
    )
    assert evidence.severity == 0.65

    episode = AnomalyEpisode(
        episode_id="ep-001",
        asset_id="DT-001",
        state=EpisodeState.WARNING,
        category=AnomalyCategory.THERMAL_DEVIATION,
        severity_score=0.65,
        start_time_utc=sample_utc_time(),
        last_seen_time_utc=sample_utc_time(),
        evidence_ids=["ev-001"],
        is_monitoring_gap=False,
        primary_reason="Persistent positive thermal residual shift",
        hypothesis_codes=["POSSIBLE_COOLING_DEGRADATION"],
    )
    assert episode.state == EpisodeState.WARNING


def test_domain_health_and_othi_bundle() -> None:
    """Verify exact 5 OTHI domains and composite bundle."""
    domains = {
        "thermal": DomainHealth(
            domain_name="thermal",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Thermal response matches expected grey-box state",
        ),
        "loading": DomainHealth(
            domain_name="loading",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Loading within continuous nameplate rating",
        ),
        "phase_neutral": DomainHealth(
            domain_name="phase_neutral",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Three-phase balance within acceptable limits",
        ),
        "voltage_pf_freq": DomainHealth(
            domain_name="voltage_pf_freq",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="Voltage and frequency within statutory tolerance",
        ),
        "oil_protection": DomainHealth(
            domain_name="oil_protection",
            severity=0.0,
            status=HealthStatus.NORMAL,
            details="All direct protection bits clear",
        ),
    }

    # Healthy transformer with valid domains gets OTHI = 100
    bundle = OTHIBundle(
        asset_id="DT-001",
        timestamp_utc=sample_utc_time(),
        othi_score=100,
        status=HealthStatus.NORMAL,
        evidence_grade=EvidenceGrade.A,
        driving_domain=None,
        base_penalty=0.0,
        secondary_penalty=0.0,
        total_penalty=0.0,
        is_gated=False,
        gate_reason=None,
        available_domains=["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"],
        domains=domains,
    )
    assert bundle.othi_score == 100
    assert bundle.is_gated is False


def test_maintenance_recommendation_and_operator_feedback() -> None:
    """Verify MaintenanceRecommendation and OperatorFeedbackEvent contracts."""
    rec = MaintenanceRecommendation(
        recommendation_id="rec-001",
        rule_id="MNT-PROT-001",
        rule_version="1.0.0",
        title="Immediate Trip Procedure",
        priority=MaintenancePriority.P0_SAFETY,
        priority_label="P0 SAFETY",
        action_window=ActionWindow.IMMEDIATE,
        advisory_wording="Follow the site-approved trip and isolation procedure.",
        rationale="Valid oil-temperature trip detected.",
        evidence_ids=["ev-trip-01"],
        source_reference="IEEE C57.91-2011",
        merge_key="TRIP_PRIMARY",
        created_at_utc=sample_utc_time(),
    )
    assert rec.priority == MaintenancePriority.P0_SAFETY
    assert rec.acknowledged is False

    feedback = OperatorFeedbackEvent(
        feedback_id="fb-001",
        asset_id="DT-001",
        timestamp_utc=sample_utc_time(),
        recommendation_id="rec-001",
        action=FeedbackAction.ACKNOWLEDGE,
        operator_id="operator_station_1",
        notes="Inspection crew dispatched.",
    )
    assert feedback.action == FeedbackAction.ACKNOWLEDGE


def test_twin_state_and_fact_bundle_full_assembly() -> None:
    """Verify complete FactBundle assembly and JSON serialization."""
    twin_state = TwinState(
        asset_id="DT-001",
        state_time_utc=sample_utc_time(),
        last_processed_event_id="evt-001",
        event_time_watermark_utc=sample_utc_time(),
        state_sequence=1,
        state_hash="sha256_state_hash_example",
    )
    manifest = CapabilityManifest(
        asset_id="DT-001",
        evaluated_at_utc=sample_utc_time(),
        highest_tier=CapabilityTier.C0_INTEGRITY,
        current_freshness_s=10.0,
    )
    domains = {
        "thermal": DomainHealth(domain_name="thermal", severity=0.0, status=HealthStatus.NORMAL, details="Normal"),
        "loading": DomainHealth(domain_name="loading", severity=0.0, status=HealthStatus.NORMAL, details="Normal"),
        "phase_neutral": DomainHealth(domain_name="phase_neutral", severity=0.0, status=HealthStatus.NORMAL, details="Normal"),
        "voltage_pf_freq": DomainHealth(domain_name="voltage_pf_freq", severity=0.0, status=HealthStatus.NORMAL, details="Normal"),
        "oil_protection": DomainHealth(domain_name="oil_protection", severity=0.0, status=HealthStatus.NORMAL, details="Normal"),
    }
    health = OTHIBundle(
        asset_id="DT-001",
        timestamp_utc=sample_utc_time(),
        othi_score=100,
        status=HealthStatus.NORMAL,
        evidence_grade=EvidenceGrade.B,
        base_penalty=0.0,
        secondary_penalty=0.0,
        total_penalty=0.0,
        is_gated=False,
        available_domains=["thermal", "loading", "phase_neutral", "voltage_pf_freq", "oil_protection"],
        domains=domains,
    )
    fact_bundle = FactBundle(
        fact_bundle_id="fb-bundle-001",
        asset_id="DT-001",
        timestamp_utc=sample_utc_time(),
        twin_state=twin_state,
        capabilities=manifest,
        health=health,
        open_episodes=[],
        active_recommendations=[],
        provenance_hash="sha256_bundle_hash_example",
    )

    json_str = fact_bundle.model_dump_json()
    loaded_bundle = FactBundle.model_validate_json(json_str)
    assert loaded_bundle.fact_bundle_id == fact_bundle.fact_bundle_id
    assert loaded_bundle.twin_state.asset_id == "DT-001"
