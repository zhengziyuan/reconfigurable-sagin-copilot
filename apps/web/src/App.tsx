import {
  Activity,
  Antenna,
  BarChart3,
  Bot,
  ChevronRight,
  Cpu,
  Download,
  FileText,
  Layers3,
  LocateFixed,
  Map,
  MousePointer2,
  Orbit,
  Plane,
  Play,
  Plus,
  RadioTower,
  RefreshCcw,
  Search,
  Satellite,
  Settings,
  SlidersHorizontal,
  Sparkles,
  TriangleAlert,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { MouseEvent, PointerEvent } from "react";
import { createFallbackPayload } from "./demoData";
import type { BasemapKind } from "./gis/GisMap";
import { apiRequest, downloadText, errorMessage } from "./lib/api";
import { planningConstraints } from "./lib/planning";
import { useScenarioEditor, type EditorSnapshot } from "./hooks/useScenarioEditor";
import { ProjectToolbar, ScenarioParameters, NumberField } from "./components/PlanningControls";
import { ResultsAnalytics } from "./components/ResultsAnalytics";
import { ProjectManager } from "./components/ProjectManager";
import { metricScales } from "./gis/metricScale";
const GisMap = lazy(() => import("./gis/GisMap").then((module) => ({ default: module.GisMap })));
import type {
  AlgorithmDescriptor,
  BenchmarkSuite,
  DemoPayload,
  IntentPlan,
  MetricCell,
  MetricKey,
  ModelProfile,
  NodeItem,
  NodeType,
  OptimizerSolver,
  PlatformCatalog,
  ResourcePlan,
  ResourceMethod,
  RobustEvaluation,
  SensitivityResult,
  WorkspaceSnapshot,
} from "./types";

const metricLabels: Record<MetricKey, string> = {
  coverage: "覆盖",
  rate: "速率",
  localization_peb: "PEB",
  sensing: "感知",
  sla_violation: "SLA风险",
  risk: "综合风险",
};

const nodeLabels: Record<NodeType, string> = {
  satellite_leo: "卫星",
  satellite_geo: "GEO",
  haps: "HAPS",
  uav_relay: "无人机",
  ground_bs: "基站",
  ground_station: "地面站",
  ris: "RIS",
  mis: "MIS",
  ma_array: "MA",
};

type PlacementMode = NodeType | null;
type ActiveView = "workspace" | "scenario" | "usecases" | "models" | "algorithms" | "benchmarks" | "results" | "reports";
type RailTool = "layers" | "stations" | "aerial" | "surfaces" | "results" | "reports";
type ViewMode = "2d" | "3d";

const editableTypes = new Set<NodeType>(["ris", "mis", "ma_array", "uav_relay", "haps"]);

const placementLabels: Array<{ type: Exclude<PlacementMode, null>; label: string }> = [
  { type: "ris", label: "RIS" },
  { type: "mis", label: "MIS" },
  { type: "ma_array", label: "MA" },
  { type: "uav_relay", label: "无人机" },
];

const modelProfileLabels: Record<ModelProfile, string> = {
  closed_form_v0: "L0 快速闭式",
  standards_l1: "L1 3GPP/ITU",
  multi_fidelity_l2_adapter: "L2 高保真ROI",
};

const solverLabels: Record<OptimizerSolver, string> = {
  greedy_fast: "快速贪心",
  exhaustive_pareto: "精确Pareto",
  nsga2_pareto: "NSGA-II",
  robust_greedy: "贪心与鲁棒复核",
};

const resourceMethodLabels: Record<ResourceMethod, string> = {
  max_sinr: "Max-SINR",
  weighted_greedy: "需求加权",
  proportional_fair: "比例公平",
  ucb_bandit: "UCB 在线",
  wmmse: "WMMSE",
};

function App() {
  const initialPayload = useMemo(() => createFallbackPayload(), []);
  const [payload, setPayload] = useState<DemoPayload>(initialPayload);
  const [platform, setPlatform] = useState<PlatformCatalog>(initialPayload.platform as PlatformCatalog);
  const [workspaceSnapshot, setWorkspaceSnapshot] = useState<WorkspaceSnapshot>(() => createFallbackWorkspace(initialPayload));
  const [candidateDrafts, setCandidateDrafts] = useState<Array<Record<string, unknown>>>([]);
  const editor = useScenarioEditor({ scenario: initialPayload.scenario, selectedCandidateIds: initialPayload.optimization.selected_candidate_ids });
  const { scenario, setScenario, selectedCandidateIds, setSelectedCandidateIds } = editor;
  const [savedState, setSavedState] = useState(() => JSON.stringify({ scenario: initialPayload.scenario, selectedCandidateIds: initialPayload.optimization.selected_candidate_ids }));
  const [savedVersionId, setSavedVersionId] = useState<string | undefined>();
  const [draft, setDraft] = useState<EditorSnapshot | null>(() => {
    try { return JSON.parse(localStorage.getItem("rsagin-draft-v08") ?? "null"); } catch { return null; }
  });
  const [versions, setVersions] = useState<Array<Record<string, any>> | null>(null);
  const [projectsOpen, setProjectsOpen] = useState(false);
  const [resourceSettings, setResourceSettings] = useState({ max_flows: 24, iterations: 24 });
  const [reportTemplate, setReportTemplate] = useState("enterprise");
  const [reportMarkdown, setReportMarkdown] = useState<string | null>(null);
  const contextRef = useRef({ projectId: "", scenarioId: initialPayload.scenario.id });
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedCell, setSelectedCell] = useState<MetricCell | null>(null);
  const [placementMode, setPlacementMode] = useState<PlacementMode>(null);
  const [metric, setMetric] = useState<MetricKey>("rate");
  const [modelProfile, setModelProfile] = useState<ModelProfile>("closed_form_v0");
  const [solver, setSolver] = useState<OptimizerSolver>("greedy_fast");
  const [resourceMethod, setResourceMethod] = useState<ResourceMethod>("wmmse");
  const [viewMode, setViewMode] = useState<ViewMode>("2d");
  const [basemap, setBasemap] = useState<BasemapKind>("street");
  const [activeView, setActiveView] = useState<ActiveView>("workspace");
  const [activeRailTool, setActiveRailTool] = useState<RailTool>("stations");
  const [resourcePlan, setResourcePlan] = useState<ResourcePlan | null>(null);
  const [robustEvaluation, setRobustEvaluation] = useState<RobustEvaluation | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityResult | null>(null);
  const [benchmark, setBenchmark] = useState<BenchmarkSuite | null>(null);
  const [intentPlan, setIntentPlan] = useState<IntentPlan | null>(null);
  const [optimized, setOptimized] = useState(true);
  const [apiStatus, setApiStatus] = useState<"fallback" | "live" | "loading">("loading");
  const [isBusy, setIsBusy] = useState(false);
  const [isDirty, setIsDirty] = useState(false);
  const [message, setMessage] = useState("拖拽节点或放置新资产后，运行仿真或优化。");
  const userActionRef = useRef(false);

  const refreshWorkspace = useCallback(async () => {
    try {
      const params = new URLSearchParams({ scenario_id: contextRef.current.scenarioId });
      if (contextRef.current.projectId) params.set("project_id", contextRef.current.projectId);
      const response = await apiRequest(`/api/workspace?${params}`);
      const data: WorkspaceSnapshot = await response.json();
      setWorkspaceSnapshot(data);
    } catch {
      setWorkspaceSnapshot((current) => current);
    }
  }, []);

  useEffect(() => {
    let disposed = false;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 20000);
    const sceneId = localStorage.getItem("rsagin-active-scenario");
    apiRequest(`/api/demo${sceneId ? `?scenario_id=${encodeURIComponent(sceneId)}` : ""}`, { signal: controller.signal })
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("API unavailable"))))
      .then((data: DemoPayload & { workspace?: WorkspaceSnapshot }) => {
        if (disposed) return;
        setPayload(data);
        if (data.platform) setPlatform(data.platform);
        if (data.workspace) setWorkspaceSnapshot(data.workspace);
        const ids = data.scenario.deployment?.selected_candidate_ids ?? data.optimization.selected_candidate_ids;
        if (!userActionRef.current) editor.reset({ scenario: data.scenario, selectedCandidateIds: ids });
        setSavedState(JSON.stringify({ scenario: data.scenario, selectedCandidateIds: ids }));
        setSavedVersionId(String(data.workspace?.active_scenario_version?.id ?? "") || undefined);
        contextRef.current = { projectId: String(data.workspace?.active_project?.id ?? ""), scenarioId: data.scenario.id };
        setApiStatus("live");
        if (!userActionRef.current) {
          setMessage("实时 API 已连接，画布编辑会由 Python 引擎重新计算。");
        }
      })
      .catch(() => {
        if (disposed) return;
        setApiStatus("fallback");
        setMessage("API 暂不可用，后端启动前仍可使用本地兜底数据编辑。");
      })
      .finally(() => window.clearTimeout(timeout));
    return () => {
      disposed = true;
      controller.abort();
      window.clearTimeout(timeout);
    };
  }, []);

  const snapshot: EditorSnapshot = { scenario, selectedCandidateIds };
  const documentDirty = !!savedState && JSON.stringify(snapshot) !== savedState;
  useEffect(() => {
    if (!documentDirty) return;
    const timer = window.setTimeout(() => {
      try { localStorage.setItem("rsagin-draft-v08", JSON.stringify({ scenario, selectedCandidateIds })); } catch { /* Storage can be unavailable in private mode. */ }
    }, 400);
    return () => window.clearTimeout(timer);
  }, [scenario, selectedCandidateIds, documentDirty]);

  const markEdited = useCallback(() => {
    userActionRef.current = true;
    setIsDirty(true);
    setResourcePlan(null);
    setSelectedCell(null);
    setMessage("场景已修改，运行仿真可刷新结果；保存版本可保留本次编辑。");
  }, []);

  const changeScenario = useCallback((next: DemoPayload["scenario"]) => { setScenario(next); markEdited(); }, [setScenario, markEdited]);

  const loadScenario = async (id: string) => {
    setIsBusy(true);
    try {
      const response = await apiRequest(`/api/demo?scenario_id=${encodeURIComponent(id)}`);
      const data = await response.json();
      const ids = data.scenario.deployment?.selected_candidate_ids ?? data.optimization.selected_candidate_ids;
      editor.reset({ scenario: data.scenario, selectedCandidateIds: ids });
      setSavedState(JSON.stringify({ scenario: data.scenario, selectedCandidateIds: ids }));
      setPayload(data);
      setWorkspaceSnapshot(data.workspace);
      setSavedVersionId(data.workspace.active_scenario_version?.id);
      contextRef.current = { projectId: data.workspace.active_project.id, scenarioId: id };
      localStorage.setItem("rsagin-active-scenario", id);
      setIsDirty(false); setOptimized(true); setResourcePlan(null); setSelectedNodeId(null); setSelectedCell(null);
      setMessage(`已载入场景 ${data.scenario.name}。`);
    } catch (error) { setMessage(`载入失败：${errorMessage(error)}`); }
    finally { setIsBusy(false); }
  };

  const saveScenario = async () => {
    setIsBusy(true);
    try {
      const scene = { ...scenario, deployment: { selected_candidate_ids: selectedCandidateIds } };
      const existing = workspaceSnapshot.scenarios.some((item) => item.id === scene.id);
      const projectId = contextRef.current.projectId || workspaceSnapshot.active_project?.id;
      const response = await apiRequest(existing ? `/api/scenarios/${encodeURIComponent(scene.id)}/versions` : `/api/projects/${encodeURIComponent(projectId ?? "")}/scenarios`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario: scene, notes: "工作台保存" }),
      });
      const data = await response.json();
      const versionId = data.version?.id ?? data.scenario?.current_version_id;
      setSavedVersionId(versionId);
      setSavedState(JSON.stringify(snapshot));
      localStorage.setItem("rsagin-active-scenario", scene.id);
      localStorage.removeItem("rsagin-draft-v08"); setDraft(null);
      contextRef.current.scenarioId = scene.id;
      await refreshWorkspace();
      setMessage(`场景版本 ${versionId} 已保存。`);
    } catch (error) { setMessage(`保存失败：${errorMessage(error)}`); }
    finally { setIsBusy(false); }
  };

  const importScenario = async (file: File) => {
    setIsBusy(true);
    try {
      if (file.size > 2_000_000) throw new Error("场景文件不能超过 2 MB");
      const raw = JSON.parse(await file.text());
      const response = await apiRequest("/api/scenarios/validate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario: raw.scenario ?? raw }) });
      const data = await response.json();
      const ids = raw.selected_candidate_ids ?? data.scenario.deployment?.selected_candidate_ids ?? [];
      editor.update(() => ({ scenario: data.scenario, selectedCandidateIds: ids.filter((id: string) => data.scenario.candidate_nodes.some((node: NodeItem) => node.id === id)) }));
      contextRef.current.scenarioId = data.scenario.id;
      markEdited();
      setMessage(`已导入 ${data.scenario.name}，${data.grid_cells} 个有效网格；保存版本后可再次载入。`);
    } catch (error) { setMessage(`导入失败：${errorMessage(error)}`); }
    finally { setIsBusy(false); }
  };

  const openVersions = async () => {
    try {
      const response = await apiRequest(`/api/scenarios/${encodeURIComponent(scenario.id)}/versions`);
      setVersions((await response.json()).versions);
    } catch (error) { setMessage(`版本查询失败：${errorMessage(error)}`); }
  };

  useEffect(() => {
    void refreshWorkspace();
  }, [refreshWorkspace]);

  useEffect(() => {
    apiRequest("/api/platform")
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error("platform unavailable"))))
      .then((data: PlatformCatalog) => setPlatform(data))
      .catch(() => undefined);
  }, []);

  const runSimulation = useCallback(async () => {
    userActionRef.current = true;
    setIsBusy(true);
    setMessage("正在对当前编辑场景运行仿真...");
    try {
      const response = await apiRequest("/api/jobs/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario,
          selected_candidate_ids: selectedCandidateIds,
          model_profile: modelProfile,
        }),
      });
      if (!response.ok) throw new Error("simulate failed");
      const jobResponse = await response.json();
      if (jobResponse.error) throw new Error(jobResponse.error);
      const run = jobResponse.result;
      setPayload((current) => ({
        ...current,
        scenario,
        baseline: run,
        optimization: {
          ...current.optimization,
          baseline_run: run,
        },
      }));
      setResourcePlan(null);
      setOptimized(false);
      setIsDirty(false);
      setApiStatus("live");
      setActiveView("results");
      setActiveRailTool("results");
      setMessage(`仿真完成：覆盖率 ${run.summary.coverage_percent}%，平均速率 ${run.summary.avg_rate_mbps} Mbps。`);
      void refreshWorkspace();
    } catch (error) {
      setMessage(`仿真失败：${errorMessage(error)}`);
    } finally {
      setIsBusy(false);
    }
  }, [modelProfile, refreshWorkspace, scenario, selectedCandidateIds]);

  const runOptimization = useCallback(async () => {
    userActionRef.current = true;
    setIsBusy(true);
    setMessage("正在为当前场景优化部署...");
    try {
      const response = await apiRequest("/api/jobs/optimize", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario, model_profile: modelProfile, solver }),
      });
      if (!response.ok) throw new Error("optimize failed");
      const jobResponse = await response.json();
      if (jobResponse.error) throw new Error(jobResponse.error);
      const run = jobResponse.result;
      setPayload((current) => ({
        ...current,
        scenario,
        baseline: run.baseline_run,
        optimization: run,
      }));
      setSelectedCandidateIds(run.selected_candidate_ids);
      setResourcePlan(null);
      setOptimized(true);
      setIsDirty(false);
      setApiStatus("live");
      setActiveView("results");
      setActiveRailTool("results");
      setMessage(`优化完成（${solverLabels[solver]}）：已选择 ${run.selected_candidate_ids.length} 个候选节点。`);
      void refreshWorkspace();
    } catch (error) {
      setMessage(`优化失败：${errorMessage(error)}`);
    } finally {
      setIsBusy(false);
    }
  }, [modelProfile, refreshWorkspace, scenario, solver]);

  const runCandidateGeneration = useCallback(async () => {
    userActionRef.current = true;
    setIsBusy(true);
    setMessage("正在基于区域、热点和遮挡区生成候选站址...");
    try {
      const response = await apiRequest("/api/candidates/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario, limit: 10 }),
      });
      if (!response.ok) throw new Error("candidate generation failed");
      const data = await response.json();
      const newNodes = Array.isArray(data.candidate_nodes) ? data.candidate_nodes as NodeItem[] : [];
      setCandidateDrafts(Array.isArray(data.candidates) ? data.candidates : []);
      if (newNodes.length) {
        setScenario((current) => {
          const existing = new Set(current.candidate_nodes.map((node) => node.id));
          return {
            ...current,
            candidate_nodes: [...current.candidate_nodes, ...newNodes.filter((node) => !existing.has(node.id))],
          };
        });
      }
      setIsDirty(true);
      setActiveView("scenario");
      setMessage(`已生成 ${newNodes.length} 个自动候选节点，请运行优化评估边际收益。`);
    } catch {
      setMessage("候选点生成失败：API 暂不可用或场景缺少区域边界。");
      setCandidateDrafts([]);
    } finally {
      setIsBusy(false);
    }
  }, [scenario]);

  const runReportJob = useCallback(async () => {
    userActionRef.current = true;
    setIsBusy(true);
    setMessage("正在创建绑定当前场景的报告任务...");
    try {
      const response = await apiRequest("/api/jobs/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario, selected_candidate_ids: selectedCandidateIds, model_profile: modelProfile, template: reportTemplate }),
      });
      if (!response.ok) throw new Error("report job failed");
      const data = await response.json();
      if (data.error) throw new Error(data.error);
      setReportMarkdown(data.result?.storage?.markdown ?? null);
      await refreshWorkspace();
      setActiveView("reports");
      setActiveRailTool("reports");
      setMessage("报告任务已完成，证据与 Markdown 报告已写入本地运行目录。");
    } catch (error) {
      setMessage(`报告任务失败：${errorMessage(error)}`);
    } finally {
      setIsBusy(false);
    }
  }, [modelProfile, refreshWorkspace, scenario, selectedCandidateIds, reportTemplate]);

  const updateNodePosition = useCallback((nodeId: string, position: { lat: number; lon: number }) => {
    userActionRef.current = true;
    setScenario((current) => ({
      ...current,
      fixed_nodes: current.fixed_nodes.map((node) =>
        node.id === nodeId ? { ...node, position: { ...node.position, ...position } } : node,
      ),
      candidate_nodes: current.candidate_nodes.map((node) =>
        node.id === nodeId ? { ...node, position: { ...node.position, ...position } } : node,
      ),
    }));
    setOptimized(false);
    setIsDirty(true);
    setMessage(`节点 ${nodeId} 已移动，请运行仿真或优化以刷新结果。`);
  }, []);

  const addNodeAt = useCallback((type: Exclude<PlacementMode, null>, position: { lat: number; lon: number }) => {
    userActionRef.current = true;
    const node = createCandidateNode(type, position, scenario.candidate_nodes.length + 1);
    const fixed = ["satellite_leo", "satellite_geo", "ground_bs", "ground_station", "haps"].includes(type);
    editor.update((current) => ({
      scenario: {
        ...current.scenario,
        fixed_nodes: fixed ? [...current.scenario.fixed_nodes, node] : current.scenario.fixed_nodes,
        candidate_nodes: fixed ? current.scenario.candidate_nodes : [...current.scenario.candidate_nodes, node],
      },
      selectedCandidateIds: fixed ? current.selectedCandidateIds : [...new Set([...current.selectedCandidateIds, node.id])],
    }));
    setSelectedNodeId(node.id);
    setPlacementMode(null);
    setOptimized(false);
    setIsDirty(true);
    setMessage(`已放置 ${nodeLabels[type]} 节点 ${node.id}，请运行仿真或优化以刷新结果。`);
  }, [scenario.candidate_nodes.length]);

  const deleteSelectedNode = useCallback(() => {
    userActionRef.current = true;
    if (!selectedNodeId) return;
    editor.update((current) => ({
      scenario: {
        ...current.scenario,
        fixed_nodes: current.scenario.fixed_nodes.filter((node) => node.id !== selectedNodeId),
        candidate_nodes: current.scenario.candidate_nodes.filter((node) => node.id !== selectedNodeId),
      },
      selectedCandidateIds: current.selectedCandidateIds.filter((id) => id !== selectedNodeId),
    }));
    setSelectedNodeId(null);
    setIsDirty(true);
    setMessage("节点已删除，可撤销；请重新运行仿真刷新指标。");
  }, [selectedNodeId]);

  const toggleCandidate = useCallback((nodeId: string) => {
    userActionRef.current = true;
    setSelectedCandidateIds((current) =>
      current.includes(nodeId) ? current.filter((id) => id !== nodeId) : [...current, nodeId],
    );
    setOptimized(false);
    setIsDirty(true);
    setMessage("部署选择已变化，请运行仿真评估当前组合。");
  }, []);

  const toggleCandidateGroup = useCallback((nodeIds: string[]) => {
    userActionRef.current = true;
    if (nodeIds.length === 0) return;
    setSelectedCandidateIds((current) => {
      const currentSet = new Set(current);
      const allSelected = nodeIds.every((id) => currentSet.has(id));
      if (allSelected) {
        return current.filter((id) => !nodeIds.includes(id));
      }
      return [...new Set([...current, ...nodeIds])];
    });
    setOptimized(false);
    setIsDirty(true);
    setMessage("候选节点组已变化，请运行仿真评估当前组合。");
  }, []);

  const applyOptimizedSelection = useCallback(() => {
    userActionRef.current = true;
    setSelectedCandidateIds(payload.optimization.selected_candidate_ids);
    setResourcePlan(null);
    setOptimized(true);
    setIsDirty(false);
    setMessage("已将优化器选择的候选节点应用到画布。");
  }, [payload.optimization.selected_candidate_ids]);

  const runResourcePlan = useCallback(async (method?: ResourceMethod) => {
    const selectedMethod = method ?? resourceMethod;
    userActionRef.current = true;
    setIsBusy(true);
    setActiveView("results");
    setActiveRailTool("results");
    setMessage("正在为当前拓扑运行资源管控方案...");
    try {
      const response = await apiRequest("/api/resource-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario,
          selected_candidate_ids: selectedCandidateIds,
          method: selectedMethod,
          ...resourceSettings,
          model_profile: modelProfile,
        }),
      });
      if (!response.ok) throw new Error("resource planning failed");
      const plan: ResourcePlan = await response.json();
      setResourcePlan(plan);
      setApiStatus("live");
      setMessage(`资源管控完成：${plan.summary.scheduled_flows} 条业务流，总速率 ${plan.summary.sum_rate_mbps} Mbps。`);
      void refreshWorkspace();
    } catch (error) {
      setMessage(`资源管控失败：${errorMessage(error)}`);
    } finally {
      setIsBusy(false);
    }
  }, [refreshWorkspace, resourceMethod, scenario, selectedCandidateIds, resourceSettings, modelProfile]);

  const runRobustAnalysis = useCallback(async () => {
    userActionRef.current = true;
    setIsBusy(true);
    setActiveView("benchmarks");
    setMessage("正在运行鲁棒性、敏感性和基准评测套件...");
    try {
      const commonBody = { scenario, selected_candidate_ids: selectedCandidateIds, model_profile: modelProfile };
      const [robustResponse, sensitivityResponse, benchmarkResponse, intentResponse] = await Promise.all([
        apiRequest("/api/robust-evaluate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...commonBody, samples: 8 }),
        }),
        apiRequest("/api/sensitivity", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(commonBody),
        }),
        apiRequest("/api/benchmark", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scenario, model_profile: modelProfile === "multi_fidelity_l2_adapter" ? "standards_l1" : modelProfile }),
        }),
        apiRequest("/api/intent-plan", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ intent: "低空园区需要95%覆盖、10 Mbps边缘速率、PEB低于5 m，并生成科研和企业报告。" }),
        }),
      ]);
      setRobustEvaluation(await robustResponse.json());
      setSensitivity(await sensitivityResponse.json());
      setBenchmark(await benchmarkResponse.json());
      setIntentPlan(await intentResponse.json());
      setApiStatus("live");
      setMessage("鲁棒性、敏感性、基准评测和意图规划已生成。");
    } catch {
      setApiStatus("fallback");
      setMessage("基准评测流程失败：API 暂不可用。");
    } finally {
      setIsBusy(false);
    }
  }, [modelProfile, scenario, selectedCandidateIds]);

  const handleRailTool = useCallback((tool: RailTool) => {
    userActionRef.current = true;
    setActiveRailTool(tool);
    if (tool === "layers") {
      setActiveView("scenario");
      setMetric("coverage");
      setMessage("图层工具已启用：当前显示覆盖热力图。");
    } else if (tool === "stations") {
      const station = scenario.fixed_nodes.find((node) => node.type === "ground_station" || node.type === "ground_bs") ?? null;
      setActiveView("scenario");
      setSelectedNodeId(station?.id ?? null);
      setSelectedCell(null);
      setPlacementMode(null);
      setMessage(station ? `地面站工具已启用：已选择 ${station.id}。` : "地面站工具已启用：未发现地面站。");
    } else if (tool === "aerial") {
      setActiveView("scenario");
      setPlacementMode("uav_relay");
      setMessage("空中平台工具已启用：点击地图放置无人机中继。");
    } else if (tool === "surfaces") {
      setActiveView("scenario");
      setPlacementMode("ris");
      setMessage("可重构表面工具已启用：点击地图放置 RIS 节点。");
    } else if (tool === "results") {
      void runResourcePlan();
    } else if (tool === "reports") {
      setActiveView("reports");
      setMessage("报告视图已启用：当前仿真、优化和资源管控结果已汇总。");
    }
  }, [runResourcePlan, scenario.fixed_nodes]);

  const selectedNode = useMemo(
    () => [...scenario.fixed_nodes, ...scenario.candidate_nodes].find((node) => node.id === selectedNodeId) ?? null,
    [scenario, selectedNodeId],
  );
  const selectedIds = useMemo(() => new Set(selectedCandidateIds), [selectedCandidateIds]);
  const activeRun = optimized ? { ...payload.optimization.optimized_run, run_id: payload.optimization.run_id ?? payload.optimization.optimized_run.run_id } : payload.baseline;
  const resultStale = isDirty || activeRun.model_profile !== modelProfile;
  const activeLayer = activeRun.layers[metric];
  const allNodes = [...scenario.fixed_nodes, ...scenario.candidate_nodes];

  return (
    <main className="app-shell">
      <TopBar
        apiStatus={apiStatus}
        activeView={activeView}
        isBusy={isBusy}
        onWorkspace={() => {
          setActiveView("workspace");
          setActiveRailTool("layers");
          void refreshWorkspace();
        }}
        onScenario={() => {
          setActiveView("scenario");
          setActiveRailTool("stations");
        }}
        onSimulate={() => void runSimulation()}
        onOptimize={() => void runOptimization()}
        onUseCases={() => {
          setActiveView("usecases");
          setActiveRailTool("layers");
          setMessage("用例工作台已启用：场景族、问题模板和报告作为可复用资产组织。");
        }}
        onModels={() => {
          setActiveView("models");
          setActiveRailTool("layers");
          setMessage("模型实验室已启用：可检查保真档位、标准依据、模型假设和运行质量。");
        }}
        onAlgorithms={() => {
          setActiveView("algorithms");
          setActiveRailTool("results");
          setMessage("算法实验室已启用：可查看算法族、硬件感知规划、插件和智能体工具链。");
        }}
        onBenchmarks={() => void runRobustAnalysis()}
        onResults={() => { setActiveView("results"); setActiveRailTool("results"); }}
        onReports={() => {
          setActiveView("reports");
          setActiveRailTool("reports");
        }}
      />
      <ProjectToolbar scenario={scenario} workspace={workspaceSnapshot} dirty={documentDirty} busy={isBusy} canUndo={editor.canUndo} canRedo={editor.canRedo} hasDraft={!!draft}
        onUndo={() => { editor.undo(); markEdited(); }} onRedo={() => { editor.redo(); markEdited(); }} onSave={() => void saveScenario()}
        onExport={() => downloadText(`${scenario.id}.json`, JSON.stringify({ schema_version: "0.8", scenario, selected_candidate_ids: selectedCandidateIds, model_profile: modelProfile }, null, 2))}
        onImport={(file) => void importScenario(file)} onHistory={() => void openVersions()} onLoad={(id) => void loadScenario(id)} onProjects={() => setProjectsOpen(true)}
        onRestoreDraft={() => { if (draft) { editor.update(() => draft); markEdited(); setDraft(null); } }} />
      <div className="workspace">
        <Rail activeTool={activeRailTool} onTool={handleRailTool} />
        {activeView === "workspace" && (
          <WorkspaceHome
            workspace={workspaceSnapshot}
            payload={payload}
            platform={platform}
            candidateDrafts={candidateDrafts}
            isBusy={isBusy}
            message={message}
            onScenario={() => setActiveView("scenario")}
            onSimulate={runSimulation}
            onOptimize={runOptimization}
            onGenerateCandidates={runCandidateGeneration}
            onReport={runReportJob}
            onRefresh={refreshWorkspace}
            scenario={scenario}
            onChangeScenario={changeScenario}
            activeRun={activeRun}
            stale={resultStale}
            onExport={() => downloadText(`${scenario.id}.json`, JSON.stringify(snapshot, null, 2))}
          />
        )}
        {activeView === "scenario" && (
          <ScenarioPanel
            optimized={optimized}
            metric={metric}
            setMetric={setMetric}
            modelProfile={modelProfile}
            setModelProfile={setModelProfile}
            solver={solver}
            setSolver={setSolver}
            setOptimized={setOptimized}
            payload={payload}
            platform={platform}
            scenario={scenario}
            selectedCandidateIds={selectedCandidateIds}
            selectedNode={selectedNode}
            selectedCell={selectedCell}
            isBusy={isBusy}
            isDirty={resultStale}
            message={message}
            onRunSimulation={runSimulation}
            onRunOptimization={runOptimization}
            onToggleCandidate={toggleCandidate}
            onToggleCandidateGroup={toggleCandidateGroup}
            onDeleteSelectedNode={deleteSelectedNode}
          />
        )}
        {activeView === "usecases" && <UseCaseStudio platform={platform} message={message} />}
        {activeView === "models" && (
          <ModelLab
            payload={payload}
            run={activeRun}
            platform={platform}
            modelProfile={modelProfile}
            setModelProfile={setModelProfile}
            message={message}
          />
        )}
        {activeView === "algorithms" && (
          <AlgorithmLab
            platform={platform}
            solver={solver}
            setSolver={setSolver}
            resourceMethod={resourceMethod}
            setResourceMethod={setResourceMethod}
            intentPlan={intentPlan}
            isBusy={isBusy}
            message={message}
            onRunDeployment={runOptimization}
            onRunResource={(method) => void runResourcePlan(method)}
            scenario={scenario} onChangeScenario={changeScenario}
            resourceSettings={resourceSettings} setResourceSettings={setResourceSettings}
          />
        )}
        {activeView === "benchmarks" && (
          <BenchmarkCenter
            robustEvaluation={robustEvaluation}
            sensitivity={sensitivity}
            benchmark={benchmark}
            isBusy={isBusy}
            message={message}
            onRun={runRobustAnalysis}
          />
        )}
        {activeView === "results" && (
          <ResultsPanel
            payload={payload}
            optimized={optimized}
            resourcePlan={resourcePlan}
            isBusy={isBusy}
            message={message}
            modelProfile={modelProfile}
            solver={solver}
            resourceMethod={resourceMethod}
            setResourceMethod={setResourceMethod}
            onRunResourcePlan={(method) => void runResourcePlan(method)}
          />
        )}
        {activeView === "reports" && (
          <ReportPanel payload={payload} platform={platform} optimized={optimized} resourcePlan={resourcePlan} message={message} modelProfile={modelProfile} solver={solver}
            template={reportTemplate} setTemplate={setReportTemplate} onGenerate={() => void runReportJob()} isBusy={isBusy} markdown={reportMarkdown} />
        )}
        <DigitalTwin
          polygon={scenario.region.polygon}
          nodes={allNodes}
          selectedIds={selectedIds}
          cells={activeLayer.cells}
          metric={metric}
          setMetric={setMetric}
          modelProfile={modelProfile}
          viewMode={viewMode}
          setViewMode={setViewMode}
          basemap={basemap}
          setBasemap={setBasemap}
          optimized={optimized}
          placementMode={placementMode}
          selectedNodeId={selectedNodeId}
          selectedCell={selectedCell}
          isDirty={resultStale}
          setPlacementMode={setPlacementMode}
          onSelectNode={setSelectedNodeId}
          onSelectCell={setSelectedCell}
          onMoveNode={updateNodePosition}
          onAddNode={addNodeAt}
          onDeleteSelectedNode={deleteSelectedNode}
          onChangeNode={(updated) => { editor.update((current) => ({ ...current, scenario: { ...current.scenario, fixed_nodes: current.scenario.fixed_nodes.map((node) => node.id === updated.id ? updated : node), candidate_nodes: current.scenario.candidate_nodes.map((node) => node.id === updated.id ? updated : node) } })); markEdited(); }}
        />
        {activeView === "workspace" ? (
          <JobCenterPanel workspace={workspaceSnapshot} payload={payload} run={activeRun} scenario={scenario} stale={resultStale} onRefresh={refreshWorkspace} onReport={runReportJob} />
        ) : activeView === "results" ? (
          <ResourcePanel resourcePlan={resourcePlan} isBusy={isBusy} onRunResourcePlan={() => void runResourcePlan()} />
        ) : activeView === "reports" ? (
          <ReferencePanel resourcePlan={resourcePlan} />
        ) : (
          <CopilotPanel
            payload={payload}
            run={activeRun}
            stale={resultStale}
            selectedCandidateIds={selectedCandidateIds}
            onApplySelected={applyOptimizedSelection}
            onSelectNode={setSelectedNodeId}
          />
        )}
      </div>
      <ResultsAnalytics run={activeRun} baseline={payload.optimization.baseline_run} scenario={scenario} stale={resultStale} />
      <div className={`operation-status ${isBusy ? "running" : ""}`} role="status"><span className="operation-dot" />{message}</div>
      {projectsOpen && <ProjectManager activeProjectId={contextRef.current.projectId} scenario={scenario} selectedIds={selectedCandidateIds} onClose={() => setProjectsOpen(false)} onOpen={(id) => void loadScenario(id)} />}
      {versions && <div className="modal-backdrop" onClick={() => setVersions(null)}><section className="version-dialog" role="dialog" aria-modal="true" aria-label="场景版本历史" onClick={(event) => event.stopPropagation()}>
        <div className="panel-title-row"><h2>场景版本历史</h2><button className="icon-button subtle" aria-label="关闭版本历史" onClick={() => setVersions(null)}><X size={18} /></button></div>
        {versions.length ? versions.map((version) => <div className="version-row" key={version.id}><div><strong>版本 {version.version}</strong><span>{version.notes} · {new Date(version.created_at).toLocaleString("zh-CN")}</span><code>{String(version.manifest_hash ?? "").slice(0, 16)}</code></div><button onClick={() => { editor.update(() => ({ scenario: version.payload, selectedCandidateIds: version.payload.deployment?.selected_candidate_ids ?? [] })); markEdited(); setVersions(null); }}>恢复</button></div>) : <p>此场景尚无已保存版本。</p>}
      </section></div>}
    </main>
  );
}

