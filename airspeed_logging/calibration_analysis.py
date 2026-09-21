"""Bench-Rig Calibration Analysis & Characterization Toolkit.

Author: Algorithm & Calibration Lead
Target: Honeywell ABP2 Differential Pressure Sensor + BME280 Environmental Sensor
Role Deliverable: Week 2 Core Build

Features:
  - Moist air density compensation using CIPM / Tetens formulation
  - Raw and density-compensated airspeed calculations
  - Multi-run statistical characterization (mean, standard deviation, noise)
  - Error metrics: MBE, MAE, RMSE, percentage relative error
  - Step-response settling time quantification (5% tolerance band)
  - Linear gain/offset regression and Pitot recovery coefficient (C_p) fitting
  - Direct export to 'calibration_parameters.json' and 'calibration_constants.h'
  - Standalone SVG / HTML calibration curves generation
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

STANDARD_SEA_LEVEL_DENSITY = 1.225  # kg/m^3 (ISA standard)
GAS_CONSTANT_DRY_AIR = 287.058      # J / (kg * K)
GAS_CONSTANT_WATER_VAPOR = 461.495  # J / (kg * K)
COUNT_TO_INH2O_CONVERSION = 8.0 / (15099494.0 - 1677722.0)  # ABP2 10% to 90% transfer
INH2O_TO_PA = 249.08891                                      # 1 inH2O = 249.08891 Pa


def compute_air_density(temp_c: float, pressure_hpa: float, humidity_pct: float) -> float:
    """Calculate moist air density using CIPM / Tetens formulation.

    Args:
        temp_c: Ambient temperature in degrees Celsius (°C).
        pressure_hpa: Barometric static pressure in hectopascals (hPa).
        humidity_pct: Relative humidity in percent (0 - 100%).

    Returns:
        Local moist air density in kg/m^3.
    """
    temp_k = temp_c + 273.15
    # Magnus-Tetens formula for saturation vapor pressure in hPa
    p_sat_hpa = 6.1078 * (10.0 ** ((7.5 * temp_c) / (temp_c + 237.3)))
    # Partial pressure of water vapor in Pa
    p_vapor_pa = (max(0.0, min(100.0, humidity_pct)) / 100.0) * (p_sat_hpa * 100.0)
    # Partial pressure of dry air in Pa
    p_dry_pa = max(0.0, (pressure_hpa * 100.0) - p_vapor_pa)

    # Combined moist air density
    density = (p_dry_pa / (GAS_CONSTANT_DRY_AIR * temp_k)) + (
        p_vapor_pa / (GAS_CONSTANT_WATER_VAPOR * temp_k)
    )
    return float(density)


def compute_raw_airspeed(diff_pressure_pa: float) -> float:
    """Calculate raw indicated airspeed assuming standard sea-level density.

    V_raw = sqrt(2 * max(diff_pressure_pa, 0) / 1.225)
    """
    if diff_pressure_pa <= 0.0:
        return 0.0
    return math.sqrt(2.0 * diff_pressure_pa / STANDARD_SEA_LEVEL_DENSITY)


def compute_density_compensated_airspeed(diff_pressure_pa: float, density: float) -> float:
    """Calculate true airspeed compensated for ambient moist air density.

    V_comp = sqrt(2 * max(diff_pressure_pa, 0) / rho)
    """
    if diff_pressure_pa <= 0.0 or density <= 0.0:
        return 0.0
    return math.sqrt(2.0 * diff_pressure_pa / density)


def compute_settling_time(
    timestamps_s: List[float],
    values: List[float],
    target_value: float,
    tolerance_fraction: float = 0.05,
) -> Optional[float]:
    """Calculate settling time: duration until signal enters and stays within tolerance.

    Args:
        timestamps_s: Elapsed time array in seconds.
        values: Measured response values.
        target_value: Steady-state final setpoint value.
        tolerance_fraction: Error bound fraction (default 0.05 = ±5%).

    Returns:
        Settling time in seconds relative to start, or None if signal never settled.
    """
    if not timestamps_s or not values or len(timestamps_s) != len(values):
        return None
    delta = abs(target_value) * tolerance_fraction
    lower = target_value - delta
    upper = target_value + delta

    # Find the last point where the value was outside the tolerance band
    last_outside_idx = -1
    for i, v in enumerate(values):
        if v < lower or v > upper:
            last_outside_idx = i

    if last_outside_idx == -1:
        # Always within tolerance from t0
        return 0.0
    if last_outside_idx == len(values) - 1:
        # Never settled
        return None
    return float(timestamps_s[last_outside_idx + 1] - timestamps_s[0])


def load_calibration_csv(filepath: Path) -> List[Dict[str, Any]]:
    """Load and normalize a CSV log file with the 19-column or legacy schema."""
    rows: List[Dict[str, Any]] = []
    with filepath.open("r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed: Dict[str, Any] = {}
            for k, v in row.items():
                parsed[k.strip()] = v.strip() if v is not None else ""

            # Standardize numeric fields
            try:
                t_ms = float(parsed.get("timestamp_ms", 0.0))
                temp_c = float(parsed.get("temp_C", 25.0))
                press_hpa = float(parsed.get("pressure_hPa", 1013.25))
                hum_pct = float(parsed.get("humidity_pct", 50.0))

                # Handle differential pressure from Pa or raw counts
                diff_p = parsed.get("diff_pressure_Pa", "")
                if diff_p and diff_p != "":
                    dp_val = float(diff_p)
                elif "diff_pressure_counts" in parsed and parsed["diff_pressure_counts"] != "":
                    counts = float(parsed["diff_pressure_counts"])
                    inh2o = (counts - 1677722.0) * COUNT_TO_INH2O_CONVERSION - 4.0
                    dp_val = inh2o * INH2O_TO_PA
                elif "abp3_pressure_zeroed_counts" in parsed and parsed["abp3_pressure_zeroed_counts"] != "":
                    # Legacy count test approximation (approx 0.14 Pa / count)
                    dp_val = float(parsed["abp3_pressure_zeroed_counts"]) * 0.142
                else:
                    dp_val = 0.0

                ref_speed_str = parsed.get("reference_speed_mps", "")
                ref_speed = float(ref_speed_str) if ref_speed_str != "" else None

                density = compute_air_density(temp_c, press_hpa, hum_pct)
                raw_v = compute_raw_airspeed(dp_val)
                comp_v = compute_density_compensated_airspeed(dp_val, density)

                rows.append({
                    "timestamp_ms": t_ms,
                    "timestamp_s": t_ms / 1000.0,
                    "temp_C": temp_c,
                    "pressure_hPa": press_hpa,
                    "humidity_pct": hum_pct,
                    "density_kg_m3": density,
                    "diff_pressure_Pa": dp_val,
                    "airspeed_raw_mps": raw_v,
                    "airspeed_calibrated_mps": comp_v,
                    "reference_speed_mps": ref_speed,
                })
            except (ValueError, TypeError):
                continue
    return rows


def perform_linear_regression(x: List[float], y: List[float]) -> Tuple[float, float, float, float]:
    """Perform simple ordinary least squares linear regression y = m * x + c.

    Returns:
        (slope, intercept, r_squared, rmse)
    """
    n = len(x)
    if n < 2:
        return 1.0, 0.0, 1.0, 0.0

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    ss_xx = sum((xi - mean_x) ** 2 for xi in x)
    ss_yy = sum((yi - mean_y) ** 2 for yi in y)
    ss_xy = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))

    if ss_xx == 0.0:
        return 1.0, 0.0, 0.0, 0.0

    slope = ss_xy / ss_xx
    intercept = mean_y - slope * mean_x

    residuals = [yi - (slope * xi + intercept) for xi, yi in zip(x, y)]
    ss_res = sum(r ** 2 for r in residuals)
    r_squared = 1.0 - (ss_res / ss_yy) if ss_yy > 0.0 else 1.0
    rmse = math.sqrt(ss_res / n)

    return float(slope), float(intercept), float(r_squared), float(rmse)


def analyze_calibration_setpoints(all_trials: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate multi-setpoint trials and compute comprehensive calibration metrics."""
    # Group trials by nearest nominal setpoint (0, 3, 6, 9, 12, 15 etc.)
    target_candidates = [0.0, 3.0, 6.0, 9.0, 12.0, 15.0, 18.0, 20.0]
    setpoint_groups: Dict[float, List[Dict[str, Any]]] = {}

    for row in all_trials:
        ref = row.get("reference_speed_mps")
        if ref is None:
            continue
        # Find nearest target candidate
        nearest_target = min(target_candidates, key=lambda t: abs(ref - t))
        if abs(ref - nearest_target) <= 1.2:
            nominal = nearest_target
        else:
            nominal = round(ref, 0)

        if nominal not in setpoint_groups:
            setpoint_groups[nominal] = []
        setpoint_groups[nominal].append(row)

    sorted_setpoints = sorted(setpoint_groups.keys())
    setpoint_summaries: List[Dict[str, Any]] = []

    all_v_comp: List[float] = []
    all_v_ref: List[float] = []
    all_pitot_coeffs: List[float] = []

    for sp in sorted_setpoints:
        rows = setpoint_groups[sp]
        n_pts = len(rows)
        if n_pts == 0:
            continue

        dp_list = [r["diff_pressure_Pa"] for r in rows]
        v_raw_list = [r["airspeed_raw_mps"] for r in rows]
        v_comp_list = [r["airspeed_calibrated_mps"] for r in rows]
        v_ref_list = [r["reference_speed_mps"] for r in rows]
        density_list = [r["density_kg_m3"] for r in rows]

        mean_dp = sum(dp_list) / n_pts
        std_dp = math.sqrt(sum((p - mean_dp) ** 2 for p in dp_list) / max(1, n_pts - 1))

        mean_v_raw = sum(v_raw_list) / n_pts
        std_v_raw = math.sqrt(sum((v - mean_v_raw) ** 2 for v in v_raw_list) / max(1, n_pts - 1))

        mean_v_comp = sum(v_comp_list) / n_pts
        std_v_comp = math.sqrt(sum((v - mean_v_comp) ** 2 for v in v_comp_list) / max(1, n_pts - 1))

        mean_v_ref = sum(v_ref_list) / n_pts
        mean_density = sum(density_list) / n_pts

        # Error metrics against ground truth
        errors = [c - r for c, r in zip(v_comp_list, v_ref_list)]
        mbe = sum(errors) / n_pts
        mae = sum(abs(e) for e in errors) / n_pts
        rmse = math.sqrt(sum(e ** 2 for e in errors) / n_pts)
        rel_error_pct = (mbe / mean_v_ref * 100.0) if mean_v_ref > 0.0 else 0.0

        # Pitot recovery coefficient: C_p = sqrt(2 * dp / (rho * V_ref^2))
        if mean_v_ref > 0.5 and mean_dp > 0.0:
            c_p = math.sqrt(2.0 * mean_dp / (mean_density * (mean_v_ref ** 2)))
            all_pitot_coeffs.append(c_p)
        else:
            c_p = 1.0

        # Settling time calculation across trial window
        t_s = [r["timestamp_s"] for r in rows]
        t_settle = compute_settling_time(t_s, v_comp_list, mean_v_ref, tolerance_fraction=0.05)

        summary = {
            "nominal_setpoint_mps": sp,
            "sample_count": n_pts,
            "mean_reference_mps": round(mean_v_ref, 3),
            "mean_diff_pressure_pa": round(mean_dp, 3),
            "std_diff_pressure_pa": round(std_dp, 4),
            "mean_density_kg_m3": round(mean_density, 4),
            "mean_raw_airspeed_mps": round(mean_v_raw, 3),
            "std_raw_airspeed_mps": round(std_v_raw, 4),
            "mean_comp_airspeed_mps": round(mean_v_comp, 3),
            "std_comp_airspeed_mps": round(std_v_comp, 4),
            "mbe_mps": round(mbe, 4),
            "mae_mps": round(mae, 4),
            "rmse_mps": round(rmse, 4),
            "relative_error_pct": round(rel_error_pct, 2),
            "pitot_recovery_factor_cp": round(c_p, 4),
            "settling_time_s": round(t_settle, 3) if t_settle is not None else "N/A",
        }
        setpoint_summaries.append(summary)

        all_v_comp.extend(v_comp_list)
        all_v_ref.extend(v_ref_list)

    # Perform regression: V_calibrated = m * V_comp + c
    slope, intercept, r_sq, overall_rmse = perform_linear_regression(all_v_comp, all_v_ref)
    mean_cp = sum(all_pitot_coeffs) / len(all_pitot_coeffs) if all_pitot_coeffs else 1.0

    valid_min_speed = min(sorted_setpoints) if sorted_setpoints else 0.0
    valid_max_speed = max(sorted_setpoints) if sorted_setpoints else 20.0

    return {
        "metadata": {
            "analysis_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "author": "Algorithm & Calibration Lead",
            "sensor": "Honeywell ABP2MRRN004NDSA3XE",
            "units": "m/s (airspeed), Pa (differential pressure), kg/m^3 (density)",
            "valid_range_mps": [valid_min_speed, valid_max_speed],
        },
        "fit_model": {
            "model_type": "linear",
            "formula": "V_calibrated = slope * V_comp + intercept",
            "slope": round(slope, 5),
            "intercept_mps": round(intercept, 5),
            "r_squared": round(r_sq, 5),
            "overall_rmse_mps": round(overall_rmse, 4),
            "mean_pitot_coefficient_cp": round(mean_cp, 4),
        },
        "setpoint_summaries": setpoint_summaries,
    }


