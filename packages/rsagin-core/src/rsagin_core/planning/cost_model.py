from __future__ import annotations

from typing import Any

from rsagin_core.models import NodeType, Scenario


def cost_benefit_summary(scenario: Scenario, selected_candidate_ids: list[str], summary: dict[str, Any]) -> dict[str, Any]:
    selected = [node for node in scenario.candidate_nodes if node.id in set(selected_candidate_ids)]
    capex = sum(_capex(node.type, node.cost) for node in selected)
    opex = sum(_opex(node.type, node.cost) for node in selected)
    benefit = (
        float(summary.get("coverage_percent", 0.0)) * 0.8
        + float(summary.get("p5_rate_mbps", 0.0)) * 1.2
        + max(0.0, 12.0 - float(summary.get("p95_peb_m", 20.0))) * 3.0
        + float(summary.get("avg_sensing_score", 0.0)) * 45.0
    )
    return {
        "capex_proxy": round(capex, 3),
        "opex_proxy": round(opex, 3),
        "maintenance_proxy": round(0.08 * capex + 0.15 * opex, 3),
        "benefit_proxy": round(benefit, 3),
        "benefit_cost_ratio": round(benefit / max(capex + opex, 1e-6), 4),
    }


def _capex(node_type: NodeType, cost: float) -> float:
    multiplier = {
        NodeType.RIS: 1.1,
        NodeType.MIS: 1.35,
        NodeType.MA_ARRAY: 1.25,
        NodeType.UAV_RELAY: 1.55,
    }.get(node_type, 1.0)
    return cost * multiplier


def _opex(node_type: NodeType, cost: float) -> float:
    multiplier = {
        NodeType.RIS: 0.10,
        NodeType.MIS: 0.12,
        NodeType.MA_ARRAY: 0.18,
        NodeType.UAV_RELAY: 0.42,
    }.get(node_type, 0.16)
    return cost * multiplier
