import io,json
import numpy as np
import pandas as pd
import pytest
from conftest import ROOT
from runtime.dataset_compatibility_100kva import read_table,prepare_dataset,import_dataset
from runtime.schema_adapter_100kVA import CompatibilityError
from runtime.run_voltmind_100kVA import predict_batch

@pytest.fixture
def readings(frame):return frame.iloc[:400].copy().reset_index(drop=True)

def test_same_canonical_input_preserves_predictions(readings):
    converted,report=prepare_dataset(readings)
    a=predict_batch(converted);b=predict_batch(readings)
    for row in a+b:row.pop('inputTimestamp')
    assert a==b
    assert report['output_rows']==len(readings)

@pytest.mark.parametrize('suffix,sep',[('.csv',','),('.csv',';'),('.tsv','\t'),('.txt','|')])
def test_delimited_files(readings,suffix,sep):
    raw=readings.to_csv(index=False,sep=sep).encode()
    imported=read_table(raw,'judge'+suffix)
    assert len(imported)==len(readings)
    assert 'IR_A' in imported

@pytest.mark.parametrize('suffix',['.json','.jsonl','.ndjson'])
def test_json_formats(readings,suffix):
    raw=readings.to_json(orient='records',lines=suffix!='.json').encode()
    assert len(read_table(raw,'judge'+suffix))==len(readings)

def test_xlsx_and_multisheet_selection(readings):
    raw=io.BytesIO()
    with pd.ExcelWriter(raw,engine='openpyxl') as writer:
        readings.to_excel(writer,sheet_name='Readings',index=False)
        pd.DataFrame({'description':['checklist']}).to_excel(writer,sheet_name='Notes',index=False)
    with pytest.raises(CompatibilityError,match='multiple sheets'):read_table(raw.getvalue(),'judge.xlsx')
    assert len(read_table(raw.getvalue(),'judge.xlsx',sheet='Readings'))==len(readings)

def test_explicit_renaming_and_units(readings):
    changed=readings.rename(columns={'IR_A':'Load X','ambient_temp_C':'Weather F','VR_V':'Voltage kV'})
    changed['Load X']*=1000;changed['Weather F']=changed['Weather F']*9/5+32;changed['Voltage kV']/=1000
    out,_=prepare_dataset(changed,schema={'current_r_a':'Load X','ambient_temp_c':'Weather F','voltage_r_v':'Voltage kV'},units={'current_r_a':'mA','ambient_temp_c':'F','voltage_r_v':'kV'})
    np.testing.assert_allclose(out.IR_A,readings.IR_A,equal_nan=True)
    np.testing.assert_allclose(out.ambient_temp_C,readings.ambient_temp_C,equal_nan=True)
    np.testing.assert_allclose(out.VR_V,readings.VR_V,equal_nan=True)

def test_numeric_epoch_requires_explicit_unit(readings):
    readings.timestamp_IST=pd.to_datetime(readings.timestamp_IST,utc=True).dt.as_unit('ns').astype('int64')//10**9
    with pytest.raises(CompatibilityError,match='timestamps'):prepare_dataset(readings)
    out,_=prepare_dataset(readings,epoch_unit='s')
    assert len(out)==len(readings)

def test_day_month_requires_format(readings):
    readings.timestamp_IST=pd.to_datetime(readings.timestamp_IST).dt.strftime('%d/%m/%Y %H:%M:%S')
    with pytest.raises(CompatibilityError,match='timestamps'):prepare_dataset(readings)
    out,_=prepare_dataset(readings,timestamp_format='%d/%m/%Y %H:%M:%S')
    assert len(out)==len(readings)

def test_dense_causal_resampling_does_not_use_future(readings):
    dense=pd.concat([readings.iloc[[0]]]*21,ignore_index=True)
    start=pd.Timestamp(readings.timestamp_IST.iloc[0]);dense.timestamp_IST=[(start+pd.Timedelta(minutes=i)).isoformat() for i in range(21)]
    dense.top_oil_temp_C=np.arange(21)+40
    a,report=prepare_dataset(dense,sampling='five_minute_last')
    assert a.top_oil_temp_C.tolist()==[40,45,50,55,60]
    changed=dense.copy();changed.loc[11:,'top_oil_temp_C']=150
    b,_=prepare_dataset(changed,sampling='five_minute_last')
    pd.testing.assert_frame_equal(a.iloc[:3],b.iloc[:3])
    assert report['source_rows_combined']==16
    prefix,prefix_report=prepare_dataset(dense.iloc[:7],sampling='five_minute_last')
    pd.testing.assert_frame_equal(a.iloc[:2],prefix)
    assert prefix_report['trailing_unclosed_rows']==1

