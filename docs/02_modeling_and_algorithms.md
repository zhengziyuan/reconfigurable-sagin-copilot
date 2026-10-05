# Modeling And Algorithms

## Core Objects

```text
Scenario
Region
GridCell
Node
CandidateSite
Link
ServiceDemand
MetricLayer
SimulationRun
OptimizationRun
Recommendation
Report
```

## Node Types

```text
satellite_leo
satellite_geo
haps
uav_relay
ground_bs
ground_station
ris
mis
ma_array
user
target
sensor
```

## Level-0 Link Budget

Thermal noise:

```text
N[dBm] = -174 + 10 log10(B[Hz]) + NF[dB]
```

Free-space path loss:

```text
FSPL[dB] = 32.45 + 20 log10(d[km]) + 20 log10(f[MHz])
```

Received power:

```text
Pr[dBm] = Pt + Gt + Gr + Gextra - FSPL - Lextra
```

SINR:

```text
SINR = S / (I + N)
```

Rate:

```text
R = eta * B * log2(1 + SINR)
```

## Reconfigurable Gain Proxy

RIS:

```text
G_ris[dB] = 20 log10(N_elements) - reflection_loss - phase_quant_loss - angle_loss
```

MIS:

```text
G_mis[dB] = aperture_gain + focusing_gain - transmission_loss - layer_coupling_loss
```

MA:

```text
G_ma[dB] = codebook_gain + aperture_gain - movement_penalty
```

The MVP uses a conservative capped gain so it is useful for planning without pretending to be a full-wave electromagnetic simulator.

## Level-1 Standards-Inspired Channel Model

The `standards_l1` profile adds a standards-inspired physical channel layer:

- terrestrial links: 3GPP TR 38.901 UMa/RMa path-loss subset, LOS probability, deterministic shadow-fading proxy, and urban clutter loss,
- NTN links: 3GPP TR 38.811-style decomposition with FSPL, atmospheric gas loss, rain loss, cloud/fog loss, scintillation, clutter, and shadow fading,
- atmospheric gas: ITU-R P.676-inspired oxygen/water-vapour approximation,
- rain attenuation: ITU-R P.838 power-law model using interpolated `k` and `alpha` coefficients.

Each heatmap cell stores physical channel metadata:

```text
channel_model
path_loss_db
extra_loss_db
los_probability
elevation_deg
rain_loss_db
gaseous_loss_db
```

The implementation lives in `packages/rsagin-core/src/rsagin_core/channel_models.py`.

## Localization Proxy

The MVP uses a geometry and SNR weighted Fisher-information proxy:

```text
J(p) = sum_i rho_i u_i u_i^T
PEB = sqrt(trace(inv(J)))
```

Where `rho_i` increases with anchor SNR and bandwidth, and `u_i` is the unit direction from anchor to target point.

## Sensing Proxy

The MVP uses a monotonic sensing score:

```text
SensingScore = sum_i alpha_i * gain_i / distance_i^beta
```

This is later replaceable by radar equation, detection probability, and CRB models.

## Optimization Objective

The MVP combines normalized metrics:

```text
score =
  w_cov * coverage_score
+ w_rate * rate_score
+ w_loc * localization_score
+ w_sense * sensing_score
- w_cost * cost_score
```

Greedy candidate deployment:

1. simulate baseline,
2. evaluate each remaining candidate added to the current set,
3. choose the candidate with largest positive objective improvement,
4. repeat until budget or candidate limits are reached,
5. emit selected nodes, comparison summary, and recommendations.

This simple solver is intentionally transparent and acts as a baseline for later MILP, convex, metaheuristic, and multi-objective solvers.

Exact small-scale Pareto mode:

1. enumerate all feasible candidate-node subsets,
2. simulate each subset under the selected model profile,
3. keep objective/cost/coverage/rate/PEB summaries,
4. return the best feasible subset and a compact Pareto front.

This mode is useful for demos, papers, and small enterprise planning scenes where exact explainability matters more than speed.

## Resource Management Layer

After deployment selection, the prototype now runs a separate resource-management layer:

```text
ResourcePlan
ResourceFlow
ResourceTransmitter
BenchmarkSummary
IterationTrace
```

The L0 resource-management problem is:

```text
maximize   sum_k w_k B_k log2(1 + SINR_k)
subject to sum_k B_k <= B_total
           sum_{k served by n} P_k <= P_n,max
           each scheduled flow k is served by one transmitter
```

Implemented methods:

1. `weighted_greedy`
   - Associates demand-heavy cells with strong feasible serving links.
   - Allocates bandwidth by demand-weighted square-root shares.
   - Allocates power by local demand and channel quality.
2. `ucb_bandit`
   - Adds a small exploration term to association selection.
   - Acts as a lightweight learning-style baseline without training.
3. `wmmse`
   - Reproduces a SISO weighted-MMSE style alternating update.
   - Updates receiver equalizers, MSE weights, and transmit powers.
   - Uses bisection to enforce per-transmitter power budgets.

Current outputs:

- scheduled flow list,
- serving transmitter per flow,
- bandwidth MHz,
- transmit power dBm,
- SINR dB,
- rate Mbps,
- transmitter utilization,
- Jain fairness,
- p5 flow rate,
- weighted sum-rate,
- iteration trace,
- greedy and bandit benchmark summaries.

The implementation lives in `packages/rsagin-core/src/rsagin_core/resource_management.py`.
