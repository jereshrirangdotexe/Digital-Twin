import json
from pathlib import Path
ML_FIELDS=['expectedOilTempC','thermalResidualC','thermalResidualTrendCPerMin','thermalResidualMean30minC','nominalModelResidualC','thermalScore','thermalDecisionMargin','thermalAlert','thermalState','phaseLoadingWarning','undervoltageWarning','imbalanceWarning','electricalState','dataConfidence','assetCondition','calibrationStatus','warmupStatus','modelVersion','modelStatus','runtimeVersion','lowOilGaugeAssessment']

def to_frontend_payload(result):
 payload={'asset':{'id':result['assetId'],'ratingKVA':result['transformerRatingKVA'],'status':'OFFLINE' if result['telemetry']['communicationAvailable'] is False else 'ONLINE' if result['telemetry']['communicationAvailable'] is True else 'UNKNOWN'},'timestamp':result['timestamp'],'telemetry':dict(result['telemetry']),'ml':{k:result[k] for k in ML_FIELDS},'diagnostics':list(result['diagnostics']),'failed':result['failed'],'digitalTwin':result.get('digitalTwin',{'healthIndex':None,'healthBand':None,'riskScore':None,'riskLevel':None,'agingState':None,'maintenancePriority':None,'maintenanceRecommendation':None,'explanation':None})}
 json.dumps(payload,allow_nan=False);return payload

def to_history_point(result):
 return {**{'timestamp':result['timestamp'],'actualOilTempC':result['actualOilTempC'],'expectedOilTempC':result['expectedOilTempC'],'thermalResidualC':result['thermalResidualC'],'thermalScore':result['thermalScore'],'thermalState':result['thermalState'],'electricalState':result['electricalState'],'dataConfidence':result['dataConfidence']},**{k:v for k,v in result['telemetry'].items() if k!='communicationAvailable'}}

def to_history(results):return [to_history_point(r) for r in results]

_CONTRACT=None
def validate_frontend_payload(payload):
 global _CONTRACT
 if _CONTRACT is None:_CONTRACT=json.loads((Path(__file__).resolve().parents[1]/'config/250kVA_frontend_contract.json').read_text())
 for spec in _CONTRACT['fields']:
  value=payload
  for part in spec['name'].split('.'):
   if not isinstance(value,dict) or part not in value:raise ValueError('FRONTEND_FIELD_MISSING:'+spec['name'])
   value=value[part]
  if value is None:
   if not spec['nullable']:raise ValueError('FRONTEND_NULL_INVALID:'+spec['name'])
   continue
  correct=(isinstance(value,str) if spec['type']=='string' else isinstance(value,bool) if spec['type']=='boolean' else isinstance(value,(float,int)) and not isinstance(value,bool) if spec['type']=='number' else isinstance(value,list))
  if not correct:raise ValueError('FRONTEND_TYPE_INVALID:'+spec['name'])
  if spec.get('enum') and value not in spec['enum']:raise ValueError('FRONTEND_ENUM_INVALID:'+spec['name'])
 json.dumps(payload,allow_nan=False);return True
