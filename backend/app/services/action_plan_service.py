import json
import logging
import threading
import time
from datetime import date, datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.domain_events import DomainEventName
from app.core.event_bus import event_bus
from app.models.action_plan import ActionPlan, ActionPlanFrequency, ActionPlanItem, ActionPlanStatus
from app.models.goal import Goal, GoalBreakdown, GoalBreakdownStatus
from app.models.profile import UserProfile
from app.schemas.action_plan import ActionPlanDetailRead
from app.models.growth_record import GrowthRecordType, GrowthRecordSource
from app.services import milestone_service
from app.services.milestone_service import MilestoneFinalizeInfo
from app.services.goal_breakdown_utils import list_main_breakdown_nodes
from app.services.growth_record_service import create_growth_record, void_growth_record_by_idempotency_key
from app.services.ukl_execution_service import maybe_sync_execution_slices

logger = logging.getLogger(__name__)


def _schedule_item_completion_side_effects(
    user_id: int,
    *,
    plan_id: int,
    goal_id: int,
    growth_record_id: int | None,
    item_title: str,
    item_sequence: int,
    pending_milestones: list[MilestoneFinalizeInfo],
) -> None:
    """Run UKL ingest, domain events, and milestone finalize off the request thread."""

    def _run() -> None:
        import app.core.database as database_module

        try:
            if growth_record_id is not None:
                event_bus.publish(
                    event_name=DomainEventName.ON_ACTION_COMPLETED.value,
                    user_id=user_id,
                    payload={
                        "plan_id": plan_id,
                        "goal_id": goal_id,
                        "plan_item_title": item_title,
                        "plan_item_sequence": item_sequence,
                    },
                    fail_fast=False,
                )
                event_bus.publish(
                    event_name=DomainEventName.ON_GROWTH_UPDATED.value,
                    user_id=user_id,
                    payload={
                        "record_id": growth_record_id,
                        "record_type": GrowthRecordType.ACTION_PLAN.value,
                        "source_type": GrowthRecordSource.ACTION_PLAN.value,
                        "source": "action_plan_completion",
                    },
                    fail_fast=False,
                )
            if pending_milestones:
                milestone_service.finalize_milestones_after_commit(user_id, pending_milestones)

            db = database_module.SessionLocal()
            try:
                maybe_sync_execution_slices(db, user_id, goal_id=goal_id)
            finally:
                db.close()
        except Exception:
            logger.exception(
                "Item completion side effects failed user_id=%s plan_id=%s",
                user_id,
                plan_id,
            )

    if settings.ACTION_PLAN_COMPLETION_ASYNC:
        threading.Thread(target=_run, daemon=True).start()
    else:
        _run()


def get_action_plan_for_user(db: Session, user_id: int, plan_id: int) -> ActionPlan | None:
    return (
        db.query(ActionPlan)
        .join(Goal, Goal.id == ActionPlan.goal_id)
        .filter(ActionPlan.id == plan_id, Goal.user_id == user_id)
        .first()
    )


def get_action_plan_for_goal(db: Session, user_id: int, goal_id: int) -> ActionPlan | None:
    """Return the first action plan for a goal (kept for facade compatibility)."""
    return (
        db.query(ActionPlan)
        .join(Goal, Goal.id == ActionPlan.goal_id)
        .filter(ActionPlan.goal_id == goal_id, Goal.user_id == user_id)
        .order_by(ActionPlan.main_breakdown_id.asc(), ActionPlan.id.asc())
        .first()
    )


def list_action_plans_for_goal(db: Session, user_id: int, goal_id: int) -> list[ActionPlan]:
    return (
        db.query(ActionPlan)
        .join(Goal, Goal.id == ActionPlan.goal_id)
        .filter(ActionPlan.goal_id == goal_id, Goal.user_id == user_id)
        .order_by(ActionPlan.main_breakdown_id.asc(), ActionPlan.id.asc())
        .all()
    )


