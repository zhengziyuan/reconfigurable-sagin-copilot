from __future__ import annotations

from typing import Any


def parse_rt_result(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "parsed",
        "cell_count": len(payload.get("cells", [])),
        "calibration_terms": payload.get("calibration_terms", {}),
    }
