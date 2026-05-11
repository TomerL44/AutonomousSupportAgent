# Autonomous Support Agent

A stateful, autonomous customer-support AI agent powered by **LangGraph**, **LangChain**, and **FastAPI**.

## Architecture

```
Customer Message
       │
       ▼
  ┌──────────┐
  │  Input    │  (Accept JSON: customer_id + message)
  └────┬─────┘
       │
       ▼
  ┌──────────────┐
  │  Classifier   │  (LLM decides: answer directly or call tools)
  └──┬────────┬──┘
     │        │
  has tools   no tools
     │        │
     ▼        ▼
  ┌───────┐  END
  │ Tools │  (execute DB queries / mutations)
  └──┬────┘
     │
     ├── escalation? ──► Escalation Node ──► END
     │
     └── otherwise ──► Classifier (synthesise final answer) ──► END
```

## Quick Start

```bash
# 1. Create & activate virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env
# Edit .env with your OPENAI_API_KEY

# 4. Initialise database
python db_setup.py

# 5. Run the server
uvicorn main:app --reload --port 8000
```

## API Usage

### POST /chat

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "C001", "message": "Where is my order ORD002?"}'
```

**Response:**
```json
{
  "response": "Your order ORD002 is currently being processed ...",
  "traversal_path": ["Input", "Classifier", "Tool(get_order_status)", "Classifier", "Output"],
  "current_intent": "tool_call(get_order_status)"
}
```

### GET /health
```bash
curl http://localhost:8000/health
```

## Available Tools

| Tool | Description |
|------|-------------|
| `get_customer_info` | Retrieve customer name, email, loyalty tier |
| `get_order_status` | Check order status, amount, and shipping address |
| `update_shipping_address` | Update address (only if order is "Processing") |
| `process_refund` | Process refund (escalates if amount > $50) |

## Edge Cases Handled

- **Hallucination Prevention**: Agent always calls tools before answering data questions
- **Shipped Order Guard**: Address updates rejected for non-Processing orders
- **Refund Escalation**: Amounts > $50 trigger human escalation
- **Traversal Logging**: Full graph path printed to console for debugging
