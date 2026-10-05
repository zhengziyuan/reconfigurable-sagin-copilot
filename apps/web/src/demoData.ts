import type { DemoPayload, MetricCell, MetricKey, MetricLayer, NodeItem, PlatformCatalog, ScenarioShape, SimulationRun } from "./types";

const polygon: [number, number][] = [
  [120.1200, 30.2500],
  [120.1440, 30.2520],
  [120.1525, 30.2660],
  [120.1460, 30.2810],
  [120.1215, 30.2790],
  [120.1100, 30.2660],
];

const fixedNodes: NodeItem[] = [
  { id: "bs_north", type: "ground_bs", position: { lat: 30.2770, lon: 120.1260, alt_m: 35 } },
  { id: "gs_south", type: "ground_station", position: { lat: 30.2550, lon: 120.1350, alt_m: 18 } },
  { id: "leo_pass_01", type: "satellite_leo", position: { lat: 30.2900, lon: 120.1600, alt_m: 600000 } },
];

const candidateNodes: NodeItem[] = [
  { id: "ris_facade_east", type: "ris", position: { lat: 30.2650, lon: 120.1470, alt_m: 35 }, cost: 8 },
  { id: "ris_facade_south", type: "ris", position: { lat: 30.2580, lon: 120.1320, alt_m: 28 }, cost: 6 },
  { id: "mis_rooftop_center", type: "mis", position: { lat: 30.2665, lon: 120.1345, alt_m: 42 }, cost: 10 },
  { id: "uav_relay_hotspot", type: "uav_relay", position: { lat: 30.2645, lon: 120.1400, alt_m: 150 }, cost: 15 },
  { id: "uav_relay_west", type: "uav_relay", position: { lat: 30.2675, lon: 120.1195, alt_m: 130 }, cost: 13 },
  { id: "ma_array_south", type: "ma_array", position: { lat: 30.2570, lon: 120.1435, alt_m: 12 }, cost: 9 },
];

const scenario: ScenarioShape = {
  id: "demo_low_altitude_emergency",
  name: "低空应急空天地协同示范",
  description: "面向低空园区、应急保障和通感一体化的可重构 SAGIN 规划场景。",
  region: { polygon },
  fixed_nodes: fixedNodes,
  candidate_nodes: candidateNodes,
  grid: {
    nx: 20,
    ny: 16,
    demand_hotspots: [{ id: "command_center", center: [30.265, 120.142], weight: 1.8 }],
    shadow_zones: [{ id: "southern_blockage", center: [30.2585, 120.133], lat: 30.2585, lon: 120.133, radius_m: 760, loss_db: 24 }],
  },
  spectrum: { carrier_frequency_hz: 28e9, bandwidth_hz: 100e6, noise_figure_db: 7 },
  services: {
    communication: { min_rate_mbps: 10, min_coverage_percent: 90 },
    localization: { max_peb_m: 5 },
    sensing: { min_score: 0.55 },
    cost: { max_budget: 36 },
  },
  optimization: { solver: "greedy_fast", budget: { max_total_cost: 36, max_ris: 2, max_mis: 1, max_uav: 1, max_ma: 1 } },
};

