from __future__ import annotations

import math
import statistics
import time
from typing import Any

import numpy as np

from .geo import bearing_unit_xy, generate_grid, haversine_m, satellite_geometry
from .artifacts.manifest import build_run_manifest
from .channel_models import assumptions_for, channel_loss, fidelity_level, is_standards_profile
from .hardware.catalogs import hardware_catalog_summary
from .models import (
    GridCell,
    MetricCell,
    MetricLayer,
    Node,
    NodeType,
    PositionLLA,
    Scenario,
    SimulationRun,
)
from .planning.cost_model import cost_benefit_summary
from .planning.performance_field import summarize_multi_service_field
from .radio import (
    assisted_gain_to_cell_db,
    dbm_to_mw,
    mw_to_dbm,
    node_extra_loss_db,
    rx_power_dbm,
    thermal_noise_dbm,
)
from .validation.run_quality import evaluate_run_quality

DEFAULT_ASSUMPTIONS = [
    "Level-0 closed-form model.",
    "Free-space path loss with simplified excess losses.",
    "RIS/MIS/MA effects are conservative capped gain proxies.",
    "Localization and sensing values are planning proxies, not full CRB models.",
]

SERVING_TYPES = {
    NodeType.GROUND_BS,
    NodeType.GROUND_STATION,
    NodeType.SATELLITE_LEO,
    NodeType.SATELLITE_GEO,
    NodeType.HAPS,
    NodeType.UAV_RELAY,
    NodeType.MA_ARRAY,
}


