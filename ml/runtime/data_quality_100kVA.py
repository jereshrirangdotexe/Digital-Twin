"""Plausibility checks are independent of transformer condition decisions."""
from .schema_adapter_100kVA import SIGNALS

def assess(row,config):
    clean=dict(row); issues=list(row['issues']); suspect=False
    for field in SIGNALS:
        value=clean[field]
        kind='voltage' if field.startswith('voltage') else 'current' if field.startswith('current') else 'ambient' if field.startswith('ambient') else 'oil'
        lo,hi=config['physical_ranges'][kind]
        if value is not None and not lo<=value<=hi:
            clean[field]=None; issues.append('SENSOR_RANGE:'+field); suspect=True
    if row['communication_available'] is not True:
        for field in SIGNALS: clean[field]=None
        issues.append('COMMUNICATION_UNAVAILABLE')
    valid=all(clean[field] is not None for field in SIGNALS)
    clean['issues']=issues
    return clean,valid,suspect
