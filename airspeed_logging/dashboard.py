"""Run: python -m streamlit run airspeed_logging/dashboard.py"""
from pathlib import Path
from io import BytesIO
import time
import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from telemetry import prepare

st.set_page_config(page_title='AERIS | Airspeed Lab', page_icon='◈', layout='wide')
st.markdown('''<style>
.stApp {background: #0b1220; color: #e5edf8;}
[data-testid="stSidebar"] {background:#111c2e;}
[data-testid="stHeader"] {background:transparent;}
.block-container {padding-top:2rem; max-width:1500px;}
.eyebrow {color:#5eead4;letter-spacing:.22em;font-size:.75rem;font-weight:700;}
.hero {padding:26px 30px;border:1px solid #29405b;border-radius:20px;
background:linear-gradient(115deg,#15364a,#142039 65%,#162d40);margin-bottom:18px;}
.hero h1 {font-size:2.8rem;letter-spacing:-.04em;margin:6px 0;color:#f2f7ff;}
.hero p {color:#b7c8dd;margin-bottom:0;}
[data-testid="stMetric"] {background:#142238;border:1px solid #29405b;border-radius:14px;padding:18px;}
[data-testid="stMetricLabel"] {color:#b7c8dd;}
[data-testid="stMetricValue"] {color:#5eead4;}
[data-testid="stTabs"] button {font-weight:600;}
.stCaption {color:#a9bad0;}
</style>''', unsafe_allow_html=True)
st.markdown('''<div class="hero"><div class="eyebrow">AERIS / EXPERIMENTAL TELEMETRY</div>
<h1>Airspeed Lab</h1><p>Pressure to insight. Environmental compensation, Kalman smoothing and sensor diagnostics.</p></div>''', unsafe_allow_html=True)
st.warning('EXPERIMENTAL PROTOTYPE · Absolute airspeed accuracy unvalidated · Not for flight control · No IMU fusion')
root = Path(__file__).resolve().parents[1]
with st.sidebar:
    st.markdown('### Session controls')
    files = sorted((root/'logs'/'airflow').glob('*.csv'), key=lambda p:p.stat().st_mtime, reverse=True)
    files = [p for p in files if 'manifest' not in p.name.lower()]
    selected = st.selectbox('Recording', files, format_func=lambda p:p.name)
    upload = st.file_uploader('Or upload a recording', type='csv')
    monitor = st.checkbox('Monitor growing CSV (refresh every 2 s)', disabled=upload is not None)
    st.caption('The serial logger owns the COM port. This dashboard only reads its CSV; it does not reset the ESP32.')
    st.markdown('### Analysis filter')
    q = st.number_input('Q · process variance (Pa²/s)', min_value=0.0, value=4.0)
    r = st.number_input('R · measurement variance (Pa²)', min_value=0.001, value=121.0)
    st.caption('Provisional settings. Larger Q or smaller R responds faster. Smoothing adds lag; it does not calibrate accuracy. These controls do not change firmware settings.')
    compare = st.checkbox('Show reference comparison')
    reference = st.number_input('Anemometer mean (m/s)', min_value=0.0, value=6.5, disabled=not compare)


def chart(d, columns, title, unit):
    available = [c for c in columns if c in d]
    if not available:
        st.info('These channels are not present in this recording.')
        return
    data = d[['elapsed_s']+available].copy().rename(columns=columns)
    data = data.melt('elapsed_s', var_name='Signal', value_name='Value')
    graph = alt.Chart(data).mark_line(strokeWidth=2, clip=True).encode(
        x=alt.X('elapsed_s:Q', title='Elapsed time (s)'),
        y=alt.Y('Value:Q', title=unit, scale=alt.Scale(zero=False)),
        color=alt.Color('Signal:N', scale=alt.Scale(domain=[columns[c] for c in available], range=['#94a3b8','#2dd4bf','#fbbf24','#a78bfa'][:len(available)]), legend=alt.Legend(orient='bottom')),
        tooltip=['Signal', alt.Tooltip('elapsed_s:Q', format='.1f'), alt.Tooltip('Value:Q', format='.3f')]
    ).properties(height=290, title=title).configure(background='#101c2e').configure_axis(
        labelColor='#b7c8dd', titleColor='#b7c8dd', gridColor='#24344b').configure_title(
        color='#eef5ff', anchor='start').configure_legend(labelColor='#b7c8dd', titleColor='#b7c8dd')
    st.altair_chart(graph, width='stretch')


