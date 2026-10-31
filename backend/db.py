import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from backend.config import DATABASE_PATH, ROOT_DIR

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DATABASE_PATH), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def db_connection() -> Iterator[sqlite3.Connection]:
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db() -> None:
    with db_connection() as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_run(run_id: str, kind: str, filename: Optional[str] = None) -> None:
    with db_connection() as connection:
        connection.execute(
            "INSERT INTO runs (id, kind, filename, status, started_at) VALUES (?, ?, ?, ?, ?)",
            (run_id, kind, filename, "running", utc_now()),
        )


def append_run_event(run_id: str, node: str, status: str, detail: str, retry: int = 0) -> dict:
    event = {
        "node": node,
        "status": status,
        "detail": detail,
        "retry": retry,
        "timestamp": utc_now(),
    }
    with db_connection() as connection:
        row = connection.execute("SELECT events_json FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise LookupError(f"Run {run_id} does not exist")
        events = json.loads(row["events_json"])
        events.append(event)
        connection.execute("UPDATE runs SET events_json = ? WHERE id = ?", (json.dumps(events), run_id))
    return event


def finish_run(run_id: str, status: str = "completed", metrics: Optional[dict] = None) -> None:
    with db_connection() as connection:
        cursor = connection.execute(
            "UPDATE runs SET status = ?, ended_at = ?, metrics_json = ? WHERE id = ?",
            (status, utc_now(), json.dumps(metrics or {}), run_id),
        )
        if cursor.rowcount == 0:
            raise LookupError(f"Run {run_id} does not exist")


def get_run_events(run_id: str) -> Optional[list]:
    with db_connection() as connection:
        row = connection.execute(
            "SELECT events_json FROM runs WHERE id = ?", (run_id,)
        ).fetchone()
    return json.loads(row["events_json"]) if row else None


def get_run(run_id: str) -> Optional[dict]:
    with db_connection() as connection:
        row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def resolve_path(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT_DIR / candidate
