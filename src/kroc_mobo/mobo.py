"""Independent Matérn-5/2 GPs and constrained qNEHVI (q=1, CPU double precision)."""

import numpy as np
import torch
from botorch.acquisition.multi_objective.logei import qLogNoisyExpectedHypervolumeImprovement
from botorch.acquisition.multi_objective.monte_carlo import qNoisyExpectedHypervolumeImprovement
from botorch.acquisition.multi_objective.objective import IdentityMCMultiOutputObjective
from botorch.fit import fit_gpytorch_mll
from botorch.models import ModelListGP, SingleTaskGP
from botorch.models.transforms.outcome import Standardize
from botorch.optim import optimize_acqf
from botorch.sampling.normal import SobolQMCNormalSampler
from gpytorch.constraints import Interval
from gpytorch.kernels import MaternKernel, ScaleKernel
from gpytorch.mlls import SumMarginalLogLikelihood
from gpytorch.priors import LogNormalPrior

from .config import bounds


def sobol_design(c, seed):
    return (
        torch.quasirandom.SobolEngine(3, scramble=True, seed=seed)
        .draw(c["mobo"]["n_evaluations"], dtype=torch.double)
        .numpy()
    )


def decode(unit, c):
    b = bounds(c)
    return b[:, 0] + np.asarray(unit) * (b[:, 1] - b[:, 0])


def suggest(history, c, seed):
    settings = c["mobo"]
    torch.set_num_threads(settings["torch_threads"])
    torch.manual_seed(seed)
    x = torch.tensor([[r[f"x{i}"] for i in range(3)] for r in history], dtype=torch.double)
    finite = np.array([np.isfinite([r["JT"], r["JE"]]).all() for r in history])
    if finite.sum() < 2:
        # Numerical failures cannot be invented objective observations.
        return None, "sobol_recovery_insufficient_finite_objectives"
    models = []
    for j, key in enumerate(["JT", "JE", "constraint_margin"]):
        use = finite if j < 2 else np.ones(len(history), dtype=bool)
        rows = [r for r, ok in zip(history, use) if ok]
        scale = settings["objective_scales"][j] if j < 2 else 1.0
        sign = -1 if j < 2 else 1
        values = torch.tensor([[sign * r[key] / scale] for r in rows], dtype=torch.double)
        variance = torch.tensor(
            [[max(r.get(f"{key}_sem2", 0) / scale**2, settings["observation_variance_floor"])] for r in rows],
            dtype=torch.double,
        )
        models.append(
            SingleTaskGP(
                x[torch.tensor(use)],
                values,
                train_Yvar=variance,
                covar_module=ScaleKernel(
                    MaternKernel(
                        nu=2.5,
                        ard_num_dims=3,
                        lengthscale_constraint=Interval(0.01, 10.0),
                        lengthscale_prior=LogNormalPrior(-1.0, 1.0),
                    ),
                    outputscale_constraint=Interval(1e-4, 100.0),
                    outputscale_prior=LogNormalPrior(0.0, 1.0),
                ),
                outcome_transform=Standardize(m=1),
            )
        )
    model = ModelListGP(*models)
    fit_gpytorch_mll(
        SumMarginalLogLikelihood(model.likelihood, model),
        optimizer_kwargs={"options": {"maxiter": settings["fit_maxiter"], "maxls": 50}},
    )
    acquisition_class = (
        qNoisyExpectedHypervolumeImprovement
        if settings["backend"] == "qnehvi"
        else qLogNoisyExpectedHypervolumeImprovement
    )
    acquisition = acquisition_class(
        model=model,
        ref_point=(-np.array(settings["reference_point"]) / settings["objective_scales"]).tolist(),
        X_baseline=x,
        sampler=SobolQMCNormalSampler(torch.Size([settings["mc_samples"]]), seed=seed),
        objective=IdentityMCMultiOutputObjective(outcomes=[0, 1]),
        constraints=[lambda samples: samples[..., 2]],
        prune_baseline=False,
        cache_root=False,
    )
    candidate, _ = optimize_acqf(
        acquisition,
        bounds=torch.tensor([[0.0] * 3, [1.0] * 3], dtype=torch.double),
        q=1,
        num_restarts=settings["num_restarts"],
        raw_samples=settings["raw_samples"],
        options={"maxiter": settings["acq_maxiter"], "maxls": 50, "batch_limit": 2},
    )
    candidate = candidate.detach().cpu().numpy()[0]
    if np.min(np.linalg.norm(x.numpy() - candidate, axis=1)) < 1e-6:
        return None, "sobol_recovery_duplicate_proposal"
    return candidate, settings["backend"]
