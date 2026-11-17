import { useEffect, useRef, useState } from 'react'
import { useQuery } from './useQuery'
import { Icon, Notice, Picker } from './components'
import Browse from './screens/Browse'
import Booking from './screens/Booking'
import Wallet from './screens/Wallet'
import Analytics from './screens/Analytics'
import Nearby from './screens/Nearby'
import Reviews from './screens/Reviews'

// `source` names the real database object behind each screen (shown as console telemetry).
const screens = [
  { id: 'browse', title: 'Browse Data', short: 'Browse', source: 'riders · vehicles · trips', engine: 'PostgreSQL', description: 'Explore riders, vehicles and trips in your RideSync workspace.' },
  { id: 'booking', title: 'Book a Trip', short: 'Book', source: 'CALL sp_book_trip()', engine: 'PostgreSQL', description: 'Choose a rider and vehicle, then review the wallet charge.' },
  { id: 'wallet', title: 'Wallet Audit', short: 'Wallet', source: 'wallet_audit_logs', engine: 'PostgreSQL trigger', description: 'Follow the saved wallet changes for your selected rider.' },
  { id: 'analytics', title: 'Vehicle Analytics', short: 'Analytics', source: 'AVG() OVER 7 days · DENSE_RANK() · mv_vehicle_lifetime_stats', engine: 'PostgreSQL', description: 'Explore revenue, daily rankings and lifetime vehicle totals.' },
  { id: 'nearby', title: 'Nearby Vehicles', short: 'Nearby', source: '$geoNear · TelemetryPings', engine: 'MongoDB', description: 'Find fresh, available vehicles around a chosen origin.' },
  { id: 'reviews', title: 'Trip Reviews', short: 'Reviews', source: '$facet · TripReviews · VehicleMetadata', engine: 'MongoDB', description: 'Read rider feedback and explore vehicle features and inspections.' },
]
const LOCKED = 'Locked until the last booking result has been checked'
const clock = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' })

function Clock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => { const timer = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(timer) }, [])
  return <span className="clock" aria-label="Time in Hyderabad">HYDERABAD <b>{clock.format(now)}</b> IST</span>
}

export default function App() {
  const [screen, setScreen] = useState('browse')
  const [actor, setActor] = useState(null)
  const [menu, setMenu] = useState(false)
  const [busy, setBusy] = useState(false)
  const heading = useRef(null)
  const initialRider = useQuery('/api/riders?pageSize=1')
  useEffect(() => { if (!actor && initialRider.data?.items.length) setActor(initialRider.data.items[0]) }, [actor, initialRider.data])
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
      <div className="actor"><span className="avatar" aria-hidden="true">{actor?.name.slice(0, 1) || 'R'}</span><Picker kind="riders" label="Demo rider" value={actor} onChange={setActor} disabled={busy} title={busy ? LOCKED : undefined} /></div>
    </header>
    <div className="workspace">
      <main id="main">
        <div className="page-heading">
          <div><p className="eyebrow"><span>{String(index + 1).padStart(2, '0')}</span>{current.short}</p><h1 tabIndex="-1" ref={heading}>{current.title}</h1><p>{current.description}</p></div>
          <pre className="telemetry" aria-label={'Data source: ' + current.source}>{`// ${current.engine}\nSOURCE  ${current.source}\nRIDER   ${actor ? actor.name.toUpperCase() : '—'}\nSTATUS  ${busy ? 'LOCKED · CHECKING BOOKING' : 'NOMINAL'}`}</pre>
        </div>
        {initialRider.error && !actor && <Notice kind="error" onRetry={initialRider.reload}>{initialRider.error.message}</Notice>}
        {busy && <Notice kind="warning">Finish the current booking check before changing the rider or screen.</Notice>}
        <div className="screen" key={screen}>
          {screen === 'browse' && <Browse actor={actor} key={actor?.id} />}
          {screen === 'booking' && <Booking actor={actor} key={actor?.id} onBusy={setBusy} />}
          {screen === 'wallet' && <Wallet actor={actor} key={actor?.id} />}
          {screen === 'analytics' && <Analytics />}{screen === 'nearby' && <Nearby />}{screen === 'reviews' && <Reviews />}
        </div>
      </main>
      <footer><span>X 78.4867°E · Y 17.3850°N</span><span>RIDESYNC · TEAM 10 · ASSIGNMENT DEMO · INR · ASIA/KOLKATA</span></footer>
    </div>
  </div>
}
