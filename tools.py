"""
tools.py — LangChain tools the agent can invoke.

Each tool interacts with the SQLite database via SQLAlchemy and is
decorated with @tool so LangChain can bind it to the LLM.
"""

from langchain_core.tools import tool
from database import SessionLocal, Customer, Order


# ---------------------------------------------------------------------------
# 1. Get Customer Info
# ---------------------------------------------------------------------------
@tool
def get_customer_info(customer_id: str) -> dict:
    """Retrieve customer details (name, loyalty tier, email) by customer ID.

    Args:
        customer_id: The unique customer identifier, e.g. 'C001'.

    Returns:
        A dict with customer info or an error message.
    """
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {"error": f"No customer found with ID '{customer_id}'."}
        return customer.to_dict()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 2. Get Order Status
# ---------------------------------------------------------------------------
@tool
def get_order_status(order_id: str) -> dict:
    """Retrieve the shipping status, total amount, and shipping address for a given order.

    Args:
        order_id: The unique order identifier, e.g. 'ORD001'.

    Returns:
        A dict with order details or an error message.
    """
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return {"error": f"No order found with ID '{order_id}'."}
        return order.to_dict()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 3. Update Shipping Address
# ---------------------------------------------------------------------------
@tool
def update_shipping_address(order_id: str, new_address: str) -> str:
    """Update the shipping address for an order.

    This is only allowed while the order status is 'Processing'.
    If the order has already been shipped or delivered, the update is refused.

    Args:
        order_id: The unique order identifier.
        new_address: The new shipping address string.

    Returns:
        A confirmation message or an error explaining why the update failed.
    """
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return f"Error: No order found with ID '{order_id}'."

        if order.status != "Processing":
            return (
                f"Error: Cannot update shipping address — order {order_id} "
                f"is currently '{order.status}'. Address changes are only "
                f"allowed while an order is still 'Processing'."
            )

        order.shipping_address = new_address
        db.commit()
        return f"Success: Shipping address for order {order_id} updated to '{new_address}'."
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 4. Process Refund
# ---------------------------------------------------------------------------
@tool
def process_refund(order_id: str, amount: float) -> str:
    """Process a refund for a given order.

    If the refund amount exceeds $50, the request is flagged for human
    escalation instead of being processed automatically.

    Args:
        order_id: The unique order identifier.
        amount: The dollar amount to refund.

    Returns:
        A confirmation string, an error, or an escalation notice.
    """
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return f"Error: No order found with ID '{order_id}'."

        if amount <= 0:
            return "Error: Refund amount must be positive."

        if amount > order.total_amount:
            return (
                f"Error: Refund amount ${amount:.2f} exceeds the order "
                f"total of ${order.total_amount:.2f}."
            )

        if amount > 50:
            return (
                f"Escalation Required: Refund of ${amount:.2f} for order "
                f"{order_id} exceeds the $50 auto-approval threshold. "
                f"This request has been forwarded to a human agent for review."
            )

        # Auto-approved refund
        return (
            f"Refund Processed: ${amount:.2f} has been refunded for order "
            f"{order_id}. The customer will see the credit within 3-5 "
            f"business days."
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Convenience list for binding
# ---------------------------------------------------------------------------
ALL_TOOLS = [
    get_customer_info,
    get_order_status,
    update_shipping_address,
    process_refund,
]
