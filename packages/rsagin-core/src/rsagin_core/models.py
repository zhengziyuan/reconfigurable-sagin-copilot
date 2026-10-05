from __future__ import annotations

from enum import Enum
from typing import Any, Literal

import math
from pydantic import BaseModel, Field, model_validator


class NodeType(str, Enum):
    SATELLITE_LEO = "satellite_leo"
    SATELLITE_GEO = "satellite_geo"
    HAPS = "haps"
    UAV_RELAY = "uav_relay"
    GROUND_BS = "ground_bs"
    GROUND_STATION = "ground_station"
    RIS = "ris"
    MIS = "mis"
    MA_ARRAY = "ma_array"
    USER = "user"
    TARGET = "target"
    SENSOR = "sensor"


class PositionLLA(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)
    alt_m: float = Field(default=0.0, ge=-500, le=50_000_000, allow_inf_nan=False)


class RadioSpec(BaseModel):
    tx_power_dbm: float = Field(default=0.0, ge=-100, le=100, allow_inf_nan=False)
    antenna_gain_dbi: float = Field(default=0.0, ge=-50, le=100, allow_inf_nan=False)
    rx_gain_dbi: float = Field(default=0.0, ge=-50, le=100, allow_inf_nan=False)
    bandwidth_hz: float | None = Field(default=None, gt=0, le=10e9, allow_inf_nan=False)
    carrier_frequency_hz: float | None = Field(default=None, gt=0, le=1e12, allow_inf_nan=False)
    noise_figure_db: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)


class ReconfigurableSpec(BaseModel):
    kind: Literal["none", "ris", "mis", "ma"] = "none"
    num_elements_x: int | None = None
    num_elements_y: int | None = None
    phase_bits: int | None = None
    reflection_loss_db: float | None = None
    transmission_loss_db: float | None = None
    focusing_gain_db: float | None = None
    num_layers: int | None = None
    num_antennas: int | None = None
    movement_region_m: float | None = None
    codebook_gain_db: float | None = None
    max_gain_db: float | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Node(BaseModel):
    id: str
    type: NodeType
    position: PositionLLA
    radio: RadioSpec = Field(default_factory=RadioSpec)
    reconfigurable: ReconfigurableSpec = Field(default_factory=ReconfigurableSpec)
    mobility: dict[str, Any] = Field(default_factory=dict)
    cost: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    enabled: bool = True


class Region(BaseModel):
    id: str
    name: str
    crs: str = "EPSG:4326"
    polygon: list[tuple[float, float]]
    terrain: str = "flat"
    area_hint_km2: float | None = None

    @model_validator(mode="after")
    def valid_polygon(self):
        if self.crs != "EPSG:4326":
            raise ValueError("Region coordinates must use EPSG:4326 (longitude, latitude).")
        if len(set(self.polygon)) < 3 or len(self.polygon) > 1000:
            raise ValueError("Region requires 3-1000 polygon vertices.")
        if any(not math.isfinite(lon) or not math.isfinite(lat) or not -180 <= lon <= 180 or not -90 <= lat <= 90 for lon, lat in self.polygon):
            raise ValueError("Region longitude/latitude is invalid.")
        points = self.polygon
        area = sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1] for i in range(len(points)))
        if abs(area) < 1e-10:
            raise ValueError("Region polygon must have non-zero area.")
        return self


class GridCell(BaseModel):
    id: str
    lat: float
    lon: float
    demand_weight: float = 1.0
    properties: dict[str, Any] = Field(default_factory=dict)


class MetricCell(BaseModel):
    cell_id: str
    lat: float
    lon: float
    value: float
    properties: dict[str, Any] = Field(default_factory=dict)


class MetricLayer(BaseModel):
    run_id: str
    metric_name: str
    unit: str
    model_profile: str
    time_slot: int = 0
    cells: list[MetricCell]
    summary: dict[str, Any]


