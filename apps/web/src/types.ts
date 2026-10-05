export type NodeType =
  | "satellite_leo"
  | "satellite_geo"
  | "haps"
  | "uav_relay"
  | "ground_bs"
  | "ground_station"
  | "ris"
  | "mis"
  | "ma_array";

export type MetricKey = "coverage" | "rate" | "localization_peb" | "sensing" | "sla_violation" | "risk";
export type ModelProfile = "closed_form_v0" | "standards_l1" | "multi_fidelity_l2_adapter";
export type OptimizerSolver = "greedy_fast" | "exhaustive_pareto" | "nsga2_pareto" | "robust_greedy";
export type ResourceMethod = "max_sinr" | "weighted_greedy" | "proportional_fair" | "ucb_bandit" | "wmmse";

export interface Position {
  lat: number;
  lon: number;
  alt_m: number;
}

export interface NodeItem {
  id: string;
  type: NodeType;
  position: Position;
  radio?: Record<string, number | string | boolean | null>;
  reconfigurable?: Record<string, number | string | boolean | null>;
  mobility?: Record<string, number | string | boolean | null>;
  cost?: number;
  enabled?: boolean;
}

export interface ScenarioShape {
  id: string;
  name: string;
  description?: string;
  region: {
    polygon: [number, number][];
    id?: string;
    name?: string;
    crs?: string;
  };
  fixed_nodes: NodeItem[];
  candidate_nodes: NodeItem[];
  grid?: Record<string, unknown>;
  spectrum?: Record<string, unknown>;
  services?: Record<string, unknown>;
  optimization?: Record<string, unknown>;
  deployment?: { selected_candidate_ids?: string[] };
}

export interface MetricCell {
  cell_id: string;
  lat: number;
  lon: number;
  value: number;
  properties: {
    sinr_db?: number;
    rate_mbps?: number;
    peb_m?: number;
    sensing_score?: number;
    demand_weight?: number;
    best_node?: string;
    channel_model?: string;
    path_loss_db?: number;
    extra_loss_db?: number;
    helper_gain_db?: number;
    shadow_loss_db?: number;
    los_probability?: number;
    elevation_deg?: number;
    rain_loss_db?: number;
    gaseous_loss_db?: number;
    sla_violation?: number;
    risk_score?: number;
  };
}

export interface MetricLayer {
  metric_name: string;
  unit: string;
  cells: MetricCell[];
  summary: Record<string, any>;
}

export interface SimulationRun {
  run_id?: string;
  scenario_id?: string;
  summary: Record<string, any>;
  layers: Record<MetricKey, MetricLayer>;
  selected_candidate_ids: string[];
  model_profile?: ModelProfile | string;
  fidelity_level?: number;
  assumptions?: string[];
}

export interface Recommendation {
  node_id: string;
  node_type: NodeType;
  reason: string;
  expected_gain: Record<string, number>;
}

export interface OptimizationRun {
  run_id?: string;
  selected_candidate_ids: string[];
  recommendations: Recommendation[];
  baseline_run: SimulationRun;
  optimized_run: SimulationRun;
  summary: {
    baseline: Record<string, number>;
    optimized: Record<string, number>;
    delta: Record<string, number>;
    solver?: string;
    evaluated_candidates?: number;
    pareto_front?: Array<Record<string, unknown>>;
    robust_evaluation?: RobustEvaluation;
    optimization_status?: string;
    constraint_status?: Array<Record<string, unknown>>;
    infeasibility_explanation?: Array<Record<string, unknown>>;
    marginal_gain_trace?: Array<Record<string, unknown>>;
  };
}

export interface DemoPayload {
  scenario: ScenarioShape;
  baseline: SimulationRun;
  optimization: OptimizationRun;
  platform?: PlatformCatalog;
}

export interface ResourceFlow {
  cell_id: string;
  lat: number;
  lon: number;
  serving_node: string;
  serving_type: NodeType;
  demand_weight: number;
  bandwidth_mhz: number;
  power_dbm: number;
  sinr_db: number;
  rate_mbps: number;
}

export interface ResourceTransmitter {
  node_id: string;
  node_type: NodeType;
  allocated_power_mw: number;
  max_power_mw: number;
  utilization: number;
  scheduled_flows: number;
}

