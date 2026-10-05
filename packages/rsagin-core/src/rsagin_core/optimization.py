from __future__ import annotations

import itertools
import random
import time

from .models import Node, NodeType, OptimizationRun, Recommendation, Scenario
from .simulation import objective_score, simulate_scenario
from .uncertainty import robust_evaluate


def optimize_deployment(
    scenario: Scenario,
    model_profile: str = "closed_form_v0",
    run_id: str | None = None,
    solver: str | None = None,
) -> OptimizationRun:
    run_id = run_id or f"opt_{int(time.time() * 1000)}"
    baseline = simulate_scenario(
        scenario,
        selected_candidate_ids=[],
        model_profile=model_profile,
        run_id=f"{run_id}_baseline",
    )
    solver = solver or str(scenario.optimization.get("solver", "greedy_fast"))
    if solver in {"exhaustive_pareto", "exact_small"}:
        if len(scenario.candidate_nodes) > 14:
            raise ValueError("Exact Pareto supports at most 14 candidate nodes; use NSGA-II for larger scenes.")
        return _optimize_exhaustive(scenario, baseline, model_profile, run_id, solver)
    if solver in {"nsga2_pareto", "nsga2"}:
        parameters = scenario.optimization.get("nsga2", {})
        return _optimize_nsga2(scenario, baseline, model_profile, run_id, solver,
            population_size=int(parameters.get("population_size", 18)), generations=int(parameters.get("generations", 8)), seed=int(parameters.get("seed", 20260711)))
    if solver in {"robust_greedy", "robust_pareto"}:
        run = _optimize_greedy(scenario, baseline, model_profile, run_id, solver)
        run.summary["robust_evaluation"] = robust_evaluate(
            scenario,
            selected_candidate_ids=run.selected_candidate_ids,
            model_profile=model_profile,
            samples=8,
        )
        return run
    if solver != "greedy_fast":
        raise ValueError(f"Unknown deployment solver: {solver}")
    return _optimize_greedy(scenario, baseline, model_profile, run_id, solver)


def _optimize_greedy(
    scenario: Scenario,
    baseline,
    model_profile: str,
    run_id: str,
    solver: str,
) -> OptimizationRun:
    selected: list[str] = []
    marginal_summaries: dict[str, tuple[dict, dict]] = {}
    current = baseline
    best_score = objective_score(current.summary, scenario)
    budget = scenario.optimization.get("budget", {})
    max_total_cost = float(budget.get("max_total_cost", 999.0))
    max_counts = _max_counts(budget)

    while True:
        feasible = [
            node
            for node in scenario.candidate_nodes
            if node.id not in selected and _is_feasible(node, scenario, selected, max_total_cost, max_counts)
        ]
        if not feasible:
            break

        best_node: Node | None = None
        best_candidate_run = None
        best_candidate_score = best_score
        for node in feasible:
            candidate_ids = [*selected, node.id]
            candidate_run = simulate_scenario(
                scenario,
                selected_candidate_ids=candidate_ids,
                model_profile=model_profile,
                run_id=f"{run_id}_try_{len(candidate_ids)}_{node.id}",
            )
            score = objective_score(candidate_run.summary, scenario)
            if score > best_candidate_score + 0.001:
                best_node = node
                best_candidate_run = candidate_run
                best_candidate_score = score

        if best_node is None or best_candidate_run is None:
            break
        marginal_summaries[best_node.id] = (current.summary, best_candidate_run.summary)
        selected.append(best_node.id)
        current = best_candidate_run
        best_score = best_candidate_score

    optimized = simulate_scenario(
        scenario,
        selected_candidate_ids=selected,
        model_profile=model_profile,
        run_id=f"{run_id}_optimized",
    )
    node_by_id = {node.id: node for node in scenario.candidate_nodes}
    recommendations = []
    for node_id in selected:
        node = node_by_id[node_id]
        before, after = marginal_summaries.get(node_id, (baseline.summary, optimized.summary))
        recommendations.append(_recommendation(node, before, after))
    summary = _comparison_summary(baseline.summary, optimized.summary)
    summary["solver"] = solver
    summary["evaluated_candidates"] = len(marginal_summaries)
    summary.update(_optimization_explainability(scenario, optimized.summary, recommendations, marginal_summaries))
    return OptimizationRun(
        run_id=run_id,
        scenario_id=scenario.id,
        baseline_run=baseline,
        optimized_run=optimized,
        selected_candidate_ids=selected,
        recommendations=recommendations,
        summary=summary,
    )


