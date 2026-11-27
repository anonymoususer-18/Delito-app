import os
import hashlib
import html
from pathlib import Path
from urllib.parse import quote
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel


CATALOGUE_URL = os.getenv("CATALOGUE_SERVICE_URL", "http://catalogue-service:8001")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

conversation_history: dict[str, list[dict[str, str]]] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ImageRequest(BaseModel):
    prompt: str
    width: int = 1024
    height: int = 1024


IMAGE_CACHE = Path(__file__).resolve().parent / "generated-images"
IMAGE_CACHE.mkdir(parents=True, exist_ok=True)


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


def grounded_answer(
    question: str,
    products: list[dict[str, Any]],
    conversation_context: str = "",
) -> str:
    lower = question.lower().replace("protien", "protein")

    def find_named_product():
        for product in products:
            if product["name"].lower() in lower:
                return product
        if " it " in f" {lower} " or lower.endswith(" it") or "that" in lower:
            context_lower = conversation_context.lower()
            mentioned = [
                (context_lower.find(product["name"].lower()), product)
                for product in products
                if product["name"].lower() in context_lower
            ]
            if mentioned:
                _, product = min(mentioned, key=lambda item: item[0])
                return product
        for product in products:
            words = [word for word in product["name"].lower().split() if len(word) > 3]
            if any(word in lower for word in words):
                return product
        return None

    named_product = find_named_product()

    if "protein" in lower:
        if named_product:
            return f"{named_product['name']} contains {named_product['nutrition'].get('protein', 'unavailable')} g of protein per 100 g/unit."
        ranked = sorted(
            products,
            key=lambda product: float(product["nutrition"].get("protein", 0)),
            reverse=True,
        )
        top = ranked[:3]
        return (
            "High-protein options in the catalogue include "
            + ", ".join(
                f"{product['name']} ({product['nutrition'].get('protein', 0)} g protein)"
                for product in top
            )
            + "."
        )

    if "price" in lower or "cost" in lower or ("how much" in lower and "protein" not in lower and "calorie" not in lower and "sugar" not in lower):
        if named_product:
            return (
                f"{named_product['name']} costs Rs {named_product['price']} per "
                f"{named_product['unit']}. "
                f"It is {'available' if named_product['available'] else 'currently unavailable'}."
            )
        if products:
            return "Which product would you like the price for? " + ", ".join(
                product["name"] for product in products[:5]
            ) + "."

    if "ingredient" in lower:
        if named_product:
            return f"The ingredients in {named_product['name']} are: {named_product['ingredients']}."
        matching = [product for product in products if "ingredient" in lower or product["name"].lower() in lower]
        if matching:
            return "I found these products: " + ", ".join(product["name"] for product in matching[:5]) + "."

    if "available" in lower or "availability" in lower or "in stock" in lower:
        if named_product:
            status = "available" if named_product["available"] else "currently unavailable"
            return f"{named_product['name']} is {status} in the DELITO catalogue."

    if "calorie" in lower:
        if named_product:
            return f"{named_product['name']} contains {named_product['nutrition'].get('calories', 'unavailable')} calories per 100 g/unit."

    if "sugar" in lower:
        if named_product:
            return f"{named_product['name']} contains {named_product['nutrition'].get('sugar', 'unavailable')} g of sugar per 100 g/unit."

    if "protein" in lower or "high protein" in lower or "high protien" in lower:
        ranked = sorted(
            products,
            key=lambda product: float(product["nutrition"].get("protein", 0)),
            reverse=True,
        )
        top = ranked[:3]
        return (
            "High-protein options in the catalogue include "
            + ", ".join(
                f"{product['name']} ({product['nutrition'].get('protein', 0)} g protein)"
                for product in top
            )
            + "."
        )

    if "nutrition" in lower or "nutritional" in lower:
        if named_product:
            nutrition = named_product["nutrition"]
            return (
                f"{named_product['name']} nutrition per 100 g/unit: "
                f"{nutrition.get('calories', 'unavailable')} calories, "
                f"{nutrition.get('protein', 'unavailable')} g protein, "
                f"{nutrition.get('fat', 'unavailable')} g fat, "
                f"{nutrition.get('carbs', 'unavailable')} g carbohydrates, "
                f"{nutrition.get('fibre', 'unavailable')} g fibre, and "
                f"{nutrition.get('sugar', 'unavailable')} g sugar."
            )

    if named_product:
        product = named_product
        return (
            f"{product['name']} costs Rs {product['price']} per {product['unit']}. "
            f"It is {'available' if product['available'] else 'currently unavailable'}, "
            f"with ingredients: {product['ingredients']}. "
            f"Protein: {product['nutrition'].get('protein', 'unavailable')} g."
        )

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


