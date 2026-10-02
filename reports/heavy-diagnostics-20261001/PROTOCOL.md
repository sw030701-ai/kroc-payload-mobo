# Heavy-payload supplementary diagnostics — 2026-10-01

Recorded before additional evaluations. Canonical bounds stay [800,400,80], and the main Experiment 1/2 remains the preserved 80-evaluation run. No Experiment 3 and no physical-model changes.

## MOBO budget diagnosis

At 2 and 3 kg, continue each of the five stored 80-candidate histories to 160 total candidates using the same qLogNEHVI, seeds, GP settings, noise, feasibility and bounds. Reuse (and hash) the first 80 training/selection observations; evaluate candidates 81–160 on the original three training and five selection seeds. No nominal CT is added to these independent local histories. Report incremental cost separately: 800 new candidates, not 1,600 new candidates.

Primary budget statistic: 100*(mean minimum feasible selection JT at 80 - mean minimum at 160)/mean minimum at 80, separately per payload, plus every paired repeat. Less than 5% indicates low observed budget sensitivity over this interval only. It does not certify the true Pareto front, sufficient extreme-point coverage, convergence, or a global optimum. >=5% indicates material remaining budget sensitivity. Report regional fronts and common tracking-budget energy as secondary diagnostics.

## Short single-objective diagnostic

At each heavy payload and repeat, run constrained qLogNEI on -JT alone with a separate constraint GP. JE is recorded but is not optimized. Forty total candidates include ten initial points: zero PID, the frozen nominal CT, and eight Sobol points. The CT seed is explicitly a warm start; this is a targeted existence diagnostic, not a fair optimizer benchmark against unseeded MOBO. All forty target observations are new; the same train/selection seed policy applies. Record all failed/infeasible attempts in the budget. No target test results enter candidate generation or selection.

Freeze each arm's minimum feasible selection-JT candidate before testing. Compare MOBO80, MOBO160, SO40 and the unchanged nominal CT on the original ten paired test seeds, plus ten newly reserved confirmation seeds 300000 + 1000*repeat + [0..9]. Physical feasibility requires every rollout to pass all constraints. Report paired JT differences, seed-wise wins and 95% Student-t intervals across noise seeds (conditional on the selected gains, not optimization-repeat uncertainty). A feasible candidate with lower paired mean JT is an observed counterexample; a negative upper confidence limit on fresh seeds gives stronger evidence. If none is found, report failure to find one, never nonexistence. If CT is infeasible, report that explicitly rather than counting a feasible-performance comparison.

Main-paper interpretation: current-limit violations show an applicability constraint on aggressive transferred gains. They do not locate the global constrained optimum or prove that voltage saturation sets the limit. Larger bounds enlarge the search domain under a fixed budget, but no quantitative coverage-density claim is made from volume alone. MOBO sample efficiency or superiority is not established without an appropriate equal-budget optimizer benchmark.

## Provenance and execution

Parent: `83e88835e127d456e3a06233cd1ec6605016b1a1`, `results/budget80-20260927/canonical`. New immutable output: `results/heavy-diagnostics-20261001`. Each condition checkpoints after each evaluation and records inherited file hashes and new costs. Independent conditions run in two separate processes; each uses one Torch thread. Execution is local against the GitHub repository; code/results/history are pushed to a separate branch. This does not claim that the optimization ran on GitHub Actions.

Run: `python -m kroc_mobo.heavy_diagnostics --parent results/budget80-20260927/canonical --out results/heavy-diagnostics-20261001`. `--resume` reuses only matching completed/checkpointed conditions; existing outputs otherwise fail. Preserve the 80-evaluation report and link the supplementary report from it. Record revisions 1–4 using dated Git evidence, distinguishing editorial numbering from original experiment labels.
