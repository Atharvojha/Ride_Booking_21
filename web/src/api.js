export class ApiError extends Error {
  constructor(message, code = 'NETWORK_ERROR', uncertain = false) {
    super(message)
    this.code = code
    this.uncertain = uncertain
  }
}

export function apiUrl(path, params = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== '' && value !== null && value !== undefined) query.set(key, String(value))
  })
  return path + (query.size ? '?' + query.toString() : '')
}

export async function request(url, { signal, method = 'GET', body } = {}) {
  const controller = new AbortController()
  const cancel = () => controller.abort()
  if (signal?.aborted) cancel()
  signal?.addEventListener('abort', cancel, { once: true })
  const timer = setTimeout(cancel, 30000)
  const write = method !== 'GET'
  try {
    const response = await fetch(url, { method, signal: controller.signal,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined })
    const data = await response.json()
    if (!response.ok) throw new ApiError(data.error?.message || 'The request failed.',
      data.error?.code || 'SERVER_ERROR', write && response.status >= 500)
    return data
  } catch (error) {
    if (signal?.aborted) throw error
    if (error instanceof ApiError) throw error
    throw new ApiError(write ? 'The reply was lost. Check the saved result before trying again.' :
      'Cannot reach RideSync. Check that the API is running and try again.', 'NETWORK_ERROR', write)
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', cancel)
  }
}

export function fareInPaise(text) {
  if (!/^\d{1,8}(\.\d{1,2})?$/.test(text)) return null
  const [whole, fraction = ''] = text.split('.')
  const paise = Number(whole) * 100 + Number(fraction.padEnd(2, '0'))
  return paise > 0 && paise <= 9999999999 ? paise : null
}

export function fixedFare(text) {
  const paise = fareInPaise(text)
  return paise === null ? null : (paise / 100).toFixed(2)
}

export function money(value) {
  if (value === null || value === undefined) return 'Unknown'
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' }).format(Number(value))
}

export function time(value) {
  if (!value) return 'Unknown'
  return new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Kolkata' }).format(new Date(value))
}

export function shortId(value) { return value?.slice(0, 8) || '—' }
