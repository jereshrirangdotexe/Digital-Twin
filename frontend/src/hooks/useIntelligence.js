import { useEffect, useState } from 'react'
import { api } from '../services/api'
export function useIntelligence(monitoring) {
  const [summary, setSummary] = useState(null), [error, setError] = useState(''), [refresh, setRefresh] = useState(0)
  const sessionId = monitoring.session?.sessionId, rating = monitoring.rating
  useEffect(() => { setSummary(null); setError('') }, [sessionId, rating])
  useEffect(() => {
    if (!sessionId || rating !== 100) return
    const controller = new AbortController(); let timer
    const read = async () => {
      try { const data = await api(`/summary/overall?sessionId=${sessionId}`, { signal: controller.signal }); setSummary(data); setError('') }
      catch (e) { if (e.name !== 'AbortError') setError(e.message) }
      if (!controller.signal.aborted) timer = setTimeout(read, 5000)
    }
    read(); return () => { controller.abort(); clearTimeout(timer) }
  }, [sessionId, rating, refresh])
  return { summary, error, sessionId, refresh: () => setRefresh((r) => r + 1) }
}
