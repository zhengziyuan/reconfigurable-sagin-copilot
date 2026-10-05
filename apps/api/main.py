from __future__ import annotations

import sys
import os
import json
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = ROOT / "packages" / "rsagin-core" / "src"
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from starlette.middleware.gzip import GZipMiddleware
except ModuleNotFoundError as exc:  # pragma: no cover - setup guard
    raise RuntimeError("FastAPI is not installed. Run scripts/setup.ps1 first.") from exc

from rsagin_core.agent.planner import build_tool_plan
from rsagin_core.agent.report_writer import run_grounded_report
from rsagin_core.algorithm_catalog import algorithm_catalog
from rsagin_core.benchmarks import benchmark_suite
from rsagin_core.candidates import generate_candidates
from rsagin_core.config import load_config
from rsagin_core.copilot import run_bound_answer
from rsagin_core.data_ingestion import preview_import, summarize_quality
from rsagin_core.high_fidelity import export_roi_scene, select_high_fidelity_rois, sionna_rt_adapter_descriptor
from rsagin_core.model_fidelity.profile import get_model_profile, list_model_profiles
from rsagin_core.model_fidelity.validity import validate_model_profile
from rsagin_core.models import Scenario, SimulationRun, OptimizationRun, scenario_from_config
from rsagin_core.geo import generate_grid
from pydantic import ValidationError
from fastapi.responses import JSONResponse, Response
from rsagin_core.optimization import optimize_deployment
from rsagin_core.performance_field import diff_layers, normalize_run_layers, run_diagnosis
from rsagin_core.persistence import (
    create_job,
    create_project,
    create_scenario,
    create_scenario_version,
    get_job,
    get_job_log,
    get_report,
    get_report_evidence,
    get_run,
    get_scenario,
    initialize_store,
    list_jobs,
    list_project_scenarios,
    list_projects,
    list_reports,
    list_runs,
    list_scenario_versions,
    resolve_workspace_context,
    save_report,
    save_run,
    seed_demo_workspace,
    update_job,
)
from rsagin_core.platform_catalog import platform_catalog
from rsagin_core.resource_management import plan_resources
from rsagin_core.sensitivity import one_factor_sensitivity
from rsagin_core.simulation import simulate_scenario
from rsagin_core.uncertainty import robust_evaluate

CONFIG_PATH = ROOT / "configs" / "scenarios" / "demo_low_altitude_emergency.yaml"
ARTIFACT_ROOT = Path(os.environ.get("RSAGIN_DATA_DIR", str(ROOT / "runs"))).resolve()
DB_PATH = ARTIFACT_ROOT / "rsagin_local.db"

