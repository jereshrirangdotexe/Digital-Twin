import { assessmentTwin, assessmentCondition, dateLabel } from '../services/assessment'

export default function AssessmentSummary({ current }) {
  if (!current) return null
  const a = current.assessment, latest = a?.latest, twin = assessmentTwin(current)
  return <section className="assessment-summary" aria-label="Two-hour assessment">
    <div><span className="section-kicker">AUTOMATIC TWO-HOUR ASSESSMENT / 24 ROWS</span>
      <h2>{assessmentCondition(current).replaceAll('_', ' ')}</h2>
      <p>{!a ? 'Restart the Python ML server to enable two-hour assessments.' : latest ?
        `Last published block ${latest.number}: ${dateLabel(latest.firstTimestamp)} to ${dateLabel(latest.lastTimestamp)} · ${latest.rows} rows${latest.partial ? ' · final partial block' : ''}` : 'Collecting the first block. No summary has been published yet.'}</p>
      <p>{latest ? `${latest.assessableRows}/${latest.rows} rows assessable (${latest.coveragePct}%). ${latest.thermalAlertRows} thermal-alert rows; ${latest.electricalWarningRows} electrical-warning rows; ${latest.offlineRows} offline rows; ${latest.sensorSuspectRows} sensor-suspect rows.` : current?.asset.ratingKVA === 630 ? `The 630-kVA detector needs ${Math.ceil(current.ml.warmupRequiredMinutes)} clean historical minutes for this calibration; outages or invalid readings reset its warm-up.` : current?.asset.ratingKVA === 100 ? 'The final thermal detector requires at least 12 consecutive clean five-minute readings and valid asset calibration. Missing measurements interrupt readiness.' : 'The model needs more than 288 initial clean history rows before thermal assessment can become available.'}</p>
      {latest?.optionalAlertRows > 0 && <p><strong>{latest.optionalAlertRows} readings with an oil-depletion or terminal-heating indication in this block.</strong> These detectors are separate from the numeric thermal/electrical health score.</p>}
      <p>{current.replay.status === 'COMPLETE' ? 'Replay complete. This summary remains fixed until another replay starts.' : `Next block: ${a?.pendingRows ?? 0}/24 rows. Displayed summary stays fixed until that block is complete.`}</p>
    </div><div className="assessment-values"><div><span>BLOCK MEAN HEALTH</span><strong>{twin.healthIndex == null ? 'UNASSESSED' : `${twin.healthIndex}/100`}</strong></div>
      <div><span>BLOCK MEAN RISK</span><strong>{twin.riskScore == null ? 'UNASSESSED' : `${twin.riskScore}/100`}</strong></div>
      <p>{twin.maintenanceRecommendation}</p><p>{twin.suggestedReviewTiming}</p><small>Historical summary; live measurements and alerts below can change. Missing data is never counted as healthy.</small>
    </div>
  </section>
}
