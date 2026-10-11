import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../services/api'
import { insightCategories, value, downloadFile } from '../services/intelligence'
import { answerMonitoring, formatTime } from '../services/monitoringInsights'

export function Evidence({ event, onClose }) {
  const dialog = useRef(null)
  useEffect(() => {
    if (!event) return
    const previous = document.activeElement
    dialog.current?.querySelector('button')?.focus()
    return () => previous?.focus()
  }, [event])
  if (!event) return null
  const evidence = event.evidence, incident = evidence?.incident || event
  const source = evidence?.startMeasurements || incident.evidence || {}
  const investigation = source.investigation || evidence?.pointInvestigation
  const labels = { actualOilTempC: ['Actual oil',' °C'],topOilTempC: ['Actual oil',' °C'],expectedOilTempC: ['Expected oil',' °C'],thermalResidualC: ['Actual minus expected oil',' °C'],loadingPct: ['Apparent-power loading','%'],ambientTempC: ['Ambient air temperature',' °C'],thermalScore: ['Uncalibrated detector score',''],decisionThreshold: ['Detector threshold',''],dataConfidence: ['Measurement readiness',''],calibrationStatus: ['Calibration contract',''] }
  return createPortal(<div className="evidence-backdrop" onClick={onClose}><section ref={dialog} className="evidence-dialog" role="dialog" aria-modal="true" aria-label="Fault evidence report" tabIndex={-1} onClick={(e) => e.stopPropagation()} onKeyDown={(e) => { if (e.key === 'Escape') onClose(); if (e.key === 'Tab') { const items = [...dialog.current.querySelectorAll('button,summary,a,input,[tabindex="0"]')]; const first = items[0], last = items.at(-1); if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus() } else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus() } } }}>
    <button className="panel-close" autoFocus onClick={onClose}>Close report</button><p className="section-kicker">RECORDED EVIDENCE / {event.id}</p><h2>{value(event.category || incident.category)} investigation</h2>
    <h3>What happened?</h3><p>{incident.explanation || 'A monitored condition generated a recorded alert.'}</p><p>{value(event.start || incident.timestamp)} — {event.status === 'ACTIVE' ? `Still active; latest observation ${event.end}` : value(event.end || incident.resolvedTimestamp || 'Observation snapshot')}</p>
    <h3>Why VoltMind flagged it</h3><dl className="intelligence-metrics">{Object.entries(source).filter(([,v]) => v === null || typeof v !== 'object').map(([k, v]) => <div key={k}><dt>{labels[k]?.[0] || k.replace(/([A-Z])/g, ' $1')}</dt><dd>{typeof v === 'boolean' ? v ? 'Yes' : 'No' : value(v,labels[k]?.[1] || '')}</dd></div>)}</dl>
    <h3>What may have contributed?</h3><p>{investigation?.message || 'Review the recorded loading, ambient and residual history. Changed cooling, additional losses and a biased temperature sensor remain alternatives; a physical cause is unconfirmed.'}</p>{investigation?.competingExplanations?.map((h) => <p key={h.explanation}>{h.explanation} {h.support} Next check: {h.verification}</p>)}
    <h3>How reliable is this assessment?</h3><p>Calibration: {value(evidence?.calibration?.calibration_status)}. Missing or suspect observations interrupt the thermal assessment. Local data and commissioning are synthetic.</p>
    <h3>What to do next</h3><p>Independently verify temperature, inspect cooling and review sustained phase loading before assigning a component fault.</p>
    <button onClick={() => downloadFile(`VoltMind-evidence-${event.id}.json`, event)}>Download evidence JSON</button><button onClick={() => window.print()}>Print / Save as PDF</button>
    <details><summary>Complete recorded source evidence</summary><pre>{JSON.stringify(event, null, 2)}</pre></details>
  </section></div>, document.body)
}

