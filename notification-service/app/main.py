import sqlite3
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel


DB_PATH = Path(os.getenv("DATA_DIR", str(Path(__file__).resolve().parent.parent))) / "notifications.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class NotificationCreate(BaseModel):
    title: str
    message: str
    type: str = "order"


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT NOT NULL,
            is_read INTEGER NOT NULL,
            created_at TEXT NOT NULL
            )"""
        )


app = FastAPI(title="DELITO Notification Service", version="1.0.0")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "healthy", "service": "notification"}


@app.post("/notifications", status_code=202)
async def create_notification(notification: NotificationCreate):
    notification_id = "NTF-" + uuid.uuid4().hex[:8].upper()
    created_at = datetime.now(timezone.utc).isoformat()
    with get_db() as connection:
        connection.execute(
            "INSERT INTO notifications VALUES (?, ?, ?, ?, 0, ?)",
            (notification_id, notification.title, notification.message,
             notification.type, created_at),
        )
    return {"id": notification_id, "accepted": True, "title": notification.title,
            "message": notification.message, "type": notification.type,
            "is_read": False, "created_at": created_at}


@app.get("/notifications")
def list_notifications():
    with get_db() as connection:
        rows = connection.execute("SELECT * FROM notifications ORDER BY created_at DESC").fetchall()
    return [
        {**dict(row), "is_read": bool(row["is_read"])}
        for row in rows
    ]
