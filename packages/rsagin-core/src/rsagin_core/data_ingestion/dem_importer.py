from __future__ import annotations


def load_dem_asset(path: str) -> dict:
    return {
        "asset_type": "dem",
        "path": path,
        "status": "adapter_ready",
        "supported_outputs": ["terrain_height_grid", "line_of_sight_mask", "sionna_scene_heightmap"],
    }
