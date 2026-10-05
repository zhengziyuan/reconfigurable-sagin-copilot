from __future__ import annotations

from typing import Any


HIGHER_IS_BETTER = {"coverage", "rate", "sensing"}
LOWER_IS_BETTER = {"localization_peb", "sla_violation", "risk"}


def normalize_run_layers(run_payload: Any) -> dict[str, Any]:
    payload = _to_dict(run_payload)
    layers = payload.get("layers", {}) if isinstance(payload, dict) else {}
    normalized: dict[str, Any] = {}
    for metric_name, layer in layers.items():
        layer_dict = _to_dict(layer)
        cells = [_to_dict(cell) for cell in layer_dict.get("cells", [])]
        normalized[metric_name] = {
            "metric_name": metric_name,
            "unit": layer_dict.get("unit", ""),
            "cells": cells,
            "statistics": layer_statistics(cells),
        }
    return normalized


def layer_statistics(cells: list[dict[str, Any]]) -> dict[str, float]:
    values = [float(cell.get("value", 0.0)) for cell in cells]
    if not values:
        return {"count": 0, "min": 0.0, "max": 0.0, "mean": 0.0, "p5": 0.0, "p50": 0.0, "p95": 0.0}
    ordered = sorted(values)
    return {
        "count": float(len(values)),
        "min": round(ordered[0], 4),
        "max": round(ordered[-1], 4),
        "mean": round(sum(values) / len(values), 4),
        "p5": round(_percentile(ordered, 0.05), 4),
        "p50": round(_percentile(ordered, 0.50), 4),
        "p95": round(_percentile(ordered, 0.95), 4),
    }


def diff_layers(baseline_run: Any, candidate_run: Any) -> dict[str, Any]:
    baseline_layers = normalize_run_layers(baseline_run)
    candidate_layers = normalize_run_layers(candidate_run)
    metrics = sorted(set(baseline_layers) & set(candidate_layers))
    diffs = {}
    for metric in metrics:
        baseline_cells = {cell.get("cell_id"): cell for cell in baseline_layers[metric]["cells"]}
        delta_cells = []
        for cell in candidate_layers[metric]["cells"]:
            cell_id = cell.get("cell_id")
            before = float(baseline_cells.get(cell_id, {}).get("value", 0.0))
            after = float(cell.get("value", 0.0))
            delta = after - before
            benefit = -delta if metric in LOWER_IS_BETTER else delta
            delta_cells.append(
                {
                    "cell_id": cell_id,
                    "lat": cell.get("lat"),
                    "lon": cell.get("lon"),
                    "before": round(before, 4),
                    "after": round(after, 4),
                    "delta": round(delta, 4),
                    "benefit": round(benefit, 4),
                }
            )
        diffs[metric] = {
            "metric_name": metric,
            "direction": "lower_is_better" if metric in LOWER_IS_BETTER else "higher_is_better",
            "cells": delta_cells,
            "statistics": layer_statistics([{"value": item["benefit"]} for item in delta_cells]),
        }
    return {"metrics": metrics, "diffs": diffs}


def run_diagnosis(run_payload: Any) -> dict[str, Any]:
    payload = _to_dict(run_payload)
    summary = payload.get("summary", {})
    findings: list[dict[str, Any]] = []
    coverage = float(summary.get("coverage_percent", 0.0))
    p5_rate = float(summary.get("p5_rate_mbps", 0.0))
    p95_peb = float(summary.get("p95_peb_m", 999.0))
    risk = float(summary.get("risk_score", 1.0))
    if coverage < 90:
        findings.append({"level": "warning", "metric": "coverage", "message": "覆盖率未达到工程演示目标，建议生成 RIS/MIS 或低空平台候选点。"})
    if p5_rate < 10:
        findings.append({"level": "warning", "metric": "rate", "message": "边缘速率偏低，建议检查回传瓶颈和热点带宽分配。"})
    if p95_peb > 10:
        findings.append({"level": "warning", "metric": "localization_peb", "message": "定位尾部误差偏高，建议增加几何多样性或 MA 阵列候选点。"})
    if risk > 0.35:
        findings.append({"level": "critical", "metric": "risk", "message": "综合风险偏高，需要鲁棒扰动和敏感性实验复核。"})
    return {
        "run_id": payload.get("run_id"),
        "scenario_id": payload.get("scenario_id"),
        "findings": findings,
        "field_schema": {
            "coverage": "0/1 覆盖场",
            "rate": "Mbps 容量场",
            "localization_peb": "m 定位精度场",
            "sensing": "score 感知性能场",
            "sla_violation": "0/1 SLA 违约场",
            "risk": "0-1 风险场",
        },
    }


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    index = min(max(q, 0.0), 1.0) * (len(values) - 1)
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    weight = index - lower
    return values[lower] * (1.0 - weight) + values[upper] * weight


def _to_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return {}