def export_calibration_artifacts(
    results: Dict[str, Any],
    output_dir: Path,
    dataset_name: str,
) -> Tuple[Path, Path]:
    """Export calibration parameters to JSON and C++ header file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "calibration_parameters.json"
    header_path = output_dir / "calibration_constants.h"

    # Save full JSON
    results["metadata"]["dataset_source"] = dataset_name
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Save C++ Header for Firmware Developer
    fit = results["fit_model"]
    meta = results["metadata"]
    header_content = f"""/*
 * Auto-generated Calibration Constants Header
 * Role: Algorithm & Calibration Lead
 * Generated: {meta['analysis_date']}
 * Dataset Source: {dataset_name}
 * Sensor: {meta['sensor']}
 */

#pragma once

#ifndef CALIBRATION_CONSTANTS_H
#define CALIBRATION_CONSTANTS_H

// Linear Calibration Model: V_calibrated = (CALIBRATION_SLOPE * V_comp) + CALIBRATION_OFFSET_MPS
#define CALIBRATION_SLOPE             {fit['slope']:.6f}f
#define CALIBRATION_OFFSET_MPS        {fit['intercept_mps']:.6f}f
#define CALIBRATION_R_SQUARED         {fit['r_squared']:.6f}f
#define CALIBRATION_RMSE_MPS          {fit['overall_rmse_mps']:.6f}f