def list_action_plans_for_user(db: Session, user_id: int) -> list[ActionPlan]:
    return (
        db.query(ActionPlan)
        .join(Goal, Goal.id == ActionPlan.goal_id)
        .filter(Goal.user_id == user_id)
        .order_by(ActionPlan.created_at.desc(), ActionPlan.id.desc())
        .all()
    )


def get_plan_detail(db: Session, user_id: int, plan_id: int) -> ActionPlanDetailRead | None:
    plan = get_action_plan_for_user(db, user_id, plan_id)
    if not plan:
        return None

    return ActionPlanDetailRead.model_validate(plan)


def refresh_action_plan(db: Session, user_id: int, plan_id: int) -> ActionPlan | None:
    plan = get_action_plan_for_user(db, user_id, plan_id)
    if not plan:
        return None

    goal = _get_goal_for_user(db, user_id, plan.goal_id)
    if not goal:
        return None

    main_node = (
        db.query(GoalBreakdown)
        .filter(GoalBreakdown.id == plan.main_breakdown_id, GoalBreakdown.goal_id == goal.id)
        .first()
    )
    if not main_node:
        raise ValueError("Action plan is missing its main breakdown node")

    raw_response = _generate_action_plan_response_for_main(db, goal, main_node)
    payload = parse_action_plan_response(raw_response)
    if payload is None:
        raise ValueError("AI output is not valid JSON")

    return _upsert_action_plan(db, goal, payload, existing_plan=plan)


def generate_action_plan_with_retry(
    db: Session,
    user_id: int,
    plan_id: int,
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 1.0,
) -> ActionPlan | None:
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return refresh_action_plan(db, user_id, plan_id)
        except (RuntimeError, ValueError) as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            delay = base_delay_seconds * (2 ** (attempt - 1))
            time.sleep(delay)
    if last_error:
        raise last_error
    return None


def _get_goal_for_user(db: Session, user_id: int, goal_id: int) -> Goal | None:
    return db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()


def _generate_action_plan_response_for_main(db: Session, goal: Goal, main_node: GoalBreakdown) -> str:
    from app.services import chat_service, profile_service, ukl_prompt_service

    secondary = _list_secondary_breakdowns_for_main(db, main_node.id)
    today_iso = date.today().isoformat()
    if settings.UKL_ENABLED:
        prompt = ukl_prompt_service.build_action_plan_prompt_for_main(
            db,
            goal,
            main_node,
            secondary,
            today_iso,
        )
    else:
        profile = profile_service.get_profile_for_user(db, goal.user_id)
        prompt = _build_action_plan_prompt_for_main(goal, main_node, secondary, profile, today_iso)
    return chat_service.build_action_plan_response(prompt)


def _list_secondary_breakdowns_for_main(db: Session, main_id: int) -> list[GoalBreakdown]:
    return (
        db.query(GoalBreakdown)
        .filter(GoalBreakdown.parent_id == main_id)
        .order_by(GoalBreakdown.sequence.asc(), GoalBreakdown.id.asc())
        .all()
    )


