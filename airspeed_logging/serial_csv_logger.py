"""Save CSV rows emitted by airspeed_logger.ino.

Install once:  python -m pip install pyserial
Run:           python serial_csv_logger.py --port COM5
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path
import sys
import time

try:
    import serial
except ImportError as error:
    raise SystemExit("pyserial is required: python -m pip install pyserial") from error

SCHEMA = [
    "timestamp_ms", "source", "temp_C", "pressure_hPa", "humidity_pct",
    "accel_x_g", "accel_y_g", "accel_z_g", "gyro_x_dps", "gyro_y_dps", "gyro_z_dps",
    "abp3_pressure_raw_counts", "abp3_pressure_zeroed_counts", "abp3_temperature_C",
    "abp3_status", "diff_pressure_Pa", "airspeed_raw_mps", "airspeed_calibrated_mps",
    "reference_speed_mps",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Log airspeed CSV records from an ESP32 serial port.")
    parser.add_argument("--port", required=True, help="ESP32 serial port, e.g. COM5")
    parser.add_argument("--baud", type=int, default=115200)
    destination_group = parser.add_mutually_exclusive_group()
    destination_group.add_argument(
        "--output",
        type=Path,
        help="Exact destination CSV path; useful for named calibration trials.",
    )
    destination_group.add_argument("--output-dir", type=Path, default=Path("logs"))
    arguments = parser.parse_args()

    if arguments.output is not None:
        destination = arguments.output
        destination.parent.mkdir(parents=True, exist_ok=True)
    else:
        arguments.output_dir.mkdir(parents=True, exist_ok=True)
        destination = arguments.output_dir / f"airspeed_{datetime.now():%Y%m%d_%H%M%S}.csv"
    print(f"Waiting for CSV data on {arguments.port} at {arguments.baud} baud…")

    with serial.Serial(arguments.port, arguments.baud, timeout=1) as device:
        # Most ESP32 boards reset when the serial connection opens.
        time.sleep(2)
        with destination.open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.writer(output_file)
            writer.writerow(SCHEMA)
            output_file.flush()
            print(f"Logging to {destination}. Press Ctrl+C to stop.")
            try:
                while True:
                    line = device.readline().decode("utf-8", errors="replace").strip()
                    if not line or line.startswith("#") or line == ",".join(SCHEMA):
                        continue
                    row = next(csv.reader([line]))
                    if len(row) != len(SCHEMA):
                        print(f"Ignored malformed line ({len(row)} fields): {line}", file=sys.stderr)
                        continue
                    writer.writerow(row)
                    output_file.flush()
            except KeyboardInterrupt:
                print(f"\nSaved {destination}")


if __name__ == "__main__":
    main()
