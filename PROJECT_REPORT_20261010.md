# ESP32-Based Experimental Airspeed Monitoring System

## Implementation and bench-test report

**Report date:** 10 October 2026  
**Status:** Integrated experimental prototype; absolute airspeed accuracy unvalidated  
**Platform:** ESP32, Honeywell ABP3, Pitot probe, BME280, MPU-6500-compatible IMU  
**Team / institution / mentor:** Insert confirmed submission details before release.

## Abstract

This project implements an experimental airspeed-monitoring system intended
as a foundation for drone instrumentation. An ESP32 acquires differential
pressure, environmental measurements and inertial data over a shared I2C
bus. Signed ABP3 pressure counts are zeroed at startup and converted to
pascals using the adopted mentor-provided transfer function. Airspeed is
estimated using Bernoulli's relation and moist-air density calculated from
BME280 measurements. A scalar Kalman filter smooths differential pressure
before airspeed conversion. Both unfiltered and filtered results are retained.

A Python logger records serial telemetry, while a Streamlit dashboard
provides recorded-data analysis, growing-file monitoring, environmental and
IMU plots, diagnostic indicators and CSV export. The updated firmware has
been compiled and a hardware-generated 27-column log confirms integrated
operation. Fourteen automated Python tests pass.

Bench measurements demonstrate airflow response and pressure recovery toward
the initial baseline. However, the Pitot-derived estimate disagrees with a
sequential handheld-anemometer reference. In one selected fan-on interval,
the unfiltered mean was 9.68 m/s against an approximately 6.5 m/s reference.
Filtering reduced variation but did not resolve this discrepancy. The work
therefore demonstrates implementation and functional operation, not validated
airspeed accuracy, IMU–airspeed fusion or flight suitability.

## 1. Objectives and scope

The implemented objectives are to acquire three sensor streams, convert
pressure counts into physical units, compensate the airspeed estimate for
air density, reduce short-term fluctuations, record reproducible telemetry,
and provide an understandable monitoring interface.

The present scope is a stationary bench prototype. Autonomous flight control,
certified instrumentation, independently validated calibration and navigation
sensor fusion are outside the completed scope. Data labelled `live` means
hardware-origin measurements rather than mock data; it does not prove that
a displayed saved recording is currently updating.

## 2. System architecture

```text
Pitot total/static ports --> ABP3 --> signed counts --> startup tare --> Pa
                                                                      |
BME280 --> temperature / absolute pressure / humidity --> density       |
                                                          |           |
                         +--------------------------------+-----------+
                         |                                            |
                  direct Bernoulli                         pressure Kalman filter
                         |                                            |
                  unfiltered speed                         filtered Bernoulli speed

MPU-6500 --> acceleration / angular rate ----+
All pressure, environment and speed data ---+--> ESP32 serial --> CSV logger
                                                             --> dashboard
```

The dashboard reads the logger's CSV rather than opening the serial port.
This avoids a second serial connection and the associated risk of a board
reset and unintended startup tare. Filtering occurs on the ESP32; the
dashboard also reconstructs an analysis filter for comparison.

## 3. Hardware configuration and acquisition

| Component | Configuration and role |
|---|---|
| ESP32 | Shared I2C: SDA GPIO21, SCL GPIO22, 100 kHz; serial 115200 baud |
| ABP3 | I2C 0x6C; adopted differential range -1 to +1 kPa |
| Pitot probe | Supplies total/static pressure difference; correct plumbing and alignment are required |
| BME280 | I2C 0x76, expected chip ID 0x60; temperature, absolute pressure, humidity |
| MPU-6500-compatible board | I2C 0x68, expected identity 0x70; acceleration and angular rate |
| Bench source | Blower with transparent duct; sequential handheld anemometer reference |

The firmware initiates an ABP3 single-shot conversion by writing 0x8B93
LSB-first to register 0x22, waits 10 ms, and reads six bytes beginning at
0x2E. The temperature and pressure words are interpreted as signed 16-bit
values; the final word is retained as status. Sampling is scheduled at
approximately 100 ms intervals. The MCU timestamp is acquisition-time
telemetry, not a synchronized wall-clock or anemometer timestamp.

The exact sensor ordering code, module supply wiring and anemometer model
should be added from physical labels before formal submission. They are not
inferred from family names or photographs. Sensor response alone does not
independently verify the pressure-port plumbing.

## 4. Conversion equations

### 4.1 Startup zero correction

With both pressure ports at equal pressure, the firmware averages 32 ABP3
samples and rounds the result to a whole count:

`C_zeroed = C_raw - C_tare`

This removes an initial offset; it does not determine pressure sensitivity
or correct subsequent drift. Serial reconnection may reset the ESP32, so
the fan must remain off until tare completes. A fixed 30-second waiting
period is not the firmware's tare definition: the completion message is
the operational indication.