function TopBar({
  apiStatus,
  activeView,
  isBusy,
  onWorkspace,
  onScenario,
  onSimulate,
  onOptimize,
  onUseCases,
  onModels,
  onAlgorithms,
  onBenchmarks,
  onResults,
  onReports,
}: {
  apiStatus: string;
  activeView: ActiveView;
  isBusy: boolean;
  onWorkspace: () => void;
  onScenario: () => void;
  onSimulate: () => void;
  onOptimize: () => void;
  onUseCases: () => void;
  onModels: () => void;
  onAlgorithms: () => void;
  onBenchmarks: () => void;
  onResults: () => void;
  onReports: () => void;
}) {
  const actionsDisabled = isBusy || apiStatus === "loading";
  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark">
          <Orbit size={25} />
        </div>
        <div>
          <strong>空天地可重构网络规划智能体</strong>
          <span>Reconfigurable SAGIN Copilot</span>
        </div>
      </div>
      <nav className="topnav">
        <button className={activeView === "workspace" ? "nav-active" : ""} onClick={onWorkspace}><Bot size={16} />工作台</button>
        <button className={activeView === "scenario" ? "nav-active" : ""} onClick={onScenario}><Map size={16} />场景</button>
        <button disabled={actionsDisabled} onClick={onSimulate}><Activity size={16} />仿真</button>
        <button disabled={actionsDisabled} onClick={onOptimize}><Zap size={16} />优化</button>
        <button className={activeView === "usecases" ? "nav-active" : ""} onClick={onUseCases}><Layers3 size={16} />用例</button>
        <button className={activeView === "models" ? "nav-active" : ""} onClick={onModels}><Settings size={16} />模型</button>
        <button className={activeView === "algorithms" ? "nav-active" : ""} onClick={onAlgorithms}><Cpu size={16} />算法</button>
        <button className={activeView === "benchmarks" ? "nav-active" : ""} disabled={actionsDisabled} onClick={onBenchmarks}><BarChart3 size={16} />基准</button>
        <button className={activeView === "results" ? "nav-active" : ""} disabled={actionsDisabled} onClick={onResults}><BarChart3 size={16} />结果</button>
        <button className={activeView === "reports" ? "nav-active" : ""} onClick={onReports}><FileText size={16} />报告</button>
      </nav>
      <div className="top-actions">
        <select className="mobile-view-select" aria-label="导航" value={activeView} onChange={(event) => {
          const actions: Record<string, () => void> = { workspace: onWorkspace, scenario: onScenario, usecases: onUseCases, models: onModels, algorithms: onAlgorithms, benchmarks: onBenchmarks, results: onResults, reports: onReports };
          actions[event.target.value]?.();
        }}>
          <option value="workspace">工作台</option><option value="scenario">场景</option><option value="usecases">用例</option><option value="models">模型</option><option value="algorithms">算法</option><option value="benchmarks">基准</option><option value="results">结果</option><option value="reports">报告</option>
        </select>
        <span className={`status-dot ${apiStatus}`}>{apiStatus === "live" ? "实时API" : apiStatus === "loading" ? "加载中" : "本地数据"}</span>
        <button className="icon-button" aria-label="模型设置" title="模型设置" onClick={onModels}><Settings size={17} /></button>
        <span className="version-tag">v0.8</span>
      </div>
    </header>
  );
}

