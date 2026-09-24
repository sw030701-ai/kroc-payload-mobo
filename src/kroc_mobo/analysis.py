"""Paper-facing tables and figures; repeated optimizations are never pooled as one front."""

import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "kroc-matplotlib"))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .io import load_snapshot, require_complete, save_csv
from .metrics import pareto


def _save(fig, directory, name, status):
    fig.suptitle(status, fontsize=9, color="#8a4b14")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(directory / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(directory / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def make_analysis(root):
    root = Path(root)
    c = load_snapshot(root)
    status = c["metadata"]["parameter_status"]
    directory = root / "analysis"
    directory.mkdir(exist_ok=True)
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "font.size": 10})
    setup = [
        {"section": section, "parameter": key, "value": str(value), "parameter_status": status}
        for section, values in c.items()
        for key, value in values.items()
    ]
    save_csv(directory / "table1_setup.csv", setup)
    if (root / "pilot" / "summary.csv").exists():
        for trace_path in sorted((root / "pilot").glob("trace_*.csv")):
            d = pd.read_csv(trace_path)
            fig, axes = plt.subplots(3, 2, figsize=(10, 8))
            axes[0, 0].plot(d.t, d.reference, "k--", label="Reference")
            axes[0, 0].plot(d.t, d.theta, label="Actual")
            axes[0, 0].set_ylabel("Angle [rad]")
            axes[0, 0].legend()
            for ax, col, label in zip(
                axes.flat[1:],
                ["error", "voltage", "current", "power", "energy_net"],
                ["Error [rad]", "Voltage [V]", "Current [A]", "Power [W]", "Net energy [J]"],
            ):
                ax.plot(d.t, d[col])
                ax.set_ylabel(label)
            for ax in axes.flat:
                ax.set_xlabel("Time [s]")
            _save(fig, directory, trace_path.stem, status)
    if not (root / "exp1" / "manifest.json").exists():
        return
    require_complete(root, "exp1")
    fronts = pd.read_csv(root / "exp1" / "pareto_all.csv")
    fig, ax = plt.subplots(figsize=(6, 4.5))
    colors = plt.get_cmap("tab10")
    for i, payload in enumerate(c["experiment"]["payloads"]):
        p = fronts.loc[fronts.payload == payload]
        for j, (repeat, group) in enumerate(p.groupby("repeat")):
            g = group.sort_values("JT")
            ax.plot(
                g.JT,
                g.JE,
                "o-",
                color=colors(i),
                alpha=0.65,
                markersize=4,
                label=f"{payload:g} kg" if j == 0 else None,
            )
    ax.set(xlabel="Tracking RMSE JT [rad]", ylabel="Net terminal energy JE [J]")
    if not fronts.empty:
        ax.legend(title="Separate lines: optimization repeats")
    else:
        ax.text(0.5, 0.5, "No feasible Pareto points", transform=ax.transAxes, ha="center")
    _save(fig, directory, "fig1_payload_pareto", status)
    selected = pd.read_csv(root / "exp1" / "selection_all.csv")
    result_rows = []
    for (repeat, payload), candidates in selected.groupby(["repeat", "payload"]):
        front = fronts.loc[(fronts.repeat == repeat) & (fronts.payload == payload)]
        result_rows.append(
            dict(
                repeat=repeat,
                payload=payload,
                attempted=len(candidates),
                feasible=int(candidates.feasible.sum()),
                pareto_count=len(front),
                JT_min=front.JT.min(),
                JT_max=front.JT.max(),
                JE_min=front.JE.min(),
                JE_max=front.JE.max(),
            )
        )
    result_frame = pd.DataFrame(result_rows)
    timing_path = root / "exp1" / "condition_summary.csv"
    if timing_path.exists():
        timings = pd.read_csv(timing_path)[["repeat", "payload", "elapsed_seconds"]]
        result_frame = result_frame.merge(timings, on=["repeat", "payload"])
    save_csv(directory / "exp1_results_per_repeat.csv", result_frame)
    summary_fields = [k for k in result_frame.columns if k not in ("repeat", "payload")]
    stats = result_frame.groupby("payload")[summary_fields].agg(["mean", "std"])
    stats.columns = [f"{a}_{b}" for a, b in stats.columns]
    save_csv(directory / "exp1_results_across_repeats.csv", stats.reset_index())
    # Discrete achievable tradeoffs at common thresholds; no fitted knee or extrapolation.
    comparisons = []
    for repeat, repeated in fronts.groupby("repeat"):
        groups = [repeated.loc[repeated.payload == m] for m in c["experiment"]["payloads"]]
        if any(g.empty for g in groups):
            continue
        for fixed, other in [("JT", "JE"), ("JE", "JT")]:
            lo, hi = max(g[fixed].min() for g in groups), min(g[fixed].max() for g in groups)
            if lo > hi:
                continue
            for threshold in np.linspace(lo, hi, 5):
                for payload, g in zip(c["experiment"]["payloads"], groups):
                    eligible = g.loc[g[fixed] <= threshold]
                    comparisons.append(
                        dict(
                            repeat=repeat,
                            payload=payload,
                            budget_objective=fixed,
                            budget=threshold,
                            optimized_objective=other,
                            achieved=eligible[other].min(),
                        )
                    )
    save_csv(
        directory / "common_budget_comparison.csv",
        pd.DataFrame(
            comparisons,
            columns=["repeat", "payload", "budget_objective", "budget", "optimized_objective", "achieved"],
        ),
    )
    if not (root / "exp2" / "manifest.json").exists():
        return
    require_complete(root, "exp2")
    summary = pd.read_csv(root / "exp2" / "transfer_summary.csv")
    save_csv(directory / "table2_transfer_per_repeat.csv", summary)
    fields = [key for key in ["R_P", "R_P_union", "L_HV", "N0", "N_ret", "N_feasible"] if key in summary]
    aggregated = summary.groupby("payload")[fields].agg(["mean", "std", "count"])
    aggregated.columns = [f"{a}_{b}" for a, b in aggregated.columns]
    save_csv(directory / "table2_transfer_across_repeats.csv", aggregated.reset_index())
    reps = pd.read_csv(root / "exp2" / "representative_performance.csv")
    save_csv(directory / "representative_performance.csv", reps)
    if not reps.empty:
        fields = ["JT", "JE", "delta_JT_pct", "delta_JE_pct", "feasible"]
        if "practical_satisfied" in reps:
            fields.append("practical_satisfied")
        primary = reps.groupby(["role", "payload"])[fields].agg(["mean", "std", "count"])
        primary.columns = [f"{a}_{b}" for a, b in primary.columns]
        save_csv(directory / "primary_representatives_across_repeats.csv", primary.reset_index())
        fig, axes = plt.subplots(1, 2, figsize=(9, 4))
        for i, role in enumerate(["CT", "CB", "CE"]):
            p = primary.loc[role].reset_index()
            for ax, key in zip(axes, ["JT", "JE"]):
                ax.errorbar(p.payload + (i - 1) * .035, p[f"{key}_mean"],
                            yerr=p[f"{key}_std"], fmt="o-", capsize=3, label=role)
        if "selection" in c:
            axes[0].axhline(c["selection"]["practical_JT_max"], ls="--", color="grey",
                            label="Nominal selection criterion")
        for ax, key, unit in zip(axes, ["JT", "JE"], ["rad", "J"]):
            ax.set(xlabel="Payload [kg]", ylabel=f"{key} [{unit}]", xticks=c["experiment"]["payloads"])
            ax.grid(alpha=.2)
            ax.legend(fontsize=8)
        _save(fig, directory, "fig3_primary_transfer", status + " | mean +/- SD across 5 optimization repeats")
    for repeat in range(c["experiment"]["repeats"]):
        fig, axes = plt.subplots(4, 3, figsize=(12, 10), squeeze=False, sharey="row")
        diagnostic, daxes = plt.subplots(2, 3, figsize=(12, 6), squeeze=False, sharey="row")
        found = False
        for col, role in enumerate(["CT", "CB", "CE"]):
            for i, payload in enumerate(c["experiment"]["payloads"]):
                path = root / "exp2" / f"repeat_{repeat:02d}" / f"payload_{payload:g}kg" / f"trace_{role}.csv"
                if not path.exists():
                    continue
                found = True
                d = pd.read_csv(path)
                if i == 0:
                    daxes[0, col].plot(d.t, d.reference, "k--", label="Reference")
                    axes[0, col].plot(d.t, d.reference, "k--", label="Reference")
                for row, key in enumerate(["theta", "error", "power", "energy_net"]):
                    axes[row, col].plot(d.t, d[key], color=colors(i), label=f"{payload:g} kg")
                for row, key in enumerate(["theta", "power"]):
                    daxes[row, col].plot(d.t, d[key], color=colors(i), label=f"{payload:g} kg")
            for axs in (axes, daxes):
                axs[0, col].set_title(role)
                axs[-1, col].set_xlabel("Time [s]")
        axes[0, 0].set_ylabel("Angle [rad]")
        axes[1, 0].set_ylabel("Tracking error [rad]")
        axes[2, 0].set_ylabel("Terminal power [W]")
        axes[3, 0].set_ylabel("Net energy [J]")
        daxes[0, 0].set_ylabel("Angle [rad]")
        daxes[1, 0].set_ylabel("Terminal power [W]")
        if found:
            axes[0, 0].legend()
            daxes[0, 0].legend()
            _save(fig, directory, f"fig2_representative_r{repeat:02d}", status + " | first paired test seed")
            _save(diagnostic, directory, f"diagnostic_angle_power_r{repeat:02d}", status)
        else:
            plt.close(fig)
            plt.close(diagnostic)
    transferred = pd.read_csv(root / "exp2" / "transfer_all.csv")
    local = pd.read_csv(root / "exp2" / "local_retested_all.csv")
    for repeat in range(c["experiment"]["repeats"]):
        fig, axes = plt.subplots(1, len(c["experiment"]["payloads"]), figsize=(12, 4), squeeze=False)
        for ax, payload in zip(axes.flat, c["experiment"]["payloads"]):
            for label, frame, marker in [("Transferred", transferred, "o"), ("Local retested", local, "s")]:
                p = pareto(frame.loc[(frame.repeat == repeat) & (frame.payload == payload)])
                ax.plot(p.JT, p.JE, marker + "-", label=label)
            ax.set(title=f"{payload:g} kg", xlabel="JT [rad]", ylabel="JE [J]")
            ax.legend()
        _save(fig, directory, f"transfer_vs_local_r{repeat:02d}", status)
