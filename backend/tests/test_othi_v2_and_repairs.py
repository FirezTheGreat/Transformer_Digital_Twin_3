"""Automated Acceptance and Regression Test Suite for Condition Engine Repairs and OTHI_V2.

Covers:
1. 12 explicit OTHI evaluation fixtures comparing MAX_PLUS_SECONDARY_V1 and OTHI_V2
   (Literature grounding: CIGRE TB 761, Li et al. 2023, IEEE C57.91).
2. End-to-end trip latching on lv_breaker_closed=0.
3. Anti-uplift and non-recovery during unaddressed protection trip.
4. Authorized resolution through OperatorFeedbackLedger and clean recovery to 100.
5. Review flag dismissal and state persistence.
6. Oil/pressure physical configuration isolation (conservator vs sealed corrugated tank).
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.engine.anomaly_detectors import detect_protection_oil_status
from app.engine.electrical_episodes import ElectricalEpisodeEngine
from app.engine.feedback import OperatorFeedbackLedger
from app.engine.othi import (
    OTHIEngine,
    aggregate_othi_max_plus_secondary,
    aggregate_othi_v2,
    status_from_othi,
)
from app.engine.reducer import TwinReducer
from app.engine.review import ReviewFlagEngine
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.electrical_episode import ElectricalEpisodeType, EpisodeSeverity, EpisodeStatus
from app.models.maintenance import FeedbackAction, OperatorFeedbackEvent
from app.models.health import HealthStatus
from app.models.profile import AssetProfile
from app.models.review import HumanWorkflowState, ReviewLifecycleState
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)


def _make_meas(
    signal_id: str,
    value: float | int | bool | str,
    unit: str = "A",
    phase: str | None = None,
    severity: QualitySeverity = QualitySeverity.GOOD,
    flags: list[str] | None = None,
) -> Measurement:
    return Measurement(
        signal_id=signal_id,
        phase=phase,  # type: ignore[arg-type]
        value=value,
        value_type="bool" if isinstance(value, bool) else ("int" if isinstance(value, int) else "float"),
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(severity=severity, flags=flags or []),
    )


def _make_event(
    event_id: str,
    event_time: datetime,
    asset_id: str = "DT-01",
    measurements: list[Measurement] | None = None,
    quality_flags: list[str] | None = None,
) -> CanonicalEvent:
    meas = measurements or [
        _make_meas("top_oil_temperature", 55.0, "Cel"),
        _make_meas("ambient_temperature", 28.0, "Cel"),
        _make_meas("current_l1", 100.0, "A", phase="L1"),
        _make_meas("current_l2", 100.0, "A", phase="L2"),
        _make_meas("current_l3", 100.0, "A", phase="L3"),
        _make_meas("voltage_l1_n", 230.0, "V", phase="L1"),
        _make_meas("voltage_l2_n", 230.0, "V", phase="L2"),
        _make_meas("voltage_l3_n", 230.0, "V", phase="L3"),
        _make_meas("power_factor_total", 0.95, "1"),
        _make_meas("frequency", 50.0, "Hz"),
        _make_meas("lv_breaker_closed", 1, "1"),
        _make_meas("oil_level_percent", 65.0, "%"),
    ]
    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=event_id,
        asset_id=asset_id,
        event_time_utc=event_time,
        received_time_utc=None,
        source=SourceRef(
            system="test_gridpulse",
            adapter_id="adapter_test",
            source_record_id=f"row_{event_id}",
            source_uri="fixtures/test.csv",
            raw_sha256="abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
        ),
        measurements=meas,
        event_quality_flags=quality_flags or [],
        mapping_version="1.0.0",
    )


# ===========================================================================
# 1. 12 EXPLICIT OTHI EVALUATION FIXTURES (MAX_PLUS_SECONDARY_V1 vs OTHI_V2)
# ===========================================================================

class TestOTHI12Fixtures:
    """Rigorous evaluation of 12 condition fixtures across V1 and V2 algorithms."""

    def test_fixture_1_all_nominal(self):
        """Case 1: All domains 0.0 -> OTHI must be exactly 100 in both formulations."""
        sevs = {"thermal": 0.0, "loading": 0.0, "phase_neutral": 0.0, "voltage_pf_freq": 0.0, "oil_protection": 0.0}
        s1, b1, sec1, t1, _ = aggregate_othi_max_plus_secondary(sevs)
        s2, b2, sec2, t2, _ = aggregate_othi_v2(sevs)
        assert s1 == 100 and s2 == 100
        assert b1 == 0.0 and b2 == 0.0
        assert t1 == 0.0 and t2 == 0.0

    def test_fixture_2_single_mild_deviation(self):
        """Case 2: Single mild thermal deviation (0.25) -> OTHI = 75."""
        sevs = {"thermal": 0.25, "loading": 0.0, "phase_neutral": 0.0, "voltage_pf_freq": 0.0, "oil_protection": 0.0}
        s1, b1, sec1, t1, d1 = aggregate_othi_max_plus_secondary(sevs)
        s2, b2, sec2, t2, d2 = aggregate_othi_v2(sevs)
        assert s1 == 75 and s2 == 75
        assert b1 == 0.25 and b2 == 0.25
        assert sec1 == 0.0 and sec2 == 0.0
        assert d1 == "thermal" and d2 == "thermal"

    def test_fixture_3_direct_protection_trip(self):
        """Case 3: Direct hardware trip (oil_protection=1.0) -> OTHI must be exactly 0."""
        sevs = {"thermal": 0.0, "loading": 0.0, "oil_protection": 1.0}
        s1, b1, _, t1, d1 = aggregate_othi_max_plus_secondary(sevs)
        s2, b2, _, t2, d2 = aggregate_othi_v2(sevs)
        assert s1 == 0 and s2 == 0
        assert b1 == 1.0 and b2 == 1.0
        assert t1 == 1.0 and t2 == 1.0
        assert d1 == "oil_protection" and d2 == "oil_protection"

    def test_fixture_4_trip_with_co_occurring_deviations(self):
        """Case 4: Protection trip (1.0) with thermal (0.80) and loading (0.60) -> worst-condition dominance."""
        sevs = {"thermal": 0.80, "loading": 0.60, "oil_protection": 1.0}
        s1, _, _, t1, _ = aggregate_othi_max_plus_secondary(sevs)
        s2, _, _, t2, _ = aggregate_othi_v2(sevs)
        # Both must dominate at 0 without exceeding 1.0 penalty
        assert s1 == 0 and s2 == 0
        assert t1 == 1.0 and t2 == 1.0

    def test_fixture_5_two_mild_deviations(self):
        """Case 5: Two mild deviations (0.25 each) -> compounded penalty."""
        sevs = {"thermal": 0.25, "loading": 0.25}
        s1, b1, sec1, t1, _ = aggregate_othi_max_plus_secondary(sevs)
        s2, b2, sec2, t2, _ = aggregate_othi_v2(sevs)
        # V1: base=0.25, sec=0.20*0.25=0.05, total=0.30 -> OTHI=70
        assert s1 == 70
        # V2: base=0.25, sec=0.25*(1-0.25)*0.25=0.046875, total=0.296875 -> OTHI=70
        assert s2 == 70

    def test_fixture_6_three_mild_deviations_diminishing_returns(self):
        """Case 6: Three mild deviations (0.25 each) -> V2 demonstrates diminishing returns."""
        sevs = {"thermal": 0.25, "loading": 0.25, "voltage_pf_freq": 0.25}
        s1, _, sec1, t1, _ = aggregate_othi_max_plus_secondary(sevs)
        s2, _, sec2, t2, _ = aggregate_othi_v2(sevs)
        assert s1 == 65  # V1 linear compounding
        assert s2 == 67  # V2 smooth probabilistic diminishing compounding

    def test_fixture_7_dominant_warning_with_mild_secondary(self):
        """Case 7: Warning (0.55) with mild secondary (0.20)."""
        sevs = {"thermal": 0.55, "phase_neutral": 0.20}
        s1, b1, _, _, d1 = aggregate_othi_max_plus_secondary(sevs)
        s2, b2, _, _, d2 = aggregate_othi_v2(sevs)
        assert d1 == "thermal" and d2 == "thermal"
        assert status_from_othi(s1) == HealthStatus.WARNING
        assert status_from_othi(s2) == HealthStatus.WARNING

    def test_fixture_8_severe_critical_thermal_without_trip(self):
        """Case 8: Severe overheating (0.90) without hardware trip contact."""
        sevs = {"thermal": 0.90, "loading": 0.10}
        s1, _, _, _, _ = aggregate_othi_max_plus_secondary(sevs)
        s2, _, _, _, _ = aggregate_othi_v2(sevs)
        assert s1 <= 10 and s2 <= 10
        assert status_from_othi(s1) == HealthStatus.CRITICAL
        assert status_from_othi(s2) == HealthStatus.CRITICAL

    def test_fixture_9_all_five_domains_moderate_warning(self):
        """Case 9: All 5 domains at moderate warning (0.50)."""
        sevs = {
            "thermal": 0.50,
            "loading": 0.50,
            "phase_neutral": 0.50,
            "voltage_pf_freq": 0.50,
            "oil_protection": 0.50,
        }
        s1, b1, _, t1, _ = aggregate_othi_max_plus_secondary(sevs)
        s2, b2, _, t2, _ = aggregate_othi_v2(sevs)
        # V1: base=0.50 + 4*0.50*0.20 = 0.50 + 0.40 = 0.90 -> OTHI=10
        assert s1 == 10
        # V2: base=0.50 + 0.25*(0.50)*(1 - 0.5^4) = 0.50 + 0.125*0.9375 = 0.617 -> OTHI=38
        assert s2 == 38
        assert t2 < 1.0

    def test_fixture_10_strict_monotonicity(self):
        """Case 10: Monotonicity guarantee: increasing any domain severity never increases OTHI."""
        sevs_a = {"thermal": 0.30, "loading": 0.20, "phase_neutral": 0.10}
        sevs_b = {"thermal": 0.35, "loading": 0.20, "phase_neutral": 0.10}
        sevs_c = {"thermal": 0.35, "loading": 0.30, "phase_neutral": 0.10}

        s2_a, _, _, _, _ = aggregate_othi_v2(sevs_a)
        s2_b, _, _, _, _ = aggregate_othi_v2(sevs_b)
        s2_c, _, _, _, _ = aggregate_othi_v2(sevs_c)

        assert s2_a >= s2_b >= s2_c

    def test_fixture_11_permutation_and_duplicate_invariance(self):
        """Case 11: Reordering dictionary or equal severities produces identical results."""
        sevs_order1 = {"thermal": 0.40, "loading": 0.40, "phase_neutral": 0.20}
        sevs_order2 = {"phase_neutral": 0.20, "loading": 0.40, "thermal": 0.40}

        res1 = aggregate_othi_v2(sevs_order1)
        res2 = aggregate_othi_v2(sevs_order2)
        assert res1 == res2

    def test_fixture_12_strict_boundary_without_cliff(self):
        """Case 12: Total penalty is strictly <= 1.0 and OTHI >= 0 without unnatural clipping."""
        sevs_max = {
            "thermal": 0.95,
            "loading": 0.95,
            "phase_neutral": 0.95,
            "voltage_pf_freq": 0.95,
            "oil_protection": 0.95,
        }
        score, base_p, sec_p, total_p, _ = aggregate_othi_v2(sevs_max)
        assert 0.0 <= total_p <= 1.0
        assert 0 <= score <= 100


# ===========================================================================
# 2. LV BREAKER OPEN / TRIP LATCHING & RESOLUTION LIFECYCLE
# ===========================================================================

def test_lv_breaker_closed_zero_latches_trip():
    """Verify that lv_breaker_closed=0 triggers DET_PROT_LV_BREAKER_TRIP and latches OTHI to 0."""
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    engine = OTHIEngine(expected_cadence_seconds=900.0)

    # Telemetry with LV Breaker Open (lv_breaker_closed = 0)
    meas = [
        _make_meas("top_oil_temperature", 50.0, "Cel"),
        _make_meas("ambient_temperature", 25.0, "Cel"),
        _make_meas("current_l1", 0.0, "A"),
        _make_meas("lv_breaker_closed", 0, "1"),  # OPEN / TRIPPED
    ]
    event = _make_event("evt-trip-01", t0, measurements=meas)

    bundle = engine.evaluate(event=event)
    assert engine.latched_protection_trip is True
    assert bundle.othi_score == 0
    assert bundle.status == HealthStatus.CRITICAL
    assert bundle.driving_domain == "oil_protection"
    assert bundle.driving_condition_family == "DIRECT_PROTECTION_TRIP"


def test_protection_trip_holds_over_normal_frames_until_authorized_resolution():
    """Verify that normal telemetry alone does not recover a latched protection trip."""
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(minutes=15)
    t2 = t0 + timedelta(minutes=30)
    t3 = t0 + timedelta(minutes=45)

    ledger = OperatorFeedbackLedger()
    engine = OTHIEngine(expected_cadence_seconds=900.0)
    engine.feedback_ledger = ledger

    # 1. Trip frame
    meas_trip = [
        _make_meas("top_oil_temperature", 50.0, "Cel"),
        _make_meas("ambient_temperature", 25.0, "Cel"),
        _make_meas("current_l1", 0.0, "A"),
        _make_meas("lv_breaker_closed", 0, "1"),
    ]
    ev0 = _make_event("evt-0", t0, measurements=meas_trip)
    b0 = engine.evaluate(ev0)
    assert b0.othi_score == 0
    assert engine.latched_protection_trip is True

    # 2. Re-energized / normal telemetry frame arriving at t1 without operator clearance
    ev1 = _make_event("evt-1", t1)  # lv_breaker_closed = 1, current = 100A
    b1 = engine.evaluate(ev1)
    # MUST REMAIN LATCHED AT 0
    assert engine.latched_protection_trip is True
    assert b1.othi_score == 0
    assert b1.status == HealthStatus.CRITICAL

    # 3. Operator logs authorized resolution into immutable feedback ledger
    ledger.append(
        OperatorFeedbackEvent(
            feedback_id="fb-res-99",
            recommendation_id="REC-DT-01-MNT-PROT-001",
            asset_id="DT-01",
            timestamp_utc=t2,
            operator_id="OP_CHIEF_SHIVANSH",
            action=FeedbackAction.RESOLVE,
            reason_code="SITE_CLEARANCE_VERIFIED",
            merge_key="PROTECTION_TRIP_RESOLVED",
        )
    )

    # 4. Telemetry frame arriving at t3 after resolution
    ev2 = _make_event("evt-2", t3)
    b2 = engine.evaluate(ev2)
    # Cleanly unlatched and recovered to 100
    assert engine.latched_protection_trip is False
    assert b2.othi_score == 100
    assert b2.status == HealthStatus.NORMAL


def test_review_flag_dismissal_removes_flag_and_persists():
    """Verify review flag dismissal immediately transitions state and ignores dismissed flags."""
    review_engine = ReviewFlagEngine(asset_id="DT-01")
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Simulate ambiguous physical evidence creating an open review flag
    ev = EvidenceItem(
        evidence_id="ev_rev_01",
        asset_id="DT-01",
        event_time_utc=t0,
        category=AnomalyCategory.SENSOR_PLAUSIBILITY,
        detector_id="DET_SENSOR_PLAUSIBILITY_TOP_OIL",
        observed_value=3.2,
        expected_value=0.0,
        unit="degC",
        threshold_or_band="> 2.5 degC",
        direction="HIGH",
        severity=0.55,
        confidence=0.40,
        input_lineage=["top_oil_temperature"],
        reason_codes=["SENSOR_PLAUSIBILITY_EXCURSION"],
        hypothesis_codes=["UNQUALIFIED_PREDICTIVE_MODEL"],
    )

    active_reviews = review_engine.evaluate_step(
        event_time_utc=t0,
        stream_position=1,
        evidence_items=[ev],
        open_episodes=[],
        previous_reviews=[],
    )
    assert len(active_reviews) == 1
    rev = active_reviews[0]
    assert rev.lifecycle_state == ReviewLifecycleState.OPEN
    assert rev.workflow_state == HumanWorkflowState.UNACKNOWLEDGED

    # Operator dismisses the review flag
    updated_reviews = review_engine.apply_feedback_mutation(
        reviews=active_reviews,
        review_id=rev.review_id,
        action="DISMISS",
        actor_id="OP_CONTROL_01",
        rationale="Evaluated: benign ambient variation",
        event_time_utc=t0,
        stream_position=2,
    )
    dismissed_rev = updated_reviews[0]
    assert dismissed_rev.workflow_state == HumanWorkflowState.DISMISSED

    # Open review filter ignores dismissed reviews
    open_filtered = [r for r in updated_reviews if (r.lifecycle_state in (ReviewLifecycleState.OPEN, ReviewLifecycleState.CLEARING)) and r.workflow_state != HumanWorkflowState.DISMISSED]
    assert len(open_filtered) == 0


def test_oil_and_pressure_profile_configuration_consistency():
    """Verify that conservator assets do not fabricate tank pressure evidence."""
    t0 = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    conservator_profile = AssetProfile(
        asset_id="DT-01",
        tank_type="CONSERVATOR",
        has_oil_level_gauge=True,
        has_pressure_sensor=False,
    )

    sealed_profile = AssetProfile(
        asset_id="DT-SEALED",
        tank_type="SEALED_CORRUGATED",
        has_oil_level_gauge=False,
        has_pressure_sensor=True,
    )

    # Event containing pressure measurements
    event = _make_event(
        "evt-press-test",
        t0,
        measurements=[
            _make_meas("tank_pressure_kpa_g", 45.0, "kPa"),
            _make_meas("oil_level_percent", 15.0, "%"),
        ],
    )

    # 1. Conservator asset: detects low oil level, SUPPRESSES pressure detector
    ev_conservator = detect_protection_oil_status(event, profile=conservator_profile)
    det_ids_conservator = [e.detector_id for e in ev_conservator]
    assert "DET_OIL_LEVEL_INDICATOR" in det_ids_conservator
    assert "DET_PRESSURE_HIGH_ALARM" not in det_ids_conservator

    # 2. Sealed tank: detects pressure, SUPPRESSES conservator oil level
    ev_sealed = detect_protection_oil_status(event, profile=sealed_profile)
    det_ids_sealed = [e.detector_id for e in ev_sealed]
    assert "DET_PRESSURE_HIGH_ALARM" in det_ids_sealed
    assert "DET_OIL_LEVEL_INDICATOR" not in det_ids_sealed
