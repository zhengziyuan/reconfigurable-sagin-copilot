# Reconfigurable SAGIN Copilot v0.5 Upgrade

This document records the upgrade from a functional SAGIN dashboard to a research and planning operating-system prototype.

## Implemented Scope

The v0.5 codebase now covers the major roadmap requirements:

- Unified theory abstraction: R-SAGIN-PP and multi-service performance field.
- Model system: L0 closed-form, L1 3GPP/ITU-traceable planning, and L2 ROI high-fidelity adapter mode.
- Scenario system: eight reusable use-case families for low-altitude ISAC, emergency recovery, industrial private networks, remote NTN coverage, urban RIS/MIS, ISAC monitoring, AI edge SAGIN, and array-as-a-service.
- Algorithm system: candidate generation, deployment optimization, resource management, trajectory/position, multi-fidelity, learning-assisted stubs, explainable optimization, and intent-driven planning.
- Hardware system: RIS/MIS/MA planning catalog, switching-cost proxies, and effective reconfigurable DoF.
- Robustness system: Monte Carlo weather/channel/hardware perturbation, CVaR, SLA violation probability, and stability score.
- Sensitivity system: one-factor perturbation for rain, bandwidth, and budget assumptions.
- Benchmark system: no-deployment, random-like, geometry heuristic, greedy, and exact Pareto comparisons.
- Artifact system: run manifest and reproducibility schema for layers, geo files, figures, tables, and reports.
- Validation system: run-quality checks, model-validity warnings, golden-scenario registry, and regression tests.
- Copilot system: intent parser, tool-chain planner, verifier, critic, and run-grounded report writer.
- Frontend workbench: Use Case Studio, Model Lab, Algorithm Lab, Benchmark Center, Results, Reports, 2D/3D digital twin, SLA/risk layers.
- Plugin architecture: channel, metric, optimizer, hardware, and report plugin protocols plus registry.
- Data ingestion adapters: GeoJSON, Shapefile, OSM, KML, TLE, DEM, and demand assets.
- Commercial delivery skeleton: project/user/permission entity model, local artifact mode, FastAPI endpoints, CLI extensions, and error taxonomy.

## New Core Modules

Key additions under `packages/rsagin-core/src/rsagin_core/`:

- `model_fidelity/`: profiles, assumptions, validity, warnings.
- `planning/`: performance field, SLA, cost model, intent parsing, problem templates.
- `hardware/`: catalog and ER-DoF.
- `uncertainty/`: distributions, Monte Carlo robust evaluation, CVaR, confidence summaries.
- `sensitivity/`: one-factor sensitivity.
- `validation/`: run quality.
- `artifacts/`: run manifest and artifact schema.
- `benchmarks/`: benchmark suite and baselines.
- `high_fidelity/`: ROI selection, scene export, Sionna RT adapter descriptor, calibration hooks.
- `agent/`: planner, verifier, critic, reporter.
- `plugins/`: protocol interfaces and registry.
- `data_ingestion/`: import adapters.
- `standards/`: standards trace registry.

## New API Endpoints

- `GET /api/platform`
- `POST /api/robust-evaluate`
- `POST /api/sensitivity`
- `POST /api/benchmark`
- `POST /api/intent-plan`
- `POST /api/report`
- `POST /api/high-fidelity/roi`

Existing simulation and optimization endpoints now return richer summaries with:

- `summary.multi_service_field`
- `summary.engineering`
- `summary.cost_benefit`
- `summary.run_quality`
- `summary.run_manifest`
- `summary.hardware`

## Frontend Workbench

The React app now includes: Scenario, Simulate, Optimize, Use Cases, Model Lab, Algorithm Lab, Benchmark, Results, and Reports.

The map supports additional layers: Coverage, Rate, PEB, Sensing, SLA Risk, and Risk.

## Validation

Current validation commands:

```powershell
.\.venv\Scripts\python.exe -m pytest packages\rsagin-core\tests
pnpm --dir apps\web build
```

Browser validation was performed against:

```text
http://127.0.0.1:5174/
```

Verified flows:

- Use Case Studio renders use-case families and scenario-model-algorithm matrix.
- Model Lab renders fidelity profiles, standards trace, run quality, and manifest.
- Algorithm Lab renders algorithm families, plugin registry, and intent tool chain.
- Benchmark Center runs robust evaluation, sensitivity analysis, and benchmark suite.
- Reports renders research/enterprise/grant templates and artifact package.

## Limitations

This is a v0.5 research and planning prototype, not a final field-acceptance simulator.

- L1 is standards-traceable in decomposition and validity reporting, but it is not a full stochastic clustered 3GPP implementation.
- L2 exports ROI scenes and calibration targets but does not bundle Sionna RT or ns-3 execution.
- Hardware models are planning proxies until calibrated by lab or field measurements.
- Database, permissions, Docker/Helm, and SDK are represented as local-mode architecture and API/CLI skeletons.
