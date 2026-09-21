"""Sampled voltage PID; filtered derivative on measurement; integral state in volts."""

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class PID:
    gains: tuple
    dt: float
    voltage_max: float
    filter_tau: float
    antiwindup_gain: float
    qf: float
    z: float = 0.0

    def step(self, reference, measured):
        kp, ki, kd = self.gains
        error = reference - measured
        # qf is the filter state at t_k; sensor samples are held until t_(k+1).
        derivative = (measured - self.qf) / self.filter_tau
        command = kp * error + self.z - kd * derivative
        voltage = float(np.clip(command, -self.voltage_max, self.voltage_max))
        self.z += self.dt * (ki * error + self.antiwindup_gain * (voltage - command))
        self.qf = measured + (self.qf - measured) * math.exp(-self.dt / self.filter_tau)
        return voltage, command
