import { assessmentCondition } from '../services/assessment'
export default function IncidentSummary({ alerts, session, current, onOpen }) {
  const warnings = alerts.filter(a => a.severity === 'WARNING')
  const active = warnings.filter(a => a.status === 'ACTIVE').length
  const readiness = alerts.filter(a => a.category === 'DATA QUALITY').length
  return <section className="incident-spotlight" aria-label="Session incident summary">
    <div className="incident-headline"><span className="section-kicker">MONITORING SUMMARY / EVIDENCE FIRST</span><div><strong>{(session?.processedRows ?? 0).toLocaleString()}</strong><h2>readings processed</h2></div><p className="summary-condition">Last two-hour assessment: <b>{assessmentCondition(current).replaceAll('_',' ').toLowerCase()}</b></p><p><b>{active} active warning episodes</b><span> · {warnings.length} recorded warning episodes · {readiness} readiness events</span></p></div>
    <div className="incident-breakdown">{[['THERMAL','Thermal'],['ELECTRICAL','Electrical'],['OIL','Oil'],['TERMINAL','Terminal'],['SENSOR','Sensor'],['COMMUNICATION','Link']].map(([id,label]) => <div key={id}><span>{label}</span><strong>{alerts.filter(a => a.category === id).length}</strong></div>)}<button type="button" onClick={onOpen}>View incident timeline <span aria-hidden="true">↗</span></button></div>
    <small>Category counts are detected condition episodes, not software errors or confirmed equipment failures. Readiness events include model warm-up and insufficient assessment data. Recorded warnings remain in history after recovery; the active count shows current episodes.</small>
  </section>
}

