# Solo completion plan — 10 October 2026

## First priority: verify tare during one complete run

An important correction to previous advice: turbulence was not established as
the sole cause. In the stored logs raw minus zeroed counts reveals the tare:
September 29 fanoff_rep2 = -47 counts; fanon_rep2 = +1411 counts.
September 25 speed-run offsets increase from +130 to +1640 counts, while
fan-off offsets are around -73 to -78. Airflow during startup tare is a strong
possibility. Confirm experimentally; do not retrospectively substitute offsets
from another session and call it validated calibration.

1. Secure the probe and leave fan OFF. Close Arduino Serial Monitor.
2. Find the port: `python -m serial.tools.list_ports`.
3. Start one log (replace COM5 with the actual port):
   `python airspeed_logging/serial_csv_logger.py --port COM5 --output logs/airflow/abp3_20261010_off_on_off_rep1.csv`
4. Read the printed `# ABP3 tare_counts=...` message. The logger now displays
   firmware comments/errors. If no startup message appears, reset the board
   with fan OFF while the logger remains connected.
5. Record 15–20 seconds fan OFF. Turn it ON without restarting the logger.
6. Let flow settle, then hold one speed for 30–60 seconds. Write down the
   anemometer mean/range and the approximate time of each transition.
7. Turn the fan OFF again, keep recording for 15–20 seconds, then Ctrl+C.
8. Check whether pressure returns to its initial baseline. Do not reconnect
   serial with fan ON: reconnecting can reset the board and tare under airflow.

Keep all phases in the original file. Select only a settled interval for
reference comparison; never assign the airflow reference to the initial zero
segment. The older calibration_analysis.py averages whole files and implements
an empirical count-to-speed fit, not the new Bernoulli validation workflow.

## Run the local CSV dashboard

`python -m streamlit run airspeed_logging/dashboard.py`

Select an existing live log or upload one. Inspect the inferred tare, choose the
time interval, inspect pressure/speed plots, and enter the actual anemometer
mean. Export the selected analysis CSV. Mean, bias, MAE, and RMSE include zero
speed samples. No fitted correction, Kalman fusion, or live serial dashboard
is claimed. Serial recording and CSV upload are separate steps.

## Deliverables

- Day 1: one verified off/on/off run, then at least three reference speeds
  with repetitions if time permits. Photograph fixed geometry.
- Day 2: selected-window validation tables/plots and report draft, using
  HANDOVER_REPORT_GUIDE.md but correcting its tare/turbulence explanation.
- Day 3: freeze firmware, final report/PPT and a rehearsed demonstration with
  saved backup logs. Do not claim flight readiness or validated sensor fusion.

Current firmware uses the agreed 0.0390625 Pa/count. Its column named
airspeed_calibrated_mps means density-compensated Bernoulli speed, not an
independently validated calibration. Near-zero positive speed from clipping
pressure noise is expected; a baseline alone does not validate absolute scale.
