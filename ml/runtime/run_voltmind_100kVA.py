"""Batch uses the same state transition as streaming, then vectorized locked scoring."""
import argparse,json,csv
from pathlib import Path
import pandas as pd
from .streaming_runtime_100kVA import DigitalTwinMLRuntime100kVA
from .decision import decision_margin
from .input_adapter_100kVA import read_csv
from .frontend_adapter_100kVA import to_frontend_payload,to_history_point
from calibration.commission_100kVA import commission_asset

def predict_batch(frame,calibration=None,**options):
    runtime=DigitalTwinMLRuntime100kVA(calibration,**options)
    if frame.empty: raise ValueError('EMPTY_INPUT: no rows')
    results=[];features=[];indices=[]
    for index,row in enumerate(frame.to_dict('records')):
        result=runtime._update(row,score=False)
        if '_features' in result:
            features.append(result.pop('_features'));indices.append(index)
        results.append(result)
    if features:
        margins=decision_margin(runtime.artifact,pd.DataFrame(features,columns=runtime.artifact['features']))
        for index,margin in zip(indices,margins): runtime.apply_margin(results[index],float(margin))
    return results

def flat_result(r):
    out={k:v for k,v in r.items() if k not in ['telemetry','calibration']}
    out.update(r['telemetry'])
    out['qualityIssues']=json.dumps(out['qualityIssues'])
    return out

def main():
    ap=argparse.ArgumentParser(description='Frozen 100-kVA model; batch CSV + frontend JSONL')
    ap.add_argument('--input',required=True,type=Path);ap.add_argument('--output',required=True,type=Path)
    g=ap.add_mutually_exclusive_group();g.add_argument('--calibration',type=Path);g.add_argument('--commissioning',type=Path)
    ap.add_argument('--verified-healthy',action='store_true')
    ap.add_argument('--schema',type=Path);ap.add_argument('--units',type=Path);ap.add_argument('--asset-id');ap.add_argument('--timezone',default='Asia/Kolkata')
    ap.add_argument('--frontend-output',type=Path);ap.add_argument('--history-output',type=Path);ap.add_argument('--commissioning-output',type=Path)
    args=ap.parse_args()
    options=dict(schema=json.loads(args.schema.read_text()) if args.schema else None,units=json.loads(args.units.read_text()) if args.units else None,timezone=args.timezone,asset_id=args.asset_id)
    try:
        cal=args.calibration
        if args.commissioning:
            cal=commission_asset(read_csv(args.commissioning),verified_healthy=args.verified_healthy,**options)
            if args.commissioning_output: args.commissioning_output.write_text(json.dumps(cal,indent=2,allow_nan=False))
        results=predict_batch(read_csv(args.input),cal,**options)
        pd.DataFrame([flat_result(r) for r in results]).to_csv(args.output,index=False)
        for output,adapter in [(args.frontend_output,to_frontend_payload),(args.history_output,to_history_point)]:
            if output:
                with output.open('w',encoding='utf-8') as f:
                    for result in results: f.write(json.dumps(adapter(result),allow_nan=False)+'\n')
        print(json.dumps(dict(processed_rows=len(results),failed_rows=0,unassessed_rows=sum(not r['thermalAssessable'] for r in results),assets=len({r['assetId'] for r in results}),calibration_status=results[0]['calibrationStatus'])))
    except (ValueError,FileNotFoundError,KeyError) as error:
        ap.exit(2,'VoltMind compatibility/configuration error: '+str(error)+'\n')

if __name__=='__main__': main()
