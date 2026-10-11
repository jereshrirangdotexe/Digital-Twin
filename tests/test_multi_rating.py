import copy,math
from pathlib import Path
import pandas as pd
import pytest
from service import Manager,Session
from model_registry import model_for
from vendor250.runtime.streaming_runtime_250kVA import DigitalTwinMLRuntime250kVA
from vendor250.runtime.frontend_adapter_250kVA import to_frontend_payload

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def rows250():
    return pd.read_csv(ROOT/'data/250kVA_SCADA_FINAL_BASIC.csv',nrows=6048).to_dict('records')

def test_250_frozen_inference_and_two_hour_summary(rows250,tmp_path):
    m=Manager('multi-test',state_dir=tmp_path)
    model=model_for(250)
    d={'id':'250-test','mode':'LOCAL','filename':'250.csv','ratingKVA':250,
       'groups':{'R01':rows250},'options':{},'calibration':model.resolve(None)}
    s=Session(d,'R01',d['calibration'],{},60,m)
    original=DigitalTwinMLRuntime250kVA()
    previous=None
    for row in rows250:
        expected=original.update(row)
        s.process_one();p=s.current
        for key,value in to_frontend_payload(expected)['ml'].items():assert p['ml'][key]==value
        assert p['telemetry']==expected['telemetry']
        assert p['asset']['ratingKVA']==250
        assert p['asset']['ratedCurrent']==pytest.approx(250000/(math.sqrt(3)*433))
        if s.index%24:
            assert p['assessment']['latest']==previous
        else:previous=copy.deepcopy(p['assessment']['latest'])
    assert s.status=='COMPLETE'
    assert s.current['assessment']['publishedCount']==252
    assert s.current['ml']['modelVersion']=='VoltMind_250kVA_Prototype_ML_v1.0'
    m.close()

def test_validation_rating_calibration_and_missing_sensors(rows250,tmp_path):
    m=Manager('validation',state_dir=tmp_path/'state')
    path=tmp_path/'data.csv';frame=pd.DataFrame(rows250[:360]);frame.to_csv(path,index=False)
    d=m.prepare(path,path.name,'UPLOADED',rating=250)
    assert d['status']=='READY',d['error']
    assert m.metadata(d)['ratingKVA']==250
    frame['transformer_rating_kva']=100;frame.to_csv(path,index=False)
    d=m.prepare(path,path.name,'UPLOADED',rating=250)
    assert d['status']=='FAILED' and 'rating' in d['error']
    with pytest.raises(ValueError):model_for(250).resolve({'rating_kva':100})
    frame=frame.drop(columns=['transformer_rating_kva','top_oil_temp_C']);frame.to_csv(path,index=False)
    d=m.prepare(path,path.name,'UPLOADED',rating=250)
    assert d['status']=='FAILED' and 'top_oil_temp_c' in d['error']
    with pytest.raises(ValueError):model_for(500)
    m.close()

def test_rating_switch_resets_runtime_and_summary(rows250,tmp_path,frame):
    m=Manager('switch',state_dir=tmp_path)
    path=tmp_path/'250.csv';pd.DataFrame(rows250[:360]).to_csv(path,index=False)
    d=m.prepare(path,path.name,'UPLOADED',rating=250)
    first=m.start(d,'R01',60)
    second=m.prepare(ROOT/'examples/example_internal_input.csv','100.csv','LOCAL')
    snapshot=m.start(second,second['replays'][0]['id'],1)
    assert snapshot['sessionId']!=first['sessionId']
    assert snapshot['source']['ratingKVA']==100
    assert m.active.runtime.__class__.__name__=='FinalRuntime100'
    assert m.active.assessment_window.published==0
    m.close()
