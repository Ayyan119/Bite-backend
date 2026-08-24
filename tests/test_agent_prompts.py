from datetime import datetime
import pytest
from app.services.langgraph_of_chatbot.agent_prompts import build_system_prompt


def test_build_system_prompt_structure():
    """Verify system prompt temporal formatting, regional fallback, and edibility rules."""
    fixed_now = datetime(2026, 8, 24, 14, 30, 0)
    long_term = "Daily Target: 2000 kcal | Protein: 150g"
    short_term = "User logged breakfast earlier."

    prompt = build_system_prompt(
        long_term_context=long_term,
        short_term_summary=short_term,
        now=fixed_now,
    )

    assert "2026-08-24 14:30:00" in prompt
    assert "Monday" in prompt
    assert long_term in prompt
    assert short_term in prompt
    assert "REGIONAL & CULTURAL DISH LLM FALLBACK STRATEGY" in prompt
    assert "cholay / chana masala" in prompt
    assert "is_fallback: True" in prompt
    assert "laptop" in prompt
