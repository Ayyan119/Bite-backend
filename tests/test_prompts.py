from app.services.langgraph.prompts import (
    FALLBACK_SYSTEM_PROMPT,
    VISION_SYSTEM_PROMPT,
    format_fallback_prompt,
    format_vision_prompt,
)


def test_format_vision_prompt_with_caption():
    """Verify vision prompt includes user caption context."""
    prompt = format_vision_prompt("Grilled chicken salad with olive oil")
    assert "Grilled chicken salad with olive oil" in prompt
    assert "Rules:" in prompt


def test_format_vision_prompt_without_caption():
    """Verify vision prompt handles None or empty caption gracefully."""
    prompt = format_vision_prompt(None)
    assert "None provided" in prompt


def test_format_fallback_prompt_with_method():
    """Verify fallback prompt formats food name and cooking method."""
    prompt = format_fallback_prompt(food_name="Dragonfruit", cooking_method="raw")
    assert "Food Item: Dragonfruit" in prompt
    assert "Cooking Method: raw" in prompt


def test_format_fallback_prompt_default_method():
    """Verify fallback prompt defaults missing cooking method to raw/unknown."""
    prompt = format_fallback_prompt(food_name="Alien Berries", cooking_method=None)
    assert "Food Item: Alien Berries" in prompt
    assert "Cooking Method: raw/unknown" in prompt
