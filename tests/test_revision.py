"""Regression checks for scientific selection, anchor fairness and the branch rule."""

import numpy as np
import pandas as pd
import pytest

from kroc_mobo.config import load_config, validate
from kroc_mobo.io import save_json
from kroc_mobo.metrics import representatives
from kroc_mobo.mobo import decode, sobol_design
from kroc_mobo.sensitivity import choose_bounds, normalized_hausdorff


def practical_front():
    return pd.DataFrame(
        [
            dict(controller_id="zero", kp=0.0, ki=0.0, kd=0.0, JT=0.65546, JE=0.0, feasible=True),
            dict(controller_id="tracking", kp=200.0, ki=100.0, kd=0.0, JT=0.003, JE=2.6, feasible=True),
            dict(controller_id="balanced", kp=100.0, ki=20.0, kd=0.0, JT=0.015, JE=2.3, feasible=True),
            dict(controller_id="energy", kp=40.0, ki=0.0, kd=0.0, JT=0.05, JE=2.0, feasible=True),
            dict(controller_id="too_slow", kp=20.0, ki=0.0, kd=0.0, JT=0.051, JE=1.9, feasible=True),
            dict(controller_id="failed", kp=900.0, ki=0.0, kd=0.0, JT=0.001, JE=1.0, feasible=False),
        ]
    )


def test_practical_selection_excludes_zero_and_uses_inclusive_threshold():
    p = practical_front()
    selected, status = representatives(p, tracking_max=0.05)
    assert status == "ok"
    assert selected.controller_id.tolist() == ["tracking", "balanced", "energy"]
    assert selected.role.tolist() == ["CT", "CB", "CE"]
    assert len(p) == 6  # Selection never truncates the original front in place.
    assert (selected.JT <= 0.05).all()
    shuffled, _ = representatives(p.sample(frac=1, random_state=1), tracking_max=0.05)
    assert shuffled.controller_id.tolist() == selected.controller_id.tolist()


def test_zero_explicitly_excluded_even_with_loose_threshold():
    reps, _ = representatives(practical_front(), tracking_max=1.0)
    assert "zero" not in reps.controller_id.tolist()


def test_cb_exact_utopia_minimum_allows_duplicate_roles():
    selected, status = representatives(practical_front().iloc[[0, 1, 3]], tracking_max=0.05)
    assert len(selected) == 3
    assert "coincident" in status
    assert selected.controller_id.tolist() == ["tracking", "tracking", "energy"]
    empty, status = representatives(practical_front(), tracking_max=0.0001)
    assert empty.empty and "no_practical" in status


def test_anchor_is_one_initial_slot_without_changing_budget():
    c = load_config("configs/canonical_final.toml")
    c["mobo"]["include_zero_anchor"] = True
    anchored = sobol_design(c, 731)
    c["mobo"]["include_zero_anchor"] = False
    legacy = sobol_design(c, 731)
    assert anchored.shape == (c["mobo"]["n_evaluations"], 3)
    np.testing.assert_array_equal(decode(anchored[0], c), [0, 0, 0])
    np.testing.assert_array_equal(anchored[1:10], legacy[:9])
    c["mobo"]["include_zero_anchor"] = True
    c["search"]["kp"][0] = 1.0
    with pytest.raises(ValueError, match="zero anchor"):
        validate(c)


@pytest.mark.parametrize(
    "improvement,outside,overlap,expected",
    [
        (4.99, False, True, "original"),
        (5.0, False, True, "expanded"),
        (1.0, True, True, "expanded"),
        (1.0, False, False, "expanded"),
    ],
)
def test_sensitivity_threshold_and_conservative_branch(improvement, outside, overlap, expected):
    assert choose_bounds(improvement, outside, overlap)[0] == expected


def test_hausdorff_identity_and_missing_coverage():
    assert normalized_hausdorff([[0.01, 2], [0.02, 1]], [[0.02, 1], [0.01, 2]]) == 0
    assert np.isnan(normalized_hausdorff([], [[0.01, 2]]))


@pytest.mark.parametrize("improvement,expected", [(4.9, "original"), (5.1, "expanded")])
def test_budget80_decision_does_not_equate_boundary_with_saturation(tmp_path, monkeypatch, improvement, expected):
    from kroc_mobo import sensitivity

    monkeypatch.setattr(sensitivity, "plot_fronts", lambda *a, **kw: None)
    for arm, factor in (("original", 1), ("expanded", 2)):
        c = load_config("configs/canonical_final.toml")
        c["experiment"]["payloads"] = [1.0]
        c["experiment"]["repeats"] = 1
        c["search"] = dict(kp=[0., 400. * factor], ki=[0., 200. * factor], kd=[0., 40. * factor])
        save_json(tmp_path / arm / "config.json", c)
        save_json(tmp_path / arm / "exp1/manifest.json", {"status": "completed"})
        pd.DataFrame([dict(repeat=0, kp=400. * factor, ki=200. * factor, kd=0.,
            JT=.002 * (1 - improvement / 100 if factor == 2 else 1), JE=2.6,
            saturation_fraction=0., max_current=2.)]).to_csv(tmp_path / arm / "exp1/pareto_all.csv", index=False)
    decision = sensitivity.analyze(tmp_path / "original", tmp_path / "expanded", tmp_path / "analysis", protocol="budget80")
    assert decision["adopted"] == expected
    assert decision["expanded_CT_at_upper_count"] == 1
    diagnostics = pd.read_csv(tmp_path / "analysis/tracking_extremes.csv")
    assert (diagnostics.saturation_fraction == 0).all()
