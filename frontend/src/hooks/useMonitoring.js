import { useCallback, useEffect, useRef, useState } from 'react'
import { api, uploadCsv } from '../services/api'

const stageLabel = {
  READING_CSV: 'Reading CSV', VALIDATING_SCHEMA: 'Validating schema', VALIDATING_MEASUREMENTS: 'Validating measurements',
  CHECKING_TIMESTAMPS: 'Checking timestamps', RESOLVING_CALIBRATION: 'Resolving calibration', PREPARING_ML_RUNTIME: 'Preparing ML runtime',
  READY: 'Dataset ready', FAILED: 'Failed',
}

export function useMonitoring() {
  const [rating, setRating] = useState(100)
  const [local, setLocal] = useState(null), [dataset, setDataset] = useState(null)
  const [selectedReplay, setSelectedReplay] = useState('')
  const [session, setSession] = useState(null), [current, setCurrent] = useState(null), [history, setHistory] = useState([]), [alerts, setAlerts] = useState([])
  const [status, setStatus] = useState('IDLE'), [progressText, setProgressText] = useState(''), [error, setError] = useState('')
  const [health, setHealth] = useState(null), [speed, setSpeed] = useState(5)
  const [transport, setTransport] = useState('DISCONNECTED')
  const streamRef = useRef(null), sessionRef = useRef(null), generation = useRef(0), lastRow = useRef(0), abortRef = useRef(null)
  const clientId = useRef(crypto.randomUUID())
  const pending = useRef([]), flushTimer = useRef(null)
  const localOptions = useRef({}), localCommissioning = useRef(null)
  const disconnect = useCallback(() => { streamRef.current?.close(); streamRef.current = null; clearTimeout(flushTimer.current); flushTimer.current = null; pending.current = [] }, [])

  useEffect(() => {
    const controller = new AbortController()
    api('/health', { signal: controller.signal }).then(setHealth).catch((e) => { if (e.name !== 'AbortError') setError(e.message) })
    api('/datasets/local', { signal: controller.signal }).then((meta) => { if (generation.current === 0) { setLocal(meta); setSelectedReplay(meta.replays?.[0]?.id || '') } }).catch((e) => { if (e.name !== 'AbortError') setError(e.message) })
    const leave = () => {
      if (sessionRef.current) navigator.sendBeacon('/api/replay/stop', new Blob([JSON.stringify({ sessionId: sessionRef.current })], { type: 'application/json' }))
    }
    window.addEventListener('beforeunload', leave)
    return () => { controller.abort(); abortRef.current?.abort(); disconnect(); leave(); window.removeEventListener('beforeunload', leave) }
  }, [disconnect])

  const refreshAlerts = useCallback((id) => {
    api(`/transformers/alerts?sessionId=${encodeURIComponent(id)}`).then((r) => { if (sessionRef.current === id) setAlerts(r.alerts) }).catch(() => {})
  }, [])

  const connect = useCallback((next, token) => {
    disconnect(); sessionRef.current = next.sessionId; setSession(next); setStatus(next.status)
    const id = next.sessionId
    const flush = () => {
      flushTimer.current = null
      if (generation.current !== token || sessionRef.current !== id) { pending.current = []; return }
      const batch = pending.current; pending.current = []
      if (!batch.length) return
      const value = batch.at(-1)
      setCurrent(value); setSession(value.replay); setStatus(value.replay.status)
      setHistory(existing => [...existing, ...batch].slice(-10000))
    }
    const stream = new EventSource(`/api/replay/stream?sessionId=${encodeURIComponent(id)}&after=${lastRow.current}`)
    streamRef.current = stream
    stream.addEventListener('reading', (event) => {
      if (generation.current !== token || sessionRef.current !== id) return
      try {
        const value = JSON.parse(event.data)
        if (value.sessionId !== id || value.replay.processedRows <= lastRow.current) return
        lastRow.current = value.replay.processedRows
        // Keep every sensor row, but paint at most five times a second at fast replay speeds.
        pending.current.push(value)
        if (!flushTimer.current) flushTimer.current = setTimeout(flush, 200)
        if (lastRow.current % 10 === 0 || lastRow.current === 1) refreshAlerts(id)
      } catch { setError('Invalid live event received from the backend') }
    })
    stream.addEventListener('status', (event) => {
      if (generation.current !== token || sessionRef.current !== id) return
      clearTimeout(flushTimer.current); flush()
      const value = JSON.parse(event.data); setSession(value); setStatus(value.status)
      if (value.error) setError(value.error)
    })
    stream.addEventListener('ended', (event) => {
      if (generation.current === token && sessionRef.current === id) {
        clearTimeout(flushTimer.current); flush()
        const ended = JSON.parse(event.data || '{}')
        if (ended.reason === 'SESSION_REPLACED') {
          ++generation.current; disconnect(); sessionRef.current = null; setSession(null); setCurrent(null); setHistory([]); setAlerts([]); setStatus('IDLE'); setTransport('DISCONNECTED'); setProgressText('This session was stopped or replaced. Choose a data source to begin.'); return
        }
        stream.close(); refreshAlerts(id)
        api(`/replay/status?sessionId=${id}`).then((r) => { if (sessionRef.current === id) { setSession(r); setStatus(r.status) } }).catch(() => {})
      }
    })
    stream.onerror = () => {
      if (generation.current === token && sessionRef.current === id) {
        setTransport('RECONNECTING');setProgressText('Stream interrupted; reconnecting to the same session without restarting inference.')
        api(`/replay/status?sessionId=${id}`).catch((e) => {
          if (generation.current !== token || sessionRef.current !== id) return
          if (e.message.includes('No active monitoring session') || e.message.includes('Stale or missing session')) {
            ++generation.current;disconnect();sessionRef.current=null;setSession(null);setCurrent(null);setHistory([]);setAlerts([]);setStatus('FAILED');setError('The backend session ended or restarted. Select a data source to begin a new session.');setTransport('DISCONNECTED')
          }
        })
      }
    }
    stream.onopen = () => { if (generation.current === token) { setTransport('CONNECTED');setProgressText('Running real locked-model inference') } }
  }, [disconnect, refreshAlerts])

  const begin = useCallback(async () => {
    const token = ++generation.current
    abortRef.current?.abort(); abortRef.current = new AbortController()
    disconnect(); const previous = sessionRef.current; sessionRef.current = null
    setDataset(null); setSession(null); setCurrent(null); setHistory([]); setAlerts([]);setTransport('DISCONNECTED'); lastRow.current = 0; setError('')
    if (previous) { try { await api('/replay/stop', { method: 'POST', body: { sessionId: previous } }) } catch { /* A newer session may already have replaced it. */ } }
    return token
  }, [disconnect])

  const startLocal = useCallback(async (options = {}, replayId = selectedReplay, commissioning = null) => {
    localOptions.current = options; localCommissioning.current = commissioning
    if (!local?.replays?.some((r) => r.id === replayId)) replayId = local?.replays?.[0]?.id
    const token = await begin(); setStatus('PREPARING'); setProgressText('Validating local SCADA and resolving calibration')
    try {
      const next = await api('/replay/local/start', { method: 'POST', body: { ratingKVA: rating, replayId, speed, options, clientId: clientId.current, generation: token, commissioningCsv: commissioning ? await commissioning.text() : null, verifiedHealthy: options.verified_healthy === true } })
      if (generation.current !== token) { api('/replay/stop', { method: 'POST', body: { sessionId: next.sessionId } }).catch(() => {}); return }
      setDataset(local); setSelectedReplay(next.replayId); connect(next, token)
    } catch (e) { if (generation.current === token) { setError(e.message); setStatus('FAILED') } }
  }, [begin, connect, local, selectedReplay, speed, rating])

  const startUpload = useCallback(async (file, options = {}, commissioning = null) => {
    const token = await begin(); setStatus('UPLOADING'); setProgressText('Uploading dataset')
    try {
      if (file.size > 100 * 1024 * 1024) throw new Error('Dataset exceeds the 100 MiB upload limit')
      let meta = await uploadCsv(file, { ...options, ratingKVA: rating }, commissioning, (text) => { if (generation.current === token) setProgressText(text) }, abortRef.current.signal)
      while (meta.status !== 'READY' && meta.status !== 'FAILED') {
        if (generation.current !== token) return
        setProgressText(stageLabel[meta.status] || meta.status)
        await new Promise((resolve) => setTimeout(resolve, 200))
        meta = await api(`/datasets/status?datasetId=${meta.id}`, { signal: abortRef.current.signal })
      }
      if (generation.current !== token) return
      if (meta.status === 'FAILED') throw new Error(meta.error || 'Dataset validation failed')
      setDataset(meta); setSelectedReplay(meta.replays[0].id); setProgressText('Starting replay'); setStatus('STARTING')
      const next = await api('/replay/uploaded/start', { method: 'POST', body: { datasetId: meta.id, replayId: meta.replays[0].id, speed, clientId: clientId.current, generation: token } })
      if (generation.current !== token) { api('/replay/stop', { method: 'POST', body: { sessionId: next.sessionId } }).catch(() => {}); return }
      connect(next, token)
    } catch (e) { if (generation.current === token && e.name !== 'AbortError') { setError(e.message); setStatus('FAILED') } }
  }, [begin, connect, speed, rating])

  const control = useCallback(async (action, value) => {
    if (!sessionRef.current) return
    setError('')
    const id = sessionRef.current
    const controlGeneration = generation.current
    try {
      if (action === 'restart') {
        const token = ++generation.current; disconnect(); lastRow.current = 0; setCurrent(null); setHistory([]); setAlerts([])
        const next = await api('/replay/restart', { method: 'POST', body: { sessionId: id, clientId: clientId.current, generation: token } })
        if (generation.current === token) connect(next, token)
        else api('/replay/stop', { method: 'POST', body: { sessionId: next.sessionId } }).catch(() => {})
      } else {
        const next = await api(`/replay/${action}`, { method: 'POST', body: { sessionId: id, ...(action === 'speed' ? { speed: value } : {}) } })
        if (sessionRef.current === id) { setSession(next); setStatus(next.status) }
        if (action === 'stop') { ++generation.current; disconnect(); sessionRef.current = null; setSession(null); setCurrent(null); setHistory([]); setAlerts([]); lastRow.current = 0; setStatus('IDLE'); setTransport('DISCONNECTED'); setProgressText('Monitoring stopped') }
      }
    } catch (e) { if (generation.current === controlGeneration || (action === 'restart' && generation.current === controlGeneration + 1)) setError(e.message) }
  }, [connect, disconnect])

  const changeReplay = useCallback(async (id) => {
    setSelectedReplay(id)
    if (!sessionRef.current) return
    if (!dataset || dataset.mode === 'LOCAL') return startLocal(localOptions.current, id, localCommissioning.current)
    const token = await begin()
    try {
      const next = await api('/replay/uploaded/start', { method: 'POST', body: { datasetId: dataset.id, replayId: id, speed, clientId: clientId.current, generation: token } })
      if (generation.current === token) { setDataset(dataset); connect(next, token) }
      else api('/replay/stop', { method: 'POST', body: { sessionId: next.sessionId } }).catch(() => {})
    } catch (e) { if (generation.current === token) { setError(e.message); setStatus('FAILED') } }
  }, [begin, connect, dataset, speed, startLocal])

  const changeRating = useCallback(async (value) => {
    const nextRating = Number(value)
    if (nextRating === rating) return
    const token = await begin()
    setRating(nextRating); setLocal(null); setSelectedReplay('');setStatus('PREPARING');setProgressText(`Validating ${nextRating}-kVA local data`)
    localOptions.current = {}; localCommissioning.current = null
    try {
      const meta = await api(`/datasets/local?ratingKVA=${nextRating}`, { signal: abortRef.current.signal })
      if (generation.current !== token) return
      setLocal(meta);setSelectedReplay(meta.replays?.[0]?.id || '');setStatus('IDLE');setProgressText('Select Run on local data or add a matching CSV')
    } catch (e) { if (generation.current === token && e.name !== 'AbortError') { setError(e.message);setStatus('FAILED') } }
  }, [begin, rating])

  const changeSpeed = useCallback((value) => { setSpeed(value); if (sessionRef.current) control('speed', value) }, [control])
  return { rating, changeRating, local, dataset, selectedReplay, changeReplay, session, current, history, alerts, health, status, progressText, error, speed, changeSpeed, transport,
    startLocal, startUpload, control, reconnect: () => { if (session) connect(session, generation.current) },
    cancel: async () => { const token=await begin();setStatus('IDLE');setProgressText('Preparation canceled');await api('/replay/cancel',{method:'POST',body:{clientId:clientId.current,generation:token}}) },
    clearError: () => setError(''), removeUpload: async () => {
      if (!dataset || dataset.mode !== 'UPLOADED') return
      await control('stop'); await api('/datasets/delete', { method: 'POST', body: { datasetId: dataset.id } }); setDataset(null)
    } }
}
