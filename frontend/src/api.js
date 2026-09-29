export class ApiError extends Error {
  constructor(message, status = 0, detail = null) { super(message); this.status = status; this.detail = detail }
}

// Maps the real cause to a message: network failure, or whatever the server said.
export async function apiFetch(url, options) {
  let response
  try { response = await fetch(url, options) } catch { throw new ApiError('Could not reach the API') }
  if (response.ok) return response.json()
  const body = await response.json().catch(() => null)
  const detail = body?.detail ?? body
  const message = (typeof detail === 'string' ? detail : detail?.message || detail?.error || (Array.isArray(detail) && detail[0]?.msg)) || `Server error (${response.status})`
  throw new ApiError(message, response.status, detail)
}
