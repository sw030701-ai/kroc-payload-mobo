# Canonical revision protocol — 2026-09-24

Written before the sensitivity or revised canonical results were inspected.
Scope: the existing **1-DOF** joint, Experiment 1 and Experiment 2 only. All
physical parameters, noise, controller implementation, seeds and optimizer
settings remain those of the canonical model. Experiment 3 is excluded.

## Preservation and provenance

- Local starting revision: `b746dfa`; inspected GitHub main: `2f21d55fb8eadfbfed97a10e5a21e6b78594492b`.
- Preserve `results/canonical-final-qlog-v3`, all failed/historical run directories,
  the original full results ZIP, and the original report bundle.
- Exact report backup: `reports/archive/canonical-final-20260923`, with an adjacent
  SHA256 inventory. Revised files receive new manifests/config fingerprints.
- Sensitivity output: `results/bounds-sensitivity-20260924/{original,expanded}`.
- Revised output: `results/canonical-revision-20260924`.

## Step 1 — paired nominal sensitivity

Run both [200,100,20] and [400,200,40] upper bounds at 1 kg, 5 repeats and
40 evaluations (10 Sobol initial), with identical optimizer/noise seed lists,
3 train / 5 independent selection replicates. This isolates bounds **before**
the zero-anchor revision; neither arm receives the new anchor. All 40 candidates
are independently re-evaluated, then filtered to the feasible observed front.

Primary improvement = 100*(mean of original repeat minima - mean of expanded
repeat minima)/(mean of original repeat minima). Also report all paired changes.
"Clearly outside old bounds" means an expanded repeat CT exceeds at least one
old upper bound by >1% of that old parameter range. "At upper bound" means
within 0.1% of that arm's parameter range. These are numerical design conventions.

Front overlap diagnostics: bidirectional Hausdorff distance between discrete
fronts in the tracking region JT<=0.01 rad and practical region JT<=0.05 rad,
using each paired region's pooled min/max ranges (zero spans ignored).
Near-overlap requires both distances <=0.05 in every repeat. Also report
observed minimum JE under the fixed JT budgets 0.005, 0.01, 0.02, 0.05 rad;
missing coverage is explicit, and no interpolation or extrapolation is used.
Hausdorff distances describe finite sampled coverage, not convergence.

Adopt expanded if mean minimum-JT improvement >=5%, **or any** expanded CT is
clearly outside the old bounds. Retain original only if improvement <5%, no CT
is clearly outside, and fronts meet the near-overlap rule. Otherwise adopt
expanded conservatively because the precondition for retention was not met.
Expanded-bound attachment remains a limitation, not proof of a global optimum;
do not recursively expand bounds in this protocol.

## Steps 2–5 — revised canonical experiment

1. Apply the Step 1 decision to `configs/canonical_final.toml`.
2. Include exact zero PID as the first of the **10** initial evaluations in
   every payload/repeat (9 Sobol + 1 anchor; total budget remains 40). Re-run all
   payloads even if original bounds are retained, since the initial design changed.
3. Before inspecting revised outcomes, fix representative criterion JT<=0.05 rad.
   This criterion applies only to representative selection; retain the full front
   for Experiment 1 and supplementary transfer metrics. Explicitly exclude zero
   PID from all representative candidates.
4. Within each nominal practical front select CT=min JT, CE=min JE, and CB as
   the minimum Euclidean distance to the utopia point after min/max normalization
   of JT and JE over that same subset. CB is a balanced point, not a geometric
   knee. Allow coincident roles if the exact rule selects the same point; report
   this rather than secretly selecting a second-best point. Tie break by JT, JE,
   Kp, Ki, Kd. Persist gains, nominal selection JT/JE, scales and distance before
   any target test outcome is used. Empty subsets are explicit failures.
5. Transfer the frozen gains to 1/2/3 kg on the existing ten disjoint paired test
   seeds. JT, JE, within-controller percentage changes versus 1 kg, and physical
   feasibility are primary. Track practical-criterion satisfaction separately;
   it is not the definition of physical feasibility. Retention and HV are
   supplementary. Variability is across five optimization repeats, not 50
   independent optimizations. Use repeat 0 for the preselected example figure.

## Limitations kept in scope

Full 5 s quintic movement without a hold; constant gear efficiency; no thermal,
backlash or detailed driver model; finite-budget search and possible residual
boundary sensitivity. No extra physical model or Experiment 3 is implemented.
