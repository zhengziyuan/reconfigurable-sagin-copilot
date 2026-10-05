import type { ScenarioShape, SimulationRun } from "../types";

export function planningConstraints(run: SimulationRun, scenario: ScenarioShape) {
  const communication = (scenario.services?.communication ?? {}) as Record<string, number>;
  const localization = (scenario.services?.localization ?? {}) as Record<string, number>;
  const sensing = (scenario.services?.sensing ?? {}) as Record<string, number>;
  const budget = (scenario.optimization?.budget ?? {}) as Record<string, number>;
  return [
    { label: "覆盖率", key: "coverage_percent", unit: "%", target: communication.min_coverage_percent ?? 90, lower: false },
    { label: "P5 边缘速率", key: "p5_rate_mbps", unit: "Mbps", target: communication.min_rate_mbps ?? 10, lower: false },
    { label: "P95 定位 PEB", key: "p95_peb_m", unit: "m", target: localization.max_peb_m ?? 5, lower: true },
    { label: "平均感知", key: "avg_sensing_score", unit: "", target: sensing.min_score ?? 0.55, lower: false },
    { label: "部署成本", key: "selected_cost", unit: "", target: budget.max_total_cost ?? 36, lower: true },
  ].map((row) => {
    const value = Number(run.summary[row.key]);
    return { ...row, value, operator: row.lower ? "≤" : "≥", satisfied: Number.isFinite(value) && (row.lower ? value <= row.target : value >= row.target) };
  });
}
