// Use 127.0.0.1, not localhost — on this system "localhost" resolves to
// ::1 (IPv6) first, but uvicorn only binds IPv4, so browsers/Node's fetch
// attempt the IPv6 route and get ERR_CONNECTION_RESET. See BUGS.md.
const API = 'http://127.0.0.1:8000'

export async function uploadFile(endpoint, propertyId, file) {
  const form = new FormData()
  form.append('property_id', propertyId)
  form.append('file', file)
  const res = await fetch(`${API}/ingest/${endpoint}`, {
    method: 'POST',
    body: form,
  })
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
  return res.json()
}

export async function getProperty(propertyId) {
  const res = await fetch(`${API}/property/${propertyId}`)
  if (!res.ok) throw new Error(`Fetch property failed: ${res.status}`)
  return res.json()
}

export async function getContractors(category) {
  const res = await fetch(`${API}/contractors?category=${encodeURIComponent(category)}`)
  if (!res.ok) throw new Error(`Fetch contractors failed: ${res.status}`)
  return res.json()
}

export async function sendChat(propertyId, message) {
  const form = new FormData()
  form.append('property_id', propertyId)
  form.append('message', message)
  const res = await fetch(`${API}/chat`, { method: 'POST', body: form })
  if (!res.ok) throw new Error(`Chat failed: ${res.status}`)
  return res.json()
}
