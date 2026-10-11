import test from 'node:test'
import assert from 'node:assert/strict'
import { historicalDay, availableDays, readingsForDay, recentLoading, electricalMeaning } from '../src/services/presentation.js'

test('historical day selection respects IST midnight and preserves source readings', () => {
  const rows = ['2026-01-01T18:29:59Z', '2026-01-01T18:30:00Z', 'invalid'].map(timestamp => ({ timestamp }))
  assert.equal(historicalDay(rows[0].timestamp), '2026-01-01')
  assert.equal(historicalDay(rows[1].timestamp), '2026-01-02')
  assert.equal(historicalDay('invalid'), null)
  assert.deepEqual(availableDays(rows), ['2026-01-01', '2026-01-02'])
  assert.deepEqual(readingsForDay(rows, '2026-01-02'), [rows[1]])
  assert.equal(readingsForDay(rows, 'all'), rows)
  assert.deepEqual(readingsForDay(rows, '2026-01-03'), [])
  assert.equal(rows.length, 3)
})

test('recent utilization uses only last 24 rows and excludes missing values', () => {
  const rows = Array.from({length: 25}, (_, i) => ({timestamp: String(i), telemetry:{loadingPct: i === 0 ? 999 : i === 1 ? null : 50}}))
  const result = recentLoading(rows)
  assert.equal(result.rows, 24)
  assert.equal(result.valid, 23)
  assert.equal(result.average, 50)
  assert.equal(result.peak, 50)
  assert.equal(recentLoading([]).average, null)
})

test('unassessed electrical conditions never become no-warning results', () => {
  assert.match(electricalMeaning(null, 'voltage'), /Not assessed/)
  assert.match(electricalMeaning(false, 'voltage'), /No warning/)
  assert.match(electricalMeaning(true, 'voltage'), /Warning:/)
})
