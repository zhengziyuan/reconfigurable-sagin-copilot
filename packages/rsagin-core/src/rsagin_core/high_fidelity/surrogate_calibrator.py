from __future__ import annotations

from typing import Any


def calibrate_l1_surrogate(samples: list[dict[str, Any]]) -> dict[str, Any]:
    if not samples:
        return {"bias_db": 0.0, "status": "no_samples"}
    deltas = [float(item.get("shadow_loss_delta_db", 0.0)) for item in samples]
    bias = sum(deltas) / len(deltas)
    return {
        "bias_db": round(bias, 4),
        "sample_count": len(samples),
        "status": "calibrated_proxy",
    }
