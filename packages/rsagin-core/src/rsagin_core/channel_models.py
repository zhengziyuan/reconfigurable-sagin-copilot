from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any

from .geo import haversine_m, satellite_geometry
from .models import Node, NodeType, PositionLLA, Scenario
from .radio import fspl_db
from .standards.rain_p838 import rain_coefficients


@dataclass(frozen=True)
class ChannelResult:
    model: str
    path_loss_db: float
    extra_loss_db: float
    los_probability: float
    components: dict[str, float] = field(default_factory=dict)


STANDARD_ASSUMPTIONS = [
    "Level-1 standards-inspired channel model.",
    "Terrestrial links use a deterministic 3GPP TR 38.901 UMa/RMa path-loss subset with LOS probability and shadow fading proxies.",
    "Satellite/NTN links use a 3GPP TR 38.811-style FSPL plus atmospheric, clutter, rain, cloud, and scintillation loss decomposition.",
    "Rain specific attenuation implements ITU-R P.838-3 equations (1)-(5); slant-path length is a planning approximation, not a full P.618 availability model.",
    "Gaseous attenuation uses a lightweight ITU-R P.676-inspired approximation; satellite geometry uses spherical-Earth ECEF with an elevation mask.",
    "This L1 model exposes physical loss terms for planning and comparison, but is not a full stochastic clustered channel simulator.",
]


def channel_loss(
    scenario: Scenario,
    node: Node,
    point: PositionLLA,
    frequency_hz: float,
    model_profile: str,
    grid_config: dict[str, Any],
) -> ChannelResult:
    if not is_standards_profile(model_profile):
        distance = max(haversine_m(node.position, point), 1.0)
        return ChannelResult(
            model="fspl_l0",
            path_loss_db=fspl_db(distance, frequency_hz),
            extra_loss_db=0.0,
            los_probability=1.0,
            components={"fspl_db": round(fspl_db(distance, frequency_hz), 3)},
        )
    if node.type in {NodeType.SATELLITE_LEO, NodeType.SATELLITE_GEO} or node.position.alt_m > 20000:
        return _ntn_loss(scenario, node, point, frequency_hz, grid_config)
    return _terrestrial_loss(scenario, node, point, frequency_hz, grid_config)


def is_standards_profile(model_profile: str) -> bool:
    return model_profile in {"standards_l1", "3gpp_itu_l1", "l1_standard", "multi_fidelity_l2_adapter"}


def fidelity_level(model_profile: str) -> int:
    if model_profile == "multi_fidelity_l2_adapter":
        return 1
    return 1 if is_standards_profile(model_profile) else 0


def assumptions_for(model_profile: str, default: list[str]) -> list[str]:
    if model_profile == "multi_fidelity_l2_adapter":
        return [
            *STANDARD_ASSUMPTIONS,
            "Level-2 adapter mode uses L1 for global planning and exports weak ROI cells for future high-fidelity ray-tracing or measurement calibration.",
        ]
    return STANDARD_ASSUMPTIONS if is_standards_profile(model_profile) else default


