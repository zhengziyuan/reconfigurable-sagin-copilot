from __future__ import annotations


def load_osm_asset(path: str) -> dict:
    return {
        "asset_type": "osm",
        "path": path,
        "status": "adapter_ready",
        "supported_outputs": ["building_footprints", "roads", "candidate_facades"],
    }
