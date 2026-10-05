from __future__ import annotations

from typing import Any

from rsagin_core.models import SimulationRun


def select_high_fidelity_rois(run: SimulationRun, limit: int = 8) -> list[dict[str, Any]]:
    rate_layer = run.layers.get("rate")
    peb_layer = run.layers.get("localization_peb")
    if not rate_layer or not peb_layer:
        return []
    peb_by_id = {cell.cell_id: cell.value for cell in peb_layer.cells}
    candidates = []
    for cell in rate_layer.cells:
        rate = float(cell.value)
        peb = float(peb_by_id.get(cell.cell_id, 0.0))
        risk = max(0.0, (12.0 - rate) / 12.0) + max(0.0, (peb - 5.0) / 20.0)
        if risk > 0.15:
            candidates.append(
                {
                    "cell_id": cell.cell_id,
                    "lat": cell.lat,
                    "lon": cell.lon,
                    "roi_priority": round(risk, 4),
                    "reason": "Low rate or weak localization confidence; send to local high-fidelity calibration.",
                }
            )
    return sorted(candidates, key=lambda item: item["roi_priority"], reverse=True)[:limit]
