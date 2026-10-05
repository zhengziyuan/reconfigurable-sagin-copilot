from __future__ import annotations

from typing import Any

from rsagin_core.models import Scenario


def export_roi_scene(scenario: Scenario, rois: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "format": "rsagin_l2_scene_v0",
        "scenario_id": scenario.id,
        "region": scenario.region.model_dump(mode="json"),
        "nodes": [node.model_dump(mode="json") for node in [*scenario.fixed_nodes, *scenario.candidate_nodes]],
        "rois": rois,
        "targets": {
            "ray_tracing": ["path_gain", "delay_spread", "angular_spread", "blockage_state"],
            "calibration": ["shadow_loss_delta_db", "ris_angular_loss_db", "l1_bias_db"],
        },
    }
