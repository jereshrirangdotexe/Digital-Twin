"""Real Spring proxy/replay/summary/export acceptance check; use isolated test ports."""
from pathlib import Path
import argparse,json,time,urllib.request,urllib.error
ap=argparse.ArgumentParser();ap.add_argument('--base',default='http://127.0.0.1:8085');ap.add_argument('--output',type=Path,default=Path('reports/FINAL_HTTP_ACCEPTANCE.json'));args=ap.parse_args()
def request(path,body=None):
    raw=json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(urllib.request.Request(args.base+'/api'+path,data=raw,headers={'Content-Type':'application/json'}),timeout=120) as r:return json.load(r)
out={};health=request('/health');assert health['modelVersion']=='VoltMind_LR_V4_LOCKED';out['health']=True
meta=request('/datasets/local')
demo=[r for r in meta['replays'] if r['id']=='DEMO100_THERMAL_TWIN']
original=[r for r in meta['replays'] if r['id']!='DEMO100_THERMAL_TWIN']
assert len(original)==60 and all(r['rows']==4032 for r in original)
assert len(demo)<=1 and all(r['rows']==4032 for r in demo)
assert meta['totalRows']==241920+4032*len(demo)
s=request('/replay/local/start',{'ratingKVA':100,'replayId':meta['replays'][0]['id'],'speed':60});id=s['sessionId']
try:
    time.sleep(2);paused=request('/replay/pause',{'sessionId':id});index=paused['processedRows'];time.sleep(.2)
    assert request('/replay/status?sessionId='+id)['processedRows']==index;out['pauseStable']=True
    p=request('/transformers/current?sessionId='+id);assert p['asset']['ratingKVA']==100
    zero=request('/intelligence/simulate',{'sessionId':id,'loadReductionPct':0,'durationHours':1});assert zero['finalDifferenceC']==0
    scenario=request('/intelligence/simulate',{'sessionId':id,'loadReductionPct':30,'durationHours':4});assert scenario['finalDifferenceC']>0
    assert request('/transformers/current?sessionId='+id)==p;out['simulationIndependent']=True
    request('/intelligence/maintenance',{'sessionId':id,'timestamp':p['timestamp'],'action':'ACCEPTANCE TEST ONLY — no physical repair performed','component':'test record','verification':'No recovery asserted'})
    request('/replay/resume',{'sessionId':id})
    deadline=time.monotonic()+160
    while time.monotonic()<deadline:
        state=request('/replay/status?sessionId='+id)
        if state['status']=='COMPLETE':break
        assert state['status']!='FAILED',state;time.sleep(2)
    assert state['status']=='COMPLETE',state
    for category in ['overall','thermal','electrical','data-quality','model','recurrence','thermal-dna','maintenance']:
        summary=request('/summary/'+category+'?sessionId='+id);assert summary['statistics']['processedRows']==4032 and summary['statistics']['complete'];out[category]=True
    export=request('/summary/export?sessionId='+id);assert '<!doctype html>' in export['printableHtml'];assert export['summary']['maintenance'];out['exportAndPersistence']=True
    if summary['incidents']:
        incident=summary['incidents'][0];e=request('/intelligence/evidence?sessionId='+id+'&incidentId='+incident['id']);assert e['evidence']['modelSHA256']==health['modelSHA256'];out['evidence']=True
    alerts=request('/transformers/alerts?sessionId='+id)['alerts']
    assert len(alerts)==len(summary['incidents']);out['incidentsMatch']=True
    args.output.parent.mkdir(parents=True,exist_ok=True)
    (args.output.parent/'SAMPLE_FINAL_SUMMARY.json').write_text(json.dumps(export['summary'],indent=2),encoding='utf-8')
    (args.output.parent/'SAMPLE_FINAL_REPORT.html').write_text(export['printableHtml'],encoding='utf-8')
finally:request('/replay/stop',{'sessionId':id})
for rating,count in [(250,145152),(630,193536)]:
    meta=request('/datasets/local?ratingKVA='+str(rating));assert meta['totalRows']==count
    s=request('/replay/local/start',{'ratingKVA':rating,'replayId':meta['replays'][0]['id'],'speed':60});time.sleep(.3)
    p=request('/transformers/current?sessionId='+s['sessionId']);assert p['asset']['ratingKVA']==rating
    request('/replay/stop',{'sessionId':s['sessionId']});out[str(rating)+'OriginalRuntime']=True
args.output.write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
