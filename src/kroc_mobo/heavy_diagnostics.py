"""Checkpointed supplementary 80→160 MOBO and warm-started SO40 diagnostics."""

import argparse
import hashlib
import json
import os
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from botorch.acquisition.logei import qLogNoisyExpectedImprovement
from botorch.acquisition.objective import GenericMCObjective
from botorch.fit import fit_gpytorch_mll
from botorch.models import ModelListGP, SingleTaskGP
from botorch.models.transforms.outcome import Standardize
from botorch.optim import optimize_acqf
from botorch.sampling.normal import SobolQMCNormalSampler
from gpytorch.constraints import Interval
from gpytorch.kernels import MaternKernel, ScaleKernel
from gpytorch.mlls import SumMarginalLogLikelihood
from gpytorch.priors import LogNormalPrior

from .config import bounds, fingerprint, seeds
from .experiments import evaluate_row
from .io import finish_run, initialize_run, load_snapshot, require_complete, save_csv, save_json
from .metrics import GAINS, OBJECTIVES, pareto
from .mobo import decode, sobol_design, suggest


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return pd.read_csv(path, float_precision="round_trip")


def confirm_seeds(repeat):
    return list(range(300000 + repeat * 1000, 300010 + repeat * 1000))


def best_feasible(frame):
    usable = frame.loc[frame.feasible & np.isfinite(frame[OBJECTIVES]).all(axis=1)]
    if usable.empty:
        raise ValueError("No feasible selection candidate; cannot invent a diagnostic winner")
    return usable.sort_values(OBJECTIVES + GAINS, kind="stable").iloc[0]


def suggest_tracking(history, c, seed):
    """Same GP priors/settings as MOBO; JT and constraint models only."""
    torch.set_num_threads(c["mobo"]["torch_threads"])
    torch.manual_seed(seed)
    settings = c["mobo"]
    x = torch.tensor([[r[f"x{i}"] for i in range(3)] for r in history], dtype=torch.double)
    finite = np.array([np.isfinite(r["JT"]) for r in history])
    if finite.sum() < 2:
        return None, "sobol_recovery_insufficient_finite_objectives"
    models = []
    for j, key in enumerate(("JT", "constraint_margin")):
        mask = finite if j == 0 else np.ones(len(history), dtype=bool)
        rows = [r for r, keep in zip(history, mask) if keep]
        scale = settings["objective_scales"][0] if j == 0 else 1.0
        sign = -1 if j == 0 else 1
        models.append(SingleTaskGP(
            x[torch.tensor(mask)], torch.tensor([[sign * r[key] / scale] for r in rows], dtype=torch.double),
            train_Yvar=torch.tensor([[max(r.get(f"{key}_sem2", 0) / scale**2,
                settings["observation_variance_floor"])] for r in rows], dtype=torch.double),
            covar_module=ScaleKernel(MaternKernel(nu=2.5, ard_num_dims=3,
                lengthscale_constraint=Interval(.01, 10.), lengthscale_prior=LogNormalPrior(-1., 1.)),
                outputscale_constraint=Interval(1e-4, 100.), outputscale_prior=LogNormalPrior(0., 1.)),
            outcome_transform=Standardize(m=1)))
    model = ModelListGP(*models)
    fit_gpytorch_mll(SumMarginalLogLikelihood(model.likelihood, model),
        optimizer_kwargs={"options": {"maxiter": settings["fit_maxiter"], "maxls": 50}})
    acquisition = qLogNoisyExpectedImprovement(model=model, X_baseline=x,
        sampler=SobolQMCNormalSampler(torch.Size([settings["mc_samples"]]), seed=seed),
        objective=GenericMCObjective(lambda samples, X=None: samples[..., 0]),
        constraints=[lambda samples: samples[..., 1]], prune_baseline=False, cache_root=False)
    candidate, _ = optimize_acqf(acquisition,
        bounds=torch.tensor([[0.] * 3, [1.] * 3], dtype=torch.double), q=1,
        num_restarts=settings["num_restarts"], raw_samples=settings["raw_samples"],
        options={"maxiter": settings["acq_maxiter"], "maxls": 50, "batch_limit": 2})
    unit = candidate.detach().cpu().numpy()[0]
    if np.linalg.norm(x.numpy() - unit, axis=1).min() < 1e-6:
        return None, "sobol_recovery_duplicate_proposal"
    return unit, "qlognei_tracking"


