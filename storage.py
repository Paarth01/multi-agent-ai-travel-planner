"""
SQLite-backed itinerary persistence — zero-config, no new dependency.

Stores the full itinerary JSON alongside queryable metadata columns
(destination, dates, cost) so listing all trips doesn't need to
deserialize every row.  Thread-safe via check_same_thread=False.
"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from config import settings


class ItineraryStore:
    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or settings.sqlite_db_path
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS itineraries (
                id          TEXT PRIMARY KEY,
                destination TEXT NOT NULL,
                origin      TEXT NOT NULL,
                start_date  TEXT NOT NULL,
                end_date    TEXT NOT NULL,
                total_cost  REAL NOT NULL,
                best_effort INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL,
                data        TEXT NOT NULL
            )
        """)
        self._conn.commit()

    def save(self, itinerary: dict) -> str:
        """Persist a full itinerary dict and return its generated id."""
        trip_id = uuid.uuid4().hex[:12]
        trip_req = itinerary.get("trip_request", {})
        now = datetime.now(timezone.utc).isoformat()

        self._conn.execute(
            """INSERT INTO itineraries
               (id, destination, origin, start_date, end_date, total_cost, best_effort, created_at, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trip_id,
                trip_req.get("destination", ""),
                trip_req.get("origin", ""),
                trip_req.get("start_date", ""),
                trip_req.get("end_date", ""),
                itinerary.get("total_cost", 0.0),
                1 if itinerary.get("best_effort", False) else 0,
                now,
                json.dumps(itinerary, default=str),
            ),
        )
        self._conn.commit()
        return trip_id

    def get(self, trip_id: str) -> dict[str, Any] | None:
        """Retrieve a full itinerary by id, or None if not found."""
        row = self._conn.execute(
            "SELECT data, id, created_at FROM itineraries WHERE id = ?", (trip_id,)
        ).fetchone()
        if row is None:
            return None
        itinerary = json.loads(row["data"])
        itinerary["id"] = row["id"]
        itinerary["created_at"] = row["created_at"]
        return itinerary

    def list_all(self) -> list[dict[str, Any]]:
        """Return metadata for all saved itineraries, newest first."""
        rows = self._conn.execute(
            """SELECT id, destination, origin, start_date, end_date,
                      total_cost, best_effort, created_at
               FROM itineraries ORDER BY created_at DESC"""
        ).fetchall()
        return [
            {
                "id": r["id"],
                "destination": r["destination"],
                "origin": r["origin"],
                "start_date": r["start_date"],
                "end_date": r["end_date"],
                "total_cost": r["total_cost"],
                "best_effort": bool(r["best_effort"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def delete(self, trip_id: str) -> bool:
        """Delete an itinerary by id. Returns True if it existed."""
        cursor = self._conn.execute(
            "DELETE FROM itineraries WHERE id = ?", (trip_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def close(self) -> None:
        self._conn.close()