app = FastAPI(title="Reconfigurable SAGIN Copilot API", version="0.8.0")
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("RSAGIN_CORS_ORIGINS", "").split(",") if os.environ.get("RSAGIN_CORS_ORIGINS") else [
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

initialize_store(DB_PATH)
_default_scenario = scenario_from_config(load_config(CONFIG_PATH))
seed_demo_workspace(DB_PATH, _default_scenario.model_dump(mode="json"))


@app.exception_handler(ValueError)
async def invalid_input(_request, exc: ValueError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
async def invalid_scenario(_request, exc: ValidationError):
    return JSONResponse(status_code=422, content={"detail": [{"loc": list(error["loc"]), "msg": error["msg"]} for error in exc.errors()]})


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "rsagin-api",
        "version": app.version,
        "store": str(DB_PATH),
        "artifact_root": str(ARTIFACT_ROOT),
    }


@app.get("/api/health/db")
def db_health() -> dict[str, Any]:
    return {"status": "ok", "backend": "sqlite", "path": str(DB_PATH), "projects": len(list_projects(DB_PATH))}


@app.get("/api/health/artifacts")
def artifact_health() -> dict[str, Any]:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    return {"status": "ok", "backend": "local-files", "path": str(ARTIFACT_ROOT), "exists": ARTIFACT_ROOT.exists()}


@app.get("/api/health/models")
def model_health() -> dict[str, Any]:
    scenario = scenario_from_config(load_config(CONFIG_PATH))
    return {
        "status": "ok",
        "profiles": [profile["id"] for profile in list_model_profiles()],
        "default_validation": validate_model_profile(scenario, "standards_l1"),
    }


@app.get("/api/workspace")
def workspace(project_id: str | None = None, scenario_id: str | None = None) -> dict[str, Any]:
    if scenario_id and not project_id:
        project_id = (get_scenario(DB_PATH, scenario_id) or {}).get("project_id")
    context = resolve_workspace_context(DB_PATH, project_id=project_id, scenario_id=scenario_id)
    project_id = (context.get("project") or {}).get("id")
    scenario_id = (context.get("scenario") or {}).get("id")
    return {
        "active_project": context.get("project"),
        "active_scenario": context.get("scenario"),
        "active_scenario_version": context.get("scenario_version"),
        "projects": context.get("projects", []),
        "scenarios": context.get("scenarios", []),
        "runs": list_runs(DB_PATH, limit=16, project_id=project_id, scenario_id=scenario_id),
        "jobs": [job for job in list_jobs(DB_PATH, limit=24, project_id=project_id, include_details=False) if job["scenario_id"] == scenario_id],
        "reports": [report for report in list_reports(DB_PATH, limit=12, project_id=project_id) if report["scenario_id"] == scenario_id],
        "model_profiles": list_model_profiles(),
        "health": {"db": "ok", "artifacts": "ok", "scenario_id": scenario_id},
    }


@app.get("/api/demo")
def demo(scenario_id: str | None = None) -> dict[str, Any]:
    record = get_scenario(DB_PATH, scenario_id or _default_scenario.id)
    if scenario_id and not record:
        raise HTTPException(status_code=404, detail="场景不存在")
    scenario = _scenario_from_payload({"scenario": record["payload"]}) if record else _default_scenario
    baseline = simulate_scenario(
        scenario,
        selected_candidate_ids=[],
        model_profile="closed_form_v0",
        run_id="api_baseline",
    )
    selected = [node_id for node_id in scenario.deployment.get("selected_candidate_ids", []) if node_id in {node.id for node in scenario.candidate_nodes}]
    current = simulate_scenario(scenario, selected_candidate_ids=selected, model_profile="closed_form_v0", run_id="scene_preview") if selected else baseline
    optimized = OptimizationRun(run_id="scene_preview", scenario_id=scenario.id, baseline_run=baseline, optimized_run=current,
        selected_candidate_ids=selected, recommendations=[], summary={"baseline": baseline.summary, "optimized": current.summary,
        "delta": {key: round(float(current.summary.get(key, 0)) - float(value), 3) for key, value in baseline.summary.items() if isinstance(value, (int, float))},
        "solver": "saved_deployment", "optimization_status": "preview"})
    return {
        "scenario": scenario.model_dump(mode="json"),
        "baseline": baseline.model_dump(mode="json"),
        "optimization": optimized.model_dump(mode="json"),
        "platform": platform_catalog(),
        "workspace": workspace(scenario_id=scenario.id),
    }


@app.get("/api/platform")
def platform() -> dict[str, Any]:
    return platform_catalog()


@app.get("/api/algorithms")
def algorithms() -> dict[str, Any]:
    return algorithm_catalog()


@app.get("/api/projects")
def projects() -> dict[str, Any]:
    return {"projects": list_projects(DB_PATH)}


@app.post("/api/projects")
def project_create(payload: dict) -> dict[str, Any]:
    return {"project": create_project(DB_PATH, name=str(payload.get("name", "新项目")), description=str(payload.get("description", "")))}


@app.get("/api/projects/{project_id}/scenarios")
def project_scenarios(project_id: str) -> dict[str, Any]:
    return {"scenarios": list_project_scenarios(DB_PATH, project_id)}


@app.post("/api/projects/{project_id}/scenarios")
def scenario_create(project_id: str, payload: dict) -> dict[str, Any]:
    scenario_payload = payload.get("scenario") if isinstance(payload.get("scenario"), dict) else payload
    if not any(project["id"] == project_id for project in list_projects(DB_PATH)):
        raise HTTPException(status_code=404, detail="项目不存在")
    scene = _scenario_from_payload({"scenario": scenario_payload}).model_dump(mode="json")
    if get_scenario(DB_PATH, scene["id"]):
        raise HTTPException(status_code=409, detail="场景 ID 已存在，请保存为新版本或修改 ID")
    return {"scenario": create_scenario(DB_PATH, project_id=project_id, scenario_payload=scene)}


@app.post("/api/scenarios/validate")
def scenario_validate(payload: dict) -> dict[str, Any]:
    scene_payload = payload.get("scenario")
    if not isinstance(scene_payload, dict) or not all(key in scene_payload for key in ("id", "name", "region", "fixed_nodes", "candidate_nodes")):
        raise HTTPException(status_code=422, detail="场景需要 id、name、region、fixed_nodes 和 candidate_nodes 字段")
    scene = _scenario_from_payload(payload)
    cells = generate_grid(scene.region, scene.grid)
    if not cells:
        raise HTTPException(status_code=422, detail="区域内没有有效网格，请检查边界与网格分辨率")
    return {"scenario": scene.model_dump(mode="json"), "grid_cells": len(cells), "valid": True}


@app.get("/api/scenarios/{scenario_id}")
def scenario_get(scenario_id: str) -> dict[str, Any]:
    scenario = get_scenario(DB_PATH, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="scenario not found")
    return {"scenario": scenario}


@app.get("/api/scenarios/{scenario_id}/versions")
def scenario_versions(scenario_id: str) -> dict[str, Any]:
    return {"versions": list_scenario_versions(DB_PATH, scenario_id)}


@app.post("/api/scenarios/{scenario_id}/versions")
def scenario_version_create(scenario_id: str, payload: dict) -> dict[str, Any]:
    if not get_scenario(DB_PATH, scenario_id):
        raise HTTPException(status_code=404, detail="场景不存在")
    scenario_payload = payload.get("scenario") if isinstance(payload.get("scenario"), dict) else payload
    scene = _scenario_from_payload({"scenario": scenario_payload}).model_dump(mode="json")
    if scene["id"] != scenario_id:
        raise HTTPException(status_code=422, detail="版本的场景 ID 必须与目标场景一致")
    return {"version": create_scenario_version(DB_PATH, scenario_id=scenario_id, scenario_payload=scene, notes=str(payload.get("notes", "场景更新")))}


@app.get("/api/runs")
def runs(limit: int = 20, project_id: str | None = None, scenario_id: str | None = None) -> dict[str, Any]:
    return {"runs": list_runs(DB_PATH, limit=limit, project_id=project_id, scenario_id=scenario_id)}


@app.get("/api/runs/{run_id}")
def run_get(run_id: str) -> dict[str, Any]:
    run = get_run(DB_PATH, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return {"run": run, "field": normalize_run_layers(run.get("payload", run)), "diagnosis": run_diagnosis(run.get("payload", run))}


@app.post("/api/simulate")
def simulate(payload: dict) -> dict[str, Any]:
    return _simulate_result(payload or {})


@app.post("/api/optimize")
def optimize(payload: dict | None = None) -> dict[str, Any]:
    return _optimize_result(payload or {})


@app.post("/api/resource-plan")
def resource_plan(payload: dict | None = None) -> dict[str, Any]:
    payload = payload or {}
    scenario = _scenario_from_payload(payload)
    result = plan_resources(
        scenario,
        selected_candidate_ids=payload.get("selected_candidate_ids", []),
        method=payload.get("method", "wmmse"),
        max_flows=int(payload.get("max_flows", 24)),
        iterations=int(payload.get("iterations", 24)),
        model_profile=payload.get("model_profile", "closed_form_v0"),
    )
    context = _snapshot_context(scenario, payload)
    result["storage"] = save_run(DB_PATH, {**result, "scenario": scenario.model_dump(mode="json")}, run_type="resource", artifact_root=ARTIFACT_ROOT, **context)
    return result


@app.post("/api/robust-evaluate")
def robust(payload: dict | None = None) -> dict[str, Any]:
    payload = payload or {}
    scenario = _scenario_from_payload(payload)
    return robust_evaluate(
        scenario,
        selected_candidate_ids=payload.get("selected_candidate_ids", []),
        model_profile=payload.get("model_profile", "standards_l1"),
        samples=int(payload.get("samples", 12)),
        seed=int(payload.get("seed", 20260707)),
    )


@app.post("/api/sensitivity")
def sensitivity(payload: dict | None = None) -> dict[str, Any]:
    payload = payload or {}
    scenario = _scenario_from_payload(payload)
    return one_factor_sensitivity(
        scenario,
        selected_candidate_ids=payload.get("selected_candidate_ids", []),
        model_profile=payload.get("model_profile", "standards_l1"),
    )


@app.post("/api/benchmark")
def benchmark(payload: dict | None = None) -> dict[str, Any]:
    payload = payload or {}
    scenario = _scenario_from_payload(payload)
    return benchmark_suite(
        scenario,
        model_profile=payload.get("model_profile", "closed_form_v0"),
    )


@app.post("/api/intent-plan")
def intent_plan(payload: dict | None = None) -> dict[str, Any]:
    payload = payload or {}
    text = str(payload.get("intent", "低空园区需要 95% 覆盖、10 Mbps 边缘速率、PEB 低于 5 m，并生成科研和企业报告。"))
    return build_tool_plan(text)


@app.post("/api/report")
def report(payload: dict | None = None) -> dict[str, Any]:
    return _report_result(payload or {})


@app.get("/api/reports")
def reports(limit: int = 20, project_id: str | None = None) -> dict[str, Any]:
    return {"reports": list_reports(DB_PATH, limit=limit, project_id=project_id)}


@app.get("/api/reports/{report_id}")
def report_get(report_id: str) -> dict[str, Any]:
    report_payload = get_report(DB_PATH, report_id)
    if not report_payload:
        raise HTTPException(status_code=404, detail="report not found")
    return {"report": report_payload}


@app.get("/api/reports/{report_id}/download")
def report_download(report_id: str):
    record = get_report(DB_PATH, report_id)
    if not record:
        raise HTTPException(status_code=404, detail="报告不存在")
    return Response(content=record["markdown"], media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{report_id}.md"'})


@app.get("/api/reports/{report_id}/evidence")
def report_evidence(report_id: str) -> dict[str, Any]:
    evidence = get_report_evidence(DB_PATH, report_id)
    if evidence is None:
        raise HTTPException(status_code=404, detail="report not found")
    return {"evidence": evidence}


@app.post("/api/high-fidelity/roi")
def high_fidelity_roi(payload: dict | None = None) -> dict[str, Any]:
    payload = payload or {}
    scenario = _scenario_from_payload(payload)
    run = simulate_scenario(
        scenario,
        selected_candidate_ids=payload.get("selected_candidate_ids", []),
        model_profile=payload.get("model_profile", "standards_l1"),
    )
    rois = select_high_fidelity_rois(run)
    return {
        "adapter": sionna_rt_adapter_descriptor(),
        "rois": rois,
        "scene": export_roi_scene(scenario, rois),
    }


@app.get("/api/jobs")
def jobs(limit: int = 50, project_id: str | None = None, status: str | None = None) -> dict[str, Any]:
    return {"jobs": list_jobs(DB_PATH, limit=limit, project_id=project_id, status=status, include_details=False)}


@app.get("/api/jobs/{job_id}")
def job_get(job_id: str) -> dict[str, Any]:
    job = get_job(DB_PATH, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return {"job": job}


@app.get("/api/jobs/{job_id}/logs")
def job_logs(job_id: str) -> dict[str, Any]:
    return {"logs": get_job_log(DB_PATH, job_id)}


@app.post("/api/jobs/{job_id}/cancel")
def job_cancel(job_id: str) -> dict[str, Any]:
    job = get_job(DB_PATH, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    if job["status"] in {"succeeded", "failed", "canceled"}:
        return {"job": job, "message": "任务已结束，无法取消。"}
    return {"job": update_job(DB_PATH, job_id, status="canceled", progress=100, message="任务已取消")}


@app.post("/api/jobs/simulate")
def job_simulate(payload: dict | None = None) -> dict[str, Any]:
    return _run_local_job("simulate", payload or {}, _simulate_result)


@app.post("/api/jobs/optimize")
def job_optimize(payload: dict | None = None) -> dict[str, Any]:
    return _run_local_job("optimize", payload or {}, _optimize_result)


@app.post("/api/jobs/resource-plan")
def job_resource_plan(payload: dict | None = None) -> dict[str, Any]:
    return _run_local_job("resource-plan", payload or {}, lambda request: resource_plan(request))


@app.post("/api/jobs/robust-evaluate")
def job_robust(payload: dict | None = None) -> dict[str, Any]:
    return _run_local_job("robust-evaluate", payload or {}, lambda request: robust(request))


@app.post("/api/jobs/sensitivity")
def job_sensitivity(payload: dict | None = None) -> dict[str, Any]:
    return _run_local_job("sensitivity", payload or {}, lambda request: sensitivity(request))


@app.post("/api/jobs/benchmark")
def job_benchmark(payload: dict | None = None) -> dict[str, Any]:
    return _run_local_job("benchmark", payload or {}, lambda request: benchmark(request))


@app.post("/api/jobs/report")
def job_report(payload: dict | None = None) -> dict[str, Any]:
    return _run_local_job("report", payload or {}, _report_result)


@app.get("/api/model-profiles")
def model_profiles() -> dict[str, Any]:
    return {"profiles": list_model_profiles()}


@app.get("/api/model-profiles/{profile_id}")
def model_profile_get(profile_id: str) -> dict[str, Any]:
    return {"profile": get_model_profile(profile_id)}


@app.post("/api/model-profiles/{profile_id}/validate")
def model_profile_validate(profile_id: str, payload: dict | None = None) -> dict[str, Any]:
    scenario = _scenario_from_payload(payload or {})
    return validate_model_profile(scenario, profile_id)


@app.post("/api/import/preview")
def import_preview(payload: dict) -> dict[str, Any]:
    preview = preview_import(
        str(payload.get("kind", "nodes")),
        str(payload.get("content", "")),
        filename=str(payload.get("filename", "upload.csv")),
    )
    return {**preview, "quality_summary": summarize_quality(preview)}


@app.post("/api/candidates/generate")
def candidates_generate(payload: dict | None = None) -> dict[str, Any]:
    payload = payload or {}
    scenario = _scenario_from_payload(payload)
    return generate_candidates(
        scenario,
        families=payload.get("families"),
        limit=int(payload.get("limit", 16)),
    )


@app.get("/api/scenarios/{scenario_id}/candidates")
def scenario_candidates(scenario_id: str, limit: int = 16) -> dict[str, Any]:
    scenario_record = get_scenario(DB_PATH, scenario_id)
    scenario_payload = scenario_record.get("payload") if scenario_record else None
    scenario = scenario_from_config(load_config(CONFIG_PATH)) if not scenario_payload else _scenario_from_payload({"scenario": scenario_payload})
    return generate_candidates(scenario, limit=limit)


@app.post("/api/performance-field/diff")
def performance_diff(payload: dict) -> dict[str, Any]:
    baseline = payload.get("baseline") or payload.get("baseline_run") or {}
    candidate = payload.get("candidate") or payload.get("optimized_run") or payload.get("optimized") or {}
    return diff_layers(baseline, candidate)


@app.post("/api/copilot/ask")
def copilot_ask(payload: dict) -> dict[str, Any]:
    run_payload = None
    if payload.get("run_id"):
        run_record = get_run(DB_PATH, str(payload["run_id"]))
        run_payload = (run_record or {}).get("payload") or run_record
    return run_bound_answer(
        str(payload.get("message", "解释当前运行结果。")),
        run_payload=run_payload,
        report_payload=payload.get("report") if isinstance(payload.get("report"), dict) else None,
        workspace_context=workspace(),
    )


def _simulate_result(payload: dict[str, Any]) -> dict[str, Any]:
    scenario = _scenario_from_payload(payload)
    selected = payload.get("selected_candidate_ids", [])
    run = simulate_scenario(
        scenario,
        selected_candidate_ids=selected,
        model_profile=payload.get("model_profile", "closed_form_v0"),
        run_id=payload.get("run_id"),
    )
    result = run.model_dump(mode="json")
    context = _snapshot_context(scenario, payload)
    artifact_payload = {**result, "scenario": scenario.model_dump(mode="json")}
    result["storage"] = save_run(
        DB_PATH,
        artifact_payload,
        run_type="simulation",
        **context,
        artifact_root=ARTIFACT_ROOT,
    )
    return result


def _optimize_result(payload: dict[str, Any]) -> dict[str, Any]:
    scenario = _scenario_from_payload(payload)
    run = optimize_deployment(
        scenario,
        model_profile=payload.get("model_profile", "closed_form_v0"),
        solver=payload.get("solver"),
        run_id=payload.get("run_id"),
    )
    result = run.model_dump(mode="json")
    context = _snapshot_context(scenario, {**payload, "selected_candidate_ids": run.selected_candidate_ids})
    artifact_payload = {**result, "scenario": scenario.model_dump(mode="json")}
    result["storage"] = save_run(
        DB_PATH,
        artifact_payload,
        run_type="optimization",
        **context,
        artifact_root=ARTIFACT_ROOT,
    )
    return result


def _report_result(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("template", "enterprise") not in {"enterprise", "research", "grant"}:
        raise ValueError("Unknown report template.")
    result = _simulate_result(payload)
    scenario = _scenario_from_payload(payload)
    run = SimulationRun.model_validate(result)
    report_payload = run_grounded_report(run, scenario, template=payload.get("template", "enterprise"))
    saved = save_report(DB_PATH, report_payload, project_id=result["storage"]["project_id"], artifact_root=ARTIFACT_ROOT)
    return {**report_payload, "storage": saved}


def _run_local_job(job_type: str, payload: dict[str, Any], handler: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    scene = _scenario_from_payload(payload)
    snapshot = _snapshot_context(scene, payload)
    context = resolve_workspace_context(
        DB_PATH,
        **snapshot,
    )
    job = create_job(
        DB_PATH,
        job_type=job_type,
        request=payload,
        project_id=(context.get("project") or {}).get("id"),
        scenario_id=(context.get("scenario") or {}).get("id"),
        scenario_version_id=(context.get("scenario_version") or {}).get("id"),
        message=f"{job_type} 任务已创建",
    )
    job_id = job["job_id"]
    try:
        update_job(DB_PATH, job_id, status="running", progress=18, message=f"{job_type} 正在执行")
        result = handler(payload)
        storage = result.get("storage", {}) if isinstance(result, dict) else {}
        completed_context = storage
        if result.get("run_id") and not storage.get("scenario_version_id"):
            completed_context = get_run(DB_PATH, result["run_id"]) or storage
        job = update_job(
            DB_PATH,
            job_id,
            status="succeeded",
            progress=100,
            message=f"{job_type} 已完成",
            result=result,
            run_id=result.get("run_id") or storage.get("run_id"),
            report_id=storage.get("report_id") or result.get("report_id"),
            project_id=completed_context.get("project_id"),
            scenario_id=completed_context.get("scenario_id"),
            scenario_version_id=completed_context.get("scenario_version_id"),
        )
        return {"job": job, "result": result}
    except Exception as exc:
        job = update_job(DB_PATH, job_id, status="failed", progress=100, message=f"{job_type} 执行失败", error=str(exc))
        return {"job": job, "error": str(exc)}


def _snapshot_context(scenario: Scenario, payload: dict) -> dict[str, Any]:
    scenario.deployment = {**scenario.deployment, "selected_candidate_ids": payload.get("selected_candidate_ids", [])}
    scene = scenario.model_dump(mode="json")
    record = get_scenario(DB_PATH, scenario.id)
    project_id = (record or {}).get("project_id") or payload.get("project_id") or resolve_workspace_context(DB_PATH)["project"]["id"]
    if not record:
        record = create_scenario(DB_PATH, project_id=project_id, scenario_payload=scene, notes="运行快照")
    elif json.dumps(record["payload"], sort_keys=True) != json.dumps(scene, sort_keys=True):
        version = create_scenario_version(DB_PATH, scenario_id=scenario.id, scenario_payload=scene, notes="运行前自动快照")
        record["current_version_id"] = version["id"]
    return {"project_id": project_id, "scenario_id": scenario.id, "scenario_version_id": record["current_version_id"]}


def _scenario_from_payload(payload: dict) -> Scenario:
    defaults = _default_scenario.model_dump(mode="json")
    scenario_payload = payload.get("scenario")
    if payload.get("model_profile", "closed_form_v0") not in {"closed_form_v0", "standards_l1", "multi_fidelity_l2_adapter"}:
        raise ValueError("Unknown model profile.")
    if not isinstance(scenario_payload, dict):
        return _default_scenario.model_copy(deep=True)

    base = {"scenario": {}, "region": defaults["region"], "grid": defaults["grid"], "spectrum": defaults["spectrum"], "services": defaults["services"], "optimization": defaults["optimization"]}
    base["scenario"] = {
        "id": scenario_payload.get("id", defaults["id"]),
        "name": scenario_payload.get("name", defaults["name"]),
        "description": scenario_payload.get("description", base.get("scenario", {}).get("description", "")),
    }

    region_payload = scenario_payload.get("region", {})
    if isinstance(region_payload, dict):
        base["region"] = {
            **base.get("region", {}),
            **region_payload,
        }

    base["grid"] = {**base.get("grid", {}), **scenario_payload.get("grid", {})}
    base["spectrum"] = scenario_payload.get("spectrum", base.get("spectrum", {}))
    base["services"] = scenario_payload.get("services", base.get("services", {}))
    base["optimization"] = scenario_payload.get("optimization", base.get("optimization", {}))
    base["deployment"] = scenario_payload.get("deployment", {})
    base["time"] = scenario_payload.get("time", base.get("time", {}))
    fixed_nodes = scenario_payload.get("fixed_nodes")
    candidate_nodes = scenario_payload.get("candidate_nodes")
    base["nodes"] = {
        "fixed": [_node_payload_to_config(item) for item in fixed_nodes] if isinstance(fixed_nodes, list) else defaults["fixed_nodes"],
        "candidates": [_node_payload_to_config(item) for item in candidate_nodes] if isinstance(candidate_nodes, list) else defaults["candidate_nodes"],
    }
    scene = scenario_from_config(base)
    selected = payload.get("selected_candidate_ids", [])
    if not isinstance(selected, list) or any(node_id not in {node.id for node in scene.candidate_nodes} for node_id in selected):
        raise ValueError("Selected deployment contains unknown candidate IDs.")
    return scene


def _node_payload_to_config(node: dict) -> dict:
    return {
        "id": node["id"],
        "type": node["type"],
        "position": node.get("position", {}),
        "radio": node.get("radio", {}),
        "reconfigurable": node.get("reconfigurable", {}),
        "mobility": node.get("mobility", {}),
        "cost": node.get("cost", 0),
        "enabled": node.get("enabled", True),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.environ.get("RSAGIN_HOST", "127.0.0.1"), port=int(os.environ.get("RSAGIN_PORT", "8000")), log_level="info")
