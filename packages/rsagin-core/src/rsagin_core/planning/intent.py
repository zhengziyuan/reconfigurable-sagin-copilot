from __future__ import annotations

import re
from typing import Any


def parse_planning_intent(text: str) -> dict[str, Any]:
    normalized = text.strip()
    numbers = [float(item) for item in re.findall(r"\d+(?:\.\d+)?", normalized)]
    return {
        "intent_text": normalized,
        "domain": _domain(normalized),
        "constraints": {
            "target_coverage_percent": _after_keyword(normalized, ["覆盖"], default=95.0),
            "min_edge_rate_mbps": _after_keyword(normalized, ["速率", "Mbps", "mbps"], default=10.0),
            "max_peb_m": _after_keyword(normalized, ["PEB", "定位"], default=5.0),
            "max_budget": numbers[-1] if "预算" in normalized and numbers else 36.0,
        },
        "recommended_profile": "standards_l1" if any(word in normalized for word in ["可信", "标准", "横向", "基金"]) else "closed_form_v0",
        "recommended_solver": "exhaustive_pareto" if any(word in normalized for word in ["Pareto", "多目标", "折中"]) else "greedy_fast",
    }


def _domain(text: str) -> str:
    if "应急" in text or "灾害" in text:
        return "emergency_resilience"
    if "工业" in text or "港口" in text or "矿山" in text:
        return "industrial_private_network"
    if "偏远" in text or "卫星" in text:
        return "remote_ntn_coverage"
    if "ISAC" in text or "感知" in text:
        return "low_altitude_isac"
    return "low_altitude_isac"


def _after_keyword(text: str, keywords: list[str], default: float) -> float:
    for keyword in keywords:
        idx = text.find(keyword)
        if idx >= 0:
            window = text[max(0, idx - 12): idx + 24]
            matches = re.findall(r"\d+(?:\.\d+)?", window)
            if matches:
                return float(matches[0])
    return default
