from rsagin_core.agent.planner import build_tool_plan
from rsagin_core.algorithm_catalog import algorithm_catalog
from rsagin_core.benchmarks import benchmark_suite
from rsagin_core.candidates import generate_candidates
from rsagin_core.config import load_config
from rsagin_core.copilot import run_bound_answer
from rsagin_core.data_ingestion import preview_import
from rsagin_core.high_fidelity import select_high_fidelity_rois
from rsagin_core.models import scenario_from_config
from rsagin_core.optimization import optimize_deployment
from rsagin_core.performance_field import diff_layers
from rsagin_core.persistence import (
    create_job,
    get_job,
    get_report_evidence,
    get_run,
    initialize_store,
    list_runs,
    save_report,
    save_run,
    seed_demo_workspace,
    update_job,
)
from rsagin_core.platform_catalog import platform_catalog
from rsagin_core.resource_management import plan_resources
from rsagin_core.simulation import simulate_scenario
from rsagin_core.uncertainty import robust_evaluate


def test_demo_scenario_simulates():
    config = load_config("configs/scenarios/demo_low_altitude_emergency.yaml")
    scenario = scenario_from_config(config)
    run = simulate_scenario(scenario, run_id="test_run")

    assert run.summary["grid_cell_count"] > 0
    assert 0 <= run.summary["coverage_percent"] <= 100
    assert run.layers["rate"].cells
    assert run.layers["sla_violation"].cells
    assert run.layers["risk"].cells
    assert run.summary["run_quality"]["failed"] == 0
    assert run.summary["run_manifest"]["manifest_version"] == "0.5"
    assert "multi_service_field" in run.summary


def test_optimizer_selects_within_budget_and_explains_constraints():
    config = load_config("configs/scenarios/demo_low_altitude_emergency.yaml")
    scenario = scenario_from_config(config)
    run = optimize_deployment(scenario, run_id="test_opt")

    assert run.summary["optimized"]["selected_cost"] <= scenario.services["cost"]["max_budget"]
    assert len(run.selected_candidate_ids) <= len(scenario.candidate_nodes)
    assert run.summary["constraint_status"]
    assert "optimization_status" in run.summary
    assert "marginal_gain_trace" in run.summary


def test_resource_plan_returns_schedulable_flows():
    config = load_config("configs/scenarios/demo_low_altitude_emergency.yaml")
    scenario = scenario_from_config(config)
    selected = ["ma_array_south", "ris_facade_south", "ris_facade_east", "uav_relay_west"]
    plan = plan_resources(scenario, selected_candidate_ids=selected, max_flows=10, iterations=4)

    assert plan["summary"]["scheduled_flows"] == 10
    assert plan["summary"]["sum_rate_mbps"] > 0
    assert plan["summary"]["access_backhaul"]["end_to_end_sum_rate_mbps"] > 0
    assert plan["flows"][0]["serving_node"]
    assert plan["flows"][0]["bandwidth_mhz"] > 0
    assert "weighted_greedy" in plan["benchmarks"]
    assert len(plan["iterations"]) == 4


def test_standards_l1_exposes_physical_channel_terms():
    config = load_config("configs/scenarios/demo_low_altitude_emergency.yaml")
    scenario = scenario_from_config(config)
    run = simulate_scenario(
        scenario,
        selected_candidate_ids=["ma_array_south", "ris_facade_south", "ris_facade_east", "uav_relay_west"],
        model_profile="standards_l1",
        run_id="test_standards_l1",
    )
    first_cell = run.layers["rate"].cells[0]

    assert run.fidelity_level == 1
    assert "3GPP" in " ".join(run.assumptions)
    assert first_cell.properties["channel_model"].startswith("3gpp")
    assert first_cell.properties["path_loss_db"] > 0
    assert "los_probability" in first_cell.properties


