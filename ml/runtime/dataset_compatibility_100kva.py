"""Explicit, causal format conversion for measured 100 kVA time series.

This layer changes input representation, never trained weights or missing sensors.
"""
from pathlib import Path
import csv, io, json, math, zipfile
import numpy as np
import pandas as pd
from .schema_adapter_100kVA import SchemaAdapter100kVA, CompatibilityError, SIGNALS, LEGACY

MAX_ROWS=300000
MAX_BYTES=100*1024*1024

def _unique_json_object(pairs):
    out={}
    for key,value in pairs:
        if key in out:raise CompatibilityError('Duplicate JSON field: '+key)
        out[key]=value
    return out

def read_table(source,filename=None,*,sheet=None,delimiter=None,decimal='.',encoding='utf-8-sig'):
    raw=source if isinstance(source,bytes) else Path(source).read_bytes()
    if len(raw)>MAX_BYTES:raise CompatibilityError('File exceeds 100 MB input limit')
    suffix=Path(filename or str(source)).suffix.lower() if not isinstance(source,bytes) or filename else '.csv'
    if suffix=='.xlsx':
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if sum(x.file_size for x in z.infolist())>300*1024*1024:raise CompatibilityError('Workbook expands beyond the supported size limit')
        try:
            book=pd.ExcelFile(io.BytesIO(raw),engine='openpyxl')
            if sheet is None and len(book.sheet_names)!=1:raise CompatibilityError('Workbook has multiple sheets; choose datasetInput.sheet explicitly')
            chosen=sheet if sheet is not None else book.sheet_names[0]
            table=pd.read_excel(book,sheet_name=chosen,header=None,nrows=MAX_ROWS+2)
        except ImportError as e:raise CompatibilityError('Excel input requires openpyxl; install project requirements') from e
        if table.empty:raise CompatibilityError('EMPTY_INPUT: workbook has no readings')
        header=table.iloc[0].tolist();frame=table.iloc[1:].copy();frame.columns=header;frame=frame.reset_index(drop=True)
    elif suffix in ['.json','.jsonl','.ndjson']:
        text=raw.decode(encoding)
        if suffix=='.json':
            value=json.loads(text,object_pairs_hook=_unique_json_object)
            if isinstance(value,dict) and set(value)=={'records'}:value=value['records']
        else:value=[json.loads(line,object_pairs_hook=_unique_json_object) for line in text.splitlines() if line.strip()]
        if not isinstance(value,list) or not all(isinstance(x,dict) for x in value):raise CompatibilityError('JSON must contain an array of row objects, a records array, or JSON Lines')
        frame=pd.DataFrame(value);header=frame.columns.tolist()
    elif suffix in ['.csv','.tsv','.txt']:
        text=raw.decode(encoding)
        if delimiter is None:
            try:delimiter=csv.Sniffer().sniff(text[:65536],delimiters=',;\t|').delimiter
            except csv.Error:delimiter='\t' if suffix=='.tsv' else ','
        if delimiter not in [',',';','\t','|']:raise CompatibilityError('Delimiter must be comma, semicolon, tab or pipe')
        header=next(csv.reader(io.StringIO(text),delimiter=delimiter),[])
        frame=pd.read_csv(io.StringIO(text),sep=delimiter,decimal=decimal,nrows=MAX_ROWS+1)
    else:raise CompatibilityError('Supported files: CSV, TSV, TXT, XLSX, JSON, JSONL, NDJSON')
    if any(pd.isna(x) or not str(x).strip() for x in header):raise CompatibilityError('Header contains empty names; use a single table with measured signal names in the first row')
    if len(set(map(str,header)))!=len(header):raise CompatibilityError('Duplicate column names; select distinct measured signals before importing')
    if frame.empty:raise CompatibilityError('EMPTY_INPUT: no reading rows')
    if len(frame)>MAX_ROWS or len(frame.columns)>1000:raise CompatibilityError('Input exceeds 300,000 rows or 1,000 columns')
    frame.columns=[str(x) for x in frame.columns]
    return frame

