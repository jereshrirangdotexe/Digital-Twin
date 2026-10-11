"""Normalize an external sensor file and optionally run the existing locked model."""
from pathlib import Path
import argparse,json
import pandas as pd
from runtime.dataset_compatibility_100kva import import_dataset
from runtime.run_voltmind_100kVA import predict_batch,flat_result

def main():
    ap=argparse.ArgumentParser(description='100 kVA measured-dataset compatibility and offline prediction')
    ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--settings',type=Path,help='JSON with schema, units, timezone, asset_id and datasetInput')
    ap.add_argument('--predictions',type=Path);ap.add_argument('--calibration',type=Path)
    args=ap.parse_args()
    try:
        cfg=json.loads(args.settings.read_text(encoding='utf-8')) if args.settings else {}
        allowed={'schema','units','timezone','asset_id','datasetInput'}
        if not isinstance(cfg,dict) or set(cfg)-allowed:raise ValueError('Settings allow only schema, units, timezone, asset_id and datasetInput')
        dests=[args.output,args.output.with_suffix('.compatibility.json')]+([args.predictions] if args.predictions else [])
        if len(set(p.resolve() for p in dests))!=len(dests) or args.input.resolve() in [p.resolve() for p in dests]:raise ValueError('Output paths must be distinct and cannot overwrite input')
        frame,report=import_dataset(args.input,dataset_input=cfg.pop('datasetInput',None),**cfg)
        for p in dests:p.parent.mkdir(parents=True,exist_ok=True)
        frame.to_csv(args.output,index=False)
        if args.predictions:
            results=predict_batch(frame,args.calibration)
            pd.DataFrame([flat_result(r) for r in results]).to_csv(args.predictions,index=False)
            report['assessable_prediction_rows']=sum(r['thermalAssessable'] for r in results)
            report['reference_calibration_warning']=args.calibration is None
        args.output.with_suffix('.compatibility.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({'processed_rows':len(frame),'normalized_csv':str(args.output),'report':str(args.output.with_suffix('.compatibility.json'))}))
    except (ValueError,OSError,KeyError) as e:ap.exit(2,'Dataset compatibility error: '+str(e)+'\n')

if __name__=='__main__':main()
