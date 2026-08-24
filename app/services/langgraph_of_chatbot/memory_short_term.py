import asyncio
import logging
from typing import Any, Callable, List, Sequence
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_openai import ChatOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# Configuration constants
SUMMARIZATION_THRESHOLD_USER_MESSAGES = 10
DEFAULT_WINDOW_SIZE = 4


def get_trimmed_messages(
    messages: Sequence[BaseMessage], max_messages: int = DEFAULT_WINDOW_SIZE
) -> List[BaseMessage]:
    """
    Slices and retains the latest `max_messages` from conversation history.
    Preserves any leading SystemMessage if present.
    """
    if not messages:
        return []

    system_msgs = [m for m in messages if isinstance(m, SystemMessage)]
    non_system_msgs = [m for m in messages if not isinstance(m, SystemMessage)]

    trimmed_non_system = (
        non_system_msgs[-max_messages:]
        if len(non_system_msgs) > max_messages
        else non_system_msgs
    )
    return system_msgs + trimmed_non_system


def count_user_messages(messages: Sequence[BaseMessage]) -> int:
    """Counts the number of HumanMessage instances in the message history."""
    return sum(1 for m in messages if isinstance(m, HumanMessage))


async def summarize_history_async(
    messages: Sequence[BaseMessage],
    existing_summary: str = "",
) -> str:
    """
    Summarizes older conversation messages asynchronously using LLM.
    """
    if not messages:
        return existing_summary

    try:
        api_key = settings.OPENAI_API_KEY or "dummy_key"
        llm = ChatOpenAI(
            model=settings.FAST_LLM_MODEL,
            api_key=api_key,
            temperature=0.2,
        )
        prompt = (
            "Summarize the following nutrition chat conversation history concisely. "
            "Focus on logged meals, dietary restrictions, and caloric goals. Keep under 150 words.\n\n"
            f"Existing Summary:\n{existing_summary or 'None'}\n\n"
            "New Messages to Summarize:\n"
            + "\n".join(f"{m.type.capitalize()}: {m.content}" for m in messages)
        )
        response = await llm.ainvoke(prompt)
        return str(response.content).strip()
    except Exception as e:
        logger.error(f"Error during background history summarization: {e}")
        return existing_summary


def maybe_trigger_background_summarization(
    messages: Sequence[BaseMessage],
    existing_summary: str = "",
    on_summary_complete: Callable[[str], Any] | None = None,
    threshold: int = SUMMARIZATION_THRESHOLD_USER_MESSAGES,
    window_size: int = DEFAULT_WINDOW_SIZE,
) -> bool:
    """
    Checks if user message count exceeds threshold (>10 user messages).
    If triggered, launches summarize_history_async via asyncio.create_task (non-blocking).
    Returns True if background summarization task was spawned, False otherwise.
    """
    user_count = count_user_messages(messages)
    if user_count <= threshold:
        return False

    non_system_msgs = [m for m in messages if not isinstance(m, SystemMessage)]
    older_messages = (
        non_system_msgs[:-window_size] if len(non_system_msgs) > window_size else []
    )

    if not older_messages:
        return False

    async def _background_summarizer_task():
        summary = await summarize_history_async(older_messages, existing_summary)
        if on_summary_complete and summary:
            try:
                res = on_summary_complete(summary)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as ex:
                logger.error(f"Error executing on_summary_complete callback: {ex}")

    asyncio.create_task(_background_summarizer_task())
    return True
