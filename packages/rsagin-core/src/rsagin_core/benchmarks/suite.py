from __future__ import annotations

import time
from typing import Any

from rsagin_core.models import Scenario
from rsagin_core.optimization import optimize_deployment
from rsagin_core.simulation import simulate_scenario

from .baselines import geometry_heuristic_baseline, random_like_baseline


def benchmark_suite(scenario: Scenario, model_profile: str = "closed_form_v0") -> dict[str, Any]:
    rows = []
    rows.append(_row("no_deployment", lambda: simulate_scenario(scenario, [], model_profile, run_id="bench_none")))
    rows.append(_row("random_like", lambda: random_like_baseline(scenario, model_profile)))
    rows.append(_row("geometry_heuristic", lambda: geometry_heuristic_baseline(scenario, model_profile)))
    rows.append(_row("greedy_fast", lambda: optimize_deployment(scenario, model_profile=model_profile, solver="greedy_fast").optimized_run))
    rows.append(_row("exhaustive_pareto", lambda: optimize_deployment(scenario, model_profile=model_profile, solver="exhaustive_pareto").optimized_run))
    best_objective = max(float(row["objective_score"]) for row in rows)
    for row in rows:
        row["optimality_gap"] = round(best_objective - float(row["objective_score"]), 4)
    return {
        "suite_id": "rsagin_v05_planning_suite",
        "model_profile": model_profile,
        "rows": sorted(rows, key=lambda item: item["objective_score"], reverse=True),
        "ablation_axes": [
            "L0 vs L1 channel profile",
            "with vs without reconfigurable nodes",
            "greedy vs exact Pareto solver",
            "resource allocation baselines",
            "robustness under weather/channel/hardware uncertainty",
        ],
    }


def _row(name: str, factory) -> dict[str, Any]:
    start = time.perf_counter()
    run = factory()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return {
        "algorithm": name,
        "runtime_ms": round(elapsed_ms, 2),
        "coverage_percent": run.summary["coverage_percent"],
        "avg_rate_mbps": run.summary["avg_rate_mbps"],
        "p5_rate_mbps": run.summary["p5_rate_mbps"],
        "p95_peb_m": run.summary["p95_peb_m"],
        "avg_sensing_score": run.summary["avg_sensing_score"],
        "selected_cost": run.summary["selected_cost"],
        "objective_score": run.summary["objective_score"],
        "selected_candidate_ids": run.selected_candidate_ids,
    }
