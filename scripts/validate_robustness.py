"""Execute real adapter/runtime robustness scenarios without model fitting."""
from pathlib import Path
import sys,json
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ml'))
from main import predict_batch,to_frontend_payload
from runtime.schema_adapter_100kVA import SIGNALS,LEGACY
from runtime.thermal_model import expected_oil
from calibration.commission_100kVA import resolve_calibration
def mutate(frame,column,rows,value):
    f=frame.copy();f.loc[rows,column]=value;return f

def robustness_matrix(base):
    """Each case executes a real adapter/runtime; assertions define safe behavior."""
    cases=[]
    def add(name,frame=None,expect='continue',reason=None,options=None,check=None):
        cases.append(dict(name=name,frame=frame,expect=expect,reason=reason,options=options or {},check=check))
    add('canonical schema',base.rename(columns=dict(zip(LEGACY,SIGNALS))).rename(columns={'replay_id':'asset_id','timestamp_IST':'timestamp'}))
    add('columns reordered',base[list(reversed(base.columns))])
    aliases={'timestamp_IST':'recorded_at','VR_V':'R_voltage','VY_V':'Y_voltage','VB_V':'B_voltage','IR_A':'R_current','IY_A':'Y_current','IB_A':'B_current','ambient_temp_C':'Tamb','top_oil_temp_C':'Toil'}
    add('safe aliases',base.rename(columns=aliases))
    add('mixed capitalization',base.rename(columns={k:k.swapcase() for k in base}))
    add('spaces instead of underscores',base.rename(columns={k:k.replace('_',' ') for k in base}))
    add('extra columns',pd.concat([base,pd.DataFrame({f'extra_{k}':k for k in range(200)},index=base.index)],axis=1))
    add('no replay_id',base.drop(columns=['replay_id']))
    add('no asset_id',base.drop(columns=['replay_id']))
    add('missing optional columns',base[['replay_id','timestamp_IST']+LEGACY])
    add('required signal missing',base.drop(columns=['ambient_temp_C']),check=lambda r: all(not x['thermalAssessable'] for x in r))
    add('isolated NaN',mutate(base,'top_oil_temp_C',310,np.nan),check=lambda r:not r[310]['thermalAssessable'])
    add('first snapshot missing',mutate(base,'IR_A',0,np.nan),check=lambda r:r[0]['expectedOilTempC'] is None)
    add('isolated missing sample',base.drop(index=310),check=lambda r:'HISTORY_RESET' in r[310]['qualityIssues'])
    add('long missing gap',base.drop(index=range(290,330)),check=lambda r:not r[290]['thermalAssessable'])
    add('communication outage',mutate(base,'communication_available',slice(310,315),0),check=lambda r:all(x['dataConfidence']=='UNAVAILABLE' and x['thermalAlert'] is None for x in r[310:316]))
    add('prolonged driver loss',mutate(base,'IR_A',slice(300,340),np.nan),check=lambda r:all(not x['thermalAssessable'] for x in r[300:]))
    add('duplicate timestamps',mutate(base,'timestamp_IST',310,base.loc[309,'timestamp_IST']),check=lambda r:'DUPLICATE_TIMESTAMP' in r[310]['qualityIssues'])
    add('duplicate rows',pd.concat([base.iloc[:310],base.iloc[[309]],base.iloc[310:]],ignore_index=True),check=lambda r:'DUPLICATE_TIMESTAMP' in r[310]['qualityIssues'])
    add('out-of-order timestamps',mutate(base,'timestamp_IST',310,base.loc[300,'timestamp_IST']),check=lambda r:'OUT_OF_ORDER_TIMESTAMP' in r[310]['qualityIssues'])
    add('timestamp corruption',mutate(base,'timestamp_IST',310,'bad'),check=lambda r:r[310]['timestamp'] is None and r[310]['thermalAlert'] is None)
    f=base.copy();f.timestamp_IST=pd.to_datetime(f.timestamp_IST,utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ');add('timezone differences',f)
    f=base.copy();f.timestamp_IST=pd.to_datetime(f.timestamp_IST,utc=True).dt.tz_convert('Asia/Kolkata').dt.strftime('%Y/%m/%d %H:%M:%S');add('timestamp string variants',f)
    f=base.copy();f.timestamp_IST=pd.date_range('2026-01-01',periods=len(f),freq='1min').astype(str);add('different sampling interval',f,check=lambda r:all(not x['thermalAssessable'] for x in r))
    f=base.copy();f.loc[310:,'timestamp_IST']=pd.date_range(pd.Timestamp(base.timestamp_IST.iloc[310])+pd.Timedelta(minutes=1),periods=len(base)-310,freq='5min').astype(str);add('irregular sampling',f,check=lambda r:not r[310]['thermalAssessable'])
    for offset in [1,-1]:
        add(f'oil {offset:+d} C bias',mutate(base,'top_oil_temp_C',slice(None),base.top_oil_temp_C+offset))
    add('temperature quantization',mutate(base,'top_oil_temp_C',slice(None),(base.top_oil_temp_C/2).round()*2))
    noise=np.random.default_rng(100).normal(0,.1,len(base))
    add('small random sensor noise',mutate(base,'top_oil_temp_C',slice(None),base.top_oil_temp_C+noise))
    add('oil sensor spike',mutate(base,'top_oil_temp_C',310,base.loc[310,'top_oil_temp_C']+10),check=lambda r:'OIL_SENSOR_JUMP' in r[310]['qualityIssues'])
    f=base.copy();f.loc[280:,'top_oil_temp_C']=40;f.loc[280:,'ambient_temp_C']=50;f.loc[280:,['IR_A','IY_A','IB_A']]=150
    add('stuck oil sensor',f,check=lambda r:any('OIL_SENSOR_STUCK_SUSPECT' in x['qualityIssues'] for x in r))
    add('voltage sensor corruption',mutate(base,'VR_V',310,-100),check=lambda r:r[310]['thermalAlert'] is None and r[310]['assetCondition']=='SENSOR_SUSPECT')
    add('current sensor corruption',mutate(base,'IR_A',310,10000),check=lambda r:r[310]['thermalAlert'] is None and r[310]['assetCondition']=='SENSOR_SUSPECT')
    f=base.copy();f.loc[300:,LEGACY]=base.loc[300,LEGACY].to_numpy();add('frozen telemetry',f,check=lambda r:any('FROZEN_TELEMETRY_SUSPECT' in x['qualityIssues'] for x in r))
    f=base.copy();f.loc[280:,'IR_A']=100;f.loc[280:,'IY_A']=np.linspace(20,160,80);add('constant-valued channel',f,check=lambda r:any('STUCK_CHANNEL_SUSPECT:current_r_a' in x['qualityIssues'] for x in r))
    for name,current in [('low load',5),('high but healthy load',180),('load distribution shift',110)]:
        f=base.copy();f[['IR_A','IY_A','IB_A']]=current
        f['top_oil_temp_C']=expected_oil(f,**{k:resolve_calibration()[k] for k in ['rise','tau','bias','loss_ratio']})
        add(name,f,check=lambda r:all(x['thermalAlert'] is not True for x in r))
    f=base.copy();f.ambient_temp_C+=5;add('ambient temperature shift',f)
    f=base.copy();f['VR_V']=200;add('undervoltage without forced thermal fault',f,check=lambda r:r[-1]['undervoltageWarning'] is True)
    f=base.copy();f[['IR_A','IY_A','IB_A']]=[30,150,60];f['top_oil_temp_C']=expected_oil(f,**{k:resolve_calibration()[k] for k in ['rise','tau','bias','loss_ratio']});add('phase imbalance without thermal fault',f,check=lambda r:r[-1]['imbalanceWarning'] is True and r[-1]['thermalAlert'] is False)
    add('incomplete warm-up',base.iloc[:100],check=lambda r:all(x['thermalAlert'] is None for x in r))
    add('very short history',base.iloc[:3],check=lambda r:all(x['thermalAlert'] is None for x in r))
    add('one-row CSV',base.iloc[:1],check=lambda r:r[0]['warmupStatus']=='WARMING_UP')
    add('empty CSV',base.iloc[:0],expect='error',reason='EMPTY_INPUT')
    add('wrong transformer rating',base.assign(rating_kva=250),expect='error',reason='100-kVA')
    add('unsupported units',base,expect='error',reason='Unsupported unit',options={'units':{'voltage_r_v':'unknown'}})
    f=base.copy();f['VR_kV']=f.pop('VR_V')/1000;f['Toil_F']=f.pop('top_oil_temp_C')*9/5+32;add('explicit unit conversion',f)
    add('ambiguous alias',base.assign(Tamb=30),expect='error',reason='Ambiguous')
    add('explicit schema override',base.rename(columns={'ambient_temp_C':'sensor_42'}),options={'schema':{'ambient_temp_c':'sensor_42'}})
    corrupt=resolve_calibration();corrupt['tau']=float('nan');add('corrupted calibration',base,expect='error',reason='Calibration tau',options={'calibration':corrupt})
    add('missing calibration reference fallback',base,check=lambda r:all(x['calibrationStatus']=='REFERENCE_CALIBRATION' for x in r))
    outputs=[]
    for case in cases:
        name=case['name']
        try:
            options=dict(case['options']);cal=options.pop('calibration',None)
            predictions=predict_batch(case['frame'],cal,**options)
            assert len(predictions)==len(case['frame']),'Row preservation failed'
            for p in predictions:
                json.dumps(to_frontend_payload(p),allow_nan=False)
                if not p['thermalAssessable']: assert p['thermalAlert'] is None and p['thermalScore'] is None
            if case['check']: assert case['check'](predictions),'Specific safety assertion failed'
            assert case['expect']=='continue','Expected compatibility error'
            outputs.append(dict(case=name,status='PASS',behavior='SAFE_CONTINUE',rows=len(predictions),unassessed=sum(not p['thermalAssessable'] for p in predictions),reason='; '.join(sorted({i for p in predictions for i in p['qualityIssues']}))))
        except (ValueError,AssertionError) as e:
            passed=case['expect']=='error' and case['reason'] in str(e)
            outputs.append(dict(case=name,status='PASS' if passed else 'FAIL',behavior='SAFE_FAILURE' if passed else 'UNEXPECTED_FAILURE',rows=len(case['frame']),unassessed=None,reason=str(e)))
        print('Matrix:',name,outputs[-1]['status'],flush=True)
    return outputs

if __name__=='__main__':
    results=robustness_matrix(pd.read_csv(ROOT/'examples/example_internal_input.csv'))
    pd.DataFrame(results).to_csv(ROOT/'reports/organizer_robustness.csv',index=False)
    failures=[r for r in results if r['status']!='PASS']
    (ROOT/'reports/organizer_compatibility.json').write_text(json.dumps(dict(status='PASS' if not failures else 'FAIL',cases=len(results),failures=failures,limitations=['Synthetic stress tests do not establish organizer accuracy.','Supported aliases require documented units; ambiguous signals reject.','No sensor measurements are fabricated.','Only 100-kVA, five-minute measured phase-neutral voltage/phase current/ambient/oil telemetry is supported.']),indent=2))
    sys.exit(bool(failures))
