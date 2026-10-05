from __future__ import annotations


def sionna_rt_adapter_descriptor() -> dict:
    return {
        "id": "sionna_rt_l2",
        "status": "adapter_ready",
        "execution": "external",
        "inputs": ["roi_scene", "building_mesh_or_osm", "carrier_frequency_hz", "material_catalog"],
        "outputs": ["path_gain", "delay_spread", "shadow_loss_delta_db", "calibrated_l1_bias"],
        "note": "This v0.5 prototype exports ROI scenes and calibration targets; it does not bundle or execute Sionna RT.",
    }
