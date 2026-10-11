import { assessmentPoints } from './assessment.js'

const measurements = {
  loadingPct: 'Loading (%)', topOilTempC: 'Actual oil (C)', ambientTempC: 'Ambient (C)',
  voltageR: 'R voltage (V)', voltageY: 'Y voltage (V)', voltageB: 'B voltage (V)',
  currentR: 'R current (A)', currentY: 'Y current (A)', currentB: 'B current (A)',
}

export function createReport(history, alerts = []) {
  const current = history.at(-1)
  if (!current) throw new Error('Process at least one reading before exporting a report.')
  const trends = Object.entries(measurements).map(([key, label]) => {
    const values = history.map((r) => r.telemetry[key]).filter((v) => Number.isFinite(v))
    return { label, validReadings: values.length, minimum: values.length ? Math.min(...values) : null,
      maximum: values.length ? Math.max(...values) : null,
      mean: values.length ? values.reduce((s, v) => s + v, 0) / values.length : null,
      first: values[0] ?? null, last: values.at(-1) ?? null }
  })
  return { application: 'VoltMind', generatedAt: new Date().toISOString(), asset: current.asset.id, ratingKVA: current.asset.ratingKVA,
    source: current.source, sessionId: current.sessionId, replay: current.replay,
    scope: 'Retained browser readings for this session; not future data or an entire fleet.',
    retainedRows: history.length, firstTimestamp: history[0].timestamp, lastTimestamp: current.timestamp,
    model: { version: current.ml.modelVersion, calibration: current.ml.calibrationStatus },
    latestAssessment: current.assessment?.latest ?? null,
    assessmentPolicy: 'Nonoverlapping 24-row blocks = two hours at five-minute sampling. Final short block explicitly partial.',
    assessments: assessmentPoints(history).map((r) => r.assessment.latest),
    trends, alerts,
    limitations: ['Synthetic benchmark model; unseen organizer and field accuracy unestablished.',
      'Block health is the mean of assessable prototype scores. Missing readings excluded with coverage reported.',
      'Worst observed maintenance priority is retained within each block; live alerts are not delayed.',
      'Condition guidance is not a prediction of failure date. Aging and remaining useful life unavailable.',
      'Browser/backend history retention is limited to 10,000 rows. Stream gaps can limit this export.',
      ...(current.asset.ratingKVA === 630 ? ['630-kVA source detector is PersistentPhysics. Health/risk are added prototype dashboard indices; the source detector provides no validated health, risk or RUL index.'] : [])], }
}

const csvCell = (value) => {
  let text = value == null ? '' : String(value)
  if (/^[=+@\-\t\r]/.test(text) && typeof value !== 'number') text = `'${text}`
  return `"${text.replaceAll('"', '""')}"`
}

export function readingsCsv(history) {
  const headers = ['timestamp', 'asset', 'rating_kVA', 'row', 'loading_pct', 'actual_oil_C', 'expected_oil_C', 'residual_C',
    'ambient_C', 'VR_V', 'VY_V', 'VB_V', 'IR_A', 'IY_A', 'IB_A', 'communication', 'live_condition',
    'confidence', 'thermal_alert', 'raw_health', 'raw_risk', 'block_published', 'block_health', 'block_risk', 'block_condition']
  const records = history.map((r) => [r.timestamp, r.asset.id, r.asset.ratingKVA, r.replay.processedRows, r.telemetry.loadingPct,
    r.telemetry.topOilTempC, r.ml.expectedOilTempC, r.ml.thermalResidualC, r.telemetry.ambientTempC,
    r.telemetry.voltageR, r.telemetry.voltageY, r.telemetry.voltageB, r.telemetry.currentR,
    r.telemetry.currentY, r.telemetry.currentB, r.telemetry.communicationAvailable, r.ml.assetCondition,
    r.ml.dataConfidence, r.ml.thermalAlert, r.digitalTwin.healthIndex, r.digitalTwin.riskScore,
    r.assessment?.publishedOnThisRow ?? false, r.assessment?.latest?.digitalTwin.healthIndex,
    r.assessment?.latest?.digitalTwin.riskScore, r.assessment?.latest?.condition])
  return '\uFEFF' + [headers, ...records].map((row) => row.map(csvCell).join(',')).join('\r\n')
}

