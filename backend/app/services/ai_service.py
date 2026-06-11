from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger("ai_mentor.ai_service")


class AIServiceError(RuntimeError):
    """Raised when AI provider calls fail at the service layer."""


def _get_ai_client(db=None) -> OpenAI:
    from app.services.system_config_service import (
        resolve_llm_api_base_url,
        resolve_llm_api_key,
    )

    api_key = resolve_llm_api_key(db)
    base_url = resolve_llm_api_base_url(db)
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not configured")
    if not base_url:
        raise RuntimeError("LLM_API_BASE_URL is not configured")

    return OpenAI(
        base_url=base_url,
        api_key=api_key,
    )


def _get_model(db=None) -> str:
    from app.services.system_config_service import resolve_llm_model

    model = resolve_llm_model(db)
    if not model:
        raise RuntimeError("LLM_MODEL is not configured")
    return model


def extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = getattr(response, "output", None) or []
    chunks: list[str] = []

    for item in output:
        if getattr(item, "type", None) != "message":
            continue

        content_items = getattr(item, "content", None) or []
        for content_item in content_items:
            if getattr(content_item, "type", None) != "output_text":
                continue

            text = getattr(content_item, "text", None)
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())

    if chunks:
        return "\n".join(chunks).strip()

    raise RuntimeError("AI response did not contain any text content")


def _parse_token_usage(response: Any) -> tuple[int, int]:
    """Extract prompt/completion token counts from an OpenAI Responses API object."""
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0

    prompt_tokens = getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0) or 0
    completion_tokens = getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0) or 0
    return int(prompt_tokens or 0), int(completion_tokens or 0)


def _log_usage(model: str, task: str, response: Any, user_id: int | None = None) -> None:
    """Fire-and-forget: write usage stats to ai_usage_logs if table exists."""
    try:
        from app.core.database import SessionLocal
        from app.models.system_config import AIUsageLog

        prompt_tokens, completion_tokens = _parse_token_usage(response)
        if getattr(response, "usage", None) is None:
            logger.info(
                "ai_usage_skipped: no usage metadata on response (task=%s user_id=%s); logging call with zero tokens",
                task,
                user_id,
            )

        db = SessionLocal()
        try:
            record = AIUsageLog(
                user_id=user_id,
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                task=task,
            )
            db.add(record)
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "ai_service: usage log failed (task=%s user_id=%s): %s",
            task,
            user_id,
            exc,
        )


def _invoke_ai(
    *,
    task_name: str,
    message: str,
    instructions: str | None = None,
    db=None,
    user_id: int | None = None,
) -> str:
    rate_limit_user_id: int | None = None
    if task_name == "chat" and user_id is not None:
        from app.core.db_session import session_scope
        from app.models.user import User
        from app.services.ai_rate_limit_service import assert_chat_allowed

        with session_scope() as rate_db:
            rate_limit_user = rate_db.query(User).filter(User.id == user_id).first()
            if rate_limit_user is not None:
                assert_chat_allowed(rate_db, rate_limit_user)
                rate_limit_user_id = rate_limit_user.id

    try:
        client = _get_ai_client(db)
        model = _get_model(db)
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=message.strip(),
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise AIServiceError(f"AI {task_name} request failed: {exc}") from exc

    _log_usage(model, task_name, response, user_id=user_id)

    if task_name == "chat" and rate_limit_user_id is not None:
        from app.core.db_session import session_scope
        from app.models.user import User
        from app.services.ai_rate_limit_service import sync_user_risk_flag

        with session_scope() as rate_db:
            rate_limit_user = rate_db.query(User).filter(User.id == rate_limit_user_id).first()
            if rate_limit_user is not None:
                sync_user_risk_flag(rate_db, rate_limit_user)

    return extract_response_text(response)


