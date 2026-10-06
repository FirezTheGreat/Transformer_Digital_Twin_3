"""Focused unit and integration test suite for Phase 5.2 Two-Sided CUSUM Tracker.

Verifies:
1. Standardization (median subtraction, single 1.4826 MAD scaling, 0.50°C floor).
2. Positive and negative drift accumulation and zero-floor clamping.
3. Noise rejection (single isolated spike suppression).
4. Persistent drift detection (eventual crossing of decision limit h).
5. Warm-up, gap reset, bad telemetry, and fallback suppression.
6. Strict capability authority isolation (Tripura shadow exploratory hypothesis vs authoritative fault).
7. Replay determinism and state consistency.
"""

from datetime import datetime, timedelta, timezone
import pytest

from app.engine.cusum import (
    CUSUMConfig,
    CUSUMDirection,
    CUSUMTrustStatus,
    TwoSidedCUSUMTracker,
)
from app.models.anomaly import AnomalyCategory


# ---------------------------------------------------------------------------
# 1. Standardization & Scale Floor Tests
# ---------------------------------------------------------------------------

def test_cusum_standardization_and_scale_floor():
    """Verify median subtraction, single MAD scaling, and 0.50°C resolution floor."""
    # Case A: Normal scale above floor (MAD scale = 0.9613 > 0.50)
    tracker_a = TwoSidedCUSUMTracker(
        calibration_median=0.20,
        calibration_mad=0.9613,
        sensor_resolution_floor=0.50,
    )
    assert tracker_a.scale == 0.9613
    # r = 1.1613 -> z = (1.1613 - 0.20) / 0.9613 = 1.0000
    res_a = tracker_a.update(residual_degc=1.1613)
    assert res_a.standardized_residual_z == 1.0

    # Case B: Scale below resolution floor (MAD scale = 0.10 < 0.50 floor)
    tracker_b = TwoSidedCUSUMTracker(
        calibration_median=0.0,
        calibration_mad=0.10,
        sensor_resolution_floor=0.50,
    )
    assert tracker_b.scale == 0.50  # Enforces 0.50 floor
    # r = 1.00 -> z = (1.00 - 0.0) / 0.50 = 2.0000
    res_b = tracker_b.update(residual_degc=1.00)
    assert res_b.standardized_residual_z == 2.0


# ---------------------------------------------------------------------------
# 2. Positive & Negative Drift Accumulation and Clamping Tests
# ---------------------------------------------------------------------------

def test_positive_drift_accumulation_and_clamping():
    """Verify positive drift accumulates in C+ and clamps at zero when residuals recover."""
    tracker = TwoSidedCUSUMTracker(
        reference_k=0.50,
        decision_limit_h=4.50,
        calibration_median=0.0,
        calibration_mad=1.0,
    )
    # Step 1: z = +1.5 -> C+ = max(0, 0 + 1.5 - 0.5) = 1.0
    r1 = tracker.update(residual_degc=1.5)
    assert r1.cusum_pos == 1.0
    assert r1.cusum_neg == 0.0

    # Step 2: z = +1.5 -> C+ = max(0, 1.0 + 1.5 - 0.5) = 2.0
    r2 = tracker.update(residual_degc=1.5)
    assert r2.cusum_pos == 2.0

    # Step 3: z = -3.0 -> C+ = max(0, 2.0 - 3.0 - 0.5) = 0.0 (zero-floor clamped)
    r3 = tracker.update(residual_degc=-3.0)
    assert r3.cusum_pos == 0.0


def test_negative_drift_accumulation_and_clamping():
    """Verify negative drift accumulates in C- and clamps at zero when residuals recover."""
    tracker = TwoSidedCUSUMTracker(
        reference_k=0.50,
        decision_limit_h=4.50,
        calibration_median=0.0,
        calibration_mad=1.0,
    )
    # Step 1: z = -1.5 -> C- = min(0, 0 - 1.5 + 0.5) = -1.0
    r1 = tracker.update(residual_degc=-1.5)
    assert r1.cusum_neg == -1.0
    assert r1.cusum_pos == 0.0

    # Step 2: z = -1.5 -> C- = min(0, -1.0 - 1.5 + 0.5) = -2.0
    r2 = tracker.update(residual_degc=-1.5)
    assert r2.cusum_neg == -2.0

    # Step 3: z = +3.0 -> C- = min(0, -2.0 + 3.0 + 0.5) = 0.0 (zero-floor clamped)
    r3 = tracker.update(residual_degc=3.0)
    assert r3.cusum_neg == 0.0


