"""Pilot, independent payload optimization, and frozen-set transfer protocol."""

import time
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd

from .config import seeds
from .io import finish_run, initialize_run, require_complete, save_csv, save_json
from .metrics import GAINS, pareto, representatives, transfer_metrics
from .simulation import evaluate, simulate


def condition_dir(root, stage, repeat, payload):
    return Path(root) / stage / f"repeat_{repeat:02d}" / f"payload_{payload:g}kg"


def evaluate_row(candidate, payload, c, noise_seeds, **labels):
    gains = [float(candidate[k]) for k in GAINS]
    result, raw = evaluate(gains, payload, c, noise_seeds)
    identity = {
        "controller_id": candidate["controller_id"],
        **dict(zip(GAINS, gains)),
        **labels,
        "payload": payload,
        "parameter_status": c["metadata"]["parameter_status"],
    }
    return {**identity, **result}, [{**identity, **row} for row in raw]


def run_pilot(c, root):
    manifest = initialize_run(root, c, "pilot")
    rows, raw, convergence = [], [], []
    for payload in c["experiment"]["payloads"]:
        for label, gains in c["pilot"].items():
            candidate = {"controller_id": label, **dict(zip(GAINS, gains))}
            metrics, rollouts = evaluate_row(candidate, payload, c, seeds(c, "train", 0), phase="pilot")
            rows.append(metrics)
            raw.extend(rollouts)
            trace = simulate(gains, payload, c, seeds(c, "train", 0)[0], record=True)
            save_csv(Path(root) / "pilot" / f"trace_{label}_{payload:g}kg.csv", trace.trace)
            fine = deepcopy(c)
            fine["simulation"]["integration_substeps"] *= 2
            refined = simulate(gains, payload, fine, seeds(c, "train", 0)[0]).metrics
            convergence.append(
                dict(
                    controller=label,
                    payload=payload,
                    JT=trace.metrics["JT"],
                    JT_refined=refined["JT"],
                    JE=trace.metrics["JE"],
                    JE_refined=refined["JE"],
                    delta_JT=refined["JT"] - trace.metrics["JT"],
                    delta_JE=refined["JE"] - trace.metrics["JE"],
                    energy_balance_residual=trace.metrics["energy_balance_residual"],
                )
            )
            print(
                f"pilot {payload:g} kg {label}: JT={metrics['JT']:.5g}, JE={metrics['JE']:.5g}, "
                f"feasible={metrics['feasible']}",
                flush=True,
            )
    save_csv(Path(root) / "pilot" / "summary.csv", rows)
    save_csv(Path(root) / "pilot" / "rollouts.csv", raw)
    save_csv(Path(root) / "pilot" / "integration_convergence.csv", convergence)
    finish_run(root, "pilot", manifest, rollout_count=len(raw) + 2 * len(rows))


def run_exp1(c, root):
    from .mobo import decode, sobol_design, suggest

    manifest = initialize_run(root, c, "exp1")
    start = time.perf_counter()
    all_fronts, all_selected, raw_count, optimization_count = [], [], 0, 0
    timings = []
    for repeat in range(c["experiment"]["repeats"]):
        opt_seed = c["experiment"]["base_seed"] + repeat
        design = sobol_design(c, opt_seed)
        for payload in c["experiment"]["payloads"]:
            condition_start = time.perf_counter()
            directory = condition_dir(root, "exp1", repeat, payload)
            history, raw = [], []
            save_json(
                directory / "seeds.json",
                {
                    "optimizer_seed": opt_seed,
                    "train": seeds(c, "train", repeat),
                    "selection": seeds(c, "selection", repeat),
                },
            )
            for index in range(c["mobo"]["n_evaluations"]):
                source, unit = "sobol_initial", design[index]
                if index >= c["mobo"]["n_initial"]:
                    if c["mobo"]["backend"] == "sobol":
                        source = "sobol_baseline"
                    else:
                        # Programming/fitting errors abort visibly; never silently claim a Sobol fallback is MOBO.
                        proposal, source = suggest(history, c, opt_seed * 10000 + index)
                        if proposal is not None:
                            unit = proposal
                candidate = dict(
                    controller_id=f"r{repeat}_p{payload:g}_c{index:04d}", **dict(zip(GAINS, decode(unit, c)))
                )
                row, detail = evaluate_row(
                    candidate,
                    payload,
                    c,
                    seeds(c, "train", repeat),
                    repeat=repeat,
                    phase="train",
                    candidate_index=index,
                    source=source,
                )
                row.update({f"x{i}": float(unit[i]) for i in range(3)})
                history.append(row)
                raw.extend(detail)
                optimization_count += len(detail)
                save_csv(directory / "train.csv", history)
                save_csv(directory / "train_rollouts.csv", raw)
                print(
                    f"exp1 repeat={repeat} payload={payload:g} {index + 1}/{len(design)} {source}: "
                    f"JT={row['JT']:.4g} JE={row['JE']:.4g} feasible={row['feasible']}",
                    flush=True,
                )
            validated, validation_raw = [], []
            # Re-evaluate ALL attempted candidates, not just noisy training-front winners.
            for candidate in history:
                row, detail = evaluate_row(
                    candidate, payload, c, seeds(c, "selection", repeat), repeat=repeat, phase="selection"
                )
                validated.append(row)
                validation_raw.extend(detail)
            frame = pd.DataFrame(validated)
            front = pareto(frame)
            all_fronts.append(front)
            all_selected.append(frame)
            raw_count += len(raw) + len(validation_raw)
            save_csv(directory / "selection.csv", frame)
            save_csv(directory / "selection_rollouts.csv", validation_raw)
            save_csv(directory / "pareto.csv", front)
            timings.append(
                dict(
                    repeat=repeat,
                    payload=payload,
                    elapsed_seconds=time.perf_counter() - condition_start,
                    attempted=len(history),
                    feasible=int(frame.feasible.sum()),
                    pareto_count=len(front),
                )
            )
            save_csv(Path(root) / "exp1" / "condition_summary.csv", timings)
    save_csv(Path(root) / "exp1" / "pareto_all.csv", pd.concat(all_fronts, ignore_index=True))
    save_csv(Path(root) / "exp1" / "selection_all.csv", pd.concat(all_selected, ignore_index=True))
    finish_run(
        root,
        "exp1",
        manifest,
        optimization_rollouts=optimization_count,
        selection_rollouts=raw_count - optimization_count,
        elapsed_seconds=time.perf_counter() - start,
    )


