from __future__ import annotations

from typing import Any


def built_in_problem_templates() -> list[dict[str, Any]]:
    return [
        {
            "id": "robust_isac_reconfigurable_planning",
            "name": "可重构 SAGIN 鲁棒通感部署规划",
            "decision_variables": {
                "deployment": ["ris_selection", "mis_selection", "uav_position", "ma_mode"],
                "resource": ["user_association", "bandwidth_allocation", "power_allocation", "surface_codeword"],
                "temporal": ["uav_trajectory", "satellite_time_window", "ris_switching_state"],
            },
            "objectives": {
                "maximize": ["key_area_coverage", "cell_edge_rate", "sensing_detection_score"],
                "minimize": ["peb_95_percentile", "total_cost", "sla_violation_probability"],
            },
            "constraints": {
                "hard": ["max_ris_count", "max_uav_count", "max_budget"],
                "physical": ["ris_angular_feasibility", "uav_altitude_range", "backhaul_capacity"],
                "robust": ["coverage_chance_constraint", "rate_chance_constraint"],
            },
            "recommended_algorithms": {
                "small_scale": ["exhaustive_pareto"],
                "medium_scale": ["robust_greedy", "local_search"],
                "large_scale": ["surrogate_pareto", "multi_fidelity_screening"],
            },
        },
        {
            "id": "cost_benefit_enterprise_planning",
            "name": "企业成本收益型可重构网络规划",
            "decision_variables": {
                "deployment": ["site_upgrade", "ris_selection", "uav_relay_count"],
                "resource": ["sla_class_association", "backhaul_reservation"],
            },
            "objectives": {
                "maximize": ["sla_satisfaction", "marginal_benefit"],
                "minimize": ["capex", "opex", "deployment_risk"],
            },
            "constraints": {
                "hard": ["budget", "site_permission", "installation_height"],
                "physical": ["power_supply", "backhaul_capacity"],
            },
            "recommended_algorithms": {
                "small_scale": ["exact_small"],
                "medium_scale": ["greedy_fast", "robust_greedy"],
                "large_scale": ["surrogate_assisted_screening"],
            },
        },
    ]
