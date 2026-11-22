# AERIS — Drone Airspeed Monitoring Prototype

**ESP32 · Honeywell ABP3 · BME280 · MPU-6500-compatible IMU · Python · Streamlit**

An experimental airspeed-monitoring system with live sensor acquisition,
pressure conversion, environmental density compensation, on-device Kalman
filtering, CSV logging and a telemetry dashboard.

> **Status — 10 October 2026:** Integrated bench prototype. Absolute airspeed
> accuracy remains **unvalidated**. Kalman filtering smooths differential
> pressure; it is **not IMU–airspeed fusion** or an accuracy correction.
> This system is not validated for flight control.

## Start here

- [Run the hardware and dashboard demo](RUN_AIRSPEED_DEMO.md)
- [Detailed implementation and test report](PROJECT_REPORT_20261010.md)
- [Presentation outline, screenshots and questions](PRESENTATION_BRIEF_20261010.md)

## What is implemented

- Shared-I2C acquisition of ABP3 pressure, BME280 environmental data and IMU channels.
- Startup pressure tare using 32 equal-pressure samples.
- Signed counts-to-pascals conversion using the adopted ABP3 transfer function.
- Standard-density and BME280-density-compensated Bernoulli airspeed.
- Scalar pressure Kalman filtering on the ESP32, with independent Python reconstruction.
- Serial CSV capture supporting both legacy 19-column and new 27-column logs.
- A dark telemetry dashboard with airspeed/pressure, environment, IMU motion,
  diagnostics, reference comparison and export panels.
- Monitoring of a growing CSV every two seconds, with a stale-data warning
  after five seconds without a file update.
- Invalid-reading handling and visible ABP3 diagnostic flags.

The dashboard reads the logger's file; it does not open the serial port.
Recorded data and live-file monitoring are explicitly distinguished.

## System architecture

```text
Pitot --> ABP3 --> signed counts --> startup tare --> differential pressure
                                                        |          |
                                                        |     Kalman filter
BME280 --> temperature / pressure / humidity --> density |          |
                                                   |    |          |
                                                   +--> Bernoulli conversion
                                                        |          |
                                                 unfiltered     filtered
                                                   airspeed      airspeed

IMU --> acceleration and angular rate -------------------------+
Pressure / environment / airspeed / sensor status --------------+
                                                              |
                                                   ESP32 serial output
                                                              |
                                                       Python CSV logger
                                                              |
                                                     Streamlit dashboard
```

IMU readings support motion monitoring only. They are not inputs to the
current airspeed estimator.

## Hardware configuration

| Component | Active configuration |
|---|---|
| Controller | ESP32; serial 115200 baud; approximately 10 samples/s |
| I2C bus | SDA GPIO21, SCL GPIO22, 100 kHz |
| Differential pressure | Honeywell ABP3 at `0x6C`; adopted range ±1 kPa |
| Environment | BME280 at `0x76`; expected chip ID `0x60` |
| IMU | MPU-6500-compatible board at `0x68`; expected identity `0x70` |
| IMU ranges | ±8 g acceleration; ±500°/s angular rate |
| Bench airflow | Blower, duct and Pitot probe; handheld anemometer reference |

Confirm module power requirements, exact part numbers and pressure-port
connections against your hardware documentation before wiring. This table
is not a complete electrical wiring specification.

## Quick start

Run commands from the repository root. The development environment uses
Windows/PowerShell; replace the serial port and output filename as needed.

### 1. Install Python dependencies

```powershell
python -m pip install -r requirements.txt
```

Observed working versions include Python 3.14.5, NumPy 2.4.6, pandas 3.0.3,
Streamlit 1.58.0, Altair 6.1.0 and pyserial 3.5. A clean-machine installation
has not been independently verified; `requirements.txt` also includes
dependencies used by historical analysis utilities.

### 2. Explore an existing recording

```powershell
python -m streamlit run airspeed_logging/dashboard.py
```

Open the local URL printed in the terminal. Expand the **top-left sidebar
chevron** to access **Session controls**, then select a recording or upload
a CSV. Uncheck **Use full recording** to choose an analysis interval.

For the documented October 10 rep2 comparison, select
`abp3_20261010_off_on_off_rep2.csv`, use **50–110 seconds**, and enable
**Show reference comparison** with an approximate reference of **6.5 m/s**.

