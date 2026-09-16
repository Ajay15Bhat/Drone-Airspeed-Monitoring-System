# Week 2 — Core Build

This plan translates the approved methodology and implementation timeline into concrete Week 2 work. It replaces every remaining reference to the old **MPXV7002DP analog/ADC sensor** with the selected **Honeywell ABP2MRRN004NDSA3XE SPI sensor**.

## Week 2 objective

By the end of the week, the team should have:

- a stable Pitot-tube bench fixture;
- real BME280 + MPU-6500 data streamed and logged as CSV;
- onboard pressure-to-airspeed calculation with BME280 density compensation;
- a documented calibration run ready to execute as soon as the ABP2 arrives;
- a dashboard prototype able to display either the current mock stream or recorded CSV files.

The ABP2 hardware is currently unavailable. This is not a reason to pause Week 2: keep `USE_MOCK_ABP2 = true` until it is wired and individually verified. Clearly label all mock-pressure results as **simulation**, not experimental measurements.

## Current verified baseline

| Component | Confirmed configuration | Status |
|---|---|---|
| ESP32 | DOIT ESP32 DEVKIT V1, serial at 115200 baud | Working |
| BME280 | I2C address `0x76`; chip-ID register `0xD0` returns `0x60` | Working |
| MPU sensor | I2C address `0x68`; `WHO_AM_I` register `0x75` returns `0x70` (MPU-6500-compatible) | Working |
| ABP2MRRN004NDSA3XE | ±4 inH2O differential, 3.3 V SPI, mode 0 | Awaiting hardware |
| Logging pipeline | `airspeed_logging/airspeed_logger/airspeed_logger.ino` -> serial -> `serial_csv_logger.py` -> `logs/*.csv` | Working in mock mode |

Do not use the separate `BMP280_TEST` folder for this project. The working environmental sensor is the BME280 listed above.

## Team task board

### Hardware & Integration Lead

- [ ] Build the Pitot-tube mount so the probe is secure, faces the airflow, and can be rotated repeatably for attitude tests.
- [ ] Build the bench-rig frame and document the airflow source, test distance, probe position, and safety precautions.
- [ ] Record a labelled photo or wiring diagram for the BME280 and MPU I2C bus: ESP32 `GPIO21` = SDA and `GPIO22` = SCL.
- [ ] Prepare ABP2 wiring without connecting it to 5 V. The ABP2 is a **3.3 V SPI** device.
- [ ] Decide and document the ESP32 SPI wiring used by the firmware: default proposal is `SCLK=18`, `MISO=19`, `MOSI=23`, `CS=5`, plus 3.3 V and GND.
- [ ] When the ABP2 arrives, verify package/breakout pin labels before applying power. Do not assume an I2C breakout pin order: this part is SPI.
- [ ] Connect the Pitot total-pressure port to ABP2 P1/high port and the static reference to P2/low port. Confirm the actual breakout’s port labels first.
- [ ] Run a zero-flow check after plumbing. Differential pressure should be near zero; if it is persistently negative, investigate port orientation or record a software sign correction.

**Hardware hand-off:** a photo-labelled fixture, wiring diagram, and a one-page bench-rig setup note for the calibration lead.

### Firmware Developer

- [ ] Keep the working sensor identities unchanged: BME280 `0x76`/`0x60`; MPU `0x68`/`0x70`.
- [ ] Use `airspeed_logger.ino` as the Week 2 firmware baseline, not `COMBINED_TESTING2.ino`, because the new sketch emits machine-readable CSV.
- [ ] Confirm the sample interval (`SAMPLE_PERIOD_MS`) is stable at 100 ms (10 Hz). Log the actual `timestamp_ms`; do not infer timestamps on the host.
- [ ] Add/verify a short moving average or low-pass filter for **differential pressure only**. Keep `diff_pressure_Pa` as the unfiltered converted value and add a new field only if a filtered value is logged.
- [ ] Keep the raw and corrected airspeed calculations distinct:
  - `airspeed_raw_mps = sqrt(2 * max(diff_pressure_Pa, 0) / 1.225)`
  - `airspeed_calibrated_mps = sqrt(2 * max(diff_pressure_Pa, 0) / air_density)` followed by a calibration gain/offset when those are measured.
- [ ] When the ABP2 arrives, set `USE_MOCK_ABP2 = false`, verify the SPI pins, then test status byte, pressure counts, pressure in inH2O, and pressure in Pa before relying on calculated airspeed.
- [ ] Preserve the CSV header exactly unless the algorithm and UI leads agree to a schema update together.
- [ ] Add a clear serial diagnostic for ABP2 status failure; never silently substitute mock values in live mode.

