"""Bridge the user-selected locked V4 bundle into the existing dashboard contract."""
from pathlib import Path
import sys,json,hashlib,math
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
FINAL=HERE/'final100'
sys.path.insert(0,str(FINAL/'runtime'))
import voltmind_v4_lr_runtime as locked
import voltmind_v4_input_adapter as hardened
from voltmind_v4_table_reader import read_table as frozen_read_table

def read_table(path,filename=None,**options):
    if Path(path).stat().st_size>100*1024*1024:raise ValueError('Dataset exceeds the 100 MiB limit')
    if Path(filename or str(path)).suffix.lower() in ['.json','.jsonl','.ndjson']:
        def unique_pairs(pairs):
            result={}
            for key,value in pairs:
                if key in result:raise ValueError('Duplicate JSON field: '+key)
                result[key]=value
            return result
        text=Path(path).read_text(encoding='utf-8-sig')
        if Path(filename or str(path)).suffix.lower()=='.json':json.loads(text,object_pairs_hook=unique_pairs)
        else:
            for line in text.splitlines():
                if line.strip():json.loads(line,object_pairs_hook=unique_pairs)
    return frozen_read_table(path,filename,**options)

KEEP=['replay_id','timestamp_IST']+locked.vr.RAW+['oil_level_fraction','terminal_R_surface_temp_C','communication_available','oil_level_sensor_available','terminal_sensor_available','transformer_rating_kva','data_origin','inputIssues']
def finite(v):return float(v) if v is not None and np.isfinite(v) else None
def boolean(v):return bool(v) if v is not None and not pd.isna(v) else None
def clean(v):
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
    if isinstance(v,list):return [clean(x) for x in v]
    if isinstance(v,(np.integer,np.floating,np.bool_)):return clean(v.item())
    if isinstance(v,float) and not math.isfinite(v):return None
    return v

