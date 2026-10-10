# Airspeed filtering demo — validation pending

> Update: the firmware and dashboard now support on-device filtering and
> monitoring a growing CSV. Use [RUN_AIRSPEED_DEMO.md](RUN_AIRSPEED_DEMO.md)
> for current setup, health handling and schema details. The original
> saved-log implementation and its numerical example are documented below.

## What is implemented

The existing ESP32 firmware logs ABP3 pressure counts, BME280 environmental
measurements, IMU readings, and unfiltered Bernoulli airspeed. The Python
dashboard now adds a causal scalar Kalman filter to differential pressure,
then converts filtered pressure to density-compensated airspeed.

This is saved-log analysis, not real-time ESP32 filtering or IMU fusion.
No firmware reflash is required. Original logs and original CSV columns are
preserved. Export adds filtered fields, filter settings and validation state.

## Run the demonstration

From the project directory:

```powershell
python -m streamlit run airspeed_logging/dashboard.py
```

1. Select `abp3_20261010_off_on_off_rep2.csv` in the saved-log selector.
2. Show the full recording to explain OFF–ON–OFF behaviour and filter lag.
3. Select 50–110 seconds for the middle fan-on interval, provided the operator
   confirms this was the intended steady fan setting.
4. Show pressure and speed charts: raw and filtered estimates are overlaid.
5. Enable reference comparison and enter 6.5 m/s. Explain that this is an
   approximate, sequential handheld reading, not a synchronized trace.
6. Download the selected analysis CSV if needed for the report.

Do not delete zero samples to improve agreement. Do not compare a full-run
average containing fan-off periods with a fan-on reference speed.

## Filter definition and limitations

State: differential pressure x in Pa. Measurement: zeroed counts * 0.0390625.
Model: x[k] = x[k-1] + process noise; z[k] = x[k] + measurement noise.

At each sample, using actual elapsed time dt:

```text
P_predict = P_previous + Q_rate * dt
K = P_predict / (P_predict + R)
x = x_previous + K * (measurement - x_previous)
P = (1 - K) * P_predict
speed = sqrt(2 * max(x, 0) / BME280_density)
```

Initialize x from the first measurement and P from R. Defaults: Q_rate=4
Pa²/s and R=121 Pa². These are provisional demonstration settings. The R
value approximately reflects rep2 fan-on pressure variance, which contains
real airflow fluctuations as well as measurement noise. It is not an
independent sensor-noise calibration. Larger Q or smaller R increases
responsiveness; stronger smoothing adds lag and can hide real fluctuations.

The filter processes the entire log before selecting a display interval.
Negative pressure remains visible; only speed conversion clamps at zero.
Timestamp resets, missing required numeric data and non-finite inputs are
rejected. ABP3 status counts are displayed, but diagnostic fault rejection
is not implemented: the filter must not be treated as a sensor health check.

No IMU-derived velocity is fused. IMU channels remain recorded for future
motion/vibration analysis. The filter cannot correct a wrong pressure scale,
pressure-port connection, rig disturbance, or reference mismatch. Output
is experimental and not validated for flight control.

## Rep2 result (50–110 seconds)

| Quantity | Result |
|---|---:|
| Approximate handheld reference | 6.5 m/s |
| Unfiltered speed mean | 9.68 m/s |
| Filtered speed mean | 9.75 m/s |
| Unfiltered speed sample SD | 1.11 m/s |
| Filtered speed sample SD | 0.16 m/s |

These results demonstrate reduced variation, NOT improved absolute accuracy.
Filtering pressure before the nonlinear square root can change mean speed;
the filtered mean need not equal the unfiltered mean. Transition lag is also
visible in the full-run plot. Do not call the SD reduction an accuracy gain.

## Presentation wording

"We implemented three-sensor acquisition, CSV logging, the selected ABP3
transfer function, density-compensated Bernoulli airspeed, and a Python
Kalman pressure-filtering demonstration. Filtering reduces output
fluctuations. Absolute airspeed validation remains incomplete: this run
reports approximately 9.7 m/s against an approximately 6.5 m/s handheld
reference. Pressure-reference and airflow-rig checks are the next steps."

## Remaining work

- Check pressure connections and compare ABP3 against a suitable low-range
  differential-pressure reference when available.
- Establish comparable Pitot/anemometer measurement conditions; repeat at
  multiple speeds and keep separate holdout runs for validation.
- Tune noise parameters using justified data and evaluate transition lag.
- Add explicit sensor-status handling before deployment.
- If required later, port the tested filter to firmware and verify hardware
  behaviour. IMU fusion requires a justified motion/wind model and additional
  information; it is not a replacement for independent validation.

## Verification performed

Six unit tests cover known updates, elapsed-time scaling, causality,
constant/negative pressure, convergence, invalid inputs and empty inputs.
Dashboard initial-load smoke test passed; full interactive browser operation
and hardware execution have not been tested in this change.

```powershell
python -m unittest discover -s airspeed_logging -p test_kalman_filter.py
```
