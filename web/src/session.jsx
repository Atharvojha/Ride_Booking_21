import { useCallback, useEffect, useState } from 'react'
import { request } from './api'
import { Icon, Notice, Picker } from './components'

// The signed-in person: { role: 'admin' | 'rider', id, name }, or null when signed out.
export function useSession() {
  const [state, setState] = useState({ ready: false, session: null, error: null })
  useEffect(() => {
    const controller = new AbortController()
    request('/api/session', { signal: controller.signal })
      .then(data => setState({ ready: true, session: data.role ? data : null, error: null }))
      .catch(error => { if (!controller.signal.aborted) setState({ ready: true, session: null, error }) })
    // Any request answered "session required" (for example after 8 hours) returns to the sign-in screen.
    const expired = () => setState({ ready: true, session: null, error: null })
    window.addEventListener('ridesync:signed-out', expired)
    return () => { controller.abort(); window.removeEventListener('ridesync:signed-out', expired) }
  }, [])
  const signedIn = useCallback(session => setState({ ready: true, session, error: null }), [])
  const signOut = useCallback(async () => {
    try { await request('/api/session/logout', { method: 'POST' }) } catch { /* the cookie ends on its own */ }
    setState({ ready: true, session: null, error: null })
  }, [])
  return { ...state, signedIn, signOut }
}

export function RiderSignIn({ onSignedIn }) {
  const [rider, setRider] = useState(null)
  const [error, setError] = useState(null)
  const [working, setWorking] = useState(false)
  async function go() {
    if (!rider || working) return
    setWorking(true); setError(null)
    try { onSignedIn(await request('/api/session/rider', { method: 'POST', body: { riderId: rider.id } })) }
    catch (problem) { setError(problem); setWorking(false) }
  }
  return <div className="signin-form">
    <p className="signin-note">Demo sign-in: choose one of the seeded riders. You will see only your own wallet and trips.</p>
    {error && <Notice kind="error">{error.message}</Notice>}
    <Picker kind="riders" endpoint="/api/session/riders" label="Sign in as rider" value={rider} onChange={setRider} disabled={working} />
    <button className="cta" onClick={go} disabled={!rider || working}>{working ? 'Signing in…' : rider ? 'Continue as ' + rider.name : 'Choose a rider first'}<Icon name="arrow" size={16} /></button>
  </div>
}

export function AdminSignIn({ onSignedIn }) {
  const [form, setForm] = useState({ username: '', password: '' })
  const [error, setError] = useState(null)
  const [working, setWorking] = useState(false)
  async function submit(event) {
    event.preventDefault()
    if (working) return
    setWorking(true); setError(null)
    try { onSignedIn(await request('/api/session/admin', { method: 'POST', body: form })) }
    catch (problem) { setError(problem); setWorking(false) }
  }
  return <form className="signin-form" onSubmit={submit}>
    <p className="signin-note">Admins see every rider, vehicle and trip, read revenue analytics and refresh the totals.</p>
    {error && <Notice kind="error">{error.message}</Notice>}
    <label>Username<input autoComplete="username" required value={form.username} onChange={event => setForm({ ...form, username: event.target.value })} /></label>
    <label>Password<input type="password" autoComplete="current-password" required value={form.password} onChange={event => setForm({ ...form, password: event.target.value })} /></label>
    <button className="cta" type="submit" disabled={working}>{working ? 'Signing in…' : 'Sign in as admin'}<Icon name="arrow" size={16} /></button>
  </form>
}
