import json
import sqlite3
import threading
from pathlib import Path

from .models import ResearchRun, WorkflowEvent


class RunStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_run_sequence
                    ON events(run_id, sequence);
                """
            )

    def save_run(self, run: ResearchRun) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs(id, payload, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (run.id, run.model_dump_json(), run.updated_at.isoformat()),
            )

    def get_run(self, run_id: str) -> ResearchRun | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM runs WHERE id = ?", (run_id,)
            ).fetchone()
        return ResearchRun.model_validate_json(row["payload"]) if row else None

    def append_event(self, event: WorkflowEvent) -> WorkflowEvent:
        with self._lock, self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO events(run_id, payload, created_at) VALUES (?, ?, ?)",
                (event.run_id, event.model_dump_json(), event.created_at.isoformat()),
            )
            event.sequence = int(cursor.lastrowid)
            connection.execute(
                "UPDATE events SET payload = ? WHERE sequence = ?",
                (event.model_dump_json(), event.sequence),
            )
        return event

    def list_events(self, run_id: str, after: int = 0) -> list[WorkflowEvent]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload FROM events
                WHERE run_id = ? AND sequence > ?
                ORDER BY sequence
                """,
                (run_id, after),
            ).fetchall()
        return [WorkflowEvent.model_validate_json(row["payload"]) for row in rows]