export function createFallbackPayload(): DemoPayload {
  const baseline = createRun(false);
  const optimized = createRun(true);
  return {
    scenario,
    baseline,
    platform: createFallbackPlatform(),
    optimization: {
      selected_candidate_ids: ["uav_relay_hotspot", "ris_facade_south", "ma_array_south"],
      recommendations: [
        {
          node_id: "uav_relay_hotspot",
          node_type: "uav_relay",
          reason: "在热点上方放置无人机中继，缩短空地链路并改善定位几何。",
          expected_gain: { coverage_percent: 8.2, avg_rate_mbps: 16.4, avg_peb_m: 2.1, avg_sensing_score: 0.08 },
        },
        {
          node_id: "ris_facade_south",
          node_type: "ris",
          reason: "将 RIS 指向南侧遮挡区，增强非视距覆盖与边缘速率。",
          expected_gain: { coverage_percent: 5.5, avg_rate_mbps: 9.1, avg_peb_m: 1.1, avg_sensing_score: 0.03 },
        },
        {
          node_id: "ma_array_south",
          node_type: "ma_array",
          reason: "启用移动天线阵列的局部孔径增益，稳定边缘速率和感知单元。",
          expected_gain: { coverage_percent: 2.8, avg_rate_mbps: 6.5, avg_peb_m: 0.6, avg_sensing_score: 0.05 },
        },
      ],
      baseline_run: baseline,
      optimized_run: optimized,
      summary: {
        baseline: baseline.summary as Record<string, number>,
        optimized: optimized.summary as Record<string, number>,
        delta: {
          coverage_percent: 13.7,
          avg_rate_mbps: 22.9,
          p5_rate_mbps: 8.4,
          avg_peb_m: -3.8,
          avg_sensing_score: 0.16,
          selected_cost: 30,
          objective_score: 0.18,
        },
        solver: "greedy_fast",
        evaluated_candidates: 6,
        optimization_status: "feasible",
        constraint_status: [
          { metric: "coverage_percent", label: "覆盖率", value: 91.4, target: 90, operator: ">=", satisfied: true, margin: 1.4 },
          { metric: "p5_rate_mbps", label: "边缘速率", value: 18.1, target: 10, operator: ">=", satisfied: true, margin: 8.1 },
          { metric: "selected_cost", label: "部署成本", value: 30, target: 36, operator: "<=", satisfied: true, margin: 6 },
        ],
        marginal_gain_trace: [
          { step: 1, node_id: "uav_relay_hotspot", objective_before: 0.632, objective_after: 0.741 },
          { step: 2, node_id: "ris_facade_south", objective_before: 0.741, objective_after: 0.786 },
          { step: 3, node_id: "ma_array_south", objective_before: 0.786, objective_after: 0.812 },
        ],
      },
    },
  };
}

function createRun(optimized: boolean): SimulationRun {
  const metricKeys: MetricKey[] = ["coverage", "rate", "localization_peb", "sensing", "sla_violation", "risk"];
  const layers = Object.fromEntries(metricKeys.map((metric) => [metric, createLayer(metric, optimized)])) as Record<MetricKey, MetricLayer>;
  const summary = optimized
    ? {
        coverage_percent: 91.4,
        avg_rate_mbps: 72.8,
        p5_rate_mbps: 18.1,
        avg_peb_m: 4.3,
        p95_peb_m: 9.6,
        avg_sensing_score: 0.74,
        sla_violation_percent: 12.4,
        risk_score: 0.18,
        selected_cost: 30,
        objective_score: 0.812,
        blind_cell_count: 8,
        grid_cell_count: layers.coverage.cells.length,
      }
    : {
        coverage_percent: 77.7,
        avg_rate_mbps: 49.9,
        p5_rate_mbps: 9.7,
        avg_peb_m: 8.1,
        p95_peb_m: 17.8,
        avg_sensing_score: 0.58,
        sla_violation_percent: 35.2,
        risk_score: 0.41,
        selected_cost: 0,
        objective_score: 0.632,
        blind_cell_count: 28,
        grid_cell_count: layers.coverage.cells.length,
      };
  return {
    run_id: optimized ? "fallback_optimized" : "fallback_baseline",
    scenario_id: scenario.id,
    selected_candidate_ids: optimized ? ["uav_relay_hotspot", "ris_facade_south", "ma_array_south"] : [],
    model_profile: "closed_form_v0",
    fidelity_level: 0,
    assumptions: ["L0 快速闭式模型。", "该数据用于 API 未启动时的离线兜底展示。"],
    layers,
    summary,
  };
}

