# Independent trajectory-training and gain-bound follow-up

Base: PR2 commit367544e. New branch pilot/trajectory-generalization-20261110. This folder is an exploratory follow-up, not canonical motor-model data. Read PROTOCOL.md and LITERATURE_KO.md first. Existing pilot results are inherited unchanged, not newly executed here.

From repository root, Python3.13:
```
python3 -m venv .venv-followup
.venv-followup/bin/pip install -r pilot/objective-budget-torque-20261110/requirements.txt
MPLCONFIGDIR=/tmp/kroc-mpl .venv-followup/bin/python pilot/trajectory-generalization-20261110/validate_followup.py
MPLCONFIGDIR=/tmp/kroc-mpl .venv-followup/bin/python pilot/trajectory-generalization-20261110/run_followup.py > pilot/trajectory-generalization-20261110/execution.log 2>&1
MPLCONFIGDIR=/tmp/kroc-mpl .venv-followup/bin/python pilot/trajectory-generalization-20261110/analyze_followup.py
```

Execution uses only numpy/pandas/numba/matplotlib and standard library. Full actual existing environment is recorded in environment-freeze.txt. The actual commands used locally are in ACTUAL_COMMANDS.txt. Re-running writes results in this folder; preserve old results first when desired.

Train and test are deterministic simulation trajectories. Seed variability is optimizer variability. New tasks3/4/6 are three fixed quintic moves, task5 is a fixed step, not an independently sampled population of robots. Candidate optimization evaluations differ from simulator rollouts: mixed uses two rollout calls per gain. At equal256calls, step evaluates256gains, mixed128gains. There is no extra candidate replacement on failure and no test-based controller selection.

results/candidates.csv.gz includes every gain candidate, scalar train score, per-training-task components, seed, settings and numerical validity. selected.csv is chosen solely from own training scores. test_metrics.csv contains every held-out checkpoint test; refinement.csv contains all final-gain tests at half the plant integration step with controller timing fixed. audit.json independently verifies candidate accounting, shared normalized initial population, and archive minimum selection. No hardware or Actions runs are claimed.

Optional prespecified illustrative trace, run after optimization:
```
MPLCONFIGDIR=/tmp/kroc-mpl .venv-followup/bin/python pilot/trajectory-generalization-20261110/trace_diagnostic.py
```
This adds TWO simulator calls (not optimization). The illustration uses fixed seed301/ISE/reduced/paper/task3, not a best-looking seed. Segment errors are diagnostic, not extra independent replications. Here the arm starts horizontally at q=0 with zero integral state, no gravity feedforward and no model compensation. Smooth references begin at zero while gravity is nonzero, so initial gravitational sag is part of this particular benchmark and may affect transfer results. Do not generalize the findings to gravity-compensated industrial servo architectures without re-tuning and new tests.

After numerical analysis, regenerate the numerical report with:
```
.venv-followup/bin/python pilot/trajectory-generalization-20261110/build_report.py
```
The final reviewer verdict is kept separately in VERDICT_KO.md and should be read together with results/REPORT_KO.md. Artifact integrity can be checked by computing SHA256 for each relative path in results/sha256.json. This report is an internal research assessment; scores are not official KRoC review criteria or an acceptance forecast.
