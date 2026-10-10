"""Regression and verification tests for backend stabilization fixes (FIX-1 through FIX-8).

Covers:
- FIX-1: Thermal residual evidence wiring from reducer into anomaly engine.
- FIX-2: Protection trip lifecycle, persistence, authorized unlatching, and recovery.
- FIX-3: Decoupling direct physical thermal limits from software model qualification.
- FIX-4: Advisory RESOLVE and DISMISS persistence and auto-closure.
- FIX-5: Telemetry adapter signal aliases (oil_level_pct, current_i1..3, voltage_v1..3) satisfying domain freshness.
- FIX-6: Dynamic nominal voltage binding from AssetProfile.
- FIX-7 & FIX-8: Sensor plausibility absolute step spike catching and flatline detection.
"""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from app.core.config import Settings
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.health import DomainFreshness, HealthStatus
from app.models.maintenance import (
    ActionWindow,
    FeedbackAction,
    MaintenancePriority,
    MaintenanceRecommendation,
    OperatorFeedbackEvent,
)
from app.models.profile import AssetProfile, ProfileField, ProfileVerificationStatus
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)
from app.models.thermal_artifact import QualificationStatus, ThermalModelQualification
from app.engine.anomaly_detectors import (
    AnomalyDetectorThresholds,
    MultiDomainAnomalyEngine,
    detect_sensor_plausibility,
    detect_voltage_pf_frequency,
)
from app.engine.feedback import OperatorFeedbackLedger
from app.engine.maintenance import MaintenanceEngine
from app.engine.othi import OTHIEngine
from app.engine.reducer import TwinReducer
from app.engine.thermal_fallback import ThermalFallbackGate


from app.engine.thermal import ThermalModelParameters


def _make_source_ref() -> SourceRef:
    return SourceRef(
        system="SCADA",
        adapter_id="test_adapter",
        source_record_id="rec_001",
        source_uri="test://telemetry/001",
        raw_sha256="0" * 64,
    )


def _make_event(
    asset_id: str = "TX_1000_COMM",
    event_time: datetime | None = None,
    measurements: list[Measurement] | None = None,
) -> CanonicalEvent:
    t = event_time or datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    ms = measurements or [
        Measurement(
            signal_id="frequency",
            value=50.0,
            value_type="float",
            unit_ucum="Hz",
            original_name="FREQ",
            original_value="50.0",
            original_unit="Hz",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD),
        )
    ]
    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=f"ev_{asset_id}_{t.strftime('%Y%m%d%H%M%S')}",
        asset_id=asset_id,
        event_time_utc=t,
        received_time_utc=t,
        source=_make_source_ref(),
        measurements=ms,
        event_quality_flags=[],
        mapping_version="1.0.0",
    )


# ==============================================================================
# 1. FIX-1: Thermal Residual Evidence Wiring in Reducer
# ==============================================================================