def _terrestrial_loss(
    scenario: Scenario,
    node: Node,
    point: PositionLLA,
    frequency_hz: float,
    grid_config: dict[str, Any],
) -> ChannelResult:
    distance_2d_m = max(haversine_m(PositionLLA(lat=node.position.lat, lon=node.position.lon, alt_m=0), PositionLLA(lat=point.lat, lon=point.lon, alt_m=0)), 10.0)
    distance_3d_m = math.sqrt(distance_2d_m**2 + max(node.position.alt_m - point.alt_m, 0.0) ** 2)
    fc_ghz = frequency_hz / 1e9
    scenario_hint = str(scenario.grid.get("channel_scenario", "uma")).lower()
    los_probability = _los_probability_3gpp(distance_2d_m, scenario_hint)
    los = _deterministic_unit(node.id, point, "los") <= los_probability
    if scenario_hint == "rma":
        los_loss = 20.0 * math.log10(40.0 * math.pi * distance_3d_m * fc_ghz / 3.0)
        nlos_loss = 35.3 * math.log10(distance_3d_m) + 22.4 + 21.3 * math.log10(fc_ghz) - 0.3 * (node.position.alt_m - 35.0)
        model = "3gpp_tr38901_rma"
    elif node.type in {NodeType.UAV_RELAY, NodeType.HAPS} or node.position.alt_m > 80:
        los_loss = 28.0 + 22.0 * math.log10(distance_3d_m) + 20.0 * math.log10(fc_ghz)
        nlos_loss = max(los_loss, 13.54 + 39.08 * math.log10(distance_3d_m) + 20.0 * math.log10(fc_ghz) - 0.6 * (point.alt_m - 1.5))
        model = "3gpp_tr38901_uma_airground"
    else:
        los_loss = 28.0 + 22.0 * math.log10(distance_3d_m) + 20.0 * math.log10(fc_ghz)
        nlos_loss = max(los_loss, 13.54 + 39.08 * math.log10(distance_3d_m) + 20.0 * math.log10(fc_ghz) - 0.6 * (point.alt_m - 1.5))
        model = "3gpp_tr38901_uma"
    shadow_sigma = 4.0 if los else 7.8
    shadow_db = _shadow_fading_db(node.id, point, shadow_sigma)
    clutter_db = _urban_clutter_loss(distance_2d_m, grid_config)
    path_loss = (los_loss if los else nlos_loss) + shadow_db + clutter_db
    return ChannelResult(
        model=model,
        path_loss_db=path_loss,
        extra_loss_db=shadow_db + clutter_db,
        los_probability=los_probability,
        components={
            "distance_2d_m": round(distance_2d_m, 3),
            "distance_3d_m": round(distance_3d_m, 3),
            "los_probability": round(los_probability, 4),
            "los_state": 1.0 if los else 0.0,
            "path_loss_los_db": round(los_loss, 3),
            "path_loss_nlos_db": round(nlos_loss, 3),
            "shadow_fading_db": round(shadow_db, 3),
            "clutter_loss_db": round(clutter_db, 3),
        },
    )


def _ntn_loss(
    scenario: Scenario,
    node: Node,
    point: PositionLLA,
    frequency_hz: float,
    grid_config: dict[str, Any],
) -> ChannelResult:
    distance_m, elevation_deg = satellite_geometry(node.position, point)
    distance_m = max(distance_m, 1.0)
    minimum_elevation = float(scenario.grid.get("minimum_elevation_deg", 10.0))
    if elevation_deg < minimum_elevation:
        return ChannelResult(model="ntn_below_elevation_mask", path_loss_db=300.0, extra_loss_db=300.0, los_probability=0.0,
            components={"distance_3d_m": round(distance_m, 3), "elevation_deg": round(elevation_deg, 3), "visible": 0.0, "minimum_elevation_deg": minimum_elevation})
    fspl = fspl_db(distance_m, frequency_hz)
    atmosphere = _gaseous_loss_itu_p676(frequency_hz, elevation_deg, scenario)
    rain = _rain_loss_itu_p838(frequency_hz, elevation_deg, scenario)
    cloud = _cloud_fog_loss(elevation_deg, scenario)
    scintillation = _scintillation_loss(frequency_hz, elevation_deg, scenario)
    clutter = _ntn_clutter_loss(elevation_deg, grid_config)
    shadow = _shadow_fading_db(node.id, point, 2.2 if elevation_deg > 30 else 4.0)
    total = fspl + atmosphere + rain + cloud + scintillation + clutter + shadow
    return ChannelResult(
        model="3gpp_tr38811_ntn_itu",
        path_loss_db=total,
        extra_loss_db=atmosphere + rain + cloud + scintillation + clutter + shadow,
        los_probability=max(0.35, min(0.99, elevation_deg / 70.0)),
        components={
            "distance_3d_m": round(distance_m, 3),
            "elevation_deg": round(elevation_deg, 3),
            "visible": 1.0,
            "fspl_db": round(fspl, 3),
            "gaseous_loss_db": round(atmosphere, 3),
            "rain_loss_db": round(rain, 3),
            "cloud_loss_db": round(cloud, 3),
            "scintillation_loss_db": round(scintillation, 3),
            "clutter_loss_db": round(clutter, 3),
            "shadow_fading_db": round(shadow, 3),
        },
    )


def _los_probability_3gpp(distance_2d_m: float, scenario_hint: str) -> float:
    if scenario_hint == "rma":
        return 1.0 if distance_2d_m <= 10 else math.exp(-(distance_2d_m - 10.0) / 1000.0)
    return min(18.0 / distance_2d_m, 1.0) * (1.0 - math.exp(-distance_2d_m / 63.0)) + math.exp(-distance_2d_m / 63.0)


