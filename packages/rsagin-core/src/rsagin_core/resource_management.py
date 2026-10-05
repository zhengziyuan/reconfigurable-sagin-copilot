from __future__ import annotations

import math
import time
from typing import Any

import numpy as np

from .geo import generate_grid, haversine_m
from .models import GridCell, Node, NodeType, PositionLLA, Scenario
from .radio import dbm_to_mw, mw_to_dbm, node_extra_loss_db, rx_power_dbm, thermal_noise_dbm
from .simulation import SERVING_TYPES, _shadow_zone_loss_db, _link_powers

RESOURCE_MANAGEMENT_REFERENCES = [
    {
        "name": "Hypatia",
        "url": "https://github.com/snkas/hypatia",
        "note": "LEO time-varying topology, routing, packet simulation, and link utilization workflow.",
    },
    {
        "name": "Sionna",
        "url": "https://github.com/NVlabs/sionna",
        "note": "Reproducible communication-system simulation patterns and link-level abstractions.",
    },
    {
        "name": "ns-3-leo",
        "url": "https://github.com/dadada/ns-3-leo",
        "note": "LEO mobility, propagation loss, satellite-ground and inter-satellite channel modeling.",
    },
    {
        "name": "StarryNet",
        "url": "https://github.com/SpaceNetLab/StarryNet",
        "note": "Satellite Internet emulation APIs for routing, damage, recovery, ping, and perf experiments.",
    },
    {
        "name": "WMMSE / alternating optimization",
        "url": "https://doi.org/10.1109/TSP.2011.2147784",
        "note": "Weighted sum-rate maximization through the weighted-MMSE equivalence and alternating updates.",
    },
    {
        "name": "Proportional Fair scheduling",
        "url": "https://doi.org/10.1109/JCN.2010.5710556",
        "note": "Throughput and fairness balancing through proportional-fair scheduling utilities.",
    },
]


