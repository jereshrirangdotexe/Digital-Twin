"""Single safe schema boundary. Unknown columns are inert; ambiguous aliases fail."""
import re, math
import pandas as pd

class CompatibilityError(ValueError):
    pass

SIGNALS=['voltage_r_v','voltage_y_v','voltage_b_v','current_r_a','current_y_a','current_b_a','ambient_temp_c','top_oil_temp_c']
LEGACY=['VR_V','VY_V','VB_V','IR_A','IY_A','IB_A','ambient_temp_C','top_oil_temp_C']
ALIASES={
 'timestamp':['timestamp_IST','timestamp','time','datetime','date_time','reading_time','recorded_at'],
 'asset_id':['asset_id','assetId','transformer_id','replay_id'],
 'transformer_rating_kva':['transformer_rating_kva','rating_kva','transformerRatingKVA'],
 'ambient_temp_c':['ambient_temp_C','ambient_temperature','ambient_temp','Tamb','temperature_ambient','ambient'],
 'top_oil_temp_c':['top_oil_temp_C','top_oil_temperature','top_oil_temp','oil_temp','oil_temperature','Toil'],
 'communication_available':['communication_available','communicationAvailable','comm_available','online'],
 'loading_pct':['loading_pct','loading_percent','loading_est_pct','loading_fraction'],
}
for phase,letter in [('r','R'),('y','Y'),('b','B')]:
    ALIASES[f'voltage_{phase}_v']=[f'V{letter}_V',f'V_{letter}',f'V{letter}',f'{letter}_voltage',f'voltage_{phase}',f'{phase}_phase_voltage',f'phase_{phase}_voltage',f'voltage_{phase}_v']
    ALIASES[f'current_{phase}_a']=[f'I{letter}_A',f'I_{letter}',f'I{letter}',f'{letter}_current',f'current_{phase}',f'{phase}_phase_current',f'phase_{phase}_current',f'current_{phase}_a']

# Common phase-1/2/3 and phase-A/C labels. Phase B alone remains RYB-B;
# ABC sources should supply an explicit schema to prevent swapping phases.
for index,phase in enumerate(['r','y','b'],1):
    ALIASES[f'voltage_{phase}_v'] += [f'voltage_l{index}_n',f'voltage_l{index}',f'voltage_phase_{index}',f'V{index}_V']
    ALIASES[f'current_{phase}_a'] += [f'current_l{index}',f'current_phase_{index}',f'I{index}_A']
ALIASES['voltage_r_v'] += ['voltage_phase_a','phase_a_voltage']
ALIASES['voltage_b_v'] += ['voltage_phase_c','phase_c_voltage']
ALIASES['current_r_a'] += ['current_phase_a','phase_a_current']
ALIASES['current_b_a'] += ['current_phase_c','phase_c_current']

def norm(name):
    return re.sub('[^a-z0-9]','',str(name).lower())

def number(value):
    try:
        x=float(value)
        return x if math.isfinite(x) else None
    except (TypeError,ValueError):
        return None

def default_unit(field):
    return '%' if field=='loading_pct' else 'V' if field.startswith('voltage') else 'A' if field.startswith('current') else 'C'

def declared_aliases(field):
    """Add only explicit physical unit suffixes to recognized stems."""
    aliases={norm(v):default_unit(field) for v in ALIASES[field]}
    if field=='loading_pct': aliases[norm('loading_fraction')]='fraction'
    units=['V','kV'] if field.startswith('voltage') else ['A','mA','kA'] if field.startswith('current') else ['C','F','K'] if field in SIGNALS else []
    stems=set(ALIASES[field])
    for alias in ALIASES[field]:
        if alias.lower().endswith(('_v','_a','_c')):
            stems.add(alias[:-2])
    for stem in stems:
        for unit in units:
            aliases[norm(stem+'_'+unit)]=unit
    return aliases

