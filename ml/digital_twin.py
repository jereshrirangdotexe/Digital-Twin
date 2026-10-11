"""Transparent operational observation rules; never alters or feeds back into ML."""
import math

TWIN_VERSION='VoltMind_Operational_Observation_v1.0'

def interpret(payload):
    ml=payload['ml'];telemetry=payload['telemetry'];quality=payload['quality']
    issues=quality['issues'];flags=[ml[k] for k in ['phaseLoadingWarning','undervoltageWarning','imbalanceWarning']]
    currents=[telemetry[k] for k in ['currentR','currentY','currentB']]
    rated=payload['asset']['ratingKVA']*1000/(math.sqrt(3)*433)
    max_loading=max(currents)/rated*100 if all(v is not None for v in currents) else None
    reliable=quality['thermalAssessable'] and ml['dataConfidence']!='UNAVAILABLE' and ml['assetCondition']!='SENSOR_SUSPECT'
    drivers=[]
    if ml['thermalAlert'] is True: drivers.append('LOCKED_ML_THERMAL_ALERT')
    for key,flag in zip(['PHASE_LOADING','UNDERVOLTAGE','CURRENT_IMBALANCE'],flags):
        if flag is True: drivers.append(key)
    reference=ml['calibrationStatus'] in ['REFERENCE_CALIBRATION','REFERENCE_PROVISIONAL','KNOWN_SYNTHETIC_REFERENCE'] or payload.get('syntheticCalibration',False)
    if reference: drivers.append('REFERENCE_CALIBRATION_UNCERTAINTY')
    sensor=any(s.startswith(('SENSOR_RANGE','OIL_SENSOR','FROZEN_TELEMETRY','STUCK_CHANNEL')) for s in issues) or (payload['asset']['ratingKVA']==630 and ml['assetCondition']=='SENSOR_SUSPECT')
    result=dict(version=TWIN_VERSION,healthIndex=None,healthBand='UNASSESSED',riskScore=None,riskLevel='UNASSESSED',
       riskDrivers=drivers,agingState=None,rulEstimate=None,maintenancePriority='DATA_REQUIRED',
       maintenanceRecommendation='Collect the required clean history before interpreting thermal condition.',
       explanation='Thermal condition is currently unassessed; absence of an alert is not evidence of health.',
       scoreScope='Prototype operational observation index; not certified insulation health or failure probability.',
       formulaComponents=None,maxPhaseLoadingPct=max_loading,ratedCurrentA=rated,
       assessmentReliability=ml['dataConfidence'],thermalSeverity='UNASSESSED',inspectionUrgency='ASSESSMENT_REQUIRED')
    if telemetry['communicationAvailable'] is not True:
        result.update(maintenancePriority='RESTORE_TELEMETRY',maintenanceRecommendation='Restore communications and verify timestamped sensor readings before assessment.',explanation='Communication is unavailable or unknown; current asset health and risk cannot be assessed.',inspectionUrgency='RESTORE_DATA')
    elif sensor:
        result.update(maintenancePriority='VERIFY_SENSORS',maintenanceRecommendation='Verify the affected sensors and wiring. Reassess after clean history is restored.',explanation='Sensor-suspect evidence: '+', '.join(s for s in issues if payload['asset']['ratingKVA']==630 or s.startswith(('SENSOR_RANGE','OIL_SENSOR','FROZEN_TELEMETRY','STUCK_CHANNEL'))),inspectionUrgency='SENSOR_REVIEW')
    elif reliable:
        components=dict(observation_uncertainty=10,reference_calibration_uncertainty=10 if reference else 0,
           thermal_alert=40 if ml['thermalAlert'] is True else 0,
           electrical_warnings=10*sum(f is True for f in flags),
           loading_stress=min(15,max(0,(max_loading or 0)-100)*.3),
           positive_residual_stress=min(15,max(0,ml['thermalResidualC'] or 0)*1.5))
        risk=round(min(100,sum(components.values())),1);health=round(100-risk,1)
        level='LOW' if risk<30 else 'MODERATE' if risk<50 else 'HIGH' if risk<75 else 'CRITICAL'
        band='OBSERVED_STABLE' if health>=75 else 'WATCH' if health>=55 else 'ELEVATED_STRESS' if health>=35 else 'HIGH_STRESS'
        result.update(healthIndex=health,healthBand=band,riskScore=risk,riskLevel=level,formulaComponents=components,
          thermalSeverity='ALERT' if ml['thermalAlert'] is True else 'NO_MODEL_ALERT')
        if ml['thermalAlert'] is True:
            result.update(maintenancePriority='PROMPT_INSPECTION',inspectionUrgency='PROMPT_QUALIFIED_REVIEW',maintenanceRecommendation='Arrange qualified inspection of cooling, loading and the oil probe; verify the observed thermal deviation.',explanation=f"The locked model reports thermal excess. Measured oil is {ml['thermalResidualC']:.2f} C above its calibrated expected response. Electrical warnings are evaluated separately.")
        elif any(f is True for f in flags):
            result.update(maintenancePriority='REVIEW_OPERATING_WARNING',inspectionUrgency='OPERATING_REVIEW',maintenanceRecommendation='Review phase loading, voltage and current balance against the active engineering warnings.',explanation='Measured operating warnings: '+', '.join(d for d in drivers if d!='REFERENCE_CALIBRATION_UNCERTAINTY')+'. They do not establish transformer thermal failure.')
        elif risk>=30:
            result.update(maintenancePriority='TREND_REVIEW',inspectionUrgency='TREND_REVIEW',maintenanceRecommendation='Review the positive residual and loading trend; confirm asset-specific calibration before maintenance decisions.',explanation='No locked-model thermal alarm is active. The documented prototype index reflects observed residual/loading stress and calibration uncertainty.')
        else:
            result.update(maintenancePriority='ROUTINE_OBSERVATION',inspectionUrgency='ROUTINE',maintenanceRecommendation='Continue observation and confirm independently verified asset commissioning.',explanation='No active locked-model thermal or engineering warning is observed on this assessable row. This is not a certification of transformer health.')
        if reference: result['explanation']+=' Synthetic reference calibration transfer is unverified; this index is provisional.'
    elif any(f is True for f in flags):
        result.update(maintenancePriority='REVIEW_OPERATING_WARNING',maintenanceRecommendation='Review the known electrical warning while collecting clean thermal history.',explanation='Electrical operating warnings are present, but the thermal model is not assessable. Numeric health and risk are withheld.',inspectionUrgency='OPERATING_REVIEW')
    if payload['asset']['ratingKVA']==630:
        result['explanation']+=' The 630-kVA detector observes persistent deviation; physical change and gradual sensor bias require independent verification.'
        result['scoreScope']+=' Added by the shared dashboard interpretation; the source 630-kVA detector provides no validated health or risk index.'
    if payload['asset']['ratingKVA']==100:
        optional=[name for name,key in [('oil inventory depletion','oilAlert'),('R-phase LV terminal surface heating','terminalAlert')] if ml.get(key) is True]
        result['optionalDetectorAlerts']=optional
        result['scoreScope']+=' Numeric score covers thermal/electrical observations; experimental oil and terminal detectors are reported separately.'
        if optional:
            result['riskDrivers']+=['EXPERIMENTAL_OPTIONAL_SENSOR_ALERT']
            if result['maintenancePriority'] not in ['RESTORE_TELEMETRY','VERIFY_SENSORS']:
                result.update(maintenancePriority='PROMPT_INSPECTION',inspectionUrgency='PROMPT_QUALIFIED_REVIEW',
                  maintenanceRecommendation='Independently verify the '+', '.join(optional)+' indication; inspect the relevant gauge or terminal before assigning a physical fault.')
            result['explanation']+=' Separate experimental indication: '+', '.join(optional)+'. It is not a confirmed component diagnosis.'
    payload['digitalTwin']=result
    payload['asset'].update(ratedCurrent=rated,nominalVoltage=433/math.sqrt(3),coolingType='ONAN',samplingInterval='5 min')
    return payload
