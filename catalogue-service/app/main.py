import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


DB_PATH = Path(__file__).resolve().parent.parent / "catalogue.db"

PRODUCTS = [
    {"name": "Farm Fresh Bananas", "category": "Fruits", "price": 49, "unit": "1 kg", "image": "https://images.unsplash.com/photo-1603833665858-e61d17a86224", "description": "Naturally ripened sweet bananas.", "ingredients": "Banana", "nutrition": {"calories": 89, "protein": 1.1, "fat": 0.3, "carbs": 22.8, "fibre": 2.6, "sugar": 12.2}, "available": True},
    {"name": "Red Delicious Apples", "category": "Fruits", "price": 189, "unit": "1 kg", "image": "https://images.unsplash.com/photo-1560806887-1e4cd0b6cbd6", "description": "Crunchy, juicy red apples.", "ingredients": "Apple", "nutrition": {"calories": 52, "protein": 0.3, "fat": 0.2, "carbs": 14, "fibre": 2.4, "sugar": 10.4}, "available": True},
    {"name": "Baby Spinach", "category": "Vegetables", "price": 59, "unit": "250 g", "image": "https://images.unsplash.com/photo-1576045057995-568f588f82fb", "description": "Fresh, tender baby spinach leaves.", "ingredients": "Spinach", "nutrition": {"calories": 23, "protein": 2.9, "fat": 0.4, "carbs": 3.6, "fibre": 2.2, "sugar": 0.4}, "available": True},
    {"name": "Cherry Tomatoes", "category": "Vegetables", "price": 79, "unit": "250 g", "image": "https://images.unsplash.com/photo-1561136594-7f68413baa99", "description": "Sweet cherry tomatoes for salads.", "ingredients": "Cherry tomato", "nutrition": {"calories": 18, "protein": 0.9, "fat": 0.2, "carbs": 3.9, "fibre": 1.2, "sugar": 2.6}, "available": True},
    {"name": "Whole Wheat Bread", "category": "Bakery", "price": 55, "unit": "400 g", "image": "https://images.unsplash.com/photo-1509440159596-0249088772ff", "description": "Soft, fibre-rich whole wheat bread.", "ingredients": "Whole wheat flour, water, yeast, salt", "nutrition": {"calories": 247, "protein": 13, "fat": 4.2, "carbs": 41, "fibre": 7, "sugar": 4}, "available": True},
    {"name": "Farm Eggs", "category": "Dairy & Eggs", "price": 99, "unit": "6 pieces", "image": "https://images.unsplash.com/photo-1506976785307-8732e854ad03", "description": "Fresh protein-rich farm eggs.", "ingredients": "Egg", "nutrition": {"calories": 155, "protein": 12.6, "fat": 10.6, "carbs": 1.1, "fibre": 0, "sugar": 1.1}, "available": True},
    {"name": "Fresh Cow Milk", "category": "Dairy & Eggs", "price": 68, "unit": "1 litre", "image": "https://images.unsplash.com/photo-1550583724-b2692b85b150", "description": "Creamy everyday pasteurized milk.", "ingredients": "Cow milk", "nutrition": {"calories": 61, "protein": 3.2, "fat": 3.3, "carbs": 4.8, "fibre": 0, "sugar": 5.1}, "available": True},
    {"name": "Greek Yogurt", "category": "Dairy & Eggs", "price": 135, "unit": "400 g", "image": "https://images.unsplash.com/photo-1571212515416-fca77c1bdc6b", "description": "Thick, tangy high-protein yogurt.", "ingredients": "Milk, live cultures", "nutrition": {"calories": 97, "protein": 9, "fat": 5, "carbs": 3.6, "fibre": 0, "sugar": 3.2}, "available": True},
    {"name": "Rolled Oats", "category": "Breakfast", "price": 149, "unit": "500 g", "image": "https://images.unsplash.com/photo-1517673132405-a56a62b18caf", "description": "Whole grain oats for quick breakfasts.", "ingredients": "Rolled oats", "nutrition": {"calories": 389, "protein": 16.9, "fat": 6.9, "carbs": 66.3, "fibre": 10.6, "sugar": 0.99}, "available": True},
    {"name": "Natural Peanut Butter", "category": "Breakfast", "price": 249, "unit": "350 g", "image": "https://images.unsplash.com/photo-1590080875515-8a3a8dc5735e", "description": "Smooth peanut butter with no added sugar.", "ingredients": "Roasted peanuts", "nutrition": {"calories": 588, "protein": 25, "fat": 50, "carbs": 20, "fibre": 6, "sugar": 5}, "available": True},
    {"name": "Basmati Rice", "category": "Pantry", "price": 299, "unit": "5 kg", "image": "https://images.unsplash.com/photo-1586201375761-83865001e31c", "description": "Aromatic long-grain basmati rice.", "ingredients": "Basmati rice", "nutrition": {"calories": 360, "protein": 7.1, "fat": 0.6, "carbs": 79, "fibre": 1.4, "sugar": 0}, "available": True},
    {"name": "Extra Virgin Olive Oil", "category": "Pantry", "price": 449, "unit": "1 litre", "image": "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5", "description": "Cold-pressed olive oil for cooking.", "ingredients": "Extra virgin olive oil", "nutrition": {"calories": 884, "protein": 0, "fat": 100, "carbs": 0, "fibre": 0, "sugar": 0}, "available": True},
]


class Product(BaseModel):
    id: int
    name: str
    category: str
    price: float
    unit: str
    image: str
    description: str
    ingredients: str
    nutrition: dict
    available: bool


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                price REAL NOT NULL,
                unit TEXT NOT NULL,
                image TEXT NOT NULL,
                description TEXT NOT NULL,
                ingredients TEXT NOT NULL,
                nutrition TEXT NOT NULL,
                available INTEGER NOT NULL
            )
            """
        )
        if connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            import json

            connection.executemany(
                """
                INSERT INTO products
                (name, category, price, unit, image, description, ingredients, nutrition, available)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        p["name"], p["category"], p["price"], p["unit"], p["image"],
                        p["description"], p["ingredients"], json.dumps(p["nutrition"]),
                        int(p["available"]),
                    )
                    for p in PRODUCTS
                ],
            )


def row_to_product(row):
    import json

    return {
        "id": row["id"],
        "name": row["name"],
        "category": row["category"],
        "price": row["price"],
        "unit": row["unit"],
        "image": row["image"],
        "description": row["description"],
        "ingredients": row["ingredients"],
        "nutrition": json.loads(row["nutrition"]),
        "available": bool(row["available"]),
    }


app = FastAPI(title="DELITO Catalogue Service", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "healthy", "service": "catalogue"}


@app.get("/products", response_model=list[Product])
def list_products(
    search: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
):
    query = "SELECT * FROM products WHERE 1=1"
    parameters = []
    if search:
        query += " AND (lower(name) LIKE ? OR lower(description) LIKE ? OR lower(ingredients) LIKE ?)"
        needle = f"%{search.lower()}%"
        parameters.extend([needle, needle, needle])
    if category:
        query += " AND lower(category) = lower(?)"
        parameters.append(category)
    query += " ORDER BY id"

    with get_db() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [row_to_product(row) for row in rows]


@app.get("/products/{product_id}", response_model=Product)
def get_product(product_id: int):
    with get_db() as connection:
        row = connection.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return row_to_product(row)


@app.get("/categories")
def list_categories():
    with get_db() as connection:
        rows = connection.execute(
            "SELECT category, COUNT(*) AS count FROM products GROUP BY category ORDER BY category"
        ).fetchall()
    return [{"name": row["category"], "count": row["count"]} for row in rows]
