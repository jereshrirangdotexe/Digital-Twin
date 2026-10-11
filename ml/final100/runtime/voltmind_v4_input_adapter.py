"""Explicit schema/unit boundary for the frozen V4 LR model. No guessed sensors."""
from pathlib import Path
import argparse,json,re
import numpy as np
import pandas as pd
import voltmind_v4_lr_runtime as rt
from voltmind_v4_table_reader import read_table, CompatibilityError

def norm(x):return re.sub(r'[^a-z0-9]','',str(x).lower())
ALIASES={
 'replay_id':['replay_id','asset_id','transformer_id'],
 'timestamp_IST':['timestamp_IST','timestamp','datetime','date_time','reading_time'],
 'transformer_rating_kva':['transformer_rating_kva','rating_kva'],
 'ambient_temp_C':['ambient_temp_C','ambient_temperature','ambient_temp','Tamb'],
 'top_oil_temp_C':['top_oil_temp_C','top_oil_temperature','top_oil_temp','Toil'],
 'oil_level_fraction':['oil_level_fraction','oil_level','oil_level_pct','oil_level_percent'],
 'terminal_R_surface_temp_C':['terminal_R_surface_temp_C','terminal_r_temperature','lv_terminal_r_temp'],
 'communication_available':['communication_available','comm_available','online'],
 'oil_level_sensor_available':['oil_level_sensor_available'],
 'terminal_sensor_available':['terminal_sensor_available'],
}
for phase in 'RYB':
    ALIASES[f'V{phase}_V']=[f'V{phase}_V',f'V{phase}',f'voltage_{phase.lower()}',f'{phase}_voltage',f'voltage_{phase.lower()}_v']
    ALIASES[f'I{phase}_A']=[f'I{phase}_A',f'I{phase}',f'current_{phase.lower()}',f'{phase}_current',f'current_{phase.lower()}_a']
NUMERIC=rt.vr.RAW+['oil_level_fraction','terminal_R_surface_temp_C']
UNITS={c:('V' if c in rt.vr.RAW[:3] else 'A' if c in rt.vr.RAW[3:6] else 'fraction' if c=='oil_level_fraction' else 'C') for c in NUMERIC}

def variants(field):
    out={}
    for alias in ALIASES[field]:
        unit=UNITS.get(field)
        explicit=(alias.lower().endswith(('_v','_a','_c','_fraction','_pct','_percent')))
        if alias.lower().endswith(('_pct','_percent')):unit='%'
        out[norm(alias)]=(unit if explicit else None)
        if field in NUMERIC:
            stem=re.sub(r'_(?:V|A|C|fraction|pct|percent)$','',alias,flags=re.I)
            suffixes=['V','kV'] if UNITS[field]=='V' else ['A','mA','kA'] if UNITS[field]=='A' else ['fraction','pct','percent'] if UNITS[field]=='fraction' else ['C','F','K']
            for suffix in suffixes:out[norm(stem+'_'+suffix)]='%' if suffix in ['pct','percent'] else suffix
    return out

def convert(v,unit,field):
    v=pd.to_numeric(v,errors='coerce').replace([np.inf,-np.inf],np.nan)
    kind=UNITS[field]
    if kind=='V' and unit in ['V','kV']:return v*(1000 if unit=='kV' else 1)
    if kind=='A' and unit in ['A','mA','kA']:return v*{'A':1,'mA':.001,'kA':1000}[unit]
    if kind=='C' and unit in ['C','F','K']:return (v-32)*5/9 if unit=='F' else v-273.15 if unit=='K' else v
    if kind=='fraction' and unit in ['fraction','%','percent','pct']:return v/100 if unit in ['%','percent','pct'] else v
    raise CompatibilityError(f'Unsupported unit {unit!r} for {field}')

