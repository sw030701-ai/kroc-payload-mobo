# Change and commit summary — 2026-09-24

Branch: `revision/practical-bound-sensitivity-20260924` (local; not pushed).

- `ef04ab6`: predeclared nominal bounds sensitivity; expanded canonical bounds
  [400,200,40]; zero anchor as one initial evaluation; practical JT<=0.05 selection;
  exact normalized-utopia CB; primary performance aggregation; regression tests.
- `17da804`: data-driven revised report builder, independent raw-data and numerical
  audit, source preservation checks, revised documentation and sensitivity zoom plots.
- `5bc2af3`: explicit same-test-seed diagnostic showing incomplete local tracking coverage at 2/3 kg.
- The following results commit preserves the original report bundle and records the
  new report, tables, figures, full raw-data archive, validation and SHA256 inventory.

## Changed implementation

- `configs/canonical_final.toml`: expanded bounds, initial zero anchor, explicit
  practical threshold and balanced rule. Physical model and all budgets/seeds unchanged.
- `configs/sensitivity_{original,expanded}.toml`: paired 1 kg pre-anchor protocols.
- `src/kroc_mobo/sensitivity.py`: fixed branch rule, paired diagnostics, observed-front plots.
- `src/kroc_mobo/mobo.py`: zero + 9 Sobol within the existing 10/40 evaluation budget.
- `src/kroc_mobo/metrics.py`: practical selection excludes zero PID, preserves the full front,
  logs normalization and exact CT/CB/CE definitions. Historical no-threshold API remains.
- `src/kroc_mobo/experiments.py`: anchor source label; frozen selection metadata; primary
  performance/percentage changes and separate practical satisfaction; supplementary set metrics.
- `src/kroc_mobo/config.py`, `io.py`: selection/anchor validation and Numba version provenance.
- `src/kroc_mobo/analysis.py`, `analysis/build_report.py`: primary tables/figures and data-derived findings.
- `analysis/audit_revision.py`, tests: raw means, seed separation, fixed gains, minimum selection,
  budget/anchor fairness, percentage denominators, archive integrity and RK4 refinement checks.
- `docs/CANONICAL_MODEL.md`, `docs/REVISION_PROTOCOL.md`, `README.md`: revised protocol and limitations.

## Execution and preservation

Sensitivity: 2 arms x 5 repeats x 40 evaluations, 3 train + 5 selection rollouts per candidate.
Canonical Experiment 1: 3 payloads x 5 repeats x 40 evaluations, 1,800 train + 3,000 selection rollouts.
Canonical Experiment 2: 2,650 unique held-out test rollouts plus 45 trace rollouts.
Representative numerical audit: 45 conditions x two RK4 resolutions, numerical checks only (not Experiment 3).

Executed canonical source commit: `ef04ab6`. Complete execution source snapshots and file hashes
are in the raw archive; current report/analysis source commit is `5bc2af3`. Subsequent changes only
corrected reporting/auditing and a zoom-display edge, not simulation, optimizer, selection or raw metrics.
The original sensitivity figure is also preserved under `analysis/initial-plots` in the raw archive.

Old report: `reports/archive/canonical-final-20260923`, with adjacent exact SHA256 inventory.
Old raw run: `results/canonical-final-qlog-v3`, untouched. Prior full root ZIP is also untouched.
Inspected remote main: `2f21d55fb8eadfbfed97a10e5a21e6b78594492b`; starting local code/config/docs/tests
matched remote Git blob hashes. No GitHub publication was performed.

32 tests passed; 569 data/provenance consistency checks passed. No Experiment 3 or additional
hold/thermal/backlash/driver model was implemented. HV/retention are supplementary.