def _optimize_exhaustive(
    scenario: Scenario,
    baseline,
    model_profile: str,
    run_id: str,
    solver: str,
) -> OptimizationRun:
    budget = scenario.optimization.get("budget", {})
    max_total_cost = float(budget.get("max_total_cost", 999.0))
    max_counts = _max_counts(budget)
    best_ids: list[str] = []
    best_run = baseline
    best_score = objective_score(baseline.summary, scenario)
    evaluated = 0
    pareto: list[dict] = []

    candidates = list(scenario.candidate_nodes)
    for size in range(1, len(candidates) + 1):
        for combo in itertools.combinations(candidates, size):
            ids = [node.id for node in combo]
            if not _is_combo_feasible(combo, max_total_cost, max_counts):
                continue
            evaluated += 1
            run = simulate_scenario(
                scenario,
                selected_candidate_ids=ids,
                model_profile=model_profile,
                run_id=f"{run_id}_exact_{evaluated}",
            )
            score = objective_score(run.summary, scenario)
            pareto.append(
                {
                    "selected_candidate_ids": ids,
                    "objective_score": round(score, 4),
                    "selected_cost": run.summary["selected_cost"],
                    "coverage_percent": run.summary["coverage_percent"],
                    "avg_rate_mbps": run.summary["avg_rate_mbps"],
                    "avg_peb_m": run.summary["avg_peb_m"],
                }
            )
            if score > best_score + 1e-9:
                best_score = score
                best_ids = ids
                best_run = run

    node_by_id = {node.id: node for node in scenario.candidate_nodes}
    recommendations = [_recommendation(node_by_id[node_id], baseline.summary, best_run.summary) for node_id in best_ids]
    summary = _comparison_summary(baseline.summary, best_run.summary)
    summary["solver"] = solver
    summary["evaluated_candidates"] = evaluated
    summary["pareto_front"] = _pareto_front(pareto)[:8]
    summary.update(_optimization_explainability(scenario, best_run.summary, recommendations, {}))
    return OptimizationRun(
        run_id=run_id,
        scenario_id=scenario.id,
        baseline_run=baseline,
        optimized_run=best_run,
        selected_candidate_ids=best_ids,
        recommendations=recommendations,
        summary=summary,
    )


