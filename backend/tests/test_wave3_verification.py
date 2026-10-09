"""Wave 3 Verification Suite — Comprehensive tests for Batches 5 & 6 and Wave 2 Gaps.

Covers:
1. Part 1.A: Thermal inversion cadence, elapsed-time persistence, rapid sampling, gaps, and recovery.
2. Part 1.B: Review Flag determinism, feedback replay via reduce_stream_with_feedback, expected-revision checks.
3. Part 2: Thermal exposure conventions (piecewise-linear vs sample-hold), hand-calculated crossings,
          gap-safety, C3/C4 bidirectional independence, discrete WTI isolation, and truthful RUL unavailable state.
4. Part 3: Residual-trigger 5-gate promotion engine, qualification evaluation, and uncertainty metrics.
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.engine.capability import CapabilityEvaluator
from app.engine.exposure import ThermalExposureEngine
from app.engine.reducer import TwinReducer
from app.engine.review import (
    ReviewFlagEngine,
    build_review_id,
    evaluate_residual_trigger_promotion_gate,
)
from app.engine.thermal import ThermalModelParameters
from app.engine.thermal_fallback import (
    ThermalFallbackGate,
    ThermalFallbackReason,
    ThermalTrustState,
)
from app.models.anomaly import AnomalyCategory, EvidenceItem
from app.models.exposure import (
    InsulationProfile,
    ObservedThermalExposure,
    ThermalExposureBundle,
)
from app.models.maintenance import (
    FeedbackAction,
    OperatorFeedbackEvent,
)
from app.models.profile import (
    AssetProfile,
    InsulationClass,
    ProfileVerificationStatus,
)
from app.models.review import (
    ConditionState,
    HumanWorkflowState,
    ObservabilityState,
    ResidualTriggerPolicy,
    ReviewConditionFamily,
    ReviewLifecycleState,
)
from app.models.telemetry import (
    CanonicalEvent,
    Measurement,
    MeasurementQuality,
    QualitySeverity,
    SourceRef,
)
from app.models.thermal_artifact import BaselineMetricEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc(hour: int = 12, minute: int = 0, second: int = 0) -> datetime:
    return datetime(2026, 10, 2, hour, minute, second, tzinfo=timezone.utc)


def _make_meas(
    signal_id: str,
    value: float | int | str | bool,
    unit: str = "Cel",
    severity: QualitySeverity = QualitySeverity.GOOD,
) -> Measurement:
    return Measurement(
        signal_id=signal_id,
        value=value,
        value_type="float" if isinstance(value, float) else "str",
        unit_ucum=unit,
        original_name=signal_id,
        original_value=str(value),
        original_unit=unit,
        quality=MeasurementQuality(severity=severity, flags=[]),
    )


def _make_event(
    event_id: str,
    ts: datetime,
    asset_id: str = "DT-001",
    measurements: list[Measurement] | None = None,
) -> CanonicalEvent:
    return CanonicalEvent(
        schema_version="1.0.0",
        event_id=event_id,
        asset_id=asset_id,
        event_time_utc=ts,
        received_time_utc=None,
        source=SourceRef(
            system="test_system",
            adapter_id="test_v1",
            source_record_id=f"rec_{event_id}",
            source_uri="data/test.csv",
            raw_sha256="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        ),
        event_quality_flags=[],
        measurements=measurements or [],
        mapping_version="test-map-1.0.0",
    )


# ===========================================================================
# 1. Part 1.A: Cadence & Elapsed-Time Aware Thermal Inversion
# ===========================================================================

def test_thermal_inversion_rapid_cadence_does_not_prematurely_fallback() -> None:
    """High-rate observations (e.g. 1-minute) with moderate inversion must NOT trigger fallback before elapsed time threshold."""
    params = ThermalModelParameters(beta_0=1.0, beta_1=2.8, tau_hours=0.5)
    gate = ThermalFallbackGate(
        asset_id="DT-001",
        params=params,
        is_model_promoted=True,
        nominal_cadence_s=900,  # 15 minutes minimum persistence required
    )

    t0 = _utc(12, 0, 0)
    # Step 1 at t0: Ta=35.0, To=23.5 (delta = -11.5 degC)
    out1 = gate.evaluate_step(t0, top_oil_obs=23.5, ambient_obs=35.0, load_obs=100.0)
    assert ThermalFallbackReason.PHYSICAL_IMPOSSIBILITY not in out1.fallback_reasons
    assert out1.trust_state != ThermalTrustState.FALLBACK_PERSISTENCE
    assert any("TOP_OIL_AMBIENT_INVERSION_CONTEXTUAL" in ev.reason_codes for ev in out1.emitted_evidence)

    # Step 2 at t0 + 1 minute: 2nd observation, but elapsed time is only 60s < 900s
    t1 = t0 + timedelta(minutes=1)
    out2 = gate.evaluate_step(t1, top_oil_obs=23.5, ambient_obs=35.0, load_obs=100.0)
    assert ThermalFallbackReason.PHYSICAL_IMPOSSIBILITY not in out2.fallback_reasons
    assert out2.trust_state != ThermalTrustState.FALLBACK_PERSISTENCE
    assert any("TOP_OIL_AMBIENT_INVERSION_CONTEXTUAL" in ev.reason_codes for ev in out2.emitted_evidence)

    # Step 3 at t0 + 15 minutes: elapsed time reaches 900s -> now sustained!
    t2 = t0 + timedelta(minutes=15)
    out3 = gate.evaluate_step(t2, top_oil_obs=23.5, ambient_obs=35.0, load_obs=100.0)
    assert ThermalFallbackReason.PHYSICAL_IMPOSSIBILITY in out3.fallback_reasons
    assert out3.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE
    assert any("SUSTAINED_TOP_OIL_AMBIENT_INVERSION" in ev.reason_codes for ev in out3.emitted_evidence)


def test_extreme_inversion_triggers_immediate_fallback() -> None:
    """Extreme inversion (<= -15 degC delta) immediately triggers PHYSICAL_IMPOSSIBILITY fallback on step 1."""
    params = ThermalModelParameters(beta_0=1.0, beta_1=2.8, tau_hours=0.5)
    gate = ThermalFallbackGate(asset_id="DT-001", params=params, is_model_promoted=True)

    t0 = _utc(12, 0, 0)
    # Ta=40.0, To=24.0 (delta = -16.0 degC <= -15.0 degC)
    out = gate.evaluate_step(t0, top_oil_obs=24.0, ambient_obs=40.0, load_obs=100.0)
    assert ThermalFallbackReason.PHYSICAL_IMPOSSIBILITY in out.fallback_reasons
    assert out.trust_state == ThermalTrustState.FALLBACK_PERSISTENCE


def test_gap_resets_inversion_persistence() -> None:
    """A monitoring gap terminates observation sequence and resets inversion persistence."""
    params = ThermalModelParameters(beta_0=1.0, beta_1=2.8, tau_hours=0.5)
    gate = ThermalFallbackGate(
        asset_id="DT-001",
        params=params,
        is_model_promoted=True,
        max_gap_hours=1.0,
    )

    t0 = _utc(12, 0, 0)
    # Step 1: Inversion delta = -11.5 degC
    gate.evaluate_step(t0, top_oil_obs=23.5, ambient_obs=35.0, load_obs=100.0)
    assert gate.consecutive_inversions == 1

    # 3-hour gap
    t1 = t0 + timedelta(hours=3)
    out_gap = gate.evaluate_step(t1, top_oil_obs=23.5, ambient_obs=35.0, load_obs=100.0)
    assert ThermalFallbackReason.MONITORING_GAP_EXCEEDED in out_gap.fallback_reasons
    # Gap reset should reinitialize inversion tracking
    assert gate.consecutive_inversions == 1  # 1 because t1 was inverted and started fresh after gap reset


# ===========================================================================
# 2. Part 1.B: Deterministic Review Flag & Feedback Replay
# ===========================================================================

def test_reduce_stream_with_feedback_reconstructs_exact_state_deterministically() -> None:
    """Interleaved telemetry and recorded operator feedback reconstruct identical state and hashes."""
    class MockAnomalyEngine:
        def evaluate_event(self, event, derived):
            for m in event.measurements:
                if m.signal_id == "current_imbalance" and float(m.value) > 10.0:
                    return [
                        EvidenceItem(
                            evidence_id=f"ev_{event.event_id}",
                            asset_id=event.asset_id,
                            event_time_utc=event.event_time_utc,
                            category=AnomalyCategory.PHASE_OR_NEUTRAL,
                            detector_id="unbalance_detector",
                            observed_value=float(m.value),
                            expected_value=5.0,
                            direction="HIGH",
                            severity=0.5,
                            confidence=0.8,
                            reason_codes=["UNBALANCE_EXCEEDED"],
                            hypothesis_codes=["LOAD_ASYMMETRY"],
                        )
                    ]
            return []

    reducer1 = TwinReducer(
        anomaly_engine=MockAnomalyEngine(),
        review_engine=ReviewFlagEngine(asset_id="DT-001"),
    )
    reducer2 = TwinReducer(
        anomaly_engine=MockAnomalyEngine(),
        review_engine=ReviewFlagEngine(asset_id="DT-001"),
    )

    t0 = _utc(12, 0, 0)
    t1 = t0 + timedelta(minutes=15)
    t2 = t0 + timedelta(minutes=30)
    t3 = t0 + timedelta(minutes=45)

    # Telemetry events with unbalance triggering advisory evidence
    ev0 = _make_event("ev0", t0, measurements=[
        _make_meas("current_imbalance", 20.0, unit="%"),
        _make_meas("top_oil_temperature", 60.0),
    ])
    ev1 = _make_event("ev1", t1, measurements=[
        _make_meas("current_imbalance", 20.0, unit="%"),
        _make_meas("top_oil_temperature", 60.0),
    ])
    ev2 = _make_event("ev2", t2, measurements=[
        _make_meas("current_imbalance", 20.0, unit="%"),
        _make_meas("top_oil_temperature", 60.0),
    ])
    ev3 = _make_event("ev3", t3, measurements=[
        _make_meas("current_imbalance", 5.0, unit="%"),  # normal
        _make_meas("top_oil_temperature", 60.0),
    ])

    events = [ev0, ev1, ev2, ev3]

    # Operator feedback submitted at t1 + 5 minutes (after ev1, so revision is 2)
    fb_time = t1 + timedelta(minutes=5)
    rev_id = build_review_id("DT-001", ReviewConditionFamily.ELECTRICAL_UNBALANCE_ADVISORY, "electrical_imbalance")
    fb_event = OperatorFeedbackEvent(
        feedback_id="fb_001",
        asset_id="DT-001",
        timestamp_utc=fb_time,
        review_id=rev_id,
        action=FeedbackAction.ACKNOWLEDGE,
        operator_id="operator_alice",
        actor_id="operator_alice",
        expected_revision=2,
        idempotency_key="idemp_key_001",
    )

    state1 = reducer1.reduce_stream_with_feedback(events, [fb_event])
    state2 = reducer2.reduce_stream_with_feedback(events, [fb_event])

    assert state1 is not None and state2 is not None
    assert state1.state_hash == state2.state_hash
    assert len(state1.active_reviews) == 1
    rev = state1.active_reviews[0]
    assert rev.workflow_state == HumanWorkflowState.ACKNOWLEDGED
    # Revision incremented from 2 to 3 by the feedback mutation, and remains acknowledged through ev2 and ev3
    assert rev.revision >= 3
    # Acknowledgement preserves underlying physical condition
    assert rev.condition in (ConditionState.INSUFFICIENT_EVIDENCE, ConditionState.NORMAL)


def test_feedback_expected_revision_conflict_handling() -> None:
    """apply_feedback_mutation rejects stale revision with conflict error."""
    engine = ReviewFlagEngine(asset_id="DT-001")
    t0 = _utc(12, 0, 0)
    ev = EvidenceItem(
        evidence_id="ev_01",
        asset_id="DT-001",
        event_time_utc=t0,
        category=AnomalyCategory.PHASE_OR_NEUTRAL,
        detector_id="unbalance_detector",
        observed_value=20.0,
        expected_value=5.0,
        direction="HIGH",
        severity=0.5,
        confidence=0.8,
        reason_codes=["UNBALANCE_EXCEEDED"],
        hypothesis_codes=["LOAD_ASYMMETRY"],
    )
    reviews = engine.evaluate_step(
        event_time_utc=t0,
        stream_position=1,
        evidence_items=[ev],
        open_episodes=[],
        previous_reviews=[],
    )
    assert len(reviews) == 1
    rec = reviews[0]
    assert rec.revision == 1

    # Attempt mutation with wrong expected revision (e.g. 5 instead of 1)
    with pytest.raises(ValueError, match="expected revision 5, but active revision is 1"):
        engine.apply_feedback_mutation(
            reviews=reviews,
            review_id=rec.review_id,
            action="ACKNOWLEDGE",
            actor_id="op_bob",
            expected_revision=5,
            event_time_utc=t0,
        )


# ===========================================================================
# 3. Part 2: Thermal Exposure Conventions, Gaps, Ageing & Honest RUL
# ===========================================================================

def test_hand_calculated_piecewise_linear_threshold_crossings() -> None:
    """Verify exact hand-calculated integral areas for rising and falling threshold crossings."""
    engine = ThermalExposureEngine(
        asset_id="DT-001",
        max_gap_seconds=7200.0,
        integration_convention="PIECEWISE_LINEAR",
    )

    t0 = _utc(12, 0, 0)
    # Event 0: 70 Cel (below 85)
    engine.step(_make_event("e0", t0, measurements=[_make_meas("top_oil_temperature", 70.0)]))

    # Event 1 (12:30): 80 Cel (still below 85) -> 0 duration, 0 deg-hours
    t1 = t0 + timedelta(minutes=30)
    b1 = engine.step(_make_event("e1", t1, measurements=[_make_meas("top_oil_temperature", 80.0)]))
    assert b1.observed_exposure.bands["T_gt_85C"].duration_seconds == 0.0
    assert b1.observed_exposure.degree_hours_above_85c == 0.0

    # Event 2 (13:00): 90 Cel (crosses 85 Cel at alpha = 0.5)
    # Active duration = (1 - 0.5) * 1800s = 900s = 0.25h
    # Degree-hours = 0.5 * (90 - 85) * 0.25h = 0.625 deg-h
    t2 = t1 + timedelta(minutes=30)
    b2 = engine.step(_make_event("e2", t2, measurements=[_make_meas("top_oil_temperature", 90.0)]))
    assert b2.observed_exposure.bands["T_gt_85C"].duration_seconds == 900.0
    assert b2.observed_exposure.degree_hours_above_85c == pytest.approx(0.625)

    # Event 3 (13:30): 80 Cel (falling crossing from 90 to 80 across 85 Cel at alpha = 0.5)
    # Active duration = 0.5 * 1800s = 900s = 0.25h
    # Degree-hours = 0.5 * (90 - 85) * 0.25h = 0.625 deg-h
    # Total duration = 900 + 900 = 1800s (0.5h). Total deg-h = 0.625 + 0.625 = 1.25 deg-h.
    t3 = t2 + timedelta(minutes=30)
    b3 = engine.step(_make_event("e3", t3, measurements=[_make_meas("top_oil_temperature", 80.0)]))
    assert b3.observed_exposure.bands["T_gt_85C"].duration_seconds == 1800.0
    assert b3.observed_exposure.degree_hours_above_85c == pytest.approx(1.25)


def test_coverage_and_wall_clock_tracking() -> None:
    """Monitored exposure reports wall-clock duration and coverage ratio correctly."""
    engine = ThermalExposureEngine(asset_id="DT-001", max_gap_seconds=1800.0)  # 30-min max gap

    t0 = _utc(12, 0, 0)
    engine.step(_make_event("e0", t0, measurements=[_make_meas("top_oil_temperature", 80.0)]))

    # 15 min later: normal step
    t1 = t0 + timedelta(minutes=15)
    engine.step(_make_event("e1", t1, measurements=[_make_meas("top_oil_temperature", 82.0)]))

    # 2 hours later: gap of 120 minutes (7200s)
    t2 = t1 + timedelta(hours=2)
    b2 = engine.step(_make_event("e2", t2, measurements=[_make_meas("top_oil_temperature", 84.0)]))

    # Total wall clock: 2h 15m = 2.25 hours
    # Monitored: only 15 minutes = 0.25 hours
    obs = b2.observed_exposure
    assert obs.wall_clock_coverage_hours == pytest.approx(2.25)
    assert obs.total_monitored_hours == pytest.approx(0.25)
    assert obs.monitored_coverage_ratio == pytest.approx(0.25 / 2.25, rel=1e-3)


def test_discrete_wti_contact_cannot_feed_continuous_exposure_or_ageing() -> None:
    """Binary WTI contacts are isolated from continuous temperature measurements."""
    engine = ThermalExposureEngine(
        asset_id="DT-001",
        insulation_profile=InsulationProfile.CELLULOSIC_THERMALLY_UPGRADED,
    )
    t0 = _utc(12, 0, 0)
    # Event contains only discrete protection contact alarms
    ev = _make_event("e0", t0, measurements=[
        _make_meas("winding_temp_alarm", True),
        _make_meas("winding_temp_trip", False),
        _make_meas("top_oil_temp_trip", 1.0),
    ])
    bundle = engine.step(ev)
    assert bundle.observed_exposure.valid_sample_count == 0
    assert bundle.observed_exposure.peak_top_oil_temp_c is None
    assert bundle.standards_ageing.is_enabled is False
    assert bundle.standards_ageing.hotspot_source == "UNAVAILABLE"


def test_honest_rul_unavailable_state() -> None:
    """Operational RUL and failure probabilities are explicitly unavailable/not-qualified."""
    engine = ThermalExposureEngine(asset_id="DT-001")
    t0 = _utc(12, 0, 0)
    ev = _make_event("e0", t0, measurements=[_make_meas("top_oil_temperature", 85.0)])
    bundle = engine.step(ev)

    assert bundle.whole_life_rul_supported is False
    assert bundle.failure_probability_supported is False
    assert bundle.rul_status == "NOT_QUALIFIED"
    assert "No validated initial degradation state" in bundle.rul_rationale


# ===========================================================================
# 4. Part 3: Residual-Trigger Promotion Gate & Uncertainty Diagnostics
# ===========================================================================

def test_residual_trigger_promotion_gate_enforces_all_5_criteria() -> None:
    """Candidate residual trigger rule must satisfy all 5 criteria to be qualified."""
    # Candidate lacking sufficient benign CAL asset-days (< 21)
    cand_insufficient_cal = ResidualTriggerPolicy(
        policy_id="res_pol_01",
        policy_version="v1.0",
        benign_cal_asset_days=15.0,  # < 21.0
        unmatched_flags_per_7_asset_days=0.5,
        challenge_cases_passed=True,
        sealed_test_passed=True,
    )
    res_insuf = evaluate_residual_trigger_promotion_gate(cand_insufficient_cal)
    assert res_insuf.is_qualified is False
    assert any("INSUFFICIENT_BENIGN_CAL_DAYS" in r for r in res_insuf.gate_failure_reasons)

    # Candidate with excessive workload budget (> 1 unmatched per 7 asset-days)
    cand_high_budget = ResidualTriggerPolicy(
        policy_id="res_pol_02",
        policy_version="v1.0",
        benign_cal_asset_days=25.0,
        unmatched_flags_per_7_asset_days=1.5,  # > 1.0
        challenge_cases_passed=True,
        sealed_test_passed=True,
    )
    res_budget = evaluate_residual_trigger_promotion_gate(cand_high_budget)
    assert res_budget.is_qualified is False
    assert any("WORKLOAD_BUDGET_EXCEEDED" in r for r in res_budget.gate_failure_reasons)

    # Candidate passing all 5 criteria
    cand_valid = ResidualTriggerPolicy(
        policy_id="res_pol_03",
        policy_version="v1.0",
        benign_cal_asset_days=28.0,
        unmatched_flags_per_7_asset_days=0.25,
        challenge_cases_passed=True,
        sealed_test_passed=True,
    )
    res_valid = evaluate_residual_trigger_promotion_gate(cand_valid)
    assert res_valid.is_qualified is True
    assert len(res_valid.gate_failure_reasons) == 0


def test_review_flag_engine_residual_gating() -> None:
    """ReviewFlagEngine suppresses residual flags when policy is unpromoted, and emits them when qualified."""
    # 1. Unpromoted policy: residual evidence is ignored
    unpromoted_policy = ResidualTriggerPolicy(
        policy_id="res_pol_01",
        policy_version="v1.0",
        is_qualified=False,
    )
    engine_gated = ReviewFlagEngine(asset_id="DT-001", residual_policy=unpromoted_policy)

    t0 = _utc(12, 0, 0)
    ev_residual = EvidenceItem(
        evidence_id="ev_res_01",
        asset_id="DT-001",
        event_time_utc=t0,
        category=AnomalyCategory.THERMAL_DEVIATION,
        detector_id="thermal_residual_detector",
        observed_value=5.0,
        expected_value=0.0,
        direction="HIGH",
        severity=0.7,
        confidence=0.8,
        reason_codes=["THERMAL_RESIDUAL_HIGH"],
        hypothesis_codes=["COOLING_DEGRADATION"],
    )

    reviews_gated = engine_gated.evaluate_step(
        event_time_utc=t0,
        stream_position=1,
        evidence_items=[ev_residual],
        open_episodes=[],
        previous_reviews=[],
    )
    assert len(reviews_gated) == 0  # Suppressed!

    # 2. Qualified policy: residual evidence creates Review Flag
    promoted_policy = ResidualTriggerPolicy(
        policy_id="res_pol_02",
        policy_version="v1.0",
        benign_cal_asset_days=25.0,
        unmatched_flags_per_7_asset_days=0.2,
        challenge_cases_passed=True,
        sealed_test_passed=True,
        is_qualified=True,
    )
    engine_promoted = ReviewFlagEngine(asset_id="DT-001", residual_policy=promoted_policy)
    reviews_promoted = engine_promoted.evaluate_step(
        event_time_utc=t0,
        stream_position=1,
        evidence_items=[ev_residual],
        open_episodes=[],
        previous_reviews=[],
    )
    assert len(reviews_promoted) == 1
    rev = reviews_promoted[0]
    assert rev.condition_family == ReviewConditionFamily.THERMAL_BEHAVIOUR_UNVERIFIED
    assert rev.target == "thermal_residual"


def test_baseline_metric_entry_distinguishes_marginal_and_path_coverage() -> None:
    """BaselineMetricEntry data contract explicitly distinguishes marginal from simultaneous path coverage."""
    entry = BaselineMetricEntry(
        model_name="first_order_greybox",
        mae_degc=1.25,
        rmse_degc=1.65,
        bias_degc=0.15,
        marginal_coverage_90_pct=91.5,
        simultaneous_path_coverage_90_pct=86.2,
        mean_width_degc=5.98,
    )
    assert entry.marginal_coverage_90_pct == 91.5
    assert entry.simultaneous_path_coverage_90_pct == 86.2
    assert entry.marginal_coverage_90_pct != entry.simultaneous_path_coverage_90_pct