### 3. Upload firmware

Open [airspeed_logger.ino](airspeed_logging/airspeed_logger/airspeed_logger.ino)
in Arduino IDE. Install the appropriate ESP32 board support and the
**Adafruit BME280 Library** with its required dependencies. Select your actual
board and port, verify, then upload.

**Keep the fan OFF and both pressure ports at equal pressure during startup
tare.** Closing/opening serial can reset the board and repeat tare. Do not
reconnect with airflow present. The current sketch does not require the
historical empirical `calibration_constants.h` correction.

### 4. Record telemetry

Close Arduino Serial Monitor, identify the port, then start the logger:

```powershell
python -m serial.tools.list_ports
python airspeed_logging/serial_csv_logger.py --port COM6 --output logs/airflow/abp3_demo_new_run.csv
```

Replace `COM6` with the actual port and choose a **new filename for each
recording**. Existing files are not overwritten. Read the printed tare
completion message before turning on the fan.

In a second terminal, run the dashboard command above. Refresh/rerun the
dashboard if necessary to update the file list, select the new recording,
and tick **Monitor growing CSV (refresh every 2 s)**. Keep the logger running.
Use Ctrl+C in its terminal when capture is complete.

A useful demonstration records OFF, startup/settled ON, and OFF again in
one continuous file. Note transition times and reference readings. Compare
steady fan-on intervals, not a whole-recording mean containing fan-off data.

## Calculation and filtering

The adopted conversion uses −25,600 counts at −1,000 Pa and +25,600 counts
at +1,000 Pa:

```text
zeroed_counts = raw_counts - startup_tare_counts
delta_P_Pa = zeroed_counts * 0.0390625
airspeed_mps = sqrt(2 * max(delta_P_Pa, 0) / density_kg_m3)
```

Density is calculated from BME280 temperature, absolute pressure and relative
humidity using an ideal moist-air mixture and a saturation-vapour-pressure
approximation. Full equations are in the [technical report](PROJECT_REPORT_20261010.md).

The Kalman estimator has one state: differential pressure. It uses actual
elapsed time, provisional **Q = 4 Pa²/s** and **R = 121 Pa²**, and resets after
invalid airspeed inputs or a gap over one second. These are demonstration
parameters, not independently calibrated noise values. Stronger smoothing
adds lag and can suppress genuine fluctuations.

Sidebar Q/R controls change the **Python analysis filter only**, not firmware
settings. Raw data, firmware-filtered values and analysis results remain
separate. A reference value does not tune the estimator.

## Data fields and health indicators

| Field/group | Meaning |
|---|---|
| `timestamp_ms`, `source` | MCU timestamp and hardware-origin source label |
| `temp_C`, `pressure_hPa`, `humidity_pct` | BME280 environment measurements |
| `accel_*_g`, `gyro_*_dps` | IMU axes; acceleration includes gravity |
| `abp3_pressure_raw_counts`, `abp3_pressure_zeroed_counts` | Pressure counts before/after startup tare |
| `abp3_temperature_C`, `abp3_status` | ABP3 temperature and diagnostic word |
| `diff_pressure_Pa` | Converted differential pressure |
| `airspeed_raw_mps` | Unfiltered speed using fixed density 1.225 kg/m³ |
| `airspeed_calibrated_mps` | Legacy name: density-compensated speed, **not independently calibrated** |
| `reference_speed_mps` | Optional reference; normally blank in firmware logs |
| `density_kg_m3` | Firmware-computed moist-air density |
| `kalman_pressure_Pa`, `kalman_speed_mps` | Firmware-filtered pressure and derived speed |
| `sample_valid`, `imu_valid` | Implemented airspeed-input and IMU validity checks |
| `kalman_q_Pa2_per_s`, `kalman_r_Pa2`, `validation_state` | Filter settings and unvalidated status |

Updated records have 27 columns. The dashboard adds derived/`analysis_*`
fields without replacing firmware output.

Failed reads and relevant diagnostic faults produce invalid derived outputs
(`nan`), not artificial zero speeds. Valid nonpositive pressure is retained
and maps to zero speed. CRC, saturation, bridge faults and missing pressure
updates invalidate pressure use. Missed-update flags remain visible warnings;
`0xC018`/`0xC019` are **not proof of fault-free acquisition timing**.

## Results and verification

### Bench comparison: 10 October 2026, rep2

Selected interval: **50–110 seconds**, 600 samples. Handheld reference:
**approximately 6.5 m/s**, measured sequentially rather than synchronously.

| Quantity | Unfiltered | Python Kalman |
|---|---:|---:|
| Mean airspeed | 9.68 m/s | 9.75 m/s |
| Sample standard deviation | 1.11 m/s | 0.16 m/s |

Mean pressure was approximately **49.57 Pa**. The unfiltered mean exceeds
the approximate reference by **3.18 m/s (49%)**. Filtering reduces variation
but does not resolve the accuracy discrepancy. Sample standard deviation is
not an accuracy bound, and R² is not reported for a single constant reference.

### Integration and software checks

- ESP32 firmware compiled successfully for generic `esp32:esp32:esp32` using
  core 3.3.11: 309,004 bytes program storage and 23,700 bytes global data.
- The first **12,921 samples / approximately 21.5 minutes** of
  `abp3_kalman_demo_rep1.csv` demonstrate the updated 27-column hardware output.
  All passed implemented airspeed-input/IMU checks; missed-update flags persist.
- Firmware and independently reconstructed Python filtered speed agree within
  approximately **0.00008 m/s** over that interval. This verifies numerical
  consistency, not independent physical accuracy.
- **14 automated tests** cover filtering, invalid inputs, gaps/resets, schema
  compatibility and firmware/logger header agreement.
- Dashboard component checks cover loading, interval selection, reference
  comparison and stale-data monitoring; the user reported successful operation.

Run tests:

```powershell
python -B -m unittest discover -s airspeed_logging -p "test_*.py"
```

## Repository guide

| Path | Purpose |
|---|---|
| [Firmware](airspeed_logging/airspeed_logger/airspeed_logger.ino) | Active ESP32 acquisition, conversions, diagnostics and filter |
| [Serial logger](airspeed_logging/serial_csv_logger.py) | Hardware CSV capture |
| [Dashboard](airspeed_logging/dashboard.py) | AERIS telemetry interface |
| [Telemetry analysis](airspeed_logging/telemetry.py) | Reconstruction, validity checks and analysis fields |
| [Pressure filter](airspeed_logging/kalman_filter.py) | Independent scalar Kalman implementation |
| [Filter tests](airspeed_logging/test_kalman_filter.py) / [telemetry tests](airspeed_logging/test_telemetry.py) | Automated verification |
| [Airflow recordings](logs/airflow/) | Bench measurements and historical manifests |
| [Run guide](RUN_AIRSPEED_DEMO.md) | Operating sequence and presentation checks |
| [Project report](PROJECT_REPORT_20261010.md) | Equations, evidence, limitations and future work |
| [Presentation brief](PRESENTATION_BRIEF_20261010.md) | Slide outline and screenshot checklist |

## Limitations and next steps

1. Resolve the pressure/airspeed reference discrepancy with a suitable
   low-range pressure reference and comparable airflow sampling.
2. Investigate ABP3 missed-update flags and characterize timing behaviour.
3. Quantify repeatability, filter lag and uncertainty using multiple speeds
   and separate validation runs.
4. Complete controlled error/recovery testing and freeze the demonstrated
   source/data version before presentation.
5. Treat genuine IMU–airspeed fusion as future work requiring a justified
   motion/wind model and additional reference information.

The curved duct, probe/support geometry and sequential anemometer placement
are possible contributors to disagreement, not proven explanations for all
of it. Neither density compensation nor filtering establishes accuracy by
itself. No autonomous blockage/icing detection or flight-safe fallback is
claimed for this active prototype.

## Historical artifacts and publication notes

This repository also contains earlier ABP2 experiments, synthetic datasets,
preliminary calibration outputs and prototype fusion scripts. They are **not
the active ABP3 pipeline**. Earlier README claims such as R² ≈ 0.9919, a
validated empirical correction, high-accuracy flight operation and completed
IMU fusion must not be presented as measured performance of this system.
Use the dated report linked above for current claims and evidence.

Mentor-provided technical material may be confidential. Before making the
repository or report public, review document/data permissions and exclude
restricted PDFs, personal information and unrelated artifacts. This README
update does not authorize publication of those materials.
