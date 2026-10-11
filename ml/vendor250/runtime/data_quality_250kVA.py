"""Observable plausibility checks; no inferred fault labels."""
import math
SIGNALS=['voltage_r_v','voltage_y_v','voltage_b_v','current_r_a','current_y_a','current_b_a','ambient_temp_c','top_oil_temp_c']

def sanitize(row):
 x=dict(row);x['_issues']=list(row.get('_issues',[]))
 for name in SIGNALS:
  value=x[name]
  limits=(0,450) if name.startswith('voltage') else (0,2500) if name.startswith('current') else (-50,70) if name=='ambient_temp_c' else (-50,200)
  if value is not None and (not math.isfinite(value) or not limits[0]<=value<=limits[1]):
   x[name]=None;x['_issues'].append('SENSOR_RANGE_INVALID:'+name)
 if x['communication_available'] is not True:
  for name in SIGNALS:x[name]=None
 return x
