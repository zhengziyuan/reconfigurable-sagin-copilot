from __future__ import annotations

import math

from rsagin_core.models import Node, NodeType


def erdof_for_node(node: Node) -> float:
    spec = node.reconfigurable
    if node.type == NodeType.RIS:
        elements = (spec.num_elements_x or 1) * (spec.num_elements_y or 1)
        phase_states = 2 ** (spec.phase_bits or 1)
        loss_factor = math.exp(-float(spec.reflection_loss_db or 3.0) / 12.0)
        return round(math.sqrt(elements) * math.log2(phase_states + 1.0) * loss_factor, 3)
    if node.type == NodeType.MIS:
        layers = spec.num_layers or 1
        loss_factor = math.exp(-float(spec.transmission_loss_db or 4.0) / 14.0)
        return round(layers * float(spec.focusing_gain_db or 8.0) * loss_factor, 3)
    if node.type == NodeType.MA_ARRAY:
        antennas = spec.num_antennas or 1
        region = max(float(spec.movement_region_m or 0.5), 0.1)
        return round(antennas * math.log1p(region) * 1.35, 3)
    return 0.0
