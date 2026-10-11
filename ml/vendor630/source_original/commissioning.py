"""Optional explicit commissioning from separately declared verified-healthy observations.
The declaration is the caller's responsibility; this tool cannot verify asset health.
"""
from pathlib import Path
import json,csv,sys
import numpy as np
from scipy.optimize import least_squares
from input_adapter import InputAdapter
from thermal_model import step,rated_current
def commission(input_path,output_path,asset_id,verified_healthy=False,tz=None):
    if not verified_healthy:raise ValueError('Commissioning requires an explicit verified-healthy declaration')
    c=json.loads((Path(__file__).parent/'config/transformer_config.json').read_text());adapter=InputAdapter(tz=tz,asset_id=asset_id)
    with open(input_path,encoding='utf-8-sig',newline='') as f:rows=[adapter.normalize(r) for r in csv.DictReader(f)]
    if len(rows)<1000:raise ValueError('At least 1000 valid observations over seven days are required')
    if any(r['_problems'] or r['communication_available'] is False for r in rows):raise ValueError('Commissioning data must have valid required measurements and communication')
    if len({r['asset_id'] for r in rows})!=1:raise ValueError('Commission only one asset at a time')
    intervals=np.array([(rows[i]['_dt']-rows[i-1]['_dt']).total_seconds()/60 for i in range(1,len(rows))])
    if intervals.sum()<7*1440 or np.any(intervals<=0) or np.any(intervals>30):raise ValueError('Seven days of chronological history with gaps <=30 minutes required')
    load=np.array([np.sqrt(np.mean([r[k]**2 for k in ['IR_A','IY_A','IB_A']]))/rated_current(c) for r in rows]);ambient=np.array([r['ambient_temp_C'] for r in rows]);oil=np.array([r['top_oil_temp_C'] for r in rows])
    if np.quantile(load,.9)-np.quantile(load,.1)<.25:raise ValueError('Insufficient loading diversity to identify dynamics')
    def residual(params):
        cfg={**c,'nominal_top_oil_rise_K':params[0],'tau_heat_min':params[1],'tau_cool_min':params[2]};temp=params[3];pred=[temp]
        for i,dt in enumerate(intervals):temp=step(temp,ambient[i],load[i],dt,cfg);pred.append(temp)
        return np.array(pred)-oil
    fit=least_squares(residual,[50,240,300,oil[0]],bounds=([42,140,180,-20],[60,420,540,160]),max_nfev=100,loss='soft_l1')
    err=residual(fit.x);rmse=float(np.sqrt(np.mean(err**2)));p95=float(np.quantile(np.abs(err),.95))
    if not fit.success or rmse>3 or p95>6:raise ValueError('Calibration fit failed diagnostic limits')
    result=dict(type='DECLARED_VERIFIED_HEALTHY_COMMISSIONING',assets={asset_id:dict(validated=True,rating_kva=630,nominal_top_oil_rise_K=float(fit.x[0]),tau_heat_min=float(fit.x[1]),tau_cool_min=float(fit.x[2]),oil_exponent=.8,source=str(Path(input_path).name),health_verified_by='Caller declaration, not inferred by VoltMind',fit_diagnostics=dict(rmse_C=rmse,p95_absolute_error_C=p95,samples=len(rows),minutes=float(intervals.sum()),load_10_90_span=float(np.quantile(load,.9)-np.quantile(load,.1))),uncertainty='Fit diagnostics only, no guaranteed transfer or statistical confidence interval')})
    Path(output_path).write_text(json.dumps(result,indent=2));return result