def plan_resources(
    scenario: Scenario,
    selected_candidate_ids: list[str] | None = None,
    method: str = "wmmse",
    max_flows: int = 24,
    iterations: int = 24,
    run_id: str | None = None,
    model_profile: str = "closed_form_v0",
) -> dict[str, Any]:
    """Create a reproducible resource-management plan for a selected topology.

    This is an engineering-grade L0 reproduction of common SAGIN resource
    management ideas: association by strongest feasible link, demand-aware
    bandwidth allocation, UCB-style exploration scores, and a SISO WMMSE power
    update for weighted sum-rate under per-transmitter power budgets.
    """

    if method not in {"max_sinr", "weighted_greedy", "proportional_fair", "ucb_bandit", "wmmse"}:
        raise ValueError(f"Unknown resource method: {method}")
    if not 1 <= max_flows <= 64 or not 1 <= iterations <= 100:
        raise ValueError("Resource planning supports 1-64 flows and 1-100 iterations.")
    selected_candidate_ids = selected_candidate_ids or []
    run_id = run_id or f"resource_{int(time.time() * 1000)}"
    grid = _top_demand_cells(scenario, max_flows)
    transmitters = _active_transmitters(scenario, selected_candidate_ids)
    if not grid or not transmitters:
        return _empty_plan(run_id, scenario, selected_candidate_ids, method)

    helpers = [node for node in scenario.candidate_nodes if node.enabled and node.id in selected_candidate_ids and node.type not in SERVING_TYPES]
    channel = _channel_matrix(scenario, grid, transmitters, model_profile, helpers)
    associations = np.argmax(channel, axis=1)
    weights = np.array([max(cell.demand_weight, 0.05) for cell in grid], dtype=float)
    bandwidth_hz = float(scenario.spectrum.get("bandwidth_hz", 100e6))
    noise_mw = dbm_to_mw(thermal_noise_dbm(bandwidth_hz / max(len(grid), 1), float(scenario.spectrum.get("noise_figure_db", 7.0))))
    pmax_mw = np.array([max(dbm_to_mw(node.radio.tx_power_dbm), 1e-6) for node in transmitters], dtype=float)

    max_sinr = _evaluate_plan(
        grid,
        transmitters,
        channel,
        associations,
        _equal_power(associations, pmax_mw),
        _equal_bandwidth(len(grid), bandwidth_hz),
        noise_mw,
        "max_sinr",
    )

    greedy = _evaluate_plan(
        grid,
        transmitters,
        channel,
        associations,
        _greedy_power(channel, associations, pmax_mw, weights),
        _bandwidth_share(weights, bandwidth_hz),
        noise_mw,
        "weighted_greedy",
    )
    bandit = _evaluate_plan(
        grid,
        transmitters,
        channel,
        _ucb_associations(channel, weights),
        _greedy_power(channel, _ucb_associations(channel, weights), pmax_mw, weights),
        _bandwidth_share(weights, bandwidth_hz),
        noise_mw,
        "ucb_bandit",
    )

    fair_associations = _proportional_fair_associations(channel, weights)
    proportional_fair = _evaluate_plan(
        grid,
        transmitters,
        channel,
        fair_associations,
        _greedy_power(channel, fair_associations, pmax_mw, np.sqrt(weights)),
        _proportional_fair_bandwidth(channel, fair_associations, weights, bandwidth_hz),
        noise_mw,
        "proportional_fair",
    )

    wmmse_powers, wmmse_trace = _wmmse_power(channel, associations, pmax_mw, weights, noise_mw, iterations)
    wmmse = _evaluate_plan(
        grid,
        transmitters,
        channel,
        associations,
        wmmse_powers,
        _bandwidth_share(weights, bandwidth_hz),
        noise_mw,
        "wmmse",
    )

    plans = {
        "max_sinr": max_sinr,
        "weighted_greedy": greedy,
        "proportional_fair": proportional_fair,
        "ucb_bandit": bandit,
        "wmmse": wmmse,
    }
    selected_result = plans.get(method, wmmse)
    trace = wmmse_trace if selected_result["method"] == "wmmse" else [
        {"iteration": 0, "weighted_sum_rate": selected_result["summary"]["weighted_sum_rate"]}
    ]

    access_backhaul = _access_backhaul_summary(scenario, selected_candidate_ids, selected_result["summary"])

    return {
        "run_id": run_id,
        "scenario_id": scenario.id,
        "method": selected_result["method"],
        "model_profile": model_profile,
        "selected_candidate_ids": selected_candidate_ids,
        "summary": {**selected_result["summary"], "access_backhaul": access_backhaul},
        "flows": selected_result["flows"],
        "transmitters": selected_result["transmitters"],
        "iterations": trace,
        "benchmarks": {
            "max_sinr": max_sinr["summary"],
            "weighted_greedy": greedy["summary"],
            "proportional_fair": proportional_fair["summary"],
            "ucb_bandit": bandit["summary"],
            "wmmse": wmmse["summary"],
        },
        "references": RESOURCE_MANAGEMENT_REFERENCES,
        "assumptions": [
            "Top demand grid cells are treated as scheduled user/task flows.",
            "Each flow is associated to one serving transmitter per scheduling epoch.",
            "RIS/MIS/MA gains are already reflected by the selected topology and link budget proxy.",
            "The WMMSE block is a SISO weighted sum-rate reproduction for planning, not a full MIMO precoder.",
            "The selected L0/L1 link-budget kernel is shared with coverage simulation; intra-epoch cochannel leakage remains a planning approximation.",
            "Proportional-fair allocation is a single-epoch load-balancing heuristic; backhaul capacity is a planning estimate.",
        ],
    }


