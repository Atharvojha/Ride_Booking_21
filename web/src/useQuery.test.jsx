import { act, renderHook, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { useQuery } from './useQuery'
import { usePolling } from './usePolling'

function reply(data) { return { ok: true, json: async () => data } }
it('ignores an old rider reply even if it arrives last', async () => {
  const replies = []
  vi.stubGlobal('fetch', vi.fn(() => new Promise(resolve => replies.push(resolve))))
  const { result, rerender } = renderHook(({ url }) => useQuery(url), { initialProps: { url: '/api/riders/one' } })
  rerender({ url: '/api/riders/two' }); expect(result.current.data).toBeNull()
  await act(async () => replies[1](reply({ name: 'Second rider' })))
  await act(async () => replies[0](reply({ name: 'First rider' })))
  expect(result.current.data.name).toBe('Second rider')
})
it('keeps a last good read on refresh failure and clears it for a new filter', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(reply({ total: 25 })).mockRejectedValueOnce(new Error('offline')).mockImplementation(() => new Promise(() => {})))
  const { result, rerender } = renderHook(({ url }) => useQuery(url), { initialProps: { url: '/api/riders' } })
  await waitFor(() => expect(result.current.data?.total).toBe(25))
  const reload = result.current.reload
  act(() => reload()); await waitFor(() => expect(result.current.error).toBeTruthy())
  expect(result.current.data.total).toBe(25); expect(result.current.reload).toBe(reload)
  rerender({ url: '/api/riders?search=new' }); expect(result.current.data).toBeNull()
})
it('polls only when visible and idle, then stops after leaving', () => {
  vi.useFakeTimers(); let hidden = false
  vi.spyOn(document, 'hidden', 'get').mockImplementation(() => hidden)
  const reload = vi.fn()
  const { rerender, unmount } = renderHook(({ loading }) => usePolling(reload, loading), { initialProps: { loading: false } })
  act(() => vi.advanceTimersByTime(10000)); expect(reload).toHaveBeenCalledTimes(1)
  hidden = true; act(() => vi.advanceTimersByTime(20000)); expect(reload).toHaveBeenCalledTimes(1)
  hidden = false; act(() => document.dispatchEvent(new Event('visibilitychange'))); expect(reload).toHaveBeenCalledTimes(2)
  rerender({ loading: true }); act(() => vi.advanceTimersByTime(10000)); expect(reload).toHaveBeenCalledTimes(2)
  unmount(); act(() => vi.advanceTimersByTime(20000)); expect(reload).toHaveBeenCalledTimes(2)
})