class SchemaAdapter100kVA:
    def __init__(self,schema=None,units=None,timezone='Asia/Kolkata',asset_id=None):
        self.schema=dict(schema or {}) # canonical field -> exact raw column
        self.units=dict(units or {}) # canonical field -> explicitly declared unit
        self.timezone=timezone
        self.asset_id=asset_id
        unknown=(set(self.schema)|set(self.units))-set(ALIASES)
        if unknown:
            raise CompatibilityError('Unknown canonical mapping fields: '+', '.join(sorted(unknown)))
        self._cache={}

    def resolve(self,columns):
        columns=tuple(columns)
        if columns in self._cache:
            return self._cache[columns]
        result={}
        for field in ALIASES:
            if field in self.schema:
                col=self.schema[field]
                if col not in columns:
                    raise CompatibilityError(f'Explicit mapping for {field} references absent column {col}')
                matches=[col]; unit=default_unit(field)
            else:
                variants=declared_aliases(field)
                matches=[col for col in columns if norm(col) in variants]
                unit=variants[norm(matches[0])] if matches else default_unit(field)
            if len(matches)>1:
                raise CompatibilityError(f'Ambiguous {field}: {matches}. Supply --schema to select one.')
            if matches:
                result[field]=(matches[0],self.units.get(field,unit))
        assigned=[v[0] for v in result.values()]
        if len(assigned)!=len(set(assigned)):
            raise CompatibilityError('A raw column cannot represent multiple canonical signals')
        if 'timestamp' not in result:
            raise CompatibilityError('Missing timestamp column; supply --schema with a timestamp mapping')
        self._cache[columns]=result
        return result

    def normalize(self,row):
        mapping=self.resolve(row.keys())
        out={}; issues=[]
        for field,(col,unit) in mapping.items():
            value=row[col]
            if field in SIGNALS:
                suffix=re.search(r'(?:_|\s|\[|\()(kV|mA|kA|V|A|C|F|K)(?:\]|\))?$',str(col),re.I)
                if field not in self.units and not suffix:
                    issues.append('UNIT_CONTRACT_ASSUMED:'+field+'='+unit)
                value=number(value)
                allowed={'V':1,'kV':1000} if field.startswith('voltage') else {'A':1,'mA':.001,'kA':1000} if field.startswith('current') else {'C':1,'F':1,'K':1}
                if unit not in allowed:
                    raise CompatibilityError(f'Unsupported unit {unit!r} for {field}; use V/kV, A/mA/kA or C/F/K as applicable')
                if value is not None:
                    value=(value-32)*5/9 if unit=='F' else value-273.15 if unit=='K' else value*allowed[unit]
            elif field=='loading_pct':
                if unit not in ['%','pct','percent','fraction']:
                    raise CompatibilityError('Unsupported loading unit; declare % or fraction')
                value=number(value)
                if value is not None:
                    value=value*100 if unit=='fraction' else value
                    if value<0:
                        value=None;issues.append('INVALID_LOADING_VALUE')
            out[field]=value
        for field in SIGNALS:
            out.setdefault(field,None)
            if out[field] is None:
                issues.append('REQUIRED_SIGNAL_MISSING:'+field)
        raw_timestamp=out['timestamp']
        try:
            if isinstance(raw_timestamp,(int,float)):
                raise ValueError('Numeric epoch requires prior explicit conversion to ISO-8601')
            ambiguous_date=re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})(?:\s|T|$)',str(raw_timestamp))
            if ambiguous_date and int(ambiguous_date[1])<=12 and int(ambiguous_date[2])<=12:
                raise ValueError('Ambiguous day/month timestamp requires explicit ISO-8601 conversion')
            t=pd.Timestamp(raw_timestamp)
            if pd.isna(t):
                raise ValueError('Missing timestamp')
            if t.tzinfo is None:
                if not self.timezone:
                    raise CompatibilityError('Naive timestamp requires --timezone')
                t=t.tz_localize(self.timezone,ambiguous='raise',nonexistent='raise')
            out['timestamp']=t.isoformat()
        except CompatibilityError:
            raise
        except (ValueError,TypeError,OverflowError):
            out['timestamp']=None; issues.append('INVALID_TIMESTAMP')
        rid=out.get('asset_id')
        if self.asset_id and rid is not None and str(rid)!=self.asset_id:
            raise CompatibilityError('Asset override conflicts with input asset ID; split assets before overriding')
        out['asset_id']=self.asset_id or (str(rid) if rid is not None and not pd.isna(rid) and str(rid).strip() else 'ORGANIZER_ASSET_001')
        rating=number(out.get('transformer_rating_kva',100))
        if rating!=100:
            raise CompatibilityError('Only 100-kVA input is supported; rating must equal 100')
        out['transformer_rating_kva']=100
        if 'communication_available' not in out:
            out['communication_available']=True
            issues.append('COMMUNICATION_ASSUMED_AVAILABLE')
        else:
            val=out['communication_available']
            if isinstance(val,str):
                val=val.strip().lower()
                if val in ['true','online','1','1.0']: val=True
                elif val in ['false','offline','0','0.0']: val=False
                else: val=None
            elif number(val) in [0,1]:
                val=bool(number(val))
            else: val=None
            out['communication_available']=val
            if val is None: issues.append('INVALID_COMMUNICATION_FLAG')
        out['input_timestamp']=str(raw_timestamp)
        out['issues']=issues
        return out