def build_session_summary_response(
    prior_summary: str | None,
    new_dialogue: str,
    *,
    db=None,
    user_id: int | None = None,
) -> str:
    prior = (prior_summary or "").strip()
    dialogue = (new_dialogue or "").strip()
    if not dialogue:
        return prior

    if prior:
        message = f"已有摘要：\n{prior}\n\n新增对话：\n{dialogue}"
    else:
        message = f"新增对话：\n{dialogue}"

    return _invoke_ai(
        task_name="session_summary",
        message=message,
        instructions=settings.CHAT_SESSION_SUMMARY_SYSTEM_PROMPT,
        db=db,
        user_id=user_id,
    )


def build_chat_response(
    message: str,
    *,
    instructions: str | None = None,
    db=None,
    user_id: int | None = None,
) -> str:
    if instructions is None:
        from app.core.db_session import session_scope
        from app.services.system_config_service import resolve_llm_system_prompt

        if db is not None:
            instructions = resolve_llm_system_prompt(db)
        else:
            with session_scope() as prompt_db:
                instructions = resolve_llm_system_prompt(prompt_db)
    return _invoke_ai(
        task_name="chat",
        message=message,
        instructions=instructions,
        user_id=user_id,
    )


def build_admin_chat_response(message: str, db=None, *, user_id: int | None = None) -> str:
    """
    Admin chat: uses admin system prompt + DB query tools.
    Supports multi-turn tool calling loop.
    db: optional SQLAlchemy Session for tool execution (short-lived scopes used when None).
    user_id: session owner for ai_usage_logs attribution.
    """
    from app.core.db_session import session_scope
    from app.services.admin_tool_service import ADMIN_TOOLS, execute_tool
    from app.services.system_config_service import resolve_admin_llm_system_prompt

    if db is not None:
        admin_prompt = resolve_admin_llm_system_prompt(db)
    else:
        with session_scope() as prompt_db:
            admin_prompt = resolve_admin_llm_system_prompt(prompt_db)

    try:
        client = _get_ai_client(db)
        model = _get_model(db)
    except RuntimeError:
        raise

    MAX_TOOL_ROUNDS = 5
    current_input: str | list = message.strip()

    for _round_num in range(MAX_TOOL_ROUNDS):
        try:
            response = client.responses.create(
                model=model,
                instructions=admin_prompt,
                input=current_input,
                tools=ADMIN_TOOLS,
            )
        except RuntimeError:
            raise
        except Exception as exc:
            raise AIServiceError(f"AI admin chat request failed: {exc}") from exc

        _log_usage(model, "admin_chat", response, user_id=user_id)

        output = getattr(response, "output", None) or []
        tool_calls = [item for item in output if getattr(item, "type", None) == "function_call"]

        if not tool_calls:
            return extract_response_text(response)

        tool_results = []

        def _execute_tools(tool_session) -> list[dict]:
            results = []
            for tc in tool_calls:
                tool_name = getattr(tc, "name", "")
                call_id = getattr(tc, "call_id", "")
                raw_args = getattr(tc, "arguments", "{}")
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    result = execute_tool(tool_session, tool_name, args)
                    logger.info("admin_tool: executed tool=%s args=%s", tool_name, args)
                except Exception as exc:
                    logger.error("admin_tool: tool %s failed: %s", tool_name, exc)
                    result = json.dumps({"error": f"CHAT_A001: Tool execution failed: {exc}"})
                results.append({
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": result,
                })
            return results

        if db is not None:
            tool_results = _execute_tools(db)
        else:
            with session_scope() as tool_db:
                tool_results = _execute_tools(tool_db)

        current_input = list(output) + tool_results

    try:
        response = client.responses.create(
            model=model,
            instructions=admin_prompt,
            input=current_input,
        )
        _log_usage(model, "admin_chat", response, user_id=user_id)
        return extract_response_text(response)
    except Exception as exc:
        raise AIServiceError(f"AI admin chat final response failed: {exc}") from exc


def build_profile_extraction_response(message: str) -> str:
    return _invoke_ai(
        task_name="profile extraction",
        message=message,
        instructions=settings.PROFILE_EXTRACTION_SYSTEM_PROMPT,
    )