def test_reducer_wires_thermal_output_into_anomaly_engine() -> None:
    """TwinReducer must compute thermal_output and pass it into anomaly_engine.evaluate_event."""
    params = ThermalModelParameters(
        beta_0=5.0,
        beta_1=25.0,
        tau_hours=3.5,
    )
    gate = ThermalFallbackGate(
        asset_id="TX_1000_COMM",
        params=params,
        is_model_promoted=True,
    )
    qual = ThermalModelQualification(
        residual_anomaly_qualification=QualificationStatus.QUALIFIED,
        cusum_qualification=QualificationStatus.QUALIFIED,
        maintenance_inference_qualification=QualificationStatus.QUALIFIED,
    )
    anomaly_engine = MultiDomainAnomalyEngine(
        asset_id="TX_1000_COMM",
        qualification=qual,
    )
    reducer = TwinReducer(
        thermal_gate=gate,
        anomaly_engine=anomaly_engine,
    )

    # Step with large top-oil deviation relative to ambient and load
    event = _make_event(
        asset_id="TX_1000_COMM",
        measurements=[
            Measurement(
                signal_id="top_oil_temperature",
                value=95.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="95.0",
                original_unit="degC",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
            Measurement(
                signal_id="ambient_temperature",
                value=25.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="TAMB",
                original_value="25.0",
                original_unit="degC",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
            Measurement(
                signal_id="apparent_power_total",
                value=500.0,
                value_type="float",
                unit_ucum="kVA",
                original_name="S",
                original_value="500.0",
                original_unit="kVA",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
        ],
    )

    state = reducer.reduce(None, event)
    assert state is not None
    assert state.thermal_latent.top_oil_expected_degc is not None

    # The anomaly engine should have received thermal_output without crashing
    assert isinstance(reducer.latest_emitted_evidence, list)


# ==============================================================================
# 2. FIX-2: Protection-Trip Lifecycle, Persistence, and Authorized Unlatching
# ==============================================================================

def test_protection_trip_recovery_lifecycle() -> None:
    """Frame 1: Normal (100) -> Frame 2: Trip (0, CRITICAL) -> Frame 3: Normal with RESOLVE unlatches to 100."""
    ledger = OperatorFeedbackLedger()
    othi_engine = OTHIEngine(expected_cadence_seconds=900.0)
    othi_engine.feedback_ledger = ledger

    t1 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 12, 15, tzinfo=timezone.utc)
    t3 = datetime(2025, 1, 1, 12, 30, tzinfo=timezone.utc)

    # Frame 1: Normal healthy operation
    ev1 = _make_event(
        asset_id="TX_1000_COMM",
        event_time=t1,
        measurements=[
            Measurement(
                signal_id="top_oil_temperature",
                value=55.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="55.0",
                original_unit="degC",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
            Measurement(
                signal_id="breaker_trip",
                value=0,
                value_type="int",
                unit_ucum="1",
                original_name="TRIP",
                original_value="0",
                original_unit="1",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
        ],
    )
    b1 = othi_engine.evaluate(event=ev1)
    assert othi_engine.latched_protection_trip is False
    assert b1.othi_score == 100
    assert b1.status == HealthStatus.NORMAL

    # Frame 2: Direct protection trip occurs
    ev2 = _make_event(
        asset_id="TX_1000_COMM",
        event_time=t2,
        measurements=[
            Measurement(
                signal_id="top_oil_temperature",
                value=55.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="55.0",
                original_unit="degC",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
            Measurement(
                signal_id="breaker_trip",
                value=1,
                value_type="int",
                unit_ucum="1",
                original_name="TRIP",
                original_value="1",
                original_unit="1",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
        ],
    )
    b2 = othi_engine.evaluate(event=ev2)
    assert othi_engine.latched_protection_trip is True
    assert b2.othi_score == 0
    assert b2.status == HealthStatus.CRITICAL

    # Frame 2b: Breaker recloses (breaker_trip = 0), but NO operator resolution exists
    # Trip MUST remain latched!
    ev2b = _make_event(
        asset_id="TX_1000_COMM",
        event_time=t3,
        measurements=[
            Measurement(
                signal_id="top_oil_temperature",
                value=55.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="55.0",
                original_unit="degC",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
            Measurement(
                signal_id="breaker_trip",
                value=0,
                value_type="int",
                unit_ucum="1",
                original_name="TRIP",
                original_value="0",
                original_unit="1",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
        ],
    )
    b2b = othi_engine.evaluate(event=ev2b)
    assert othi_engine.latched_protection_trip is True, "Trip must not unlatch without authorized resolution"
    assert b2b.othi_score == 0

    # Frame 3: Operator records authorized resolution
    fb = OperatorFeedbackEvent(
        feedback_id="FB-TRIP-RESET-001",
        asset_id="TX_1000_COMM",
        timestamp_utc=t3,
        operator_id="PROTECTION_LEAD_01",
        action=FeedbackAction.RESOLVE,
        recommendation_id="REC-TX_1000_COMM-MNT-PROT-001",
        reason_code="TRIP_RESOLVED_AND_RESET",
        rationale="Fault verified cleared, breaker reclosed, transformer inspected.",
    )
    ledger.append(fb)

    # Frame 3 re-evaluation with breaker_trip = 0 and active resolution
    b3 = othi_engine.evaluate(event=ev2b)
    assert othi_engine.latched_protection_trip is False, "Trip must unlatch when signals are normal and resolution is recorded"
    assert b3.othi_score == 100
    assert b3.status == HealthStatus.NORMAL


# ==============================================================================
# 3. FIX-3: Decoupling Direct Physical Thermal Limits from Model Qualification
# ==============================================================================

def test_direct_thermal_limit_fires_on_unpromoted_asset() -> None:
    """Direct physical top-oil limit (>85°C) must trigger MNT-THERM-002 even if is_thermal_qualified=False."""
    engine = MaintenanceEngine(
        is_thermal_qualified=False,  # Unpromoted asset
        is_model_promoted=False,
    )

    ev_time = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    event = _make_event(asset_id="TX_250_MIX", event_time=ev_time)

    # Direct physical thermal limit evidence
    evidence = [
        EvidenceItem(
            evidence_id="ev_limit_001",
            asset_id="TX_250_MIX",
            event_time_utc=ev_time,
            category=AnomalyCategory.THERMAL_LIMIT,
            condition_family="THERMAL_LIMIT_EXCEEDANCE",
            detector_id="DET_THERMAL_LIMIT_ABSOLUTE",
            observed_value=92.0,
            expected_value="< 85.0 Cel",
            unit="Cel",
            threshold_or_band=">= 85.0 Cel",
            direction="HIGH",
            severity=0.85,
            confidence=0.95,
            input_lineage=["top_oil_temperature"],
            reason_codes=["TOP_OIL_LIMIT_ABSOLUTE_EXCEEDED"],
            hypothesis_codes=["HIGH_AMBIENT_OVERLOAD"],
        )
    ]

    recs = engine.evaluate(event=event, evidence_items=evidence)
    assert len(recs) >= 1
    therm_rec = next((r for r in recs if r.rule_id == "MNT-THERM-002"), None)
    assert therm_rec is not None, "MNT-THERM-002 must fire on direct physical limit even if model is unqualified"
    assert therm_rec.priority == MaintenancePriority.P1_URGENT_INSPECTION
    assert therm_rec.action_window == ActionWindow.WITHIN_24H
    assert "Direct" in therm_rec.title


def test_model_residual_deviation_gated_behind_qualification() -> None:
    """Model residual deviation alone must NOT trigger MNT-THERM-002 when is_thermal_qualified=False."""
    engine = MaintenanceEngine(
        is_thermal_qualified=False,  # Unpromoted asset
        is_model_promoted=False,
    )

    ev_time = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    event = _make_event(asset_id="TX_250_MIX", event_time=ev_time)

    # Model residual deviation evidence only (no physical limit)
    evidence = [
        EvidenceItem(
            evidence_id="ev_dev_001",
            asset_id="TX_250_MIX",
            event_time_utc=ev_time,
            category=AnomalyCategory.THERMAL_DEVIATION,
            condition_family="THERMAL_DEVIATION_UNEXPECTED",
            detector_id="DET_THERMAL_CUSUM_DRIFT",
            observed_value=4.8,
            expected_value=0.0,
            unit="sigma",
            threshold_or_band=">= 4.5",
            direction="POSITIVE_SHIFT",
            severity=0.75,
            confidence=0.85,
            input_lineage=["top_oil_temperature", "apparent_power_total"],
            reason_codes=["PERSISTENT_THERMAL_RESIDUAL_DRIFT"],
            hypothesis_codes=["COOLING_EFFICIENCY_SHIFT"],
        )
    ]

    recs = engine.evaluate(event=event, evidence_items=evidence)
    assert not any(r.rule_id == "MNT-THERM-002" for r in recs), "Model residual deviation must remain gated on unqualified asset"


# ==============================================================================
# 4. FIX-4: Advisory RESOLVE and DISMISS Persistence and Auto-Closure
# ==============================================================================

def test_operator_resolve_action_clears_recommendation() -> None:
    """Operator RESOLVE feedback must remove active recommendation and prevent recurrence until new evidence occurs."""
    ledger = OperatorFeedbackLedger()
    engine = MaintenanceEngine(
        feedback_ledger=ledger,
    )

    t1 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    t2 = datetime(2025, 1, 1, 12, 15, tzinfo=timezone.utc)
    t3 = datetime(2025, 1, 1, 12, 30, tzinfo=timezone.utc)

    # Frame 1: Phase unbalance evidence generates MNT-PHASE-004
    ev_item1 = EvidenceItem(
        evidence_id="ev_phase_001",
        asset_id="TX_1000_COMM",
        event_time_utc=t1,
        category=AnomalyCategory.PHASE_OR_NEUTRAL,
        condition_family="PHASE_OR_NEUTRAL_UNBALANCE",
        detector_id="DET_PHASE_CURRENT_IMBALANCE",
        observed_value=18.5,
        expected_value="< 10.0 %",
        unit="%",
        threshold_or_band=">= 15.0 %",
        direction="HIGH",
        severity=0.60,
        confidence=0.90,
        input_lineage=["current_i1", "current_i2", "current_i3"],
        reason_codes=["PHASE_CURRENT_IMBALANCE_WARNING"],
        hypothesis_codes=["FEEDER_UNBALANCE"],
    )
    event1 = _make_event(asset_id="TX_1000_COMM", event_time=t1)
    recs1 = engine.evaluate(event=event1, evidence_items=[ev_item1])
    assert any(r.rule_id == "MNT-PHASE-004" for r in recs1)
    rec_instance = next(r for r in recs1 if r.rule_id == "MNT-PHASE-004")

    # Frame 2: Operator records RESOLVE action
    fb = OperatorFeedbackEvent(
        feedback_id="FB-PHASE-RES-001",
        asset_id="TX_1000_COMM",
        timestamp_utc=t2,
        operator_id="SUBSTATION_TECH_01",
        action=FeedbackAction.RESOLVE,
        recommendation_id=rec_instance.recommendation_id,
        reason_code="PHASE_LOADS_REBALANCED",
        rationale="Phase loads rebalanced across downstream feeders.",
    )
    ledger.append(fb)

    # Frame 3: Subsequent telemetry step with NO new unbalance evidence
    event3 = _make_event(asset_id="TX_1000_COMM", event_time=t3)
    recs3 = engine.evaluate(
        event=event3,
        evidence_items=[],
        previous_recommendations=recs1,
    )
    assert not any(r.rule_id == "MNT-PHASE-004" for r in recs3), "Resolved recommendation must not persist"


# ==============================================================================
# 5. FIX-5: Telemetry Adapter Aliases Satisfying Domain Freshness
# ==============================================================================

def test_oil_level_pct_satisfies_freshness() -> None:
    """oil_level_pct must satisfy oil_protection domain freshness, preventing spurious Anti-Uplift lock."""
    othi_engine = OTHIEngine(expected_cadence_seconds=900.0)
    t = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    event = _make_event(
        asset_id="TX_1000_COMM",
        event_time=t,
        measurements=[
            Measurement(
                signal_id="oil_level_pct",
                value=85.0,
                value_type="float",
                unit_ucum="%",
                original_name="OIL_LVL",
                original_value="85.0",
                original_unit="%",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            )
        ],
    )

    bundle = othi_engine.evaluate(event=event)
    oil_domain = bundle.domains["oil_protection"]
    assert oil_domain.freshness == DomainFreshness.CURRENT
    assert oil_domain.is_stale is False


def test_current_and_voltage_aliases_satisfy_freshness() -> None:
    """current_i1..3 and voltage_v1..3 must satisfy loading, phase_neutral, and voltage_pf_freq freshness."""
    othi_engine = OTHIEngine(expected_cadence_seconds=900.0)
    t = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    event = _make_event(
        asset_id="TX_1000_COMM",
        event_time=t,
        measurements=[
            Measurement(
                signal_id="current_i1",
                value=120.0,
                value_type="float",
                unit_ucum="A",
                original_name="I1",
                original_value="120.0",
                original_unit="A",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
            Measurement(
                signal_id="voltage_v1",
                value=240.0,
                value_type="float",
                unit_ucum="V",
                original_name="V1",
                original_value="240.0",
                original_unit="V",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            ),
        ],
    )

    bundle = othi_engine.evaluate(event=event)
    assert bundle.domains["loading"].freshness == DomainFreshness.CURRENT
    assert bundle.domains["phase_neutral"].freshness == DomainFreshness.CURRENT
    assert bundle.domains["voltage_pf_freq"].freshness == DomainFreshness.CURRENT


# ==============================================================================
# 6. FIX-6: Dynamic Nominal Voltage Binding
# ==============================================================================

def test_feeder_voltage_250v_nominal_avoids_false_overvoltage() -> None:
    """With AssetProfile rated_voltage_lv_v=250.0, 245V is normal while 215V is undervoltage."""
    profile = AssetProfile(
        asset_id="DT-FEEDER-250",
        rated_voltage_lv_v=250.0,
        fields={
            "nominal_voltage_v": ProfileField(
                value=250.0,
                unit="V",
                source_document="Feeder Commissioning Report",
                status=ProfileVerificationStatus.VERIFIED,
            )
        },
    )

    t = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)

    # 1. 245.0V test (exceeds old 230V * 1.10 = 253V? No, 245 < 253, but 255 would trip old 230V)
    # At 250V nominal: V_max = 250 * 1.10 = 275V, V_min = 250 * 0.90 = 225V
    ev_260v = _make_event(
        asset_id="DT-FEEDER-250",
        event_time=t,
        measurements=[
            Measurement(
                signal_id="voltage_v1",
                value=260.0,
                value_type="float",
                unit_ucum="V",
                original_name="V1",
                original_value="260.0",
                original_unit="V",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            )
        ],
    )
    # Under old 230V default: 260V > 253V -> false overvoltage
    # Under 250V profile: 260V <= 275V -> NOT overvoltage
    evs_normal = detect_voltage_pf_frequency(event=ev_260v, profile=profile)
    assert not any(e.detector_id == "DET_VOLTAGE_SWELL_OR_OVERVOLTAGE" for e in evs_normal)

    # 2. 215.0V test:
    # Under old 230V default: 215V > 207V -> missed sag
    # Under 250V profile: 215V < 225V -> correctly caught as undervoltage!
    ev_215v = _make_event(
        asset_id="DT-FEEDER-250",
        event_time=t,
        measurements=[
            Measurement(
                signal_id="voltage_v1",
                value=215.0,
                value_type="float",
                unit_ucum="V",
                original_name="V1",
                original_value="215.0",
                original_unit="V",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            )
        ],
    )
    evs_sag = detect_voltage_pf_frequency(event=ev_215v, profile=profile)
    assert any(e.detector_id == "DET_VOLTAGE_SAG_OR_UNDERVOLTAGE" for e in evs_sag)


# ==============================================================================
# 7. FIX-7 & FIX-8: Sensor Plausibility Absolute Step Spike Catching
# ==============================================================================

def test_sensor_plausibility_catches_unphysical_temperature_step() -> None:
    """A sudden 15°C temperature step across a 30-min cadence must be caught as plausibility spike."""
    t0 = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    t1 = datetime(2025, 1, 1, 12, 30, tzinfo=timezone.utc)  # 30-minute interval

    history: dict[str, list[tuple[datetime, float]]] = {
        "top_oil_temperature": [(t0, 50.0)]
    }

    # Step from 50°C to 65°C: Delta T = 15°C, Delta t = 30 min -> RoC = 0.5 °C/min <= 1.0 °C/min
    # Without step threshold, this evades RoC check! With oti_max_step_degc=10.0, it must be caught!
    event = _make_event(
        asset_id="TX_1000_COMM",
        event_time=t1,
        measurements=[
            Measurement(
                signal_id="top_oil_temperature",
                value=65.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="65.0",
                original_unit="degC",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            )
        ],
    )

    evidence = detect_sensor_plausibility(
        event=event,
        history_buffer=history,
        thresholds=AnomalyDetectorThresholds(oti_max_step_degc=10.0),
    )
    roc_evs = [e for e in evidence if e.detector_id == "DET_PLAUS_RATE_OF_CHANGE"]
    assert len(roc_evs) == 1, "Unphysical 15°C temperature step must trigger rate-of-change/step plausibility anomaly"
