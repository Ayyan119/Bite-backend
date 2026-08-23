"""Multimodal Vision Extraction Node for LangGraph Ingestion Pipeline using OpenAI."""

from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings, validate_image_input
from app.schemas.ingestion import IngestionState, VisionAnalysisResult, VisionItem
from app.services.langgraph.prompts import format_vision_prompt


def get_vision_llm() -> ChatOpenAI:
    """Instantiate OpenAI Vision LLM instance."""
    api_key = settings.OPENAI_API_KEY or "dummy_key"
    return ChatOpenAI(
        model=settings.VISION_LLM_MODEL,
        api_key=api_key,
        temperature=0.1,
    )


async def vision_extraction_node(
    state: IngestionState, llm: Optional[Any] = None
) -> Dict[str, Any]:
    """LangGraph node for Multimodal Food Vision extraction using OpenAI."""
    errors: List[str] = list(state.get("errors", []))

    try:
        image_url = validate_image_input(
            image_bytes=state.get("image_bytes"),
            image_url=state.get("image_url"),
        )
        user_caption = state.get("user_caption")
        prompt = format_vision_prompt(user_caption)
        message = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]
        )

        model = llm or get_vision_llm()
        structured_llm = model.with_structured_output(
            VisionAnalysisResult, method="function_calling"
        )
        result: VisionAnalysisResult = await structured_llm.ainvoke([message])

        # Strict non-food enforcement
        if not result.is_food or not result.detected_items:
            errors.append("No valid food items identified in the image.")
            return {
                "detected_items": [],
                "vision_confidence": 0.0,
                "errors": errors,
            }

        # Caption mismatch enforcement (< 0.6 match score)
        if user_caption and result.caption_match_score < 0.6:
            reason = (
                result.caption_mismatch_reason
                or f"User caption '{user_caption}' does not match visual content (match score {result.caption_match_score:.2f} < 0.6)."
            )
            errors.append(f"Caption Mismatch Warning: {reason}")

        detected_items: List[VisionItem] = [
            {
                "food_name": item.food_name,
                "portion_estimate": item.portion_estimate,
                "gram_weight": item.gram_weight,
                "cooking_method": item.cooking_method or "raw",
            }
            for item in result.detected_items
        ]

        return {
            "detected_items": detected_items,
            "vision_confidence": result.confidence_score,
            "errors": errors,
        }
    except Exception as exc:
        errors.append(f"Vision extraction failed: {str(exc)}")
        return {
            "detected_items": [],
            "vision_confidence": 0.0,
            "errors": errors,
        }
