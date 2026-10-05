from __future__ import annotations

from .registry import plugin_registry


def load_plugin_descriptor(plugin_id: str) -> dict | None:
    for group in plugin_registry().values():
        for item in group:
            if item["id"] == plugin_id:
                return item
    return None
