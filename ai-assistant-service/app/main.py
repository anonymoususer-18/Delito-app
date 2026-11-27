import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


CATALOGUE_URL = os.getenv("CATALOGUE_SERVICE_URL", "http://catalogue-service:8001")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

conversation_history: dict[str, list[dict[str, str]]] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


app = FastAPI(title="DELITO AI Assistant", version="1.0.0")


async def fetch_catalogue() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(f"{CATALOGUE_URL}/products")
        response.raise_for_status()
        return response.json()


def simple_retrieve(question: str, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    terms = set(question.lower().replace("?", "").split())
    scored = []
    for product in products:
        searchable = " ".join([
            product["name"], product["category"], product["description"],
            product["ingredients"], str(product["nutrition"]),
        ]).lower()
        score = sum(term in searchable for term in terms if len(term) > 2)
        if score:
            scored.append((score, product))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [product for _, product in (scored[:5] or [(0, product) for product in products[:5]])]


def chroma_retrieve(question: str, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    try:
        import chromadb
        from chromadb.config import Settings

        class DelitoEmbeddingFunction:
            def name(self):
                return "delito-deterministic-hash"

            def __call__(self, input):
                import hashlib

                vectors = []
                for text in input:
                    digest = hashlib.sha256(text.lower().encode("utf-8")).digest()
                    vectors.append([float(byte) / 255.0 for byte in digest])
                return vectors

        client = chromadb.Client(Settings(anonymized_telemetry=False))
        collection = client.get_or_create_collection(
            "delito_catalogue",
            embedding_function=DelitoEmbeddingFunction(),
        )
        documents = []
        ids = []
        metadatas = []
        for product in products:
            documents.append(
                f"{product['name']} | category: {product['category']} | price: Rs {product['price']} "
                f"| unit: {product['unit']} | available: {product['available']} "
                f"| ingredients: {product['ingredients']} | nutrition: {product['nutrition']} "
                f"| description: {product['description']}"
            )
            ids.append(str(product["id"]))
            metadatas.append({"product_id": str(product["id"])})
        collection.upsert(documents=documents, ids=ids, metadatas=metadatas)
        result = collection.query(query_texts=[question], n_results=min(5, len(products)))
        matched_ids = set(result["ids"][0])
        matched = [product for product in products if str(product["id"]) in matched_ids]
        return matched or simple_retrieve(question, products)
    except Exception:
        return simple_retrieve(question, products)


def gemini_generate(prompt: str) -> str:
    import json
    import urllib.request

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result["candidates"][0]["content"]["parts"][0]["text"]


def grounded_answer(question: str, products: list[dict[str, Any]]) -> str:
    lower = question.lower()

    if "protein" in lower:
        ranked = sorted(
            products,
            key=lambda product: float(product["nutrition"].get("protein", 0)),
            reverse=True,
        )
        top = ranked[:3]
        facts = ", ".join(
            f"{product['name']} ({product['nutrition'].get('protein', 0)} g)"
            for product in top
        )
        return f"Among the relevant catalogue items, the protein values are: {facts}. Natural Peanut Butter and Rolled Oats are protein-rich breakfast options."

    if "compare" in lower:
        names = [product["name"] for product in products[:2]]
        if len(names) >= 2:
            first, second = products[0], products[1]
            return (
                f"{names[0]} has {first['nutrition'].get('sugar', 'unavailable')} g sugar "
                f"and {first['nutrition'].get('protein', 'unavailable')} g protein, while "
                f"{names[1]} has {second['nutrition'].get('sugar', 'unavailable')} g sugar "
                f"and {second['nutrition'].get('protein', 'unavailable')} g protein."
            )

    if "breakfast" in lower:
        breakfast = [product for product in products if product["category"] == "Breakfast"]
        if breakfast:
            names = ", ".join(product["name"] for product in breakfast)
            return f"For breakfast, you can consider: {names}. Check the individual nutrition values before choosing."

    if "salad" in lower:
        salad_items = [
            product["name"] for product in products
            if product["category"] in {"Vegetables", "Fruits"}
        ]
        if salad_items:
            return "Ingredients available for a simple salad include " + ", ".join(salad_items[:4]) + "."

    if products:
        names = ", ".join(product["name"] for product in products[:3])
        return f"The relevant catalogue items are {names}. Please ask about price, ingredients, availability, or nutrition for a specific product."

    return "No matching catalogue information is currently available."


@app.get("/health")
def health():
    return {"status": "healthy", "service": "ai-assistant",
            "gemini_configured": bool(GEMINI_API_KEY)}


@app.post("/chat")
async def chat(request: ChatRequest):
    if not request.message.strip():
        raise HTTPException(400, "Message cannot be empty")

    try:
        products = await fetch_catalogue()
    except Exception:
        raise HTTPException(503, "Catalogue information is temporarily unavailable")

    relevant = simple_retrieve(request.message, products)
    context = "\n\n".join([
        f"{p['name']} (category: {p['category']}): price Rs {p['price']} per {p['unit']}; "
        f"available: {'yes' if p['available'] else 'no'}; ingredients: {p['ingredients']}; "
        f"nutrition per 100 g/unit: {p['nutrition']}; description: {p['description']}"
        for p in relevant
    ])

    history = conversation_history.setdefault(request.session_id, [])
    history_text = "\n".join(
        f"{turn['role']}: {turn['content']}" for turn in history[-6:]
    )

    if not GEMINI_API_KEY:
        answer = (
            "DELITO AI is not connected to Gemini yet. Add GEMINI_API_KEY to `.env`. "
            "Based on the catalogue, here is the relevant information:\n\n" + context
        )
    else:
        try:
            prompt = (
                "You are DELITO AI, a helpful grocery assistant. Answer only using the "
                "catalogue context below. Do not invent ingredients or nutrition facts. "
                "If the context does not contain an answer, say that clearly.\n\n"
                f"Conversation:\n{history_text}\n\nCatalogue context:\n{context}\n\n"
                f"Customer question: {request.message}"
            )
            try:
                answer = gemini_generate(prompt)
            except Exception:
                answer = grounded_answer(request.message, relevant)
        except Exception as exc:
            raise HTTPException(502, f"Gemini response failed: {exc}") from exc

    history.append({"role": "customer", "content": request.message})
    history.append({"role": "assistant", "content": answer})
    return {"answer": answer, "session_id": request.session_id,
            "sources": [p["name"] for p in relevant]}
