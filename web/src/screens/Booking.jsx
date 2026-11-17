import { useEffect, useRef, useState } from 'react'
import { apiUrl, fareInPaise, fixedFare, money, request, shortId, time } from '../api'
import { useQuery } from '../useQuery'
import { Badge, Feedback, Icon, Notice, Picker, SplitFlap, Table, classIcon } from '../components'

const WAIT = 15000
const ACTIONS = { ESCROW_HOLD: 'Held for trip', ESCROW_RELEASE: 'Released after trip' }
const CLASSES = ['Bike', 'Auto', 'Mini', 'Sedan', 'Prime Sedan', 'XL', 'SUV']

function ClassCard({ value, selected, onPick, disabled }) {
  const count = useQuery(apiUrl('/api/vehicles', { active: true, class: value, pageSize: 1 }))
  if (count.data && count.data.total === 0) return null
  return <button type="button" className="class-card" aria-pressed={selected} disabled={disabled} onClick={() => onPick(selected ? '' : value)}>
    <Icon name={classIcon(value)} size={30} strokeWidth={1.7} />{value}<small>{count.data ? count.data.total.toLocaleString('en-IN') + ' active' : ' '}</small></button>
}

function CountdownRing({ remaining }) {
  const radius = 26, circumference = 2 * Math.PI * radius
  const fraction = Math.max(0, Math.min(1, remaining / WAIT))
  return <div className="ring-wrap" aria-hidden="true"><svg className="ring" viewBox="0 0 60 60">
    <circle className="track" cx="30" cy="30" r={radius} />
    <circle className="progress" cx="30" cy="30" r={radius} strokeDasharray={circumference} strokeDashoffset={circumference * (1 - fraction)} />
  </svg><span>{Math.ceil(remaining / 1000)}</span></div>
}

function firstName(name) { return name.split(' ')[0] }

