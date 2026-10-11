import csv,io,json,time,threading
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse
from streaming_runtime import DigitalTwinMLRuntime630kVA
from input_adapter import InputAdapter,REQUIRED,ALIASES
ROOT=Path(__file__).resolve().parents[1]
class ReplayService:
    def __init__(self):
        self.lock=threading.RLock();self.rows=[];self.index=0;self.mode='EMPTY';self.playing=False;self.speed=5;self.current=None;self.history=[];self.alerts=[];self.runtime=None;self.filename=None;self.options=[];self.source_rows=[];self.settings={};self.sequence=0;self.closed=False
        threading.Thread(target=self.loop,daemon=True).start()
    def loop(self):
        while not self.closed:
            with self.lock:
                if self.playing and self.index<len(self.rows):
                    try:self.advance()
                    except Exception as e:self.playing=False;self.error=str(e)
                if self.index>=len(self.rows):self.playing=False
                delay=1/max(self.speed,.1)
            time.sleep(min(delay,1))
    def advance(self):
        r=self.runtime.update(self.rows[self.index],dict(mode=self.mode,filename=self.filename,replayId=self.rows[self.index].get('replay_id','external')))
        self.current=r;self.index+=1;self.sequence+=1;self.history.append(r);self.history=self.history[-600:]
        if r['ml']['thermalAlert'] or r['ml']['electricalWarnings'] or r['ml']['qualityReasons']:
            self.alerts.append(dict(timestamp=r['timestamp'],assetId=r['asset']['id'],thermalState=r['ml']['thermalState'],electricalWarnings=r['ml']['electricalWarnings'],qualityReasons=r['ml']['qualityReasons'],explanation=r['digitalTwin']['explanation']));self.alerts=self.alerts[-200:]
    def status(self):return dict(mode=self.mode,filename=self.filename,playing=self.playing,index=self.index,total=len(self.rows),speed=self.speed,progress=self.index/max(len(self.rows),1),replays=self.options,selectedReplay=self.rows[0].get('replay_id','external') if self.rows else None,sequence=self.sequence,error=getattr(self,'error',None))
    def configure(self,rows,mode,filename,settings=None,replay=None):
        if not rows:raise ValueError('Dataset is empty')
        keys={str(k).lower() for k in rows[0]};settings=settings or {};schema=settings.get('schema') or {}
        missing=[k for k in REQUIRED if not any(n.lower() in keys for n in ([schema[k]] if k in schema else ALIASES[k]))]
        if missing:raise ValueError('Missing required columns: '+', '.join(missing))
        if mode=='LOCAL':settings={**settings,'calibration':str(ROOT/'ml/calibration/synthetic_assets.json')}
        groups={};adapter=InputAdapter(settings.get('schema'),settings.get('units'),settings.get('timezone'),settings.get('assetId','EXTERNAL-630'))
        for row in rows:
            r=adapter.normalize(row);groups.setdefault((r['asset_id'],r['replay_id']),[]).append(row)
        options=[dict(assetId=k[0],replayId=k[1],rows=len(v)) for k,v in groups.items()]
        selected=next((k for k in groups if k[1]==replay),next(iter(groups))) if replay else next(iter(groups))
        if replay and selected[1]!=replay:raise ValueError('Unknown replay selection')
        chosen=groups[selected];previous=None
        for row in chosen:
            r=adapter.normalize(row)
            if previous and r['_dt']<=previous:raise ValueError('Duplicate or nonchronological timestamps')
            previous=r['_dt']
        runtime=DigitalTwinMLRuntime630kVA(calibration=settings.get('calibration','reference'),schema=settings.get('schema'),units=settings.get('units'),tz=settings.get('timezone'),asset_id=settings.get('assetId','EXTERNAL-630'))
        with self.lock:
            self.source_rows=rows;self.settings=settings;self.options=options;self.rows=chosen;self.index=0;self.mode=mode;self.filename=Path(filename).name;self.current=None;self.history=[];self.alerts=[];self.playing=False;self.error=None;self.runtime=runtime;self.sequence+=1;return self.status()
    def control(self,body):
        action=body.get('action')
        if action=='select':return self.configure(self.source_rows,self.mode,self.filename,self.settings,body.get('replayId'))
        with self.lock:
            if action in ['play','resume']:
                if not self.rows:raise ValueError('Select a dataset first')
                self.playing=True
            elif action=='pause':self.playing=False
            elif action=='restart':
                if not self.runtime:raise ValueError('Select a dataset first')
                self.runtime.reset();self.index=0;self.history=[];self.alerts=[];self.current=None;self.playing=False;self.sequence+=1
            elif action=='stop':self.playing=False;self.rows=[];self.source_rows=[];self.options=[];self.index=0;self.current=None;self.history=[];self.alerts=[];self.runtime=None;self.mode='EMPTY';self.filename=None;self.sequence+=1
            elif action=='speed':
                speed=float(body.get('speed',5))
                if not .5<=speed<=100:raise ValueError('Speed must be 0.5–100 readings per second')
                self.speed=speed
            elif action=='step':
                if self.playing:raise ValueError('Pause before single step')
                if self.index<len(self.rows):self.advance()
            else:raise ValueError('Unknown replay action')
            return self.status()
def serve(port=8766):
    state=ReplayService()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send_json(self,status,data):
            raw=json.dumps(data,allow_nan=False).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            path=urlparse(self.path).path
            with state.lock:data={'/api/630/status':state.status(),'/api/630/current':state.current,'/api/630/history':state.history,'/api/630/alerts':state.alerts,'/api/630/twin':state.current['digitalTwin'] if state.current else None}.get(path,'UNKNOWN')
            self.send_json(404 if data=='UNKNOWN' else 200,data)
        def do_POST(self):
            try:
                size=int(self.headers.get('Content-Length',0))
                if size>64*1024*1024:raise ValueError('Upload limit is 64 MB')
                body=json.loads(self.rfile.read(size) or '{}');path=urlparse(self.path).path
                if path=='/api/630/local':
                    with (ROOT/'scada/630kVA_SCADA_MAIN.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
                    data=state.configure(rows,'LOCAL','630kVA_SCADA_MAIN.csv',replay=body.get('replayId'))
                elif path=='/api/630/upload':
                    settings={k:body[k] for k in ['schema','units','timezone','assetId'] if k in body};data=state.configure(list(csv.DictReader(io.StringIO(body.get('csv','')))),'UPLOADED',body.get('filename','uploaded.csv'),settings,replay=body.get('replayId'))
                elif path=='/api/630/control':data=state.control(body)
                else:self.send_json(404,dict(error='Unknown API'));return
                self.send_json(200,data)
            except (ValueError,KeyError,TypeError) as e:self.send_json(400,dict(error=str(e)))
            except Exception as e:self.send_json(500,dict(error='Runtime error: '+str(e)))
    print(f'VoltMind persistent 630-kVA runtime on http://127.0.0.1:{port}',flush=True);ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
