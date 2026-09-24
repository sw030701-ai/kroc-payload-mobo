"""Regression checks for scientific selection, anchor fairness and the branch rule."""

import numpy as np
import pandas as pd
import pytest

from kroc_mobo.config import load_config, validate
from kroc_mobo.metrics import representatives
from kroc_mobo.mobo import decode, sobol_design
from kroc_mobo.sensitivity import choose_bounds, normalized_hausdorff


def practical_front():
    return pd.DataFrame([
        dict(controller_id="zero", kp=0., ki=0., kd=0., JT=.65546, JE=0., feasible=True),
        dict(controller_id="tracking", kp=200., ki=100., kd=0., JT=.003, JE=2.6, feasible=True),
        dict(controller_id="balanced", kp=100., ki=20., kd=0., JT=.015, JE=2.3, feasible=True),
        dict(controller_id="energy", kp=40., ki=0., kd=0., JT=.05, JE=2., feasible=True),
        dict(controller_id="too_slow", kp=20., ki=0., kd=0., JT=.051, JE=1.9, feasible=True),
        dict(controller_id="failed", kp=900., ki=0., kd=0., JT=.001, JE=1., feasible=False),
    ])


def test_practical_selection_excludes_zero_and_uses_inclusive_threshold():
    p = practical_front()
    selected, status = representatives(p, tracking_max=.05)
    assert status == "ok"
    assert selected.controller_id.tolist() == ["tracking", "balanced", "energy"]
    assert selected.role.tolist() == ["CT", "CB", "CE"]
    assert len(p) == 6  # Selection never truncates the original front in place.
    assert (selected.JT <= .05).all()
    shuffled, _ = representatives(p.sample(frac=1, random_state=1), tracking_max=.05)
    assert shuffled.controller_id.tolist() == selected.controller_id.tolist()


def test_zero_explicitly_excluded_even_with_loose_threshold():
    reps, _ = representatives(practical_front(), tracking_max=1.)
    assert "zero" not in reps.controller_id.tolist()


def test_cb_exact_utopia_minimum_allows_duplicate_roles():
    selected, status = representatives(practical_front().iloc[[0, 1, 3]], tracking_max=.05)
    assert len(selected) == 3
    assert "coincident" in status
    assert selected.controller_id.tolist() == ["tracking", "tracking", "energy"]
    empty, status = representatives(practical_front(), tracking_max=.0001)
    assert empty.empty and "no_practical" in status


def test_anchor_is_one_initial_slot_without_changing_budget():
    c = load_config("configs/canonical_final.toml")
    c["mobo"]["include_zero_anchor"] = True
    anchored = sobol_design(c, 731)
    c["mobo"]["include_zero_anchor"] = False
    legacy = sobol_design(c, 731)
    assert anchored.shape == (40, 3)
    np.testing.assert_array_equal(decode(anchored[0], c), [0, 0, 0])
    np.testing.assert_array_equal(anchored[1:10], legacy[:9])
    c["mobo"]["include_zero_anchor"] = True
    c["search"]["kp"][0] = 1.
    with pytest.raises(ValueError, match="zero anchor"):
        validate(c)


@pytest.mark.parametrize("improvement,outside,overlap,expected", [
    (4.99, False, True, "original"), (5., False, True, "expanded"),
    (1., True, True, "expanded"), (1., False, False, "expanded"),
])
def test_sensitivity_threshold_and_conservative_branch(improvement, outside, overlap, expected):
    assert choose_bounds(improvement, outside, overlap)[0] == expected


def test_hausdorff_identity_and_missing_coverage():
    assert normalized_hausdorff([[.01, 2], [.02, 1]], [[.02, 1], [.01, 2]]) == 0
    assert np.isnan(normalized_hausdorff([], [[.01, 2]]))
