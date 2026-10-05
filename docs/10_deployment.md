# 一键部署与运行

## Windows

前提：Docker Desktop 已运行且使用 Linux 容器；可找到 `docker`；Compose v2 支持 `--wait`。脚本不会安装 Docker、修改系统权限、关闭防火墙或创建付费云资源。

项目根目录双击 `start.cmd`，或：

```powershell
.\scripts\deploy.ps1
```

脚本构建 Web/API 镜像、启动、等待健康检查并打开 http://127.0.0.1:8080。无浏览器启动使用 `-NoBrowser`；停止使用 `-Stop`，不删除数据。

## Linux/macOS

```bash
bash scripts/deploy.sh
```

停止使用 `docker compose down`。默认持久化为 `runs/`。

## 端口与配置

可将 `.env.example` 复制为根目录 `.env` 并修改：

```dotenv
RSAGIN_WEB_PORT=8080
```

Web 只暴露在 `127.0.0.1`；API 不发布主机端口，只供 Compose 内部 `api:8000` 访问。Web 的 `/api` 和 `/health` 由 Nginx 代理，浏览器不连接自己的 `localhost:8000`，也不会与开发 API 的 8000 端口冲突。

地图 URL 与署名在构建时生效，修改后重新部署。不要把秘密令牌写进 `VITE_*`，它们会进入公开代码；供应商提供的受域名限制的公开地图令牌另行配置。

默认卫星图是 2020 年 EOX 数据，不是当前实景。交付前按 [OSM 政策](https://operations.osmfoundation.org/policies/tiles/)和 [EOX 许可](https://cloudless.eox.at/documentation/license)替换合适服务。不要对公共 OSM 服务做城市级预取。

## 开发

```powershell
.\scripts\start-dev.ps1 -Setup
```

开发端口 5174 / 8000；日志 `runs/logs`。已安装依赖时去掉 `-Setup`。端口占用时拒绝继续；先确认冲突程序归属，不要盲目结束进程。

## 检查

```powershell
docker compose ps
docker compose logs --tail 100
python scripts/container_smoke.py
```

`/health` 返回 `status=ok`、`version=0.8.0`。地图空白时检查 WebGL、网络与配置。镜像构建因网络失败，保留日志，恢复后重新执行。

## 数据与升级

`runs/` 包含 SQLite、运行、快照、manifest 和报告，不进入 GitHub。更新/重建不删除它。备份前停止写入，再备份整个目录；恢复前停止服务。当前没有在线一致性备份和灾难恢复演练。

## 公网边界

单用户本地服务没有登录、RBAC、租户隔离或完整限流。不要把端口改为 `0.0.0.0` 直接上线；公网还需要 TLS、访问控制、配额和审计。本次发布不创建公网演示域名。
