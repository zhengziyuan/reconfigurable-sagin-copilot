from __future__ import annotations

from typing import Any

from rsagin_core.algorithm_catalog import algorithm_catalog
from rsagin_core.artifacts.manifest import artifact_schema
from rsagin_core.hardware.catalogs import hardware_catalog
from rsagin_core.model_fidelity.profile import list_model_profiles
from rsagin_core.plugins.registry import plugin_registry
from rsagin_core.standards.registry import standards_registry


def platform_catalog() -> dict[str, Any]:
    algorithms = algorithm_catalog()
    return {
        "positioning": (
            "面向空天地可重构网络的规划智能体原型，支持多业务性能场建模、多保真数字孪生、"
            "多目标鲁棒优化、硬件感知部署、资源管控、证据绑定报告和中文商业化交互。"
        ),
        "use_cases": _use_cases(),
        "problem_templates": _problem_templates(),
        "model_profiles": list_model_profiles(),
        "algorithm_families": algorithms["families"],
        "algorithm_catalog": algorithms,
        "hardware_catalog": hardware_catalog(),
        "standards": standards_registry(),
        "plugins": plugin_registry(),
        "artifact_schema": artifact_schema(),
        "report_templates": _report_templates(),
        "project_system": _project_system(),
        "delivery": _delivery_capabilities(),
        "scenario_model_algorithm_matrix": _scenario_model_algorithm_matrix(),
    }


def _use_cases() -> list[dict[str, Any]]:
    return [
        {
            "id": "low_altitude_isac_park",
            "name": "低空园区通信-定位-感知",
            "model": "standards_l1",
            "algorithm": "exhaustive_pareto",
            "outputs": ["覆盖", "速率", "PEB", "感知", "SLA 风险"],
        },
        {
            "id": "emergency_resilience_sagin",
            "name": "应急灾害空天地补盲",
            "model": "failure + NTN + temporary deployment",
            "algorithm": "robust_greedy",
            "outputs": ["恢复覆盖", "部署时间", "风险"],
        },
        {
            "id": "industrial_private_network_enhancement",
            "name": "工业专网/港口/矿山增强",
            "model": "SLA + cost + backhaul",
            "algorithm": "cost-benefit planning",
            "outputs": ["SLA", "ROI", "瓶颈"],
        },
        {
            "id": "remote_ntn_coverage",
            "name": "卫星直连与偏远泛在连接",
            "model": "NTN + terrain + satellite visibility",
            "algorithm": "space-air-ground site selection",
            "outputs": ["覆盖", "可见性", "链路预算"],
        },
        {
            "id": "urban_mmwave_ris_facade",
            "name": "城市毫米波 RIS/MIS 立面网络",
            "model": "blockage + facade + L2 ROI",
            "algorithm": "multi-fidelity RIS deployment",
            "outputs": ["街谷覆盖", "容量增益", "模型偏差"],
        },
        {
            "id": "sagin_isac_monitoring",
            "name": "空天地 ISAC 目标监测",
            "model": "detection + CRB proxy",
            "algorithm": "joint ISAC scheduling",
            "outputs": ["探测概率", "CRB", "调度解释"],
        },
        {
            "id": "ai_edge_sagin",
            "name": "空天地 AI 边缘计算",
            "model": "comm + compute + offloading",
            "algorithm": "offloading allocation",
            "outputs": ["时延", "能耗", "算力瓶颈"],
        },
        {
            "id": "array_as_a_service",
            "name": "可重构阵列即服务",
            "model": "tenant SLA + hardware catalog",
            "algorithm": "revenue-aware scheduling",
            "outputs": ["利用率", "租户 SLA", "收益"],
        },
    ]


