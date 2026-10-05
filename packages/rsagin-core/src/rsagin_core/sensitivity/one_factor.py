from __future__ import annotations

from typing import Any

from rsagin_core.models import Scenario
from rsagin_core.simulation import simulate_scenario


def one_factor_sensitivity(
    scenario: Scenario,
    selected_candidate_ids: list[str],
    model_profile: str = "standards_l1",
) -> dict[str, Any]:
    baseline = simulate_scenario(scenario, selected_candidate_ids=selected_candidate_ids, model_profile=model_profile, run_id="sensitivity_base")
    experiments = [
        ("rain_rate_mm_h", "grid.weather.rain_rate_mm_h", 0.7, 1.35),
        ("bandwidth_hz", "spectrum.bandwidth_hz", 0.75, 1.25),
        ("budget", "services.cost.max_budget", 0.85, 1.15),
    ]
    items = []
    for name, path, low_scale, high_scale in experiments:
        low_run = _scaled_run(scenario, selected_candidate_ids, model_profile, path, low_scale, f"sens_{name}_low")
        high_run = _scaled_run(scenario, selected_candidate_ids, model_profile, path, high_scale, f"sens_{name}_high")
        items.append(
            {
                "parameter": name,
                "low_scale": low_scale,
                "high_scale": high_scale,
                "objective_delta_low": round(low_run.summary["objective_score"] - baseline.summary["objective_score"], 4),
                "objective_delta_high": round(high_run.summary["objective_score"] - baseline.summary["objective_score"], 4),
                "coverage_delta_span": round(high_run.summary["coverage_percent"] - low_run.summary["coverage_percent"], 4),
                "rate_delta_span": round(high_run.summary["avg_rate_mbps"] - low_run.summary["avg_rate_mbps"], 4),
            }
        )
    return {
        "method": "one_factor_at_a_time",
        "baseline_objective": baseline.summary["objective_score"],
        "items": sorted(items, key=lambda item: abs(item["objective_delta_high"] - item["objective_delta_low"]), reverse=True),
    }


def _scaled_run(scenario: Scenario, selected: list[str], model_profile: str, path: str, scale: float, run_id: str):
    copy = scenario.model_copy(deep=True)
    current: Any = copy
    parts = path.split(".")
    for part in parts[:-1]:
        current = current[part] if isinstance(current, dict) else getattr(current, part)
    leaf = parts[-1]
    if isinstance(current, dict):
        current[leaf] = float(current.get(leaf, 0.0)) * scale
    else:
        setattr(current, leaf, float(getattr(current, leaf)) * scale)
    return simulate_scenario(copy, selected_candidate_ids=selected, model_profile=model_profile, run_id=run_id)
