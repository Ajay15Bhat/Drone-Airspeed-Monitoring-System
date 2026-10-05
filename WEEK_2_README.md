# Week 2 — Core Build

## Current scope

This checklist reflects the installed hardware: Honeywell **ABP3 I2C** pressure sensor at `0x6C`, not the obsolete ABP2 SPI sensor. ABP2-specific sketches, conversion constants, calibration outputs, and mock logs are retained only as legacy/simulation material; they are not evidence of live ABP3 calibration.

## Verified baseline

| Component | Confirmed configuration | Status |
|---|---|---|
| ESP32 | Serial at 115200 baud | Working |
| BME280 | I2C `0x76`; chip ID `0x60` | Working and logged live |
| MPU-6500-compatible board | I2C `0x68`; `WHO_AM_I` `0x70` | Working and logged live |
| Honeywell ABP3 | I2C `0x6C`; GPIO21/22; 100 kHz | Working and logged live |
| ABP3 acquisition | `0x8B93` LSB-first at `0x22`; wait 10 ms; read six bytes from `0x2E` | Working |
| Startup tare | 32 equal-pressure samples; raw and zeroed counts logged | Working |
| Logging pipeline | ESP32 → serial → `serial_csv_logger.py` → CSV | Working with live ABP3 data |

The live file `logs/airspeed_20260915_232433.csv` contains 140 valid, 19-column records at about 10 Hz. It logs ABP3 raw and zeroed signed counts, temperature, and status. Pressure in Pa and calculated airspeed remain intentionally blank because ABP3 Pa/count has not yet been measured.

## Team task board

### Hardware & Integration Lead

- [ ] Build and document a secure, repeatable Pitot-tube mount.
- [ ] Build and document the airflow bench: source, test distance, probe position, and safety precautions.
- [ ] Record a labelled photo or wiring diagram of the final shared I2C bus: ESP32 GPIO21 = SDA, GPIO22 = SCL, with BME280, MPU, and ABP3 addresses.
- [x] Wire and verify the ABP3 at 3.3 V on I2C `0x6C`; retain the 100 kHz bus rate.
- [x] Verify ABP3 single-shot communication, signed pressure counts, temperature, and status.
- [x] Perform an equal-pressure zero check and implement startup tare.
- [ ] Connect and verify the Pitot total-pressure port to ABP3 `SENSE+` and static reference to `SENSE−`; confirm pressure polarity under controlled airflow.
- [ ] Perform a documented zero-flow check after final Pitot plumbing.

**Hardware hand-off:** labelled wiring/fixture photos and a one-page bench-rig setup note.

### Firmware Developer

- [x] Preserve BME280 `0x76`/`0x60` and MPU `0x68`/`0x70` operation.
- [x] Use `airspeed_logging/airspeed_logger/airspeed_logger.ino` as the CSV-producing firmware baseline.
- [x] Log actual `timestamp_ms` at the configured 100 ms period (10 Hz).
- [x] Replace the obsolete ABP2/SPI path with the verified ABP3/I2C reader.
- [x] Update the serial logger and mock stream to the ABP3 19-column CSV schema.
- [x] Log raw and startup-tare-zeroed ABP3 pressure counts, ABP3 temperature, and ABP3 status.
- [x] Keep `diff_pressure_Pa`, `airspeed_raw_mps`, and `airspeed_calibrated_mps` blank until live ABP3 Pa/count calibration exists.
- [ ] Add a pressure-only filter after calibration establishes pressure units; log the unfiltered value separately if a filtered field is added.
- [ ] Convert zeroed ABP3 counts to Pa using a measured calibration, then implement raw and density-compensated airspeed.
- [ ] Add explicit serial diagnostics for ABP3 read/status faults instead of silently dropping a sample.
- [ ] Capture a labelled 60-second live ABP3 CSV as the firmware hand-off artifact.

### Algorithm & Calibration Lead

- [x] Draft a detailed calibration protocol: reference-instrument requirements, airflow setpoints, probe geometry, repetitions, timing, and filename convention.
- [x] Define a reference-speed source requirement; do not use an unvalidated fan setting as the reference.
- [x] Build a simulation dataset generator, calibration-analysis tool, curve export, JSON export, and firmware-constant export.
- [x] Analyse the 5,800-row **mock ABP2** dataset: statistics, density compensation, regression, error metrics, and settling-time calculation.
- [x] Design and simulate the IMU/Pitot Kalman-filter and fault-gating architecture.
- [x] Update `Calibration_Protocol.txt` and `calibration_analysis.py` to an ABP3 I2C known-pressure workflow; the legacy ABP2 dataset generator and outputs remain explicitly excluded.
- [ ] Establish ABP3 Pa/count, zero offset, polarity, linearity, and uncertainty from a controlled known-pressure reference.
- [ ] Run at least five live ABP3/Pitot airflow setpoints with three repetitions and populated `reference_speed_mps` values.
- [ ] Fit and validate a live ABP3 calibration model; do not use the current ABP2-derived slope, offset, or `0.142 Pa/count` placeholder in firmware.

### UI & Documentation Lead

- [ ] Create a Streamlit dashboard skeleton with CSV upload.
- [ ] Validate the current ABP3 CSV schema and show a clear missing-column error.
- [ ] Show temperature, barometric pressure, humidity, ABP3 raw/zeroed counts, status, and source.
- [ ] Add pressure/airspeed cards and plots only when their calibrated fields are populated.
- [ ] Plot IMU axes and conditionally overlay `reference_speed_mps` during calibration runs.
- [ ] Add a clear mock-data warning and preserve blank values during CSV export.
- [ ] Update report documentation with architecture, ABP3 I2C wiring/communication, the current CSV schema, and screenshots.

## Shared integration checkpoints

### Checkpoint A — live sensor logging

- [x] Confirm a live ABP3 log has 19 valid CSV columns.
- [x] Confirm real BME280, MPU, and ABP3 data are acquired together.
- [x] Confirm the uncalibrated Pa and airspeed fields are blank rather than fabricated.
- [ ] Save a descriptive, labelled 30–60 second live baseline log (for example, `week2_abp3_live_YYYYMMDD_zero_flow.csv`).

### Checkpoint B — calibration readiness

- [ ] Final Pitot/bench fixture and labelled wiring documentation are complete.
- [ ] Known-pressure ABP3 calibration determines Pa/count and polarity.
- [ ] Firmware emits calibrated pressure in Pa and raw/density-compensated airspeed.
- [ ] A reference anemometer airflow validation log is recorded.

### Checkpoint C — end-of-week review

- [ ] Bench fixture is stable and documented.
- [x] Firmware logs real BME280, MPU, and ABP3 data without malformed rows.
- [ ] Density-compensated airspeed is present in every calibrated live row.
- [x] Calibration protocol and analysis tooling are reviewable; the ABP3 migration remains pending.
- [ ] Dashboard skeleton is reviewable.
- [ ] Team records which remaining calibration, firmware integration, fusion validation, and bench-trial items move to Week 3.

## Current ABP3 CSV contract

```text
timestamp_ms,source,temp_C,pressure_hPa,humidity_pct,
accel_x_g,accel_y_g,accel_z_g,gyro_x_dps,gyro_y_dps,gyro_z_dps,
abp3_pressure_raw_counts,abp3_pressure_zeroed_counts,
abp3_temperature_C,abp3_status,diff_pressure_Pa,
airspeed_raw_mps,airspeed_calibrated_mps,reference_speed_mps
```

`reference_speed_mps` is blank outside a calibration run. Until known-pressure calibration is complete, the Pa and airspeed columns must remain blank.