export function SummaryBody({ summary, category, onEvent }) {
  if (!summary) return <p>No processed monitoring history is available yet.</p>
  const s = summary.statistics, model = summary.model, categories = { thermal: ['THERMAL', 'OIL', 'TERMINAL'], electrical: ['ELECTRICAL'], 'data-quality': ['SENSOR', 'COMMUNICATION', 'DATA QUALITY'] }
  const events = summary.incidents.filter((e) => !categories[category] || categories[category].includes(e.category))
  return <div className="insight-body"><p className="summary-scope">{s.complete ? 'Complete replay' : 'Preliminary — processed rows only'} · {s.processedRows.toLocaleString()} / {s.totalRows.toLocaleString()} readings</p>
    {category === 'overall' && <><dl className="intelligence-metrics">{[['Oil maximum', value(s.highestOilC, ' °C')], ['Largest oil difference', value(s.maximumResidualC, ' °C')], ['Peak apparent-power loading', value(s.maximumApparentLoadingPct, '%')], ['Thermal alert rows', s.thermalAlertRows], ['Assessed readings', s.assessableRows], ['Normal assessed readings', s.normalAssessedRows]].map(([a, b]) => <div key={a}><dt>{a}</dt><dd>{b}</dd></div>)}</dl><p>{s.monitoringStart} — {s.monitoringEnd}</p><p>Saved incidents: {Object.entries(s.incidentCounts).map(([k, n]) => `${value(k)}: ${n}`).join(' · ')}</p></>}
    {category === 'thermal' && <><p>Actual oil is measured in the dataset. Expected oil follows the independently commissioned thermal model. Their difference is not a confirmed physical diagnosis.</p><p>{s.thermalAlertRows} alert readings; {s.incidentCounts.THERMAL} distinct saved thermal incidents.</p><p>Oil depletion and LV terminal heating are separate experimental detectors; no internal-bushing or short-circuit diagnosis is inferred.</p></>}
    {category === 'electrical' && <><p>{s.electricalWarningRows} electrical-warning readings; {s.incidentCounts.ELECTRICAL} distinct saved incidents.</p><p>Loading, undervoltage and imbalance warnings describe operating stress. They do not confirm equipment damage.</p></>}
    {category === 'data-quality' && <ul><li>{s.communicationOutageRows} communication-outage readings.</li><li>{s.sensorSuspectRows} sensor-suspect readings.</li><li>{s.dataQualityRows} readings have reported quality or readiness limitations.</li><li>{s.processedRows - s.assessableRows} thermal readings were unassessed, including warm-up and missing calibration.</li></ul>}
    {category === 'model' && <><dl className="intelligence-metrics">{[['Model', model?.modelVersion], ['Readiness', model?.warmupStatus], ['Calibration', model?.calibrationStatus], ['Score definition', model?.scoreDefinition], ['Decision threshold', model?.decisionThreshold]].map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{value(v)}</dd></div>)}</dl><p>Independently generated synthetic commissioning is not field-verified calibration. Detector scores are not failure probabilities.</p></>}
    {category === 'recurrence' && <><p>{summary.recurrence.explanation}</p><p>Intervals between distinct thermal incidents: {summary.recurrence.intervalDays.map((n) => `${n.toFixed(2)} days`).join(', ') || 'Insufficient incidents'}</p><p>{summary.maintenance.length ? `${summary.maintenance.length} maintenance actions recorded.` : 'No maintenance activity has been recorded.'}</p>{summary.recurrence.repairEffectiveness.map((r) => <p key={r.record.id}>{value(r.status)} · {r.matchedRows} comparable readings · residual reduction {value(r.meanResidualReductionC, ' °C')}</p>)}<p>{summary.recurrence.scope}</p></>}
    {category === 'thermal-dna' && <><h3>{value(summary.thermalDNA.status)}</h3><p>{summary.thermalDNA.message}</p><p>{summary.thermalDNA.episodes.length} suitable natural load-response episodes.</p><p>This describes how the transformer heats and cools as demand changes. A sensor bias can mimic a response change; damage is not established.</p></>}
    {category === 'maintenance' && <><ul>{summary.recommendations.map((r) => <li key={r}>{r}</li>)}</ul><p>{summary.investigation?.message}</p><p>{summary.latestSimulation?.recommendation || 'Test a load reduction in Intelligence Lab; a result appears only after you run the simulation.'}</p>{summary.latestSimulation && <small>Hypothetical scenario from {summary.latestSimulation.timestamp}; it is not a live control action.</small>}<p>Recorded repair completion is not confirmed recovery.</p></>}
    {['overall','thermal','electrical','data-quality','maintenance'].includes(category) && <div className="incident-links">{events.length === 0 ? <p>No matching incidents recorded in processed history.</p> : events.map((e) => <button key={e.id} className={e.category === 'THERMAL' ? 'serious-incident' : ''} onClick={() => onEvent(e)}>{value(e.category)} · {formatTime(e.start)} · {value(e.status)}<span>View evidence →</span></button>)}</div>}
    <details><summary>Scope and limitations</summary><p>{summary.scope}</p><ul>{summary.limitations.map((r) => <li key={r}>{r}</li>)}</ul></details>
  </div>
}

