# Pilot diagnostic protocol 2026 10 23

Recorded before execution. Canonical model and main files are read-only inputs.
Local source HEAD 9a27fd0; GitHub default HEAD 2f21d55 differs. This experiment
uses the locally retained revision 4 canonical model, not the older default branch.
The requested /mnt/data/KRoC_Payload_MOBO_Final.docx is unavailable on this host.

1. H1: [800,400,80] truncates the nominal tracking extreme. Double upper bounds
   to [1600,800,160], unchanged lower bounds, qLogNEHVI settings, initial design,
   80 total evaluations, optimizer seeds 731..735, 3 training and 5 selection
   replicates. Compare five paired nominal repeats against saved canonical 80.
   A >=5% reduction of the mean feasible minimum JT is material sensitivity.
   Also report gain-bound contact within 0.1% of upper bound, current and energy.
   Boundary contact after expansion does not establish convergence.
2. H2: 80 evaluations leave residual budget sensitivity at heavy payloads.
   Audit existing five-repeat 2/3 kg qLogNEHVI continuations, 80 vs 160: exact
   inherited histories, raw means, seeds, feasibility, budgets and source hashes.
   Re-evaluate frozen winners on NEW paired seeds 400000+1000*r .. +9.
   Existing 160 optimization is reused, not claimed as newly computed.
3. H3: sampled peak current feasibility changes selected Pareto extremes.
   On the SAME evaluated candidate pool, compare canonical limits versus only
   removing current feasibility (retain numerical/angle/velocity limits).
   Select CT/CB/CE using the same JT<=.05 rule and re-evaluate selected controllers
   on the new seeds. This is a post hoc selection ablation, not unconstrained BO.
4. H4: HV is consistent under common [0.1 rad,10 J] scales and [1 rad,20 J]
   reference. Compare raw HV / product(scales) against scaled HV, count points
   excluded by reference, audit every active canonical/diagnostic config and
   acquisition sign conversion. Representative min/max normalization is a
   separate nominal-only selection rule and must not replace HV normalization.
5. H5: payload and energy definitions are internally consistent. Calculate Jeq,
   reflected inertia and gravity/static current for 0..5 kg (outside 1..3 is
   descriptive only). For all newly simulated raw rollouts test JE = drawn -
   returned and energy balance residual. Check expanded CT 16 vs 32 substeps
   using the same seed. No hardware validity or battery energy is inferred.

Freeze controllers before fresh evaluation. Report all repeats and failed cases.
Do not rank a current-infeasible controller as a feasible performance improvement.
Keep raw CSVs, config/source hashes, manifests, figures, console logs, scripts.
Original source/results/docs/configs/reports and synced sources stay unchanged.
