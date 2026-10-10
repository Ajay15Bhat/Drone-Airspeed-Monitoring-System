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
SCHEMA_V2 = SCHEMA + [
    "density_kg_m3", "kalman_pressure_Pa", "kalman_speed_mps", "sample_valid",
    "imu_valid", "kalman_q_Pa2_per_s", "kalman_r_Pa2", "validation_state",
]


def schema_for_row(row):
    if len(row) == len(SCHEMA):
        return SCHEMA
    if len(row) == len(SCHEMA_V2):
        return SCHEMA_V2
    raise ValueError(f"Unsupported CSV width: {len(row)}")


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

    if destination.exists():
        raise SystemExit(f"Refusing to overwrite {destination}; choose a new filename.")
    with serial.Serial(arguments.port, arguments.baud, timeout=1) as device:
        # Most ESP32 boards reset when the serial connection opens.
        time.sleep(2)
        with destination.open("x", newline="", encoding="utf-8") as output_file:
            writer = csv.writer(output_file)
            active_schema = None
            print(f"Logging to {destination}. Press Ctrl+C to stop.")
            try:
                while True:
                    line = device.readline().decode("utf-8", errors="replace").strip()
                    if line.startswith("#"):
                        print(line, flush=True)
                        continue
                    if not line or line.startswith("timestamp_ms,"):
                        continue
                    row = next(csv.reader([line]))
                    try:
                        row_schema = schema_for_row(row)
                        float(row[0])
                        if row[1] != "live":
                            raise ValueError("Not a live sensor row")
                    except ValueError:
                        print(f"Ignored malformed line ({len(row)} fields): {line}", file=sys.stderr)
                        continue
                    if active_schema is None:
                        active_schema = row_schema
                        writer.writerow(active_schema)
                    elif row_schema != active_schema:
                        raise SystemExit("Firmware schema changed during capture; start a new log.")
                    writer.writerow(row)
                    output_file.flush()
            except KeyboardInterrupt:
                print(f"\nSaved {destination}")


if __name__ == "__main__":
    main()
