# KRoC pilot diagnostic results 2026 10 23

## Main finding

Expanding nominal bounds to [1600,800,160] at unchanged 80-evaluation budget
changed the mean feasible selection minimum JT by 35.140% improvement.
Expanded winners touch an upper bound in 3/5 repeats.
This is a sensitivity test of finite observed fronts, not a global optimum claim.
All original scientific files were preserved: 2173 file hashes unchanged.

## Provenance and execution

Research baseline is GitHub branch revision/heavy-payload-diagnostics-20261001,
commit 9a27fd0569f2bb9f03b21666192028a53e3298fa (remote verified). The default main
branch points to older commit 2f21d55fb8eadfbfed97a10e5a21e6b78594492b.
No remote branch or original file was changed. Output lives in this separate pilot path.
PROTOCOL.md was written before numerical execution. Source copy is under source/.
New computation: expanded 1 kg qLogNEHVI, 5 repeats x 80 candidates = 400 candidates,
1,200 training plus 2,000 selection rollouts. Initial design uses the SAME normalized
Sobol sequence and optimizer/noise seeds; physical gains scale with the wider box.
Existing baseline 80 and heavy 160 optimization were reused and audited, not rerun.
Fresh tests: 940 rollouts saved across fresh_rollouts.csv and
bounds_fresh_rollouts.csv (duplicate controller evaluations cached within first stage).
Also five 32-substep refinement rollouts plus one recorded example trace.
Same comparison noise seeds: 400000+1000r through +9, disjoint from archived train,
selection, test and confirmation sets. Winners frozen before fresh tests.
Repeated tests reuse physical gains if roles coincide; do not count them as independent
optimization discoveries. Bounds winners are selected on selection seeds only.

## Gain bound sensitivity

| repeat | mode | kp | ki | kd | JT | JE | at_upper | max_current | saturation_fraction | feasible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | current | 800 | 400 | 0 | 0.000777666 | 2.94889 | True | 2.73599 | 0 | True |
| 0 | expanded | 1131.65 | 800 | 0 | 0.00049122 | 3.48877 | True | 3.57868 | 0 | True |
| 1 | current | 800 | 400 | 0 | 0.000783377 | 2.95004 | True | 2.35635 | 0 | True |
| 1 | expanded | 1296.88 | 800 | 0 | 0.00046685 | 3.86278 | True | 3.55591 | 0 | True |
| 2 | current | 800 | 400 | 0 | 0.000780528 | 2.95099 | True | 2.32171 | 0 | True |
| 2 | expanded | 1186.68 | 791.31 | 0 | 0.000484531 | 3.60612 | False | 3.15398 | 0 | True |
| 3 | current | 800 | 400 | 0 | 0.000778803 | 2.94378 | True | 2.31751 | 0 | True |
| 3 | expanded | 1109.1 | 800 | 0 | 0.000495794 | 3.42795 | True | 3.04994 | 0 | True |
| 4 | current | 800 | 400 | 0 | 0.000781688 | 2.93995 | True | 2.46341 | 0 | True |
| 4 | expanded | 1006.89 | 587.152 | 0 | 0.000592488 | 3.23855 | False | 3.09112 | 0 | True |

Fresh fixed-gain transfers, including infeasible outcomes (JT averages are not
feasible-only performance rankings):

| mode | payload | JT | JE | feasible_groups | Imax |
| --- | --- | --- | --- | --- | --- |
| current | 1 | 0.000781028 | 2.94339 | 5 | 2.71567 |
| current | 2 | 0.000866279 | 6.04204 | 5 | 3.31948 |
| current | 3 | 0.00096736 | 10.1342 | 2 | 4.02267 |
| expanded | 1 | 0.000506697 | 3.51529 | 5 | 3.71427 |
| expanded | 2 | 0.000551271 | 6.61807 | 1 | 4.3444 |
| expanded | 3 | 0.000605863 | 10.7153 | 0 | 4.98052 |