def _urban_clutter_loss(distance_2d_m: float, grid_config: dict[str, Any]) -> float:
    density = float(grid_config.get("urban_clutter_density", 0.45))
    return min(12.0, density * 4.0 * math.log10(max(distance_2d_m, 10.0) / 10.0))


def _ntn_clutter_loss(elevation_deg: float, grid_config: dict[str, Any]) -> float:
    density = float(grid_config.get("urban_clutter_density", 0.45))
    return max(0.0, density * (7.5 - 0.11 * elevation_deg))


def _gaseous_loss_itu_p676(frequency_hz: float, elevation_deg: float, scenario: Scenario) -> float:
    fc_ghz = frequency_hz / 1e9
    weather = _weather(scenario)
    humidity = float(weather.get("water_vapor_density_g_m3", 7.5))
    pressure = float(weather.get("pressure_hpa", 1013.25))
    temperature = float(weather.get("temperature_c", 20.0)) + 273.15
    dry_scale = pressure / 1013.25 * 293.15 / temperature
    wet_scale = humidity / 7.5
    oxygen = 0.004 * fc_ghz + 0.18 * math.exp(-((fc_ghz - 60.0) / 12.0) ** 2)
    water = 0.0022 * fc_ghz * wet_scale + 0.035 * wet_scale * math.exp(-((fc_ghz - 22.235) / 5.0) ** 2)
    slant_km = min(12.0 / max(math.sin(math.radians(elevation_deg)), 0.08), 120.0)
    return (oxygen * dry_scale + water) * slant_km


def _rain_loss_itu_p838(frequency_hz: float, elevation_deg: float, scenario: Scenario) -> float:
    weather = _weather(scenario)
    rain_rate = float(weather.get("rain_rate_mm_h", 12.0))
    if rain_rate <= 0:
        return 0.0
    fc_ghz = frequency_hz / 1e9
    k, alpha = rain_coefficients(fc_ghz, elevation_deg, float(weather.get("polarization_tilt_deg", 45.0)))
    gamma_db_km = k * (rain_rate ** alpha)
    effective_rain_height_km = float(weather.get("rain_height_km", 4.5))
    path_km = min(effective_rain_height_km / max(math.sin(math.radians(elevation_deg)), 0.08), 35.0)
    return gamma_db_km * path_km


def _rain_coefficients(fc_ghz: float) -> tuple[float, float]:
    return rain_coefficients(fc_ghz)


def _cloud_fog_loss(elevation_deg: float, scenario: Scenario) -> float:
    weather = _weather(scenario)
    liquid_water_kg_m2 = float(weather.get("cloud_liquid_water_kg_m2", 0.15))
    return liquid_water_kg_m2 * 1.2 / max(math.sin(math.radians(elevation_deg)), 0.12)


def _scintillation_loss(frequency_hz: float, elevation_deg: float, scenario: Scenario) -> float:
    weather = _weather(scenario)
    wet_term = float(weather.get("water_vapor_density_g_m3", 7.5)) / 7.5
    fc_ghz = frequency_hz / 1e9
    return min(3.0, 0.18 * wet_term * (fc_ghz / 20.0) ** 0.55 / max(math.sin(math.radians(elevation_deg)), 0.15) ** 0.45)


def _weather(scenario: Scenario) -> dict[str, Any]:
    return dict(scenario.grid.get("weather", scenario.spectrum.get("weather", {})))


def _shadow_fading_db(node_id: str, point: PositionLLA, sigma_db: float) -> float:
    unit_a = _deterministic_unit(node_id, point, "shadow_a")
    unit_b = _deterministic_unit(node_id, point, "shadow_b")
    gaussian = math.sqrt(-2.0 * math.log(max(unit_a, 1e-9))) * math.cos(2.0 * math.pi * unit_b)
    return max(-2.2 * sigma_db, min(2.2 * sigma_db, gaussian * sigma_db))


def _deterministic_unit(node_id: str, point: PositionLLA, salt: str) -> float:
    key = f"{node_id}:{point.lat:.5f}:{point.lon:.5f}:{salt}".encode("utf-8")
    digest = hashlib.sha256(key).hexdigest()
    return int(digest[:12], 16) / float(0xFFFFFFFFFFFF)
