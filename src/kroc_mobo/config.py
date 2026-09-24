"""TOML loading, validation, and explicit smoke-test overrides."""

import hashlib
import json
import math
import tomllib
from copy import deepcopy
from pathlib import Path

import numpy as np


def load_config(path, smoke=False):
    with Path(path).open("rb") as handle:
        cfg = tomllib.load(handle)
    if smoke:
        cfg = deepcopy(cfg)
        cfg["metadata"]["run_profile"] = "SMOKE: budget reduced; not research evidence"
        cfg["experiment"].update(repeats=1, train_replicates=2, selection_replicates=2, test_replicates=2)
        cfg["mobo"].update(
            n_initial=4,
            n_evaluations=6,
            mc_samples=16,
            num_restarts=2,
            raw_samples=16,
            fit_maxiter=30,
            acq_maxiter=30,
        )
    validate(cfg)
    return cfg


def validate(c):
    def positive(group, keys, allow_zero=False):
        for key in keys:
            v = c[group][key]
            if not math.isfinite(v) or (v < 0 if allow_zero else v <= 0):
                raise ValueError(f"Invalid {group}.{key}: {v}")

    positive("plant", ["J_m", "J_l", "R", "L", "K_t", "K_e", "r_p"])
    positive("plant", ["m_l", "r_l", "b", "g"], True)
    p = c["plant"]
    if "N" in p:
        positive("plant", ["N", "eta", "l"])
        positive("plant", ["J_g"], True)
        if p["eta"] > 1:
            raise ValueError("Gear efficiency must be <= 1")
        if not math.isclose(p["J_l"], p["m_l"] * p["l"] ** 2 / 3, rel_tol=1e-12):
            raise ValueError("Uniform link inertia must equal m_l*l^2/3")
    positive("simulation", ["duration", "control_dt", "integration_substeps"])
    positive("noise", ["sample_dt"])
    positive("noise", ["power"], True)
    positive("controller", ["voltage_max", "filter_tau"])
    positive("controller", ["antiwindup_gain"], True)
    positive("limits", list(c["limits"]))
    s, e, m = c["simulation"], c["experiment"], c["mobo"]
    for ratio in (s["duration"] / s["control_dt"], c["noise"]["sample_dt"] / s["control_dt"]):
        if ratio < 1 or not math.isclose(ratio, round(ratio), abs_tol=1e-8):
            raise ValueError("duration and noise.sample_dt must be integer multiples of control_dt")
    if not isinstance(s["integration_substeps"], int):
        raise ValueError("integration_substeps must be an integer")
    if s["control_dt"] / s["integration_substeps"] > 0.25 * c["plant"]["L"] / c["plant"]["R"]:
        raise ValueError("RK4 step too large relative to L/R; increase integration_substeps")
    if s["control_dt"] * c["controller"]["antiwindup_gain"] > 1:
        raise ValueError("anti-windup update too coarse; reduce control_dt")
    if not all(np.isfinite([s["theta_start"], s["theta_end"]])):
        raise ValueError("Trajectory angles must be finite")
    if not e["payloads"] or len(set(e["payloads"])) != len(e["payloads"]):
        raise ValueError("Payload list must be nonempty and unique")
    if any(not math.isfinite(p) or p < 0 for p in e["payloads"]) or e["nominal_payload"] not in e["payloads"]:
        raise ValueError("Payloads must be nonnegative and include nominal_payload")
    for name in ["repeats", "train_replicates", "selection_replicates", "test_replicates"]:
        if not isinstance(e[name], int) or e[name] < 1 or e[name] >= 1000:
            raise ValueError(f"Invalid {name}")
    seed_sets = [
        set(seeds(c, phase, r)) for phase in ("train", "selection", "test") for r in range(e["repeats"])
    ]
    if sum(map(len, seed_sets)) != len(set.union(*seed_sets)):
        raise ValueError("Noise seeds must be disjoint across phases and repeats")
    for key in ["kp", "ki", "kd"]:
        lo, hi = c["search"][key]
        if not np.isfinite([lo, hi]).all() or not 0 <= lo < hi:
            raise ValueError(f"Invalid search bound: {key}")
    for key in [
        "n_initial",
        "n_evaluations",
        "mc_samples",
        "num_restarts",
        "raw_samples",
        "fit_maxiter",
        "acq_maxiter",
        "torch_threads",
    ]:
        if not isinstance(m[key], int) or m[key] < 1:
            raise ValueError(f"Invalid mobo.{key}")
    if not 2 <= m["n_initial"] <= m["n_evaluations"]:
        raise ValueError("Require 2 <= n_initial <= n_evaluations")
    if m.get("include_zero_anchor", False) and any(c["search"][key][0] != 0 for key in ("kp", "ki", "kd")):
        raise ValueError("The zero anchor requires all gain lower bounds to be zero")
    if "selection" in c:
        positive("selection", ["practical_JT_max"])
        if c["selection"].get("balanced_rule") != "normalized_utopia_distance":
            raise ValueError("Unknown balanced selection rule")
    if m["backend"] not in ("qnehvi", "qlognehvi", "sobol"):
        raise ValueError("Unknown optimization backend")
    if (
        len(m["objective_scales"]) != 2
        or not np.isfinite(m["objective_scales"]).all()
        or min(m["objective_scales"]) <= 0
    ):
        raise ValueError("Two positive objective scales required")
    if len(m["reference_point"]) != 2 or not np.isfinite(m["reference_point"]).all():
        raise ValueError("Two finite reference coordinates required")
    positive("mobo", ["observation_variance_floor"])
    if not c["metadata"]["parameter_status"]:
        raise ValueError("parameter_status must describe parameter provenance")


def seeds(c, phase, repeat):
    e = c["experiment"]
    start = e[f"{phase}_seed_base"] + 1000 * repeat
    return list(range(start, start + e[f"{phase}_replicates"]))


def bounds(c):
    return np.array([c["search"][k] for k in ("kp", "ki", "kd")], dtype=float)


def fingerprint(c):
    return hashlib.sha256(json.dumps(c, sort_keys=True, allow_nan=False).encode()).hexdigest()
