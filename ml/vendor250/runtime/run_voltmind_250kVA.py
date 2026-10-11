"""Organizer CLI, batch/stream, stable JSON and completion accounting."""
from pathlib import Path
import argparse,csv,json,hashlib,sys
import pandas as pd
from .streaming_runtime_250kVA import DigitalTwinMLRuntime250kVA
from .input_adapter_250kVA import CompatibilityError,InputAdapter250kVA
from .frontend_adapter_250kVA import to_frontend_payload,to_history

def read_csv(path,delimiter=None,encoding='utf-8-sig',decimal='.'):
 with Path(path).open(encoding=encoding,newline='') as file:
  sample=file.read(8192);file.seek(0)
  if not sample.strip():raise CompatibilityError('EMPTY_FILE','No SCADA content')
  if delimiter is None:
   try:delimiter=csv.Sniffer().sniff(sample,delimiters=',;\t|').delimiter
   except csv.Error:raise CompatibilityError('CSV_DELIMITER_UNRESOLVED','Use --delimiter for this CSV format')
  headers=next(csv.reader(file,delimiter=delimiter),[])
 if not headers:raise CompatibilityError('EMPTY_FILE','SCADA CSV requires a header and rows')
 if len(headers)!=len(set(headers)):raise CompatibilityError('DUPLICATE_COLUMN_NAME','CSV headers must be unique')
 try:frame=pd.read_csv(path,sep=delimiter,encoding=encoding,decimal=decimal)
 except pd.errors.EmptyDataError:raise CompatibilityError('EMPTY_FILE','No SCADA rows')
 if frame.empty:raise CompatibilityError('EMPTY_INPUT','No SCADA rows to assess')
 return frame

def completeness(rows,results):
 assets={r['assetId'] for r in results};return dict(expectedRows=len(rows),processedRows=len(results),failedRows=sum(r['failed'] for r in results),unassessedRows=sum(r['thermalState']=='THERMAL_UNASSESSED' for r in results),expectedGroups=sorted(assets),processedGroups=sorted(assets),missingGroups=[],diagnosticCounts=pd.Series([d.split(':')[0] for r in results for d in r['diagnostics']],dtype='str').value_counts().to_dict())

def main():
 parser=argparse.ArgumentParser(description='Locked 250-kVA SCADA to Digital Twin and frontend JSON')
 for name in ['input','output']:parser.add_argument('--'+name,required=True)
 for name in ['schema','units','calibration','commissioning','commissioning-provenance','frontend-output','history-output','report','state-in','state-out']:parser.add_argument('--'+name)
 parser.add_argument('--asset-id',default='ORGANIZER_ASSET_001');parser.add_argument('--timezone',default='Asia/Kolkata');parser.add_argument('--timestamp-unit',choices=['s','ms','us','ns']);parser.add_argument('--dayfirst',action='store_true',default=None);parser.add_argument('--monthfirst',action='store_true');parser.add_argument('--voltage-basis',default='phase_neutral');parser.add_argument('--verified-healthy',action='store_true');parser.add_argument('--stream',action='store_true')
 parser.add_argument('--delimiter');parser.add_argument('--encoding',default='utf-8-sig');parser.add_argument('--decimal',default='.')
 args=parser.parse_args();report_path=Path(args.report or str(args.output)+'.report.json')
 try:
  frame=read_csv(args.input,args.delimiter,args.encoding,args.decimal);rows=frame.to_dict('records');schema=json.loads(Path(args.schema).read_text()) if args.schema else None;units=json.loads(Path(args.units).read_text()) if args.units else None
  options=dict(schema=schema,units=units,asset_id=args.asset_id,timezone=args.timezone,dayfirst=False if args.monthfirst else args.dayfirst,timestamp_unit=args.timestamp_unit,voltage_basis=args.voltage_basis)
  calibration=args.calibration
  if args.commissioning:
   if args.calibration:raise CompatibilityError('CALIBRATION_ARGUMENT_CONFLICT','Provide calibration or verified commissioning, not both')
   if Path(args.input).resolve()==Path(args.commissioning).resolve() or hashlib.sha256(Path(args.input).read_bytes()).digest()==hashlib.sha256(Path(args.commissioning).read_bytes()).digest():raise CompatibilityError('COMMISSIONING_NOT_SEPARATE','Organizer input cannot commission itself')
   from calibration.commission_250kVA import commission
   adapter=InputAdapter250kVA(**options);cf=pd.DataFrame([adapter.normalize(row) for row in read_csv(args.commissioning,args.delimiter,args.encoding,args.decimal).to_dict('records')]);calibration=commission(cf,args.verified_healthy,args.commissioning_provenance or '')
   if not calibration['valid']:raise CompatibilityError('COMMISSIONING_INVALID','Fit is invalid; see calibration diagnostics')
  runtime=DigitalTwinMLRuntime250kVA(calibration=calibration,**options)
  if args.state_in:runtime.load_state(args.state_in)
  results=[runtime.update(row) for row in rows] if args.stream else runtime.predict_batch(rows)
  output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
  if output.suffix.lower()=='.json':output.write_text(json.dumps(results,indent=2,allow_nan=False),encoding='utf-8')
  elif output.suffix.lower()=='.jsonl':output.write_text('\n'.join(json.dumps(r,allow_nan=False) for r in results)+'\n',encoding='utf-8')
  else:pd.json_normalize(results).to_csv(output,index=False)
  if args.frontend_output:Path(args.frontend_output).write_text('\n'.join(json.dumps(to_frontend_payload(r),allow_nan=False) for r in results)+'\n',encoding='utf-8')
  if args.history_output:Path(args.history_output).write_text(json.dumps(to_history(results),allow_nan=False),encoding='utf-8')
  if args.state_out:runtime.save_state(args.state_out)
  report=dict(status='CONDITIONAL_PASS' if any(r['thermalState']=='THERMAL_UNASSESSED' or r['failed'] for r in results) else 'PASS',modelLocked=True,modelVersion=runtime.config['modelVersion'],**completeness(rows,results))
  report_path.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8');print(json.dumps(report))
  return 0
 except (CompatibilityError,ValueError,OSError,KeyError) as exc:
  error={'status':'FAIL_SAFE','error':str(exc),'code':getattr(exc,'code',type(exc).__name__)};report_path.parent.mkdir(parents=True,exist_ok=True);report_path.write_text(json.dumps(error,indent=2),encoding='utf-8');print(json.dumps(error),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