def _empty_plan(run_id: str, scenario: Scenario, selected_candidate_ids: list[str], method: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "scenario_id": scenario.id,
        "method": method,
        "selected_candidate_ids": selected_candidate_ids,
        "summary": {
            "scheduled_flows": 0,
            "active_transmitters": 0,
            "sum_rate_mbps": 0.0,
            "weighted_sum_rate": 0.0,
            "p5_flow_rate_mbps": 0.0,
            "jain_fairness": 0.0,
            "avg_power_utilization": 0.0,
            "access_backhaul": {
                "access_sum_rate_mbps": 0.0,
                "backhaul_capacity_mbps": 0.0,
                "end_to_end_sum_rate_mbps": 0.0,
                "backhaul_bottleneck": False,
                "utilization": 0.0,
            },
        },
        "flows": [],
        "transmitters": [],
        "iterations": [],
        "benchmarks": {},
        "references": RESOURCE_MANAGEMENT_REFERENCES,
        "assumptions": [],
    }


def _access_backhaul_summary(scenario: Scenario, selected_candidate_ids: list[str], summary: dict[str, Any]) -> dict[str, Any]:
    selected_nodes = [node for node in scenario.candidate_nodes if node.id in set(selected_candidate_ids)]
    fixed_backhaul = 180.0 + 70.0 * sum(1 for node in scenario.fixed_nodes if node.type in {NodeType.GROUND_STATION, NodeType.SATELLITE_LEO})
    aerial_relay_penalty = 35.0 * sum(1 for node in selected_nodes if node.type == NodeType.UAV_RELAY)
    portable_gain = 120.0 * sum(1 for node in selected_nodes if node.type == NodeType.GROUND_STATION)
    backhaul_capacity = max(25.0, fixed_backhaul + portable_gain - aerial_relay_penalty)
    access_rate = float(summary.get("sum_rate_mbps", 0.0))
    end_to_end = min(access_rate, backhaul_capacity)
    return {
        "access_sum_rate_mbps": round(access_rate, 3),
        "backhaul_capacity_mbps": round(backhaul_capacity, 3),
        "end_to_end_sum_rate_mbps": round(end_to_end, 3),
        "backhaul_bottleneck": access_rate > backhaul_capacity,
        "utilization": round(end_to_end / max(backhaul_capacity, 1e-9), 4),
        "diagnosis": "回传受限，建议增加地面站或卫星回传容量。" if access_rate > backhaul_capacity else "当前主要瓶颈在接入侧或无线覆盖侧。",
    }


def _active_transmitters(scenario: Scenario, selected_candidate_ids: list[str]) -> list[Node]:
    selected = set(selected_candidate_ids)
    fixed = [node for node in scenario.fixed_nodes if node.enabled and node.type in SERVING_TYPES]
    candidates = [
        node
        for node in scenario.candidate_nodes
        if node.enabled and node.id in selected and node.type in SERVING_TYPES
    ]
    return fixed + candidates


def _top_demand_cells(scenario: Scenario, max_flows: int) -> list[GridCell]:
    grid = generate_grid(scenario.region, scenario.grid)
    return sorted(grid, key=lambda cell: cell.demand_weight, reverse=True)[:max(1, max_flows)]


def _channel_matrix(scenario: Scenario, grid: list[GridCell], transmitters: list[Node], model_profile: str = "closed_form_v0", helpers: list[Node] | None = None) -> np.ndarray:
    frequency_hz = float(scenario.spectrum.get("carrier_frequency_hz", 28e9))
    channel = np.zeros((len(grid), len(transmitters)), dtype=float)
    for row, cell in enumerate(grid):
        point = PositionLLA(lat=cell.lat, lon=cell.lon, alt_m=float(scenario.grid.get("user_height_m", 1.5)))
        links = {link["node_id"]: link for link in _link_powers(point, transmitters, helpers or [], frequency_hz, scenario, model_profile)}
        for col, node in enumerate(transmitters):
            rx_dbm_at_1mw = links[node.id]["rx_dbm"] - node.radio.tx_power_dbm if node.id in links else -300.0
            channel[row, col] = max(dbm_to_mw(rx_dbm_at_1mw), 1e-18)
    return channel