function Rail({ activeTool, onTool }: { activeTool: RailTool; onTool: (tool: RailTool) => void }) {
  const tools: Array<{ key: RailTool; label: string; icon: typeof Layers3 }> = [
    { key: "layers", label: "图层控制", icon: Layers3 },
    { key: "stations", label: "地面站", icon: RadioTower },
    { key: "aerial", label: "放置空中平台", icon: Antenna },
    { key: "surfaces", label: "放置可重构表面", icon: Cpu },
    { key: "results", label: "资源管控结果", icon: BarChart3 },
    { key: "reports", label: "报告", icon: FileText },
  ];
  return (
    <aside className="rail" aria-label="主工具栏">
      {tools.map(({ key, label, icon: Icon }) => (
        <button key={key} className={activeTool === key ? "rail-active" : ""} aria-label={label} title={label} onClick={() => onTool(key)}>
          <Icon size={19} />
        </button>
      ))}
    </aside>
  );
}

function WorkspaceHome({
  workspace,
  payload,
  platform,
  candidateDrafts,
  isBusy,
  message,
  onScenario,
  onSimulate,
  onOptimize,
  onGenerateCandidates,
  onReport,
  onRefresh,
  scenario,
  onChangeScenario,
  activeRun,
  stale,
  onExport,
}: {
  workspace: WorkspaceSnapshot;
  payload: DemoPayload;
  platform: PlatformCatalog;
  candidateDrafts: Array<Record<string, unknown>>;
  isBusy: boolean;
  message: string;
  onScenario: () => void;
  onSimulate: () => void;
  onOptimize: () => void;
  onGenerateCandidates: () => void;
  onReport: () => void;
  onRefresh: () => Promise<void>;
  scenario: DemoPayload["scenario"];
  onChangeScenario: (scenario: DemoPayload["scenario"]) => void;
  activeRun: DemoPayload["baseline"];
  stale: boolean;
  onExport: () => void;
}) {
  const active = activeRun.summary;
  const project = workspace.active_project ?? workspace.projects[0];
  const constraints = planningConstraints(activeRun, scenario);
  const assetRows = [
    { label: "卫星", value: `${scenario.fixed_nodes.filter((node) => node.type.startsWith("satellite")).length}`, type: "satellite_leo" as NodeType },
    { label: "HAPS / 无人机", value: `${[...scenario.fixed_nodes, ...scenario.candidate_nodes].filter((node) => ["uav_relay", "haps"].includes(node.type)).length}`, type: "uav_relay" as NodeType },
    { label: "地面站", value: `${scenario.fixed_nodes.filter((node) => node.type === "ground_bs" || node.type === "ground_station").length}`, type: "ground_station" as NodeType },
    { label: "RIS", value: `${scenario.candidate_nodes.filter((node) => node.type === "ris").length}`, type: "ris" as NodeType },
    { label: "MIS", value: `${scenario.candidate_nodes.filter((node) => node.type === "mis").length}`, type: "mis" as NodeType },
    { label: "MA", value: `${scenario.candidate_nodes.filter((node) => node.type === "ma_array").length}`, type: "ma_array" as NodeType },
  ];
  return (
    <aside className="scenario-panel workspace-home">
      <div className="panel-title-row">
        <h1>规划工作台</h1>
        <button className="ghost-button" onClick={onExport}><Download size={15} />JSON</button>
      </div>
      <div className="workspace-project-card">
        <span>当前项目</span>
        <strong>{project?.name ?? "空天地可重构网络规划智能体"}</strong>
        <p>{project?.description ?? "本地生产可运行骨架，面向论文、基金、横向和创业复用。"}</p>
      </div>

      <SectionTitle>区域与边界</SectionTitle>
      <div className="setup-card">
        <div className="setup-line">
          <span>场景</span>
          <strong>{scenario.name}</strong>
        </div>
        <div className="setup-line">
          <span>区域</span>
          <strong>{scenario.region.name ?? scenario.region.id ?? "自定义区域"}</strong>
        </div>
        <div className="setup-subline">
          <span>{scenario.region.polygon.length} 个边界点</span>
          <em>EPSG:4326</em>
        </div>
      </div>

      <SectionTitle>规划参数</SectionTitle>
      <ScenarioParameters scenario={scenario} onChange={onChangeScenario} />

      <SectionTitle>网络资产</SectionTitle>
      <div className="asset-control-list">
        {assetRows.map((row) => (
          <div key={row.label} className="asset-control-row">
            <NodeGlyph type={row.type} />
            <span>{row.label}</span>
            <strong>{row.value}</strong>
            <small>个</small>
          </div>
        ))}
      </div>

      <button className="primary-action workspace-run-button" disabled={isBusy} onClick={onSimulate}>
        <Play size={16} />
        {isBusy ? "运行中..." : "运行仿真"}
      </button>

      <SectionTitle>KPI 总览</SectionTitle>
      <div className="workspace-kpi-grid">
        <MiniMetric label="覆盖" value={`${active.coverage_percent}%`} />
        <MiniMetric label="边缘速率" value={`${active.p5_rate_mbps}`} />
        <MiniMetric label="P95 PEB" value={`${active.p95_peb_m}m`} warn={Number(active.p95_peb_m) > 5} />
        <MiniMetric label="成本" value={`${active.selected_cost}`} />
      </div>

      <SectionTitle>约束状态</SectionTitle>
      <div className="constraint-list">
        {constraints.length ? constraints.slice(0, 5).map((item) => (
          <div key={item.key} className={item.satisfied ? "constraint-row ok" : "constraint-row warn"}>
            <strong>{item.label}{stale ? " · 待重算" : ""}</strong>
            <span>{Number.isFinite(item.value) ? item.value : "--"} {item.operator} {item.target}</span>
          </div>
        )) : (
          <div className="empty-state">
            <strong>等待优化解释</strong>
            <span>运行优化后将显示硬约束满足状态和不可行解释。</span>
          </div>
        )}
      </div>

      <SectionTitle>快捷任务</SectionTitle>
      <div className="quick-action-grid">
        <button disabled={isBusy} onClick={onOptimize}><Zap size={16} /><span>优化部署</span></button>
        <button disabled={isBusy} onClick={onGenerateCandidates}><Plus size={16} /><span>生成候选</span></button>
        <button disabled={isBusy} onClick={onReport}><FileText size={16} /><span>证据报告</span></button>
        <button onClick={onScenario}><Map size={16} /><span>进入场景</span></button>
      </div>

      <div className="status-note">
        <MousePointer2 size={14} />
        <span>{message}</span>
      </div>
    </aside>
  );
}

