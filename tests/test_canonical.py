from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from kroc_mobo.config import load_config
from kroc_mobo.plant import dynamics, inertia
from kroc_mobo.simulation import simulate


@pytest.fixture
def canonical():
    return load_config(Path(__file__).resolve().parents[1] / "configs/canonical_final.toml")


def test_canonical_si_units_and_equations(canonical):
    p = canonical["plant"]
    assert p["J_m"] == pytest.approx(81.2e-7)
    assert p["J_g"] == pytest.approx(14e-7)
    np.testing.assert_allclose(
        [inertia(p, m) for m in (1, 2, 3)], [0.19780618666666667, 0.23780618666666667, 0.2778061866666667]
    )
    theta, omega, current, voltage = 0.4, 0.3, 1.2, 5.0
    actual = dynamics([theta, omega, current], voltage, 3, p)
    expected = [
        omega,
        (0.72 * 126 * 0.0292 * current - 0.05 * omega - 9.81 * (0.5 * 0.1 + 3 * 0.2) * np.sin(theta))
        / inertia(p, 3),
        (voltage - 0.568 * current - 0.0291 * 126 * omega) / 0.000191,
    ]
    np.testing.assert_allclose(actual, expected)


def test_compiled_reference_and_step_convergence(canonical):
    canonical["simulation"]["duration"] = 0.15
    canonical["simulation"]["theta_end"] = 0.02
    a = simulate([70, 30, 5], 3, canonical, 23, record=True)
    b = simulate([70, 30, 5], 3, canonical, 23, record=True, engine="reference")
    np.testing.assert_allclose(a.trace, b.trace, atol=1e-10, rtol=1e-9)
    refined = deepcopy(canonical)
    refined["simulation"]["integration_substeps"] *= 2
    fine = simulate([70, 30, 5], 3, refined, 23)
    assert a.metrics["JT"] == pytest.approx(fine.metrics["JT"], abs=1e-8)
    assert a.metrics["JE"] == pytest.approx(fine.metrics["JE"], abs=1e-6)
    assert abs(a.metrics["energy_balance_residual"]) < 1e-6
    assert np.max(np.abs(a.trace.voltage)) <= 24


def test_current_limit_is_feasibility_not_clipping(canonical):
    canonical["simulation"]["duration"] = 0.1
    a = simulate([200, 100, 20], 3, canonical, 12)
    canonical["limits"]["current_max"] = 0.001
    b = simulate([200, 100, 20], 3, canonical, 12)
    assert not b.metrics["feasible"]
    assert a.metrics["JE"] == b.metrics["JE"]
    assert a.metrics["JT"] == b.metrics["JT"]
