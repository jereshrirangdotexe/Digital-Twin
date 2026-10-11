from pathlib import Path
import math,json,hashlib
from collections import deque
import numpy as np
import pandas as pd
import joblib
from threadpoolctl import threadpool_limits
from .input_adapter_250kVA import InputAdapter250kVA,CompatibilityError
from .data_quality_250kVA import sanitize,SIGNALS
from .feature_engineering import FeatureState,RollingMean
from .calibration_resolver import resolve,reference
from .decision import apply_decision
ROOT=Path(__file__).resolve().parents[1]

def clean(value):
 if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
 if isinstance(value,(list,tuple,deque)):return [clean(v) for v in value]
 if isinstance(value,np.generic):return clean(value.item())
 if isinstance(value,float) and not math.isfinite(value):return None
 return value

class DigitalTwinMLRuntime250kVA:
 def __init__(self,calibration=None,schema=None,units=None,asset_id='ORGANIZER_ASSET_001',timezone='Asia/Kolkata',dayfirst=None,timestamp_unit=None,voltage_basis='phase_neutral',package_root=ROOT):
  self.root=Path(package_root);self.config=json.loads((self.root/'config/250kVA_config.json').read_text());self.model=joblib.load(self.root/'model/250kVA_model.joblib')
  self.adapter=InputAdapter250kVA(schema,units,asset_id,timezone,dayfirst,timestamp_unit,voltage_basis)
  self.calibration,self.calibration_issues=resolve(calibration);self.reference=reference();self.assets={}
  self.fingerprint=hashlib.sha256((self.root/'model/250kVA_model.joblib').read_bytes()).hexdigest()
 def _asset(self,rid):
  if rid not in self.assets:self.assets[rid]={'features':FeatureState(self.reference,self.calibration),'last_seen':None,'last_grid':None,'missing_run':0}
  return self.assets[rid]
 def reset(self,asset_id):self.assets.pop(asset_id,None)
 def _base(self,row):
  telemetry={a:row.get(b) for a,b in [('voltageR','voltage_r_v'),('voltageY','voltage_y_v'),('voltageB','voltage_b_v'),('currentR','current_r_a'),('currentY','current_y_a'),('currentB','current_b_a'),('ambientTempC','ambient_temp_c'),('topOilTempC','top_oil_temp_c'),('communicationAvailable','communication_available')]}
  volts=[row.get(x) for x in SIGNALS[:3]];amps=[row.get(x) for x in SIGNALS[3:6]]
  telemetry['loadingPct']=sum(v*i for v,i in zip(volts,amps))/2500 if None not in volts+amps else None
  return dict(assetId=row['asset_id'],transformerRatingKVA=250,timestamp=row['timestamp'],sourceTimestamp=row.get('_sourceTimestamp'),actualOilTempC=row['top_oil_temp_c'],expectedOilTempC=None,thermalResidualC=None,thermalResidualTrendCPerMin=None,thermalResidualMean30minC=None,nominalModelResidualC=None,thermalScore=None,thermalDecisionMargin=None,thermalAlert=None,thermalState='THERMAL_UNASSESSED',phaseLoadingWarning=None,undervoltageWarning=None,imbalanceWarning=None,electricalState='UNASSESSED',dataConfidence='UNAVAILABLE' if row['communication_available'] is False else 'REDUCED',assetCondition='UNASSESSED',calibrationStatus=self.calibration['status'],warmupStatus='WARMING_UP',modelVersion=self.config['modelVersion'],modelStatus=self.config['modelStatus'],runtimeVersion=self.config['runtimeVersion'],telemetry=telemetry,diagnostics=list(row.get('_issues',[]))+self.calibration_issues,lowOilGaugeAssessment='UNSUPPORTED_BASIC',failed=False,_sensorSuspect=False,_assessable=False,_features=None)
 def update(self,scada_row,_defer_score=False):
  row=sanitize(self.adapter.normalize(scada_row));r=self._base(row);rid=row['asset_id'];a=self._asset(rid)
  if row['timestamp'] is None or row['transformer_rating_kva']!=250:
   r['failed']=True;return self.public(apply_decision(r,None,self.config['threshold'])) if not _defer_score else r
  if self.calibration.get('asset_id') not in [None,rid] and self.calibration['status']!='REFERENCE_CALIBRATION':
   r['diagnostics'].append('CALIBRATION_ASSET_MISMATCH');r['calibrationStatus']='INVALID';r['failed']=True
   return self.public(apply_decision(r,None,self.config['threshold'])) if not _defer_score else r
  t=pd.Timestamp(row['timestamp'])
  if a['last_seen'] is not None and t<=a['last_seen']:
   r['diagnostics'].append('DUPLICATE_TIMESTAMP' if t==a['last_seen'] else 'OUT_OF_ORDER_TIMESTAMP');r['failed']=True
   return self.public(apply_decision(r,None,self.config['threshold'])) if not _defer_score else r
  a['last_seen']=t
  if a['last_grid'] is not None:
   dt=(t-a['last_grid']).total_seconds()/60
   if dt<5 or not np.isclose(dt/5,round(dt/5),atol=1e-8):
    r['diagnostics'].append('SAMPLING_INCOMPATIBLE_WITH_FIVE_MINUTE_MODEL')
    r['warmupStatus']='READY' if a['features'].initialized>288 else 'WARMING_UP'
    return self.public(apply_decision(r,None,self.config['threshold'])) if not _defer_score else r
   if dt>360:
    a['features']=FeatureState(self.reference,self.calibration);a['missing_run']=0;r['diagnostics'].append('LONG_GAP_REINITIALIZED')
   elif dt>5:
    blank={name:None for name in SIGNALS};blank['communication_available']=False
    for _ in range(int(round(dt/5))-1):a['features'].step(blank)
    r['diagnostics'].append('MISSING_GRID_SLOTS_INSERTED:'+str(int(round(dt/5))-1))
  if row['communication_available'] is not True or any(row[name] is None for name in SIGNALS):a['missing_run']+=1
  else:
   if a['missing_run']>72:a['features']=FeatureState(self.reference,self.calibration);r['diagnostics'].append('LONG_OUTAGE_REINITIALIZED')
   a['missing_run']=0
  a['last_grid']=t;f,c=a['features'].step(row)
  r.update(expectedOilTempC=c['expected'],thermalResidualC=c['residual'],thermalResidualTrendCPerMin=c['residual_trend'],thermalResidualMean30minC=c['residual_mean'],nominalModelResidualC=f['nominal_oil_residual_C'],phaseLoadingWarning=c['phase'],undervoltageWarning=c['undervoltage'],imbalanceWarning=c['imbalance'],warmupStatus='WARMING_UP' if c['warmup'] else 'READY',_sensorSuspect=c['sensor_suspect'],_assessable=c['assessable'],_features=f)
  if c['sensor_suspect']:r['diagnostics'].append('OIL_SENSOR_SUSPECT')
  if not c['valid']:r['diagnostics'].append('INCOMPLETE_INPUTS')
  if not c['warmup'] and c['valid'] and not c['assessable']:r['diagnostics'].append('QUALITY_HOLDOFF')
  if c['warmup']:r['diagnostics'].append('WARMING_UP')
  # Reference assumptions and external calibration/nominal-classifier differences reduce confidence.
  r['dataConfidence']='UNAVAILABLE' if row['communication_available'] is False else 'REDUCED' if r['diagnostics'] or self.calibration['status']=='REFERENCE_CALIBRATION' or not c['assessable'] else 'GOOD'
  if _defer_score:return r
  score=self.score_features([f])[0] if c['assessable'] else None
  return self.public(apply_decision(r,score,self.config['threshold']))
 def score_features(self,rows):
  frame=pd.DataFrame(rows)[self.config['columns']]
  with threadpool_limits(limits=1):return np.round(self.model.predict_proba(frame)[:,1],12).tolist()
 @staticmethod
 def public(result):return clean({k:v for k,v in result.items() if not k.startswith('_')})
 def predict_batch(self,rows):
  results=[self.update(row,_defer_score=True) for row in rows]
  indices=[k for k,r in enumerate(results) if r['_assessable']];scores=self.score_features([results[k]['_features'] for k in indices]) if indices else []
  score_map=dict(zip(indices,scores))
  return [self.public(apply_decision(r,score_map.get(k),self.config['threshold'])) for k,r in enumerate(results)]
 def save_state(self,path):
  state={}
  for rid,a in self.assets.items():
   fs={k:clean(v) for k,v in vars(a['features']).items() if k not in ['reference','calibration','means']}
   fs['means']={name:clean(vars(mean)) for name,mean in a['features'].means.items()}
   state[rid]={'features':fs,'last_seen':a['last_seen'].isoformat() if a['last_seen'] is not None else None,'last_grid':a['last_grid'].isoformat() if a['last_grid'] is not None else None,'missing_run':a['missing_run']}
  Path(path).write_text(json.dumps({'model_sha256':self.fingerprint,'runtimeVersion':self.config['runtimeVersion'],'calibration':self.calibration,'assets':state},allow_nan=False),encoding='utf-8')
 def load_state(self,path):
  data=json.loads(Path(path).read_text())
  if data['model_sha256']!=self.fingerprint or data['runtimeVersion']!=self.config['runtimeVersion'] or data['calibration']!=self.calibration:raise ValueError('STATE_MODEL_OR_CALIBRATION_MISMATCH')
  assets={}
  for rid,a in data['assets'].items():
   fs=FeatureState(self.reference,self.calibration)
   for name,value in a['features'].items():
    original=getattr(fs,name)
    if isinstance(original,deque):
     # Numeric deques use NaN for missing, boolean persistence uses None.
     numeric=name in ['oil','load','ambient','residual','nominal_history']
     value=deque([np.nan if x is None and numeric else x for x in value],maxlen=original.maxlen)
    elif name=='phases':value=[deque(x,maxlen=3) for x in value]
    elif name=='means':
     means={}
     for label,state in value.items():
      mean=RollingMean(state['n'])
      for attribute,item in state.items():setattr(mean,attribute,deque(np.nan if x is None else x for x in item) if attribute=='values' else np.nan if item is None else item)
      means[label]=mean
     value=means
    setattr(fs,name,value)
   assets[rid]=dict(features=fs,last_seen=pd.Timestamp(a['last_seen']) if a['last_seen'] else None,last_grid=pd.Timestamp(a['last_grid']) if a['last_grid'] else None,missing_run=a['missing_run'])
  self.assets=assets