def test_exhaustive_optimizer_reports_pareto_front():
    config = load_config("configs/scenarios/demo_low_altitude_emergency.yaml")
    scenario = scenario_from_config(config)
    run = optimize_deployment(scenario, run_id="test_exact", solver="exhaustive_pareto")

    assert run.summary["solver"] == "exhaustive_pareto"
    assert run.summary["evaluated_candidates"] > 0
    assert run.summary["optimized"]["objective_score"] >= run.summary["baseline"]["objective_score"]
    assert run.summary["pareto_front"]


def test_nsga2_optimizer_is_reproducible_and_returns_front():
    config = load_config("configs/scenarios/demo_low_altitude_emergency.yaml")
    scenario = scenario_from_config(config)
    run = optimize_deployment(scenario, run_id="test_nsga2", solver="nsga2_pareto")

    assert run.summary["solver"] == "nsga2_pareto"
    assert run.summary["evaluated_candidates"] > 0
    assert run.summary["pareto_front"]
    assert len(run.summary["convergence_trace"]) == run.summary["generations"]
    assert run.summary["optimized"]["selected_cost"] <= scenario.services["cost"]["max_budget"]


def test_resource_algorithm_library_runs_all_registered_methods():
    config = load_config("configs/scenarios/demo_low_altitude_emergency.yaml")
    scenario = scenario_from_config(config)
    selected = ["ma_array_south", "ris_facade_south", "uav_relay_hotspot"]
    for method in ["max_sinr", "weighted_greedy", "proportional_fair", "ucb_bandit", "wmmse"]:
        plan = plan_resources(scenario, selected_candidate_ids=selected, method=method, max_flows=8, iterations=3)
        assert plan["method"] == method
        assert plan["summary"]["scheduled_flows"] == 8
        assert plan["summary"]["sum_rate_mbps"] > 0
        assert set(plan["benchmarks"]) == {"max_sinr", "weighted_greedy", "proportional_fair", "ucb_bandit", "wmmse"}


def test_algorithm_catalog_distinguishes_maturity_and_execution_scope():
    catalog = algorithm_catalog()
    algorithms = {item["id"]: item for item in catalog["algorithms"]}

    assert catalog["version"] == "0.8.0"
    assert algorithms["nsga2_pareto"]["status"] == "research_reproduction"
    assert algorithms["proportional_fair"]["engine"] == "native"
    assert algorithms["l2_roi_export"]["engine"] == "adapter"


def test_platform_catalog_and_agent_plan_are_available():
    catalog = platform_catalog()
    plan = build_tool_plan("低空园区需要 95% 覆盖、10 Mbps 边缘速率、PEB 低于 5 m，并生成科研和企业报告。")

    assert len(catalog["use_cases"]) >= 8
    assert catalog["problem_templates"]
    assert plan["must_bind_run_id"] is True
    assert any(item["tool"] == "robust_evaluate" for item in plan["tool_chain"])


def test_robust_benchmark_and_roi_workflow_runs():
    config = load_config("configs/scenarios/demo_low_altitude_emergency.yaml")
    scenario = scenario_from_config(config)
    selected = ["ma_array_south", "ris_facade_south", "uav_relay_hotspot"]
    robust = robust_evaluate(scenario, selected_candidate_ids=selected, model_profile="standards_l1", samples=3, seed=7)
    suite = benchmark_suite(scenario, model_profile="closed_form_v0")
    run = simulate_scenario(scenario, selected_candidate_ids=selected, model_profile="standards_l1", run_id="test_roi")
    rois = select_high_fidelity_rois(run, limit=3)

    assert robust["samples"] == 3
    assert "sla_violation_probability" in robust["risk"]
    assert suite["rows"]
    assert len(rois) <= 3