def build_portrait_summary_response(message: str) -> str:
    return _invoke_ai(
        task_name="portrait summary",
        message=message,
        instructions=settings.PORTRAIT_SUMMARY_SYSTEM_PROMPT,
    )


def build_goal_breakdown_response(message: str) -> str:
    return _invoke_ai(
        task_name="goal breakdown",
        message=message,
        instructions=settings.GOAL_BREAKDOWN_SYSTEM_PROMPT,
    )


def build_breakdown_summary_response(message: str) -> str:
    return _invoke_ai(
        task_name="breakdown summary",
        message=message,
        instructions=settings.BREAKDOWN_SUMMARY_SYSTEM_PROMPT,
    )


def build_growth_journal_response(message: str) -> str:
    return _invoke_ai(
        task_name="growth journal",
        message=message,
        instructions=settings.GROWTH_JOURNAL_SYSTEM_PROMPT,
    )


def build_weekly_summary_response(message: str) -> str:
    return _invoke_ai(
        task_name="weekly summary",
        message=message,
        instructions=settings.FEEDBACK_SUMMARY_SYSTEM_PROMPT,
    )


def build_instant_feedback_response(message: str) -> str:
    return _invoke_ai(
        task_name="instant feedback",
        message=message,
        instructions=settings.INSTANT_FEEDBACK_SYSTEM_PROMPT,
    )


def build_milestone_achievement_response(message: str) -> str:
    return _invoke_ai(
        task_name="milestone achievement",
        message=message,
        instructions=(
            "你是成长叙事助手。用 80-150 字中文描述用户达成该里程碑的意义与进展。"
            "不要输出 JSON、markdown 或标题；不要编造未给出的细节。"
        ),
    )


def build_growth_pattern_response(message: str) -> str:
    return _invoke_ai(
        task_name="growth pattern",
        message=message,
        instructions=settings.GROWTH_PATTERN_SYSTEM_PROMPT,
    )


def build_episodic_narrative_response(message: str) -> str:
    return _invoke_ai(
        task_name="episodic narrative",
        message=message,
        instructions=settings.EPISODIC_NARRATIVE_SYSTEM_PROMPT,
    )


def build_goal_intent_response(message: str) -> str:
    return _invoke_ai(
        task_name="goal intent",
        message=message,
        instructions=settings.GOAL_INTENT_SYSTEM_PROMPT,
    )


def build_memory_fact_extraction_response(message: str) -> str:
    return _invoke_ai(
        task_name="memory fact extraction",
        message=message,
        instructions=settings.MEMORY_FACT_EXTRACTION_SYSTEM_PROMPT,
    )


def create_embedding(text: str, *, db=None) -> list[float]:
    content = (text or "").strip()
    if not content:
        return []

    if not settings.EMBEDDING_MODEL:
        raise RuntimeError("EMBEDDING_MODEL is not configured")

    try:
        client = _get_ai_client(db)
        response = client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=content,
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise AIServiceError(f"AI embedding request failed: {exc}") from exc

    data = getattr(response, "data", None) or []
    if not data:
        raise AIServiceError("AI embedding response did not contain any vectors")

    embedding = getattr(data[0], "embedding", None)
    if not isinstance(embedding, list) or not embedding:
        raise AIServiceError("AI embedding response vector is empty")

    return [float(value) for value in embedding]


def build_action_plan_response(message: str) -> str:
    return _invoke_ai(
        task_name="action plan",
        message=message,
        instructions=settings.ACTION_PLAN_SYSTEM_PROMPT,
    )


def build_session_title_response(user_message: str, assistant_message: str) -> str:
    prompt = f"用户: {user_message.strip()}\n助手: {assistant_message.strip()}"
    return _invoke_ai(
        task_name="session title",
        message=prompt,
        instructions=settings.SESSION_TITLE_SYSTEM_PROMPT,
    )

