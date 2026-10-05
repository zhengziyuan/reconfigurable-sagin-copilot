from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.6"
DEFAULT_PROJECT_ID = "proj_reconfigurable_sagin_copilot"


def initialize_store(db_path: str | Path) -> Path:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                owner TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scenarios (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                current_version_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL,
                FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scenario_versions (
                id TEXT PRIMARY KEY,
                scenario_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                author TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                manifest_hash TEXT NOT NULL,
                notes TEXT NOT NULL,
                FOREIGN KEY(scenario_id) REFERENCES scenarios(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                scenario_id TEXT NOT NULL,
                scenario_version_id TEXT,
                run_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'succeeded',
                model_profile TEXT,
                created_at TEXT NOT NULL,
                finished_at TEXT,
                summary_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                artifact_dir TEXT,
                manifest_path TEXT,
                artifact_root TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                path TEXT NOT NULL,
                sha256 TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                scenario_id TEXT,
                scenario_version_id TEXT,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                progress REAL NOT NULL,
                message TEXT NOT NULL,
                request_json TEXT NOT NULL,
                result_json TEXT,
                run_id TEXT,
                report_id TEXT,
                error TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS job_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                run_id TEXT,
                scenario_id TEXT NOT NULL,
                template TEXT NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                evidence_json TEXT NOT NULL DEFAULT '{}',
                markdown TEXT NOT NULL,
                artifact_path TEXT
            )
            """
        )
        _ensure_columns(
            conn,
            "runs",
            {
                "project_id": "TEXT",
                "scenario_version_id": "TEXT",
                "status": "TEXT NOT NULL DEFAULT 'succeeded'",
                "finished_at": "TEXT",
                "manifest_path": "TEXT",
                "artifact_root": "TEXT",
            },
        )
        _ensure_columns(conn, "artifacts", {"sha256": "TEXT"})
        _ensure_columns(conn, "reports", {"project_id": "TEXT", "evidence_json": "TEXT NOT NULL DEFAULT '{}'"})
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )
    return path


def seed_demo_workspace(db_path: str | Path, scenario_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    now = _now()
    scenario_payload = scenario_payload or {}
    scenario_id = str(scenario_payload.get("id") or "demo_low_altitude_emergency")
    scenario_name = str(scenario_payload.get("name") or "低空应急空天地协同示范区")
    scenario_description = str(
        scenario_payload.get("description") or "面向低空园区、应急保障和通感一体化的可重构 SAGIN 规划场景。"
    )
    version_id = f"{scenario_id}_v1"
    manifest_hash = _sha256_json(scenario_payload or {"id": scenario_id})
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO projects(
                id, name, description, owner, status, created_at, updated_at, metadata_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                DEFAULT_PROJECT_ID,
                "空天地可重构网络规划智能体",
                "面向论文、基金、横向和创业演示复用的 SAGIN 规划工程底座。",
                "local",
                "active",
                now,
                now,
                _json(
                    {
                        "stage": "local-production",
                        "language": "zh-CN",
                        "delivery_modes": ["paper", "grant", "enterprise", "startup"],
                    }
                ),
            ),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO scenarios(
                id, project_id, name, description, current_version_id, created_at,
                updated_at, payload_json, metadata_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_id,
                DEFAULT_PROJECT_ID,
                scenario_name,
                scenario_description,
                version_id,
                now,
                now,
                _json(scenario_payload),
                _json({"source": "configs/scenarios/demo_low_altitude_emergency.yaml", "reproducible": True}),
            ),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO scenario_versions(
                id, scenario_id, version, created_at, author, payload_json, manifest_hash, notes
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (version_id, scenario_id, 1, now, "system", _json(scenario_payload), manifest_hash, "默认演示场景快照"),
        )
        conn.execute(
            "UPDATE scenarios SET current_version_id = ?, updated_at = ? WHERE id = ?",
            (version_id, now, scenario_id),
        )
    return {
        "project_id": DEFAULT_PROJECT_ID,
        "scenario_id": scenario_id,
        "scenario_version_id": version_id,
    }


def list_projects(db_path: str | Path) -> list[dict[str, Any]]:
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT p.*,
                   (SELECT COUNT(*) FROM scenarios s WHERE s.project_id = p.id) AS scenario_count,
                   (SELECT COUNT(*) FROM runs r WHERE r.project_id = p.id) AS run_count,
                   (SELECT COUNT(*) FROM jobs j WHERE j.project_id = p.id) AS job_count
            FROM projects p
            ORDER BY p.updated_at DESC
            """
        ).fetchall()
    return [_project_from_row(row) for row in rows]


def create_project(
    db_path: str | Path,
    *,
    name: str,
    description: str = "",
    owner: str = "local",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _now()
    project_id = _slug_id("proj", name)
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO projects(id, name, description, owner, status, created_at, updated_at, metadata_json)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (project_id, name, description, owner, "active", now, now, _json(metadata or {})),
        )
    return get_project(db_path, project_id)


def get_project(db_path: str | Path, project_id: str) -> dict[str, Any] | None:
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return _project_from_row(row) if row else None


def list_project_scenarios(db_path: str | Path, project_id: str | None = None) -> list[dict[str, Any]]:
    db = initialize_store(db_path)
    sql = "SELECT * FROM scenarios"
    params: tuple[Any, ...] = ()
    if project_id:
        sql += " WHERE project_id = ?"
        params = (project_id,)
    sql += " ORDER BY updated_at DESC"
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return [_scenario_from_row(row) for row in rows]


def create_scenario(
    db_path: str | Path,
    *,
    project_id: str,
    scenario_payload: dict[str, Any],
    author: str = "local",
    notes: str = "手动创建场景",
) -> dict[str, Any]:
    now = _now()
    scenario_id = str(scenario_payload.get("id") or _slug_id("scenario", scenario_payload.get("name", "scenario")))
    version_id = f"{scenario_id}_v1"
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO scenarios(
                id, project_id, name, description, current_version_id, created_at,
                updated_at, payload_json, metadata_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_id,
                project_id,
                str(scenario_payload.get("name") or scenario_id),
                str(scenario_payload.get("description") or ""),
                version_id,
                now,
                now,
                _json(scenario_payload),
                _json({}),
            ),
        )
        conn.execute(
            """
            INSERT INTO scenario_versions(
                id, scenario_id, version, created_at, author, payload_json, manifest_hash, notes
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (version_id, scenario_id, 1, now, author, _json(scenario_payload), _sha256_json(scenario_payload), notes),
        )
    return get_scenario(db_path, scenario_id) or {}


def get_scenario(db_path: str | Path, scenario_id: str) -> dict[str, Any] | None:
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,)).fetchone()
    return _scenario_from_row(row) if row else None


def create_scenario_version(
    db_path: str | Path,
    *,
    scenario_id: str,
    scenario_payload: dict[str, Any],
    author: str = "local",
    notes: str = "场景更新",
) -> dict[str, Any]:
    now = _now()
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM scenario_versions WHERE scenario_id = ?", (scenario_id,)).fetchone()[0]
        version = int(current) + 1
        version_id = f"{scenario_id}_v{version}"
        conn.execute(
            """
            INSERT INTO scenario_versions(
                id, scenario_id, version, created_at, author, payload_json, manifest_hash, notes
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (version_id, scenario_id, version, now, author, _json(scenario_payload), _sha256_json(scenario_payload), notes),
        )
        conn.execute(
            """
            UPDATE scenarios
            SET name = ?, description = ?, current_version_id = ?, updated_at = ?, payload_json = ?
            WHERE id = ?
            """,
            (
                str(scenario_payload.get("name") or scenario_id),
                str(scenario_payload.get("description") or ""),
                version_id,
                now,
                _json(scenario_payload),
                scenario_id,
            ),
        )
    return get_scenario_version(db_path, version_id) or {}


def list_scenario_versions(db_path: str | Path, scenario_id: str) -> list[dict[str, Any]]:
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM scenario_versions WHERE scenario_id = ? ORDER BY version DESC",
            (scenario_id,),
        ).fetchall()
    return [_scenario_version_from_row(row) for row in rows]


