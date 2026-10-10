"""Scalar random-walk pressure estimator. Smoothing, not accuracy validation.

Q rate has units Pa^2/s; R has units Pa^2. Defaults are provisional demo
settings, not independently identified sensor-noise parameters.
"""
from math import isfinite


def filter_pressure(timestamps_s, pressures_pa, q_rate=4.0, r_variance=121.0):
    """Return causal pressure estimates; initialize from the first measurement.

    x[k] = x[k-1] + w; z[k] = x[k] + v. No IMU input, reference-speed
    input, clipping, automatic calibration, or prediction across invalid data.
    """
    if not isfinite(q_rate) or q_rate < 0:
        raise ValueError("Q rate must be finite and nonnegative")
    if not isfinite(r_variance) or r_variance <= 0:
        raise ValueError("R variance must be finite and positive")
    times, measurements = list(timestamps_s), list(pressures_pa)
    if len(times) != len(measurements):
        raise ValueError("Timestamp and pressure lengths differ")
    if not all(isfinite(v) for v in times + measurements):
        raise ValueError("Inputs must be finite")
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("Timestamps must strictly increase")
    if not times:
        return []
    estimate, variance = measurements[0], r_variance
    result = [estimate]
    for i in range(1, len(times)):
        predicted_variance = variance + q_rate * (times[i] - times[i - 1])
        gain = predicted_variance / (predicted_variance + r_variance)
        estimate += gain * (measurements[i] - estimate)
        variance = (1 - gain) * predicted_variance
        result.append(estimate)
    return result
