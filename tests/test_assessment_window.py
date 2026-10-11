import copy
from assessment_window import AssessmentWindow
from main import DigitalTwinMLRuntime100kVA, to_frontend_payload
from digital_twin import interpret
from service import Session

def reading(i, health=80, thermal=False, offline=False):
    return dict(timestamp=f'2026-04-05T{i:04d}', replay={'processedRows': i},
        telemetry={'communicationAvailable': not offline},
        ml=dict(thermalAlert=thermal, phaseLoadingWarning=False, undervoltageWarning=False,
            imbalanceWarning=False, assetCondition='NORMAL'),
        digitalTwin=dict(healthIndex=health, riskScore=100-health if health is not None else None,
            maintenancePriority='PROMPT_INSPECTION' if thermal else 'RESTORE_TELEMETRY' if offline else 'ROUTINE_OBSERVATION',
            maintenanceRecommendation='Inspect' if thermal else 'Observe'))

def test_publication_only_at_24_rows_and_previous_snapshot_is_immutable():
    window=AssessmentWindow()
    for i in range(1,24):
        out=window.update(reading(i))
        assert out['latest'] is None and not out['publishedOnThisRow']
    published=window.update(reading(24))
    assert published['latest']['digitalTwin']['healthIndex']==80 and published['publishedOnThisRow']
    saved=copy.deepcopy(published)
    for i in range(25,48):
        out=window.update(reading(i,40))
        assert out['latest']==saved['latest'] and not out['publishedOnThisRow']
    assert window.update(reading(48,40))['latest']['digitalTwin']['healthIndex']==40
    assert saved==published

def test_excludes_missing_health_reports_coverage_and_preserves_alarm_priority():
    window=AssessmentWindow()
    for i in range(1,13): window.update(reading(i,80))
    for i in range(13,24): window.update(reading(i,None,offline=True))
    out=window.update(reading(24,20,thermal=True))['latest']
    assert out['assessableRows']==13 and out['offlineRows']==11
    assert out['digitalTwin']['healthIndex']==round((12*80+20)/13,1)
    assert out['thermalAlertRows']==1 and out['condition']=='THERMAL_ALERT_OBSERVED'
    assert out['digitalTwin']['maintenancePriority']=='PROMPT_INSPECTION'

def test_all_unassessed_and_short_final_block_and_new_session_reset():
    window=AssessmentWindow()
    for i in range(1,8): out=window.update(reading(i,None,offline=True),final=i==7)
    block=out['latest']
    assert block['partial'] and block['rows']==7 and block['assessableRows']==0
    assert block['digitalTwin']['healthIndex'] is None and block['digitalTwin']['riskScore'] is None
    assert block['condition']=='DATA_INTERRUPTED'
    fresh=AssessmentWindow().update(reading(1))
    assert fresh['latest'] is None and fresh['publishedCount']==0

def test_real_session_keeps_original_model_and_row_twin_output(manager):
    dataset=manager.local();id=dataset['replays'][0]['id']
    session=Session(dataset,id,dataset['calibration'],dataset['options'],60,manager)
    from integration100 import FinalRuntime100
    original=FinalRuntime100(dataset['calibration']);original.bind(session.rows)
    for i,row in enumerate(session.rows):
        expected=interpret(original.update(row))
        session.process_one()
        assert session.current['ml']==expected['ml']
        assert session.current['digitalTwin']==expected['digitalTwin']
        if (i+1)%24 and i+1<len(session.rows): assert not session.current['assessment']['publishedOnThisRow']
    assert session.current['assessment']['latest']['lastRow']==len(session.rows)
    assert session.current['assessment']['publishedCount']==(len(session.rows)+23)//24
