"""Phase 5.4 — Multi-Domain Anomaly Detectors Test Suite.

Comprehensive tests verifying detection across all 8 canonical anomaly categories:
1. DATA_QUALITY
2. SENSOR_PLAUSIBILITY
3. THERMAL_DEVIATION
4. THERMAL_LIMIT
5. LOADING
6. PHASE_OR_NEUTRAL
7. VOLTAGE_PF_FREQUENCY
8. PROTECTION_OR_OIL_STATUS

Asserts that all emitted EvidenceItem records carry exact severity, confidence,
deterministic reason codes, and input lineage.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from app.engine.anomaly_detectors import (
    AnomalyDetectorThresholds,
    MultiDomainAnomalyEngine,
    detect_data_quality,
    detect_sensor_plausibility,
    detect_thermal_limits,
    detect_thermal_deviation,
    detect_loading,
    detect_phase_neutral,
    detect_voltage_pf_frequency,
    detect_protection_oil_status,
)
from app.engine.physics import extract_electrical_features
from app.engine.thermal_fallback import ThermalRuntimeOutput
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.features import DerivedFeatures
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)
from app.models.thermal_artifact import QualificationStatus, ThermalModelQualification


# ---------------------------------------------------------------------------
# Test Helpers & Event Builders
# ---------------------------------------------------------------------------

def _source_ref() -> SourceRef:
    return SourceRef(
        system="tripura_csv",
        adapter_id="tripura_v1",
        source_record_id="row_1",
        source_uri="file:///data/test.csv",
        raw_sha256="abcdef1234567890",
    )


def _build_event(
    asset_id: str = "TX_01",
    event_time_utc: datetime | None = None,
    measurements: list[Measurement] | None = None,
    flags: list[str] | None = None,
) -> CanonicalEvent:
    t = event_time_utc or datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    meas = measurements or [
        Measurement(
            signal_id="oti_degc",
            value=60.0,
            value_type="float",
            unit_ucum="Cel",
            original_name="OTI",
            original_value="60.0",
            original_unit="degC",
            quality=MeasurementQuality(severity=QualitySeverity.GOOD),
        )
    ]
    return CanonicalEvent(
        event_id=f"evt_{int(t.timestamp())}",
        asset_id=asset_id,
        event_time_utc=t,
        source=_source_ref(),
        measurements=meas,
        event_quality_flags=flags or [],
        mapping_version="1.0.0",
    )


# ---------------------------------------------------------------------------
# 1. DATA_QUALITY Tests
# ---------------------------------------------------------------------------

def test_data_quality_bad_measurement_severity():
    """Verify BAD measurement quality severity emits DATA_QUALITY evidence."""
    ev = _build_event(
        measurements=[
            Measurement(
                signal_id="current_l1",
                value=50.0,
                value_type="float",
                unit_ucum="A",
                original_name="I_L1",
                original_value="50.0",
                original_unit="A",
                quality=MeasurementQuality(
                    severity=QualitySeverity.BAD,
                    flags=["CORRUPTED_CRC", "OUT_OF_RANGE"],
                ),
            )
        ]
    )

    evidence = detect_data_quality(ev)
    assert len(evidence) == 1
    item = evidence[0]
    assert item.category == AnomalyCategory.DATA_QUALITY
    assert item.detector_id == "DET_DQ_MEASUREMENT_QUALITY"
    assert item.severity == 0.70
    assert item.confidence == 1.0
    assert "current_l1" in item.input_lineage
    assert "MEASUREMENT_QUALITY_FLAGGED" in item.reason_codes


def test_data_quality_pqs_inconsistency():
    """Verify P-Q-S inconsistency metric emits DATA_QUALITY evidence."""
    ev = _build_event()
    derived = DerivedFeatures(
        timestamp_utc=ev.event_time_utc,
        pqs_inconsistency=0.25,  # 25% discrepancy between S and sqrt(P^2+Q^2)
        transform_version="1.0.0",
    )

    evidence = detect_data_quality(ev, derived=derived)
    pqs_items = [e for e in evidence if e.detector_id == "DET_DQ_PQS_INCONSISTENCY"]
    assert len(pqs_items) == 1
    item = pqs_items[0]
    assert item.category == AnomalyCategory.DATA_QUALITY
    assert item.observed_value == 0.25
    assert "PQS_TRIANGLE_INCONSISTENCY" in item.reason_codes


# ---------------------------------------------------------------------------
# 2. SENSOR_PLAUSIBILITY Tests
# ---------------------------------------------------------------------------

def test_sensor_plausibility_impossible_rate_of_change():
    """Verify impossible thermal rate of change (>1.0 degC/min) emits SENSOR_PLAUSIBILITY evidence."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc)

    history = {"oti_degc": [(t0, 50.0)]}
    # 50 -> 80 in 15 min = 2.0 degC/min (exceeds 1.0 degC/min floor)
    ev = _build_event(
        event_time_utc=t1,
        measurements=[
            Measurement(
                signal_id="oti_degc",
                value=80.0,
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="80.0",
                original_unit="degC",
                quality=MeasurementQuality(severity=QualitySeverity.GOOD),
            )
        ],
    )

    evidence = detect_sensor_plausibility(ev, history_buffer=history)
    assert len(evidence) == 1
    item = evidence[0]
    assert item.category == AnomalyCategory.SENSOR_PLAUSIBILITY
    assert item.detector_id == "DET_PLAUS_RATE_OF_CHANGE"
    assert item.observed_value == 2.0
    assert item.severity == 0.85


