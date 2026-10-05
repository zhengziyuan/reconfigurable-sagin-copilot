import { useRef } from "react";
import { Download, FolderOpen, History, Redo2, Save, Undo2, Upload } from "lucide-react";
import type { ScenarioShape, WorkspaceSnapshot } from "../types";

export function ProjectToolbar(props: {
  scenario: ScenarioShape; workspace: WorkspaceSnapshot; dirty: boolean; busy: boolean;
  canUndo: boolean; canRedo: boolean; hasDraft: boolean;
  onUndo: () => void; onRedo: () => void; onSave: () => void; onExport: () => void;
  onImport: (file: File) => void; onHistory: () => void; onRestoreDraft: () => void;
  onLoad: (id: string) => void;
  onProjects: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  return <div className="project-toolbar">
    <div className="project-context">
      <button aria-label="项目管理" title="项目与场景" onClick={props.onProjects} disabled={props.busy}><FolderOpen size={17} /></button>
      <select aria-label="选择场景" value={props.scenario.id} onChange={(event) => props.onLoad(event.target.value)} disabled={props.busy}>
        {!props.workspace.scenarios.some((scene) => scene.id === props.scenario.id) && <option value={props.scenario.id}>{props.scenario.name}</option>}
        {props.workspace.scenarios.map((scene) => <option key={String(scene.id)} value={String(scene.id)}>{String(scene.name)}</option>)}
      </select>
      <span className={props.dirty ? "document-state unsaved" : "document-state"}>{props.dirty ? "有未保存修改" : "场景已载入"}</span>
    </div>
    <div className="document-actions">
      {props.hasDraft && <button className="draft-button" onClick={props.onRestoreDraft}>恢复草稿</button>}
      <button title="撤销" aria-label="撤销" disabled={!props.canUndo || props.busy} onClick={props.onUndo}><Undo2 size={16} /></button>
      <button title="重做" aria-label="重做" disabled={!props.canRedo || props.busy} onClick={props.onRedo}><Redo2 size={16} /></button>
      <span className="toolbar-divider" />
      <button title="导入场景 JSON" aria-label="导入场景" onClick={() => input.current?.click()} disabled={props.busy}><Upload size={16} /></button>
      <button title="导出场景 JSON" aria-label="导出场景" onClick={props.onExport}><Download size={16} /></button>
      <button title="版本历史" aria-label="版本历史" onClick={props.onHistory} disabled={props.busy}><History size={16} /></button>
      <button className="save-button" disabled={props.busy} onClick={props.onSave}><Save size={15} /><span>保存版本</span></button>
      <input ref={input} type="file" accept=".json,application/json" hidden onChange={(event) => {
        const file = event.target.files?.[0];
        if (file) props.onImport(file);
        event.target.value = "";
      }} />
    </div>
  </div>;
}

export function ScenarioParameters({ scenario, onChange }: { scenario: ScenarioShape; onChange: (next: ScenarioShape) => void }) {
  const grid = scenario.grid ?? {};
  const weather = (grid.weather ?? {}) as Record<string, number>;
  const spectrum = scenario.spectrum ?? {};
  const services = scenario.services ?? {};
  const optimization = scenario.optimization ?? {};
  const budget = (optimization.budget ?? {}) as Record<string, number>;
  const communication = (services.communication ?? {}) as Record<string, number>;
  const localization = (services.localization ?? {}) as Record<string, number>;
  const setGrid = (key: string, value: unknown) => onChange({ ...scenario, grid: { ...grid, [key]: value } });
  return <div className="parameter-section">
    <label className="field-label">场景名称<input aria-label="场景名称" value={scenario.name} onChange={(event) => onChange({ ...scenario, name: event.target.value })} /></label>
    <div className="parameter-grid">
      <NumberField label="载频" unit="GHz" value={Number(spectrum.carrier_frequency_hz ?? 28e9) / 1e9} min={1} max={100} step={0.5} onChange={(v) => onChange({ ...scenario, spectrum: { ...spectrum, carrier_frequency_hz: v * 1e9 } })} />
      <NumberField label="带宽" unit="MHz" value={Number(spectrum.bandwidth_hz ?? 100e6) / 1e6} min={1} max={1000} onChange={(v) => onChange({ ...scenario, spectrum: { ...spectrum, bandwidth_hz: v * 1e6 } })} />
      <NumberField label="网格列数" value={Number(grid.nx ?? 20)} min={4} max={50} onChange={(v) => setGrid("nx", v)} />
      <NumberField label="网格行数" value={Number(grid.ny ?? 16)} min={4} max={50} onChange={(v) => setGrid("ny", v)} />
      <NumberField label="雨强" unit="mm/h" value={Number(weather.rain_rate_mm_h ?? 0)} min={0} max={150} onChange={(v) => setGrid("weather", { ...weather, rain_rate_mm_h: v })} />
      <NumberField label="部署预算" value={Number(budget.max_total_cost ?? 36)} min={0} max={1000} onChange={(v) => onChange({ ...scenario, optimization: { ...optimization, budget: { ...budget, max_total_cost: v } }, services: { ...services, cost: { ...(services.cost as object ?? {}), max_budget: v } } })} />
      <NumberField label="覆盖目标" unit="%" value={Number(communication.min_coverage_percent ?? 90)} min={0} max={100} onChange={(v) => onChange({ ...scenario, services: { ...services, communication: { ...communication, min_coverage_percent: v } } })} />
      <NumberField label="边缘速率目标" unit="Mbps" value={Number(communication.min_rate_mbps ?? 10)} min={0} max={1000} onChange={(v) => onChange({ ...scenario, services: { ...services, communication: { ...communication, min_rate_mbps: v } } })} />
      <NumberField label="定位上限" unit="m" value={Number(localization.max_peb_m ?? 5)} min={0.1} max={1000} step={0.5} onChange={(v) => onChange({ ...scenario, services: { ...services, localization: { ...localization, max_peb_m: v } } })} />
      <label className="field-label">地面环境<select aria-label="地面环境" value={String(grid.channel_scenario ?? "uma")} onChange={(event) => setGrid("channel_scenario", event.target.value)}><option value="uma">城市宏站 UMa</option><option value="rma">乡村宏站 RMa</option></select></label>
    </div>
  </div>;
}

export function NumberField(props: { label: string; unit?: string; value: number; min: number; max: number; step?: number; onChange: (value: number) => void }) {
  return <label className="field-label">{props.label}<div className="number-field"><input type="number" aria-label={props.label} value={props.value} min={props.min} max={props.max} step={props.step ?? 1} onChange={(event) => {
    const value = event.target.valueAsNumber;
    if (Number.isFinite(value)) props.onChange(Math.max(props.min, Math.min(props.max, value)));
  }} />{props.unit && <span>{props.unit}</span>}</div></label>;
}
