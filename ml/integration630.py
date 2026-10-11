"""Transport compatibility for the supplied 630-kVA causal detector."""
from pathlib import Path
import json,math,hashlib,copy,tempfile
import pandas as pd
from vendor630.input_adapter import InputAdapter,ALIASES
from vendor630.streaming_runtime import DigitalTwinMLRuntime630kVA
from vendor630.commissioning import commission

ROOT=Path(__file__).parent/'vendor630'
FIELDS={'voltage_r_v':'VR_V','voltage_y_v':'VY_V','voltage_b_v':'VB_V',
 'current_r_a':'IR_A','current_y_a':'IY_A','current_b_a':'IB_A',
 'ambient_temp_c':'ambient_temp_C','top_oil_temp_c':'top_oil_temp_C',
 'timestamp':'timestamp','asset_id':'asset_id','replay_id':'replay_id',
 'transformer_rating_kva':'transformer_rating_kva','communication_available':'communication_available'}

class NativeAdapter630(InputAdapter):
    def __init__(self,schema=None,units=None,timezone='Asia/Kolkata',asset_id=None):
        self.timezone=timezone
        translated={FIELDS.get(k,k):v for k,v in (schema or {}).items()}
        unknown=set(translated)-set(ALIASES)
        if unknown:raise ValueError('Unknown schema field: '+str(unknown))
        out={}
        for k,v in (units or {}).items():
            names=[s for c,s in FIELDS.items() if c.startswith(k)] if k in ['voltage','current'] else ['ambient_temp_C','top_oil_temp_C'] if k=='temperature' else [FIELDS.get(k,k)]
            u={'v':'V','kv':'kV','a':'A','ka':'kA','c':'C','f':'F','k':'K'}.get(str(v).lower(),v)
            for name in names:out[name]=u
        super().__init__(translated,out,None,asset_id or 'EXTERNAL-630')
    def mapping(self,columns):
        lower={str(c).lower():c for c in columns};mapping={}
        for canonical,source in FIELDS.items():
            aliases=[self.schema[source]] if source in self.schema else ALIASES[source]
            matches=[lower[n.lower()] for n in aliases if n.lower() in lower]
            mapping[canonical]=matches[0] if matches else None
        return mapping
    def normalize(self,raw):
        mapping=self.mapping(raw.keys());column=mapping['timestamp'];value=raw.get(column)
        # Source runtime accepts aware ISO timestamps. Localize explicit user timezone
        # before ingress for naive timestamps; retain offset-aware input unchanged.
        if value is not None:
            t=pd.Timestamp(value)
            if t.tzinfo is None:
                if not self.timezone:raise ValueError('Naive timestamp requires explicit timezone')
                t=t.tz_localize(self.timezone,ambiguous='raise',nonexistent='raise')
                raw=dict(raw);raw[column]=t.isoformat()
        return super().normalize(raw)

class Adapter630(NativeAdapter630):
    def normalize(self,raw):
        row=super().normalize(raw)
        result={canonical:row[source] for canonical,source in FIELDS.items()}
        result['original_asset_id']=row['asset_id']
        result['asset_id']=row['asset_id']+' / '+row['replay_id']
        result['issues']=row['_problems']
        return result

class Runtime630(DigitalTwinMLRuntime630kVA):
    def __init__(self,calibration=None,schema=None,units=None,timezone='Asia/Kolkata',asset_id=None):
        super().__init__(calibration=calibration or 'reference')
        self.adapter=NativeAdapter630(schema,units,timezone,asset_id)