@app.post("/image")
async def generate_image(request: ImageRequest):
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(400, "Image prompt cannot be empty")
    if len(prompt) > 500:
        raise HTTPException(400, "Image prompt is too long")

    width = max(256, min(request.width, 1536))
    height = max(256, min(request.height, 1536))
    seed_source = f"{prompt}:{width}:{height}".encode("utf-8")
    seed = int(hashlib.sha256(seed_source).hexdigest()[:8], 16)
    svg_filename = f"{hashlib.sha256(seed_source).hexdigest()}.svg"
    jpg_filename = f"{hashlib.sha256(seed_source).hexdigest()}.jpg"
    svg_path = IMAGE_CACHE / svg_filename
    jpg_path = IMAGE_CACHE / jpg_filename
    cached_path = jpg_path if jpg_path.exists() else svg_path

    if not jpg_path.exists() and not svg_path.exists():
        enhanced_prompt = (
            f"Professional premium grocery ecommerce photography, {prompt}, "
            "fresh, vibrant, natural lighting, clean composition, no text"
        )
        provider_url = (
            f"https://image.pollinations.ai/prompt/{quote(enhanced_prompt)}"
            f"?width={width}&height={height}&nologo=true&seed={seed}"
        )
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                response = await client.get(provider_url)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "image/" not in content_type or not response.content:
                    raise HTTPException(502, "Image provider returned an invalid response")
                jpg_path.write_bytes(response.content)
                cached_path = jpg_path
        except HTTPException:
            pass
        except Exception as exc:
            pass

    if not jpg_path.exists() and not svg_path.exists():
        safe_prompt = html.escape(prompt[:120])
        svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="#edf8df"/>
<circle cx="{width*0.22}" cy="{height*0.28}" r="{min(width,height)*0.12}" fill="#ff9f43"/>
<circle cx="{width*0.72}" cy="{height*0.28}" r="{min(width,height)*0.13}" fill="#ef5b5b"/>
<circle cx="{width*0.52}" cy="{height*0.54}" r="{min(width,height)*0.16}" fill="#77ba51"/>
<circle cx="{width*0.28}" cy="{height*0.68}" r="{min(width,height)*0.11}" fill="#c8ef72"/>
<circle cx="{width*0.75}" cy="{height*0.68}" r="{min(width,height)*0.12}" fill="#ffc857"/>
<path d="M {width*0.52} {height*0.41} Q {width*0.58} {height*0.30} {width*0.68} {height*0.38} Q {width*0.60} {height*0.44} {width*0.52} {height*0.41}" fill="#123d2b"/>
<path d="M {width*0.22} {height*0.16} Q {width*0.30} {height*0.10} {width*0.34} {height*0.20}" fill="none" stroke="#123d2b" stroke-width="{min(width,height)*0.018}" stroke-linecap="round"/>
<rect x="{width*0.11}" y="{height*0.78}" width="{width*0.78}" height="{height*0.12}" rx="{height*0.03}" fill="#ffffff" fill-opacity="0.92"/>
<text x="{width*0.50}" y="{height*0.85}" text-anchor="middle" fill="#123d2b" font-family="Arial, sans-serif" font-size="{min(width,height)*0.035}" font-weight="700">{safe_prompt}</text>
</svg>"""
        svg_path.write_text(svg, encoding="utf-8")
        cached_path = svg_path

    filename = cached_path.name

    return {
        "prompt": prompt,
        "filename": filename,
        "image_url": f"/generated-images/{filename}",
        "cached": cached_path.exists(),
    }


@app.get("/generated-images/{filename}")
def get_generated_image(filename: str):
    path = IMAGE_CACHE / filename
    if not path.is_file():
        raise HTTPException(404, "Generated image not found")
    media_type = "image/svg+xml" if path.suffix.lower() == ".svg" else "image/jpeg"
    return FileResponse(path, media_type=media_type)


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
                answer = grounded_answer(request.message, products, history_text)
        except Exception as exc:
            raise HTTPException(502, f"Gemini response failed: {exc}") from exc

    history.append({"role": "customer", "content": request.message})
    history.append({"role": "assistant", "content": answer})
    return {"answer": answer, "session_id": request.session_id,
            "sources": [p["name"] for p in relevant]}
