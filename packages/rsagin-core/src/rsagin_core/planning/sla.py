from __future__ import annotations

from typing import Any


def sla_constraints_from_services(services: dict[str, Any]) -> dict[str, float]:
    return {
        "min_rate_mbps": float(services.get("communication", {}).get("min_rate_mbps", 10.0)),
        "min_coverage_percent": float(services.get("communication", {}).get("min_coverage_percent", 95.0)),
        "max_peb_m": float(services.get("localization", {}).get("max_peb_m", 5.0)),
        "min_sensing_score": float(services.get("sensing", {}).get("min_score", 0.55)),
        "max_budget": float(services.get("cost", {}).get("max_budget", 36.0)),
    }


def evaluate_sla(summary: dict[str, Any], constraints: dict[str, float]) -> dict[str, Any]:
    checks = {
        "coverage": float(summary.get("coverage_percent", 0.0)) >= constraints["min_coverage_percent"],
        "edge_rate": float(summary.get("p5_rate_mbps", 0.0)) >= constraints["min_rate_mbps"],
        "peb": float(summary.get("p95_peb_m", 999.0)) <= constraints["max_peb_m"],
        "sensing": float(summary.get("avg_sensing_score", 0.0)) >= constraints["min_sensing_score"],
        "budget": float(summary.get("selected_cost", 0.0)) <= constraints["max_budget"],
    }
    return {
        "checks": checks,
        "passed": sum(1 for value in checks.values() if value),
        "failed": sum(1 for value in checks.values() if not value),
    }
