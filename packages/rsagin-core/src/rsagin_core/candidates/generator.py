from __future__ import annotations

import math
from typing import Any


DEFAULT_FAMILIES = ["ris", "mis", "ma_array", "uav_relay", "ground_station"]


def generate_candidates(
    scenario: Any,
    *,
    families: list[str] | None = None,
    limit: int = 16,
) -> dict[str, Any]:
    """Generate reproducible engineering candidate sites from geometry and demand hints."""

    scenario_data = _scenario_data(scenario)
    polygon = _polygon(scenario_data)
    if not polygon:
        return {"scenario_id": scenario_data.get("id", "scenario"), "candidates": [], "quality_flags": ["缺少区域 polygon。"]}

    families = families or DEFAULT_FAMILIES
    centroid = _centroid(polygon)
    anchors = _anchors(polygon, centroid)
    shadow_zones = _shadow_zones(scenario_data)
    demand_hotspots = _demand_hotspots(scenario_data, centroid)
    candidates: list[dict[str, Any]] = []

    for index, anchor in enumerate(anchors):
        family = families[index % len(families)]
        candidates.append(_candidate(family, anchor, "边界/立面候选点", scenario_data, len(candidates)))

    for hotspot in demand_hotspots:
        candidates.append(_candidate("uav_relay", hotspot, "需求热点上空中继", scenario_data, len(candidates), alt_m=140.0))

    for zone in shadow_zones:
        candidates.append(_candidate("ris", zone, "遮挡区反射补盲", scenario_data, len(candidates), alt_m=35.0))

    candidates.append(_candidate("mis", centroid, "中心屋面透反射增强", scenario_data, len(candidates), alt_m=42.0))
    candidates.append(_candidate("ma_array", _offset(centroid, 0.0018, -0.0012), "边缘移动阵列增强", scenario_data, len(candidates), alt_m=12.0))

    scored = sorted((_score_candidate(item, scenario_data) for item in candidates), key=lambda value: value["score"], reverse=True)
    selected = _deduplicate(scored)[: max(1, int(limit))]
    return {
        "scenario_id": scenario_data.get("id", "scenario"),
        "method": "geometry_hotspot_shadow_anchor_v1",
        "families": families,
        "candidates": selected,
        "candidate_nodes": [_node_payload(item) for item in selected],
        "quality_flags": _quality_flags(selected, polygon),
    }


def _candidate(
    family: str,
    point: tuple[float, float],
    reason: str,
    scenario_data: dict[str, Any],
    index: int,
    *,
    alt_m: float | None = None,
) -> dict[str, Any]:
    alt_by_type = {"ris": 30.0, "mis": 42.0, "ma_array": 10.0, "uav_relay": 140.0, "ground_station": 15.0}
    cost_by_type = {"ris": 7.0, "mis": 11.0, "ma_array": 9.0, "uav_relay": 15.0, "ground_station": 20.0}
    lat, lon = point
    return {
        "id": f"auto_{family}_{index + 1:02d}",
        "type": family,
        "position": {"lat": round(lat, 7), "lon": round(lon, 7), "alt_m": float(alt_m if alt_m is not None else alt_by_type.get(family, 20.0))},
        "reason": reason,
        "cost": cost_by_type.get(family, 8.0),
        "scores": {
            "coverage_gap": 0.0,
            "demand": 0.0,
            "geometry": 0.0,
            "cost_efficiency": 0.0,
        },
        "hardware_hint": _hardware_hint(family),
        "source": "auto_candidate_generation",
        "scenario_id": scenario_data.get("id", "scenario"),
    }


def _score_candidate(candidate: dict[str, Any], scenario_data: dict[str, Any]) -> dict[str, Any]:
    lat = candidate["position"]["lat"]
    lon = candidate["position"]["lon"]
    hotspots = _demand_hotspots(scenario_data, _centroid(_polygon(scenario_data)))
    shadows = _shadow_zones(scenario_data)
    demand_score = max((_gaussian(lat, lon, h_lat, h_lon, 0.006) for h_lat, h_lon in hotspots), default=0.45)
    shadow_score = max((_gaussian(lat, lon, s_lat, s_lon, 0.0055) for s_lat, s_lon in shadows), default=0.25)
    geometry_score = 0.7 if candidate["type"] in {"ris", "mis", "ma_array"} else 0.55
    if candidate["type"] == "uav_relay":
        geometry_score = 0.85
    cost_efficiency = 1.0 / max(float(candidate["cost"]), 1.0)
    score = 0.36 * demand_score + 0.28 * shadow_score + 0.24 * geometry_score + 1.2 * cost_efficiency
    candidate["scores"] = {
        "coverage_gap": round(shadow_score, 4),
        "demand": round(demand_score, 4),
        "geometry": round(geometry_score, 4),
        "cost_efficiency": round(cost_efficiency, 4),
    }
    candidate["score"] = round(score, 4)
    candidate["quality_flags"] = ["需结合建筑物/禁飞区数据复核"] if candidate["type"] == "uav_relay" else []
    return candidate


