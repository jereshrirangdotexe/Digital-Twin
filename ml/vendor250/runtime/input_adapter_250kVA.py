"""One schema/unit boundary. Aliases never enter model feature logic."""
import re,math
import pandas as pd

CANONICAL=['timestamp','asset_id','transformer_rating_kva','voltage_r_v','voltage_y_v','voltage_b_v','current_r_a','current_y_a','current_b_a','ambient_temp_c','top_oil_temp_c','communication_available']
ALIASES={
 'timestamp':['timestamp','timestamp_IST','time','datetime','date_time','reading_time'],
 'asset_id':['asset_id','assetId','transformer_id','device_id','replay_id'],
 'transformer_rating_kva':['transformer_rating_kva','rating_kva','ratingKVA'],
 'ambient_temp_c':['ambient_temp_C','ambient_temperature','ambient_temp','Tamb','temperature_ambient','ambientTempC'],
 'top_oil_temp_c':['top_oil_temp_C','top_oil_temperature','oil_temp','oil_temperature','Toil','topOilTempC'],
 'communication_available':['communication_available','communicationAvailable','communication_status','comm_status','online']}
for phase in 'ryb':
 ALIASES[f'voltage_{phase}_v']=[f'V{phase.upper()}_V',f'V_{phase.upper()}',f'V{phase}',f'{phase}_voltage',f'voltage_{phase}',f'{phase}_phase_voltage',f'voltage{phase.upper()}']
 ALIASES[f'current_{phase}_a']=[f'I{phase.upper()}_A',f'I_{phase.upper()}',f'I{phase}',f'{phase}_current',f'current_{phase}',f'{phase}_phase_current',f'current{phase.upper()}']
for phase,number in zip('ryb',[1,2,3]):
 ALIASES[f'voltage_{phase}_v'] += [f'V_L{number}_V',f'voltage_l{number}_v',f'VL{number}_V',f'phase{number}_voltage_V']
 ALIASES[f'current_{phase}_a'] += [f'I_L{number}_A',f'current_l{number}_a',f'IL{number}_A',f'phase{number}_current_A']

class CompatibilityError(ValueError):
 def __init__(self,code,message):self.code=code;super().__init__(code+': '+message)

def key(s):return re.sub('[^a-z0-9]','',str(s).lower())
def unit_suffix(name):
 s=str(name).strip()
 m=re.search(r'(?:[_\s\[(])(?:°\s*)?((?:kV|mA|V|A|C|F|K))(?:[\])])?$',s,re.I)
 return m.group(1).lower() if m else None
def semantic_key(name):
 s=re.sub(r'(?:[_\s\[(])(?:°\s*)?(?:kV|mA|V|A|C|F|K)(?:[\])])?$','',str(name).strip(),flags=re.I)
 return key(s)