def get_scenario_version(db_path: str | Path, version_id: str) -> dict[str, Any] | None:
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM scenario_versions WHERE id = ?", (version_id,)).fetchone()
    return _scenario_version_from_row(row) if row else None


def resolve_workspace_context(
    db_path: str | Path,
    *,
    project_id: str | None = None,
    scenario_id: str | None = None,
    scenario_version_id: str | None = None,
) -> dict[str, Any]:
    projects = list_projects(db_path)
    if not projects:
        seed_demo_workspace(db_path)
        projects = list_projects(db_path)
    project = get_project(db_path, project_id) if project_id else projects[0]
    if not project:
        project = projects[0]
    scenarios = list_project_scenarios(db_path, project["id"])
    scenario = get_scenario(db_path, scenario_id) if scenario_id else (scenarios[0] if scenarios else None)
    version = None
    if scenario_version_id:
        version = get_scenario_version(db_path, scenario_version_id)
    elif scenario:
        version = get_scenario_version(db_path, str(scenario.get("current_version_id") or ""))
    return {
        "project": project,
        "scenario": scenario,
        "scenario_version": version,
        "projects": projects,
        "scenarios": scenarios,
    }


def save_run(
    db_path: str | Path,
    run_payload: Any,
    *,
    run_type: str,
    scenario_id: str | None = None,
    run_id: str | None = None,
    project_id: str | None = None,
    scenario_version_id: str | None = None,
    status: str = "succeeded",
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    payload = _to_jsonable(run_payload)
    resolved_run_id = run_id or _pick(payload, "run_id") or _pick(payload, "optimized_run.run_id") or _timestamp_id(run_type)
    resolved_scenario_id = scenario_id or _pick(payload, "scenario_id") or _pick(payload, "optimized_run.scenario_id") or "scenario"
    context = resolve_workspace_context(db_path, project_id=project_id, scenario_id=resolved_scenario_id, scenario_version_id=scenario_version_id)
    resolved_project_id = project_id or (context.get("project") or {}).get("id")
    resolved_version_id = scenario_version_id or (context.get("scenario_version") or {}).get("id")
    model_profile = _pick(payload, "model_profile") or _pick(payload, "optimized_run.model_profile")
    summary = _pick(payload, "summary") or _pick(payload, "optimized_run.summary") or {}
    created_at = _now()
    finished_at = created_at if status in {"succeeded", "failed", "canceled"} else None
    artifact_dir = _write_run_artifacts(
        artifact_root,
        resolved_run_id,
        payload,
        summary,
        run_type=run_type,
        project_id=resolved_project_id,
        scenario_id=resolved_scenario_id,
        scenario_version_id=resolved_version_id,
        model_profile=str(model_profile or ""),
    )
    manifest_path = artifact_dir / "manifest.json" if artifact_dir else None

    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO runs(
                id, project_id, scenario_id, scenario_version_id, run_type, status,
                model_profile, created_at, finished_at, summary_json, payload_json,
                artifact_dir, manifest_path, artifact_root
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_run_id,
                resolved_project_id,
                resolved_scenario_id,
                resolved_version_id,
                run_type,
                status,
                str(model_profile or ""),
                created_at,
                finished_at,
                _json(summary),
                _json(payload),
                str(artifact_dir) if artifact_dir else None,
                str(manifest_path) if manifest_path else None,
                str(artifact_root) if artifact_root else None,
            ),
        )
        if artifact_dir:
            for artifact_path in sorted(artifact_dir.iterdir()):
                if artifact_path.is_file():
                    conn.execute(
                        """
                        INSERT INTO artifacts(run_id, artifact_type, path, sha256, created_at)
                        VALUES(?, ?, ?, ?, ?)
                        """,
                        (resolved_run_id, artifact_path.stem, str(artifact_path), _sha256_file(artifact_path), created_at),
                    )
    return {
        "run_id": resolved_run_id,
        "project_id": resolved_project_id,
        "scenario_id": resolved_scenario_id,
        "scenario_version_id": resolved_version_id,
        "run_type": run_type,
        "status": status,
        "model_profile": model_profile,
        "created_at": created_at,
        "artifact_dir": str(artifact_dir) if artifact_dir else None,
        "manifest_path": str(manifest_path) if manifest_path else None,
    }