def adapt(frame,config=None):
    config=dict(config or {});allowed={'schema','units','timezone','timestamp_format','epoch_unit','asset_id','sort','rating_kva'}
    if set(config)-allowed:raise CompatibilityError('Unknown adapter options: '+str(sorted(set(config)-allowed)))
    schema=config.get('schema',{});units=config.get('units',{})
    if not isinstance(schema,dict) or not isinstance(units,dict):raise CompatibilityError('schema and units must be objects')
    if set(schema)-set(ALIASES) or set(units)-set(NUMERIC):raise CompatibilityError('Unknown canonical fields in mapping/units')
    if config.get('sort',False) not in [True,False]:raise CompatibilityError('sort must be boolean')
    if config.get('timestamp_format') and config.get('epoch_unit'):raise CompatibilityError('Use timestamp_format OR epoch_unit')
    if frame.empty or frame.columns.duplicated().any() or any(not str(c).strip() for c in frame):raise CompatibilityError('Nonempty table with unique nonblank headers required')
    mappings={};inferred={}
    for field in ALIASES:
        opts=variants(field)
        matches=[schema[field]] if field in schema else [c for c in frame if norm(c) in opts]
        if len(matches)>1:raise CompatibilityError(f'Ambiguous {field}: {matches}; select an exact column in schema')
        if matches:
            source=matches[0]
            if source not in frame:raise CompatibilityError(f'Mapped column {source!r} missing')
            mappings[field]=source;inferred[field]=opts.get(norm(source))
    if len(set(mappings.values()))!=len(mappings):raise CompatibilityError('A column cannot represent two physical signals')
    if 'timestamp_IST' not in mappings:raise CompatibilityError('No timestamped measurements found; organiser reference/checklist is not a SCADA history')
    out=pd.DataFrame(index=range(len(frame)));issues=[[] for _ in range(len(frame))];frame=frame.reset_index(drop=True)
    for field in NUMERIC:
        if field not in mappings:
            out[field]=np.nan
            for i in issues:i.append('MISSING_COLUMN:'+field)
            continue
        unit=units.get(field,inferred[field])
        if unit is None:raise CompatibilityError(f'Unit required for {field} ({mappings[field]}); add units mapping')
        out[field]=convert(frame[mappings[field]],unit,field)
        bad=out[field].isna()&frame[mappings[field]].notna()
        for i in np.flatnonzero(bad):issues[i].append('INVALID_NUMBER:'+field)
    for field in ['communication_available','oil_level_sensor_available','terminal_sensor_available']:
        if field in mappings:
            raw=frame[mappings[field]]
            def flag(v):
                if isinstance(v,(bool,np.bool_)):return int(v)
                if str(v).strip().lower() in ['1','true','yes','online']:return 1
                if str(v).strip().lower() in ['0','false','no','offline']:return 0
                return np.nan
            parsed=raw.map(flag);out[field]=parsed.fillna(0).astype(int)
            for i in np.flatnonzero(parsed.isna()):issues[i].append('INVALID_AVAILABILITY:'+field)
    raw=frame[mappings['timestamp_IST']];stamps=[]
    for value in raw:
        try:
            if pd.isna(value):raise ValueError('missing timestamp')
            if config.get('epoch_unit'):
                if config['epoch_unit'] not in ['s','ms','us','ns']:raise ValueError('unsupported epoch unit')
                timestamp=pd.to_datetime(float(value),unit=config['epoch_unit'],utc=True)
            else:
                if isinstance(value,(int,float,np.integer,np.floating)) or re.fullmatch(r'\d{10,19}',str(value).strip()):raise ValueError('numeric epoch requires explicit epoch_unit')
                if not config.get('timestamp_format') and re.match(r'^\d{1,2}[/-]\d{1,2}[/-]\d{4}',str(value)):raise ValueError('day/month date requires explicit timestamp_format')
                timestamp=pd.Timestamp(pd.to_datetime(value,format=config['timestamp_format'],errors='raise')) if config.get('timestamp_format') else pd.Timestamp(value)
                if timestamp.tzinfo is None:
                    if not config.get('timezone'):raise ValueError('naive timestamp requires explicit timezone')
                    timestamp=timestamp.tz_localize(config['timezone'],ambiguous='raise',nonexistent='raise')
            if pd.isna(timestamp):raise ValueError('invalid timestamp')
            stamps.append(timestamp.tz_convert('UTC'))
        except (ValueError,TypeError,OverflowError) as e:raise CompatibilityError('Timestamp rejected: '+str(e)) from e
    out['timestamp_IST']=[x.isoformat() for x in stamps]
    if 'replay_id' in mappings:
        ids=frame[mappings['replay_id']]
        if ids.isna().any() or ids.astype(str).str.strip().eq('').any():raise CompatibilityError('Blank asset identifier')
        out['replay_id']=ids.astype(str).str.strip()
        if config.get('asset_id') and not out.replay_id.eq(str(config['asset_id'])).all():raise CompatibilityError('Asset override conflicts with input identifiers')
    elif config.get('asset_id'):out['replay_id']=str(config['asset_id'])
    else:raise CompatibilityError('No asset identifier; supply asset_id explicitly')
    if 'transformer_rating_kva' in mappings:
        rating=pd.to_numeric(frame[mappings['transformer_rating_kva']],errors='coerce')
        if not rating.eq(100).all():raise CompatibilityError('Rating mismatch: 100 kVA only')
    elif float(config.get('rating_kva',100))!=100:raise CompatibilityError('Rating mismatch: 100 kVA only')
    out['transformer_rating_kva']=100
    if out.duplicated(['replay_id','timestamp_IST']).any():raise CompatibilityError('Duplicate asset timestamps; resolve conflicts explicitly')
    out['_input_row']=np.arange(len(out));out['_issues']=[';'.join(i) for i in issues]
    segments=np.zeros(len(out),dtype=int);segment_n=0;gap_count=0
    for asset,g in out.groupby('replay_id',sort=False):
        ts=pd.to_datetime(g.timestamp_IST,utc=True)
        if config.get('sort',False):
            order=ts.sort_values(kind='stable').index;g=g.loc[order];ts=ts.loc[order]
        delta=ts.diff().dt.total_seconds();d=delta.iloc[1:]
        if (d<=0).any():raise CompatibilityError('Out-of-order readings; sorting requires explicit sort=true')
        if ((d<300)|((d%300)!=0)).any():raise CompatibilityError('Sampling incompatible with five-minute model; no automatic resampling')
        cuts=delta.isna()|delta.gt(300);local=cuts.cumsum().astype(int)+segment_n
        segments[g.index]=local;segment_n=int(local.max());gap_count+=int(delta.gt(300).sum())
    out['_segment']=segments
    # Physical validity is handled by the locked normalizer; record every masked reading.
    for _,g in out.groupby(['replay_id','_segment'],sort=False):
        g=g.sort_values('timestamp_IST',kind='stable')
        normalized=rt.normalize(g)
        for c in NUMERIC:
            bad=g[c].notna().to_numpy()&normalized[c].isna().to_numpy()
            for ix in g.index[bad]:out.at[ix,'_issues']+=';INVALID_OR_UNAVAILABLE:'+c
    used=set(mappings.values());audit={'rows':len(out),'assets':out.replay_id.nunique(),'segments':segment_n,'gaps_reset':gap_count,
      'schema':mappings,'resolved_units':{f:units.get(f,inferred.get(f)) for f in NUMERIC if f in mappings},
      'ignored_columns':[str(c) for c in frame if c not in used],'missing_measurements':[f for f in NUMERIC if f not in mappings],
      'sorting_explicitly_enabled':config.get('sort',False),'synthetic_rows_inserted':0,'interpolation_performed':False,
      'rows_with_input_issues':int(out._issues.str.strip(';').ne('').sum())}
    return out,audit

