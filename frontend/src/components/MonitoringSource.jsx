import { useRef, useState } from 'react'

export default function MonitoringSource({ monitoring }) {
  const filePicker = useRef(null)
  const [files, setFiles] = useState({}), [verified, setVerified] = useState(false), [timezone, setTimezone] = useState('Asia/Kolkata')
  const [configurationError, setConfigurationError] = useState('')
  const m = monitoring
  const preparing = ['UPLOADING', 'PREPARING', 'STARTING'].includes(m.status)
  const replays = m.dataset?.replays || m.local?.replays || []
  const options = async () => {
    const out = { timezone, verified_healthy: verified }
    for (const key of ['schema', 'units', 'calibration', ...(Number(m.rating) === 100 ? ['datasetInput'] : [])]) if (files[key]) {
      try { out[key] = JSON.parse(await files[key].text()) } catch { throw new Error(`Invalid ${key} JSON file`) }
    }
    return out
  }
  const local = async () => { setConfigurationError(''); try { await m.startLocal(await options(), m.selectedReplay, files.commissioning) } catch (e) { setConfigurationError(e.message) } }
  const upload = async (file) => { if (!file) return; setConfigurationError(''); try { await m.startUpload(file, await options(), files.commissioning) } catch (e) { setConfigurationError(e.message) } }
  return <section className="monitoring-source" aria-label="Data source and replay controls">
    <div className="source-topline"><span>{m.rating}-kVA CONDITION MONITORING</span><strong data-testid="session-status">{m.session ? m.status : m.status === 'IDLE' ? 'NO ACTIVE MONITORING SESSION' : m.status}</strong></div>
    <div className="source-actions">
      <label className="rating-selector">TRANSFORMER RATING <select aria-label="Transformer rating" value={m.rating} disabled={preparing} onChange={(e) => { setFiles({});setVerified(false);setConfigurationError('');m.changeRating(e.target.value) }}><option value="100">100 kVA</option><option value="250">250 kVA</option><option value="630">630 kVA</option></select></label>
      <button type="button" className="primary-action" onClick={local} disabled={!m.local || preparing}>RUN ON LOCAL DATA</button>
      <button type="button" className="secondary-action" onClick={() => filePicker.current?.click()}>ADD A DATASET</button>
      {['UPLOADING','PREPARING','STARTING'].includes(m.status) && <button type="button" onClick={() => m.cancel().catch((e)=>setConfigurationError(e.message))}>Cancel preparation</button>}
      <input ref={filePicker} aria-label="Upload SCADA dataset" type="file" accept={Number(m.rating) === 100 ? ".csv,.tsv,.txt,.xlsx,.json,.jsonl,.ndjson" : ".csv,text/csv"} className="visually-hidden" onChange={(e) => { upload(e.target.files[0]); e.target.value = '' }} />
      <label className="inline-select"><span>REPLAY</span><select aria-label="Replay selector" value={m.selectedReplay} onChange={(e) => m.changeReplay(e.target.value)} disabled={!replays.length || preparing}>{replays.map((r) => <option key={r.id} value={r.id}>{r.id==='DEMO100_THERMAL_TWIN' ? 'JUDGE DEMO · thermal twin · synthetic' : r.id} · {r.rows.toLocaleString()} rows</option>)}</select></label>
      <label className="inline-select"><span>REPLAY SPEED</span><select aria-label="Replay speed" value={m.speed} onChange={(e) => m.changeSpeed(Number(e.target.value))}>{[1, 5, 10, 30, 60].map((v) => <option key={v} value={v}>{v}x</option>)}</select></label>
    </div>
    <p className="source-help">{m.dataset ? `${m.dataset.mode === 'LOCAL' ? 'LOCAL SCADA' : 'UPLOADED DATA'} / ${m.dataset.filename}` : m.local ? `LOCAL DATA READY / ${m.local.filename} · ${m.local.replays.length} replays · ${m.local.totalRows.toLocaleString()} rows. Click RUN ON LOCAL DATA to start.` : m.error ? 'Local dataset unavailable; see the error below.' : `Loading and validating ${m.rating}-kVA local data. First load can take 1–2 minutes.`} Historical samples are five minutes apart; playback uses 1 second per row at 1x.</p>
    {(m.progressText || configurationError || m.error) && <div className={configurationError || m.error ? 'inline-error' : 'processing-state'} role={configurationError || m.error ? 'alert' : 'status'}>{configurationError || m.error || m.progressText}</div>}
    {m.session && <div className="session-controls">
      <button type="button" onClick={() => m.control(m.status === 'COMPLETE' ? 'restart' : 'play')} disabled={!['PAUSED', 'COMPLETE'].includes(m.status)}>Play</button>
      <button type="button" onClick={() => m.control('pause')} disabled={m.status !== 'RUNNING'}>Pause</button>
      <button type="button" onClick={() => m.control('resume')} disabled={m.status !== 'PAUSED'}>Resume</button>
      <button type="button" onClick={() => m.control('restart')}>Restart</button>
      <button type="button" onClick={() => m.control('stop')}>Stop</button>
      <button type="button" onClick={m.reconnect}>Reconnect stream</button>
      {m.dataset?.mode === 'UPLOADED' && <button type="button" onClick={() => m.removeUpload().catch((e) => setConfigurationError(e.message))}>Remove uploaded data</button>}
      <span data-testid="replay-progress">{m.session.processedRows.toLocaleString()} / {m.session.totalRows.toLocaleString()} rows · {m.session.progressPct.toFixed(1)}%</span>
      <progress aria-label="Replay progress" value={m.session.processedRows} max={m.session.totalRows} />
    </div>}
    <details className="dataset-explanation"><summary>What are SCADA, R00 and these graphs?</summary>
      <p>SCADA means Supervisory Control and Data Acquisition: a notebook of sensor readings. One CSV row records the transformer at one time. In the bundled simulated data, rows are five minutes apart.</p>
      <p>The selected final 100-kVA dataset has 60 original independent synthetic replay IDs plus one separate 4,032-row thermal-twin demonstration, each with 4,032 five-minute readings over 14 days. An ID identifies a separate simulated story, not the next time interval or a verified physical transformer. The 250-kVA dataset keeps its 24 replays with 6,048 readings each; the 630-kVA dataset keeps its 24 replays with 8,064 readings each. Uploaded IDs come from the uploaded file.</p>
      <p>Actual oil is the recorded temperature. Expected oil is the thermal model’s estimate under that load and ambient temperature. Their difference is the thermal residual. Graph time comes from the dataset, not today’s clock. Grey bands mark unavailable readings or expectations. Optional dotted bridges across short gaps are display estimates only; long gaps remain unavailable.</p>
      <p>Each 24 rows forms a two-hour block. The main health, risk and maintenance summary updates automatically at block boundaries. Live sensor readings and alerts continue. At 60x, a full 100-kVA replay takes about 67 seconds and a 250-kVA replay about 101 seconds, and a 630-kVA replay about 134 seconds plus processing overhead; speed does not change historical time.</p>
    </details>
    <details className="input-configuration"><summary>Advanced upload settings (optional)</summary>
      <p>Local data uses independent synthetic commissioning. Uploaded data needs its own matching calibration; thermal inference abstains when that evidence is missing. Use separate verified healthy commissioning; never assume uploaded monitoring data is healthy. Configuration applies to the next source start.</p>
      <div className="configuration-grid">{[['schema', 'Schema mapping JSON'], ['units', 'Unit mapping JSON'], ['calibration', 'Asset calibration JSON'], ['commissioning', 'Separate healthy commissioning CSV'], ...(Number(m.rating) === 100 ? [['datasetInput', 'File and time settings JSON']] : [])].map(([key, label]) => <label key={key}>{label}<input type="file" accept={key === 'commissioning' ? '.csv' : '.json'} onChange={(e) => setFiles((old) => ({ ...old, [key]: e.target.files[0] || null }))} /></label>)}
        <label>Timezone for naive timestamps<input aria-label="Naive timestamp timezone" value={timezone} onChange={(e) => setTimezone(e.target.value)} /></label>
        <label className="verified-choice"><input type="checkbox" checked={verified} onChange={(e) => setVerified(e.target.checked)} />I independently verified that the separate commissioning data is healthy.</label>
      </div>
      <button type="button" onClick={() => { setFiles({}); setVerified(false); setTimezone('Asia/Kolkata'); setConfigurationError('') }}>Reset configuration</button>
      {m.dataset?.warnings?.length > 0 && <p>Input limitations: {m.dataset.warnings.join(', ')}</p>}
    </details>
  </section>
}