def _build_action_plan_prompt_for_main(
    goal: Goal,
    main_node: GoalBreakdown,
    secondary_nodes: list[GoalBreakdown],
    profile: UserProfile | None,
    today_iso: str,
) -> str:
    lines: list[str] = []
    lines.append(f"Current date (planning anchor): {today_iso}")
    lines.append("\nParent goal context:")
    lines.append(f"Title: {goal.title}")
    if goal.description:
        lines.append(f"Description: {goal.description}")
    if goal.priority:
        lines.append(f"Priority: {goal.priority}")
    if goal.target_date:
        lines.append(f"Target date: {goal.target_date}")

    lines.append("\nMain milestone (pillar) for this action plan:")
    lines.append(f"- [{main_node.id}] {main_node.title}")
    if main_node.description:
        lines.append(f"  Description: {main_node.description}")

    if profile:
        profile_bits: list[str] = []
        if profile.goals:
            profile_bits.append(f"goals={', '.join(profile.goals)}")
        if profile.skills:
            profile_bits.append(f"skills={', '.join(profile.skills)}")
        if profile.interests:
            profile_bits.append(f"interests={', '.join(profile.interests)}")
        if profile.study_habits:
            profile_bits.append(f"study_habits={', '.join(profile.study_habits)}")
        if profile.preferences:
            profile_bits.append(f"preferences={', '.join(profile.preferences)}")
        if profile_bits:
            lines.append("\nExtended profile context:")
            lines.extend(profile_bits)

    lines.append("\nSecondary breakdown nodes (use ONLY these as breakdown_ref targets for items):")
    if secondary_nodes:
        for node in secondary_nodes:
            desc = f" — {node.description}" if node.description else ""
            lines.append(f"- [{node.id}] {node.title}{desc}")
    else:
        lines.append(
            "- (No secondary nodes.) Treat the main milestone as the only scope; "
            "still return concrete items and set breakdown_ref to the main milestone id when needed."
        )
        lines.append(f"- [{main_node.id}] {main_node.title}")

    lines.append(
        "\nReturn strict JSON with structure: {\"plan\": {\"title\": string, \"summary\": string}, "
        "\"items\": [{\"title\": string, \"description\": string|null, \"frequency\": string, "
        "\"schedule\": string|null, \"status\": string, \"start_date\": string|null, "
        "\"due_date\": string|null, \"sequence\": number, \"breakdown_ref\": number|string|null}] }"
        "\nEach item must map to one secondary breakdown id via breakdown_ref (numeric id). "
        "Produce enough items to operationalize every secondary node; merge only when clearly redundant."
    )

    return "\n".join(lines)


def _build_breakdown_lookup_for_main(db: Session, goal_id: int, main_breakdown_id: int) -> dict[str, int]:
    """Allow refs to the main pillar and its direct children only."""
    lookup: dict[str, int] = {}
    nodes = (
        db.query(GoalBreakdown)
        .filter(
            GoalBreakdown.goal_id == goal_id,
            or_(GoalBreakdown.id == main_breakdown_id, GoalBreakdown.parent_id == main_breakdown_id),
        )
        .all()
    )
    for breakdown in nodes:
        lookup[str(breakdown.id)] = breakdown.id
        title_key = _normalize_lookup_key(breakdown.title)
        if title_key:
            lookup[title_key] = breakdown.id
    return lookup


def _resolve_breakdown_ref(breakdown_ref: object, breakdown_lookup: dict[str, int]) -> int | None:
    if breakdown_ref is None:
        return None

    if isinstance(breakdown_ref, int):
        return breakdown_ref if str(breakdown_ref) in breakdown_lookup else None

    text = str(breakdown_ref).strip()
    if not text:
        return None

    lookup_key = _normalize_lookup_key(text)
    if lookup_key and lookup_key in breakdown_lookup:
        return breakdown_lookup[lookup_key]

    if text.isdigit() and text in breakdown_lookup:
        return breakdown_lookup[text]

    return None


def _validate_secondary_coverage(
    secondary_nodes: list[GoalBreakdown],
    main_breakdown_id: int,
    normalized_items: list[dict],
    breakdown_lookup: dict[str, int],
) -> list[str]:
    if not normalized_items:
        return [str(node.id) for node in secondary_nodes] or [str(main_breakdown_id)]

    if not secondary_nodes:
        for item in normalized_items:
            ref_id = _resolve_breakdown_ref(item.get("breakdown_ref"), breakdown_lookup)
            if ref_id == main_breakdown_id:
                return []
        return [str(main_breakdown_id)]

    missing: list[str] = []
    for node in secondary_nodes:
        covered = False
        for item in normalized_items:
            ref_id = _resolve_breakdown_ref(item.get("breakdown_ref"), breakdown_lookup)
            if ref_id == node.id:
                covered = True
                break
        if not covered:
            missing.append(str(node.id))
    return missing


