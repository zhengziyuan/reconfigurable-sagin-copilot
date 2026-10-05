from __future__ import annotations

from typing import Any, Callable

from rsagin_core.persistence import create_job, update_job

from .executor_base import JobExecutor


class LocalSyncJobExecutor(JobExecutor):
    def __init__(self, db_path: str, *, project_id: str | None = None, scenario_id: str | None = None) -> None:
        self.db_path = db_path
        self.project_id = project_id
        self.scenario_id = scenario_id

    def submit(self, job_type: str, request: dict[str, Any], handler: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
        job = create_job(
            self.db_path,
            job_type=job_type,
            request=request,
            project_id=self.project_id or request.get("project_id"),
            scenario_id=self.scenario_id or request.get("scenario_id"),
        )
        job_id = job["job_id"]
        try:
            update_job(self.db_path, job_id, status="running", progress=12, message="任务已开始执行")
            result = handler(request)
            storage = result.get("storage", {}) if isinstance(result, dict) else {}
            return update_job(
                self.db_path,
                job_id,
                status="succeeded",
                progress=100,
                message="任务执行完成",
                result=result,
                run_id=result.get("run_id") or storage.get("run_id"),
                report_id=storage.get("report_id") or result.get("report_id"),
            )
        except Exception as exc:
            return update_job(
                self.db_path,
                job_id,
                status="failed",
                progress=100,
                message="任务执行失败",
                error=str(exc),
            )
