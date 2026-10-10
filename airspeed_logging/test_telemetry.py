import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from telemetry import prepare
from serial_csv_logger import SCHEMA, SCHEMA_V2, schema_for_row


def fixture():
    return pd.DataFrame({'timestamp_ms':[100,200,300,400], 'source':['live']*4,
        'temp_C':[29]*4, 'pressure_hPa':[913]*4, 'humidity_pct':[53]*4,
        'abp3_pressure_raw_counts':[0,100,200,300],
        'abp3_pressure_zeroed_counts':[0,100,200,300], 'abp3_status':['0xC018']*4})


class TelemetryTests(unittest.TestCase):
    def test_legacy(self):
        d=prepare(fixture())
        self.assertTrue(d.analysis_valid.all())
        self.assertAlmostEqual(d.derived_pressure_Pa.iloc[1],3.90625)
        self.assertTrue(d.missed_update.all())

    def test_fault_resets_filter(self):
        f=fixture(); f.loc[1,'abp3_status']='0xCD98'
        d=prepare(f)
        self.assertTrue(np.isnan(d.analysis_kalman_speed_mps.iloc[1]))
        self.assertEqual(d.analysis_kalman_pressure_Pa.iloc[2],d.derived_pressure_Pa.iloc[2])

    def test_missing_and_bad_environment(self):
        f=fixture(); f.loc[1,'temp_C']=np.nan; f.loc[2,'humidity_pct']=101
        d=prepare(f)
        self.assertEqual(d.analysis_valid.tolist(),[True,False,False,True])

    def test_firmware_fields_preserved(self):
        f=fixture(); f['kalman_speed_mps']=42.; f['sample_valid']=[1,0,1,1]
        d=prepare(f)
        self.assertTrue(d.kalman_speed_mps.eq(42).all())
        self.assertFalse(d.analysis_valid.iloc[1])

    def test_gap_resets(self):
        f=fixture(); f.timestamp_ms=[100,200,2000,2100]
        d=prepare(f)
        self.assertEqual(d.analysis_kalman_pressure_Pa.iloc[2],d.derived_pressure_Pa.iloc[2])

    def test_reject_reset_and_mock(self):
        for column,value in [('timestamp_ms',0),('source','mock')]:
            f=fixture(); f.loc[2,column]=value
            with self.assertRaises(ValueError): prepare(f)

    def test_schemas(self):
        self.assertEqual(len(SCHEMA),19)
        self.assertEqual(len(SCHEMA_V2),27)
        self.assertEqual(schema_for_row(['']*19),SCHEMA)
        self.assertEqual(schema_for_row(['']*27),SCHEMA_V2)
        with self.assertRaises(ValueError): schema_for_row(['']*20)

    def test_firmware_header_matches_logger(self):
        sketch=(Path(__file__).parent/'airspeed_logger'/'airspeed_logger.ino').read_text()
        header=next(line.split('"')[1] for line in sketch.splitlines() if 'Serial.println("timestamp_ms,' in line)
        self.assertEqual(header.split(','),SCHEMA_V2)


if __name__=='__main__': unittest.main()
