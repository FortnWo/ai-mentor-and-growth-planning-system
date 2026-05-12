from sqlalchemy.orm import Session

from app.models.extended_profile import UserExtendedProfile
from app.models.goal import Goal
from app.schemas.extended_profile import ExtendedProfileExtractionResult
from app.services import chat_service, extended_profile_service


def generate_chat_reply(message: str, *, instructions: str | None = None) -> str:
    return chat_service.build_ai_response(message, instructions=instructions)


def generate_profile_extraction(extraction_input: str) -> str:
    return chat_service.build_profile_extraction_response(extraction_input)


def generate_goal_breakdown(goal_prompt: str) -> str:
    return chat_service.build_goal_breakdown_response(goal_prompt)


def generate_action_plan(action_plan_prompt: str) -> str:
    return chat_service.build_action_plan_response(action_plan_prompt)


def build_goal_breakdown_prompt(goal: Goal, profile: UserExtendedProfile | None) -> str:
    lines: list[str] = []
    lines.append("Goal to break down:")
    lines.append(f"Title: {goal.title}")
    if goal.description:
        lines.append(f"Description: {goal.description}")

    if profile:
        lines.append("\nUser profile context:")
        if profile.goals:
            lines.append(f"User's goals: {', '.join(profile.goals)}")
        if profile.skills:
            lines.append(f"User's skills: {', '.join(profile.skills)}")
        if profile.interests:
            lines.append(f"User's interests: {', '.join(profile.interests)}")

    return "\n".join(lines)


def extract_profile_from_session(
    db: Session,
    *,
    session_id: int,
    user_id: int,
    message_window: int,
) -> tuple[UserExtendedProfile, ExtendedProfileExtractionResult] | None:
    messages = extended_profile_service.list_recent_messages_for_session(
        db,
        session_id=session_id,
        limit=message_window,
    )
    extraction_input = extended_profile_service.build_extraction_input(messages)
    if not extraction_input:
        return None

    raw_result = generate_profile_extraction(extraction_input)
    extraction_result = extended_profile_service.parse_extraction_result(raw_result)
    profile = extended_profile_service.apply_extraction_result_for_user(
        db,
        user_id=user_id,
        result=extraction_result,
    )
    return profile, extraction_result
