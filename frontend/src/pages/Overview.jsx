import StatusPill from '../components/StatusPill'
import { assessmentTwin, assessmentCondition } from '../services/assessment'

function riskTone(level) {
  if (level === 'LOW') return 'success'
  if (level === 'CRITICAL') return 'danger'
  if (level === 'UNAVAILABLE') return 'neutral'
  return 'warning'
}

export default function Overview({ fleet, onOpenAsset, onNavigate, intelligence }) {
  const online = fleet.filter((item) => item.telemetry.communicationAvailable).length
  const attention = fleet.filter((item) => ['MODERATE', 'HIGH', 'CRITICAL'].includes(assessmentTwin(item).riskLevel)).length
  const critical = fleet.filter((item) => assessmentTwin(item).riskLevel === 'CRITICAL').length
  const maintenanceDue = fleet.filter((item) => ['PROMPT_INSPECTION', 'REVIEW_OPERATING_WARNING', 'VERIFY_SENSORS'].includes(assessmentTwin(item).maintenancePriority)).length

  return (
    <div className="editorial-page overview-page">
      <section className="overview-hero light-section section-frame">
        <div className="hero-kicker-row">
          <span>(01) YOUR MONITORING SESSION</span>
          <span>MEASURE → COMPARE → INVESTIGATE</span>
        </div>
        <h1 className="display-title">EVERY WARNING<br />HAS A STORY.</h1>
        <div className="hero-bottom-grid">
          <p>
            VoltMind compares measured transformer behaviour with expected behaviour,
            then turns the deviation into condition, health, risk and maintenance context.
          </p>
          <div className="overview-counts">
            <div><span>TOTAL</span><strong>{fleet.length}</strong></div>
            <div><span>ONLINE</span><strong>{online}</strong></div>
            <div><span>ATTENTION</span><strong>{attention}</strong></div>
            <div><span>CRITICAL</span><strong>{critical}</strong></div>
            <div><span>MAINT. DUE</span><strong>{maintenanceDue}</strong></div>
          </div>
        </div>
      </section>

      <section className="demo-path capability-directory" aria-label="Explore existing VoltMind tools">
        <div className="directory-heading"><div><span className="section-kicker">THE TOOLS BEHIND THE WARNING</span><h2>Start with the signal.<br />Follow the evidence.</h2></div><p>Everything already in VoltMind, with a clear place to begin. Choose a tool to open its workspace.</p></div>
        <div className="demo-stops">{[
          ['live','01','Live thermal twin','Measured oil, expected behaviour and full-size historical graphs.','Monitoring'],
          ['alerts','02','Incident evidence','Follow each recorded episode back to its measurements.','Investigation'],
          ['faults','03','Falsification Twin','Review competing explanations, recurrence and recorded maintenance.','100 kVA'],
          ['dna','04','Thermal DNA','Inspect load-response episodes and healthy-reference requirements.','100 kVA'],
          ['lab','05','What-if & sensor checks','Compare a projected load reduction and inspect sensor explanations.','100 kVA'],
          ['reports','06','Reports & insights','Export processed readings, assessments and incident evidence.','Reporting'],
        ].map(([id,n,title,copy,scope]) => <button key={id} onClick={() => onNavigate(id)}><span className="tool-eyebrow">{n}<i>{scope}</i><b aria-hidden="true">↗</b></span><strong>{title}</strong><p>{copy}</p><small>{scope==='100 kVA' && fleet[0]?.asset.ratingKVA!==100 ? 'Select 100 kVA to use this tool' : id==='dna' ? (intelligence?.summary?.thermalDNA?.episodes?.length ? `${intelligence.summary.thermalDNA.episodes.length} response episode${intelligence.summary.thermalDNA.episodes.length===1 ? '' : 's'} · open evidence` : 'Reference readiness and response evidence') : 'Open workspace →'}</small></button>)}</div>
      </section>

      <section className="dark-section fleet-section section-frame">
        <div className="section-title-row dark">
          <span>(02)</span>
          <div>
            <p className="section-kicker">TRANSFORMER INDEX</p>
            <h2>ASSET STATE</h2>
          </div>
          <p>Selected session only. Health, risk and maintenance use the last published 24-row block; load remains a live reading.</p>
        </div>

        <div className="asset-index-list dark-list">
          {fleet.map((item, index) => (
            <button
              type="button"
              className="asset-index-row"
              key={item.asset.id}
              onClick={() => onOpenAsset(item.asset.id)}
            >
              <span className="asset-row-index">0{index + 1}.</span>
              <div className="asset-row-main">
                <strong>{item.asset.id}</strong>
                <small>{item.asset.ratingKVA} kVA / {item.asset.location}</small>
              </div>
              <div className="asset-row-stat">
                <span>TWO-HOUR MEAN HEALTH</span>
                <strong>{assessmentTwin(item).healthIndex ?? 'UNAVAILABLE'}</strong>
              </div>
              <div className="asset-row-stat">
                <span>LOAD</span>
                <strong>{item.telemetry.loadingPct?.toFixed(0) ?? 'UNAVAILABLE'}%</strong>
              </div>
              <div className="asset-row-stat risk-stat">
                <span>TWO-HOUR MEAN RISK</span>
                <StatusPill tone={riskTone(assessmentTwin(item).riskLevel)}>{assessmentTwin(item).riskLevel}</StatusPill>
              </div>
              <div className="asset-row-reveal">
                <span>{assessmentCondition(item)}</span>
                <span>{item.ml.dataConfidence} DATA</span>
                <span>{assessmentTwin(item).maintenancePriority}</span>
              </div>
              <span className="row-arrow">↘</span>
            </button>
          ))}
        </div>
      </section>

      <section className="light-section explanation-section section-frame">
        <div className="section-title-row">
          <span>(03)</span>
          <div>
            <p className="section-kicker">HOW VOLTMIND READS THE SYSTEM</p>
            <h2>FROM SCADA TO ACTION</h2>
          </div>
        </div>

        <div className="reasoning-flow">
          {[
            ['01', 'SCADA', 'Measured voltage, current, ambient and top-oil temperature.'],
            ['02', 'EXPECTED BEHAVIOUR', 'The runtime estimates what the transformer should be doing now.'],
            ['03', 'DEVIATION', 'Actual behaviour is compared with the expected operating response.'],
            ['04', 'CONDITION', 'Thermal, electrical and data-quality states remain separate and explicit.'],
            ['05', 'ACTION', 'Documented backend prototype health/risk and maintenance rules interpret the observed evidence.'],
          ].map(([index, title, body]) => (
            <div className="flow-row" key={index}>
              <span>{index}</span>
              <strong>{title}</strong>
              <p>{body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
