import { describe, expect, it, vi } from 'vitest'
import { apiUrl, fareInPaise, fixedFare, request, time } from './api'

it('keeps zero and false filters while dropping empty filters', () => {
  expect(apiUrl('/api/vehicles', { active: false, page: 0, search: '', vehicleId: null })).toBe('/api/vehicles?active=false&page=0')
})
it.each(['0', '-1', '1.001', 'NaN', 'Infinity', '1e2', '100000000.00', '', '.10'])('rejects invalid fare %s', text => expect(fareInPaise(text)).toBeNull())
it.each([['0.01', 1, '0.01'], ['120.1', 12010, '120.10'], ['99999999.99', 9999999999, '99999999.99']])('keeps exact paise for %s', (text, paise, fixed) => {
  expect(fareInPaise(text)).toBe(paise); expect(fixedFare(text)).toBe(fixed)
})
it('formats dates in India even near midnight UTC', () => expect(time('2026-10-10T20:00:00Z')).toContain('11 Oct 2026'))
it('shows a known failure without claiming a lost write', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 409, json: async () => ({ error: { code: 'ACTIVE_TRIP_EXISTS', message: 'Finish your active trip.' } }) }))
  await expect(request('/api/trips', { method: 'POST', body: {} })).rejects.toMatchObject({ message: 'Finish your active trip.', uncertain: false })
})
it.each([500, 503])('requires checking a write after HTTP %s', async status => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status, json: async () => ({ error: { message: 'Unavailable' } }) }))
  await expect(request('/api/trips', { method: 'POST' })).rejects.toMatchObject({ uncertain: true })
})
it('requires checking a write after a lost reply', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
  await expect(request('/api/trips', { method: 'POST' })).rejects.toMatchObject({ uncertain: true })
  await expect(request('/api/riders')).rejects.toMatchObject({ uncertain: false })
})
it('times out a stalled request and clears its timer', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn((url, options) => new Promise((resolve, reject) => options.signal.addEventListener('abort', () => reject(new Error('aborted'))))))
  const result = request('/api/trips', { method: 'POST' }).catch(error => error)
  await vi.advanceTimersByTimeAsync(30000)
  expect(await result).toMatchObject({ uncertain: true }); expect(vi.getTimerCount()).toBe(0)
})