### 4.2 Differential pressure

The adopted mentor-provided endpoints are -25,600 counts at -1,000 Pa and
+25,600 counts at +1,000 Pa. The linear slope is:

`(1000 - (-1000)) / (25600 - (-25600)) = 0.0390625 Pa/count`

After tare:

`delta_P = C_zeroed * 0.0390625`

The 10–90% designation describes transfer-function endpoints; it is not
another multiplier to apply after this calculation. The formula is the
adopted configuration, not an experimentally fitted correction to force
agreement with the handheld anemometer.

### 4.3 Air density

For BME280 temperature `T` in degrees Celsius, relative humidity `RH` in
percent and absolute pressure `P_hPa`:

```text
T_K = T + 273.15
P = 100 * P_hPa
e = (RH/100) * 610.78 * 10^(7.5*T/(T+237.3))
rho = (P-e)/(287.058*T_K) + e/(461.495*T_K)
```

Here `e` is estimated water-vapour partial pressure in Pa and `rho` is in
kg/m³. Atmospheric pressure and Pitot differential pressure are distinct
inputs and must not be interchanged.

### 4.4 Airspeed

```text
V = sqrt(2 * max(delta_P, 0) / rho)
```

The implementation assumes the pressure difference appropriately represents
Pitot dynamic pressure and uses an ideal coefficient of one. Alignment,
static-pressure sampling, nonuniform flow and probe/duct interference remain
experimental concerns. Negative differential pressure is retained in the
log but mapped to zero in the nonnegative speed estimate. Invalid sensor
data instead produces `nan`, not a false zero-speed measurement.

Two unfiltered outputs are retained: `airspeed_raw_mps` uses standard density
1.225 kg/m³; the legacy field `airspeed_calibrated_mps` uses BME280-derived
density. The latter name does **not** indicate independently calibrated
airspeed.

### 4.5 Other sensor conversions

ABP3 temperature is `(signed_temperature_counts + 16485)/387.88` degrees C.
The configured IMU accelerometer range is +/-8 g, giving counts/4096 in g;
the gyroscope range is +/-500 degrees/s, giving counts/65.5 in degrees/s.
Acceleration includes gravity. Neither IMU conversion is an airspeed
measurement.

## 5. Kalman pressure estimator

The estimator is a one-state random-walk pressure model, not an inertial
navigation filter. Its state is pressure `x`; its measurement is zeroed,
converted ABP3 pressure `z`.

```text
P_pred = P_previous + Q_rate * dt
K = P_pred / (P_pred + R)
x = x_previous + K * (z - x_previous)
P = (1-K) * P_pred
V_filtered = sqrt(2 * max(x,0) / rho)
```

The initial state is the first usable measurement and initial variance is R.
Defaults are Q_rate=4 Pa²/s and R=121 Pa². These are provisional demonstration
settings. The selected R is approximately the observed rep2 fan-on pressure
variance, which includes genuine flow fluctuations as well as measurement
noise; it is not an independent noise characterization.

The filter uses elapsed MCU time and resets after invalid airspeed samples
or a gap exceeding one second. Stronger smoothing adds response lag and can
hide real fluctuations. Filtering before the nonlinear square root can
change the mean speed. Reduced standard deviation is therefore reported as
reduced variation, not improved absolute accuracy.

Dashboard Q/R controls affect reconstructed analysis only. Firmware settings
are separately logged and firmware estimates remain separate plot/export
fields. The reference anemometer value never adjusts the estimator.

## 6. Logging, diagnostics and interface

### 6.1 Data record

The logger supports legacy 19-column and updated 27-column records. The
original fields comprise timestamp, source, three environmental readings,
six IMU channels, ABP3 raw/zeroed counts, ABP3 temperature/status, pressure,
two unfiltered speed estimates and an optional reference value. New fields
are density, filtered pressure, filtered speed, airspeed-input validity, IMU
validity, Q, R and the unvalidated status label.

Files are opened in exclusive-create mode to avoid overwriting previous
runs. The schema is inferred from the first data row; a schema change within
a capture is rejected. Firmware comment/error lines appear in the terminal,
but are not stored as CSV rows. Malformed row widths are rejected. A serial
disconnect may require manual logger restart; automatic reconnection is not
claimed. Start a new file after a board reset.

### 6.2 Validity handling

CRC, saturation and bridge-check/supply status faults are masked by 0x0D80.
A missing pressure-update bit also invalidates pressure use. Environmental
inputs are checked for finite values and supported ranges. Failed IMU reads
produce invalid IMU fields independently of pressure validity.

