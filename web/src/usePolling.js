import { useEffect } from 'react'

export function usePolling(reload, loading, interval = 10000) {
  useEffect(() => {
    function update() { if (!document.hidden && !loading) reload() }
    const timer = setInterval(update, interval)
    document.addEventListener('visibilitychange', update)
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', update) }
  }, [reload, loading, interval])
}
