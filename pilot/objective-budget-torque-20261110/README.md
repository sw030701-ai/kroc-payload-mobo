# Objective × evaluation budget × actuator saturation study
Independent benchmark. Main, canonical motor model, and prior pilot are untouched.

From repository root (Python 3.13 used):
```
python -m venv .venv-study
.venv-study/bin/pip install -r pilot/objective-budget-torque-20261110/requirements.txt
MPLCONFIGDIR=/tmp/kroc-mpl .venv-study/bin/python pilot/objective-budget-torque-20261110/validate.py
MPLCONFIGDIR=/tmp/kroc-mpl .venv-study/bin/python pilot/objective-budget-torque-20261110/run.py > pilot/objective-budget-torque-20261110/execution.log 2>&1
MPLCONFIGDIR=/tmp/kroc-mpl .venv-study/bin/python pilot/objective-budget-torque-20261110/analyze.py
```
Full actual environment: environment-freeze.txt. Read PROTOCOL.md before interpreting results. Initial compile failure is retained; it occurred before any candidate simulations and was fixed without changing scientific conditions. All later numerical failures, if any, stay in candidate archive. Candidate count includes duplicates and failed candidates; no uncounted replacement trials.

Statistical intervals concern optimizer seed variability, not sensor noise, hardware variation, or population of robots. Test trajectories are not independent optimizer replications. No hardware performance or energy-saving claims.
