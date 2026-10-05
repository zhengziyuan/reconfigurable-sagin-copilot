from __future__ import annotations

from typing import Any


def run_grounded_report(run: Any, scenario: Any, template: str = "enterprise") -> dict[str, Any]:
    summary = run.summary
    common = {
        "run_id": run.run_id,
        "scenario_id": scenario.id,
        "model_profile": run.model_profile,
        "summary": summary,
        "assumptions": run.assumptions,
        "limitations": [
            "当前结果属于规划阶段仿真，不等同于现场验收结论。",
            "L1 档位在结构上对齐 3GPP/ITU 标准项，但尚未覆盖完整随机信道栈。",
            "RIS/MIS/MA 硬件模型仍是规划代理模型，工程部署前需要实验室或外场校准。",
        ],
    }
    if template == "research":
        sections = [
            "场景描述",
            "数学建模与问题表述",
            "模型假设与标准依据",
            "基线算法与消融设置",
            "主要仿真结果",
            "鲁棒性与敏感性分析",
            "运行效率分析",
            "局限性",
        ]
    elif template == "grant":
        sections = [
            "科学问题",
            "技术路线",
            "原型系统架构",
            "模型与算法创新",
            "验证方案",
            "预期成果",
            "应用前景",
        ]
    else:
        sections = [
            "项目区域与业务目标",
            "现网基础能力",
            "覆盖与容量短板",
            "定位与感知能力",
            "推荐部署方案",
            "KPI 对比",
            "成本收益分析",
            "风险与局限",
            "分阶段落地计划",
        ]
    return {
        **common,
        "template": template,
        "sections": sections,
        "executive_summary": (
            f"运行 {run.run_id} 在当前场景下达到 {summary.get('coverage_percent')}% 覆盖率、"
            f"{summary.get('avg_rate_mbps')} Mbps 平均速率、"
            f"{summary.get('p95_peb_m')} m P95 定位误差，部署成本为 {summary.get('selected_cost')}。"
        ),
    }
