"""LangGraph Ingestion Workflow Definition & Compiled Runnable Graph."""

from typing import Literal
from langgraph.graph import END, START, StateGraph

from app.schemas.ingestion import IngestionState
from app.services.langgraph.fallback_node import fallback_node
from app.services.langgraph.scale_node import reconciliation_node
from app.services.langgraph.usda_node import usda_resolver_node
from app.services.langgraph.vision_node import vision_extraction_node


def check_fallback_needed(
    state: IngestionState,
) -> Literal["fallback", "reconciliation"]:
    """Determine whether any food item requires LLM fallback macro estimation."""
    detected_items = state.get("detected_items", [])
    usda_matches = state.get("usda_matches", {})

    if not detected_items:
        return "reconciliation"

    for item in detected_items:
        food_name = item["food_name"]
        if usda_matches.get(food_name) is None:
            return "fallback"

    return "reconciliation"


def build_ingestion_graph() -> StateGraph:
    """Build and assemble the Food Vision & USDA Resolver ingestion workflow graph."""
    builder = StateGraph(IngestionState)

    # Add Nodes
    builder.add_node("vision_extraction", vision_extraction_node)
    builder.add_node("usda_resolver", usda_resolver_node)
    builder.add_node("fallback", fallback_node)
    builder.add_node("reconciliation", reconciliation_node)

    # Add Edges & Conditional Routing
    builder.add_edge(START, "vision_extraction")
    builder.add_edge("vision_extraction", "usda_resolver")
    builder.add_conditional_edges(
        "usda_resolver",
        check_fallback_needed,
        {
            "fallback": "fallback",
            "reconciliation": "reconciliation",
        },
    )
    builder.add_edge("fallback", "reconciliation")
    builder.add_edge("reconciliation", END)

    return builder


# Compile runnable graph instance
ingestion_graph = build_ingestion_graph().compile()
