"""Official thermal fit, gated by independent healthy verification and schema checks."""
import json, math
from pathlib import Path
import pandas as pd
from runtime.schema_adapter_100kVA import SIGNALS,LEGACY,CompatibilityError
from runtime.input_adapter_100kVA import normalize_frame
from runtime.data_quality_100kVA import assess
from runtime.thermal_model import commission

ROOT=Path(__file__).resolve().parents[1]

def validate_calibration(calibration,asset_id=None):
    cal=dict(calibration)
    policy=json.loads((ROOT/'calibration/calibration_policy.json').read_text())
    if cal.get('rating_kva',100)!=100: raise CompatibilityError('Calibration rating must be 100 kVA')
    for key,(lo,hi) in policy['parameter_bounds'].items():
        try: value=float(cal[key])
        except (KeyError,ValueError,TypeError): raise CompatibilityError('Invalid calibration parameter: '+key)
        if not math.isfinite(value) or not lo<=value<=hi:
            raise CompatibilityError(f'Calibration {key} outside validated bounds [{lo}, {hi}]')
        cal[key]=value
    status=cal.get('calibration_status','ASSET_SPECIFIC')
    if status not in ['ASSET_SPECIFIC','VERIFIED_COMMISSIONED','REFERENCE_CALIBRATION']:
        raise CompatibilityError('Invalid calibration status')
    if status!='REFERENCE_CALIBRATION':
        if cal.get('verified_healthy_required') is not True:
            raise CompatibilityError('Asset calibration requires independent healthy commissioning verification')
        samples=cal.get('commission_samples')
        if not isinstance(samples,(int,float)) or not math.isfinite(samples) or samples<2016 or int(samples)!=samples:
            raise CompatibilityError('Asset calibration requires >=2016 commissioning samples')
        duration=cal.get('commission_duration_minutes')
        if not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<10080:
            raise CompatibilityError('Asset calibration requires >=10080 minutes of independently verified commissioning')
        if not cal.get('asset_id'):
            raise CompatibilityError('Asset calibration requires asset_id binding')
        if asset_id and str(cal['asset_id'])!=str(asset_id):
            raise CompatibilityError('Calibration asset_id does not match telemetry asset')
        rmse=cal.get('commission_rmse_C')
        if not isinstance(rmse,(int,float)) or not math.isfinite(rmse) or rmse<0:
            raise CompatibilityError('Asset calibration requires finite nonnegative commissioning RMSE')
    cal['calibration_status']=status
    cal['bound_warnings']=list(dict.fromkeys(list(cal.get('bound_warnings',[]))+[f'{k} near {"lower" if abs(cal[k]-lo)<abs(cal[k]-hi) else "upper"} bound' for k,(lo,hi) in policy['parameter_bounds'].items() if min(abs(cal[k]-lo),abs(cal[k]-hi))<.05*(hi-lo)]))
    return cal

def commission_asset(frame,*,verified_healthy=False,**adapter_options):
    if not verified_healthy:
        raise CompatibilityError('Supply --verified-healthy only after independent verification of a separate commissioning period')
    if len(frame)<2016:
        raise CompatibilityError('At least seven complete days of healthy commissioning required (2016 five-minute samples)')
    canonical=normalize_frame(frame,**adapter_options)
    if canonical.asset_id.nunique()!=1: raise CompatibilityError('Commission exactly one asset at a time')
    config=json.loads((ROOT/'config/100kVA_config.json').read_text())
    for row in canonical.to_dict('records'):
        clean,valid,suspect=assess(row,config)
        if not valid or suspect or clean['timestamp'] is None:
            raise CompatibilityError('Commissioning requires complete plausible available sensors and valid timestamps')
    basic=canonical[SIGNALS].rename(columns=dict(zip(SIGNALS,LEGACY)))
    basic['timestamp_IST']=canonical.timestamp
    basic['replay_id']=canonical.asset_id
    # Original fit uses only measurements; no hidden truth or model weights touched.
    cal=commission(basic,'thermal_fit',verified_healthy=True)
    cal.update(asset_id=canonical.asset_id.iloc[0],rating_kva=100,calibration_status='VERIFIED_COMMISSIONED',
               commission_duration_minutes=len(basic)*5,provenance='Explicitly independently verified separate commissioning CSV')
    return validate_calibration(cal)

def resolve_calibration(calibration=None):
    if calibration is None:
        calibration=json.loads((ROOT/'calibration/reference_calibration.json').read_text())
    if isinstance(calibration,(str,Path)):
        calibration=json.loads(Path(calibration).read_text(encoding='utf-8'))
    return validate_calibration(calibration)