def _optimize_nsga2(
    scenario: Scenario,
    baseline,
    model_profile: str,
    run_id: str,
    solver: str,
    population_size: int = 18,
    generations: int = 8,
    seed: int = 20260711,
) -> OptimizationRun:
    """Binary NSGA-II reproduction for scalable multi-objective deployment.

    Each chromosome activates a subset of candidate nodes. Feasibility repair
    enforces cost and per-hardware limits before a chromosome is evaluated by
    the same physical simulation engine used by the other optimizers.
    """

    candidates = list(scenario.candidate_nodes)
    if not candidates:
        summary = _comparison_summary(baseline.summary, baseline.summary)
        summary.update({"solver": solver, "evaluated_candidates": 0, "pareto_front": []})
        summary.update(_optimization_explainability(scenario, baseline.summary, [], {}))
        return OptimizationRun(
            run_id=run_id,
            scenario_id=scenario.id,
            baseline_run=baseline,
            optimized_run=baseline,
            selected_candidate_ids=[],
            recommendations=[],
            summary=summary,
        )

    rng = random.Random(seed)
    budget = scenario.optimization.get("budget", {})
    max_total_cost = float(budget.get("max_total_cost", 999.0))
    max_counts = _max_counts(budget)
    chromosome_length = len(candidates)
    population_size = max(8, min(int(population_size), 40))
    generations = max(2, min(int(generations), 30))
    mutation_rate = 1.0 / chromosome_length
    cache: dict[tuple[int, ...], tuple[object, dict]] = {}
    evaluation_counter = 0

    def repair(chromosome: tuple[int, ...]) -> tuple[int, ...]:
        bits = list(chromosome)
        while True:
            combo = tuple(candidates[index] for index, active in enumerate(bits) if active)
            if _is_combo_feasible(combo, max_total_cost, max_counts):
                return tuple(bits)
            active_indices = [index for index, active in enumerate(bits) if active]
            if not active_indices:
                return tuple(bits)
            bits[rng.choice(active_indices)] = 0

    def evaluate(chromosome: tuple[int, ...]) -> tuple[object, dict]:
        nonlocal evaluation_counter
        chromosome = repair(chromosome)
        if chromosome in cache:
            return cache[chromosome]
        ids = [candidates[index].id for index, active in enumerate(chromosome) if active]
        evaluation_counter += 1
        run = simulate_scenario(
            scenario,
            selected_candidate_ids=ids,
            model_profile=model_profile,
            run_id=f"{run_id}_nsga2_{evaluation_counter}",
        )
        record = _pareto_record(ids, run.summary)
        cache[chromosome] = (run, record)
        return run, record

    population: list[tuple[int, ...]] = [tuple(0 for _ in candidates)]
    population.extend(tuple(1 if index == active else 0 for index in range(chromosome_length)) for active in range(chromosome_length))
    while len(population) < population_size:
        population.append(repair(tuple(1 if rng.random() < 0.38 else 0 for _ in candidates)))
    population = population[:population_size]
    convergence_trace: list[dict] = []

    for generation in range(generations):
        for chromosome in population:
            evaluate(chromosome)
        ranks, crowding = _nsga_rank_and_crowding(population, cache)

        def tournament() -> tuple[int, ...]:
            first, second = rng.choice(population), rng.choice(population)
            if ranks[first] != ranks[second]:
                return first if ranks[first] < ranks[second] else second
            return first if crowding[first] >= crowding[second] else second

        offspring: list[tuple[int, ...]] = []
        while len(offspring) < population_size:
            parent_a, parent_b = tournament(), tournament()
            if chromosome_length > 1 and rng.random() < 0.9:
                cut = rng.randrange(1, chromosome_length)
                child_a = parent_a[:cut] + parent_b[cut:]
                child_b = parent_b[:cut] + parent_a[cut:]
            else:
                child_a, child_b = parent_a, parent_b
            for child in (child_a, child_b):
                mutated = tuple(1 - bit if rng.random() < mutation_rate else bit for bit in child)
                offspring.append(repair(mutated))
                if len(offspring) >= population_size:
                    break

        combined = list(dict.fromkeys([*population, *offspring]))
        fill_attempts = 0
        while len(combined) < population_size and fill_attempts < population_size * 8:
            combined.append(repair(tuple(1 if rng.random() < 0.4 else 0 for _ in candidates)))
            combined = list(dict.fromkeys(combined))
            fill_attempts += 1
        if len(combined) < population_size:
            combined.extend(rng.choice(combined) for _ in range(population_size - len(combined)))
        for chromosome in combined:
            evaluate(chromosome)
        population = _nsga_select(combined, cache, population_size)
        generation_best = max((cache[item][1] for item in population), key=lambda value: value["objective_score"])
        convergence_trace.append(
            {
                "generation": generation + 1,
                "best_objective": generation_best["objective_score"],
                "front_size": len(_nsga_front(population, cache)),
                "evaluated": evaluation_counter,
            }
        )

    front_chromosomes = _nsga_front(population, cache)
    best_chromosome = max(population, key=lambda item: cache[item][1]["objective_score"])
    best_run, _ = cache[best_chromosome]
    best_ids = [candidates[index].id for index, active in enumerate(best_chromosome) if active]
    node_by_id = {node.id: node for node in candidates}
    recommendations = [_recommendation(node_by_id[node_id], baseline.summary, best_run.summary) for node_id in best_ids]
    summary = _comparison_summary(baseline.summary, best_run.summary)
    summary.update(
        {
            "solver": solver,
            "evaluated_candidates": evaluation_counter,
            "pareto_front": sorted(
                (cache[item][1] for item in front_chromosomes),
                key=lambda value: value["objective_score"],
                reverse=True,
            )[:12],
            "population_size": population_size,
            "generations": generations,
            "seed": seed,
            "convergence_trace": convergence_trace,
        }
    )
    summary.update(_optimization_explainability(scenario, best_run.summary, recommendations, {}))
    return OptimizationRun(
        run_id=run_id,
        scenario_id=scenario.id,
        baseline_run=baseline,
        optimized_run=best_run,
        selected_candidate_ids=best_ids,
        recommendations=recommendations,
        summary=summary,
    )


