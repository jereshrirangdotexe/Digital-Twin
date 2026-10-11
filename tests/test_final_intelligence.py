"""Adversarial checks for sidecars; no fitting or rewriting locked artifacts."""
from types import SimpleNamespace
from pathlib import Path
import copy,json
import numpy as np
import pandas as pd
import pytest
from integration100 import FinalModel100,FinalRuntime100
from intelligence import IntelligenceStore,project,investigate,thermal_dna,printable_report
from digital_twin import interpret

@pytest.fixture(scope='module')
def operating():
    root=Path(__file__).resolve().parents[1]
    model=FinalModel100();d=model.prepare(root/'data/final100/scada/100kVA_SCADA_V4_FULL.csv','final.csv','LOCAL')
    asset=next(iter(d['groups']));r=FinalRuntime100(d['calibration']);r.bind(d['groups'][asset][:100])
    return interpret(copy.deepcopy(next(p for p in r.outputs[48:] if p['quality']['thermalAssessable'])))

def test_projection_independent_and_zero(operating):
    original=copy.deepcopy(operating)
    z=project(operating,{'loadReductionPct':0,'durationHours':2})
    assert all(p['baselineC']==p['interventionC'] for p in z['trajectory'])
    lower=project(operating,{'loadReductionPct':40,'durationHours':4})
    assert lower['finalDifferenceC']>0
    assert operating==original

@pytest.mark.parametrize('body',[{'loadReductionPct':-1},{'durationHours':25},{'loadReductionPct':True},{'durationHours':float('nan')},{'coolingRepair':True}])
def test_projection_kill_invalid(operating,body):
    with pytest.raises(ValueError):project(operating,body)

def test_simulation_rejects_missing_calibration_and_unassessed(operating):
    for key,val in [('calibration',{}),('quality',{'thermalAssessable':False})]:
        p=copy.deepcopy(operating);p[key]=val
        with pytest.raises((ValueError,KeyError)):project(p,{})

def test_sensor_spike_competing_evidence(operating):
    p=copy.deepcopy(operating);old=copy.deepcopy(p);old['telemetry']['topOilTempC']-=20
    result=investigate(p,[old]);assert result['sensorSuspect'];assert result['investigationStatus']=='SENSOR_REVIEW'
    assert result['competingExplanations']
    p['telemetry']['communicationAvailable']=False
    assert investigate(p,[])['investigationStatus']=='DATA_UNAVAILABLE'

def sequence(p,loads,oil=None):
    out=[]
    for i,load in enumerate(loads):
        r=copy.deepcopy(p);r['timestamp']=(pd.Timestamp('2026-04-01',tz='UTC')+pd.Timedelta(minutes=5*i)).isoformat()
        r['quality']['thermalAssessable']=True;r['ml']['thermalAlert']=False;r['ml']['assetCondition']='NORMAL_OBSERVED'
        r['telemetry'].update(loadingPct=load,ambientTempC=30,topOilTempC=40 if oil is None else oil[i],communicationAvailable=True)
        out.append(r)
    return out

def dna_history(p,scale=1):
    loads=[];oil=[]
    for _ in range(4):
        loads.extend([30]*36+[60]*36)
        oil.extend([40]*36+[40+scale*10*min(i/18,1) for i in range(36)])
    return sequence(p,loads,oil)

