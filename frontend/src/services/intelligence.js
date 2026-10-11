export const insightCategories = [
  ['overall', 'Overall dataset'], ['thermal', 'Thermal Digital Twin'], ['electrical', 'Electrical warnings'],
  ['data-quality', 'Sensors and data quality'], ['model', 'Model and calibration'],
  ['recurrence', 'Recurring faults and maintenance'], ['thermal-dna', 'Thermal DNA'], ['maintenance', 'Maintenance evidence'],
]
export const value = (v, unit = '', digits = 1) => v == null ? 'Unavailable' : typeof v === 'number' ? `${v.toFixed(digits)}${unit}` : String(v).replaceAll('_', ' ')
export function downloadFile(name, content, type = 'application/json') {
  const blob = new Blob([typeof content === 'string' ? content : JSON.stringify(content, null, 2)], { type })
  const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export const waveformData = (sample, rating, kind) => {
  const rms = ['R', 'Y', 'B'].map((p) => sample?.[`${kind}${p}`])
  const nominal = kind === 'voltage' ? 433 / Math.sqrt(3) : rating * 1000 / (Math.sqrt(3) * 433)
  const ideal = kind === 'voltage' ? nominal : rms.every((v) => Number.isFinite(v)) ? rms.reduce((a, b) => a + b, 0) / 3 : null
  return Array.from({ length: 121 }, (_, i) => {
    const ms = i / 3, angle = 2 * Math.PI * 50 * ms / 1000, point = { ms }
    ;['R', 'Y', 'B'].forEach((p, j) => {
      const factor = Math.SQRT2 * Math.sin(angle - j * 2 * Math.PI / 3)
      point[`ideal${p}`] = ideal == null ? null : ideal * factor
      point[`scada${p}`] = Number.isFinite(rms[j]) ? rms[j] * factor : null
      point[`reference${p}`] = nominal * factor
    })
    return point
  })
}
