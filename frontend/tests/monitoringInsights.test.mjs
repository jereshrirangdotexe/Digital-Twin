import test from 'node:test'
import assert from 'node:assert/strict'
import { temperatureDisplay, readingExplanation, answerMonitoring, formatTime, representativeTrend } from '../src/services/monitoringInsights.js'

const points = values => values.map((v,i) => ({ timestamp: new Date(i*300000).toISOString(), epoch:i*300000, actualOil:v, expectedOil:40 }))
test('short graph gaps get separate display bridges without altering measurements', () => {
  const input=points([40,null,null,46]), original=structuredClone(input)
  const {data,gaps}=temperatureDisplay(input)
  assert.deepEqual(input,original); assert.equal(data[1].actualOil,null)
  assert.deepEqual(data.map(r=>r.actualBridge),[40,42,44,46]); assert.equal(gaps[0].short,true)
})
test('long gaps, trailing gaps and non-native cadence cannot be filled', () => {
  for (const input of [points([40,null,null,null,null,46]),points([40,null]),points([null,40])]) assert(temperatureDisplay(input).data.every(r=>r.actualBridge===null))
  const input=points([40,null,46]); input[2].epoch+=300000
  assert(temperatureDisplay(input).data.every(r=>r.actualBridge===null))
})
test('visual gap bridges can be disabled', () => assert(temperatureDisplay(points([40,null,46]),false).data.every(r=>r.actualBridge===null)))
test('expected gaps and actual gaps remain independently traceable', () => {
  const input=points([40,41,42]);input[1].expectedOil=null
  const out=temperatureDisplay(input)
  assert.equal(out.gaps[0].key,'expectedOil');assert.equal(out.data[1].expectedOil,null);assert.equal(out.data[1].expectedBridge,40)
})
test('point explanation uses the selected point and preserves small differences', () => {
  const row={telemetry:{topOilTempC:40.92,loadingPct:47,ambientTempC:31.5},ml:{expectedOilTempC:41.08,thermalAlert:false},quality:{thermalAssessable:true}}
  assert.match(readingExplanation(row),/0.16 °C below/)
  row.telemetry.topOilTempC=46.3;assert.match(readingExplanation(row),/5.22 °C above/)
  row.telemetry.topOilTempC=null;assert.match(readingExplanation(row),/unavailable/)
})
const summary={statistics:{processedRows:100,totalRows:4032,complete:false,incidentCounts:{THERMAL:2,OIL:1,TERMINAL:0},thermalAlertRows:6,electricalWarningRows:0,assessableRows:80,communicationOutageRows:3,sensorSuspectRows:2,highestOilC:62,maximumResidualC:5.2},incidents:[{id:'recorded'}]}
test('assistant answers detected faults using real counts and processed scope',()=>{
  const reply=answerMonitoring('What faults were detected?',summary)
  assert.match(reply.text,/100 of 4,032/);assert.match(reply.text,/thermal: 2/);assert.match(reply.text,/oil: 1/);assert.match(reply.text,/80\/100/)
})
test('assistant distinguishes missing data, unsupported faults and no session',()=>{
  assert.equal(answerMonitoring('why gaps?',summary).category,'data-quality')
  assert.match(answerMonitoring('short circuit?',summary).text,/not measured or diagnosed/)
  assert.match(answerMonitoring('summary',null).text,/Start monitoring/)
  assert.match(answerMonitoring('tell me a joke',summary).text,/I can answer questions/)
})
test('historical time uses explicit IST independent of workstation timezone',()=> assert.match(formatTime('2026-01-01T00:00:00Z'),/05:30 IST/))
test('dense display preserves extremes, missing intervals and alert transitions',()=>{
  const rows=points(Array(4032).fill(40));rows[1555].actualOil=100;rows[1700].actualOil=null;rows[2300].raw={ml:{thermalAlert:true}}
  const display=representativeTrend(rows,['actualOil'])
  assert(display.length<1000);assert(display.includes(rows[0]));assert(display.includes(rows.at(-1)))
  for(const i of [1555,1699,1700,1701,2299,2300,2301]) assert(display.includes(rows[i]))
  assert.equal(rows.length,4032)
})
