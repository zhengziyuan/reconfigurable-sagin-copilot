from __future__ import annotations


def plugin_registry() -> dict[str, list[dict]]:
    return {
        "channel_models": [
            {"id": "fspl_l0", "class": "rsagin_core.channel_models.FSPL", "status": "stable"},
            {"id": "tr38901_l1", "class": "rsagin_core.channel_models.TR38901Subset", "status": "partial_traceable"},
            {"id": "sionna_rt_l2", "class": "rsagin_core.high_fidelity.sionna_adapter.SionnaRTAdapter", "status": "adapter_ready"},
        ],
        "optimizers": [
            {"id": "greedy_fast", "class": "rsagin_core.optimization.GreedyDeploymentOptimizer", "status": "stable"},
            {"id": "exhaustive_pareto", "class": "rsagin_core.optimization.ExactSmallPareto", "status": "stable_small_scale"},
            {"id": "robust_greedy", "class": "rsagin_core.uncertainty.monte_carlo.RobustWrapper", "status": "prototype"},
        ],
        "hardware": [
            {"id": "ris_planning", "class": "rsagin_core.hardware.catalogs.RISPlanningModel", "status": "stable_proxy"},
            {"id": "mis_planning", "class": "rsagin_core.hardware.catalogs.MISPlanningModel", "status": "prototype"},
            {"id": "ma_planning", "class": "rsagin_core.hardware.catalogs.MAPlanningModel", "status": "prototype"},
        ],
        "reports": [
            {"id": "research_report", "template_type": "research", "status": "ready"},
            {"id": "enterprise_report", "template_type": "enterprise", "status": "ready"},
            {"id": "grant_report", "template_type": "grant", "status": "ready"},
        ],
    }
