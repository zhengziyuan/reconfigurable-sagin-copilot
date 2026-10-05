from __future__ import annotations

import math
from typing import Iterable

from .models import GridCell, PositionLLA, Region

EARTH_RADIUS_M = 6_371_000.0


def satellite_geometry(satellite: PositionLLA, receiver: PositionLLA) -> tuple[float, float]:
    """Spherical-Earth ECEF slant range and receiver-local elevation."""
    def ecef(position: PositionLLA) -> tuple[float, float, float]:
        lat, lon = math.radians(position.lat), math.radians(position.lon)
        radius = EARTH_RADIUS_M + position.alt_m
        return radius * math.cos(lat) * math.cos(lon), radius * math.cos(lat) * math.sin(lon), radius * math.sin(lat)
    source, target = ecef(satellite), ecef(receiver)
    delta = tuple(source[index] - target[index] for index in range(3))
    distance = math.sqrt(sum(value * value for value in delta))
    up = tuple(value / (EARTH_RADIUS_M + receiver.alt_m) for value in target)
    projection = sum(delta[index] * up[index] for index in range(3))
    elevation = math.degrees(math.asin(max(-1.0, min(1.0, projection / max(distance, 1e-9)))))
    return distance, elevation


def haversine_m(a: PositionLLA, b: PositionLLA) -> float:
    if max(a.alt_m, b.alt_m) > 20_000:
        return satellite_geometry(a, b)[0]
    lat1 = math.radians(a.lat)
    lat2 = math.radians(b.lat)
    dlat = lat2 - lat1
    dlon = math.radians(b.lon - a.lon)
    h = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    )
    ground = 2.0 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))
    return math.hypot(ground, b.alt_m - a.alt_m)


def bearing_unit_xy(src: PositionLLA, dst: PositionLLA) -> tuple[float, float]:
    mean_lat = math.radians((src.lat + dst.lat) / 2.0)
    dx = math.radians(dst.lon - src.lon) * EARTH_RADIUS_M * math.cos(mean_lat)
    dy = math.radians(dst.lat - src.lat) * EARTH_RADIUS_M
    norm = math.hypot(dx, dy)
    if norm <= 1e-9:
        return (0.0, 0.0)
    return (dx / norm, dy / norm)


def point_in_polygon(lon: float, lat: float, polygon: Iterable[tuple[float, float]]) -> bool:
    points = list(polygon)
    if len(points) < 3:
        return False

    inside = False
    j = len(points) - 1
    for i, point in enumerate(points):
        xi, yi = point
        xj, yj = points[j]
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def generate_grid(region: Region, grid_config: dict) -> list[GridCell]:
    polygon = region.polygon
    if len(polygon) < 3:
        raise ValueError("Region polygon must contain at least three points.")

    min_lon = min(point[0] for point in polygon)
    max_lon = max(point[0] for point in polygon)
    min_lat = min(point[1] for point in polygon)
    max_lat = max(point[1] for point in polygon)
    nx = int(grid_config.get("nx", 16))
    ny = int(grid_config.get("ny", 12))
    hotspot = grid_config.get("hotspot", {})

    cells: list[GridCell] = []
    for y in range(ny):
        lat = min_lat + (y + 0.5) * (max_lat - min_lat) / ny
        row_offset = 0.5 if y % 2 else 0.0
        for x in range(nx):
            lon = min_lon + (x + 0.5 + 0.18 * row_offset) * (max_lon - min_lon) / nx
            if not point_in_polygon(lon, lat, polygon):
                continue
            demand_weight = _demand_weight(lat, lon, hotspot)
            cells.append(
                GridCell(
                    id=f"cell_{len(cells):04d}",
                    lat=lat,
                    lon=lon,
                    demand_weight=demand_weight,
                    properties={"row": y, "col": x},
                )
            )
    return cells


def _demand_weight(lat: float, lon: float, hotspot: dict) -> float:
    if not hotspot:
        return 1.0
    radius_m = float(hotspot.get("radius_m", 1.0))
    boost = float(hotspot.get("weight_boost", 1.0))
    center = PositionLLA(lat=float(hotspot["lat"]), lon=float(hotspot["lon"]), alt_m=0)
    point = PositionLLA(lat=lat, lon=lon, alt_m=0)
    distance = haversine_m(center, point)
    if distance > radius_m:
        return 1.0
    return 1.0 + boost * (1.0 - distance / radius_m)