def _bandwidth_share(weights: np.ndarray, bandwidth_hz: float) -> np.ndarray:
    shaped = np.sqrt(np.maximum(weights, 1e-6))
    return bandwidth_hz * shaped / max(float(np.sum(shaped)), 1e-9)


def _equal_bandwidth(flow_count: int, bandwidth_hz: float) -> np.ndarray:
    return np.full(flow_count, bandwidth_hz / max(flow_count, 1), dtype=float)


def _equal_power(associations: np.ndarray, pmax_mw: np.ndarray) -> np.ndarray:
    powers = np.zeros(len(associations), dtype=float)
    for tx_index, max_power in enumerate(pmax_mw):
        flow_indices = np.where(associations == tx_index)[0]
        if len(flow_indices):
            powers[flow_indices] = max_power / len(flow_indices)
    return powers


def _proportional_fair_associations(channel: np.ndarray, weights: np.ndarray) -> np.ndarray:
    loads = np.zeros(channel.shape[1], dtype=float)
    associations = np.zeros(channel.shape[0], dtype=int)
    order = np.argsort(-weights)
    for flow_index in order:
        row = channel[flow_index]
        normalized = row / max(float(np.max(row)), 1e-18)
        score = weights[flow_index] * normalized / (1.0 + loads)
        choice = int(np.argmax(score))
        associations[flow_index] = choice
        loads[choice] += max(weights[flow_index], 0.05)
    return associations


def _proportional_fair_bandwidth(
    channel: np.ndarray,
    associations: np.ndarray,
    weights: np.ndarray,
    bandwidth_hz: float,
) -> np.ndarray:
    direct = np.array([channel[index, associations[index]] for index in range(len(associations))], dtype=float)
    quality = direct / max(float(np.max(direct)), 1e-18)
    utility_weight = np.sqrt(np.maximum(weights, 0.05)) / np.sqrt(np.maximum(quality, 0.08))
    utility_weight = np.minimum(utility_weight, np.percentile(utility_weight, 90))
    return bandwidth_hz * utility_weight / max(float(np.sum(utility_weight)), 1e-9)


def _greedy_power(channel: np.ndarray, associations: np.ndarray, pmax_mw: np.ndarray, weights: np.ndarray) -> np.ndarray:
    powers = np.zeros(channel.shape[0], dtype=float)
    for tx_index in range(len(pmax_mw)):
        flow_indices = np.where(associations == tx_index)[0]
        if len(flow_indices) == 0:
            continue
        local_weights = weights[flow_indices] * channel[flow_indices, tx_index]
        local_weights = local_weights / max(float(np.sum(local_weights)), 1e-12)
        powers[flow_indices] = pmax_mw[tx_index] * local_weights
    return powers


def _ucb_associations(channel: np.ndarray, weights: np.ndarray) -> np.ndarray:
    counts = np.ones(channel.shape[1], dtype=float)
    associations: list[int] = []
    for t, row in enumerate(channel, start=2):
        normalized = row / max(float(np.max(row)), 1e-18)
        exploration = np.sqrt(2.0 * math.log(t + 1.0) / counts)
        score = weights[t - 2] * normalized + 0.08 * exploration
        choice = int(np.argmax(score))
        associations.append(choice)
        counts[choice] += 1.0
    return np.array(associations, dtype=int)