export default function Insights({ intelligence, rating, current }) {
  const [open, setOpen] = useState(false), [category, setCategory] = useState('overall'), [event, setEvent] = useState(null)
  const [question, setQuestion] = useState(''), [messages, setMessages] = useState([]), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const request = useRef(null), log = useRef(null), input = useRef(null), evidenceDetails = useRef(null), activeSession = useRef(intelligence.sessionId)
  activeSession.current = intelligence.sessionId
  useEffect(() => { setMessages([]); setEvent(null); setError(''); setBusy(false); request.current?.abort() }, [intelligence.sessionId])
  useEffect(() => { if (open) input.current?.focus() }, [open])
  useEffect(() => { log.current?.scrollTo({ top: log.current.scrollHeight, behavior: 'smooth' }) }, [messages, busy])
  useEffect(() => () => request.current?.abort(), [])
  const ask = async (text = question) => {
    const q = text.trim(); if (!q || busy) return
    setQuestion(''); setError(''); setMessages(old => [...old, { role: 'user', text: q }]); setBusy(true)
    const id = intelligence.sessionId
    request.current?.abort(); request.current = new AbortController()
    try {
      const fresh = id && rating === 100 ? await api(`/summary/overall?sessionId=${encodeURIComponent(id)}`, { signal: request.current.signal }) : null
      if (id !== activeSession.current) return
      const reply = rating !== 100 ? { category: 'overall', text: 'The evidence assistant supports 100 kVA. The 250/630 kVA monitoring models remain available in Live Twin and Alerts.' } : answerMonitoring(q, fresh, current)
      setCategory(reply.category); setMessages(old => [...old, { role: 'assistant', ...reply }])
    } catch (e) { if (e.name !== 'AbortError' && id === activeSession.current) { setError(e.message); setMessages(old => [...old, { role: 'assistant', text: 'I could not read the monitoring history. Check the ML and backend services, then retry your question.' }]) } }
    finally { if (id === activeSession.current) setBusy(false) }
  }
  const exportSummary = async (format) => {
    try { const r = await api(`/summary/export?sessionId=${encodeURIComponent(intelligence.sessionId)}`); downloadFile(`VoltMind-monitoring-summary.${format === 'json' ? 'json' : 'html'}`, format === 'json' ? r.summary : r.printableHtml, format === 'json' ? 'application/json' : 'text/html') } catch (e) { setError(e.message) }
  }
  return createPortal(<><button className="insights-toggle" aria-label="Open VoltMind Assistant" aria-expanded={open} aria-controls="voltmind-insights" onClick={() => setOpen(!open)}><span className="assistant-dot" />VoltMind Assistant <span>{open ? '−' : 'Ask a question +'}</span></button>
    {open && <aside id="voltmind-insights" className="insights-panel" role="dialog" aria-label="VoltMind Assistant" onKeyDown={(e) => { if (e.key === 'Escape') { setOpen(false); document.querySelector('.insights-toggle')?.focus() } }}>
      <header className="assistant-header"><div><span className="section-kicker">LOCAL MONITORING ASSISTANT</span><h2>VoltMind Insights</h2></div><button aria-label="Close assistant" onClick={() => setOpen(false)}>×</button></header>
      <p className="assistant-context">{intelligence.summary ? `${intelligence.summary.statistics.processedRows.toLocaleString()} / ${intelligence.summary.statistics.totalRows.toLocaleString()} readings · ${intelligence.summary.statistics.complete ? 'Replay complete' : 'Live evidence'}` : 'Waiting for a monitoring session'} · {rating} kVA</p>
      <div className="assistant-log" role="log" aria-label="Monitoring conversation" aria-live="polite" ref={log}><div className="chat-message chat-message--assistant"><strong>VoltMind</strong><p>Ask me what was detected, why oil temperatures differ, or why the graph has gaps. Answers use processed measurements and saved evidence.</p></div>{messages.map((m,i) => <div className={`chat-message chat-message--${m.role}`} key={i}><strong>{m.role === 'user' ? 'You' : 'VoltMind'}</strong><p>{m.text}</p>{m.timestamp && <small>Snapshot: {formatTime(m.timestamp)}</small>}{m.category && intelligence.summary && <button className="chat-evidence-link" onClick={() => { setCategory(m.category); evidenceDetails.current.open = true; evidenceDetails.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' }) }}>View supporting evidence →</button>}</div>)}{busy && <p role="status">Reading monitoring evidence…</p>}</div>
      <form className="assistant-question" onSubmit={e => { e.preventDefault(); ask() }}><label className="visually-hidden" htmlFor="monitoring-question">Ask about this transformer</label><input id="monitoring-question" ref={input} maxLength={600} autoComplete="off" value={question} onChange={e => setQuestion(e.target.value)} placeholder="What faults were detected?" /><button disabled={busy || !question.trim()}>Send</button></form>
      <div className="assistant-quick"><button disabled={busy} onClick={() => ask('What faults were detected?')}>Detected faults</button><button disabled={busy} onClick={() => ask('Why is the oil temperature different?')}>Oil temperature</button><button disabled={busy} onClick={() => ask('Why are there gaps in the graph?')}>Graph gaps</button></div>
      {(error || intelligence.error) && <p role="alert" className="inline-error">{error || intelligence.error}</p>}
      <details ref={evidenceDetails} className="assistant-evidence"><summary>Explore evidence and all eight summaries</summary><div className="insight-options">{insightCategories.map(([id, label]) => <button key={id} aria-pressed={category === id} onClick={() => setCategory(id)}>{label}</button>)}</div>{rating === 100 && <SummaryBody summary={intelligence.summary} category={category} onEvent={setEvent} />}<div className="report-actions"><button disabled={!intelligence.summary || rating !== 100} onClick={() => exportSummary('json')}>Download JSON</button><button disabled={!intelligence.summary || rating !== 100} onClick={() => exportSummary('html')}>Printable report / PDF</button></div></details>
      <small className="assistant-note">Evidence-based answers with supported topics; physical causes and field accuracy require verification.</small>
    </aside>}
    <Evidence event={event} onClose={() => setEvent(null)} />
  </>, document.body)
}