def simulate_scenario(
    scenario: Scenario,
    selected_candidate_ids: list[str] | None = None,
    model_profile: str = "closed_form_v0",
    run_id: str | None = None,
) -> SimulationRun:
    selected_candidate_ids = selected_candidate_ids or []
    selected = {
        node.id
        for node in scenario.candidate_nodes
        if node.id in set(selected_candidate_ids)
    }
    run_id = run_id or f"run_{int(time.time() * 1000)}"
    grid = generate_grid(scenario.region, scenario.grid)
    active_nodes = [
        *[node for node in scenario.fixed_nodes if node.enabled],
        *[node for node in scenario.candidate_nodes if node.enabled and node.id in selected],
    ]
    serving_nodes = [node for node in active_nodes if node.type in SERVING_TYPES]
    helper_nodes = [
        node
        for node in active_nodes
        if node.type in {NodeType.RIS, NodeType.MIS, NodeType.MA_ARRAY, NodeType.UAV_RELAY}
    ]

    spectrum = scenario.spectrum
    frequency_hz = float(spectrum.get("carrier_frequency_hz", 28e9))
    bandwidth_hz = float(spectrum.get("bandwidth_hz", 100e6))
    noise_figure_db = float(spectrum.get("noise_figure_db", 7.0))
    threshold_db = float(spectrum.get("sinr_threshold_db", 0.0))
    efficiency = float(spectrum.get("implementation_efficiency", 0.68))
    noise_mw = dbm_to_mw(thermal_noise_dbm(bandwidth_hz, noise_figure_db))

    sinr_cells: list[MetricCell] = []
    coverage_cells: list[MetricCell] = []
    rate_cells: list[MetricCell] = []
    peb_cells: list[MetricCell] = []
    sensing_cells: list[MetricCell] = []
    sla_violation_cells: list[MetricCell] = []
    risk_cells: list[MetricCell] = []
    min_rate_mbps = float(scenario.services.get("communication", {}).get("min_rate_mbps", 10.0))
    max_peb_m = float(scenario.services.get("localization", {}).get("max_peb_m", 5.0))
    min_sensing_score = float(scenario.services.get("sensing", {}).get("min_score", 0.55))

    for cell in grid:
        point = PositionLLA(lat=cell.lat, lon=cell.lon, alt_m=float(scenario.grid.get("user_height_m", 1.5)))
        link_powers = _link_powers(point, serving_nodes, helper_nodes, frequency_hz, scenario, model_profile)
        best_link = max(link_powers, key=lambda item: item["rx_mw"], default=None)
        signal_mw = best_link["rx_mw"] if best_link else 0.0
        interference_mw = max(sum(item["rx_mw"] for item in link_powers) - signal_mw, 0.0) * 0.12
        sinr_linear = signal_mw / max(noise_mw + interference_mw, 1e-18)
        sinr_db = 10.0 * math.log10(max(sinr_linear, 1e-18))
        rate_mbps = efficiency * bandwidth_hz * math.log2(1.0 + sinr_linear) / 1e6
        coverage = 1.0 if sinr_db >= threshold_db else 0.0
        peb_m = _localization_peb(point, link_powers, serving_nodes)
        sensing_score = _sensing_score(point, active_nodes, helper_nodes)
        sla_violation = 1.0 if coverage < 0.5 or rate_mbps < min_rate_mbps or peb_m > max_peb_m or sensing_score < min_sensing_score else 0.0
        cell_risk = min(
            1.0,
            0.40 * sla_violation
            + 0.25 * max(0.0, (min_rate_mbps - rate_mbps) / max(min_rate_mbps, 1.0))
            + 0.20 * max(0.0, (peb_m - max_peb_m) / max(max_peb_m * 3.0, 1.0))
            + 0.15 * cell.demand_weight / max(float(scenario.grid.get("hotspot", {}).get("weight_boost", 1.8)), 1.0),
        )

        common = {
            "best_node": best_link["node_id"] if best_link else None,
            "sinr_db": round(sinr_db, 3),
            "rate_mbps": round(rate_mbps, 3),
            "peb_m": round(peb_m, 3),
            "sensing_score": round(sensing_score, 3),
            "sla_violation": round(sla_violation, 3),
            "risk_score": round(cell_risk, 3),
            "demand_weight": round(cell.demand_weight, 3),
        }
        if best_link:
            common.update(
                {
                    "channel_model": best_link.get("channel_model"),
                    "path_loss_db": round(float(best_link.get("path_loss_db", 0.0)), 3),
                    "extra_loss_db": round(float(best_link.get("extra_loss_db", 0.0)), 3),
                    "helper_gain_db": round(float(best_link.get("helper_gain_db", 0.0)), 3),
                    "shadow_loss_db": round(float(best_link.get("shadow_loss_db", 0.0)), 3),
                    "los_probability": round(float(best_link.get("los_probability", 1.0)), 4),
                    "elevation_deg": best_link.get("components", {}).get("elevation_deg"),
                    "rain_loss_db": best_link.get("components", {}).get("rain_loss_db"),
                    "gaseous_loss_db": best_link.get("components", {}).get("gaseous_loss_db"),
                }
            )
        sinr_cells.append(_metric_cell(cell, sinr_db, common))
        coverage_cells.append(_metric_cell(cell, coverage, common))
        rate_cells.append(_metric_cell(cell, rate_mbps, common))
        peb_cells.append(_metric_cell(cell, peb_m, common))
        sensing_cells.append(_metric_cell(cell, sensing_score, common))
        sla_violation_cells.append(_metric_cell(cell, sla_violation, common))
        risk_cells.append(_metric_cell(cell, cell_risk, common))

    summary = _summary(
        grid,
        coverage_cells,
        rate_cells,
        peb_cells,
        sensing_cells,
        sla_violation_cells,
        risk_cells,
        scenario,
        selected_candidate_ids,
    )
    layers = {
        "sinr": _layer(run_id, "sinr", "dB", model_profile, sinr_cells, summary),
        "coverage": _layer(run_id, "coverage", "0/1", model_profile, coverage_cells, summary),
        "rate": _layer(run_id, "rate", "Mbps", model_profile, rate_cells, summary),
        "localization_peb": _layer(run_id, "localization_peb", "m", model_profile, peb_cells, summary),
        "sensing": _layer(run_id, "sensing", "score", model_profile, sensing_cells, summary),
        "sla_violation": _layer(run_id, "sla_violation", "0/1", model_profile, sla_violation_cells, summary),
        "risk": _layer(run_id, "risk", "score", model_profile, risk_cells, summary),
    }

    run = SimulationRun(
        run_id=run_id,
        scenario_id=scenario.id,
        selected_candidate_ids=selected_candidate_ids,
        model_profile=model_profile,
        fidelity_level=fidelity_level(model_profile),
        assumptions=assumptions_for(model_profile, DEFAULT_ASSUMPTIONS),
        grid=grid,
        layers=layers,
        summary=summary,
    )
    run.summary["run_quality"] = evaluate_run_quality(run, scenario)
    run.summary["run_manifest"] = build_run_manifest(run, scenario)
    run.summary["hardware"] = hardware_catalog_summary(scenario, selected_candidate_ids)
    return run


