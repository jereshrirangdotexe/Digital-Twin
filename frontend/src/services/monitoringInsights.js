export const formatTime = (timestamp) => new Date(timestamp).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }) + ' IST'
const number = (v, suffix = '', digits = 2) => Number.isFinite(v) ? v.toFixed(digits) + suffix : 'unavailable'

export function representativeTrend(rows, keys, buckets = 100) {
  if (rows.length <= 1000) return rows
  const selected = new Set([0, rows.length - 1]), size = Math.ceil(rows.length / buckets)
  for (let start = 0; start < rows.length; start += size) {
    const end = Math.min(rows.length, start + size)
    selected.add(start); selected.add(end - 1)
    for (const key of keys) {
      let low = null, high = null
      for (let i = start; i < end; i++) if (Number.isFinite(rows[i][key])) {
        if (low === null || rows[i][key] < rows[low][key]) low = i
        if (high === null || rows[i][key] > rows[high][key]) high = i
      }
      if (low !== null) selected.add(low)
      if (high !== null) selected.add(high)
    }
  }
  const state = row => JSON.stringify([row.raw?.ml?.thermalAlert,row.raw?.ml?.oilAlert,row.raw?.ml?.terminalAlert,row.raw?.ml?.assetCondition,row.raw?.ml?.electricalState])
  for (let i = 1; i < rows.length; i++) if (keys.some(k => Number.isFinite(rows[i][k]) !== Number.isFinite(rows[i - 1][k])) || state(rows[i]) !== state(rows[i-1])) { selected.add(i-1); selected.add(i) }
  return [...selected].sort((a,b) => a-b).map(i => rows[i])
}

// Display-only interpolation, bounded by genuine observations and native cadence.
// These values never enter inference, reports, evidence or measured-value tooltips.
export function temperatureDisplay(rows, enabled = true) {
  const data = rows.map(r => ({ ...r, actualBridge: null, expectedBridge: null }))
  const gaps = []
  for (const [key, bridge, label] of [['actualOil','actualBridge','Actual oil'], ['expectedOil','expectedBridge','Expected oil']]) {
    for (let i = 0; i < data.length; i++) {
      if (Number.isFinite(data[i][key])) continue
      const start = i
      while (i + 1 < data.length && !Number.isFinite(data[i + 1][key])) i++
      const end = i, left = data[start - 1], right = data[end + 1]
      const short = end - start + 1 <= 3 && left && right && right.epoch - left.epoch === (end - start + 2) * 300000
      gaps.push({ key, label, start, end, count: end - start + 1, short: Boolean(short), from: data[start].timestamp, to: data[end].timestamp, x1: left?.epoch ?? data[start].epoch, x2: right?.epoch ?? data[end].epoch })
      if (short && enabled) {
        data[start - 1][bridge] = left[key]; data[end + 1][bridge] = right[key]
        for (let j = start; j <= end; j++) data[j][bridge] = left[key] + (right[key] - left[key]) * (data[j].epoch - left.epoch) / (right.epoch - left.epoch)
      }
    }
  }
  return { data, gaps }
}

export function readingExplanation(row) {
  const actual = row?.telemetry?.topOilTempC, expected = row?.ml?.expectedOilTempC
  if (!Number.isFinite(actual)) return 'The oil sensor reading is unavailable at this time. A dashed bridge, if shown, is only a visual estimate.'
  if (!Number.isFinite(expected)) return `Measured oil is ${number(actual, ' °C')}. Expected oil is unavailable: ${row?.ml?.warmupStatus === 'WARMING_UP' ? 'the model is collecting clean history' : 'required measurements or calibration are unavailable'}.`
  const difference = actual - expected
  return `Measured oil is ${number(actual, ' °C')}; expected oil is ${number(expected, ' °C')}. Oil is ${number(Math.abs(difference), ' °C')} ${difference >= 0 ? 'above' : 'below'} expectation at ${number(row.telemetry.loadingPct, '%')} loading and ${number(row.telemetry.ambientTempC, ' °C')} ambient. ${row.ml.thermalAlert === true ? 'The locked thermal detector is alerting.' : row.quality?.thermalAssessable ? 'No thermal detector alert on this reading.' : 'Thermal detection is not assessable on this reading.'}`
}