def test_empty_bins_do_not_fill_measurements(readings):
    dense=pd.concat([readings.iloc[[0]]]*7,ignore_index=True)
    start=pd.Timestamp(readings.timestamp_IST.iloc[0]);dense.timestamp_IST=[(start+pd.Timedelta(minutes=i)).isoformat() for i in [0,1,2,3,4,5,20]]
    out,report=prepare_dataset(dense,sampling='five_minute_last')
    assert out.loc[2:3,'top_oil_temp_C'].isna().all()
    assert out.loc[2:3,'communication_available'].eq(False).all()
    assert report['inserted_gap_rows']==2

@pytest.mark.parametrize('sampling',['strict','five_minute_last'])
def test_slower_data_is_rejected(readings,sampling):
    with pytest.raises(CompatibilityError,match='coarser|exceeds five'):prepare_dataset(readings.iloc[::3],sampling=sampling)

def test_duplicates_and_ambiguity_rejected(readings):
    with pytest.raises(CompatibilityError,match='Duplicate asset'):prepare_dataset(pd.concat([readings,readings.iloc[[0]]]))
    with pytest.raises(CompatibilityError,match='Ambiguous'):prepare_dataset(readings.assign(current_r=1))
    with pytest.raises(CompatibilityError,match='Duplicate column'):read_table(b'timestamp,IR_A,IR_A\n2026-01-01,1,2\n','x.csv')

def test_sort_requires_explicit_choice(readings):
    with pytest.raises(CompatibilityError,match='Out-of-order'):prepare_dataset(readings.iloc[::-1])
    out,_=prepare_dataset(readings.iloc[::-1],sort=True)
    assert pd.to_datetime(out.timestamp_IST,utc=True).is_monotonic_increasing

def test_checklist_not_invented_as_sensor_data():
    with pytest.raises(CompatibilityError,match='missing'):prepare_dataset(pd.DataFrame({'timestamp':['2026-01-01'],'voltage_reference':[250],'voltage_software':[249]}))

def test_other_rating_rejected(readings):
    with pytest.raises(CompatibilityError,match='Only 100'):prepare_dataset(readings.assign(transformer_rating_kva=250))

def test_truth_and_events_are_inert(readings):
    a,_=prepare_dataset(readings)
    b,report=prepare_dataset(readings.assign(latent_fault=1,event_id='oil_failure',truth_top_oil=150))
    pd.testing.assert_frame_equal(a,b)
    assert 'latent_fault' in report['ignored_columns']

def test_service_imports_json_and_applies_mapping(manager,readings,tmp_path):
    renamed=readings.rename(columns={'IR_A':'Judge Current'})
    path=tmp_path/'judge.json';path.write_text(renamed.to_json(orient='records'))
    d=manager.prepare(path,'judge.json','UPLOADED',options={'schema':{'current_r_a':'Judge Current'},'units':{'current_r_a':'A'}})
    assert d['status']=='READY',d['error']
    assert d['compatibility']['audit']['rows']==len(readings)
    assert 'schema' not in d['options']

def test_mixed_assets_kept_separate(readings):
    second=readings.copy();second['replay_id']='OTHER'
    out,report=prepare_dataset(pd.concat([readings,second],ignore_index=True))
    assert report['assets']==2
    assert out.asset_id.nunique()==2

def test_duplicate_json_fields_rejected():
    with pytest.raises(CompatibilityError,match='Duplicate JSON'):read_table(b'[{"IR_A":1,"IR_A":2}]','judge.json')

def test_new_phase_aliases_and_unit_suffixes(readings):
    changed=readings.rename(columns={'IR_A':'current_L1_mA','VY_V':'voltage_L2_N_kV'})
    changed.current_L1_mA*=1000;changed.voltage_L2_N_kV/=1000
    out,_=prepare_dataset(changed)
    np.testing.assert_allclose(out.IR_A,readings.IR_A,equal_nan=True)
    np.testing.assert_allclose(out.VY_V,readings.VY_V,equal_nan=True)
