export const readable = value => value ? String(value).replaceAll('_', ' ').toLowerCase() : 'Not available'

// Group by historical IST day, independently of the browser's timezone.
export function historicalDay(timestamp) {
  const epoch = Date.parse(timestamp)
  return Number.isFinite(epoch) ? new Date(epoch + 330*60000).toISOString().slice(0,10) : null
}

export function availableDays(history) {
  return [...new Set(history.map(r => historicalDay(r.timestamp)).filter(Boolean))].sort()
}

export function readingsForDay(history, day) {
  return day === 'all' ? history : history.filter(r => historicalDay(r.timestamp) === day)
}

export function recentLoading(history) {
  const rows = history.slice(-24)
  const loads = rows.map(r => r.telemetry.loadingPct).filter(v => v != null && Number.isFinite(Number(v))).map(Number)
  return { rows: rows.length, valid: loads.length, average: loads.length ? loads.reduce((a,b) => a+b,0)/loads.length : null, peak: loads.length ? Math.max(...loads) : null, first: rows[0]?.timestamp, last: rows.at(-1)?.timestamp }
}

export function thermalMeaning(ml) {
  if (ml.thermalAlert === true) return 'The detector sees excess heating. Check loading, cooling and the oil probe; the physical cause is not established.'
  if (ml.thermalAlert === false) return 'No thermal detector alert at this reading. This only covers the conditions this detector can assess.'
  return 'Thermal assessment is not ready. Check sensor availability, clean history and matching asset calibration before interpreting a result.'
}

export function electricalMeaning(flag, subject) {
  if (flag == null) return `Not assessed: the available measurements cannot establish ${subject}.`
  return flag ? `Warning: the ${subject} screen has triggered. Review the affected measurements.` : `No warning from the ${subject} screen at this reading. This is not a certificate that the transformer is fault-free.`
}

export function calibrationMeaning(status, rating) {
  if (!status || status.includes('MISSING') || status.includes('INVALID')) return 'The model needs a valid thermal reference matched to this asset. Affected predictions remain unassessed.'
  if (status.includes('REFERENCE') || status.includes('PROVISIONAL')) return 'A reference assumption is being used. It is not a verified calibration of this physical transformer; temperature differences may include model mismatch.'
  return `Calibration describes how this asset is expected to heat and cool. Local ${rating}-kVA data and commissioning are synthetic; input eligibility does not mean field certification.`
}