def _wmmse_power(
    channel: np.ndarray,
    associations: np.ndarray,
    pmax_mw: np.ndarray,
    weights: np.ndarray,
    noise_mw: float,
    iterations: int,
) -> tuple[np.ndarray, list[dict[str, float]]]:
    powers = _greedy_power(channel, associations, pmax_mw, weights)
    best_powers = powers.copy()
    best_utility = _weighted_sinr_utility(channel, associations, powers, weights, noise_mw)
    trace: list[dict[str, float]] = []
    direct = np.array([channel[k, associations[k]] for k in range(channel.shape[0])], dtype=float)

    for iteration in range(max(1, iterations)):
        total_rx = _received_total(channel, associations, powers) + noise_mw
        sqrt_signal = np.sqrt(np.maximum(direct * powers, 1e-18))
        equalizers = sqrt_signal / np.maximum(total_rx, 1e-18)
        mse = np.maximum(1.0 - 2.0 * equalizers * sqrt_signal + equalizers * equalizers * total_rx, 1e-9)
        wmmse_weights = weights / mse

        updated = np.zeros_like(powers)
        for tx_index in range(len(pmax_mw)):
            flow_indices = np.where(associations == tx_index)[0]
            if len(flow_indices) == 0:
                continue
            lambda_low = 0.0
            lambda_high = 1.0
            while _tx_power_for_lambda(channel, associations, equalizers, wmmse_weights, flow_indices, tx_index, lambda_high) > pmax_mw[tx_index]:
                lambda_high *= 2.0
                if lambda_high > 1e18:
                    break
            for _ in range(40):
                lambda_mid = (lambda_low + lambda_high) / 2.0
                trial_power = _tx_power_for_lambda(channel, associations, equalizers, wmmse_weights, flow_indices, tx_index, lambda_mid)
                if trial_power > pmax_mw[tx_index]:
                    lambda_low = lambda_mid
                else:
                    lambda_high = lambda_mid
            for flow_index in flow_indices:
                numerator = wmmse_weights[flow_index] * equalizers[flow_index] * math.sqrt(max(direct[flow_index], 1e-18))
                denominator = lambda_high + sum(
                    wmmse_weights[i] * equalizers[i] * equalizers[i] * channel[i, tx_index]
                    for i in range(channel.shape[0])
                )
                updated[flow_index] = (numerator / max(denominator, 1e-18)) ** 2
        powers = 0.55 * powers + 0.45 * updated
        utility = _weighted_sinr_utility(channel, associations, powers, weights, noise_mw)
        if utility > best_utility:
            best_utility = utility
            best_powers = powers.copy()
        trace.append(
            {
                "iteration": iteration + 1,
                "weighted_sum_rate": round(utility, 6),
                "best_weighted_sum_rate": round(best_utility, 6),
                "allocated_power_mw": round(float(np.sum(powers)), 6),
            }
        )
    return best_powers, trace


def _weighted_sinr_utility(
    channel: np.ndarray,
    associations: np.ndarray,
    powers: np.ndarray,
    weights: np.ndarray,
    noise_mw: float,
) -> float:
    sinr = _sinr(channel, associations, powers, noise_mw)
    return float(np.sum(weights * np.log2(1.0 + np.maximum(sinr, 0.0))))


def _tx_power_for_lambda(
    channel: np.ndarray,
    associations: np.ndarray,
    equalizers: np.ndarray,
    weights: np.ndarray,
    flow_indices: np.ndarray,
    tx_index: int,
    lambda_value: float,
) -> float:
    total = 0.0
    for flow_index in flow_indices:
        direct = max(channel[flow_index, associations[flow_index]], 1e-18)
        numerator = weights[flow_index] * equalizers[flow_index] * math.sqrt(direct)
        denominator = lambda_value + sum(
            weights[i] * equalizers[i] * equalizers[i] * channel[i, tx_index]
            for i in range(channel.shape[0])
        )
        total += (numerator / max(denominator, 1e-18)) ** 2
    return total


def _received_total(channel: np.ndarray, associations: np.ndarray, powers: np.ndarray) -> np.ndarray:
    total = np.zeros(channel.shape[0], dtype=float)
    for flow_index in range(channel.shape[0]):
        for other_index, tx_index in enumerate(associations):
            total[flow_index] += channel[flow_index, tx_index] * powers[other_index]
    return total


def _flow_rates(
    channel: np.ndarray,
    associations: np.ndarray,
    powers: np.ndarray,
    bandwidth_hz: np.ndarray,
    noise_mw: float,
) -> np.ndarray:
    sinr = _sinr(channel, associations, powers, noise_mw)
    return bandwidth_hz * np.log2(1.0 + sinr) / 1e6


