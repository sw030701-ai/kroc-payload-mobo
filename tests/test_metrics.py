import numpy as np
import pandas as pd
import pytest

from kroc_mobo.metrics import hypervolume, nondominated, representatives, transfer_metrics


def frame(y, feasible=None):
    df = pd.DataFrame(y, columns=["JT", "JE"])
    df["feasible"] = True if feasible is None else feasible
    df["kp"] = np.arange(len(df))
    df["ki"] = 0.0
    df["kd"] = 0.0
    return df


def test_pareto_ties_nan_and_dominance():
    assert nondominated([[1, 3], [2, 2], [3, 3], [1, 3], [np.nan, 0]]).tolist() == [
        True,
        True,
        False,
        True,
        False,
    ]


def test_hypervolume_hand_calculation_negative_energy_and_empty():
    assert hypervolume([[1, 3], [2, 2], [3, 1]], [4, 4]) == 6
    assert hypervolume([[1, -1]], [3, 2]) == 6
    assert hypervolume([], [4, 4]) == 0
    assert hypervolume([[5, 1], [1, 5]], [4, 4]) == 0


def test_internal_vs_union_retention_and_failures():
    transfer = frame([[1, 3], [2, 2], [3, 1], [0.1, 0.1]], [True, True, True, False])
    local = frame([[0.9, 2.9], [2, 2], [3, 1]])
    m = transfer_metrics(4, transfer, local, [1, 1], [4, 4])
    assert m["R_P"] == 75
    assert m["R_P_union"] == 50
    assert m["N_feasible"] == 3


def test_negative_loss_not_clamped_zero_reference_is_undefined():
    m = transfer_metrics(1, frame([[1, 1]]), frame([[2, 2]]), [1, 1], [3, 3])
    assert m["L_HV"] == -300
    m = transfer_metrics(1, frame([[1, 1]]), frame([[4, 4]]), [1, 1], [3, 3])
    assert np.isnan(m["L_HV"])


def test_empty_local_front_and_all_failed_transfers():
    empty = pd.DataFrame(columns=["JT", "JE", "feasible", "kp", "ki", "kd"])
    m = transfer_metrics(1, frame([[1, 1]]), empty, [1, 1], [3, 3])
    assert m["N_local"] == 0 and m["N_ret_union"] == 1
    assert np.isnan(m["L_HV"])
    m = transfer_metrics(2, frame([[1, 1], [2, 2]], [False, False]), frame([[1, 1]]), [1, 1], [3, 3])
    assert m["N_ret"] == 0 and m["R_P"] == 0 and m["L_HV"] == 100


def test_representative_selection_balanced_excludes_extremes():
    p = frame([[1, 10], [2, 4], [4, 2], [10, 1]])
    reps, status = representatives(p)
    assert status == "ok"
    assert reps.role.tolist() == ["CT", "CB", "CE"]
    assert reps.kp.tolist() == [0, 1, 3]
    assert representatives(p.iloc[:2])[0].empty


def test_hypervolume_matches_botorch():
    import torch
    from botorch.utils.multi_objective.hypervolume import Hypervolume
    from botorch.utils.multi_objective.pareto import is_non_dominated

    y = np.random.default_rng(91).uniform(-1, 2, (40, 2))
    ref = np.array([2.5, 2.5])
    maximized = torch.tensor(-y, dtype=torch.double)
    expected = Hypervolume(torch.tensor(-ref)).compute(maximized[is_non_dominated(maximized)])
    assert hypervolume(y, ref) == pytest.approx(expected)
