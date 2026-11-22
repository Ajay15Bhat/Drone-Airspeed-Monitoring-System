# Drone Airspeed Monitoring — Team Handover and Report Guide

> HISTORICAL GUIDE: superseded for final reporting by
> [PROJECT_REPORT_20261010.md](PROJECT_REPORT_20261010.md) and
> [PRESENTATION_BRIEF_20261010.md](PRESENTATION_BRIEF_20261010.md).
> In particular, filtering is now integrated, status 0xC018/0xC019 includes
> missed-update flags, and the cause of the accuracy discrepancy is not proven.
> Do not copy the older calibration/completion claims below into a final report.

## Purpose

This file gives the remaining team members the verified project state and a
source-grounded plan for writing the detailed progress report. The report must
describe the live Honeywell **ABP3** system only. Do **not** present old ABP2
code, mock logs, legacy calibration curves, or legacy constants as project
results.

## One-paragraph project summary

The project is a drone airspeed-monitoring system built around an ESP32, a
Honeywell ABP3 differential-pressure sensor, a Pitot tube, a BME280
environmental sensor, and an MPU-6500-compatible IMU. The ESP32 reads all
three sensors over I2C and saves live 19-column CSV logs. The ABP3 pressure
reading is zeroed at startup, converted from signed digital counts to
differential pressure using the mentor-provided 10–90% transfer function, and
converted to Bernoulli airspeed using BME280-derived moist-air density. The
current work stage is **bench validation**: the digital pressure and
environmental calculations work, but the Pitot/blower fixture must be made
rigid and less turbulent before claiming a final airspeed accuracy.

## Confirmed system configuration

| Item | Confirmed configuration |
| --- | --- |
| Controller | ESP32, serial logging at 115200 baud |
| BME280 | I2C address `0x76`, chip ID `0x60` |
| MPU-6500-compatible IMU | I2C address `0x68`, `WHO_AM_I = 0x70` |
| Honeywell ABP3 | I2C address `0x6C`, SDA GPIO21, SCL GPIO22, 100 kHz |
| ABP3 acquisition | Write `0x8B93` LSB-first to `0x22`; wait 10 ms; read six bytes at `0x2E` |
| Startup tare | Average 32 equal-pressure ABP3 samples; subtract from every pressure reading |
| Pressure transfer adopted for this project | `−25600 counts = −1 kPa`, `+25600 counts = +1 kPa` |
| Pressure conversion | `diff_pressure_Pa = zeroed_counts × 0.0390625` |
| Density-compensated airspeed | `V = sqrt(2 × max(ΔP, 0) / ρ)` |

The transfer function and I2C protocol come from the mentor-provided files:

- `ABP3-I2C_Technote_19082026 (1).pdf`
- `hon-ia-hss-3021-9392-a-abp3-bm-press-dts-en.pdf` (originally supplied from Downloads)

## Completed work and evidence

### 1. Hardware communication and integration — complete

- BME280, MPU-6500, and ABP3 respond on the shared I2C bus.
- Firmware checks BME280 chip ID, MPU identity, and ABP3 I2C presence at
  startup.
- ABP3 single-shot measurement, signed pressure count interpretation,
  temperature conversion, and status logging are implemented.

**Evidence:** `airspeed_logging/airspeed_logger/airspeed_logger.ino`,
`ABP3_I2C_TEST/ABP3_I2C_TEST.ino`, and `ABP3_I2C_TEST/Sensor_test.txt`.

### 2. Live CSV logging — complete

The ESP32 writes live rows with environmental, IMU, ABP3 raw/zeroed counts,
ABP3 temperature/status, differential pressure, and calculated airspeed.

**CSV schema:**

```text
timestamp_ms,source,temp_C,pressure_hPa,humidity_pct,
accel_x_g,accel_y_g,accel_z_g,gyro_x_dps,gyro_y_dps,gyro_z_dps,
abp3_pressure_raw_counts,abp3_pressure_zeroed_counts,
abp3_temperature_C,abp3_status,diff_pressure_Pa,
airspeed_raw_mps,airspeed_calibrated_mps,reference_speed_mps
```

**Evidence:** `airspeed_logging/serial_csv_logger.py` and `logs/airflow/`.

### 3. Zero-flow and polarity testing — complete

The following physical checks have been completed with expected results:

