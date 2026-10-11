"""Backend transport-ready JSON contract v1; no invented health or RUL values."""
import json,math
from .digital_twin_adapter_100kVA import to_digital_twin_result

ML_FIELDS=['expectedOilTempC','thermalResidualC','residualMean30minC','residualMean60minC','residualChange30minC',
 'thermalScore','thermalDecisionMargin','thermalAlert','thermalState','phaseLoadingWarning','undervoltageWarning',
 'imbalanceWarning','electricalState','dataConfidence','assetCondition','calibrationStatus','warmupStatus','modelVersion','modelStatus','runtimeVersion']

def sanitize(value):
    if isinstance(value,dict): return {str(k):sanitize(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [sanitize(v) for v in value]
    if hasattr(value,'item'): return sanitize(value.item())
    if isinstance(value,float) and not math.isfinite(value): return None
    return value

def to_frontend_payload(result):
    r=to_digital_twin_result(result)
    payload=dict(contractVersion='1.0',asset=dict(id=r['assetId'],ratingKVA=100,status='ONLINE' if r['telemetry']['communicationAvailable'] is True else 'OFFLINE' if r['telemetry']['communicationAvailable'] is False else 'UNKNOWN'),
      timestamp=r['timestamp'],telemetry=r['telemetry'],ml={k:r[k] for k in ML_FIELDS},
      calibration=r['calibration'],quality=dict(issues=r['qualityIssues'],thermalAssessable=r['thermalAssessable'],inputTimestamp=r['inputTimestamp']),
      digitalTwin={k:None for k in ['healthIndex','healthBand','riskScore','riskLevel','agingState','maintenancePriority','maintenanceRecommendation','explanation']})
    payload=sanitize(payload)
    json.dumps(payload,allow_nan=False)
    return payload

def to_history_point(result):
    p=to_frontend_payload(result)
    return dict(assetId=p['asset']['id'],timestamp=p['timestamp'],actualOilTempC=p['telemetry']['topOilTempC'],**p['telemetry'],**p['ml'])
