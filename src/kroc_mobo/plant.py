"""Geared DC motor and vertical 1-DOF rigid joint (SI units)."""

import math

import numpy as np


def inertia(plant, payload):
    return (
        plant.get("N", 1.0) ** 2 * (plant["J_m"] + plant.get("J_g", 0.0))
        + plant["J_l"]
        + payload * plant["r_p"] ** 2
    )


def gravity_coefficient(plant, payload):
    return (plant["m_l"] * plant["r_l"] + payload * plant["r_p"]) * plant["g"] * plant["gravity"]


def dynamics(x, voltage, payload, plant):
    theta, omega, current = x
    return np.array(
        [
            omega,
            (
                plant.get("eta", 1.0) * plant.get("N", 1.0) * plant["K_t"] * current
                - plant["b"] * omega
                - gravity_coefficient(plant, payload) * math.sin(theta)
            )
            / inertia(plant, payload),
            (voltage - plant["R"] * current - plant["K_e"] * plant.get("N", 1.0) * omega) / plant["L"],
        ]
    )
