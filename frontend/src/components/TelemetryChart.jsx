import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ReferenceLine,
  ReferenceArea,
} from 'recharts'
import { useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { waveformData, value } from '../services/intelligence'
import { formatTime, temperatureDisplay, readingExplanation, representativeTrend } from '../services/monitoringInsights'
import { Evidence } from './Insights'

import { assessmentPoints } from '../services/assessment'

const metricConfig = {
  temperature: [
    ['actualOil', 'Actual oil'],
    ['expectedOil', 'Expected oil'],
  ],
  residual: [['residual', 'Thermal residual']],
  loading: [['loading', 'Loading']],
  voltage: [
    ['voltageR', 'R voltage'],
    ['voltageY', 'Y voltage'],
    ['voltageB', 'B voltage'],
  ],
  current: [
    ['currentR', 'R current'],
    ['currentY', 'Y current'],
    ['currentB', 'B current'],
  ],
  health: [
    ['health', 'Health index'],
    ['risk', 'Risk score'],
  ],
  thermalScore: [['thermalScore', 'Thermal score']],
  ambient: [['ambient', 'Ambient temperature']],
  risk: [['risk', 'Prototype risk']],
}

function chartRows(history) {
  // Keep every retained observation: sampling could hide spikes or bridge missing readings.
  const display = history
  return display.map((row) => ({
    time: new Date(row.timestamp).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }),
    actualOil: row.telemetry.topOilTempC,
    ambient: row.telemetry.ambientTempC,
    expectedOil: row.ml.expectedOilTempC,
    residual: row.ml.thermalResidualC,
    loading: row.telemetry.loadingPct,
    voltageR: row.telemetry.voltageR,
    voltageY: row.telemetry.voltageY,
    voltageB: row.telemetry.voltageB,
    currentR: row.telemetry.currentR,
    currentY: row.telemetry.currentY,
    currentB: row.telemetry.currentB,
    health: row.assessment?.latest?.digitalTwin.healthIndex,
    risk: row.assessment?.latest?.digitalTwin.riskScore,
    thermalScore: row.ml.thermalScore,
    explanation: row.explanation,
    threshold: row.ml.decisionThreshold,
    timestamp: row.timestamp,
    epoch: Date.parse(row.timestamp),
    rating: row.asset.ratingKVA,
    raw: row,
  }))
}

const descriptions = {
  temperature: 'Measured oil temperature compared with the commissioned thermal expectation. A persistent gap needs investigation; it does not identify a failed component.',
  residual: 'Thermal residual = actual oil minus expected oil temperature (°C). Positive means hotter than expected. Persistence, calibration and sensor quality matter.',
  loading: 'Apparent-power loading uses measured phase voltages and currents relative to the transformer kVA rating. Maximum-phase current loading is a separate engineering warning.',
  voltage: 'Historical phase-to-neutral RMS voltage in volts. The cycle illustration uses assumed sinusoidal shape and phase angles.',
  current: 'Historical phase RMS current in amperes. The cycle illustration cannot reveal harmonics or power factor.',
  thermalScore: '100 kVA: uncalibrated Logistic Regression detector score; the marked threshold and persistence determine the alert. Other ratings keep their native score conventions. This is not failure probability.',
  ambient: 'Ambient temperature is the surrounding air temperature. Warmer air can increase oil temperature even at similar electrical loading.',
  health: 'Health and risk average assessable prototype observation indices in each published 24-row block. Missing rows are excluded, not considered healthy.',
  risk: 'A prototype index combining observed thermal, loading and electrical stress with calibration uncertainty. This is not predicted failure probability.',
}
function ExplainTooltip({ active, payload, label, metric }) {
  if (!active || !payload?.length) return null
  const point = payload[0].payload, explanation = point.explanation
  return createPortal(<div className="explain-tooltip floating-reading" role="status"><span className="section-kicker">READING AT POINTER</span><strong>{formatTime(point.timestamp)}</strong>{payload.filter(p => !p.dataKey.endsWith('Bridge')).map((p) => <p key={p.dataKey}><span>{p.name}</span><b>{value(p.value, ['temperature','residual','ambient'].includes(metric) ? ' °C' : metric === 'loading' ? '%' : metric === 'voltage' ? ' V' : metric === 'current' ? ' A' : '', 2)}</b></p>)}
    {metric === 'temperature' && <><p>Difference: <b>{value(point.residual, ' °C', 2)}</b></p><p className="reading-explanation">{readingExplanation(point.raw)}</p><small>{value(point.raw?.ml.dataConfidence)} · {value(point.raw?.ml.warmupStatus)}. Click to select this reading below.</small></>}
    {metric !== 'temperature' && <small>{descriptions[metric]}</small>}</div>, document.body)
}

