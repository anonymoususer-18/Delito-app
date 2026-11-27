import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


DB_PATH = Path(os.getenv("DATA_DIR", str(Path(__file__).resolve().parent.parent))) / "orders.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class OrderCreate(BaseModel):
    customer_name: str
    address: str
    phone: str
    payment_method: str
    items: list[dict[str, Any]]
    total: float


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            address TEXT NOT NULL,
            phone TEXT NOT NULL,
            payment_method TEXT NOT NULL,
            items TEXT NOT NULL,
            total REAL NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
            )"""
        )


def row_to_order(row):
    return {
        "id": row["id"], "customer_name": row["customer_name"],
        "address": row["address"], "phone": row["phone"],
        "payment_method": row["payment_method"], "items": json.loads(row["items"]),
        "total": row["total"], "status": row["status"], "created_at": row["created_at"],
    }


app = FastAPI(title="DELITO Order Service", version="1.0.0")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "healthy", "service": "order"}


@app.post("/orders", status_code=201)
def create_order(order: OrderCreate):
    order_id = "DLT-" + uuid.uuid4().hex[:8].upper()
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        connection.execute(
            """INSERT INTO orders
            (id, customer_name, address, phone, payment_method, items, total, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (order_id, order.customer_name, order.address, order.phone,
             order.payment_method, json.dumps(order.items), order.total,
             "Confirmed", created_at),
        )
    return get_order(order_id)


@app.get("/orders")
def list_orders():
    with get_db() as connection:
        rows = connection.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    return [row_to_order(row) for row in rows]


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    with get_db() as connection:
        row = connection.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Order not found")
    return row_to_order(row)


@app.patch("/orders/{order_id}/status")
def update_status(order_id: str, status: str):
    allowed = {"Pending", "Confirmed", "Packed", "Out for Delivery", "Delivered"}
    if status not in allowed:
        raise HTTPException(400, "Invalid order status")
    with get_db() as connection:
        result = connection.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        if result.rowcount == 0:
            raise HTTPException(404, "Order not found")
    return get_order(order_id)
