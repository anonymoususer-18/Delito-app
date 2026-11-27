import sqlite3
import uuid
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel


DB_PATH = Path(__file__).resolve().parent.parent / "payments.db"


class PaymentCreate(BaseModel):
    order_id: str
    amount: float
    method: str


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS payments (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            amount REAL NOT NULL,
            method TEXT NOT NULL,
            status TEXT NOT NULL
            )"""
        )


app = FastAPI(title="DELITO Payment Service", version="1.0.0")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "healthy", "service": "payment"}


@app.post("/payments")
def create_payment(payment: PaymentCreate):
    status = "Pending" if payment.method.lower() == "cash on delivery" else "Success"
    payment_id = "PAY-" + uuid.uuid4().hex[:10].upper()
    with get_db() as connection:
        connection.execute(
            "INSERT INTO payments (id, order_id, amount, method, status) VALUES (?, ?, ?, ?, ?)",
            (payment_id, payment.order_id, payment.amount, payment.method, status),
        )
    return {"id": payment_id, "order_id": payment.order_id, "amount": payment.amount,
            "method": payment.method, "status": status}


@app.get("/payments")
def list_payments():
    with get_db() as connection:
        rows = connection.execute("SELECT * FROM payments").fetchall()
    return [dict(row) for row in rows]
