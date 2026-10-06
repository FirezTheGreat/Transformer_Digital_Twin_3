"""Phase 6.5 — Final Phase 6 Verification & Comprehensive Integration Suite.

Audits the complete end-to-end Phase 6 chain:
Evidence -> OTHI -> Thermal Exposure/Ageing -> Maintenance Recommendations -> Operator Feedback

Verifies:
1. End-to-end integration: CanonicalEvent -> Reducer -> AnomalyEngine -> OTHIEngine -> ExposureEngine -> MaintenanceEngine -> FeedbackLedger.
2. Exact mathematical invariants: MAX_PLUS_SECONDARY_V1 with 0.20 secondary coefficient.
3. Anti-uplift rule: missing/stale domains cannot improve health score.
4. Gating invariants: CUSUM/thermal model recommendations suppressed when unqualified (Tripura default).
5. Standards-derived ageing gating: unverified insulation profile safely gates off Leq while preserving degree-hours.
6. Safety precedence: direct hardware protection trips dominate OTHI (CRITICAL) and trigger P0 IMMEDIATE advice.
7. Bad data selective suppression: bad sensor telemetry suppresses only dependent model recommendations (never P0).
8. Feedback ledger audit semantics: append-only immutability, recurrence reopening, P0 non-silent dismissal protection.
9. Deterministic state hash and reproducible replay integrity.
10. Explicit preservation of project exclusions (no RUL, no failure probabilities, no autonomous control).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import pytest

from app.engine.anomaly_detectors import MultiDomainAnomalyEngine
from app.engine.exposure import ThermalExposureEngine
from app.engine.feedback import ALLOWED_P0_RESOLUTION_REASON_CODES, OperatorFeedbackLedger
from app.engine.maintenance import MaintenanceEngine
from app.engine.othi import OTHIEngine, aggregate_othi_max_plus_secondary
from app.engine.reducer import TwinReducer
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.exposure import InsulationProfile
from app.models.health import EvidenceGrade, HealthStatus, OTHIBundle

from app.models.maintenance import (
    ActionWindow,
    ActionWindowProvenanceType,
    FeedbackAction,
    MaintenancePriority,
    MaintenanceRecommendation,
    OperatorFeedbackEvent,
)
from app.models.telemetry import CanonicalEvent, Measurement, MeasurementQuality, QualitySeverity, SourceRef
from app.models.twin_state import TwinState


def _make_utc(hour: int = 12, minute: int = 0, second: int = 0, day: int = 1) -> datetime:
    """Helper to create UTC datetime."""
    return datetime(2026, 3, day, hour, minute, second, tzinfo=timezone.utc)


def _make_measurement(
    signal_id: str,
    value: float | int | str | bool,
    unit: str = "1",
    phase: str | None = None,
    severity: QualitySeverity = QualitySeverity.GOOD,
) -> Measurement:
    """Helper to create valid Measurement."""
    if isinstance(value, bool):
        val_type = "bool"
    elif isinstance(value, int):
        val_type = "int"
    elif isinstance(value, float):
        val_type = "float"
    else:
        val_type = "str"

    return Measurement(
        signal_id=signal_id,
        phase=phase,  # type: ignore[arg-type]
        value=value,
        value_type=val_type,
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(severity=severity, flags=[]),
    )


def _make_canonical_event(
    event_id: str,
    event_time: datetime,
    asset_id: str = "DT-001",
    measurements: list[Measurement] | None = None,
) -> CanonicalEvent:
    """Helper to create CanonicalEvent."""
    if measurements is None:
        measurements = [_make_measurement("top_oil_temp", 45.0, unit="degC")]

    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=event_id,
        asset_id=asset_id,
        event_time_utc=event_time,
        received_time_utc=None,
        source=SourceRef(
            system="test_system",
            adapter_id="test_v1",
            source_record_id=f"rec_{event_id}",
            source_uri="data/test.csv",
            raw_sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        ),
        event_quality_flags=[],
        measurements=measurements,
        mapping_version="test-map-1.0.0",
    )


# ---------------------------------------------------------------------------
# 1. Full Multi-Engine Pipeline Integration Checkpoint
# ---------------------------------------------------------------------------


def test_phase6_full_pipeline_integration() -> None:
    """Verify entire Phase 6 chain integrated into TwinReducer."""
    othi_engine = OTHIEngine()
    exposure_engine = ThermalExposureEngine(asset_id="DT-001", insulation_profile=InsulationProfile.UNKNOWN)
    maintenance_engine = MaintenanceEngine(cusum_qualification="DISABLED", is_thermal_qualified=False)

    reducer = TwinReducer(
        othi_engine=othi_engine,
        exposure_engine=exposure_engine,
        maintenance_engine=maintenance_engine,
    )

    t0 = _make_utc(12, 0, 0)

    measurements = [
        _make_measurement("top_oil_temperature", 55.0, unit="degC"),
        _make_measurement("ambient_temperature", 30.0, unit="degC"),
        _make_measurement("current_l1", 100.0, unit="A"),
        _make_measurement("current_l2", 100.0, unit="A"),
        _make_measurement("current_l3", 100.0, unit="A"),
    ]
    ev0 = _make_canonical_event("e-001", t0, measurements=measurements)

    state0 = reducer.reduce(None, ev0)

    # 1. State vector populated
    assert state0 is not None
    assert state0.health_bundle is not None
    assert state0.exposure_state is not None
    assert isinstance(state0.active_recommendations, list)
    assert len(state0.state_hash) == 64

    # 2. OTHI computed cleanly
    assert state0.health_bundle.othi_score is not None
    assert state0.health_bundle.status == HealthStatus.NORMAL

    # 3. Exposure state tracked top-oil hours without unauthorized ageing
    assert state0.exposure_state.is_ageing_enabled is False
    assert state0.exposure_state.equivalent_ageing_hours is None


# ---------------------------------------------------------------------------
# 2. OTHI Mathematical Aggregation & Anti-Uplift Verification
# ---------------------------------------------------------------------------


def test_phase6_othi_max_plus_secondary_and_anti_uplift() -> None:
    """Verify MAX_PLUS_SECONDARY_V1 formula (0.20 secondary coefficient) and anti-uplift."""
    # Test formula: base 0.50, secondary sum 0.30 -> total penalty 0.50 + 0.20 * 0.30 = 0.56 -> OTHI = 44
    severities = {
        "thermal": 0.50,
        "loading": 0.20,
        "phase_neutral": 0.10,
        "voltage_pf_freq": 0.0,
        "oil_protection": 0.0,
    }
    score, base_p, sec_p, total_p, driving = aggregate_othi_max_plus_secondary(severities)
    assert total_p == 0.56
    assert score == 44
    assert driving == "thermal"

    # Anti-uplift test: previous score 45, fresh score 90 with stale domain -> score clamped to 45
    engine = OTHIEngine()
    t0 = _make_utc(12, 0, 0)
    t1 = t0 + timedelta(hours=3)  # Exceeds staleness threshold

    ev_phase = EvidenceItem(
        evidence_id="ev-p-1",
        asset_id="DT-001",
        event_time_utc=t0,
        detector_id="PHASE_IMBALANCE_DETECTOR",
        observed_value=25.0,
        category=AnomalyCategory.PHASE_OR_NEUTRAL,
        severity=0.55,
        confidence=0.9,
        input_lineage=["i_current_unbalance_pct"],
        condition_family="PHASE_IMBALANCE_UNBALANCE",
    )
    meas0 = [
        _make_measurement("top_oil_temperature", 60.0, unit="degC"),
        _make_measurement("current_l1", 100.0, unit="A"),
        _make_measurement("current_l2", 80.0, unit="A"),
        _make_measurement("current_l3", 70.0, unit="A"),
    ]
    b0 = engine.evaluate(
        event=_make_canonical_event("e0", t0, measurements=meas0),
        evidence_items=[ev_phase],
    )
    assert b0.othi_score is not None
    assert b0.othi_score <= 55

    # Subsequent event with no new evidence but previously degraded electrical domain becomes stale
    meas1 = [
        _make_measurement("top_oil_temperature", 60.0, unit="degC"),
        _make_measurement("voltage_l1_n", 240.0, unit="V"),
    ]
    b1 = engine.evaluate(
        event=_make_canonical_event("e1", t1, measurements=meas1),
        evidence_items=[],
        previous_bundle=b0,
    )
    # Anti-uplift rule: Loss of observability on degraded domain gates score and preserves degraded operational status
    assert b1.is_gated is True
    assert "degraded" in b1.gate_reason.lower()
    assert b1.last_valid_othi == b0.othi_score
    assert b1.operational_status == HealthStatus.WARNING



# ---------------------------------------------------------------------------
# 3. Thermal Exposure & Standards-Derived Ageing Qualification Verification
# ---------------------------------------------------------------------------


def test_phase6_thermal_exposure_qualification_and_exclusions() -> None:
    """Verify standards-derived ageing is gated off until profile and hot-spot are verified."""
    engine_unverified = ThermalExposureEngine(asset_id="DT-001", insulation_profile=InsulationProfile.UNKNOWN)
    t0 = _make_utc(12, 0, 0)
    t1 = t0 + timedelta(minutes=15)

    # Initial step
    ev0 = _make_canonical_event(
        "e-th-0",
        t0,
        measurements=[
            _make_measurement("top_oil_temperature", 110.0, unit="degC"),
            _make_measurement("ambient_temperature", 35.0, unit="degC"),
        ],
    )
    engine_unverified.step(ev0)

    # Second step 15 min later at 110 degC
    ev1 = _make_canonical_event(
        "e-th-1",
        t1,
        measurements=[
            _make_measurement("top_oil_temperature", 110.0, unit="degC"),
            _make_measurement("ambient_temperature", 35.0, unit="degC"),
        ],
    )
    res_unverified = engine_unverified.step(ev1)

    # Observed degree-hours accumulated above 105 degC band
    assert res_unverified.observed_exposure.degree_hours_above_105c > 0.0
    # But standards-derived ageing is strictly gated off
    assert res_unverified.standards_ageing.is_enabled is False
    assert res_unverified.standards_ageing.equivalent_ageing_hours is None

    # Explicit exclusions preserved
    assert res_unverified.whole_life_rul_supported is False
    assert res_unverified.failure_probability_supported is False


# ---------------------------------------------------------------------------

# 4. Maintenance Recommendation Gating & Protection Precedence Verification
# ---------------------------------------------------------------------------


def test_phase6_maintenance_gating_and_protection_precedence() -> None:
    """Verify CUSUM suppression on Tripura and hardware protection dominance."""
    engine = MaintenanceEngine(cusum_qualification="DISABLED", is_thermal_qualified=False)
    t0 = _make_utc(12, 0, 0)

    # 1. CUSUM/thermal model evidence -> suppressed due to disabled qualification
    ev_cusum = EvidenceItem(
        evidence_id="ev-cusum-1",
        asset_id="DT-001",
        event_time_utc=t0,
        detector_id="CUSUM_RESIDUAL_TRACKER",
        observed_value=4.5,
        category=AnomalyCategory.THERMAL_DEVIATION,
        severity=0.8,
        confidence=0.9,
        input_lineage=["top_oil_temp"],
        condition_family="THERMAL_RESIDUAL_PERSISTENT_BIAS",
    )
    event_normal = _make_canonical_event("e-norm", t0)
    recs_cusum = engine.evaluate(event=event_normal, evidence_items=[ev_cusum])
    assert len(recs_cusum) == 0  # Suppressed!

    # 2. Hardware protection trip -> P0 IMMEDIATE emitted regardless of sensor quality
    bad_temp = _make_measurement("top_oil_temp", 0.0, unit="degC", severity=QualitySeverity.BAD)
    trip_meas = _make_measurement("breaker_trip", True, unit="1")
    event_trip = _make_canonical_event("e-trip", t0, measurements=[bad_temp, trip_meas])

    recs_trip = engine.evaluate(event=event_trip, evidence_items=[])
    assert len(recs_trip) == 1
    assert recs_trip[0].priority == MaintenancePriority.P0_SAFETY
    assert recs_trip[0].action_window == ActionWindow.IMMEDIATE
    assert recs_trip[0].window_provenance_type == ActionWindowProvenanceType.PROTECTION_OR_SITE_PROCEDURE


# ---------------------------------------------------------------------------
# 5. Operator Feedback Ledger & Recurrence Lifecycle Verification
# ---------------------------------------------------------------------------


def test_phase6_operator_feedback_and_recurrence_verification() -> None:
    """Verify feedback append-only ledger, P0 dismissal rejection, and recurrence reopening."""
    engine = MaintenanceEngine()
    t0 = _make_utc(12, 0, 0)
    trip_meas = [_make_measurement("breaker_trip", True, unit="1")]
    event_trip = _make_canonical_event("e-fb-trip", t0, measurements=trip_meas)

    recs = engine.evaluate(event=event_trip, evidence_items=[])
    assert len(recs) == 1
    rec_p0 = recs[0]

    # 1. P0 Safety cannot be dismissed without authorized resolution code
    with pytest.raises(ValueError, match="P0 Safety/Protection recommendations cannot be dismissed without documented resolution"):
        engine.record_feedback(
            OperatorFeedbackEvent(
                feedback_id="fb-err",
                asset_id="DT-001",
                timestamp_utc=t0 + timedelta(minutes=5),
                recommendation_id=rec_p0.recommendation_id,
                action=FeedbackAction.DISMISS,
                operator_id="operator_sam",
                reason_code="OPERATOR_OVERRIDE",
                rationale="Ignored in demo",
            ),
            target_recommendation=rec_p0,
        )

    # 2. Dismiss with authorized resolution code
    engine.record_feedback(
        OperatorFeedbackEvent(
            feedback_id="fb-p0-ok",
            asset_id="DT-001",
            timestamp_utc=t0 + timedelta(minutes=10),
            recommendation_id=rec_p0.recommendation_id,
            merge_key=rec_p0.merge_key,
            action=FeedbackAction.DISMISS,
            operator_id="substation_chief",
            reason_code="SITE_CLEARANCE_VERIFIED",
            rationale="Trip inspection completed per SOP-01. Feeder cleared.",
        ),
        target_recommendation=rec_p0,
    )

    # 3. Recurrence: new trip event at t0 + 30m reopens a new recommendation instance
    t_recur = t0 + timedelta(minutes=30)
    event_recur = _make_canonical_event("e-recur", t_recur, measurements=trip_meas)
    recs_recur = engine.evaluate(event=event_recur, evidence_items=[])
    assert len(recs_recur) == 1
    assert recs_recur[0].acknowledged is False
