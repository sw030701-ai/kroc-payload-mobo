"""Minimization Pareto sets, exact 2-D hypervolume, and frozen representative selection."""

import numpy as np
import pandas as pd

OBJECTIVES = ["JT", "JE"]
GAINS = ["kp", "ki", "kd"]


def nondominated(values):
    y = np.asarray(values, dtype=float).reshape(-1, 2)
    valid = np.isfinite(y).all(axis=1)
    keep = valid.copy()
    for i in np.flatnonzero(valid):
        keep[i] = not np.any(np.all(y[valid] <= y[i], axis=1) & np.any(y[valid] < y[i], axis=1))
    return keep


def pareto(frame):
    valid = frame.loc[frame.feasible.astype(bool)].copy()
    if valid.empty:
        return valid
    valid = valid.drop_duplicates(GAINS).sort_values(OBJECTIVES + GAINS, kind="stable")
    return valid.loc[nondominated(valid[OBJECTIVES])].reset_index(drop=True)


def hypervolume(values, reference):
    """Union of rectangles [point, reference], minimization, no extrapolation/clipping."""
    y = np.asarray(values, dtype=float).reshape(-1, 2)
    r = np.asarray(reference, dtype=float)
    if r.shape != (2,) or not np.isfinite(r).all():
        raise ValueError("Finite two-dimensional reference required")
    y = y[np.isfinite(y).all(axis=1) & np.all(y < r, axis=1)]
    y = y[nondominated(y)]
    y = y[np.argsort(y[:, 0], kind="stable")]
    area, ceiling = 0.0, r[1]
    for x, z in y:
        if z < ceiling:
            area += (r[0] - x) * (ceiling - z)
            ceiling = z
    return float(area)


def transfer_metrics(nominal_count, transferred, local, scales, reference):
    # Every nominal controller stays in denominator, including failed transfers.
    valid = transferred.loc[
        transferred.feasible.astype(bool)
        & np.isfinite(transferred[OBJECTIVES].to_numpy(dtype=float)).all(axis=1)
    ]
    local_valid = local.loc[
        local.feasible.astype(bool) & np.isfinite(local[OBJECTIVES].to_numpy(dtype=float)).all(axis=1)
    ]
    y, yl = valid[OBJECTIVES].to_numpy(dtype=float), local_valid[OBJECTIVES].to_numpy(dtype=float)
    internal = nondominated(y)
    union = nondominated(np.concatenate([y, yl]))[: len(y)]
    sc, ref = np.asarray(scales), np.asarray(reference) / np.asarray(scales)
    hv_t, hv_l = hypervolume(y / sc, ref), hypervolume(yl / sc, ref)
    return dict(
        N0=nominal_count,
        N_local=int(nondominated(yl).sum()),
        N_feasible=len(valid),
        N_ret=int(internal.sum()),
        R_P=100 * internal.sum() / nominal_count if nominal_count else np.nan,
        N_ret_union=int(union.sum()),
        R_P_union=100 * union.sum() / nominal_count if nominal_count else np.nan,
        HV_transfer=hv_t,
        HV_local=hv_l,
        L_HV=100 * (hv_l - hv_t) / hv_l if hv_l > 0 else np.nan,
        HV_status="ok" if hv_l > 0 else "undefined_zero_local_hv",
        N_transfer_outside_ref=int(np.any(y >= np.asarray(reference), axis=1).sum()),
        N_local_outside_ref=int(np.any(yl >= np.asarray(reference), axis=1).sum()),
    )


def representatives(front):
    """CT/CE extrema; CB closest normalized ideal among remaining points, not geometric knee."""
    p = pareto(front)
    empty = p.assign(role=pd.Series(dtype=str), selection_status=pd.Series(dtype=str))
    if len(p) < 3:
        return empty.iloc[:0], f"insufficient_distinct_nominal_front: {len(p)} < 3"
    ct = p.sort_values(["JT", "JE"] + GAINS, kind="stable").index[0]
    ce = p.sort_values(["JE", "JT"] + GAINS, kind="stable").index[0]
    span = p[OBJECTIVES].max() - p[OBJECTIVES].min()
    active = span > 0
    remaining = p.drop(index=list({ct, ce})).copy()
    if ct == ce or remaining.empty:
        return empty.iloc[:0], "degenerate_extrema"
    normalized = (remaining[OBJECTIVES].loc[:, active] - p[OBJECTIVES].min()[active]) / span[active]
    remaining["distance"] = np.sqrt((normalized**2).sum(axis=1))
    cb = remaining.sort_values(["distance", "JT", "JE"] + GAINS, kind="stable").index[0]
    result = p.loc[[ct, cb, ce]].copy()
    result["role"] = ["CT", "CB", "CE"]
    result["selection_status"] = "ok" if active.all() else "degenerate_objective_range"
    return result.reset_index(drop=True), result.selection_status.iloc[0]
