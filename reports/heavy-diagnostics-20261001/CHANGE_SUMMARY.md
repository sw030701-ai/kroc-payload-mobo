# Revision 4 delivery — 2026-10-03

- `37412f7`: predeclared heavy-payload continuation and constrained tracking diagnostics.
- `aaa761b`: recorded user-confirmed revision 1–4 history, audits and preserved main80 archive.
- `8aaa4b0`: fixed main budget and added supplementary interpretation/packaging.
- The enclosing delivery commit publishes raw records, reports, tables, figures, validation and final history.

Implementation: `src/kroc_mobo/heavy_diagnostics.py`, reporting/packaging programs, diagnostic tests, protocol and history. Main bounds [800,400,80] and main80 configuration are unchanged. New work comprises 800 MOBO continuation candidates, 400 single-objective candidates, 3,600 training rollouts, 6,000 selection rollouts and 800 held-out rollouts. No Experiment 3.

Results: 80→160 mean minimum feasible JT improved 9.16% (2 kg) and 26.93% (3 kg), both above 5%. SO40 found no feasible candidate beating CT on fresh paired mean JT. Neither convergence nor global optimality is established.

Validation: 37 tests passed; 1,292 data/provenance checks passed; integration refinement and archived file hashes verified. TESTS.txt records four library warnings. Temporary console stdout from the experiment was not retained; complete candidates, rollouts, seeds, source snapshots, checkpoints and completion manifests are preserved in raw-results.zip. Experiments ran locally against the GitHub repository, not on GitHub Actions.

The prior main80 report is archived unchanged. The current main report receives only a supplementary section and links; primary raw results and representative controllers are preserved. Revision history includes all companion changes and experiments for stages 1–4.
