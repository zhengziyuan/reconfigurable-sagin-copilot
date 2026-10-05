from __future__ import annotations

from typing import Any


def summarize_percentiles(samples: list[dict[str, Any]], key: str) -> dict[str, float]:
    values = sorted(float(item["summary"][key]) for item in samples)
    if not values:
        return {"p5": 0.0, "p50": 0.0, "p95": 0.0}
    return {
        "p5": round(_percentile(values, 5), 3),
        "p50": round(_percentile(values, 50), 3),
        "p95": round(_percentile(values, 95), 3),
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    index = (len(values) - 1) * percentile / 100.0
    low = int(index)
    high = min(low + 1, len(values) - 1)
    if low == high:
        return values[low]
    return values[low] * (high - index) + values[high] * (index - low)