def _pareto_record(selected_ids: list[str], summary: dict) -> dict:
    return {
        "selected_candidate_ids": selected_ids,
        "objective_score": round(float(summary["objective_score"]), 4),
        "selected_cost": float(summary["selected_cost"]),
        "coverage_percent": float(summary["coverage_percent"]),
        "avg_rate_mbps": float(summary["avg_rate_mbps"]),
        "p5_rate_mbps": float(summary["p5_rate_mbps"]),
        "avg_peb_m": float(summary["avg_peb_m"]),
        "p95_peb_m": float(summary["p95_peb_m"]),
        "avg_sensing_score": float(summary["avg_sensing_score"]),
    }


def _nsga_objectives(record: dict) -> tuple[float, ...]:
    return (
        record["coverage_percent"],
        record["p5_rate_mbps"],
        record["avg_sensing_score"],
        -record["p95_peb_m"],
        -record["selected_cost"],
    )


def _nsga_dominates(first: dict, second: dict) -> bool:
    left, right = _nsga_objectives(first), _nsga_objectives(second)
    return all(a >= b for a, b in zip(left, right)) and any(a > b for a, b in zip(left, right))


def _nsga_front(population: list[tuple[int, ...]], cache: dict) -> list[tuple[int, ...]]:
    return [
        item
        for item in population
        if not any(other != item and _nsga_dominates(cache[other][1], cache[item][1]) for other in population)
    ]


def _nsga_rank_and_crowding(population: list[tuple[int, ...]], cache: dict) -> tuple[dict, dict]:
    remaining = list(dict.fromkeys(population))
    ranks: dict[tuple[int, ...], int] = {}
    crowding: dict[tuple[int, ...], float] = {item: 0.0 for item in remaining}
    rank = 0
    while remaining:
        front = [
            item
            for item in remaining
            if not any(other != item and _nsga_dominates(cache[other][1], cache[item][1]) for other in remaining)
        ]
        for item in front:
            ranks[item] = rank
        _assign_crowding(front, cache, crowding)
        remaining = [item for item in remaining if item not in set(front)]
        rank += 1
    return ranks, crowding


def _assign_crowding(front: list[tuple[int, ...]], cache: dict, crowding: dict) -> None:
    if not front:
        return
    for objective_index in range(5):
        ordered = sorted(front, key=lambda item: _nsga_objectives(cache[item][1])[objective_index])
        crowding[ordered[0]] = float("inf")
        crowding[ordered[-1]] = float("inf")
        low = _nsga_objectives(cache[ordered[0]][1])[objective_index]
        high = _nsga_objectives(cache[ordered[-1]][1])[objective_index]
        if high == low:
            continue
        for index in range(1, len(ordered) - 1):
            previous_value = _nsga_objectives(cache[ordered[index - 1]][1])[objective_index]
            next_value = _nsga_objectives(cache[ordered[index + 1]][1])[objective_index]
            crowding[ordered[index]] += (next_value - previous_value) / (high - low)


def _nsga_select(population: list[tuple[int, ...]], cache: dict, limit: int) -> list[tuple[int, ...]]:
    ranks, crowding = _nsga_rank_and_crowding(population, cache)
    return sorted(population, key=lambda item: (ranks[item], -crowding[item]))[:limit]


def _max_counts(budget: dict) -> dict[NodeType, int]:
    return {
        NodeType.RIS: int(budget.get("max_ris", 99)),
        NodeType.MIS: int(budget.get("max_mis", 99)),
        NodeType.UAV_RELAY: int(budget.get("max_uav", 99)),
        NodeType.MA_ARRAY: int(budget.get("max_ma", 99)),
    }


