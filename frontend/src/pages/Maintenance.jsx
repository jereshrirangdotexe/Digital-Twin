import { assessmentTwin } from '../services/assessment'

export default function Maintenance({ current, history }) {
  if (!current) return <div className="empty-state">No current asset state.</div>

  const { ml, telemetry, asset } = current
  const digitalTwin = assessmentTwin(current)
  const recentResiduals = history
    .slice(-24)
    .map((item) => item.ml.thermalResidualC)
    .filter((value) => value != null)
  const maxResidual = recentResiduals.length ? Math.max(...recentResiduals) : null

  return (
    <div className="editorial-page maintenance-page">
      <section className="dark-section section-frame maintenance-hero">
        <div className="hero-kicker-row dark">
          <span>(01) PREDICTIVE MAINTENANCE</span>
          <span>{asset.id} / LAST PUBLISHED TWO-HOUR GUIDANCE</span>
        </div>
        <div className="maintenance-hero-grid">
          <div>
            <span className="section-kicker">PUBLISHED BLOCK PRIORITY</span>
            <h1 className="priority-display-large">{digitalTwin.maintenancePriority}</h1>
          </div>
          <div className="maintenance-headline">
            <h2>{digitalTwin.maintenanceRecommendation}</h2>
            <p>{digitalTwin.explanation}</p>
            <p>{digitalTwin.suggestedReviewTiming}</p>
          </div>
        </div>
      </section>

      <section className="light-section section-frame">
        <div className="section-title-row">
          <span>(02)</span>
          <div>
            <p className="section-kicker">SUPPORTING EVIDENCE</p>
            <h2>WHY THIS PRIORITY?</h2>
          </div>
          <p>The recommendation retains the highest-priority evidence in the published block. Supporting live readings below continue to update independently.</p>
        </div>

        <div className="evidence-index">
          {[
            ['01', 'THERMAL STATE', ml.thermalState, `Residual ${ml.thermalResidualC?.toFixed(1) ?? 'UNAVAILABLE'} °C`],
            ['02', 'ELECTRICAL STATE', ml.electricalState, `Loading ${telemetry.loadingPct?.toFixed(1) ?? 'UNAVAILABLE'}%`],
            ['03', 'RISK', digitalTwin.riskLevel, `Score ${digitalTwin.riskScore ?? 'UNAVAILABLE'}`],
            ['04', 'RECENT MAX DEVIATION', maxResidual == null ? 'UNAVAILABLE' : `${maxResidual.toFixed(1)} °C`, 'Replay buffer'],
            ['05', 'DATA CONFIDENCE', ml.dataConfidence, ml.warmupStatus],
          ].map(([index, label, value, note]) => (
            <div className="evidence-row" key={index}>
              <span>{index}</span>
              <strong>{label}</strong>
              <b>{value}</b>
              <small>{note}</small>
            </div>
          ))}
        </div>
      </section>

      <section className="dark-section section-frame">
        <div className="section-title-row dark">
          <span>(03)</span>
          <div>
            <p className="section-kicker">AGING / RUL</p>
            <h2>{digitalTwin.agingState || 'AGING ASSESSMENT UNAVAILABLE'}</h2>
          </div>
        </div>

        <div className="rul-row">
          <div>
            <span>RUL ESTIMATE</span>
            <strong>NOT AVAILABLE</strong>
          </div>
          <p>
            VoltMind will not claim an exact remaining life unless the backend/model actually supports it.
            The supplied model does not provide validated insulation aging or remaining useful life.
          </p>
        </div>
      </section>

      <section className="light-section section-frame">
        <div className="section-title-row">
          <span>(04)</span>
          <div>
            <p className="section-kicker">ENGINEERING DETAILS</p>
            <h2>OPEN WHEN NEEDED</h2>
          </div>
        </div>
        <div className="detail-accordions">
          <details>
            <summary><span>01</span><strong>THERMAL REASONING</strong><em>OPEN +</em></summary>
            <p>{digitalTwin.explanation}</p>
          </details>
          <details>
            <summary><span>02</span><strong>MODEL STATUS</strong><em>{ml.modelStatus}</em></summary>
            <div className="details-grid">
              <div><span>Model</span><strong>{ml.modelVersion}</strong></div>
              <div><span>Warm-up</span><strong>{ml.warmupStatus}</strong></div>
              <div><span>Calibration</span><strong>{ml.calibrationStatus}</strong></div>
              <div><span>Confidence</span><strong>{ml.dataConfidence}</strong></div>
            </div>
          </details>
        </div>
      </section>
    </div>
  )
}