def test_dna_no_fabricated_baseline_and_known_change(operating):
    rows=dna_history(operating);described=thermal_dna(rows)
    assert len(described['episodes'])>=3
    assert described['status']=='FINGERPRINT_NOT_ESTABLISHED'
    reference={'episodes':copy.deepcopy(described['episodes']),'referencePeriodEnd':(pd.Timestamp(rows[0]['timestamp'])-pd.Timedelta(days=1)).isoformat()}
    for e in reference['episodes']:e['timestamp']=(pd.Timestamp(e['timestamp'])-pd.Timedelta(days=30)).isoformat()
    assert thermal_dna(rows,reference)['status']=='THERMAL_RESPONSE_STABLE'
    assert thermal_dna(dna_history(operating,2),reference)['status']=='THERMAL_RESPONSE_DRIFT'
    reference['referencePeriodEnd']=rows[-1]['timestamp']
    assert thermal_dna(rows,reference)['status']=='BASELINE_AVAILABLE'
    flat=sequence(operating,[40]*100)
    assert thermal_dna(flat)['status']=='INSUFFICIENT_EXCITATION'
    for r in rows:r['quality']['thermalAssessable']=False
    assert not thermal_dna(rows)['episodes']

def test_persistence_replay_dedup_and_repair(operating,tmp_path):
    store=IntelligenceStore(tmp_path/'memory.sqlite')
    session=SimpleNamespace(id='one',index=1,dataset={'ratingKVA':100,'fingerprint':'source'},replay_id='asset',alerts=[],rows=[1]*100,status='PAUSED',source=lambda:{'mode':'TEST'})
    p=copy.deepcopy(operating)
    session.alerts=[dict(category='THERMAL',timestamp=p['timestamp'],status='ACTIVE',id='alert',evidence={'actualOilTempC':70})]
    store.record(session,p);session.id='two';store.record(session,p)
    assert len(store.incidents(session))==1
    result=store.add_maintenance(session,{'timestamp':p['timestamp'],'action':'<script>repair</script>'})
    again=IntelligenceStore(store.path);assert again.maintenance(session)[0]['id']==result['id']
    assert again.recurrence(session)['repairEffectiveness'][0]['status']=='INSUFFICIENT_COMPARABLE_HISTORY'
    summary=again.summary(session);assert summary['statistics']['processedRows']==1
    assert '&lt;script&gt;' in printable_report(summary);assert '<script>repair' not in printable_report(summary)
    with pytest.raises(ValueError):again.add_maintenance(session,{'timestamp':'2026-04-01','action':'repair'})
    with pytest.raises(ValueError):again.establish_reference(session,{'verifiedHealthy':False})

def test_import_missing_sensors_abstains(operating,tmp_path):
    f=tmp_path/'judge.csv';pd.DataFrame({'timestamp':pd.date_range('2026-04-01',periods=30,freq='5min',tz='UTC').astype(str),'asset_id':'judge','ambient_temp_C':30,'top_oil_temp_C':40}).to_csv(f,index=False)
    d=FinalModel100().prepare(f,f.name,'UPLOADED');r=FinalRuntime100(d['calibration']);r.bind(d['groups']['judge'])
    assert all(not p['quality']['thermalAssessable'] and p['ml']['thermalAlert'] is None for p in r.outputs)

def test_summary_excludes_incidents_not_encountered_in_restarted_replay(operating,tmp_path):
    store=IntelligenceStore(tmp_path/'causal-summary.sqlite')
    session=SimpleNamespace(id='old',index=1,dataset={'ratingKVA':100,'fingerprint':'same-file'},replay_id='asset',alerts=[],rows=[1]*100,status='PAUSED',source=lambda:{'mode':'TEST'})
    future=copy.deepcopy(operating);future['timestamp']=(pd.Timestamp(future['timestamp'])+pd.Timedelta(days=10)).isoformat()
    session.alerts=[dict(category='THERMAL',timestamp=future['timestamp'],status='ACTIVE',id='future-alert',evidence={})]
    store.record(session,future)
    assert len(store.incidents(session))==1
    session.id='restart';session.alerts=[];store.record(session,copy.deepcopy(operating))
    summary=store.summary(session)
    assert summary['incidents']==[] and summary['statistics']['incidentCounts']['THERMAL']==0
    assert summary['recurrence']['thermalIncidents']==0
    assert len(store.incidents(session))==1  # persistent record is retained, never falsely counted as current

