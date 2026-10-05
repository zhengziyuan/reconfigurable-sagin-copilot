# Engineering Plan

## M0: Project Skeleton

Deliverables:

- monorepo layout,
- Python core package,
- CLI entry point,
- FastAPI wrapper,
- React/Vite dashboard,
- demo scenario config,
- model and optimization profiles,
- setup and dev scripts,
- design concept reference.

Acceptance:

- core tests pass,
- CLI can simulate and optimize the demo scenario,
- API health endpoint responds,
- frontend renders the primary dashboard.

## M1: Region And Grid

Tasks:

- load polygon region from YAML or JSON,
- generate grid cells inside polygon,
- compute centers, area proxy, and demand weights,
- export layer-like cell objects for web visualization.

Acceptance:

- every grid cell has id, lat, lon, demand weight, and metric slots,
- web canvas shows region and grid.

## M2: Node Placement And Link Budget

Tasks:

- support fixed and candidate nodes,
- model ground BS, ground station, LEO, HAPS/UAV, RIS, MIS, MA,
- compute distance, FSPL, received power, noise, SINR.

Acceptance:

- baseline simulation produces coverage and rate summaries,
- nodes appear in the dashboard with type-specific visual markers.

## M3: Multi-Metric Layers

Tasks:

- coverage and SINR layer,
- rate layer,
- localization PEB proxy layer,
- sensing score layer,
- summary metrics and distribution statistics.

Acceptance:

- frontend can switch metric layer,
- CLI writes summary and layer JSON artifacts.

## M4: Reconfigurable Node Model

Tasks:

- RIS assisted link proxy,
- MIS transmission/focusing proxy,
- MA gain/codebook proxy,
- node cost and deployment feasibility.

Acceptance:

- enabling candidate nodes changes heatmaps in plausible ways,
- system can attribute expected gains to selected nodes.

## M5: Deployment Optimization

Tasks:

- greedy candidate selection,
- budget constraints,
- objective weights,
- baseline vs optimized comparison,
- recommendation text.

Acceptance:

- optimizer selects a bounded set of candidate nodes,
- summary shows improvement and cost,
- report explains the selected deployment.

## M6: Scheduling

Tasks:

- user/grid-to-node association,
- simple bandwidth allocation,
- power allocation profile,
- time-slot animation.

Acceptance:

- time slider shows different service links and metric layers.

## M7: Copilot

Tasks:

- intent parsing for scenario constraints,
- tool-calling wrapper around simulate, optimize, compare, report,
- explanation generation grounded in run outputs,
- report export.

Acceptance:

- a natural-language planning request can modify constraints and trigger runs,
- all quantitative statements trace back to tool outputs.

## M8: High-Fidelity Model Adapters

Tasks:

- 3GPP/ITU profiles,
- Skyfield orbit adapter,
- Sionna RT adapter,
- measurement LUT adapter,
- uncertainty propagation.

Acceptance:

- same scenario can run multiple model profiles,
- output clearly labels fidelity and assumptions.

