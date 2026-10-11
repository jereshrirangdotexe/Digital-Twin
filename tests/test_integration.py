import copy,hashlib,json,time
import pandas as pd
import pytest
from conftest import ROOT
from main import predict_batch,DigitalTwinMLRuntime100kVA,to_frontend_payload
from service import APIError,Session,parse_multipart
from digital_twin import interpret
from runtime.schema_adapter_100kVA import SchemaAdapter100kVA,CompatibilityError
from calibration.commission_100kVA import resolve_calibration,commission_asset

def test_integrity():
    expected=json.loads((ROOT/'ml/config/100kVA_config.json').read_text())['model_sha256']
    assert hashlib.sha256((ROOT/'ml/model/100kVA_model.joblib').read_bytes()).hexdigest()==expected

def test_corrupt_artifact_fails_without_fallback(tmp_path):
    path=tmp_path/'model.joblib';path.write_bytes(b'corrupt')
    with pytest.raises(CompatibilityError,match='MODEL_INTEGRITY_FAILURE'):DigitalTwinMLRuntime100kVA(model_path=path)
    with pytest.raises(CompatibilityError,match='Missing model'):DigitalTwinMLRuntime100kVA(model_path=tmp_path/'missing.joblib')

def test_runtime_restart_reproduces_causal_state(frame,tmp_path):
    runtime=DigitalTwinMLRuntime100kVA();rows=frame.to_dict('records')
    for row in rows[:300]:runtime.update(row)
    path=tmp_path/'state.json';runtime.save(path);restored=DigitalTwinMLRuntime100kVA.load(path)
    assert [runtime.update(row) for row in rows[300:]]==[restored.update(row) for row in rows[300:]]

def test_unknown_offline_fields_are_inert(frame):
    extra=frame.assign(truth_fault=1,event_id='fake',profile_tag='fault')
    assert predict_batch(extra)==predict_batch(frame)

def test_duplicate_csv_headers_rejected(manager,tmp_path):
    path=tmp_path/'duplicate.csv';path.write_text('timestamp,IR_A,IR_A\n2026-01-01,1,2\n')
    r=manager.prepare(path,'duplicate.csv','UPLOADED')
    assert r['status']=='FAILED' and 'Duplicate' in r['error']

def test_separate_verified_commissioning_and_binding(manager,frame):
    commissioning=pd.read_csv(ROOT/'examples/verified_synthetic_commissioning_R05.csv')
    d=manager.prepare(ROOT/'examples/example_internal_input.csv','input.csv','LOCAL',commissioning=commissioning,verified=True)
    assert d['status']=='READY',d.get('error')
    assert d['calibration']['R05']['calibration_status']=='VERIFIED_COMMISSIONED' and d['calibration']['R05']['asset_id']=='R05'
    with pytest.raises(APIError,match='Unknown replay'):manager.start(d,'ANOTHER_ASSET')

def test_causal_batch_stream_equivalence(frame):
    expected=predict_batch(frame);r=DigitalTwinMLRuntime100kVA()
    assert [r.update(row) for row in frame.to_dict('records')]==expected

def test_no_future_leakage(frame):
    base=predict_batch(frame.iloc[:40]);changed=frame.copy();changed.loc[40:,'top_oil_temp_C']=170
    assert predict_batch(changed)[:40]==base

def test_initial_idle_metadata_not_inference(manager):
    assert manager.health()['activeSessionId'] is None
    meta=manager.metadata(manager.local())
    assert meta['status']=='READY' and manager.inference_rows==0

def test_session_controls_and_isolation(manager):
    first=manager.start(manager.local(),speed=60);id=first['sessionId']
    time.sleep(.12);paused=manager.control('pause',id,{})
    time.sleep(.12);assert manager.selected(id).index==paused['processedRows']
    assert manager.control('speed',id,{'speed':10})['speed']==10
    manager.control('resume',id,{});time.sleep(.12)
    assert manager.selected(id).index>paused['processedRows']
    restarted=manager.control('restart',id,{})
    assert restarted['sessionId']!=id and restarted['processedRows']<=1
    with pytest.raises(APIError,match='Stale'):manager.selected(id)
    manager.control('stop',restarted['sessionId'],{})
    assert manager.active is None

def test_stale_source_selection(manager):
    t=manager.register_selection({'clientId':'test','generation':2})
    with pytest.raises(APIError,match='Stale'):manager.register_selection({'clientId':'test','generation':1})
    manager.register_selection({'clientId':'test','generation':3})
    with pytest.raises(APIError,match='Stale'):manager.start(manager.local(),token=t)

