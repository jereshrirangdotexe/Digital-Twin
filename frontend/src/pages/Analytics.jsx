import { useState } from 'react'
import TelemetryChart from '../components/TelemetryChart'
import { selectedHistory } from '../services/api'
import { availableDays, readingsForDay } from '../services/presentation'

export default function Analytics({ history }) {
  const [metric, setMetric] = useState('temperature')
  const [range, setRange] = useState('Live')
  const [day, setDay] = useState('all')
  const days = availableDays(history)
  const selectedDay = days.includes(day) ? day : 'all'

  const visibleHistory = selectedDay === 'all' ? selectedHistory(history, range) : readingsForDay(history, selectedDay)

  return (
    <div className="editorial-page analytics-page">
      <section className="light-section section-frame analytics-hero">
        <div className="hero-kicker-row">
          <span>(01) ANALYTICS / TRENDS</span>
          <span>BUFFERED REPLAY HISTORY</span>
        </div>
        <h1 className="display-title">READ THE<br />BEHAVIOUR OVER TIME.</h1>
        <div className="range-index">
          {['Live', '15 min', '1 hour', '6 hours', '24 hours', '7 days', 'All history'].map((item, index) => (
            <button
              key={item}
              type="button"
              className={range === item ? 'active' : ''}
              onClick={() => { setRange(item); setDay('all') }}
            >
              <span>0{index + 1}</span>{item}
            </button>
          ))}
        </div>
        <div className="day-selector"><label>Or inspect a historical date · IST<select aria-label="Analytics historical date" value={selectedDay} onChange={e => setDay(e.target.value)}><option value="all">Use selected time range</option>{days.map(d => <option key={d} value={d}>{new Date(d+'T12:00:00+05:30').toLocaleDateString('en-IN',{timeZone:'Asia/Kolkata',day:'numeric',month:'long',year:'numeric'})}</option>)}</select></label><p>{selectedDay === 'all' ? `${range}: ${visibleHistory.length} processed readings.` : `${selectedDay}: ${visibleHistory.length} processed readings. This date overrides the time-range buttons for every graph below.`}</p></div>
      </section>

      <section className="dark-section section-frame">
        <div className="section-title-row dark">
          <span>(02)</span>
          <div>
            <p className="section-kicker">PRIMARY ANALYSIS</p>
            <h2>{selectedDay === 'all' ? range.toUpperCase() : selectedDay} / SELECTED METRIC</h2>
          </div>
        </div>
        <TelemetryChart key={`${selectedDay}-${range}`}
          history={visibleHistory}
          metric={metric}
          onMetricChange={setMetric}
          title="OPERATING TREND"
          variant="dark"
        />
      </section>

      <section className="light-section section-frame">
        <div className="section-title-row">
          <span>(03)</span>
          <div>
            <p className="section-kicker">DIGITAL TWIN INTERPRETATION</p>
            <h2>HEALTH / RISK / LOADING</h2>
          </div>
        </div>
        <div className="analytics-stack">
          <TelemetryChart key={`health-${selectedDay}-${range}`} history={visibleHistory} metric="health" title="HEALTH INDEX / RISK SCORE" allowSelector={false} />
          <TelemetryChart key={`loading-${selectedDay}-${range}`} history={visibleHistory} metric="loading" title="TRANSFORMER UTILIZATION" allowSelector={false} />
        </div>
      </section>

      <section className="dark-section section-frame">
        <div className="section-title-row dark">
          <span>(04)</span>
          <div>
            <p className="section-kicker">RAW ELECTRICAL CONTEXT</p>
            <h2>PHASE BEHAVIOUR</h2>
          </div>
        </div>
        <div className="analytics-stack">
          <TelemetryChart key={`voltage-${selectedDay}-${range}`} history={visibleHistory} metric="voltage" title="PHASE VOLTAGE" allowSelector={false} variant="dark" />
          <TelemetryChart key={`current-${selectedDay}-${range}`} history={visibleHistory} metric="current" title="PHASE CURRENT" allowSelector={false} variant="dark" />
        </div>
      </section>
    </div>
  )
}
