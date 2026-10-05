from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .base import ArtifactStore


class LocalArtifactStore(ArtifactStore):
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_json(self, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
        return self.put_bytes(key, text.encode("utf-8"), content_type="application/json")

    def put_bytes(self, key: str, payload: bytes, *, content_type: str) -> dict[str, Any]:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return {
            "key": key,
            "path": str(path),
            "content_type": content_type,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
        }

    def get_json(self, key: str) -> dict[str, Any]:
        path = self.root / key
        return json.loads(path.read_text(encoding="utf-8"))

    def url_for(self, key: str) -> str:
        return str((self.root / key).resolve())
