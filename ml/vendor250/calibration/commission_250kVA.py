"""Explicit verified healthy commissioning; never harvests organizer prefixes."""
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import pandas as pd
from scipy.optimize import least_squares

ROOT=Path(__file__).resolve().parents[1]
def commission(frame,verified_healthy=False,provenance=''):
 if not verified_healthy:raise ValueError('VERIFIED_HEALTHY_ATTESTATION_REQUIRED')
 if not provenance.strip():raise ValueError('INDEPENDENT_HEALTHY_PROVENANCE_REQUIRED')
 if len(frame)<288:raise ValueError('COMMISSIONING_INSUFFICIENT_ROWS')
 if frame.asset_id.nunique()!=1:raise ValueError('COMMISSIONING_REQUIRES_ONE_ASSET')
 times=pd.to_datetime(frame.timestamp,utc=True)
 if not times.diff().iloc[1:].eq(pd.Timedelta(minutes=5)).all():raise ValueError('COMMISSIONING_REQUIRES_REGULAR_FIVE_MINUTES')
 duration=(times.iloc[-1]-times.iloc[0]).total_seconds()/60
 if duration<1440:raise ValueError('COMMISSIONING_REQUIRES_ONE_DAY')
 names=['voltage_r_v','voltage_y_v','voltage_b_v','current_r_a','current_y_a','current_b_a','ambient_temp_c','top_oil_temp_c']
 x=frame[names].to_numpy(float)
 if not np.isfinite(x).all() or not frame.communication_available.eq(True).all():raise ValueError('COMMISSIONING_REQUIRES_COMPLETE_VALID_SIGNALS')
 if np.ptp(np.mean(x[:,3:6],axis=1))<30:raise ValueError('COMMISSIONING_INSUFFICIENT_LOAD_EXCITATION')
 ref=json.loads((ROOT/'calibration/reference_calibration.json').read_text());vn=433/np.sqrt(3);ir=250000/(np.sqrt(3)*433)
 loss=280*np.mean((x[:,:3]/vn)**2,axis=1)+2200*np.mean((x[:,3:6]/ir)**2,axis=1)
 def simulate(params):
  rise,tau,bias=params;eq=x[:,6]+rise*(loss/2480)**.8+bias;state=np.empty(len(x));state[0]=x[0,7]
  a=np.exp(-5/tau)
  for k in range(1,len(x)):state[k]=eq[k-1]+(state[k-1]-eq[k-1])*a
  return state
 fit=least_squares(lambda p:simulate(p)[72:]-x[72:,7],[33,155.5312164077913,0],bounds=([20,80,-5],[45,600,5]))
 rmse=float(np.sqrt(np.mean((simulate(fit.x)[72:]-x[72:,7])**2)))
 bounds=[]
 for name,value,lo,hi in zip(['rise_K','tau_min','bias_C'],fit.x,[20,80,-5],[45,600,5]):
  if min(value-lo,hi-value)<.01*(hi-lo):bounds.append('BOUND_NEAR:'+name)
 result=dict(ref,status='VERIFIED_COMMISSIONED',rise_K=float(fit.x[0]),tau_min=float(fit.x[1]),bias_C=float(fit.x[2]),rmse_C=rmse,sample_count=len(x),duration_min=duration,bound_warnings=bounds,verified_healthy=True,provenance=provenance,asset_id=str(frame.asset_id.iloc[0]),valid=bool(fit.success and rmse<=3 and not bounds))
 if not result['valid']:result['status']='INVALID'
 return result

def main():
 from runtime.input_adapter_250kVA import InputAdapter250kVA
 parser=argparse.ArgumentParser();parser.add_argument('--input',required=True);parser.add_argument('--output',required=True);parser.add_argument('--verified-healthy',action='store_true');parser.add_argument('--provenance',required=True);args=parser.parse_args()
 adapter=InputAdapter250kVA();frame=pd.DataFrame([adapter.normalize(row) for row in pd.read_csv(args.input).to_dict('records')])
 result=commission(frame,args.verified_healthy,args.provenance);result['source_sha256']=hashlib.sha256(Path(args.input).read_bytes()).hexdigest();Path(args.output).write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
if __name__=='__main__':main()
