from __future__ import annotations


def load_kml_asset(path: str) -> dict:
    return {
        "asset_type": "kml",
        "path": path,
        "status": "adapter_ready",
        "supported_outputs": ["region_polygon", "route_lines", "site_marks"],
    }