def get_run(db_path: str | Path, run_id: str) -> dict[str, Any] | None:
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        artifacts = conn.execute(
            "SELECT artifact_type, path, sha256, created_at FROM artifacts WHERE run_id = ? ORDER BY artifact_type",
            (run_id,),
        ).fetchall()
    if not row:
        return None
    run = _run_from_row(row)
    run["artifacts"] = [dict(item) for item in artifacts]
    return run


def list_runs(
    db_path: str | Path,
    limit: int = 20,
    *,
    project_id: str | None = None,
    scenario_id: str | None = None,
) -> list[dict[str, Any]]:
    db = initialize_store(db_path)
    sql = """
        SELECT id, project_id, scenario_id, scenario_version_id, run_type, status,
               model_profile, created_at, finished_at, summary_json, artifact_dir, manifest_path
        FROM runs
    """
    filters: list[str] = []
    params: list[Any] = []
    if project_id:
        filters.append("project_id = ?")
        params.append(project_id)
    if scenario_id:
        filters.append("scenario_id = ?")
        params.append(scenario_id)
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [_run_from_row(row) for row in rows]


def create_job(
    db_path: str | Path,
    *,
    job_type: str,
    request: dict[str, Any] | None = None,
    project_id: str | None = None,
    scenario_id: str | None = None,
    scenario_version_id: str | None = None,
    message: str = "已进入本地任务队列",
) -> dict[str, Any]:
    now = _now()
    job_id = _timestamp_id(f"job_{job_type}")
    context = resolve_workspace_context(db_path, project_id=project_id, scenario_id=scenario_id, scenario_version_id=scenario_version_id)
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO jobs(
                id, project_id, scenario_id, scenario_version_id, job_type, status,
                created_at, started_at, finished_at, progress, message,
                request_json, result_json, run_id, report_id, error
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                project_id or (context.get("project") or {}).get("id"),
                scenario_id or (context.get("scenario") or {}).get("id"),
                scenario_version_id or (context.get("scenario_version") or {}).get("id"),
                job_type,
                "queued",
                now,
                None,
                None,
                0.0,
                message,
                _json(request or {}),
                None,
                None,
                None,
                None,
            ),
        )
    append_job_log(db_path, job_id, "info", message, {"status": "queued"})
    return get_job(db_path, job_id) or {}