def _sync_aggregate_plan_and_main_status(
    db: Session,
    plan: ActionPlan,
    *,
    pending_milestones: list[MilestoneFinalizeInfo] | None = None,
) -> None:
    items = (
        db.query(ActionPlanItem)
        .filter(ActionPlanItem.plan_id == plan.id)
        .order_by(ActionPlanItem.sequence.asc(), ActionPlanItem.id.asc())
        .all()
    )
    total = len(items)
    completed = sum(1 for item in items if item.status == ActionPlanStatus.COMPLETED.value)
    if total == 0:
        plan.status = ActionPlanStatus.PENDING.value
    elif completed == total:
        plan.status = ActionPlanStatus.COMPLETED.value
    elif completed > 0:
        plan.status = ActionPlanStatus.IN_PROGRESS.value
    else:
        plan.status = ActionPlanStatus.PENDING.value

    goal = db.query(Goal).filter(Goal.id == plan.goal_id).first()
    user_id = goal.user_id if goal else None

    bd = db.query(GoalBreakdown).filter(GoalBreakdown.id == plan.main_breakdown_id).first()
    if bd:
        old_main_status = bd.status
        if total == 0:
            pass
        elif completed == total:
            bd.status = GoalBreakdownStatus.COMPLETED.value
        elif completed > 0:
            bd.status = GoalBreakdownStatus.IN_PROGRESS.value
        else:
            bd.status = GoalBreakdownStatus.PENDING.value
        db.add(bd)
        if user_id:
            info = milestone_service.handle_breakdown_status_transition(
                db,
                user_id,
                bd,
                old_main_status,
                bd.status,
                plan_id=plan.id,
                main_breakdown_id=plan.main_breakdown_id,
            )
            if info and pending_milestones is not None:
                pending_milestones.append(info)

    _sync_secondary_breakdown_statuses(
        db, plan, items, user_id=user_id, pending_milestones=pending_milestones
    )
    db.add(plan)


def _sync_secondary_breakdown_statuses(
    db: Session,
    plan: ActionPlan,
    items: list[ActionPlanItem],
    *,
    user_id: int | None = None,
    pending_milestones: list[MilestoneFinalizeInfo] | None = None,
) -> None:
    """Soft-aggregate branch node status from linked action plan items."""
    secondary_nodes = _list_secondary_breakdowns_for_main(db, plan.main_breakdown_id)
    if not secondary_nodes:
        return

    for node in secondary_nodes:
        linked = [item for item in items if item.breakdown_id == node.id]
        if not linked:
            continue
        old_status = node.status
        completed = sum(1 for item in linked if item.status == ActionPlanStatus.COMPLETED.value)
        if completed == len(linked):
            node.status = GoalBreakdownStatus.COMPLETED.value
        elif completed > 0:
            node.status = GoalBreakdownStatus.IN_PROGRESS.value
        else:
            node.status = GoalBreakdownStatus.PENDING.value
        db.add(node)
        if user_id:
            info = milestone_service.handle_breakdown_status_transition(
                db,
                user_id,
                node,
                old_status,
                node.status,
                plan_id=plan.id,
                main_breakdown_id=plan.main_breakdown_id,
            )
            if info and pending_milestones is not None:
                pending_milestones.append(info)


