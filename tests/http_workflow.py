"""Run against the real started app. Starts/stops test sessions; no mocked ML."""
from pathlib import Path
import json,time,urllib.request,urllib.error,uuid,argparse
ROOT=Path(__file__).resolve().parents[1]
def run(base):
    checks={}
    def request(path,body=None,raw=None,content='application/json',expected=200):
        data=raw if raw is not None else json.dumps(body).encode() if body is not None else None
        req=urllib.request.Request(base+'/api'+path,data=data,headers={'Content-Type':content})
        try:
            with urllib.request.urlopen(req,timeout=120) as r:status=r.status;value=json.load(r)
        except urllib.error.HTTPError as e:status=e.code;value=json.load(e)
        assert status==expected,(path,status,value)
        return value
    def upload(path):
        boundary='VoltMind'+uuid.uuid4().hex
        raw=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{path.name}"\r\nContent-Type: text/csv\r\n\r\n').encode()+path.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
        meta=request('/datasets/upload',raw=raw,content='multipart/form-data; boundary='+boundary,expected=202)
        for _ in range(600):
            meta=request('/datasets/status?datasetId='+meta['id'])
            if meta['status'] in ['READY','FAILED']:return meta
            time.sleep(.1)
        raise AssertionError('Validation timeout')
    health=request('/health');assert health['application']=='VoltMind'
    if health['activeSessionId']:request('/replay/stop',{'sessionId':health['activeSessionId']})
    before=request('/health')['inferenceRows'];local=request('/datasets/local')
    assert local['totalRows']==48384 and len(local['replays'])==12
    assert request('/health')['inferenceRows']==before;checks['idle_metadata_no_inference']='PASS'
    a=request('/replay/local/start',{'replayId':'R05','speed':60});id=a['sessionId'];time.sleep(.12)
    paused=request('/replay/pause',{'sessionId':id});time.sleep(.15)
    assert request('/replay/status?sessionId='+id)['processedRows']==paused['processedRows'];checks['pause']='PASS'
    for speed in [1,5,10,30,60]:assert request('/replay/speed',{'sessionId':id,'speed':speed})['speed']==speed
    checks['all_speeds']='PASS';request('/replay/resume',{'sessionId':id});time.sleep(.15)
    assert request('/replay/status?sessionId='+id)['processedRows']>paused['processedRows'];checks['resume']='PASS'
    # Disconnect/reconnect SSE while paused: history cursor changes neither model calls nor history.
    snapshot=request('/replay/pause',{'sessionId':id});count=request('/health')['inferenceRows'];cursor=snapshot['processedRows']
    with urllib.request.urlopen(base+'/api/replay/stream?sessionId='+id+'&after='+str(cursor-1),timeout=5) as stream:
        lines=[]
        for _ in range(20):
            line=stream.readline().decode();lines.append(line)
            if line.startswith('data:'):break
        assert any(line.startswith('event: reading') for line in lines)
    current=request('/transformers/current?sessionId='+id)
    assert current['source']['mode']=='LOCAL' and current['asset']['id']=='R05'
    assert current['ml']['modelVersion']=='VoltMind_100kVA_Final_Selected_v3'
    with urllib.request.urlopen(base+'/api/replay/stream?sessionId='+id+'&after='+str(cursor),timeout=5) as stream:
        assert stream.readline().decode().startswith(': connected')
    assert request('/health')['inferenceRows']==count;checks['sse_reconnect_no_reinference']='PASS'
    restarted=request('/replay/restart',{'sessionId':id});assert restarted['sessionId']!=id
    request('/replay/status?sessionId='+id,expected=409);checks['restart_stale_isolation']='PASS'
    request('/replay/stop',{'sessionId':restarted['sessionId']})
    meta=upload(ROOT/'examples/example_organizer_input.csv');assert meta['status']=='READY',meta
    uploaded=request('/replay/uploaded/start',{'datasetId':meta['id'],'speed':60});uid=uploaded['sessionId']
    for _ in range(200):
        status=request('/replay/status?sessionId='+uid)
        if status['status']=='COMPLETE':break
        time.sleep(.1)
    assert status['status']=='COMPLETE' and status['processedRows']==360
    final=request('/transformers/current?sessionId='+uid)
    assert final['source']['mode']=='UPLOADED' and final['quality']['thermalAssessable']
    assert final['digitalTwin']['healthIndex'] is not None and final['digitalTwin']['rulEstimate'] is None
    assert len(request('/transformers/history?sessionId='+uid)['history'])==360
    assert isinstance(request('/transformers/alerts?sessionId='+uid)['alerts'],list)
    checks['organizer_upload_complete_real_ml_twin_history']='PASS'
    request('/replay/stop',{'sessionId':uid});request('/datasets/delete',{'datasetId':meta['id']})
    request('/transformers/current?sessionId='+uid,expected=404);checks['stop_upload_cleanup']='PASS'
    report={'status':'PASS','base':base,'checks':checks,'modelSHA256':health['modelSHA256']}
    (ROOT/'reports/http_workflow.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',default='http://127.0.0.1:5173');run(parser.parse_args().base)
