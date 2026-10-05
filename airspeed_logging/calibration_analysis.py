"""Calibrate live Honeywell ABP3 zeroed counts.

The input manifest supplies the trusted pressure reference for each *live* ABP3
CSV. This tool intentionally rejects the obsolete ABP2 schema and mock rows;
it never assumes a Pa/count value.

Known-pressure example:
    python airspeed_logging/calibration_analysis.py ^
      --manifest logs/calibration/abp3_known_pressure_manifest.csv

Direct anemometer example:
    python airspeed_logging/calibration_analysis.py ^
      --airspeed-manifest logs/airflow/abp3_airspeed_manifest_20260925.csv

The latter fits the empirical model ``airspeed_mps =
sqrt(max(A * zeroed_counts + B, 0))``.  It does not claim a Pa/count value.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any

REQUIRED_LOG_COLUMNS = {
    "timestamp_ms",
    "source",
    "abp3_pressure_zeroed_counts",
    "abp3_temperature_C",
    "abp3_status",
}
REQUIRED_MANIFEST_COLUMNS = {"filename", "known_pressure_pa"}
REQUIRED_AIRSPEED_MANIFEST_COLUMNS = {"filename", "reference_speed_mps"}


class CalibrationError(ValueError):
    """Raised when files are not suitable for live ABP3 calibration."""


def mean_and_sample_std(values: list[float]) -> tuple[float, float]:
    if not values:
        raise CalibrationError("A trial has no valid zeroed-count values.")
    return statistics.fmean(values), statistics.stdev(values) if len(values) > 1 else 0.0


def linear_fit(x_values: list[float], y_values: list[float]) -> dict[str, float]:
    """Fit y = slope*x + intercept and return fit quality metrics."""
    if len(x_values) < 3:
        raise CalibrationError("At least three independent pressure trials are required.")
    if len(set(x_values)) < 2:
        raise CalibrationError("The trial mean counts do not span more than one value.")

    mean_x = statistics.fmean(x_values)
    mean_y = statistics.fmean(y_values)
    variance_x = sum((value - mean_x) ** 2 for value in x_values)
    covariance_xy = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values))
    slope = covariance_xy / variance_x
    intercept = mean_y - slope * mean_x
    residuals = [y - (slope * x + intercept) for x, y in zip(x_values, y_values)]
    sum_squared_error = sum(residual * residual for residual in residuals)
    total_variance = sum((y - mean_y) ** 2 for y in y_values)
    return {
        "pa_per_count": slope,
        "offset_pa": intercept,
        "r_squared": 1.0 - sum_squared_error / total_variance if total_variance else 1.0,
        "rmse_pa": math.sqrt(sum_squared_error / len(y_values)),
    }


def read_manifest(manifest_path: Path) -> list[dict[str, str]]:
    with manifest_path.open(newline="", encoding="utf-8-sig") as manifest_file:
        reader = csv.DictReader(manifest_file)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_MANIFEST_COLUMNS - columns
        if missing:
            raise CalibrationError(f"Manifest is missing required column(s): {', '.join(sorted(missing))}.")

        trials: list[dict[str, str]] = []
        for line_number, row in enumerate(reader, start=2):
            filename = (row.get("filename") or "").strip()
            pressure = (row.get("known_pressure_pa") or "").strip()
            if not filename and not pressure:
                continue
            if not filename or not pressure:
                raise CalibrationError(f"Manifest line {line_number} requires filename and known_pressure_pa.")
            try:
                float(pressure)
            except ValueError as error:
                raise CalibrationError(f"Manifest line {line_number} has invalid known_pressure_pa: {pressure!r}.") from error
            trials.append({key: (value or "").strip() for key, value in row.items()})
    if not trials:
        raise CalibrationError("The manifest has no calibration trials.")
    return trials


def read_airspeed_manifest(manifest_path: Path) -> list[dict[str, str]]:
    """Read filenames and independently observed anemometer speeds."""
    with manifest_path.open(newline="", encoding="utf-8-sig") as manifest_file:
        reader = csv.DictReader(manifest_file)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_AIRSPEED_MANIFEST_COLUMNS - columns
        if missing:
            raise CalibrationError(
                f"Airspeed manifest is missing required column(s): {', '.join(sorted(missing))}."
            )
        trials: list[dict[str, str]] = []
        for line_number, row in enumerate(reader, start=2):
            filename = (row.get("filename") or "").strip()
            speed = (row.get("reference_speed_mps") or "").strip()
            if not filename and not speed:
                continue
            if not filename or not speed:
                raise CalibrationError(f"Airspeed manifest line {line_number} requires filename and reference_speed_mps.")
            try:
                parsed_speed = float(speed)
            except ValueError as error:
                raise CalibrationError(f"Airspeed manifest line {line_number} has invalid reference_speed_mps: {speed!r}.") from error
            if parsed_speed < 0:
                raise CalibrationError(f"Airspeed manifest line {line_number} has a negative reference_speed_mps.")
            trials.append({key: (value or "").strip() for key, value in row.items()})
    if len(trials) < 3:
        raise CalibrationError("At least three live airflow trials are required.")
    return trials


def summarize_live_abp3_log(log_path: Path, known_pressure_pa: float) -> dict[str, Any]:
    with log_path.open(newline="", encoding="utf-8-sig", errors="replace") as log_file:
        reader = csv.DictReader(log_file)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_LOG_COLUMNS - columns
        if missing:
            raise CalibrationError(
                f"{log_path.name} is not an ABP3 CSV; missing: {', '.join(sorted(missing))}. "
                "Do not use legacy ABP2 logs."
            )

        counts: list[float] = []
        temperatures: list[float] = []
        statuses: set[str] = set()
        for line_number, row in enumerate(reader, start=2):
            if (row.get("source") or "").strip().lower() != "live":
                raise CalibrationError(f"{log_path.name} line {line_number} is not live ABP3 data.")
            try:
                counts.append(float((row.get("abp3_pressure_zeroed_counts") or "").strip()))
                temperatures.append(float((row.get("abp3_temperature_C") or "").strip()))
            except ValueError as error:
                raise CalibrationError(f"{log_path.name} line {line_number} has invalid ABP3 numeric data.") from error
            statuses.add((row.get("abp3_status") or "").strip())

    mean_counts, std_counts = mean_and_sample_std(counts)
    mean_temperature_c, _ = mean_and_sample_std(temperatures)
    return {
        "filename": log_path.name,
        "known_pressure_pa": known_pressure_pa,
        "sample_count": len(counts),
        "mean_zeroed_counts": mean_counts,
        "std_zeroed_counts": std_counts,
        "mean_abp3_temperature_c": mean_temperature_c,
        "abp3_statuses": sorted(statuses),
    }


def analyse_manifest(manifest_path: Path) -> dict[str, Any]:
    trials = read_manifest(manifest_path)
    summaries: list[dict[str, Any]] = []
    for trial in trials:
        log_path = manifest_path.parent / trial["filename"]
        if not log_path.is_file():
            raise CalibrationError(f"Manifest input does not exist: {log_path}")
        summary = summarize_live_abp3_log(log_path, float(trial["known_pressure_pa"]))
        summary["reference_instrument"] = trial.get("reference_instrument", "")
        summary["notes"] = trial.get("notes", "")
        summaries.append(summary)

    fit = linear_fit(
        [summary["mean_zeroed_counts"] for summary in summaries],
        [summary["known_pressure_pa"] for summary in summaries],
    )
    return {
        "metadata": {
            "analysis_date": datetime.now().isoformat(timespec="seconds"),
            "sensor": "Honeywell ABP3 I2C",
            "calibration_type": "known differential pressure",
            "formula": "differential_pressure_pa = pa_per_count * zeroed_counts + offset_pa",
            "manifest": str(manifest_path),
            "source_requirement": "live ABP3 CSV only",
        },
        "fit": fit,
        "trials": summaries,
    }


def analyse_airspeed_manifest(manifest_path: Path) -> dict[str, Any]:
    """Fit reference airspeed squared against each log's mean ABP3 count."""
    trials = read_airspeed_manifest(manifest_path)
    summaries: list[dict[str, Any]] = []
    for trial in trials:
        log_path = manifest_path.parent / trial["filename"]
        if not log_path.is_file():
            raise CalibrationError(f"Manifest input does not exist: {log_path}")
        summary = summarize_live_abp3_log(log_path, 0.0)
        reference_speed_mps = float(trial["reference_speed_mps"])
        summary.pop("known_pressure_pa")
        summary["reference_speed_mps"] = reference_speed_mps
        summary["notes"] = trial.get("notes", "")
        summaries.append(summary)

    counts = [summary["mean_zeroed_counts"] for summary in summaries]
    speed_squared = [summary["reference_speed_mps"] ** 2 for summary in summaries]
    fit = linear_fit(counts, speed_squared)
    coefficient_a = fit.pop("pa_per_count")
    coefficient_b = fit.pop("offset_pa")
    if coefficient_a <= 0:
        raise CalibrationError(
            "The fitted count-to-airspeed coefficient is non-positive. "
            "These logs do not support a physically usable direct-airflow calibration."
        )
    predicted_speeds = [math.sqrt(max(coefficient_a * count + coefficient_b, 0.0)) for count in counts]
    errors = [predicted - summary["reference_speed_mps"] for predicted, summary in zip(predicted_speeds, summaries)]
    for summary, predicted_speed, error in zip(summaries, predicted_speeds, errors):
        summary["predicted_speed_mps"] = predicted_speed
        summary["error_mps"] = error
    fit.update({
        "count_to_airspeed_a": coefficient_a,
        "count_to_airspeed_b": coefficient_b,
        "airspeed_rmse_mps": math.sqrt(sum(error * error for error in errors) / len(errors)),
        "airspeed_mae_mps": sum(abs(error) for error in errors) / len(errors),
        "valid_reference_speed_range_mps": [min(speed_squared) ** 0.5, max(speed_squared) ** 0.5],
    })
    return {
        "metadata": {
            "analysis_date": datetime.now().isoformat(timespec="seconds"),
            "sensor": "Honeywell ABP3 I2C",
            "calibration_type": "direct reference-anemometer airflow",
            "formula": "airspeed_mps = sqrt(max(A * zeroed_counts + B, 0))",
            "manifest": str(manifest_path),
            "source_requirement": "live ABP3 CSV only",
        },
        "fit": fit,
        "trials": summaries,
    }