export default function Booking({ actor, onBusy }) {
  const [vehicleClass, setVehicleClass] = useState('')
  const [vehicle, setVehicle] = useState(null)
  const [fare, setFare] = useState('')
  const [review, setReview] = useState(false)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(null)
  const [unknown, setUnknown] = useState(null)
  const [saved, setSaved] = useState(null)
  const [now, setNow] = useState(Date.now())
  const submitting = useRef(false)
  const resultHeading = useRef(null)
  const ticketRef = useRef(null)
  const wallet = useQuery(actor ? '/api/riders/' + actor.id : null)
  const history = useQuery(actor ? apiUrl('/api/trips', { riderId: actor.id, pageSize: 10 }) : null)
  const amount = fareInPaise(fare)
  const balance = wallet.data?.rider.walletBalance
  const balancePaise = balance === undefined ? null : Math.round(Number(balance) * 100)
  const insufficient = !success && amount !== null && balancePaise !== null && !wallet.error && amount > balancePaise
  const activeTrip = history.data?.items.find(trip => trip.status !== 'COMPLETED')
  const recentFares = [...new Set((history.data?.items || []).map(trip => trip.fareAmount))].slice(0, 3)
  const locked = pending || Boolean(unknown)
  useEffect(() => { onBusy(pending || Boolean(unknown)); return () => onBusy(false) }, [pending, unknown, onBusy])
  useEffect(() => {
    if (!unknown) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [unknown])
  useEffect(() => { if (success || unknown) resultHeading.current?.focus() }, [success, unknown])
  useEffect(() => {
    if (!review || !ticketRef.current) return
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    ticketRef.current.scrollIntoView?.({ block: 'center', behavior: still ? 'auto' : 'smooth' })
    ticketRef.current.focus({ preventScroll: true })
  }, [review])
  function edit(action) { action(); setReview(false); setError(null); setSuccess(null) }
  function pickClass(value) { edit(() => { setVehicleClass(value); if (value && vehicle?.class !== value) setVehicle(null) }) }
  async function book() {
    if (submitting.current || !review || amount === null || !vehicle || !actor || unknown) return
    submitting.current = true; setPending(true); setError(null)
    const submittedAt = Date.now()
    try {
      const result = await request('/api/trips', { method: 'POST', body: {
        riderId: actor.id, vehicleId: vehicle.id, fareAmount: fixedFare(fare) } })
      setSuccess(result); setReview(false); wallet.reload(); history.reload()
      navigator.vibrate?.(10)
    } catch (failure) {
      setError(failure)
      if (failure.uncertain) { setNow(Date.now()); setUnknown({ checkAfter: Date.now() + WAIT, submittedAt, vehicleId: vehicle.id, fare: fixedFare(fare) }) }
    } finally { submitting.current = false; setPending(false) }
  }
  async function checkSaved() {
    if (pending || now < unknown.checkAfter) return
    setPending(true); setError(null); setSaved(null)
    try {
      const [rider, trips] = await Promise.all([request('/api/riders/' + actor.id),
        request(apiUrl('/api/trips', { riderId: actor.id, pageSize: 5 }))])
      const match = trips.items.find(trip => trip.vehicleId === unknown.vehicleId && trip.fareAmount === unknown.fare &&
        Date.parse(trip.createdAt) >= unknown.submittedAt - 60000)
      setSaved({ rider: rider.rider, trips: trips.items, match }); wallet.reload(); history.reload()
    } catch (failure) { setError(failure) }
    finally { setPending(false) }
  }
  if (!actor) return <section className="card"><Notice>Choose a demo rider in the header before booking.</Notice></section>
  const projected = amount !== null && balancePaise !== null && !wallet.error ? (balancePaise - amount < 0 ? 'SHORT ' + money(((amount - balancePaise) / 100).toFixed(2)) : money(((balancePaise - amount) / 100).toFixed(2))) : null
  const remaining = unknown ? Math.max(0, unknown.checkAfter - now) : 0
  return <><div className="two-columns"><section className="card">
    <div className="section-title"><span className="step-number">1</span><div><h2>Trip details</h2><p className="muted">Pick a class, a vehicle and a demo fare.</p></div></div>
    <div className="booking-for"><span className="avatar" aria-hidden="true">{actor.name.slice(0, 1)}</span><span>Booking for <strong>{actor.name}</strong></span></div>
    <Feedback query={wallet} hasRows={true} rows={1} />
    <div className="class-cards" role="group" aria-label="Filter vehicles by class">{CLASSES.map(value => <ClassCard key={value} value={value} selected={vehicleClass === value} onPick={pickClass} disabled={locked} />)}</div>
    <Picker kind="vehicles" label="Active vehicle" active={true} params={vehicleClass ? { class: vehicleClass } : {}} value={vehicle} onChange={value => edit(() => setVehicle(value))} disabled={locked} />
    <label className="fare-field">Demo fare (INR)<input value={fare} inputMode="decimal" placeholder="0.00" disabled={locked} maxLength={11} onChange={event => edit(() => setFare(event.target.value))} /></label>
    {recentFares.length > 0 && !locked && !success && <div className="fare-chips" role="group" aria-label="Recent fares for this rider"><span>Recent fares</span>
      {recentFares.map(value => <button key={value} type="button" className="small secondary" aria-pressed={fixedFare(fare) === value} onClick={() => edit(() => setFare(value))}>{money(value)}</button>)}</div>}
    <p className="muted">Enter a positive fare with up to two decimal places. This demo does not estimate a route.</p>
    {fare && amount === null && <Notice kind="error">Enter a fare between ₹0.01 and ₹99,999,999.99, with at most two decimal places.</Notice>}
    {activeTrip && !success && !unknown && <Notice kind="warning">{actor.name} already has a trip {activeTrip.status === 'REQUESTED' ? 'requested' : 'in transit'} ({activeTrip.licensePlate}). Complete it in Browse Data before booking another.</Notice>}
    {insufficient && <Notice kind="warning">{money(((amount - balancePaise) / 100).toFixed(2))} short. The wallet has {money(balance)}, so this booking will be refused.</Notice>}
    {error && !(review && !unknown) && <Notice kind="error">{error.message}</Notice>}
    {!unknown && !success && !review && <button className="wide glow" disabled={!vehicle || amount === null || !wallet.data || wallet.loading || Boolean(wallet.error)} onClick={() => setReview(true)}>Review booking <Icon name="arrow" size={16} /></button>}
  </section>
  <div className="booking-side">
    <section className="board" aria-label="Wallet preview">
      <div className="board-head"><span>Wallet · {firstName(actor.name)}</span><span className="live"><span className="live-dot" />Live</span></div>
      <div className="stat"><span>Current balance</span><strong><SplitFlap value={wallet.error ? 'UNAVAILABLE' : balance === undefined ? '—' : money(balance)} /></strong></div>
      <div className="board-row">
        <div className="stat"><span>Demo fare</span><strong><SplitFlap size="small" value={amount === null ? '—' : '−' + money(fixedFare(fare))} /></strong></div>
        <div className="stat to"><span>{success ? 'Saved balance after booking' : 'Projected balance'}</span><strong><SplitFlap size="small" value={success ? money(success.balanceAfter) : projected === null ? '—' : projected} /></strong></div>
      </div>
      <span className="muted">{success ? 'These are the saved balances from your booking.' : 'An estimate. The saved balances appear after you confirm.'} One requested or in-transit trip per rider.</span>
    </section>
    {review && !success && !unknown && <section className="ticket review" aria-label="Confirm your booking" tabIndex="-1" ref={ticketRef}>{error ? <span className="stamp declined">DECLINED</span> : <span className="stamp">REVIEW</span>}
      <div className="ticket-top"><div className="ticket-label">Boarding pass · RideSync</div>
        <h3 className="sr-only">Confirm your booking</h3>
        <div className="ticket-route"><span>{firstName(actor.name)}</span><i /><span>{vehicle.class}</span></div>
        <div className="ticket-meta"><div>Plate<b>{vehicle.licensePlate}</b></div><div>Wallet now<b>{money(balance)}</b></div><div>Status<b>Not booked</b></div></div>
        <p className="sr-only">{actor.name} · {vehicle.licensePlate} · {money(fixedFare(fare))}</p></div>
      {error && <Notice kind="error">{error.message}</Notice>}
      <div className="ticket-stub"><div className="barcode" aria-hidden="true" /><div className="ticket-total">Held from wallet<b>{money(fixedFare(fare))}</b></div></div>
      <div className="ticket-actions"><button onClick={book} disabled={pending}>{pending ? 'Booking…' : 'Confirm booking'}</button><button className="secondary" disabled={pending} onClick={() => setReview(false)}>Edit details</button></div>
      {pending && <p className="muted pending-note" role="status">Saving your booking — please keep this page open.</p>}
    </section>}
    {success && <section className="ticket success-card"><span className="stamp booked">BOOKED</span>
      <div className="ticket-top"><div className="ticket-label">Boarding pass · Trip {shortId(success.trip.id)}</div>
        <h2 tabIndex="-1" ref={resultHeading}>Trip booked</h2>
        <div className="ticket-route"><span>{firstName(actor.name)}</span><i /><span>{vehicle?.class || 'Vehicle'}</span></div></div>
      <dl className="record"><div><dt>Trip ID</dt><dd className="id wrap">{success.trip.id}</dd></div><div><dt>Status</dt><dd><Badge status={success.trip.status} /></dd></div><div><dt>Balance before</dt><dd>{money(success.balanceBefore)}</dd></div><div><dt>Balance after</dt><dd>{money(success.balanceAfter)}</dd></div>
        <div><dt>Audit entry ID</dt><dd className="id wrap">{success.auditEntry.id}</dd></div><div><dt>Wallet change</dt><dd>{money(success.auditEntry.amountChanged)} · {ACTIONS[success.auditEntry.actionType] || 'Wallet change'} <code className="db-value">{success.auditEntry.actionType.replaceAll('_', ' ')}</code></dd></div><div><dt>Recorded at</dt><dd>{time(success.auditEntry.timestamp)}</dd></div>
        <div><dt>Written by</dt><dd><code className="db-value">trg_wallet_audit</code> → <code className="db-value">wallet_audit_logs</code></dd></div></dl>
      <div className="ticket-stub"><div className="barcode" aria-hidden="true" /><div className="ticket-total">Held from wallet<b>{money(success.auditEntry.amountChanged.replace('-', ''))}</b></div></div>
      <div className="actions"><button onClick={() => { setSuccess(null); setFare(''); setReview(false) }}>Prepare another booking</button></div></section>}
  </div></div>
    {unknown && <section className="card pending-card"><h2 tabIndex="-1" ref={resultHeading}>Check the saved result</h2>
      <Notice kind="warning">Don't book again yet. We do not know whether the booking was saved. Wait briefly, then read this rider's trips and wallet before continuing.</Notice>
      {now < unknown.checkAfter && <div className="countdown"><CountdownRing remaining={remaining} /><div className="countdown-value"><strong>Giving the database time to finish</strong>Checking is available in {Math.ceil(remaining / 1000)} seconds.</div></div>}
      <button disabled={pending || now < unknown.checkAfter} onClick={checkSaved}>{pending ? 'Checking…' : now < unknown.checkAfter ? 'Check available in ' + Math.ceil((unknown.checkAfter - now) / 1000) + ' seconds' : 'Check trips and wallet'}</button>
      {saved && <><div style={{ height: 16 }} />
        {saved.match ? <Notice kind="success">Found it. A matching trip was saved at {time(saved.match.createdAt)} for {money(saved.match.fareAmount)}. Don't book it again.</Notice> :
          <Notice>No matching trip was found in the latest saved trips. Check the wallet and trips below before trying again.</Notice>}
        <div className="stats"><div className="stat"><span>Current saved wallet</span><strong>{money(saved.rider.walletBalance)}</strong></div></div>
        <Table label="Recently saved rider trips" rows={saved.trips} columns={[{ key: 'id', label: 'Trip', render: row => <span className="id">{shortId(row.id)}</span> }, { key: 'licensePlate', label: 'Vehicle', render: row => <span className="plate">{row.licensePlate}</span> }, { key: 'fareAmount', label: 'Fare', align: 'right', render: row => money(row.fareAmount) }, { key: 'status', label: 'Status', render: row => <Badge status={row.status} /> }, { key: 'createdAt', label: 'Booked at', render: row => time(row.createdAt) }]} />
        <p className="muted">These are saved records, not a guessed booking result. An active trip must be completed before another booking.</p>
        <button className="secondary" disabled={pending} onClick={() => { setUnknown(null); setSaved(null); setError(null); setReview(false) }}>Continue after checking</button></>}
    </section>}
  </>
}
