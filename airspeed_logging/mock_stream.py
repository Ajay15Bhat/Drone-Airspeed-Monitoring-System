"""Emit firmware-compatible ABP3 CSV rows for dashboard and logger development.

Example: python mock_stream.py --period-ms 100 --reference-speed 4.5
The pressure-in-Pa and airspeed fields intentionally remain blank until the
ABP3 pressure calibration determines Pa/count.
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
    "abp3_pressure_raw_counts", "abp3_pressure_zeroed_counts", "abp3_temperature_C",
    "abp3_status", "diff_pressure_Pa", "airspeed_raw_mps", "airspeed_calibrated_mps",
    "reference_speed_mps",
]
ABP3_TARE_COUNTS = -60


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate test rows with the ESP32 ABP3 CSV schema.")
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
            humidity_pct = 58.0 + math.cos(elapsed / 40)
            zeroed_counts = round(700 * math.sin(0.8 * elapsed))
            raw_counts = ABP3_TARE_COUNTS + zeroed_counts
            writer.writerow([
                round(elapsed * 1000), "mock", f"{temp_c:.2f}", f"{pressure_hpa:.2f}", f"{humidity_pct:.2f}",
                f"{0.01 * math.sin(elapsed):.4f}", f"{0.01 * math.cos(elapsed):.4f}", "1.0000",
                f"{1.5 * math.sin(elapsed):.3f}", f"{math.cos(elapsed):.3f}", "0.000",
                raw_counts, zeroed_counts, "30.00", "0xC018", "", "", "",
                "" if arguments.reference_speed is None else f"{arguments.reference_speed:.3f}",
            ])
            sys.stdout.flush()
            time.sleep(arguments.period_ms / 1000)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