**Firmware hand-off:** a tagged/dated `.ino` file, a 60-second sample CSV, and a note stating whether the pressure data are `mock` or `live`.

### Algorithm & Calibration Lead

- [ ] Finalize `Calibration_Protocol.txt` before bench testing. It must specify reference instrument, airflow settings/speeds, sensor positions, trial duration, repetitions, and data-file naming.
- [ ] Define the reference-speed source. Suitable options include a calibrated anemometer, a fan/flow rig with a known calibration curve, or another documented reference. Do not treat a fan’s speed setting as true airspeed without validation.
- [ ] Use at least five setpoints across the usable bench range, including a near-zero/low-speed point, and repeat each setpoint at least three times.
- [ ] During calibration runs, populate `reference_speed_mps`; leave it blank for normal runs.
- [ ] For each run, calculate mean pressure, mean raw airspeed, mean density-compensated airspeed, standard deviation, error against reference, and response/settling time.
- [ ] Fit the simplest correction that explains the data (normally gain + offset or a low-order curve). Save the formula, units, valid range, date, and input dataset filename.
- [ ] Begin the Kalman-filter design on paper or in Python: state variables, input measurements, expected noise, and fault flags. Do not claim fusion accuracy until real ABP2 data exist.

**Algorithm hand-off:** approved calibration protocol, reference-speed data table, correction equation, and a short analysis notebook/script plan.

### UI & Documentation Lead

- [ ] Create a Streamlit project skeleton with a file-upload mode first. This avoids blocking dashboard work on serial access or the ABP2 delivery.
- [ ] Load and validate the current CSV schema. Show a useful error if a required field is missing.
- [ ] Display current values: temperature, static pressure, humidity, differential pressure, raw airspeed, calibrated airspeed, and `source` (`mock` or `live`).
- [ ] Plot time series for `diff_pressure_Pa`, `airspeed_raw_mps`, `airspeed_calibrated_mps`, and IMU axes.
- [ ] Display `reference_speed_mps` only when it is populated; overlay it during calibration analysis.
- [ ] Add a conspicuous dashboard warning whenever `source == mock` so simulated results cannot be mistaken for sensor measurements.
- [ ] Ensure CSV export preserves the full schema and does not rewrite blank `reference_speed_mps` cells as zero.
- [ ] Start the report’s implementation section: architecture diagram, wiring/communication summary, log-schema table, and a screenshot of the live/mock dashboard.

**UI hand-off:** a runnable Streamlit skeleton, one CSV import test, and screenshots showing mock-mode labelling.

## Shared integration checkpoints

### Checkpoint A — now

- [ ] Save a new 30–60 second log using the current mock mode.
- [ ] Confirm every row has 19 CSV columns and `source` is `mock`.
- [ ] Archive the log with a descriptive name, for example `week2_mock_20260910_run01.csv`.

### Checkpoint B — after ABP2 arrival

- [ ] Photograph the sensor and wiring before power-up.
- [ ] Perform an SPI communication/status test with no pressure applied.
- [ ] Set `USE_MOCK_ABP2 = false`.
- [ ] Verify `source` changes to `live`, the ABP status indicates powered/not busy/no error, and the pressure data vary with gentle applied pressure.
- [ ] Record a new log named `week2_abp2_live_<date>_run01.csv`.

### Checkpoint C — end-of-week review

- [ ] Bench fixture is stable and documented.
- [ ] Firmware logs real BME280 + MPU data and mock or live ABP2 data without malformed rows.
- [ ] Density-compensated airspeed is present in every valid row.
- [ ] Calibration protocol and dashboard skeleton are reviewable.
- [ ] Team agrees which remaining work moves to Week 3: live ABP2 calibration, fusion integration, and first bench trials.

## CSV contract

Do not rename or reorder fields without notifying every lead:

```text
timestamp_ms,source,temp_C,pressure_hPa,humidity_pct,
accel_x_g,accel_y_g,accel_z_g,gyro_x_dps,gyro_y_dps,gyro_z_dps,
diff_pressure_counts,diff_pressure_inH2O,diff_pressure_Pa,
abp_temperature_C,abp_status,airspeed_raw_mps,
airspeed_calibrated_mps,reference_speed_mps
```

Units are encoded in each field name. `reference_speed_mps` is blank outside calibration runs. `source=mock` means every ABP2-derived pressure and airspeed value is simulated; BME280 and MPU fields remain real measurements.

## Definition of done for Week 2

Week 2 is complete when the team can demonstrate an end-to-end run from sensor sampling to CSV to dashboard, the Pitot bench fixture is ready, the calibration procedure is approved, and the pressure-to-airspeed/density-correction calculations are implemented and documented. If the ABP2 has not arrived, record that limitation explicitly and use mock-mode results only to validate the software pipeline.
