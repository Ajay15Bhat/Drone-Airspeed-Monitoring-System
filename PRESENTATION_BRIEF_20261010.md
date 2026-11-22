# Presentation outline and evidence checklist

Use PROJECT_REPORT_20261010.md as the current technical report. This file is
a slide/storyboard guide, not a claim that a finished PPT has been produced.

## Suggested 9-slide structure

| Slide | Content | Evidence / visual |
|---|---|---|
| 1 | Problem, objective, experimental scope | Project title and one clear hardware photo |
| 2 | System architecture | Recreate the report's sensor-to-CSV pipeline |
| 3 | Integrated hardware | Annotated ESP32/ABP3/BME280/IMU/Pitot photo; no unverified wiring labels |
| 4 | Physical-unit calculations | Tare, 0.0390625 Pa/count, density, Bernoulli |
| 5 | Kalman implementation | State=pressure, Q/R, raw/filter chart; explain lag |
| 6 | Software and live demonstration | Dashboard overview and sensor tabs |
| 7 | Measured results | Rep2 50–110 s: 9.68 raw, 9.75 filtered, reference approx. 6.5 m/s |
| 8 | Verification and limitations | 14 tests, hardware log parity, unresolved discrepancy and flags |
| 9 | Conclusion and next phase | Integrated prototype completed; accuracy/fusion/flight remain future work |

## Screenshots to capture

1. Full rig and a separate clear sensor/wiring photograph.
2. Terminal startup tare/schema message (fan OFF at startup).
3. Dashboard with a genuine growing recording and MONITORING CSV label.
4. Full OFF–ON–OFF pressure/speed chart to show transitions and filter lag.
5. Rep2 50–110 s raw/filtered curves and reference comparison at 6.5 m/s.
6. Environment tab showing temperature, pressure, humidity and density.
7. IMU tab during gentle board motion; identify this as motion response only.
8. Diagnostics tab including missed-update counts, not only the valid count.
9. CSV header/data showing 27 columns and firmware filter values.
10. Passing test summary; optional compiler size summary.

Keep filenames and selected intervals visible wherever practical. Do not use
an old mock plot, remove warnings, label a saved recording live, or describe
the whole-run mean as the fan-on accuracy result. Crop unrelated browser tabs
and personal information from presentation screenshots.

## Short opening script

"Our project is an ESP32-based experimental airspeed monitor. We integrated
a differential-pressure sensor with a Pitot probe, an environmental sensor
for air-density compensation, and an IMU for motion monitoring. The system
records raw and filtered estimates and displays them in a dashboard. The
implementation is working, while independent accuracy validation remains
incomplete."

## Explain the result without overstating it

"In the selected test interval, our unfiltered estimate averaged 9.68 m/s
against an approximately 6.5 m/s sequential handheld reading. Kalman
filtering reduced speed variation from 1.11 to 0.16 m/s standard deviation,
but did not remove that disagreement. We therefore claim signal smoothing
and integrated operation, not validated accuracy."

## Likely questions

**Why isn't the IMU fused?** It measures device motion, not stationary fan
airflow. Fusion requires a defensible motion/wind model and additional
reference information; reading all sensors is not itself fusion.

**Does the filter improve accuracy?** It reduces variation under the chosen
model, with lag. It does not establish or correct absolute accuracy.

**Why is the reference different?** The current measurements do not isolate
the cause. Pressure reference checks and comparable airflow sampling are
needed; the support/duct geometry is a possible contributor, not a proven
explanation for the entire error.

**What is complete?** Acquisition, adopted transfer calculation, density
compensation, on-device filtering, CSV capture, monitoring and analysis.

**What should happen next?** Check pressure against a suitable reference,
improve reference placement, investigate status flags, repeat across speeds,
then quantify accuracy on separate validation runs.

## Before submission or publication

- Add confirmed names, institution, mentor, exact part/model identifiers.
- Complete and record the final rehearsal, offline replay and export checks.
- Stop the capture normally before archiving a final log; the report uses a
  defined prefix of the still-growing demo recording.
- Freeze the intended source/log version in Git; no commit or push was done
  as part of preparing these documents.
- Verify permissions before sharing the confidential mentor technote or any
  derived restricted details. Exclude unrelated files, personal screenshots
  and old mock results from the publication package.
- Export to the institution's required report/PPT/PDF format after review.
  No external publication has been performed.
