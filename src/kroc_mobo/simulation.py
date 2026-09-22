"""Fixed-control-step simulator with RK4 quadrature and explicit feasibility."""

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .pid import PID
from .plant import dynamics, gravity_coefficient, inertia
from .trajectory import quintic


@dataclass
class Rollout:
    metrics: dict
    trace: pd.DataFrame | None


def simulate(gains, payload, c, seed, record=False, *, engine="compiled"):
    if engine not in ("compiled", "reference"):
        raise ValueError("Unknown simulation engine")
    s, p, limits = c["simulation"], c["plant"], c["limits"]
    dt, duration = s["control_dt"], s["duration"]
    n, sub = round(duration / dt), s["integration_substeps"]
    h = dt / sub
    times = np.arange(n + 1) * dt
    reference = quintic(times, duration, s["theta_start"], s["theta_end"])
    stride = round(c["noise"]["sample_dt"] / dt)
    noise = np.random.default_rng(seed).normal(
        0, math.sqrt(c["noise"]["power"] / c["noise"]["sample_dt"]), (n // stride) + 1
    )
    pid = PID(tuple(gains), dt, **c["controller"], qf=s["theta_start"])
    # theta, omega, i, integrated squared true error, net/drawn/returned energy, resistive/viscous loss.
    x = np.zeros(10)
    x[0] = s["theta_start"]
    peak = np.abs(x[:3])
    saturated, records, numerical, reason = 0, [], False, ""

    def rhs(t, y, voltage):
        theta, omega, current = y[:3]
        ref = float(quintic(t, duration, s["theta_start"], s["theta_end"]))
        power = voltage * current
        return np.r_[
            dynamics(y[:3], voltage, payload, p),
            (ref - theta) ** 2,
            power,
            max(power, 0),
            max(-power, 0),
            p["R"] * current**2,
            p["b"] * omega**2,
            p.get("N", 1.0) * (p["K_e"] - p.get("eta", 1.0) * p["K_t"]) * current * omega,
        ]

    def row(k, v, u, measured):
        return dict(
            t=times[k],
            reference=reference[k],
            theta=x[0],
            omega=x[1],
            current=x[2],
            measured=measured,
            error=reference[k] - x[0],
            voltage=v,
            command=u,
            power=v * x[2],
            energy_net=x[4],
            energy_drawn=x[5],
            energy_returned=x[6],
        )

    if engine == "compiled":
        from .kernel import integrate

        ratio, efficiency = p.get("N", 1.0), p.get("eta", 1.0)
        parameters = np.array(
            [
                inertia(p, payload),
                gravity_coefficient(p, payload),
                p["b"],
                p["R"],
                p["L"],
                efficiency * ratio * p["K_t"],
                ratio * p["K_e"],
            ]
        )
        x, peak, saturated, numerical, k, trace = integrate(
            np.asarray(gains, dtype=float),
            parameters,
            dt,
            duration,
            sub,
            s["theta_start"],
            s["theta_end"],
            noise,
            stride,
            c["controller"]["voltage_max"],
            c["controller"]["filter_tau"],
            c["controller"]["antiwindup_gain"],
            limits["numerical_abs_max"],
            record,
        )
        if numerical:
            reason = "numerical_failure"
        if record:
            records = pd.DataFrame(
                trace,
                columns=[
                    "t",
                    "reference",
                    "theta",
                    "omega",
                    "current",
                    "measured",
                    "error",
                    "voltage",
                    "command",
                    "power",
                    "energy_net",
                    "energy_drawn",
                    "energy_returned",
                ],
            )
    else:
        for k in range(n):
            measured = x[0] + noise[k // stride]
            voltage, command = pid.step(reference[k], measured)
            saturated += abs(command) > c["controller"]["voltage_max"]
            if record:
                records.append(row(k, voltage, command, measured))
            with np.errstate(over="ignore", invalid="ignore"):
                for j in range(sub):
                    t = times[k] + j * h
                    try:
                        a = rhs(t, x, voltage)
                        b = rhs(t + h / 2, x + h * a / 2, voltage)
                        d = rhs(t + h / 2, x + h * b / 2, voltage)
                        f = rhs(t + h, x + h * d, voltage)
                        x += h * (a + 2 * b + 2 * d + f) / 6
                    except (OverflowError, ValueError):
                        numerical, reason = True, "numerical_failure"
                        break
                    if not np.isfinite(x).all() or max(np.abs(x[:3])) > limits["numerical_abs_max"]:
                        numerical, reason = True, "numerical_failure"
                        break
                    peak = np.maximum(peak, np.abs(x[:3]))
            if numerical:
                break
        if record and not numerical:
            # Final row uses the left-limit held voltage; no extra controller update at T.
            records.append(row(n, voltage, command, x[0] + noise[n // stride]))
    margins = (
        peak / np.array([limits["angle_abs_max"], limits["velocity_abs_max"], limits["current_max"]]) - 1
    )
    feasible = not numerical and max(margins) <= 0
    violations = [name for name, margin in zip(("angle", "velocity", "current"), margins) if margin > 0]
    metrics = dict(
        seed=int(seed),
        payload=float(payload),
        JT=math.nan,
        JE=math.nan,
        feasible=bool(feasible),
        numerical_failure=bool(numerical),
        violation=reason or ";".join(violations),
        constraint_margin=float(max(margins)) if not numerical else 1.0,
        max_angle=float(peak[0]),
        max_velocity=float(peak[1]),
        max_current=float(peak[2]),
        saturation_fraction=float(saturated / (k + 1)),
        terminal_error=math.nan,
        energy_drawn=math.nan,
        energy_returned=math.nan,
        energy_balance_residual=math.nan,
        transmission_exchange=math.nan,
    )
    if not numerical:
        stored_delta = (
            0.5 * inertia(p, payload) * x[1] ** 2
            + 0.5 * p["L"] * x[2] ** 2
            + gravity_coefficient(p, payload) * (math.cos(s["theta_start"]) - math.cos(x[0]))
        )
        metrics.update(
            JT=math.sqrt(max(x[3], 0) / duration),
            JE=float(x[4]),
            terminal_error=float(reference[-1] - x[0]),
            energy_drawn=float(x[5]),
            energy_returned=float(x[6]),
            energy_balance_residual=float(x[4] - stored_delta - x[7] - x[8] - x[9]),
            transmission_exchange=float(x[9]),
        )
    return Rollout(metrics, pd.DataFrame(records) if record else None)


def evaluate(gains, payload, c, noise_seeds):
    rows = [simulate(gains, payload, c, seed).metrics for seed in noise_seeds]
    frame = pd.DataFrame(rows)
    valid = not frame.numerical_failure.any()
    result = {
        "JT": math.nan,
        "JE": math.nan,
        "JT_std": math.nan,
        "JE_std": math.nan,
        "JT_sem2": math.nan,
        "JE_sem2": math.nan,
    }
    if valid:
        for objective in ("JT", "JE"):
            std = float(frame[objective].std(ddof=1)) if len(frame) > 1 else 0.0
            result.update(
                {
                    objective: float(frame[objective].mean()),
                    f"{objective}_std": std,
                    f"{objective}_sem2": std**2 / len(frame),
                }
            )
    result.update(
        feasible=bool(frame.feasible.all()),
        numerical_failure=not valid,
        constraint_margin=float(frame.constraint_margin.max()),
        max_current=float(frame.max_current.max()),
        saturation_fraction=float(frame.saturation_fraction.mean()),
        terminal_error=float(frame.terminal_error.mean()) if valid else math.nan,
        n_rollouts=len(frame),
        violation=";".join(sorted(set(frame.violation) - {""})),
    )
    return result, rows
