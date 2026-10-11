export function assessmentTwin(current) {
  return current?.assessment?.latest?.digitalTwin || {
    healthIndex: null, riskScore: null, healthBand: 'COLLECTING BLOCK', riskLevel: 'UNASSESSED',
    maintenancePriority: 'DATA_REQUIRED', maintenanceRecommendation: 'Wait for the first 24-row assessment block.',
    explanation: 'Live readings and alerts continue. The summary publishes automatically every 24 rows (two historical hours).',
    agingState: null, rulEstimate: null, formulaComponents: null,
    scoreScope: 'No published block yet. A score requires assessable model history.',
  }
}

export function assessmentCondition(current) {
  if (!current) return 'NO ASSESSMENT'
  return current?.assessment?.latest?.condition || 'COLLECTING BLOCK'
}

export function assessmentPoints(history) {
  return history.filter((r) => r.assessment?.publishedOnThisRow && r.assessment.latest)
}

export function dateLabel(value) {
  if (!value || Number.isNaN(new Date(value).getTime())) return 'Unavailable timestamp'
  return new Date(value).toLocaleString()
}
