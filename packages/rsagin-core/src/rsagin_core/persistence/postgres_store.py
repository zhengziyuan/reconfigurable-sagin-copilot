from __future__ import annotations

from typing import Any


class PostgresPlanningStore:
    """Postgres adapter placeholder with the same contract as the SQLite store.

    The local prototype uses SQLite for zero-config execution. This class marks
    the production swap point: wire SQLAlchemy or asyncpg here, keep API
    handlers unchanged, and move JSON payloads into JSONB columns.
    """

    backend = "postgres"

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def health(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "status": "not_configured",
            "dsn_present": bool(self.dsn),
            "next_step": "Implement SQLAlchemy models for projects, scenarios, runs, jobs and reports.",
        }
