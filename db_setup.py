"""
db_setup.py — Standalone script to create and seed the SQLite database.

Usage:
    python db_setup.py
"""

from database import create_tables, seed_database


def main():
    print("Setting up database …")
    create_tables()
    seed_database()
    print("\n✅ Database is ready. File: support_agent.db")
    print("   Tables: customers, orders")

    # Quick verification
    from database import SessionLocal, Customer, Order

    db = SessionLocal()
    try:
        customers = db.query(Customer).all()
        orders = db.query(Order).all()
        print(f"   Customers: {len(customers)}")
        for c in customers:
            print(f"     • {c.id}: {c.name} ({c.loyalty_tier})")
        print(f"   Orders: {len(orders)}")
        for o in orders:
            print(f"     • {o.id}: {o.status} — ${o.total_amount:.2f} → {o.shipping_address[:30]}…")
    finally:
        db.close()


if __name__ == "__main__":
    main()
