"""Loopback-only persistent service, controlled datasets, causal replay and SSE."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from email.parser import BytesParser
from email.policy import default as email_policy
from urllib.parse import urlparse,parse_qs,unquote
from collections import deque
import json,threading,time,uuid,csv,io,hashlib,copy,math
import pandas as pd
from runtime.input_adapter_100kVA import read_csv
from runtime.dataset_compatibility_100kva import import_dataset
from runtime.schema_adapter_100kVA import SchemaAdapter100kVA,SIGNALS,CompatibilityError
from runtime.streaming_runtime_100kVA import DigitalTwinMLRuntime100kVA
from runtime.frontend_adapter_100kVA import to_frontend_payload
from calibration.commission_100kVA import resolve_calibration,commission_asset
from digital_twin import interpret
from assessment_window import AssessmentWindow
from model_registry import model_for, rating_value
from intelligence import IntelligenceStore,point_explanation,project,printable_report

ROOT=Path(__file__).resolve().parents[1]
MAX_BYTES=100*1024*1024
MAX_ROWS=200000
MAX_HISTORY=10000
SPEEDS=[1,5,10,30,60]

class APIError(ValueError):
    def __init__(self,message,status=400): super().__init__(message);self.status=status

def now(): return pd.Timestamp.now(tz='UTC').isoformat()

def json_clean(value):
    if isinstance(value,dict): return {k:json_clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [json_clean(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value): return None
    if hasattr(value,'item'): return json_clean(value.item())
    return value

class Session:
    def __init__(self,dataset,replay_id,calibration,options,speed,manager):
        self.id=uuid.uuid4().hex;self.dataset=dataset;self.replay_id=replay_id;self.manager=manager
        self.rows=dataset['groups'][replay_id];self.model=model_for(dataset.get('ratingKVA',100));self.runtime=self.model.runtime(calibration,**options)
        if hasattr(self.runtime,'bind'):self.runtime.bind(self.rows)
        self.lock=threading.RLock();self.stop_event=threading.Event();self.status='RUNNING';self.speed=speed
        self.index=0;self.current=None;self.history=deque(maxlen=MAX_HISTORY);self.alerts=[];self.active_alerts={};self.error=None
        self.assessment_window=AssessmentWindow()
        self.sequence=0;self.created_at=now();self.thread=threading.Thread(target=self.run,daemon=True,name='replay-'+self.id[:8])

    def snapshot(self):
        with self.lock:
            return dict(sessionId=self.id,status=self.status,processedRows=self.index,totalRows=len(self.rows),
              progressPct=self.index/len(self.rows)*100,speed=self.speed,error=self.error,
              source=self.source(),replayId=self.replay_id,createdAt=self.created_at,historyRetainedRows=len(self.history),
              historicalIntervalMinutes=5,playbackSecondsPerRow=1/self.speed,sequence=self.sequence)

    def source(self): return dict(mode=self.dataset['mode'],filename=self.dataset['filename'],datasetId=self.dataset['id'],replayId=self.replay_id,ratingKVA=self.dataset.get('ratingKVA',100))

    def update_alerts(self,payload):
        ml=payload['ml'];q=payload['quality'];t=payload['telemetry'];conditions={}
        if ml['thermalAlert'] is True: conditions['THERMAL']='Locked model thermal alert'
        if payload['asset']['ratingKVA']==100:
            if ml.get('oilAlert') is True:conditions['OIL']='Suspected oil inventory depletion; gauge bias remains an alternative.'
            if ml.get('terminalAlert') is True:conditions['TERMINAL']='Suspected R-phase LV terminal contact heating; not internal bushing diagnosis.'
        if any(ml[k] is True for k in ['phaseLoadingWarning','undervoltageWarning','imbalanceWarning']): conditions['ELECTRICAL']=ml['electricalState']
        if t['communicationAvailable'] is not True: conditions['COMMUNICATION']='Telemetry communication unavailable'
        if ml['assetCondition']=='SENSOR_SUSPECT': conditions['SENSOR']=', '.join(q['issues'])
        if ml['warmupStatus']=='WARMING_UP' and ml['assetCondition']!='SENSOR_SUSPECT': conditions['DATA QUALITY']='Collecting required clean temporal history'
        for category in list(self.active_alerts):
            if category not in conditions:
                interrupted=(category=='THERMAL' and not q['thermalAssessable']) or (category=='OIL' and ml.get('oilAlert') is None) or (category=='TERMINAL' and ml.get('terminalAlert') is None)
                self.active_alerts[category].update(status='EVIDENCE_INTERRUPTED' if interrupted else 'RESOLVED',resolvedTimestamp=payload['timestamp'])
                del self.active_alerts[category]
        for category,reason in conditions.items():
            if category not in self.active_alerts:
                alert=dict(id=uuid.uuid4().hex,category=category,severity='WARNING' if category in ['THERMAL','ELECTRICAL','SENSOR','COMMUNICATION','OIL','TERMINAL'] else 'INFO',
                   timestamp=payload['timestamp'],assetId=payload['asset']['id'],status='ACTIVE',resolvedTimestamp=None,
                   explanation=reason,evidence=dict(actualOilTempC=t['topOilTempC'],expectedOilTempC=ml['expectedOilTempC'],thermalResidualC=ml['thermalResidualC'],dataConfidence=ml['dataConfidence'],
                   loadingPct=t['loadingPct'],ambientTempC=t['ambientTempC'],thermalScore=ml['thermalScore'],decisionThreshold=ml.get('decisionThreshold'),
                   thermalAlert=ml['thermalAlert'],phaseLoadingWarning=ml['phaseLoadingWarning'],undervoltageWarning=ml['undervoltageWarning'],imbalanceWarning=ml['imbalanceWarning'],
                   calibrationStatus=ml['calibrationStatus'],qualityIssues=list(q['issues']),investigation=payload.get('explanation',{}).get('investigation')))
                self.alerts.append(alert);self.active_alerts[category]=alert

    def process_one(self):
        result=self.runtime.update(self.rows[self.index])
        payload=interpret(self.model.payload(result,self.runtime))
        self.index+=1;self.sequence+=1
        payload.update(sessionId=self.id,sequence=self.sequence,source=self.source(),processedAt=now())
        payload['replay']=self.snapshot()
        payload['assessment']=self.assessment_window.update(payload,final=self.index==len(self.rows))
        if self.dataset.get('ratingKVA')==100:
            payload['explanation']=point_explanation(payload,list(self.history)[-36:])
        self.current=payload;self.history.append(payload);self.update_alerts(payload)
        if self.dataset.get('ratingKVA')==100:self.manager.intelligence.record(self,payload)
        self.manager.inference_rows+=1
        if self.index==len(self.rows):
            self.status='COMPLETE';self.sequence+=1;self.current['replay']=self.snapshot()

    def run(self):
        while not self.stop_event.is_set():
            start=time.monotonic()
            with self.lock:
                if self.status=='RUNNING':
                    try: self.process_one()
                    except Exception as error:
                        self.status='FAILED';self.error=type(error).__name__+': '+str(error);self.sequence+=1
                if self.status in ['COMPLETE','FAILED','STOPPED']: return
                delay=1/self.speed if self.status=='RUNNING' else .05
            self.stop_event.wait(max(.001,delay-(time.monotonic()-start)))

    def stop(self):
        self.stop_event.set()
        with self.lock: self.status='STOPPED';self.sequence+=1
        self.thread.join(timeout=2)

class Manager:
    def __init__(self,instance_id,data_path=None,state_dir=None):
        self.instance_id=instance_id;self.local_path=Path(data_path or ROOT/'data/final100/scada/100kVA_SCADA_V4_FULL.csv').resolve()
        self.storage=Path(state_dir or ROOT/'.state/uploads').resolve();self.storage.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.datasets={};self.active=None;self.inference_rows=0
        self.selection_tokens={}
        self.intelligence=IntelligenceStore(self.storage.parent/'intelligence.sqlite')
        self.local_cache=None;self.local_caches={};self.model_check=DigitalTwinMLRuntime100kVA();self.model_infos=[model_for(r).info() for r in [100,250,630]];self.started_at=now()
        # Orphan uploads are owned by this service and are never auto-restored/replayed.
        for p in self.storage.glob('*.csv'):
            if p.stem.startswith('upload_') and p.resolve().parent==self.storage: p.unlink()

    def health(self):
        active100=model_for(100).info()
        return dict(application='VoltMind',status='UP',instanceId=self.instance_id,modelVersion=active100['modelVersion'],
          assessmentPolicy='24_ROWS_2_HOURS',supportedRatings=[100,250,630],models=self.model_infos,
          inputCompatibility100KVA=dict(version='1.0',formats=['csv','tsv','txt','xlsx','json','jsonl','ndjson'],requiresMeasuredSensors=True),
          modelStatus=active100['modelStatus'],modelSHA256=active100['modelSHA256'],
          activeSessionId=self.active.id if self.active and self.active.status not in ['STOPPED','FAILED','COMPLETE'] else None,
          inferenceRows=self.inference_rows,startedAt=self.started_at,engineering=dict(ratedCurrentA=self.model_check.config['rated_current_a'],nominalPhaseVoltageV=self.model_check.config['phase_neutral_voltage_v']))

    def stage(self,dataset,name):
        dataset['status']=name;dataset['validationSteps'].append(dict(stage=name,at=now()))

    def prepare(self,path,filename,mode,dataset_id=None,options=None,commissioning=None,verified=False,rating=100):
        model=model_for(rating);rating=model.rating
        dataset=dict(id=dataset_id or uuid.uuid4().hex,filename=filename,mode=mode,path=str(path),status='READING_CSV',validationSteps=[],warnings=[],error=None,ratingKVA=rating)
        self.datasets[dataset['id']]=dataset
        try:
            dataset['fingerprint']=hashlib.sha256(Path(path).read_bytes()).hexdigest()
            if rating==100:
                self.stage(dataset,'VALIDATING_SCHEMA')
                dataset.update(model.prepare(path,filename,mode,options,commissioning,verified))
                if mode=='LOCAL' and 'DEMO100_THERMAL_TWIN' in dataset['groups']:
                    demo_root=ROOT/'data/demo100'
                    digest=hashlib.sha256(Path(path).read_bytes())
                    digest.update((demo_root/'100kVA_THERMAL_TWIN_DEMO_4032.csv').read_bytes())
                    digest.update((demo_root/'calibration.json').read_bytes())
                    dataset['fingerprint']=digest.hexdigest()
                self.stage(dataset,'READY')
                return dataset
            self.stage(dataset,'READING_CSV')
            options=dict(options or {})
            if rating==100 and mode=='UPLOADED':
                frame,compatibility=import_dataset(path,filename,dataset_input=options.pop('datasetInput',None),
                    **{k:options[k] for k in ['schema','units','timezone','asset_id'] if k in options})
                dataset['compatibility']=compatibility
                dataset['warnings'].extend(compatibility['warnings']+compatibility['assumptions'])
                # Monitoring rows are now canonical. Commissioning remains in its
                # own original schema and must use original adapter settings.
                commissioning_options={k:options[k] for k in ['schema','units','timezone','asset_id'] if k in options}
                for key in ['schema','units','asset_id']:options.pop(key,None)
            else:
                frame=read_csv(path)
                commissioning_options=None
            if len(frame)>MAX_ROWS: raise APIError(f'CSV exceeds {MAX_ROWS} row limit')
            if len(frame.columns)>1000: raise APIError('CSV exceeds 1000 column limit')
            options=dict(options or {});options.pop('ratingKVA',None);adapter_options={k:options[k] for k in ['schema','units','timezone','asset_id'] if k in options}
            for k in ['schema','units','calibration']:
                if k in options and not isinstance(options[k],dict): raise APIError(k+' must be a JSON object')
            self.stage(dataset,'VALIDATING_SCHEMA');adapter=model.adapter(**adapter_options)
            mapping=model.mapping(adapter,frame.columns)
            missing=[field for field in SIGNALS if not mapping.get(field)]
            if missing: raise APIError('Required measured columns missing: '+', '.join(missing)+'. Supply an explicit schema mapping for renamed channels; do not invent sensors.')
            self.stage(dataset,'VALIDATING_MEASUREMENTS')
            records=frame.to_dict('records');canonical=[adapter.normalize(row) for row in records]
            model.validate_rating(canonical)
            self.stage(dataset,'CHECKING_TIMESTAMPS')
            valid_timestamps=sum(r['timestamp'] is not None for r in canonical)
            if not valid_timestamps: raise APIError('No valid timestamps. Normalize ambiguous/numeric timestamps to ISO-8601.')
            groups={}
            for raw,row in zip(records,canonical): groups.setdefault(row['asset_id'],[]).append(raw)
            warning_codes=set(dataset['warnings']) | {issue for row in canonical for issue in row.get('issues',row.get('_issues',[]))}
            intervals=[]
            for asset in groups:
                timestamps=[pd.Timestamp(r['timestamp']) for r in canonical if r['asset_id']==asset and r['timestamp'] is not None]
                delta=[(b-a).total_seconds()/60 for a,b in zip(timestamps,timestamps[1:])]
                intervals.extend(delta)
                if any(d!=5 for d in delta): warning_codes.add('NONREGULAR_TIMESTAMPS_ROWS_RETAINED')
            if intervals and not any(math.isclose(d,5) for d in intervals):
                raise APIError('Incompatible sampling interval: locked model requires five-minute history; no compatible intervals found.')
            self.stage(dataset,'RESOLVING_CALIBRATION')
            calibration=options.get('calibration')
            if commissioning is not None:
                if calibration is not None: raise APIError('Choose calibration OR commissioning, not both')
                calibration=model.commission(commissioning,verified,commissioning_options or adapter_options)
            calibration=model.resolve(calibration,local=mode=='LOCAL')
            model.validate_calibration(calibration,canonical)
            self.stage(dataset,'PREPARING_ML_RUNTIME')
            # Construct once to verify compatibility before an intentionally selected replay.
            model.runtime(calibration,**adapter_options)
            dataset.update(groups=groups,options=adapter_options,calibration=calibration,totalRows=len(records),warnings=sorted(warning_codes),
              replays=[dict(id=asset,rows=len(rows),firstTimestamp=next((c['timestamp'] for c in canonical if c['asset_id']==asset and c['timestamp'] is not None),None)) for asset,rows in groups.items()])
            self.stage(dataset,'READY')
        except Exception as e:
            dataset.update(error=str(e));self.stage(dataset,'FAILED')
        return dataset

    def metadata(self,dataset):
        return {k:copy.deepcopy(dataset.get(k)) for k in ['id','filename','mode','status','validationSteps','warnings','error','totalRows','replays','ratingKVA','compatibility']}

    def local(self,rating=100):
        rating=rating_value(rating)
        with self.lock:
            if rating not in self.local_caches:
                path=self.local_path if rating==100 else ROOT/('data/250kVA_SCADA_FINAL_BASIC.csv' if rating==250 else 'data/630kVA_SCADA_MAIN.csv')
                dataset=self.prepare(path,path.name,'LOCAL',dataset_id=f'local-{rating}kva',rating=rating)
                if dataset['status']=='FAILED': raise APIError(dataset['error'],422)
                self.local_caches[rating]=dataset
                if rating==100: self.local_cache=dataset
            return self.local_caches[rating]

    def upload(self,raw,filename,options=None,commissioning=None,verified=False):
        if sum(d['mode']=='UPLOADED' and d['status']!='FAILED' for d in self.datasets.values())>=10:
            raise APIError('Maximum ten uploaded datasets per worker. Stop and remove old uploads or restart the application.',413)
        rating=rating_value((options or {}).get('ratingKVA',100))
        dataset_id=uuid.uuid4().hex;path=self.storage/('upload_'+dataset_id+'.csv')
        path.write_bytes(raw)
        safe_name=Path(filename.replace('\\','/')).name[:180] or 'uploaded.csv'
        pending=dict(id=dataset_id,filename=safe_name,mode='UPLOADED',path=str(path),status='READING_CSV',validationSteps=[],warnings=[],error=None,ratingKVA=rating)
        self.datasets[dataset_id]=pending
        def task():
            self.prepare(path,safe_name,'UPLOADED',dataset_id,options,commissioning,verified,rating=rating)
            # Failed uploads contain no usable session; delete their controlled storage.
            if self.datasets[dataset_id]['status']=='FAILED' and path.resolve().parent==self.storage: path.unlink(missing_ok=True)
        threading.Thread(target=task,daemon=True).start()
        return self.metadata(pending)

    def selected(self,session_id):
        session=self.active
        if not session: raise APIError('No active monitoring session',404)
        if not session_id or session_id!=session.id: raise APIError('Stale or missing session ID; select the current session',409)
        return session

    def register_selection(self,body):
        client=body.get('clientId');generation=body.get('generation')
        if client is None: return None
        if not isinstance(client,str) or len(client)>80 or not isinstance(generation,int) or isinstance(generation,bool) or generation<1:
            raise APIError('Invalid selection token')
        with self.lock:
            if generation<self.selection_tokens.get(client,0): raise APIError('Stale data-source selection rejected',409)
            self.selection_tokens[client]=generation
            if len(self.selection_tokens)>256: self.selection_tokens.pop(next(iter(self.selection_tokens)))
        return client,generation

    def start(self,dataset,replay_id=None,speed=5,token=None):
        if dataset.get('status')!='READY': raise APIError(dataset.get('error') or 'Dataset is not ready',422)
        replay_id=replay_id or dataset['replays'][0]['id']
        if replay_id not in dataset['groups']: raise APIError('Unknown replay ID')
        model_for(dataset.get('ratingKVA',100)).validate_selection(dataset['calibration'],dataset['groups'][replay_id],replay_id)
        if speed not in SPEEDS: raise APIError('Replay speed must be 1, 5, 10, 30 or 60')
        with self.lock:
            if token and self.selection_tokens.get(token[0])!=token[1]: raise APIError('Stale data-source selection rejected',409)
            previous=self.active
            if previous: previous.stop()
            session=Session(dataset,replay_id,dataset['calibration'],dataset['options'],speed,self)
            session.client_id=token[0] if token else None
            self.active=session;session.thread.start()
            return session.snapshot()

    def control(self,action,session_id,body):
        with self.lock:
            session=self.selected(session_id)
            if action=='restart':
                token=self.register_selection(body) if body.get('clientId') else (session.client_id,self.selection_tokens.get(session.client_id)) if session.client_id else None
                return self.start(session.dataset,session.replay_id,session.speed,token)
            if action=='stop':
                session.stop();snapshot=session.snapshot();self.active=None;return snapshot
            with session.lock:
                if action=='pause':
                    if session.status not in ['RUNNING','PAUSED']: raise APIError('Only a running replay can pause',409)
                    session.status='PAUSED'
                elif action in ['resume','play']:
                    if session.status not in ['RUNNING','PAUSED']: raise APIError('Restart a completed/failed replay instead',409)
                    session.status='RUNNING'
                elif action=='speed':
                    if body.get('speed') not in SPEEDS: raise APIError('Unsupported replay speed')
                    session.speed=body['speed']
                else: raise APIError('Unknown replay control',404)
                session.sequence+=1
                if session.current: session.current['replay']=session.snapshot()
                return session.snapshot()

    def close(self):
        if self.active: self.active.stop()

def parse_multipart(content_type,body):
    message=BytesParser(policy=email_policy).parsebytes(('Content-Type: '+content_type+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+body)
    if not message.is_multipart(): raise APIError('Expected multipart/form-data')
    parts={}
    for part in message.iter_parts():
        name=part.get_param('name',header='content-disposition')
        if name in parts: raise APIError('Duplicate upload field: '+str(name))
        parts[name]=(part.get_filename(),part.get_payload(decode=True) or b'')
    if 'file' not in parts: raise APIError('CSV file is required')
    filename,data=parts['file']
    if not filename or Path(filename).suffix.lower() not in ['.csv','.tsv','.txt','.xlsx','.json','.jsonl','.ndjson']: raise APIError('Upload CSV, TSV, TXT, XLSX, JSON or JSON Lines')
    options=json.loads(parts.get('options',(None,b'{}'))[1])
    if not isinstance(options,dict): raise APIError('Upload options must be a JSON object')
    allowed={'schema','units','timezone','asset_id','calibration','verified_healthy','ratingKVA','datasetInput'}
    if set(options)-allowed: raise APIError('Unknown upload option')
    if 'datasetInput' in options and not isinstance(options['datasetInput'],dict):raise APIError('datasetInput must be a JSON object')
    if int(options.get('ratingKVA',100))!=100 and (Path(filename).suffix.lower()!='.csv' or 'datasetInput' in options):raise APIError('Extended input compatibility currently supports only 100 kVA')
    commissioning=None
    if 'commissioning' in parts:
        commission_name,raw=parts['commissioning']
        if not commission_name or not commission_name.lower().endswith('.csv'): raise APIError('Commissioning file must be CSV')
        commissioning=pd.read_csv(io.BytesIO(raw))
    return data,filename,options,commissioning,options.pop('verified_healthy',False) is True

def serve(port=8765,instance_id='manual',data_path=None,state_dir=None):
    manager=Manager(instance_id,data_path,state_dir)
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def log_message(self,*args): pass
        def respond(self,value,status=200):
            data=json.dumps(json_clean(value),allow_nan=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
        def body(self):
            length=int(self.headers.get('Content-Length','0'))
            if length<0 or length>MAX_BYTES: raise APIError('Upload/request exceeds 100 MiB limit',413)
            if self.headers.get('Transfer-Encoding'): raise APIError('Chunked uploads are unsupported; send a known content length')
            return self.rfile.read(length)
        def do_GET(self):
            try:
                url=urlparse(self.path);q=parse_qs(url.query);path=url.path
                if path=='/api/health': return self.respond(manager.health())
                if path=='/api/datasets/local': return self.respond(manager.metadata(manager.local(q.get('ratingKVA',['100'])[0])))
                if path=='/api/datasets/status':
                    dataset=manager.datasets.get(q.get('datasetId',[''])[0])
                    if not dataset: raise APIError('Unknown dataset ID',404)
                    return self.respond(manager.metadata(dataset))
                session=manager.selected(q.get('sessionId',[''])[0])
                if path.startswith('/api/summary/') or path.startswith('/api/intelligence/'):
                    if session.dataset.get('ratingKVA')!=100:raise APIError('These intelligence modules are configured for 100 kVA. Other-rating models remain unchanged.',422)
                    with session.lock:
                        if path.startswith('/api/summary/'):
                            category=path.rsplit('/',1)[-1]
                            summary=manager.intelligence.summary(session,'overall' if category=='export' else category)
                            if category=='export':return self.respond(dict(summary=summary,printableHtml=printable_report(summary)))
                            return self.respond(summary)
                        if path=='/api/intelligence/maintenance':return self.respond(dict(records=manager.intelligence.maintenance(session)))
                        if path=='/api/intelligence/dna':return self.respond(manager.intelligence.dna(session,manager.intelligence.history(session)))
                        if path=='/api/intelligence/evidence':
                            identity=q.get('incidentId',[''])[0]
                            events=manager.intelligence.incidents(session,current_only=True)
                            found=next((e for e in events if e['id']==identity or json.loads(e['evidence'])['incident']['id']==identity),None)
                            if not found:raise APIError('Unknown incident for this asset/source',404)
                            return self.respond(dict(incident=found,evidence=json.loads(found['evidence'])))
                if path=='/api/replay/stream': return self.stream(session,q)
                if path=='/api/replay/status': return self.respond(session.snapshot())
                with session.lock:
                    if path in ['/api/transformers/current','/api/transformer/current']: return self.respond(copy.deepcopy(session.current))
                    if path=='/api/transformers/history':
                        after=int(q.get('after',['0'])[0]);limit=min(10000,max(1,int(q.get('limit',['10000'])[0])))
                        return self.respond(dict(sessionId=session.id,history=[copy.deepcopy(r) for r in session.history if r['replay']['processedRows']>after][-limit:],retainedRows=len(session.history)))
                    if path=='/api/transformers/alerts': return self.respond(dict(sessionId=session.id,alerts=copy.deepcopy(session.alerts)))
                    if path=='/api/transformers/maintenance': return self.respond(session.current['digitalTwin'] if session.current else None)
                raise APIError('Unknown API route',404)
            except (APIError,ValueError,KeyError,FileNotFoundError) as e: self.respond(dict(error=str(e),status='FAILED'),getattr(e,'status',400))
            except (BrokenPipeError,ConnectionResetError): pass
            except Exception as e: self.respond(dict(error=type(e).__name__+': '+str(e),status='FAILED'),500)
        def do_POST(self):
            try:
                path=urlparse(self.path).path;raw=self.body()
                if path=='/api/datasets/upload':
                    data,filename,options,commissioning,verified=parse_multipart(self.headers.get('Content-Type',''),raw)
                    return self.respond(manager.upload(data,filename,options,commissioning,verified),202)
                body=json.loads(raw or b'{}')
                if not isinstance(body,dict): raise APIError('Request body must be a JSON object')
                if path.startswith('/api/intelligence/'):
                    session=manager.selected(body.get('sessionId'))
                    if session.dataset.get('ratingKVA')!=100:raise APIError('Intelligence actions are configured for 100 kVA only',422)
                    with session.lock:
                        if path=='/api/intelligence/simulate':
                            if not session.current:raise APIError('Process an assessable operating state first',422)
                            result=project(copy.deepcopy(session.current),body)
                            with manager.intelligence.db() as db:db.execute('INSERT INTO simulations VALUES(?,?,?)',(session.id,session.current['timestamp'],json.dumps(result)))
                            return self.respond(result)
                        if path=='/api/intelligence/maintenance':return self.respond(manager.intelligence.add_maintenance(session,body),201)
                        if path=='/api/intelligence/dna/reference':return self.respond(manager.intelligence.establish_reference(session,body),201)
                if path=='/api/replay/local/start':
                    token=manager.register_selection(body)
                    options=dict(body.get('options') or {})
                    options.pop('verified_healthy',None)
                    rating=rating_value(body.get('ratingKVA',options.pop('ratingKVA',100)))
                    if options.get('timezone')=='Asia/Kolkata': options.pop('timezone')
                    if options or body.get('commissioningCsv'):
                        base=manager.local(rating)
                        commissioning=pd.read_csv(io.StringIO(body['commissioningCsv'])) if body.get('commissioningCsv') else None
                        dataset=manager.prepare(base['path'],base['filename'],'LOCAL',dataset_id=f'local-configured-{rating}',options=options,commissioning=commissioning,verified=body.get('verifiedHealthy') is True,rating=rating)
                    else: dataset=manager.local(rating)
                    return self.respond(manager.start(dataset,body.get('replayId'),body.get('speed',5),token))
                if path=='/api/replay/uploaded/start':
                    token=manager.register_selection(body)
                    dataset=manager.datasets.get(body.get('datasetId'))
                    if not dataset: raise APIError('Unknown uploaded dataset ID',404)
                    if dataset['mode']!='UPLOADED': raise APIError('Dataset is not an upload')
                    return self.respond(manager.start(dataset,body.get('replayId'),body.get('speed',5),token))
                if path=='/api/replay/cancel':
                    token=manager.register_selection(body)
                    with manager.lock:
                        if manager.active and token and getattr(manager.active,'client_id',None)==token[0]:
                            manager.active.stop();manager.active=None
                    return self.respond(dict(status='IDLE'))
                if path.startswith('/api/replay/'):
                    return self.respond(manager.control(path.rsplit('/',1)[-1],body.get('sessionId'),body))
                if path=='/api/datasets/delete':
                    dataset=manager.datasets.get(body.get('datasetId'))
                    if not dataset or dataset['mode']!='UPLOADED': raise APIError('Only owned uploaded datasets can be removed')
                    if manager.active and manager.active.dataset['id']==dataset['id']: raise APIError('Stop the selected replay before removing its upload',409)
                    p=Path(dataset['path']).resolve()
                    if p.parent!=manager.storage or not p.stem.startswith('upload_'): raise APIError('Invalid upload storage path',400)
                    p.unlink(missing_ok=True);del manager.datasets[dataset['id']]
                    return self.respond(dict(deleted=True))
                raise APIError('Unknown API route',404)
            except (APIError,ValueError,KeyError,FileNotFoundError) as e: self.respond(dict(error=str(e),status='FAILED'),getattr(e,'status',400))
            except (BrokenPipeError,ConnectionResetError): pass
            except Exception as e: self.respond(dict(error=type(e).__name__+': '+str(e),status='FAILED'),500)
        def stream(self,session,q):
            try:
                last=int(self.headers.get('Last-Event-ID') or q.get('after',['0'])[0])
            except ValueError: raise APIError('Invalid stream cursor')
            self.close_connection=True
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Cache-Control','no-store');self.send_header('Connection','close');self.send_header('Transfer-Encoding','chunked');self.send_header('X-Accel-Buffering','no');self.end_headers()
            def send(data):
                # Explicit HTTP chunks make Java's upstream client publish even one small paused-session event immediately.
                self.wfile.write(format(len(data),'x').encode()+b'\r\n'+data+b'\r\n');self.wfile.flush()
            def finish():
                self.wfile.write(b'0\r\n\r\n');self.wfile.flush()
            last_status=None;heartbeat=time.monotonic()
            try:
                send(b': connected\n\n')
                while True:
                    with session.lock:
                        if manager.active is not session:
                            send(b'event: ended\ndata: {"reason":"SESSION_REPLACED"}\n\n');finish();return
                        rows=[copy.deepcopy(r) for r in session.history if r['replay']['processedRows']>last]
                        snapshot=session.snapshot()
                    for row in rows:
                        index=row['replay']['processedRows']
                        send(('id: '+str(index)+'\nevent: reading\ndata: '+json.dumps(row,allow_nan=False)+'\n\n').encode());last=index
                    if snapshot['status']!=last_status:
                        send(('event: status\ndata: '+json.dumps(snapshot)+'\n\n').encode());last_status=snapshot['status']
                    if time.monotonic()-heartbeat>2:
                        send(b': heartbeat\n\n');heartbeat=time.monotonic()
                    if snapshot['status'] in ['STOPPED','FAILED','COMPLETE']:
                        send(('event: ended\ndata: '+json.dumps(snapshot)+'\n\n').encode());finish();return
                    time.sleep(.03)
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError): return
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True
    print('VoltMind persistent worker ready on 127.0.0.1:'+str(port),flush=True)
    try: server.serve_forever(poll_interval=.1)
    except KeyboardInterrupt: pass
    finally: manager.close();server.server_close()

