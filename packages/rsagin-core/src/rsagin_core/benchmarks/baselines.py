from __future__ import annotations

from rsagin_core.models import NodeType, Scenario
from rsagin_core.simulation import simulate_scenario


def random_like_baseline(scenario: Scenario, model_profile: str = "closed_form_v0"):
    budget = scenario.optimization.get("budget", {})
    max_cost = float(budget.get("max_total_cost", 999.0))
    selected: list[str] = []
    cost = 0.0
    for node in sorted(scenario.candidate_nodes, key=lambda item: (item.type.value, item.cost, item.id)):
        if cost + node.cost <= max_cost:
            selected.append(node.id)
            cost += node.cost
    return simulate_scenario(scenario, selected_candidate_ids=selected[:3], model_profile=model_profile, run_id="bench_random_like")


def geometry_heuristic_baseline(scenario: Scenario, model_profile: str = "closed_form_v0"):
    type_priority = {
        NodeType.UAV_RELAY: 0,
        NodeType.RIS: 1,
        NodeType.MA_ARRAY: 2,
        NodeType.MIS: 3,
    }
    selected = [
        node.id
        for node in sorted(
            scenario.candidate_nodes,
            key=lambda item: (type_priority.get(item.type, 9), item.cost),
        )[:3]
    ]
    return simulate_scenario(scenario, selected_candidate_ids=selected, model_profile=model_profile, run_id="bench_geometry")