def _is_feasible(
    node: Node,
    scenario: Scenario,
    selected_ids: list[str],
    max_total_cost: float,
    max_counts: dict[NodeType, int],
) -> bool:
    selected_nodes = [item for item in scenario.candidate_nodes if item.id in set(selected_ids)]
    if sum(item.cost for item in selected_nodes) + node.cost > max_total_cost:
        return False
    selected_of_type = sum(1 for item in selected_nodes if item.type == node.type)
    return selected_of_type < max_counts.get(node.type, 99)


def _is_combo_feasible(combo: tuple[Node, ...], max_total_cost: float, max_counts: dict[NodeType, int]) -> bool:
    if sum(node.cost for node in combo) > max_total_cost:
        return False
    for node_type, max_count in max_counts.items():
        if sum(1 for node in combo if node.type == node_type) > max_count:
            return False
    return True


def _pareto_front(items: list[dict]) -> list[dict]:
    front = []
    for item in items:
        dominated = False
        for other in items:
            if other is item:
                continue
            better_or_equal = (
                other["objective_score"] >= item["objective_score"]
                and other["coverage_percent"] >= item["coverage_percent"]
                and other["avg_rate_mbps"] >= item["avg_rate_mbps"]
                and other["avg_peb_m"] <= item["avg_peb_m"]
                and other["selected_cost"] <= item["selected_cost"]
            )
            strictly_better = (
                other["objective_score"] > item["objective_score"]
                or other["coverage_percent"] > item["coverage_percent"]
                or other["avg_rate_mbps"] > item["avg_rate_mbps"]
                or other["avg_peb_m"] < item["avg_peb_m"]
                or other["selected_cost"] < item["selected_cost"]
            )
            if better_or_equal and strictly_better:
                dominated = True
                break
        if not dominated:
            front.append(item)
    return sorted(front, key=lambda value: value["objective_score"], reverse=True)


def _recommendation(node: Node, baseline: dict, optimized: dict) -> Recommendation:
    gains = {
        "coverage_percent": round(optimized["coverage_percent"] - baseline["coverage_percent"], 2),
        "avg_rate_mbps": round(optimized["avg_rate_mbps"] - baseline["avg_rate_mbps"], 2),
        "p5_rate_mbps": round(optimized["p5_rate_mbps"] - baseline["p5_rate_mbps"], 2),
        "avg_peb_m": round(baseline["avg_peb_m"] - optimized["avg_peb_m"], 2),
        "p95_peb_m": round(baseline["p95_peb_m"] - optimized["p95_peb_m"], 2),
        "avg_sensing_score": round(optimized["avg_sensing_score"] - baseline["avg_sensing_score"], 3),
    }
    if node.type == NodeType.RIS:
        reason = "部署 RIS 将能量重定向到遮挡或边缘单元，提升非视距覆盖。"
    elif node.type == NodeType.MIS:
        reason = "启用 MIS 形成透射/聚焦辅助，增强热点与感知单元。"
    elif node.type == NodeType.UAV_RELAY:
        reason = "在热点上方放置无人机中继，缩短空地链路并改善定位几何。"
    elif node.type == NodeType.MA_ARRAY:
        reason = "激活移动天线阵列获得局部孔径增益，提升边缘速率稳定性。"
    else:
        reason = "选择该候选节点，因为它提升了加权规划目标。"
    return Recommendation(
        node_id=node.id,
        node_type=node.type,
        reason=reason,
        expected_gain=gains,
    )


def _comparison_summary(baseline: dict, optimized: dict) -> dict:
    keys = [
        "coverage_percent",
        "avg_rate_mbps",
        "p5_rate_mbps",
        "avg_peb_m",
        "p95_peb_m",
        "avg_sensing_score",
        "selected_cost",
        "objective_score",
    ]
    return {
        "baseline": {key: baseline[key] for key in keys},
        "optimized": {key: optimized[key] for key in keys},
        "delta": {key: round(optimized[key] - baseline[key], 4) for key in keys},
    }


