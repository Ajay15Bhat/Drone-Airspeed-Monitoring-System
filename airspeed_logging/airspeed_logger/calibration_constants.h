/*
 * Auto-generated Calibration Constants Header
 * Role: Algorithm & Calibration Lead
 * Generated: 2026-09-19 21:33:51
 * Dataset Source: calib_20260920_sp00_rep1.csv, calib_20260920_sp00_rep2.csv, calib_20260920_sp00_rep3.csv
 * Sensor: Honeywell ABP2MRRN004NDSA3XE
 */

#pragma once

#ifndef CALIBRATION_CONSTANTS_H
#define CALIBRATION_CONSTANTS_H

// Linear Calibration Model: V_calibrated = (CALIBRATION_SLOPE * V_comp) + CALIBRATION_OFFSET_MPS
#define CALIBRATION_SLOPE             1.051460f
#define CALIBRATION_OFFSET_MPS        -0.471050f
#define CALIBRATION_R_SQUARED         0.991940f
#define CALIBRATION_RMSE_MPS          0.451700f

// Aerodynamic Pitot Recovery Factor: C_p
#define CALIBRATION_PITOT_COEFF_CP    0.997600f

// Operational Valid Velocity Bounds (m/s)
#define CALIBRATION_VELOCITY_MIN_MPS  0.00f
#define CALIBRATION_VELOCITY_MAX_MPS  15.00f

/**
 * Apply empirical calibration correction to density-compensated airspeed.
 * @param v_comp_mps Density-compensated airspeed in meters per second.
 * @return Calibrated true airspeed in meters per second.
 */
static inline float apply_airspeed_calibration(float v_comp_mps) {
    if (v_comp_mps <= 0.0f) return 0.0f;
    float v_cal = (CALIBRATION_SLOPE * v_comp_mps) + CALIBRATION_OFFSET_MPS;
    return (v_cal > 0.0f) ? v_cal : 0.0f;
}

#endif // CALIBRATION_CONSTANTS_H