def _problem_templates() -> list[dict[str, Any]]:
    return [
        {
            "id": "robust_isac_reconfigurable_planning",
            "name": "可重构 SAGIN 鲁棒通感部署规划",
            "objectives": {"maximize": ["coverage", "edge_rate", "sensing"], "minimize": ["p95_peb", "cost", "risk"]},
            "hard_constraints": ["budget", "max_node_count", "min_rate", "max_peb", "backhaul_capacity"],
        },
        {
            "id": "cost_benefit_enterprise_planning",
            "name": "横向项目成本收益规划",
            "objectives": {"maximize": ["sla_satisfaction", "roi"], "minimize": ["capex", "opex", "deployment_complexity"]},
            "hard_constraints": ["budget", "deployment_window", "site_availability"],
        },
    ]


def _report_templates() -> list[dict[str, Any]]:
    return [
        {"id": "research", "name": "科研论文实验报告", "sections": ["场景", "模型", "问题表述", "基线", "结果", "消融", "鲁棒性", "局限性"]},
        {"id": "enterprise", "name": "横向交付报告", "sections": ["业务目标", "现网能力", "瓶颈", "部署方案", "KPI 对比", "成本收益", "风险", "落地计划"]},
        {"id": "grant", "name": "基金/项目申请报告", "sections": ["科学问题", "技术路线", "原型系统", "创新点", "验证方案", "预期成果", "应用前景"]},
    ]


def _project_system() -> dict[str, Any]:
    return {
        "entities": ["用户", "组织", "项目", "场景", "场景版本", "运行", "任务", "报告", "证据"],
        "roles": ["viewer", "editor", "admin"],
        "local_mode": True,
        "database_ready_schema": [
            "projects",
            "scenarios",
            "scenario_versions",
            "runs",
            "jobs",
            "reports",
            "artifacts",
        ],
    }


def _delivery_capabilities() -> dict[str, Any]:
    return {
        "private_deployment": ["docker_compose_ready", "single_machine_sqlite", "postgres_minio_celery_ready"],
        "api": [
            "FastAPI OpenAPI",
            "simulate",
            "optimize",
            "candidate-generate",
            "resource-plan",
            "robust-evaluate",
            "benchmark",
            "report",
            "copilot",
        ],
        "sdk_cli": ["rsagin simulate", "rsagin optimize", "rsagin benchmark", "rsagin report"],
        "error_taxonomy": [
            "data_error",
            "model_out_of_range",
            "optimization_infeasible",
            "server_error",
            "job_timeout",
            "permission_error",
        ],
    }


def _scenario_model_algorithm_matrix() -> list[dict[str, str]]:
    return [
        {"scenario": "低空园区", "model": "通信+定位+感知性能场", "algorithm": "Pareto + UAV/RIS/MA 部署", "output": "覆盖、速率、PEB、感知、风险"},
        {"scenario": "应急灾害", "model": "失效网络+卫星窗口+临时空中平台", "algorithm": "鲁棒恢复 + 时间扩展调度", "output": "恢复覆盖、部署时间、SLA 风险"},
        {"scenario": "工业专网", "model": "SLA+成本+回传瓶颈", "algorithm": "成本收益规划 + 关联优化", "output": "SLA 满足率、成本收益、瓶颈定位"},
        {"scenario": "偏远覆盖", "model": "NTN 链路+地形遮挡+卫星可见性", "algorithm": "星地/空地协同选址", "output": "泛在覆盖、卫星可见性、链路预算"},
        {"scenario": "城市毫米波", "model": "建筑遮挡+RIS/MIS 立面+L2 ROI", "algorithm": "多保真 RIS/MIS 部署", "output": "街谷覆盖、容量增益、模型偏差"},
        {"scenario": "ISAC 监测", "model": "感知 CRB+探测概率+通信约束", "algorithm": "通感联合调度", "output": "探测概率、CRB、资源占用"},
        {"scenario": "AI 边缘", "model": "通信+计算+任务卸载", "algorithm": "offloading + resource allocation", "output": "时延、能耗、算力瓶颈"},
    ]