def _sinr(channel: np.ndarray, associations: np.ndarray, powers: np.ndarray, noise_mw: float) -> np.ndarray:
    values = np.zeros(channel.shape[0], dtype=float)
    for flow_index, tx_index in enumerate(associations):
        signal = channel[flow_index, tx_index] * powers[flow_index]
        total = noise_mw
        for other_index, other_tx in enumerate(associations):
            if other_index == flow_index:
                continue
            total += 0.08 * channel[flow_index, other_tx] * powers[other_index]
        values[flow_index] = signal / max(total, 1e-18)
    return values


def _evaluate_plan(
    grid: list[GridCell],
    transmitters: list[Node],
    channel: np.ndarray,
    associations: np.ndarray,
    powers: np.ndarray,
    bandwidth_hz: np.ndarray,
    noise_mw: float,
    method: str,
) -> dict[str, Any]:
    weights = np.array([max(cell.demand_weight, 0.05) for cell in grid], dtype=float)
    sinr = _sinr(channel, associations, powers, noise_mw)
    rates = bandwidth_hz * np.log2(1.0 + sinr) / 1e6
    utilization_by_tx = []
    flows = []
    for flow_index, cell in enumerate(grid):
        tx_index = int(associations[flow_index])
        tx = transmitters[tx_index]
        flows.append(
            {
                "cell_id": cell.id,
                "lat": round(cell.lat, 6),
                "lon": round(cell.lon, 6),
                "serving_node": tx.id,
                "serving_type": tx.type.value,
                "demand_weight": round(cell.demand_weight, 3),
                "bandwidth_mhz": round(float(bandwidth_hz[flow_index] / 1e6), 3),
                "power_dbm": round(mw_to_dbm(max(float(powers[flow_index]), 1e-12)), 3),
                "sinr_db": round(10.0 * math.log10(max(float(sinr[flow_index]), 1e-18)), 3),
                "rate_mbps": round(float(rates[flow_index]), 3),
            }
        )
    transmitters_payload = []
    for tx_index, tx in enumerate(transmitters):
        allocated = float(np.sum(powers[np.where(associations == tx_index)]))
        pmax = max(dbm_to_mw(tx.radio.tx_power_dbm), 1e-9)
        utilization = allocated / pmax
        utilization_by_tx.append(utilization)
        transmitters_payload.append(
            {
                "node_id": tx.id,
                "node_type": tx.type.value,
                "allocated_power_mw": round(allocated, 6),
                "max_power_mw": round(pmax, 6),
                "utilization": round(utilization, 4),
                "scheduled_flows": int(np.sum(associations == tx_index)),
            }
        )

    summary = {
        "scheduled_flows": len(flows),
        "active_transmitters": len([item for item in transmitters_payload if item["scheduled_flows"] > 0]),
        "sum_rate_mbps": round(float(np.sum(rates)), 3),
        "weighted_sum_rate": round(float(np.sum(weights * rates) / max(float(np.sum(weights)), 1e-9)), 3),
        "p5_flow_rate_mbps": round(_percentile([float(rate) for rate in rates], 5), 3),
        "jain_fairness": round(_jain_fairness([float(rate) for rate in rates]), 4),
        "avg_power_utilization": round(float(np.mean(utilization_by_tx)), 4) if utilization_by_tx else 0.0,
    }
    return {
        "method": method,
        "summary": summary,
        "flows": sorted(flows, key=lambda item: item["demand_weight"], reverse=True),
        "transmitters": transmitters_payload,
    }


def _jain_fairness(values: list[float]) -> float:
    if not values:
        return 0.0
    numerator = sum(values) ** 2
    denominator = len(values) * sum(value * value for value in values)
    return numerator / denominator if denominator else 0.0


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile / 100.0
    low = math.floor(index)
    high = math.ceil(index)
    if low == high:
        return ordered[int(index)]
    return ordered[low] * (high - index) + ordered[high] * (index - low)