def run_exp2(c, root):
    require_complete(root, "exp1")
    manifest = initialize_run(root, c, "exp2")
    fronts = pd.read_csv(Path(root) / "exp1" / "pareto_all.csv")
    nominal = c["experiment"]["nominal_payload"]
    summaries, all_transferred, all_local, all_raw, rep_results, frozen, statuses = [], [], [], [], [], [], []
    for repeat in range(c["experiment"]["repeats"]):
        p0 = fronts.loc[(fronts.repeat == repeat) & (fronts.payload == nominal)].copy()
        reps, status = representatives(p0)
        frozen.append(reps)
        statuses.append(dict(repeat=repeat, status=status, nominal_count=len(p0)))
        # Selection is checkpointed BEFORE any target-payload outcome is inspected.
        save_csv(Path(root) / "exp2" / "representatives_frozen.csv", pd.concat(frozen, ignore_index=True))
        save_json(Path(root) / "exp2" / "selection_status.json", statuses)
        if p0.empty:
            for payload in c["experiment"]["payloads"]:
                summaries.append(
                    dict(
                        repeat=repeat,
                        payload=payload,
                        N0=0,
                        N_ret=0,
                        R_P=np.nan,
                        R_P_union=np.nan,
                        L_HV=np.nan,
                        status="no_nominal_feasible_front",
                    )
                )
            continue
        test_seeds = seeds(c, "test", repeat)
        save_json(Path(root) / "exp2" / f"repeat_{repeat:02d}" / "seeds.json", {"test": test_seeds})
        cache = {}

        def test(candidate, payload):
            key = (payload, *(float(candidate[g]) for g in GAINS))
            if key not in cache:
                metrics, detail = evaluate_row(candidate, payload, c, test_seeds, repeat=repeat, phase="test")
                cache[key] = metrics
                all_raw.extend(detail)
            return {**cache[key], "controller_id": candidate["controller_id"]}

        for payload in c["experiment"]["payloads"]:
            transferred = pd.DataFrame([test(row, payload) for _, row in p0.iterrows()])
            local_frozen = fronts.loc[(fronts.repeat == repeat) & (fronts.payload == payload)]
            local_rows = [test(row, payload) for _, row in local_frozen.iterrows()]
            local = pd.DataFrame(local_rows, columns=transferred.columns)
            directory = condition_dir(root, "exp2", repeat, payload)
            save_csv(directory / "transfer.csv", transferred)
            save_csv(directory / "local_retested.csv", local)
            all_transferred.append(transferred)
            all_local.append(local)
            metrics = transfer_metrics(
                len(p0), transferred, local, c["mobo"]["objective_scales"], c["mobo"]["reference_point"]
            )
            summaries.append(
                dict(
                    repeat=repeat,
                    payload=payload,
                    **metrics,
                    status="ok",
                    parameter_status=c["metadata"]["parameter_status"],
                )
            )
            for _, rep in reps.iterrows():
                row = transferred.loc[transferred.controller_id == rep.controller_id].iloc[0].to_dict()
                rep_results.append({**row, "role": rep.role})
                trace = simulate([rep[g] for g in GAINS], payload, c, test_seeds[0], record=True)
                save_csv(directory / f"trace_{rep.role}.csv", trace.trace)
            print(
                f"exp2 repeat={repeat} payload={payload:g}: retained {metrics['N_ret']}/{len(p0)}; "
                f"HV loss={metrics['L_HV']:.3g}%",
                flush=True,
            )
    rep_frame = pd.DataFrame(rep_results)
    if not rep_frame.empty:
        for (repeat, role), group in rep_frame.groupby(["repeat", "role"]):
            base = group.loc[group.payload == nominal].iloc[0]
            for objective in ("JT", "JE"):
                ix = group.index
                rep_frame.loc[ix, f"delta_{objective}"] = group[objective] - base[objective]
                rep_frame.loc[ix, f"delta_{objective}_pct"] = (
                    100 * (group[objective] - base[objective]) / base[objective]
                    if base[objective] > 1e-9
                    else np.nan
                )
    else:
        rep_frame = pd.DataFrame(columns=["repeat", "payload", "role", "controller_id", *GAINS, "JT", "JE"])
    save_csv(Path(root) / "exp2" / "transfer_summary.csv", summaries)
    save_csv(Path(root) / "exp2" / "representative_performance.csv", rep_frame)
    save_csv(
        Path(root) / "exp2" / "test_rollouts.csv", all_raw if all_raw else pd.DataFrame(columns=["JT", "JE"])
    )
    save_csv(
        Path(root) / "exp2" / "transfer_all.csv",
        pd.concat(all_transferred) if all_transferred else fronts.iloc[:0],
    )
    save_csv(
        Path(root) / "exp2" / "local_retested_all.csv", pd.concat(all_local) if all_local else fronts.iloc[:0]
    )
    finish_run(
        root,
        "exp2",
        manifest,
        test_rollouts=len(all_raw),
        trace_rollouts=len(rep_results),
        representative_status=statuses,
    )
