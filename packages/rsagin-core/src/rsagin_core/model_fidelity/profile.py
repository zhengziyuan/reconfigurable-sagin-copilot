from __future__ import annotations

from typing import Any


MODEL_PROFILES: dict[str, dict[str, Any]] = {
    "closed_form_v0": {
        "id": "closed_form_v0",
        "name": "L0 快速闭式规划模型",
        "fidelity_level": 0,
        "status": "stable_demo",
        "valid_frequency_range_hz": [1e9, 100e9],
        "supported_links": ["terrestrial", "air_ground", "ntn_proxy"],
        "traceability": [
            "自由空间路径损耗与 Shannon 风格速率方程。",
            "PEB 与感知评分采用规划代理指标。",
        ],
        "limitations": [
            "暂不追踪完整随机簇信道、小尺度衰落、降雨和 NTN 标准项。",
            "适合快速筛选、教学展示和 UI 冒烟测试。",
        ],
        "recommended_use": "快速全局扫描、算法调试和交互式候选点探索。",
    },
    "standards_l1": {
        "id": "standards_l1",
        "name": "L1 3GPP/ITU 可追溯规划模型",
        "fidelity_level": 1,
        "status": "partial_traceable",
        "valid_frequency_range_hz": [1e9, 100e9],
        "supported_links": ["terrestrial", "air_ground", "ntn"],
        "traceability": [
            "3GPP TR 38.901 UMa/RMa 路径损耗结构与 LOS 概率子集。",
            "3GPP TR 38.811 风格 NTN 星地损耗分解。",
            "ITU-R P.838-3 比雨衰公式；有效雨程与 P.676 风格气体吸收仍为近似。",
        ],
        "limitations": [
            "不是完整随机簇信道模型。",
            "雨衰、气体吸收和杂波项为紧凑规划近似。",
            "适合可行性规划，不等同最终外场验收。",
        ],
        "recommended_use": "科研原型、基金演示、横向规划和早期工程比选。",
    },
    "multi_fidelity_l2_adapter": {
        "id": "multi_fidelity_l2_adapter",
        "name": "L2 局部高保真射线追踪适配器",
        "fidelity_level": 2,
        "status": "adapter_ready",
        "valid_frequency_range_hz": [1e9, 100e9],
        "supported_links": ["local_roi", "ray_tracing_export"],
        "traceability": [
            "导出薄弱/关键 ROI 场景，供外部高保真工具使用。",
            "可将校准后的损耗差异回灌到 L1 规划运行。",
        ],
        "limitations": [
            "当前本地模式不内置执行射线追踪求解器。",
            "真正 L2/L3 验证需要 Sionna RT、ns-3 或实验室/硬件流水线。",
        ],
        "recommended_use": "ROI 选择、场景导出、高保真闭环校准和论文消融实验。",
    },
}


def list_model_profiles() -> list[dict[str, Any]]:
    return list(MODEL_PROFILES.values())


def get_model_profile(profile_id: str) -> dict[str, Any]:
    return MODEL_PROFILES.get(profile_id, MODEL_PROFILES["closed_form_v0"])
