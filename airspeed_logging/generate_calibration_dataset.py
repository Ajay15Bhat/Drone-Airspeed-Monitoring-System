"""Generate realistic bench-rig calibration dataset for testing analysis and fusion tools.

Author: Algorithm & Calibration Lead
Target: Honeywell ABP2MRRN004NDSA3XE SPI Sensor + BME280 + MPU-6500
Complies with Week 2 19-column CSV Contract:
  timestamp_ms,source,temp_C,pressure_hPa,humidity_pct,
  accel_x_g,accel_y_g,accel_z_g,gyro_x_dps,gyro_y_dps,gyro_z_dps,
  diff_pressure_counts,diff_pressure_inH2O,diff_pressure_Pa,
  abp_temperature_C,abp_status,airspeed_raw_mps,
  airspeed_calibrated_mps,reference_speed_mps
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
import random
from typing import List

# Conversion constants for Honeywell ABP2MRRN004NDSA3XE (±4 inH2O differential, SPI)
P_MIN_INH2O = -4.0
P_MAX_INH2O = 4.0
OUTPUT_MIN = 1677722.0    # 10% of 2^24
OUTPUT_MAX = 15099494.0   # 90% of 2^24
INH2O_TO_PA = 249.08891
STANDARD_AIR_DENSITY = 1.225

CSV_HEADER = [
    "timestamp_ms", "source", "temp_C", "pressure_hPa", "humidity_pct",
    "accel_x_g", "accel_y_g", "accel_z_g", "gyro_x_dps", "gyro_y_dps", "gyro_z_dps",
    "diff_pressure_counts", "diff_pressure_inH2O", "diff_pressure_Pa",
    "abp_temperature_C", "abp_status", "airspeed_raw_mps",
    "airspeed_calibrated_mps", "reference_speed_mps",
]


def generate_single_calibration_run(
    output_path: Path,
    target_speed_mps: float,
    duration_sec: float = 45.0,
    sample_rate_hz: float = 10.0,
    true_pitot_coefficient: float = 0.985,  # Slight real-world aerodynamic recovery factor
    sensor_pressure_offset_pa: float = 0.45, # Realistic slight physical zero offset
    ambient_temp_c: float = 28.5,
    ambient_press_hpa: float = 918.0,
    ambient_humidity_pct: float = 58.0,
    is_step_transient: bool = False,
    step_target_speed_mps: float = 12.0,
    step_time_sec: float = 20.0,
) -> None:
    """Generate one calibration trial CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dt = 1.0 / sample_rate_hz
    total_samples = int(duration_sec * sample_rate_hz)

    # Compute moist air density for ambient conditions
    temp_k = ambient_temp_c + 273.15
    p_sat = 6.1078 * (10.0 ** ((7.5 * ambient_temp_c) / (ambient_temp_c + 237.3)))
    p_v = (ambient_humidity_pct / 100.0) * p_sat * 100.0
    p_d = (ambient_press_hpa * 100.0) - p_v
    moist_density = (p_d / (287.058 * temp_k)) + (p_v / (461.495 * temp_k))

    current_speed = target_speed_mps

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)

        for i in range(total_samples):
            t_sec = i * dt
            t_ms = int(t_sec * 1000)

            # Step change handling if transient test
            if is_step_transient and t_sec >= step_time_sec:
                # First order dynamic settling response (tau = 0.25s)
                current_speed += (step_target_speed_mps - current_speed) * (1.0 - math.exp(-dt / 0.25))
            else:
                current_speed = target_speed_mps

            # Reference anemometer reading with ±0.03 m/s instrument jitter
            ref_noise = random.gauss(0.0, 0.025)
            ref_speed = max(0.0, current_speed + ref_noise)

            # Aerodynamic differential pressure: delta_P = 0.5 * rho * (V * C_p)^2 + offset + turbulence
            turbulence = random.gauss(0.0, 0.015 * current_speed)
            true_flow_speed = max(0.0, current_speed * true_pitot_coefficient + turbulence)
            dynamic_pressure = 0.5 * moist_density * (true_flow_speed ** 2)

            # Add sensor die noise (Honeywell ABP2 ~1.2 Pa noise floor)
            sensor_noise = random.gauss(0.0, 1.15)
            measured_p_pa = dynamic_pressure + sensor_pressure_offset_pa + sensor_noise
            measured_p_pa = max(-20.0, measured_p_pa)  # allow slight negative near zero

            # Convert to ABP2 counts & inH2O
            p_inh2o = measured_p_pa / INH2O_TO_PA
            clamped_inh2o = max(P_MIN_INH2O, min(P_MAX_INH2O, p_inh2o))
            counts = int(((clamped_inh2o - P_MIN_INH2O) / (P_MAX_INH2O - P_MIN_INH2O)) * (OUTPUT_MAX - OUTPUT_MIN) + OUTPUT_MIN)

            # Raw and compensated airspeed calculations
            dp_positive = max(0.0, measured_p_pa)
            raw_airspeed = math.sqrt(2.0 * dp_positive / STANDARD_AIR_DENSITY)
            comp_airspeed = math.sqrt(2.0 * dp_positive / moist_density)

            # IMU simulated readings (bench fixture vibration + longitudinal step accel)
            if is_step_transient and step_time_sec <= t_sec <= (step_time_sec + 1.2):
                accel_x = 0.25 + random.gauss(0.0, 0.015)  # forward acceleration pulse
            else:
                accel_x = 0.02 + random.gauss(0.0, 0.008)  # slight mounting bias + vibration

            accel_y = -0.01 + random.gauss(0.0, 0.008)
            accel_z = 0.998 + random.gauss(0.0, 0.009)  # 1g vertical gravity
            gyro_x = random.gauss(0.0, 0.15)
            gyro_y = random.gauss(0.0, 0.15)
            gyro_z = random.gauss(0.0, 0.10)

            # Environmental minor sensor noise
            temp_c = ambient_temp_c + random.gauss(0.0, 0.05)
            press_hpa = ambient_press_hpa + random.gauss(0.0, 0.08)
            hum_pct = ambient_humidity_pct + random.gauss(0.0, 0.15)

            writer.writerow([
                t_ms,
                "mock",  # clearly labelled as simulation/mock until real ABP2 arrives
                f"{temp_c:.2f}",
                f"{press_hpa:.2f}",
                f"{hum_pct:.2f}",
                f"{accel_x:.4f}",
                f"{accel_y:.4f}",
                f"{accel_z:.4f}",
                f"{gyro_x:.3f}",
                f"{gyro_y:.3f}",
                f"{gyro_z:.3f}",
                counts,
                f"{p_inh2o:.5f}",
                f"{measured_p_pa:.3f}",
                f"{temp_c + 0.5:.2f}",
                "0x40",  # Healthy ABP2 status (powered, not busy, no errors)
                f"{raw_airspeed:.3f}",
                f"{comp_airspeed:.3f}",
                f"{ref_speed:.3f}",
            ])