function PlanningSlider({ label, value, percent }: { label: string; value: string; percent: number }) {
  return (
    <div className="planning-slider">
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <i><b style={{ width: `${percent}%` }} /></i>
    </div>
  );
}

function JobCenterPanel({
  workspace,
  payload,
  run,
  scenario,
  stale,
  onRefresh,
  onReport,
}: {
  workspace: WorkspaceSnapshot;
  payload: DemoPayload;
  run: DemoPayload["baseline"];
  scenario: DemoPayload["scenario"];
  stale: boolean;
  onRefresh: () => Promise<void>;
  onReport: () => void;
}) {
  const [tab, setTab] = useState<"recommendations" | "evidence">("recommendations");
  const latestRun = workspace.runs[0];
  const latestReport = workspace.reports[0];
  const summary = run.summary;
  const jobs = workspace.jobs.slice(0, 5);
  const recommendations = !stale && run.run_id === (payload.optimization.run_id ?? payload.optimization.optimized_run.run_id) ? payload.optimization.recommendations.slice(0, 3) : [];
  const constraints = planningConstraints(run, scenario);
  const satisfied = constraints.filter((item) => item.satisfied).length;
  return (
    <aside className="copilot-panel job-center-panel">
      <div className="panel-title-row">
        <h2>任务与建议</h2>
        <button className="icon-button" aria-label="刷新任务" onClick={() => void onRefresh()}><RefreshCcw size={16} /></button>
      </div>

      <div className="tabs compact-tabs">
        <button className={tab === "recommendations" ? "tab-active" : ""} onClick={() => setTab("recommendations")}>推荐</button>
        <button className={tab === "evidence" ? "tab-active" : ""} onClick={() => setTab("evidence")}>证据</button>
      </div>

      <div className="assessment copilot-score-card">
        <div className="score-ring">{satisfied}/{constraints.length}</div>
        <div>
          <strong>规划约束满足情况</strong>
          <span>{stale ? "参数已修改，等待重新计算" : `${constraints.length - satisfied} 项尚未达标`}</span>
        </div>
      </div>

      <div className="audit-mini-grid">
        <MiniMetric label="覆盖" value={`${summary.coverage_percent}%`} />
        <MiniMetric label="P5速率" value={`${summary.p5_rate_mbps}`} />
        <MiniMetric label="P95 PEB" value={`${summary.p95_peb_m}m`} warn={Number(summary.p95_peb_m) > 5} />
        <MiniMetric label="成本" value={`${summary.selected_cost}`} warn />
      </div>

      {tab === "recommendations" && <><div className="copilot-command-card">
        <strong>下一步建议</strong>
        <p>{stale ? "当前结果已过期，请重新仿真或优化。" : recommendations.length ? `当前算法建议部署 ${recommendations.map((item) => item.node_id).join("、")}。` : "本次结果暂无部署优化建议。"}</p>
        <button onClick={onReport}><FileText size={15} />生成交付报告</button>
      </div>

      <h3>部署动作</h3>
      <div className="recommendation-list compact-recommendations">
        {recommendations.map((item, index) => (
          <div key={item.node_id} className="recommendation recommendation-static">
            <NodeGlyph type={item.node_type} />
            <div>
              <strong>{item.node_id}</strong>
              <p>{item.reason}</p>
              <span>
                边缘速率 {formatDelta(item.expected_gain.p5_rate_mbps ?? item.expected_gain.avg_rate_mbps)} Mbps ·
                定位 {formatDelta(item.expected_gain.p95_peb_m ?? item.expected_gain.avg_peb_m)} m
              </span>
            </div>
            <em className={index === 0 ? "impact-high" : "impact-med"}>{index === 0 ? "高" : "中"}</em>
          </div>
        ))}
      </div></>}

      <h3>{tab === "evidence" ? "运行证据" : "最近任务"}</h3>
      <div className="job-list">
        {jobs.map((job) => (
          <div key={job.job_id} className={`job-row ${job.status}`}>
            <div>
              <strong>{job.job_type}</strong>
              <span>{job.message}</span>
              <i><b style={{ width: `${Math.round(Number(job.progress ?? 0))}%` }} /></i>
            </div>
            <em>{statusLabel(job.status)}</em>
          </div>
        ))}
      </div>
      {!jobs.length && <div className="empty-state">尚未执行任务</div>}

      {latestRun ? (
        <div className="resource-summary-card evidence-card compact-evidence-card">
          <SummaryLine label="Run" value={String(latestRun.run_id)} />
          <SummaryLine label="类型" value={String(latestRun.run_type)} />
          <SummaryLine label="模型" value={String(latestRun.model_profile)} />
          <SummaryLine label="Manifest" value={latestRun.manifest_path ? "已生成" : "待生成"} />
        </div>
      ) : (
        <div className="empty-state">
          <strong>暂无后端运行记录</strong>
          <span>点击仿真或优化后，会生成 run、manifest、quality 与 artifact 索引。</span>
        </div>
      )}

      {latestReport ? (
        <div className="resource-summary-card evidence-card compact-evidence-card">
          <SummaryLine label="报告" value={latestReport.title} />
          <SummaryLine label="模板" value={latestReport.template} />
          <SummaryLine label="Run" value={latestReport.run_id ?? "未绑定"} />
        </div>
      ) : (
        <div className="empty-state">
          <strong>尚未生成报告</strong>
          <span>生成报告后，证据索引会绑定 run_id、模型档位和场景版本。</span>
        </div>
      )}
    </aside>
  );
}

function UseCaseStudio({ platform, message }: { platform: PlatformCatalog; message: string }) {
  return (
    <aside className="scenario-panel studio-panel">
      <div className="panel-title-row">
        <h1>用例工作台</h1>
        <Sparkles size={17} />
      </div>
      <div className="status-note">
        <MousePointer2 size={14} />
        <span>{message}</span>
      </div>
      <SectionTitle>平台定位</SectionTitle>
      <div className="report-block">
        <p>{platform.positioning}</p>
      </div>
      <SectionTitle>场景族</SectionTitle>
      <div className="studio-list">
        {platform.use_cases.slice(0, 8).map((item) => (
          <div key={String(item.id)} className="studio-row">
            <strong>{String(item.name)}</strong>
            <span>{String(item.model ?? "模型档位")} | {String(item.algorithm ?? "算法")}</span>
          </div>
        ))}
      </div>
      <SectionTitle>场景 x 模型 x 算法</SectionTitle>
      <div className="matrix-list">
        {platform.scenario_model_algorithm_matrix.slice(0, 5).map((item) => (
          <div key={item.scenario} className="matrix-row">
            <strong>{item.scenario}</strong>
            <span>{item.model}</span>
            <em>{item.algorithm}</em>
          </div>
        ))}
      </div>
    </aside>
  );
}

function ModelLab({
  payload,
  run: activeRun,
  platform,
  modelProfile,
  setModelProfile,
  message,
}: {
  payload: DemoPayload;
  run: DemoPayload["baseline"];
  platform: PlatformCatalog;
  modelProfile: ModelProfile;
  setModelProfile: (profile: ModelProfile) => void;
  message: string;
}) {
  const quality = activeRun.summary.run_quality as { passed?: number; warning?: number; failed?: number; score?: number; checks?: Array<Record<string, unknown>> } | undefined;
  const manifest = activeRun.summary.run_manifest as { manifest_version?: string; data_sources?: Record<string, string>; reproducibility?: Record<string, unknown> } | undefined;
  return (
    <aside className="scenario-panel model-lab-panel">
      <div className="panel-title-row">
        <h1>模型实验室</h1>
        <Settings size={17} />
      </div>
      <div className="status-note">
        <MousePointer2 size={14} />
        <span>{message}</span>
      </div>
      <SectionTitle>保真档位</SectionTitle>
      <div className="profile-card-list">
        {platform.model_profiles.map((profile) => {
          const id = String(profile.id) as ModelProfile;
          const isSelectable = id in modelProfileLabels;
          return (
            <button key={id} className={modelProfile === id ? "profile-card active" : "profile-card"} disabled={!isSelectable} onClick={() => isSelectable && setModelProfile(id)}>
              <strong>{String(profile.name)}</strong>
              <span>等级 {String(profile.fidelity_level ?? "?")} | {String(profile.status ?? "已注册")}</span>
            </button>
          );
        })}
      </div>
      <SectionTitle>标准依据</SectionTitle>
      <div className="studio-list">
        {platform.standards.map((item) => (
          <div key={String(item.id)} className="studio-row">
            <strong>{String(item.name)}</strong>
            <span>{String(item.implemented_scope ?? item.role ?? "已注册标准")}</span>
          </div>
        ))}
      </div>
      <SectionTitle>运行质量</SectionTitle>
      <div className="quality-strip">
        <MiniMetric label="通过" value={`${quality?.passed ?? 0}`} />
        <MiniMetric label="警告" value={`${quality?.warning ?? 0}`} warn />
        <MiniMetric label="失败" value={`${quality?.failed ?? 0}`} />
        <MiniMetric label="评分" value={`${quality?.score ?? "n/a"}`} />
      </div>
      <div className="quality-list">
        {(quality?.checks ?? []).slice(0, 6).map((check) => (
          <div key={String(check.id)} className={`quality-row ${String(check.status)}`}>
            <strong>{String(check.id)}</strong>
            <span>{String(check.message)}</span>
          </div>
        ))}
      </div>
      <SectionTitle>运行清单</SectionTitle>
      <div className="resource-summary-card">
        <SummaryLine label="清单版本" value={String(manifest?.manifest_version ?? "0.5")} />
        <SummaryLine label="场景" value={String(activeRun.scenario_id ?? payload.scenario.id)} />
        <SummaryLine label="数据源" value={String(manifest?.data_sources?.scenario_config ?? "场景配置")} />
      </div>
    </aside>
  );
}

function AlgorithmLab({
  platform,
  solver,
  setSolver,
  resourceMethod,
  setResourceMethod,
  intentPlan,
  isBusy,
  message,
  onRunDeployment,
  onRunResource,
  scenario,
  onChangeScenario,
  resourceSettings,
  setResourceSettings,
}: {
  platform: PlatformCatalog;
  solver: OptimizerSolver;
  setSolver: (solver: OptimizerSolver) => void;
  resourceMethod: ResourceMethod;
  setResourceMethod: (method: ResourceMethod) => void;
  intentPlan: IntentPlan | null;
  isBusy: boolean;
  message: string;
  onRunDeployment: () => void;
  onRunResource: (method: ResourceMethod) => void;
  scenario: DemoPayload["scenario"];
  onChangeScenario: (scenario: DemoPayload["scenario"]) => void;
  resourceSettings: { max_flows: number; iterations: number };
  setResourceSettings: (settings: { max_flows: number; iterations: number }) => void;
}) {
  const [category, setCategory] = useState<"deployment" | "resource" | "all">("deployment");
  const [query, setQuery] = useState("");
  const [focusedAlgorithmId, setFocusedAlgorithmId] = useState<string | null>(null);
  const algorithms = useMemo(
    () => platform.algorithm_catalog?.algorithms ?? legacyAlgorithmDescriptors(platform),
    [platform],
  );
  const visibleAlgorithms = algorithms.filter((algorithm) => {
    const matchesCategory = category === "all" || algorithm.category === category;
    const search = query.trim().toLowerCase();
    const matchesSearch = !search || `${algorithm.name} ${algorithm.id} ${algorithm.description}`.toLowerCase().includes(search);
    return matchesCategory && matchesSearch;
  });
  const selectedId = focusedAlgorithmId ?? (category === "resource" ? resourceMethod : solver);
  const selectedAlgorithm = algorithms.find((algorithm) => algorithm.id === selectedId)
    ?? algorithms.find((algorithm) => algorithm.id === solver)
    ?? visibleAlgorithms[0];

  const selectAlgorithm = (algorithm: AlgorithmDescriptor) => {
    setFocusedAlgorithmId(algorithm.id);
    if (algorithm.category === "deployment" && algorithm.id in solverLabels) {
      setSolver(algorithm.id as OptimizerSolver);
    }
    if (algorithm.category === "resource" && algorithm.id in resourceMethodLabels) {
      setResourceMethod(algorithm.id as ResourceMethod);
    }
  };

  const runSelected = () => {
    if (selectedAlgorithm?.category === "resource") {
      onRunResource(selectedAlgorithm.id as ResourceMethod);
    } else {
      onRunDeployment();
    }
  };

  return (
    <aside className="scenario-panel algorithm-lab-panel">
      <div className="panel-title-row">
        <div>
          <h1>算法中心</h1>
          <span className="panel-kicker">{algorithms.length} 个算法 · 统一注册与审计</span>
        </div>
        <Cpu size={18} />
      </div>
      <div className="status-note">
        <MousePointer2 size={14} />
        <span>{message}</span>
      </div>

      <div className="algorithm-tabs" role="tablist" aria-label="算法分类">
        <button className={category === "deployment" ? "is-active" : ""} onClick={() => { setCategory("deployment"); setFocusedAlgorithmId(null); }}>部署</button>
        <button className={category === "resource" ? "is-active" : ""} onClick={() => { setCategory("resource"); setFocusedAlgorithmId(null); }}>资源</button>
        <button className={category === "all" ? "is-active" : ""} onClick={() => { setCategory("all"); setFocusedAlgorithmId(null); }}>全部</button>
      </div>

      <label className="algorithm-search">
        <Search size={15} />
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索算法、目标或方法" />
      </label>

      <div className="algorithm-catalog-list">
        {visibleAlgorithms.map((algorithm) => {
          const selected = algorithm.id === solver || algorithm.id === resourceMethod;
          return (
            <button key={algorithm.id} className={selected ? "algorithm-card is-selected" : "algorithm-card"} onClick={() => selectAlgorithm(algorithm)}>
              <span className="algorithm-card-head">
                <span>
                  <strong>{algorithm.name}</strong>
                  <code>{algorithm.id}</code>
                </span>
                <em className={`algorithm-status status-${algorithm.engine}`}>{algorithm.maturity}</em>
              </span>
              <p>{algorithm.description}</p>
              <span className="algorithm-card-foot">
                <span>{algorithm.objectives.slice(0, 3).join(" · ")}</span>
                <span>{algorithm.runtime_class}</span>
              </span>
            </button>
          );
        })}
      </div>

      {selectedAlgorithm && (
        <div className="algorithm-config-card">
          <div>
            <span>当前选择</span>
            <strong>{selectedAlgorithm.name}</strong>
          </div>
          <dl>
            {Object.entries(selectedAlgorithm.parameters).slice(0, 3).map(([key, value]) => (
              <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{String(value)}</dd></div>
            ))}
          </dl>
          {selectedAlgorithm.id === "nsga2_pareto" && <div className="parameter-grid">
            {([ ["population_size", "种群数量", 18, 8, 40], ["generations", "迭代代数", 8, 2, 30], ["seed", "随机种子", 20260711, 0, 2147483647] ] as const).map(([key, label, fallback, min, max]) => <NumberField key={key} label={label} value={Number((scenario.optimization?.nsga2 as Record<string, number> | undefined)?.[key] ?? fallback)} min={min} max={max} onChange={(value) => onChangeScenario({ ...scenario, optimization: { ...scenario.optimization, nsga2: { ...(scenario.optimization?.nsga2 as object ?? {}), [key]: value } } })} />)}
          </div>}
          {selectedAlgorithm.category === "resource" && <div className="parameter-grid">
            <NumberField label="业务流数量" value={resourceSettings.max_flows} min={4} max={64} onChange={(value) => setResourceSettings({ ...resourceSettings, max_flows: value })} />
            <NumberField label="求解迭代数" value={resourceSettings.iterations} min={2} max={100} onChange={(value) => setResourceSettings({ ...resourceSettings, iterations: value })} />
          </div>}
          <button className="primary-action" disabled={isBusy || !["deployment", "resource"].includes(selectedAlgorithm.category)} onClick={runSelected}>
            <Play size={16} />{isBusy ? "正在运行" : "运行当前算法"}
          </button>
        </div>
      )}

      <SectionTitle>运行编排</SectionTitle>
      <div className="algorithm-pipeline">
        {(intentPlan?.tool_chain ?? [
          { tool: "scenario_validate", reason: "场景与模型检查" },
          { tool: "algorithm_execute", reason: "约束求解" },
          { tool: "evidence_bind", reason: "结果与证据绑定" },
        ]).slice(0, 4).map((step, index) => (
          <div key={`${step.tool}-${index}`}>
            <em>{index + 1}</em>
            <span><strong>{String(step.tool)}</strong><small>{String(step.reason ?? step.profile ?? "已规划")}</small></span>
          </div>
        ))}
      </div>
    </aside>
  );
}

