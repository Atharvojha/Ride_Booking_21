import { useEffect, useRef, useState } from 'react'
import { useQuery } from './useQuery'
import { Icon, Notice, Picker } from './components'
import { useSession } from './session'
import { Landing } from './home'
import Browse from './screens/Browse'
import Booking from './screens/Booking'
import Wallet from './screens/Wallet'
import Analytics from './screens/Analytics'
import Nearby from './screens/Nearby'
import Reviews from './screens/Reviews'

const all = {
  browse: { id: 'browse', title: 'Browse Data', short: 'Browse', description: 'Explore riders, vehicles and trips in your RideSync workspace.' },
  trips: { id: 'browse', title: 'Trips & Vehicles', short: 'Browse', description: 'Look through your own trips and the vehicles you can book.' },
  booking: { id: 'booking', title: 'Book a Trip', short: 'Book', description: 'Choose a vehicle, then review the wallet charge.' },
  myWallet: { id: 'wallet', title: 'My Wallet', short: 'Wallet', description: 'Follow every change to your wallet balance.' },
  wallet: { id: 'wallet', title: 'Wallet Audit', short: 'Wallet', description: 'Follow the saved wallet changes for the rider you are inspecting.' },
  analytics: { id: 'analytics', title: 'Vehicle Analytics', short: 'Analytics', description: 'Explore revenue, daily rankings and lifetime vehicle totals.' },
  nearby: { id: 'nearby', title: 'Nearby Vehicles', short: 'Nearby', description: 'Find fresh, available vehicles around a chosen origin.' },
  reviews: { id: 'reviews', title: 'Trip Reviews', short: 'Reviews', description: 'Read rider feedback and explore vehicle features and inspections.' },
}
// What each role can open. The API enforces the same split.
const views = {
  rider: [all.booking, all.myWallet, all.trips, all.nearby, all.reviews],
  admin: [all.browse, all.analytics, all.wallet, all.nearby, all.reviews],
}
const LOCKED = 'Locked until the last booking result has been checked'
const clock = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' })

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => { const timer = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(timer) }, [])
  return <span className="clock" aria-label="Time in Hyderabad">HYDERABAD <b>{clock.format(now)}</b> IST</span>
}

export default function App() {
  const { ready, session, error, signedIn, signOut } = useSession()
  if (!ready) return <div className="landing"><p className="muted" role="status">Loading…</p></div>
  if (!session) return <Landing onSignedIn={signedIn} error={error} />
  return <Console session={session} onSignOut={signOut} key={session.role + session.id} />
}

function Console({ session, onSignOut }) {
  const isAdmin = session.role === 'admin'
  const screens = views[session.role]
  const [screen, setScreen] = useState(screens[0].id)
  const [chosen, setActor] = useState(null)
  const [menu, setMenu] = useState(false)
  const [busy, setBusy] = useState(false)
  const heading = useRef(null)
  // A rider is always themselves; an admin picks which rider to inspect (the first one to start).
  const initialRider = useQuery(isAdmin ? '/api/riders?pageSize=1' : '/api/riders/' + session.id)
  // Screens restart when the inspected rider changes, but not when the default one finishes loading.
  const actorKey = isAdmin ? chosen?.id : session.id
  const actor = isAdmin ? chosen || initialRider.data?.items[0] || null : initialRider.data?.rider || null
  useEffect(() => { heading.current?.focus({ preventScroll: true }) }, [screen])
  useEffect(() => {
    const close = event => { if (event.key === 'Escape') setMenu(false) }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [])
  const index = screens.findIndex(item => item.id === screen)
  const current = screens[index]
  function navigate(value) { if (!busy) { setScreen(value); setMenu(false); window.scrollTo({ top: 0 }) } }
  return <div className="app"><a className="skip-link" href="#main">Skip to content</a>
    {menu && <button className="menu-backdrop" aria-label="Close navigation" onClick={() => setMenu(false)} />}
    <header className="topbar">
      <div className="brand"><span className="brand-mark" aria-hidden="true"><Icon name="nearby" size={16} strokeWidth={1.8} /></span><span>RIDE<b>SYNC</b></span></div>
      <button className="menu-button icon-button" aria-label="Open navigation" aria-expanded={menu} onClick={() => setMenu(!menu)}><Icon name="menu" /></button>
      <div className="console-meta"><Clock /><aside className={'sidebar ' + (menu ? 'open' : '')}>
        <nav aria-label="Main navigation">{screens.map((item, position) => <button key={item.id} disabled={busy} title={busy ? LOCKED : item.title} aria-label={item.title}
          className={screen === item.id ? 'active' : ''} aria-current={screen === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}>
          <span className="nav-index" aria-hidden="true">{String(position + 1).padStart(2, '0')}</span><span aria-hidden="true">{item.short}</span></button>)}</nav>
        <div className="ruler" aria-hidden="true" style={{ '--at': index, '--count': screens.length }}><i /></div>
      </aside></div>
      <div className="actor"><span className="avatar" aria-hidden="true">{(isAdmin ? actor?.name : session.name)?.slice(0, 1) || 'R'}</span>
        {isAdmin ? <Picker kind="riders" label="Inspect rider" value={actor} onChange={setActor} disabled={busy} title={busy ? LOCKED : undefined} />
          : <div className="whoami"><span className="field-label">Signed in as rider</span><strong>{session.name}</strong></div>}</div>
      <div className="session-chip">{isAdmin && <span className="admin-badge"><Icon name="check" size={14} strokeWidth={2} />Admin</span>}
        <button className="small secondary" disabled={busy} title={busy ? LOCKED : undefined} onClick={onSignOut}>Sign out</button></div>
    </header>
    <div className="workspace">
      <main id="main">
        <div className="page-heading">
          <div><p className="eyebrow"><span>{String(index + 1).padStart(2, '0')}</span>{current.short}</p><h1 tabIndex="-1" ref={heading}>{current.title}</h1><p>{current.description}</p></div>
        </div>
        {initialRider.error && !actor && <Notice kind="error" onRetry={initialRider.reload}>{initialRider.error.message}</Notice>}
        {busy && <Notice kind="warning">Finish the current booking check before changing the rider or screen.</Notice>}
        <div className="screen" key={screen}>
          {screen === 'browse' && <Browse actor={actor} role={session.role} key={actorKey} />}
          {screen === 'booking' && <Booking actor={actor} key={actorKey} onBusy={setBusy} />}
          {screen === 'wallet' && <Wallet actor={actor} key={actorKey} />}
          {screen === 'analytics' && <Analytics />}{screen === 'nearby' && <Nearby />}{screen === 'reviews' && <Reviews />}
        </div>
      </main>
      <footer><span>X 78.4867°E · Y 17.3850°N</span><span>RIDESYNC · TEAM 10 · ASSIGNMENT DEMO · INR · ASIA/KOLKATA</span></footer>
    </div>
  </div>
}
