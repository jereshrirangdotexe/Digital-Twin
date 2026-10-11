"""Real HTTP check; deliberately replaces the selected monitoring session."""
import os,json,time,urllib.request
from pathlib import Path
BASE=os.environ.get('VOLTMIND_TEST_BASE','http://127.0.0.1:5173')+'/api'
def request(path,body=None):
    raw=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(BASE+path,data=raw,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=15) as response:return json.load(response)

session=request('/replay/local/start',{'replayId':'R05','speed':60})
sid=session['sessionId']
try:
    deadline=time.monotonic()+30
    while request('/replay/status?sessionId='+sid)['processedRows']<340:
        assert time.monotonic()<deadline,'Replay did not progress'
        time.sleep(.05)
    paused=request('/replay/pause',{'sessionId':sid})
    current=request('/transformers/current?sessionId='+sid)
    # API wraps current in a dictionary in the original service.
    if 'current' in current:current=current['current']
    a=current['assessment']
    assert a['policy']=='24_ROWS_2_HOURS' and a['latest']['rows']==24
    assert a['latest']['lastRow']==paused['processedRows']//24*24
    history=request('/transformers/history?sessionId='+sid)['history']
    blocks=[r for r in history if r['assessment']['publishedOnThisRow']]
    assert len(blocks)==paused['processedRows']//24
    for previous,following in zip(history,history[1:]):
        if not following['assessment']['publishedOnThisRow']:
            assert previous['assessment']['latest']==following['assessment']['latest']
    old=paused['processedRows'];time.sleep(.1)
    assert request('/replay/status?sessionId='+sid)['processedRows']==old
    restarted=request('/replay/restart',{'sessionId':sid})
    sid=restarted['sessionId']
    assert sid!=paused['sessionId']
    request('/replay/pause',{'sessionId':sid})
    fresh=request('/transformers/current?sessionId='+sid)
    if 'current' in fresh:fresh=fresh['current']
    if fresh:assert fresh['assessment']['latest'] is None
    report=dict(status='PASS',base=BASE,processedRows=old,publishedBlocks=len(blocks),
        publicationAndHold='PASS',pause='PASS',restartIsolation='PASS',
        finalSummary='Covered by separate 4032-row actual browser run/download validation')
    path=Path(__file__).resolve().parents[1]/'reports/twohour_http_workflow.json'
    path.write_text(json.dumps(report,indent=2));print(json.dumps(report))
finally:
    request('/replay/stop',{'sessionId':sid})