def update_job(
    db_path: str | Path,
    job_id: str,
    *,
    status: str | None = None,
    progress: float | None = None,
    message: str | None = None,
    result: dict[str, Any] | None = None,
    run_id: str | None = None,
    report_id: str | None = None,
    error: str | None = None,
    project_id: str | None = None,
    scenario_id: str | None = None,
    scenario_version_id: str | None = None,
) -> dict[str, Any]:
    job = get_job(db_path, job_id)
    if not job:
        raise KeyError(f"job not found: {job_id}")
    updates: list[str] = []
    params: list[Any] = []
    now = _now()
    for column, value in (("project_id", project_id), ("scenario_id", scenario_id), ("scenario_version_id", scenario_version_id)):
        if value is not None:
            updates.append(f"{column} = ?")
            params.append(value)
    if status is not None:
        updates.append("status = ?")
        params.append(status)
        if status == "running" and not job.get("started_at"):
            updates.append("started_at = ?")
            params.append(now)
        if status in {"succeeded", "failed", "canceled"}:
            updates.append("finished_at = ?")
            params.append(now)
    if progress is not None:
        updates.append("progress = ?")
        params.append(float(progress))
    if message is not None:
        updates.append("message = ?")
        params.append(message)
    if result is not None:
        updates.append("result_json = ?")
        params.append(_json(result))
    if run_id is not None:
        updates.append("run_id = ?")
        params.append(run_id)
    if report_id is not None:
        updates.append("report_id = ?")
        params.append(report_id)
    if error is not None:
        updates.append("error = ?")
        params.append(error)
    if not updates:
        return job
    params.append(job_id)
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?", tuple(params))
    if message:
        append_job_log(db_path, job_id, "info" if status != "failed" else "error", message, {"status": status, "progress": progress})
    return get_job(db_path, job_id) or {}