export default function TelemetryChart({
  history,
  metric = 'temperature',
  onMetricChange,
  title = 'Live telemetry',
  allowSelector = true,
  variant = 'light',
  caption,
  compact = false,
}) {
  const [cycle, setCycle] = useState(false)
  const [inspected, setInspected] = useState(null)
  const [reviewTimestamp, setReviewTimestamp] = useState(null)
  const [bridgeGaps, setBridgeGaps] = useState(true)
  const [groups, setGroups] = useState({ voltage: { ideal: true, scada: true, reference: false }, current: { ideal: true, scada: true, reference: false } })
  const blockMetric = ['health', 'risk'].includes(metric)
  const plotHistory = blockMetric ? assessmentPoints(history) : history
  const mapped = useMemo(() => chartRows(plotHistory), [plotHistory])
  const display = useMemo(() => temperatureDisplay(mapped, bridgeGaps && metric === 'temperature'), [mapped, bridgeGaps, metric])
  const data = useMemo(() => representativeTrend(display.data, metric === 'temperature' ? ['actualOil','expectedOil','residual','actualBridge','expectedBridge'] : (metricConfig[metric] ?? metricConfig.temperature).map(([k])=>k)), [display.data,metric])
  const timeTicks = data.length > 1 ? Array.from({length:5}, (_,i) => data[Math.round(i*(data.length-1)/4)].epoch) : undefined
  const reviewed = plotHistory.find(r => r.timestamp === reviewTimestamp) || plotHistory.at(-1)
  const reviewIndex = Math.max(0, plotHistory.indexOf(reviewed))
  const series = metricConfig[metric] ?? metricConfig.temperature
  const dark = variant === 'dark' || metric === 'temperature'
  const axis = dark ? '#b5b3ab' : '#6a6965'
  const grid = dark ? '#2b2b29' : '#c9c7c0'
  const seriesColors = dark
    ? ['#ebe9e4', '#ff916b', '#a6a39b']
    : ['#111111', '#d86a30', '#777771']
  const electrical = ['voltage','current'].includes(metric)
  const last = history.at(-1)
  const wave = electrical && cycle ? waveformData(last?.telemetry, last?.asset.ratingKVA || 100, metric) : []

  return (
    <figure className={`telemetry-figure telemetry-figure--${dark ? 'dark' : 'light'} ${metric === 'temperature' ? 'oil-temperature-chart' : ''}`}>
      <figcaption>
        <div>
          <span className="section-kicker">TREND / {metric.toUpperCase()}</span>
          <h3>{title}</h3>
          {caption && <p>{caption}</p>}
          <p className="metric-explanation">{descriptions[metric]}</p>
        </div>

        {allowSelector && (
          <label className="inline-select chart-select">
            <span>METRIC</span>
            <select value={metric} onChange={(event) => onMetricChange?.(event.target.value)}>
              <option value="temperature">Actual vs Expected Oil</option>
              <option value="residual">Thermal Residual</option>
              <option value="loading">Loading %</option>
              <option value="voltage">Voltage R/Y/B</option>
              <option value="current">Current R/Y/B</option>
              <option value="health">Two-hour mean Health + Risk</option>
              <option value="thermalScore">Thermal Score</option>
              <option value="ambient">Ambient Temperature</option>
              <option value="risk">Two-hour mean Prototype Risk</option>
            </select>
          </label>
        )}
      </figcaption>

      {electrical && <div className="waveform-controls"><button type="button" aria-pressed={!cycle} onClick={() => setCycle(false)}>Historical RMS trend</button><button type="button" aria-pressed={cycle} onClick={() => setCycle(true)}>Illustrative 50 Hz cycles</button>{cycle && <><div className="waveform-switches">{[['ideal','Ideal balanced reference'],['scada','SCADA RMS reconstruction'],['reference','Nominal engineering reference']].map(([id,label]) => <label key={id}><input type="checkbox" checked={groups[metric][id]} onChange={(e) => setGroups((old) => ({ ...old, [metric]: { ...old[metric], [id]: e.target.checked } }))} />{label}</label>)}</div><p>R/Y/B separated by assumed 120°. SCADA supplies RMS magnitudes only; peak = RMS × √2. Harmonics, actual phase-angle deviations and current power factor are unmeasured. Voltage basis: 433 V line-to-line / √3 phase-to-neutral. Current reference: {value(last?.asset.ratedCurrent, ' A')}.</p><p><strong>Illustration source: {formatTime(last?.timestamp)} — last processed reading in this graph’s selected history.</strong></p><p>R / Y / B RMS: {['R','Y','B'].map((p) => value(last?.telemetry[metric+p], metric === 'voltage' ? ' V' : ' A')).join(' / ')}. Ideal current uses the observed mean; engineering current uses the rated value. Ideal and nominal voltage references coincide by definition.</p></>}</div>}

      {electrical && cycle ? <div className="chart-canvas"><ResponsiveContainer width="100%" height="100%"><LineChart data={wave}><CartesianGrid stroke={grid} /><XAxis dataKey="ms" unit=" ms" tick={{ fill: axis }} /><YAxis unit={metric === 'voltage' ? ' V' : ' A'} tick={{ fill: axis }} /><Tooltip /><Legend />{Object.entries(groups[metric]).filter(([,enabled]) => enabled).flatMap(([group]) => ['R','Y','B'].map((phase,i) => <Line key={group+phase} name={`${group === 'scada' ? 'RMS reconstruction' : group === 'ideal' ? 'Ideal' : 'Engineering'} ${phase}`} dataKey={group+phase} stroke={(dark ? ['#ff793d','#bbb','#f7f5ef'] : ['#d86a30','#777','#222'])[i]} strokeDasharray={group === 'ideal' ? '6 4' : group === 'reference' ? '2 5' : undefined} strokeWidth={group === 'scada' ? 2 : 1} dot={false} isAnimationActive={false} />))}</LineChart></ResponsiveContainer></div> : data.length === 0 ? <div className="chart-empty">NO PUBLISHED POINTS / Readings or a completed assessment block are needed.</div> : <div className="chart-canvas">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }} onClick={(e) => { if (e?.activePayload?.[0]?.payload?.timestamp) setReviewTimestamp(e.activePayload[0].payload.timestamp) }}>
            <CartesianGrid vertical={false} stroke={grid} strokeDasharray="1 0" />
            <XAxis dataKey="epoch" type="number" scale="time" domain={['dataMin','dataMax']} ticks={timeTicks} tickFormatter={(v) => new Date(v).toLocaleString('en-IN',{timeZone:'Asia/Kolkata',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false})} minTickGap={35} tick={{ fontSize: 10, fill: axis }} axisLine={{ stroke: grid }} tickLine={false} />
            <YAxis domain={metric === 'temperature' ? ['auto','auto'] : undefined} tick={{ fontSize: 10, fill: axis }} width={56} axisLine={false} tickLine={false} />
            <Tooltip filterNull={false} isAnimationActive={false} content={<ExplainTooltip metric={metric} />} />
            {metric === 'temperature' && display.gaps.slice(0,100).map((g,i) => <ReferenceArea key={i} x1={g.x1} x2={g.x2} fill="#777" fillOpacity={0.07} />)}
            {metric === 'residual' && <ReferenceLine y={0} stroke={axis} label="Actual = expected" />}
            {metric === 'loading' && <ReferenceLine y={100} stroke={axis} strokeDasharray="5 5" label="Rated kVA" />}
            {metric === 'thermalScore' && last?.ml.decisionThreshold != null && <ReferenceLine y={last.ml.decisionThreshold} stroke="#d86a30" strokeDasharray="5 5" label="Decision threshold" />}
            <Legend wrapperStyle={{ fontSize: 11, paddingTop: 12 }} />
            {series.map(([key, label], index) => (
              <Line
                key={key}
                type={blockMetric ? 'stepAfter' : 'linear'}
                dataKey={key}
                name={label}
                stroke={seriesColors[index % seriesColors.length]}
                strokeWidth={index === 0 ? 2 : 1.5}
                dot={data.length === 1 ? { r: 3 } : false}
                activeDot={{ r: 5, stroke: '#fff', strokeWidth: 2 }}
                strokeDasharray={metric === 'temperature' && key === 'expectedOil' ? '6 3' : undefined}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
            {metric === 'temperature' && bridgeGaps && [['actualBridge','#111'],['expectedBridge','#d86a30']].map(([key,color]) => <Line key={key} dataKey={key} stroke={color} strokeDasharray="2 5" type="linear" dot={false} activeDot={false} legendType="none" tooltipType="none" connectNulls={false} isAnimationActive={false} />)}
          </LineChart>
        </ResponsiveContainer>
      </div>}
      {blockMetric && <small>One point per published block. Scores average assessable rows only; unassessed blocks leave gaps.</small>}
      <small>{electrical && cycle ? 'Illustrative cycles from one timestamp, not a recorded waveform. Switch to Historical RMS trend to see the selected day over time.' : <>{plotHistory.length.toLocaleString()} original readings in this view{data.length < plotHistory.length ? ` · ${data.length.toLocaleString()} representative chart points, preserving extremes, gaps and detector transitions` : ' · every reading plotted'} · historical time in IST. Hover for exact values.{metric === 'temperature' && ' The reading slider uses every original point in this view.'}</>}</small>
      {metric === 'temperature' && data.length > 0 && <details className="chart-inspection" open={compact ? undefined : true}><summary>Inspect individual readings & missing intervals <span>+</span></summary><div className="chart-quality"><label><input type="checkbox" checked={bridgeGaps} onChange={e => setBridgeGaps(e.target.checked)} />Show dotted visual bridges across short gaps (up to 15 minutes)</label><span>{display.gaps.reduce((n,g) => n + (g.key === 'actualOil' ? g.count : 0),0)} unavailable actual readings · {display.gaps.reduce((n,g) => n + (g.key === 'expectedOil' ? g.count : 0),0)} unavailable expected readings</span></div>{display.gaps.length > 0 && <details className="gap-details"><summary>Why are there gaps? View missing intervals</summary><p>Grey bands mark unavailable measurements or model expectation. Dotted lines interpolate between real endpoints for display only; inference and evidence always use the original readings. Long gaps and warm-up are never filled.</p>{display.gaps.slice(0,30).map((g,i) => <p key={i}>{g.label}: {formatTime(g.from)} — {formatTime(g.to)} · {g.count} missing readings · {g.short && bridgeGaps ? 'dotted display estimate' : 'unavailable'}</p>)}</details>}<section className="reading-inspector" aria-label="Selected temperature reading"><div><span className="section-kicker">{reviewTimestamp ? 'SELECTED READING' : 'LATEST READING'}</span><h4>{formatTime(reviewed.timestamp)}</h4><p>{readingExplanation(reviewed)}</p><small>Readiness: {value(reviewed.ml.dataConfidence)} · Model: {value(reviewed.ml.warmupStatus)} · {reviewed.quality?.issues?.join(', ') || 'No reported sensor-quality issues'}</small></div><label>Inspect historical reading {reviewIndex + 1} / {plotHistory.length}<input aria-label={`Historical reading for ${title}`} type="range" min="0" max={Math.max(0,plotHistory.length-1)} value={reviewIndex} onChange={e => setReviewTimestamp(plotHistory[Number(e.target.value)].timestamp)} /></label><div className="reading-actions"><button onClick={() => setInspected(reviewed)}>Open selected evidence</button><button onClick={() => setReviewTimestamp(null)}>Follow latest reading</button></div></section></details>}
      <Evidence event={inspected ? { id: inspected.timestamp, category: 'Temperature', evidence: { incident: { explanation: inspected.explanation?.message || 'Recorded temperature observation', timestamp: inspected.timestamp }, startMeasurements: { ...inspected.telemetry, thermalResidualC: inspected.ml.thermalResidualC, expectedOilTempC: inspected.ml.expectedOilTempC, thermalScore: inspected.ml.thermalScore, dataConfidence: inspected.ml.dataConfidence }, calibration: inspected.calibration, pointInvestigation: inspected.explanation?.investigation } } : null} onClose={() => setInspected(null)} />
    </figure>
  )
}
