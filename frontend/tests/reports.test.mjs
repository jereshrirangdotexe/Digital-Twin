import test from 'node:test'
import assert from 'node:assert/strict'
import { createReport, readingsCsv, reportHtml } from '../src/services/report.js'
import { assessmentTwin, assessmentCondition, assessmentPoints, dateLabel } from '../src/services/assessment.js'

function row(n, value, published=false) {
  return { timestamp:`2026-04-05T00:${n===1?'00':'05'}:00+05:30`, asset:{id:'R00'}, sessionId:'s',
    source:{filename:'<script>bad</script>'}, replay:{status:'PAUSED',processedRows:n,totalRows:4032},
    ml:{modelVersion:'frozen',calibrationStatus:'REFERENCE_CALIBRATION',assetCondition:'NORMAL',dataConfidence:'REDUCED'},
    telemetry:{topOilTempC:value,loadingPct:20},digitalTwin:{healthIndex:80,riskScore:20},
    assessment:{publishedOnThisRow:published,latest:published?{number:1,rows:24,assessableRows:24,coveragePct:100,
      condition:'NO_ALERT_OBSERVED',digitalTwin:{healthIndex:80,riskScore:20}}:null}}
}
test('report uses observed rows, excludes missing measurements and escapes source names',()=>{
  const history=[row(1,40),row(2,null,true)],report=createReport(history)
  const oil=report.trends.find((t)=>t.label==='Actual oil (C)')
  assert.equal(oil.validReadings,1);assert.equal(oil.minimum,40);assert.equal(oil.mean,40)
  assert.equal(report.retainedRows,2);assert.equal(report.assessments.length,1)
  const html=reportHtml(report);assert.ok(html.includes('&lt;script&gt;bad&lt;/script&gt;'))
  assert.ok(!html.includes('<script>bad</script>'));assert.ok(html.includes('Print / Save as PDF'))
})
test('CSV distinguishes raw readings and published summary and prevents formula injection',()=>{
  const r=row(1,40);r.asset.id='=DANGEROUS()'
  const csv=readingsCsv([r]);assert.ok(csv.includes("\"'=DANGEROUS()\""))
  assert.ok(csv.includes('"raw_health"'));assert.ok(csv.includes('"block_health"'))
  assert.throws(()=>createReport([]),/at least one/)
})
test('unpublished health is never substituted with fluctuating per-row score',()=>{
  assert.equal(assessmentCondition(null),'NO ASSESSMENT')
  const r=row(1,40);assert.equal(assessmentTwin(r).healthIndex,null)
  assert.equal(assessmentCondition(r),'COLLECTING BLOCK');assert.equal(assessmentPoints([r]).length,0)
  const published=row(2,41,true);assert.equal(assessmentTwin(published).healthIndex,80)
  assert.equal(assessmentPoints([r,published]).length,1)
  assert.equal(dateLabel(null),'Unavailable timestamp');assert.equal(dateLabel('bad'),'Unavailable timestamp')
})

test('250-kVA exports retain independent rating and model identity',()=>{
 const r=row(1,42,true);r.asset.ratingKVA=250;r.ml.modelVersion='VoltMind_250kVA_Prototype_ML_v1.0'
 const report=createReport([r]);assert.equal(report.ratingKVA,250);assert.ok(reportHtml(report).includes('250-kVA monitoring report'));assert.ok(readingsCsv([r]).includes('rating_kVA'));assert.equal(report.model.version,r.ml.modelVersion)
})

test('630-kVA report names native physics scope and added prototype indices',()=>{ const r=row(1,40,true);r.asset.ratingKVA=630;r.ml.modelVersion='VoltMind_630kVA_Prototype_ML_v1.0';const report=createReport([r]);assert.equal(report.ratingKVA,630);assert.ok(reportHtml(report).includes('630-kVA monitoring report'));assert.ok(report.limitations.some(s=>s.includes('PersistentPhysics'))); })
