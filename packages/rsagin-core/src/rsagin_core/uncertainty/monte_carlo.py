from __future__ import annotations

import random
from typing import Any

from rsagin_core.models import Scenario
from rsagin_core.planning.sla import evaluate_sla, sla_constraints_from_services
from rsagin_core.simulation import simulate_scenario

from .confidence_layers import summarize_percentiles
from .cvar import cvar
from .distributions import sample_uncertainty


def robust_evaluate(
    scenario: Scenario,
    selected_candidate_ids: list[str] | None = None,
    model_profile: str = "standards_l1",
    samples: int = 12,
    seed: int = 20260707,
) -> dict[str, Any]:
    rng = random.Random(seed)
    base_weather = dict(scenario.grid.get("weather", {}))
    selected_candidate_ids = selected_candidate_ids or []
    runs: list[dict[str, Any]] = []
    constraints = sla_constraints_from_services(scenario.services)
    for index in range(max(1, samples)):
        draw = sample_uncertainty(base_weather, rng)
        perturbed = scenario.model_copy(deep=True)
        weather = dict(perturbed.grid.get("weather", {}))
        weather.update({k: v for k, v in draw.items() if k in {"rain_rate_mm_h", "water_vapor_density_g_m3", "pressure_hpa"}})
        perturbed.grid["weather"] = weather
        for zone in perturbed.grid.get("shadow_zones", []):
            zone["loss_db"] = float(zone.get("loss_db", 0.0)) * draw["shadow_loss_scale"]
        run = simulate_scenario(
            perturbed,
            selected_candidate_ids=selected_candidate_ids,
            model_profile=model_profile,
            run_id=f"robust_{index:03d}",
        )
        runs.append(
            {
                "sample": index,
                "uncertainty": {key: round(float(value), 4) for key, value in draw.items()},
                "summary": run.summary,
                "sla": evaluate_sla(run.summary, constraints),
            }
        )

    objective_values = [float(item["summary"]["objective_score"]) for item in runs]
    violation_probability = sum(1 for item in runs if item["sla"]["failed"] > 0) / max(len(runs), 1)
    return {
        "method": "monte_carlo_robust_evaluation",
        "samples": len(runs),
        "seed": seed,
        "model_profile": model_profile,
        "selected_candidate_ids": selected_candidate_ids,
        "percentiles": {
            "coverage_percent": summarize_percentiles(runs, "coverage_percent"),
            "p5_rate_mbps": summarize_percentiles(runs, "p5_rate_mbps"),
            "p95_peb_m": summarize_percentiles(runs, "p95_peb_m"),
            "objective_score": summarize_percentiles(runs, "objective_score"),
        },
        "risk": {
            "sla_violation_probability": round(violation_probability, 4),
            "objective_cvar_10": round(cvar(objective_values, alpha=0.10, lower_tail=True), 4),
            "stability_score": round(max(0.0, 1.0 - violation_probability), 4),
        },
        "samples_preview": runs[: min(6, len(runs))],
    }
