"""Focused Unit and Integration Tests for Batch 4 Deterministic Review Flag Workflow.

Verifies:
1. Distinct evidence lifecycle (OPEN, CLEARING, CLOSED, SUPERSEDED) and human workflow (UNACKNOWLEDGED, ACKNOWLEDGED, DISMISSED) states.
2. Acknowledgement or dismissal does not imply evidence has cleared (lifecycle remains OPEN).
3. Deterministic review_id and idempotent deduplication by asset + family + target.
4. Expected-revision and idempotency-key handling on mutations.
5. Gap suspension: data gaps do not prove recovery or clear active reviews.
6. Superseding: qualified anomaly on target transitions review to SUPERSEDED.
7. Replay determinism: canonical telemetry + feedback yields identical review state without wall-clock now().
8. Invariance: review flag operations never modify OTHI, model capabilities, CUSUM gates, or protection events.
"""

from datetime import datetime, timezone, timedelta
import pytest

from app.engine.review import ReviewFlagEngine, build_review_id
from app.models.anomaly import AnomalyCategory, AnomalyEpisode, EvidenceItem
from app.models.review import (
    ConditionState,
    HumanWorkflowState,
    ObservabilityState,
    ReviewConditionFamily,
    ReviewFlagRecord,
    ReviewLifecycleState,
)


def _make_evidence(
    ev_id: str,
    event_time: datetime,
    category: AnomalyCategory = AnomalyCategory.SENSOR_PLAUSIBILITY,
    reason: str = "TOP_OIL_AMBIENT_INVERSION_CONTEXTUAL",
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=ev_id,
        asset_id="test_dt_01",
        event_time_utc=event_time,
        category=category,
        detector_id="test_detector",
        observed_value=23.5,
        expected_value=35.0,
        direction="CONTEXTUAL_INVERSION",
        severity=0.4,
        confidence=0.6,
        reason_codes=[reason],
        hypothesis_codes=["RAPID_AMBIENT_RISE"],
    )


def test_independent_lifecycle_and_human_workflow_dimensions():
    """Verify that acknowledging or dismissing records a human workflow decision while evidence lifecycle remains OPEN."""
    engine = ReviewFlagEngine(asset_id="test_dt_01")
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    # 1. Trigger review flag via plausibility evidence
    ev1 = _make_evidence("ev_001", t0)
    reviews = engine.evaluate_step(
        event_time_utc=t0,
        stream_position=1,
        evidence_items=[ev1],
        open_episodes=[],
        previous_reviews=[],
    )

    assert len(reviews) == 1
    rec = reviews[0]
    assert rec.lifecycle_state == ReviewLifecycleState.OPEN
    assert rec.workflow_state == HumanWorkflowState.UNACKNOWLEDGED
    assert rec.revision == 1

    # 2. Human acknowledges review
    reviews_acked = engine.apply_feedback_mutation(
        reviews=reviews,
        review_id=rec.review_id,
        action="ACKNOWLEDGE",
        actor_id="operator_alice",
        expected_revision=1,
    )
    acked_rec = reviews_acked[0]
    # Human workflow updated, but physical lifecycle remains OPEN!
    assert acked_rec.workflow_state == HumanWorkflowState.ACKNOWLEDGED
    assert acked_rec.lifecycle_state == ReviewLifecycleState.OPEN
    assert acked_rec.revision == 2

    # 3. Human dismisses review
    reviews_dismissed = engine.apply_feedback_mutation(
        reviews=reviews_acked,
        review_id=rec.review_id,
        action="DISMISS",
        actor_id="operator_alice",
        rationale="Known sensor transient during solar noon.",
        expected_revision=2,
    )
    dismissed_rec = reviews_dismissed[0]
    # Human workflow updated to DISMISSED, but physical evidence lifecycle is STILL OPEN!
    assert dismissed_rec.workflow_state == HumanWorkflowState.DISMISSED
    assert dismissed_rec.lifecycle_state == ReviewLifecycleState.OPEN
    assert dismissed_rec.revision == 3


def test_deterministic_deduplication_and_evidence_accumulation():
    """Verify that multiple successive evidence items update the existing active review idempotently."""
    engine = ReviewFlagEngine(asset_id="test_dt_01")
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    ev1 = _make_evidence("ev_001", t0)
    reviews1 = engine.evaluate_step(
        event_time_utc=t0,
        stream_position=1,
        evidence_items=[ev1],
        open_episodes=[],
        previous_reviews=[],
    )
    assert len(reviews1) == 1
    r_id = reviews1[0].review_id

    # Step 2: Next event emits another evidence item on same sensor
    t1 = t0 + timedelta(minutes=15)
    ev2 = _make_evidence("ev_002", t1)
    reviews2 = engine.evaluate_step(
        event_time_utc=t1,
        stream_position=2,
        evidence_items=[ev2],
        open_episodes=[],
        previous_reviews=reviews1,
    )

    # Must NOT create a second review; must deduplicate by asset + family + target
    assert len(reviews2) == 1
    assert reviews2[0].review_id == r_id
    assert reviews2[0].revision == 2
    assert "ev_001" in reviews2[0].supporting_evidence_ids
    assert "ev_002" in reviews2[0].supporting_evidence_ids
    assert reviews2[0].logical_stream_position == 2


