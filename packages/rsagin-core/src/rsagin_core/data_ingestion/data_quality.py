from __future__ import annotations

from typing import Any


def summarize_quality(preview: dict[str, Any]) -> dict[str, Any]:
    quality = preview.get("quality", {})
    errors = quality.get("errors", [])
    warnings = quality.get("warnings", [])
    return {
        "valid": bool(quality.get("valid")),
        "score": float(quality.get("score", 0.0)),
        "grade": "A" if quality.get("score", 0) >= 0.9 else "B" if quality.get("score", 0) >= 0.75 else "C",
        "blocking_errors": errors,
        "warnings": warnings,
        "recommended_action": "可直接入库" if not errors else "先修复必填列或越界坐标",
    }
