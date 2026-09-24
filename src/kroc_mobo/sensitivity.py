"""Predeclared, paired gain-bound sensitivity; no target-payload data used."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .config import bounds, seeds
from .io import load_snapshot, require_complete, save_csv, save_json
from .metrics import GAINS, OBJECTIVES

IMPROVEMENT_THRESHOLD_PCT = 5.0
OUTSIDE_RANGE_FRACTION = 0.01
BOUNDARY_RANGE_FRACTION = 0.001
OVERLAP_DISTANCE = 0.05
TRACKING_JT_MAX = 0.01
PRACTICAL_JT_MAX = 0.05
TRACKING_BUDGETS = (0.005, 0.01, 0.02, 0.05)


def normalized_hausdorff(a, b):
    """Symmetric discrete distance, normalized by the pooled regional ranges."""
    a, b = np.asarray(a, float).reshape(-1, 2), np.asarray(b, float).reshape(-1, 2)
    if not len(a) or not len(b):
        return np.nan
    span = np.ptp(np.vstack([a, b]), axis=0)
    span[span == 0] = 1
    distance = np.linalg.norm(a[:, None, :] / span - b[None, :, :] / span, axis=2)
    return float(max(distance.min(axis=0).max(), distance.min(axis=1).max()))


def choose_bounds(improvement_pct, outside_old, overlap):
    reasons = []
    if improvement_pct >= IMPROVEMENT_THRESHOLD_PCT:
        reasons.append("mean_min_JT_improvement_at_least_5pct")
    if outside_old:
        reasons.append("expanded_CT_clearly_outside_original_bounds")
    if not reasons and not overlap:
        reasons.append("near_overlap_not_demonstrated_conservative_expansion")
    return ("expanded" if reasons else "original"), (reasons or ["under_5pct_and_near_overlap"])


def analyze(original, expanded, out):
    original, expanded, out = Path(original), Path(expanded), Path(out)
    if (out / "decision.json").exists():
        raise FileExistsError("Sensitivity decision already exists; use a new output directory")
    configs, fronts = [], []
    for root in (original, expanded):
        require_complete(root, "exp1")
        configs.append(load_snapshot(root))
        fronts.append(pd.read_csv(root / "exp1/pareto_all.csv"))
    c0, c1 = configs
    for section in ("plant", "simulation", "controller", "limits", "noise", "experiment", "mobo"):
        if c0[section] != c1[section]:
            raise ValueError(f"Unpaired sensitivity settings: {section}")
    if c0["experiment"]["payloads"] != [c0["experiment"]["nominal_payload"]]:
        raise ValueError("Sensitivity must use nominal payload only")
    b0, b1 = bounds(c0), bounds(c1)
    rows, budgets, controllers = [], [], []
    for repeat in range(c0["experiment"]["repeats"]):
        pair = [f.loc[f.repeat == repeat] for f in fronts]
        if any(p.empty for p in pair):
            raise ValueError(f"No feasible front at repeat {repeat}")
        ct0, ct1 = [p.sort_values(OBJECTIVES + GAINS, kind="stable").iloc[0] for p in pair]
        outside = bool(np.any(ct1[GAINS].to_numpy(float) > b0[:, 1] + OUTSIDE_RANGE_FRACTION * np.diff(b0)[:, 0]))
        row = dict(
            repeat=repeat,
            original_min_JT=float(ct0.JT), expanded_min_JT=float(ct1.JT),
            improvement_pct=float(100 * (ct0.JT - ct1.JT) / ct0.JT),
            expanded_CT_outside_old=outside,
        )
        for name, ct, b, p in zip(("original", "expanded"), (ct0, ct1), (b0, b1), pair):
            at_upper = (b[:, 1] - ct[GAINS].to_numpy(float)) <= BOUNDARY_RANGE_FRACTION * np.diff(b)[:, 0]
            row[f"{name}_CT_at_upper"] = bool(at_upper.any())
            practical = p.loc[p.JT <= PRACTICAL_JT_MAX]
            row[f"{name}_practical_count"] = len(practical)
            row[f"{name}_practical_min_JE"] = practical.JE.min()
            controllers.append(dict(
                arm=name, repeat=repeat, **{k:ct[k] for k in GAINS + OBJECTIVES},
                **{f"{g}_at_upper":bool(v) for g,v in zip(GAINS, at_upper)},
                outside_original=outside if name == "expanded" else False,
            ))
            for budget in TRACKING_BUDGETS:
                eligible = p.loc[p.JT <= budget]
                budgets.append(dict(arm=name, repeat=repeat, JT_budget_rad=budget,
                                    count=len(eligible), best_observed_JE=eligible.JE.min()))
        for name, threshold in (("tracking", TRACKING_JT_MAX), ("practical", PRACTICAL_JT_MAX)):
            subsets = [p.loc[p.JT <= threshold, OBJECTIVES].to_numpy() for p in pair]
            row[f"{name}_hausdorff"] = normalized_hausdorff(*subsets)
        rows.append(row)
    table = pd.DataFrame(rows)
    improvement = float(100 * (table.original_min_JT.mean() - table.expanded_min_JT.mean()) / table.original_min_JT.mean())
    distances = table[["tracking_hausdorff", "practical_hausdorff"]].to_numpy()
    overlap = bool(np.isfinite(distances).all() and np.all(distances <= OVERLAP_DISTANCE))
    adopted, reasons = choose_bounds(improvement, bool(table.expanded_CT_outside_old.any()), overlap)
    decision = dict(
        adopted=adopted, reasons=reasons, min_JT_improvement_pct=improvement,
        original_mean_min_JT=float(table.original_min_JT.mean()),
        expanded_mean_min_JT=float(table.expanded_min_JT.mean()),
        expanded_CT_outside_old_count=int(table.expanded_CT_outside_old.sum()),
        expanded_CT_at_upper_count=int(table.expanded_CT_at_upper.sum()),
        near_overlap=overlap, repeats=len(table),
        rule=dict(improvement_threshold_pct=IMPROVEMENT_THRESHOLD_PCT,
                  outside_range_fraction=OUTSIDE_RANGE_FRACTION,
                  boundary_range_fraction=BOUNDARY_RANGE_FRACTION,
                  overlap_distance=OVERLAP_DISTANCE,
                  tracking_JT_max=TRACKING_JT_MAX, practical_JT_max=PRACTICAL_JT_MAX),
        optimizer_seeds=[c0["experiment"]["base_seed"]+r for r in range(len(table))],
        selection_seeds=[seeds(c0,"selection",r) for r in range(len(table))],
        original=str(original), expanded=str(expanded),
        limitation="Finite-budget observed fronts; expanded boundary attachment is not resolved by this comparison.",
    )
    save_csv(out / "per_repeat.csv", table)
    save_csv(out / "tracking_budget_comparison.csv", budgets)
    save_csv(out / "tracking_extremes.csv", controllers)
    # Persist the machine-readable branching decision, including all thresholds.
    save_json(out / "decision.json", decision)
    from .analysis import _save, plt

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for arm, f, color in zip(("Original", "Expanded"), fronts, ("C0", "C1")):
        for repeat, group in f.groupby("repeat"):
            group = group.sort_values("JT")
            for ax in axes:
                ax.plot(group.JT, group.JE, "o-", ms=3, alpha=.6, color=color,
                        label=arm if repeat == 0 else None)
    for ax in axes:
        ax.set(xlabel="JT [rad]", ylabel="JE [J]")
        ax.grid(alpha=.2)
    axes[0].set_title("Full observed fronts")
    axes[1].set(xlim=(0, TRACKING_JT_MAX), title="Tracking side")
    axes[2].set(xlim=(0, PRACTICAL_JT_MAX), title="Practical region")
    practical_y = pd.concat(fronts).loc[lambda f:f.JT <= PRACTICAL_JT_MAX, "JE"]
    for ax in axes[1:]:
        ax.set_ylim(practical_y.min()-.05, practical_y.max()+.05)
    axes[0].legend()
    _save(fig, out, "bounds_sensitivity", "Nominal 1 kg | 5 paired repeats | 40 evaluations | pre-anchor")
    print(decision)
    return decision


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", required=True)
    parser.add_argument("--expanded", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    analyze(args.original, args.expanded, args.out)
