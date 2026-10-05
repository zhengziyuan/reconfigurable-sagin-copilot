from __future__ import annotations

import math
from typing import Any

from rsagin_core.models import NodeType, Scenario


def summarize_multi_service_field(
    *,
    coverage_values: list[float],
    rate_values: list[float],
    peb_values: list[float],
    sensing_values: list[float],
    demand_weights: list[float],
    scenario: Scenario,
    selected_candidate_ids: list[str],
) -> dict[str, Any]:
    services = scenario.services
    min_rate = float(services.get("communication", {}).get("min_rate_mbps", 10.0))
    max_peb = float(services.get("localization", {}).get("max_peb_m", 5.0))
    min_sensing = float(services.get("sensing", {}).get("min_score", 0.55))
    total = max(len(rate_values), 1)
    weighted_total = sum(demand_weights) or float(total)

    violations = [
        int(coverage < 0.5 or rate < min_rate or peb > max_peb or sensing < min_sensing)
        for coverage, rate, peb, sensing in zip(coverage_values, rate_values, peb_values, sensing_values, strict=False)
    ]
    weighted_violations = sum(v * w for v, w in zip(violations, demand_weights, strict=False)) / weighted_total
    selected_nodes = [node for node in scenario.candidate_nodes if node.id in set(selected_candidate_ids)]
    cost = sum(node.cost for node in selected_nodes)
    covered_cells = max(sum(1 for value in coverage_values if value >= 0.5), 1)
    avg_rate = sum(rate_values) / max(len(rate_values), 1)
    weather = scenario.grid.get("weather", {})
    rain_rate = float(weather.get("rain_rate_mm_h", 0.0))
    uncertainty_weather = min(1.0, rain_rate / 80.0)
    risk_score = min(1.0, 0.55 * weighted_violations + 0.25 * uncertainty_weather + 0.20 * _deployment_complexity(selected_nodes))
    energy = _energy_proxy_kwh(selected_nodes)
    backhaul = _backhaul_capacity_mbps(scenario, selected_nodes)
    compute = _compute_latency_ms(scenario, selected_nodes)

    return {
        "multi_service_field": {
            "communication_utility_sum_rate": round(sum(rate_values), 3),
            "communication_utility_pf": round(sum(math.log1p(max(rate, 0.0)) for rate in rate_values), 3),
            "localization_utility": round(sum(max(0.0, 1.0 - peb / max(max_peb, 0.1)) for peb in peb_values) / total, 4),
            "sensing_utility": round(sum(min(1.0, value / max(min_sensing, 0.01)) for value in sensing_values) / total, 4),
            "sla_violation_percent": round(weighted_violations * 100.0, 2),
            "risk_score": round(risk_score, 4),
        },
        "engineering": {
            "cost_per_covered_cell": round(cost / covered_cells, 4),
            "cost_per_mbps": round(cost / max(avg_rate, 1e-6), 4),
            "energy_proxy_kwh": round(energy, 3),
            "backhaul_bottleneck_mbps": round(backhaul, 3),
            "compute_latency_proxy_ms": round(compute, 2),
            "deployment_complexity": round(_deployment_complexity(selected_nodes), 3),
        },
    }


def _deployment_complexity(nodes) -> float:
    if not nodes:
        return 0.05
    type_weight = {
        NodeType.RIS: 0.16,
        NodeType.MIS: 0.22,
        NodeType.MA_ARRAY: 0.18,
        NodeType.UAV_RELAY: 0.30,
    }
    return min(1.0, sum(type_weight.get(node.type, 0.12) for node in nodes))


def _energy_proxy_kwh(nodes) -> float:
    energy = 0.0
    for node in nodes:
        if node.type == NodeType.UAV_RELAY:
            energy += 1.6
        elif node.type == NodeType.MIS:
            energy += 0.28
        elif node.type == NodeType.RIS:
            elements = (node.reconfigurable.num_elements_x or 16) * (node.reconfigurable.num_elements_y or 16)
            energy += 0.04 + elements / 4096.0 * 0.18
        elif node.type == NodeType.MA_ARRAY:
            energy += 0.32
        else:
            energy += 0.18
    return energy


def _backhaul_capacity_mbps(scenario: Scenario, nodes) -> float:
    fixed_backhaul = 180.0 + 70.0 * sum(1 for node in scenario.fixed_nodes if node.type in {NodeType.GROUND_STATION, NodeType.SATELLITE_LEO})
    uav_penalty = 35.0 * sum(1 for node in nodes if node.type == NodeType.UAV_RELAY)
    return max(25.0, fixed_backhaul - uav_penalty)


def _compute_latency_ms(scenario: Scenario, nodes) -> float:
    base = 42.0
    edge_gain = 7.0 * sum(1 for node in scenario.fixed_nodes if node.type == NodeType.GROUND_STATION)
    uav_gain = 4.0 * sum(1 for node in nodes if node.type == NodeType.UAV_RELAY)
    return max(8.0, base - edge_gain - uav_gain + 2.5 * len(nodes))
