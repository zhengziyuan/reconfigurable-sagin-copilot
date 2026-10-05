# 生产组件升级说明

本阶段目标是把原型从“页面演示”推进到“本地生产可运行”的工程形态。系统仍保持单机可启动，但关键模块已经具备可替换边界，后续可以平滑升级到 PostgreSQL、MinIO/S3、Celery 和 Kubernetes。

## 已完成组件

| 模块 | 当前组件 | 生产替换口 |
| --- | --- | --- |
| 后端 API | FastAPI + OpenAPI | 保持 handler 不变，接入鉴权、租户和网关 |
| 任务系统 | 本地同步 Job 表 | `rsagin_core.jobs.CeleryJobExecutor` |
| 项目数据库 | SQLite + WAL | `rsagin_core.persistence.postgres_store.PostgresPlanningStore` |
| 产物系统 | 本地 `runs/` 文件目录 | `ArtifactStore` / MinIO / S3 |
| 运行审计 | manifest v0.6 + 快照 + quality + warnings | 数据湖/对象存储索引 |
| 报告系统 | Markdown + evidence.json | DOCX/PPTX/PDF 生成器 |
| 前端 | React + Vite 中文规划工作台 | 接入 RBAC、多人协作和项目权限 |

## 数据闭环

1. 用户在中文工作台选择项目、场景版本、模型档位和求解器。
2. 前端通过任务接口触发仿真、优化、资源管控、基准或报告任务。
3. `rsagin-core` 生成性能场、优化解释、资源方案和运行质量。
4. API 写入 SQLite，并在 `runs/runs/<run_id>/` 写入 `run.json`、`summary.json`、`manifest.json`、`quality.json`、`artifacts.json` 等审计文件。
5. 报告模块基于 run-bound evidence 生成中文报告，避免脱离运行结果的空报告。

## 本地启动

```powershell
.\scripts\setup.ps1
.\.venv\Scripts\python.exe apps\api\main.py
pnpm --dir apps\web dev --host 127.0.0.1 --port 5174
```

访问：

- Web: `http://127.0.0.1:5174`
- API: `http://127.0.0.1:8000/health`
- OpenAPI: `http://127.0.0.1:8000/docs`

## 容器模式

```powershell
docker compose up --build
```

访问：

- Web: `http://127.0.0.1:8080`
- API: `http://127.0.0.1:8000/health`

## 验收口径

- `/api/workspace` 返回项目、场景、运行、任务、报告和模型档案。
- `/api/jobs/simulate`、`/api/jobs/optimize`、`/api/jobs/report` 写入任务状态并生成运行/报告产物。
- `/api/candidates/generate` 能生成 RIS/MIS/MA/低空平台候选点。
- `/api/copilot/ask` 在绑定 run_id 时返回证据约束回答。
- 前端默认进入“规划工作台”，顶栏、左侧工具、快捷任务和报告按钮均可交互。
- `pytest packages/rsagin-core/tests/test_core.py` 通过。
