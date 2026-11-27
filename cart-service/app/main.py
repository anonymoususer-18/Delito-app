import sqlite3
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


DB_PATH = Path(os.getenv("DATA_DIR", str(Path(__file__).resolve().parent.parent))) / "cart.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class CartItem(BaseModel):
    product_id: int
    name: str
    price: float
    image: str
    quantity: int = 1


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS cart_items (
            product_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            image TEXT NOT NULL,
            quantity INTEGER NOT NULL
            )"""
        )


app = FastAPI(title="DELITO Cart Service", version="1.0.0")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "healthy", "service": "cart"}


@app.get("/cart")
def get_cart():
    with get_db() as connection:
        rows = connection.execute("SELECT * FROM cart_items").fetchall()
    items = [dict(row) for row in rows]
    return {"items": items, "item_count": sum(i["quantity"] for i in items),
            "subtotal": round(sum(i["price"] * i["quantity"] for i in items), 2)}


@app.post("/cart")
def add_to_cart(item: CartItem):
    if item.quantity < 1:
        raise HTTPException(400, "Quantity must be at least one")
    with get_db() as connection:
        connection.execute(
            """INSERT INTO cart_items (product_id, name, price, image, quantity)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(product_id) DO UPDATE SET quantity = quantity + excluded.quantity""",
            (item.product_id, item.name, item.price, item.image, item.quantity),
        )
    return get_cart()


@app.patch("/cart/{product_id}")
def set_quantity(product_id: int, quantity: int):
    if quantity < 1:
        raise HTTPException(400, "Quantity must be at least one")
    with get_db() as connection:
        result = connection.execute(
            "UPDATE cart_items SET quantity = ? WHERE product_id = ?", (quantity, product_id)
        )
        if result.rowcount == 0:
            raise HTTPException(404, "Cart item not found")
    return get_cart()


@app.delete("/cart/{product_id}")
def remove_item(product_id: int):
    with get_db() as connection:
        connection.execute("DELETE FROM cart_items WHERE product_id = ?", (product_id,))
    return get_cart()


@app.delete("/cart")
def clear_cart():
    with get_db() as connection:
        connection.execute("DELETE FROM cart_items")
    return get_cart()
