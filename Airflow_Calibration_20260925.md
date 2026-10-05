# ABP3 direct-airflow calibration review — 2026-09-25

Nine live ABP3 Pitot logs were analysed against the anemometer speeds encoded in
their filenames: a fan-off baseline and eight nominal points from 2.6 to 7.8
m/s. All logs use the live 19-column ABP3 schema and only status values
`0xC018` and `0xC019`.

## Result

The present data are valid **response-test evidence**, but they do not validate
a count-to-airspeed conversion for firmware. A least-squares fit of

```text
airspeed_mps = sqrt(max(A * zeroed_counts + B, 0))
```

gave `A = 0.138321367 (m/s)^2/count`, `B = 26.293218 (m/s)^2`, `R² = 0.281370`,
and airspeed RMSE = `2.231181 m/s`. Critically, the fitted zero-flow prediction
is `5.109 m/s`; it must not be used.

| Reference speed (m/s) | Mean zeroed count | Count SD |
| ---: | ---: | ---: |
| 0.0 | -1.4 | 15.2 |
| 2.6 | 3.2 | 72.2 |
| 3.8 | -57.7 | 175.4 |
| 4.6 | 46.3 | 273.6 |
| 5.8 | -91.4 | 379.3 |
| 6.3 | 180.8 | 443.6 |
| 7.0 | 82.3 | 559.1 |
| 7.5 | 53.1 | 542.1 |
| 7.8 | 111.3 | 559.5 |

The standard deviation increases markedly with blower speed and several higher
speed means overlap or reverse sign. That is consistent with a turbulent,
non-uniform jet or changing probe/anemometer sampling position, rather than a
stable calibration setpoint.

## Safe next collection pass

Keep the verified Pitot orientation and tubing unchanged. For each target,
log only after both the anemometer and ABP3 counts have settled, retain a fixed
anemometer/probe geometry, and record three repetitions. A duct extension or
flow straightener will help. Do not install airspeed constants until a new fit
has a near-zero fan-off prediction and acceptable repeatability/RMSE.

The analysis command is:

```powershell
python airspeed_logging\calibration_analysis.py --airspeed-manifest logs\airflow\abp3_airspeed_manifest_20260925.csv --output-dir calibration_output\airflow_20260925
```

It writes an analysis JSON only. A firmware header requires the explicit
`--approve-airspeed-calibration` switch after engineering review.