function createLayer(metric: MetricKey, optimized: boolean): MetricLayer {
  const cells = createCells(metric, optimized);
  return {
    metric_name: metric,
    unit: metric === "rate" ? "Mbps" : metric === "localization_peb" ? "m" : metric === "coverage" || metric === "sla_violation" ? "0/1" : "score",
    cells,
    summary: {},
  };
}

function createCells(metric: MetricKey, optimized: boolean): MetricCell[] {
  const cells: MetricCell[] = [];
  const [minLon, maxLon] = [120.110, 120.153];
  const [minLat, maxLat] = [30.250, 30.281];
  for (let row = 0; row < 14; row += 1) {
    for (let col = 0; col < 18; col += 1) {
      const lat = minLat + ((row + 0.5) / 14) * (maxLat - minLat);
      const lon = minLon + ((col + 0.5 + (row % 2 ? 0.22 : 0)) / 18) * (maxLon - minLon);
      if (!inside(lon, lat, polygon)) continue;
      const eastHotspot = gaussian(lat, lon, 30.265, 120.145, 0.0065);
      const southBlind = gaussian(lat, lon, 30.258, 120.131, 0.006);
      const westWeak = gaussian(lat, lon, 30.267, 120.118, 0.007);
      const boost = optimized ? 0.18 + 0.28 * southBlind + 0.18 * eastHotspot : 0;
      const rate = 28 + 55 * eastHotspot + 18 * westWeak - 22 * southBlind + (optimized ? 30 * boost : 0);
      const peb = 13 - 6 * eastHotspot + 7 * southBlind - (optimized ? 7 * boost : 0);
      const sensing = 0.38 + 0.34 * eastHotspot + 0.18 * westWeak + (optimized ? 0.22 * boost : 0);
      const coverage = rate > (optimized ? 12 : 16) ? 1 : 0;
      const slaViolation = coverage < 0.5 || rate < 10 || peb > 5 || sensing < 0.55 ? 1 : 0;
      const risk = Math.min(1, 0.4 * slaViolation + 0.25 * Math.max(0, (10 - rate) / 10) + 0.2 * Math.max(0, (peb - 5) / 15) + 0.15 * eastHotspot);
      const value = metric === "coverage" ? coverage : metric === "rate" ? rate : metric === "localization_peb" ? peb : metric === "sensing" ? sensing : metric === "sla_violation" ? slaViolation : risk;
      cells.push({
        cell_id: `demo_${row}_${col}`,
        lat,
        lon,
        value: Number(value.toFixed(4)),
        properties: {
          sinr_db: Number((rate / 7 - 4).toFixed(2)),
          rate_mbps: Number(rate.toFixed(2)),
          peb_m: Number(Math.max(1.6, peb).toFixed(2)),
          sensing_score: Number(Math.min(0.96, sensing).toFixed(3)),
          sla_violation: Number(slaViolation.toFixed(3)),
          risk_score: Number(risk.toFixed(3)),
          demand_weight: Number((1 + 1.4 * eastHotspot).toFixed(2)),
          best_node: eastHotspot > 0.45 ? "bs_north" : "gs_south",
        },
      });
    }
  }
  return cells;
}

