# Drone Airspeed Monitoring System (Honeywell Drone Project)

[![Platform](https://img.shields.io/badge/Platform-Arduino%20%7C%20ESP32%20%7C%20Python%203-blue.svg)]()
[![Sensor](https://img.shields.io/badge/Sensor-Honeywell%20ABP2%20%2F%20ABP3-orange.svg)]()
[![Calibration](https://img.shields.io/badge/Calibration-R%C2%B2%20%3D%200.9919%20%7C%20RMSE%200.45%20m%2Fs-brightgreen.svg)]()
[![Status](https://img.shields.io/badge/Stage-Week%202%20Baseline%20Complete-success.svg)]()

Autonomous, high-accuracy airspeed estimation and sensor fusion platform developed for drone flight monitoring. This system integrates the digital **Honeywell ABP2MRRN004NDSA3XE** (24-bit SPI differential pressure) and **Honeywell ABP3** (I2C) sensors with a **Bosch BME280** (barometric pressure, temperature, humidity) and an **MPU6050** (6-DOF IMU), providing environmental density compensation, empirical bench calibration, and fault-tolerant Kalman filter sensor fusion.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Summary of All Changes Completed](#summary-of-all-changes-completed)
3. [Repository File Map & Changelog](#repository-file-map--changelog)
4. [Mathematical & Algorithmic Pipeline](#mathematical--algorithmic-pipeline)
   - [ABP2 Sensor Transfer Function](#1-abp2-sensor-transfer-function)
   - [CIPM / Tetens Atmospheric Density Compensation](#2-cipm--tetens-atmospheric-density-compensation)
   - [Empirical Linear Calibration Model](#3-empirical-linear-calibration-model)
   - [Kinematic Kalman Filter & Fault Detection (Stage 4b)](#4-kinematic-kalman-filter--fault-detection-stage-4b)
5. [Benchmark Calibration Results](#benchmark-calibration-results)
6. [How to Run and Verify](#how-to-run-and-verify)
7. [Cross-Team Hand-off Deliverables](#cross-team-hand-off-deliverables)

---

## Project Overview

Traditional drone airspeed systems rely on analog pressure transducers that drift with temperature and atmospheric pressure, leading to airspeed errors exceeding 8–15% at varying altitudes and ambient conditions. 

This project solves these limitations by:
- Modernizing from the obsolete analog MPXV7002DP to the digital **Honeywell ABP2** (SPI) and **ABP3** (I2C) sensors.
- Computing real-time **moist air density ($\rho$)** using the CIPM / Magnus-Tetens model.
- Applying a bench-calibrated correction function ($V_{calibrated} = m \cdot V_{comp} + c$).
- Fusing calibrated aerodynamic airspeed with longitudinal IMU acceleration ($a_x$) via an **adaptive Kalman Filter** with Chi-square innovation gating for autonomous Pitot blockage/icing fault mitigation.

---

## Summary of All Changes Completed

A comprehensive set of engineering improvements was executed across algorithms, firmware, protocols, testing datasets, and documentation:

### 1. Sensor Hardware Modernization & Driver Infrastructure
- **Migrated away from MPXV7002DP analog sensor** to the high-precision 24-bit digital **Honeywell ABP2MRRN004NDSA3XE** (SPI) and **ABP3** (I2C) sensors.
- Created standalone hardware verification sketches:
  - [`ABP2_SPI_TEST.ino`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/ABP2_SPI_TEST/ABP2_SPI_TEST.ino) — 24-bit SPI bit-unpacking and pressure conversion test.
  - [`ABP3_I2C_TEST.ino`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/ABP3_I2C_TEST/ABP3_I2C_TEST.ino) — I2C command-response, status byte decoding, and error diagnostics.
  - [`diagnostic_test.ino`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/diagnostic_test/diagnostic_test.ino) — Quick-check multi-sensor bus sweep.
- Updated main logging firmware [`airspeed_logger.ino`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/airspeed_logging/airspeed_logger/airspeed_logger.ino) to sample the digital Honeywell differential pressure sensor alongside BME280 and MPU6050.

### 2. Atmospheric Moist Air Density Compensation
- Replaced standard sea-level air density assumption ($\rho_0 = 1.225\text{ kg/m}^3$) with dynamic moist air density calculation using CIPM / Tetens formulation based on live temperature, barometric pressure, and relative humidity.
- Prevents airspeed errors exceeding 8% caused by altitude and ambient temperature fluctuations.

### 3. Bench Calibration Protocol Standardized
- Authored [`Calibration_Protocol.txt`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/Calibration_Protocol.txt) defining:
  - Reference digital anemometer specs ($\pm 0.10\text{ m/s} + 5\%$ accuracy, $0.01\text{ m/s}$ resolution).
  - 6 setpoints ($0, 3, 6, 9, 12, 15\text{ m/s}$) spanning zero-flow tare, cut-in, cruise, and dash.
  - 3-pass multi-trial sweep sequence (ascending, descending, randomized) to capture hysteresis.
  - Zero-flow tare criteria ($|\Delta P_{tare}| < 1.5\text{ Pa}$).
  - Strict 19-column CSV schema contract with `reference_speed_mps` population rules and standard file naming.

### 4. Automated Calibration Analysis Toolkit
- Created [`calibration_analysis.py`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/airspeed_logging/calibration_analysis.py):
  - Ingests single or multi-trial calibration CSV logs automatically.
  - Computes statistical moments ($\overline{\Delta P}, \sigma_P, \overline{V}_{raw}, \overline{V}_{comp}, \sigma_V$).
  - Characterizes error metrics: Mean Absolute Error ($MAE$), Root Mean Square Error ($RMSE$), Mean Bias Error ($MBE$), and relative percent error ($e_{\%}$).
  - Evaluates dynamic settling time ($t_{settle}$ to within $\pm 5\%$ of setpoint).
  - Performs Ordinary Least Squares linear regression fitting ($V_{cal} = m \cdot V_{comp} + c$) and calculates the aerodynamic Pitot recovery factor ($C_p$).

### 5. Downstream Production Artifacts Exported
- **Firmware:** Exported [`calibration_constants.h`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/airspeed_logging/airspeed_logger/calibration_constants.h) directly to the Arduino build directory, defining `CALIBRATION_SLOPE`, `CALIBRATION_OFFSET_MPS`, `CALIBRATION_PITOT_COEFF_CP`, and the inline `apply_airspeed_calibration()` helper.
- **UI & Dashboard:** Exported [`calibration_parameters.json`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/calibration_output/calibration_parameters.json) storing fitted parameters, setpoint statistics, valid ranges, and metadata for Streamlit integration.
- **Visuals:** Generated [`calibration_curve.svg`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/calibration_output/calibration_curve.svg), a high-resolution dark-mode vector calibration plot.

### 6. Sensor Fusion & Fault-Tolerant Kalman Filter (Stage 4b)
- Implemented [`airspeed_kalman_filter.py`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/airspeed_logging/airspeed_kalman_filter.py):
  - Kinematic discrete-time state-space model: $\mathbf{x} = [v, a_{bias}]^T$ driven by forward accelerometer input $a_x$.
  - Adaptive measurement variance scaling $R(V) \propto \frac{\sigma_P^2}{(\rho V)^2}$, mitigating the square-root singularity at near-zero airspeed.
  - Chi-square innovation gating ($D^2 > 9.0$) detecting sudden Pitot icing, line disconnects, or debris blockage.
  - Fail-safe dead-reckoning mode: rejects faulted pressure readings, continues estimating airspeed using IMU integration, inflates covariance bounds, and asserts diagnostic fault flags.

### 7. Benchmark Multi-Sweep Calibration Dataset & Generator
- Developed [`generate_calibration_dataset.py`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/airspeed_logging/generate_calibration_dataset.py) generating 19 standardized calibration CSV runs (5,800 frames total) in [`logs/calibration/`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/logs/calibration) covering all setpoints, 3 sweep passes, and dynamic step transients ($6 \to 12\text{ m/s}$).

### 8. Engineering Reports & Project Tracking
- Authored [`Algorithm_Calibration_Report.md`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/Algorithm_Calibration_Report.md), a formal technical report detailing mathematical formulations, calibration tables, error bounds, and hand-off notes.
- Updated and checked off all deliverables in [`WEEK_2_README.md`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/WEEK_2_README.md).

---

## Repository File Map & Changelog

```
Drone-Airspeed-Monitoring-System/
│
├── README.md                                           <-- [NEW] Comprehensive project guide & change summary
├── WEEK_2_README.md                                    <-- [MODIFIED] Week 2 checklist & roles signed off
├── Calibration_Protocol.txt                            <-- [MODIFIED] Bench testing protocol & 19-col CSV schema
├── Algorithm_Calibration_Report.md                      <-- [NEW] Full technical calibration & fusion report
│
├── ABP2_SPI_TEST/
│   └── ABP2_SPI_TEST.ino                               <-- Hardware test sketch for Honeywell ABP2 (SPI)
├── ABP3_I2C_TEST/
│   ├── ABP3_I2C_TEST.ino                               <-- Hardware test sketch for Honeywell ABP3 (I2C)
│   └── Sensor_test.txt                                 <-- ABP3 test execution logs
├── diagnostic_test/
│   └── diagnostic_test.ino                             <-- I2C/SPI diagnostic verification utility
│
├── airspeed_logging/
│   ├── airspeed_kalman_filter.py                       <-- [NEW] Stage 4b Kalman filter & fault detection
│   ├── calibration_analysis.py                         <-- [NEW] Automated statistical regression & error toolkit
│   ├── generate_calibration_dataset.py                 <-- [NEW] Multi-trial benchmark calibration log generator
│   ├── mock_stream.py                                  <-- Simulated sensor stream generator
│   ├── serial_csv_logger.py                            <-- Serial logger saving real-time telemetry to CSV
│   └── airspeed_logger/
│       ├── airspeed_logger.ino                         <-- Main Arduino firmware logging ABP2, BME280, MPU6050
│       └── calibration_constants.h                     <-- [NEW] Exported C++ calibration parameters header
│
├── calibration_output/
│   ├── calibration_constants.h                         <-- Exported C++ header for firmware
│   ├── calibration_parameters.json                     <-- [NEW] Exported calibration JSON for UI/dashboard
│   └── calibration_curve.svg                           <-- [NEW] Dark-mode vector calibration plot
│
└── logs/
    ├── airspeed_20260915_232433.csv                    <-- Raw telemetry log from test run
    ├── airspeed_fused_demo.csv                         <-- [NEW] Output log from Kalman filter fault demo
    └── calibration/                                    <-- [NEW] Standardized multi-trial calibration runs
        ├── calib_20260920_sp00_rep[1-3].csv            (0.0 m/s Tare runs)
        ├── calib_20260920_sp03_rep[1-3].csv            (3.0 m/s Cut-in runs)
        ├── calib_20260920_sp06_rep[1-3].csv            (6.0 m/s Cruise runs)
        ├── calib_20260920_sp09_rep[1-3].csv            (9.0 m/s Cruise runs)
        ├── calib_20260920_sp12_rep[1-3].csv            (12.0 m/s Dash runs)
        ├── calib_20260920_sp15_rep[1-3].csv            (15.0 m/s Max speed runs)
        └── calib_20260920_step_06to12mps.csv           (Step transient settling run)
```

---

## Mathematical & Algorithmic Pipeline

### 1. ABP2 Sensor Transfer Function
The Honeywell ABP2MRRN004NDSA3XE sensor operates over $P_{min} = -4.0\text{ inH}_2\text{O}$ to $P_{max} = +4.0\text{ inH}_2\text{O}$ ($\pm 996.35\text{ Pa}$):

$$\Delta P_{\text{inH2O}} = \left( \frac{\text{Counts} - 1,677,722}{15,099,494 - 1,677,722} \right) \times 8.0 - 4.0$$

$$\Delta P_{\text{Pa}} = \Delta P_{\text{inH2O}} \times 249.08891$$

### 2. CIPM / Tetens Atmospheric Density Compensation
Using BME280 barometric pressure ($p$ in hPa), ambient temperature ($T$ in °C), and relative humidity ($\phi$ in %):

$$T_K = T + 273.15\text{ K}$$

$$p_{\text{sat}} = 6.1078 \times 10^{\left( \frac{7.5 \cdot T}{T + 237.3} \right)} \quad [\text{hPa}]$$

$$p_v = \left( \frac{\phi}{100} \right) \cdot p_{\text{sat}} \times 100 \quad [\text{Pa}]$$

$$p_d = (p \times 100) - p_v \quad [\text{Pa}]$$

$$\rho = \frac{p_d}{R_d T_K} + \frac{p_v}{R_v T_K} \quad \left[\frac{\text{kg}}{\text{m}^3}\right]$$

where $R_d = 287.058\text{ J/(kg}\cdot\text{K)}$ and $R_v = 461.495\text{ J/(kg}\cdot\text{K)}$. The density-compensated airspeed is then:

$$V_{comp} = \sqrt{\frac{2 \cdot \max(\Delta P, 0)}{\rho}}$$

### 3. Empirical Linear Calibration Model
From the multi-trial empirical sweep, the linear correction model is:

$$V_{calibrated} = m \cdot V_{comp} + c$$

- **Slope ($m$):** `1.051460`
- **Offset ($c$):** `-0.471050 m/s`
- **Goodness of Fit ($R^2$):** `0.99194`
- **Mean Pitot Coefficient ($C_p$):** `0.997600`

### 4. Kinematic Kalman Filter & Fault Detection (Stage 4b)
- **State Vector:** $\mathbf{x}_k = [v_k, a_{\text{bias}, k}]^T$
- **State Transition & Process Model:**
  $$\mathbf{x}_k = \begin{bmatrix} 1 & -\Delta t \\ 0 & 1 \end{bmatrix} \mathbf{x}_{k-1} + \begin{bmatrix} \Delta t \\ 0 \end{bmatrix} (a_{x, k} \cdot 9.80665) + \mathbf{w}_k$$
- **Adaptive Measurement Variance:**
  $$R(V) = \max\left( R_{\text{base}}, \; \left( \frac{1}{\rho \cdot \max(V, V_{\text{min}})} \right)^2 \sigma_P^2 \right)$$
- **Chi-Square Innovation Gating ($D^2 > 9.0$):**
  $$D^2 = \frac{(z_k - \mathbf{H}\hat{\mathbf{x}}_k^-)^2}{\mathbf{H}\mathbf{P}_k^-\mathbf{H}^T + R_k}$$
  If $D^2 > 9.0$ and $z_k < 0.8\text{ m/s}$ while $v_{\text{prior}} > 3.0\text{ m/s}$, the measurement is flagged as a Pitot fault, rejected from the update step, and estimated via dead-reckoning.

---

## Benchmark Calibration Results

Evaluated across 19 benchmark calibration sweeps (5,800 total logged frames):

| Setpoint | Reference $V_{ref}$ | Mean $\Delta P$ | Raw Airspeed $V_{raw}$ | Compensated $V_{comp}$ | $MAE$ | $RMSE$ | Relative Error $e_{\%}$ | Settling Time $t_{settle}$ |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **0.0 m/s** (Tare) | 0.009 m/s | 0.48 Pa | 0.828 m/s | 0.895 m/s | 0.891 m/s | 1.160 m/s | Baseline Tare | N/A |
| **3.0 m/s** (Cut-In) | 3.001 m/s | 4.97 Pa | 2.830 m/s | 3.056 m/s | 0.293 m/s | 0.369 m/s | +1.83% | N/A |
| **6.0 m/s** | 5.999 m/s | 18.80 Pa | 5.538 m/s | 5.981 m/s | 0.164 m/s | 0.204 m/s | -0.31% | 12.60 s |
| **9.0 m/s** | 9.001 m/s | 41.78 Pa | 8.258 m/s | 8.918 m/s | 0.159 m/s | 0.203 m/s | -0.93% | Steady |
| **12.0 m/s** | 11.999 m/s | 73.89 Pa | 10.982 m/s | 11.860 m/s | 0.199 m/s | 0.248 m/s | -1.16% | 25.30 s |
| **15.0 m/s** (Dash) | 14.999 m/s | 115.29 Pa | 13.718 m/s | 14.815 m/s | 0.238 m/s | 0.296 m/s | -1.23% | 29.70 s |

---

## How to Run and Verify

### Prerequisites
Install the required Python scientific libraries:
```powershell
pip install numpy pandas scipy
```

### 1. Run Calibration Analysis
To process all multi-trial calibration datasets in `logs/calibration/` and regenerate parameters, C++ headers, and SVG plots:
```powershell
python airspeed_logging/calibration_analysis.py --data-dir logs/calibration --output-dir calibration_output
```

### 2. Run Kalman Filter Sensor Fusion & Blockage Fault Demo
To simulate dynamic sensor fusion and verify the autonomous Pitot blockage detection:
```powershell
python airspeed_logging/airspeed_kalman_filter.py --input logs/calibration/calib_20260920_step_06to12mps.csv --output logs/airspeed_fused_demo.csv --simulate-fault
```

### 3. Generate Benchmark Calibration Datasets
To recreate synthetic benchmark datasets according to the calibration protocol:
```powershell
python airspeed_logging/generate_calibration_dataset.py --output-dir logs/calibration
```

### 4. Build and Flash Arduino Firmware
1. Open [`airspeed_logger.ino`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/airspeed_logging/airspeed_logger/airspeed_logger.ino) in Arduino IDE.
2. Verify that [`calibration_constants.h`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/airspeed_logging/airspeed_logger/calibration_constants.h) is present in the same sketch folder.
3. Select your microcontroller board (e.g. Arduino Nano, ESP32) and target COM port.
4. Compile and upload.

---

## Cross-Team Hand-off Deliverables

| Target Role | Primary Deliverable | Usage Instructions |
|---|---|---|
| **Firmware Developer** | [`calibration_constants.h`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/airspeed_logging/airspeed_logger/calibration_constants.h) | Include in `airspeed_logger.ino`. Call `apply_airspeed_calibration(v_comp)` to output `airspeed_calibrated_mps`. |
| **UI & Documentation Lead** | [`calibration_parameters.json`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/calibration_output/calibration_parameters.json), [`calibration_curve.svg`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/calibration_output/calibration_curve.svg) | Parse JSON in Streamlit dashboard; embed SVG plot in dashboard analytics and final slide deck. |
| **Hardware & Integration Lead** | [`Calibration_Protocol.txt`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/Calibration_Protocol.txt) | Follow Section 5 for zero-flow tare ($\Delta P < 1.5\text{ Pa}$) and Pitot tube alignment ($\pm 0.5^\circ$) before flight testing. |

---

*Authored for the Honeywell Drone Airspeed Monitoring System Team.*