- Fan-off baseline recorded.
- ABP3 counts respond to applied airflow.
- Pitot 180° orientation test completed.
- `SENSE+` is connected to Pitot total pressure and `SENSE−` to static
  pressure.

Latest strong baseline evidence:

| File | Duration | Valid rows | Mean zeroed counts | Count SD | Mean ΔP |
| --- | ---: | ---: | ---: | ---: | ---: |
| `abp3_airflow_20260929_fanoff_rep2.csv` | 195.6 s | 1957 | +0.30 | 14.24 | 0.012 Pa |

Only normal ABP3 status values (`0xC018`, `0xC019`) occurred in that run.

### 4. Pressure conversion and Bernoulli calculation — implemented

The active firmware now uses the agreed signed ABP3 conversion:

```text
ΔP_Pa = zeroed_counts × (1000 / 25600)
```

It calculates both:

```text
airspeed_raw_mps = sqrt(2 × max(ΔP, 0) / 1.225)
airspeed_calibrated_mps = sqrt(2 × max(ΔP, 0) / rho_BME280)
```

`rho_BME280` is calculated from BME280 temperature, atmospheric pressure, and
relative humidity using the moist-air gas-law/Magnus-Tetens approach.

**Evidence:** `airspeed_logging/airspeed_logger/airspeed_logger.ino`.

### 5. Initial airflow testing — completed, not final validation

Initial airflow runs were collected at nominal anemometer readings between
approximately 2.6 and 7.8 m/s. They demonstrated ABP3 response but had poor
repeatability because the Pitot was hand-held and airflow in the bent duct was
turbulent. A direct count-to-speed fit of that initial set produced:

```text
R² = 0.281370
RMSE = 2.231181 m/s
```

These values must be reported as an early bench-test finding, not as final
performance. The analysis correctly identified that the fixture needed
improvement.

**Evidence:** `Airflow_Calibration_20260925.md`,
`calibration_output/airflow_20260925/abp3_airspeed_calibration.json`, and
the earlier `logs/airflow/abp3_pitot_*.csv` files.

### 6. Latest fan-on result — promising calculation, invalid final accuracy

For `abp3_airflow_20260929_fanon_rep2.csv`, the anemometer was reported around
5.5–6 m/s. The firmware produced populated pressure and airspeed columns. If
zero-speed samples are excluded, the mean BME280-density-compensated airspeed
is 5.212 m/s. This is only a diagnostic comparison because 289 of 623 samples
were clipped to zero after negative pressure readings; the fixture is still not
stable enough for final accuracy claims.

## Current limitations (must be stated honestly)

1. The Pitot was previously hand-held and could contact the duct wall.
2. The bent blower duct causes swirl and non-uniform airflow.
3. The fan-on pressure run still has large positive/negative count swings.
4. A final validated correction curve, final RMSE, and final R² are therefore
   not yet available.
5. The Kalman filter and Streamlit dashboard are not yet integrated with the
   validated live ABP3/Bernoulli output.

## Remaining technical work

### Priority 1 — repeatable bench fixture

- Rigidly mount and centre the Pitot; do not hold it by hand.
- Ensure the tip faces incoming airflow and static holes remain clear.
- Prevent contact between the Pitot and duct wall.
- Use a straight outlet section or flow straightener where possible.
- Position the anemometer near the Pitot tip at the same height, outside its
  wake.
- Photograph the final fixture, tubing, wiring, and Pitot orientation.

### Priority 2 — validation data collection

For every target speed:

1. Fan off and reset/start logger so the 32-sample tare happens at zero flow.
2. Record a 30–60 second fan-off baseline.
3. Turn on the fan and set one fixed airflow level.
4. Wait 20–30 seconds for settling.
5. Record 30–60 seconds of stable flow.
6. Record the actual mean anemometer speed, not only a blower setting/range.
7. Repeat three times per speed.

Suggested target levels: 0, 2.5–3, 4, 5–5.5, 6–6.5, and 7–8 m/s.

### Priority 3 — final validation analysis

For each stable part of each log, calculate:

- mean/standard deviation of zeroed counts;
- mean/standard deviation of pressure in Pa;
- mean/standard deviation of BME280-density-compensated airspeed;
- bias, MAE, RMSE, percentage error, and R² against the anemometer;
- repeatability across the three repetitions.