function BenchmarkCenter({
  robustEvaluation,
  sensitivity,
  benchmark,
  isBusy,
  message,
  onRun,
}: {
  robustEvaluation: RobustEvaluation | null;
  sensitivity: SensitivityResult | null;
  benchmark: BenchmarkSuite | null;
  isBusy: boolean;
  message: string;
  onRun: () => void;
}) {
  return (
    <aside className="scenario-panel benchmark-panel">
      <div className="panel-title-row">
        <h1>基准评测中心</h1>
        <button className="ghost-button" disabled={isBusy} onClick={onRun}><RefreshCcw size={15} />运行</button>
      </div>
      <div className="status-note">
        <MousePointer2 size={14} />
        <span>{message}</span>
      </div>
      <SectionTitle>鲁棒性</SectionTitle>
      {robustEvaluation ? (
        <>
          <div className="quality-strip">
            <MiniMetric label="样本" value={`${robustEvaluation.samples}`} />
            <MiniMetric label="SLA风险" value={`${Math.round(robustEvaluation.risk.sla_violation_probability * 100)}%`} warn />
            <MiniMetric label="CVaR" value={`${robustEvaluation.risk.objective_cvar_10}`} />
            <MiniMetric label="稳定性" value={`${robustEvaluation.risk.stability_score}`} />
          </div>
          <div className="resource-summary-card">
            <SummaryLine label="覆盖 p5/p50/p95" value={`${robustEvaluation.percentiles.coverage_percent.p5}/${robustEvaluation.percentiles.coverage_percent.p50}/${robustEvaluation.percentiles.coverage_percent.p95}`} />
            <SummaryLine label="边缘速率 p5/p50/p95" value={`${robustEvaluation.percentiles.p5_rate_mbps.p5}/${robustEvaluation.percentiles.p5_rate_mbps.p50}/${robustEvaluation.percentiles.p5_rate_mbps.p95}`} />
          </div>
        </>
      ) : (
        <div className="empty-state">
          <strong>尚未运行鲁棒性评测</strong>
          <span>点击运行后执行蒙特卡洛鲁棒性与敏感性分析。</span>
        </div>
      )}
      <SectionTitle>基线算法</SectionTitle>
      <div className="benchmark-list">
        {(benchmark?.rows ?? []).slice(0, 6).map((row) => (
          <div key={String(row.algorithm)} className="benchmark-row">
            <strong>{String(row.algorithm)}</strong>
            <span>{String(row.objective_score)} | {String(row.runtime_ms)} ms</span>
          </div>
        ))}
      </div>
      <SectionTitle>敏感性</SectionTitle>
      <div className="studio-list">
        {(sensitivity?.items ?? []).slice(0, 4).map((item) => (
          <div key={String(item.parameter)} className="studio-row">
            <strong>{String(item.parameter)}</strong>
            <span>目标变化 {String(item.objective_delta_low)} / {String(item.objective_delta_high)}</span>
          </div>
        ))}
      </div>
    </aside>
  );
}

function ResultsPanel({
  payload,
  optimized,
  resourcePlan,
  isBusy,
  message,
  modelProfile,
  solver,
  resourceMethod,
  setResourceMethod,
  onRunResourcePlan,
}: {
  payload: DemoPayload;
  optimized: boolean;
  resourcePlan: ResourcePlan | null;
  isBusy: boolean;
  message: string;
  modelProfile: ModelProfile;
  solver: OptimizerSolver;
  resourceMethod: ResourceMethod;
  setResourceMethod: (method: ResourceMethod) => void;
  onRunResourcePlan: (method?: ResourceMethod) => void;
}) {
  const active = optimized ? payload.optimization.optimized_run.summary : payload.baseline.summary;
  const benchmarkEntries = resourcePlan ? Object.entries(resourcePlan.benchmarks) : [];
  const maxBenchmarkRate = Math.max(1, ...benchmarkEntries.map(([, summary]) => Number(summary.sum_rate_mbps ?? 0)));
  return (
    <aside className="scenario-panel results-panel">
      <div className="panel-title-row">
        <h1>结果</h1>
        <button className="ghost-button" disabled={isBusy} onClick={() => onRunResourcePlan(resourceMethod)}><Play size={15} />运行</button>
      </div>
      <div className="status-note">
        <MousePointer2 size={14} />
        <span>{message}</span>
      </div>
      <div className="profile-strip">
        <span>{modelProfileLabels[modelProfile]}</span>
        <strong>{solverLabels[solver]}</strong>
      </div>
      <SectionTitle>当前运行</SectionTitle>
      <div className="result-grid">
        <MiniMetric label="覆盖" value={`${active.coverage_percent}%`} />
        <MiniMetric label="速率" value={`${active.avg_rate_mbps}`} />
        <MiniMetric label="PEB" value={`${active.avg_peb_m}m`} />
        <MiniMetric label="感知" value={`${active.avg_sensing_score}`} />
      </div>

      <SectionTitle>资源管控</SectionTitle>
      <div className="result-method-picker">
        <label>
          <span>调度算法</span>
          <select value={resourceMethod} onChange={(event) => setResourceMethod(event.target.value as ResourceMethod)}>
            {(Object.keys(resourceMethodLabels) as ResourceMethod[]).map((method) => (
              <option key={method} value={method}>{resourceMethodLabels[method]}</option>
            ))}
          </select>
        </label>
        <button disabled={isBusy} onClick={() => onRunResourcePlan(resourceMethod)}><Zap size={15} />重新计算</button>
      </div>
      {resourcePlan ? (
        <div className="resource-summary-card">
          <SummaryLine label="方法" value={resourcePlan.method.toUpperCase()} />
          <SummaryLine label="调度流数" value={`${resourcePlan.summary.scheduled_flows}`} />
          <SummaryLine label="总速率" value={`${resourcePlan.summary.sum_rate_mbps} Mbps`} />
          <SummaryLine label="P5 流速率" value={`${resourcePlan.summary.p5_flow_rate_mbps} Mbps`} />
          <SummaryLine label="公平性" value={`${resourcePlan.summary.jain_fairness}`} />
          <SummaryLine label="功率利用率" value={`${Math.round(resourcePlan.summary.avg_power_utilization * 100)}%`} />
        </div>
      ) : (
        <div className="empty-state">
          <strong>尚未生成资源管控方案</strong>
          <span>点击“结果/资源”后，将对当前拓扑运行 WMMSE 风格的功率与带宽分配。</span>
        </div>
      )}

      <SectionTitle>基线对比</SectionTitle>
      <div className="algorithm-comparison-chart" aria-label="资源算法吞吐对比图">
        {resourcePlan ? benchmarkEntries.map(([name, summary]) => (
          <button key={name} className={resourcePlan.method === name ? "comparison-bar is-current" : "comparison-bar"} onClick={() => {
            if (name in resourceMethodLabels) {
              setResourceMethod(name as ResourceMethod);
              onRunResourcePlan(name as ResourceMethod);
            }
          }}>
            <span><strong>{resourceMethodLabels[name as ResourceMethod] ?? name.replaceAll("_", " ")}</strong><em>{summary.sum_rate_mbps} Mbps</em></span>
            <i><b style={{ width: `${Math.max(5, Number(summary.sum_rate_mbps ?? 0) / maxBenchmarkRate * 100)}%` }} /></i>
            <small>公平性 {Number(summary.jain_fairness ?? 0).toFixed(3)}</small>
          </button>
        )) : (
          <div className="comparison-placeholder">运行一次资源方案后，这里会同时比较 5 类算法。</div>
        )}
      </div>
    </aside>
  );
}