def run_condition(parent, root, mode, repeat, payload):
    parent, root = Path(parent), Path(root)
    c = load_snapshot(root)
    budget = 160 if mode == "mobo160" else 40
    c["mobo"]["n_evaluations"] = budget
    directory = root / mode / f"repeat_{repeat:02d}" / f"payload_{payload:g}kg"
    original = parent / "exp1" / f"repeat_{repeat:02d}" / f"payload_{payload:g}kg"
    parent_hashes = {name: sha(original / name) for name in
        ("train.csv", "train_rollouts.csv", "selection.csv", "selection_rollouts.csv")}
    inherited = 80 if mode == "mobo160" else 0
    if (directory / "diagnostic/manifest.json").exists():
        manifest = json.loads((directory / "diagnostic/manifest.json").read_text())
        if manifest["config_sha256"] != fingerprint(c) or manifest["parent_hashes"] != parent_hashes:
            raise ValueError("Resume config/parent mismatch")
        if manifest["source_sha256"] != {k: sha(k) for k in manifest["source_sha256"]}:
            raise ValueError("Resume source changed")
        if manifest["status"] == "completed":
            return str(directory)
    else:
        manifest = initialize_run(directory, c, "diagnostic")
        manifest.update(parent_hashes=parent_hashes, mode=mode, repeat=repeat, payload=payload,
            inherited_candidates=inherited)
        save_json(directory / "diagnostic/manifest.json", manifest)
    if (directory / "train.csv").exists():
        history = read(directory / "train.csv").to_dict("records")
        # Training aggregates and raw details are checkpointed together below.
        raw = read(directory / "train_rollouts.csv").to_dict("records")
        valid_ids = {r["controller_id"] for r in history}
        raw = [r for r in raw if r["controller_id"] in valid_ids]
        if len(raw) != len(history) * c["experiment"]["train_replicates"]:
            raise ValueError("Incomplete paired checkpoint; restore the last complete condition")
    elif inherited:
        history = read(original / "train.csv").to_dict("records")
        raw = read(original / "train_rollouts.csv").to_dict("records")
        if len(history) != 80:
            raise ValueError("Expected exactly 80 inherited candidates")
    else:
        history, raw = [], []
    opt_seed = c["experiment"]["base_seed"] + repeat
    design = sobol_design(c, opt_seed)
    frozen = read(parent / "exp2/representatives_frozen.csv")
    ct = frozen.loc[(frozen.repeat == repeat) & (frozen.role == "CT")].iloc[0]
    if mode == "so40":
        design[2:10] = design[1:9].copy()
        b = bounds(c)
        design[1] = (ct[GAINS].to_numpy(float) - b[:, 0]) / (b[:, 1] - b[:, 0])
    save_json(directory / "seeds.json", dict(optimizer_seed=opt_seed, train=seeds(c, "train", repeat),
        selection=seeds(c, "selection", repeat), test=seeds(c, "test", repeat), confirm=confirm_seeds(repeat)))
    for index in range(len(history), budget):
        unit, source = design[index], "sobol_initial"
        if index == 0:
            source = "known_zero_pid_anchor"
        elif mode == "so40" and index == 1:
            source = "frozen_nominal_CT_warm_start"
        if index >= c["mobo"]["n_initial"]:
            proposal, source = (suggest if mode == "mobo160" else suggest_tracking)(
                history, c, opt_seed * 10000 + index)
            if proposal is not None:
                unit = proposal
        candidate = dict(controller_id=f"{mode}_r{repeat}_p{payload:g}_c{index:04d}",
            **dict(zip(GAINS, decode(unit, c))))
        row, details = evaluate_row(candidate, payload, c, seeds(c, "train", repeat),
            repeat=repeat, phase="train", candidate_index=index, source=source)
        row.update({f"x{i}": float(unit[i]) for i in range(3)})
        history.append(row)
        raw.extend(details)
        save_csv(directory / "train_rollouts.csv", raw)
        save_csv(directory / "train.csv", history)
        print(f"{mode} r{repeat} p{payload:g} {index+1}/{budget} JT={row['JT']:.7g} feasible={row['feasible']}", flush=True)
    validated = read(original / "selection.csv").to_dict("records") if inherited else []
    validation_raw = read(original / "selection_rollouts.csv").to_dict("records") if inherited else []
    for candidate in history[inherited:]:
        row, details = evaluate_row(candidate, payload, c, seeds(c, "selection", repeat),
            repeat=repeat, phase="selection")
        validated.append(row)
        validation_raw.extend(details)
    selected = pd.DataFrame(validated)
    save_csv(directory / "selection.csv", selected)
    save_csv(directory / "selection_rollouts.csv", validation_raw)
    save_csv(directory / "pareto.csv", pareto(selected))
    winner = best_feasible(selected)
    save_csv(directory / "winner_frozen.csv", pd.DataFrame([winner]))
    finish_run(directory, "diagnostic", manifest, attempted=budget,
        new_candidates=budget-inherited, new_train_rollouts=3*(budget-inherited),
        new_selection_rollouts=5*(budget-inherited))
    return str(directory)


