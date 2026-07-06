// Dev (Vite on :5173): talk to uvicorn on 127.0.0.1:8000 — not
// "localhost", which resolves to ::1 (IPv6) first on this system while
// uvicorn only binds IPv4 (ERR_CONNECTION_RESET, see BUGS.md #18).
// Production build: served BY the FastAPI server itself (see main.py's
// static mount), so API calls are same-origin relative paths.
const API = import.meta.env.DEV ? 'http://127.0.0.1:8000' : ''

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// Ingestion runs a multi-second OCR/Vision pipeline and chat runs a full
// RAG graph — those get a long budget; simple reads should fail fast.
const READ_TIMEOUT_MS = 15_000
const PIPELINE_TIMEOUT_MS = 240_000

async function request(path, { method = 'GET', body, timeoutMs = READ_TIMEOUT_MS } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  let res
  try {
    res = await fetch(`${API}${path}`, { method, body, signal: controller.signal })
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new ApiError(`Request timed out after ${Math.round(timeoutMs / 1000)}s`, 0)
    }
    throw new ApiError('Could not reach the Property Intelligence API — is the backend running on :8000?', 0)
  } finally {
    clearTimeout(timer)
  }

  if (!res.ok) {
    // FastAPI puts human-readable failure reasons in {"detail": ...} —
    // surface that instead of a bare status code.
    let detail = ''
    try {
      const data = await res.json()
      detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail || `Request failed (${res.status})`, res.status)
  }
  return res.json()
}

export function uploadFile(endpoint, propertyId, file) {
  const form = new FormData()
  form.append('property_id', propertyId)
  form.append('file', file)
  return request(`/ingest/${endpoint}`, {
    method: 'POST', body: form, timeoutMs: PIPELINE_TIMEOUT_MS,
  })
}

export function getProperty(propertyId) {
  return request(`/property/${propertyId}`)
}

export function getContractors(category) {
  return request(`/contractors?category=${encodeURIComponent(category)}`)
}

// For resources the API serves by relative URL (e.g. uploaded photos).
export function apiUrl(path) {
  return `${API}${path}`
}

export function resetDatabase() {
  return request('/reset', { method: 'POST' })
}

export function sendChat(propertyId, message) {
  const form = new FormData()
  form.append('property_id', propertyId)
  form.append('message', message)
  return request('/chat', { method: 'POST', body: form, timeoutMs: PIPELINE_TIMEOUT_MS })
}
