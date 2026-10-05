from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ArtifactStore(ABC):
    """Object-store contract for run artifacts and evidence bundles."""

    @abstractmethod
    def put_json(self, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def put_bytes(self, key: str, payload: bytes, *, content_type: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_json(self, key: str) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def url_for(self, key: str) -> str:
        raise NotImplementedError
