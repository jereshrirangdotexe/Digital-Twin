export async function api(path, { method = 'GET', body, signal } = {}) {
  const response = await fetch(`/api${path}`, {
    method, signal, headers: body && !(body instanceof FormData) ? { 'Content-Type': 'application/json' } : undefined,
    body: body instanceof FormData ? body : body == null ? undefined : JSON.stringify(body),
  })
  const text = await response.text()
  let result
  try { result = text ? JSON.parse(text) : null } catch { throw new Error('Backend returned an invalid response. Verify that all services are running.') }
  if (!response.ok) throw new Error(result?.error || `Backend request failed (${response.status})`)
  return result
}

export function uploadCsv(file, options, commissioning, onProgress, signal) {
  return new Promise((resolve, reject) => {
    const form = new FormData(); form.append('file', file); form.append('options', JSON.stringify(options))
    if (commissioning) form.append('commissioning', commissioning)
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/datasets/upload')
    xhr.upload.onprogress = (event) => { if (event.lengthComputable) onProgress?.(`Uploading dataset — ${Math.round(event.loaded / event.total * 100)}%`) }
    const abort = () => xhr.abort()
    signal?.addEventListener('abort', abort, { once: true })
    xhr.onload = () => {
      signal?.removeEventListener('abort', abort)
      try {
        const value = JSON.parse(xhr.responseText)
        if (xhr.status >= 400) reject(new Error(value.error || 'Upload failed'))
        else resolve(value)
      } catch { reject(new Error('Backend returned an invalid upload response')) }
    }
    xhr.onerror = () => reject(new Error('Upload connection failed. Verify that the backend is running.'))
    xhr.onabort = () => reject(new DOMException('Upload canceled', 'AbortError'))
    xhr.send(form)
  })
}

export function selectedHistory(history, range) {
  const minutes = { '15 min': 15, '1 hour': 60, '6 hours': 360, '24 hours': 1440, '7 days': 10080 }[range]
  if (!minutes || !history.length) return range === 'Live' ? history.slice(-120) : history
  const valid = history.filter((r) => r.timestamp != null)
  if (!valid.length) return []
  const latest = Date.parse(valid.at(-1).timestamp)
  return valid.filter((r) => Date.parse(r.timestamp) >= latest - minutes * 60000)
}