def _optimization_explainability(
    scenario: Scenario,
    optimized: dict,
    recommendations: list[Recommendation],
    marginal_summaries: dict[str, tuple[dict, dict]],
) -> dict:
    constraint_status = _constraint_status(scenario, optimized)
    feasible = all(item["satisfied"] for item in constraint_status)
    return {
        "optimization_status": "feasible" if feasible else "infeasible",
        "constraint_status": constraint_status,
        "infeasibility_explanation": [] if feasible else _infeasibility_explanation(constraint_status),
        "marginal_gain_trace": _marginal_gain_trace(recommendations, marginal_summaries),
    }


def _constraint_status(scenario: Scenario, summary: dict) -> list[dict]:
    communication = scenario.services.get("communication", {})
    localization = scenario.services.get("localization", {})
    sensing = scenario.services.get("sensing", {})
    cost = scenario.services.get("cost", {})
    min_rate = float(communication.get("min_rate_mbps", 10.0))
    min_coverage = float(communication.get("min_coverage_percent", 90.0))
    max_peb = float(localization.get("max_peb_m", 5.0))
    min_sensing = float(sensing.get("min_score", 0.55))
    max_budget = float(cost.get("max_budget", scenario.optimization.get("budget", {}).get("max_total_cost", 999.0)))
    checks = [
        ("coverage_percent", "覆盖率", summary.get("coverage_percent", 0.0), min_coverage, ">="),
        ("p5_rate_mbps", "边缘速率", summary.get("p5_rate_mbps", 0.0), min_rate, ">="),
        ("p95_peb_m", "P95 定位误差", summary.get("p95_peb_m", 999.0), max_peb, "<="),
        ("avg_sensing_score", "平均感知评分", summary.get("avg_sensing_score", 0.0), min_sensing, ">="),
        ("selected_cost", "部署成本", summary.get("selected_cost", 0.0), max_budget, "<="),
    ]
    status = []
    for key, label, value, target, operator in checks:
        value = float(value)
        satisfied = value >= target if operator == ">=" else value <= target
        margin = value - target if operator == ">=" else target - value
        status.append(
            {
                "metric": key,
                "label": label,
                "value": round(value, 4),
                "target": round(float(target), 4),
                "operator": operator,
                "margin": round(margin, 4),
                "satisfied": satisfied,
            }
        )
    return status


def _infeasibility_explanation(constraint_status: list[dict]) -> list[dict]:
    explanations = []
    for item in constraint_status:
        if item["satisfied"]:
            continue
        if item["metric"] == "selected_cost":
            action = "放宽预算、减少低收益候选点，或切换成本收益模板。"
        elif item["metric"] == "p95_peb_m":
            action = "增加几何分集，优先考虑 MA 阵列、空中平台或多站协同。"
        elif item["metric"] == "p5_rate_mbps":
            action = "检查回传容量、热点带宽和边缘遮挡，加入 RIS/MIS 或无人机中继。"
        elif item["metric"] == "coverage_percent":
            action = "在盲区边界生成更多候选点，并运行鲁棒贪心或 Pareto 搜索。"
        else:
            action = "提高感知节点密度或将该指标纳入更高权重的多目标优化。"
        explanations.append({"metric": item["metric"], "gap": item["margin"], "suggested_relaxation": action})
    return explanations


def _marginal_gain_trace(
    recommendations: list[Recommendation],
    marginal_summaries: dict[str, tuple[dict, dict]],
) -> list[dict]:
    trace = []
    for step, rec in enumerate(recommendations, start=1):
        before, after = marginal_summaries.get(rec.node_id, ({}, {}))
        trace.append(
            {
                "step": step,
                "node_id": rec.node_id,
                "node_type": rec.node_type.value if hasattr(rec.node_type, "value") else str(rec.node_type),
                "objective_before": round(float(before.get("objective_score", 0.0)), 4),
                "objective_after": round(float(after.get("objective_score", 0.0)), 4),
                "expected_gain": rec.expected_gain,
                "reason": rec.reason,
            }
        )
    return trace
