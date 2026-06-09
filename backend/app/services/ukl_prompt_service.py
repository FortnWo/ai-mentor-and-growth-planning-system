from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ukl_constants import SCENE_ACTION_PLAN, SCENE_BREAKDOWN
from app.models.goal import Goal, GoalBreakdown
from app.schemas.ukl import ContextBundle
from app.services import profile_service, ukl_service


def format_ukl_context_section(bundle: ContextBundle) -> str:
    lines: list[str] = ["[UKL 上下文]"]

    for block in bundle.narrative_blocks:
        text = (block or "").strip()
        if text:
            lines.append(text)

    anchors = bundle.anchors or {}
    profile_fields = anchors.get("profile_fields") or {}
    if profile_fields:
        bits: list[str] = []
        for key in ("goals", "skills", "interests", "study_habits", "preferences"):
            values = profile_fields.get(key) or []
            if values:
                bits.append(f"{key}={', '.join(str(v) for v in values)}")
        if bits:
            lines.append("用户画像字段：" + "；".join(bits))

    workload = anchors.get("workload")
    if isinstance(workload, dict) and workload:
        lines.append(
            "跨目标负载："
            f"活跃目标 {workload.get('active_goal_count', 0)}，"
            f"进行中计划 {workload.get('active_plan_count', 0)}，"
            f"待办项 {workload.get('pending_item_count', 0)}。"
        )

    execution = anchors.get("execution_feedback")
    if isinstance(execution, dict) and execution.get("total_items"):
        lines.append(
            "执行反馈："
            f"完成 {execution.get('completed_items', 0)}/{execution.get('total_items', 0)}，"
            f"完成率 {float(execution.get('completion_rate', 0)):.0%}。"
        )

    breakdown_summary = anchors.get("breakdown_summary")
    if isinstance(breakdown_summary, dict):
        summary_text = str(breakdown_summary.get("summary") or "").strip()
        if summary_text:
            lines.append(f"拆解叙事：{summary_text}")

    breakdown_anchors = anchors.get("breakdown_anchors")
    if isinstance(breakdown_anchors, dict):
        constraints = breakdown_anchors.get("critical_constraints") or []
        if constraints:
            lines.append("拆解约束：" + "；".join(str(c) for c in constraints))
        deps = breakdown_anchors.get("dependency_notes") or []
        if deps:
            lines.append("依赖说明：" + "；".join(str(d) for d in deps))
        capacity = breakdown_anchors.get("capacity_hint")
        if capacity:
            lines.append(f"容量提示：{capacity}")

    return "\n".join(lines)


def build_legacy_goal_breakdown_prompt(db: Session, user_id: int, goal: Goal) -> str:
    user_profile = profile_service.get_profile_for_user(db, user_id)
    lines: list[str] = []
    lines.append("待拆解目标：")
    lines.append(f"标题：{goal.title}")
    if goal.description:
        lines.append(f"描述：{goal.description}")

    if user_profile:
        lines.append("\n用户画像上下文：")
        if user_profile.goals:
            lines.append(f"目标：{', '.join(user_profile.goals)}")
        if user_profile.skills:
            lines.append(f"技能：{', '.join(user_profile.skills)}")
        if user_profile.interests:
            lines.append(f"兴趣：{', '.join(user_profile.interests)}")

    return "\n".join(lines)


def build_goal_breakdown_prompt(
    db: Session,
    user_id: int,
    goal: Goal,
    *,
    is_refresh: bool = False,
) -> str:
    if not settings.UKL_ENABLED:
        return build_legacy_goal_breakdown_prompt(db, user_id, goal)

    bundle = ukl_service.assemble_context(
        db,
        user_id,
        SCENE_BREAKDOWN,
        goal_id=goal.id,
        is_refresh=is_refresh,
    )
    lines = [format_ukl_context_section(bundle), "\n[目标实体]"]
    lines.append(f"标题：{goal.title}")
    if goal.description:
        lines.append(f"描述：{goal.description}")
    if goal.priority:
        lines.append(f"优先级：{goal.priority}")
    if goal.target_date:
        lines.append(f"目标日期：{goal.target_date}")
    return "\n".join(lines)


def _format_action_plan_entity_section(
    goal: Goal,
    main_node: GoalBreakdown,
    secondary_nodes: list[GoalBreakdown],
    today_iso: str,
) -> list[str]:
    lines: list[str] = []
    lines.append(f"当前日期（规划锚点）：{today_iso}")
    lines.append("\n父目标上下文：")
    lines.append(f"标题：{goal.title}")
    if goal.description:
        lines.append(f"描述：{goal.description}")
    if goal.priority:
        lines.append(f"优先级：{goal.priority}")
    if goal.target_date:
        lines.append(f"目标日期：{goal.target_date}")

    lines.append("\n本行动计划对应的主里程碑（支柱）：")
    lines.append(f"- [{main_node.id}] {main_node.title}")
    if main_node.description:
        lines.append(f"  描述：{main_node.description}")

    lines.append("\n次级拆解节点（items 的 breakdown_ref 只能引用以下 id）：")
    if secondary_nodes:
        for node in secondary_nodes:
            desc = f" — {node.description}" if node.description else ""
            lines.append(f"- [{node.id}] {node.title}{desc}")
    else:
        lines.append(
            "- （无次级节点。）以主里程碑为唯一范围；仍需返回具体行动项，"
            "必要时将 breakdown_ref 设为主里程碑 id。"
        )
        lines.append(f"- [{main_node.id}] {main_node.title}")

    lines.append(
        "\n仅输出严格 JSON，结构：{\"plan\": {\"title\": string, \"summary\": string}, "
        "\"items\": [{\"title\": string, \"description\": string|null, \"frequency\": string, "
        "\"schedule\": string|null, \"status\": string, \"start_date\": string|null, "
        "\"due_date\": string|null, \"sequence\": number, \"breakdown_ref\": number|string|null}] }"
        "\n每项须通过 breakdown_ref（数字 id）映射到一个次级拆解节点；"
        "为每个次级节点产出足够行动项，仅在明显冗余时合并。"
    )
    return lines


def build_action_plan_prompt_for_main(
    db: Session,
    goal: Goal,
    main_node: GoalBreakdown,
    secondary_nodes: list[GoalBreakdown],
    today_iso: str | None = None,
) -> str:
    anchor_date = today_iso or date.today().isoformat()
    bundle = ukl_service.assemble_context(
        db,
        goal.user_id,
        SCENE_ACTION_PLAN,
        goal_id=goal.id,
        main_breakdown_id=main_node.id,
    )
    lines = [format_ukl_context_section(bundle), "\n[Breakdown 实体]"]
    lines.extend(_format_action_plan_entity_section(goal, main_node, secondary_nodes, anchor_date))
    return "\n".join(lines)