class Model630:
    rating=630
    runtime=Runtime630
    adapter=Adapter630
    def mapping(self,adapter,columns):return adapter.mapping(columns)
    def validate_rating(self,rows):
        if any(row['transformer_rating_kva']!=630 for row in rows):raise ValueError('Only 630-kVA assets are supported')
    def resolve(self,calibration,local=False):
        if calibration is None:
            return json.loads((ROOT/'calibration/synthetic_assets.json').read_text()) if local else {'type':'REFERENCE_PROVISIONAL','assets':{}}
        if not isinstance(calibration,dict):raise ValueError('630-kVA calibration must be a JSON object')
        result=copy.deepcopy(calibration)
        if not isinstance(result.get('assets'),dict) or not result['assets']:raise ValueError('630-kVA explicit calibration requires an assets mapping')
        config=json.loads((ROOT/'config/transformer_config.json').read_text())
        for asset,entry in result['assets'].items():
            if not isinstance(entry,dict) or entry.get('validated') is not True or entry.get('rating_kva')!=630:raise ValueError('Invalid asset calibration declaration for '+str(asset))
            for field,key in [('nominal_top_oil_rise_K','rise_K'),('tau_heat_min','tau_heat_min'),('tau_cool_min','tau_cool_min'),('oil_exponent','oil_exponent')]:
                value=float(entry[field]);lo,hi=config['thermal_ranges'][key]
                if not math.isfinite(value) or not lo<=value<=hi:raise ValueError('Calibration outside supported bounds: '+field)
        result.setdefault('type','ASSET_SPECIFIC')
        return result
    def calibration_status(self,calibration):return calibration.get('type','REFERENCE_PROVISIONAL')
    def validate_calibration(self,calibration,canonical):
        if calibration.get('type') not in ['KNOWN_SYNTHETIC_REFERENCE','REFERENCE_PROVISIONAL']:
            missing={r['original_asset_id'] for r in canonical}-set(calibration['assets'])
            if missing:raise ValueError('Supplied calibration is not bound to assets: '+str(sorted(missing)))
    def validate_selection(self,calibration,rows,replay_id=None):pass
    def commission(self,frame,verified,options):
        if not verified:raise ValueError('Commissioning requires an explicit verified-healthy declaration')
        adapter=NativeAdapter630(**options);rows=[adapter.normalize(r) for r in frame.to_dict('records')]
        assets={r['asset_id'] for r in rows}
        if len(assets)!=1:raise ValueError('Commission only one asset at a time')
        with tempfile.TemporaryDirectory(prefix='voltmind630_') as folder:
            inp=Path(folder)/'separate_commissioning.csv';out=Path(folder)/'calibration.json'
            pd.DataFrame([{k:v for k,v in r.items() if not k.startswith('_')} for r in rows]).to_csv(inp,index=False)
            return self.resolve(commission(inp,out,next(iter(assets)),verified_healthy=True))
    def payload(self,result,runtime):
        payload=copy.deepcopy(result);ml=payload['ml'];warnings=ml['electricalWarnings'];issues=list(ml['qualityReasons'])
        available=ml['electricalState']!='UNASSESSED'
        for key,name in [('phaseLoadingWarning','PHASE_LOADING_WARNING'),('undervoltageWarning','UNDERVOLTAGE_WARNING'),('imbalanceWarning','IMBALANCE_WARNING')]:
            ml[key]=True if name in warnings else False if available else None
        sensor=ml['sensorState']=='SENSOR_SUSPECT' and any(x!='COMMUNICATION_LOSS' for x in issues)
        if sensor:condition='SENSOR_SUSPECT'
        elif ml['thermalAlert'] and warnings:condition='MULTIPLE_CONDITIONS'
        elif ml['thermalAlert']:condition='THERMAL_CONDITION_ALERT'
        elif warnings:condition='ELECTRICAL_CONDITION_ALERT'
        elif ml['thermalScore'] is None:condition='UNASSESSED'
        else:condition='NORMAL'
        ml.update(assetCondition=condition,runtimeVersion='630-source-causal-runtime',residualMean30minC=None,residualMean60minC=None,residualChange30minC=None)
        config=dict(runtime.c);entry=runtime.cal.get('assets',{}).get(result['asset']['id'],{});config.update(entry)
        ml['warmupRequiredMinutes']=3*max(config['tau_heat_min'],config['tau_cool_min'])
        payload['contractVersion']='1.0';payload['quality']={'issues':issues,'thermalAssessable':ml['thermalScore'] is not None,'inputTimestamp':result['timestamp']}
        payload['calibration']=copy.deepcopy(runtime.cal)
        payload['nativeSource']=copy.deepcopy(result['source'])
        payload['sourceDigitalTwin']=copy.deepcopy(result['digitalTwin'])
        return payload
    def info(self):
        runtime=Runtime630()
        return {'ratingKVA':630,'modelVersion':'VoltMind_630kVA_Prototype_ML_v1.0',
          'modelStatus':runtime.artifact.get('status','UNLOCKED'),
          'modelSHA256':hashlib.sha256((ROOT/'630kVA_model.joblib').read_bytes()).hexdigest(),
          'detectorKind':runtime.artifact['kind'],'warmupRule':'Three times the larger configured oil time constant',
          'engineering':{'ratedCurrentA':630000/(math.sqrt(3)*433),'nominalPhaseVoltageV':433/math.sqrt(3)}}
