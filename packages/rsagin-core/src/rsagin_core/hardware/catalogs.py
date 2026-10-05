from __future__ import annotations

from typing import Any

from rsagin_core.models import NodeType, Scenario

from .erdof import erdof_for_node


def hardware_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": "ris_2bit_facade_24x24",
            "type": "ris",
            "elements": 576,
            "phase_bits": 2,
            "reflection_loss_db": 3.5,
            "switching_delay_ms": 8,
            "angular_range_deg": 110,
            "planning_status": "available",
        },
        {
            "id": "ris_3bit_facade_32x32",
            "type": "ris",
            "elements": 1024,
            "phase_bits": 3,
            "reflection_loss_db": 2.8,
            "switching_delay_ms": 11,
            "angular_range_deg": 100,
            "planning_status": "available",
        },
        {
            "id": "mis_3layer_rooftop",
            "type": "mis",
            "layers": 3,
            "transmission_loss_db": 4.0,
            "focusing_gain_db": 12.0,
            "switching_delay_ms": 15,
            "planning_status": "experimental",
        },
        {
            "id": "ma_8elem_mobile_array",
            "type": "ma_array",
            "antennas": 8,
            "movement_region_m": 2.0,
            "mechanical_delay_ms": 120,
            "planning_status": "available",
        },
    ]


def hardware_catalog_summary(scenario: Scenario, selected_candidate_ids: list[str] | None = None) -> dict[str, Any]:
    selected = set(selected_candidate_ids or [])
    nodes = [node for node in scenario.candidate_nodes if not selected or node.id in selected]
    reconf_nodes = [node for node in nodes if node.type in {NodeType.RIS, NodeType.MIS, NodeType.MA_ARRAY}]
    return {
        "catalog": hardware_catalog(),
        "scenario_hardware": [
            {
                "node_id": node.id,
                "node_type": node.type.value,
                "effective_reconfigurable_dof": erdof_for_node(node),
                "switching_cost_proxy": _switching_cost_proxy(node.type),
                "hardware_note": _hardware_note(node.type),
            }
            for node in reconf_nodes
        ],
    }


def _switching_cost_proxy(node_type: NodeType) -> float:
    return {
        NodeType.RIS: 0.08,
        NodeType.MIS: 0.15,
        NodeType.MA_ARRAY: 0.32,
    }.get(node_type, 0.1)


def _hardware_note(node_type: NodeType) -> str:
    return {
        NodeType.RIS: "Passive surface with quantized phase and orientation constraints.",
        NodeType.MIS: "Metasurface stack with transmission/focusing loss and higher calibration risk.",
        NodeType.MA_ARRAY: "Movable aperture with mechanical delay and spacing constraints.",
    }.get(node_type, "Generic reconfigurable hardware.")