class FinalRuntime100:
    def __init__(self,calibration=None,**options):
        self.bundle=locked.load_locked(FINAL);self.calibrations=calibration or {};self.cursor=0
        self.artifact={'model_version':'VoltMind_LR_V4_LOCKED','status':'SYNTHETICALLY_VALIDATED_RESEARCH','features':self.bundle['tasks']['thermal']['features']}
        self.config={'model_sha256':hashlib.sha256((FINAL/'models/100kVA_LR_V4_LOCKED.joblib').read_bytes()).hexdigest(),'rated_current_a':locked.vr.IRATED,'phase_neutral_voltage_v':433/math.sqrt(3)}
    def bind(self,rows):
        frame=pd.DataFrame(rows);asset=str(frame.replay_id.iloc[0]);cal=self.calibrations.get(asset)
        calibration_problem=locked.calibration_issue(frame,cal)
        predictions,audit=hardened.predict_table(frame,self.bundle,self.calibrations)
        self.calibration=cal or {'calibration_status':'MISSING_CALIBRATION'};self.audit=audit
        prepared,_=hardened.adapt(frame);details={};measurements={}
        for _,g in prepared.groupby('_segment',sort=False):
            g=g.reset_index(drop=True)
            normalized=locked.normalize(g)
            for j in range(len(g)):measurements[int(g._input_row.iloc[j])]=normalized.iloc[j]
            if cal and not locked.calibration_issue(g,cal):
                x,c=locked.vr.features(locked.normalize(g),cal)
                for j in range(len(g)):details[int(g._input_row.iloc[j])]=(x.iloc[j],c.iloc[j])
        self.outputs=[]
        for i,pred in predictions.iterrows():
            raw=frame.iloc[i];f=measurements[i];pair=details.get(i);x,c=pair if pair else (None,None)
            expected=finite(c.expected_oil_C) if c is not None else None
            actual=finite(f.top_oil_temp_C);ready=bool(pred.thermal_assessable);alert=boolean(pred.thermal_alert)
            score=finite(pred.thermal_score_uncalibrated);threshold=self.bundle['tasks']['thermal']['threshold']
            sensor=bool(c.sensor_suspect) if c is not None else False
            issues=[a for a in str(pred.input_issues).split(';') if a]
            issues+=str(raw.get('inputIssues','')).strip(';').split(';') if raw.get('inputIssues') else []
            if sensor:issues.append('OIL_SENSOR_SUSPECT')
            if not ready:issues.append(str(pred.thermal_status))
            voltage=[finite(f[k]) for k in ['VR_V','VY_V','VB_V']];current=[finite(f[k]) for k in ['IR_A','IY_A','IB_A']]
            # Warning outputs retain the locked feature module's engineering convention.
            flags={k:boolean(pred.get(v)) for k,v in [('phaseLoadingWarning','phase_loading_warning'),('undervoltageWarning','undervoltage_warning'),('imbalanceWarning','imbalance_warning')]}
            avg=sum(current)/3 if all(v is not None for v in current) else None
            vavg=sum(voltage)/3 if all(v is not None for v in voltage) else None
            apparent=sum(v*i for v,i in zip(voltage,current))/1000 if vavg is not None and avg is not None else None
            condition='SENSOR_SUSPECT' if sensor else 'THERMAL_ALERT' if alert is True else 'OPERATING_WARNING' if any(v is True for v in flags.values()) else 'NORMAL_OBSERVED' if ready else 'UNASSESSED'
            ml=dict(expectedOilTempC=expected,thermalResidualC=actual-expected if actual is not None and expected is not None else None,
                residualMean30minC=finite(x.residual_mean_30min_C) if x is not None else None,residualMean60minC=finite(x.residual_mean_60min_C) if x is not None else None,
                residualChange30minC=finite(x.residual_change_30min_C) if x is not None else None,thermalScore=score,thermalDecisionMargin=score-threshold if score is not None else None,
                thermalAlert=alert,thermalState='THERMAL_ALERT' if alert else 'NO_MODEL_ALERT' if ready else 'UNASSESSED',**flags,
                electricalState='ELECTRICAL_WARNING' if any(v is True for v in flags.values()) else 'NO_WARNING_OBSERVED' if all(v is not None for v in flags.values()) else 'UNASSESSED',
                dataConfidence='GOOD' if ready and not sensor else 'REDUCED' if all(v is not None for v in current) and actual is not None else 'UNAVAILABLE',assetCondition=condition,
                calibrationStatus=cal.get('calibration_status') if cal else 'MISSING_CALIBRATION',warmupStatus='READY' if ready else str(pred.thermal_status) if calibration_problem else 'WARMING_UP',
                modelVersion='VoltMind_LR_V4_LOCKED',modelStatus='SYNTHETICALLY_VALIDATED_RESEARCH',runtimeVersion='V4_HARDENED_BRIDGE_1',
                scoreDefinition='Uncalibrated Logistic Regression positive-class detector score, not failure probability',decisionThreshold=threshold,
                oilAlert=boolean(pred.oil_alert),oilScore=finite(pred.oil_score_uncalibrated),oilStatus=pred.oil_status,
                terminalAlert=boolean(pred.terminal_alert),terminalScore=finite(pred.terminal_score_uncalibrated),terminalStatus=pred.terminal_status)
            telemetry=dict(zip(['voltageR','voltageY','voltageB','currentR','currentY','currentB'],voltage+current))
            telemetry.update(ambientTempC=finite(f.ambient_temp_C),topOilTempC=actual,loadingPct=apparent,apparentPowerKVA=apparent,communicationAvailable=bool(f.communication_available),
                oilLevelFraction=finite(f.oil_level_fraction),terminalRTempC=finite(f.terminal_R_surface_temp_C))
            self.outputs.append(clean(dict(contractVersion='1.0',asset={'id':asset,'ratingKVA':100,'status':'ONLINE' if f.communication_available else 'OFFLINE'},timestamp=pred.timestamp_IST,
                telemetry=telemetry,ml=ml,calibration=self.calibration,quality={'issues':issues,'thermalAssessable':ready,'inputTimestamp':raw.timestamp_IST},
                modelSHA256=self.config['model_sha256'],dataOrigin=str(raw.get('data_origin','USER_SUPPLIED_MEASUREMENTS')),
                syntheticCalibration='synthetic' in str((cal or {}).get('provenance','')).lower())))
    def update(self,row):
        if not hasattr(self,'outputs'):raise ValueError('Bind the selected ordered replay before inference')
        if self.cursor>=len(self.outputs):raise ValueError('Replay exhausted')
        result=self.outputs[self.cursor];self.cursor+=1;return result

