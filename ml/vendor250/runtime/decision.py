"""Stable condition enums, with unknown distinct from normal."""
def apply_decision(result,score,threshold):
 r=dict(result);r['thermalScore']=score;r['thermalDecisionMargin']=None if score is None else score-threshold
 r['thermalAlert']=None if score is None else bool(score>threshold)
 r['thermalState']='THERMAL_UNASSESSED' if score is None else 'THERMAL_ALERT' if r['thermalAlert'] else 'NORMAL'
 warnings=[r['phaseLoadingWarning'],r['undervoltageWarning'],r['imbalanceWarning']]
 labels=['PHASE_LOADING_WARNING','UNDERVOLTAGE_WARNING','IMBALANCE_WARNING'];active=[label for label,flag in zip(labels,warnings) if flag is True]
 r['electricalState']='MULTIPLE_WARNINGS' if len(active)>1 else active[0] if active else 'UNASSESSED' if None in warnings else 'NORMAL'
 if r.get('_sensorSuspect'):condition='SENSOR_SUSPECT'
 elif r['thermalAlert'] is True and active:condition='MULTIPLE_CONDITIONS'
 elif r['thermalAlert'] is True:condition='THERMAL_CONDITION_ALERT'
 elif active:condition='ELECTRICAL_CONDITION_ALERT'
 elif r['thermalState']=='THERMAL_UNASSESSED' or r['electricalState']=='UNASSESSED':condition='UNASSESSED'
 else:condition='NORMAL'
 r['assetCondition']=condition;return r
