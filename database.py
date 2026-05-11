"""
database.py — SQLAlchemy ORM models, engine setup, and seed data.

Tables:
  • Customers  – id (PK), name, email, loyalty_tier
  • Orders     – id (PK), customer_id (FK), status, total_amount, shipping_address
"""

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    ForeignKey,
    Enum,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# ---------------------------------------------------------------------------
# Engine & Session
# ---------------------------------------------------------------------------
DATABASE_URL = "sqlite:///./support_agent.db"

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------
class Customer(Base):
    __tablename__ = "customers"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    loyalty_tier = Column(
        Enum("Bronze", "Silver", "Gold", name="loyalty_tier"),
        nullable=False,
        default="Bronze",
    )

    orders = relationship("Order", back_populates="customer")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "loyalty_tier": self.loyalty_tier,
        }


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    status = Column(
        Enum("Processing", "Shipped", "Delivered", name="order_status"),
        nullable=False,
        default="Processing",
    )
    total_amount = Column(Float, nullable=False)
    shipping_address = Column(String, nullable=False)

    customer = relationship("Customer", back_populates="orders")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "status": self.status,
            "total_amount": self.total_amount,
            "shipping_address": self.shipping_address,
        }


# ---------------------------------------------------------------------------
# Table Creation
# ---------------------------------------------------------------------------
def create_tables():
    """Create all tables (idempotent)."""
    Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# Seed Data
# ---------------------------------------------------------------------------
SEED_CUSTOMERS = [
    Customer(id="C001", name="Alice Johnson", email="alice@example.com", loyalty_tier="Gold"),
    Customer(id="C002", name="Bob Martinez", email="bob@example.com", loyalty_tier="Silver"),
    Customer(id="C003", name="Carol Lee", email="carol@example.com", loyalty_tier="Bronze"),
]

SEED_ORDERS = [
    Order(id="ORD001", customer_id="C001", status="Delivered", total_amount=129.99, shipping_address="123 Oak St, Springfield, IL 62704"),
    Order(id="ORD002", customer_id="C001", status="Processing", total_amount=49.95, shipping_address="123 Oak St, Springfield, IL 62704"),
    Order(id="ORD003", customer_id="C002", status="Shipped", total_amount=74.50, shipping_address="456 Elm Ave, Portland, OR 97201"),
    Order(id="ORD004", customer_id="C002", status="Processing", total_amount=210.00, shipping_address="456 Elm Ave, Portland, OR 97201"),
    Order(id="ORD005", customer_id="C003", status="Delivered", total_amount=33.25, shipping_address="789 Pine Rd, Austin, TX 78701"),
]


def seed_database():
    """Insert seed data if the tables are empty."""
    db = SessionLocal()
    try:
        if db.query(Customer).count() == 0:
            db.add_all(SEED_CUSTOMERS)
            db.commit()
            print("✓ Seeded 3 customers.")

        if db.query(Order).count() == 0:
            db.add_all(SEED_ORDERS)
            db.commit()
            print("✓ Seeded 5 orders.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Convenience helper used by tools
# ---------------------------------------------------------------------------
def get_db():
    """Yield a DB session (for use with FastAPI Depends or manual context)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    create_tables()
    seed_database()
    print("✓ Database initialised and seeded successfully.")