const escape = (value) => String(value ?? 'Unavailable').replace(/[&<>"']/g, (c) => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]))
const number = (v) => v == null ? 'Unavailable' : Number(v).toFixed(2)

export function reportHtml(report) {
  const a = report.latestAssessment
  return `<!doctype html><html lang="en"><meta charset="utf-8"><title>VoltMind monitoring report</title>
  <style>body{font:16px Arial,sans-serif;margin:40px;color:#171717;max-width:1100px}h1{font-size:36px}h2{margin-top:32px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid #ccc;padding:9px;text-align:left}p,li{line-height:1.6}button{padding:10px}@media print{button{display:none}body{margin:0}tr{break-inside:avoid}}</style>
  <h1>VoltMind / ${escape(report.ratingKVA)}-kVA monitoring report</h1><button onclick="window.print()">Print / Save as PDF</button>
  <p>Asset ${escape(report.asset)} · ${escape(report.replay.status)} · ${report.retainedRows} retained rows<br>
  Historical period ${escape(report.firstTimestamp)} to ${escape(report.lastTimestamp)}<br>
  Source ${escape(report.source.filename)} · Generated ${escape(report.generatedAt)}</p>
  <p>${escape(report.scope)} Processed ${report.replay.processedRows}/${report.replay.totalRows} rows.</p>
  <h2>Last published two-hour assessment</h2>
  ${a ? `<p>${escape(a.condition)} · Mean health ${number(a.digitalTwin.healthIndex)}/100 · Mean risk ${number(a.digitalTwin.riskScore)}/100<br>
  ${escape(a.firstTimestamp)} to ${escape(a.lastTimestamp)} · ${a.assessableRows}/${a.rows} assessable rows · ${a.coveragePct}% coverage${a.partial ? ' · final partial block' : ''}</p>
  <p>${escape(a.digitalTwin.maintenanceRecommendation)}</p><p>${escape(a.digitalTwin.suggestedReviewTiming)}</p><p>${escape(a.digitalTwin.explanation)}</p>` : '<p>No block published yet.</p>'}
  <h2>Measured performance trends</h2><table><thead><tr><th>Measurement</th><th>Valid rows</th><th>Minimum</th><th>Mean</th><th>Maximum</th><th>First valid</th><th>Last valid</th></tr></thead><tbody>
  ${report.trends.map((t) => `<tr><td>${escape(t.label)}</td><td>${t.validReadings}</td><td>${number(t.minimum)}</td><td>${number(t.mean)}</td><td>${number(t.maximum)}</td><td>${number(t.first)}</td><td>${number(t.last)}</td></tr>`).join('')}</tbody></table>
  <h2>Published assessment history</h2><table><thead><tr><th>End time</th><th>Rows / usable</th><th>Mean health</th><th>Mean risk</th><th>Condition</th><th>Maintenance</th></tr></thead><tbody>
  ${report.assessments.map((b) => `<tr><td>${escape(b.lastTimestamp)}${b.partial ? ' (partial)' : ''}</td><td>${b.rows} / ${b.assessableRows}</td><td>${number(b.digitalTwin.healthIndex)}</td><td>${number(b.digitalTwin.riskScore)}</td><td>${escape(b.condition)}</td><td>${escape(b.digitalTwin.maintenancePriority)}</td></tr>`).join('')}</tbody></table>
  <h2>Alert history (${report.alerts.length})</h2><table><thead><tr><th>Time</th><th>Category</th><th>Status</th><th>Evidence</th></tr></thead><tbody>
  ${report.alerts.map((a) => `<tr><td>${escape(a.timestamp)}</td><td>${escape(a.category)}</td><td>${escape(a.status)}</td><td>${escape(a.explanation)}</td></tr>`).join('')}</tbody></table>
  <h2>Method and limitations</h2><p>${escape(report.assessmentPolicy)} Model ${escape(report.model.version)}; calibration ${escape(report.model.calibration)}.</p>
  <ul>${report.limitations.map((l) => `<li>${escape(l)}</li>`).join('')}</ul></html>`
}

export function download(content, filename, type) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const link = document.createElement('a'); link.href = url; link.download = filename; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