def predict_table(frame,bundle,calibrations=None,config=None):
    f,audit=adapt(frame,config);outputs=[];calibrations=dict(calibrations or {})
    for (asset,segment),g in f.groupby(['replay_id','_segment'],sort=False):
        g=g.sort_values('timestamp_IST',kind='stable').reset_index(drop=True)
        out=rt.predict(g,calibrations.get(asset),bundle)
        # Low-voltage readings that also match unconverted kV cannot safely be classified.
        suspect=(g[rt.vr.RAW[:3]].gt(0)&g[rt.vr.RAW[:3]].lt(10)).any(axis=1)
        # Reset history around suspect readings; do not let plausible unit errors affect later thermal state.
        if suspect.any():
            g.loc[suspect,rt.vr.RAW[:3]]=np.nan;out=rt.predict(g,calibrations.get(asset),bundle)
            out.loc[suspect,'thermal_status']='VOLTAGE_SCALE_OR_EXTREME_LOW_VOLTAGE_REVIEW_REQUIRED'
        out['input_row']=g._input_row;out['history_segment']=segment;out['input_issues']=g._issues.str.strip(';')
        out.loc[suspect,'input_issues']=out.loc[suspect,'input_issues'].str.cat(pd.Series(['VOLTAGE_SCALE_REVIEW']*int(suspect.sum()),index=out.index[suspect]),sep=';')
        outputs.append(out)
    result=pd.concat(outputs,ignore_index=True).sort_values('input_row',kind='stable').reset_index(drop=True)
    audit['assessment_counts']={task:{'assessed':int(result[task+'_assessable'].sum()),'total':len(result)} for task in ['thermal','oil','terminal']}
    audit['voltage_scale_review_rows']=int(result.input_issues.str.contains('VOLTAGE_SCALE_REVIEW').sum())
    return result,audit

def main():
    ap=argparse.ArgumentParser(description='Hardened offline V4 LR importer. Explicit schema, units and timestamp contract.')
    for name in ['input','output']:ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--config',type=Path);ap.add_argument('--calibrations',type=Path);ap.add_argument('--sheet');ap.add_argument('--decimal',default='.')
    args=ap.parse_args();root=Path(__file__).resolve().parent.parent
    audit_path=args.output.with_suffix('.audit.json')
    inputs=[args.input,args.config,args.calibrations,root/'models/100kVA_LR_V4_LOCKED.joblib',root/'LOCK_MANIFEST.json']
    if any(p and p.resolve() in [args.output.resolve(),audit_path.resolve()] for p in inputs):raise CompatibilityError('Output cannot overwrite an input or model/config file')
    if args.output.exists() or audit_path.exists():raise CompatibilityError('Output already exists; choose a new path')
    config=json.loads(args.config.read_text()) if args.config else None
    calibrations=json.loads(args.calibrations.read_text()) if args.calibrations else None
    frame=read_table(args.input,sheet=args.sheet,decimal=args.decimal)
    result,audit=predict_table(frame,rt.load_locked(root),calibrations,config)
    args.output.parent.mkdir(parents=True,exist_ok=True);result.to_csv(args.output,index=False)
    audit_path.write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps(audit['assessment_counts']))

if __name__=='__main__':main()