The domain comparison keeps proposal budget and algorithm fixed. A larger domain
changes candidate coverage and current-noise amplification. More accurate tracking
may cost energy and feasibility. Neither gain boundary nor zero voltage saturation
establishes a physically optimal envelope. Do not substitute pilot CTs into the old
cross-payload table; that would mix controller selection protocols.

## Evaluation budget sensitivity

The existing 80→160 continuations passed 1,292 checks in budget_audit_verified/AUDIT.json,
including exact inherited values, source/parent hashes, raw means, seeds, budgets,
feasibility and frozen winners. A first audit invocation used the wrong working directory
and failed resolving a relative archive path; its log is retained. The successful audit
used the repository working directory and wrote all outputs into the pilot path.

Fresh-seed comparison of the frozen 80/160 winners:

| payload | JT80 | JT160 | SD80 | SD160 | improvement_pct |
| --- | --- | --- | --- | --- | --- |
| 2 | 0.000988546 | 0.000897882 | 9.61609e-05 | 3.71295e-05 | 9.17141 |
| 3 | 0.00305043 | 0.00222907 | 0.00111662 | 0.00131941 | 26.9259 |

All repeat-specific values are in budget_fresh_paired.csv. These results test the
archived continuation and fresh predictive performance; no new 160-candidate
optimization is claimed. The archived selection improvement is 9.16% at 2 kg and
26.93% at 3 kg. Full-front HV can be dominated by low-energy/poor-tracking regions;
JT extreme and common-JT energy comparisons remain necessary.

## Current feasibility and extreme selection

Within the same 80 evaluated candidates per condition, removing ONLY the current
feasibility filter changes the representative selections as follows:

| payload | role | changed | canonical_pass | ignore_current_pass |
| --- | --- | --- | --- | --- |
| 1 | CB | 0 | 5 | 5 |
| 1 | CE | 0 | 5 | 5 |
| 1 | CT | 0 | 5 | 5 |
| 2 | CB | 0 | 5 | 5 |
| 2 | CE | 0 | 5 | 5 |
| 2 | CT | 0 | 5 | 5 |
| 3 | CB | 1 | 5 | 5 |
| 3 | CE | 0 | 5 | 5 |
| 3 | CT | 1 | 5 | 4 |

Other numerical, angle and velocity constraints stay active. The table gives counts
out of five repeats, not a new unconstrained optimization. Re-evaluation always applies
the canonical 3.84 A limit so failure remains visible. The nominal CT transfer on new
seeds is:

| payload | JT | JE | feasible_groups |
| --- | --- | --- | --- |
| 1 | 0.000781028 | 2.94339 | 5 |
| 2 | 0.000866279 | 6.04204 | 5 |
| 3 | 0.00096736 | 10.1342 | 2 |

At 3 kg, original CT passes 47/50 individual fresh rollouts,
but only 2/5 groups pass all ten.
The main paper's 3/5 is its original fixed test set; retain that result, and disclose
this new 2/5-group diagnostic as seed sensitivity. All original nominal CT gains are
[800,400,0], so these five groups do not represent five distinct gain discoveries.
Current infeasibility is not voltage clipping or proof of a global performance limit.

## Hypervolume and normalization

Checked 45 payload/repeat front collections with fixed objective scales
[0.1 rad,10 J] and common reference [1 rad,20 J]. Maximum raw/scaled HV discrepancy
is 7.105e-15; 0 feasible points lie outside
the reference in the audited collections. Configs agree. The acquisition code transforms
minimization objectives and reference together with a minus sign and the same scales.
CB uses nominal practical-subset min/max normalization; this is deliberately separate
from common HV normalization. No payload-dependent rescaling was found.

## Payload inertia and energy sanity

| payload | Jeq | Jeq_ratio_to_1kg | reflected_inertia | reflected_fraction | gravity_coefficient | static_current_at_target |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 0.197806 | 1 | 0.15114 | 0.764079 | 2.4525 | 0.801777 |
| 2 | 0.237806 | 1.20222 | 0.15114 | 0.635558 | 4.4145 | 1.4432 |
| 3 | 0.277806 | 1.40444 | 0.15114 | 0.544047 | 6.3765 | 2.08462 |