def test_winners(parent, root):
    parent, root = Path(parent), Path(root)
    c = load_snapshot(root)
    manifest = initialize_run(root, c, "heldout")
    rows, raw = [], []
    frozen = read(parent / "exp2/representatives_frozen.csv")
    winners = []
    for repeat in range(5):
        ct = frozen.loc[(frozen.repeat == repeat) & (frozen.role == "CT")].iloc[0]
        for payload in (2., 3.):
            original = parent / "exp1" / f"repeat_{repeat:02d}" / f"payload_{payload:g}kg"
            candidates = {"CT": ct, "mobo80": best_feasible(read(original / "selection.csv"))}
            for mode in ("mobo160", "so40"):
                directory = root / mode / f"repeat_{repeat:02d}" / f"payload_{payload:g}kg"
                require_complete(directory, "diagnostic")
                candidates[mode] = read(directory / "winner_frozen.csv").iloc[0]
            for mode, candidate in candidates.items():
                winners.append(dict(mode=mode, repeat=repeat, payload=payload,
                    **{k: candidate[k] for k in ["controller_id", *GAINS, *OBJECTIVES]}))
    save_csv(root / "heldout/frozen_candidates.csv", winners)
    for candidate in winners:
        repeat, payload, mode = candidate["repeat"], candidate["payload"], candidate["mode"]
        for phase, noise_seeds in (("test", seeds(c, "test", repeat)), ("confirm", confirm_seeds(repeat))):
            row, details = evaluate_row(candidate, payload, c, noise_seeds, repeat=repeat, phase=phase, mode=mode)
            rows.append(row)
            raw.extend(details)
    save_csv(root / "heldout/summary.csv", rows)
    save_csv(root / "heldout/rollouts.csv", raw)
    finish_run(root, "heldout", manifest, rollout_count=len(raw), selection_uses_test=False)


def run(parent, root, resume=False):
    parent, root = Path(parent), Path(root)
    require_complete(parent, "exp1")
    require_complete(parent, "exp2")
    c = load_snapshot(parent)
    if root.exists():
        if not resume or load_snapshot(root) != c:
            raise FileExistsError("Existing output; resume requires the exact parent configuration")
    else:
        root.mkdir(parents=True)
        save_json(root / "config.json", c)
        shutil.copytree("src", root / "source/src", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2("docs/HEAVY_DIAGNOSTIC_PROTOCOL.md", root / "protocol.md")
        save_json(root / "parent.json", dict(path=str(parent), config_hash=sha(parent / "config.json"),
            exp1_manifest_hash=sha(parent / "exp1/manifest.json"),
            frozen_CT_hash=sha(parent / "exp2/representatives_frozen.csv")))
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[key] = "1"
    # SO diagnostics first, so their compact results are available while long MOBO continuations run.
    jobs = [(str(parent), str(root), mode, repeat, payload)
        for mode in ("so40", "mobo160") for repeat in range(5) for payload in (2., 3.)]
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_condition, *job) for job in jobs]
        for future in as_completed(futures):
            print("CONDITION COMPLETE " + future.result(), flush=True)
    if not (root / "heldout/manifest.json").exists():
        test_winners(parent, root)
    else:
        require_complete(root, "heldout")
    print("HEAVY DIAGNOSTICS COMPLETE", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    run(args.parent, args.out, args.resume)
