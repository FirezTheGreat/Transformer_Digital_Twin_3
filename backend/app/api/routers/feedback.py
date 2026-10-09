"""Operator Feedback Submission Router (Phase 7.3).

Provides endpoint:
- POST /v1/feedback: Submit operator acknowledge, dismissal, inspection outcome, or override.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, status

from app.api.deps import AppState, get_app_state, get_feedback_ledger
from app.api.errors import ValidationException
from app.api.schemas import OperatorFeedbackRequest
from app.engine.feedback import OperatorFeedbackLedger
from app.models.maintenance import (
    FeedbackAction,
    MaintenanceRecommendation,
    OperatorFeedbackEvent,
)

router = APIRouter(tags=["Feedback"])


@router.post(
    "/feedback",
    response_model=OperatorFeedbackEvent,
    status_code=status.HTTP_200_OK,
    summary="Record operator acknowledgement, dismissal, inspection finding, or authorized override",
)
async def submit_operator_feedback(
    request: OperatorFeedbackRequest,
    app_state: AppState = Depends(get_app_state),
    ledger: OperatorFeedbackLedger = Depends(get_feedback_ledger),
) -> OperatorFeedbackEvent:
    """Validate, record into append-only immutable ledger, and update active recommendation workflow state."""
    # 1. Parse / Validate action enum
    try:
        action_enum = FeedbackAction(request.action.upper().strip())
    except ValueError:
        raise ValidationException(
            message=f"Invalid feedback action '{request.action}'. Supported actions: {[a.value for a in FeedbackAction]}.",
            details={"action": request.action},
        )

    # 2. Build canonical OperatorFeedbackEvent
    event_id = request.feedback_id or f"FB-{uuid.uuid4().hex[:12].upper()}"
    ts = request.timestamp_utc or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    event = OperatorFeedbackEvent(
        feedback_id=event_id,
        asset_id=request.asset_id,
        timestamp_utc=ts,
        recommendation_id=request.recommendation_id,
        merge_key=request.merge_key,
        action=action_enum,
        operator_id=request.operator_id,
        actor_id=request.actor_id or request.operator_id,
        reason_code=request.reason_code,
        notes=request.notes,
        rationale=request.rationale,
        inspection_outcome=request.inspection_outcome,
        authorized_role=request.authorized_role,
        override_expiry_utc=request.override_expiry_utc,
        review_id=request.review_id,
        expected_revision=request.expected_revision,
        idempotency_key=request.idempotency_key,
    )

    # 3. Locate target recommendation if present in state for P0 safety checks
    target_rec: MaintenanceRecommendation | None = None
    if app_state.current_state and request.recommendation_id:
        for r in app_state.current_state.active_recommendations:
            if r.recommendation_id == request.recommendation_id:
                target_rec = r
                break
    elif app_state.latest_fact_bundle and request.recommendation_id:
        for r in app_state.latest_fact_bundle.active_recommendations:
            if r.recommendation_id == request.recommendation_id:
                target_rec = r
                break

    # 4. Append to append-only immutable ledger
    try:
        recorded_event = ledger.append(event, target_recommendation=target_rec)
    except ValueError as err:
        raise ValidationException(
            message=str(err),
            details={
                "action": action_enum.value,
                "recommendation_id": request.recommendation_id,
                "reason_code": request.reason_code,
            },
        )

    # 5. Synchronize active state workflow metadata
    if app_state.current_state is not None:
        current_recs = list(app_state.current_state.active_recommendations)
        if action_enum == FeedbackAction.ACKNOWLEDGE:
            updated_recs = []
            for r in current_recs:
                match = (request.recommendation_id and r.recommendation_id == request.recommendation_id) or (
                    request.merge_key and r.merge_key == request.merge_key
                )
                if match:
                    r_dict = r.model_dump()
                    r_dict["acknowledged"] = True
                    r_dict["acknowledged_at_utc"] = ts
                    r_dict["acknowledged_by"] = request.operator_id
                    updated_recs.append(MaintenanceRecommendation.model_validate(r_dict))
                else:
                    updated_recs.append(r)
            app_state.current_state = app_state.current_state.model_copy(
                update={"active_recommendations": updated_recs}
            )
        elif action_enum == FeedbackAction.DISMISS:
            updated_recs = [
                r for r in current_recs
                if not (
                    (request.recommendation_id and r.recommendation_id == request.recommendation_id)
                    or (request.merge_key and r.merge_key == request.merge_key)
                )
            ]
            app_state.current_state = app_state.current_state.model_copy(
                update={"active_recommendations": updated_recs}
            )

    if app_state.latest_fact_bundle is not None:
        bundle_recs = list(app_state.latest_fact_bundle.active_recommendations)
        if action_enum == FeedbackAction.ACKNOWLEDGE:
            updated_bundle_recs = []
            for r in bundle_recs:
                match = (request.recommendation_id and r.recommendation_id == request.recommendation_id) or (
                    request.merge_key and r.merge_key == request.merge_key
                )
                if match:
                    r_dict = r.model_dump()
                    r_dict["acknowledged"] = True
                    r_dict["acknowledged_at_utc"] = ts
                    r_dict["acknowledged_by"] = request.operator_id
                    updated_bundle_recs.append(MaintenanceRecommendation.model_validate(r_dict))
                else:
                    updated_bundle_recs.append(r)
            app_state.latest_fact_bundle = app_state.latest_fact_bundle.model_copy(
                update={"active_recommendations": updated_bundle_recs}
            )
        elif action_enum == FeedbackAction.DISMISS:
            updated_bundle_recs = [
                r for r in bundle_recs
                if not (
                    (request.recommendation_id and r.recommendation_id == request.recommendation_id)
                    or (request.merge_key and r.merge_key == request.merge_key)
                )
            ]
            app_state.latest_fact_bundle = app_state.latest_fact_bundle.model_copy(
                update={"active_recommendations": updated_bundle_recs}
            )

    # 6. Synchronize active state ReviewFlag workflow metadata if review_id is specified
    if request.review_id and app_state.current_state is not None:
        if app_state.reducer and app_state.reducer.review_engine:
            try:
                updated_reviews = app_state.reducer.review_engine.apply_feedback_mutation(
                    reviews=app_state.current_state.active_reviews,
                    review_id=request.review_id,
                    action=request.action,
                    actor_id=request.actor_id or request.operator_id,
                    rationale=request.rationale or request.notes,
                    expected_revision=request.expected_revision,
                    idempotency_key=request.idempotency_key,
                    event_time_utc=ts,
                    stream_position=app_state.current_state.state_sequence,
                )
                app_state.current_state = app_state.current_state.model_copy(
                    update={"active_reviews": updated_reviews}
                )
            except (ValueError, KeyError) as e:
                raise ValidationException(message=str(e), details={"review_id": request.review_id})

    return recorded_event
