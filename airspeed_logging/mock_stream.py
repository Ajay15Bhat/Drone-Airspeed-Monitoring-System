"""Emit firmware-compatible CSV data for dashboard and logger development.

Example: python mock_stream.py --period-ms 100 --reference-speed 4.5
Pipe to a dashboard or redirect to a file. The default blank reference-speed
matches normal (non-calibration) operation.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time

SCHEMA = [
    "timestamp_ms", "source", "temp_C", "pressure_hPa", "humidity_pct",
    "accel_x_g", "accel_y_g", "accel_z_g", "gyro_x_dps", "gyro_y_dps", "gyro_z_dps",
    "diff_pressure_counts", "diff_pressure_inH2O", "diff_pressure_Pa", "abp_temperature_C",
    "abp_status", "airspeed_raw_mps", "airspeed_calibrated_mps", "reference_speed_mps",
]
OUTPUT_MIN, OUTPUT_MAX = 1_677_722, 15_099_494
INH2O_TO_PA = 249.08891


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate test rows with the ESP32 CSV schema.")
    parser.add_argument("--period-ms", type=int, default=100)
    parser.add_argument("--reference-speed", type=float, help="Populate only for a calibration run.")
    arguments = parser.parse_args()
    if arguments.period_ms <= 0:
        raise SystemExit("--period-ms must be positive")

    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(SCHEMA)
    start = time.monotonic()
    try:
        while True:
            elapsed = time.monotonic() - start
            temp_c = 27.0 + 0.3 * math.sin(elapsed / 30)
            pressure_hpa = 1008.0 + 0.5 * math.sin(elapsed / 45)
            humidity_pct = 58.0 + 1.0 * math.cos(elapsed / 40)
            diff_inh2o = 0.7 + 0.35 * math.sin(0.8 * elapsed)
            diff_pa = diff_inh2o * INH2O_TO_PA
            counts = round(OUTPUT_MIN + (diff_inh2o + 4.0) * (OUTPUT_MAX - OUTPUT_MIN) / 8.0)
            raw_speed = math.sqrt(2.0 * max(diff_pa, 0.0) / 1.225)
            density = 1.17
            calibrated_speed = math.sqrt(2.0 * max(diff_pa, 0.0) / density)
            writer.writerow([
                round(elapsed * 1000), "mock", f"{temp_c:.2f}", f"{pressure_hpa:.2f}", f"{humidity_pct:.2f}",
                f"{0.01 * math.sin(elapsed):.4f}", f"{0.01 * math.cos(elapsed):.4f}", "1.0000",
                f"{1.5 * math.sin(elapsed):.3f}", f"{1.0 * math.cos(elapsed):.3f}", "0.000",
                counts, f"{diff_inh2o:.5f}", f"{diff_pa:.3f}", "25.00", "0x40",
                f"{raw_speed:.3f}", f"{calibrated_speed:.3f}",
                "" if arguments.reference_speed is None else f"{arguments.reference_speed:.3f}",
            ])
            sys.stdout.flush()
            time.sleep(arguments.period_ms / 1000)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
