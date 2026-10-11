import test from 'node:test'
import assert from 'node:assert/strict'
import { selectedHistory } from '../src/services/api.js'
const rows=Array.from({length:301},(_,i)=>({timestamp:new Date(Date.UTC(2026,0,1,0,i*5)).toISOString(),telemetry:{topOilTempC:null}}))
test('Time ranges select actual historical timestamps',()=>{
 assert.equal(selectedHistory(rows,'15 min').length,4)
 assert.equal(selectedHistory(rows,'1 hour').length,13)
 assert.equal(selectedHistory(rows,'24 hours').length,289)
 assert.equal(selectedHistory(rows,'Live').length,120)
})
test('Missing signals remain null and empty histories stay empty',()=>{
 assert.equal(selectedHistory(rows,'15 min')[0].telemetry.topOilTempC,null)
 assert.deepEqual(selectedHistory([],'24 hours'),[])
})