def test_sqlite_run_store_persists_runs_and_reports(tmp_path):
    config = load_config("configs/scenarios/demo_low_altitude_emergency.yaml")
    scenario = scenario_from_config(config)
    run = simulate_scenario(scenario, run_id="test_persist_run")
    db_path = tmp_path / "rsagin_test.db"
    artifact_root = tmp_path / "artifacts"

    initialize_store(db_path)
    saved = save_run(db_path, run, run_type="simulation", artifact_root=artifact_root)
    rows = list_runs(db_path)
    report = save_report(
        db_path,
        {
            "run_id": run.run_id,
            "scenario_id": scenario.id,
            "model_profile": run.model_profile,
            "template": "enterprise",
            "summary": run.summary,
            "sections": ["部署方案"],
            "executive_summary": "测试报告摘要。",
            "assumptions": run.assumptions,
            "limitations": ["测试环境。"],
        },
        artifact_root=artifact_root,
    )

    assert saved["run_id"] == "test_persist_run"
    assert rows[0]["run_id"] == "test_persist_run"
    assert (artifact_root / "runs" / "test_persist_run" / "run.json").exists()
    assert (artifact_root / "runs" / "test_persist_run" / "manifest.json").exists()
    assert report["artifact_path"]
    assert "测试报告摘要" in report["markdown"]


def test_project_job_manifest_and_evidence_workflow(tmp_path):
    config = load_config("configs/scenarios/demo_low_altitude_emergency.yaml")
    scenario = scenario_from_config(config)
    db_path = tmp_path / "rsagin_test.db"
    artifact_root = tmp_path / "artifacts"

    context = seed_demo_workspace(db_path, scenario.model_dump(mode="json"))
    job = create_job(db_path, job_type="simulate", request={"scenario_id": scenario.id}, project_id=context["project_id"])
    updated = update_job(db_path, job["job_id"], status="running", progress=50, message="运行中")
    assert updated["status"] == "running"

    run = simulate_scenario(scenario, run_id="test_manifest_v06")
    saved = save_run(
        db_path,
        {**run.model_dump(mode="json"), "scenario": scenario.model_dump(mode="json")},
        run_type="simulation",
        project_id=context["project_id"],
        scenario_version_id=context["scenario_version_id"],
        artifact_root=artifact_root,
    )
    report = save_report(
        db_path,
        {
            "run_id": run.run_id,
            "scenario_id": scenario.id,
            "model_profile": run.model_profile,
            "template": "enterprise",
            "summary": run.summary,
            "sections": ["部署方案"],
            "executive_summary": "测试报告摘要。",
            "assumptions": run.assumptions,
            "limitations": ["测试环境。"],
        },
        project_id=context["project_id"],
        artifact_root=artifact_root,
    )
    update_job(db_path, job["job_id"], status="succeeded", progress=100, message="完成", run_id=run.run_id, result={"storage": saved})

    stored_run = get_run(db_path, run.run_id)
    stored_job = get_job(db_path, job["job_id"])
    evidence = get_report_evidence(db_path, report["report_id"])

    assert stored_run["manifest_path"].endswith("manifest.json")
    assert stored_job["run_id"] == run.run_id
    assert evidence["run_id"] == run.run_id
    assert (artifact_root / "runs" / run.run_id / "quality.json").exists()


def test_candidate_generation_import_performance_and_copilot():
    config = load_config("configs/scenarios/demo_low_altitude_emergency.yaml")
    scenario = scenario_from_config(config)
    generated = generate_candidates(scenario, limit=6)
    preview = preview_import("nodes", "id,type,lat,lon,alt_m\nn1,ris,30.26,120.14,20\n", filename="nodes.csv")
    baseline = simulate_scenario(scenario, run_id="test_diff_base")
    optimized = optimize_deployment(scenario, run_id="test_diff_opt")
    layer_diff = diff_layers(baseline, optimized.optimized_run)
    answer = run_bound_answer("解释覆盖和速率", run_payload=optimized.optimized_run.model_dump(mode="json"))

    assert generated["candidates"]
    assert generated["candidate_nodes"][0]["position"]["lat"]
    assert preview["quality"]["valid"] is True
    assert "rate" in layer_diff["diffs"]
    assert answer["mode"] == "run_bound"
