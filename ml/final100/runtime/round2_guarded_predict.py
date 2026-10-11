"""Offline inference for the round-two candidate; verified calibration required."""
from pathlib import Path
import argparse,json,hashlib,sys
import numpy as np
import pandas as pd
import joblib
import voltmind_tournament_runtime as vr

def calibration_issue(frame,cal):
    if not isinstance(cal,dict):return 'CALIBRATION_REQUIRED'
    if cal.get('calibration_status') not in ['VERIFIED_COMMISSIONED','ASSET_SPECIFIC'] or cal.get('verified_healthy_required') is not True:return 'VERIFIED_HEALTHY_COMMISSIONING_REQUIRED'
    if frame.replay_id.nunique()!=1 or str(cal.get('asset_id'))!=str(frame.replay_id.iloc[0]):return 'CALIBRATION_ASSET_MISMATCH'
    try:
        for key,lo,hi in [('rise',20,35),('tau',75,520),('bias',-4,4),('loss_ratio',.08,.25)]:
            value=float(cal[key])
            if not np.isfinite(value) or not lo<=value<=hi:return 'CALIBRATION_OUT_OF_RANGE'
        if int(cal.get('rating_kva',0))!=100:return 'CALIBRATION_RATING_MISMATCH'
        samples=float(cal['commission_samples']);duration=float(cal['commission_duration_minutes']);rmse=float(cal['commission_rmse_C'])
        if not np.isfinite([samples,duration,rmse]).all() or samples<2016 or samples!=int(samples) or duration<10080 or rmse<0:return 'INSUFFICIENT_COMMISSIONING_EVIDENCE'
    except (KeyError,TypeError,ValueError,OverflowError):return 'INVALID_CALIBRATION'
    return None

def predict(frame,cal,artifact):
    issue=calibration_issue(frame,cal)
    if issue:
        return pd.DataFrame({'replay_id':frame.replay_id,'timestamp_IST':frame.timestamp_IST,
          'thermal_alert':np.nan,'thermal_score_uncalibrated':np.nan,'thermal_assessable':False,'assessment_status':issue})
    out=vr.predict(frame,cal,artifact)
    out['assessment_status']=np.where(out.thermal_assessable,'ASSESSED_RESEARCH_ONLY','INSUFFICIENT_VALID_HISTORY')
    return out

def main():
    ap=argparse.ArgumentParser(description='Locked round-two research model, offline only')
    ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--calibration',type=Path);ap.add_argument('--allow-research-model',action='store_true')
    args=ap.parse_args();root=Path(__file__).resolve().parent.parent
    if not args.allow_research_model:ap.error('Review reports/OUTCOME.json and use --allow-research-model for offline evaluation')
    lock=json.loads((root/'LOCK_MANIFEST.json').read_text());path=root/lock['primary_artifact']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=lock['sha256']:raise ValueError('Model integrity failure')
    a=joblib.load(path);f=pd.read_csv(args.input)
    if 'asset_id' in f and 'replay_id' not in f:f=f.rename(columns={'asset_id':'replay_id'})
    if 'transformer_rating_kva' in f and not f.transformer_rating_kva.eq(100).all():raise ValueError('Only 100 kVA input supported')
    cal=json.loads(args.calibration.read_text()) if args.calibration else None
    if args.output.resolve()==args.input.resolve():raise ValueError('Output cannot replace input')
    out=predict(f,cal,a);args.output.parent.mkdir(parents=True,exist_ok=True);out.to_csv(args.output,index=False)
    print(json.dumps({'rows':len(out),'assessed_rows':int(out.thermal_assessable.sum()),'status_counts':out.assessment_status.value_counts().to_dict()}))

if __name__=='__main__':main()
