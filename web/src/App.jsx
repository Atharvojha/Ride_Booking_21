import { useEffect, useRef, useState } from 'react'
import { useQuery } from './useQuery'
import { Icon, Notice, Picker } from './components'
import Browse from './screens/Browse'
import Booking from './screens/Booking'
import Wallet from './screens/Wallet'
import Analytics from './screens/Analytics'
import Nearby from './screens/Nearby'
import Reviews from './screens/Reviews'

const screens = [
  { id: 'browse', title: 'Browse Data', description: 'Explore riders, vehicles and trips in your RideSync workspace.' },
  { id: 'booking', title: 'Book a Trip', description: 'Choose a rider and vehicle, then review the wallet charge.' },
  { id: 'wallet', title: 'Wallet Audit', description: 'Follow the saved wallet changes for your selected rider.' },
  { id: 'analytics', title: 'Vehicle Analytics', description: 'Explore revenue, daily rankings and lifetime vehicle totals.' },
  { id: 'nearby', title: 'Nearby Vehicles', description: 'Find fresh, available vehicles around a chosen origin.' },
  { id: 'reviews', title: 'Trip Reviews', description: 'Read rider feedback and explore vehicle features and inspections.' },
]

export default function App() {
  const [screen, setScreen] = useState('browse')
  const [actor, setActor] = useState(null)
  const [menu, setMenu] = useState(false)
  const [busy, setBusy] = useState(false)
  const heading = useRef(null)
  const initialRider = useQuery('/api/riders?pageSize=1')
  useEffect(() => { if (!actor && initialRider.data?.items.length) setActor(initialRider.data.items[0]) }, [actor, initialRider.data])
  useEffect(() => { heading.current?.focus() }, [screen])
  useEffect(() => {
    const close = event => { if (event.key === 'Escape') setMenu(false) }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [])
  const current = screens.find(item => item.id === screen)
  function navigate(value) { if (!busy) { setScreen(value); setMenu(false) } }
  return <div className="app"><a className="skip-link" href="#main">Skip to content</a>
    {menu && <button className="menu-backdrop" aria-label="Close navigation" onClick={() => setMenu(false)} />}
    <aside className={'sidebar ' + (menu ? 'open' : '')}><div className="brand"><span className="brand-icon">R</span>RideSync</div>
      <p className="nav-label">WORKSPACE</p><nav aria-label="Main navigation">{screens.map(item => <button key={item.id} disabled={busy} className={screen === item.id ? 'active' : ''} aria-current={screen === item.id ? 'page' : undefined} onClick={() => navigate(item.id)}><Icon name={item.id} />{item.title}</button>)}</nav>
      <div className="sidebar-note"><span className="live-dot" /><strong>Team 10 workspace</strong><small>Assignment demo · Local data</small></div></aside>
    <div className="workspace"><header className="topbar"><div className="breadcrumb"><button className="menu-button secondary" aria-label="Open navigation" aria-expanded={menu} onClick={() => setMenu(!menu)}>☰</button><span>Workspace</span><span aria-hidden="true">›</span><strong>{current.title}</strong></div>
      <div className="actor"><span className="avatar" aria-hidden="true">{actor?.name.slice(0, 1) || 'R'}</span><Picker kind="riders" label="Demo rider" value={actor} onChange={setActor} disabled={busy} /></div></header>
      <main id="main"><div className="page-heading"><div><p className="eyebrow">RIDESYNC / TEAM 10</p><h1 tabIndex="-1" ref={heading}>{current.title}</h1><p>{current.description}</p></div><span className="workspace-tag"><span className="live-dot" />Database workspace</span></div>
        {initialRider.error && !actor && <Notice kind="error" onRetry={initialRider.reload}>{initialRider.error.message}</Notice>}
        {busy && <Notice>Finish the current booking check before changing the rider or screen.</Notice>}
        {screen === 'browse' && <Browse actor={actor} key={actor?.id} />}
        {screen === 'booking' && <Booking actor={actor} key={actor?.id} onBusy={setBusy} />}
        {screen === 'wallet' && <Wallet actor={actor} key={actor?.id} />}
        {screen === 'analytics' && <Analytics />}{screen === 'nearby' && <Nearby />}{screen === 'reviews' && <Reviews />}
      </main><footer>RideSync · Team 10 <span>Assignment demo · INR · Asia/Kolkata</span></footer>
    </div>
  </div>
}