class Scenario(BaseModel):
    id: str
    name: str
    description: str = ""
    region: Region
    fixed_nodes: list[Node]
    candidate_nodes: list[Node]
    grid: dict[str, Any] = Field(default_factory=dict)
    spectrum: dict[str, Any] = Field(default_factory=dict)
    services: dict[str, Any] = Field(default_factory=dict)
    optimization: dict[str, Any] = Field(default_factory=dict)
    deployment: dict[str, Any] = Field(default_factory=dict)
    time: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_scenario(self):
        nodes = self.fixed_nodes + self.candidate_nodes
        if len(nodes) > 100 or len({node.id for node in nodes}) != len(nodes):
            raise ValueError("Node IDs must be unique; at most 100 nodes are supported per planning scene.")
        nx, ny = int(self.grid.get("nx", 16)), int(self.grid.get("ny", 12))
        if not 1 <= nx <= 50 or not 1 <= ny <= 50:
            raise ValueError("Grid rows and columns must be between 1 and 50.")
        for key in ("carrier_frequency_hz", "bandwidth_hz"):
            value = float(self.spectrum.get(key, 28e9 if key == "carrier_frequency_hz" else 100e6))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{key} must be positive and finite.")
        for zone in self.grid.get("shadow_zones", []):
            if "lat" not in zone or "lon" not in zone:
                center = zone.get("center", [])
                if not isinstance(center, (list, tuple)) or len(center) != 2:
                    raise ValueError("Shadow zone requires lat/lon or center=[latitude, longitude].")
                zone["lat"], zone["lon"] = center
            PositionLLA(lat=zone["lat"], lon=zone["lon"])
            if not math.isfinite(float(zone.get("radius_m", 1))) or float(zone.get("radius_m", 1)) <= 0:
                raise ValueError("Shadow radius must be positive and finite.")
        return self


class SimulationRun(BaseModel):
    run_id: str
    scenario_id: str
    selected_candidate_ids: list[str]
    model_profile: str
    fidelity_level: int
    assumptions: list[str]
    grid: list[GridCell]
    layers: dict[str, MetricLayer]
    summary: dict[str, Any]


class Recommendation(BaseModel):
    node_id: str
    node_type: NodeType
    reason: str
    expected_gain: dict[str, float] = Field(default_factory=dict)


class OptimizationRun(BaseModel):
    run_id: str
    scenario_id: str
    baseline_run: SimulationRun
    optimized_run: SimulationRun
    selected_candidate_ids: list[str]
    recommendations: list[Recommendation]
    summary: dict[str, Any]


def scenario_from_config(config: dict[str, Any]) -> Scenario:
    scenario_cfg = config.get("scenario", {})
    region_cfg = config.get("region", {})
    nodes_cfg = config.get("nodes", {})

    fixed_nodes = [_node_from_config(item) for item in nodes_cfg.get("fixed", [])]
    candidate_nodes = [_node_from_config(item) for item in nodes_cfg.get("candidates", [])]

    return Scenario(
        id=scenario_cfg.get("id", "scenario"),
        name=scenario_cfg.get("name", "Scenario"),
        description=scenario_cfg.get("description", ""),
        region=Region(
            id=region_cfg.get("id", "region"),
            name=region_cfg.get("name", "Region"),
            crs=region_cfg.get("crs", "EPSG:4326"),
            polygon=[tuple(point) for point in region_cfg.get("polygon", [])],
            terrain=region_cfg.get("terrain", "flat"),
            area_hint_km2=region_cfg.get("area_hint_km2"),
        ),
        fixed_nodes=fixed_nodes,
        candidate_nodes=candidate_nodes,
        grid=config.get("grid", {}),
        spectrum=config.get("spectrum", {}),
        services=config.get("services", {}),
        optimization=config.get("optimization", {}),
        deployment=config.get("deployment", {}),
        time=config.get("time", {}),
    )


def _node_from_config(item: dict[str, Any]) -> Node:
    return Node(
        id=item["id"],
        type=NodeType(item["type"]),
        position=PositionLLA(**item.get("position", {})),
        radio=RadioSpec(**item.get("radio", {})),
        reconfigurable=ReconfigurableSpec(**item.get("reconfigurable", {})),
        mobility=item.get("mobility", {}),
        cost=float(item.get("cost", 0.0)),
        enabled=bool(item.get("enabled", True)),
    )
