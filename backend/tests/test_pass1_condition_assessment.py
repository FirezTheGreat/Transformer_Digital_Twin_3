"""Pass 1 Focused Verification Suite: Telemetry Contracts, Model Qualification,
Physical Domain Handling, and OTHI Architecture.
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.engine.anomaly_detectors import (
    DEFAULT_DETECTOR_THRESHOLDS,
    MultiDomainAnomalyEngine,
    detect_data_quality,
    detect_protection_oil_status,
    detect_thermal_deviation,
)
from app.engine.feedback import OperatorFeedbackLedger
from app.models.maintenance import FeedbackAction, OperatorFeedbackEvent
from app.engine.othi import OTHIEngine, aggregate_othi_max_plus_secondary
from app.engine.thermal_fallback import ThermalFallbackGate
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.health import DomainFreshness, EvidenceGrade, HealthStatus
from app.models.profile import AssetProfile, ProfileVerificationStatus
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)
from app.models.thermal_artifact import (
    CalibratedThermalModelArtifact,
    PromotionDecision,
    QualificationStatus,
    ThermalModelParamsDict,
    ThermalModelQualification,
)


@pytest.fixture
def base_source_ref():
    return SourceRef(
        system="test_system",
        adapter_id="test_adapter",
        source_record_id="rec_1",
        source_uri="fixtures/test.json",
        raw_sha256="0" * 64,
    )


def test_partition_cal_metadata_not_flagged_as_data_quality_fault(base_source_ref):
    """Verify that PARTITION_CAL or other partition metadata is not flagged as a DQ anomaly."""
    event = CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt-dq-01",
        asset_id="DT-01",
        event_time_utc=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        source=base_source_ref,
        measurements=[
            Measurement(
                signal_id="current_i1",
                phase="L1",
                value=50.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_R",
                original_value="50.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            )
        ],
        event_quality_flags=["PARTITION_CAL", "PARTITION_FIT", "PARTITION_TEST", "VALIDATED"],
        mapping_version="1.0.0",
    )

    ev_items = detect_data_quality(event)
    env_flags = [e for e in ev_items if e.detector_id == "DET_DQ_ENVELOPE_FLAG"]
    assert len(env_flags) == 0, "Partition metadata or operational flags must not be treated as DQ faults"


def test_unpromoted_model_qualification_gating():
    """Verify unpromoted model cannot emit qualified operational anomaly evidence."""
    # Create an artifact marked NOT_PROMOTED but having calibration qualification flags
    artifact = CalibratedThermalModelArtifact(
        dataset_id="gridpulse_synthetic_v1",
        asset_id="DT-02",
        created_at_utc="2026-01-01T00:00:00Z",
        parameters=ThermalModelParamsDict(beta_0=5.0, beta_1=15.0, tau_hours=2.5),
        promotion=PromotionDecision(
            status="NOT_PROMOTED",
            mae_improvement_pct=2.1,
            passes_mae_criterion=False,
            passes_bias_criterion=True,
            passes_coverage_criterion=True,
            passes_scenario_criterion=True,
            passes_identifiability_criterion=True,
            all_criteria_met=False,
            reasons=["MAE improvement below 5%"],
        ),
        qualification=ThermalModelQualification(
            residual_anomaly_qualification=QualificationStatus.QUALIFIED,
            cusum_qualification=QualificationStatus.QUALIFIED,
        ),
    )

    gate = ThermalFallbackGate.from_artifact(artifact)
    assert not gate.is_model_promoted
    assert gate.qualification is not None
    assert gate.qualification.residual_anomaly_qualification == QualificationStatus.NOT_QUALIFIED
    assert gate.qualification.cusum_qualification == QualificationStatus.DISABLED
    assert not gate.cusum_tracker.is_qualified


def test_shadow_thermal_residuals_gated_from_othi():
    """Verify that unqualified shadow descriptive evidence is gated from driving physical OTHI severity."""
    engine = OTHIEngine(expected_cadence_seconds=1800.0)
    current_time = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    # Base event with normal measurements
    event = CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt-th-shadow",
        asset_id="DT-02",
        event_time_utc=current_time,
        source=SourceRef(
            system="test", adapter_id="test", source_record_id="1", source_uri="u", raw_sha256="0" * 64
        ),
        measurements=[
            Measurement(
                signal_id="top_oil_temperature",
                value=45.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="45.0",
                original_unit="°C",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="current_i1",
                value=40.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_R",
                original_value="40.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="current_i2",
                value=40.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_Y",
                original_value="40.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="current_i3",
                value=40.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_B",
                original_value="40.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
        ],
        event_quality_flags=[],
        mapping_version="1.0.0",
    )

    # Shadow descriptive evidence item emitted by unqualified model
    shadow_ev = EvidenceItem(
        evidence_id="ev_shadow_01",
        asset_id="DT-02",
        event_time_utc=current_time,
        category=AnomalyCategory.THERMAL_DEVIATION,
        detector_id="DET_THERMAL_SHADOW_DESCRIPTIVE",
        observed_value=2.5,
        expected_value=0.0,
        unit="sigma",
        threshold_or_band="Shadow Exploratory",
        direction="POSITIVE_SHIFT",
        severity=0.50,
        confidence=0.40,
        input_lineage=["oti_degc"],
        reason_codes=["SHADOW_THERMAL_CUSUM_EXCURSION"],
        hypothesis_codes=["UNQUALIFIED_SHADOW_EVIDENCE"],
    )

    bundle = engine.evaluate(event=event, evidence_items=[shadow_ev])
    # Thermal domain should NOT be penalized by the shadow evidence
    assert bundle.domains["thermal"].severity == 0.0
    assert bundle.othi_score == 100
    assert bundle.status == HealthStatus.NORMAL


def test_sealed_tank_asset_pressure_assessed_without_oil_level_gauge(base_source_ref):
    """Verify sealed-tank asset (DT-03) has oil_protection assessed via pressure without oil level gauge."""
    engine = OTHIEngine(expected_cadence_seconds=1800.0)
    current_time = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    # DT-03 has tank_pressure_kpa_g and no oil level
    event = CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt-dt03-press",
        asset_id="DT-03",
        event_time_utc=current_time,
        source=base_source_ref,
        measurements=[
            Measurement(
                signal_id="tank_pressure_kpa_g",
                value=12.5,
                value_type="float",
                unit_ucum="kPa",
                original_name="P_TANK",
                original_value="12.5",
                original_unit="kPa(g)",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="current_i1",
                value=35.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_R",
                original_value="35.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="current_i2",
                value=35.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_Y",
                original_value="35.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="current_i3",
                value=35.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_B",
                original_value="35.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
        ],
        event_quality_flags=[],
        mapping_version="1.0.0",
    )

    bundle = engine.evaluate(event=event)
    # oil_protection must be CURRENT and available because tank_pressure_kpa_g is fresh
    assert bundle.domains["oil_protection"].freshness == DomainFreshness.CURRENT
    assert "oil_protection" in bundle.current_domains
    assert "oil_protection" in bundle.available_domains


def test_bad_quality_oil_trend_suppressed_from_leak_evidence(base_source_ref):
    """Verify that bad-quality telemetry suppresses suspected leak trend evidence."""
    profile = AssetProfile(
        asset_id="DT-04",
        phase_topology="THREE_PHASE_4W",
        nominal_frequency_hz=50.0,
        rated_kva=160.0,
        rated_voltage_hv_v=11000.0,
        rated_voltage_lv_v=250.0,
        tank_type="CONSERVATOR",
        has_oil_level_gauge=True,
        has_pressure_sensor=False,
        cooling_class="ONAN",
        expected_cadence_s=1800,
        profile_status=ProfileVerificationStatus.VERIFIED,
        profile_version="1.0.0",
    )

    # Bad-quality oil trend measurement
    event_bad = CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt-bad-trend",
        asset_id="DT-04",
        event_time_utc=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        source=base_source_ref,
        measurements=[
            Measurement(
                signal_id="oil_level_trend_pct_per_day",
                value=-0.08,
                value_type="float",
                unit_ucum="percent/day",
                original_name="oil_trend",
                original_value="-0.08",
                original_unit="%/day",
                quality=MeasurementQuality(severity=QualitySeverity.BAD, flags=["COMM_LOSS"]),
            )
        ],
        event_quality_flags=[],
        mapping_version="1.0.0",
    )

    ev_bad = detect_protection_oil_status(event_bad, profile=profile)
    leak_evs = [e for e in ev_bad if e.detector_id == "DET_OIL_LEVEL_DECLINING_TREND"]
    assert len(leak_evs) == 0, "Bad-quality telemetry must not substantiate a physical leak trend"


def test_othi_monotonicity_and_anti_uplift():
    """Verify OTHI aggregation monotonicity and missing-evidence anti-uplift enforcement."""
    # 1. Monotonicity of aggregation formula
    score_clean, _, _, _, _ = aggregate_othi_max_plus_secondary(
        {"thermal": 0.0, "loading": 0.0, "phase_neutral": 0.0}
    )
    assert score_clean == 100

    score_mild, _, _, _, _ = aggregate_othi_max_plus_secondary(
        {"thermal": 0.30, "loading": 0.0, "phase_neutral": 0.0}
    )
    assert score_mild < score_clean

    score_severe, _, _, _, _ = aggregate_othi_max_plus_secondary(
        {"thermal": 0.70, "loading": 0.30, "phase_neutral": 0.0}
    )
    assert score_severe < score_mild

    # 2. Anti-uplift rule: missing domain cannot improve score
    engine = OTHIEngine(expected_cadence_seconds=1800.0)
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, 14, 0, tzinfo=timezone.utc)  # 2 hours later

    # Initial event with degraded thermal limit (severity 0.70)
    ev_thermal_crit = EvidenceItem(
        evidence_id="ev_th_01",
        asset_id="DT-01",
        event_time_utc=t0,
        category=AnomalyCategory.THERMAL_LIMIT,
        detector_id="DET_THERMAL_LIMIT_ABSOLUTE",
        observed_value=98.0,
        expected_value="< 90.0",
        unit="Cel",
        threshold_or_band=">= 90.0",
        direction="HIGH",
        severity=0.70,
        confidence=1.0,
        input_lineage=["top_oil_temperature"],
        reason_codes=["TOP_OIL_CRITICAL"],
        hypothesis_codes=["HIGH_LOSS"],
    )

    e0 = CanonicalEvent(
        schema_version="1.0.0",
        event_id="e0",
        asset_id="DT-01",
        event_time_utc=t0,
        source=SourceRef(system="s", adapter_id="a", source_record_id="0", source_uri="u", raw_sha256="0" * 64),
        measurements=[
            Measurement(
                signal_id="top_oil_temperature",
                value=98.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="98.0",
                original_unit="°C",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="current_i1",
                value=50.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_R",
                original_value="50.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
        ],
        event_quality_flags=[],
        mapping_version="1.0.0",
    )
    b0 = engine.evaluate(event=e0, evidence_items=[ev_thermal_crit])
    assert b0.othi_score is not None
    assert b0.othi_score <= 35
    assert b0.status == HealthStatus.CRITICAL

    # Next event at t1: top_oil_temperature sensor is lost (missing/stale), only current is present
    e1 = CanonicalEvent(
        schema_version="1.0.0",
        event_id="e1",
        asset_id="DT-01",
        event_time_utc=t1,
        source=SourceRef(system="s", adapter_id="a", source_record_id="1", source_uri="u", raw_sha256="0" * 64),
        measurements=[
            Measurement(
                signal_id="current_i1",
                value=50.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_R",
                original_value="50.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
        ],
        event_quality_flags=[],
        mapping_version="1.0.0",
    )
    b1 = engine.evaluate(event=e1, evidence_items=[])
    # Anti-uplift rule must trigger: numeric OTHI must be gated off with explanation
    assert b1.is_gated, "Losing thermal telemetry after a critical thermal fault must trigger anti-uplift gating"
    assert b1.gate_reason is not None
    assert b1.last_valid_othi == b0.othi_score
    assert b1.last_valid_status == HealthStatus.CRITICAL


def test_direct_protection_trip_latching_and_unlatching(base_source_ref):
    """Verify decisive direct protection trip latches OTHI to 0 / CRITICAL and unlatches upon resolution."""
    ledger = OperatorFeedbackLedger()
    engine = OTHIEngine(expected_cadence_seconds=1800.0)
    engine.feedback_ledger = ledger

    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, 12, 30, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc)

    # 1. Direct trip occurs at t0
    trip_event = CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt-trip-t0",
        asset_id="DT-01",
        event_time_utc=t0,
        source=base_source_ref,
        measurements=[
            Measurement(
                signal_id="oil_temp_trip_flag",
                value=True,
                value_type="bool",
                unit_ucum="1",
                original_name="OTI_T",
                original_value="1",
                original_unit="flag",
                quality=MeasurementQuality(severity=QualitySeverity.BAD, flags=["DIRECT_TRIP"]),
            ),
            Measurement(
                signal_id="lv_breaker_closed",
                value=False,
                value_type="bool",
                unit_ucum="1",
                original_name="52A",
                original_value="0",
                original_unit="binary",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=["BREAKER_TRIPPED"]),
            ),
        ],
        event_quality_flags=["PROTECTION_TRIP_ACTIVE"],
        mapping_version="1.0.0",
    )
    b0 = engine.evaluate(event=trip_event)
    assert b0.othi_score == 0
    assert b0.status == HealthStatus.CRITICAL
    assert engine.latched_protection_trip is True

    # 2. At t1, breaker is reclosed, but NO operator resolution in feedback ledger yet
    reclose_event = CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt-reclose-t1",
        asset_id="DT-01",
        event_time_utc=t1,
        source=base_source_ref,
        measurements=[
            Measurement(
                signal_id="oil_temp_trip_flag",
                value=False,
                value_type="bool",
                unit_ucum="1",
                original_name="OTI_T",
                original_value="0",
                original_unit="flag",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="lv_breaker_closed",
                value=True,
                value_type="bool",
                unit_ucum="1",
                original_name="52A",
                original_value="1",
                original_unit="binary",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="current_i1",
                value=40.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_R",
                original_value="40.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="current_i2",
                value=40.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_Y",
                original_value="40.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="current_i3",
                value=40.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_B",
                original_value="40.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
        ],
        event_quality_flags=[],
        mapping_version="1.0.0",
    )
    b1 = engine.evaluate(event=reclose_event)
    # Protection trip must remain latched until authorized resolution
    assert engine.latched_protection_trip is True
    assert b1.othi_score == 0
    assert b1.status == HealthStatus.CRITICAL

    # 3. Operator logs authorized resolution into feedback ledger
    ledger.append(
        OperatorFeedbackEvent(
            feedback_id="fb-res-01",
            recommendation_id="REC-DT-01-MNT-PROT-001",
            asset_id="DT-01",
            timestamp_utc=t1,
            operator_id="OP_CHIEF_99",
            action=FeedbackAction.RESOLVE,
            reason_code="SITE_CLEARANCE_VERIFIED",
            merge_key="PROTECTION_TRIP_RESOLVED",
        )
    )

    # 4. At t2, next event arrives after resolution
    normal_event = CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt-normal-t2",
        asset_id="DT-01",
        event_time_utc=t2,
        source=base_source_ref,
        measurements=reclose_event.measurements,
        event_quality_flags=[],
        mapping_version="1.0.0",
    )
    b2 = engine.evaluate(event=normal_event)
    assert engine.latched_protection_trip is False
    assert b2.othi_score is not None and b2.othi_score >= 80
    assert b2.status == HealthStatus.NORMAL


# ---------------------------------------------------------------------------
# Focused Tests: Gap 1 — Condition Health vs Instantaneous Operating Stress
# ---------------------------------------------------------------------------


def test_othi_temporal_condition_vs_instantaneous_stress_excursion(base_source_ref):
    """Verify 1-frame excursion does not degrade condition score, but raw_othi captures stress."""
    engine = OTHIEngine(expected_cadence_seconds=1800.0)
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=15)
    t2 = t0 + timedelta(minutes=30)

    def _make_event(eid, t, top_oil):
        return CanonicalEvent(
            schema_version="1.0.0",
            event_id=eid,
            asset_id="DT-01",
            event_time_utc=t,
            source=base_source_ref,
            measurements=[
                Measurement(
                    signal_id="top_oil_temperature",
                    value=top_oil,
                    value_type="float",
                    unit_ucum="Cel",
                    original_name="OTI",
                    original_value=str(top_oil),
                    original_unit="°C",
                    quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
                ),
                Measurement(
                    signal_id="current_i1",
                    value=40.0,
                    value_type="float",
                    unit_ucum="A",
                    original_name="I_R",
                    original_value="40.0",
                    original_unit="A",
                    quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
                ),
            ],
            event_quality_flags=[],
            mapping_version="1.0.0",
        )

    # 1. Baseline normal event
    e0 = _make_event("e0", t0, top_oil=60.0)
    b0 = engine.evaluate(event=e0, evidence_items=[])
    assert b0.othi_score == 100
    assert b0.raw_othi == 100
    assert b0.status == HealthStatus.NORMAL

    # 2. One-frame operating stress excursion (thermal critical penalty 0.70)
    e1 = _make_event("e1", t1, top_oil=98.0)
    ev_stress = EvidenceItem(
        evidence_id="ev_th_stress",
        asset_id="DT-01",
        event_time_utc=t1,
        category=AnomalyCategory.THERMAL_LIMIT,
        detector_id="DET_THERMAL_LIMIT_ABSOLUTE",
        observed_value=98.0,
        expected_value="< 90.0",
        unit="Cel",
        threshold_or_band=">= 90.0",
        direction="HIGH",
        severity=0.70,
        confidence=1.0,
        input_lineage=["top_oil_temperature"],
        reason_codes=["TOP_OIL_CRITICAL"],
        hypothesis_codes=["HIGH_LOSS"],
    )
    b1 = engine.evaluate(event=e1, evidence_items=[ev_stress])
    # Instantaneous stress captured in raw_othi
    assert b1.raw_othi is not None and b1.raw_othi <= 35
    assert b1.raw_status == HealthStatus.CRITICAL
    # Slower-moving condition score holds baseline (100) on 1-frame excursion
    assert b1.othi_score == 100
    assert b1.status == HealthStatus.NORMAL

    # 3. Next frame returns to normal
    e2 = _make_event("e2", t2, top_oil=62.0)
    b2 = engine.evaluate(event=e2, evidence_items=[])
    assert b2.othi_score == 100
    assert b2.raw_othi == 100
    assert b2.status == HealthStatus.NORMAL


def test_othi_sustained_degradation_transitions_condition_score(base_source_ref):
    """Verify sustained operating stress across persistence window degrades condition score."""
    engine = OTHIEngine(expected_cadence_seconds=1800.0)
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=15)
    t2 = t0 + timedelta(minutes=45)  # 30 min later: elapsed >= 1800s

    def _make_event(eid, t):
        return CanonicalEvent(
            schema_version="1.0.0",
            event_id=eid,
            asset_id="DT-01",
            event_time_utc=t,
            source=base_source_ref,
            measurements=[
                Measurement(
                    signal_id="top_oil_temperature",
                    value=98.0,
                    value_type="float",
                    unit_ucum="Cel",
                    original_name="OTI",
                    original_value="98.0",
                    original_unit="°C",
                    quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
                ),
                Measurement(
                    signal_id="current_i1",
                    value=40.0,
                    value_type="float",
                    unit_ucum="A",
                    original_name="I_R",
                    original_value="40.0",
                    original_unit="A",
                    quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
                ),
            ],
            event_quality_flags=[],
            mapping_version="1.0.0",
        )

    ev_stress = EvidenceItem(
        evidence_id="ev_th_stress",
        asset_id="DT-01",
        event_time_utc=t1,
        category=AnomalyCategory.THERMAL_LIMIT,
        detector_id="DET_THERMAL_LIMIT_ABSOLUTE",
        observed_value=98.0,
        expected_value="< 90.0",
        unit="Cel",
        threshold_or_band=">= 90.0",
        direction="HIGH",
        severity=0.70,
        confidence=1.0,
        input_lineage=["top_oil_temperature"],
        reason_codes=["TOP_OIL_CRITICAL"],
        hypothesis_codes=["HIGH_LOSS"],
    )

    # Baseline healthy
    e0 = CanonicalEvent(
        schema_version="1.0.0",
        event_id="e0",
        asset_id="DT-01",
        event_time_utc=t0,
        source=base_source_ref,
        measurements=[
            Measurement(
                signal_id="top_oil_temperature",
                value=60.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="60.0",
                original_unit="°C",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="current_i1",
                value=40.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_R",
                original_value="40.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
        ],
        event_quality_flags=[],
        mapping_version="1.0.0",
    )
    b0 = engine.evaluate(event=e0, evidence_items=[])
    assert b0.othi_score == 100

    # First observation of degradation (candidate)
    e1 = _make_event("e1", t1)
    b1 = engine.evaluate(event=e1, evidence_items=[ev_stress])
    assert b1.raw_othi <= 35
    assert b1.othi_score == 100  # Held pending persistence

    # Second observation after elapsed >= 1800s: sustained degradation confirmed
    e2 = _make_event("e2", t2)
    ev_stress2 = ev_stress.model_copy(update={"event_time_utc": t2})
    b2 = engine.evaluate(event=e2, evidence_items=[ev_stress2])
    assert b2.raw_othi <= 35
    assert b2.othi_score <= 35
    assert b2.status == HealthStatus.CRITICAL


def test_othi_condition_recovery_behavior(base_source_ref):
    """Verify that condition score recovers to normal once sustained degradation clears."""
    engine = OTHIEngine(expected_cadence_seconds=1800.0)
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=45)
    t2 = t0 + timedelta(minutes=75)

    meas_clean = [
        Measurement(
            signal_id="top_oil_temperature",
            value=60.0,
            value_type="float",
            unit_ucum="Cel",
            original_name="OTI",
            original_value="60.0",
            original_unit="°C",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
        ),
        Measurement(
            signal_id="current_i1",
            value=40.0,
            value_type="float",
            unit_ucum="A",
            original_name="I_R",
            original_value="40.0",
            original_unit="A",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
        ),
    ]

    # Cold start into degraded state
    ev_deg = EvidenceItem(
        evidence_id="ev_deg",
        asset_id="DT-01",
        event_time_utc=t0,
        category=AnomalyCategory.THERMAL_LIMIT,
        detector_id="DET_THERMAL_LIMIT_ABSOLUTE",
        observed_value=98.0,
        expected_value="< 90.0",
        unit="Cel",
        threshold_or_band=">= 90.0",
        direction="HIGH",
        severity=0.70,
        confidence=1.0,
        input_lineage=["top_oil_temperature"],
        reason_codes=["TOP_OIL_CRITICAL"],
        hypothesis_codes=["HIGH_LOSS"],
    )
    e0 = CanonicalEvent(
        schema_version="1.0.0",
        event_id="e0",
        asset_id="DT-01",
        event_time_utc=t0,
        source=base_source_ref,
        measurements=meas_clean,
        event_quality_flags=[],
        mapping_version="1.0.0",
    )
    b0 = engine.evaluate(event=e0, evidence_items=[ev_deg])
    assert b0.othi_score <= 35

    # Telemetry clears and returns to normal
    e1 = CanonicalEvent(
        schema_version="1.0.0",
        event_id="e1",
        asset_id="DT-01",
        event_time_utc=t1,
        source=base_source_ref,
        measurements=meas_clean,
        event_quality_flags=[],
        mapping_version="1.0.0",
    )
    b1 = engine.evaluate(event=e1, evidence_items=[])
    assert b1.othi_score == 100
    assert b1.status == HealthStatus.NORMAL


def test_othi_direct_protection_trip_immediate(base_source_ref):
    """Verify that a direct protection trip drops othi_score to 0 immediately on frame 1."""
    engine = OTHIEngine(expected_cadence_seconds=1800.0)
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    # Initial healthy state
    e0 = CanonicalEvent(
        schema_version="1.0.0",
        event_id="e0",
        asset_id="DT-01",
        event_time_utc=t0,
        source=base_source_ref,
        measurements=[
            Measurement(
                signal_id="top_oil_temperature",
                value=60.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="60.0",
                original_unit="°C",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="current_i1",
                value=40.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_R",
                original_value="40.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
        ],
        event_quality_flags=[],
        mapping_version="1.0.0",
    )
    b0 = engine.evaluate(event=e0, evidence_items=[])
    assert b0.othi_score == 100

    # Protection trip arrives on frame 1
    t1 = t0 + timedelta(minutes=5)
    e1 = CanonicalEvent(
        schema_version="1.0.0",
        event_id="e1",
        asset_id="DT-01",
        event_time_utc=t1,
        source=base_source_ref,
        measurements=[
            Measurement(
                signal_id="breaker_trip",
                value=1,
                value_type="int",
                unit_ucum="1",
                original_name="TRIP",
                original_value="1",
                original_unit="binary",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=["DIRECT_TRIP"]),
            ),
        ],
        event_quality_flags=["DIRECT_PROTECTION_TRIP"],
        mapping_version="1.0.0",
    )
    b1 = engine.evaluate(event=e1, evidence_items=[])
    # Unconditional immediate precedence: score drops to 0 on frame 1 without delay
    assert b1.othi_score == 0
    assert b1.status == HealthStatus.CRITICAL
    assert engine.latched_protection_trip is True


def test_othi_replay_determinism_and_asset_isolation(base_source_ref):
    """Verify replay determinism and zero state leakage across asset switching."""
    engine = OTHIEngine(expected_cadence_seconds=1800.0)
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=15)

    e0 = CanonicalEvent(
        schema_version="1.0.0",
        event_id="e0",
        asset_id="DT-01",
        event_time_utc=t0,
        source=base_source_ref,
        measurements=[
            Measurement(
                signal_id="top_oil_temperature",
                value=60.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="60.0",
                original_unit="°C",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="current_i1",
                value=40.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_R",
                original_value="40.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
        ],
        event_quality_flags=[],
        mapping_version="1.0.0",
    )

    # Run pass 1
    r1_b0 = engine.evaluate(event=e0, evidence_items=[])
    engine.reset()
    # Run pass 2 after reset: bit-for-bit identical
    r2_b0 = engine.evaluate(event=e0, evidence_items=[])
    assert r1_b0.othi_score == r2_b0.othi_score
    assert r1_b0.raw_othi == r2_b0.raw_othi

    # Switch asset to DT-02: engine automatically resets without leaking DT-01 state
    e_dt02 = CanonicalEvent(
        schema_version="1.0.0",
        event_id="e_dt02",
        asset_id="DT-02",
        event_time_utc=t1,
        source=base_source_ref,
        measurements=e0.measurements,
        event_quality_flags=[],
        mapping_version="1.0.0",
    )
    b_dt02 = engine.evaluate(event=e_dt02, evidence_items=[])
    assert engine.current_asset_id == "DT-02"
    assert b_dt02.asset_id == "DT-02"


# ---------------------------------------------------------------------------
# Focused Tests: Gap 2 — Pressure Transient vs Sustained Excursions
# ---------------------------------------------------------------------------


def test_pressure_isolated_excursion_distinguished_from_sustained(base_source_ref):
    """Verify analog pressure threshold spike emits TRANSIENT evidence and does NOT emit HIGH_ALARM."""
    profile = AssetProfile(
        asset_id="DT-03",
        rated_kva=500.0,
        tank_type="SEALED_CORRUGATED",
        has_pressure_sensor=True,
        has_oil_level_gauge=False,
    )
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=15)

    history = {"tank_pressure_kpa_g": [(t0, 10.0)]}

    # Isolated excursion: pressure jumps to 28.0 kPa(g) >= 25.0 warning threshold
    event = CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt-p-spike",
        asset_id="DT-03",
        event_time_utc=t1,
        source=base_source_ref,
        measurements=[
            Measurement(
                signal_id="tank_pressure_kpa_g",
                value=28.0,
                value_type="float",
                unit_ucum="kPa",
                original_name="P_TANK",
                original_value="28.0",
                original_unit="kPa(g)",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            )
        ],
        event_quality_flags=[],
        mapping_version="1.0.0",
    )

    evidence = detect_protection_oil_status(event=event, profile=profile, history_buffer=history)
    det_ids = [e.detector_id for e in evidence]
    assert "DET_PRESSURE_HIGH_TRANSIENT" in det_ids
    assert "DET_PRESSURE_HIGH_ALARM" not in det_ids
    transient_item = next(e for e in evidence if e.detector_id == "DET_PRESSURE_HIGH_TRANSIENT")
    assert transient_item.severity == 0.25


def test_pressure_sustained_threshold_violation(base_source_ref):
    """Verify consecutive pressure threshold crossings emit actionable DET_PRESSURE_HIGH_ALARM."""
    profile = AssetProfile(
        asset_id="DT-03",
        rated_kva=500.0,
        tank_type="SEALED_CORRUGATED",
        has_pressure_sensor=True,
        has_oil_level_gauge=False,
    )
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=15)

    # History already shows prior high reading (27.5 kPa(g) >= 25.0)
    history = {"tank_pressure_kpa_g": [(t0, 27.5)]}

    event = CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt-p-sustained",
        asset_id="DT-03",
        event_time_utc=t1,
        source=base_source_ref,
        measurements=[
            Measurement(
                signal_id="tank_pressure_kpa_g",
                value=28.0,
                value_type="float",
                unit_ucum="kPa",
                original_name="P_TANK",
                original_value="28.0",
                original_unit="kPa(g)",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            )
        ],
        event_quality_flags=[],
        mapping_version="1.0.0",
    )

    evidence = detect_protection_oil_status(event=event, profile=profile, history_buffer=history)
    det_ids = [e.detector_id for e in evidence]
    assert "DET_PRESSURE_HIGH_ALARM" in det_ids
    alarm_item = next(e for e in evidence if e.detector_id == "DET_PRESSURE_HIGH_ALARM")
    assert alarm_item.severity == 0.85


def test_pressure_immediate_protection_contact(base_source_ref):
    """Verify hardware PRD operation is immediate and never delayed by history."""
    profile = AssetProfile(
        asset_id="DT-03",
        rated_kva=500.0,
        tank_type="SEALED_CORRUGATED",
        has_pressure_sensor=True,
        has_oil_level_gauge=False,
    )
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    event = CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt-prd-immediate",
        asset_id="DT-03",
        event_time_utc=t0,
        source=base_source_ref,
        measurements=[
            Measurement(
                signal_id="prd_operated",
                value=1,
                value_type="int",
                unit_ucum="1",
                original_name="PRD",
                original_value="1",
                original_unit="binary",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            )
        ],
        event_quality_flags=[],
        mapping_version="1.0.0",
    )

    evidence = detect_protection_oil_status(event=event, profile=profile, history_buffer={})
    det_ids = [e.detector_id for e in evidence]
    assert "DET_PRESSURE_RELIEF_OPERATED" in det_ids
    prd_item = next(e for e in evidence if e.detector_id == "DET_PRESSURE_RELIEF_OPERATED")
    assert prd_item.severity == 1.0


# ---------------------------------------------------------------------------
# Focused Tests: Gap 3 — Online Oil-Level Trend Fallback
# ---------------------------------------------------------------------------


def test_online_oil_trend_temperature_variation_without_leak(base_source_ref):
    """Verify bulk-oil temperature correction prevents false leak alarm under heavy thermal expansion."""
    profile = AssetProfile(
        asset_id="DT-01",
        rated_kva=100.0,
        tank_type="CONSERVATOR",
        has_oil_level_gauge=True,
        has_pressure_sensor=False,
    )
    history: dict = {}
    t_base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Simulate 24 hours of data (48 points, 30 min apart)
    # Temperature rises from 30°C to 50°C; level expands by 0.75 * 20 = 15% (from 50% to 65%)
    for i in range(48):
        t = t_base + timedelta(minutes=30 * i)
        temp = 30.0 + (20.0 * i / 47.0)
        # Raw level expands with temperature:
        raw_level = 50.0 + 0.75 * (temp - 30.0)

        ev = CanonicalEvent(
            schema_version="1.0.0",
            event_id=f"evt-temp-sweep-{i}",
            asset_id="DT-01",
            event_time_utc=t,
            source=base_source_ref,
            measurements=[
                Measurement(
                    signal_id="oil_level_pct",
                    value=round(raw_level, 2),
                    value_type="float",
                    unit_ucum="%",
                    original_name="OIL_LVL",
                    original_value=str(round(raw_level, 2)),
                    original_unit="%",
                    quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
                ),
                Measurement(
                    signal_id="top_oil_temperature",
                    value=round(temp, 2),
                    value_type="float",
                    unit_ucum="Cel",
                    original_name="OTI",
                    original_value=str(round(temp, 2)),
                    original_unit="°C",
                    quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
                ),
            ],
            event_quality_flags=[],
            mapping_version="1.0.0",
        )
        evidence = detect_protection_oil_status(event=ev, profile=profile, history_buffer=history)

    # Corrected level is constant at 50%; slope is 0.0 -> no leak trend emitted
    det_ids = [e.detector_id for e in evidence]
    assert "DET_OIL_LEVEL_DECLINING_TREND" not in det_ids


def test_online_oil_trend_sustained_leak(base_source_ref):
    """Verify online estimator detects true leakage slope when precomputed trend is absent."""
    profile = AssetProfile(
        asset_id="DT-01",
        rated_kva=100.0,
        tank_type="CONSERVATOR",
        has_oil_level_gauge=True,
        has_pressure_sensor=False,
    )
    history: dict = {}
    t_base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Simulate 24 hours of data with 2.4% / day oil loss at constant temperature 30°C
    evidence = []
    for i in range(48):
        t = t_base + timedelta(minutes=30 * i)
        # Declines by 2.4% over 48 steps (24 hours)
        raw_level = 50.0 - (2.4 * i / 47.0)

        ev = CanonicalEvent(
            schema_version="1.0.0",
            event_id=f"evt-leak-{i}",
            asset_id="DT-01",
            event_time_utc=t,
            source=base_source_ref,
            measurements=[
                Measurement(
                    signal_id="oil_level_pct",
                    value=round(raw_level, 2),
                    value_type="float",
                    unit_ucum="%",
                    original_name="OIL_LVL",
                    original_value=str(round(raw_level, 2)),
                    original_unit="%",
                    quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
                ),
                Measurement(
                    signal_id="top_oil_temperature",
                    value=30.0,
                    value_type="float",
                    unit_ucum="Cel",
                    original_name="OTI",
                    original_value="30.0",
                    original_unit="°C",
                    quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
                ),
            ],
            event_quality_flags=[],
            mapping_version="1.0.0",
        )
        evidence = detect_protection_oil_status(event=ev, profile=profile, history_buffer=history)

    det_ids = [e.detector_id for e in evidence]
    assert "DET_OIL_LEVEL_DECLINING_TREND" in det_ids
    leak_item = next(e for e in evidence if e.detector_id == "DET_OIL_LEVEL_DECLINING_TREND")
    assert leak_item.observed_value <= -2.0  # ~ -2.4 %/day
    assert "EST_DAYS_TO_WARN" in leak_item.threshold_or_band
    assert "ONLINE_ESTIMATE" in leak_item.reason_codes[0]


def test_online_oil_trend_insufficient_history(base_source_ref):
    """Verify online estimator does NOT fabricate a leak estimate with insufficient history."""
    profile = AssetProfile(
        asset_id="DT-01",
        rated_kva=100.0,
        tank_type="CONSERVATOR",
        has_oil_level_gauge=True,
        has_pressure_sensor=False,
    )
    history: dict = {}
    t_base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Only 3 samples over 1 hour (requires >= 6 samples and >= 12 hours)
    for i in range(3):
        t = t_base + timedelta(minutes=30 * i)
        ev = CanonicalEvent(
            schema_version="1.0.0",
            event_id=f"evt-short-{i}",
            asset_id="DT-01",
            event_time_utc=t,
            source=base_source_ref,
            measurements=[
                Measurement(
                    signal_id="oil_level_pct",
                    value=45.0 - i,
                    value_type="float",
                    unit_ucum="%",
                    original_name="OIL_LVL",
                    original_value=str(45.0 - i),
                    original_unit="%",
                    quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
                ),
                Measurement(
                    signal_id="top_oil_temperature",
                    value=30.0,
                    value_type="float",
                    unit_ucum="Cel",
                    original_name="OTI",
                    original_value="30.0",
                    original_unit="°C",
                    quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
                ),
            ],
            event_quality_flags=[],
            mapping_version="1.0.0",
        )
        evidence = detect_protection_oil_status(event=ev, profile=profile, history_buffer=history)

    det_ids = [e.detector_id for e in evidence]
    assert "DET_OIL_LEVEL_DECLINING_TREND" not in det_ids


def test_online_oil_trend_bad_quality_suppressed(base_source_ref):
    """Verify online estimator is suppressed when telemetry quality is BAD."""
    profile = AssetProfile(
        asset_id="DT-01",
        rated_kva=100.0,
        tank_type="CONSERVATOR",
        has_oil_level_gauge=True,
        has_pressure_sensor=False,
    )
    t = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ev = CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt-bad-qual",
        asset_id="DT-01",
        event_time_utc=t,
        source=base_source_ref,
        measurements=[
            Measurement(
                signal_id="oil_level_pct",
                value=20.0,
                value_type="float",
                unit_ucum="%",
                original_name="OIL_LVL",
                original_value="20.0",
                original_unit="%",
                quality=MeasurementQuality(severity=QualitySeverity.BAD, flags=["COMM_LOSS"]),
            ),
            Measurement(
                signal_id="top_oil_temperature",
                value=30.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="30.0",
                original_unit="°C",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
        ],
        event_quality_flags=[],
        mapping_version="1.0.0",
    )
    evidence = detect_protection_oil_status(event=ev, profile=profile, history_buffer={})
    det_ids = [e.detector_id for e in evidence]
    assert "DET_OIL_LEVEL_DECLINING_TREND" not in det_ids


def test_online_oil_trend_reset_and_asset_isolation(base_source_ref):
    """Verify engine reset and asset isolation clear online corrected oil history."""
    engine = MultiDomainAnomalyEngine(asset_id="DT-01")
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    ev = CanonicalEvent(
        schema_version="1.0.0",
        event_id="evt-iso-0",
        asset_id="DT-01",
        event_time_utc=t0,
        source=base_source_ref,
        measurements=[
            Measurement(
                signal_id="oil_level_pct",
                value=50.0,
                value_type="float",
                unit_ucum="%",
                original_name="OIL_LVL",
                original_value="50.0",
                original_unit="%",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
            Measurement(
                signal_id="top_oil_temperature",
                value=30.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="30.0",
                original_unit="°C",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD, flags=[]),
            ),
        ],
        event_quality_flags=[],
        mapping_version="1.0.0",
    )
    engine.evaluate_event(event=ev)
    assert "_online_corr_oil_DT-01" in engine._history_buffer
    assert len(engine._history_buffer["_online_corr_oil_DT-01"]) == 1

    # Reset clears history
    engine.reset_history()
    assert len(engine._history_buffer) == 0
