"""Select independent frozen runtimes; normalize transport without changing inference."""
import math,hashlib
import pandas as pd
from runtime.streaming_runtime_100kVA import DigitalTwinMLRuntime100kVA
from runtime.schema_adapter_100kVA import SchemaAdapter100kVA
from runtime.frontend_adapter_100kVA import to_frontend_payload
from calibration.commission_100kVA import resolve_calibration,commission_asset
from vendor250.runtime.streaming_runtime_250kVA import DigitalTwinMLRuntime250kVA
from vendor250.runtime.input_adapter_250kVA import InputAdapter250kVA
from vendor250.runtime.frontend_adapter_250kVA import to_frontend_payload as payload250
from vendor250.runtime.calibration_resolver import resolve as resolve250
from vendor250.calibration.commission_250kVA import commission as commission250

def rating_value(value):
    if isinstance(value,bool) or str(value) not in ['100','250','630']: raise ValueError('Choose supported transformer rating: 100, 250 or 630 kVA')
    return int(value)

class Model:
    def __init__(self,rating):
        self.rating=rating
        self.runtime=DigitalTwinMLRuntime100kVA if rating==100 else DigitalTwinMLRuntime250kVA
        self.adapter=SchemaAdapter100kVA if rating==100 else InputAdapter250kVA
    def mapping(self,adapter,columns):
        return adapter.resolve(columns) if self.rating==100 else adapter.mapping(columns)
    def validate_rating(self,rows):
        key='transformer_rating_kva'
        if any(row.get(key,self.rating)!=self.rating for row in rows):
            raise ValueError('Dataset rating does not match the selected model; mixed ratings are unsupported in one replay')
    def resolve(self,calibration,local=False):
        if self.rating==100:return resolve_calibration(calibration)
        value,issues=resolve250(calibration)
        if any(x.startswith('INVALID_CALIBRATION_FALLBACK') for x in issues):
            raise ValueError('; '.join(issues))
        return value
    def calibration_status(self,calibration):
        return calibration['calibration_status' if self.rating==100 else 'status']
    def commission(self,frame,verified,options):
        if self.rating==100:return commission_asset(frame,verified_healthy=verified,**options)
        adapter=self.adapter(**options)
        normalized=pd.DataFrame([adapter.normalize(row) for row in frame.to_dict('records')])
        self.validate_rating(normalized.to_dict('records'))
        result=commission250(normalized,verified_healthy=verified,provenance='Separate commissioning CSV; user independently attested healthy')
        return self.resolve(result)
    def payload(self,result,runtime):
        if self.rating==100:return to_frontend_payload(result)
        payload=payload250(result)
        payload['contractVersion']='1.0'
        payload['quality']={'issues':list(result['diagnostics']),
          'thermalAssessable':result['thermalScore'] is not None and not result['failed'],
          'inputTimestamp':result.get('sourceTimestamp')}
        payload['calibration']=dict(runtime.calibration)
        # Additional 100-kVA-only temporal features are unavailable, never reconstructed.
        for key in ['residualMean30minC','residualMean60minC','residualChange30minC']:
            payload['ml'][key]=None
        return payload
    def validate_calibration(self,calibration,canonical):
        if self.calibration_status(calibration)!='REFERENCE_CALIBRATION' and str(calibration['asset_id']) not in {r['asset_id'] for r in canonical}:
            raise ValueError('Supplied calibration asset binding does not match dataset.')
    def validate_selection(self,calibration,rows,replay_id=None):
        if self.calibration_status(calibration)!='REFERENCE_CALIBRATION':
            asset=replay_id if replay_id is not None else self.adapter().normalize(rows[0])['asset_id']
            if str(calibration['asset_id'])!=asset:raise ValueError('Calibration is bound to a different selected replay/asset')
    def info(self):
        runtime=self.runtime()
        return {'ratingKVA':self.rating,'modelVersion':runtime.artifact['model_version'] if self.rating==100 else runtime.config['modelVersion'],
          'modelStatus':runtime.artifact['status'] if self.rating==100 else runtime.config['modelStatus'],
          'modelSHA256':runtime.config['model_sha256'] if self.rating==100 else runtime.fingerprint,
          'engineering':{'ratedCurrentA':self.rating*1000/(math.sqrt(3)*433),'nominalPhaseVoltageV':433/math.sqrt(3)}}

from integration630 import Model630
MODELS={r:Model(r) for r in [100,250]}
MODELS[630]=Model630()
from integration100 import FinalModel100
MODELS[100]=FinalModel100()
def model_for(rating=100):return MODELS[rating_value(rating)]