def _node_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    node_type = candidate["type"]
    radio = {"tx_power_dbm": 24, "antenna_gain_dbi": 8, "rx_gain_dbi": 0}
    reconfigurable: dict[str, Any] = {"kind": "none"}
    if node_type == "ris":
        radio = {"tx_power_dbm": 0, "antenna_gain_dbi": 0, "rx_gain_dbi": 0}
        reconfigurable = {"kind": "ris", "num_elements_x": 24, "num_elements_y": 24, "phase_bits": 2, "reflection_loss_db": 1.5}
    elif node_type == "mis":
        radio = {"tx_power_dbm": 0, "antenna_gain_dbi": 0, "rx_gain_dbi": 0}
        reconfigurable = {"kind": "mis", "num_layers": 3, "focusing_gain_db": 13.0, "transmission_loss_db": 2.0}
    elif node_type == "ma_array":
        radio = {"tx_power_dbm": 20, "antenna_gain_dbi": 9, "rx_gain_dbi": 0}
        reconfigurable = {"kind": "ma", "num_antennas": 8, "movement_region_m": 4.0, "codebook_gain_db": 5.0}
    elif node_type == "uav_relay":
        radio = {"tx_power_dbm": 30, "antenna_gain_dbi": 11, "rx_gain_dbi": 0}
    return {
        "id": candidate["id"],
        "type": node_type,
        "position": candidate["position"],
        "radio": radio,
        "reconfigurable": reconfigurable,
        "mobility": {"mode": "fixed" if node_type != "uav_relay" else "loiter"},
        "cost": candidate["cost"],
        "enabled": True,
    }


def _scenario_data(scenario: Any) -> dict[str, Any]:
    if hasattr(scenario, "model_dump"):
        return scenario.model_dump(mode="json")
    return scenario if isinstance(scenario, dict) else {}


def _polygon(scenario_data: dict[str, Any]) -> list[tuple[float, float]]:
    region = scenario_data.get("region", {})
    raw = region.get("polygon", []) if isinstance(region, dict) else []
    return [(float(item[0]), float(item[1])) for item in raw if len(item) >= 2]


def _centroid(polygon: list[tuple[float, float]]) -> tuple[float, float]:
    lat = sum(point[0] for point in polygon) / max(len(polygon), 1)
    lon = sum(point[1] for point in polygon) / max(len(polygon), 1)
    return lat, lon


def _anchors(polygon: list[tuple[float, float]], centroid: tuple[float, float]) -> list[tuple[float, float]]:
    anchors = []
    for left, right in zip(polygon, polygon[1:] + polygon[:1], strict=False):
        anchors.append(((left[0] + right[0] + centroid[0]) / 3.0, (left[1] + right[1] + centroid[1]) / 3.0))
    return anchors


def _shadow_zones(scenario_data: dict[str, Any]) -> list[tuple[float, float]]:
    grid = scenario_data.get("grid", {})
    zones = grid.get("shadow_zones", []) if isinstance(grid, dict) else []
    points: list[tuple[float, float]] = []
    for zone in zones:
        center = zone.get("center") if isinstance(zone, dict) else None
        if isinstance(center, (list, tuple)) and len(center) >= 2:
            points.append((float(center[0]), float(center[1])))
    return points


def _demand_hotspots(scenario_data: dict[str, Any], fallback: tuple[float, float]) -> list[tuple[float, float]]:
    grid = scenario_data.get("grid", {})
    hotspots = grid.get("demand_hotspots", []) if isinstance(grid, dict) else []
    points: list[tuple[float, float]] = []
    for hotspot in hotspots:
        center = hotspot.get("center") if isinstance(hotspot, dict) else None
        if isinstance(center, (list, tuple)) and len(center) >= 2:
            points.append((float(center[0]), float(center[1])))
    return points or [fallback, _offset(fallback, 0.0025, 0.0025)]


def _offset(point: tuple[float, float], d_lat: float, d_lon: float) -> tuple[float, float]:
    return point[0] + d_lat, point[1] + d_lon


def _gaussian(lat: float, lon: float, c_lat: float, c_lon: float, sigma: float) -> float:
    distance = math.hypot(lat - c_lat, lon - c_lon)
    return math.exp(-(distance * distance) / (2.0 * sigma * sigma))


def _hardware_hint(node_type: str) -> dict[str, Any]:
    return {
        "ris": {"catalog_id": "ris_2bit_facade_24x24", "er_dof": 576},
        "mis": {"catalog_id": "mis_3layer_rooftop", "er_dof": 768},
        "ma_array": {"catalog_id": "ma_8elem_mobile_array", "er_dof": 8},
        "uav_relay": {"catalog_id": "uav_relay_5g_28ghz", "endurance_min": 42},
        "ground_station": {"catalog_id": "portable_ground_station_ku", "backhaul_mbps": 500},
    }.get(node_type, {"catalog_id": "generic"})


def _quality_flags(candidates: list[dict[str, Any]], polygon: list[tuple[float, float]]) -> list[str]:
    flags: list[str] = []
    if len(candidates) < 4:
        flags.append("候选点数量偏少，建议导入道路、建筑或站址数据。")
    if len(polygon) < 4:
        flags.append("区域边界过于粗略，面积和边缘覆盖结论可信度较低。")
    if any(item["type"] == "uav_relay" for item in candidates):
        flags.append("低空平台候选点需要叠加禁飞区、航线和续航约束。")
    return flags


def _deduplicate(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, int, int]] = set()
    unique = []
    for item in candidates:
        key = (item["type"], round(item["position"]["lat"] * 10000), round(item["position"]["lon"] * 10000))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique
