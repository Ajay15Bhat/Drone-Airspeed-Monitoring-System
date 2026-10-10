# AERIS airspeed prototype: run and demonstrate

Accuracy remains unvalidated. This is not flight-control software. Kalman
smoothing is not an accuracy correction or IMU fusion.

## 1. Preview the redesigned dashboard with existing logs

From the project root, run:

```powershell
python -m streamlit run airspeed_logging/dashboard.py
```

Restart an existing Streamlit process to pick up the new dark theme. Choose
rep2 in the sidebar, uncheck **Use full recording**, select 50–110 seconds,
then enable **Show reference comparison** and enter 6.5 m/s.

Dashboard tabs cover speed/pressure, environment, IMU motion, diagnostics,
and data export. The defaults reproduce roughly 9.68 m/s unfiltered and
9.75 m/s filtered in this interval. Filtering reduces variation but does not
remove the reference discrepancy. Never compare the fan-on reference with
a whole-recording mean containing fan-off sections.

## 2. Upload the updated firmware manually

Close the serial logger and Arduino Serial Monitor. Keep the fan OFF and
the pressure ports at equal pressure. Open:

`airspeed_logging/airspeed_logger/airspeed_logger.ino`

Select your actual ESP32 board and port in Arduino IDE, verify, then upload.
The code now calculates a pressure Kalman estimate on the ESP32 at each
sample. Both original and filtered outputs are logged. Opening serial can
reset the board and repeat the 32-sample startup tare: always keep fan OFF
until the tare message is printed.

The build check uses generic `esp32:esp32:esp32`; your actual board selection
must still match your hardware. No automated upload is performed.

## 3. Record and monitor live data

Find the actual port:

```powershell
python -m serial.tools.list_ports
```

In terminal 1 (replace COM6 if necessary, and choose a new output filename):

```powershell
python airspeed_logging/serial_csv_logger.py --port COM6 --output logs/airflow/abp3_kalman_demo_rep1.csv
```

Keep the fan OFF while tare completes. In terminal 2, start the dashboard.
If already open, rerun it to refresh the recording list; select the new log
and enable **Monitor growing CSV**. The dashboard refreshes every 2 seconds
and never opens the serial port itself. A file with no update for 5 seconds
is labelled stale. Latest-sample cards are distinct from interval means.

Record OFF for 20 seconds, ON through startup and 30–60 seconds of settled
flow, then OFF for 20 seconds. Note transition times and any reference
reading. Do not reconnect serial while the fan is ON. Stop with Ctrl+C.

## Data compatibility and sensor health

- Logger accepts legacy 19-column and new 27-column firmware rows. It
  determines schema from the first data row and refuses a mid-file schema
  change. Existing log files are not overwritten.
- Original column names remain for compatibility. `airspeed_raw_mps` uses
  fixed density 1.225 kg/m³; `airspeed_calibrated_mps` is the legacy name for
  density-compensated, unvalidated airspeed.
- New fields: density, Kalman pressure/speed, `sample_valid`, `imu_valid`,
  Q/R, and `validation_state`. `sample_valid` means pressure plus density
  inputs usable; IMU health is independent.
- Failed pressure reads, diagnostic faults (CRC, saturation, bridge
  check/supply), missing pressure-update flags, or invalid environment data
  invalidate the appropriate derived outputs. Invalid outputs are `nan`,
  not misleading zero speeds. Failed IMU reads become `nan` IMU channels.
- Missed-update flags remain visible warnings, not fatal faults. Tare
  rejects diagnostic faults or missing pressure updates.
- Filter resets after invalid airspeed samples or a gap over 1 second.
  Q=4 Pa²/s and R=121 Pa² are provisional settings, not noise calibration.
- Dashboard `analysis_*` fields are reconstructed in Python and do not
  overwrite firmware fields. Sidebar Q/R affects analysis only. Firmware
  settings can differ, so a separate firmware curve is shown when present.
- Dashboard rejects timestamp resets within one file; start a new capture
  after a reset. It does not silently stitch separate startup tares together.

## Presentation checklist

1. Show the full OFF–ON–OFF recording and startup tare.
2. Show raw versus filtered curves and discuss smoothing versus lag.
3. Show temperature, pressure, humidity and calculated density.
4. Show IMU axes; explain that acceleration includes gravity and the motion
   proxy is not a calibrated vibration or airflow measurement.
5. Show reference discrepancy and diagnostic flags without hiding them.
6. Export the selected interval as reproducible evidence.

Before presenting live, complete one real hardware run with the new firmware
and check the 27-column CSV. Check a stopped logger produces a stale warning.
Hardware disconnect/recovery, actual upload, and sensor fault behaviour must
still be verified on the bench. Do not disconnect wiring while powered just
to create a fault; perform any hardware test with appropriate power isolation.

## Software tests

```powershell
python -m unittest discover -s airspeed_logging -p "test_*.py"
```

Unit tests cover filtering, invalid samples, timestamp gaps/resets, legacy
and v2 data, and preservation of firmware values. Streamlit component checks
cover initial load, reference comparison, interval selection and stale-data
monitoring. Browser appearance still needs a human visual check.

The updated sketch compiled successfully with the installed ESP32 3.3.11
core for `esp32:esp32:esp32`: 309,004 bytes program storage, 23,700 bytes
global data. Compilation is not a hardware execution or accuracy test.