def _upsert_action_plan(
    db: Session,
    goal: Goal,
    payload: dict,
    *,
    existing_plan: ActionPlan,
) -> ActionPlan:
    plan_data = payload.get("plan") if isinstance(payload.get("plan"), dict) else {}
    items_data = payload.get("items") if isinstance(payload.get("items"), list) else []

    plan = existing_plan
    plan.title = _normalize_plan_title(goal, plan_data)
    plan.summary = _normalize_text(plan_data.get("summary"))

    plan.error_message = None

    db.query(ActionPlanItem).filter(ActionPlanItem.plan_id == plan.id).delete(synchronize_session=False)

    normalized_items = _normalize_items_payload(items_data)
    if not normalized_items:
        logger.warning("Action plan generation produced no items for goal_id=%s plan_id=%s", goal.id, plan.id)

    breakdown_lookup = _build_breakdown_lookup_for_main(db, goal.id, plan.main_breakdown_id)

    if settings.UKL_ENABLED and settings.ACTION_PLAN_COVERAGE_VALIDATION_ENABLED:
        secondary_nodes = _list_secondary_breakdowns_for_main(db, plan.main_breakdown_id)
        missing_ids = _validate_secondary_coverage(
            secondary_nodes,
            plan.main_breakdown_id,
            normalized_items,
            breakdown_lookup,
        )
        if missing_ids:
            logger.warning(
                "Action plan missing secondary coverage goal_id=%s plan_id=%s missing=%s",
                goal.id,
                plan.id,
                missing_ids,
            )
            raise ValueError(
                f"Action plan missing coverage for breakdown ids: {', '.join(missing_ids)}"
            )

    for item_data in normalized_items:
        breakdown_ref = item_data.get("breakdown_ref")
        breakdown_id = _resolve_breakdown_ref(breakdown_ref, breakdown_lookup)

        item_status = _normalize_status(item_data.get("status"), default=ActionPlanStatus.PENDING.value)

        new_item = ActionPlanItem(
            plan_id=plan.id,
            breakdown_id=breakdown_id,
            title=item_data["title"],
            description=item_data.get("description"),
            frequency=_normalize_frequency(item_data.get("frequency")),
            schedule=_normalize_text(item_data.get("schedule")),
            status=item_status,
            start_date=_normalize_date(item_data.get("start_date")),
            due_date=_normalize_date(item_data.get("due_date")),
            sequence=item_data["sequence"],
        )

        db.add(new_item)

        if item_status == ActionPlanStatus.COMPLETED.value:
            growth_record = create_growth_record(
                db,
                goal.user_id,
                title=new_item.title,
                summary=new_item.description,
                content=f"自动回写：来自行动计划 {plan.id} 项目",
                record_type=GrowthRecordType.ACTION_PLAN.value,
                source_type=GrowthRecordSource.ACTION_PLAN.value,
                source_ref_id=None,
                occurred_at=datetime.utcnow(),
                commit=False,
                refresh=False,
            )
            event_bus.publish(
                event_name=DomainEventName.ON_ACTION_COMPLETED.value,
                user_id=goal.user_id,
                payload={
                    "plan_id": plan.id,
                    "goal_id": goal.id,
                    "plan_item_title": new_item.title,
                    "plan_item_sequence": new_item.sequence,
                },
                fail_fast=False,
            )
            event_bus.publish(
                event_name=DomainEventName.ON_GROWTH_UPDATED.value,
                user_id=goal.user_id,
                payload={
                    "record_id": growth_record.id,
                    "record_type": growth_record.record_type,
                    "source_type": growth_record.source_type,
                    "source": "action_plan_completion",
                },
                fail_fast=False,
            )

    db.flush()
    _sync_aggregate_plan_and_main_status(db, plan)
    db.commit()
    db.refresh(plan)
    maybe_sync_execution_slices(db, goal.user_id, goal_id=goal.id)
    return plan


def parse_action_plan_response(raw_text: str) -> dict | None:
    if not raw_text or not isinstance(raw_text, str):
        return None

    text = raw_text.strip()
    if not text:
        return None

    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        try:
            payload = json.loads(text[start_idx : end_idx + 1])
            if isinstance(payload, dict):
                return payload
        except json.JSONDecodeError:
            pass

    logger.warning("Failed to parse action plan response: %s", raw_text[:120])
    return None


def _normalize_plan_title(goal: Goal, plan_data: dict) -> str:
    title = plan_data.get("title") if isinstance(plan_data, dict) else None
    text = _normalize_text(title)
    return text or f"{goal.title} Action Plan"


def _normalize_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_status(value: object, *, default: str) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {status.value for status in ActionPlanStatus}:
            return normalized
    return default


