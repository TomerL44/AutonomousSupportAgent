"""
streamlit_app.py — Chat UI for the Autonomous Support Agent.

Run with:
    streamlit run streamlit_app.py

Does NOT require the FastAPI server — it calls run_agent() directly.
"""

import streamlit as st
from database import create_tables, seed_database, SessionLocal, Customer, Order
from agent import run_agent

# ---------------------------------------------------------------------------
# Page Config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Support Agent",
    page_icon="🤖",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom CSS — clean dark-mode look
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* ── General ─────────────────────────────── */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Sidebar ─────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid #1e293b;
    }
    section[data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }

    /* ── Main area ───────────────────────────── */
    .main { background: #0f172a; }

    /* ── Chat bubbles ────────────────────────── */
    .bubble-user {
        background: #1e40af;
        color: #fff;
        border-radius: 18px 18px 4px 18px;
        padding: 12px 16px;
        margin: 6px 0;
        max-width: 72%;
        float: right;
        clear: both;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    .bubble-agent {
        background: #1e293b;
        color: #e2e8f0;
        border-radius: 18px 18px 18px 4px;
        padding: 12px 16px;
        margin: 6px 0;
        max-width: 72%;
        float: left;
        clear: both;
        font-size: 0.95rem;
        line-height: 1.5;
        border: 1px solid #334155;
    }
    .clearfix { clear: both; }

    /* ── Traversal badge ─────────────────────── */
    .traversal {
        font-size: 0.72rem;
        color: #64748b;
        font-family: monospace;
        margin: 2px 0 12px 4px;
        clear: both;
    }

    /* ── Customer card ───────────────────────── */
    .customer-card {
        background: #1e293b;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 14px 16px;
        margin-top: 16px;
    }
    .customer-card h4 { margin: 0 0 6px 0; font-size: 1rem; color: #f1f5f9; }
    .customer-card p  { margin: 2px 0; font-size: 0.82rem; color: #94a3b8; }
    .tier-gold   { color: #f59e0b !important; font-weight: 700; }
    .tier-silver { color: #94a3b8 !important; font-weight: 700; }
    .tier-bronze { color: #b45309 !important; font-weight: 700; }

    /* ── Order pill ──────────────────────────── */
    .order-pill {
        display: inline-block;
        font-size: 0.75rem;
        border-radius: 99px;
        padding: 2px 10px;
        margin: 3px 3px 3px 0;
        font-weight: 600;
    }
    .status-Processing { background:#0c4a6e; color:#38bdf8; }
    .status-Shipped    { background:#14532d; color:#4ade80; }
    .status-Delivered  { background:#1e1b4b; color:#a78bfa; }

    /* ── Header ──────────────────────────────── */
    .page-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 24px;
        padding-bottom: 16px;
        border-bottom: 1px solid #1e293b;
    }
    .page-header h1 { font-size: 1.5rem; margin: 0; color: #f1f5f9; }
    .page-header p  { margin: 0; color: #64748b; font-size: 0.85rem; }
    </style>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# DB bootstrap (idempotent — safe to call every run)
# ---------------------------------------------------------------------------
@st.cache_resource
def bootstrap_db():
    create_tables()
    seed_database()

bootstrap_db()

# ---------------------------------------------------------------------------
# Helpers to load DB data
# ---------------------------------------------------------------------------
@st.cache_data
def load_customers() -> list[dict]:
    db = SessionLocal()
    try:
        return [c.to_dict() for c in db.query(Customer).all()]
    finally:
        db.close()


def load_orders_for(customer_id: str) -> list[dict]:
    db = SessionLocal()
    try:
        return [o.to_dict() for o in db.query(Order).filter(Order.customer_id == customer_id).all()]
    finally:
        db.close()


TIER_CLASS = {"Gold": "tier-gold", "Silver": "tier-silver", "Bronze": "tier-bronze"}
STATUS_CLASS = {"Processing": "status-Processing", "Shipped": "status-Shipped", "Delivered": "status-Delivered"}

# ---------------------------------------------------------------------------
# Session State Defaults
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []   # list of {"role": "user"|"agent", "content": str, "path": list}

if "selected_customer" not in st.session_state:
    st.session_state.selected_customer = None

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
customers = load_customers()
customer_map = {f"{c['id']} — {c['name']}": c for c in customers}

with st.sidebar:
    st.markdown("## 🤖 Support Agent")
    st.markdown("---")
    st.markdown("### Select Customer")

    choice = st.selectbox(
        "Customer",
        options=list(customer_map.keys()),
        label_visibility="collapsed",
    )
    selected = customer_map[choice]

    # Switch customer → clear chat history
    if st.session_state.selected_customer != selected["id"]:
        st.session_state.selected_customer = selected["id"]
        st.session_state.messages = []

    # Customer card
    tier_cls = TIER_CLASS.get(selected["loyalty_tier"], "")
    st.markdown(
        f"""
        <div class="customer-card">
            <h4>{selected['name']}</h4>
            <p>📧 {selected['email']}</p>
            <p>Tier: <span class="{tier_cls}">{selected['loyalty_tier']}</span></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Orders
    st.markdown("#### Orders")
    orders = load_orders_for(selected["id"])
    if orders:
        for o in orders:
            sc = STATUS_CLASS.get(o["status"], "")
            st.markdown(
                f'<span class="order-pill {sc}">{o["id"]} · {o["status"]}</span> '
                f'<span style="font-size:0.78rem; color:#64748b;">${o["total_amount"]:.2f}</span>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("No orders found.")

    st.markdown("---")
    if st.button("🗑 Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.caption("Powered by LangGraph · FastAPI · Ollama")

# ---------------------------------------------------------------------------
# Main — Header
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="page-header">
        <div>
            <h1>💬 Customer Support Chat</h1>
            <p>Chatting as <strong>{selected['name']}</strong> ({selected['id']})</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Chat History
# ---------------------------------------------------------------------------
chat_container = st.container()

with chat_container:
    if not st.session_state.messages:
        st.markdown(
            "<p style='color:#475569; text-align:center; margin-top:60px;'>"
            "👋 Start by typing a message below.</p>",
            unsafe_allow_html=True,
        )

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="bubble-user">{msg["content"]}</div>'
                f'<div class="clearfix"></div>',
                unsafe_allow_html=True,
            )
        else:
            path_str = " → ".join(msg.get("path", []))
            st.markdown(
                f'<div class="bubble-agent">{msg["content"]}</div>'
                f'<div class="clearfix"></div>'
                f'<div class="traversal">🔀 {path_str}</div>',
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# Input Box
# ---------------------------------------------------------------------------
st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

with st.form("chat_form", clear_on_submit=True):
    col1, col2 = st.columns([6, 1])
    with col1:
        user_input = st.text_input(
            "Message",
            placeholder="e.g. Where is my order ORD002? Can I get a refund?",
            label_visibility="collapsed",
        )
    with col2:
        submitted = st.form_submit_button("Send ➤", use_container_width=True)

if submitted and user_input.strip():
    # Append user message
    st.session_state.messages.append({"role": "user", "content": user_input.strip()})

    # Call the agent
    with st.spinner("Agent is thinking …"):
        result = run_agent(
            customer_id=st.session_state.selected_customer,
            message=user_input.strip(),
        )

    # Append agent response
    st.session_state.messages.append({
        "role": "agent",
        "content": result["response"],
        "path": result.get("traversal_path", []),
    })

    st.rerun()