The missed-update bits 15/14 are reported rather than treated as fatal
faults. Thus records with 0xC018/0xC019 cannot be described as proof of
fault-free acquisition timing. Software-valid samples mean only that the
implemented checks passed, not that physical accuracy has been established.

### 6.3 Dashboard

The AERIS dashboard provides:

- Mean speed/pressure and usable-sample cards for a selected interval.
- Separate latest-received-sample cards in monitoring mode.
- Raw, reconstructed Kalman and available firmware Kalman curves.
- Environmental measurements and calculated density.
- IMU axis plots and acceleration-magnitude standard deviation as a basic
  motion proxy, not a calibrated vibration measurement.
- ABP3 status counts, invalid samples, timestamp gaps and inferred tare.
- Constant-reference bias, MAE and RMSE, and analysis CSV export.

Monitoring refreshes every two seconds and marks files stale after five
seconds without modification. Recorded mode is explicitly labelled.
Invalid measurements are not replaced with plausible values. Filters process
the full log before analysis-window selection. The sidebar is opened with
the top-left chevron if collapsed.

## 7. Experimental method

The recommended recording sequence is fan OFF during startup tare, an initial
OFF interval, fan startup followed by settled flow, and a final OFF interval.
The board remains connected throughout. Transition times and reference
readings should be recorded separately. Statistics use elapsed time from
the first CSV sample and exclude transition intervals when evaluating a
nominal steady fan setting.

The handheld reference was measured sequentially: the user removed the
Pitot and placed a vane anemometer at the duct outlet without intentionally
moving the duct. Photographs show different probe locations and different
outlet obstruction during these measurements. The effects of this mismatch,
the curved duct, support geometry, reference rotor coverage and pressure
connections have not been isolated experimentally. None is asserted to be
the proven sole cause of disagreement.

Valid zero-speed samples remain included within the selected interval.
Deleting zero values selectively or including fan-off periods to obtain a
closer overall mean would not be a defensible accuracy comparison.

## 8. Results

### 8.1 October 10 bench recordings

| Recording / interval | Samples | Mean pressure | Unfiltered mean | Approximate handheld reference |
|---|---:|---:|---:|---:|
| off_on_off_rep1, 40–110 s | 700 | 22.00 Pa | 6.41 m/s | 3.8 m/s reported for the run |
| off_on_off_rep2, 50–110 s | 600 | 49.57 Pa | 9.68 m/s | 6.5 m/s reported for the run |

Intervals are analyst-selected middle fan-on windows, not synchronized
anemometer measurements. Full files contain 1,486 samples/148.499 s and
1,477 samples/147.599 s respectively.

For rep2, the approximate mean discrepancy is +3.18 m/s, about +49% relative
to 6.5 m/s. Its mean density is approximately 1.044 kg/m³. At this density,
6.5 m/s would imply roughly 22.1 Pa, whereas the selected interval reports
49.57 Pa. This identifies the disagreement but does not establish which
instrument or experimental condition is responsible.

Rep2 pressure averages approximately +0.37 Pa over 0–35 s and -0.08 Pa over
130–148 s, demonstrating recovery near the starting baseline. This does not
validate pressure sensitivity or establish the accuracy of the fan-on speed.

### 8.2 Filtering effect: rep2, 50–110 s

| Quantity | Unfiltered | Reconstructed Kalman |
|---|---:|---:|
| Mean speed | 9.681 m/s | 9.748 m/s |
| Sample standard deviation | 1.112 m/s | 0.157 m/s |

The signal is less variable, but the reference disagreement remains. The
standard deviation is sample variation, not a calibrated uncertainty or
confidence bound. There are no zero-speed samples in this interval. No R²
is reported for a single constant reference reading.

### 8.3 Updated firmware: hardware integration evidence

`abp3_kalman_demo_rep1.csv` was still growing while this report was prepared.
For a fixed reporting scope, this section uses the **first 12,921 data rows**,
covering 1,291.999 seconds (approximately 21.5 minutes), not its eventual
full-file length.

- The record has the expected 27 columns, including firmware filter output.
- All 12,921 rows pass implemented airspeed-input checks and have IMU validity 1.
- Inferred startup tare is -28 counts throughout this interval.
- Status counts are 12,742 occurrences of 0xC018 and 179 of 0xC019.
- The maximum difference between firmware and independently reconstructed
  Python filtered speed is approximately 0.000079 m/s.

The close numerical agreement supports consistent algorithm implementation,
not independent physical accuracy: both calculations use the same sensor
measurements and model. No reference speed or steady-state accuracy result
is assigned to the entire long recording.

## 9. Software verification

The ESP32 sketch compiled using installed core 3.3.11 for generic target
`esp32:esp32:esp32`: 309,004 bytes program storage and 23,700 bytes global
data. The actual board selection must match the hardware when uploading.