def prepare_action_plans_for_goal(
    db: Session,
    user_id: int,
    goal_id: int,
    *,
    reset_items: bool = False,
) -> list[ActionPlan]:
    """Create or reset placeholder rows for each root breakdown (one action plan article per main pillar)."""
    goal = _get_goal_for_user(db, user_id, goal_id)
    if not goal:
        return []

    main_nodes = list_main_breakdown_nodes(db, goal_id)
    main_ids = {node.id for node in main_nodes}

    if main_ids:
        stale_plans = (
            db.query(ActionPlan)
            .filter(ActionPlan.goal_id == goal_id, ActionPlan.main_breakdown_id.notin_(main_ids))
            .all()
        )
        for stale in stale_plans:
            db.delete(stale)

    out: list[ActionPlan] = []
    for main_node in main_nodes:
        plan = (
            db.query(ActionPlan)
            .filter(ActionPlan.goal_id == goal_id, ActionPlan.main_breakdown_id == main_node.id)
            .first()
        )
        if plan is None:
            plan = ActionPlan(
                goal_id=goal.id,
                main_breakdown_id=main_node.id,
                title=f"{main_node.title} — 行动计划",
                summary=None,
                status=ActionPlanStatus.IN_PROGRESS.value,
                error_message=None,
            )
            db.add(plan)
            db.flush()
        else:
            plan.status = ActionPlanStatus.IN_PROGRESS.value
            plan.error_message = None

        if reset_items:
            db.query(ActionPlanItem).filter(ActionPlanItem.plan_id == plan.id).delete(synchronize_session=False)

        out.append(plan)

    db.commit()
    for plan in out:
        db.refresh(plan)
    return out


def sync_goal_deadlines(db: Session, goal: Goal) -> None:
    """After goal target date, mark unfinished main pillars (and their plans) as failed."""
    if not goal.target_date:
        return
    try:
        due = date.fromisoformat(str(goal.target_date)[:10])
    except ValueError:
        return
    if date.today() <= due:
        return

    main_nodes = list_main_breakdown_nodes(db, goal.id)
    changed = False
    for main_node in main_nodes:
        if main_node.status == GoalBreakdownStatus.COMPLETED.value:
            continue
        plan = (
            db.query(ActionPlan)
            .filter(ActionPlan.goal_id == goal.id, ActionPlan.main_breakdown_id == main_node.id)
            .first()
        )
        if plan and plan.status == ActionPlanStatus.COMPLETED.value:
            continue
        if main_node.status != GoalBreakdownStatus.FAILED.value:
            main_node.status = GoalBreakdownStatus.FAILED.value
            db.add(main_node)
            changed = True
        if plan and plan.status not in (ActionPlanStatus.COMPLETED.value, ActionPlanStatus.FAILED.value):
            plan.status = ActionPlanStatus.FAILED.value
            if not plan.error_message:
                plan.error_message = "已超过目标截止日期且仍有未完成项。"
            db.add(plan)
            changed = True
    if changed:
        db.commit()


def list_main_action_plan_progress(db: Session, goal_id: int) -> list[dict]:
    main_nodes = list_main_breakdown_nodes(db, goal_id)
    out: list[dict] = []
    for main_node in main_nodes:
        plan = (
            db.query(ActionPlan)
            .filter(ActionPlan.goal_id == goal_id, ActionPlan.main_breakdown_id == main_node.id)
            .first()
        )
        total_items = 0
        completed_items = 0
        plan_id: int | None = None
        plan_status: str | None = None
        if plan:
            plan_id = plan.id
            plan_status = plan.status
            items = db.query(ActionPlanItem).filter(ActionPlanItem.plan_id == plan.id).all()
            total_items = len(items)
            completed_items = sum(1 for item in items if item.status == ActionPlanStatus.COMPLETED.value)
        out.append(
            {
                "main_breakdown_id": main_node.id,
                "plan_id": plan_id,
                "plan_status": plan_status,
                "total_items": total_items,
                "completed_items": completed_items,
            }
        )
    return out


def prepare_action_plan_for_refresh(
    db: Session,
    user_id: int,
    plan_id: int,
    *,
    reset_items: bool = False,
) -> ActionPlan | None:
    plan = get_action_plan_for_user(db, user_id, plan_id)
    if not plan:
        return None

    plan.status = ActionPlanStatus.IN_PROGRESS.value
    plan.error_message = None

    if reset_items:
        db.query(ActionPlanItem).filter(ActionPlanItem.plan_id == plan.id).delete(synchronize_session=False)

    db.commit()
    db.refresh(plan)
    return plan


