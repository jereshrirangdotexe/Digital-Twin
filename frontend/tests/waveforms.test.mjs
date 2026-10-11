import test from 'node:test'
import assert from 'node:assert/strict'
import {waveformData} from '../src/services/intelligence.js'

test('50 Hz reconstruction preserves RMS magnitudes, period and balanced phase sum',()=>{
  const sample={voltageR:240,voltageY:250,voltageB:260,currentR:40,currentY:50,currentB:60}
  for(const kind of ['voltage','current']) {
    const wave=waveformData(sample,100,kind)
    for(const p of ['R','Y','B']) {
      assert.ok(Math.abs(wave[15]['scada'+p]-wave[75]['scada'+p])<1e-10)
      const rms=Math.sqrt(wave.slice(0,60).reduce((s,r)=>s+r['scada'+p]**2,0)/60)
      assert.ok(Math.abs(rms-sample[kind+p])<1e-10)
    }
    for(const r of wave) assert.ok(Math.abs(r.idealR+r.idealY+r.idealB)<1e-10)
  }
})
test('missing SCADA magnitudes remain unavailable while nominal reference is explicit',()=>{
  const voltage=waveformData({},100,'voltage'),current=waveformData({currentR:40},250,'current')
  assert.equal(voltage[15].scadaR,null)
  assert.equal(current[15].scadaY,null)
  assert.equal(current[15].idealR,null)
  assert.ok(Math.abs(current[15].referenceR-250000/(Math.sqrt(3)*433)*Math.SQRT2)<1e-10)
})
