"""Analysis for legacy and v2 logs. Invalid rows remain gaps."""
import numpy as np
import pandas as pd
from kalman_filter import filter_pressure


def prepare(frame, q=4.0, r=121.0):
    d = frame.copy()
    required = ['timestamp_ms', 'source', 'temp_C', 'pressure_hPa', 'humidity_pct',
                'abp3_pressure_raw_counts', 'abp3_pressure_zeroed_counts', 'abp3_status']
    missing = set(required) - set(d)
    if missing:
        raise ValueError('Missing telemetry columns: ' + ', '.join(sorted(missing)))
    if len(d) < 2 or not d.source.eq('live').all():
        raise ValueError('Need at least two live sensor rows, not a manifest or mock log.')
    for c in required:
        if c not in ('source', 'abp3_status'):
            d[c] = pd.to_numeric(d[c], errors='raise')
    if not np.isfinite(d.timestamp_ms).all() or not d.timestamp_ms.diff().iloc[1:].gt(0).all():
        raise ValueError('Timestamps reset, repeat or are invalid. Start a separate recording after board resets.')
    d['elapsed_s'] = (d.timestamp_ms-d.timestamp_ms.iloc[0])/1000
    def status_value(v):
        try:
            return int(str(v), 16)
        except ValueError:
            return 0xFFFF
    status = d.abp3_status.map(status_value)
    d['diagnostic_fault'] = (status & 0x0D80) != 0
    d['missed_update'] = (status & 0xC000) != 0
    valid = (~d.diagnostic_fault & ((status & 8) != 0) &
             d.temp_C.between(-40,85) & d.pressure_hPa.between(300,1100) &
             d.humidity_pct.between(0,100) & np.isfinite(d.abp3_pressure_zeroed_counts) &
             np.isfinite(d.abp3_pressure_raw_counts))
    if 'sample_valid' in d:
        valid &= pd.to_numeric(d.sample_valid, errors='coerce').eq(1)
    d['analysis_valid'] = valid
    d['tare_counts'] = d.abp3_pressure_raw_counts-d.abp3_pressure_zeroed_counts
    e = d.humidity_pct/100*610.78*10**(7.5*d.temp_C/(d.temp_C+237.3))
    density = (d.pressure_hPa*100-e)/(287.058*(d.temp_C+273.15))+e/(461.495*(d.temp_C+273.15))
    d['analysis_density_kg_m3'] = density.where(valid)
    d['derived_pressure_Pa'] = (d.abp3_pressure_zeroed_counts*.0390625).where(valid)
    d['derived_speed_mps'] = np.sqrt(2*d.derived_pressure_Pa.clip(lower=0)/d.analysis_density_kg_m3)
    filtered = np.full(len(d), np.nan)
    start = None
    for i in range(len(d)+1):
        good = i < len(d) and bool(valid.iloc[i])
        gap = i > 0 and i < len(d) and d.elapsed_s.iloc[i]-d.elapsed_s.iloc[i-1] > 1
        if start is not None and (not good or gap):
            filtered[start:i] = filter_pressure(d.elapsed_s.iloc[start:i], d.derived_pressure_Pa.iloc[start:i], q, r)
            start = None
        if good and start is None:
            start = i
    d['analysis_kalman_pressure_Pa'] = filtered
    d['analysis_kalman_speed_mps'] = np.sqrt(2*np.maximum(filtered,0)/d.analysis_density_kg_m3)
    d['analysis_q_Pa2_per_s'], d['analysis_r_Pa2'] = q, r
    d['analysis_validation_state'] = 'unvalidated_no_imu_fusion'
    return d
