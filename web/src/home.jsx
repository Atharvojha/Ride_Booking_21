import { useEffect, useRef, useState } from 'react'
import { Icon, Notice, classIcon } from './components'
import { AdminSignIn, RiderSignIn } from './session'

const steps = [
  { icon: 'booking', title: 'Choose a vehicle', text: 'Pick a class and an active vehicle, then enter a fare. The wallet charge is shown before you confirm.' },
  { icon: 'wallet', title: 'Book from your wallet', text: 'Confirming holds the fare in escrow. Each rider has one active trip at a time, so nothing is double-booked.' },
  { icon: 'analytics', title: 'Follow every rupee', text: 'Every wallet change is written to an audit trail, and the admin sees revenue and fleet rankings.' },
]
const views = [
  { id: 'rider', label: 'For riders', title: 'Book and track your own trips', points: ['Book a trip in three steps', 'My Wallet with a full audit trail', 'Your trips, and the vehicles you can book', 'Nearby vehicles on a live map and rider reviews'], cta: 'Use the rider view' },
  { id: 'admin', label: 'For admins', title: 'See and run the whole fleet', points: ['Browse every rider, vehicle and trip', 'Seven-day revenue averages and daily rankings', 'Refresh lifetime vehicle totals', 'Inspect any rider’s wallet history'], cta: 'Use the admin view' },
]
const fleet = ['Bike', 'Auto', 'Mini', 'Sedan', 'Prime Sedan', 'XL', 'SUV']

// A decorative city map with a route being drawn. It carries no data.
function RouteVisual() {
  return <div className="route-card" aria-hidden="true">
    <svg viewBox="0 0 560 320" preserveAspectRatio="xMidYMid slice">
      <path className="river" d="M-20 270 C 120 230, 220 300, 360 250 S 520 220, 600 250" />
      <rect className="park" x="226" y="150" width="86" height="64" rx="14" />
      <g className="roads">{[60, 135, 210, 285].map(y => <line key={y} x1="-10" x2="570" y1={y} y2={y} />)}{[70, 190, 320, 450].map(x => <line key={x} y1="-10" y2="330" x1={x} x2={x} />)}</g>
      <path className="route-base" d="M70 285 V210 H190 V135 H320 V60 H450" />
      <path className="route" d="M70 285 V210 H190 V135 H320 V60 H450" />
      <circle className="from" cx="70" cy="285" r="9" />
      <g transform="translate(450 60)"><circle className="ring" r="10" /><circle className="to" r="9" /></g>
    </svg>
    <div className="chip chip-a"><span className="chip-icon"><Icon name="check" size={14} strokeWidth={2.2} /></span><span><b>Trip booked</b><small>Fare held in escrow</small></span></div>
    <div className="chip chip-b"><span className="chip-icon"><Icon name="wallet" size={14} strokeWidth={2} /></span><span><b>Wallet audit</b><small>Every change recorded</small></span></div>
  </div>
}

export function Landing({ onSignedIn, error }) {
  const [tab, setTab] = useState('rider')
  const panel = useRef(null)
  const openPanel = which => {
    setTab(which)
    panel.current?.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center' })
  }
  useEffect(() => { document.title = 'RideSync · Book trips, track your wallet' }, [])
  return <div className="home">
    <header className="home-nav">
      <a className="home-brand" href="#top" aria-label="RideSync home"><span className="brand-mark" aria-hidden="true"><Icon name="nearby" size={16} strokeWidth={1.8} /></span><span>RIDE<b>SYNC</b></span></a>
      <nav aria-label="Site"><a href="#how">How it works</a><a href="#views">Rider &amp; admin</a><a href="#fleet">Fleet</a></nav>
      <a className="nav-signin" href="#signin" onClick={event => { event.preventDefault(); openPanel(tab) }}>Sign in</a>
    </header>
    <main id="main">
      <section className="hero" id="top">
        <div className="hero-copy">
          <p className="pill"><span className="pulse" aria-hidden="true" />Hyderabad fleet · live data</p>
          <h1>Every ride,<br />perfectly <em>in sync.</em></h1>
          <p className="lede">Book a trip, follow every rupee in your wallet, and run the whole fleet from one calm console.</p>
          <RouteVisual />
        </div>
        <aside className="hero-panel" id="signin" ref={panel} aria-labelledby="signin-title">
          <h2 id="signin-title">Welcome to RideSync</h2>
          <p className="panel-sub">Choose how you want to use it.</p>
          {error && <Notice kind="error">{error.message}</Notice>}
          <div className="seg" role="tablist" aria-label="Sign in as">
            {['rider', 'admin'].map(which => <button key={which} role="tab" id={'tab-' + which} aria-selected={tab === which} aria-controls="signin-body" tabIndex={tab === which ? 0 : -1}
              className={tab === which ? 'on' : ''} onClick={() => setTab(which)}
              onKeyDown={event => { if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') { event.preventDefault(); setTab(which === 'rider' ? 'admin' : 'rider'); document.getElementById('tab-' + (which === 'rider' ? 'admin' : 'rider'))?.focus() } }}>
              {which === 'rider' ? 'Rider' : 'Admin'}</button>)}
          </div>
          <div id="signin-body" role="tabpanel" aria-labelledby={'tab-' + tab}>
            {tab === 'rider' ? <RiderSignIn onSignedIn={onSignedIn} /> : <AdminSignIn onSignedIn={onSignedIn} />}
          </div>
        </aside>
      </section>

      <section className="band" id="how" aria-labelledby="how-title">
        <p className="kicker">How it works</p>
        <h2 id="how-title">From pickup to payout in three steps</h2>
        <ol className="steps">{steps.map((step, index) => <li key={step.title}>
          <span className="step-no">{String(index + 1).padStart(2, '0')}</span>
          <span className="step-icon"><Icon name={step.icon} size={22} strokeWidth={1.6} /></span>
          <h3>{step.title}</h3><p>{step.text}</p></li>)}</ol>
      </section>

      <section className="band alt" id="views" aria-labelledby="views-title">
        <p className="kicker">Two views, one console</p>
        <h2 id="views-title">The right tools for who you are</h2>
        <div className="views">{views.map(view => <article key={view.id} className={'view-card ' + view.id}>
          <p className="kicker">{view.label}</p><h3>{view.title}</h3>
          <ul>{view.points.map(point => <li key={point}><Icon name="check" size={16} strokeWidth={2.2} />{point}</li>)}</ul>
          <button className={view.id === 'admin' ? 'cta' : 'ghost'} onClick={() => openPanel(view.id)}>{view.cta}<Icon name="arrow" size={16} /></button>
        </article>)}</div>
      </section>

      <section className="band" id="fleet" aria-labelledby="fleet-title">
        <p className="kicker">The fleet</p>
        <h2 id="fleet-title">One fleet, every kind of ride</h2>
        <ul className="fleet">{fleet.map(name => <li key={name}><span><Icon name={classIcon(name)} size={26} strokeWidth={1.5} /></span>{name}</li>)}</ul>
      </section>
    </main>
    <footer className="home-foot"><span>RIDESYNC · TEAM 10 · ASSIGNMENT DEMO</span><span>INR · ASIA/KOLKATA</span></footer>
  </div>
}
