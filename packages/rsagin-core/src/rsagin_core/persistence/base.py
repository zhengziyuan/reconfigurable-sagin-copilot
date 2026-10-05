from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PlanningStore(ABC):
    """Production replacement boundary for project, scenario, run and job storage."""

    @abstractmethod
    def list_projects(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def save_run(self, payload: dict[str, Any], *, run_type: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def create_job(self, *, job_type: str, request: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def update_job(self, job_id: str, **fields: Any) -> dict[str, Any]:
        raise NotImplementedError


class ArtifactIndex(ABC):
    """Boundary used by local files, MinIO, S3 or object-store backed deployments."""

    @abstractmethod
    def put_json(self, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_json(self, key: str) -> dict[str, Any]:
        raise NotImplementedError
