# Reconfigurable SAGIN Copilot Project Blueprint

中文名：空天地可重构网络规划智能体

## 1. Project Positioning

This project should not start as another isolated simulation script. It should start as a reusable planning platform prototype for papers, grants, enterprise projects, and future productization.

The first product sentence:

> Reconfigurable SAGIN Copilot is a digital-twin-based planning and optimization prototype for space-air-ground integrated networks, where satellites, aerial platforms, terrestrial stations, and reconfigurable electromagnetic nodes such as RIS, MIS, and movable antennas can be jointly deployed, simulated, visualized, optimized, and explained.

中文定位：

> 空天地可重构网络规划智能体面向卫星、低空平台、地面站、智能超表面、层叠超表面和可移动天线等异构可重构节点，构建区域级网络数字孪生、性能评估与智能优化闭环，实现覆盖、容量、定位精度和感知性能的可视化预测与部署调度建议。

## 2. First Demonstration Loop

The first version must complete an end-to-end loop:

1. Choose or load a region.
2. Generate a ground grid, demand weights, candidate deployment sites, and target points.
3. Place fixed and candidate nodes: LEO/GEO, HAPS/UAV, ground station/base station, RIS, MIS, MA, users, targets.
4. Simulate baseline coverage, rate, localization PEB, and sensing score.
5. Optimize deployment under budget and node-count constraints.
6. Compare baseline and optimized results.
7. Explain the bottlenecks, recommendations, trade-offs, and residual blind spots.
8. Export run artifacts and a report.

This loop is the strategic asset. After it is stable, 3GPP, ITU, Sionna RT, hardware measurement LUTs, multi-objective solvers, and reinforcement learning can be plugged in as higher-fidelity engines.

## 3. Architecture

```text
User / Demo Layer
  - Web app: map, 3D/digital-twin canvas, heatmaps, node editing, Copilot, reports
  - CLI / notebooks: paper reproducibility, batch experiments, publication figures

API Layer
  - Scenario API: region, nodes, tasks, constraints
  - Simulation API: coverage, rate, localization, sensing
  - Optimization API: deployment, scheduling, trajectory, codebook planning
  - Copilot API: natural-language planning, tool calls, explanations
  - Artifact API: GeoJSON, heatmaps, run folders, reports

Core Engine Layer
  - Geo / Scenario Engine
  - Mobility / Orbit Engine
  - Channel Engine
  - Metric Engine
  - Optimization Engine
  - Copilot / Explanation Engine
  - Report Engine

Data Layer
  - Config files for reproducible scenarios and profiles
  - Run registry with config, model version, assumptions, seed, and artifacts
  - PostGIS later for production spatial state
  - Object/file storage later for Parquet, GeoJSON, figures, reports
```

## 4. Recommended Technical Stack

MVP stack:

- Frontend: React, Vite, TypeScript, SVG/HTML canvas-style digital twin.
- Backend: Python, FastAPI, Pydantic, NumPy.
- Core: package-first Python modules, CLI-first reproducibility.
- Config: YAML scenario/profile files.
- Dev: PowerShell helpers for Windows, pytest, pnpm.

Growth stack:

- Map and large layer rendering: deck.gl, MapLibre, CesiumJS.
- GIS: GeoPandas, Shapely, PyProj, H3, PostGIS.
- Satellite orbit: Skyfield, SGP4, CelesTrak TLE ingestion.
- Optimization: OR-Tools, CVXPY, Pyomo, pymoo.
- High fidelity radio: 3GPP NTN model profiles, ITU-R earth-space propagation, Sionna RT.
- Parallel/batch: Ray or Dask.
- Reports: Markdown first, then PDF/PPT export.

## 5. Model Fidelity Levels

Every result should carry a model profile and fidelity level.

### Level 0: Closed-Form Demonstration Model

Purpose: fast, stable, explainable demo and system testing.

Includes:

- free-space path loss,
- simplified LoS/NLoS losses,
- simplified RIS/MIS/MA gain,
- Shannon-style rate,
- geometry and SNR weighted PEB proxy,
- simplified sensing score,
- greedy deployment optimization.

### Level 1: Standardized Communication Model

Adds:

- 3GPP NTN and terrestrial channel profiles,
- ITU-R earth-space propagation,
- HAPS/UAV air-ground profiles,
- satellite pass windows and beam constraints.

### Level 2: Scene-Level Ray-Tracing Model

Adds:

- buildings, materials, reflection, diffraction, blockage,
- Sionna RT adapter,
- scenario-level propagation digital twin.

### Level 3: Measurement-Calibrated Hardware Digital Twin

Adds:

- hardware LUTs or neural surrogates for RIS/MIS/MA response,
- uncertainty propagation,
- robust deployment optimization,
- field measurement calibration loop.

## 6. MVP Scenario

Recommended first demo:

```text
Low-altitude emergency communication, localization, and sensing enhancement
Region: 2 km x 2 km urban-industrial / campus / emergency area
Existing assets:
  - one ground base station
  - one ground station
  - one simplified LEO pass
Candidate assets:
  - RIS/MIS facade nodes
  - UAV relay candidate hover points
  - MA array candidate positions
Goals:
  - improve coverage blind spots
  - improve 5% edge rate
  - reduce localization PEB
  - increase sensing score
  - control cost
```

## 7. Shared Outputs

One codebase supports several output forms:

- Paper: reproducible scenarios, ablations, heatmaps, Pareto curves, algorithm comparisons.
- Grant: system architecture, scientific questions, prototype screenshots, validation pipeline.
- Enterprise project: customer-region planning, deployment suggestions, cost-benefit reports.
- Startup product: planning software, private-network design tool, reconfigurable node control platform.

## 8. Strategic Research Directions

The strongest original contributions are likely to be:

1. uncertainty-aware modeling of reconfigurable electromagnetic nodes,
2. multi-objective planning across coverage, capacity, localization, sensing, and cost,
3. AI-native planning workflow that invokes tools instead of inventing results,
4. hardware-measurement closed loop for RIS/MIS/MA calibration,
5. reusable scenario and model-profile registry for repeatable experiments.

## 9. Anti-Patterns To Avoid

- Do not start with full ray tracing before the planning loop works.
- Do not let AI directly fabricate coverage or rate numbers.
- Do not put core logic only in notebooks.
- Do not run simulations without model version, seed, and assumptions.
- Do not mix units casually: dBm/W, Hz/GHz, m/km, LLA/ECEF/ENU, dB/linear.
- Do not optimize only sum-rate; enterprise scenarios need interpretable trade-offs.

