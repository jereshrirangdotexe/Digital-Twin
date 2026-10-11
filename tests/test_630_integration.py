from pathlib import Path
import json,hashlib,math,copy
import pandas as pd
import pytest
from service import Manager,Session
from model_registry import model_for

ROOT=Path(__file__).resolve().parents[1]
@pytest.fixture(scope='module')
def rows630():return pd.read_csv(ROOT/'data/630kVA_SCADA_MAIN.csv',nrows=8064).to_dict('records')

def test_full_630_replay_matches_original_and_publishes_336_blocks(rows630,tmp_path):
    model=model_for(630);m=Manager('630-test',state_dir=tmp_path)
    calibration=model.resolve(None,local=True)
    d={'id':'630','mode':'LOCAL','filename':'630.csv','ratingKVA':630,
       'groups':{'TX-630-01 / R01':rows630},'calibration':calibration,'options':{}}
    s=Session(d,'TX-630-01 / R01',calibration,{},60,m)
    digests=(ROOT/'tests/fixtures/630_R01_native_sha256.txt').read_text().splitlines()
    fields=json.loads((ROOT/'tests/fixtures/630_reference_fields.json').read_text())['mlFields']
    latest=None
    for row,expected in zip(rows630,digests):
        s.process_one();p=s.current
        native={'asset':{k:p['asset'][k] for k in ['id','ratingKVA','status']},'timestamp':p['timestamp'],
          'telemetry':p['telemetry'],'ml':{k:p['ml'][k] for k in fields},'digitalTwin':p['sourceDigitalTwin']}
        assert hashlib.sha256(json.dumps(native,sort_keys=True,allow_nan=False).encode()).hexdigest()==expected
        assert p['asset']['ratedCurrent']==pytest.approx(840.024641084213)
        if s.index%24:assert p['assessment']['latest']==latest
        else:latest=copy.deepcopy(p['assessment']['latest'])
    assert len(digests)==s.index==8064
    assert s.status=='COMPLETE' and s.current['assessment']['publishedCount']==336
    m.close()

def test_630_schema_calibration_and_group_isolation(rows630,tmp_path):
    m=Manager('630-validation',state_dir=tmp_path/'state')
    path=tmp_path/'630.csv';frame=pd.DataFrame(rows630[:240]);frame.to_csv(path,index=False)
    d=m.prepare(path,'630.csv','LOCAL',rating=630)
    assert d['status']=='READY',d['error']
    assert d['calibration']['type']=='KNOWN_SYNTHETIC_REFERENCE'
    frame.to_csv(path,index=False);uploaded=m.prepare(path,'upload.csv','UPLOADED',rating=630)
    assert uploaded['calibration']['type']=='REFERENCE_PROVISIONAL'
    other=frame.copy();other.replay_id='another';pd.concat([frame,other]).to_csv(path,index=False)
    both=m.prepare(path,'two.csv','LOCAL',rating=630)
    assert both['status']=='READY' and len(both['groups'])==2
    frame.drop(columns=['top_oil_temp_C']).to_csv(path,index=False)
    assert m.prepare(path,'missing.csv','LOCAL',rating=630)['status']=='FAILED'
    frame.assign(transformer_rating_kva=250).to_csv(path,index=False)
    assert m.prepare(path,'wrong.csv','LOCAL',rating=630)['status']=='FAILED'
    model=model_for(630);cal=model.resolve(None,local=True);cal['assets']['TX-630-01']['tau_heat_min']=0
    with pytest.raises(ValueError):model.resolve(cal)
    m.close()

def test_630_quality_resets_warmup_and_keeps_scores_unavailable(rows630):
    model=model_for(630);runtime=model.runtime(model.resolve(None,local=True))
    for row in rows630[:240]:result=runtime.update(row)
    assert result['ml']['thermalScore'] is not None
    missing=dict(rows630[240]);missing['communication_available']=0
    result=runtime.update(missing);p=model.payload(result,runtime)
    assert p['ml']['thermalScore'] is None and p['ml']['thermalAlert'] is None
    assert p['quality']['thermalAssessable'] is False
    assert p['ml']['calibrationStatus']=='KNOWN_SYNTHETIC_REFERENCE'
    for row in rows630[241:265]:assert runtime.update(row)['ml']['thermalScore'] is None
    assert p['sourceDigitalTwin']['healthIndex'] is None
