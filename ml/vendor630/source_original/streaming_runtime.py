from pathlib import Path
import json,joblib,hashlib
from input_adapter import InputAdapter
from base_features import FeatureEngine,FEATURE_NAMES
from decision import Decision,raw_score
from digital_twin_adapter import interpretation
class DigitalTwinMLRuntime630kVA:
    def __init__(self,model_path=None,calibration='reference',schema=None,units=None,tz=None,asset_id='EXTERNAL-630',config_path=None):
        root=Path(__file__).parent
        self.c=json.loads(Path(config_path or root/'config/transformer_config.json').read_text(encoding='utf-8'))
        if self.c.get('rating_kva')!=630 or self.c.get('secondary_line_V')!=433 or self.c.get('primary_V')!=11000:
            raise ValueError('Locked reference supports 630 kVA 11/0.433 kV only; other designs require separate validation')
        if any(self.c.get(k,0)<=0 for k in ['no_load_loss_W','load_loss_W_at_75C','nominal_top_oil_rise_K','tau_heat_min','tau_cool_min']):raise ValueError('Invalid thermal/loss configuration')
        self.artifact=joblib.load(model_path or root/'630kVA_model.joblib')
        if self.artifact['feature_names']!=FEATURE_NAMES:raise ValueError('Locked feature schema mismatch')
        if calibration in ('reference',None):self.cal={};self.caltype='REFERENCE_PROVISIONAL'
        else:self.cal=json.loads(Path(calibration).read_text(encoding='utf-8'));self.caltype=self.cal.get('type','ASSET_SPECIFIC')
        self.adapter=InputAdapter(schema,units,tz,asset_id);self.states={};self.last_features=None
    def reset(self):self.states.clear();self.last_features=None
    def update(self,raw,source=None):
        row=self.adapter.normalize(raw);key=(row['asset_id'],row['replay_id'])
        if key not in self.states:
            cfg=dict(self.c);entry=self.cal.get('assets',{}).get(row['asset_id'])
            if entry:
                if not entry.get('validated') or entry.get('rating_kva')!=630:raise ValueError('Invalid asset calibration declaration')
                for k in ['nominal_top_oil_rise_K','tau_heat_min','tau_cool_min','oil_exponent']:
                    value=float(entry[k]);bounds=self.c['thermal_ranges'].get({'nominal_top_oil_rise_K':'rise_K', 'tau_heat_min':'tau_heat_min','tau_cool_min':'tau_cool_min','oil_exponent':'oil_exponent'}[k])
                    if not bounds[0]<=value<=bounds[1]:raise ValueError('Calibration outside supported bounds: '+k)
                    cfg[k]=value
            self.states[key]=(FeatureEngine(cfg),Decision(self.artifact),bool(entry))
        engine,decision,assetcal=self.states[key];f=engine.update(row);self.last_features=f['features']
        score=raw_score(self.artifact,f['features']) if f['ready'] else None
        alert=decision.update(score,row['_dt'],f['ready'])
        problems=f['problems'];sensor='SENSOR_SUSPECT' if problems else ('AMBIGUOUS_TEMPERATURE_DEVIATION' if alert else 'NO_DETECTED_SENSOR_ISSUE')
        confidence='UNAVAILABLE' if problems else ('REDUCED' if alert or not assetcal else 'GOOD_SYNTHETIC_CALIBRATION')
        state='THERMAL_UNASSESSED' if not f['ready'] else ('THERMAL_DEVIATION' if alert else 'NORMAL')
        result=dict(asset=dict(id=row['asset_id'],ratingKVA=630,status='COMMUNICATION_LOSS' if row['communication_available'] is False else 'ONLINE' if row['communication_available'] else 'COMMUNICATION_UNCONFIRMED'),source=source or dict(mode='LOCAL_OR_EXTERNAL',filename=None,replayId=row['replay_id']),timestamp=row['timestamp'],telemetry=dict(voltageR=row['VR_V'],voltageY=row['VY_V'],voltageB=row['VB_V'],currentR=row['IR_A'],currentY=row['IY_A'],currentB=row['IB_A'],ambientTempC=row['ambient_temp_C'],topOilTempC=row['top_oil_temp_C'],loadingPct=f['loading'],communicationAvailable=row['communication_available']),ml=dict(expectedOilTempC=f['expected'],thermalResidualC=f['residual'],thermalScore=score,thermalDecisionMargin=None if score is None else score-self.artifact['threshold'],thermalAlert=alert if f['ready'] else None,thermalState=state,electricalState='UNASSESSED' if f['load'] is None else 'MULTIPLE_WARNINGS' if len(f['warnings'])>1 else f['warnings'][0] if f['warnings'] else 'NORMAL',electricalWarnings=f['warnings'],dataConfidence=confidence,sensorState=sensor,calibrationStatus=self.caltype if assetcal else 'REFERENCE_PROVISIONAL',calibrationUncertainty='Reference envelope; not a measured asset confidence interval',warmupStatus='READY' if f['ready'] else 'WARMING_UP',qualityReasons=problems,modelVersion='VoltMind_630kVA_Prototype_ML_v1.0',modelStatus=self.artifact.get('status','UNLOCKED')))
        result['digitalTwin']=interpretation(result);return result
