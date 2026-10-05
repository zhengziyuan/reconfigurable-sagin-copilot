from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_geojson_asset(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    features = payload.get("features", []) if payload.get("type") == "FeatureCollection" else [payload]
    return {
        "asset_type": "geojson",
        "feature_count": len(features),
        "geometry_types": sorted({feature.get("geometry", {}).get("type", "unknown") for feature in features}),
        "quality": {
            "has_crs": "crs" in payload,
            "has_features": bool(features),
            "warnings": [] if features else ["GeoJSON asset has no features."],
        },
        "raw": payload,
    }
