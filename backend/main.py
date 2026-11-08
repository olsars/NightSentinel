
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


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
def create_event(event: EventInput, response: Response):
    now = datetime.now(timezone.utc)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        previous = conn.execute(
            """
            SELECT * FROM events
            WHERE track_id = ?
            AND event_type = ?
            AND zone = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (event.track_id, event.event_type, event.zone)
        ).fetchone()

        if previous:
            last_time = datetime.fromisoformat(
                previous["timestamp"]
            )
            seconds = (now - last_time).total_seconds()

            if 0 <= seconds < 15:
                response.status_code = 200
                return dict(previous)

        priority = (
            "high"
            if event.event_type == "restricted_zone_entry"
            else "low"
        )

        timestamp = now.isoformat()

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

        return {
            "id": cursor.lastrowid,
            "track_id": event.track_id,
            "event_type": event.event_type,
            "zone": event.zone,
            "priority": priority,
            "timestamp": timestamp
        }

    finally:
        conn.close()



@app.get("/events")
def get_events(
    priority: Literal["low", "high"] | None = None,
    event_type: Literal["person_detected", "restricted_zone_entry"] | None = None
):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            """
            SELECT * FROM events
            WHERE (? IS NULL OR priority = ?)
            AND (? IS NULL OR event_type = ?)
            ORDER BY id DESC
            LIMIT 100
            """,
            (priority, priority, event_type, event_type)
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        conn.close()


# Keep API routes above this mount so the Jetson serves both the dashboard and
# its JSON API from one address without a separate frontend development server.
app.mount(
    "/",
    StaticFiles(directory=FRONTEND_DIR, html=True),
    name="frontend",
)

