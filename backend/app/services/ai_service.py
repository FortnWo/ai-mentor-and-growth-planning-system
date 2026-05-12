from __future__ import annotations

from typing import Any

from openai import OpenAI

from app.core.config import settings


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


def _invoke_ai(*, task_name: str, message: str, instructions: str | None = None) -> str:
    try:
        client = _get_ai_client()
        response = client.responses.create(
            model=_get_model(),
            instructions=instructions,
            input=message.strip(),
        )
    except RuntimeError:
        raise
    except Exception as exc:
        raise AIServiceError(f"AI {task_name} request failed: {exc}") from exc

    return extract_response_text(response)


def build_chat_response(message: str, *, instructions: str | None = None) -> str:
    return _invoke_ai(
        task_name="chat",
        message=message,
        instructions=instructions if instructions is not None else (settings.LLM_SYSTEM_PROMPT or None),
    )


def build_profile_extraction_response(message: str) -> str:
    return _invoke_ai(
        task_name="profile extraction",
        message=message,
        instructions=settings.PROFILE_EXTRACTION_SYSTEM_PROMPT,
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

