"""Kalman Filter Sensor Fusion for Pitot-Static & IMU Airspeed Estimation.

Author: Algorithm & Calibration Lead
Role Deliverable: Week 2 Core Build (Stage 4b Sensor Fusion Architecture)
Target Platform: Host-side refinement (Python) and embedded reference implementation

Features:
  - State vector: [airspeed_v (m/s), accel_bias (m/s^2)]
  - Longitudinal kinematic process model driven by IMU ax acceleration
  - Adaptive measurement noise scaling R(v) handling Bernoulli square-root singularity
  - Chi-square innovation gating for Pitot blockage, icing, and disconnection detection
  - Seamless IMU dead-reckoning fallback with covariance inflation during faults
  - Batch CSV processor and real-time streaming class interface
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

GRAVITY_MPS2 = 9.80665


class AirspeedKalmanFilter:
    """Discrete-time linear Kalman filter fusing differential pressure and IMU acceleration."""

    def __init__(
        self,
        dt: float = 0.1,
        sigma_accel: float = 0.05,       # Accelerometer noise (m/s^2)
        sigma_bias_drift: float = 0.001,  # Bias random walk (m/s^2 / s)
        sigma_pressure_pa: float = 1.2,   # ABP2 differential pressure noise floor (Pa)
        base_airspeed_variance: float = 0.04,
        gating_threshold_sigma: float = 3.0,
    ) -> None:
        """Initialize the Kalman filter parameters and state matrices.

        Args:
            dt: Sampling time step in seconds (nominal 0.1s for 10 Hz).
            sigma_accel: Accelerometer measurement noise density.
            sigma_bias_drift: Longitudinal bias random walk variance rate.
            sigma_pressure_pa: Honeywell ABP2 pressure measurement noise (Pa).
            base_airspeed_variance: Minimum measurement variance floor (m/s)^2.
            gating_threshold_sigma: Normalized innovation rejection threshold.
        """
        self.dt = dt
        self.sigma_accel = sigma_accel
        self.sigma_bias_drift = sigma_bias_drift
        self.sigma_pressure_pa = sigma_pressure_pa
        self.base_airspeed_variance = base_airspeed_variance
        self.gating_threshold = gating_threshold_sigma ** 2  # Chi-square with 1 DOF

        # State vector: [v (m/s), a_bias (m/s^2)]^T
        self.x = [0.0, 0.0]

        # Estimation error covariance P (2x2)
        self.P = [
            [0.25, 0.0],
            [0.0, 0.05],
        ]

        # Process noise covariance Q (2x2)
        q_v = (self.sigma_accel * self.dt) ** 2
        q_b = (self.sigma_bias_drift * self.dt) ** 2
        self.Q = [
            [q_v, 0.0],
            [0.0, q_b],
        ]

        # Diagnostic fault flags
        self.fault_flags: Dict[str, bool] = {
            "pitot_blocked": False,
            "sensor_degraded": False,
            "chi_square_gated": False,
            "low_speed_singularity": False,
        }
        self.consecutive_fault_count = 0

    def predict(self, accel_x_g: float, pitch_deg: float = 0.0) -> Tuple[float, float]:
        """Perform time update (prediction) step using IMU longitudinal acceleration.

        Args:
            accel_x_g: Measured forward acceleration in units of g.
            pitch_deg: Pitch attitude angle in degrees (default 0 for level flight/bench).

        Returns:
            Tuple of predicted state (v_prior, a_bias_prior).
        """
        # Convert g to m/s^2 and remove gravity tilt component: a_long = a_x - g*sin(pitch)
        pitch_rad = math.radians(pitch_deg)
        a_x_mps2 = accel_x_g * GRAVITY_MPS2 - GRAVITY_MPS2 * math.sin(pitch_rad)

        v_old = self.x[0]
        b_old = self.x[1]

        # Kinematic state propagation:
        # v_k = v_{k-1} + (a_x - b_{k-1}) * dt
        # b_k = b_{k-1}
        v_prior = max(0.0, v_old + (a_x_mps2 - b_old) * self.dt)
        b_prior = b_old
        self.x = [v_prior, b_prior]

        # Covariance propagation: P_prior = F * P * F^T + Q
        # F = [[1, -dt], [0, 1]]
        p00 = self.P[0][0]
        p01 = self.P[0][1]
        p10 = self.P[1][0]
        p11 = self.P[1][1]

        dt = self.dt
        new_p00 = p00 - dt * (p10 + p01) + (dt ** 2) * p11 + self.Q[0][0]
        new_p01 = p01 - dt * p11
        new_p10 = p10 - dt * p11
        new_p11 = p11 + self.Q[1][1]

        self.P = [
            [new_p00, new_p01],
            [new_p10, new_p11],
        ]
        return self.x[0], self.x[1]

    def _compute_adaptive_r(self, v_estimate: float, air_density: float) -> float:
        """Calculate adaptive measurement noise variance R(v) based on Bernoulli derivative.

        R(v) = (1 / (rho * max(v, v_min)))^2 * sigma_P^2 + R_base
        """
        # Minimum speed guard to avoid 1/0 singularity near rest
        v_guard = max(1.0, v_estimate)
        rho = max(0.8, air_density)
        # Sensitivity: dV / dP = 1 / (rho * V)
        dv_dp = 1.0 / (rho * v_guard)
        r_adaptive = (dv_dp * self.sigma_pressure_pa) ** 2 + self.base_airspeed_variance
        return min(25.0, float(r_adaptive))

    def update(
        self,
        v_pitot_comp: float,
        air_density: float = 1.225,
        hardware_fault_detected: bool = False,
    ) -> Dict[str, Any]:
        """Perform measurement update step using Pitot-derived airspeed with fault gating.

        Args:
            v_pitot_comp: Density-compensated airspeed from Pitot sensor (m/s).
            air_density: Local moist air density in kg/m^3.
            hardware_fault_detected: Boolean flag from ABP2 SPI status register.

        Returns:
            Dictionary containing estimated state, variance, innovation, and fault flags.
        """
        v_prior = self.x[0]
        b_prior = self.x[1]

        # Reset transient fault flags
        self.fault_flags["chi_square_gated"] = False
        self.fault_flags["low_speed_singularity"] = (v_prior < 1.5)

        # Adaptive measurement variance
        R = self._compute_adaptive_r(v_prior, air_density)

        # Observation matrix H = [1, 0]
        # Innovation (measurement residual)
        innovation = v_pitot_comp - v_prior
        # Innovation covariance: S = H * P * H^T + R = P[0][0] + R
        S = self.P[0][0] + R
        # Normalized squared innovation (Mahalanobis distance)
        d_squared = (innovation ** 2) / S

        # Blockage / Disconnect Fault Detection:
        # If Pitot drops close to 0 while estimated speed is high and forward accel is non-negative
        is_blockage = (v_pitot_comp < 0.8 and v_prior > 3.0)

        # Innovation Chi-Square Gating
        is_gated = (d_squared > self.gating_threshold) or is_blockage or hardware_fault_detected

        if is_gated:
            self.consecutive_fault_count += 1
            self.fault_flags["chi_square_gated"] = True
            if is_blockage:
                self.fault_flags["pitot_blocked"] = True
            if self.consecutive_fault_count >= 3:
                self.fault_flags["sensor_degraded"] = True

            # Reject measurement update: keep prior state (IMU dead-reckoning)
            # Covariance inflation reflecting sensor unreliability
            self.P[0][0] += 0.05 * self.dt
            self.P[1][1] += 0.005 * self.dt
            status_str = "REJECTED_FAULT"
        else:
            # Valid measurement: calculate Kalman gain K = P * H^T / S
            self.consecutive_fault_count = 0
            self.fault_flags["pitot_blocked"] = False
            self.fault_flags["sensor_degraded"] = False

            K0 = self.P[0][0] / S
            K1 = self.P[1][0] / S

            # State update
            self.x[0] = max(0.0, v_prior + K0 * innovation)
            self.x[1] = b_prior + K1 * innovation

            # Covariance update: P = (I - K * H) * P
            new_p00 = (1.0 - K0) * self.P[0][0]
            new_p01 = (1.0 - K0) * self.P[0][1]
            new_p10 = self.P[1][0] - K1 * self.P[0][0]
            new_p11 = self.P[1][1] - K1 * self.P[0][1]

            self.P = [
                [new_p00, new_p01],
                [new_p10, new_p11],
            ]
            status_str = "FUSED_NOMINAL"

        # 95% confidence interval (2 * sigma)
        speed_std = math.sqrt(max(1e-6, self.P[0][0]))

        return {
            "airspeed_fused_mps": round(self.x[0], 3),
            "accel_bias_mps2": round(self.x[1], 4),
            "speed_std_mps": round(speed_std, 4),
            "confidence_lower_mps": round(max(0.0, self.x[0] - 2.0 * speed_std), 3),
            "confidence_upper_mps": round(self.x[0] + 2.0 * speed_std, 3),
            "innovation_mps": round(innovation, 4),
            "innovation_variance_S": round(S, 4),
            "mahalanobis_d2": round(d_squared, 3),
            "adaptive_R": round(R, 4),
            "update_status": status_str,
            "fault_flags": dict(self.fault_flags),
        }


def run_filter_on_csv(
    input_csv: Path,
    output_csv: Path,
    inject_blockage_window: Optional[Tuple[float, float]] = None,
) -> Dict[str, Any]:
    """Process a logged CSV dataset through the Kalman sensor fusion pipeline.

    Args:
        input_csv: Path to input 19-column CSV file.
        output_csv: Path to write enriched output CSV with fused airspeed and fault flags.
        inject_blockage_window: Optional (start_sec, end_sec) tuple to simulate Pitot blockage.

    Returns:
        Summary statistics of the fusion run.
    """
    kf = AirspeedKalmanFilter(dt=0.1)

    with input_csv.open("r", encoding="utf-8", errors="replace") as f_in:
        reader = csv.DictReader(f_in)
        fieldnames = list(reader.fieldnames or [])

        # Add fusion columns
        fusion_fields = [
            "airspeed_fused_mps",
            "accel_bias_mps2",
            "speed_confidence_band_mps",
            "fusion_status",
            "pitot_fault_flag",
        ]
        out_fields = fieldnames + [col for col in fusion_fields if col not in fieldnames]

        records_out: List[Dict[str, Any]] = []
        fused_speeds: List[float] = []
        pitot_speeds: List[float] = []
        fault_count = 0

        last_time_s: Optional[float] = None

        for row in reader:
            try:
                t_ms = float(row.get("timestamp_ms", 0.0))
                t_s = t_ms / 1000.0
                ax = float(row.get("accel_x_g", 0.0))
                v_comp_str = row.get("airspeed_calibrated_mps", "")
                v_comp = float(v_comp_str) if v_comp_str else 0.0

                # Check for synthetic fault injection (for testing fault response)
                if inject_blockage_window is not None:
                    if inject_blockage_window[0] <= t_s <= inject_blockage_window[1]:
                        v_comp = 0.0  # Simulated blockage!

                # Estimate time step dt
                if last_time_s is not None and t_s > last_time_s:
                    kf.dt = min(0.5, max(0.01, t_s - last_time_s))
                last_time_s = t_s

                # Kalman prediction & update
                kf.predict(accel_x_g=ax, pitch_deg=0.0)
                res = kf.update(v_pitot_comp=v_comp, air_density=1.20)

                row["airspeed_fused_mps"] = f"{res['airspeed_fused_mps']:.3f}"
                row["accel_bias_mps2"] = f"{res['accel_bias_mps2']:.4f}"
                row["speed_confidence_band_mps"] = f"±{2.0 * res['speed_std_mps']:.3f}"
                row["fusion_status"] = res["update_status"]
                row["pitot_fault_flag"] = "1" if res["fault_flags"]["pitot_blocked"] else "0"

                if res["fault_flags"]["pitot_blocked"]:
                    fault_count += 1

                fused_speeds.append(res["airspeed_fused_mps"])
                pitot_speeds.append(v_comp)
                records_out.append(row)
            except (ValueError, TypeError):
                continue

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=out_fields)
        writer.writeheader()
        writer.writerows(records_out)

    return {
        "total_frames": len(records_out),
        "mean_fused_airspeed_mps": round(sum(fused_speeds) / max(1, len(fused_speeds)), 3),
        "pitot_faults_detected": fault_count,
        "output_file": str(output_csv),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Kalman sensor fusion on airspeed CSV logs.")
    parser.add_argument("input_csv", type=Path, help="Input CSV log file")
    parser.add_argument("--output-csv", type=Path, default=Path("logs/airspeed_fused.csv"), help="Output fused CSV file")
    parser.add_argument("--test-fault-window", nargs=2, type=float, metavar=("T_START", "T_END"), help="Inject synthetic Pitot blockage from T_START to T_END seconds")
    args = parser.parse_args()

    if not args.input_csv.is_file():
        print(f"Error: File not found: {args.input_csv}", file=sys.stderr)
        sys.exit(1)

    print(f"Executing Kalman fusion on {args.input_csv}...")
    window = tuple(args.test_fault_window) if args.test_fault_window else None
    summary = run_filter_on_csv(args.input_csv, args.output_csv, inject_blockage_window=window)

    print("\n" + "=" * 60)
    print("         KALMAN FILTER FUSION SUMMARY (STAGE 4b)")
    print("=" * 60)
    print(f"Total Processed Frames:     {summary['total_frames']}")
    print(f"Mean Fused Airspeed:        {summary['mean_fused_airspeed_mps']} m/s")
    print(f"Pitot Fault Flags Raised:   {summary['pitot_faults_detected']}")
    print(f"Fused Output Saved To:      {summary['output_file']}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
