def interpretation(result):
    m=result['ml'];messages=[]
    if m['thermalAlert']:messages.append('Persistent unexplained top-oil deviation. Physical abnormality and gradual sensor bias remain indistinguishable without independent verification.')
    if m['electricalWarnings']:messages.append('Electrical operating limits exceeded: '+', '.join(m['electricalWarnings']))
    if m['sensorState']!='NO_DETECTED_SENSOR_ISSUE':messages.append('Data quality requires attention: '+m['sensorState'])
    return dict(healthIndex=None,healthBand=None,riskScore=None,riskLevel=None,agingState=None,maintenancePriority=None,maintenanceRecommendation=None,explanation=' '.join(messages) or 'No assessed deviation; review calibration and warm-up status.')
