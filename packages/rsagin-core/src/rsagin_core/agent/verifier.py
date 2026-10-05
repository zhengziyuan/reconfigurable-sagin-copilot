from __future__ import annotations

from typing import Any

from rsagin_core.planning.sla import evaluate_sla, sla_constraints_from_services
from rsagin_core.validation.run_quality import evaluate_run_quality


def verify_plan_result(run: Any, scenario: Any) -> dict[str, Any]:
    return {
        "run_id": run.run_id,
        "quality": evaluate_run_quality(run, scenario),
        "sla": evaluate_sla(run.summary, sla_constraints_from_services(scenario.services)),
        "grounded": True,
    }
