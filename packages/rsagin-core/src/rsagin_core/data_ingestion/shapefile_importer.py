from __future__ import annotations


def load_shapefile_asset(path: str) -> dict:
    return {
        "asset_type": "shapefile",
        "path": path,
        "status": "adapter_ready",
        "message": "Install pyshp/geopandas in a production environment to enable native Shapefile import.",
    }