// Answers use recorded backend summaries only; unsupported questions never invent facts.
export function answerMonitoring(question, summary, current) {
  if (!summary) return { category: 'overall', text: 'Start monitoring with RUN ON LOCAL DATA or upload your dataset. I can answer once processed readings are available.' }
  const s = summary.statistics, counts = s.incidentCounts || {}
  const scope = `${s.processedRows.toLocaleString()} of ${s.totalRows.toLocaleString()} readings processed${s.complete ? ' (complete replay)' : ' (replay still in progress)'}.`
  let category = 'overall', text
  if (/short.?circuit|pressure|impedance|internal.?bushing|remaining.?life|\brul\b/i.test(question)) text = 'Those conditions are not measured or diagnosed by the supplied model. Terminal surface heating is not an internal bushing diagnosis, and oil depletion is not confirmed leakage.'
  else if (/gap|missing|no data|sensor|quality|offline|communication/i.test(question)) {
    category = 'data-quality'; text = `${s.communicationOutageRows} communication-outage readings; ${s.sensorSuspectRows} sensor-suspect readings; ${s.processedRows - s.assessableRows} thermal readings unassessed (including warm-up or missing calibration). Graph gaps mark unavailable values. Short dashed bridges are display estimates only.`
  } else if (/maintenance|repair|recommend|what.*do|action/i.test(question)) {
    category = 'maintenance'; text = `${(summary.recommendations || []).join(' ')} ${summary.maintenance?.length || 0} recorded maintenance actions. ${summary.latestSimulation?.recommendation || 'Run a load-reduction scenario in Intelligence Lab for a hypothetical projection.'}`
  } else if (/dna|fingerprint|heat.*cool/i.test(question)) {
    category = 'thermal-dna'; text = `${summary.thermalDNA?.message || 'No established healthy reference.'} ${summary.thermalDNA?.episodes?.length || 0} suitable response episodes found.`
  } else if (/recurr|repeat/i.test(question)) {
    category = 'recurrence'; text = summary.recurrence?.explanation || 'Insufficient separate incidents to establish recurrence.'
  } else if (/model|calibrat|accuracy|threshold/i.test(question)) {
    category = 'model'; text = `${summary.model?.modelVersion}; threshold ${number(summary.model?.decisionThreshold)}. ${summary.model?.scoreDefinition || ''} Calibration: ${summary.model?.calibrationStatus}. Unseen judges’ accuracy is not verified.`
  } else if (/electri|voltage|current|load|overload/i.test(question)) {
    category = 'electrical'; text = `${s.electricalWarningRows} electrical-warning readings; ${counts.ELECTRICAL || 0} distinct incidents. Peak apparent-power loading: ${number(s.maximumApparentLoadingPct, '%')}. Warnings describe observed stress, not confirmed damage.`
  } else if (/temperature|oil|thermal|hot|expected|difference/i.test(question)) {
    category = 'thermal'; text = `${current ? readingExplanation(current) : ''} Across processed history: maximum oil ${number(s.highestOilC, ' °C')}; largest actual-minus-expected difference ${number(s.maximumResidualC, ' °C')}; ${s.thermalAlertRows} thermal-alert readings; ${counts.THERMAL || 0} thermal, ${counts.OIL || 0} oil-depletion and ${counts.TERMINAL || 0} terminal-heating incidents. Causes require verification.`
  } else if (/health|risk|normal|unstable|safe/i.test(question)) {
    const block = current?.assessment?.latest
    text = block ? `Last published two-hour block: ${String(block.condition).replaceAll('_',' ')}. Health ${number(block.digitalTwin?.healthIndex, '/100', 1)}; risk ${number(block.digitalTwin?.riskScore, '/100', 1)}; ${block.assessableRows}/${block.rows} readings assessable. Updates after each 24 rows; alarms remain immediate.` : 'No complete two-hour assessment is available yet. Health and risk remain unavailable until an assessable block is published.'
  } else if (/summary|overall|happen|caught|fault|alert|incident|detect/i.test(question)) {
    text = `${Object.entries(counts).map(([k,n]) => `${k.toLowerCase()}: ${n}`).join('; ') || 'No saved incidents'}. ${s.thermalAlertRows} thermal-alert readings, ${s.electricalWarningRows} electrical-warning readings. ${s.assessableRows}/${s.processedRows} thermal readings assessable. ${summary.incidents?.length ? 'Open a recorded incident below to inspect its evidence.' : 'No incident has been recorded in processed history; this does not establish that all possible faults are absent.'}`
  } else text = 'I can answer questions about recorded alerts, oil temperature, graph gaps, loading, health, calibration, maintenance, recurrence and Thermal DNA. Try “What faults were detected?” or choose a summary below.'
  return { category, text: `${scope}\n${text}`, timestamp: current?.timestamp || s.monitoringEnd }
}
