from __future__ import annotations

from typing import Any

from .intent_parser import parse_intent


def build_tool_plan(text: str) -> dict[str, Any]:
    intent = parse_intent(text)
    return {
        "intent": intent,
        "tool_chain": [
            {"tool": "validate_model_profile", "reason": "计算前检查模型适用范围、频段、链路类型和局限性。"},
            {"tool": "generate_candidates", "reason": "根据区域、热点和遮挡区自动生成 RIS/MIS/MA/低空平台候选点。"},
            {"tool": "simulate_scenario", "profile": "closed_form_v0", "reason": "先做快速全局基线扫描。"},
            {"tool": "optimize_deployment", "profile": intent["recommended_profile"], "solver": intent["recommended_solver"]},
            {"tool": "plan_resources", "method": "wmmse", "reason": "评估接入、回传、带宽和功率分配。"},
            {"tool": "robust_evaluate", "samples": 12, "reason": "估计天气、信道和硬件不确定性风险。"},
            {"tool": "one_factor_sensitivity", "reason": "识别最敏感的场景假设。"},
            {"tool": "run_grounded_report", "templates": ["research", "enterprise", "grant"]},
        ],
        "must_bind_run_id": True,
    }
