import type { MetricKey } from "../types";

export const metricScales: Record<MetricKey, { min: number; max: number; unit: string; low: string; high: string; colors: string[] }> = {
  coverage: { min: 0, max: 1, unit: "", low: "未覆盖", high: "已覆盖", colors: ["#cc475e", "#f0a33a", "#42b8bd", "#007c83"] },
  rate: { min: 0, max: 200, unit: "Mbps", low: "0", high: "≥200", colors: ["#cc475e", "#f0a33a", "#42b8bd", "#007c83"] },
  localization_peb: { min: 0, max: 20, unit: "m", low: "0", high: "≥20", colors: ["#087f7e", "#63c0b0", "#f2a83b", "#d84a62"] },
  sensing: { min: 0, max: 1, unit: "", low: "0", high: "1", colors: ["#d34e66", "#e9a33f", "#48a7c6", "#2e64ad"] },
  sla_violation: { min: 0, max: 1, unit: "", low: "达标", high: "违约", colors: ["#18877d", "#78bba7", "#ee8f3f", "#d9475f"] },
  risk: { min: 0, max: 1, unit: "", low: "0", high: "1", colors: ["#177f79", "#72b7a8", "#ee8f3f", "#d9475f"] },
};

export function metricFraction(metric: MetricKey, value: number) {
  const scale = metricScales[metric];
  return Math.max(0, Math.min(1, (value - scale.min) / (scale.max - scale.min)));
}
export function physicalMetricColor(metric: MetricKey, value: number) {
  const colors = metricScales[metric].colors;
  return colors[Math.min(colors.length - 1, Math.floor(metricFraction(metric, value) * colors.length))];
}
