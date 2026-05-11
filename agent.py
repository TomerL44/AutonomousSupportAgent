"""
agent.py — LangGraph state machine for the autonomous support agent.

Graph nodes:
  1. classify   – Prepend system prompt & customer context, then call the LLM.
  2. tools      – Execute any tool calls the LLM requested.
  3. escalate   – Draft a human-handover summary when escalation is triggered.

Routing:
  • If the LLM response contains tool_calls  → route to *tools* node.
  • If any tool output contains "Escalation Required" → route to *escalate* node.
  • Otherwise → END (final answer).
"""

import os
from typing import Annotated, Literal

from dotenv import load_dotenv
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from tools import ALL_TOOLS

load_dotenv()

# ---------------------------------------------------------------------------
# LLM Initialisation (supports OpenAI or Ollama)
# ---------------------------------------------------------------------------

def _build_llm():
    provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if provider == "ollama":
        from langchain_community.chat_models import ChatOllama

        return ChatOllama(
            model=os.getenv("OLLAMA_MODEL", "llama3"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
    )


llm = _build_llm()
llm_with_tools = llm.bind_tools(ALL_TOOLS)

# ---------------------------------------------------------------------------
# Agent State
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    """Shared state flowing through the graph."""
    messages: Annotated[list, add_messages]
    customer_id: str
    current_intent: str
    traversal_path: list[str]      # debug log of visited nodes


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are an expert customer-support AI agent for an online retailer.

RULES YOU MUST FOLLOW:
1. NEVER guess or fabricate order statuses, customer details, or any data.
   Always call the appropriate tool first.
2. When answering about orders, you MUST call get_order_status before responding.
3. When answering about customer info, you MUST call get_customer_info first.
4. If a tool returns an error, relay the error politely to the customer.
5. If a refund is escalated, inform the customer that a human agent will review it.
6. Be concise, professional, and friendly.
7. If you don't know the answer or the query is outside your scope, say so clearly.
"""

# ---------------------------------------------------------------------------
# Node: classify (LLM call)
# ---------------------------------------------------------------------------

def classify(state: AgentState) -> dict:
    """Call the LLM with system prompt + conversation history."""
    path = list(state.get("traversal_path", []))
    path.append("Classifier")
    print(f"  ► Node: Classifier")

    messages = state["messages"]

    # Ensure the system prompt is always first
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    response = llm_with_tools.invoke(messages)

    # Detect intent from the response for logging
    intent = "direct_answer"
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_names = [tc["name"] for tc in response.tool_calls]
        intent = f"tool_call({', '.join(tool_names)})"

    return {
        "messages": [response],
        "current_intent": intent,
        "traversal_path": path,
    }


# ---------------------------------------------------------------------------
# Node: escalate (human handover)
# ---------------------------------------------------------------------------

def escalate(state: AgentState) -> dict:
    """Generate a human-handover summary when escalation is triggered."""
    path = list(state.get("traversal_path", []))
    path.append("Escalation")
    print(f"  ► Node: Escalation")

    # Build a summary of the conversation for the human agent
    escalation_summary = (
        "🚨 ESCALATION — This request requires human review.\n\n"
        f"Customer ID: {state.get('customer_id', 'Unknown')}\n"
        "Reason: A tool returned 'Escalation Required' (likely a refund "
        "exceeding the auto-approval threshold).\n\n"
        "The customer has been informed that a human agent will follow up."
    )
    print(f"  ⚠ {escalation_summary}")

    # Ask the LLM to compose a polite customer-facing response
    escalation_prompt = (
        "One of the tool results indicates an escalation is required. "
        "Please compose a polite response informing the customer that their "
        "request has been forwarded to a human agent for review and that "
        "someone will follow up shortly."
    )

    messages = list(state["messages"]) + [HumanMessage(content=escalation_prompt)]
    response = llm_with_tools.invoke(messages)

    return {
        "messages": [response],
        "current_intent": "escalation",
        "traversal_path": path,
    }


# ---------------------------------------------------------------------------
# Routing Logic
# ---------------------------------------------------------------------------

def should_continue(state: AgentState) -> Literal["tools", "escalate", "__end__"]:
    """Decide the next node after the classifier / LLM call."""
    last_message = state["messages"][-1]

    # If the LLM wants to call tools → route to tool node
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        print(f"  ↳ Routing → Tools")
        return "tools"

    print(f"  ↳ Routing → END")
    return "__end__"


def after_tools(state: AgentState) -> Literal["escalate", "classify"]:
    """After tools execute, check if any result requires escalation."""
    # Look at the most recent tool messages
    for msg in reversed(state["messages"]):
        if not isinstance(msg, ToolMessage):
            break
        if "Escalation Required" in (msg.content or ""):
            print(f"  ↳ Routing → Escalation (tool flagged escalation)")
            return "escalate"

    # Otherwise loop back to the LLM so it can synthesise a final answer
    print(f"  ↳ Routing → Classifier (synthesise answer)")
    return "classify"


# ---------------------------------------------------------------------------
# Tool Node (with traversal logging)
# ---------------------------------------------------------------------------

def tool_node_with_logging(state: AgentState) -> dict:
    """Run tools and log traversal."""
    path = list(state.get("traversal_path", []))

    # Identify which tools are being called
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tc in last_message.tool_calls:
            node_name = f"Tool({tc['name']})"
            path.append(node_name)
            print(f"  ► Node: {node_name}")

    # Delegate to LangGraph's built-in ToolNode
    tool_executor = ToolNode(ALL_TOOLS)
    result = tool_executor.invoke(state)

    # Merge traversal path into result
    if isinstance(result, dict):
        result["traversal_path"] = path
    return result


# ---------------------------------------------------------------------------
# Build & Compile Graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("classify", classify)
    graph.add_node("tools", tool_node_with_logging)
    graph.add_node("escalate", escalate)

    # Entry point
    graph.set_entry_point("classify")

    # Edges
    graph.add_conditional_edges("classify", should_continue, {
        "tools": "tools",
        "escalate": "escalate",
        "__end__": END,
    })
    graph.add_conditional_edges("tools", after_tools, {
        "escalate": "escalate",
        "classify": "classify",
    })
    graph.add_edge("escalate", END)

    return graph


# Compile once at module level for reuse
compiled_graph = build_graph().compile()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_agent(customer_id: str, message: str) -> dict:
    """
    Invoke the agent graph with a customer message.

    Returns:
        {
            "response": str,          # final AI message
            "traversal_path": [str],   # nodes visited
            "current_intent": str,     # detected intent
        }
    """
    print(f"\n{'='*60}")
    print(f"  Customer: {customer_id}  |  Message: {message}")
    print(f"{'='*60}")

    initial_state: AgentState = {
        "messages": [HumanMessage(content=message)],
        "customer_id": customer_id,
        "current_intent": "",
        "traversal_path": ["Input"],
    }

    final_state = compiled_graph.invoke(initial_state)

    # Extract the last AI message as the response
    ai_response = ""
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            ai_response = msg.content
            break

    traversal = final_state.get("traversal_path", []) + ["Output"]
    print(f"\n  Path: {' → '.join(traversal)}")
    print(f"{'='*60}\n")

    return {
        "response": ai_response,
        "traversal_path": traversal,
        "current_intent": final_state.get("current_intent", ""),
    }


# ---------------------------------------------------------------------------
# Quick smoke test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    result = run_agent("C001", "What is the status of my order ORD002?")
    print(f"\nAgent says:\n{result['response']}")
