from __future__ import annotations

from typing import Any, Callable

from .executor_base import JobExecutor


class CeleryJobExecutor(JobExecutor):
    """Celery replacement point for production-scale async execution."""

    backend = "celery"

    def __init__(self, broker_url: str, result_backend: str | None = None) -> None:
        self.broker_url = broker_url
        self.result_backend = result_backend

    def submit(self, job_type: str, request: dict[str, Any], handler: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        return {
            "job_type": job_type,
            "status": "not_configured",
            "request": request,
            "next_step": "Register a Celery task per job_type and call delay(request) here.",
            "broker_present": bool(self.broker_url),
            "result_backend_present": bool(self.result_backend),
        }
