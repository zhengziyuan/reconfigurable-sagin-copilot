# Reconfigurable SAGIN Copilot

本轮实际运行与截图记录：[v0.8 发布验收](docs/11_v08_verification.md)。

**空天地可重构网络规划智能体 | v0.8**

面向科研、方案论证和项目演示的中文网络规划工作台。输入地理区域，组织卫星、HAPS、无人机、地面站和 RIS/MIS/MA 资产，计算性能场，比较部署及资源分配方案，并保存场景版本和运行证据。

这是**可运行的研究与产品原型**，不是经过外场标定、完整标准认证或多租户安全验收的商业产品。能力边界见 [产品审视与模型审计](docs/09_v08_product_audit.md)。较早版本文档中的计划、接口预留和“生产”措辞，不代表当前已经完成相应集成。

## 工作台

![v0.8 实际工作台](docs/design/workbench-v08.png)

- **中文交互**：紧凑工作台、移动端导航、性能场透明度、图层开关、区域定位、节点属性编辑、撤销与重做。
- **项目与场景**：新建项目、复制场景、JSON 导入导出、草稿恢复、保存版本与历史恢复。
- **GIS**：MapLibre 街道/卫星底图、EPSG:4326 区域、节点拖拽与放置、2D 性能场及 3D 指标柱体。柱体表示指标，不代表真实建筑物或地形。
- **真实结果**：覆盖、速率、定位代理 PEB、感知代理评分、风险图层；实际网格 CDF、目标达标检查和 CSV 导出。离线示例与启动预览不作为保存的运行证据。
- **部署算法**：边际收益贪心、小规模精确 Pareto、NSGA-II、贪心加 Monte Carlo/CVaR 复核。
- **资源算法**：最强链路基线、需求加权、单时隙公平启发式、UCB 探索启发式、SISO WMMSE。共享 L0/L1 链路预算内核，不是完整协议栈仿真。
- **模型增强**：ITU-R P.838-3 全频段系数公式、极化与仰角修正；球形地球 ECEF 星地斜距、仰角和可见性屏蔽；L2 未连接时明确使用 L1 回退。
- **运行证据**：仿真、优化、资源和报告保存到 SQLite/本地文件；运行绑定项目、场景和不可变版本；中文 Markdown 报告、manifest、quality 和 artifact 索引。
- **交付**：Docker Compose 一键部署、同源 API 代理、健康检查、持久化目录、GitHub Actions 测试与容器冒烟验证。

## 一键部署

Windows 需要已安装并启动 **Docker Desktop（Linux 容器）**，Linux/macOS 需要 Docker Engine 和 Compose v2。首次部署需联网下载基础镜像与依赖。

```powershell
git clone https://github.com/zhengziyuan/reconfigurable-sagin-copilot.git
cd reconfigurable-sagin-copilot
.\start.cmd
```

Linux/macOS：

```bash
git clone https://github.com/zhengziyuan/reconfigurable-sagin-copilot.git
cd reconfigurable-sagin-copilot
bash scripts/deploy.sh
```

入口：**http://127.0.0.1:8080**。数据库、场景版本、运行和报告保存在 `runs/`。停止服务不会删除这些数据。

默认只绑定本机回环地址，**没有用户登录和租户隔离，不应直接开放到公网**。本次交付包含源代码和本机一键部署，不包含付费云资源或公网托管。端口、地图服务、备份和排障详见 [部署指南](docs/10_deployment.md)。

## 开发启动

需要 Python 3.11+、Node.js 22 和 pnpm。

```powershell
.\scripts\start-dev.ps1 -Setup
```

开发前端为 http://127.0.0.1:5174，API 为 http://127.0.0.1:8000，接口文档为 http://127.0.0.1:8000/docs。端口占用时脚本报错，不覆盖其他进程；日志保存在 `runs/logs/`。

## 演示流程

1. 打开项目管理，新建项目或复制当前场景。
2. 编辑载频、带宽、天气、网格和服务目标，放置或拖拽节点。
3. 保存版本，在模型面板选择 L0 或 L1，运行仿真。
4. 在算法面板选择部署求解器或资源算法，设置参数并执行。
5. 检查实际 CDF、约束、模型假设和运行证据，导出网格或生成报告。

目前区域通过场景 JSON 的 `region.polygon` 输入，坐标顺序为 `[longitude, latitude]`。尚未实现地图多边形绘制和全球地点搜索。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest packages/rsagin-core/tests apps/api/tests -q
pnpm --dir apps/web build
```

GitHub Actions 额外构建容器，并通过网页同源代理调用一次 L1 仿真、读取保存的运行和场景版本。测试通过不代表标准全覆盖或外场精度已验证。

## 工程组织

```text
apps/api/                   FastAPI 接口、任务编排与 API 测试
apps/web/src/components/    项目管理、场景参数、结果分析
apps/web/src/hooks/         场景编辑历史
apps/web/src/gis/           地图、物理量颜色尺度
packages/rsagin-core/src/   模型、仿真、优化、资源与证据核心
configs/                   场景、模型、硬件和问题模板
scripts/                   安装、开发、一键部署、容器验证
.github/workflows/         自动测试与交付验证
docs/                      产品审计、设计、模型与部署说明
runs/                      本机持久化数据（不上传）
```

## 数据与许可

街道底图默认使用 OpenStreetMap 的尽力服务，必须遵守其 [瓦片使用政策](https://operations.osmfoundation.org/policies/tiles/)，不可据此承诺商用 SLA。默认卫星底图来自 EOX 的 2020 年影像，不是实时遥感；对外商业项目应按 [EOX 许可说明](https://cloudless.eox.at/documentation/license)取得合适授权或替换合规服务。底图变量支持自定义服务和署名。

本平台当前没有实际调用 Sionna RT、PostgreSQL、S3/MinIO、Celery 集群或外部大模型。相关代码主要为接口/适配层，详见审计矩阵。项目自身的开源许可证由项目所有者另行确定；第三方依赖、数据与标准遵循各自条款。