def _link_powers(
    point: PositionLLA,
    serving_nodes: list[Node],
    helper_nodes: list[Node],
    frequency_hz: float,
    scenario: Scenario,
    model_profile: str,
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for node in serving_nodes:
        if node.type in {NodeType.SATELLITE_LEO, NodeType.SATELLITE_GEO} and satellite_geometry(node.position, point)[1] < float(scenario.grid.get("minimum_elevation_deg", 10.0)):
            continue
        distance = haversine_m(node.position, point)
        helper_gain = sum(
            assisted_gain_to_cell_db(helper, point, serving_nodes, frequency_hz)
            for helper in helper_nodes
            if helper.id != node.id
        )
        helper_gain = min(helper_gain, 18.0)
        shadow_loss = _shadow_zone_loss_db(point, node, scenario.grid)
        if is_standards_profile(model_profile):
            channel = channel_loss(scenario, node, point, frequency_hz, model_profile, scenario.grid)
            rx_dbm = (
                node.radio.tx_power_dbm
                + node.radio.antenna_gain_dbi
                + node.radio.rx_gain_dbi
                + helper_gain
                - channel.path_loss_db
                - node_extra_loss_db(node, distance)
                - shadow_loss
            )
        else:
            channel = channel_loss(scenario, node, point, frequency_hz, model_profile, scenario.grid)
            rx_dbm = rx_power_dbm(
                node.radio.tx_power_dbm,
                node.radio.antenna_gain_dbi,
                node.radio.rx_gain_dbi,
                distance,
                frequency_hz,
                extra_loss_db=node_extra_loss_db(node, distance) + shadow_loss,
                extra_gain_db=helper_gain,
            )
        links.append(
            {
                "node_id": node.id,
                "node_type": node.type.value,
                "distance_m": distance,
                "rx_dbm": rx_dbm,
                "rx_mw": dbm_to_mw(rx_dbm),
                "helper_gain_db": helper_gain,
                "shadow_loss_db": shadow_loss,
                "channel_model": channel.model,
                "path_loss_db": channel.path_loss_db,
                "extra_loss_db": channel.extra_loss_db,
                "los_probability": channel.los_probability,
                "components": channel.components,
            }
        )
    return links


def _shadow_zone_loss_db(point: PositionLLA, node: Node, grid_config: dict[str, Any]) -> float:
    loss = 0.0
    for zone in grid_config.get("shadow_zones", []):
        affected = set(zone.get("affected_types", []))
        if affected and node.type.value not in affected:
            continue
        center = PositionLLA(lat=float(zone["lat"]), lon=float(zone["lon"]), alt_m=point.alt_m)
        distance = haversine_m(center, point)
        radius = float(zone.get("radius_m", 1.0))
        if distance <= radius:
            loss += float(zone.get("loss_db", 0.0)) * (1.0 - 0.35 * distance / max(radius, 1.0))
    return loss


def _localization_peb(point: PositionLLA, links: list[dict[str, Any]], serving_nodes: list[Node]) -> float:
    if len(links) < 2:
        return 50.0

    node_by_id = {node.id: node for node in serving_nodes}
    j11, j22, j12 = 0.015, 0.015, 0.0
    for link in links:
        node = node_by_id.get(link["node_id"])
        if node is None:
            continue
        ux, uy = bearing_unit_xy(node.position, point)
        snr_weight = max(0.01, min(10.0, dbm_to_mw(link["rx_dbm"] + 105.0) / 10.0))
        j11 += snr_weight * ux * ux
        j22 += snr_weight * uy * uy
        j12 += snr_weight * ux * uy
    # Exact trace of the regularized 2x2 inverse avoids per-cell BLAS overhead.
    determinant = j11 * j22 - j12 * j12
    peb = math.sqrt((j11 + j22) / determinant) * 6.0 if determinant > 0 else 50.0
    return min(80.0, max(0.5, peb))


def _sensing_score(point: PositionLLA, active_nodes: list[Node], helper_nodes: list[Node]) -> float:
    score = 0.0
    for node in active_nodes:
        if node.type not in SERVING_TYPES:
            continue
        distance = max(haversine_m(node.position, point), 30.0)
        gain = 10.0 ** ((node.radio.antenna_gain_dbi + max(node.radio.tx_power_dbm - 30.0, 0.0)) / 20.0)
        score += gain / ((distance / 100.0) ** 2.6)
    score *= 0.12
    score += 0.03 * len([node for node in helper_nodes if node.type in {NodeType.RIS, NodeType.MIS, NodeType.MA_ARRAY}])
    return max(0.0, min(1.0, score))


def _summary(
    grid: list[GridCell],
    coverage_cells: list[MetricCell],
    rate_cells: list[MetricCell],
    peb_cells: list[MetricCell],
    sensing_cells: list[MetricCell],
    sla_violation_cells: list[MetricCell],
    risk_cells: list[MetricCell],
    scenario: Scenario,
    selected_candidate_ids: list[str],
) -> dict[str, Any]:
    weights = [cell.demand_weight for cell in grid]
    coverage = _weighted_mean([cell.value for cell in coverage_cells], weights)
    rate_values = [cell.value for cell in rate_cells]
    peb_values = [cell.value for cell in peb_cells]
    sensing_values = [cell.value for cell in sensing_cells]
    sla_values = [cell.value for cell in sla_violation_cells]
    risk_values = [cell.value for cell in risk_cells]
    selected_cost = sum(node.cost for node in scenario.candidate_nodes if node.id in set(selected_candidate_ids))

    summary = {
        "coverage_percent": round(coverage * 100.0, 2),
        "avg_rate_mbps": round(_weighted_mean(rate_values, weights), 2),
        "p5_rate_mbps": round(_percentile(rate_values, 5), 2),
        "avg_peb_m": round(_weighted_mean(peb_values, weights), 2),
        "p95_peb_m": round(_percentile(peb_values, 95), 2),
        "avg_sensing_score": round(_weighted_mean(sensing_values, weights), 3),
        "blind_cell_count": int(sum(1 for cell in coverage_cells if cell.value < 0.5)),
        "grid_cell_count": len(grid),
        "selected_candidate_count": len(selected_candidate_ids),
        "selected_cost": round(selected_cost, 2),
        "sla_violation_percent": round(_weighted_mean(sla_values, weights) * 100.0, 2),
        "risk_score": round(_weighted_mean(risk_values, weights), 4),
    }
    summary["objective_score"] = round(objective_score(summary, scenario), 4)
    summary.update(
        summarize_multi_service_field(
            coverage_values=[cell.value for cell in coverage_cells],
            rate_values=rate_values,
            peb_values=peb_values,
            sensing_values=sensing_values,
            demand_weights=weights,
            scenario=scenario,
            selected_candidate_ids=selected_candidate_ids,
        )
    )
    summary["cost_benefit"] = cost_benefit_summary(scenario, selected_candidate_ids, summary)
    return summary


def objective_score(summary: dict[str, Any], scenario: Scenario) -> float:
    objective = scenario.optimization.get("objective", {})
    services = scenario.services
    max_budget = float(services.get("cost", {}).get("max_budget", 1.0))
    max_budget = max(max_budget, 1.0)
    coverage_score = summary["coverage_percent"] / 100.0
    avg_rate_score = min(summary["avg_rate_mbps"] / 180.0, 1.4)
    edge_rate_score = min(summary["p5_rate_mbps"] / 120.0, 1.4)
    rate_score = 0.45 * avg_rate_score + 0.55 * edge_rate_score
    avg_loc_score = max(0.0, min(1.4, 1.0 - summary["avg_peb_m"] / 18.0))
    tail_loc_score = max(0.0, min(1.4, 1.0 - summary["p95_peb_m"] / 24.0))
    loc_score = 0.45 * avg_loc_score + 0.55 * tail_loc_score
    sense_score = min(summary["avg_sensing_score"] / 0.08, 1.3)
    cost_score = min(summary["selected_cost"] / max_budget, 2.0)

    return (
        float(objective.get("coverage_weight", 0.38)) * coverage_score
        + float(objective.get("rate_weight", 0.24)) * rate_score
        + float(objective.get("localization_weight", 0.18)) * loc_score
        + float(objective.get("sensing_weight", 0.12)) * sense_score
        - float(objective.get("cost_weight", 0.08)) * cost_score
    )


def _weighted_mean(values: list[float], weights: list[float]) -> float:
    if not values:
        return 0.0
    total_weight = sum(weights) or 1.0
    return sum(value * weight for value, weight in zip(values, weights, strict=False)) / total_weight


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


def _metric_cell(cell: GridCell, value: float, properties: dict[str, Any]) -> MetricCell:
    return MetricCell(
        cell_id=cell.id,
        lat=cell.lat,
        lon=cell.lon,
        value=round(float(value), 6),
        properties=dict(properties),
    )


def _layer(
    run_id: str,
    metric_name: str,
    unit: str,
    model_profile: str,
    cells: list[MetricCell],
    summary: dict[str, Any],
) -> MetricLayer:
    values = [cell.value for cell in cells]
    layer_summary = {
        **summary,
        "metric_min": round(min(values), 4) if values else 0.0,
        "metric_max": round(max(values), 4) if values else 0.0,
        "metric_mean": round(statistics.fmean(values), 4) if values else 0.0,
    }
    return MetricLayer(
        run_id=run_id,
        metric_name=metric_name,
        unit=unit,
        model_profile=model_profile,
        cells=cells,
        summary=layer_summary,
    )
