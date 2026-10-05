from __future__ import annotations

from typing import Any

from rsagin_core.models import NodeType, Scenario

from .profile import get_model_profile


def validate_model_profile(scenario: Scenario, model_profile: str) -> dict[str, Any]:
    profile = get_model_profile(model_profile)
    warnings: list[dict[str, str]] = []
    blockers: list[dict[str, str]] = []
    frequency_hz = float(scenario.spectrum.get("carrier_frequency_hz", 28e9))
    low, high = profile.get("valid_frequency_range_hz", [0.0, float("inf")])
    if not low <= frequency_hz <= high:
        blockers.append(
            {
                "code": "frequency_out_of_range",
                "severity": "error",
                "message": f"Carrier frequency {frequency_hz:.3g} Hz is outside {profile['id']} range.",
            }
        )

    weather = scenario.grid.get("weather", {})
    if model_profile == "standards_l1" and not weather:
        warnings.append(
            {
                "code": "missing_weather",
                "severity": "warning",
                "message": "L1 standards profile works best with temperature, pressure, humidity, and rain-rate inputs.",
            }
        )
    if scenario.grid.get("type") not in {"rectangular_hex_proxy", "hex", "rectangular"}:
        warnings.append(
            {
                "code": "grid_type_unverified",
                "severity": "warning",
                "message": "Grid type is not part of the current golden-scenario validation set.",
            }
        )

    has_ntn = any(
        node.type in {NodeType.SATELLITE_LEO, NodeType.SATELLITE_GEO, NodeType.HAPS}
        for node in [*scenario.fixed_nodes, *scenario.candidate_nodes]
    )
    if has_ntn and model_profile == "closed_form_v0":
        warnings.append(
            {
                "code": "ntn_low_fidelity",
                "severity": "warning",
                "message": "NTN assets are present; use standards_l1 before relying on Earth-space link margins.",
            }
        )

    confidence = 0.92 if model_profile == "standards_l1" else 0.68
    confidence -= 0.08 * len(warnings) + 0.18 * len(blockers)
    return {
        "profile": profile,
        "applicable": not blockers,
        "confidence_score": round(max(0.0, min(1.0, confidence)), 3),
        "warnings": warnings,
        "blockers": blockers,
    }
