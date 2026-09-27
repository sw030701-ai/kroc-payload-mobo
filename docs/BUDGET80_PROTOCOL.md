# 2026-09-27 paired bounds and budget experiment

Before inspecting new results, compare [400,200,40] and [800,400,80] at nominal 1 kg with five paired repeats, 80 evaluations including ten initial points, and the same zero anchor and disjoint training/selection/test seed policy. All physical and optimizer settings except the total evaluation budget and gain bounds remain unchanged.

Use the percentage decrease in mean selection-set minimum feasible JT across five repeats. Adopt expanded bounds at >=5% improvement and rerun all three payloads. Below 5%, retain current bounds provisionally and report whether saturation evidence supports this choice. Gain attachment alone does not demonstrate saturation. Report CT voltage-clipping fraction, peak current relative to the 3.84 A feasibility limit, paired improvement and boundary attachment. There is no current clipping in this model.

Run a fresh canonical Experiment 1 and Experiment 2 at the selected bounds and 80 evaluations. Practical selection remains JT <=0.05 rad, excludes zero PID, and does not truncate full fronts. Report local versus transferred tracking on identical test seeds, even if coverage gaps remain. Compare each new run's first 40 evaluated candidates against all 80 on the same selection seeds to isolate the budget effect at fixed bounds. HV and retention remain supplementary. No Experiment 3 or physical-model additions.

Execute `python analysis/run_budget80.py --out results/budget80-20260927` from the repository root. Runs fail rather than overwrite an existing destination. Source snapshots, config snapshots, seed files and manifests accompany the raw data. Archive the previous canonical report before replacing the published report.