def mark_action_plan_failed(db: Session, plan_id: int, message: str | None = None) -> None:
    plan = db.query(ActionPlan).filter(ActionPlan.id == plan_id).first()
    if not plan:
        return
    plan.status = ActionPlanStatus.FAILED.value
    plan.error_message = (message or "Action plan generation failed.").strip()
    db.commit()


def _normalize_frequency(value: object) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {frequency.value for frequency in ActionPlanFrequency}:
            return normalized
    return ActionPlanFrequency.CUSTOM.value


def _normalize_date(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_items_payload(items_data: object) -> list[dict]:
    if not isinstance(items_data, list):
        return []

    normalized_items: list[dict] = []
    for sequence, raw_item in enumerate(items_data):
        if not isinstance(raw_item, dict):
            continue

        title = _normalize_text(raw_item.get("title")) or f"Action Item {sequence + 1}"
        normalized_items.append(
            {
                "title": title,
                "description": _normalize_text(raw_item.get("description")),
                "frequency": _normalize_frequency(raw_item.get("frequency")),
                "schedule": _normalize_text(raw_item.get("schedule")),
                "status": _normalize_status(raw_item.get("status"), default=ActionPlanStatus.PENDING.value),
                "start_date": _normalize_date(raw_item.get("start_date")),
                "due_date": _normalize_date(raw_item.get("due_date")),
                "sequence": _normalize_sequence(raw_item.get("sequence"), sequence),
                "breakdown_ref": raw_item.get("breakdown_ref"),
            }
        )

    return normalized_items


def _normalize_sequence(value: object, fallback: int) -> int:
    try:
        if value is None or value == "":
            return fallback
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _normalize_lookup_key(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def update_action_plan_item_completion(
    db: Session,
    user_id: int,
    plan_id: int,
    item_id: int,
    *,
    completed: bool,
) -> ActionPlanItem | None:
    """Mark an action plan item completed or not; completion syncs a growth record (idempotent)."""
    item = (
        db.query(ActionPlanItem)
        .join(ActionPlan, ActionPlan.id == ActionPlanItem.plan_id)
        .join(Goal, Goal.id == ActionPlan.goal_id)
        .filter(
            ActionPlanItem.id == item_id,
            ActionPlanItem.plan_id == plan_id,
            Goal.user_id == user_id,
        )
        .first()
    )
    if not item:
        return None

    idem = f"action-plan-item-{item_id}-completed"
    growth_record_id: int | None = None
    pending_milestones: list[MilestoneFinalizeInfo] = []

    if completed:
        item.status = ActionPlanStatus.COMPLETED.value
        goal = db.query(Goal).filter(Goal.id == item.plan.goal_id).first()
        goal_title = goal.title if goal else ""
        title = f"完成行动：{item.title}"
        summary_parts: list[str] = []
        if item.description:
            summary_parts.append(str(item.description))
        if goal_title:
            summary_parts.append(f"关联目标：{goal_title}")
        growth_record = create_growth_record(
            db,
            user_id,
            title=title[:255],
            summary="\n".join(summary_parts) if summary_parts else None,
            content=None,
            record_type=GrowthRecordType.ACTION_PLAN.value,
            source_type=GrowthRecordSource.ACTION_PLAN.value,
            source_ref_id=item_id,
            score=3,
            idempotency_key=idem,
            commit=False,
            refresh=False,
        )
        growth_record_id = growth_record.id
    else:
        item.status = ActionPlanStatus.PENDING.value
        void_growth_record_by_idempotency_key(db, user_id, idem, commit=False)

    db.add(item)
    db.flush()
    plan_row = db.query(ActionPlan).filter(ActionPlan.id == plan_id).first()
    if plan_row:
        _sync_aggregate_plan_and_main_status(
            db, plan_row, pending_milestones=pending_milestones
        )
    db.commit()
    db.refresh(item)

    if completed:
        _schedule_item_completion_side_effects(
            user_id,
            plan_id=plan_id,
            goal_id=item.plan.goal_id,
            growth_record_id=growth_record_id,
            item_title=item.title,
            item_sequence=item.sequence,
            pending_milestones=pending_milestones,
        )

    return item
