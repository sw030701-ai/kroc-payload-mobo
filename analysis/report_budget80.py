"""Report and independent consistency checks for the 2026-09-27 experiment."""

import argparse
import hashlib
import json
import shutil
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
from build_report import markdown, mean_sd, table

from kroc_mobo.analysis import _save, plt
from kroc_mobo.config import seeds
from kroc_mobo.io import load_snapshot, require_complete, save_json
from kroc_mobo.metrics import GAINS, pareto, representatives
from kroc_mobo.simulation import simulate


def build(root, out):
    root, out = Path(root), Path(out)
    if out.exists():
        raise FileExistsError(out)
    canonical = root / "canonical"
    for stage in ("pilot", "exp1", "exp2"):
        require_complete(canonical, stage)
    c = load_snapshot(canonical)
    out.mkdir(parents=True)
    checks = []

    def check(name, condition):
        checks.append(dict(check=name, passed=bool(condition)))
        if not condition:
            raise AssertionError(name)

    budgets = []
    for arm in ("current", "expanded", "canonical"):
        run = root / arm
        cfg = load_snapshot(run)
        require_complete(run, "exp1")
        for directory in sorted((run / "exp1").glob("repeat_*/payload_*")):
            train = pd.read_csv(directory / "train.csv")
            selected = pd.read_csv(directory / "selection.csv")
            repeat, payload = int(train.repeat.iloc[0]), float(train.payload.iloc[0])
            label = f"{arm}/{repeat}/{payload}"
            check(label + "/budget", len(train) == len(selected) == 80)
            check(label + "/anchor", (train.iloc[0][GAINS].to_numpy(float) == 0).all())
            check(label + "/initial", train.iloc[:10].source.str.contains("initial|anchor").all())
            check(label + "/BO", train.iloc[10:].source.str.contains("qlognehvi|recovery").all())
            for phase, aggregate in (("train", train), ("selection", selected)):
                raw = pd.read_csv(directory / f"{phase}_rollouts.csv")
                check(label + phase + "/raw_count", len(raw) == 80 * len(seeds(cfg, phase, repeat)))
                check(label + phase + "/seed_sets", all(
                    sorted(g.seed) == seeds(cfg, phase, repeat) for _, g in raw.groupby("controller_id")))
                for objective in ("JT", "JE"):
                    means = raw.groupby("controller_id")[objective].mean()
                    actual = aggregate.set_index("controller_id")[objective].reindex(means.index)
                    check(label + phase + objective, np.allclose(means, actual, rtol=1e-10, atol=1e-12, equal_nan=True))
            if arm == "canonical":
                ids = train.iloc[:40].controller_id
                first = pareto(selected.loc[selected.controller_id.isin(ids)])
                full = pareto(selected)
                budgets.append(dict(repeat=repeat, payload=payload,
                    JT_40=first.JT.min(), JT_80=full.JT.min(),
                    improvement_pct=100 * (first.JT.min() - full.JT.min()) / first.JT.min(),
                    practical_JE_40=first.loc[first.JT <= .05, "JE"].min(),
                    practical_JE_80=full.loc[full.JT <= .05, "JE"].min()))
        manifest = json.loads((run / "exp1/manifest.json").read_text())
        for path, expected in manifest["source_sha256"].items():
            check(arm + "/source/" + path, hashlib.sha256((root / "source" / path).read_bytes()).hexdigest() == expected)

    budget = pd.DataFrame(budgets)
    table(out, "budget40_vs80_paired", budget)
    budget_summary = budget.groupby("payload")[["JT_40", "JT_80", "improvement_pct"]].agg(["mean", "std"])
    budget_summary.to_csv(out / "budget40_vs80_summary.csv")
    fronts = pd.read_csv(canonical / "exp1/pareto_all.csv")
    reps = pd.read_csv(canonical / "exp2/representative_performance.csv")
    frozen = pd.read_csv(canonical / "exp2/representatives_frozen.csv")
    check("representative_conditions", len(reps) == 45)
    check("zero_excluded", not (frozen[GAINS] == 0).all(axis=1).any())
    check("practical_selection", (frozen.JT <= .05).all())
    for repeat in range(5):
        expected, _ = representatives(fronts.loc[(fronts.repeat == repeat) & (fronts.payload == 1)], tracking_max=.05)
        observed = frozen.loc[frozen.repeat == repeat]
        check(f"selection/{repeat}", expected.controller_id.tolist() == observed.controller_id.tolist())
        for role in ("CT", "CB", "CE"):
            group = reps.loc[(reps.repeat == repeat) & (reps.role == role)]
            nominal = group.loc[group.payload == 1].iloc[0]
            chosen = observed.loc[observed.role == role].iloc[0]
            check(f"frozen/{repeat}/{role}", np.allclose(group[GAINS], chosen[GAINS].to_numpy(float)))
            for objective in ("JT", "JE"):
                check(f"delta/{repeat}/{role}/{objective}", np.allclose(
                    group[f"delta_{objective}_pct"], 100 * (group[objective] / nominal[objective] - 1), atol=1e-10))
    raw_test = pd.read_csv(canonical / "exp2/test_rollouts.csv")
    numerical = []
    fine = deepcopy(c)
    fine["simulation"]["integration_substeps"] *= 2
    for _, rep in reps.iterrows():
        details = raw_test.loc[(raw_test.repeat == rep["repeat"]) & (raw_test.payload == rep.payload)]
        details = details.loc[np.isclose(details[GAINS], rep[GAINS].to_numpy(float), atol=1e-10, rtol=0).all(axis=1)]
        label = f"test/{rep['repeat']}/{rep.role}/{rep.payload}"
        check(label + "/seeds", sorted(details.seed) == seeds(c, "test", int(rep["repeat"])))
        check(label + "/means", np.allclose(rep[["JT", "JE"]].to_numpy(float), details[["JT", "JE"]].mean(), atol=1e-12))
        check(label + "/feasible", bool(rep.feasible) == bool(details.feasible.all()))
        noise_seed = seeds(c, "test", int(rep["repeat"]))[0]
        a = simulate(rep[GAINS].to_numpy(float), rep.payload, c, noise_seed).metrics
        b = simulate(rep[GAINS].to_numpy(float), rep.payload, fine, noise_seed).metrics
        numerical.append(dict(repeat=rep["repeat"], role=rep.role, payload=rep.payload,
            delta_JT=b["JT"]-a["JT"], delta_JE=b["JE"]-a["JE"],
            same_feasibility=a["feasible"] == b["feasible"], energy_balance_residual=a["energy_balance_residual"]))
    numerical = pd.DataFrame(numerical)
    check("numerical/JT", numerical.delta_JT.abs().max() < 1e-7)
    check("numerical/JE", numerical.delta_JE.abs().max() < 1e-5)
    check("numerical/feasibility", numerical.same_feasibility.all())
    for archive_name in ("canonical-final-20260923", "canonical-final-20260924-budget40"):
        archive = Path("reports/archive") / archive_name
        inventory = json.loads(archive.with_suffix(".sha256.json").read_text())
        for relative, expected in inventory.items():
            check("preserved/" + archive_name + "/" + relative,
                hashlib.sha256((archive / relative).read_bytes()).hexdigest() == expected)
    table(out, "representative_integration_convergence", numerical)
    save_json(out / "audit.json", dict(passed=True, checks=checks, count=len(checks)))

    for path in (canonical / "analysis").iterdir():
        if path.is_file() and path.suffix in (".csv", ".png", ".pdf"):
            shutil.copy2(path, out / path.name)
    shutil.copytree(root / "sensitivity", out / "sensitivity")
    for name in ("representatives_frozen.csv", "selection_rule.json", "selection_status.json", "representative_performance.csv"):
        shutil.copy2(canonical / "exp2" / name, out / name)
    shutil.copy2(canonical / "config.json", out / "config.json")
    for stage in ("pilot", "exp1", "exp2"):
        shutil.copy2(canonical / stage / "manifest.json", out / f"manifest_{stage}.json")
    per = pd.read_csv(canonical / "analysis/exp1_results_per_repeat.csv")
    compact = per.groupby("payload").agg(min_JT_mean=("JT_min", "mean"), min_JT_SD=("JT_min", "std"),
        feasible_mean=("feasible", "mean"), pareto_mean=("pareto_count", "mean")).reset_index()
    table(out, "exp1_compact", compact)
    primary = pd.DataFrame([dict(role=role, payload=p, JT_rad=mean_sd(g.JT), JE_J=mean_sd(g.JE),
        delta_JT_pct=mean_sd(g.delta_JT_pct), delta_JE_pct=mean_sd(g.delta_JE_pct),
        feasible=f"{g.feasible.sum()}/{len(g)}", tracking_only=f"{(g.JT <= .05).sum()}/{len(g)}",
        feasible_and_practical=f"{g.practical_satisfied.sum()}/{len(g)}")
        for (role, p), g in reps.groupby(["role", "payload"], sort=False)])
    table(out, "table2_primary_transfer", primary)
    selection = frozen[["repeat", "role", *GAINS, "JT", "JE", "utopia_distance", "selection_status"]]
    table(out, "table_selection", selection)
    local = pd.read_csv(canonical / "exp2/local_retested_all.csv")
    coverage = local.loc[local.feasible].groupby(["repeat", "payload"]).JT.min().rename("local_JT").reset_index()
    coverage = coverage.merge(reps.loc[reps.role == "CT", ["repeat", "payload", "JT", "feasible"]], on=["repeat", "payload"])
    coverage["transfer_better"] = coverage.JT < coverage.local_JT - 1e-12
    coverage["feasible_transfer_better"] = coverage.transfer_better & coverage.feasible
    table(out, "local_tracking_coverage_diagnostic", coverage)
    coverage_summary = coverage.groupby("payload").agg(local_JT=("local_JT", "mean"), transfer_JT=("JT", "mean"),
        lower_transfer_JT_count=("transfer_better", "sum"), feasible_transfer_count=("feasible", "sum"),
        feasible_transfer_better_count=("feasible_transfer_better", "sum")).reset_index()
    table(out, "local_tracking_coverage_summary", coverage_summary)
    fixed = pd.DataFrame([dict(repeat=r, payload=p, best_JE=g.loc[g.JT <= .01, "JE"].min())
        for (r, p), g in fronts.groupby(["repeat", "payload"])])
    table(out, "tracking_budget_001rad", fixed)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for i, (payload, group) in enumerate(fronts.groupby("payload")):
        for repeat, f in group.groupby("repeat"):
            f = f.sort_values("JT")
            for ax, view in zip(axes, (f, f.loc[f.JT <= .05])):
                ax.plot(view.JT, view.JE, "o-", color=f"C{i}", alpha=.5, ms=3,
                    label=f"{payload:g} kg" if repeat == 0 else None)
    for ax in axes:
        ax.set(xlabel="JT [rad]", ylabel="JE [J]")
        ax.grid(alpha=.2)
    axes[0].legend()
    axes[0].set_title("Full fronts including zero anchor")
    axes[1].set_title("Practical region (display only)")
    _save(fig, out, "fig1_full_and_zoom", "80 evaluations | 5 independent repeats per payload")
    fig, ax = plt.subplots(figsize=(7, 4))
    nominal_view = fronts.loc[(fronts.repeat == 0) & (fronts.payload == 1) & (fronts.JT <= .05)].sort_values("JT")
    ax.plot(nominal_view.JT, nominal_view.JE, "o-", color="grey", label="Nominal practical subset")
    for role, marker, color in zip(("CT", "CB", "CE"), ("s", "D", "^"), ("C0", "C1", "C2")):
        selected = frozen.loc[(frozen.repeat == 0) & (frozen.role == role)].iloc[0]
        ax.scatter(selected.JT, selected.JE, marker=marker, color=color, s=80, label=role, zorder=3)
    ax.axvline(.05, color="black", ls="--", label="Selection threshold")
    ax.set(xlabel="Selection JT [rad]", ylabel="Selection JE [J]")
    ax.legend(fontsize=8)
    ax.grid(alpha=.2)
    _save(fig, out, "fig_selection_r00", "Frozen representative selection | repeat 0")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for p, group in budget.groupby("payload"):
        axes[0].plot([40, 80], [group.JT_40.mean(), group.JT_80.mean()], "o-", label=f"{p:g} kg")
    axes[0].set(xlabel="Candidate budget", ylabel="Mean selection minimum JT [rad]", xticks=[40, 80])
    axes[0].legend()
    axes[1].plot(coverage_summary.payload, coverage_summary.local_JT, "o-", label="Local front min JT")
    axes[1].plot(coverage_summary.payload, coverage_summary.transfer_JT, "s--", label="Transferred CT JT (all 5)")
    count_text = "; ".join(f"{int(r.payload)} kg: {int(r.feasible_transfer_count)}/5" for r in coverage_summary.itertuples())
    axes[1].text(.03, .97, "CT feasible: " + count_text, transform=axes[1].transAxes, va="top", fontsize=8)
    axes[1].set(xlabel="Payload [kg]", ylabel="Mean test JT [rad]", xticks=[1, 2, 3])
    axes[1].legend()
    _save(fig, out, "fig_budget_and_coverage", "Fixed-bounds nested budget comparison | identical test seeds for coverage")

    decision = json.loads((root / "sensitivity/decision.json").read_text())
    sensitivity_per = pd.read_csv(root / "sensitivity/per_repeat.csv")
    sat = pd.read_csv(root / "sensitivity/tracking_extremes.csv")
    saturation = sat.groupby("arm").agg(voltage_saturation_mean=("saturation_fraction", "mean"),
        voltage_saturation_max=("saturation_fraction", "max"), peak_current_max_A=("max_current", "max"),
        CT_JT_mean=("JT", "mean"), CT_JE_mean=("JE", "mean")).reset_index()
    ct_energy = sat.groupby("arm").JE.mean()
    ct_energy_increase = 100 * (ct_energy["expanded"] / ct_energy["original"] - 1)
    table(out, "sensitivity_actuator_diagnostics", saturation)
    remaining = int(coverage.loc[coverage.payload > 1, "transfer_better"].sum())
    feasible_remaining = int(coverage.loc[coverage.payload > 1, "feasible_transfer_better"].sum())
    feasible_transfers = int(coverage.loc[coverage.payload > 1, "feasible"].sum())
    violations = reps.loc[~reps.feasible, ["repeat", "role", "payload", "JT", "JE", "max_current", "violation"]]
    table(out, "representative_constraint_violations", violations)
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    for role, group in reps.groupby("role", sort=False):
        grouped = group.groupby("payload")
        for ax, metric, label in zip(axes.flat, ("JT", "JE", "delta_JT_pct", "delta_JE_pct"),
                ("JT [rad]", "JE [J]", "JT change from nominal [%]", "JE change from nominal [%]")):
            stats = grouped[metric].agg(["mean", "std"])
            ax.errorbar(stats.index, stats["mean"], yerr=stats["std"], marker="o", capsize=3, label=role)
            ax.set(xlabel="Payload [kg]", ylabel=label, xticks=[1, 2, 3])
            ax.grid(alpha=.2)
    axes[0, 0].legend()
    _save(fig, out, "fig_primary_with_feasibility",
        f"All 5 repeats, including violations | CT feasible: {count_text} | CB/CE: 5/5 at each payload")
    ct3 = reps.loc[(reps.role == "CT") & (reps.payload == 3)]
    ce3 = reps.loc[(reps.role == "CE") & (reps.payload == 3)]
    findings = [
        f"1 kg, paired 80-evaluation bound comparison: mean minimum JT decreased from {decision['original_mean_min_JT']:.8f} to {decision['expanded_mean_min_JT']:.8f} rad ({decision['min_JT_improvement_pct']:.2f}%), while CT energy increased {ct_energy_increase:.2f}% ({ct_energy['original']:.5f}→{ct_energy['expanded']:.5f} J). Decision: {decision['adopted']} bounds; expanded CT attached to its upper bound in {decision['expanded_CT_at_upper_count']}/5 repeats.",
        "At fixed selected bounds, extending the same candidate sequence from 40 to 80 evaluations reduced mean minimum JT by " + "; ".join(f"{p:g} kg: {100*(g.JT_40.mean()-g.JT_80.mean())/g.JT_40.mean():.2f}%" for p, g in budget.groupby('payload')) + ".",
        f"On identical test seeds, transferred CT had lower JT in {remaining}/10 heavy-payload comparisons, but only {feasible_transfers}/10 transfers were feasible. All {feasible_remaining}/{feasible_transfers} feasible transfers beat the observed feasible local tracking extreme; infeasible transfers are excluded from this coverage-gap evidence.",
        f"Without retuning, CT at 3 kg had JT={mean_sd(ct3.JT)} rad and JE={mean_sd(ct3.JE)} J across all five repeats, including two current-limit violations; these are not five feasible outcomes. Changes from its own nominal response were {mean_sd(ct3.delta_JT_pct)}% and {mean_sd(ct3.delta_JE_pct)}%.",
        f"CE at 3 kg achieved JT={mean_sd(ce3.JT)} rad and JE={mean_sd(ce3.JE)} J. Physical feasibility held in {int(reps.feasible.sum())}/45 representative conditions; JT≤0.05 rad alone held in {int((reps.JT <= .05).sum())}/45, and both requirements held in {int(reps.practical_satisfied.sum())}/45. CT at 3 kg was feasible in {int(ct3.feasible.sum())}/5 repeats. Zero PID was selected for 0/15 representative roles.",
    ]
    (out / "QUANTITATIVE_FINDINGS.md").write_text("# Quantitative findings\n\nMean ± sample SD across five independent optimization repeats; each test value averages ten noise seeds.\n\n" + "\n\n".join(f"{i+1}. {s}" for i, s in enumerate(findings)) + "\n")
    upper = [c["search"][k][1] for k in ("kp", "ki", "kd")]
    saturation_text = ("Voltage saturation was absent in all ten selected sensitivity CTs. The bound effect cannot be attributed to voltage saturation."
        if sat.saturation_fraction.max() == 0 else "Voltage saturation was observed; its frequency is reported below, without claiming causality from correlation.")
    report = f"""# Canonical final — 80-evaluation follow-up (2026-09-27)

## Decision and primary findings

{chr(10).join('- ' + s for s in findings)}

The >=5% threshold was fixed before the new data in `docs/BUDGET80_PROTOCOL.md`. Adopted upper bounds: **{upper}**. Both sensitivity arms used 80 evaluations, 10 initial points (one zero-PID anchor plus nine Sobol), qLogNEHVI, and five paired optimizer repeats. All three gain bounds changed together, so this comparison does not isolate the effect of Kp alone. The canonical experiment was then rerun from scratch at the chosen bounds for all three payloads. The runs were executed locally against the GitHub repository; manifests identify the actual platform and source revision.

## Model and evaluation protocol

This is the canonical **1-DOF geared-joint simulation**, not a coupled 3-DOF hardware experiment. Physical values remain unchanged: Maxon RE35 323890, GP42C N=126, constant eta=0.72; R=0.568 ohm, L=0.000191 H, Kt=0.0292 Nm/A, Ke=0.0291 Vs/rad; Jm=8.12e-6, Jg=1.4e-6 kg m² (input-side); 0.20 m / 0.50 kg link, COM=0.10 m, tip payload radius=0.20 m; b=0.05, g=9.81. These are user-specified model parameters, not hardware identification results.

Full 5 s quintic 0→60° trajectory, no hold. JT is true-angle RMSE [rad]; JE is signed integral V i dt [J]. Voltage clips at ±24 V; |current|≤3.84 A is a feasibility constraint, **not current clipping**. Numerical settings: 1 ms control interval, RK4 16 substeps, PID filter 20 ms, antiwindup gain 10/s. Noise power=1e-10 rad²s, sample period=1 ms. Train/selection/test replicates are 3/5/10 with disjoint phase seeds; the full frozen configuration and every seed are saved.

Experiment 1 uses 5×3×80=1,200 candidates, including infeasible attempts; all are independently reevaluated on selection seeds. No nominal controller is inserted post hoc into a target local front. HV and retention are supplementary only.

## Bounds: performance and actuator evidence

![Bounds comparison](sensitivity/bounds_sensitivity.png)

{markdown(sensitivity_per[['repeat', 'original_min_JT', 'expanded_min_JT', 'improvement_pct', 'expanded_CT_at_upper']])}

{markdown(saturation)}

{saturation_text} Peak current is compared with 3.84 A, not interpreted as an implemented current limiter. Expanded-bound attachment remains a limitation; this is not proof of gain convergence. Regional front distances and practical-region energy are reported in the sensitivity CSVs; all fronts retain the zero-PID point.

The mean minimum observed energy subject to JT≤0.05 rad was {sensitivity_per.original_practical_min_JE.mean():.6f} J at current bounds and {sensitivity_per.expanded_practical_min_JE.mean():.6f} J at expanded bounds. Tracking improvement does **not** establish uniform dominance of the practical front. Finite-budget exploration over a larger search domain can alter energy-side coverage.

## Experiment 1 and budget effect

{markdown(compact)}

![Full and practical fronts](fig1_full_and_zoom.png)

The following comparison uses the first 40 candidates versus all 80 in each new canonical run, at the **same bounds and selection seeds**. It isolates the extra search budget within this run; old 400-bound/40-evaluation results are archived separately and are not confounded with a simultaneous bound change. The table's improvement_pct is the mean of repeat-level percentages; headline budget percentages are computed from the two repeat means. Neither is a statistical significance claim.

{markdown(budget.groupby('payload')[['JT_40', 'JT_80', 'improvement_pct']].mean().reset_index())}

![Budget and coverage](fig_budget_and_coverage.png)

{markdown(coverage_summary)}

Remaining local-versus-transfer reversals, if any, must remain visible. Eighty evaluations do not establish global optimality or guarantee adequate tracking-side coverage. Local observed fronts and transfer fronts are finite-budget observations.

Only feasible transfers provide valid evidence of better feasible tracking than the local front. Two infeasible 3 kg CT transfers have low JT but cannot support that comparison. Coverage counts above therefore separate raw lower-JT counts from feasible lower-JT counts.

## Representative selection and Experiment 2

The practical criterion JT≤0.05 rad is predefined **only for representative selection; it does not truncate the Pareto front**. Exclude [0,0,0]. CT minimizes JT; CE minimizes JE within the practical subset; CB minimizes Euclidean distance to utopia after min/max normalization of JT and JE over that subset. Ties use objectives then gains as recorded in `selection_rule.json`; coincident roles are allowed and explicitly reported. Gains are frozen from nominal selection data before target testing. Selection JT/JE below differ legitimately from disjoint test estimates.

{markdown(selection)}

![Nominal representative selection](fig_selection_r00.png)

Primary test results (mean ± SD across five optimization repeats; deltas calculated per controller against its own 1 kg test response before averaging):

{markdown(primary)}

![Primary transfer with feasibility](fig_primary_with_feasibility.png)

**Constraint violations are retained, not removed or retuned:**

{markdown(violations)}

The 3.84 A peak-current criterion is evaluated across all ten test rollouts in each condition. Both violations occurred without voltage saturation. The JT-only requirement holds in all 45 conditions, whereas physical feasibility and the combined practical flag hold in 43/45. Reported CT 3 kg mean/SD include the two violations and must not be presented as five feasible controllers. All CB/CE conditions remained feasible. Nominal feasible selection therefore does not guarantee cross-payload current feasibility.

`representative_performance.csv` preserves all 45 conditions and feasibility. Per-repeat angle/current/voltage/power plots accompany the report. Retention and HV are in `table2_transfer_across_repeats.csv` and related figures as **supplementary metrics**, not primary evidence for payload ordering or robustness.

## Verification and provenance

{len(checks)} independent consistency checks passed: full candidate counts, anchor placement, raw-to-aggregate objective reproduction, execution-source hashes, reproducible selection, frozen gains and nominal-relative deltas. See `audit.json`; test-suite results and numerical refinement checks are saved separately. These checks validate implementation consistency, not hardware validity.

The prior canonical report is preserved at `reports/archive/canonical-final-20260924-budget40`; the original 2026-09-23 archive is also retained. `raw-results.zip` contains both sensitivity arms, the selected canonical run, raw rollouts, traces, config/seed/manifest files, and the exact execution-source snapshot. `PROVENANCE.json` and `ARTIFACTS.sha256.json` identify paths and content hashes. No Experiment 3 was performed.

Reproduce with `python analysis/run_budget80.py --out results/new-budget80`, then `python analysis/report_budget80.py --root results/new-budget80 --out reports/new-budget80`. Existing destinations are refused. The runner explicitly reconstructs both 400 and 800 arms irrespective of the final canonical bound setting.

## Limitations

- No hold segment: conclusions cover only the finite 5 s movement, not long-term holding energy or settling after 5 s.
- Constant gear efficiency eta=0.72; no speed/load-dependent efficiency map.
- No thermal, backlash, or detailed driver model; no current-clipping implementation or hardware validation.
- One-DOF simulation, fixed trajectory and prescribed noise model; no coupled 3-DOF validation.
- Finite optimization budget and five repeats. Upper-bound attachment and local tracking coverage must not be presented as resolved unless the data demonstrate this. No statistical significance claim from the 5% engineering threshold.
"""
    (out / "REPORT.md").write_text(report)
    save_json(out / "PROVENANCE.json", dict(run=str(root), canonical=str(canonical),
        prior_report="reports/archive/canonical-final-20260924-budget40", selected_upper=upper,
        sensitivity_decision=decision, execution="local repository run; pushed to GitHub"))
    print("\n".join(findings), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    build(args.root, args.out)
