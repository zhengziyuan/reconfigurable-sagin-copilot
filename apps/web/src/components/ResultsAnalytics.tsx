import { useState } from "react";
import { Download } from "lucide-react";
import { downloadText } from "../lib/api";
import { planningConstraints } from "../lib/planning";
import type { SimulationRun, ScenarioShape } from "../types";

export function ResultsAnalytics({ run, baseline, scenario, stale }: { run: SimulationRun; baseline: SimulationRun; scenario: ScenarioShape; stale: boolean }) {
  const [chartMetric, setChartMetric] = useState<"rate" | "localization_peb">("rate");
  const values = run.layers[chartMetric]?.cells.map((cell) => cell.value).filter(Number.isFinite) ?? [];
  const original = baseline.layers[chartMetric]?.cells.map((cell) => cell.value).filter(Number.isFinite) ?? [];
  const rows = planningConstraints(run, scenario);
  const exportCells = () => {
    const cells = run.layers.rate.cells;
    const content = ["cell_id,longitude,latitude,rate_mbps,peb_m,sinr_db,sensing_score,serving_node", ...cells.map((cell) => [cell.cell_id, cell.lon, cell.lat, cell.properties.rate_mbps, cell.properties.peb_m, cell.properties.sinr_db, cell.properties.sensing_score, cell.properties.best_node].join(","))].join("\n");
    downloadText(`${run.run_id ?? scenario.id}-cells.csv`, content, "text/csv");
  };
  return <footer className="results-analytics">
    <section className="analytics-kpis">
      <div className="analytics-heading"><h2>运行指标</h2><span>{stale ? "编辑后待重算" : `${run.layers.rate.cells.length} 个网格 · L${run.fidelity_level ?? 0}`}</span></div>
      <div className="actual-kpi-row">{rows.map((row) => {
        const value = row.value;
        const good = row.satisfied;
        return <div key={row.key} className="actual-kpi"><span>{row.label}</span><strong>{format(value)}<small>{row.unit}</small></strong><em className={good ? "target-met" : "target-missed"}>{good ? "达标" : "未达标"} · {row.lower ? "≤" : "≥"} {row.target}</em></div>;
      })}</div>
      <div className="run-provenance"><code>{run.run_id ?? "预览数据"}</code><span>{stale ? "指标对应上次运行" : run.run_id?.startsWith("api_") || run.run_id === "scene_preview" ? "启动预览 · 尚未保存为运行" : run.run_id?.startsWith("fallback") ? "离线示例 · 非运行证据" : "指标对应当前运行"}</span></div>
    </section>
    <section className="analytics-chart">
      <div className="analytics-heading"><div className="chart-tabs"><button className={chartMetric === "rate" ? "active" : ""} onClick={() => setChartMetric("rate")}>速率分布</button><button className={chartMetric === "localization_peb" ? "active" : ""} onClick={() => setChartMetric("localization_peb")}>定位分布</button></div><button title="导出网格结果 CSV" aria-label="导出网格结果" onClick={exportCells}><Download size={16} /></button></div>
      <CdfPlot current={values} baseline={original} unit={chartMetric === "rate" ? "Mbps" : "m"} />
    </section>
  </footer>;
}

function CdfPlot({ current, baseline, unit }: { current: number[]; baseline: number[]; unit: string }) {
  const finite = [...current, ...baseline].filter(Number.isFinite);
  const max = Math.max(1, ...finite);
  const min = Math.min(0, ...finite);
  const path = (items: number[]) => [...items].sort((a, b) => a - b).map((value, index, sorted) => `${index ? "L" : "M"}${(40 + (value - min) / (max - min) * 430).toFixed(2)},${(111 - (index + 1) / sorted.length * 86).toFixed(2)}`).join(" ");
  return <svg className="cdf-plot" viewBox="0 0 510 143" role="img" aria-label={`${unit} 累计概率分布，${current.length} 个网格`}>
    {[0, 0.5, 1].map((value) => <g key={value}><line x1="40" y1={111 - value * 86} x2="470" y2={111 - value * 86} className="cdf-grid" /><text x="32" y={115 - value * 86} textAnchor="end">{value * 100}%</text></g>)}
    <path d={path(baseline)} className="cdf-baseline" /><path d={path(current)} className="cdf-current" />
    {[0, 0.5, 1].map((value) => <text key={value} x={40 + value * 430} y="131" textAnchor={value === 1 ? "end" : value === 0 ? "start" : "middle"}>{format(min + value * (max - min))}</text>)}
    <text x="505" y="131" textAnchor="end">{unit}</text>
    <line x1="316" y1="12" x2="332" y2="12" className="cdf-baseline" /><text x="338" y="16">基线</text>
    <line x1="397" y1="12" x2="413" y2="12" className="cdf-current" /><text x="419" y="16">当前</text>
  </svg>;
}

function format(value: number) { return Number.isFinite(value) ? Number(value.toFixed(2)).toLocaleString("zh-CN") : "--"; }
