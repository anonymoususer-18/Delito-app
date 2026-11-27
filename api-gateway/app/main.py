import os
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


JWT_SECRET = os.getenv("JWT_SECRET", "delito-development-secret")
JWT_ALGORITHM = "HS256"
SERVICES = {
    "catalogue": os.getenv("CATALOGUE_SERVICE_URL", "http://catalogue-service:8001"),
    "cart": os.getenv("CART_SERVICE_URL", "http://cart-service:8002"),
    "orders": os.getenv("ORDER_SERVICE_URL", "http://order-service:8003"),
    "payments": os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8004"),
    "notifications": os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8005"),
    "ai": os.getenv("AI_SERVICE_URL", "http://ai-assistant-service:8006"),
}


class LoginRequest(BaseModel):
    name: str = "DELITO Customer"


app = FastAPI(title="DELITO API Gateway", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_auth(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required")
    try:
        return jwt.decode(
            authorization.removeprefix("Bearer "),
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "Invalid or expired token") from exc


async def forward(service: str, path: str, method: str,
                  request: Request, body: Any = None,
                  params: dict[str, Any] | None = None):
    url = SERVICES[service].rstrip("/") + path
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.request(
                method,
                url,
                json=body,
                params=params,
            )
            return response.json()
        except httpx.TimeoutException as exc:
            raise HTTPException(504, f"{service.title()} service timed out") from exc
        except httpx.HTTPError as exc:
            raise HTTPException(503, f"{service.title()} service unavailable") from exc


@app.get("/health")
def health():
    return {"status": "healthy", "service": "api-gateway"}


@app.post("/api/v1/auth/demo-login")
def demo_login(payload: LoginRequest):
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    token = jwt.encode(
        {"sub": payload.name, "exp": expires},
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )
    return {"access_token": token, "token_type": "bearer", "name": payload.name}


@app.get("/api/v1/catalogue/products")
async def catalogue_products(request: Request, search: str | None = None,
                             category: str | None = None):
    params = {key: value for key, value in {"search": search, "category": category}.items() if value}
    return await forward("catalogue", "/products", "GET", request, params=params)


@app.get("/api/v1/catalogue/products/{product_id}")
async def catalogue_product(product_id: int, request: Request):
    return await forward("catalogue", f"/products/{product_id}", "GET", request)


@app.get("/api/v1/catalogue/categories")
async def catalogue_categories(request: Request):
    return await forward("catalogue", "/categories", "GET", request)


@app.get("/api/v1/cart")
async def get_cart(request: Request, _claims=Depends(require_auth)):
    return await forward("cart", "/cart", "GET", request)


@app.post("/api/v1/cart")
async def add_cart(request: Request, _claims=Depends(require_auth)):
    body = await request.json()
    return await forward("cart", "/cart", "POST", request, body=body)


@app.patch("/api/v1/cart/{product_id}")
async def change_cart(product_id: int, quantity: int, request: Request,
                      _claims=Depends(require_auth)):
    return await forward("cart", f"/cart/{product_id}", "PATCH", request,
                         params={"quantity": quantity})


@app.delete("/api/v1/cart/{product_id}")
async def delete_cart(product_id: int, request: Request,
                      _claims=Depends(require_auth)):
    return await forward("cart", f"/cart/{product_id}", "DELETE", request)


@app.delete("/api/v1/cart")
async def clear_cart(request: Request, _claims=Depends(require_auth)):
    return await forward("cart", "/cart", "DELETE", request)


@app.post("/api/v1/orders")
async def place_order(request: Request, _claims=Depends(require_auth)):
    body = await request.json()
    order = await forward("orders", "/orders", "POST", request, body=body)
    await forward("payments", "/payments", "POST", request, body={
        "order_id": order["id"], "amount": order["total"],
        "method": order["payment_method"],
    })
    await forward("notifications", "/notifications", "POST", request, body={
        "title": "Order confirmed",
        "message": f"Your DELITO order {order['id']} has been confirmed.",
        "type": "order",
    })
    return order


@app.get("/api/v1/orders")
async def list_orders(request: Request, _claims=Depends(require_auth)):
    return await forward("orders", "/orders", "GET", request)


@app.get("/api/v1/orders/{order_id}")
async def get_order(order_id: str, request: Request,
                    _claims=Depends(require_auth)):
    return await forward("orders", f"/orders/{order_id}", "GET", request)


@app.get("/api/v1/notifications")
async def list_notifications(request: Request, _claims=Depends(require_auth)):
    return await forward("notifications", "/notifications", "GET", request)


@app.post("/api/v1/ai/chat")
async def ai_chat(request: Request, _claims=Depends(require_auth)):
    body = await request.json()
    return await forward("ai", "/chat", "POST", request, body=body)
