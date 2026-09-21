"""Quintic rest-to-rest trajectory; angles in radians."""

import numpy as np


def quintic(t, duration, start, end):
    s = np.clip(np.asarray(t) / duration, 0.0, 1.0)
    return start + (end - start) * (10 * s**3 - 15 * s**4 + 6 * s**5)
