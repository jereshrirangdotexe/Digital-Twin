"""Bounded causal state per asset. Frozen feature, thermal and screen equations."""
from collections import deque
from pathlib import Path
from functools import lru_cache
import hashlib,json,math
import joblib,numpy as np,pandas as pd
from scipy.special import expit
from .schema_adapter_100kVA import SIGNALS,CompatibilityError,SchemaAdapter100kVA
from .data_quality_100kVA import assess
from .decision import decision_margin
from calibration.commission_100kVA import resolve_calibration,validate_calibration

ROOT=Path(__file__).resolve().parents[1]

def load_artifact(path,expected_hash):
    p=Path(path)
    if not p.is_file(): raise CompatibilityError('Missing model artifact: '+str(p))
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    if digest!=expected_hash: raise CompatibilityError('MODEL_INTEGRITY_FAILURE: SHA256 differs from frozen artifact')
    artifact=joblib.load(p)
    schema=json.loads((ROOT/'config/100kVA_FEATURE_SCHEMA.json').read_text())
    if artifact.get('rating_kVA')!=100 or artifact.get('features')!=schema['feature_order'] or artifact.get('representation')!='residual':
        raise CompatibilityError('Artifact rating/feature/representation mismatch')
    return artifact

def persistent(values,count):
    if len(values)<count or any(v is None for v in list(values)[-count:]): return None
    return all(list(values)[-count:])

def average(values,minimum):
    v=[x for x in values if x is not None]
    return float(np.mean(v)) if len(v)>=minimum else None

