"""Independent consistency audit of saved raw results and expanded-gain numerics."""

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

from kroc_mobo.config import fingerprint, seeds
from kroc_mobo.io import load_snapshot, require_complete, save_csv, save_json
from kroc_mobo.simulation import simulate

GAINS = ["kp", "ki", "kd"]


def audit(root, out):
    root, out = Path(root), Path(out)
    if (out / "audit.json").exists():
        raise FileExistsError("Audit output exists; select a new directory")
    c = load_snapshot(root)
    repo = Path(__file__).resolve().parents[1]
    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    for stage in ("pilot", "exp1", "exp2"):
        require_complete(root, stage)
        m = json.loads((root / stage / "manifest.json").read_text())
        check(f"{stage} config hash", m["config_sha256"] == fingerprint(c))
        for path, expected in m["source_sha256"].items():
            snapshot = root / "source" / path
            source = snapshot if snapshot.exists() else repo / path
            check(
                f"{stage} source hash: {path}",
                hashlib.sha256(source.read_bytes()).hexdigest() == expected,
            )
            if Path(path).name not in {"analysis.py", "sensitivity.py"}:
                check(
                    f"current numerical/selection source unchanged: {path}",
                    hashlib.sha256((repo / path).read_bytes()).hexdigest() == expected,
                )
    e, threshold = c["experiment"], c["selection"]["practical_JT_max"]
    legacy = json.loads((repo / "reports/archive/canonical-final-20260923/config.json").read_text())
    for section in ("plant", "simulation", "controller", "limits", "noise", "experiment"):
        check(f"canonical {section} unchanged", c[section] == legacy[section])
    for key, value in legacy["mobo"].items():
        check(f"optimizer setting unchanged: {key}", c["mobo"][key] == value)
    check("expanded bounds", [c["search"][g][1] for g in GAINS] == [400, 200, 40])
    check("full 5x40 budget", e["repeats"] == 5 and c["mobo"]["n_evaluations"] == 40)
    front = pd.read_csv(root / "exp1/pareto_all.csv")
    selected = pd.read_csv(root / "exp1/selection_all.csv")
    frozen = pd.read_csv(root / "exp2/representatives_frozen.csv")
    reps = pd.read_csv(root / "exp2/representative_performance.csv")
    raw = pd.read_csv(root / "exp2/test_rollouts.csv")
    all_seeds = [
        s for r in range(e["repeats"]) for phase in ("train", "selection", "test") for s in seeds(c, phase, r)
    ]
    check("phase and repeat seeds disjoint", len(set(all_seeds)) == len(all_seeds))
    anchor_count = 0
    for r in range(e["repeats"]):
        designs = []
        for payload in e["payloads"]:
            directory = root / "exp1" / f"repeat_{r:02d}" / f"payload_{payload:g}kg"
            train = pd.read_csv(directory / "train.csv")
            initial = train.iloc[: c["mobo"]["n_initial"]]
            designs.append(initial[GAINS].to_numpy())
            check(f"budget r{r} p{payload}", len(train) == 40)
            check(
                f"first zero anchor r{r} p{payload}",
                (initial.iloc[0][GAINS] == 0).all() and initial.iloc[0].source == "known_zero_pid_anchor",
            )
            check(f"9 Sobol initial r{r} p{payload}", (initial.source == "sobol_initial").sum() == 9)
            for phase in ("train", "selection"):
                details = pd.read_csv(directory / f"{phase}_rollouts.csv")
                check(f"{phase} raw budget r{r} p{payload}", len(details) == 40 * e[f"{phase}_replicates"])
                check(f"{phase} seeds r{r} p{payload}", sorted(details.seed.unique()) == seeds(c, phase, r))
                means = details.groupby("controller_id")[["JT", "JE"]].mean()
                aggregate = pd.read_csv(directory / f"{phase}.csv").set_index("controller_id")
                check(
                    f"{phase} means match raw r{r} p{payload}",
                    np.allclose(
                        aggregate.loc[means.index, ["JT", "JE"]],
                        means,
                        atol=1e-12,
                        rtol=1e-10,
                        equal_nan=True,
                    ),
                )
            f = front.loc[(front.repeat == r) & (front.payload == payload)]
            anchors = f.loc[(f[GAINS] == 0).all(axis=1)]
            anchor_count += len(anchors)
            check(
                f"anchor retained on full front r{r} p{payload}",
                len(anchors) == 1 and anchors.JE.iloc[0] == 0,
            )
        check(f"paired initial design r{r}", all(np.array_equal(designs[0], d) for d in designs[1:]))
        p = front.loc[
            (front.repeat == r)
            & (front.payload == e["nominal_payload"])
            & (front.JT <= threshold)
            & (front[GAINS] != 0).any(axis=1)
        ].copy()
        f = frozen.loc[frozen.repeat == r].set_index("role")
        check(f"three roles r{r}", set(f.index) == {"CT", "CB", "CE"})
        check(f"CT exact minimum r{r}", np.isclose(f.loc["CT", "JT"], p.JT.min(), rtol=0, atol=1e-14))
        check(
            f"CE exact practical energy minimum r{r}",
            np.isclose(f.loc["CE", "JE"], p.JE.min(), rtol=0, atol=1e-14),
        )
        lo, span = p[["JT", "JE"]].min(), p[["JT", "JE"]].max() - p[["JT", "JE"]].min()
        norm = (p[["JT", "JE"]] - lo) / span.replace(0, 1)
        distance = np.sqrt((norm**2).sum(axis=1))
        check(
            f"CB exact utopia minimum r{r}",
            np.isclose(f.loc["CB", "utopia_distance"], distance.min(), atol=1e-12),
        )
    check("all 15 anchors preserved", anchor_count == 15)
    check("600 independently reevaluated candidates", len(selected) == 600)
    check("15 frozen role selections", len(frozen) == 15)
    check("no zero representatives", not (frozen[GAINS] == 0).all(axis=1).any())
    check("selection criterion holds", (frozen.JT <= threshold).all())
    check("45 representative test conditions", len(reps) == 45)
    for (repeat, role), group in reps.groupby(["repeat", "role"]):
        check(f"no retuning r{repeat} {role}", len(group[GAINS].drop_duplicates()) == 1)
        base = group.loc[group.payload == e["nominal_payload"]].iloc[0]
        for key in ("JT", "JE"):
            expected = 100 * (group[key] - base[key]) / base[key]
            check(
                f"paired {key} percentage r{repeat} {role}",
                np.allclose(group[f"delta_{key}_pct"], expected, atol=1e-9),
            )
        for _, rep in group.iterrows():
            details = raw.loc[(raw.repeat == repeat) & (raw.payload == rep.payload)]
            details = details.loc[
                np.isclose(details[GAINS], rep[GAINS].to_numpy(float), atol=1e-10, rtol=0).all(axis=1)
            ]
            check(f"10 held-out raw tests r{repeat} {role} p{rep.payload}", len(details) == 10)
            check(
                f"held-out seeds r{repeat} {role} p{rep.payload}",
                sorted(details.seed) == seeds(c, "test", repeat),
            )
            check(
                f"test means r{repeat} {role} p{rep.payload}",
                np.allclose(rep[["JT", "JE"]].to_numpy(float), details[["JT", "JE"]].mean(), atol=1e-12),
            )
            check(
                f"test physical feasibility r{repeat} {role} p{rep.payload}",
                bool(rep.feasible) == bool(details.feasible.all()),
            )
    # Numerical validation of each frozen role at every payload, using the first paired test seed.
    fine = deepcopy(c)
    fine["simulation"]["integration_substeps"] *= 2
    numerical = []
    for _, rep in reps.iterrows():
        noise_seed = seeds(c, "test", int(rep["repeat"]))[0]
        gains = rep[GAINS].to_numpy(float)
        a = simulate(gains, rep.payload, c, noise_seed).metrics
        b = simulate(gains, rep.payload, fine, noise_seed).metrics
        numerical.append(
            dict(
                repeat=rep["repeat"],
                role=rep.role,
                payload=rep.payload,
                delta_JT=b["JT"] - a["JT"],
                delta_JE=b["JE"] - a["JE"],
                same_feasibility=a["feasible"] == b["feasible"],
                energy_balance_residual=a["energy_balance_residual"],
            )
        )
    numerical = pd.DataFrame(numerical)
    check("expanded representative numerical JT convergence <1e-7 rad", numerical.delta_JT.abs().max() < 1e-7)
    check("expanded representative numerical JE convergence <1e-5 J", numerical.delta_JE.abs().max() < 1e-5)
    check("expanded representative convergence preserves feasibility", numerical.same_feasibility.all())
    archive = repo / "reports/archive/canonical-final-20260923"
    inventory = json.loads(archive.with_suffix(".sha256.json").read_text())
    for relative, expected in inventory.items():
        check(
            f"historical archive unchanged: {relative}",
            hashlib.sha256((archive / relative).read_bytes()).hexdigest() == expected,
        )
    historical = repo / "results/canonical-final-qlog-v3/exp2/manifest.json"
    if historical.exists():
        check(
            "historical raw run remains complete", json.loads(historical.read_text())["status"] == "completed"
        )
    save_csv(out / "representative_integration_convergence.csv", numerical)
    summary = dict(
        status="passed",
        checks=len(checks),
        items=checks,
        max_abs_delta_JT=float(numerical.delta_JT.abs().max()),
        max_abs_delta_JE=float(numerical.delta_JE.abs().max()),
        max_abs_energy_balance_residual=float(numerical.energy_balance_residual.abs().max()),
        feasible_conditions=int(reps.feasible.sum()),
        total_representative_conditions=len(reps),
        practical_conditions=int(reps.practical_satisfied.sum()),
        anchors=anchor_count,
        historical_raw_checked=historical.exists(),
    )
    save_json(out / "audit.json", summary)
    print({k: v for k, v in summary.items() if k != "items"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--audit", required=True)
    args = parser.parse_args()
    audit(args.out, args.audit)