def test_sensor_plausibility_frozen_flatline():
    """Verify sensor stuck across 4 consecutive steps emits SENSOR_PLAUSIBILITY flatline evidence."""
    t0 = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 1, 10, 30, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 1, 10, 45, tzinfo=timezone.utc)

    history = {
        "oti_degc": [(t0, 65.0), (t1, 65.0), (t2, 65.0)]
    }
    ev = _build_event(
        event_time_utc=t3,
        measurements=[
            Measurement(
                signal_id="oti_degc",
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

    evidence = detect_sensor_plausibility(ev, history_buffer=history)
    stuck_items = [e for e in evidence if e.detector_id == "DET_PLAUS_FROZEN_SENSOR"]
    assert len(stuck_items) == 1
    item = stuck_items[0]
    assert item.category == AnomalyCategory.SENSOR_PLAUSIBILITY
    assert item.observed_value == 65.0
    assert "SENSOR_FLATLINE_DETECTED" in item.reason_codes


# ---------------------------------------------------------------------------
# 3. THERMAL_DEVIATION Tests & Qualification Gating
# ---------------------------------------------------------------------------

def test_thermal_deviation_shadow_mode_when_unqualified():
    """Verify thermal CUSUM trip under unqualified Tripura state emits shadow evidence."""
    from app.models.scenario import ThermalTrustState
    ev = _build_event()
    th_out = ThermalRuntimeOutput(
        timestamp_utc=ev.event_time_utc,
        trust_state=ThermalTrustState.SHADOW_DESCRIPTIVE,
        top_oil_observed_degc=65.0,
        expected_top_oil_degc=60.0,
        free_running_top_oil_degc=60.0,
        thermal_residual_degc=5.0,
        cusum_pos=5.20,
        cusum_neg=0.0,
        cusum_alarm_active=True,
    )

    qual = ThermalModelQualification(
        parameter_interpretability=QualificationStatus.NOT_QUALIFIED,
        forecast_qualification=QualificationStatus.QUALIFIED,
        scenario_qualification=QualificationStatus.NOT_QUALIFIED,
        residual_display_qualification=QualificationStatus.DESCRIPTIVE_ONLY,
        residual_anomaly_qualification=QualificationStatus.NOT_QUALIFIED,
        cusum_qualification=QualificationStatus.DISABLED,
        maintenance_inference_qualification=QualificationStatus.NOT_QUALIFIED,
    )

    evidence = detect_thermal_deviation(ev, thermal_output=th_out, qualification=qual)
    assert len(evidence) == 1
    item = evidence[0]
    assert item.category == AnomalyCategory.THERMAL_DEVIATION
    assert item.detector_id == "DET_THERMAL_SHADOW_DESCRIPTIVE"
    assert item.severity == 0.30  # Suppressed severity
    assert item.confidence == 0.40
    assert "UNQUALIFIED_SHADOW_EVIDENCE" in item.hypothesis_codes


def test_thermal_deviation_operational_alarm_when_qualified():
    """Verify thermal CUSUM trip under fully qualified state emits full operational evidence."""
    from app.models.scenario import ThermalTrustState
    ev = _build_event()
    th_out = ThermalRuntimeOutput(
        timestamp_utc=ev.event_time_utc,
        trust_state=ThermalTrustState.MODEL_HEALTHY,
        top_oil_observed_degc=75.0,
        expected_top_oil_degc=65.0,
        free_running_top_oil_degc=65.0,
        thermal_residual_degc=10.0,
        cusum_pos=6.50,
        cusum_neg=0.0,
        cusum_alarm_active=True,
    )

    qual = ThermalModelQualification(
        parameter_interpretability=QualificationStatus.QUALIFIED,
        forecast_qualification=QualificationStatus.QUALIFIED,
        scenario_qualification=QualificationStatus.QUALIFIED,
        residual_display_qualification=QualificationStatus.QUALIFIED,
        residual_anomaly_qualification=QualificationStatus.QUALIFIED,
        cusum_qualification=QualificationStatus.QUALIFIED,
        maintenance_inference_qualification=QualificationStatus.QUALIFIED,
    )

    evidence = detect_thermal_deviation(ev, thermal_output=th_out, qualification=qual)
    assert len(evidence) == 1
    item = evidence[0]
    assert item.detector_id == "DET_THERMAL_CUSUM_DRIFT"
    assert item.severity == 0.75
    assert item.confidence == 0.85
    assert "PERSISTENT_THERMAL_RESIDUAL_DRIFT" in item.reason_codes


# ---------------------------------------------------------------------------
# 4. THERMAL_LIMIT Tests
# ---------------------------------------------------------------------------

def test_thermal_limits_absolute_and_rise():
    """Verify direct top-oil and differential temperature limits."""
    q_good = MeasurementQuality(severity=QualitySeverity.GOOD)
    ev = _build_event(
        measurements=[
            Measurement(
                signal_id="oti_degc",
                value=96.0,  # Critical >= 95
                value_type="float",
                unit_ucum="Cel",
                original_name="OTI",
                original_value="96.0",
                original_unit="degC",
                quality=q_good,
            ),
            Measurement(
                signal_id="ambient_temperature",
                value=30.0,  # Rise = 96 - 30 = 66 (Critical >= 65)
                value_type="float",
                unit_ucum="Cel",
                original_name="ATI",
                original_value="30.0",
                original_unit="degC",
                quality=q_good,
            ),
        ]
    )

    evidence = detect_thermal_limits(ev)
    assert len(evidence) == 2

    crit_oti = next(e for e in evidence if e.detector_id == "DET_THERMAL_LIMIT_ABSOLUTE")
    assert crit_oti.category == AnomalyCategory.THERMAL_LIMIT
    assert crit_oti.severity == 0.95
    assert "TOP_OIL_CRITICAL_LIMIT_EXCEEDED" in crit_oti.reason_codes

    crit_rise = next(e for e in evidence if e.detector_id == "DET_THERMAL_LIMIT_RISE")
    assert crit_rise.observed_value == 66.0
    assert crit_rise.severity == 0.90


# ---------------------------------------------------------------------------
# 5. LOADING Tests
# ---------------------------------------------------------------------------

def test_loading_overload():
    """Verify relative load index u >= 1.25 emits critical LOADING evidence."""
    ev = _build_event()
    derived = DerivedFeatures(
        timestamp_utc=ev.event_time_utc,
        relative_load_index=1.30,  # 130% load
        transform_version="1.0.0",
    )

    evidence = detect_loading(ev, derived=derived)
    assert len(evidence) == 1
    item = evidence[0]
    assert item.category == AnomalyCategory.LOADING
    assert item.detector_id == "DET_LOAD_RELATIVE_INDEX"
    assert item.observed_value == 130.0
    assert item.severity == 0.90
    assert "CRITICAL_OVERLOAD_EXCEEDED" in item.reason_codes


# ---------------------------------------------------------------------------
# 6. PHASE_OR_NEUTRAL Tests
# ---------------------------------------------------------------------------

def test_phase_neutral_imbalance_and_neutral():
    """Verify current imbalance and neutral ratio emit PHASE_OR_NEUTRAL evidence."""
    ev = _build_event()
    derived = DerivedFeatures(
        timestamp_utc=ev.event_time_utc,
        current_magnitude_imbalance_pct=28.5,  # >= 25% critical
        neutral_current_ratio=0.55,           # >= 0.50 critical
        transform_version="1.0.0",
    )

    evidence = detect_phase_neutral(ev, derived=derived)
    assert len(evidence) == 2

    iub_item = next(e for e in evidence if e.detector_id == "DET_PHASE_CURRENT_IMBALANCE")
    assert iub_item.category == AnomalyCategory.PHASE_OR_NEUTRAL
    assert iub_item.severity == 0.90

    in_item = next(e for e in evidence if e.detector_id == "DET_NEUTRAL_CURRENT_RATIO")
    assert in_item.category == AnomalyCategory.PHASE_OR_NEUTRAL
    assert in_item.severity == 0.85


# ---------------------------------------------------------------------------
# 7. VOLTAGE_PF_FREQUENCY Tests
# ---------------------------------------------------------------------------

def test_voltage_pf_frequency_limits():
    """Verify voltage imbalance, low power factor, and undervoltage."""
    q_good = MeasurementQuality(severity=QualitySeverity.GOOD)
    ev = _build_event(
        measurements=[
            Measurement(
                signal_id="voltage_v1",
                phase="L1",
                value=195.0,  # Undervoltage < 207 V (0.90 * 230)
                value_type="float",
                unit_ucum="V",
                original_name="VL1",
                original_value="195.0",
                original_unit="V",
                quality=q_good,
            )
        ]
    )
    derived = DerivedFeatures(
        timestamp_utc=ev.event_time_utc,
        voltage_magnitude_imbalance_pct=3.5,  # >= 3.0% critical
        power_factor_derived=0.65,           # <= 0.70 critical
        transform_version="1.0.0",
    )

    evidence = detect_voltage_pf_frequency(ev, derived=derived)
    assert len(evidence) == 3

    vub_item = next(e for e in evidence if e.detector_id == "DET_VOLTAGE_IMBALANCE")
    assert vub_item.category == AnomalyCategory.VOLTAGE_PF_FREQUENCY
    assert vub_item.severity == 0.85

    pf_item = next(e for e in evidence if e.detector_id == "DET_LOW_POWER_FACTOR")
    assert pf_item.severity == 0.80

    sag_item = next(e for e in evidence if e.detector_id == "DET_VOLTAGE_SAG_OR_UNDERVOLTAGE")
    assert sag_item.severity == 0.65


# ---------------------------------------------------------------------------
# 8. PROTECTION_OR_OIL_STATUS Tests
# ---------------------------------------------------------------------------

def test_protection_contacts_and_oil_level():
    """Verify hardware protection trip contacts and low oil level."""
    q_good = MeasurementQuality(severity=QualitySeverity.GOOD)
    ev = _build_event(
        measurements=[
            Measurement(
                signal_id="wti",
                value=1,  # Direct WTI Trip contact
                value_type="int",
                unit_ucum="1",
                original_name="WTI",
                original_value="1",
                original_unit="binary",
                quality=q_good,
            ),
            Measurement(
                signal_id="oil_level_pct",
                value=8.0,  # Critical low oil < 10%
                value_type="float",
                unit_ucum="%",
                original_name="OLI",
                original_value="8.0",
                original_unit="%",
                quality=q_good,
            ),
            Measurement(
                signal_id="mog_a",
                value=1,  # Magnetic Oil Gauge low level contact
                value_type="int",
                unit_ucum="1",
                original_name="MOG_A",
                original_value="1",
                original_unit="binary",
                quality=q_good,
            ),
        ]
    )

    evidence = detect_protection_oil_status(ev)
    assert len(evidence) == 3

    wti_item = next(e for e in evidence if e.detector_id == "DET_PROT_WTI_CONTACT")
    assert wti_item.category == AnomalyCategory.PROTECTION_OR_OIL_STATUS
    assert wti_item.severity == 1.0  # Decisive trip authority
    assert wti_item.confidence == 1.0

    oli_item = next(e for e in evidence if e.detector_id == "DET_OIL_LEVEL_INDICATOR")
    assert oli_item.severity == 0.95

    mog_item = next(e for e in evidence if e.detector_id == "DET_PROT_MOG_ALARM")
    assert mog_item.severity == 0.85


# ---------------------------------------------------------------------------
# 9. Unified MultiDomainAnomalyEngine Integration Tests
# ---------------------------------------------------------------------------

def test_anomaly_engine_clean_event_zero_evidence():
    """Verify nominal event generates zero anomaly evidence."""
    engine = MultiDomainAnomalyEngine(asset_id="TX_01")
    q_good = MeasurementQuality(severity=QualitySeverity.GOOD)
    ev = _build_event(
        measurements=[
            Measurement(signal_id="oti_degc", value=60.0, value_type="float", unit_ucum="Cel", original_name="OTI", original_value="60.0", original_unit="degC", quality=q_good),
            Measurement(signal_id="ambient_temperature", value=30.0, value_type="float", unit_ucum="Cel", original_name="ATI", original_value="30.0", original_unit="degC", quality=q_good),
            Measurement(signal_id="voltage_v1", value=230.0, value_type="float", unit_ucum="V", original_name="VL1", original_value="230.0", original_unit="V", quality=q_good),
            Measurement(signal_id="wti", value=0, value_type="int", unit_ucum="1", original_name="WTI", original_value="0", original_unit="binary", quality=q_good),
        ]
    )
    derived = DerivedFeatures(
        timestamp_utc=ev.event_time_utc,
        relative_load_index=0.70,
        current_magnitude_imbalance_pct=2.0,
        voltage_magnitude_imbalance_pct=0.5,
        power_factor_derived=0.92,
        pqs_inconsistency=0.01,
        transform_version="1.0.0",
    )

    evidence = engine.evaluate_event(ev, derived=derived)
    assert len(evidence) == 0


def test_anomaly_engine_multi_fault_event():
    """Verify multi-domain fault event emits multiple structured evidence items."""
    engine = MultiDomainAnomalyEngine(asset_id="TX_01")
    q_good = MeasurementQuality(severity=QualitySeverity.GOOD)
    ev = _build_event(
        measurements=[
            Measurement(signal_id="oti_degc", value=98.0, value_type="float", unit_ucum="Cel", original_name="OTI", original_value="98.0", original_unit="degC", quality=q_good),
            Measurement(signal_id="ambient_temperature", value=30.0, value_type="float", unit_ucum="Cel", original_name="ATI", original_value="30.0", original_unit="degC", quality=q_good),
            Measurement(signal_id="wti", value=1, value_type="int", unit_ucum="1", original_name="WTI", original_value="1", original_unit="binary", quality=q_good),
        ]
    )
    derived = DerivedFeatures(
        timestamp_utc=ev.event_time_utc,
        relative_load_index=1.35,  # Overload
        current_magnitude_imbalance_pct=30.0,  # Imbalance
        transform_version="1.0.0",
    )

    evidence = engine.evaluate_event(ev, derived=derived)
    categories = {e.category for e in evidence}
    assert AnomalyCategory.THERMAL_LIMIT in categories
    assert AnomalyCategory.PROTECTION_OR_OIL_STATUS in categories
    assert AnomalyCategory.LOADING in categories
    assert AnomalyCategory.PHASE_OR_NEUTRAL in categories


def test_anomaly_engine_asset_mismatch_raises():
    """Verify evaluating an event for the wrong asset raises ValueError."""
    engine = MultiDomainAnomalyEngine(asset_id="TX_01")
    ev = _build_event(asset_id="TX_02")
    with pytest.raises(ValueError, match="Asset mismatch"):
        engine.evaluate_event(ev)


def test_twin_reducer_anomaly_engine_end_to_end():
    """Verify CanonicalEvent -> TwinReducer -> MultiDomainAnomalyEngine -> EvidenceItem integration."""
    from app.engine.reducer import TwinReducer

    anomaly_engine = MultiDomainAnomalyEngine(asset_id="TX_01")
    reducer = TwinReducer(anomaly_engine=anomaly_engine)

    q_good = MeasurementQuality(severity=QualitySeverity.GOOD)
    ev = _build_event(
        asset_id="TX_01",
        measurements=[
            Measurement(signal_id="oti_degc", value=96.0, value_type="float", unit_ucum="Cel", original_name="OTI", original_value="96.0", original_unit="degC", quality=q_good),
            Measurement(signal_id="ambient_temperature", value=30.0, value_type="float", unit_ucum="Cel", original_name="ATI", original_value="30.0", original_unit="degC", quality=q_good),
            Measurement(signal_id="active_power_total", value=50.0, value_type="float", unit_ucum="kW", original_name="P_tot", original_value="50.0", original_unit="kW", quality=q_good),
            Measurement(signal_id="reactive_power_total", value=86.6025, value_type="float", unit_ucum="kvar", original_name="Q_tot", original_value="86.6025", original_unit="kvar", quality=q_good),
            Measurement(signal_id="apparent_power_total", value=100.0, value_type="float", unit_ucum="kVA", original_name="S_tot", original_value="100.0", original_unit="kVA", quality=q_good),
        ],
    )

    state = reducer.reduce(None, ev)
    assert state.asset_id == "TX_01"
    assert len(reducer.latest_emitted_evidence) >= 2
    cats = {e.category for e in reducer.latest_emitted_evidence}
    assert AnomalyCategory.THERMAL_LIMIT in cats
    assert AnomalyCategory.VOLTAGE_PF_FREQUENCY in cats