# ---------------------------------------------------------------------------
# 3. Noise Rejection vs Persistent Drift
# ---------------------------------------------------------------------------

def test_noise_spike_does_not_trip_cusum():
    """Verify single isolated spike (e.g. z = +3.0) does not trip decision limit h = 4.50."""
    tracker = TwoSidedCUSUMTracker(
        reference_k=0.50,
        decision_limit_h=4.50,
        calibration_median=0.0,
        calibration_mad=1.0,
    )
    # Single spike
    res = tracker.update(residual_degc=3.0)
    assert res.cusum_pos == 2.5  # 3.0 - 0.5 = 2.5 < 4.50
    assert res.alarm_active is False
    assert res.direction == CUSUMDirection.NORMAL

    # Returns to normal (z = 0.0) -> decay: max(0, 2.5 + 0.0 - 0.5) = 2.0
    res2 = tracker.update(residual_degc=0.0)
    assert res2.cusum_pos == 2.0
    assert res2.alarm_active is False


def test_persistent_drift_eventually_crosses_h():
    """Verify sustained 2-sigma drift eventually trips decision limit h = 4.50."""
    tracker = TwoSidedCUSUMTracker(
        reference_k=0.50,
        decision_limit_h=4.50,
        calibration_median=0.0,
        calibration_mad=1.0,
    )
    # 2-sigma residual (z = 2.0). Each step adds z - k = 2.0 - 0.50 = 1.50
    # Step 1: 1.5
    # Step 2: 3.0
    # Step 3: 4.5 -> Trips alarm!
    r1 = tracker.update(residual_degc=2.0)
    assert r1.alarm_active is False
    r2 = tracker.update(residual_degc=2.0)
    assert r2.alarm_active is False
    r3 = tracker.update(residual_degc=2.0)
    assert r3.cusum_pos == 4.5
    assert r3.alarm_active is True
    assert r3.is_positive_alarm is True
    assert r3.direction == CUSUMDirection.POSITIVE_SHIFT


# ---------------------------------------------------------------------------
# 4. Warm-up, Gap Resets, and Fallback Suppression
# ---------------------------------------------------------------------------

def test_warmup_suppresses_cusum_escalation():
    """Verify no accumulation during warm-up phase."""
    tracker = TwoSidedCUSUMTracker(reference_k=0.50, decision_limit_h=4.50)
    res = tracker.update(residual_degc=5.0, is_warmup=True)
    assert res.cusum_pos == 0.0
    assert res.cusum_neg == 0.0
    assert res.alarm_active is False
    assert res.trust_status == CUSUMTrustStatus.WARMUP


def test_gap_resets_accumulators():
    """Verify gap (>1h) resets CUSUM accumulators to zero."""
    tracker = TwoSidedCUSUMTracker(calibration_median=0.0, calibration_mad=1.0)
    tracker.update(residual_degc=2.0)
    tracker.update(residual_degc=2.0)
    assert tracker.cusum_pos == 3.0

    # Next step with is_gap=True
    res = tracker.update(residual_degc=1.0, is_gap=True)
    # Reset to 0 before applying step: 0 + 1.0 - 0.5 = 0.5
    assert res.cusum_pos == 0.5


def test_fallback_and_invalid_inputs_disabled():
    """Verify fallback mode and invalid/None residuals do not escalate."""
    tracker = TwoSidedCUSUMTracker()
    r_fall = tracker.update(residual_degc=5.0, is_fallback=True)
    assert r_fall.alarm_active is False
    assert r_fall.trust_status == CUSUMTrustStatus.FALLBACK

    r_none = tracker.update(residual_degc=None)
    assert r_none.alarm_active is False


# ---------------------------------------------------------------------------
# 5. Qualification & Authority Isolation Tests
# ---------------------------------------------------------------------------

