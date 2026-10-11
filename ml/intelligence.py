"""Evidence-only intelligence around locked inference; persistent local SQLite memory."""
from pathlib import Path
import sqlite3,json,hashlib,math,copy,html
import numpy as np
import pandas as pd

CATEGORIES=['overall','thermal','electrical','data-quality','model','recurrence','thermal-dna','maintenance']
def clean(v):
    if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if hasattr(v,'item'):return clean(v.item())
    if isinstance(v,float) and not math.isfinite(v):return None
    return v
def dump(v):return json.dumps(clean(v),allow_nan=False)
def avg(values):
    a=[x for x in values if x is not None and math.isfinite(x)];return float(np.mean(a)) if a else None
def investigate(p,recent):
    t=p['telemetry'];m=p['ml'];q=p['quality'];evidence=[];hypotheses=[]
    quality=list(q['issues']);sensor=m['assetCondition']=='SENSOR_SUSPECT'
    if recent:
        before=recent[-1]['telemetry']['topOilTempC'];value=t['topOilTempC']
        if before is not None and value is not None and abs(value-before)>4:
            sensor=True;evidence.append(f'Oil reading changed {value-before:+.1f} C in one nominal five-minute interval.')
        vals=[r['telemetry']['topOilTempC'] for r in recent[-35:]]+[value]
        if len(vals)==36 and all(v is not None for v in vals) and max(vals)==min(vals):
            sensor=True
            evidence.append('Oil reading stayed exactly constant for three hours; a frozen sensor is possible, but stable operation can also produce steady readings.')
        if len(recent)>=12:
            residual=[r['ml']['thermalResidualC'] for r in recent[-12:]]
            if all(v is not None for v in residual) and abs(residual[-1]-residual[0])>2:
                evidence.append('Residual changed over the recent hour. Sensor drift and physical response changes remain competing explanations.')
    if t['communicationAvailable'] is not True:status='DATA_UNAVAILABLE';message='Communication is unavailable; transformer condition cannot be inferred from these readings.'
    elif sensor:status='SENSOR_REVIEW';message='The temperature reading may be unreliable. Verify the sensor before concluding the transformer has overheated.'
    elif m['thermalAlert'] is True:status='THERMAL_ABNORMALITY_SUPPORTED';message='The transformer is heating more than the commissioned model expected.'
    else:status='INSUFFICIENT_CAUSAL_EVIDENCE';message='The available measurements do not establish the physical cause of the temperature difference.'
    if m['thermalResidualC'] is not None:evidence.append(f"Actual minus expected oil temperature: {m['thermalResidualC']:+.2f} C.")
    if m['phaseLoadingWarning'] is True:hypotheses.append({'explanation':'High phase loading may contribute to heating.','support':'The configured phase-loading warning is active.','verification':'Review sustained phase currents and operating load.'})
    if m['thermalAlert'] is True:hypotheses.append({'explanation':'Changed cooling or additional losses may explain sustained thermal excess.','support':'The locked detector reports abnormal thermal behavior.','verification':'Inspect cooling and independently verify temperature; current sensors cannot distinguish these causes.'})
    if sensor or m['thermalResidualC'] is not None:hypotheses.append({'explanation':'Temperature bias or drift remains an alternative.','support':'Oil-temperature disagreement alone does not distinguish a sensor error from a physical fault.','verification':'Compare against an independent calibrated temperature probe.'})
    return dict(investigationStatus=status,message=message,sensorSuspect=sensor,transformerAbnormalitySupported=m['thermalAlert'] is True,
      dataQualityIssues=quality,evidence=evidence,competingExplanations=hypotheses,recommendedVerification='Verify temperature, recent loading and cooling before assigning a root cause.',
      limitations=['No confirmed component diagnosis. Slow sensor bias can resemble physical thermal excess.','Synthetic calibration is not field validation.'])

