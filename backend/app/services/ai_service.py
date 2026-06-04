from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger("ai_mentor.ai_service")


class AIServiceError(RuntimeError):
    """Raised when AI provider calls fail at the service layer."""


def _get_ai_client() -> OpenAI:
    if not settings.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not configured")
    if not settings.LLM_API_BASE_URL:
        raise RuntimeError("LLM_API_BASE_URL is not configured")

    return OpenAI(
        base_url=settings.LLM_API_BASE_URL,
        api_key=settings.LLM_API_KEY,
    )


def _get_model() -> str:
    if not settings.LLM_MODEL:
        raise RuntimeError("LLM_MODEL is not configured")
    return settings.LLM_MODEL


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


def _invoke_ai(*, task_name: str, message: str, instructions: str | None = None, user_id: int | None = None) -> str:
    try:
        client = _get_ai_client()
        model = _get_model()
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
    return extract_response_text(response)


def build_chat_response(
    message: str,
    *,
    instructions: str | None = None,
    user_id: int | None = None,
) -> str:
    return _invoke_ai(
        task_name="chat",
        message=message,
        instructions=instructions if instructions is not None else (settings.LLM_SYSTEM_PROMPT or None),
        user_id=user_id,
    )


_ADMIN_DEFAULT_SYSTEM_PROMPT = (
    "你是一个专业全能的系统管理助手。"
    "你可以通过工具查询系统数据库、获取日志和统计信息，用自然语言为管理员提供精准答复。"
    "回答要简洁专业，数据准确。禁止执行任何写操作或 DDL 语句。"
)


def build_admin_chat_response(message: str, db=None, *, user_id: int | None = None) -> str:
    """
    Admin chat: uses admin system prompt + DB query tools.
    Supports multi-turn tool calling loop.
    db: optional SQLAlchemy Session for tool execution.
    user_id: session owner for ai_usage_logs attribution.
    """
    from app.services.admin_tool_service import ADMIN_TOOLS, execute_tool

    admin_prompt = getattr(settings, "ADMIN_LLM_SYSTEM_PROMPT", None) or _ADMIN_DEFAULT_SYSTEM_PROMPT

    try:
        client = _get_ai_client()
        model = _get_model()
    except RuntimeError:
        raise

    MAX_TOOL_ROUNDS = 5
    current_input: str | list = message.strip()

    for round_num in range(MAX_TOOL_ROUNDS):
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

        # Check for tool_use items in output
        output = getattr(response, "output", None) or []
        tool_calls = [item for item in output if getattr(item, "type", None) == "function_call"]

        if not tool_calls:
            return extract_response_text(response)

        # Execute all tool calls and build tool results
        if db is None:
            logger.warning("admin_chat: tool call requested but no db session provided")
            return extract_response_text(response)

        tool_results = []
        for tc in tool_calls:
            tool_name = getattr(tc, "name", "")
            call_id = getattr(tc, "call_id", "")
            raw_args = getattr(tc, "arguments", "{}")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                result = execute_tool(db, tool_name, args)
                logger.info("admin_tool: executed tool=%s args=%s", tool_name, args)
            except Exception as exc:
                logger.error("admin_tool: tool %s failed: %s", tool_name, exc)
                result = json.dumps({"error": f"CHAT_A001: Tool execution failed: {exc}"})

            tool_results.append({
                "type": "function_call_output",
                "call_id": call_id,
                "output": result,
            })

        # For next round, pass current output + tool results
        current_input = list(output) + tool_results

    # Exceeded max rounds — fall through to final response
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


def build_action_plan_response(message: str) -> str:
    return _invoke_ai(
        task_name="action plan",
        message=message,
        instructions=settings.ACTION_PLAN_SYSTEM_PROMPT,
    )


def build_session_title_response(user_message: str, assistant_message: str) -> str:
    prompt = f"User: {user_message.strip()}\nAssistant: {assistant_message.strip()}"
    return _invoke_ai(
        task_name="session title",
        message=prompt,
        instructions=settings.SESSION_TITLE_SYSTEM_PROMPT,
    )

