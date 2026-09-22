"""Compiled RK4 implementation; same sampled PID and quadrature as reference simulator."""

import math

import numpy as np
from numba import njit


@njit(cache=True)
def reference(t, duration, start, end):
    u = min(1.0, max(0.0, t / duration))
    return start + (end - start) * (10 * u**3 - 15 * u**4 + 6 * u**5)


@njit(cache=True)
def rhs(t, x, v, p, duration, start, end):
    # Ieq, gravity coefficient, b, R, L, eta*N*Kt, N*Ke
    inertia, gravity, friction, resistance, inductance, torque, emf = p
    theta, omega, current = x[:3]
    power = v * current
    return np.array(
        [
            omega,
            (torque * current - friction * omega - gravity * math.sin(theta)) / inertia,
            (v - resistance * current - emf * omega) / inductance,
            (reference(t, duration, start, end) - theta) ** 2,
            power,
            max(power, 0.0),
            max(-power, 0.0),
            resistance * current**2,
            friction * omega**2,
            (emf - torque) * current * omega,
        ]
    )


@njit(cache=True)
def integrate(gains, p, dt, duration, sub, start, end, noise, stride, vmax, tau, kaw, guard, record):
    n = round(duration / dt)
    h = dt / sub
    x = np.zeros(10)
    x[0] = start
    peak = np.abs(x[:3])
    records = np.zeros((n + 1 if record else 0, 13))
    kp, ki, kd = gains
    qf, z = start, 0.0
    decay = math.exp(-dt / tau)
    saturated, numerical = 0, False
    voltage, command = 0.0, 0.0
    k = 0
    for k in range(n):
        t = k * dt
        ref = reference(t, duration, start, end)
        measured = x[0] + noise[k // stride]
        command = kp * (ref - measured) + z - kd * (measured - qf) / tau
        voltage = min(vmax, max(-vmax, command))
        saturated += abs(command) > vmax
        z += dt * (ki * (ref - measured) + kaw * (voltage - command))
        qf = measured + (qf - measured) * decay
        if record:
            records[k] = np.array(
                [
                    t,
                    ref,
                    x[0],
                    x[1],
                    x[2],
                    measured,
                    ref - x[0],
                    voltage,
                    command,
                    voltage * x[2],
                    x[4],
                    x[5],
                    x[6],
                ]
            )
        for j in range(sub):
            tj = t + j * h
            a = rhs(tj, x, voltage, p, duration, start, end)
            b = rhs(tj + h / 2, x + h * a / 2, voltage, p, duration, start, end)
            d = rhs(tj + h / 2, x + h * b / 2, voltage, p, duration, start, end)
            f = rhs(tj + h, x + h * d, voltage, p, duration, start, end)
            x += h * (a + 2 * b + 2 * d + f) / 6
            if not np.isfinite(x).all() or np.max(np.abs(x[:3])) > guard:
                numerical = True
                break
            peak = np.maximum(peak, np.abs(x[:3]))
        if numerical:
            break
    if record and not numerical:
        ref = reference(duration, duration, start, end)
        records[n] = np.array(
            [
                duration,
                ref,
                x[0],
                x[1],
                x[2],
                x[0] + noise[n // stride],
                ref - x[0],
                voltage,
                command,
                voltage * x[2],
                x[4],
                x[5],
                x[6],
            ]
        )
    return x, peak, saturated, numerical, k, records[: k + 1 if numerical else n + 1]
