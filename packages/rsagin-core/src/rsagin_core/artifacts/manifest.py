from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from rsagin_core.model_fidelity.profile import get_model_profile
from rsagin_core.models import Scenario, SimulationRun


def build_run_manifest(run: SimulationRun, scenario: Scenario, problem_template_id: str | None = None) -> dict[str, Any]:
    return {
        "manifest_version": "0.6",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run.run_id,
        "scenario_id": scenario.id,
        "problem_template_id": problem_template_id or scenario.optimization.get("problem_template", "robust_isac_reconfigurable_planning"),
        "model_profile": get_model_profile(run.model_profile),
        "selected_candidate_ids": run.selected_candidate_ids,
        "data_sources": {
            "scenario_config": "scenario_snapshot.json",
            "weather": "scenario.grid.weather",
            "hardware_catalog": "configs/hardware/hardware_catalog.yaml",
            "problem_templates": "configs/problem_templates",
        },
        "reproducibility": {
            "deterministic_grid": True,
            "deterministic_shadow_fading": True,
            "seed_policy": "hash-based deterministic channel terms",
        },
        "artifact_schema": artifact_schema(),
    }


def artifact_schema() -> dict[str, list[str]]:
    return {
        "root": ["manifest.json", "scenario_resolved.yaml", "model_profile_resolved.yaml", "optimization_profile_resolved.yaml"],
        "layers": ["coverage.parquet", "rate.parquet", "peb.parquet", "sensing.parquet", "sla_violation.parquet", "risk.parquet"],
        "geo": ["region.geojson", "nodes.geojson", "candidate_sites.geojson", "selected_sites.geojson", "links.geojson"],
        "figures": ["coverage_baseline.png", "coverage_optimized.png", "rate_cdf.png", "peb_cdf.png", "pareto_front.png", "sensitivity.png"],
        "tables": ["summary.csv", "selected_nodes.csv", "sla_table.csv", "cost_benefit.csv"],
        "reports": ["report_research.md", "report_enterprise.md", "report_grant.md", "report_summary.pptx"],
    }
