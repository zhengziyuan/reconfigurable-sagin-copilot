from __future__ import annotations

from typing import Any


def run_bound_answer(
    message: str,
    *,
    run_payload: dict[str, Any] | None = None,
    report_payload: dict[str, Any] | None = None,
    workspace_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an auditable answer constrained to a run or an explicit context."""

    run_payload = run_payload or {}
    report_payload = report_payload or {}
    workspace_context = workspace_context or {}
    summary = run_payload.get("summary", {}) if isinstance(run_payload.get("summary"), dict) else {}
    run_id = run_payload.get("run_id") or run_payload.get("id") or report_payload.get("run_id")
    scenario_id = run_payload.get("scenario_id") or report_payload.get("scenario_id") or (workspace_context.get("scenario") or {}).get("id")
    model_profile = run_payload.get("model_profile") or report_payload.get("model_profile")

    if not run_id:
        return {
            "mode": "workspace_advice",
            "answer": "当前问题没有绑定 run_id。我可以给出规划流程建议，但不会声称任何具体 KPI 结论。",
            "recommendations": [
                "先选择项目和场景版本。",
                "运行仿真或优化任务，生成 manifest 和 summary。",
                "再用绑定 run 的报告或 Copilot 解释 KPI、约束和风险。",
            ],
            "evidence": {"scenario_id": scenario_id, "run_id": None, "model_profile": model_profile},
            "limitations": ["未绑定运行结果，所有数值结论均被禁止。"],
        }

    answer_parts = [f"已绑定运行 `{run_id}`。"]
    if "覆盖" in message or "coverage" in message.lower():
        answer_parts.append(f"当前覆盖率为 {summary.get('coverage_percent', '未知')}%，重点看盲区和边缘速率的耦合。")
    if "速率" in message or "容量" in message or "rate" in message.lower():
        answer_parts.append(f"平均速率为 {summary.get('avg_rate_mbps', '未知')} Mbps，P5 边缘速率为 {summary.get('p5_rate_mbps', '未知')} Mbps。")
    if "定位" in message or "peb" in message.lower():
        answer_parts.append(f"P95 定位误差为 {summary.get('p95_peb_m', '未知')} m，建议检查几何多样性和 MA/RIS 布局。")
    if "风险" in message or "鲁棒" in message:
        answer_parts.append(f"综合风险分数为 {summary.get('risk_score', '未知')}，需要结合鲁棒扰动和敏感性实验确认。")
    if len(answer_parts) == 1:
        answer_parts.append("我会优先解释 KPI、部署建议、约束状态、边际收益和报告证据来源。")

    recommendations = _recommendations(summary)
    return {
        "mode": "run_bound",
        "answer": " ".join(answer_parts),
        "recommendations": recommendations,
        "evidence": {
            "run_id": run_id,
            "scenario_id": scenario_id,
            "model_profile": model_profile,
            "artifact_dir": run_payload.get("artifact_dir"),
            "manifest_path": run_payload.get("manifest_path"),
            "report_id": report_payload.get("report_id") or report_payload.get("id"),
        },
        "limitations": [
            "回答只引用当前 run 的 summary 和 artifact 索引。",
            "如果需要现场验收结论，需要接入测量数据或高保真外部仿真回灌。",
        ],
    }


def _recommendations(summary: dict[str, Any]) -> list[str]:
    recommendations: list[str] = []
    coverage = _float(summary.get("coverage_percent"))
    p5_rate = _float(summary.get("p5_rate_mbps"))
    p95_peb = _float(summary.get("p95_peb_m"), 0.0)
    risk = _float(summary.get("risk_score"), 0.0)
    if coverage and coverage < 95:
        recommendations.append("覆盖率仍低于 95%，优先生成遮挡区 RIS/MIS 候选点并做鲁棒优化。")
    if p5_rate and p5_rate < 10:
        recommendations.append("P5 速率低于 10 Mbps，建议检查接入/回传拆分和热点带宽分配。")
    if p95_peb and p95_peb > 8:
        recommendations.append("定位尾部误差偏高，可增加 MA 阵列或空中平台改善几何。")
    if risk and risk > 0.35:
        recommendations.append("风险偏高，建议运行鲁棒扰动和 one-factor 敏感性实验。")
    return recommendations or ["当前 KPI 没有明显阻塞项，建议进入报告证据整理和高保真 ROI 复核。"]


def _float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
