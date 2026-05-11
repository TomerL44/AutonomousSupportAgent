"""
main.py — FastAPI application exposing the autonomous support agent.

Endpoints:
  POST /chat  — Send a customer message and get the agent's response.
  GET  /health — Liveness probe.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import create_tables, seed_database
from agent import run_agent


# ---------------------------------------------------------------------------
# Lifespan: initialise DB on startup
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    print("🚀 Initialising database …")
    create_tables()
    seed_database()
    print("✅ Agent is ready.\n")
    yield


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Autonomous Support Agent",
    description=(
        "A stateful, autonomous customer-support AI agent powered by "
        "LangGraph. It can query customers, check order statuses, update "
        "shipping addresses, process refunds, and escalate complex requests."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    customer_id: str = Field(..., examples=["C001"], description="Unique customer identifier.")
    message: str = Field(..., examples=["Where is my order ORD002?"], description="Customer's message.")


class ChatResponse(BaseModel):
    response: str = Field(..., description="AI agent's reply to the customer.")
    traversal_path: list[str] = Field(
        default_factory=list,
        description="Nodes visited during graph execution (for debugging).",
    )
    current_intent: str = Field(default="", description="Detected intent of the message.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/chat", response_model=ChatResponse, tags=["Agent"])
async def chat(request: ChatRequest):
    """
    Send a customer query to the autonomous support agent.

    The agent will:
    1. Classify the message intent.
    2. Optionally call tools (DB lookups, mutations).
    3. Synthesise a natural-language response.
    4. Escalate to a human if needed.
    """
    result = run_agent(customer_id=request.customer_id, message=request.message)
    return ChatResponse(**result)


@app.get("/health", tags=["System"])
async def health():
    """Liveness / readiness probe."""
    return {"status": "healthy", "service": "autonomous-support-agent"}
