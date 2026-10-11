import { useState, useRef, useLayoutEffect } from 'react'
import Navigation from './components/Navigation'
import TopBar from './components/TopBar'
import MonitoringSource from './components/MonitoringSource'
import IdleMonitoring from './components/IdleMonitoring'
import { useMonitoring } from './hooks/useMonitoring'
import Overview from './pages/Overview'
import LiveTwin from './pages/LiveTwin'
import Analytics from './pages/Analytics'
import Alerts from './pages/Alerts'
import Maintenance from './pages/Maintenance'
import Assets from './pages/Assets'
import AssessmentSummary from './components/AssessmentSummary'
import ReportDownloads from './components/ReportDownloads'
import Insights from './components/Insights'
import Intelligence from './pages/Intelligence'
import { useIntelligence } from './hooks/useIntelligence'
import IncidentSummary from './components/IncidentSummary'

export default function App() {
  const [page, setPage] = useState('overview')
  const mainRef = useRef(null)
  const [navigationTick, setNavigationTick] = useState(0)
  const navigate = (next) => { setPage(next); setNavigationTick(t => t + 1) }
  useLayoutEffect(() => {
    if (!navigationTick) return
    mainRef.current?.scrollIntoView({ block: 'start', behavior: 'instant' })
    mainRef.current?.focus({ preventScroll: true })
  }, [page, navigationTick])
  const monitoring = useMonitoring()
  const intelligence = useIntelligence(monitoring)
  const { current, history } = monitoring
  const meta = monitoring.dataset || monitoring.local
  const model = monitoring.health?.models?.find((m) => m.ratingKVA === monitoring.rating) || monitoring.health
  const assets = (meta?.replays || []).map((r) => ({
    id: r.id, ratingKVA: monitoring.rating, nominalVoltage: model?.engineering?.nominalPhaseVoltageV,
    ratedCurrent: model?.engineering?.ratedCurrentA?.toFixed(2), coolingType: 'ONAN', samplingInterval: '5 min',
    modelVersion: model?.modelVersion || 'UNAVAILABLE', digitalTwinVersion: 'Operational observation v1.0',
    calibrationStatus: current && monitoring.selectedReplay === r.id ? current.ml.calibrationStatus : 'NOT ASSESSED', lastCalibration: null,
  }))
  const asset = assets.find((r) => r.id === monitoring.selectedReplay) || { id: monitoring.selectedReplay || '', ratingKVA: monitoring.rating }
  const openAsset = (id) => { const replayId = current?.asset.id === id ? monitoring.selectedReplay : id; if (replayId !== monitoring.selectedReplay) monitoring.changeReplay(replayId); navigate('live') }
  let content
  if (['lab','faults','dna','reports'].includes(page)) content = <Intelligence current={current} intelligence={intelligence} page={page} rating={monitoring.rating} />
  else if (page === 'analytics') content = <Analytics history={history} />
  else if (page === 'alerts') content = <Alerts alerts={monitoring.alerts} sessionId={monitoring.session?.sessionId} rating={monitoring.rating} />
  else if (page === 'maintenance') content = current ? <Maintenance current={current} history={history} /> : <IdleMonitoring rating={monitoring.rating} />
  else if (page === 'assets') content = <Assets assets={assets} current={current} onOpenAsset={openAsset} />
  else if (!current) content = <IdleMonitoring rating={monitoring.rating} />
  else if (page === 'overview') content = <Overview fleet={[current]} onOpenAsset={openAsset} onNavigate={navigate} intelligence={intelligence} />
  else content = <LiveTwin current={current} history={history} />
  return <div className="app-shell">
    <Navigation page={page} onChange={navigate} sourceMode={monitoring.session ? monitoring.dataset?.mode : 'IDLE'} />
    <TopBar asset={asset} assets={assets} current={current} onAssetChange={monitoring.changeReplay} transport={monitoring.transport} preparing={['UPLOADING','PREPARING','STARTING'].includes(monitoring.status)} />
    <details className="source-drawer" open={!current || undefined}><summary><span>Data source & replay controls</span><small>{monitoring.rating} kVA · {monitoring.status} · {monitoring.session ? `${monitoring.session.processedRows.toLocaleString()} / ${monitoring.session.totalRows.toLocaleString()} readings` : 'Choose a source to begin'}</small><b>Open controls +</b></summary><MonitoringSource monitoring={monitoring} /></details>
    <main ref={mainRef} tabIndex={-1} className={`content content--${page}`} aria-label="Selected workspace">
      {current?.asset.id==='DEMO100_THERMAL_TWIN' && <section className="demo-context" aria-label="Synthetic thermal demonstration"><span>SYNTHETIC DEMONSTRATION · 100 kVA · 4,032 READINGS</span><h2>{new Date(current.timestamp).getTime()<Date.parse('2026-02-09T00:00:00+05:30') ? '01 / Normal load response: actual follows expected' : new Date(current.timestamp).getTime()<Date.parse('2026-02-12T00:00:00+05:30') ? '02 / Injected excess heating: watch the temperature gap' : '03 / Recovery: the extra heat is removed'}</h2><p>1–8 Feb: normal heating and cooling · 9–11 Feb: controlled excess heat · 12–14 Feb: recovery. These are generated measurements for explaining the existing twin and detector, not a model-accuracy test. Warm-up is expected; a detected condition is not a software error.</p></section>}
      {current && ['overview','live','alerts'].includes(page) && <IncidentSummary current={current} alerts={monitoring.alerts} session={monitoring.session} onOpen={() => navigate('alerts')} />}
      {page === 'reports' && <ReportDownloads history={history} alerts={monitoring.alerts} />}
      <div className="page-reveal" key={page}>{content}</div>
      {page === 'overview' && current && <details className="assessment-drawer"><summary>Two-hour assessment · coverage, timing and publication details <span>+</span></summary><AssessmentSummary current={current} /></details>}
    </main>
    <Insights intelligence={intelligence} rating={monitoring.rating} current={current} />
    <footer className="site-footer"><div className="footer-mark" aria-hidden="true"><i /><i /><i /><i /></div><div><strong>VOLTMIND</strong><span>100 / 250 / 630-kVA / Condition Monitoring / Local Prototype</span></div><div className="footer-links"><span>Internal synthetic validation; not field certified.</span><details><summary>Privacy / data handling</summary><p>Uploads stay on this computer in temporary application storage. Stopping and removing an upload, or restarting the worker, clears its temporary file. Processed 100 kVA observations, incidents and maintenance remain in the local evidence database across restarts. No external telemetry service is configured.</p></details><details><summary>Use and limitations</summary><p>Health and risk are documented prototype observation indices. No remaining-life estimate or automatic protection/maintenance action is provided. Qualified engineering review remains necessary.</p></details></div></footer>
  </div>
}

