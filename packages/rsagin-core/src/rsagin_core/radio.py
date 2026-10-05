from __future__ import annotations

import math

from .geo import haversine_m
from .models import Node, NodeType, PositionLLA


def dbm_to_mw(value_dbm: float) -> float:
    return 10.0 ** (value_dbm / 10.0)


def mw_to_dbm(value_mw: float) -> float:
    return 10.0 * math.log10(max(value_mw, 1e-18))


def thermal_noise_dbm(bandwidth_hz: float, noise_figure_db: float) -> float:
    return -174.0 + 10.0 * math.log10(max(bandwidth_hz, 1.0)) + noise_figure_db


def fspl_db(distance_m: float, frequency_hz: float) -> float:
    distance_km = max(distance_m / 1000.0, 1e-9)
    frequency_mhz = frequency_hz / 1e6
    return 32.45 + 20.0 * math.log10(distance_km) + 20.0 * math.log10(frequency_mhz)


def rx_power_dbm(
    tx_power_dbm: float,
    tx_gain_dbi: float,
    rx_gain_dbi: float,
    distance_m: float,
    frequency_hz: float,
    extra_loss_db: float = 0.0,
    extra_gain_db: float = 0.0,
) -> float:
    return (
        tx_power_dbm
        + tx_gain_dbi
        + rx_gain_dbi
        + extra_gain_db
        - fspl_db(distance_m, frequency_hz)
        - extra_loss_db
    )


def node_extra_loss_db(node: Node, distance_m: float) -> float:
    if node.type in {NodeType.SATELLITE_LEO, NodeType.SATELLITE_GEO}:
        return 8.0
    if node.type in {NodeType.GROUND_BS, NodeType.GROUND_STATION} and distance_m > 1200:
        return 8.0
    return 0.0


def reconfigurable_gain_db(node: Node) -> float:
    spec = node.reconfigurable
    max_gain = spec.max_gain_db if spec.max_gain_db is not None else 18.0
    if spec.kind == "ris":
        nx = spec.num_elements_x or 16
        ny = spec.num_elements_y or 16
        raw_gain = 20.0 * math.log10(max(nx * ny, 1))
        loss = (spec.reflection_loss_db or 3.0) + _phase_quant_loss(spec.phase_bits)
        return min(max_gain, max(0.0, raw_gain - loss - 30.0))
    if spec.kind == "mis":
        gain = (spec.focusing_gain_db or 10.0) + 2.0 * max((spec.num_layers or 1) - 1, 0)
        return min(max_gain, max(0.0, gain - (spec.transmission_loss_db or 4.0)))
    if spec.kind == "ma":
        gain = (spec.codebook_gain_db or 6.0) + 10.0 * math.log10(max(spec.num_antennas or 4, 1))
        return min(max_gain, max(0.0, gain - 4.0))
    return 0.0


def assisted_gain_to_cell_db(
    candidate: Node,
    cell_position: PositionLLA,
    serving_nodes: list[Node],
    frequency_hz: float,
) -> float:
    if candidate.type in {NodeType.UAV_RELAY, NodeType.HAPS}:
        distance = haversine_m(candidate.position, cell_position)
        if distance > 1600:
            return 0.0
        return max(0.0, 12.0 - 0.005 * distance)

    if candidate.reconfigurable.kind == "none":
        return 0.0

    candidate_to_cell = haversine_m(candidate.position, cell_position)
    if candidate_to_cell > 1400:
        return 0.0
    if not serving_nodes:
        return 0.0

    best_feed_dbm = -300.0
    for serving_node in serving_nodes:
        feed_distance = haversine_m(serving_node.position, candidate.position)
        feed_dbm = rx_power_dbm(
            serving_node.radio.tx_power_dbm,
            serving_node.radio.antenna_gain_dbi,
            0.0,
            feed_distance,
            frequency_hz,
            extra_loss_db=node_extra_loss_db(serving_node, feed_distance),
        )
        best_feed_dbm = max(best_feed_dbm, feed_dbm)

    if best_feed_dbm < -110.0:
        return 0.0

    geometry_penalty = min(10.0, candidate_to_cell / 180.0)
    return max(0.0, reconfigurable_gain_db(candidate) - geometry_penalty)


def _phase_quant_loss(bits: int | None) -> float:
    if bits is None or bits >= 3:
        return 0.8
    if bits == 2:
        return 1.5
    if bits == 1:
        return 3.0
    return 5.0