def prepare_dataset(frame,*,schema=None,units=None,timezone='Asia/Kolkata',asset_id=None,
                    timestamp_format=None,epoch_unit=None,sampling='strict',sort=False):
    if frame.empty:raise CompatibilityError('EMPTY_INPUT: no reading rows')
    if not isinstance(sort,bool):raise CompatibilityError('sort must be a JSON boolean, true or false')
    if timestamp_format and epoch_unit:raise CompatibilityError('Choose timestamp_format OR epoch_unit')
    if sampling not in ['strict','five_minute_last']:raise CompatibilityError('sampling must be strict or five_minute_last')
    adapter=SchemaAdapter100kVA(schema,units,timezone,asset_id)
    mapping=adapter.resolve(frame.columns)
    missing=[x for x in SIGNALS if x not in mapping]
    if missing:
        raise CompatibilityError('Required measured columns missing: '+', '.join(missing)+'. Supply schema mappings for renamed sensors. Organiser checklist/reference pairs cannot be turned into SCADA readings by inventing measurements.')
    frame=frame.copy();tc=mapping['timestamp'][0]
    if timestamp_format or epoch_unit:
        if epoch_unit and epoch_unit not in ['s','ms','us','ns']:raise CompatibilityError('epoch_unit must be s, ms, us or ns')
        try:
            ts=pd.to_datetime(pd.to_numeric(frame[tc],errors='raise'),unit=epoch_unit,utc=True,errors='raise') if epoch_unit else pd.to_datetime(frame[tc],format=timestamp_format,errors='raise')
            frame[tc]=ts.map(lambda x:x.isoformat())
        except (ValueError,TypeError) as e:raise CompatibilityError('Timestamp conversion failed; check explicit format or epoch unit') from e
    normalized=pd.DataFrame([adapter.normalize(row) for row in frame.to_dict('records')])
    if normalized.timestamp.isna().any():
        reason='No valid timestamps' if normalized.timestamp.isna().all() else 'Invalid timestamps'
        raise CompatibilityError(reason+'. Declare timestamp_format or epoch_unit explicitly; missing or ambiguous timestamps cannot be reconstructed.')
    normalized['_time']=pd.to_datetime(normalized.timestamp,utc=True)
    if normalized.duplicated(['asset_id','_time']).any():raise CompatibilityError('Duplicate asset/timestamp readings; reconcile duplicates explicitly')
    report={'input_rows':len(frame),'assets':int(normalized.asset_id.nunique()),'sampling':sampling,
            'column_mapping':{k:{'column':v[0],'unit':v[1]} for k,v in mapping.items()},
            'ignored_columns':[str(x) for x in frame.columns if x not in [v[0] for v in mapping.values()]],
            'assumptions':sorted({i for issues in normalized.issues for i in issues if 'ASSUMED' in i}),
            'warnings':[],'resampled':False,'inserted_gap_rows':0,'source_rows_combined':0,'trailing_unclosed_rows':0}
    output=[]
    for aid,group in normalized.groupby('asset_id',sort=False):
        if not group._time.is_monotonic_increasing:
            if not sort:raise CompatibilityError('Out-of-order readings; explicitly set sort=true for offline chronological import')
            group=group.sort_values('_time');report['warnings'].append('Rows explicitly sorted within asset')
        group=group.reset_index(drop=True)
        delta=group._time.diff().dropna().dt.total_seconds()
        if sampling=='strict':
            if len(delta) and not delta.mod(300).eq(0).all():raise CompatibilityError('Sampling is not aligned to five minutes. For faster measured data choose sampling=five_minute_last. Slower measurements cannot support this model without retraining.')
            if len(delta) and delta.min()>300:raise CompatibilityError('Incompatible sampling interval: measurements are coarser than five minutes; interpolation would invent thermal history. Use a model trained for this cadence.')
            if len(delta) and delta.gt(300).any():report['warnings'].append('Missing five-minute intervals retained; runtime resets/abstains as needed')
            output.append(group)
            continue
        if len(group)<2:raise CompatibilityError('Resampling requires at least two timestamped observations')
        if delta.median()>300:raise CompatibilityError('Typical sampling interval exceeds five minutes. Upsampling is unsupported.')
        start=group._time.iloc[0];end=group._time.iloc[-1]
        n=int(math.floor((end-start).total_seconds()/300))+1
        if n>MAX_ROWS:raise CompatibilityError('Resampled history exceeds row limit')
        # A bin ending at t contains only observations in (t-5 min,t]. No future
        # interpolation, no carrying measurements across an empty interval.
        bins=np.ceil((group._time-start).dt.total_seconds()/300).astype(int)
        eligible=group.assign(_bin=bins).loc[bins<n]
        latest=eligible.groupby('_bin',sort=True).tail(1).set_index('_bin')
        res=latest.reindex(range(n));gaps=res.asset_id.isna()
        res['asset_id']=str(aid);res['transformer_rating_kva']=100
        times=pd.Series(pd.date_range(start,periods=n,freq='5min'))
        res['timestamp']=times.map(lambda x:x.isoformat()).to_numpy();res['_time']=times.to_numpy()
        res.loc[gaps,'communication_available']=False
        report['inserted_gap_rows']+=int(gaps.sum());report['source_rows_combined']+=len(eligible)-len(latest)
        report['trailing_unclosed_rows']+=len(group)-len(eligible)
        output.append(res.reset_index(drop=True));report['resampled']=True
    canonical=pd.concat(output,ignore_index=True)
    if len(canonical)>MAX_ROWS:raise CompatibilityError('Converted input exceeds row limit')
    result=pd.DataFrame({'timestamp_IST':canonical.timestamp,'asset_id':canonical.asset_id,'transformer_rating_kva':100})
    for field,legacy in zip(SIGNALS,LEGACY):result[legacy]=canonical[field].to_numpy()
    result['communication_available']=canonical.communication_available.to_numpy()
    if 'loading_pct' in canonical:result['loading_pct']=canonical.loading_pct
    report['output_rows']=len(result)
    report['rows_missing_required_measurements']=int(result[LEGACY].isna().any(axis=1).sum())
    report['calibration']='Compatibility conversion does not establish healthy commissioning or field accuracy'
    if report['resampled']:report['warnings'].append('Five-minute last-observation representation may lose short transients; validate accuracy at the converted cadence')
    return result,report

def import_dataset(source,filename=None,*,dataset_input=None,**adapter_options):
    cfg=dict(dataset_input or {})
    allowed={'sheet','delimiter','decimal','encoding','timestamp_format','epoch_unit','sampling','sort'}
    if set(cfg)-allowed:raise CompatibilityError('Unknown datasetInput options: '+str(set(cfg)-allowed))
    read_keys=['sheet','delimiter','decimal','encoding']
    frame=read_table(source,filename,**{k:cfg[k] for k in read_keys if k in cfg})
    return prepare_dataset(frame,**adapter_options,**{k:v for k,v in cfg.items() if k not in read_keys})