@st.fragment(run_every=2 if monitor and upload is None else None)
def render():
    try:
        source = upload.getvalue() if upload is not None else selected.read_bytes() if selected else b''
        if monitor and upload is None and source and not source.endswith(b'\n'):
            source = source.rsplit(b'\n',1)[0]+b'\n' if b'\n' in source else b''
        frame = pd.read_csv(BytesIO(source))
        d = prepare(frame, q, r)
    except (ValueError, OSError, pd.errors.ParserError) as exc:
        st.info(f'Waiting for usable telemetry: {exc}')
        return
    age = max(0,time.time()-selected.stat().st_mtime) if upload is None else None
    mode = 'MONITORING CSV' if monitor and upload is None else 'RECORDED DATA'
    st.caption(f'{mode}  /  {len(d):,} samples  /  {d.elapsed_s.iloc[-1]:.1f} seconds  /  '+
               ('uploaded file' if age is None else f'file updated {age:.0f} s ago'))
    if monitor and age is not None and age > 5:
        st.error('STALE DATA — no file update for more than 5 seconds. Values below are historical, not current telemetry.')
    if monitor:
        latest = d.iloc[-1]
        st.markdown('#### Latest received sample')
        last_cards = st.columns(3)
        last_cards[0].metric('Filtered estimate · latest', f'{latest.analysis_kalman_speed_mps:.2f} m/s' if latest.analysis_valid else 'INVALID')
        last_cards[1].metric('Pressure · latest', f'{latest.derived_pressure_Pa:.2f} Pa' if latest.analysis_valid else 'INVALID')
        last_cards[2].metric('Sample time', f'{latest.elapsed_s:.1f} s')
    full = st.checkbox('Use full recording', value=True)
    end_time = float(d.elapsed_s.iloc[-1])
    if not full:
        start,end = st.slider('Analysis window (seconds)', 0.0,end_time,(0.0,end_time))
        v = d[d.elapsed_s.between(start,end)].copy()
    else:
        v = d.copy()
    if len(v)<2:
        st.info('Select at least two samples.')
        return
    st.caption('Metrics summarize the selected interval, including valid zero-speed samples. Invalid samples remain gaps and are counted separately. Filters process the full recording before interval selection.')
    cards=st.columns(4)
    cards[0].metric('Filtered speed · mean', f'{v.analysis_kalman_speed_mps.mean():.2f} m/s')
    cards[1].metric('Unfiltered speed · mean', f'{v.derived_speed_mps.mean():.2f} m/s')
    cards[2].metric('Differential pressure · mean', f'{v.derived_pressure_Pa.mean():.2f} Pa')
    cards[3].metric('Usable airspeed samples', f'{v.analysis_valid.sum():,} / {len(v):,}')
    overview, environment, imu, health, export = st.tabs(['Airspeed & pressure','Environment','IMU motion','Diagnostics','Data & export'])
    with overview:
        chart(v, {'derived_speed_mps':'Unfiltered · reconstructed', 'analysis_kalman_speed_mps':'Kalman · analysis', 'kalman_speed_mps':'Kalman · firmware'}, 'Airspeed response', 'Speed (m/s)')
        left,right=st.columns(2)
        with left:
            chart(v, {'derived_pressure_Pa':'Unfiltered pressure','analysis_kalman_pressure_Pa':'Kalman pressure'}, 'Pressure response','Pressure (Pa)')
        with right:
            st.markdown('#### Signal behaviour')
            st.metric('Unfiltered speed SD', f'{v.derived_speed_mps.std():.3f} m/s')
            st.metric('Filtered speed SD', f'{v.analysis_kalman_speed_mps.std():.3f} m/s')
            st.caption('Lower variation is not proof of better accuracy. OFF/ON transitions and filter lag affect these statistics.')
        if compare:
            rows=[]
            for name,c in [('Unfiltered','derived_speed_mps'),('Analysis Kalman','analysis_kalman_speed_mps')]:
                err=v[c]-reference
                rows.append({'Estimate':name,'Reference (m/s)':reference,'Bias (m/s)':err.mean(),'MAE (m/s)':err.abs().mean(),'RMSE (m/s)':np.sqrt((err**2).mean())})
            st.markdown('#### Independent reference comparison')
            st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
            st.caption('Approximate constant reference, not synchronized ground truth. No R² for a single constant reference. Reference does not tune or alter the filter.')
    with environment:
        c=st.columns(4)
        for col,label,key,unit in zip(c,['Temperature','Atmospheric pressure','Relative humidity','Air density'],['temp_C','pressure_hPa','humidity_pct','analysis_density_kg_m3'],['°C','hPa','%','kg/m³']):
            col.metric(label, f'{v[key].mean():.2f} {unit}')
        a,b=st.columns(2)
        with a:
            chart(v, {'temp_C':'BME280','abp3_temperature_C':'ABP3 internal'},'Temperature','°C')
            chart(v, {'humidity_pct':'Relative humidity'},'Humidity','%')
        with b:
            chart(v, {'pressure_hPa':'BME280 absolute pressure'},'Atmospheric pressure','hPa')
            chart(v, {'analysis_density_kg_m3':'Moist-air density'},'Density used for airspeed','kg/m³')
    with imu:
        st.info('IMU measures device motion, not airflow. Acceleration includes gravity. No IMU/airspeed fusion or independent airspeed validation is performed.')
        chart(v, {f'accel_{a}_g':f'{a.upper()} acceleration' for a in 'xyz'},'Acceleration','g')
        chart(v, {f'gyro_{a}_dps':f'{a.upper()} angular rate' for a in 'xyz'},'Angular rate','°/s')
        axes=[f'accel_{a}_g' for a in 'xyz']
        if all(c in v for c in axes):
            norm=np.sqrt(v[axes].pow(2).sum(axis=1,min_count=3))
            st.metric('Acceleration magnitude SD · motion proxy',f'{norm.std():.4f} g')
            st.caption('Not a calibrated vibration measurement; requires IMU mechanically attached to the object being monitored.')
    with health:
        c=st.columns(3)
        c[0].metric('Invalid airspeed samples', int((~v.analysis_valid).sum()))
        c[1].metric('ABP3 diagnostic-fault samples', int(v.diagnostic_fault.sum()))
        c[2].metric('Missed-update flagged samples', int(v.missed_update.sum()))
        st.caption('CRC/saturation/bridge faults and missing pressure-update flags invalidate analysis. Missed-update flags are displayed, not proof of fault-free timing. Legacy logs cannot report all communication failures.')
        if 'imu_valid' in v:
            st.write('Invalid IMU samples:', int(v.imu_valid.ne(1).sum()))
        st.write('Inferred tare counts:', sorted(v.tare_counts.dropna().unique().tolist()))
        st.write('Timestamp gaps > 1 second:', int(d.elapsed_s.diff().gt(1).sum()))
        st.dataframe(v.abp3_status.value_counts().rename('Samples'))
        chart(v, {'abp3_pressure_raw_counts':'Raw counts','abp3_pressure_zeroed_counts':'Zeroed counts'},'ABP3 digital output','Counts')
        st.caption('Startup tare requires equal port pressures / fan OFF. Legacy airspeed_calibrated_mps means density-compensated, not independently calibrated.')
    with export:
        st.markdown('#### Reproducible analysis')
        st.caption('Original fields are preserved. analysis_* fields identify dashboard calculations; firmware Kalman fields remain separate. Experimental accuracy status and Q/R accompany export.')
        st.download_button('Download interval CSV',v.to_csv(index=False).encode(), 'aeris_analysis_unvalidated.csv','text/csv')
        st.dataframe(v, width='stretch')


render()