If a stable, systematic offset remains after proper fixture validation, fit a
small empirical correction such as:

```text
final_airspeed = a × Bernoulli_airspeed + b
```

Do not fit this correction using the unstable first airflow set.

### Priority 4 — filtering, fusion, UI

- Compare raw pressure against a moving-average or low-pass pressure filter.
- Add the filter only if it reduces noise without unacceptable delay.
- Update/test Kalman fusion using validated ABP3 airspeed and MPU data.
- Build Streamlit dashboard: CSV validation, environmental cards, ABP3 status,
  counts, pressure, airspeed, plots, and validation metrics.

## Report outline for the team

Use this structure. Assign one member to text/technical accuracy and one to
figures/data presentation, then review every number together.

1. **Title page** — project name, team, mentor, date.
2. **Abstract** — objective, live sensing capability achieved, current
   validation stage, and next work.
3. **Problem statement and objectives** — why drone airspeed matters; project
   objectives from `Objectives_and_Methodology_Updated.docx`.
4. **System architecture** — ESP32, ABP3/Pitot, BME280, MPU, serial CSV host,
   and future dashboard/fusion blocks.
5. **Hardware implementation** — wiring, addresses, I2C bus, Pitot ports,
   tubing, physical setup photo.
6. **ABP3 acquisition and conversion method** — single-shot sequence, signed
   16-bit conversion, startup tare, `±25600 ↔ ±1 kPa` mapping, density
   calculation, and Bernoulli equation.
7. **Software implementation** — firmware, CSV schema, serial logger,
   analysis workflow.
8. **Experimental procedure** — fan-off tare, fixed-speed runs, anemometer
   reference, repetitions, status checks.
9. **Results and discussion** — baseline table, initial response data,
   pressure/airspeed result, and explanation of fixture limitations.
10. **Current progress versus remaining work** — use the priority list above.
11. **Conclusion** — full live sensing chain works; final bench accuracy is
   pending rigid-fixture validation.
12. **References and appendices** — mentor-provided ABP3 technote/datasheet,
   code excerpts, CSV schema, and extra plots.

## Required figures and tables

- Photo of final wiring and final bench fixture.
- System block diagram.
- ABP3 I2C sequence diagram (`0x22`, `0x8B93`, 10 ms, `0x2E`).
- CSV schema or one annotated live-row screenshot.
- Fan-off baseline table using `fanoff_rep2`.
- Time-series plot: zeroed counts and/or pressure versus time for fan-off.
- Time-series plot: pressure and density-compensated airspeed for a stable
  airflow run after the fixture is repaired.
- Scatter plot: anemometer speed versus calculated airspeed after final trials.
- Calibration/validation table: reference speed, predicted speed, bias, SD,
  RMSE.

## Accuracy and wording rules

- Say **implemented** for live sensor acquisition, startup tare, CSV logging,
  count-to-Pa conversion, BME280 density, and Bernoulli calculation.
- Say **under validation** for bench airspeed accuracy and empirical
  correction.
- Say **future work** for validated Kalman fusion and dashboard integration.
- Never state that the initial `R² = 0.281` result is final calibration.
- Never call the zero-excluded 5.212 m/s result a final validated mean; report
  it only with its limitation.
- Use units consistently: Pa, counts, m/s, hPa, °C, %, and kg/m³.

## Relevant repository files

| File or folder | Purpose |
| --- | --- |
| `airspeed_logging/airspeed_logger/airspeed_logger.ino` | Active ESP32 firmware |
| `airspeed_logging/serial_csv_logger.py` | Serial-to-CSV logger |
| `airspeed_logging/calibration_analysis.py` | Live ABP3 analysis tool |
| `logs/airflow/` | Live baseline and airflow CSV evidence |
| `Airflow_Calibration_20260925.md` | Initial airflow-analysis conclusion |
| `Calibration_Protocol.txt` | Calibration procedure |
| `WEEK_2_README.md` | Project task tracking |
| `Objectives_and_Methodology_Updated.docx` | Formal objectives/methodology |
| `OUR_SETUP.jpeg` | Existing setup photo |

## Git hygiene

Do not commit generated Python cache files, especially:

```text
airspeed_logging/__pycache__/
```

Review every modified/untracked file before committing. Keep live ABP3 logs,
analysis reports, firmware, and documentation; omit secrets and temporary
files.
