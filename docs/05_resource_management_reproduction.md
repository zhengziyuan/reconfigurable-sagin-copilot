# Resource Management Reproduction Notes

This note records the first reproducible resource-management layer added to the Reconfigurable SAGIN Copilot prototype.

## Open-source references

- Hypatia: LEO satellite network simulation framework with time-varying topology generation, ns-3 packet simulation, link-utilization analysis, and visualization.
  - URL: https://github.com/snkas/hypatia
  - Local borrowing: keep topology/routing/link-utilization as a future L1/L2 backend boundary; current L0 plan uses its reproducible experiment organization as a reference.
- Sionna: open-source Python library for communication-systems research, including ray tracing, link-level simulation, and system-level PHY abstraction.
  - URL: https://github.com/NVlabs/sionna
  - Local borrowing: use explicit channel, noise, bandwidth, and system-level abstraction objects instead of opaque UI-only metrics.
- ns-3-leo: ns-3 LEO module with satellite mobility, propagation loss, satellite-satellite and satellite-ground channel helpers, and TLE import support.
  - URL: https://github.com/dadada/ns-3-leo
  - Local borrowing: keep mobility, propagation loss, and channel models as swappable model profiles.
- StarryNet: satellite Internet emulation framework for constellation/ground-station experiments with routing, damage/recovery, ping, perf, position, and neighbor APIs.
  - URL: https://github.com/SpaceNetLab/StarryNet
  - Local borrowing: expose operational controls and reportable experiment outputs rather than only static plots.

## Paper-method references

- WMMSE / weighted sum-rate maximization: classic family for non-convex weighted sum-rate problems in interference-limited wireless networks.
  - Current reproduction: SISO WMMSE-style power update with per-transmitter power constraints, demand-weighted flow priorities, and deterministic trace output.
- SAGIN resource orchestration / virtual network embedding:
  - Current reproduction: high-demand grid cells are treated as scheduled flows; serving-node association, bandwidth, and power are planned jointly at L0 fidelity.
- RIS-assisted weighted sum-rate optimization:
  - Current reproduction: RIS/MIS/MA gains are currently represented by topology/link-budget proxies; full phase/beamforming optimization is reserved for L1/L2.

## Implemented algorithms

File: `packages/rsagin-core/src/rsagin_core/resource_management.py`

- `weighted_greedy`
  - Associates each scheduled flow with a serving transmitter.
  - Allocates transmitter power across local flows by demand and channel quality.
  - Allocates bandwidth by demand-weighted square-root shares.
- `ucb_bandit`
  - Adds a light exploration bonus to association selection.
  - Useful as a baseline for learning-style scheduling without training a neural policy.
- `wmmse`
  - Runs iterative SISO WMMSE-style updates.
  - Uses weighted MSE equalizers and one-dimensional bisection for per-transmitter power constraints.
  - Returns iteration trace, flow allocations, transmitter utilization, fairness, p5 flow rate, sum-rate, and weighted sum-rate.
- `exhaustive_pareto` deployment optimizer
  - Enumerates feasible deployment subsets for small scenes.
  - Returns best objective plus a compact Pareto front.
  - Useful as a paper-grade exact baseline for the greedy optimizer.

## Standards-inspired channel profile

File: `packages/rsagin-core/src/rsagin_core/channel_models.py`

- `closed_form_v0`: L0 fast free-space planning model.
- `standards_l1`: L1 physical channel profile with:
  - 3GPP TR 38.901 terrestrial UMa/RMa path-loss subset,
  - 3GPP TR 38.811-style NTN loss decomposition,
  - ITU-R P.676-inspired gaseous attenuation,
  - ITU-R P.838 rain attenuation,
  - deterministic shadow-fading and clutter proxies.

## API and UI integration

- API endpoint: `POST /api/resource-plan`
- Frontend entry points:
  - Top `Results` button runs resource planning.
  - Left rail `Resource results` button runs resource planning.
  - Results side panel shows method, scheduled flows, sum-rate, p5 flow rate, fairness, power utilization, and benchmarks.
  - Resource Control panel shows scheduled flows and transmitter utilization.
  - Reports view summarizes simulation, optimization, and resource plan assumptions.

## Next reproduction targets

- L1: replace channel proxies with Sionna SYS/Sionna RT traces or calibrated 3GPP NTN path-loss profiles.
- L1: add queue-aware scheduling and latency objectives for emergency traffic.
- L2: integrate Hypatia/StarryNet-style time-varying topology slots and route-state replay.
- L2: add RIS phase/codebook optimization and MA element-position optimization as alternating blocks.
- L2: add DRL/VNE resource orchestration with reproducible training/evaluation manifests.
