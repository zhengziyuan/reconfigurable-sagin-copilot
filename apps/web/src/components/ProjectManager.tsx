import { useEffect, useState } from "react";
import { FolderPlus, Plus, X } from "lucide-react";
import { apiRequest, errorMessage } from "../lib/api";
import type { ScenarioShape } from "../types";

interface Project { id: string; name: string; description?: string }
interface Scene { id: string; name: string; current_version_id?: string }

export function ProjectManager({ activeProjectId, scenario, selectedIds, onClose, onOpen }: {
  activeProjectId: string; scenario: ScenarioShape; selectedIds: string[];
  onClose: () => void; onOpen: (id: string) => void;
}) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [projectId, setProjectId] = useState(activeProjectId);
  const [projectName, setProjectName] = useState("");
  const [sceneName, setSceneName] = useState(`${scenario.name} 副本`);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let disposed = false;
    apiRequest("/api/projects").then((response) => response.json()).then((data) => {
      if (!disposed) { setProjects(data.projects); if (!projectId) setProjectId(data.projects[0]?.id ?? ""); }
    }).catch((failure) => { if (!disposed) setError(errorMessage(failure)); });
    return () => { disposed = true; };
  }, []);
  useEffect(() => {
    if (!projectId) return;
    let disposed = false;
    setScenes([]);
    apiRequest(`/api/projects/${encodeURIComponent(projectId)}/scenarios`).then((response) => response.json()).then((data) => {
      if (!disposed) setScenes(data.scenarios);
    }).catch((failure) => { if (!disposed) setError(errorMessage(failure)); });
    return () => { disposed = true; };
  }, [projectId]);
  const createProject = async () => {
    if (!projectName.trim()) return;
    setBusy(true); setError("");
    try {
      const response = await apiRequest("/api/projects", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: projectName.trim() }) });
      const { project } = await response.json();
      setProjects((current) => [...current, project]); setProjectId(project.id); setProjectName("");
    } catch (failure) { setError(errorMessage(failure)); } finally { setBusy(false); }
  };
  const copyScene = async () => {
    if (!projectId || !sceneName.trim()) return;
    setBusy(true); setError("");
    try {
      const copy = { ...scenario, id: `scene_${crypto.randomUUID()}`, name: sceneName.trim(), deployment: { selected_candidate_ids: selectedIds } };
      await apiRequest(`/api/projects/${encodeURIComponent(projectId)}/scenarios`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scenario: copy }) });
      onOpen(copy.id); onClose();
    } catch (failure) { setError(errorMessage(failure)); } finally { setBusy(false); }
  };
  return <div className="modal-backdrop" onClick={onClose}><section className="version-dialog project-manager" role="dialog" aria-modal="true" aria-label="项目与场景" onClick={(event) => event.stopPropagation()}>
    <div className="panel-title-row"><h2>项目与场景</h2><button className="icon-button subtle" aria-label="关闭项目管理" onClick={onClose}><X size={18} /></button></div>
    <label className="field-label">当前项目<select aria-label="项目列表" value={projectId} disabled={busy} onChange={(event) => setProjectId(event.target.value)}>{projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label>
    <form className="project-create-row" onSubmit={(event) => { event.preventDefault(); void createProject(); }}><input aria-label="新项目名称" placeholder="新项目名称" maxLength={120} value={projectName} onChange={(event) => setProjectName(event.target.value)} /><button disabled={busy || !projectName.trim()}><FolderPlus size={15} />新建项目</button></form>
    <h3>场景</h3>
    <div className="project-scene-list">{scenes.length ? scenes.map((scene) => <div className="version-row" key={scene.id}><div><strong>{scene.name}</strong><code>{scene.id}</code></div><button disabled={busy} onClick={() => { onOpen(scene.id); onClose(); }}>打开</button></div>) : <p>此项目尚无场景。</p>}</div>
    <form className="project-create-row" onSubmit={(event) => { event.preventDefault(); void copyScene(); }}><input aria-label="新场景名称" maxLength={120} value={sceneName} onChange={(event) => setSceneName(event.target.value)} /><button disabled={busy || !projectId || !sceneName.trim()}><Plus size={15} />复制当前场景</button></form>
    {error && <p className="form-error" role="alert">{error}</p>}
  </section></div>;
}
