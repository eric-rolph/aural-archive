"""
Aural Archive — State Manager (Job Journal)
==============================================
SQLite-backed job tracking for crash recovery and idempotent
batch runs. Each project gets its own journal at:
  projects/<name>/output/.harvest_state.db

Inspired by Harvester Manager's state tracking pattern.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import config


_DB_FILENAME = ".harvest_state.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    url             TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'pending',
    category        TEXT,
    title           TEXT,
    started_at      TEXT,
    completed_at    TEXT,
    error           TEXT,
    result_file     TEXT,
    extractor       TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""


class StateManager:
    """
    SQLite-backed job state manager for a single project.

    Status lifecycle:
        pending → in_progress → completed
                              → failed
    """

    def __init__(self, project: str):
        self.project = project
        self.db_path = config.get_project_output_dir(project) / _DB_FILENAME
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    def close(self):
        """Close the database connection."""
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ── Job lifecycle ────────────────────────────────────────────────────

    def add_job(self, url: str, category: str = "", title: str = "") -> bool:
        """
        Add a new job (idempotent — skips if URL already exists).
        Returns True if the job was newly added.
        """
        now = datetime.now(timezone.utc).isoformat()
        try:
            self._conn.execute(
                "INSERT INTO jobs (url, status, category, title, created_at) VALUES (?, 'pending', ?, ?, ?)",
                (url, category, title, now),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Already exists

    def start_job(self, url: str, extractor: str = ""):
        """Mark a job as in_progress."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE jobs SET status = 'in_progress', started_at = ?, extractor = ? WHERE url = ?",
            (now, extractor, url),
        )
        self._conn.commit()

    def complete_job(self, url: str, result_file: str = ""):
        """Mark a job as completed."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE jobs SET status = 'completed', completed_at = ?, result_file = ?, error = NULL WHERE url = ?",
            (now, result_file, url),
        )
        self._conn.commit()

    def fail_job(self, url: str, error: str = ""):
        """Mark a job as failed."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE jobs SET status = 'failed', completed_at = ?, error = ? WHERE url = ?",
            (now, error, url),
        )
        self._conn.commit()

    def reset_failed(self):
        """Reset all failed jobs back to pending for retry."""
        self._conn.execute(
            "UPDATE jobs SET status = 'pending', error = NULL, started_at = NULL, completed_at = NULL WHERE status = 'failed'",
        )
        self._conn.commit()

    def reset_in_progress(self):
        """Reset any in_progress jobs back to pending (crash recovery)."""
        self._conn.execute(
            "UPDATE jobs SET status = 'pending', started_at = NULL WHERE status = 'in_progress'",
        )
        self._conn.commit()

    # ── Queries ──────────────────────────────────────────────────────────

    def is_completed(self, url: str) -> bool:
        """Check if a URL has already been successfully downloaded."""
        row = self._conn.execute(
            "SELECT status FROM jobs WHERE url = ?", (url,)
        ).fetchone()
        return row is not None and row["status"] == "completed"

    def get_status(self, url: str) -> str | None:
        """Get the status of a specific URL."""
        row = self._conn.execute(
            "SELECT status FROM jobs WHERE url = ?", (url,)
        ).fetchone()
        return row["status"] if row else None

    def get_pending(self) -> list[dict]:
        """Return all pending jobs."""
        return self._query_jobs("pending")

    def get_failed(self) -> list[dict]:
        """Return all failed jobs."""
        return self._query_jobs("failed")

    def get_completed(self) -> list[dict]:
        """Return all completed jobs."""
        return self._query_jobs("completed")

    def get_all(self) -> list[dict]:
        """Return all jobs."""
        rows = self._conn.execute("SELECT * FROM jobs ORDER BY created_at").fetchall()
        return [dict(r) for r in rows]

    def get_counts(self) -> dict:
        """Return a summary of job counts by status."""
        rows = self._conn.execute(
            "SELECT status, COUNT(*) as count FROM jobs GROUP BY status"
        ).fetchall()
        counts = {r["status"]: r["count"] for r in rows}
        counts["total"] = sum(counts.values())
        return counts

    # ── Internal ─────────────────────────────────────────────────────────

    def _query_jobs(self, status: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY created_at",
            (status,),
        ).fetchall()
        return [dict(r) for r in rows]
