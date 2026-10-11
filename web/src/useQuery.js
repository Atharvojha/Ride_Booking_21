import { useCallback, useEffect, useState } from 'react'
import { request } from './api'

export function useQuery(url) {
  const [version, setVersion] = useState(0)
  const [state, setState] = useState({ key: null, data: null, error: null, loading: false, loadedAt: null })
  useEffect(() => {
    if (!url) return
    let current = true
    const controller = new AbortController()
    setState(old => ({ key: url, data: old.key === url ? old.data : null,
      loadedAt: old.key === url ? old.loadedAt : null, error: null, loading: true }))
    request(url, { signal: controller.signal }).then(data => {
      if (current) setState({ key: url, data, error: null, loading: false, loadedAt: new Date().toISOString() })
    }).catch(error => {
      if (current) setState(old => ({ ...old, error, loading: false }))
    })
    return () => { current = false; controller.abort() }
  }, [url, version])
  // Clear old actor/filter results immediately, before the new request finishes.
  const visible = state.key === url ? state : { data: null, error: null, loading: Boolean(url), loadedAt: null }
  const reload = useCallback(() => setVersion(value => value + 1), [])
  return { ...visible, reload }
}
