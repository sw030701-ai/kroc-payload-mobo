"""Tests of diagnostic selection, seed separation, and SO target independence."""

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from kroc_mobo.config import load_config, seeds
from kroc_mobo.heavy_diagnostics import best_feasible, confirm_seeds, suggest_tracking


def test_min_tracking_rejects_faster_infeasible_candidate():
    f = pd.DataFrame([
        dict(JT=.0001, JE=2., feasible=False, kp=800., ki=400., kd=0.),
        dict(JT=.001, JE=3., feasible=True, kp=600., ki=300., kd=0.),
        dict(JT=.002, JE=1., feasible=True, kp=200., ki=100., kd=0.),
    ])
    assert best_feasible(f).kp == 600
    with pytest.raises(ValueError, match="No feasible"):
        best_feasible(f.iloc[:1])


def test_confirmation_seeds_are_new_and_paired():
    c = load_config("configs/canonical_final.toml")
    previous = {s for r in range(5) for phase in ("train", "selection", "test") for s in seeds(c, phase, r)}
    fresh = [s for r in range(5) for s in confirm_seeds(r)]
    assert len(fresh) == len(set(fresh)) == 50
    assert not set(fresh) & previous


@pytest.mark.integration
def test_so_proposal_ignores_energy_values():
    c = load_config("configs/canonical_final.toml", smoke=True)
    history = [dict(x0=x, x1=.2, x2=.1, JT=.01+(x-.6)**2,
        JT_sem2=1e-7, JE=100*x, JE_sem2=1., constraint_margin=x-.9) for x in (.1, .4, .8)]
    alternative = deepcopy(history)
    for row in alternative:
        row["JE"] = -1000 * row["JE"]
    a, sa = suggest_tracking(history, c, 12345)
    b, sb = suggest_tracking(alternative, c, 12345)
    assert sa == sb == "qlognei_tracking"
    np.testing.assert_allclose(a, b, atol=1e-8, rtol=0)
