
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="NightSentinel API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


DB_PATH = Path(__file__).with_name("events.db")


class EventInput(BaseModel):
    track_id: str
    event_type: Literal["person_detected", "restricted_zone_entry"]
    zone: str


def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                zone TEXT NOT NULL,
                priority TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


initialize_database()


@app.get("/health")
def health_check():
    return {
        "status": "online",
        "service": "NightSentinel"
    }


@app.post("/events", status_code=201)
def create_event(event: EventInput):
    priority = "high" if event.event_type == "restricted_zone_entry" else "low"
    timestamp = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.execute(
            """
            INSERT INTO events
            (track_id, event_type, zone, priority, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event.track_id,
                event.event_type,
                event.zone,
                priority,
                timestamp
            )
        )
        conn.commit()
        event_id = cursor.lastrowid
    finally:
        conn.close()

    return {
        "id": event_id,
        "track_id": event.track_id,
        "event_type": event.event_type,
        "zone": event.zone,
        "priority": priority,
        "timestamp": timestamp
    }


@app.get("/events")
def get_events():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM events ORDER BY id DESC LIMIT 100"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
