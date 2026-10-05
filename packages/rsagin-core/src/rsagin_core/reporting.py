from __future__ import annotations

from .models import OptimizationRun, SimulationRun


def simulation_markdown(run: SimulationRun) -> str:
    summary = run.summary
    return f"""# 仿真报告：{run.scenario_id}

运行编号：`{run.run_id}`

模型档位：`{run.model_profile}`  
保真等级：`{run.fidelity_level}`

## 摘要

| 指标 | 数值 |
| --- | ---: |
| 覆盖率 | {summary["coverage_percent"]}% |
| 平均速率 | {summary["avg_rate_mbps"]} Mbps |
| 5% 边缘速率 | {summary["p5_rate_mbps"]} Mbps |
| 平均 PEB | {summary["avg_peb_m"]} m |
| P95 PEB | {summary["p95_peb_m"]} m |
| 感知评分 | {summary["avg_sensing_score"]} |
| 已选成本 | {summary["selected_cost"]} |
| 目标函数 | {summary["objective_score"]} |

## 模型假设

{_bullets(run.assumptions)}
"""


def optimization_markdown(run: OptimizationRun) -> str:
    delta = run.summary["delta"]
    recommendations = "\n".join(
        f"- `{item.node_id}` ({item.node_type.value}): {item.reason}"
        for item in run.recommendations
    ) or "- 未选择候选节点。"
    return f"""# 优化报告：{run.scenario_id}

优化运行编号：`{run.run_id}`

已选候选节点：{", ".join(run.selected_candidate_ids) or "无"}

## 基线与优化对比

| 指标 | 基线 | 优化后 | 变化 |
| --- | ---: | ---: | ---: |
| 覆盖率 (%) | {run.summary["baseline"]["coverage_percent"]} | {run.summary["optimized"]["coverage_percent"]} | {delta["coverage_percent"]} |
| 平均速率 (Mbps) | {run.summary["baseline"]["avg_rate_mbps"]} | {run.summary["optimized"]["avg_rate_mbps"]} | {delta["avg_rate_mbps"]} |
| P5 速率 (Mbps) | {run.summary["baseline"]["p5_rate_mbps"]} | {run.summary["optimized"]["p5_rate_mbps"]} | {delta["p5_rate_mbps"]} |
| 平均 PEB (m) | {run.summary["baseline"]["avg_peb_m"]} | {run.summary["optimized"]["avg_peb_m"]} | {delta["avg_peb_m"]} |
| 感知评分 | {run.summary["baseline"]["avg_sensing_score"]} | {run.summary["optimized"]["avg_sensing_score"]} | {delta["avg_sensing_score"]} |
| 成本 | {run.summary["baseline"]["selected_cost"]} | {run.summary["optimized"]["selected_cost"]} | {delta["selected_cost"]} |
| 目标函数 | {run.summary["baseline"]["objective_score"]} | {run.summary["optimized"]["objective_score"]} | {delta["objective_score"]} |

## 推荐节点

{recommendations}

## 智能体解释

优化器在成本和节点数量约束下选择上述节点，是因为它们提升了加权规划目标。若使用 L0 闭式模型，推荐结果应作为演示、论文基线和基金原型论证的部署假设；工程部署前应切换到更高保真模型并结合外场校准。
"""


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)