// Aerodynamic Pitot Recovery Factor: C_p
#define CALIBRATION_PITOT_COEFF_CP    {fit['mean_pitot_coefficient_cp']:.6f}f

// Operational Valid Velocity Bounds (m/s)
#define CALIBRATION_VELOCITY_MIN_MPS  {meta['valid_range_mps'][0]:.2f}f
#define CALIBRATION_VELOCITY_MAX_MPS  {meta['valid_range_mps'][1]:.2f}f

/**
 * Apply empirical calibration correction to density-compensated airspeed.
 * @param v_comp_mps Density-compensated airspeed in meters per second.
 * @return Calibrated true airspeed in meters per second.
 */
static inline float apply_airspeed_calibration(float v_comp_mps) {{
    if (v_comp_mps <= 0.0f) return 0.0f;
    float v_cal = (CALIBRATION_SLOPE * v_comp_mps) + CALIBRATION_OFFSET_MPS;
    return (v_cal > 0.0f) ? v_cal : 0.0f;
}}

#endif // CALIBRATION_CONSTANTS_H
"""
    with header_path.open("w", encoding="utf-8") as f:
        f.write(header_content)

    return json_path, header_path


def generate_svg_calibration_chart(results: Dict[str, Any], output_path: Path) -> None:
    """Generate a clean, standalone SVG plot showing V_comp vs V_ref and error curve."""
    summaries = results.get("setpoint_summaries", [])
    if not summaries:
        return

    fit = results["fit_model"]
    width = 800
    height = 500
    margin_l = 80
    margin_r = 40
    margin_t = 60
    margin_b = 60

    plot_w = width - margin_l - margin_r
    plot_h = height - margin_t - margin_b

    max_val = max([s["mean_reference_mps"] for s in summaries] + [16.0])

    def to_svg_x(val: float) -> float:
        return margin_l + (val / max_val) * plot_w

    def to_svg_y(val: float) -> float:
        return margin_t + plot_h - (val / max_val) * plot_h

    svg_lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="background:#1e1e2e;font-family:sans-serif;">',
        f'<text x="{width // 2}" y="35" text-anchor="middle" fill="#cdd6f4" font-size="18" font-weight="bold">Pitot-Static Airspeed Calibration Curve (Week 2 Core Build)</text>',
        f'<line x1="{margin_l}" y1="{margin_t}" x2="{margin_l}" y2="{margin_t + plot_h}" stroke="#45475a" stroke-width="2"/>',
        f'<line x1="{margin_l}" y1="{margin_t + plot_h}" x2="{margin_l + plot_w}" y2="{margin_t + plot_h}" stroke="#45475a" stroke-width="2"/>',
    ]

    # Gridlines and ticks
    for tick in range(0, int(max_val) + 1, 3):
        x = to_svg_x(tick)
        y = to_svg_y(tick)
        svg_lines.append(f'<line x1="{x}" y1="{margin_t}" x2="{x}" y2="{margin_t + plot_h}" stroke="#313244" stroke-dasharray="4"/>')
        svg_lines.append(f'<text x="{x}" y="{margin_t + plot_h + 20}" text-anchor="middle" fill="#a6adc8" font-size="12">{tick}</text>')
        svg_lines.append(f'<line x1="{margin_l}" y1="{y}" x2="{margin_l + plot_w}" y2="{y}" stroke="#313244" stroke-dasharray="4"/>')
        svg_lines.append(f'<text x="{margin_l - 12}" y="{y + 4}" text-anchor="end" fill="#a6adc8" font-size="12">{tick}</text>')

    # Axis labels
    svg_lines.append(f'<text x="{width // 2}" y="{height - 15}" text-anchor="middle" fill="#cdd6f4" font-size="14">Compensated Airspeed V_comp (m/s)</text>')
    svg_lines.append(f'<text x="25" y="{height // 2}" text-anchor="middle" fill="#cdd6f4" font-size="14" transform="rotate(-90 25 {height // 2})">Reference Airspeed V_ref (m/s)</text>')

    # Ideal 1:1 line
    svg_lines.append(f'<line x1="{to_svg_x(0)}" y1="{to_svg_y(0)}" x2="{to_svg_x(max_val)}" y2="{to_svg_y(max_val)}" stroke="#6c7086" stroke-width="2" stroke-dasharray="5 5"/>')

    # Fitted line
    x0 = 0.0
    y0 = fit["intercept_mps"]
    x1 = max_val
    y1 = fit["slope"] * x1 + fit["intercept_mps"]
    svg_lines.append(f'<line x1="{to_svg_x(x0)}" y1="{to_svg_y(y0)}" x2="{to_svg_x(x1)}" y2="{to_svg_y(y1)}" stroke="#89b4fa" stroke-width="3"/>')

    # Data points
    for s in summaries:
        px = to_svg_x(s["mean_comp_airspeed_mps"])
        py = to_svg_y(s["mean_reference_mps"])
        svg_lines.append(f'<circle cx="{px}" cy="{py}" r="6" fill="#f38ba8" stroke="#ffffff" stroke-width="2"/>')
        svg_lines.append(f'<text x="{px + 10}" y="{py - 5}" fill="#fab387" font-size="11">SP {s["nominal_setpoint_mps"]}m/s</text>')

    # Legend / stats box
    leg_x = margin_l + 25
    leg_y = margin_t + 25
    svg_lines.append(f'<rect x="{leg_x}" y="{leg_y}" width="260" height="100" rx="8" fill="#181825" stroke="#45475a" stroke-width="1.5"/>')
    svg_lines.append(f'<text x="{leg_x + 15}" y="{leg_y + 24}" fill="#89b4fa" font-size="13" font-weight="bold">Linear Fit Model:</text>')
    svg_lines.append(f'<text x="{leg_x + 15}" y="{leg_y + 45}" fill="#cdd6f4" font-size="12">V_cal = {fit["slope"]:.4f} * V_comp + ({fit["intercept_mps"]:.3f})</text>')
    svg_lines.append(f'<text x="{leg_x + 15}" y="{leg_y + 65}" fill="#a6e3a1" font-size="12">R² = {fit["r_squared"]:.4f} | RMSE = {fit["overall_rmse_mps"]:.3f} m/s</text>')
    svg_lines.append(f'<text x="{leg_x + 15}" y="{leg_y + 85}" fill="#f9e2af" font-size="12">Mean Pitot C_p = {fit["mean_pitot_coefficient_cp"]:.4f}</text>')

    svg_lines.append("</svg>")

    with output_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(svg_lines))


def print_ascii_summary_table(results: Dict[str, Any]) -> None:
    """Print an attractive summary table of calibration results to the terminal."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    fit = results["fit_model"]
    summaries = results["setpoint_summaries"]

    print("\n" + "=" * 88)
    print("           DRONE AIRSPEED MONITORING SYSTEM -- BENCH CALIBRATION REPORT")
    print("=" * 88)
    print(f"Date: {results['metadata']['analysis_date']} | Sensor: {results['metadata']['sensor']}")
    print(f"Regression Fit: V_cal = {fit['slope']:.4f} * V_comp + ({fit['intercept_mps']:.4f}) m/s")
    print(f"Goodness of Fit: R^2 = {fit['r_squared']:.4f} | Overall RMSE = {fit['overall_rmse_mps']:.4f} m/s | Mean Cp = {fit['mean_pitot_coefficient_cp']:.4f}")
    print("-" * 88)
    print(f"{'SP (m/s)':<8} | {'V_ref':<8} | {'dP (Pa)':<9} | {'V_raw':<8} | {'V_comp':<8} | {'MAE':<7} | {'RMSE':<7} | {'e (%)':<7} | {'t_settle':<8}")
    print("-" * 88)
    for s in summaries:
        t_settle_str = f"{s['settling_time_s']:.2f}s" if isinstance(s['settling_time_s'], (int, float)) else str(s['settling_time_s'])
        print(f"{s['nominal_setpoint_mps']:<8.1f} | {s['mean_reference_mps']:<8.3f} | {s['mean_diff_pressure_pa']:<9.2f} | {s['mean_raw_airspeed_mps']:<8.3f} | {s['mean_comp_airspeed_mps']:<8.3f} | {s['mae_mps']:<7.3f} | {s['rmse_mps']:<7.3f} | {s['relative_error_pct']:<7.2f} | {t_settle_str:<8}")
    print("=" * 88 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze bench-rig airspeed calibration logs.")
    parser.add_argument("input_files", nargs="+", help="Paths to one or more calibration CSV log files")
    parser.add_argument("--output-dir", type=Path, default=Path("calibration_output"), help="Output directory for parameters and plots")
    args = parser.parse_args()

    all_rows: List[Dict[str, Any]] = []
    file_names: List[str] = []

    import glob

    for file_arg in args.input_files:
        # Expand globs if present (standard on Windows shells)
        matched_paths = [Path(m) for m in glob.glob(file_arg)] if any(c in file_arg for c in "*?[]") else [Path(file_arg)]
        for p in matched_paths:
            if p.is_file():
                rows = load_calibration_csv(p)
                all_rows.extend(rows)
                file_names.append(p.name)
            elif p.is_dir():
                for sub in sorted(p.glob("*.csv")):
                    rows = load_calibration_csv(sub)
                    all_rows.extend(rows)
                    file_names.append(sub.name)

    if not all_rows:
        print("Error: No valid rows could be loaded from specified inputs.", file=sys.stderr)
        sys.exit(1)

    print(f"Loaded {len(all_rows)} data points across {len(file_names)} file(s).")
    results = analyze_calibration_setpoints(all_rows)
    print_ascii_summary_table(results)

    json_p, header_p = export_calibration_artifacts(results, args.output_dir, ", ".join(file_names[:3]))
    print(f"[OK] Exported parameters to: {json_p}")
    print(f"[OK] Exported C++ firmware header to: {header_p}")

    chart_p = args.output_dir / "calibration_curve.svg"
    generate_svg_calibration_chart(results, chart_p)
    print(f"[OK] Generated calibration chart: {chart_p}")


if __name__ == "__main__":
    main()