def append_job_log(
    db_path: str | Path,
    job_id: str,
    level: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT INTO job_logs(job_id, created_at, level, message, payload_json)
            VALUES(?, ?, ?, ?, ?)
            """,
            (job_id, _now(), level, message, _json(payload or {})),
        )


def get_job(db_path: str | Path, job_id: str) -> dict[str, Any] | None:
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _job_from_row(row) if row else None


def list_jobs(
    db_path: str | Path,
    limit: int = 50,
    *,
    project_id: str | None = None,
    status: str | None = None,
    include_details: bool = True,
) -> list[dict[str, Any]]:
    db = initialize_store(db_path)
    columns = "*" if include_details else "id, project_id, scenario_id, scenario_version_id, job_type, status, message, progress, created_at, started_at, finished_at, run_id, report_id, error"
    sql = f"SELECT {columns} FROM jobs"
    filters: list[str] = []
    params: list[Any] = []
    if project_id:
        filters.append("project_id = ?")
        params.append(project_id)
    if status:
        filters.append("status = ?")
        params.append(status)
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [_job_from_row(row) for row in rows]


def get_job_log(db_path: str | Path, job_id: str) -> list[dict[str, Any]]:
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT created_at, level, message, payload_json FROM job_logs WHERE job_id = ? ORDER BY id",
            (job_id,),
        ).fetchall()
    return [
        {
            "created_at": row["created_at"],
            "level": row["level"],
            "message": row["message"],
            "payload": _loads(row["payload_json"]),
        }
        for row in rows
    ]


def save_report(
    db_path: str | Path,
    report_payload: dict[str, Any],
    *,
    project_id: str | None = None,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    payload = _to_jsonable(report_payload)
    run_id = str(payload.get("run_id") or "report")
    scenario_id = str(payload.get("scenario_id") or "scenario")
    context = resolve_workspace_context(db_path, project_id=project_id, scenario_id=scenario_id)
    resolved_project_id = project_id or (context.get("project") or {}).get("id")
    template = str(payload.get("template") or "enterprise")
    report_id = f"report_{template}_{run_id}"
    title = _template_title(template, scenario_id)
    created_at = _now()
    evidence = _extract_report_evidence(payload)
    markdown = _report_markdown(payload, title, evidence)
    artifact_path: Path | None = None
    if artifact_root:
        report_dir = Path(artifact_root) / "reports" / report_id
        report_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = report_dir / "report.md"
        artifact_path.write_text(markdown, encoding="utf-8")
        (report_dir / "report.json").write_text(_json(payload, indent=2), encoding="utf-8")
        (report_dir / "evidence.json").write_text(_json(evidence, indent=2), encoding="utf-8")

    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO reports(
                id, project_id, run_id, scenario_id, template, title, created_at,
                payload_json, evidence_json, markdown, artifact_path
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                resolved_project_id,
                run_id,
                scenario_id,
                template,
                title,
                created_at,
                _json(payload),
                _json(evidence),
                markdown,
                str(artifact_path) if artifact_path else None,
            ),
        )
    return {
        "report_id": report_id,
        "project_id": resolved_project_id,
        "run_id": run_id,
        "scenario_id": scenario_id,
        "template": template,
        "title": title,
        "created_at": created_at,
        "artifact_path": str(artifact_path) if artifact_path else None,
        "evidence": evidence,
        "markdown": markdown,
    }


def list_reports(db_path: str | Path, limit: int = 20, *, project_id: str | None = None) -> list[dict[str, Any]]:
    db = initialize_store(db_path)
    sql = "SELECT id, project_id, run_id, scenario_id, template, title, created_at, artifact_path FROM reports"
    params: list[Any] = []
    if project_id:
        sql += " WHERE project_id = ?"
        params.append(project_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(int(limit))
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [dict(row) for row in rows]


def get_report(db_path: str | Path, report_id: str) -> dict[str, Any] | None:
    db = initialize_store(db_path)
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if not row:
        return None
    return {
        "report_id": row["id"],
        "project_id": row["project_id"],
        "run_id": row["run_id"],
        "scenario_id": row["scenario_id"],
        "template": row["template"],
        "title": row["title"],
        "created_at": row["created_at"],
        "payload": _loads(row["payload_json"]),
        "evidence": _loads(row["evidence_json"]),
        "markdown": row["markdown"],
        "artifact_path": row["artifact_path"],
    }


def get_report_evidence(db_path: str | Path, report_id: str) -> dict[str, Any] | None:
    report = get_report(db_path, report_id)
    return report.get("evidence") if report else None


def _write_run_artifacts(
    artifact_root: str | Path | None,
    run_id: str,
    payload: dict[str, Any],
    summary: dict[str, Any],
    *,
    run_type: str,
    project_id: str | None,
    scenario_id: str | None,
    scenario_version_id: str | None,
    model_profile: str,
) -> Path | None:
    if artifact_root is None:
        return None
    run_dir = Path(artifact_root) / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    run_payload = _json(payload, indent=2)
    summary_payload = _json(summary, indent=2)
    (run_dir / "run.json").write_text(run_payload, encoding="utf-8")
    (run_dir / "summary.json").write_text(summary_payload, encoding="utf-8")

    base_manifest = summary.get("run_manifest") if isinstance(summary.get("run_manifest"), dict) else {}
    manifest = {
        **base_manifest,
        "manifest_version": SCHEMA_VERSION,
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "project_id": project_id,
        "scenario_id": scenario_id,
        "scenario_version_id": scenario_version_id,
        "run_id": run_id,
        "run_type": run_type,
        "model_profile": model_profile,
        "payload_sha256": _sha256_text(run_payload),
        "summary_sha256": _sha256_text(summary_payload),
        "audit_contract": {
            "scenario_snapshot": "scenario_snapshot.json",
            "model_profile_snapshot": "model_profile_snapshot.json",
            "optimization_profile_snapshot": "optimization_profile_snapshot.json",
            "hardware_catalog_snapshot": "hardware_catalog_snapshot.json",
            "quality": "quality.json",
            "assumptions": "assumptions.json",
            "warnings": "warnings.json",
        },
        "artifact_schema": {
            "required": [
                "run.json",
                "summary.json",
                "manifest.json",
                "scenario_snapshot.json",
                "model_profile_snapshot.json",
                "optimization_profile_snapshot.json",
                "hardware_catalog_snapshot.json",
                "quality.json",
                "assumptions.json",
                "warnings.json",
                "artifacts.json",
            ],
            "optional": ["figures", "tables", "reports", "geo"],
        },
    }
    scenario_snapshot = payload.get("scenario") or payload.get("scenario_snapshot") or {"scenario_id": scenario_id}
    model_profile_snapshot = payload.get("model_profile_snapshot") or base_manifest.get("model_profile") or {"id": model_profile}
    optimization_snapshot = payload.get("optimization_profile_snapshot") or {
        "solver": summary.get("solver"),
        "constraint_status": summary.get("constraint_status"),
        "optimization_status": summary.get("optimization_status"),
    }
    hardware_snapshot = payload.get("hardware_catalog_snapshot") or {"selected_candidate_ids": payload.get("selected_candidate_ids", [])}
    quality = summary.get("run_quality") or payload.get("run_quality") or {"status": "unknown"}
    assumptions = payload.get("assumptions") or payload.get("optimized_run", {}).get("assumptions") or []
    warnings = summary.get("model_warnings") or summary.get("warnings") or []

    files = {
        "manifest.json": manifest,
        "scenario_snapshot.json": scenario_snapshot,
        "model_profile_snapshot.json": model_profile_snapshot,
        "optimization_profile_snapshot.json": optimization_snapshot,
        "hardware_catalog_snapshot.json": hardware_snapshot,
        "quality.json": quality,
        "assumptions.json": {"items": assumptions},
        "warnings.json": {"items": warnings},
    }
    for filename, data in files.items():
        (run_dir / filename).write_text(_json(data, indent=2), encoding="utf-8")
    artifacts = [
        {"name": item.name, "path": str(item), "sha256": _sha256_file(item)}
        for item in sorted(run_dir.iterdir())
        if item.is_file() and item.name != "artifacts.json"
    ]
    (run_dir / "artifacts.json").write_text(_json({"items": artifacts}, indent=2), encoding="utf-8")
    return run_dir


def _extract_report_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return {
        "run_id": payload.get("run_id"),
        "scenario_id": payload.get("scenario_id"),
        "model_profile": payload.get("model_profile"),
        "template": payload.get("template"),
        "sections": payload.get("sections", []),
        "assumption_count": len(payload.get("assumptions", []) or []),
        "limitation_count": len(payload.get("limitations", []) or []),
        "summary_refs": {
            key: summary.get(key)
            for key in [
                "coverage_percent",
                "avg_rate_mbps",
                "p5_rate_mbps",
                "p95_peb_m",
                "avg_sensing_score",
                "selected_cost",
                "objective_score",
            ]
            if key in summary
        },
        "evidence_policy": "所有结论必须绑定 run_id、scenario_id、model_profile 和可复现 artifact。",
    }


def _template_title(template: str, scenario_id: str) -> str:
    titles = {
        "research": "科研论文实验报告",
        "enterprise": "空天地可重构网络规划交付报告",
        "grant": "基金/项目申请支撑报告",
    }
    return f"{titles.get(template, '规划报告')} - {scenario_id}"


def _report_markdown(payload: dict[str, Any], title: str, evidence: dict[str, Any]) -> str:
    sections = payload.get("sections") or []
    section_text = "\n".join(f"## {item}\n\n本节与 run `{payload.get('run_id', '')}` 绑定，图表、表格和结论需要从对应 artifact 追溯。\n" for item in sections)
    limitations = "\n".join(f"- {item}" for item in payload.get("limitations", []))
    assumptions = "\n".join(f"- {item}" for item in payload.get("assumptions", []))
    refs = "\n".join(f"- {key}: {value}" for key, value in evidence.get("summary_refs", {}).items())
    return f"""# {title}

运行编号：`{payload.get("run_id", "")}`

模型档位：`{payload.get("model_profile", "")}`

## 执行摘要

{payload.get("executive_summary", "")}

## 证据绑定

- 场景编号：`{payload.get("scenario_id", "")}`
- 报告模板：`{payload.get("template", "")}`
- 证据策略：{evidence.get("evidence_policy", "")}

{refs or "- 暂无关键指标引用。"}

## 模型假设

{assumptions or "- 未记录。"}

{section_text}
## 局限与风险

{limitations or "- 未记录。"}
"""


def _project_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    metadata_json = data.pop("metadata_json", "{}")
    data["metadata"] = _loads(metadata_json)
    return data


def _scenario_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["payload"] = _loads(data.pop("payload_json", "{}"))
    data["metadata"] = _loads(data.pop("metadata_json", "{}"))
    return data


def _scenario_version_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["payload"] = _loads(data.pop("payload_json", "{}"))
    return data


def _run_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["run_id"] = data.pop("id")
    data["summary"] = _loads(data.pop("summary_json", "{}"))
    if "payload_json" in data:
        data["payload"] = _loads(data.pop("payload_json", "{}"))
    return data


def _job_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["job_id"] = data.pop("id")
    data["request"] = _loads(data.pop("request_json", "{}"))
    result_json = data.pop("result_json", None)
    data["result"] = _loads(result_json) if result_json else None
    return data


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _to_jsonable(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _pick(payload: dict[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for key in dotted_path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _timestamp_id(prefix: str) -> str:
    return f"{prefix}_{int(datetime.now(timezone.utc).timestamp() * 1000)}"


def _slug_id(prefix: str, value: Any) -> str:
    text = str(value or prefix).lower()
    safe = "".join(ch if ch.isalnum() else "_" for ch in text).strip("_")[:48] or prefix
    suffix = hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:8]
    return f"{prefix}_{safe}_{suffix}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any, *, indent: int | None = None) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, indent=indent)


def _loads(value: str | None) -> Any:
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def _sha256_json(value: Any) -> str:
    return _sha256_text(_json(value))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