def generate_full_calibration_campaign(base_dir: Path) -> List[Path]:
    """Generate all setpoints across 3 repetitions and 1 transient test."""
    setpoints = [0.0, 3.0, 6.0, 9.0, 12.0, 15.0]
    generated_files: List[Path] = []
    base_dir.mkdir(parents=True, exist_ok=True)

    print("Generating Week 2 Bench Calibration Test Dataset...")
    for rep in [1, 2, 3]:
        # Sweep ordering
        order = setpoints if rep == 1 else (list(reversed(setpoints)) if rep == 2 else [6.0, 12.0, 3.0, 15.0, 9.0, 0.0])
        for sp in order:
            sp_int = int(round(sp))
            fname = f"calib_20260920_sp{sp_int:02d}_rep{rep}.csv"
            filepath = base_dir / fname
            generate_single_calibration_run(
                output_path=filepath,
                target_speed_mps=sp,
                duration_sec=30.0,  # 300 rows per run (adequate for characterization)
                sample_rate_hz=10.0,
            )
            generated_files.append(filepath)

    # Dynamic Step Response Transient Run (6.0 m/s -> 12.0 m/s)
    step_file = base_dir / "calib_20260920_step_06to12mps.csv"
    generate_single_calibration_run(
        output_path=step_file,
        target_speed_mps=6.0,
        duration_sec=40.0,
        is_step_transient=True,
        step_target_speed_mps=12.0,
        step_time_sec=15.0,
    )
    generated_files.append(step_file)

    print(f"Successfully generated {len(generated_files)} calibration runs in {base_dir}")
    return generated_files


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent.parent / "logs" / "calibration"
    generate_full_calibration_campaign(out_dir)
