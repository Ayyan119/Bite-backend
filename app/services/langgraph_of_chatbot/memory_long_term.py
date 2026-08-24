import asyncio
import json
import logging
from typing import Any, Callable, Dict, Sequence
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)


def format_long_term_context(profile: Dict[str, Any] | None) -> str:
    """
    Formats user profile goals and long-term facts into a system prompt section in <0.1ms.
    """
    if not profile:
        return "No specific long-term profile data recorded yet."

    lines = ["### User Profile & Long-Term Memory Context:"]

    if profile.get("display_name"):
        lines.append(f"- Name / Display Name: {profile['display_name']}")

    # Caloric & Macro Targets
    targets = []
    if profile.get("target_calories"):
        targets.append(f"{profile['target_calories']} kcal")
    if profile.get("target_protein_g"):
        targets.append(f"Protein: {profile['target_protein_g']}g")
    if profile.get("target_carbs_g"):
        targets.append(f"Carbs: {profile['target_carbs_g']}g")
    if profile.get("target_fat_g"):
        targets.append(f"Fat: {profile['target_fat_g']}g")
    if targets:
        lines.append(f"- Daily Targets: {' | '.join(targets)}")

    # Long-term memory JSONB facts
    lt_memory = profile.get("long_term_memory") or {}
    if isinstance(lt_memory, str):
        try:
            lt_memory = json.loads(lt_memory)
        except Exception:
            lt_memory = {}

    allergies = lt_memory.get("allergies", [])
    if allergies:
        lines.append(f"- Allergies: {', '.join(allergies)}")

    dietary_preferences = lt_memory.get("dietary_preferences", [])
    if dietary_preferences:
        lines.append(f"- Dietary Preferences: {', '.join(dietary_preferences)}")

    disliked_foods = lt_memory.get("disliked_foods", [])
    if disliked_foods:
        lines.append(f"- Disliked Foods: {', '.join(disliked_foods)}")

    notes = lt_memory.get("notes", [])
    if notes:
        lines.append(f"- Additional Facts: {', '.join(notes)}")

    if len(lines) == 1:
        return "No specific long-term memory facts recorded."

    return "\n".join(lines)


async def extract_long_term_facts_async(
    messages: Sequence[BaseMessage], existing_facts: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    """
    Asynchronously extracts user long-term facts (allergies, preferences, goals) from recent messages.
    """
    existing_facts = existing_facts or {}
    human_messages = [m.content for m in messages if isinstance(m, HumanMessage)]
    if not human_messages:
        return existing_facts

    try:
        api_key = settings.OPENAI_API_KEY or "dummy_key"
        llm = ChatOpenAI(
            model=settings.FAST_LLM_MODEL,
            api_key=api_key,
            temperature=0.1,
        )
        prompt = (
            "Analyze the user's messages for personal dietary facts, allergies, food preferences, "
            "or caloric goals. Return ONLY a raw JSON object with keys: "
            "'allergies' (list of str), 'dietary_preferences' (list of str), "
            "'disliked_foods' (list of str), 'notes' (list of str).\n\n"
            f"Existing Facts:\n{json.dumps(existing_facts)}\n\n"
            f"User Messages:\n" + "\n".join(human_messages)
        )
        response = await llm.ainvoke(prompt)
        text = str(response.content).strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        extracted = json.loads(text)
        merged = {
            "allergies": list(
                set(
                    existing_facts.get("allergies", []) + extracted.get("allergies", [])
                )
            ),
            "dietary_preferences": list(
                set(
                    existing_facts.get("dietary_preferences", [])
                    + extracted.get("dietary_preferences", [])
                )
            ),
            "disliked_foods": list(
                set(
                    existing_facts.get("disliked_foods", [])
                    + extracted.get("disliked_foods", [])
                )
            ),
            "notes": list(
                set(existing_facts.get("notes", []) + extracted.get("notes", []))
            ),
        }
        return merged
    except Exception as e:
        logger.error(f"Error during long-term memory fact extraction: {e}")
        return existing_facts


def maybe_trigger_long_term_extraction(
    messages: Sequence[BaseMessage],
    user_id: str,
    existing_facts: Dict[str, Any] | None = None,
    save_facts_callback: Callable[[str, Dict[str, Any]], Any] | None = None,
) -> bool:
    """
    Non-blocking background launcher (asyncio.create_task) for long-term fact extraction.
    Returns True if background task was launched, False otherwise.
    """
    human_messages = [m for m in messages if isinstance(m, HumanMessage)]
    if not human_messages:
        return False

    async def _bg_extractor_task():
        new_facts = await extract_long_term_facts_async(messages, existing_facts)
        if save_facts_callback and new_facts != existing_facts:
            try:
                res = save_facts_callback(user_id, new_facts)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as ex:
                logger.error(f"Error executing save_facts_callback: {ex}")

    asyncio.create_task(_bg_extractor_task())
    return True
