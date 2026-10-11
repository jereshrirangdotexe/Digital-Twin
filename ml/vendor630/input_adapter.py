import math
from datetime import datetime,timezone,timedelta
ALIASES={'timestamp':['timestamp','time','datetime','date_time'], 'asset_id':['asset_id','asset','transformer_id'], 'replay_id':['replay_id','replay'], 'VR_V':['VR_V','VR','voltage_r'], 'VY_V':['VY_V','VY','voltage_y'], 'VB_V':['VB_V','VB','voltage_b'], 'IR_A':['IR_A','IR','current_r'], 'IY_A':['IY_A','IY','current_y'], 'IB_A':['IB_A','IB','current_b'], 'ambient_temp_C':['ambient_temp_C','ambient','ambient_temperature'], 'top_oil_temp_C':['top_oil_temp_C','top_oil','oil_temperature'], 'communication_available':['communication_available','communication','packet_available'], 'transformer_rating_kva':['transformer_rating_kva','rating_kva']}
REQUIRED=['timestamp','VR_V','VY_V','VB_V','IR_A','IY_A','IB_A','ambient_temp_C','top_oil_temp_C']
NUMERIC=[x for x in REQUIRED if x!='timestamp']
def timestamp(value,tz=None):
    if not value:raise ValueError('Missing timestamp')
    s=str(value).strip();dt=datetime.fromisoformat(s.replace('Z','+00:00'))
    if dt.tzinfo is None:
        if not tz: raise ValueError('Naive timestamp requires explicit --timezone, e.g. +05:30')
        sign=1 if tz[0]=='+' else -1;h,m=map(int,tz[1:].split(':'));dt=dt.replace(tzinfo=timezone(sign*timedelta(hours=h,minutes=m)))
    return dt.astimezone(timezone.utc)
class InputAdapter:
    def __init__(self,schema=None,units=None,tz=None,asset_id='EXTERNAL-630'):
        self.schema=schema or {};self.units=units or {};self.tz=tz;self.asset_id=asset_id
        allowed={**{k:{'V','kV'} for k in ['VR_V','VY_V','VB_V']},**{k:{'A','kA'} for k in ['IR_A','IY_A','IB_A']},**{k:{'C','K','F'} for k in ['ambient_temp_C','top_oil_temp_C']}}
        for k,u in self.units.items():
            if k not in allowed or u not in allowed[k]:raise ValueError(f'Unsupported unit {k}={u}')
    def normalize(self,row):
        lower={str(k).lower():v for k,v in row.items() if k is not None};out={};problems=[]
        for target,names in ALIASES.items():
            keys=[self.schema[target]] if target in self.schema else names
            found=[lower[n.lower()] for n in keys if n.lower() in lower]
            if len(found)>1 and len({str(v) for v in found})>1:raise ValueError('Conflicting aliases for '+target)
            out[target]=found[0] if found else None
        out['asset_id']=str(out['asset_id'] or self.asset_id);out['replay_id']=str(out['replay_id'] or 'external')
        dt=timestamp(out['timestamp'],self.tz);out['timestamp']=dt.isoformat();out['_dt']=dt
        for k in NUMERIC:
            try:
                v=float(out[k]);u=self.units.get(k)
                if not math.isfinite(v):raise ValueError()
                if u in ['kV','kA']:v*=1000
                if u=='K':v-=273.15
                if u=='F':v=(v-32)*5/9
                out[k]=v
            except (TypeError,ValueError):out[k]=None;problems.append('MISSING_OR_INVALID_'+k)
        for k in ['VR_V','VY_V','VB_V']:
            if out[k] is not None and not 100<=out[k]<=330:problems.append('OUT_OF_RANGE_'+k)
        for k in ['IR_A','IY_A','IB_A']:
            if out[k] is not None and not 0<=out[k]<=2000:problems.append('OUT_OF_RANGE_'+k)
        if out['ambient_temp_C'] is not None and not -20<=out['ambient_temp_C']<=60:problems.append('OUT_OF_RANGE_AMBIENT')
        if out['top_oil_temp_C'] is not None and not -20<=out['top_oil_temp_C']<=160:problems.append('OUT_OF_RANGE_OIL')
        raw=out['communication_available']
        if raw is None or raw=='':out['communication_available']=None
        elif str(raw).lower() in ['1','true','1.0']:out['communication_available']=True
        elif str(raw).lower() in ['0','false','0.0']:out['communication_available']=False
        else:out['communication_available']=None;problems.append('INVALID_COMMUNICATION_FLAG')
        rating=out['transformer_rating_kva']
        if rating not in (None,'') and float(rating)!=630:raise ValueError('Only 630-kVA assets are supported')
        out['transformer_rating_kva']=630;out['_problems']=problems
        return out