def test_repair_matches_and_true_recurrence(operating,tmp_path):
    store=IntelligenceStore(tmp_path/'repair.sqlite')
    s=SimpleNamespace(id='repair',index=0,dataset={'ratingKVA':100,'fingerprint':'repair-source'},replay_id='asset',alerts=[],rows=[1]*240,status='COMPLETE',source=lambda:{'mode':'TEST'})
    rows=sequence(operating,[40]*240)
    for i,p in enumerate(rows):
        s.index=i+1;p['ml']['thermalResidualC']=8 if i<120 else 2;store.record(s,p)
    t=rows[120]['timestamp'];store.add_maintenance(s,{'timestamp':t,'action':'TEST ONLY: inspect cooling'})
    assert store.recurrence(s)['repairEffectiveness'][0]['status']=='EVIDENCE_OF_IMPROVEMENT'
    for day in [1,4,7]:
        p=copy.deepcopy(rows[-1]);p['timestamp']=(pd.Timestamp(t)+pd.Timedelta(days=day)).isoformat()
        s.alerts=[dict(category='THERMAL',timestamp=p['timestamp'],status='ACTIVE',id=str(day),evidence={})];store.record(s,p)
    recurrence=store.recurrence(s)
    assert recurrence['intervalDays']==[3,3] and recurrence['approximatelyRegular']
    assert recurrence['repairEffectiveness'][0]['status']=='ABNORMALITY_RETURNED'

def test_dna_rejects_ambient_sensor_and_gap_confounders(operating):
    for kind in ['ambient','sensor','gap']:
        rows=dna_history(operating)
        for i,r in enumerate(rows):
            if kind=='ambient':r['telemetry']['ambientTempC']=30+i
            if kind=='sensor':r['ml']['assetCondition']='SENSOR_SUSPECT'
            if kind=='gap':r['timestamp']=(pd.Timestamp(r['timestamp'])+pd.Timedelta(minutes=5*i)).isoformat()
        assert not thermal_dna(rows)['episodes']

def test_final_causality_and_extra_truth_columns():
    root=Path(__file__).resolve().parents[1];m=FinalModel100()
    d=m.prepare(root/'data/final100/scada/100kVA_SCADA_V4_FULL.csv','final.csv','LOCAL')
    rows=next(iter(d['groups'].values()))[:80];base=FinalRuntime100(d['calibration']);base.bind(rows[:40])
    changed=copy.deepcopy(rows)
    for row in changed:
        row['truth_thermal_fault']=1;row['future_fault_event']='poison'
    for row in changed[40:]:row['top_oil_temp_C']=170
    future=FinalRuntime100(d['calibration']);future.bind(changed)
    assert [p['ml'] for p in base.outputs]==[p['ml'] for p in future.outputs[:40]]

def test_json_duplicate_fields_rejected(tmp_path):
    f=tmp_path/'duplicate.json';f.write_text('[{"timestamp":"2026-01-01T00:00:00Z","IR_A":1,"IR_A":2}]')
    with pytest.raises(ValueError,match='Duplicate JSON field'):FinalModel100().prepare(f,f.name,'UPLOADED')

def test_optional_alarm_never_presents_as_all_clear(operating):
    from assessment_window import AssessmentWindow
    p=copy.deepcopy(operating);p['ml']['thermalAlert']=False;p['ml']['oilAlert']=False;p['ml']['terminalAlert']=False
    base=interpret(copy.deepcopy(p))['digitalTwin']['healthIndex']
    p['ml']['oilAlert']=True;result=interpret(p)
    assert result['digitalTwin']['healthIndex']==base
    assert result['digitalTwin']['maintenancePriority']=='PROMPT_INSPECTION'
    result['replay']={'processedRows':1}
    published=AssessmentWindow().update(result,final=True)['latest']
    assert published['condition']=='OPTIONAL_SENSOR_ALERT_OBSERVED' and published['optionalAlertRows']==1