def test_owned_upload_cleanup(manager,frame):
    m=manager.upload(frame.to_csv(index=False).encode(),'../../safe.csv')
    for _ in range(200):
        d=manager.datasets[m['id']]
        if d['status'] in ['READY','FAILED']:break
        time.sleep(.01)
    assert d['status']=='READY' and d['filename']=='safe.csv'
    assert manager.inference_rows==0
    assert __import__('pathlib').Path(d['path']).parent==manager.storage

@pytest.mark.parametrize('change,reason',[
    ('missing',None),('ambiguous','Ambiguous'),('interval','five-minute'),('timestamp','Timestamp rejected'),('rating','100 kVA')])
def test_upload_rejection(manager,frame,tmp_path,change,reason):
    f=frame.copy()
    if change=='missing':f=f.drop(columns='IR_A')
    if change=='ambiguous':f['current_r']=f['IR_A']
    if change=='interval':f['timestamp_IST']=pd.date_range('2026-01-01',periods=len(f),freq='7min',tz='UTC').astype(str)
    if change=='timestamp':f['timestamp_IST']='01/02/2026 12:00'
    if change=='rating':f['rating_kva']=250
    path=tmp_path/'bad.csv';f.to_csv(path,index=False)
    result=manager.prepare(path,'bad.csv','UPLOADED')
    if change=='missing':
        from integration100 import FinalRuntime100
        assert result['status']=='READY'
        runtime=FinalRuntime100(result['calibration']);runtime.bind(result['groups']['R05'])
        assert all(p['ml']['thermalAlert'] is None for p in runtime.outputs)
    else:
        assert result['status']=='FAILED' and reason in result['error']

@pytest.mark.parametrize('case',['missing','nan','range','duplicate','backward','gap','communication'])
def test_quality_preserves_rows_and_does_not_fabricate(frame,case):
    f=frame.iloc[:35].copy()
    if case=='missing':f.loc[4:,'IR_A']=None
    if case=='nan':f.loc[4:,'top_oil_temp_C']=float('nan')
    if case=='range':f.loc[4:,'top_oil_temp_C']=300
    if case=='duplicate':f.loc[4,'timestamp_IST']=f.loc[3,'timestamp_IST']
    if case=='backward':f.loc[4,'timestamp_IST']=f.loc[1,'timestamp_IST']
    if case=='gap':f.loc[4,'timestamp_IST']=str(pd.Timestamp(f.loc[4,'timestamp_IST'])+pd.Timedelta(hours=8))
    if case=='communication':f['communication_available']=False
    result=predict_batch(f)
    assert len(result)==len(f)
    assert not result[4]['thermalAssessable']
    assert result[4]['thermalAlert'] is None

def test_alias_units(frame):
    baseline=predict_batch(frame)
    f=frame.copy().rename(columns={'timestamp_IST':'time','VR_V':'voltage_r_kV','IR_A':'current_r_mA','top_oil_temp_C':'oil_temperature_F'})
    f['voltage_r_kV']/=1000;f['current_r_mA']*=1000;f['oil_temperature_F']=f['oil_temperature_F']*9/5+32
    result=predict_batch(f)
    for a,b in zip(baseline,result):
        assert a['thermalAlert']==b['thermalAlert']
        assert a['actualOilTempC']==pytest.approx(b['actualOilTempC'])

def test_commissioning_separate_and_explicit(frame):
    with pytest.raises(CompatibilityError,match='independent verification'):commission_asset(frame)
    with pytest.raises(ValueError,match='seven complete days'):commission_asset(frame,verified_healthy=True)
    c=resolve_calibration();c['tau']=0
    with pytest.raises(CompatibilityError):resolve_calibration(c)

def test_twin_formula_null_and_no_feedback(frame):
    result=predict_batch(frame)
    for r in result:
        payload=to_frontend_payload(r);before=copy.deepcopy(payload['ml']);t=interpret(payload)
        assert t['ml']==before
        twin=t['digitalTwin']
        assert twin['agingState'] is None and twin['rulEstimate'] is None
        if not r['thermalAssessable']:assert twin['healthIndex'] is None and twin['riskScore'] is None
        else:
            assert twin['riskScore']==round(min(100,sum(twin['formulaComponents'].values())),1)
            assert twin['healthIndex']==round(100-twin['riskScore'],1)

def test_health_control(frame):
    results=predict_batch(frame)
    assert all(r['thermalAlert'] is not True for r in results)
    assert any(r['thermalAssessable'] for r in results)

