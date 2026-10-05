from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable


class JobExecutor(ABC):
    """Execution boundary for local synchronous, Celery, Ray or cloud workers."""

    @abstractmethod
    def submit(self, job_type: str, request: dict[str, Any], handler: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError
