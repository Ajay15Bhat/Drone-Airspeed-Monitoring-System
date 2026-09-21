# Algorithm & Calibration Lead — Week 2 Technical Report & Hand-off

**Author:** Algorithm & Calibration Lead  
**Project:** Drone Airspeed Monitoring System (Honeywell Drone Project)  
**Timeline Phase:** Week 2 — Core Build Baseline  
**Document Status:** Complete & Approved for Handoff  

---

## 1. Executive Summary

As the **Algorithm & Calibration Lead**, all Week 2 deliverables assigned in [`WEEK_2_README.md`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/WEEK_2_README.md) and [`Drone_Airspeed_Timeline_Architecture.pdf`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone_Airspeed_Timeline_Architecture.pdf) have been finalized, implemented, and empirically validated across simulated and benchmark datasets:

1. **Bench Calibration Protocol Finalized**: Complete protocol document [`Calibration_Protocol.txt`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/Calibration_Protocol.txt) defining reference anemometer requirements, spatial geometry, 6 setpoints (0.0 to 15.0 m/s), 3-pass repetition scheme (ascending, descending, randomized), zero-flow tare procedure, and settling time criteria.
2. **Environmental Density Compensation Implemented**: Validated CIPM / Magnus-Tetens moist air density formulation correcting dynamic pressure measurements for ambient temperature, barometric pressure, and relative humidity.
3. **Automated Calibration Toolkit & Models Developed**: Created [`calibration_analysis.py`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/airspeed_logging/calibration_analysis.py), computing statistical moments, noise quantification, error metrics ($MAE$, $RMSE$, $MBE$, $e_{\%}$), dynamic settling time ($t_{settle}$), linear regression ($R^2 = 0.9919$, $RMSE = 0.45\text{ m/s}$), and Pitot recovery factor ($C_p = 0.9976$).
4. **Artifacts Exported for Downstream Leads**:
   - [`calibration_constants.h`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/airspeed_logging/airspeed_logger/calibration_constants.h) exported directly to firmware for the **Firmware Developer**.
   - [`calibration_parameters.json`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/calibration_output/calibration_parameters.json) exported for the **UI & Documentation Lead**.
   - [`calibration_curve.svg`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/calibration_output/calibration_curve.svg) visual vector chart for project reports and dashboard.
5. **Sensor Fusion Architecture Designed & Simulated (Stage 4b)**: Implemented [`airspeed_kalman_filter.py`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/airspeed_logging/airspeed_kalman_filter.py) fusing Pitot dynamic pressure with longitudinal IMU acceleration ($a_x$), including adaptive measurement noise scaling $R(v)$ and Chi-square innovation gating for autonomous Pitot blockage/icing fault detection and fail-safe IMU dead-reckoning.

---

## 2. Sensor Pipeline & Unit Conversion Baseline

The project hardware has transitioned from the analog MPXV7002DP to the high-resolution **Honeywell ABP2MRRN004NDSA3XE** digital differential pressure sensor.

### 2.1 Honeywell ABP2 Transfer Function
- **Range:** $P_{min} = -4.0\text{ inH}_2\text{O}$ to $P_{max} = +4.0\text{ inH}_2\text{O}$ (Span = $8.0\text{ inH}_2\text{O} \approx \pm 996.35\text{ Pa}$)
- **Resolution:** 24-bit digital SPI output
- **Digital Counts:** 10% of $2^{24}$ (1,677,722 counts) at $P_{min}$ to 90% of $2^{24}$ (15,099,494 counts) at $P_{max}$
- **Digital Count to inH2O Conversion:**
  $$\Delta P_{\text{inH2O}} = \left( \frac{\text{Counts} - 1,677,722}{15,099,494 - 1,677,722} \right) \times 8.0 - 4.0$$
- **Inches of Water to Pascals Conversion:**
  $$\Delta P_{\text{Pa}} = \Delta P_{\text{inH2O}} \times 249.08891$$

---

## 3. Atmospheric Density Compensation Derivation

Standard Pitot-static calculations assume standard sea-level air density ($\rho_0 = 1.225\text{ kg/m}^3$). Under actual operating conditions (e.g. ambient temperature $29^\circ\text{C}$, altitude/weather pressure $918\text{ hPa}$, humidity $60\%$), actual air density drops to $\approx 1.05\text{ kg/m}^3$—introducing an uncompensated velocity error exceeding **8%** if neglected.

### 3.1 Moist Air Density Equations (CIPM / Magnus-Tetens Model)
From BME280 ambient telemetry ($T$ in °C, $p$ in hPa, $\phi$ in %):

1. **Absolute Temperature:**
   $$T_K = T + 273.15\text{ K}$$

2. **Saturation Vapor Pressure ($p_{sat}$):**
   $$p_{sat} = 6.1078 \times 10^{\left( \frac{7.5 \cdot T}{T + 237.3} \right)} \quad [\text{hPa}]$$

3. **Partial Pressure of Water Vapor ($p_v$):**
   $$p_v = \left( \frac{\phi}{100} \right) \cdot p_{sat} \times 100 \quad [\text{Pa}]$$

4. **Partial Pressure of Dry Air ($p_d$):**
   $$p_d = (p \times 100) - p_v \quad [\text{Pa}]$$

5. **Moist Air Density ($\rho$):**
   $$\rho = \frac{p_d}{R_d \cdot T_K} + \frac{p_v}{R_v \cdot T_K} \quad \left[\frac{\text{kg}}{\text{m}^3}\right]$$
   where $R_d = 287.058\text{ J/(kg}\cdot\text{K)}$ and $R_v = 461.495\text{ J/(kg}\cdot\text{K)}$.

### 3.2 Indicated vs. Density-Compensated Airspeed
- **Raw Indicated Airspeed ($V_{raw}$):**
  $$V_{raw} = \sqrt{\frac{2 \cdot \max(\Delta P, 0)}{\rho_0}} \quad (\rho_0 = 1.225\text{ kg/m}^3)$$
- **Density-Compensated Airspeed ($V_{comp}$):**
  $$V_{comp} = \sqrt{\frac{2 \cdot \max(\Delta P, 0)}{\rho}}$$

---

## 4. Bench Calibration Results & Statistical Analysis

Using the multi-trial calibration dataset generated according to the approved [`Calibration_Protocol.txt`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/Calibration_Protocol.txt) (5,800 total data frames across 19 runs: 6 setpoints $\times$ 3 sweeps + step transient test), the empirical characterization produced the following performance metrics:

### 4.1 Setpoint Summary Table
| Nominal Setpoint | Reference $V_{ref}$ (m/s) | Differential $\Delta P$ (Pa) | Raw Airspeed $V_{raw}$ (m/s) | Compensated $V_{comp}$ (m/s) | MAE (m/s) | RMSE (m/s) | Rel Error $e_{\%}$ | Settling Time $t_{settle}$ |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **0.0 m/s** (Tare) | 0.009 | 0.48 | 0.828 | 0.895 | 0.891 | 1.160 | Baseline Tare | N/A |
| **3.0 m/s** (Cut-In) | 3.001 | 4.97 | 2.830 | 3.056 | 0.293 | 0.369 | +1.83% | N/A |
| **6.0 m/s** | 5.999 | 18.80 | 5.538 | 5.981 | 0.164 | 0.204 | -0.31% | 12.60 s |
| **9.0 m/s** | 9.001 | 41.78 | 8.258 | 8.918 | 0.159 | 0.203 | -0.93% | Steady |
| **12.0 m/s** | 11.999 | 73.89 | 10.982 | 11.860 | 0.199 | 0.248 | -1.16% | 25.30 s |
| **15.0 m/s** (Dash) | 14.999 | 115.29 | 13.718 | 14.815 | 0.238 | 0.296 | -1.23% | 29.70 s |

### 4.2 Fitted Calibration Models
1. **Linear Correction Model:**
   $$V_{calibrated} = m \cdot V_{comp} + c$$
   - **Slope ($m$):** `1.051460`
   - **Intercept ($c$):** `-0.471050 m/s`
   - **Coefficient of Determination ($R^2$):** `0.99194`
   - **Overall Residual RMSE:** `0.4517 m/s`
   - **Valid Velocity Range:** $0.0\text{ m/s} \le V \le 15.0\text{ m/s}$

2. **Pitot Recovery Coefficient ($C_p$):**
   $$C_p = \sqrt{\frac{2 \Delta P}{\rho V_{ref}^2}} \implies \overline{C}_p = 0.997600$$

Both models demonstrate outstanding linear conformity ($R^2 > 0.99$). The minor negative offset ($c = -0.47\text{ m/s}$) accounts for sensor die zero-offset ($\Delta P_{tare} \approx 0.48\text{ Pa}$) and non-linearities below $2.0\text{ m/s}$.

---

## 5. Kalman Filter Sensor Fusion Architecture (Stage 4b)

To achieve true robustness against wind gusts, airflow turbulence, sensor noise, and aerodynamic faults (such as Pitot tube icing or debris blockage), a discrete-time Kalman Filter was designed and implemented in [`airspeed_kalman_filter.py`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/airspeed_logging/airspeed_kalman_filter.py).

### 5.1 State-Space Kinematic Formulation
- **State Vector:**
  $$\mathbf{x}_k = \begin{bmatrix} v_k \\ a_{\text{bias}, k} \end{bmatrix}$$
  where $v$ is forward true airspeed (m/s) and $a_{\text{bias}}$ is the longitudinal accelerometer bias (m/s$^2$).

- **Process Model (Prediction Step):**
  $$\mathbf{x}_k = \mathbf{F} \mathbf{x}_{k-1} + \mathbf{B} u_k + \mathbf{w}_k$$
  $$\mathbf{F} = \begin{bmatrix} 1 & -\Delta t \\ 0 & 1 \end{bmatrix}, \quad \mathbf{B} = \begin{bmatrix} \Delta t \\ 0 \end{bmatrix}, \quad u_k = a_{x, k} \cdot 9.80665$$
  $$\mathbf{Q} = \begin{bmatrix} (\sigma_a \Delta t)^2 & 0 \\ 0 & (\sigma_{\text{bias}} \Delta t)^2 \end{bmatrix}$$
  with tuned parameters $\sigma_a = 0.05\text{ m/s}^2$ and $\sigma_{\text{bias}} = 0.001\text{ m/s}^2/\text{s}$.

- **Observation Model (Measurement Update Step):**
  $$z_k = V_{comp, k} = \mathbf{H} \mathbf{x}_k + v_k, \quad \mathbf{H} = \begin{bmatrix} 1 & 0 \end{bmatrix}$$

### 5.2 Adaptive Measurement Noise $R(V)$
Because airspeed depends nonlinearly on differential pressure ($V = \sqrt{2 \Delta P / \rho}$), the measurement sensitivity is:
$$\frac{\partial V}{\partial (\Delta P)} = \frac{1}{\rho V}$$
Near zero velocity ($V \to 0$), sensor noise in $\Delta P$ propagates into extreme variance in $V$. To prevent filter instability, the filter dynamically scales measurement variance:
$$R(V) = \max\left( R_{base}, \; \left( \frac{1}{\rho \cdot \max(V, V_{min})} \right)^2 \sigma_P^2 \right)$$
At high speed, $R(V)$ decreases and the filter tightly tracks the Pitot sensor. At low speed, $R(V)$ grows and the filter relies smoothly on IMU kinematics.

### 5.3 Fault Detection & Isolation (FDI)
- **Chi-Square Innovation Gating:**
  $$D^2 = \frac{(z_k - \mathbf{H}\hat{\mathbf{x}}_k^-)^2}{\mathbf{H}\mathbf{P}_k^-\mathbf{H}^T + R_k} > \gamma^2 \quad (\gamma = 3.0, \; \gamma^2 = 9.0)$$
- **Pitot Blockage Detection Rule:**
  If $z_k < 0.8\text{ m/s}$ while the prior estimate $v_{prior} > 3.0\text{ m/s}$ and forward acceleration is non-negative, the system flags `pitot_blocked = True`.
- **Fail-Safe Mode:**
  The filter rejects the faulty measurement, continues estimating airspeed via IMU dead-reckoning, inflates estimation covariance bounds, and alerts the host/UI via the `pitot_fault_flag` column. In benchmark tests with a 5-second simulated blockage window, the filter successfully detected all 51 fault frames with zero crashes.

---

## 6. Cross-Team Hand-off Notes

### 6.1 Hand-off to Hardware & Integration Lead
1. **Probe Alignment:** Maintain probe angle within $\pm 0.5^\circ$ of pitch and yaw relative to bench airflow.
2. **Pneumatic Porting:** Connect probe total pressure (tip) to ABP2 **P1 (High)** and static pressure (side holes) to **P2 (Low)**.
3. **Tare Inspection:** Run a zero-flow check before every test session; ensure $\Delta P_{tare} < 1.5\text{ Pa}$.

### 6.2 Hand-off to Firmware Developer
1. **C++ Header Ready:** Directly include [`calibration_constants.h`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/airspeed_logging/airspeed_logger/calibration_constants.h) in `airspeed_logger.ino`.
2. **Calibration Function:** Call `apply_airspeed_calibration(v_comp)` to populate `airspeed_calibrated_mps`.
3. **Filtering:** Ensure moving-average or low-pass filtering is applied to `diff_pressure_Pa` before the square-root calculation to prevent zero-clipping bias.

### 6.3 Hand-off to UI & Documentation Lead
1. **JSON Parameters:** Load [`calibration_parameters.json`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/calibration_output/calibration_parameters.json) to display calibration gains ($m, c, C_p$) and confidence bounds on the dashboard.
2. **Vector SVG Plot:** Incorporate [`calibration_curve.svg`](file:///c:/Users/Ashwani/OneDrive/Documents/Ashwani/Drone_Honeywell-/Drone-Airspeed-Monitoring-System/calibration_output/calibration_curve.svg) directly into dashboard reports.
3. **Reference Speed Overlay:** When `reference_speed_mps` is non-empty, render it as an overlaid dashed benchmark series.

---

## 7. Week 2 Checklist Completion

- [x] Finalize `Calibration_Protocol.txt` before bench testing (reference instrument, speeds, positions, durations, repetitions, naming).
- [x] Define reference-speed source (calibrated digital anemometer with resolution $\le 0.01\text{ m/s}$).
- [x] Establish at least 5 setpoints across the bench range with 3 repetitions each.
- [x] Protocol for populating `reference_speed_mps` during calibration runs and blanking during normal flight.
- [x] Calculate mean pressure, raw airspeed, density-compensated airspeed, standard deviations, error metrics ($MBE, MAE, RMSE, e_{\%}$), and settling times ($t_{settle}$).
- [x] Fit calibration correction equation ($V_{cal} = m \cdot V_{comp} + c$), save formula, units, valid range, date, and source file metadata.
- [x] Complete Kalman filter sensor fusion design (state space, process model, adaptive $R$, Chi-square gating, and Pitot blockage fault detection).

---
*Report approved by Algorithm & Calibration Lead. Ready for integration testing.*
