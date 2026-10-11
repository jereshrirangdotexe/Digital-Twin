"""Reproducible synthetic illustration only; never training/validation evidence."""
from pathlib import Path
import sys, json, math
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'ml'))
from integration100 import FinalRuntime100, locked
from intelligence import thermal_dna

OUT = ROOT/'data/demo100'
OUT.mkdir(parents=True, exist_ok=True)
ASSET = 'DEMO100_THERMAL_TWIN'
N = 4032
cal = dict(asset_id=ASSET, rise=30.0, tau=160.0, bias=0.0, loss_ratio=0.2,
           rating_kva=100, calibration_status='VERIFIED_COMMISSIONED',
           verified_healthy_required=True, mode='synthetic_known_parameters',
           commission_samples=4032, commission_duration_minutes=20160,
           provenance='SYNTHETIC DEMONSTRATION ONLY: known generator parameters; independent healthy synthetic commissioning file. Not field-verified or fitted on monitoring faults.')
rated = 100000/(math.sqrt(3)*433)
def generate(start, demonstration):
    rows=[]; base=None; previous_eq=None; extra=0.0
    alpha=math.exp(-5/cal['tau'])
    for i,stamp in enumerate(pd.date_range(start, periods=N, freq='5min', tz='Asia/Kolkata')):
        # Six-hour plateaus produce clear heating/cooling episodes without overloading.
        loading=0.35 if (i//72)%2 == 0 else 0.70
        ambient=30+0.25*math.sin(2*math.pi*i/288)
        current=loading*rated
        equilibrium=ambient+cal['rise']*(cal['loss_ratio']+(1-cal['loss_ratio'])*loading**2)**0.8
        base=equilibrium if base is None else alpha*base+(1-alpha)*previous_eq
        previous_eq=equilibrium
        # One controlled excess-heating interval; gradual onset and recovery, no fake sensor jumps.
        target=11.0 if demonstration and 8*288 <= i < 11*288 else 0.0
        extra=alpha*extra+(1-alpha)*target
        oil=base+extra+0.035*math.sin(i*0.31)
        level=0.5+(190*0.000725*(oil-20))/30+0.00008*math.sin(i*.19)
        rows.append(dict(replay_id=ASSET,timestamp_IST=stamp.isoformat(),
            VR_V=433/math.sqrt(3),VY_V=433/math.sqrt(3),VB_V=433/math.sqrt(3),
            IR_A=current,IY_A=current,IB_A=current,ambient_temp_C=ambient,top_oil_temp_C=oil,
            communication_available=1,oil_level_fraction=level,oil_level_sensor_available=1,
            terminal_R_surface_temp_C=ambient+current**2*0.00009+0.03*math.sin(i*.21),terminal_sensor_available=1,
            transformer_rating_kva=100,data_origin='SYNTHETIC_JUDGE_DEMONSTRATION_NOT_FIELD_DATA'))
    return pd.DataFrame(rows)

demo=generate('2026-02-01',True)
commission=generate('2025-12-01',False)
demo.to_csv(OUT/'100kVA_THERMAL_TWIN_DEMO_4032.csv',index=False,float_format='%.8f')
commission.to_csv(OUT/'independent_healthy_synthetic_commissioning_4032.csv',index=False,float_format='%.8f')
_, commissioned_context = locked.vr.features(commission,cal)
cal['commission_rmse_C'] = float(np.sqrt(np.mean((commission.top_oil_temp_C-commissioned_context.expected_oil_C)**2)))
(OUT/'calibration.json').write_text(json.dumps({ASSET:cal},indent=2))
runtime=FinalRuntime100({ASSET:cal});runtime.bind(demo.to_dict('records'))
outputs=runtime.outputs
thermal=[i for i,p in enumerate(outputs) if p['ml']['thermalAlert'] is True]
healthy=[p for p in outputs[:8*288] if p['quality']['thermalAssessable']]
assert len(demo)==4032 and not demo.isna().any().any()
assert all(p['ml']['thermalAlert'] is False for p in healthy)
assert thermal and min(thermal)>=8*288
assert all(p['ml']['thermalAlert'] is False for p in outputs[-288:])
assert not any(p['ml']['assetCondition']=='SENSOR_SUSPECT' for p in outputs)
assert not any(p['ml'][k] is True for p in outputs for k in ['phaseLoadingWarning','undervoltageWarning','imbalanceWarning','oilAlert','terminalAlert'])
episodes=thermal_dna(outputs[:8*288])
assert len(episodes['episodes'])>=3
report=dict(rows=N,intervalMinutes=5,days=14,asset=ASSET,synthetic=True,
    normalAssessedRowsBeforeInjectedEvent=len(healthy),healthyResponseEpisodes=len(episodes['episodes']),
    firstThermalAlert=outputs[min(thermal)]['timestamp'],thermalAlertRows=len(thermal),
    lastDayThermalAlerts=0,unassessedRows=sum(not p['quality']['thermalAssessable'] for p in outputs),
    modelVersion=outputs[-1]['ml']['modelVersion'],modelSHA256=outputs[-1]['modelSHA256'],
    limitation='Idealized matched-physics synthetic illustration. This is not an untouched evaluation dataset or evidence of field accuracy.')
(OUT/'validation.json').write_text(json.dumps(report,indent=2))
(OUT/'chapters.json').write_text(json.dumps([
    {'dates':'1–8 February 2026','story':'Healthy load-response: actual follows expected as loading alternates 35% / 70%.'},
    {'dates':'9–11 February 2026','story':'Injected excess heating: actual separates from expected; observe the unchanged detector.'},
    {'dates':'12–14 February 2026','story':'Injected heat removed: gradual cooling and detector recovery.'},
],indent=2))
print(json.dumps(report,indent=2))