Fourteen automated tests cover constant/negative input, known Kalman updates,
elapsed-time scaling, causality, convergence, invalid inputs, diagnostic
faults, invalid environment data, gap resets, timestamp-reset rejection,
legacy/new schemas, firmware-field preservation and firmware/logger header
agreement. Streamlit component checks covered initial rendering, reference
comparison, window selection and stale-data monitoring. The user reported
successful dashboard operation; no automated visual screenshot audit was
completed.

Hardware-origin filter output provides integration evidence. Controlled
physical fault injection, all disconnect/recovery scenarios and independent
metrology validation have not been completed. A final presentation rehearsal,
saved-file fallback, export check and version freeze remain release checks
unless separately recorded as completed.

## 10. Limitations and future work

1. **Absolute accuracy:** unresolved Pitot/anemometer disagreement; no completed
   independent low-pressure calibration/validation for this installation.
2. **Reference quality:** approximate sequential handheld readings, without a
   synchronized reference trace or documented instrument uncertainty.
3. **Bench geometry:** possible flow nonuniformity, different sensing locations
   and outlet interference; contributions are not quantified.
4. **Diagnostics:** missed-update flags persist and require investigation.
5. **Filter tuning:** provisional Q/R; transition response and noise modelling
   need formal evaluation. Filtering cannot correct systematic bias.
6. **IMU scope:** channels and motion monitoring only. Meaningful airspeed
   fusion requires a justified motion/wind model and independent information;
   a stationary IMU cannot measure the fan's airspeed.
7. **Operational scope:** local demonstration, not a hardened long-duration
   telemetry service or flight-control system.

Next-phase work should verify pressure connections, compare the ABP3 against
a suitable low-range differential-pressure reference, improve the reference
airflow arrangement, and collect repeat/holdout measurements across several
speeds. Only then should accuracy, uncertainty or fitted correction claims
be made. A controlled moving platform with independent motion measurement
would support later inertial-estimation research.

## 11. Conclusion

The project has progressed from individual sensor communication to an
integrated hardware/software prototype with physical-unit conversion,
environmental compensation, on-device filtering, data recording and a
monitoring interface. Recorded evidence supports functioning acquisition and
consistent calculation. The demonstrated outcome is an **experimental
airspeed-estimation and filtering system**, not a validated airspeed
instrument. This distinction is retained throughout the interface, results
and recommended presentation.

## Appendix A. Reproduction and software environment

See [RUN_AIRSPEED_DEMO.md](RUN_AIRSPEED_DEMO.md) for the operating sequence.

```powershell
python -m serial.tools.list_ports
python airspeed_logging/serial_csv_logger.py --port COM6 --output logs/airflow/NEW_UNIQUE_FILENAME.csv
python -m streamlit run airspeed_logging/dashboard.py
python -B -m unittest discover -s airspeed_logging -p "test_*.py"
```

Use separate terminals for logger and dashboard; substitute the actual port.
Observed environment: Windows, Python 3.14.5, NumPy 2.4.6, pandas 3.0.3,
Streamlit 1.58.0, Altair 6.1.0 and pyserial 3.5. These are observed versions,
not a tested clean-machine installation or complete dependency lockfile.

## Appendix B. Evidence and source register

| Source | Use |
|---|---|
| `airspeed_logging/airspeed_logger/airspeed_logger.ino` | Active firmware, equations, acquisition, validity and filter |
| `airspeed_logging/serial_csv_logger.py` | CSV schema and acquisition behaviour |
| `airspeed_logging/kalman_filter.py` | Independent scalar estimator implementation |
| `airspeed_logging/telemetry.py` | Reconstruction and invalid-data handling |
| `airspeed_logging/dashboard.py` | Presentation/analysis interface |
| `airspeed_logging/test_*.py` | Automated functional tests |
| `logs/airflow/abp3_20261010_off_on_off_rep1.csv` | First October 10 airflow test |
| `logs/airflow/abp3_20261010_off_on_off_rep2.csv` | Higher-setting test and filter comparison |
| `logs/airflow/abp3_kalman_demo_rep1.csv` | Updated firmware integration evidence |
| Mentor-provided ABP3 I2C technote, status pp. 4–5, conversion pp. 6–8 | Protocol, flags and conversion basis |
| Mentor-provided ABP3 series datasheet | Sensor-family/configuration reference |

The technote is marked confidential. Do not attach or publish it, or reproduce
its pages, without the owner's permission. This report summarizes the project
implementation rather than reproducing the document. Before external release,
confirm permission for any derived technical details, photographs and data.

Earlier ABP2/mock results and preliminary empirical fit results are not used
as final-system performance evidence. Older repository reports are historical
and may describe superseded software or interpretation.