def point_explanation(p,recent):
    investigation=investigate(p,recent);m=p['ml'];delta=m['thermalResidualC']
    return dict(actualOilTempC=p['telemetry']['topOilTempC'],expectedOilTempC=m['expectedOilTempC'],differenceC=delta,
      message='Expected temperature is unavailable until valid calibration and driver history are present.' if delta is None else f'The oil is {abs(delta):.1f} C {"above" if delta>=0 else "below"} the commissioned model expectation.',
      cause='The reason for this temperature difference has not been confirmed.',recommendedVerification=investigation['recommendedVerification'],
      loadingPct=p['telemetry']['loadingPct'],ambientTempC=p['telemetry']['ambientTempC'],residualMean60minC=m['residualMean60minC'],
      thermalAlert=m['thermalAlert'],dataConfidence=m['dataConfidence'],calibrationStatus=m['calibrationStatus'],investigation=investigation)

def project(p,body):
    if p['asset']['ratingKVA']!=100:raise ValueError('The maintenance simulator is configured for 100 kVA only')
    reduction=body.get('loadReductionPct',20);duration=body.get('durationHours',4)
    if isinstance(reduction,bool) or isinstance(duration,bool):raise ValueError('Numeric scenario values required')
    reduction=float(reduction);duration=float(duration)
    if not math.isfinite(reduction) or not 0<=reduction<=80 or not math.isfinite(duration) or not .5<=duration<=24:raise ValueError('Load reduction must be 0–80%; duration must be 0.5–24 hours')
    if set(body)-{'sessionId','loadReductionPct','durationHours'}:raise ValueError('Unsupported intervention fields')
    from round2_guarded_predict import calibration_issue
    cal=p['calibration'];asset=p['asset']['id'];frame=pd.DataFrame({'replay_id':[asset]})
    if calibration_issue(frame,cal):raise ValueError('A valid asset-specific calibration is required for simulation')
    t=p['telemetry'];oil=t['topOilTempC'];ambient=t['ambientTempC'];current=[t[k] for k in ['currentR','currentY','currentB']]
    if not p['quality']['thermalAssessable'] or any(v is None for v in [oil,ambient]+current):raise ValueError('Simulation needs a current assessable, reliable operating state')
    rated=100000/(math.sqrt(3)*433);load2=sum((v/rated)**2 for v in current)/3
    def equilibrium(factor):return ambient+cal['rise']*(cal['loss_ratio']+(1-cal['loss_ratio'])*load2*factor**2)**.8+cal['bias']
    baseline_eq=equilibrium(1);intervention_eq=equilibrium(1-reduction/100);a=math.exp(-5/cal['tau']);baseline=oil;intervention=oil;trajectory=[dict(minutes=0,baselineC=oil,interventionC=oil)]
    for minute in range(5,int(duration*60)+1,5):
        baseline=a*baseline+(1-a)*baseline_eq;intervention=a*intervention+(1-a)*intervention_eq
        trajectory.append(dict(minutes=minute,baselineC=baseline,interventionC=intervention))
    return dict(kind='HYPOTHETICAL_THERMAL_PROJECTION',assetId=asset,timestamp=p['timestamp'],loadReductionPct=reduction,durationHours=duration,
      currentOilC=oil,currentLoadPct=t['loadingPct'],ambientC=ambient,trajectory=trajectory,finalDifferenceC=baseline-intervention,
      recommendation=f'Under the stated assumptions, reducing loading by {reduction:g}% for {duration:g} hours gives {baseline-intervention:.1f} C less oil heating than unchanged operation. Verify load feasibility and temperature independently; this does not establish or repair a component fault.',
      assumptions=['Constant measured ambient and phase-current ratios; five-minute thermal stepping.','Independent copies initialized from measured oil; existing commissioned thermal equation.','Intervention assumes current reduces by the chosen fraction; no evolving faults or cooling repairs are simulated.'],
      limitations=['Illustrative projection, not a guaranteed outcome or a new ML prediction.','A reference/synthetic thermal calibration is not field-verified.'])

