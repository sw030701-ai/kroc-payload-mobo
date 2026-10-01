# 2026-09-27 experiment revision

- `5d05a2a`: preregister the paired 400/800-bound, 80-evaluation protocol; add immutable experiment orchestration and saturation diagnostics.
- `9f47f4d`: adopt [800,400,80] and 80 evaluations after the observed 50.51% nominal tracking improvement; preserve the complete prior 40-evaluation report and add audit/report code.
- `2885b5a`: add raw-result packaging, file hashes, and explicit budget/coverage reporting.
- Final result commit: publish this report, raw ZIP, tables/figures, feasibility-aware coverage analysis, final documentation, and validation records. The enclosing Git commit identifies the exact published version.

Modified implementation/configuration: `configs/canonical_final.toml`, `src/kroc_mobo/sensitivity.py`, `analysis/run_budget80.py`, `analysis/report_budget80.py`, `analysis/package_budget80.py`, `tests/test_revision.py`, README and canonical/protocol documentation.

Executed 800 sensitivity candidates and 1,200 canonical candidates (2,000 total), each with three training and five selection rollouts. Experiment 2 independently tests frozen nominal gains on ten held-out noise seeds per condition. Experiment 3 was not performed; physical model and practical-selection rule are unchanged.

Validation: 34 tests, lint, 680 independent data/provenance/numerical checks. At 16→32 integration substeps, maximum absolute JT change was 7.37e-15 rad and JE change 3.33e-7 J; physical feasibility was unchanged. Prior archives (57 and 90 files) passed exact SHA-256 checks.

Important outcomes: 80 evaluations improved tracking minima but did not close the local tracking coverage gap. All eight feasible heavy-payload CT transfers had lower JT than the corresponding observed feasible local extreme. Two other 3 kg CT transfers violated the current limit (4.054780 and 3.884308 A), so their lower JT is not counted as feasible superiority. The combined feasible/practical flag holds in 43/45 conditions, while JT≤0.05 rad alone holds in all 45.

The previous canonical report and its raw archive remain at `reports/archive/canonical-final-20260924-budget40`; the older 2026-09-23 archive is also unchanged. New results are on branch `revision/budget80-bounds800-20260927`; no main-branch merge is performed.