export interface ResourcePlan {
  run_id: string;
  scenario_id: string;
  method: string;
  selected_candidate_ids: string[];
  summary: {
    scheduled_flows: number;
    active_transmitters: number;
    sum_rate_mbps: number;
    weighted_sum_rate: number;
    p5_flow_rate_mbps: number;
    jain_fairness: number;
    avg_power_utilization: number;
    access_backhaul?: {
      access_sum_rate_mbps: number;
      backhaul_capacity_mbps: number;
      end_to_end_sum_rate_mbps: number;
      backhaul_bottleneck: boolean;
      utilization: number;
      diagnosis?: string;
    };
  };
  flows: ResourceFlow[];
  transmitters: ResourceTransmitter[];
  iterations: Array<Record<string, number>>;
  benchmarks: Record<string, Record<string, number>>;
  references: Array<{ name: string; url: string; note: string }>;
  assumptions: string[];
}

export interface PlatformCatalog {
  positioning: string;
  use_cases: Array<Record<string, unknown>>;
  problem_templates: Array<Record<string, unknown>>;
  model_profiles: Array<Record<string, unknown>>;
  algorithm_families: Array<Record<string, unknown>>;
  algorithm_catalog?: AlgorithmCatalog;
  hardware_catalog: Array<Record<string, unknown>>;
  standards: Array<Record<string, unknown>>;
  plugins: Record<string, Array<Record<string, unknown>>>;
  artifact_schema: Record<string, string[]>;
  report_templates: Array<Record<string, unknown>>;
  project_system: Record<string, unknown>;
  delivery: Record<string, unknown>;
  scenario_model_algorithm_matrix: Array<Record<string, string>>;
}

export interface AlgorithmDescriptor {
  id: string;
  name: string;
  category: "deployment" | "resource" | "uncertainty" | "fidelity" | string;
  category_name: string;
  engine: "native" | "adapter" | string;
  status: string;
  maturity: string;
  runtime_class: string;
  description: string;
  objectives: string[];
  parameters: Record<string, unknown>;
  reference: { label: string; url: string };
}

export interface AlgorithmCatalog {
  version: string;
  algorithms: AlgorithmDescriptor[];
  families: Array<Record<string, unknown>>;
  default_selections: Record<string, string>;
}

export interface RobustEvaluation {
  method: string;
  samples: number;
  seed: number;
  model_profile: string;
  selected_candidate_ids: string[];
  percentiles: Record<string, Record<string, number>>;
  risk: {
    sla_violation_probability: number;
    objective_cvar_10: number;
    stability_score: number;
  };
  samples_preview: Array<Record<string, unknown>>;
}

export interface BenchmarkSuite {
  suite_id: string;
  model_profile: string;
  rows: Array<Record<string, unknown>>;
  ablation_axes: string[];
}

export interface SensitivityResult {
  method: string;
  baseline_objective: number;
  items: Array<Record<string, unknown>>;
}

export interface IntentPlan {
  intent: Record<string, unknown>;
  tool_chain: Array<Record<string, unknown>>;
  must_bind_run_id: boolean;
}

export interface WorkspaceProject {
  id: string;
  name: string;
  description?: string;
  status?: string;
  scenario_count?: number;
  run_count?: number;
  job_count?: number;
  metadata?: Record<string, unknown>;
}

export interface WorkspaceJob {
  job_id: string;
  job_type: string;
  status: string;
  progress: number;
  message: string;
  created_at?: string;
  started_at?: string;
  finished_at?: string;
  run_id?: string;
  report_id?: string;
}

export interface WorkspaceReport {
  id?: string;
  report_id?: string;
  title: string;
  template: string;
  run_id?: string;
  scenario_id?: string;
  created_at?: string;
  artifact_path?: string;
}

export interface WorkspaceSnapshot {
  active_project?: WorkspaceProject;
  active_scenario?: Record<string, unknown>;
  active_scenario_version?: Record<string, unknown>;
  projects: WorkspaceProject[];
  scenarios: Array<Record<string, unknown>>;
  runs: Array<Record<string, any>>;
  jobs: WorkspaceJob[];
  reports: WorkspaceReport[];
  model_profiles: Array<Record<string, unknown>>;
  health: Record<string, unknown>;
}