function createFallbackPlatform(): PlatformCatalog {
  return {
    positioning: "面向空天地可重构网络的规划智能体原型，支持多业务性能场、多保真模型、多目标优化、资源管控和中文报告输出。",
    use_cases: [
      { id: "low_altitude_isac_park", name: "低空园区通信-定位-感知", model: "standards_l1", algorithm: "exhaustive_pareto" },
      { id: "emergency_resilience_sagin", name: "应急灾害空天地补盲", model: "standards_l1", algorithm: "robust_greedy" },
      { id: "industrial_private_network_enhancement", name: "工业专网增强", model: "SLA + cost + backhaul", algorithm: "cost-benefit planning" },
      { id: "remote_ntn_coverage", name: "偏远地区 NTN 潜在覆盖", model: "NTN + terrain", algorithm: "multi-fidelity screening" },
      { id: "urban_mmwave_ris_facade", name: "城市毫米波 RIS/MIS 立面网络", model: "blockage + facade", algorithm: "surrogate_pareto" },
      { id: "sagin_isac_monitoring", name: "空天地 ISAC 监测", model: "CRB + detection", algorithm: "joint scheduling" },
      { id: "ai_edge_sagin", name: "空天地 AI 边缘计算", model: "comm + compute", algorithm: "offloading allocation" },
      { id: "array_as_a_service", name: "可重构阵列即服务", model: "tenant SLA", algorithm: "revenue-aware scheduling" },
    ],
    problem_templates: [
      {
        id: "robust_isac_reconfigurable_planning",
        name: "可重构 SAGIN 鲁棒通感部署规划",
        objectives: { maximize: ["coverage", "edge_rate", "sensing"], minimize: ["p95_peb", "cost", "risk"] },
      },
    ],
    model_profiles: [
      { id: "closed_form_v0", name: "L0 快速闭式模型", status: "stable_demo", fidelity_level: 0 },
      { id: "standards_l1", name: "L1 3GPP/ITU 可追溯模型", status: "partial_traceable", fidelity_level: 1 },
      { id: "multi_fidelity_l2_adapter", name: "L2 高保真 ROI 适配器", status: "adapter_ready", fidelity_level: 2 },
    ],
    algorithm_families: [
      { family: "候选点生成", algorithms: ["geometry_anchor", "hotspot_shadow", "sensing_coverage"] },
      { family: "部署优化", algorithms: ["greedy_fast", "exhaustive_pareto", "robust_greedy"] },
      { family: "资源管控", algorithms: ["max_sinr", "proportional_bandwidth", "wmmse_power"] },
      { family: "多保真闭环", algorithms: ["l0_screening", "l1_eval", "l2_roi_export"] },
    ],
    hardware_catalog: [
      { id: "ris_2bit_facade_24x24", type: "ris", elements: 576 },
      { id: "mis_3layer_rooftop", type: "mis", layers: 3 },
      { id: "ma_8elem_mobile_array", type: "ma_array", antennas: 8 },
    ],
    standards: [
      { id: "3gpp_tr38901", name: "3GPP TR 38.901" },
      { id: "3gpp_tr38811", name: "3GPP TR 38.811" },
      { id: "itu_p676", name: "ITU-R P.676" },
    ],
    plugins: { channel_models: [], optimizers: [], hardware: [], reports: [] },
    artifact_schema: {
      run: ["manifest.json", "run.json", "summary.json", "quality.json"],
      evidence: ["scenario_snapshot.json", "model_profile_snapshot.json", "artifacts.json"],
    },
    report_templates: [
      { id: "research", name: "科研论文实验报告" },
      { id: "enterprise", name: "横向交付报告" },
      { id: "grant", name: "基金申请支撑报告" },
    ],
    project_system: {
      hierarchy: ["project", "scenario", "scenario_version", "run", "report"],
      audit: "每次运行写入 manifest、模型快照、质量检查和证据索引。",
    },
    delivery: {
      local: "SQLite + local artifacts",
      production: "Postgres + MinIO/S3 + Celery",
    },
    scenario_model_algorithm_matrix: [
      { scenario: "低空园区", model: "standards_l1", algorithm: "robust_greedy" },
      { scenario: "应急补盲", model: "closed_form_v0", algorithm: "greedy_fast" },
      { scenario: "论文基准", model: "multi_fidelity_l2_adapter", algorithm: "exhaustive_pareto" },
    ],
  };
}

function gaussian(lat: number, lon: number, cLat: number, cLon: number, sigma: number) {
  const dLat = lat - cLat;
  const dLon = lon - cLon;
  return Math.exp(-(dLat * dLat + dLon * dLon) / (2 * sigma * sigma));
}

function inside(x: number, y: number, poly: [number, number][]) {
  let c = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i, i += 1) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;
    if (intersect) c = !c;
  }
  return c;
}