def write_artifacts(results: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "abp3_pressure_calibration.json"
    header_path = output_dir / "abp3_pressure_constants.h"
    with json_path.open("w", encoding="utf-8") as output_file:
        json.dump(results, output_file, indent=2)

    fit = results["fit"]
    header = f"""/* Auto-generated from live ABP3 known-pressure calibration. */
#pragma once

#define ABP3_PA_PER_COUNT {fit['pa_per_count']:.9f}f
#define ABP3_PRESSURE_OFFSET_PA {fit['offset_pa']:.9f}f
#define ABP3_PRESSURE_CAL_R_SQUARED {fit['r_squared']:.6f}f
#define ABP3_PRESSURE_CAL_RMSE_PA {fit['rmse_pa']:.6f}f

static inline float abp3ZeroedCountsToPa(float zeroed_counts) {{
  return ABP3_PA_PER_COUNT * zeroed_counts + ABP3_PRESSURE_OFFSET_PA;
}}
"""
    header_path.write_text(header, encoding="utf-8")
    return json_path, header_path


def write_airspeed_artifacts(results: dict[str, Any], output_dir: Path, approved: bool) -> tuple[Path, Path | None]:
    """Export direct-airflow results; emit firmware constants only after approval."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "abp3_airspeed_calibration.json"
    header_path = output_dir / "abp3_airspeed_constants.h"
    with json_path.open("w", encoding="utf-8") as output_file:
        json.dump(results, output_file, indent=2)
    if not approved:
        return json_path, None
    fit = results["fit"]
    header = f"""/* Auto-generated from live ABP3/reference-anemometer calibration. */
#pragma once

#define ABP3_AIRSPEED_COUNT_A {fit['count_to_airspeed_a']:.9f}f
#define ABP3_AIRSPEED_COUNT_B {fit['count_to_airspeed_b']:.9f}f
#define ABP3_AIRSPEED_CAL_R_SQUARED {fit['r_squared']:.6f}f
#define ABP3_AIRSPEED_CAL_RMSE_MPS {fit['airspeed_rmse_mps']:.6f}f

static inline float abp3ZeroedCountsToAirspeedMps(float zeroed_counts) {{
  const float speed_squared = ABP3_AIRSPEED_COUNT_A * zeroed_counts + ABP3_AIRSPEED_COUNT_B;
  return speed_squared > 0.0f ? sqrtf(speed_squared) : 0.0f;
}}
"""
    header_path.write_text(header, encoding="utf-8")
    return json_path, header_path


def print_summary(results: dict[str, Any]) -> None:
    fit = results["fit"]
    is_airspeed = results["metadata"]["calibration_type"] == "direct reference-anemometer airflow"
    print("ABP3 direct-airflow calibration" if is_airspeed else "ABP3 known-pressure calibration")
    print(f"Trials: {len(results['trials'])}")
    if is_airspeed:
        print(f"A: {fit['count_to_airspeed_a']:.9f} (m/s)^2/count")
        print(f"B: {fit['count_to_airspeed_b']:.6f} (m/s)^2")
        print(f"Airspeed RMSE: {fit['airspeed_rmse_mps']:.6f} m/s")
        print(f"Airspeed MAE: {fit['airspeed_mae_mps']:.6f} m/s")
    else:
        print(f"Pa/count: {fit['pa_per_count']:.9f}")
        print(f"Offset: {fit['offset_pa']:.6f} Pa")
    print(f"R^2: {fit['r_squared']:.6f}")
    print(f"Speed-squared regression RMSE: {fit['rmse_pa']:.6f} (m/s)^2" if is_airspeed else f"RMSE: {fit['rmse_pa']:.6f} Pa")
    for trial in results["trials"]:
        if is_airspeed:
            print(
                f"  {trial['filename']}: {trial['reference_speed_mps']:.3f} m/s, "
                f"{trial['mean_zeroed_counts']:.3f} ± {trial['std_zeroed_counts']:.3f} counts, "
                f"prediction {trial['predicted_speed_mps']:.3f} m/s ({trial['error_mps']:+.3f})"
            )
        else:
            print(
                f"  {trial['filename']}: {trial['known_pressure_pa']:.3f} Pa, "
                f"{trial['mean_zeroed_counts']:.3f} ± {trial['std_zeroed_counts']:.3f} counts "
                f"({trial['sample_count']} samples)"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit live ABP3 zeroed counts to known differential pressure.")
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--manifest", type=Path, help="CSV mapping live ABP3 filenames to known pressure in Pa.")
    input_group.add_argument("--airspeed-manifest", type=Path, help="CSV mapping live ABP3 filenames to reference anemometer speed in m/s.")
    parser.add_argument(
        "--approve-airspeed-calibration",
        action="store_true",
        help="Also write an Arduino header for a reviewed direct-airflow fit.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("calibration_output"))
    arguments = parser.parse_args()

    try:
        is_airspeed = arguments.airspeed_manifest is not None
        results = analyse_airspeed_manifest(arguments.airspeed_manifest) if is_airspeed else analyse_manifest(arguments.manifest)
        print_summary(results)
        json_path, header_path = (
            write_airspeed_artifacts(results, arguments.output_dir, arguments.approve_airspeed_calibration)
            if is_airspeed else write_artifacts(results, arguments.output_dir)
        )
    except (CalibrationError, OSError) as error:
        raise SystemExit(f"Calibration failed: {error}") from error

    print(f"Wrote {json_path}")
    if header_path:
        print(f"Wrote {header_path}")
    elif arguments.airspeed_manifest:
        print("No firmware header written: review the direct-airflow fit, then rerun with --approve-airspeed-calibration.")


if __name__ == "__main__":
    main()
