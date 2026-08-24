import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Sequence, TypedDict
from typing_extensions import Annotated
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tracers.context import tracing_v2_enabled
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from app.core.config import settings
from app.services.langgraph_of_chatbot.checkpointer import (
    get_checkpointer,
    prefetch_memory_parallel,
)
from app.services.langgraph_of_chatbot.memory_short_term import (
    get_trimmed_messages,
    maybe_trigger_background_summarization,
)
from app.services.langgraph_of_chatbot.memory_long_term import (
    format_long_term_context,
    maybe_trigger_long_term_extraction,
)
from app.services.langgraph_of_chatbot.usda_tool import search_usda_food
from app.services.langgraph_of_chatbot.db_tools import (
    current_user_id_var,
    log_meal,
    get_daily_summary,
    get_micronutrient_total,
    update_meal_item,
    delete_meal_log,
)
from app.services.langgraph_of_chatbot.agent_prompts import build_system_prompt
from app.services.langgraph_of_chatbot.action_status_streamer import (
    parse_and_stream_astream_events,
)

logger = logging.getLogger(__name__)

# Complete list of 6 tenant-isolated agent tools
CHATBOT_TOOLS = [
    search_usda_food,
    log_meal,
    get_daily_summary,
    get_micronutrient_total,
    update_meal_item,
    delete_meal_log,
]


class ChatAgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    long_term_context: str
    short_term_summary: str
    user_id: str


async def agent_node(
    state: ChatAgentState, config: Optional[RunnableConfig] = None
) -> Dict[str, Any]:
    """Conversational agent decision node.

    Injects dynamic dates, long-term context, and trimmed history window into system prompt,
    then invokes ChatOpenAI bound with all 6 tools.
    """
    messages = state.get("messages", [])
    user_id = state.get("user_id") or (
        config.get("configurable", {}).get("user_id", "") if config else ""
    )
    long_term_context = state.get("long_term_context", "")
    short_term_summary = state.get("short_term_summary", "")

    # Slice history window to latest 4 messages + SystemPrompt
    trimmed_messages = get_trimmed_messages(messages, max_messages=4)
    sys_prompt = build_system_prompt(
        long_term_context=long_term_context,
        short_term_summary=short_term_summary,
    )

    full_messages = [SystemMessage(content=sys_prompt)] + [
        m for m in trimmed_messages if not isinstance(m, SystemMessage)
    ]

    api_key = settings.OPENAI_API_KEY or "dummy_key"
    llm = ChatOpenAI(
        model=settings.FAST_LLM_MODEL,
        api_key=api_key,
        temperature=0.2,
    )
    llm_with_tools = llm.bind_tools(CHATBOT_TOOLS)

    response = await llm_with_tools.ainvoke(full_messages, config=config)

    # Non-blocking background memory triggers
    maybe_trigger_background_summarization(
        messages, existing_summary=short_term_summary
    )
    if user_id:
        maybe_trigger_long_term_extraction(messages, user_id=user_id)

    return {"messages": [response]}


def build_chatbot_graph() -> StateGraph:
    """Constructs the LangGraph StateGraph machine for Project Bite Chatbot Workflow 2."""
    workflow = StateGraph(ChatAgentState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", ToolNode(CHATBOT_TOOLS))

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", tools_condition, ["tools", END])
    workflow.add_edge("tools", "agent")

    return workflow


_compiled_graph = None


async def get_compiled_chatbot_graph(checkpointer: Any = None):
    """Returns singleton compiled StateGraph with AsyncPostgresSaver checkpointer."""
    global _compiled_graph
    if _compiled_graph is None:
        cp = checkpointer or await get_checkpointer()
        workflow = build_chatbot_graph()
        _compiled_graph = workflow.compile(checkpointer=cp)
    return _compiled_graph


async def stream_chatbot_response(
    user_input: str,
    user_id: str,
    thread_id: str,
    profile_data: Optional[Dict[str, Any]] = None,
) -> AsyncGenerator[str, None]:
    """Executes compiled chatbot graph with SSE streaming (astream_events v2).

    Routes LangSmith traces to user-specific project 'Bite-{user_id}-{user_name}'
    and maintains separate session threads via thread_id.
    """
    # Bind ContextVar for sub-second tool execution
    token = current_user_id_var.set(user_id)
    try:
        graph = await get_compiled_chatbot_graph()

        user_name = (
            (profile_data.get("display_name") or "user").strip().replace(" ", "_")
            if profile_data
            else "user"
        )
        project_name = f"Bite-{user_id}-{user_name}"

        config: RunnableConfig = {
            "configurable": {
                "thread_id": f"thread_{thread_id}",
                "user_id": user_id,
            },
            "metadata": {
                "user_id": user_id,
                "user_name": user_name,
                "thread_id": thread_id,
            },
            "tags": [
                f"user_id:{user_id}",
                f"user_name:{user_name}",
                f"thread:{thread_id}",
            ],
            "project_name": project_name,
        }

        long_term_context = format_long_term_context(profile_data)

        initial_input = {
            "messages": [HumanMessage(content=user_input)],
            "long_term_context": long_term_context,
            "short_term_summary": "",
            "user_id": user_id,
        }

        with tracing_v2_enabled(project_name=project_name):
            events_gen = graph.astream_events(
                initial_input, config=config, version="v2"
            )

            async for sse_chunk in parse_and_stream_astream_events(events_gen):
                yield sse_chunk
    finally:
        current_user_id_var.reset(token)
