from copy import deepcopy

import numpy as np
import pytest

from kroc_mobo.config import validate
from kroc_mobo.pid import PID
from kroc_mobo.plant import dynamics, inertia
from kroc_mobo.simulation import simulate
from kroc_mobo.trajectory import quintic


def test_quintic_endpoints_and_midpoint():
    np.testing.assert_allclose(quintic([0, 2.5, 5], 5, -0.2, 1.2), [-0.2, 0.5, 1.2])
    h = 1e-5
    assert abs((quintic(h, 5, 0, 1) - quintic(0, 5, 0, 1)) / h) < 1e-8


def test_payload_inertia_and_dc_equations(config):
    p = config["plant"]
    assert inertia(p, 3) - inertia(p, 1) == pytest.approx(2 * p["r_p"] ** 2)
    np.testing.assert_allclose(
        dynamics([0, 0, 2], 4, 1, p), [0, 2 * p["K_t"] / inertia(p, 1), (4 - 2 * p["R"]) / p["L"]]
    )


def test_equilibrium_zero_energy(config):
    config["simulation"]["theta_end"] = 0
    config["simulation"]["duration"] = 0.1
    config["noise"]["power"] = 0
    r = simulate([10, 10, 1], 1, config, 12)
    assert r.metrics["JT"] == r.metrics["JE"] == 0
    assert r.metrics["feasible"]


def test_energy_balance_true_error_and_quadrature(config):
    gains = [70, 30, 5]
    r = simulate(gains, 3, config, 23, record=True)
    assert abs(r.metrics["energy_balance_residual"]) < 1e-5
    assert r.metrics["JE"] == pytest.approx(
        r.metrics["energy_drawn"] - r.metrics["energy_returned"], abs=1e-9
    )
    assert r.trace.energy_net.iloc[-1] == r.metrics["JE"]
    approx_rmse = np.sqrt(np.trapezoid(r.trace.error**2, r.trace.t) / config["simulation"]["duration"])
    assert approx_rmse == pytest.approx(r.metrics["JT"], rel=1e-5)
    refined = deepcopy(config)
    refined["simulation"]["integration_substeps"] *= 2
    r2 = simulate(gains, 3, refined, 23)
    assert r2.metrics["JT"] == pytest.approx(r.metrics["JT"], abs=1e-7)
    assert r2.metrics["JE"] == pytest.approx(r.metrics["JE"], abs=1e-5)


def test_seed_reproducibility_and_constraints_do_not_clip_current(config):
    config["simulation"]["duration"] = 0.2
    a = simulate([100, 20, 3], 1, config, 55)
    b = simulate([100, 20, 3], 1, config, 55)
    assert a.metrics == b.metrics
    config["limits"]["current_max"] = 0.0001
    constrained = simulate([100, 20, 3], 1, config, 55)
    assert not constrained.metrics["feasible"]
    assert constrained.metrics["JT"] == a.metrics["JT"]
    assert constrained.metrics["JE"] == a.metrics["JE"]
    assert "current" in constrained.metrics["violation"]


def test_numerical_abort_is_not_finite_objective(config):
    config["limits"]["numerical_abs_max"] = 1e-6
    r = simulate([70, 30, 5], 1, config, 1)
    assert r.metrics["numerical_failure"]
    assert not r.metrics["feasible"]
    assert np.isnan(r.metrics["JT"]) and np.isnan(r.metrics["JE"])


def test_pid_antiwindup(config):
    on = PID((10, 20, 0), 0.001, 1, 0.02, 10, qf=0)
    off = PID((10, 20, 0), 0.001, 1, 0.02, 0, qf=0)
    for _ in range(2000):
        assert abs(on.step(2, 0)[0]) <= 1
        off.step(2, 0)
    assert abs(on.z) < abs(off.z)


def test_invalid_time_step_and_seed_overlap(config):
    config["experiment"]["test_seed_base"] = config["experiment"]["train_seed_base"]
    with pytest.raises(ValueError, match="disjoint"):
        validate(config)