def test_unqualified_cusum_emits_shadow_hypothesis_only():
    """Verify unqualified artifact (Tripura) emits SHADOW hypotheses, NOT confirmed fault alarms."""
    tracker = TwoSidedCUSUMTracker(
        reference_k=0.50,
        decision_limit_h=4.50,
        calibration_median=0.0,
        calibration_mad=1.0,
        is_qualified=False,  # Unqualified Tripura state
    )
    # Trip alarm with large shift
    tracker.update(residual_degc=3.0)
    step_res = tracker.update(residual_degc=3.0)
    assert step_res.alarm_active is True
    assert step_res.trust_status == CUSUMTrustStatus.SHADOW_EXPLORATORY

    t = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    ev = tracker.create_evidence_item(
        event_time_utc=t,
        asset_id="tripura_dt_01",
        observed_top_oil=65.0,
        expected_top_oil=60.0,
        step_result=step_res,
    )
    assert ev is not None
    assert ev.category == AnomalyCategory.THERMAL_DEVIATION
    assert ev.reason_codes == ["PERSISTENT_MODEL_DEVIATION_HYPOTHESIS"]
    assert "MODEL_MISSPECIFICATION_POSSIBLE" in ev.hypothesis_codes

    # Strict: Must NOT declare transformer fault or cooling failure
    for hyp in ev.hypothesis_codes:
        assert "TRANSFORMER_FAULT" not in hyp
        assert "COOLING_FAILURE" not in hyp
        assert "CONFIRMED_ANOMALY" not in hyp


# ---------------------------------------------------------------------------
# 6. Determinism & Replay Tests
# ---------------------------------------------------------------------------

def test_cusum_replay_determinism():
    """Verify identical residual stream produces identical accumulator trajectories."""
    residuals = [0.2, 0.4, 0.8, 1.2, 1.5, 2.0, 1.8, 0.5, -0.2, -0.8, -1.5, -2.0]

    tracker1 = TwoSidedCUSUMTracker(calibration_median=0.20, calibration_mad=0.96)
    tracker2 = TwoSidedCUSUMTracker(calibration_median=0.20, calibration_mad=0.96)

    traj1 = [tracker1.update(r) for r in residuals]
    traj2 = [tracker2.update(r) for r in residuals]

    assert len(traj1) == len(traj2)
    for r1, r2 in zip(traj1, traj2):
        assert r1.cusum_pos == r2.cusum_pos
        assert r1.cusum_neg == r2.cusum_neg
        assert r1.standardized_residual_z == r2.standardized_residual_z
        assert r1.alarm_active == r2.alarm_active
        assert r1.direction == r2.direction


def test_cusum_checkpoint_restore_determinism():
    """Verify Sequence 1->N == (Sequence 1->K, Checkpoint/Restore, Sequence K+1->N)."""
    residuals = [0.3, 0.6, 1.0, 1.4, 1.8, 2.2, 2.0, 0.5, -0.3, -0.9, -1.6, -2.1, 0.0]
    k_split = 6

    # 1. Full continuous sequence A
    tracker_a = TwoSidedCUSUMTracker(
        reference_k=0.50,
        decision_limit_h=4.50,
        calibration_median=0.20,
        calibration_mad=0.96,
        is_qualified=False,
    )
    full_results_a = [tracker_a.update(r) for r in residuals]

    # 2. Split sequence B with checkpoint at k_split
    tracker_b = TwoSidedCUSUMTracker(
        reference_k=0.50,
        decision_limit_h=4.50,
        calibration_median=0.20,
        calibration_mad=0.96,
        is_qualified=False,
    )
    results_b1 = [tracker_b.update(r) for r in residuals[:k_split]]

    # Checkpoint state at k_split
    saved_c_pos = tracker_b.cusum_pos
    saved_c_neg = tracker_b.cusum_neg
    saved_samples = tracker_b.samples_tracked

    # Restore into fresh tracker instance
    tracker_restored = TwoSidedCUSUMTracker(
        reference_k=0.50,
        decision_limit_h=4.50,
        calibration_median=0.20,
        calibration_mad=0.96,
        is_qualified=False,
    )
    tracker_restored.cusum_pos = saved_c_pos
    tracker_restored.cusum_neg = saved_c_neg
    tracker_restored.samples_tracked = saved_samples

    # Continue remaining sequence
    results_b2 = [tracker_restored.update(r) for r in residuals[k_split:]]
    full_results_b = results_b1 + results_b2

    # Assert 100% equivalence
    assert len(full_results_a) == len(full_results_b)
    for ra, rb in zip(full_results_a, full_results_b):
        assert ra.cusum_pos == rb.cusum_pos
        assert ra.cusum_neg == rb.cusum_neg
        assert ra.standardized_residual_z == rb.standardized_residual_z
        assert ra.alarm_active == rb.alarm_active
        assert ra.direction == rb.direction
        assert ra.trust_status == rb.trust_status