class InputAdapter250kVA:
 def __init__(self,schema=None,units=None,asset_id='ORGANIZER_ASSET_001',timezone='Asia/Kolkata',dayfirst=None,timestamp_unit=None,voltage_basis='phase_neutral'):
  self.schema=schema or {};self.units=units or {};self.asset_id=asset_id;self.timezone=timezone;self.dayfirst=dayfirst;self.timestamp_unit=timestamp_unit;self.voltage_basis=voltage_basis;self.mapping_cache={}
  if set(self.schema)-set(CANONICAL):raise CompatibilityError('UNKNOWN_SCHEMA_FIELD',str(set(self.schema)-set(CANONICAL)))
 def mapping(self,columns):
  names=tuple(columns)
  if names in self.mapping_cache:return self.mapping_cache[names]
  if len(names)!=len(set(names)):raise CompatibilityError('DUPLICATE_COLUMN_NAME','Headers must be unique')
  mapping={}
  for canonical in CANONICAL:
   if canonical in self.schema:
    matches=[self.schema[canonical]] if self.schema[canonical] in names else []
   else:
    accepted={key(x) for x in [canonical]+ALIASES[canonical]};semantic={semantic_key(x) for x in [canonical]+ALIASES[canonical]}
    matches=[n for n in names if key(n) in accepted or semantic_key(n) in semantic]
   if len(matches)>1:raise CompatibilityError('AMBIGUOUS_COLUMN',canonical+' matches '+str(matches)+'; use --schema')
   mapping[canonical]=matches[0] if matches else None
  self.mapping_cache[names]=mapping;return mapping
 def _numeric(self,value,canonical,column,issues):
  if value is None or pd.isna(value):return None
  if isinstance(value,bool):issues.append('NON_NUMERIC:'+canonical);return None
  try:x=float(value)
  except (ValueError,TypeError):issues.append('NON_NUMERIC:'+canonical);return None
  if not math.isfinite(x):issues.append('NON_FINITE:'+canonical);return None
  group='voltage' if canonical.startswith('voltage') else 'current' if canonical.startswith('current') else 'temperature'
  unit=self.units.get(canonical,self.units.get(group)) or unit_suffix(column)
  # CamelCase canonical frontend aliases encode C; canonical internal names encode all units.
  if unit is None and str(column).endswith('TempC'):unit='c'
  if unit is None:issues.append('AMBIGUOUS_UNITS:'+canonical);return None
  unit=str(unit).lower().replace('°','').strip()
  permitted={'voltage':['v','kv'],'current':['a','ma'],'temperature':['c','f','k']}[group]
  if unit not in permitted:raise CompatibilityError('UNSUPPORTED_UNIT',canonical+'='+unit)
  if unit=='kv':x*=1000
  elif unit=='ma':x/=1000
  elif unit=='f':x=(x-32)*5/9
  elif unit=='k':x-=273.15
  return x
 def _timestamp(self,value,column,issues):
  if value is None or pd.isna(value):issues.append('TIMESTAMP_MISSING');return None
  try:
   if isinstance(value,(int,float)):
    if self.timestamp_unit not in ['s','ms','us','ns']:raise CompatibilityError('TIMESTAMP_UNIT_REQUIRED','Numeric timestamp needs s/ms/us/ns')
    t=pd.to_datetime(value,unit=self.timestamp_unit,utc=True)
   else:
    text=str(value).strip()
    match=re.match(r'^(\d{1,2})[/-](\d{1,2})[/-]\d{4}',text)
    if match and int(match[1])<=12 and int(match[2])<=12 and self.dayfirst is None:
     issues.append('AMBIGUOUS_TIMESTAMP');return None
    t=pd.Timestamp(pd.to_datetime(text,dayfirst=bool(self.dayfirst)))
    if t.tzinfo is None:
     if not self.timezone:issues.append('TIMEZONE_REQUIRED');return None
     t=t.tz_localize(self.timezone,ambiguous='raise',nonexistent='raise')
     if column!='timestamp_IST':issues.append('TIMEZONE_ASSUMED:'+self.timezone)
   if pd.isna(t):issues.append('TIMESTAMP_INVALID');return None
   return t.isoformat()
  except CompatibilityError:raise
  except (ValueError,TypeError,OverflowError):issues.append('TIMESTAMP_INVALID');return None
 def normalize(self,row):
  mapping=self.mapping(row.keys());issues=[];out={name:None for name in CANONICAL}
  for name in CANONICAL:
   column=mapping[name];value=row.get(column) if column else None
   if name=='timestamp':out[name]=self._timestamp(value,column,issues)
   elif name=='asset_id':out[name]=self.asset_id if value is None or pd.isna(value) else str(value)
   elif name=='transformer_rating_kva':
    try:out[name]=250. if value is None or pd.isna(value) else float(value)
    except (ValueError,TypeError):issues.append('INVALID_RATING')
   elif name=='communication_available':
    if value is not None and not pd.isna(value):
     status=str(value).strip().lower()
     if status in ['true','1','1.0','online','available','yes','good']:out[name]=True
     elif status in ['false','0','0.0','offline','missing','unavailable','no']:out[name]=False
     else:issues.append('UNKNOWN_COMMUNICATION_STATUS')
   elif column:out[name]=self._numeric(value,name,column,issues)
  if mapping['communication_available'] is None:
   out['communication_available']=any(out[x] is not None for x in CANONICAL if x.startswith(('voltage','current','ambient','top_oil')))
   issues.append('COMMUNICATION_ASSUMED_FROM_RECEPTION')
  if out['transformer_rating_kva']!=250:issues.append('UNSUPPORTED_TRANSFORMER_RATING')
  if self.voltage_basis!='phase_neutral':
   for name in CANONICAL:
    if name.startswith('voltage'):out[name]=None
   issues.append('UNSUPPORTED_VOLTAGE_BASIS')
  for name in CANONICAL:
   if name.startswith(('voltage','current','ambient','top_oil')) and out[name] is None:issues.append('REQUIRED_SIGNAL_MISSING:'+name)
  out['_issues']=list(dict.fromkeys(issues));out['_sourceTimestamp']=None if mapping['timestamp'] is None else str(row.get(mapping['timestamp']));return out