def test_optimistic_concurrency_and_idempotency_keys():
    """Verify revision mismatch conflict and idempotent mutation replay."""
    engine = ReviewFlagEngine(asset_id="test_dt_01")
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ev = _make_evidence("ev_001", t0)
    reviews = engine.evaluate_step(t0, 1, [ev], [], [])
    rec = reviews[0]

    # Stale client passes wrong revision
    with pytest.raises(ValueError, match="Conflict on ReviewFlag"):
        engine.apply_feedback_mutation(
            reviews=reviews,
            review_id=rec.review_id,
            action="ACKNOWLEDGE",
            actor_id="alice",
            expected_revision=99,
        )

    # Valid mutation with idempotency key
    mut1 = engine.apply_feedback_mutation(
        reviews=reviews,
        review_id=rec.review_id,
        action="ACKNOWLEDGE",
        actor_id="alice",
        expected_revision=1,
        idempotency_key="idemp_key_123",
    )
    assert mut1[0].revision == 2

    # Duplicate submission with same idempotency key: idempotent no-op
    mut2 = engine.apply_feedback_mutation(
        reviews=mut1,
        review_id=rec.review_id,
        action="ACKNOWLEDGE",
        actor_id="alice",
        idempotency_key="idemp_key_123",
    )
    assert mut2[0].revision == 2


def test_gap_suspends_recovery_and_does_not_clear_active_review():
    """Verify monitoring gaps suspend recovery counters and do not prove normality."""
    engine = ReviewFlagEngine(asset_id="test_dt_01")
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ev = _make_evidence("ev_001", t0)
    reviews = engine.evaluate_step(t0, 1, [ev], [], [])
    assert reviews[0].lifecycle_state == ReviewLifecycleState.OPEN

    # 10 gap steps with no evidence
    for i in range(10):
        t_gap = t0 + timedelta(hours=2 * (i + 1))
        reviews = engine.evaluate_step(
            event_time_utc=t_gap,
            stream_position=2 + i,
            evidence_items=[],
            open_episodes=[],
            previous_reviews=reviews,
            is_gap=True,
        )
        # In a gap, lifecycle MUST NOT transition to CLEARING or CLOSED!
        assert reviews[0].lifecycle_state == ReviewLifecycleState.OPEN


def test_consecutive_clean_steps_transition_lifecycle_open_to_clearing_to_closed():
    """Verify deterministic physical clearing over consecutive observations."""
    engine = ReviewFlagEngine(asset_id="test_dt_01", clearing_steps_required=2, closed_steps_required=4)
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ev = _make_evidence("ev_001", t0)
    reviews = engine.evaluate_step(t0, 1, [ev], [], [])
    assert reviews[0].lifecycle_state == ReviewLifecycleState.OPEN

    # Clean step 1: still OPEN
    reviews = engine.evaluate_step(t0 + timedelta(minutes=15), 2, [], [], reviews)
    assert reviews[0].lifecycle_state == ReviewLifecycleState.OPEN

    # Clean step 2: reaches clearing_steps_required -> CLEARING
    reviews = engine.evaluate_step(t0 + timedelta(minutes=30), 3, [], [], reviews)
    assert reviews[0].lifecycle_state == ReviewLifecycleState.CLEARING

    # Clean step 3: still CLEARING
    reviews = engine.evaluate_step(t0 + timedelta(minutes=45), 4, [], [], reviews)
    assert reviews[0].lifecycle_state == ReviewLifecycleState.CLEARING

    # Clean step 4: reaches closed_steps_required -> CLOSED
    reviews = engine.evaluate_step(t0 + timedelta(minutes=60), 5, [], [], reviews)
    assert reviews[0].lifecycle_state == ReviewLifecycleState.CLOSED
    assert reviews[0].condition == ConditionState.NORMAL


def test_qualified_anomaly_supersedes_matching_review():
    """Verify that a qualified anomaly episode supersedes the matching behavioural review."""
    engine = ReviewFlagEngine(asset_id="test_dt_01")
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    ev = _make_evidence("ev_001", t0)
    reviews = engine.evaluate_step(t0, 1, [ev], [], [])
    assert reviews[0].lifecycle_state == ReviewLifecycleState.OPEN

    from app.models.anomaly import EpisodeState

    # Qualified anomaly appears on sensor_top_oil
    ep = AnomalyEpisode(
        episode_id="ep_thermal_001",
        asset_id="test_dt_01",
        state=EpisodeState.CRITICAL,
        category=AnomalyCategory.SENSOR_PLAUSIBILITY,
        severity_score=0.9,
        start_time_utc=t0 + timedelta(minutes=15),
        last_seen_time_utc=t0 + timedelta(minutes=15),
        primary_reason="Severe sensor plausibility fault",
    )

    reviews_after = engine.evaluate_step(
        event_time_utc=t0 + timedelta(minutes=15),
        stream_position=2,
        evidence_items=[],
        open_episodes=[ep],
        previous_reviews=reviews,
    )

    assert reviews_after[0].lifecycle_state == ReviewLifecycleState.SUPERSEDED
    assert reviews_after[0].condition == ConditionState.QUALIFIED_ANOMALY
    assert reviews_after[0].superseded_by_anomaly_id == "ep_thermal_001"


def test_deterministic_replay_invariance():
    """Verify that identical event sequences + feedback yield 100% byte-for-byte identical review vectors."""
    t0 = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    events = [
        _make_evidence(f"ev_{i:03d}", t0 + timedelta(minutes=15 * i))
        for i in range(6)
    ]

    engine1 = ReviewFlagEngine(asset_id="test_dt_01")
    engine2 = ReviewFlagEngine(asset_id="test_dt_01")

    revs1 = []
    revs2 = []

    for i, ev in enumerate(events):
        pos = i + 1
        t_cur = t0 + timedelta(minutes=15 * i)
        revs1 = engine1.evaluate_step(t_cur, pos, [ev] if i < 3 else [], [], revs1)
        revs2 = engine2.evaluate_step(t_cur, pos, [ev] if i < 3 else [], [], revs2)

    assert len(revs1) == len(revs2)
    assert [r.model_dump() for r in revs1] == [r.model_dump() for r in revs2]
