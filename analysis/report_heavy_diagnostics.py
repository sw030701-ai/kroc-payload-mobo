"""Audit and report supplementary search-budget and constrained tracking diagnostics."""

import argparse
import json
import shutil
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
from build_report import markdown, table
from scipy.stats import t

from kroc_mobo.analysis import _save, plt
from kroc_mobo.config import seeds
from kroc_mobo.heavy_diagnostics import best_feasible, confirm_seeds, read, sha
from kroc_mobo.io import load_snapshot, require_complete, save_json
from kroc_mobo.metrics import GAINS, pareto
from kroc_mobo.simulation import simulate


def build(parent, root, out):
    parent, root, out = Path(parent), Path(root), Path(out)
    if out.exists():
        raise FileExistsError(out)
    require_complete(root, "heldout")
    out.mkdir(parents=True)
    c = load_snapshot(root)
    checks, budget_rows, energy_rows, fronts = [], [], [], []

    def check(name, passed):
        checks.append(dict(name=name, passed=bool(passed)))
        if not passed:
            raise AssertionError(name)

    for mode in ("mobo160", "so40"):
        for repeat in range(5):
            for payload in (2., 3.):
                d = root / mode / f"repeat_{repeat:02d}" / f"payload_{payload:g}kg"
                original = parent / "exp1" / f"repeat_{repeat:02d}" / f"payload_{payload:g}kg"
                require_complete(d, "diagnostic")
                train, selected = read(d / "train.csv"), read(d / "selection.csv")
                label = f"{mode}/{repeat}/{payload}"
                count = 160 if mode == "mobo160" else 40
                check(label + "/budget", len(train) == len(selected) == count)
                check(label + "/zero", (train.iloc[0][GAINS].to_numpy(float) == 0).all())
                check(label + "/bounds", all(((train[k] >= v[0]) & (train[k] <= v[1])).all()
                    for k, v in c["search"].items()))
                manifest = json.loads((d / "diagnostic/manifest.json").read_text())
                heldout_start = json.loads((root / "heldout/manifest.json").read_text())["started_utc"]
                check(label + "/freeze_before_test", manifest["finished_utc"] <= heldout_start)
                for file, expected in manifest["parent_hashes"].items():
                    check(label + "/parent/" + file, sha(original / file) == expected)
                for file, expected in manifest["source_sha256"].items():
                    check(label + "/source/" + file, sha(root / "source" / file) == expected)
                for phase, aggregate in (("train", train), ("selection", selected)):
                    raw = read(d / f"{phase}_rollouts.csv")
                    check(label + phase + "/count", len(raw) == count * len(seeds(c, phase, repeat)))
                    check(label + phase + "/seed_sets", all(sorted(g.seed) == seeds(c, phase, repeat)
                        for _, g in raw.groupby("controller_id")))
                    values = aggregate.set_index("controller_id")
                    means = raw.groupby("controller_id")[["JT", "JE"]].mean()
                    check(label + phase + "/means", np.allclose(means, values.loc[means.index, ["JT", "JE"]],
                        atol=1e-12, rtol=1e-10, equal_nan=True))
                    flags = raw.groupby("controller_id").feasible.all()
                    check(label + phase + "/feasibility", (flags == values.loc[flags.index, "feasible"]).all())
                winner = read(d / "winner_frozen.csv").iloc[0]
                expected = best_feasible(selected)
                check(label + "/frozen_winner", winner.controller_id == expected.controller_id)
                if mode == "so40":
                    check(label + "/warmstart", train.iloc[1].source == "frozen_nominal_CT_warm_start")
                    nominal = read(parent / "exp2/representatives_frozen.csv")
                    ct = nominal.loc[(nominal.repeat == repeat) & (nominal.role == "CT")].iloc[0]
                    check(label + "/warmstart_gains", np.array_equal(train.iloc[1][GAINS].to_numpy(float), ct[GAINS].to_numpy(float)))
                    check(label + "/single_objective", train.iloc[10:].source.str.contains("qlognei_tracking|recovery").all())
                else:
                    base = read(original / "selection.csv")
                    old_train = read(original / "train.csv")
                    for cols, old, new in (([*GAINS, "JT", "JE", "x0", "x1", "x2"], old_train, train),
                            ([*GAINS, "JT", "JE"], base, selected)):
                        check(label + "/inherited_values/" + str(cols), np.allclose(old[cols], new.iloc[:80][cols],
                            rtol=0, atol=0, equal_nan=True))
                    check(label + "/inherited_ids", old_train.controller_id.tolist() == train.iloc[:80].controller_id.tolist())
                    old = best_feasible(base)
                    check(label + "/nested_minimum", winner.JT <= old.JT + 1e-14)
                    budget_rows.append(dict(repeat=repeat, payload=payload, JT80=old.JT, JT160=winner.JT,
                        improvement_pct=100*(old.JT-winner.JT)/old.JT))
                    for name, f in (("MOBO80", pareto(base)), ("MOBO160", pareto(selected))):
                        fronts.append(f.assign(arm=name))
                        for threshold in (.001, .002, .005, .01, .05):
                            region = f.loc[f.JT <= threshold]
                            energy_rows.append(dict(arm=name, repeat=repeat, payload=payload,
                                JT_max=threshold, observed_points=len(region), min_JE=region.JE.min()))
    budget = pd.DataFrame(budget_rows)
    table(out, "budget80_vs160", budget)
    table(out, "common_tracking_budget_energy", pd.DataFrame(energy_rows))
    summaries = []
    for payload, group in budget.groupby("payload"):
        improvement = 100*(group.JT80.mean()-group.JT160.mean())/group.JT80.mean()
        summaries.append(dict(payload=payload, JT80_mean=group.JT80.mean(), JT80_SD=group.JT80.std(),
            JT160_mean=group.JT160.mean(), JT160_SD=group.JT160.std(), improvement_pct=improvement,
            repeats_under_5pct=int((group.improvement_pct < 5).sum()),
            diagnosis="low_observed_budget_sensitivity" if improvement < 5 else "material_budget_sensitivity"))
    summary = pd.DataFrame(summaries)
    table(out, "budget_summary", summary)
    heldout, raw = read(root / "heldout/summary.csv"), read(root / "heldout/rollouts.csv")
    frozen = read(root / "heldout/frozen_candidates.csv")
    check("heldout/count", len(heldout) == 80 and len(raw) == 800)
    for (mode, repeat, payload, phase), group in raw.groupby(["mode", "repeat", "payload", "phase"]):
        row = heldout.loc[(heldout["mode"] == mode) & (heldout.repeat == repeat)
            & (heldout.payload == payload) & (heldout.phase == phase)].iloc[0]
        chosen = frozen.loc[(frozen["mode"] == mode) & (frozen.repeat == repeat) & (frozen.payload == payload)].iloc[0]
        label = f"heldout/{mode}/{repeat}/{payload}/{phase}"
        expected_seeds = confirm_seeds(repeat) if phase == "confirm" else seeds(c, "test", repeat)
        check(label + "/seeds", sorted(group.seed) == expected_seeds)
        check(label + "/frozen", np.allclose(group[GAINS], chosen[GAINS].to_numpy(float), rtol=0, atol=0))
        check(label + "/means", np.allclose(group[["JT", "JE"]].mean(), row[["JT", "JE"]].to_numpy(float), atol=1e-12))
        check(label + "/feasibility", bool(row.feasible) == bool(group.feasible.all()))
    comparisons = []
    for (repeat, payload, phase), group in raw.groupby(["repeat", "payload", "phase"]):
        ct = group.loc[group["mode"] == "CT"].set_index("seed")
        for mode in ("mobo80", "mobo160", "so40"):
            candidate = group.loc[group["mode"] == mode].set_index("seed").reindex(ct.index)
            diff = candidate.JT - ct.JT
            radius = t.ppf(.975, len(diff)-1)*diff.std(ddof=1)/np.sqrt(len(diff))
            feasible, ct_feasible = bool(candidate.feasible.all()), bool(ct.feasible.all())
            comparisons.append(dict(mode=mode, repeat=repeat, payload=payload, phase=phase,
                candidate_JT=candidate.JT.mean(), CT_JT=ct.JT.mean(), candidate_JE=candidate.JE.mean(),
                CT_JE=ct.JE.mean(), candidate_feasible=feasible, CT_feasible=ct_feasible,
                paired_delta_JT=diff.mean(), CI95_lower=diff.mean()-radius, CI95_upper=diff.mean()+radius,
                seed_wins=int((diff < -1e-12).sum()), observed_lower=bool(feasible and diff.mean() < -1e-12),
                clear_lower=bool(feasible and diff.mean()+radius < -1e-12),
                feasible_comparison=feasible and ct_feasible))
    comparison = pd.DataFrame(comparisons)
    table(out, "paired_comparisons_to_CT", comparison)
    evidence = comparison.groupby(["phase", "mode", "payload"]).agg(
        candidate_feasible=("candidate_feasible", "sum"), CT_feasible=("CT_feasible", "sum"),
        observed_lower=("observed_lower", "sum"), clear_lower=("clear_lower", "sum"),
        both_feasible=("feasible_comparison", "sum"), candidate_JT_mean=("candidate_JT", "mean"),
        CT_JT_mean=("CT_JT", "mean")).reset_index()
    table(out, "tracking_diagnostic_evidence", evidence)
    primary = heldout.groupby(["phase", "mode", "payload"])[["JT", "JE", "max_current", "feasible"]].agg(["mean", "std"])
    primary.to_csv(out / "heldout_mean_SD.csv")
    table(out, "heldout_all_conditions", heldout)
    table(out, "frozen_candidates", frozen)

    fine = deepcopy(c)
    fine["simulation"]["integration_substeps"] *= 2
    refined = []
    for row in frozen.to_dict("records"):
        gain = [row[g] for g in GAINS]
        seed = confirm_seeds(int(row["repeat"]))[0]
        a = simulate(gain, row["payload"], c, seed).metrics
        b = simulate(gain, row["payload"], fine, seed).metrics
        refined.append(dict(mode=row["mode"], repeat=row["repeat"], payload=row["payload"],
            delta_JT=b["JT"]-a["JT"], delta_JE=b["JE"]-a["JE"], same_feasible=a["feasible"]==b["feasible"]))
    refined = pd.DataFrame(refined)
    check("numerical/JT", refined.delta_JT.abs().max() < 1e-7)
    check("numerical/JE", refined.delta_JE.abs().max() < 1e-5)
    check("numerical/feasibility", refined.same_feasible.all())
    table(out, "integration_refinement", refined)

    for archive_name in ("canonical-final-20260923", "canonical-final-20260924-budget40", "canonical-final-20260927-budget80"):
        archive = Path("reports/archive") / archive_name
        for name, expected in json.loads(archive.with_suffix(".sha256.json").read_text()).items():
            check("archive/" + archive_name + "/" + name, sha(archive / name) == expected)
    save_json(out / "AUDIT.json", dict(passed=True, count=len(checks), checks=checks))
    save_json(out / "PROVENANCE.json", dict(parent=str(parent), root=str(root),
        parent_commit="83e88835e127d456e3a06233cd1ec6605016b1a1", main_budget=80,
        supplementary_mobo_total=160, supplementary_mobo_new=800, supplementary_so_new=400,
        total_new_train_rollouts=3600, total_new_selection_rollouts=6000, heldout_rollouts=800,
        search_bounds=c["search"], decision_threshold_pct=5, execution="local repository, two independent processes"))
    shutil.copy2(root / "protocol.md", out / "PROTOCOL.md")
    shutil.copy2(root / "config.json", out / "main_config.json")
    (out / "REVISION_HISTORY.md").write_text(Path("docs/REVISION_HISTORY.md").read_text().replace("(../reports/", "(../"))

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, (payload, group) in zip(axes, budget.groupby("payload")):
        for row in group.itertuples():
            ax.plot([80, 160], [row.JT80, row.JT160], "o-", alpha=.65, label=f"repeat {row.repeat}")
        ax.set(title=f"{payload:g} kg", xlabel="Total candidates", ylabel="Feasible selection min JT [rad]", xticks=[80, 160])
        ax.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    _save(fig, out, "fig_budget", "80 stored candidates + 80 new candidates | fixed bounds [800,400,80]")
    full = pd.concat(fronts)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, payload in zip(axes, (2., 3.)):
        for (arm, repeat), f in full.loc[(full.payload == payload) & (full.JT <= .01)].groupby(["arm", "repeat"]):
            f = f.sort_values("JT")
            ax.plot(f.JT, f.JE, "o-", ms=3, alpha=.5, color="C0" if arm == "MOBO80" else "C1",
                label=arm if repeat == 0 else None)
        ax.set(title=f"{payload:g} kg", xlabel="Selection JT [rad]", ylabel="JE [J]")
        ax.legend()
        ax.grid(alpha=.2)
    _save(fig, out, "fig_tracking_fronts", "Tracking-side view only | complete fronts retained in raw data")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    fresh = heldout.loc[heldout.phase == "confirm"]
    for ax, payload in zip(axes, (2., 3.)):
        for i, mode in enumerate(("CT", "mobo80", "mobo160", "so40")):
            group = fresh.loc[(fresh.payload == payload) & (fresh["mode"] == mode)]
            good, bad = group.loc[group.feasible], group.loc[~group.feasible]
            ax.scatter(np.full(len(good), i), good.JT, marker="o", color=f"C{i}")
            ax.scatter(np.full(len(bad), i), bad.JT, marker="x", color="red", s=60)
        ax.set(title=f"{payload:g} kg", xticks=range(4), xticklabels=["CT", "MOBO80", "MOBO160", "SO40"], ylabel="Fresh confirmation JT [rad]")
        ax.grid(alpha=.2)
    _save(fig, out, "fig_confirmation", "Five frozen candidates per mode | red x = constraint violation | SO40 is warm-started")
    findings = [f"{r.payload:g} kg: mean feasible selection min JT {r.JT80_mean:.8f}→{r.JT160_mean:.8f} rad, improvement {r.improvement_pct:.2f}%; {r.diagnosis}." for r in summary.itertuples()]
    for payload in (2., 3.):
        e = evidence.loc[(evidence.phase == "confirm") & (evidence["mode"] == "so40") & (evidence.payload == payload)].iloc[0]
        findings.append(f"SO40 at {payload:g} kg on fresh seeds: feasible {int(e.candidate_feasible)}/5, lower mean JT than CT {int(e.observed_lower)}/5, negative upper paired confidence limit {int(e.clear_lower)}/5; CT itself feasible {int(e.CT_feasible)}/5.")
    (out / "QUANTITATIVE_FINDINGS.md").write_text("# Quantitative findings\n\n" + "\n\n".join(f"{i+1}. {s}" for i, s in enumerate(findings)) + "\n")
    (out / "REPORT.md").write_text(f"""# 2/3 kg supplementary diagnostics — revision 4 (2026-10-01)

## Scope and decisions

Canonical bounds remain **[800,400,80]**. The main 80-evaluation Experiment 1/2 and its frozen controllers remain unchanged. These are supplementary diagnostics, not Experiment 3 and not evidence of optimizer superiority. Current-limit violations constrain cross-payload applicability; no voltage-saturation limit or global constrained optimum has been established.

{chr(10).join('- ' + x for x in findings)}

## 80→160 MOBO continuation

{markdown(summary)}

{markdown(budget)}

![Budget](fig_budget.png)

The first 80 candidate histories and raw observations are inherited unchanged and verified against the parent. Exactly 80 new candidates per condition are generated by the unchanged qLogNEHVI method; no transferred CT is inserted into the local MOBO history. The 5% rule was fixed before the new runs. Below 5% means low **observed sensitivity to this budget extension**, not sufficient coverage of the actual front. The minimum is selection-set feasible JT; all five repeats are reported. Larger improvements indicate remaining budget sensitivity. No further automatic rerun or bound expansion is performed.

![Tracking-side fronts](fig_tracking_fronts.png)

`common_tracking_budget_energy.csv` gives observed JE at common JT thresholds with available-point counts; absent feasible coverage is not interpolated. Full fronts, including zero anchors, remain in the raw archive. These plots connect observed points only.

## Short constrained single-objective diagnostic

Forty new target evaluations per payload/repeat, including ten initial points: zero PID, the frozen nominal CT and eight Sobol points. qLogNEI optimizes JT only with a separate constraint GP; JE is recorded. This deliberate warm start makes SO40 an existence probe, **not an equal-information performance comparison** with MOBO. Three training and five disjoint selection noise seeds are retained. Winners are frozen before test evaluation; the prior 80-evaluation MOBO winner, 160-evaluation winner and nominal CT are also tested.

{markdown(evidence)}

`observed_lower` requires candidate feasibility and lower mean JT than CT. `clear_lower` additionally requires a negative upper limit of the conditional paired 95% interval. Neither requires CT feasibility; `CT_feasible` and `both_feasible` explicitly show whether the reference itself passes constraints. An infeasible reference is not counted as a feasible-performance contest. The CSV of all paired comparisons provides the exact Boolean combination for each case. A null finding means no better feasible candidate was found within this finite diagnostic budget, not that none exists.

![Fresh held-out results](fig_confirmation.png)

The original test set uses ten paired seeds; confirmation uses ten newly reserved seeds 300000+1000r through +9. Confidence intervals describe noise variation conditional on fixed selected gains, not optimization-repeat uncertainty; no multiple-testing-adjusted significance or global-optimality claim is made. Feasibility means every rollout meets all existing peak-current, angle, velocity and numerical constraints. The current threshold is 3.84 A with no current clipping. A lower tracking error alone does not imply constraint feasibility or a better energy trade-off.

`frozen_candidates.csv` records all gains. For CT, the frozen JT/JE columns are its **nominal 1 kg selection values**, while payload denotes the target; other modes' frozen values are target selection values. Actual target JT/JE, peak current, voltage saturation and feasibility are in `heldout_all_conditions.csv`. No test-dependent retuning or replacement of the main CT/CB/CE is performed.

## Cost, audit and interpretation

qLogNEHVI allocates proposals to joint tracking–energy hypervolume improvement under constraints; it does not spend every evaluation minimizing JT alone. A transferred aggressive nominal controller can therefore have lower JT than the best observed target-local point without a logical contradiction. The nominal CT gains were [800,400,0] in all five parent repeats, so these data do not establish that its discovery was merely accidental. Search allocation and finite sampled coverage are plausible explanations; they do not by themselves establish causality or prove that no better feasible controller exists.

MOBO continuation adds 800 candidates across 2 payloads×5 repeats; SO40 adds 400. New training/selection rollouts are 3,600/6,000. Comparison testing adds 800 rollouts. Inherited 80-candidate costs are not counted as newly executed. These costs are supplementary; the main paper budget remains 80. An efficiency advantage over other optimizers is not established by these experiments.

{len(checks)} data/provenance checks passed, including exact inherited numeric values, candidate budgets, raw means and feasibility, seed sets, source hashes, frozen winners/gains, and all prior report archives. See `AUDIT.json`. Raw ZIP includes source snapshots, immutable configs/manifests, every candidate/rollout, frozen selections and checkpoint records. Temporary console stdout was not retained; all candidate/rollout data and completion manifests are preserved. The run was executed locally against the GitHub repository, using two separate worker processes with one Torch thread each.

## Revision history and limitations

See [수정 1–4 이력](../../docs/REVISION_HISTORY.md) for trigger → modification → evidence → remaining limitations, with dates and commits. The [main 80-evaluation report](../canonical-final/REPORT.md) remains the primary experiment. The prior unmodified copy is [archived](../archive/canonical-final-20260927-budget80/REPORT.md).

No global optimum, exact physical performance envelope or fully converged Pareto front is claimed. Five optimizer repeats and finite noise seeds cannot guarantee stochastic feasibility for all disturbances. Bounds remain finite; larger domains can increase search burden at fixed budget, without proving a particular adaptive sampling density. The model remains a user-specified 1-DOF simulation: no hold, constant gear efficiency, no thermal/backlash/detailed driver model, no coupled 3-DOF or hardware validation. HV/retention remain supplementary in the main report.

## Reproduction

Use the parent 80-evaluation raw archive and the repository checkout. Run `python -m kroc_mobo.heavy_diagnostics --parent results/budget80-20260927/canonical --out results/new-heavy`, then `python analysis/report_heavy_diagnostics.py --parent results/budget80-20260927/canonical --root results/new-heavy --out reports/new-heavy`. Existing output directories are refused unless explicitly resuming matching computation checkpoints. Do not use the older 40/80 report builders for these supplementary diagnostics.
""")
    print("\n".join(findings))
    print(f"AUDIT PASSED: {len(checks)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    build(args.parent, args.root, args.out)