Tripling payload from 1 to 3 kg increases total equivalent inertia by only 40.44%,
because reflected motor+gear inertia is 0.15113952 kg m². Gravity coefficient grows
2.6-fold. Thus payload effects combine gravity and inertia. Keep 1/2/3 kg for this study;
do not call them a 3:1 total-inertia range. Values at 0..5 kg are descriptive calculations,
not validation of a larger operating range or gearhead/thermal safety.
JE means signed motor-terminal net electrical energy, not battery draw. Maximum
abs(JE - drawn + returned) is 3.496e-14 J; maximum
algebraic energy balance residual is 1.425e-05 J.
Maximum returned energy is 0.2903 J and minimum transmission
exchange is 0.4694 J. The supplied constant-efficiency
bidirectional model has an algebraic exchange term; it is not a validated dissipative
gear loss model. Kt and Ke remain as user-supplied rounded constants.
Numerical refinement max |JT32-JT16| = 5.554e-14 rad,
max |JE32-JE16| = 8.823e-07 J.
The expanded-current selection table separately records how the current filter changes
the minimum-JT winner in the expanded pool (expanded_current_selection.csv).

## Main experiment decision

Preserve the original [800,400,80], 80-evaluation experiment and fixed CT/CB/CE.
It supports a bounded, finite-budget approximate tradeoff and transfer study.
Wider bounds and 160 evaluations belong in diagnostics and must be acknowledged;
neither current data nor this pilot establishes convergence. If the paper intends
to claim a bound-independent achievable envelope or optimal tuning, it needs a NEW
uniformly specified main study for all payloads and repeats; replacing selected
rows or nominal gains alone is not valid. Do not increase current_max to make failures
disappear: 3.84 A is an experiment convention, not an identified peak hardware rating.

## Paper text and four page priorities

Keep payload-specific fronts (five separate repeats, shared axes), a compact CT/CB/CE
cross-payload table with JT/JE and feasibility, and the original CT 3 kg 3/5 result.
Keep model equations including N=126, reflected inertia and efficiency, the signed
terminal-energy definition, 3.84 A feasibility rule, separate train/selection/test seeds,
and qLogNEHVI / 80-evaluation settings. Compress diagnostics to a short limitations
paragraph containing bound and budget sensitivity and fresh current-feasibility evidence.
Keep full per-repeat tables, HV audit, gain details and energy accounting here.
Do not remove cross-payload transfer from the four-page paper.

The user-provided Google Docs source was fetched as readable text from
https://docs.google.com/document/d/1WKhkEWoDohY0o2GnRT-0y6-XEwAElDZutjmWLGD0yn0
It is a September 21 pre-results draft, not the later six-page results draft described
in the referenced conversation. draft_readback.txt preserves the fetched text.
The originally named /mnt/data/KRoC_Payload_MOBO_Final.docx is unavailable here.
Required source corrections: direct drive → 126:1 geared model; unspecified settings
→ canonical values; qNEHVI → qLogNEHVI; full-front CE and endpoint-excluding CB →
JT<=0.05 practical subset excluding zero PID, CB over the entire subset with coincident
roles allowed. Results/abstract placeholders need actual main results. These are
method discrepancies, not page-layout judgments; no original document was edited.

## Reproduction

Use Python and package versions recorded in bounds_expanded/exp1/manifest.json.
From the project workspace, set PYTHONPATH to this directory's source, MPLCONFIGDIR
and NUMBA_CACHE_DIR to writable temporary paths, and OMP/OPENBLAS/MKL_NUM_THREADS=1.
run_bounds.py refuses an already completed output; use a new copy of this pilot folder
without generated outputs for a fresh optimization. Then run diagnose.py initial,
diagnose.py final, summarize.py. initial can run while bounds is computing; final requires
completed expanded bounds. The existing heavy report audit requires the repository
working directory and a NEW --out path outside the repository, as recorded in logs.
Parent raw data and initial protocol are not included as newly executed optimization.
SHA256SUMS.json covers delivered pilot files; protected_before.json identifies exact
original inputs; preservation_audit.json proves their unchanged content.
