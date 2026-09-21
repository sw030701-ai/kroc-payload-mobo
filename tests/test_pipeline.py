import json

import numpy as np
import pandas as pd
import pytest

from kroc_mobo.experiments import run_exp1, run_exp2
from kroc_mobo.io import initialize_run
from kroc_mobo.mobo import suggest


@pytest.mark.integration
@pytest.mark.parametrize("backend", ["qnehvi", "qlognehvi"])
def test_real_botorch_proposal_with_constraints(config, backend):
    config["mobo"]["backend"] = backend
    history = []
    for i, x in enumerate([[0.1, 0.2, 0.3], [0.7, 0.2, 0.6], [0.4, 0.8, 0.2], [0.9, 0.6, 0.8]]):
        history.append(
            dict(
                x0=x[0],
                x1=x[1],
                x2=x[2],
                JT=0.1 + 0.02 * i,
                JE=20 - 2 * i,
                JT_sem2=1e-7,
                JE_sem2=0.001,
                constraint_margin=[-0.5, -0.3, 0.2, -0.1][i],
            )
        )
    candidate, source = suggest(history, config, 731)
    assert source == backend
    assert candidate.shape == (3,) and np.all((candidate >= 0) & (candidate <= 1))


def test_end_to_end_frozen_gains_matched_seeds_and_budget(config, tmp_path):
    config["simulation"]["duration"] = 0.1
    config["simulation"]["theta_end"] = 0.01
    config["mobo"].update(backend="sobol", n_initial=4, n_evaluations=4)
    run_exp1(config, tmp_path)
    run_exp2(config, tmp_path)
    manifest = json.loads((tmp_path / "exp1" / "manifest.json").read_text())
    assert manifest["optimization_rollouts"] == 3 * 4 * 2
    training = [pd.read_csv(p) for p in sorted((tmp_path / "exp1").glob("repeat_*/*/train.csv"))]
    for other in training[1:]:
        np.testing.assert_array_equal(training[0][["kp", "ki", "kd"]], other[["kp", "ki", "kd"]])
    transfer = pd.read_csv(tmp_path / "exp2" / "transfer_all.csv")
    for _, group in transfer.groupby("controller_id"):
        assert group[["kp", "ki", "kd"]].drop_duplicates().shape[0] == 1
        assert len(group) == 3
    summary = pd.read_csv(tmp_path / "exp2" / "transfer_summary.csv")
    assert summary.loc[summary.payload == 1, "L_HV"].iloc[0] == pytest.approx(0)
    from kroc_mobo.analysis import make_analysis

    make_analysis(tmp_path)
    assert (tmp_path / "analysis" / "fig1_payload_pareto.png").exists()


def test_snapshot_mismatch_and_existing_run_rejected(config, tmp_path):
    initialize_run(tmp_path, config, "exp1")
    with pytest.raises(FileExistsError):
        initialize_run(tmp_path, config, "exp1")
    config["plant"]["R"] = 2
    with pytest.raises(ValueError, match="different config"):
        initialize_run(tmp_path, config, "exp2")
