from __future__ import annotations


def demand_grid_from_points(points: list[dict], default_weight: float = 1.0) -> dict:
    total = sum(float(item.get("weight", default_weight)) for item in points)
    return {
        "asset_type": "demand_points",
        "point_count": len(points),
        "total_demand_weight": round(total, 4),
        "quality": {
            "warnings": [] if points else ["Demand input is empty; scenario will use uniform demand."],
        },
    }