class DigitalTwinMLRuntime100kVA:
    def __init__(self,calibration=None,*,schema=None,units=None,timezone=None,asset_id=None,model_path=None):
        self.config=json.loads((ROOT/'config/100kVA_config.json').read_text())
        self.thresholds=json.loads((ROOT/'config/100kVA_THRESHOLDS.json').read_text())
        self.artifact=load_artifact(str(Path(model_path or ROOT/'model/100kVA_model.joblib').resolve()),self.config['model_sha256'])
        if self.artifact['decision_margin_threshold']!=self.thresholds['decision_margin_threshold']:
            raise CompatibilityError('Frozen threshold differs from artifact')
        if self.config['rating_kva']!=100 or self.config['interval_minutes']!=5:
            raise CompatibilityError('Runtime rating or interval configuration mismatch')
        self.calibration=resolve_calibration(calibration)
        self.adapter=SchemaAdapter100kVA(schema,units,timezone or self.config['default_timezone'],asset_id)
        self.states={}

    def reset(self,asset_id=None):
        if asset_id is None: self.states.clear()
        else: self.states.pop(str(asset_id),None)

    @staticmethod
    def new_state():
        return dict(last_timestamp=None,expected=None,nominal=None,equilibrium=None,nominal_equilibrium=None,
                    drivers=[None]*4,driver_stale=0,initialized=0,
                    residuals=deque(maxlen=12),oil=deque(maxlen=36),nominal_history=deque(maxlen=36),
                    clean=deque(maxlen=12),phase=[deque(maxlen=3) for _ in range(3)],
                    imbalance=deque(maxlen=3),telemetry=deque(maxlen=36))

    def update(self,scada_row):
        return self._update(scada_row,score=True)

    def _update(self,scada_row,*,score):
        row=self.adapter.normalize(dict(scada_row))
        cal=self.calibration
        if cal['calibration_status']!='REFERENCE_CALIBRATION' and str(cal['asset_id'])!=row['asset_id']:
            raise CompatibilityError('Calibration asset_id does not match telemetry asset')
        clean,valid,suspect=assess(row,self.config)
        issues=clean['issues']
        asset=row['asset_id']
        if asset not in self.states:
            if len(self.states)>=1000: raise CompatibilityError('Maximum 1000 asset histories; partition the service')
            self.states[asset]=self.new_state()
        s=self.states[asset]
        timestamp_ok=clean['timestamp'] is not None
        sampling_ok=True
        if timestamp_ok and s['last_timestamp']:
            delta=(pd.Timestamp(clean['timestamp'])-pd.Timestamp(s['last_timestamp'])).total_seconds()/60
            if delta<=0:
                issues.append('DUPLICATE_TIMESTAMP' if delta==0 else 'OUT_OF_ORDER_TIMESTAMP')
                timestamp_ok=False
            elif not math.isclose(delta,5,abs_tol=1e-8):
                issues.append('TIMESTAMP_GAP' if delta>5 else 'INCOMPATIBLE_SAMPLING')
                sampling_ok=False
                # Reset rather than fabricate missing measurements or interpolate.
                s=self.new_state(); self.states[asset]=s
        if not timestamp_ok:
            # A malformed/order-rejected row cannot advance or contaminate history.
            return self._result(row,clean,s,None,None,None,False,True,issues,cal)
        s['last_timestamp']=clean['timestamp']
        if not sampling_ok:
            issues.append('HISTORY_RESET')
        drivers=[clean[k] for k in SIGNALS[3:7]]
        if all(v is not None for v in drivers): s['driver_stale']=0
        else: s['driver_stale']+=1
        if s['driver_stale']>self.config['max_driver_hold_samples']:
            t=s['last_timestamp']; stale=s['driver_stale']
            s=self.new_state();s['last_timestamp']=t;s['driver_stale']=stale;self.states[asset]=s
            issues.append('DRIVER_HOLD_EXPIRED_HISTORY_RESET')
        if s['driver_stale'] and s['expected'] is not None: issues.append('THERMAL_DRIVERS_HELD')
        s['drivers']=[new if new is not None else old for new,old in zip(drivers,s['drivers'])]
        oil=clean['top_oil_temp_c']
        if all(v is not None for v in s['drivers']):
            currents=s['drivers'][:3];ambient=s['drivers'][3]
            load2=float(np.mean((np.asarray(currents)/self.config['rated_current_a'])**2))
            eq=ambient+cal['rise']*(cal['loss_ratio']+(1-cal['loss_ratio'])*load2)**.8+cal['bias']
            nom_eq=ambient+32*(.16+.84*load2)**.8
        else: eq=nom_eq=None
        if s['expected'] is not None and s['equilibrium'] is not None:
            a=math.exp(-5/cal['tau'])
            s['expected']=a*s['expected']+(1-a)*s['equilibrium']
            an=math.exp(-5/150)
            s['nominal']=an*s['nominal']+(1-an)*s['nominal_equilibrium']
        elif eq is not None and oil is not None and row['communication_available'] is True:
            s['expected']=oil;s['nominal']=oil
        s['equilibrium']=eq;s['nominal_equilibrium']=nom_eq
        if s['expected'] is not None: s['initialized']+=1
        previous_oil=s['oil'][-1] if s['oil'] else None
        if oil is not None and previous_oil is not None and abs(oil-previous_oil)>self.thresholds['oil_jump_warning_C']:
            suspect=True;issues.append('OIL_SENSOR_JUMP')
        s['oil'].append(oil);s['nominal_history'].append(s['nominal'])
        if len(s['oil'])==36 and all(v is not None for v in s['oil']) and len(set(s['oil']))==1:
            expected=[v for v in s['nominal_history'] if v is not None]
            if len(expected)==36 and max(expected)-min(expected)>self.thresholds['oil_expected_range_warning_C']:
                suspect=True;issues.append('OIL_SENSOR_STUCK_SUSPECT')
        telemetry=tuple(clean[k] for k in SIGNALS)
        s['telemetry'].append(telemetry)
        if len(s['telemetry'])==36 and valid:
            if len(set(s['telemetry']))==1:
                suspect=True;issues.append('FROZEN_TELEMETRY_SUSPECT')
            for index,field in enumerate(SIGNALS[:6]):
                history=[v[index] for v in s['telemetry']]
                peers=[v[(index+1)%3+(3 if index>=3 else 0)] for v in s['telemetry']]
                if all(v is not None for v in history+peers) and len(set(history))==1 and max(peers)-min(peers)>(20 if index<3 else 30):
                    suspect=True;issues.append('STUCK_CHANNEL_SUSPECT:'+field)
        s['clean'].append(valid and not suspect and sampling_ok)
        residual=oil-s['expected'] if oil is not None and s['expected'] is not None else None
        previous_residual=list(s['residuals'])[-6] if len(s['residuals'])>=6 else None
        s['residuals'].append(residual)
        f=[residual,average(list(s['residuals'])[-6:],3),average(s['residuals'],6),
           residual-previous_residual if residual is not None and previous_residual is not None else None]
        assessable=valid and not suspect and sampling_ok and s['initialized']>self.thresholds['warmup_samples'] and len(s['clean'])==12 and all(s['clean'])
        # Preserve original persistent current and imbalance screens and voltage rule.
        i=[clean[k] for k in SIGNALS[3:6]];v=[clean[k] for k in SIGNALS[:3]]
        for hist,value in zip(s['phase'],i):
            hist.append(value>self.thresholds['phase_loading_pct']/100*self.config['rated_current_a'] if value is not None else None)
        phases=[persistent(h,3) for h in s['phase']]
        phase=True if any(x is True for x in phases) else None if any(x is None for x in phases) else False
        uv=True if any(x is not None and x<self.thresholds['undervoltage_pu']*self.config['phase_neutral_voltage_v'] for x in v) else None if any(x is None for x in v) else False
        im=float(np.mean(i)) if all(x is not None for x in i) else None
        imbalance=max(abs(x-im) for x in i)/im*100 if im is not None and im>0 else 0 if im==0 else None
        s['imbalance'].append(imbalance>self.thresholds['current_imbalance_pct'] if imbalance is not None else None)
        imb=persistent(s['imbalance'],3)
        result=self._result(row,clean,s,phase,uv,imb,assessable,suspect,issues,cal)
        result['residualMean30minC']=f[1];result['residualMean60minC']=f[2];result['residualChange30minC']=f[3]
        if assessable:
            if score:
                margin=float(decision_margin(self.artifact,pd.DataFrame([f],columns=self.artifact['features']))[0])
                self.apply_margin(result,margin)
            else: result['_features']=f
        return result

    def _result(self,row,clean,s,phase,uv,imb,assessable,suspect,issues,cal):
        if cal['calibration_status']=='REFERENCE_CALIBRATION':
            issues.append('REFERENCE_CALIBRATION_TRANSFER_UNVERIFIED')
        warnings=[phase,uv,imb]
        electrical='MULTIPLE_WARNINGS' if sum(x is True for x in warnings)>1 else ['PHASE_LOADING_WARNING','UNDERVOLTAGE_WARNING','IMBALANCE_WARNING'][next(i for i,x in enumerate(warnings) if x is True)] if any(x is True for x in warnings) else 'UNASSESSED' if any(x is None for x in warnings) else 'NORMAL'
        invalid_timestamp=any(i in ['INVALID_TIMESTAMP','DUPLICATE_TIMESTAMP','OUT_OF_ORDER_TIMESTAMP'] for i in issues)
        confidence='UNAVAILABLE' if row['communication_available'] is not True else 'REDUCED' if issues or suspect or not assessable else 'GOOD'
        if invalid_timestamp: confidence='UNAVAILABLE'
        # Never expose a previous thermal estimate against a rejected timestamp.
        expected=None if invalid_timestamp else s['expected']
        oil=clean['top_oil_temp_c']
        v=[clean[k] for k in SIGNALS[:3]];i=[clean[k] for k in SIGNALS[3:6]]
        load=sum(a*b for a,b in zip(v,i))/1000 if all(x is not None for x in v+i) else None
        loading_source='DERIVED_PHASE_VI' if load is not None else 'SCADA_DECLARED' if row.get('loading_pct') is not None else 'UNAVAILABLE'
        if load is None and row['communication_available'] is True: load=row.get('loading_pct')
        if load is None: loading_source='UNAVAILABLE'
        condition='SENSOR_SUSPECT' if suspect and not invalid_timestamp else 'ELECTRICAL_CONDITION_ALERT' if any(x is True for x in warnings) else 'UNASSESSED'
        result=dict(assetId=row['asset_id'],transformerRatingKVA=100,timestamp=row['timestamp'],inputTimestamp=row['input_timestamp'],
                    actualOilTempC=oil,expectedOilTempC=expected,thermalResidualC=oil-expected if oil is not None and expected is not None else None,
                    residualMean30minC=None,residualMean60minC=None,residualChange30minC=None,
                    thermalScore=None,thermalDecisionMargin=None,thermalAlert=None,thermalState='THERMAL_UNASSESSED',
                    phaseLoadingWarning=phase,undervoltageWarning=uv,imbalanceWarning=imb,electricalState=electrical,
                    dataConfidence=confidence,assetCondition=condition,calibrationStatus=cal['calibration_status'],
                    warmupStatus='READY' if s['initialized']>288 and len(s['clean'])==12 and all(s['clean']) and not invalid_timestamp else 'WARMING_UP',
                    modelVersion=self.artifact['model_version'],modelStatus=self.artifact['status'],runtimeVersion=self.config['runtime_version'],
                    telemetry=dict(zip(['voltageR','voltageY','voltageB','currentR','currentY','currentB','ambientTempC','topOilTempC'],[clean[k] for k in SIGNALS])),
                    calibration={k:cal.get(k) for k in ['rise','tau','bias','loss_ratio','commission_rmse_C','commission_samples','commission_duration_minutes','bound_warnings','provenance']},
                    qualityIssues=list(dict.fromkeys(issues)),thermalAssessable=bool(assessable))
        result['telemetry'].update(loadingPct=load,loadingSource=loading_source,communicationAvailable=row['communication_available'])
        return result

    def apply_margin(self,result,margin):
        alert=margin>self.artifact['decision_margin_threshold']
        result.update(thermalDecisionMargin=margin,thermalScore=float(expit(margin)),thermalAlert=bool(alert),thermalState='THERMAL_ALERT' if alert else 'NORMAL')
        electrical=any(result[k] is True for k in ['phaseLoadingWarning','undervoltageWarning','imbalanceWarning'])
        result['assetCondition']='MULTIPLE_CONDITIONS' if alert and electrical else 'THERMAL_CONDITION_ALERT' if alert else 'ELECTRICAL_CONDITION_ALERT' if electrical else 'NORMAL'

    def save(self,path):
        states={}
        for asset,s in self.states.items():
            states[asset]={k:([list(h) for h in v] if k=='phase' else list(v) if isinstance(v,deque) else v) for k,v in s.items()}
        data=dict(state_version=1,model_sha256=self.config['model_sha256'],runtime_version=self.config['runtime_version'],
                  config=self.config,thresholds=self.thresholds,calibration=self.calibration,states=states,
                  adapter=dict(schema=self.adapter.schema,units=self.adapter.units,timezone=self.adapter.timezone,asset_id=self.adapter.asset_id))
        Path(path).write_text(json.dumps(data,allow_nan=False,indent=2),encoding='utf-8')

    @classmethod
    def load(cls,path):
        data=json.loads(Path(path).read_text(encoding='utf-8'))
        runtime=cls(data['calibration'],**data['adapter'])
        if data.get('state_version')!=1 or data.get('model_sha256')!=runtime.config['model_sha256'] or data.get('config')!=runtime.config or data.get('thresholds')!=runtime.thresholds:
            raise CompatibilityError('State version/model/config mismatch; restart with fresh warm-up')
        for asset,s in data['states'].items():
            blank=cls.new_state()
            if set(s)!=set(blank): raise CompatibilityError('Invalid persisted state fields')
            for key in blank:
                if key=='phase': s[key]=[deque(v,maxlen=3) for v in s[key]]
                elif isinstance(blank[key],deque):
                    s[key]=deque([tuple(v) for v in s[key]] if key=='telemetry' else s[key],maxlen=blank[key].maxlen)
            runtime.states[asset]=s
        return runtime
