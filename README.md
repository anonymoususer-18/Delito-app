# DELITO

DELITO is a modern grocery quick-commerce application with a React storefront, FastAPI microservices, SQLite databases, and a Gemini-powered RAG grocery assistant.

## Architecture

```mermaid
flowchart LR
  Browser --> Gateway[API Gateway]
  Gateway --> Catalogue[Catalogue Service]
  Gateway --> Cart[Cart Service]
  Gateway --> Orders[Order Service]
  Gateway --> Payment[Payment Service]
  Gateway --> Notifications[Notification Service]
  Gateway --> AI[DELITO AI Service]
  AI --> Chroma[ChromaDB]
  AI --> Gemini[Google Gemini]
  Catalogue --> CatalogueDB[(SQLite)]
  Cart --> CartDB[(SQLite)]
  Orders --> OrderDB[(SQLite)]
  Payment --> PaymentDB[(SQLite)]
  Notifications --> NotificationDB[(SQLite)]
```

Each domain service owns a separate SQLite database. The React application only communicates with the versioned API Gateway.

## Local setup

1. Install Docker Desktop and Node.js 20+.
2. Copy `.env.example` to `.env` and set `JWT_SECRET` and `GEMINI_API_KEY`.
3. Start the complete stack:

   ```powershell
   docker compose up --build
   ```

4. Open `http://localhost:5173`.
5. API documentation: `http://localhost:8000/docs`.

## Development

See `docker-compose.yml` for service ports and container configuration.

### Service ports

| Service | Port |
| --- | --- |
| React frontend | 5173 |
| API Gateway | 8000 |
| Catalogue | 8001 |
| Cart | 8002 |
| Order | 8003 |
| Payment | 8004 |
| Notification | 8005 |
| DELITO AI | 8006 |

### Useful API routes

- `POST /api/v1/auth/demo-login`
- `GET /api/v1/catalogue/products`
- `GET /api/v1/catalogue/products/{id}`
- `POST /api/v1/cart`
- `POST /api/v1/orders`
- `GET /api/v1/orders`
- `GET /api/v1/notifications`
- `POST /api/v1/ai/chat`

## GitHub setup

```powershell
git remote add origin https://github.com/anonymoususer-18/Delito-app.git
git switch -c main
git add .
git commit -m "chore: initialize DELITO project"
git push -u origin main
```

Never commit `.env`, API keys, passwords, or SQLite databases.