class FinalModel100:
    rating=100;runtime=FinalRuntime100
    def payload(self,result,runtime):return result
    def info(self):
        r=FinalRuntime100();return dict(ratingKVA=100,modelVersion=r.artifact['model_version'],modelStatus=r.artifact['status'],modelSHA256=r.config['model_sha256'],
            engineering={'ratedCurrentA':locked.vr.IRATED,'nominalPhaseVoltageV':433/math.sqrt(3)},decisionThreshold=r.bundle['tasks']['thermal']['threshold'])
    def validate_selection(self,calibration,rows,replay_id=None):return None # Guarded per-asset prediction abstains if commissioning is missing/invalid.
    def prepare(self,path,filename,mode,options=None,commissioning=None,verified=False):
        options=dict(options or {});extra=options.pop('datasetInput',{}) or {}
        for key in ['schema','units','calibration']:
            if key in options and not isinstance(options[key],dict):raise ValueError(key+' must be a JSON object')
        if not isinstance(extra,dict):raise ValueError('datasetInput must be a JSON object')
        legacy={'timestamp':'timestamp_IST','asset_id':'replay_id',**dict(zip(['voltage_r_v','voltage_y_v','voltage_b_v','current_r_a','current_y_a','current_b_a','ambient_temp_c','top_oil_temp_c'],locked.vr.RAW))}
        config={k:options[k] for k in ['timezone','asset_id'] if k in options}
        for k in ['schema','units']:
            if k in options:config[k]={legacy.get(a,a):b for a,b in options[k].items()}
        for k in ['timestamp_format','epoch_unit','sort']:
            if k in extra:config[k]=extra[k]
        if extra.get('sampling','strict')!='strict':raise ValueError('Final V4 runtime requires native five-minute samples; resampling is not automatic')
        frame=read_table(path,filename,sheet=extra.get('sheet'),delimiter=extra.get('delimiter'),decimal=extra.get('decimal','.'))
        if mode=='LOCAL':
            canonical=frame;compatibility={'warnings':[],'assumptions':['Synthetic V4 measurements and independent synthetic commissioning. No field certification.']}
            # Separate, labelled illustration; original SCADA and locked bundle remain untouched.
            demo_path=HERE.parent/'data/demo100/100kVA_THERMAL_TWIN_DEMO_4032.csv'
            demo_cal=HERE.parent/'data/demo100/calibration.json'
            if Path(path).resolve()==(HERE.parent/'data/final100/scada/100kVA_SCADA_V4_FULL.csv').resolve() and demo_path.exists() and demo_cal.exists() and 'DEMO100_THERMAL_TWIN' not in set(canonical.replay_id.astype(str)):
                demo=pd.read_csv(demo_path)
                if len(demo)!=4032 or set(demo.replay_id.astype(str))!={'DEMO100_THERMAL_TWIN'}:
                    raise ValueError('Synthetic thermal demonstration must contain exactly 4032 rows for its own asset')
                canonical=pd.concat([canonical,demo.reindex(columns=canonical.columns)],ignore_index=True)
                compatibility['assumptions'].append('Includes a separate labelled synthetic thermal-twin demonstration; it is not validation evidence.')
        else:
            canonical,audit=hardened.adapt(frame,config);compatibility={'warnings':audit['missing_measurements'],'assumptions':['No invented sensors or automatic interpolation.'],'audit':audit}
            canonical['inputIssues']=canonical['_issues']
            if config.get('sort'):canonical=canonical.sort_values(['replay_id','timestamp_IST'],kind='stable')
        if len(canonical)>300000:raise ValueError('100 kVA limit: 300000 rows')
        if not {'replay_id','timestamp_IST'}<=set(canonical):raise ValueError('Asset and timestamp required')
        groups={str(asset):g[[c for c in KEEP if c in g]].to_dict('records') for asset,g in canonical.groupby('replay_id',sort=False)}
        calibration=options.get('calibration');cals={}
        if calibration:
            cals=calibration if 'calibration_status' not in calibration else {str(calibration.get('asset_id')):calibration}
        elif mode=='LOCAL':
            for asset in groups:
                p=FINAL/'calibration'/f'{asset}.json'
                if p.exists():cals[asset]=json.loads(p.read_text())
                elif asset=='DEMO100_THERMAL_TWIN':
                    demo_cal=HERE.parent/'data/demo100/calibration.json'
                    if demo_cal.exists():cals[asset]=json.loads(demo_cal.read_text())[asset]
        if commissioning is not None:
            if calibration:raise ValueError('Choose calibration or separate commissioning')
            if not verified:raise ValueError('Separate commissioning must be independently attested healthy')
            from calibration.commission_100kVA import commission_asset
            cal=commission_asset(commissioning,verified_healthy=True,**{k:v for k,v in options.items() if k in ['schema','units','timezone','asset_id']})
            cals={str(cal['asset_id']):cal}
        replays=[{'id':a,'rows':len(g),'firstTimestamp':str(g[0]['timestamp_IST'])} for a,g in groups.items()]
        return dict(groups=groups,options={},calibration=cals,totalRows=len(canonical),replays=replays,warnings=compatibility['warnings']+compatibility['assumptions'],compatibility=compatibility)

def cli():
    import argparse
    ap=argparse.ArgumentParser(description='Final locked 100 kVA hardened inference')
    ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--config',type=Path);ap.add_argument('--calibrations',type=Path);ap.add_argument('--sheet');ap.add_argument('--decimal',default='.')
    a=ap.parse_args();audit_path=a.output.with_suffix('.audit.json')
    inputs=[a.input,a.config,a.calibrations,FINAL/'LOCK_MANIFEST.json',FINAL/'models/100kVA_LR_V4_LOCKED.joblib']
    if any(p and p.resolve() in [a.output.resolve(),audit_path.resolve()] for p in inputs):raise ValueError('Output cannot overwrite an input or locked artifact')
    if a.output.exists() or audit_path.exists():raise ValueError('Output already exists; choose a new path')
    f=read_table(a.input,sheet=a.sheet,decimal=a.decimal)
    config=json.loads(a.config.read_text()) if a.config else None;cal=json.loads(a.calibrations.read_text()) if a.calibrations else None
    out,audit=hardened.predict_table(f,locked.load_locked(FINAL),cal,config)
    a.output.parent.mkdir(parents=True,exist_ok=True);out.to_csv(a.output,index=False);audit_path.write_text(json.dumps(audit,indent=2),encoding='utf-8')
    print(json.dumps(audit['assessment_counts']))


