# Open-Source Landscape

This project should reuse open-source work where it helps the prototype, while keeping the core product boundary clear: a scenario-driven, reconfigurable SAGIN planning copilot with reproducible runs, optimization, visualization, and report generation.

Checked on 2026-07-06 through GitHub/web search. GitHub MCP was not available in the current Codex tool list, so these are web-sourced repository leads.

## High-Relevance Projects

| Area | Project | What It Provides | How To Use It Here |
| --- | --- | --- | --- |
| SAGIN platform architecture | [UNIC-Lab/Comprehensive-Simulation-Platform-for-Space-Air-Ground-Integrated-Network](https://github.com/UNIC-Lab/Comprehensive-Simulation-Platform-for-Space-Air-Ground-Integrated-Network) | A SAGIN simulation platform integrating space, aerial, and ground network modules, controllers, mobility traces, and protocol evaluation. | Use as architecture reference for layered SAGIN simulation and controller abstractions. Not a direct MVP dependency. |
| UAV-assisted SAGIN + Sionna | [TWIST-Lab/Sionna-SAGIN](https://github.com/TWIST-Lab/Sionna-SAGIN) | Simulation/evaluation framework for UAV-assisted SAGIN improving D2C performance with propagation, fading, throughput, latency, and error-rate metrics. | Strong candidate for later `sionna_sagin_adapter` and Level-1/2 propagation validation examples. |
| LEO network simulation | [snkas/hypatia](https://github.com/snkas/hypatia) | LEO satellite network simulation with `satgenpy`, ns-3 packet simulation, and Cesium visualization. | Reuse ideas for constellation state generation, route snapshots, and Cesium satellite visualization. |
| LEO routing simulator | [Fundacio-i2CAT/LEOPath](https://github.com/Fundacio-i2CAT/LEOPath) | Python LEO constellation routing simulator and Cesium viewer. It explicitly focuses on topology/routing and is not packet-level. | Good fit for a later orbit/routing module that outputs forwarding-state artifacts for the Copilot. Watch AGPL-3.0 license constraints. |
| ns-3 LEO module | [dadada/ns-3-leo](https://github.com/dadada/ns-3-leo) | ns-3 LEO mobility model, satellite-satellite and satellite-ground propagation loss, TLE import helpers. | Use as ns-3 integration reference if this project later needs packet-level validation. |
| ns-3 NTN/SAGIN | [Muhammaduazir69/ntn-sagin](https://github.com/Muhammaduazir69/ntn-sagin) | ns-3.43 SAGIN model spanning LEO, HAPS/UAV/aircraft, and ground terminals, with SGP4 and A2G channel references. | Useful as a detailed future ns-3 validation track. Treat maturity/license carefully before depending on it. |
| RIS ray tracing | [NVlabs/sionna / Sionna RT](https://github.com/NVlabs/sionna) and [NVlabs/sionna-rt releases](https://github.com/NVlabs/sionna-rt/releases) | Sionna RT has RIS support and can compute exact paths and coverage maps; recent Sionna RT releases improve radio-map visualization and ray-tracing dependencies. | Primary candidate for Level-2 ray-tracing adapter and RIS coverage validation. |
| RIS modular simulation | [Brook1711/RIS_components](https://github.com/Brook1711/RIS_components) | Modular RIS-aided system simulation ideas, referencing SimRIS and active/passive RIS comparisons. | Use as a reference for RIS component abstraction; not enough by itself for the full SAGIN planning product. |
| UAV network simulator | [Zihao-Felix-Zhou/UavNetSim](https://github.com/Zihao-Felix-Zhou/UavNetSim) | Python platform for UAV swarm communication protocol/control algorithm simulation. | Candidate reference for UAV mobility/control abstractions and later scheduling experiments. |

## Practical Reuse Strategy

### Directly Integrate Later

- Sionna RT: Level-2 propagation and RIS radio-map generation.
- Skyfield/SGP4 ecosystem: LEO pass and visibility calculation.
- H3/GeoPandas/Shapely/PostGIS: region/grid/spatial data.
- OR-Tools/CVXPY/pymoo: optimization backends.

### Borrow Architecture/Concepts

- UNIC SAGIN platform: layered architecture and controller separation.
- Hypatia and LEOPath: constellation state and Cesium visualization pipeline.
- ns-3-leo and ntn-sagin: packet-level validation path after MVP.
- UavNetSim: UAV mobility and protocol experiment patterns.

### Keep Internal

- Scenario schema and run registry.
- Reconfigurable-node abstraction for RIS/MIS/MA.
- Multi-objective planning objective.
- Copilot tool-call and explanation layer.
- Report generation and paper/grant/enterprise artifact pipeline.

## Why Not Just Fork One Project?

The existing projects each cover an important slice, but the target here is a cross-domain planning agent:

- SAGIN + low-altitude + reconfigurable electromagnetic nodes,
- coverage/rate/localization/sensing/cost jointly,
- web demo + CLI reproducibility + report export,
- AI explanation grounded in computed artifacts,
- model-fidelity profile switching from closed-form to calibrated digital twin.

That means the best path is an orchestrating monorepo with adapters, not a single upstream fork.

## Next Adapter Candidates

```text
packages/rsagin-core/src/rsagin_core/adapters/
  skyfield_orbit.py
  sionna_rt_radio_map.py
  ns3_export.py
  leopath_import.py
  hardware_lut.py
```

First integration priority after the MVP:

1. add a Skyfield-based LEO pass profile,
2. add a Sionna RT experiment notebook or adapter stub,
3. add H3/GeoJSON export for web map layers,
4. add OR-Tools candidate selection baseline,
5. add a citations/manifest file mapping each adapter to source repositories and licenses.

