from __future__ import annotations

import math
from typing import Any

from rsagin_core.model_fidelity.validity import validate_model_profile
from rsagin_core.models import Scenario, SimulationRun


def evaluate_run_quality(run: SimulationRun, scenario: Scenario) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.extend(_metric_checks(run))
    validity = validate_model_profile(scenario, run.model_profile)
    if validity["applicable"]:
        checks.append({"id": "model_validity", "status": "passed", "message": "Model profile is applicable to this scenario."})
    else:
        checks.append({"id": "model_validity", "status": "failed", "message": "Model profile has blocking validity errors."})
    for warning in validity["warnings"]:
        checks.append({"id": warning["code"], "status": "warning", "message": warning["message"]})
    for blocker in validity["blockers"]:
        checks.append({"id": blocker["code"], "status": "failed", "message": blocker["message"]})

    passed = sum(1 for item in checks if item["status"] == "passed")
    warning = sum(1 for item in checks if item["status"] == "warning")
    failed = sum(1 for item in checks if item["status"] == "failed")
    score = max(0.0, min(1.0, 1.0 - 0.08 * warning - 0.22 * failed))
    return {
        "passed": passed,
        "warning": warning,
        "failed": failed,
        "score": round(score, 3),
        "checks": checks,
        "model_validity": validity,
    }


def _metric_checks(run: SimulationRun) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    summary = run.summary
    checks.append(_range_check("coverage_range", summary.get("coverage_percent"), 0.0, 100.0))
    checks.append(_range_check("objective_range", summary.get("objective_score"), -2.0, 3.0))
    checks.append(_positive_check("avg_rate_nonnegative", summary.get("avg_rate_mbps")))
    checks.append(_positive_check("p5_rate_nonnegative", summary.get("p5_rate_mbps")))
    checks.append(_positive_check("peb_finite", summary.get("avg_peb_m")))
    checks.append(_positive_check("selected_cost_nonnegative", summary.get("selected_cost")))
    for name, layer in run.layers.items():
        values = [cell.value for cell in layer.cells]
        if values and all(math.isfinite(float(value)) for value in values):
            checks.append({"id": f"{name}_finite", "status": "passed", "message": f"{name} layer has finite values."})
        else:
            checks.append({"id": f"{name}_finite", "status": "failed", "message": f"{name} layer contains non-finite values."})
    return checks


def _range_check(check_id: str, value: Any, low: float, high: float) -> dict[str, str]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return {"id": check_id, "status": "failed", "message": f"{check_id} is not numeric."}
    if low <= numeric <= high:
        return {"id": check_id, "status": "passed", "message": f"{check_id} is within [{low}, {high}]."}
    return {"id": check_id, "status": "failed", "message": f"{check_id}={numeric} is outside [{low}, {high}]."}


def _positive_check(check_id: str, value: Any) -> dict[str, str]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return {"id": check_id, "status": "failed", "message": f"{check_id} is not numeric."}
    if math.isfinite(numeric) and numeric >= 0:
        return {"id": check_id, "status": "passed", "message": f"{check_id} is finite and non-negative."}
    return {"id": check_id, "status": "failed", "message": f"{check_id}={numeric} is invalid."}