def thermal_dna(rows,reference=None):
    """Ambient-adjusted observed response; fitted independently from classifier."""
    if len(rows)<36:return dict(status='FINGERPRINT_NOT_ESTABLISHED',message='At least three hours of clean observations are needed.',episodes=[],reference=reference,limitations=['No healthy baseline is fabricated.'])
    episodes=[]
    for i in range(12,len(rows)-24):
        before=rows[i-6:i];window=rows[i:i+24]
        if episodes and i-episodes[-1]['index']<24:continue
        if any(not r['quality']['thermalAssessable'] or r['ml']['assetCondition']=='SENSOR_SUSPECT' or r['telemetry']['communicationAvailable'] is not True for r in before+window):continue
        loads=[r['telemetry']['loadingPct'] for r in before+window];oil=[r['telemetry']['topOilTempC'] for r in before+window];ambient=[r['telemetry']['ambientTempC'] for r in before+window]
        if any(v is None for v in loads+oil+ambient):continue
        load_before=float(np.mean(loads[:6]));load_after=float(np.mean(loads[6:12]));change=load_after-load_before
        if abs(change)<15 or np.std(loads[6:])>8 or max(ambient)-min(ambient)>2:continue
        ts=pd.to_datetime([r['timestamp'] for r in before+window],utc=True)
        if not (ts[1:]-ts[:-1]==pd.Timedelta(minutes=5)).all():continue
        rise=np.asarray(oil)-np.asarray(ambient);response=float(np.mean(rise[-6:])-np.mean(rise[:6]));normalized=response/(change/100)
        episodes.append(dict(index=i,timestamp=rows[i]['timestamp'],direction='heating' if change>0 else 'cooling',loadChangePct=change,
          initialRiseK=float(np.mean(rise[:6])),responseAfter2hK=response,responsePerUnitLoadK=normalized,ambientRangeC=max(ambient)-min(ambient),windowMinutes=120))
    if not episodes:return dict(status='INSUFFICIENT_EXCITATION',message='No clean sustained load change with stable ambient conditions was found.',episodes=[],reference=reference,limitations=['Spikes, sensor issues, missing intervals and changing ambient are excluded.'])
    fingerprint=float(np.median([e['responsePerUnitLoadK'] for e in episodes]));spread=float(np.std([e['responsePerUnitLoadK'] for e in episodes]))
    status='FINGERPRINT_NOT_ESTABLISHED';message='A descriptive response is available; an independently verified healthy baseline is still required.';comparisons=[]
    if reference and reference.get('episodes'):
        # Compare only matching directions, initial thermal rise and load-change magnitude.
        cutoff=pd.Timestamp(reference.get('referencePeriodEnd') or max(pd.Timestamp(r['timestamp'])+pd.Timedelta(minutes=120) for r in reference.get('episodes',[])))
        for e in episodes:
            if pd.Timestamp(e['timestamp'])<=cutoff:continue
            peers=[r for r in reference.get('episodes',[]) if r['direction']==e['direction'] and abs(r['initialRiseK']-e['initialRiseK'])<=3 and abs(r['loadChangePct']-e['loadChangePct'])<=10]
            if len(peers)>=3:
                ref=float(np.median([r['responsePerUnitLoadK'] for r in peers]));sd=float(np.std([r['responsePerUnitLoadK'] for r in peers]));drift=abs(e['responsePerUnitLoadK']-ref)>max(8,3*sd)
                comparisons.append({'timestamp':e['timestamp'],'referenceResponseK':ref,'observedResponseK':e['responsePerUnitLoadK'],'drift':drift,'matchedEpisodes':len(peers)})
        if len(comparisons)>=3:
            status='THERMAL_RESPONSE_DRIFT' if sum(c['drift'] for c in comparisons)>=3 else 'THERMAL_RESPONSE_STABLE'
            message='Thermal response differs from comparable healthy reference episodes; verify sensor bias and operating changes.' if status.endswith('DRIFT') else 'Comparable response episodes remain within the descriptive reference variation.'
        else:status='BASELINE_AVAILABLE';message='Healthy reference exists, but there are too few comparable response episodes for a drift decision.'
    return dict(status=status,message=message,episodes=episodes,fingerprintResponseK=fingerprint,spreadK=spread,comparisons=comparisons,reference=reference,
      limitations=['Descriptive load-response fingerprint, not measured damage or an insulation-life estimate.','Initial temperature, load-step magnitude and ambient must match; sensor bias cannot be independently ruled out.','Response after two hours is not a fully identified thermal time constant.'])

class IntelligenceStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.db() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS observations(session TEXT,row_no INTEGER,payload TEXT,PRIMARY KEY(session,row_no));
            CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY,dataset TEXT,asset TEXT,category TEXT,start TEXT,last TEXT,status TEXT,evidence TEXT);
            CREATE TABLE IF NOT EXISTS maintenance(id INTEGER PRIMARY KEY,dataset TEXT,asset TEXT,timestamp TEXT,action TEXT,component TEXT,observations TEXT,verification TEXT,followup TEXT);
            CREATE TABLE IF NOT EXISTS fingerprints(dataset TEXT,asset TEXT,reference TEXT,PRIMARY KEY(dataset,asset));
            CREATE TABLE IF NOT EXISTS simulations(session TEXT,timestamp TEXT,result TEXT);''')
    def db(self):
        db=sqlite3.connect(self.path,timeout=30);db.row_factory=sqlite3.Row;db.execute('PRAGMA journal_mode=WAL');return db
    def record(self,session,payload):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO observations VALUES(?,?,?)',(session.id,session.index,dump(payload)))
            for incident in session.alerts:
                if incident['status']!='ACTIVE' and incident.get('resolvedTimestamp')!=payload['timestamp']:continue
                identity=hashlib.sha256((session.dataset['fingerprint']+session.replay_id+incident['category']+incident['timestamp']).encode()).hexdigest()[:24]
                # Same source incident on replay restart updates one record, never creates fake recurrence.
                evidence=dict(incident=incident,modelVersion=payload['ml']['modelVersion'],modelSHA256=payload.get('modelSHA256'),
                  calibration=payload['calibration'],startMeasurements=incident['evidence'],latestMeasurements=payload['telemetry'] if incident['status']=='ACTIVE' else None,
                  latestModelEvidence=payload['ml'] if incident['status']=='ACTIVE' else None,limitations=['Recorded detector evidence, not a verified physical root cause.'])
                db.execute('INSERT INTO incidents VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET last=excluded.last,status=excluded.status,evidence=excluded.evidence',
                  (identity,session.dataset['fingerprint'],session.replay_id,incident['category'],incident['timestamp'],incident.get('resolvedTimestamp') or payload['timestamp'],incident['status'],dump(evidence)))
    def history(self,session):
        with self.db() as db:return [json.loads(r['payload']) for r in db.execute('SELECT payload FROM observations WHERE session=? ORDER BY row_no',(session.id,))]
    def incidents(self,session,current_only=False):
        with self.db() as db:events=[dict(r) for r in db.execute('SELECT * FROM incidents WHERE dataset=? AND asset=? ORDER BY start',(session.dataset['fingerprint'],session.replay_id))]
        if current_only:
            observed={hashlib.sha256((session.dataset['fingerprint']+session.replay_id+e['category']+e['timestamp']).encode()).hexdigest()[:24] for e in session.alerts}
            events=[e for e in events if e['id'] in observed]
        return events
    def maintenance(self,session):
        with self.db() as db:return [dict(r) for r in db.execute('SELECT * FROM maintenance WHERE dataset=? AND asset=? ORDER BY timestamp',(session.dataset['fingerprint'],session.replay_id))]
    def add_maintenance(self,session,body):
        if session.dataset.get('ratingKVA')!=100:raise ValueError('Maintenance intelligence is configured for 100 kVA')
        timestamp=pd.Timestamp(body.get('timestamp'))
        if pd.isna(timestamp) or timestamp.tzinfo is None:raise ValueError('Maintenance timestamp needs an explicit timezone')
        action=str(body.get('action','')).strip()
        if not action or len(action)>2000:raise ValueError('Enter a maintenance action of 1–2000 characters')
        fields=[str(body.get(k,'')).strip()[:2000] for k in ['component','observations','verification','followup']]
        with self.db() as db:
            row=db.execute('INSERT INTO maintenance(dataset,asset,timestamp,action,component,observations,verification,followup) VALUES(?,?,?,?,?,?,?,?)',
              (session.dataset['fingerprint'],session.replay_id,timestamp.tz_convert('UTC').isoformat(),action,*fields))
            return {'id':row.lastrowid,'recorded':True,'recoveryConfirmed':False}
    def dna(self,session,rows):
        with self.db() as db:r=db.execute('SELECT reference FROM fingerprints WHERE dataset=? AND asset=?',(session.dataset['fingerprint'],session.replay_id)).fetchone()
        return thermal_dna(rows,json.loads(r['reference']) if r else None)
    def establish_reference(self,session,body):
        if body.get('verifiedHealthy') is not True:raise ValueError('Independent healthy verification is required')
        rows=self.history(session);dna=thermal_dna(rows)
        if len(dna['episodes'])<3 or any(r['ml']['thermalAlert'] is True for r in rows):raise ValueError('Need at least three suitable episodes and no thermal alerts in the independently verified reference history')
        reference={'episodes':dna['episodes'],'referencePeriodEnd':rows[-1]['timestamp'],'verifiedByUser':True,'sourceSession':session.id,'establishedAt':pd.Timestamp.now(tz='UTC').isoformat(),'provenance':str(body.get('provenance',''))[:2000]}
        if not reference['provenance'].strip():raise ValueError('Record how healthy operation was independently verified')
        with self.db() as db:
            existing=db.execute('SELECT 1 FROM fingerprints WHERE dataset=? AND asset=?',(session.dataset['fingerprint'],session.replay_id)).fetchone()
            if existing:raise ValueError('Healthy reference is already locked for this asset/source; it will not be silently overwritten')
            db.execute('INSERT INTO fingerprints VALUES(?,?,?)',(session.dataset['fingerprint'],session.replay_id,dump(reference)))
        return reference
    def recurrence(self,session,rows=None,events=None):
        events=[r for r in (self.incidents(session) if events is None else events) if r['category']=='THERMAL'];maintenance=self.maintenance(session);intervals=[]
        for a,b in zip(events,events[1:]):intervals.append((pd.Timestamp(b['start'])-pd.Timestamp(a['start'])).total_seconds()/86400)
        repairs=[];rows=rows if rows is not None else self.history(session)
        for repair in maintenance:
            t=pd.Timestamp(repair['timestamp']);before=[r for r in rows if t-pd.Timedelta(hours=24)<=pd.Timestamp(r['timestamp'])<t and r['quality']['thermalAssessable']]
            after=[r for r in rows if t<pd.Timestamp(r['timestamp'])<=t+pd.Timedelta(hours=24) and r['quality']['thermalAssessable']]
            matched=[]
            for r in after:
                load=r['telemetry']['loadingPct'];ambient=r['telemetry']['ambientTempC']
                peers=[b for b in before if b['telemetry']['loadingPct'] is not None and load is not None and abs(b['telemetry']['loadingPct']-load)<=10 and b['telemetry']['ambientTempC'] is not None and ambient is not None and abs(b['telemetry']['ambientTempC']-ambient)<=2]
                baseline=avg([b['ml']['thermalResidualC'] for b in peers])
                if len(peers)>=6 and baseline is not None and r['ml']['thermalResidualC'] is not None:matched.append((baseline,r['ml']['thermalResidualC']))
            returned=[e for e in events if pd.Timestamp(e['start'])>t]
            change=avg([a-b for a,b in matched])
            state='INSUFFICIENT_COMPARABLE_HISTORY' if len(matched)<24 else 'ABNORMALITY_RETURNED' if returned else 'EVIDENCE_OF_IMPROVEMENT' if change is not None and change>=2 else 'NO_SUSTAINED_IMPROVEMENT_OBSERVED'
            repairs.append(dict(record=repair,status=state,matchedRows=len(matched),meanResidualReductionC=change,nextIncident=returned[0]['start'] if returned else None,
              limitation='Matched load within 10 percentage points and ambient within 2 C, 24h either side; minimum 24 matched post rows. Observational comparison does not prove repair causality.'))
        return dict(thermalIncidents=len(events),incidents=[{k:r[k] for k in ['id','start','last','status','category']} for r in events],intervalDays=intervals,
          approximatelyRegular=len(intervals)>=2 and np.std(intervals)<=.2*max(np.mean(intervals),1e-6),
          explanation='Repeated thermal incidents are recorded; loading, ambient, unresolved heating and sensor bias remain competing explanations.' if len(events)>1 else 'Insufficient distinct incidents to establish recurrence.',
          scope='Same asset and exact source fingerprint only; independent synthetic replays are never stitched into one asset history.',
          maintenance=maintenance,repairEffectiveness=repairs,limitations=['No permanent periodicity is inferred from a short monitoring period.','Recording a repair does not confirm recovery.'])
    def summary(self,session,category='overall'):
        if category not in CATEGORIES:raise ValueError('Unknown summary category')
        rows=self.history(session);events=self.incidents(session,current_only=True);recurrence=self.recurrence(session,rows,events);dna=self.dna(session,rows)
        def maximum(path):
            a=[r[path[0]][path[1]] for r in rows if r[path[0]].get(path[1]) is not None];return max(a) if a else None
        counts={c:sum(e['category']==c for e in events) for c in ['THERMAL','ELECTRICAL','SENSOR','COMMUNICATION','DATA QUALITY','OIL','TERMINAL']}
        # Only incidents actually encountered this session count; retained future replay memory stays excluded.
        stats=dict(processedRows=len(rows),totalRows=len(session.rows),complete=session.status=='COMPLETE',monitoringStart=rows[0]['timestamp'] if rows else None,monitoringEnd=rows[-1]['timestamp'] if rows else None,
            thermalAlertRows=sum(r['ml']['thermalAlert'] is True for r in rows),assessableRows=sum(r['quality']['thermalAssessable'] for r in rows),
            electricalWarningRows=sum(any(r['ml'][k] is True for k in ['phaseLoadingWarning','undervoltageWarning','imbalanceWarning']) for r in rows),
            communicationOutageRows=sum(r['telemetry']['communicationAvailable'] is not True for r in rows),sensorSuspectRows=sum(r['ml']['assetCondition']=='SENSOR_SUSPECT' for r in rows),
            dataQualityRows=sum(bool(r['quality']['issues']) for r in rows),normalAssessedRows=sum(r['quality']['thermalAssessable'] and r['ml']['assetCondition']=='NORMAL_OBSERVED' and r['ml'].get('oilAlert') is not True and r['ml'].get('terminalAlert') is not True for r in rows),
            highestOilC=maximum(('telemetry','topOilTempC')),maximumResidualC=maximum(('ml','thermalResidualC')),maximumApparentLoadingPct=maximum(('telemetry','loadingPct')),incidentCounts=counts)
        current=rows[-1] if rows else None
        with self.db() as db:simulation=db.execute('SELECT result FROM simulations WHERE session=? ORDER BY rowid DESC LIMIT 1',(session.id,)).fetchone()
        return dict(category=category,sessionId=session.id,dataset=session.source(),assetId=session.replay_id,statistics=stats,
          scope='Full processed session history and incidents encountered in this session only. Saved source records are deduplicated across restarts, but events not yet encountered in the current replay are excluded.',
          incidents=[dict(id=e['id'],category=e['category'],start=e['start'],end=e['last'],status=e['status'],evidence=json.loads(e['evidence'])) for e in events],
          investigation=current.get('explanation',{}).get('investigation') if current else None,model=current['ml'] if current else None,calibration=current['calibration'] if current else None,
          recurrence=recurrence,thermalDNA=dna,maintenance=self.maintenance(session),
          latestSimulation=json.loads(simulation['result']) if simulation else None,
          recommendations=[current['digitalTwin']['maintenanceRecommendation']] if current else ['Select and process a dataset before requesting a monitoring assessment.'],
          limitations=['All local 100 kVA data and model validation are synthetic.','Health/risk are engineering observation indices, not calibrated failure probabilities.','No insulation remaining-life estimate or confirmed internal fault diagnosis is supported.'])

def printable_report(summary):
    # Escape all user-entered/source text before HTML export.
    title='VoltMind monitoring evidence';stats=summary['statistics']
    sections=[('Monitoring summary',stats),('Model and calibration',{'model':summary['model'],'calibration':summary['calibration']}),('Incidents',summary['incidents']),('Recurrence and maintenance',summary['recurrence']),('Thermal DNA',summary['thermalDNA']),('Limitations',summary['limitations'])]
    body=''.join('<section><h2>'+html.escape(name)+'</h2><pre>'+html.escape(json.dumps(clean(value),indent=2))+'</pre></section>' for name,value in sections)
    return '<!doctype html><html><head><meta charset="utf-8"><title>'+title+'</title><style>body{font:14px Arial;max-width:950px;margin:40px auto;color:#111}h1{border-bottom:3px solid #111}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px Arial}section{break-inside:avoid}button{padding:10px}@media print{button{display:none}body{margin:12mm}}</style></head><body><button onclick="window.print()">Print / Save as PDF</button><h1>'+title+'</h1><p>'+html.escape(summary['assetId'])+' · '+html.escape(summary['scope'])+'</p>'+body+'</body></html>'