function ReportPanel({
  payload,
  platform,
  optimized,
  resourcePlan,
  message,
  modelProfile,
  solver,
  template,
  setTemplate,
  onGenerate,
  isBusy,
  markdown,
}: {
  payload: DemoPayload;
  platform: PlatformCatalog;
  optimized: boolean;
  resourcePlan: ResourcePlan | null;
  message: string;
  modelProfile: ModelProfile;
  solver: OptimizerSolver;
  template: string;
  setTemplate: (value: string) => void;
  onGenerate: () => void;
  isBusy: boolean;
  markdown: string | null;
}) {
  const active = optimized ? payload.optimization.optimized_run.summary : payload.baseline.summary;
  const selected = (optimized ? payload.optimization.selected_candidate_ids : payload.baseline.selected_candidate_ids).join(", ");
  const resultModel = optimized ? payload.optimization.optimized_run.model_profile : payload.baseline.model_profile;
  return (
    <aside className="scenario-panel report-panel">
      <div className="panel-title-row">
        <h1>报告</h1>
        <button className="ghost-button" disabled={!markdown} onClick={() => markdown && downloadText(`${payload.scenario.id}-report.md`, markdown, "text/markdown")}><Download size={15} />导出</button>
      </div>
      <div className="report-actions"><select aria-label="报告模板" value={template} onChange={(event) => setTemplate(event.target.value)}><option value="enterprise">项目交付报告</option><option value="research">科研实验报告</option><option value="grant">基金论证报告</option></select><button className="primary-action" disabled={isBusy} onClick={onGenerate}><FileText size={15} />生成报告</button></div>
      {markdown && <details className="report-preview"><summary>查看已生成报告</summary><pre>{markdown}</pre></details>}
      <div className="status-note">
        <MousePointer2 size={14} />
        <span>{message}</span>
      </div>
      <SectionTitle>执行摘要</SectionTitle>
      <div className="report-block">
        <p>
          当前结果在 {modelProfileLabels[resultModel as ModelProfile]} 下达到 {active.coverage_percent}% 覆盖率、
          {active.avg_rate_mbps} Mbps 平均速率、{active.avg_peb_m} m 平均 PEB 和 {active.avg_sensing_score} 感知评分。
        </p>
        <p>
          结果中的候选节点：{selected || "无"}。{optimized ? `部署优化使用 ${solverLabels[solver]}。` : "此结果来自直接仿真。"}
        </p>
      </div>
      <SectionTitle>独立资源运行</SectionTitle>
      {resourcePlan ? (
        <div className="report-block">
          <p>
            {resourcePlan.method.toUpperCase()} 在 {resourcePlan.summary.active_transmitters} 个激活发射节点上调度
            {resourcePlan.summary.scheduled_flows} 条业务流。总速率为 {resourcePlan.summary.sum_rate_mbps} Mbps，
            P5 流速率为 {resourcePlan.summary.p5_flow_rate_mbps} Mbps，Jain 公平性为 {resourcePlan.summary.jain_fairness}。
          </p>
        </div>
      ) : (
        <div className="empty-state">
          <strong>暂无当前场景资源结果</strong>
        </div>
      )}
      <SectionTitle>报告模板</SectionTitle>
      <div className="studio-list">
        {platform.report_templates.map((template) => (
          <div key={String(template.id)} className="studio-row">
            <strong>{String(template.name)}</strong>
            <span>{Array.isArray(template.sections) ? template.sections.slice(0, 5).join(" | ") : "科研 / 横向 / 基金可用"}</span>
          </div>
        ))}
      </div>
      <SectionTitle>规划产物结构</SectionTitle>
      <div className="resource-summary-card">
        {Object.entries(platform.artifact_schema).slice(0, 4).map(([name, files]) => (
          <SummaryLine key={name} label={name} value={`${files.length} 项定义`} />
        ))}
      </div>
      <SectionTitle>模型假设</SectionTitle>
      <ul className="plain-list">
        {(resourcePlan?.assumptions ?? payload.baseline.assumptions ?? []).map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </aside>
  );
}

function ResourcePanel({ resourcePlan, isBusy, onRunResourcePlan }: { resourcePlan: ResourcePlan | null; isBusy: boolean; onRunResourcePlan: () => void }) {
  return (
    <aside className="copilot-panel resource-panel">
      <div className="panel-title-row">
        <h2>资源管控</h2>
        <button className="icon-button" aria-label="运行资源方案" disabled={isBusy} onClick={() => onRunResourcePlan()}><RefreshCcw size={16} /></button>
      </div>
      {resourcePlan ? (
        <>
          <div className="assessment">
            <div className="score-ring">{Math.round(resourcePlan.summary.jain_fairness * 100)}</div>
            <div>
              <strong>{resourcePlan.method.toUpperCase()} 分配</strong>
              <span>{resourcePlan.summary.active_transmitters} 个激活发射节点</span>
            </div>
          </div>
          <div className="micro-metrics">
            <MiniMetric label="总速率" value={`${resourcePlan.summary.sum_rate_mbps}`} />
            <MiniMetric label="加权" value={`${resourcePlan.summary.weighted_sum_rate}`} />
            <MiniMetric label="P5流" value={`${resourcePlan.summary.p5_flow_rate_mbps}`} />
            <MiniMetric label="公平性" value={`${resourcePlan.summary.jain_fairness}`} />
            <MiniMetric label="流数" value={`${resourcePlan.summary.scheduled_flows}`} />
          </div>
          <h3>调度流</h3>
          <div className="flow-list">
            {resourcePlan.flows.slice(0, 10).map((flow) => (
              <button key={flow.cell_id} className="flow-row">
                <div>
                  <strong>{flow.cell_id}</strong>
                  <span>{flow.serving_node} | {flow.bandwidth_mhz} MHz | {flow.power_dbm} dBm</span>
                </div>
                <em>{flow.rate_mbps} Mbps</em>
              </button>
            ))}
          </div>
          <h3>发射节点</h3>
          <div className="transmitter-list">
            {resourcePlan.transmitters.map((item) => (
              <div key={item.node_id} className="transmitter-row">
                <NodeGlyph type={item.node_type} />
                <span>{item.node_id}</span>
                <strong>{Math.round(item.utilization * 100)}%</strong>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="empty-state">
          <strong>尚未运行资源分配</strong>
          <span>点击“结果”或刷新按钮，为当前拓扑分配带宽、功率和服务节点。</span>
        </div>
      )}
    </aside>
  );
}

function ReferencePanel({ resourcePlan }: { resourcePlan: ResourcePlan | null }) {
  const references = resourcePlan?.references ?? [
    { name: "Hypatia", url: "https://github.com/snkas/hypatia", note: "LEO 星座网络仿真与可视化参考。" },
    { name: "Sionna", url: "https://github.com/NVlabs/sionna", note: "通信系统与高保真信道研究库参考。" },
    { name: "StarryNet", url: "https://github.com/SpaceNetLab/StarryNet", note: "卫星互联网仿真/仿真编排流程参考。" },
  ];
  return (
    <aside className="copilot-panel reference-panel">
      <div className="panel-title-row">
        <h2>来源与方法</h2>
        <FileText size={16} />
      </div>
      <div className="reference-list">
        {references.map((item) => (
          <a key={item.url} className="reference-row" href={item.url} target="_blank" rel="noreferrer">
            <strong>{item.name}</strong>
            <span>{item.note}</span>
          </a>
        ))}
      </div>
    </aside>
  );
}

function ScenarioPanel({
  payload,
  platform,
  scenario,
  selectedCandidateIds,
  selectedNode,
  selectedCell,
  isBusy,
  isDirty,
  message,
  metric,
  modelProfile,
  solver,
  optimized,
  setMetric,
  setModelProfile,
  setSolver,
  setOptimized,
  onRunSimulation,
  onRunOptimization,
  onToggleCandidate,
  onToggleCandidateGroup,
  onDeleteSelectedNode,
}: {
  payload: DemoPayload;
  platform: PlatformCatalog;
  scenario: DemoPayload["scenario"];
  selectedCandidateIds: string[];
  selectedNode: NodeItem | null;
  selectedCell: MetricCell | null;
  isBusy: boolean;
  isDirty: boolean;
  message: string;
  metric: MetricKey;
  modelProfile: ModelProfile;
  solver: OptimizerSolver;
  optimized: boolean;
  setMetric: (metric: MetricKey) => void;
  setModelProfile: (profile: ModelProfile) => void;
  setSolver: (solver: OptimizerSolver) => void;
  setOptimized: (value: boolean) => void;
  onRunSimulation: () => void;
  onRunOptimization: () => void;
  onToggleCandidate: (nodeId: string) => void;
  onToggleCandidateGroup: (nodeIds: string[]) => void;
  onDeleteSelectedNode: () => void;
}) {
  const summary = optimized ? payload.optimization.optimized_run.summary : payload.baseline.summary;
  return (
    <aside className="scenario-panel">
      <div className="panel-title-row">
        <h1>场景配置</h1>
        <button className="ghost-button" onClick={() => downloadText(`${scenario.id}.json`, JSON.stringify({ scenario, selected_candidate_ids: selectedCandidateIds }, null, 2))}><Download size={15} />JSON</button>
      </div>

      <SectionTitle>场景</SectionTitle>
      <div className="field-card"><strong>{scenario.name}</strong></div>

      <SectionTitle>问题模板</SectionTitle>
      <div className="field-card">
        <strong>{String(platform.problem_templates[0]?.name ?? "鲁棒通感部署规划")}</strong>
        <span>R-SAGIN-PP | 多目标 | 约束 + 风险</span>
      </div>

      <SectionTitle>目标区域</SectionTitle>
      <div className="field-card">
        <strong>{scenario.region.name ?? "自定义区域"}</strong>
        <span>多边形 | {scenario.region.polygon.length} 个边界点 | EPSG:4326</span>
      </div>

      <SectionTitle>模型档位</SectionTitle>
      <div className="segmented">
        {(Object.keys(modelProfileLabels) as ModelProfile[]).map((profile) => (
          <button key={profile} className={modelProfile === profile ? "segment-active" : ""} onClick={() => setModelProfile(profile)}>
            {modelProfileLabels[profile]}
          </button>
        ))}
        <button disabled>L2 RT</button>
      </div>

      <SectionTitle>优化求解器</SectionTitle>
      <div className="segmented">
        {(Object.keys(solverLabels) as OptimizerSolver[]).map((item) => (
          <button key={item} className={solver === item ? "segment-active" : ""} onClick={() => setSolver(item)}>
            {solverLabels[item]}
          </button>
        ))}
      </div>

      <SectionTitle>指标图层</SectionTitle>
      <div className="metric-selector">
        {(Object.keys(metricLabels) as MetricKey[]).map((key) => (
          <button key={key} className={metric === key ? "metric-active" : ""} onClick={() => setMetric(key)}>
            {metricLabels[key]}
          </button>
        ))}
      </div>

      <SectionTitle>规划模式</SectionTitle>
      <label className="switch-row">
        <span>{optimized ? "优化部署" : "仅看基线"}</span>
        <input type="checkbox" checked={optimized} onChange={(event) => setOptimized(event.target.checked)} />
      </label>

      <SectionTitle>网络资产</SectionTitle>
      <AssetRows
        scenario={scenario}
        selectedCandidateIds={selectedCandidateIds}
        onToggleCandidate={onToggleCandidate}
        onToggleCandidateGroup={onToggleCandidateGroup}
      />

      <button className="primary-action" disabled={isBusy} onClick={onRunSimulation}>
        <Play size={16} />
        {isBusy ? "运行中..." : "运行仿真"}
      </button>
      <button className="secondary-action" disabled={isBusy} onClick={onRunOptimization}>
        <Zap size={16} />
        优化当前场景
      </button>

      <div className={isDirty ? "status-note dirty" : "status-note"}>
        <MousePointer2 size={14} />
        <span>{message}</span>
      </div>

      <div className="scenario-summary">
        <SummaryLine label="覆盖率" value={`${summary.coverage_percent}%`} />
        <SummaryLine label="平均速率" value={`${summary.avg_rate_mbps} Mbps`} />
        <SummaryLine label="平均PEB" value={`${summary.avg_peb_m} m`} />
      </div>

      <Inspector selectedNode={selectedNode} selectedCell={selectedCell} onDeleteSelectedNode={onDeleteSelectedNode} />
    </aside>
  );
}

function AssetRows({
  scenario,
  selectedCandidateIds,
  onToggleCandidate,
  onToggleCandidateGroup,
}: {
  scenario: DemoPayload["scenario"];
  selectedCandidateIds: string[];
  onToggleCandidate: (nodeId: string) => void;
  onToggleCandidateGroup: (nodeIds: string[]) => void;
}) {
  const selected = new Set(selectedCandidateIds);
  const candidateIdsFor = (type: NodeType) => scenario.candidate_nodes.filter((node) => node.type === type).map((node) => node.id);
  const fixedCountFor = (...types: NodeType[]) => scenario.fixed_nodes.filter((node) => types.includes(node.type)).length;
  const rows: Array<[string, NodeType, number, number, string[]]> = [
    ["卫星", "satellite_leo", fixedCountFor("satellite_leo"), fixedCountFor("satellite_leo"), []],
    ["HAPS / 无人机", "uav_relay", candidateIdsFor("uav_relay").filter((id) => selected.has(id)).length, candidateIdsFor("uav_relay").length, candidateIdsFor("uav_relay")],
    ["地面站/基站", "ground_station", fixedCountFor("ground_station", "ground_bs"), fixedCountFor("ground_station", "ground_bs"), []],
    ["RIS", "ris", candidateIdsFor("ris").filter((id) => selected.has(id)).length, candidateIdsFor("ris").length, candidateIdsFor("ris")],
    ["MIS", "mis", candidateIdsFor("mis").filter((id) => selected.has(id)).length, candidateIdsFor("mis").length, candidateIdsFor("mis")],
    ["MA", "ma_array", candidateIdsFor("ma_array").filter((id) => selected.has(id)).length, candidateIdsFor("ma_array").length, candidateIdsFor("ma_array")],
  ];
  return (
    <div className="asset-list">
      {rows.map(([label, type, active, total, ids]) => (
        <button
          key={label}
          className="asset-row"
          disabled={ids.length === 0}
          onClick={() => {
            if (ids.length === 1) onToggleCandidate(ids[0]);
            else onToggleCandidateGroup(ids);
          }}
          title={ids.length ? "切换该组候选节点" : "固定资产"}
        >
          <NodeGlyph type={type} />
          <span>{label}</span>
          <strong>{active}/{total}</strong>
          <span className={active ? "mini-toggle on" : "mini-toggle"} />
        </button>
      ))}
    </div>
  );
}

function Inspector({
  selectedNode,
  selectedCell,
  onDeleteSelectedNode,
}: {
  selectedNode: NodeItem | null;
  selectedCell: MetricCell | null;
  onDeleteSelectedNode: () => void;
}) {
  if (!selectedNode && !selectedCell) {
    return (
      <div className="inspector empty">
        <strong>画布检查器</strong>
        <span>点击节点或热力图单元查看细节；拖拽 RIS/MIS/MA/无人机节点可编辑部署位置。</span>
      </div>
    );
  }

  if (selectedNode) {
    const canDelete = true;
    return (
      <div className="inspector">
        <div className="inspector-head">
          <strong>{selectedNode.id}</strong>
          <NodeGlyph type={selectedNode.type} />
        </div>
        <SummaryLine label="类型" value={nodeLabels[selectedNode.type]} />
        <SummaryLine label="纬度" value={selectedNode.position.lat.toFixed(5)} />
        <SummaryLine label="经度" value={selectedNode.position.lon.toFixed(5)} />
        <SummaryLine label="高度" value={`${selectedNode.position.alt_m} m`} />
        {canDelete && (
          <button className="danger-action" onClick={onDeleteSelectedNode}>
            <Trash2 size={15} />
            删除候选节点
          </button>
        )}
      </div>
    );
  }

  const properties = selectedCell?.properties ?? {};
  return (
    <div className="inspector">
      <div className="inspector-head">
        <strong>{selectedCell?.cell_id}</strong>
        <Layers3 size={15} />
      </div>
      <SummaryLine label="SINR" value={`${properties.sinr_db ?? "-"} dB`} />
      <SummaryLine label="速率" value={`${properties.rate_mbps ?? "-"} Mbps`} />
      <SummaryLine label="PEB" value={`${properties.peb_m ?? "-"} m`} />
      <SummaryLine label="感知" value={`${properties.sensing_score ?? "-"}`} />
      <SummaryLine label="需求权重" value={`${properties.demand_weight ?? "-"}`} />
      {properties.channel_model && (
        <>
          <div className="inspector-divider">物理信道</div>
          <SummaryLine label="模型" value={properties.channel_model} />
          <SummaryLine label="路径损耗" value={`${properties.path_loss_db ?? "-"} dB`} />
          <SummaryLine label="附加损耗" value={`${properties.extra_loss_db ?? "-"} dB`} />
          <SummaryLine label="LOS概率" value={`${properties.los_probability ?? "-"}`} />
          {properties.elevation_deg !== undefined && <SummaryLine label="仰角" value={`${properties.elevation_deg} deg`} />}
          {properties.rain_loss_db !== undefined && <SummaryLine label="雨衰" value={`${properties.rain_loss_db} dB`} />}
          {properties.gaseous_loss_db !== undefined && <SummaryLine label="气体损耗" value={`${properties.gaseous_loss_db} dB`} />}
        </>
      )}
    </div>
  );
}

function DigitalTwin({
  polygon,
  nodes,
  selectedIds,
  cells,
  metric,
  setMetric,
  modelProfile,
  viewMode,
  setViewMode,
  basemap,
  setBasemap,
  optimized,
  placementMode,
  selectedNodeId,
  selectedCell,
  isDirty,
  setPlacementMode,
  onSelectNode,
  onSelectCell,
  onMoveNode,
  onAddNode,
  onDeleteSelectedNode,
  onChangeNode,
}: {
  polygon: [number, number][];
  nodes: NodeItem[];
  selectedIds: Set<string>;
  cells: MetricCell[];
  metric: MetricKey;
  setMetric: (metric: MetricKey) => void;
  modelProfile: ModelProfile;
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;
  basemap: BasemapKind;
  setBasemap: (basemap: BasemapKind) => void;
  optimized: boolean;
  placementMode: PlacementMode;
  selectedNodeId: string | null;
  selectedCell: MetricCell | null;
  isDirty: boolean;
  setPlacementMode: (mode: PlacementMode) => void;
  onSelectNode: (nodeId: string | null) => void;
  onSelectCell: (cell: MetricCell | null) => void;
  onMoveNode: (nodeId: string, position: { lat: number; lon: number }) => void;
  onAddNode: (type: Exclude<PlacementMode, null>, position: { lat: number; lon: number }) => void;
  onDeleteSelectedNode: () => void;
  onChangeNode: (node: NodeItem) => void;
}) {
  const [opacity, setOpacity] = useState(0.48);
  const [showCells, setShowCells] = useState(true);
  const [showLinks, setShowLinks] = useState(false);
  const [fitRequest, setFitRequest] = useState(0);
  const scale = metricScales[metric];
  const selectedNode = nodes.find((node) => node.id === selectedNodeId) ?? null;
  return (
    <section className={`${placementMode ? "digital-twin placing" : "digital-twin"} view-${viewMode}`}>
      <div className="canvas-toolbar">
        <div className="view-tabs">
          <span>视图</span>
          <button className={viewMode === "3d" ? "segment-active" : ""} onClick={() => setViewMode("3d")}>3D</button>
          <button className={viewMode === "2d" ? "segment-active" : ""} onClick={() => setViewMode("2d")}>2D</button>
        </div>
        <select className="layer-select" value={metric} onChange={(event) => setMetric(event.target.value as MetricKey)}>
          {(Object.keys(metricLabels) as MetricKey[]).map((key) => (
            <option key={key} value={key}>{metricLabels[key]}</option>
          ))}
        </select>
        <div className="basemap-tabs" aria-label="GIS 底图">
          <button className={basemap === "street" ? "is-active" : ""} onClick={() => setBasemap("street")}><Map size={14} />街道</button>
          <button className={basemap === "satellite" ? "is-active" : ""} onClick={() => setBasemap("satellite")}><Satellite size={14} />卫星</button>
        </div>
        <div className="legend-row">
          {(["satellite_leo", "uav_relay", "ground_station", "ris", "mis", "ma_array"] as NodeType[]).map((type) => (
            <span key={type}><NodeGlyph type={type} />{nodeLabels[type]}</span>
          ))}
        </div>
      </div>

      <div className="placement-toolbar">
        <span><Plus size={14} />放置</span>
        {placementLabels.map((item) => (
          <button
            key={item.type}
            className={placementMode === item.type ? "placement-active" : ""}
            onClick={() => setPlacementMode(placementMode === item.type ? null : item.type)}
          >
            <NodeGlyph type={item.type} />
            {item.label}
          </button>
        ))}
        <select aria-label="放置网络设施" value={placementMode ?? ""} onChange={(event) => setPlacementMode((event.target.value || null) as PlacementMode)}>
          <option value="">网络设施</option>
          <option value="ris">RIS</option><option value="mis">MIS</option><option value="ma_array">MA 阵列</option><option value="uav_relay">无人机中继</option>
          <option value="satellite_leo">低轨卫星</option>
          <option value="satellite_geo">同步卫星</option>
          <option value="haps">高空平台 HAPS</option>
          <option value="ground_bs">地面基站</option>
          <option value="ground_station">地面站</option>
        </select>
        {placementMode && <button aria-label="取消放置" title="取消放置" onClick={() => setPlacementMode(null)}><X size={14} /></button>}
      </div>

      <Suspense fallback={<div className="map-module-loading">地图加载中...</div>}><GisMap
        polygon={polygon}
        nodes={nodes}
        selectedIds={selectedIds}
        cells={cells}
        metric={metric}
        viewMode={viewMode}
        basemap={basemap}
        placementMode={placementMode}
        selectedNodeId={selectedNodeId}
        selectedCell={selectedCell}
        onSelectNode={onSelectNode}
        onSelectCell={onSelectCell}
        onMoveNode={onMoveNode}
        onAddNode={onAddNode}
        opacity={opacity} showCells={showCells} showLinks={showLinks} fitRequest={fitRequest}
      /></Suspense>

      <div className="map-layer-controls">
        <label><input type="checkbox" checked={showCells} onChange={(event) => setShowCells(event.target.checked)} />性能场</label>
        <label><input type="checkbox" checked={showLinks} onChange={(event) => setShowLinks(event.target.checked)} />候选连接</label>
        <label className="opacity-control">透明度<input type="range" aria-label="性能场透明度" min="0.1" max="0.9" step="0.05" value={opacity} onChange={(event) => setOpacity(Number(event.target.value))} /></label>
        <button title="定位到区域" aria-label="定位到区域" onClick={() => setFitRequest((current) => current + 1)}><LocateFixed size={16} /></button>
      </div>

      {(selectedNode || selectedCell) && <div className="map-inspector"><button className="inspector-close" aria-label="关闭地图检查器" onClick={() => { onSelectNode(null); onSelectCell(null); }}><X size={15} /></button><Inspector selectedNode={selectedNode} selectedCell={selectedCell} onDeleteSelectedNode={onDeleteSelectedNode} />
        {selectedNode && <div className="node-edit-fields"><NumberField label="节点高度" unit="m" value={selectedNode.position.alt_m} min={0} max={36_000_000} onChange={(value) => onChangeNode({ ...selectedNode, position: { ...selectedNode.position, alt_m: value } })} /><NumberField label="发射功率" unit="dBm" value={Number(selectedNode.radio?.tx_power_dbm ?? 0)} min={0} max={80} onChange={(value) => onChangeNode({ ...selectedNode, radio: { ...selectedNode.radio, tx_power_dbm: value } })} /><NumberField label="节点成本" value={selectedNode.cost ?? 0} min={0} max={1000} onChange={(value) => onChangeNode({ ...selectedNode, cost: value })} /></div>}
      </div>}

      <div className="metric-legend">
        <strong>{metricLabels[metric]}</strong>
        <span className="physical-color-scale" style={{ background: `linear-gradient(90deg, ${scale.colors.join(", ")})` }} />
        <span>{scale.low} ~ {scale.high} {scale.unit}</span>
      </div>

      <div className="canvas-caption">
        <span>{optimized ? "当前部署" : "仿真拓扑"}</span>
        <span>{isDirty ? "编辑待重新计算" : `模型档位: ${modelProfileLabels[modelProfile]} | ${viewMode.toUpperCase()} | ${basemap === "street" ? "真实街道" : "卫星影像"}`}</span>
      </div>
    </section>
  );
}

function CopilotPanel({
  payload,
  run,
  stale,
  selectedCandidateIds,
  onApplySelected,
  onSelectNode,
}: {
  payload: DemoPayload;
  run: DemoPayload["baseline"];
  stale: boolean;
  selectedCandidateIds: string[];
  onApplySelected: () => void;
  onSelectNode: (nodeId: string | null) => void;
}) {
  const [tab, setTab] = useState("建议");
  const summary = run.summary;
  const recommendations = !stale && run.run_id === (payload.optimization.run_id ?? payload.optimization.optimized_run.run_id) ? payload.optimization.recommendations : [];
  const runId = run.run_id ?? "preview";
  const model = run.model_profile;
  return (
    <aside className="copilot-panel">
      <div className="panel-title-row">
        <h2>智能体建议</h2>
      </div>
      <div className="tabs">
        <button className={tab === "建议" ? "tab-active" : ""} onClick={() => setTab("建议")}>建议</button>
        <button className={tab === "洞察" ? "tab-active" : ""} onClick={() => setTab("洞察")}>洞察</button>
      </div>

      <div className="assessment">
        <div className="score-ring">{selectedCandidateIds.length}</div>
        <div>
          <strong>当前候选节点</strong>
          <span>{stale ? "编辑待重算" : "结果来源"}：{runId} | {model}</span>
        </div>
      </div>

      <div className="micro-metrics">
        <MiniMetric label="覆盖" value={`${summary.coverage_percent}%`} />
        <MiniMetric label="速率" value={`${summary.avg_rate_mbps}`} />
        <MiniMetric label="PEB" value={`${summary.avg_peb_m}m`} />
        <MiniMetric label="感知" value={`${summary.avg_sensing_score}`} />
        <MiniMetric label="成本" value={`${summary.selected_cost}`} warn />
      </div>

      <h3>{tab === "建议" ? `关键建议（${recommendations.length}）` : "模型假设"}</h3>
      <div className="recommendation-list">
        {tab === "洞察" ? (run.assumptions ?? []).map((assumption) => <p key={assumption}>{assumption}</p>) : recommendations.map((item, index) => (
          <button key={item.node_id} className="recommendation" onClick={() => onSelectNode(item.node_id)}>
            <NodeGlyph type={item.node_type} />
            <div>
              <strong>{item.node_id}</strong>
              <p>{item.reason}</p>
              <span>
                边缘增益 {formatDelta(item.expected_gain.p5_rate_mbps ?? item.expected_gain.avg_rate_mbps)} Mbps | PEB95 改善 {formatDelta(item.expected_gain.p95_peb_m ?? item.expected_gain.avg_peb_m)} m
              </span>
            </div>
            <em className={index === 0 ? "impact-high" : "impact-med"}>{index === 0 ? "高" : "中"}</em>
            <ChevronRight size={17} />
          </button>
        ))}
      </div>

      <div className="copilot-note">
        <Sparkles size={16} />
        <p>
          {stale ? "当前部署已修改，建议与指标需要重新计算。" : recommendations.length ? `部署建议来自 ${payload.optimization.summary.solver ?? "当前求解器"}。` : `当前 P95 定位代理值 ${summary.p95_peb_m} m，平均感知评分 ${summary.avg_sensing_score}；尚无本次部署优化建议。`}
        </p>
      </div>

      <button className="apply-button" disabled={!recommendations.length || stale} onClick={onApplySelected}>
        <Sparkles size={16} />
        应用推荐节点（{payload.optimization.selected_candidate_ids.length}）
      </button>
    </aside>
  );
}

function BottomPanel({ payload, optimized }: { payload: DemoPayload; optimized: boolean }) {
  const active = optimized ? payload.optimization.optimized_run.summary : payload.baseline.summary;
  const baseline = payload.baseline.summary;
  const opt = payload.optimization.optimized_run.summary;
  return (
    <footer className="bottom-panel">
      <section className="key-metrics">
        <h2>关键指标</h2>
        <div className="metric-card-row">
          <MetricCard label="覆盖率" value={`${active.coverage_percent}%`} target=">= 80%" trend="up" />
          <MetricCard label="平均速率" value={`${active.avg_rate_mbps}`} suffix="Mbps" target=">= 50" trend="up" />
          <MetricCard label="平均PEB" value={`${active.avg_peb_m}`} suffix="m" target="<= 5" trend="down" />
          <MetricCard label="感知评分" value={`${active.avg_sensing_score}`} target=">= 0.6" trend="up" />
          <MetricCard label="总成本" value={`${active.selected_cost}`} target="<= 36" trend="cost" />
        </div>
      </section>

      <section className="comparison">
        <div className="comparison-head">
          <h2>优化对比</h2>
          <button className="ghost-button"><Download size={15} />导出</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>方案</th>
              <th>覆盖率</th>
              <th>速率</th>
              <th>PEB</th>
              <th>感知</th>
              <th>成本</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>当前基线</td>
              <td>{baseline.coverage_percent}%</td>
              <td>{baseline.avg_rate_mbps}</td>
              <td>{baseline.avg_peb_m}</td>
              <td>{baseline.avg_sensing_score}</td>
              <td>{baseline.selected_cost}</td>
            </tr>
            <tr className="recommended-row">
              <td>均衡推荐</td>
              <td>{opt.coverage_percent}%</td>
              <td>{opt.avg_rate_mbps}</td>
              <td>{opt.avg_peb_m}</td>
              <td>{opt.avg_sensing_score}</td>
              <td>{opt.selected_cost}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </footer>
  );
}

function SectionTitle({ children }: { children: string }) {
  return <h2 className="section-title">{children}</h2>;
}

function SummaryLine({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MiniMetric({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className={warn ? "mini-metric warn" : "mini-metric"}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MetricCard({ label, value, suffix, target, trend }: { label: string; value: string; suffix?: string; target: string; trend: "up" | "down" | "cost" }) {
  return (
    <article className="metric-card">
      <span>{label}</span>
      <strong>{value} {suffix}</strong>
      <em>{target}</em>
      <svg viewBox="0 0 120 34" aria-hidden="true">
        <polyline
          points={trend === "down" ? "2,10 22,12 43,21 64,15 84,20 106,25 118,18" : trend === "cost" ? "2,20 24,12 45,18 67,24 90,16 118,22" : "2,27 22,18 43,21 64,12 84,15 106,8 118,10"}
        />
      </svg>
    </article>
  );
}

function HexCell({
  cell,
  bounds,
  metric,
  selected,
  onSelect,
}: {
  cell: MetricCell;
  bounds: Bounds;
  metric: MetricKey;
  selected: boolean;
  onSelect: (event: PointerEvent<SVGPolygonElement>) => void;
}) {
  const point = project(cell.lon, cell.lat, bounds);
  const color = colorFor(metric, cell.value);
  const radius = 11;
  const points = Array.from({ length: 6 }, (_, index) => {
    const angle = Math.PI / 3 * index + Math.PI / 6;
    return `${point.x + radius * Math.cos(angle)},${point.y + radius * Math.sin(angle)}`;
  }).join(" ");
  return <polygon points={points} fill={color} className={selected ? "hex-cell selected" : "hex-cell"} onClick={onSelect} />;
}

function NodeMarker({
  node,
  bounds,
  active,
  selected,
  draggable,
  onPointerDown,
}: {
  node: NodeItem;
  bounds: Bounds;
  active: boolean;
  selected: boolean;
  draggable: boolean;
  onPointerDown: (event: PointerEvent<SVGGElement>) => void;
}) {
  const point = project(node.position.lon, node.position.lat, bounds);
  return (
    <g
      className={`${active ? `node-marker node-${node.type}` : "node-marker inactive"}${selected ? " selected" : ""}${draggable ? " draggable" : ""}`}
      transform={`translate(${point.x} ${point.y})`}
      onClick={(event) => event.stopPropagation()}
      onPointerDown={onPointerDown}
    >
      <circle r="16" />
      <NodeMiniGlyph type={node.type} />
      <title>{node.id}</title>
    </g>
  );
}

function NetworkLinks({ nodes, bounds, selectedIds }: { nodes: NodeItem[]; bounds: Bounds; selectedIds: Set<string> }) {
  const anchors = nodes.filter((node) => ["ground_bs", "ground_station", "satellite_leo"].includes(node.type));
  const selected = nodes.filter((node) => selectedIds.has(node.id));
  return (
    <g className="network-links">
      {selected.flatMap((node) => anchors.map((anchor) => {
        const a = project(anchor.position.lon, anchor.position.lat, bounds);
        const b = project(node.position.lon, node.position.lat, bounds);
        return <line key={`${anchor.id}-${node.id}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} />;
      }))}
    </g>
  );
}

function NodeGlyph({ type }: { type: NodeType }) {
  const common = { size: 15, strokeWidth: 2.2 };
  if (type === "satellite_leo" || type === "satellite_geo") return <Satellite {...common} />;
  if (type === "uav_relay" || type === "haps") return <Plane {...common} />;
  if (type === "ground_bs" || type === "ground_station") return <RadioTower {...common} />;
  if (type === "ris") return <Cpu {...common} />;
  if (type === "mis") return <TriangleAlert {...common} />;
  if (type === "ma_array") return <LocateFixed {...common} />;
  return <Antenna {...common} />;
}

function NodeMiniGlyph({ type }: { type: NodeType }) {
  if (type === "satellite_leo" || type === "satellite_geo") {
    return (
      <g className="node-mini-glyph" aria-hidden="true">
        <path d="M -9 -2 L 9 2" />
        <path d="M -4 -8 L -9 -2 L -3 4" />
        <path d="M 4 -4 L 9 2 L 3 8" />
        <circle r="3.2" />
      </g>
    );
  }
  if (type === "uav_relay" || type === "haps") {
    return (
      <g className="node-mini-glyph" aria-hidden="true">
        <path d="M -11 3 L 0 -8 L 11 3" />
        <path d="M 0 -8 L 0 9" />
        <path d="M -5 5 L 0 9 L 5 5" />
      </g>
    );
  }
  if (type === "ground_bs" || type === "ground_station") {
    return (
      <g className="node-mini-glyph" aria-hidden="true">
        <path d="M 0 -9 L 0 9" />
        <path d="M -7 9 L 7 9" />
        <path d="M -8 -3 C -11 -7 -11 -10 -8 -13" />
        <path d="M 8 -3 C 11 -7 11 -10 8 -13" />
        <circle cy="-4" r="2.7" />
      </g>
    );
  }
  if (type === "ris") {
    return (
      <g className="node-mini-glyph" aria-hidden="true">
        <rect x="-8" y="-8" width="16" height="16" rx="2" />
        <path d="M -4 -8 L -4 8 M 0 -8 L 0 8 M 4 -8 L 4 8 M -8 -4 L 8 -4 M -8 0 L 8 0 M -8 4 L 8 4" />
      </g>
    );
  }
  if (type === "mis") {
    return (
      <g className="node-mini-glyph" aria-hidden="true">
        <path d="M -9 8 L 0 -10 L 9 8 Z" />
        <path d="M -4 4 L 4 4 M 0 -4 L 0 4" />
      </g>
    );
  }
  if (type === "ma_array") {
    return (
      <g className="node-mini-glyph" aria-hidden="true">
        <circle r="2.4" />
        <path d="M -9 0 L 9 0 M 0 -9 L 0 9" />
        <path d="M -6 -6 L 6 6 M 6 -6 L -6 6" />
      </g>
    );
  }
  return (
    <g className="node-mini-glyph" aria-hidden="true">
      <path d="M 0 -10 L 0 10 M -7 -2 L 0 -10 L 7 -2" />
    </g>
  );
}

function MapTexture() {
  const arterialRoads = [
    "M -40 520 C 160 420, 300 430, 476 325 S 800 190, 1060 85",
    "M -20 230 C 190 255, 320 290, 520 276 S 825 250, 1040 300",
    "M 140 -20 C 210 130, 290 205, 430 318 S 620 480, 700 710",
    "M 420 -30 C 390 130, 430 260, 570 410 S 810 540, 1030 585",
  ];
  const localRoads = Array.from({ length: 17 }, (_, index) => (
    `M ${-80 + index * 66} ${88 + (index % 6) * 58} C ${180 + index * 8} ${110 + index * 14}, ${510 - index * 5} ${260 + index * 9}, 1080 ${132 + (index % 7) * 56}`
  ));
  const cityBlocks = Array.from({ length: 60 }, (_, index) => {
    const col = index % 12;
    const row = Math.floor(index / 12);
    return {
      x: 94 + col * 76 + (row % 2) * 22,
      y: 96 + row * 92 + (col % 3) * 7,
      width: 26 + ((index * 11) % 30),
      height: 12 + ((index * 7) % 24),
    };
  });
  const districts = [
    { x: 90, y: 118, label: "德清" },
    { x: 778, y: 128, label: "临平" },
    { x: 92, y: 600, label: "富阳" },
    { x: 806, y: 560, label: "萧山" },
    { x: 456, y: 114, label: "余杭" },
  ];
  return (
    <g className="map-texture">
      <defs>
        <linearGradient id="riverGradient" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0%" stopColor="#cfeaf0" />
          <stop offset="100%" stopColor="#e8f5f7" />
        </linearGradient>
        <pattern id="fineGrid" width="42" height="42" patternUnits="userSpaceOnUse">
          <path d="M 42 0 L 0 0 0 42" />
        </pattern>
      </defs>
      <rect className="map-grid-bg" x="0" y="0" width="1000" height="670" fill="url(#fineGrid)" />
      <path className="map-water" d="M -40 430 C 150 360, 270 370, 390 438 S 630 520, 780 444 S 940 335, 1060 370 L 1060 710 L -40 710 Z" />
      <path className="map-water-line" d="M -40 430 C 150 360, 270 370, 390 438 S 630 520, 780 444 S 940 335, 1060 370" />
      <g className="map-city-blocks">
        {cityBlocks.map((block, index) => (
          <rect key={index} x={block.x} y={block.y} width={block.width} height={block.height} rx="3" />
        ))}
      </g>
      <g className="map-local-roads">
        {localRoads.map((road, index) => <path key={index} d={road} />)}
      </g>
      <g className="map-arterial-roads">
        {arterialRoads.map((road, index) => <path key={index} d={road} />)}
      </g>
      <g className="map-district-labels">
        {districts.map((district) => (
          <text key={district.label} x={district.x} y={district.y}>{district.label}</text>
        ))}
      </g>
      <g className="map-scale">
        <path d="M 812 622 L 930 622" />
        <path d="M 812 616 L 812 628 M 930 616 L 930 628" />
        <text x="858" y="612">1 km</text>
      </g>
    </g>
  );
}

function TerrainExtrusion({ polygon, bounds }: { polygon: [number, number][]; bounds: Bounds }) {
  const points = polygon.map(([lon, lat]) => project(lon, lat, bounds));
  return (
    <g className="terrain-extrusion">
      {points.map((point, index) => {
        const next = points[(index + 1) % points.length];
        const side = `${point.x},${point.y} ${next.x},${next.y} ${next.x + 28},${next.y + 34} ${point.x + 28},${point.y + 34}`;
        return <polygon key={index} points={side} />;
      })}
      {Array.from({ length: 12 }, (_, index) => (
        <path key={`ridge-${index}`} d={`M ${190 + index * 42} ${185 + (index % 3) * 18} L ${430 + index * 24} ${420 - (index % 4) * 16}`} />
      ))}
    </g>
  );
}

interface Bounds {
  minLon: number;
  maxLon: number;
  minLat: number;
  maxLat: number;
}

function createBounds(polygon: [number, number][]): Bounds {
  const lon = polygon.map((point) => point[0]);
  const lat = polygon.map((point) => point[1]);
  return {
    minLon: Math.min(...lon) - 0.003,
    maxLon: Math.max(...lon) + 0.003,
    minLat: Math.min(...lat) - 0.003,
    maxLat: Math.max(...lat) + 0.003,
  };
}

function project(lon: number, lat: number, bounds: Bounds) {
  return {
    x: 80 + ((lon - bounds.minLon) / (bounds.maxLon - bounds.minLon)) * 840,
    y: 610 - ((lat - bounds.minLat) / (bounds.maxLat - bounds.minLat)) * 520,
  };
}

function inverseProject(x: number, y: number, bounds: Bounds) {
  return {
    lon: bounds.minLon + ((x - 80) / 840) * (bounds.maxLon - bounds.minLon),
    lat: bounds.minLat + ((610 - y) / 520) * (bounds.maxLat - bounds.minLat),
  };
}

function createCandidateNode(type: Exclude<PlacementMode, null>, position: { lat: number; lon: number }, index: number): NodeItem {
  const suffix = `${Date.now().toString(36)}_${index}`;
  const base = {
    id: `${type}_${suffix}`,
    type,
    position: {
      lat: Number(position.lat.toFixed(6)),
      lon: Number(position.lon.toFixed(6)),
      alt_m: type === "satellite_leo" ? 600_000 : type === "satellite_geo" ? 35_786_000 : type === "haps" ? 20_000 : type === "uav_relay" ? 140 : type === "ma_array" ? 12 : 32,
    },
    enabled: true,
  };
  if (["satellite_leo", "satellite_geo", "haps", "ground_bs", "ground_station"].includes(type)) {
    return {
      ...base,
      radio: { tx_power_dbm: type.startsWith("satellite") ? 43 : 40, antenna_gain_dbi: type.startsWith("satellite") ? 30 : 16 },
      cost: 0,
    };
  }
  if (type === "uav_relay") {
    return {
      ...base,
      radio: { tx_power_dbm: 32, antenna_gain_dbi: 11 },
      mobility: { mode: "hover", max_speed_mps: 18 },
      cost: 13,
    };
  }
  if (type === "ris") {
    return {
      ...base,
      radio: { tx_power_dbm: 0, antenna_gain_dbi: 0 },
      reconfigurable: {
        kind: "ris",
        num_elements_x: 24,
        num_elements_y: 24,
        phase_bits: 2,
        reflection_loss_db: 3.2,
        max_gain_db: 18,
      },
      cost: 7,
    };
  }
  if (type === "mis") {
    return {
      ...base,
      radio: { tx_power_dbm: 0, antenna_gain_dbi: 0 },
      reconfigurable: {
        kind: "mis",
        num_layers: 3,
        transmission_loss_db: 4,
        focusing_gain_db: 12,
        max_gain_db: 17,
      },
      cost: 10,
    };
  }
  return {
    ...base,
    radio: { tx_power_dbm: 36, antenna_gain_dbi: 10 },
    reconfigurable: {
      kind: "ma",
      num_antennas: 8,
      movement_region_m: 2,
      codebook_gain_db: 8,
      max_gain_db: 14,
    },
    cost: 9,
  };
}

function colorFor(metric: MetricKey, value: number) {
  if (metric === "coverage") return value > 0.5 ? "rgba(8, 150, 135, 0.58)" : "rgba(226, 88, 72, 0.62)";
  if (metric === "sla_violation") return value > 0.5 ? "rgba(216, 70, 69, 0.66)" : "rgba(0, 156, 146, 0.38)";
  if (metric === "risk") {
    if (value < 0.2) return "rgba(0, 161, 151, 0.58)";
    if (value < 0.38) return "rgba(117, 190, 93, 0.54)";
    if (value < 0.58) return "rgba(245, 183, 64, 0.58)";
    return "rgba(216, 70, 69, 0.66)";
  }
  if (metric === "localization_peb") {
    if (value < 3) return "rgba(45, 107, 204, 0.58)";
    if (value < 5) return "rgba(0, 161, 151, 0.58)";
    if (value < 8) return "rgba(245, 183, 64, 0.56)";
    return "rgba(216, 70, 69, 0.66)";
  }
  if (metric === "sensing") {
    if (value > 0.82) return "rgba(45, 107, 204, 0.58)";
    if (value > 0.68) return "rgba(0, 161, 151, 0.58)";
    if (value > 0.5) return "rgba(117, 190, 93, 0.52)";
    return "rgba(245, 183, 64, 0.56)";
  }
  if (value > 220) return "rgba(45, 107, 204, 0.62)";
  if (value > 150) return "rgba(0, 145, 185, 0.60)";
  if (value > 90) return "rgba(0, 161, 151, 0.60)";
  if (value > 45) return "rgba(117, 190, 93, 0.54)";
  if (value > 20) return "rgba(245, 183, 64, 0.58)";
  return "rgba(216, 70, 69, 0.64)";
}

function isCandidate(node: NodeItem) {
  return !["ground_bs", "ground_station", "satellite_leo", "satellite_geo"].includes(node.type);
}

function formatDelta(value: number | undefined) {
  if (value === undefined) return "+0";
  return value >= 0 ? `+${value}` : `${value}`;
}

function createFallbackWorkspace(payload: DemoPayload): WorkspaceSnapshot {
  return {
    active_project: {
      id: "proj_reconfigurable_sagin_copilot",
      name: "空天地可重构网络规划智能体",
      description: "本地生产可运行骨架，面向论文、基金、横向和创业演示复用。",
      status: "local",
      scenario_count: 1,
      run_count: 2,
      job_count: 3,
    },
    active_scenario: {
      id: payload.scenario.id,
      name: payload.scenario.name,
      current_version_id: `${payload.scenario.id}_v1`,
    },
    active_scenario_version: {
      id: `${payload.scenario.id}_v1`,
      version: 1,
      notes: "离线兜底场景快照",
    },
    projects: [
      {
        id: "proj_reconfigurable_sagin_copilot",
        name: "空天地可重构网络规划智能体",
        description: "本地生产可运行骨架。",
        status: "local",
        scenario_count: 1,
        run_count: 2,
        job_count: 3,
      },
    ],
    scenarios: [
      {
        id: payload.scenario.id,
        name: payload.scenario.name,
      },
    ],
    runs: [],
    jobs: [],
    reports: [],
    model_profiles: [
      { id: "closed_form_v0", name: "L0 快速闭式模型" },
      { id: "standards_l1", name: "L1 3GPP/ITU 可追溯模型" },
      { id: "multi_fidelity_l2_adapter", name: "L2 高保真 ROI 适配器" },
    ],
    health: { db: "fallback", artifacts: "fallback" },
  };
}

function legacyAlgorithmDescriptors(_platform: PlatformCatalog): AlgorithmDescriptor[] {
  const items: Array<Pick<AlgorithmDescriptor, "id" | "name" | "category" | "description" | "maturity" | "runtime_class">> = [
    { id: "greedy_fast", name: "边际收益贪心部署", category: "deployment", description: "按边际目标收益逐步加入满足预算与节点数量约束的候选节点。", maturity: "生产可用", runtime_class: "交互级" },
    { id: "exhaustive_pareto", name: "精确 Pareto 枚举", category: "deployment", description: "枚举可行组合并提取非支配前沿，用于小规模真值校验。", maturity: "小规模精确", runtime_class: "离线级" },
    { id: "nsga2_pareto", name: "NSGA-II 多目标部署", category: "deployment", description: "用非支配排序、拥挤距离和遗传操作搜索多目标部署前沿。", maturity: "科研复现", runtime_class: "准实时" },
    { id: "robust_greedy", name: "CVaR 鲁棒贪心", category: "deployment", description: "在随机信道与硬件扰动下评估尾部风险和部署稳定性。", maturity: "科研复现", runtime_class: "离线级" },
    { id: "max_sinr", name: "Max-SINR 关联", category: "resource", description: "最强链路关联与等资源分配的可解释吞吐基线。", maturity: "生产可用", runtime_class: "毫秒级" },
    { id: "weighted_greedy", name: "需求加权资源分配", category: "resource", description: "按需求权重和链路质量快速分配带宽与功率。", maturity: "生产可用", runtime_class: "毫秒级" },
    { id: "proportional_fair", name: "比例公平调度", category: "resource", description: "联合链路质量和负载，平衡吞吐、边缘速率与公平性。", maturity: "生产可用", runtime_class: "毫秒级" },
    { id: "ucb_bandit", name: "UCB 在线关联", category: "resource", description: "在链路收益与探索之间自适应折中。", maturity: "科研复现", runtime_class: "在线级" },
    { id: "wmmse", name: "WMMSE 功率控制", category: "resource", description: "通过加权 MMSE 交替更新复现加权和速率功率优化。", maturity: "科研复现", runtime_class: "准实时" },
  ];
  return items.map((item) => ({
    ...item,
    category_name: item.category === "resource" ? "资源管控" : "部署优化",
    engine: "native",
    status: item.maturity === "生产可用" ? "stable" : "research_reproduction",
    objectives: item.category === "resource" ? ["吞吐", "公平性", "功率"] : ["覆盖", "速率", "成本"],
    parameters: item.id === "wmmse" ? { iterations: 24 } : item.id === "nsga2_pareto" ? { population_size: 18, generations: 8 } : {},
    reference: { label: "内置算法", url: "" },
  }));
}

function statusLabel(status: string) {
  if (status === "succeeded") return "完成";
  if (status === "running") return "运行中";
  if (status === "failed") return "失败";
  if (status === "canceled") return "取消";
  return "排队";
}

export default App;
