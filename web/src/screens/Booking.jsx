import { useEffect, useRef, useState } from 'react'
import { apiUrl, fareInPaise, fixedFare, money, request, shortId, time } from '../api'
import { useQuery } from '../useQuery'
import { Badge, Feedback, Notice, Picker, Stat, Table } from '../components'

export default function Booking({ actor, onBusy }) {
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
  const wallet = useQuery(actor ? '/api/riders/' + actor.id : null)
  const amount = fareInPaise(fare)
  const balance = wallet.data?.rider.walletBalance
  const insufficient = !success && amount !== null && balance !== undefined && !wallet.error && amount > Math.round(Number(balance) * 100)
  useEffect(() => { onBusy(pending || Boolean(unknown)); return () => onBusy(false) }, [pending, unknown, onBusy])
  useEffect(() => {
    if (!unknown) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [unknown])
  function edit(action) { action(); setReview(false); setError(null); setSuccess(null) }
  async function book() {
    if (submitting.current || !review || amount === null || !vehicle || !actor || unknown) return
    submitting.current = true; setPending(true); setError(null)
    try {
      const result = await request('/api/trips', { method: 'POST', body: {
        riderId: actor.id, vehicleId: vehicle.id, fareAmount: fixedFare(fare) } })
      setSuccess(result); setReview(false); wallet.reload()
    } catch (failure) {
      setError(failure)
      if (failure.uncertain) setUnknown({ checkAfter: Date.now() + 15000 })
    } finally { submitting.current = false; setPending(false) }
  }
  async function checkSaved() {
    if (pending || now < unknown.checkAfter) return
    setPending(true); setError(null); setSaved(null)
    try {
      const [rider, trips] = await Promise.all([request('/api/riders/' + actor.id),
        request(apiUrl('/api/trips', { riderId: actor.id, pageSize: 5 }))])
      setSaved({ rider: rider.rider, trips: trips.items }); wallet.reload()
    } catch (failure) { setError(failure) }
    finally { setPending(false) }
  }
  if (!actor) return <section className="card"><Notice>Choose a demo rider in the header before booking.</Notice></section>
  return <><div className="two-columns"><section className="card"><div className="section-title"><span className="step-number">1</span><div><h2>Trip details</h2><p className="muted">Choose a vehicle and enter a demo fare.</p></div></div>
    <p>Booking for <strong>{actor.name}</strong></p><Feedback query={wallet} hasRows={true} />
    <Picker kind="vehicles" label="Active vehicle" active={true} value={vehicle} onChange={value => edit(() => setVehicle(value))} disabled={pending || Boolean(unknown)} />
    <label>Demo fare (INR)<input value={fare} inputMode="decimal" placeholder="e.g. 120.00" disabled={pending || Boolean(unknown)} maxLength={11} onChange={event => edit(() => setFare(event.target.value))} /></label>
    <p className="muted">Enter a positive fare with up to two decimal places. This demo does not estimate a route.</p>
    {fare && amount === null && <Notice kind="error">Enter a fare between ₹0.01 and ₹99,999,999.99, with at most two decimal places.</Notice>}
    {error && <Notice kind="error">{error.message}</Notice>}
    {!unknown && !success && (!review ? <button disabled={!vehicle || amount === null || !wallet.data || wallet.loading || Boolean(wallet.error)} onClick={() => setReview(true)}>Review booking</button> :
      <div className="review"><h3>Confirm your booking</h3><p>{actor.name} · {vehicle.licensePlate} · {money(fixedFare(fare))}</p>
        <div className="button-row"><button onClick={book} disabled={pending}>{pending ? 'Booking…' : 'Confirm booking'}</button><button className="secondary" disabled={pending} onClick={() => setReview(false)}>Edit details</button></div></div>)}
  </section><section className="card"><h2>Wallet preview</h2><Stat label="Current balance" value={wallet.error ? 'Unavailable' : money(balance)} />
    <Stat label="Demo fare" value={amount === null ? '—' : money(fixedFare(fare))} />
    <Stat label={success ? "Saved balance after booking" : "Projected balance"} value={success ? money(success.balanceAfter) : amount !== null && balance !== undefined && !wallet.error ? money(((Math.round(Number(balance) * 100) - amount) / 100).toFixed(2)) : '—'} note={success ? 'These are the saved balances from your booking.' : 'An estimate. The saved balances appear after you confirm.'} />
    {insufficient && <p className="muted">The fare is more than this rider's wallet balance, so the booking will be refused.</p>}
    <p className="muted">A rider can have one requested or in-transit trip at a time.</p></section></div>
    {success && <section className="card success-card"><h2>Trip booked</h2><Notice kind="success">Your trip was saved. The wallet change and audit entry below came from this booking.</Notice>
      <dl className="record"><div><dt>Trip ID</dt><dd className="id wrap">{success.trip.id}</dd></div><div><dt>Status</dt><dd><Badge status={success.trip.status} /></dd></div><div><dt>Balance before</dt><dd>{money(success.balanceBefore)}</dd></div><div><dt>Balance after</dt><dd>{money(success.balanceAfter)}</dd></div>
        <div><dt>Audit entry ID</dt><dd className="id wrap">{success.auditEntry.id}</dd></div><div><dt>Wallet change</dt><dd>{money(success.auditEntry.amountChanged)} · {success.auditEntry.actionType.replaceAll('_', ' ')}</dd></div><div><dt>Recorded at</dt><dd>{time(success.auditEntry.timestamp)}</dd></div></dl>
      <button className="secondary" onClick={() => { setSuccess(null); setFare(''); setReview(false) }}>Prepare another booking</button></section>}
    {unknown && <section className="card"><h2>Check the saved result</h2><Notice>We do not know whether the booking was saved. Wait briefly, then read this rider's trips and wallet before continuing.</Notice>
      <button disabled={pending || now < unknown.checkAfter} onClick={checkSaved}>{pending ? 'Checking…' : now < unknown.checkAfter ? 'Check available in ' + Math.ceil((unknown.checkAfter - now) / 1000) + ' seconds' : 'Check trips and wallet'}</button>
      {saved && <><Stat label="Current saved wallet" value={money(saved.rider.walletBalance)} />
        <Table label="Recently saved rider trips" rows={saved.trips} columns={[{ key: 'id', label: 'Trip', render: row => shortId(row.id) }, { key: 'licensePlate', label: 'Vehicle' }, { key: 'fareAmount', label: 'Fare', render: row => money(row.fareAmount) }, { key: 'status', label: 'Status' }, { key: 'createdAt', label: 'Booked at', render: row => time(row.createdAt) }]} />
        <p className="muted">These are saved records, not a guessed booking result. An active trip must be completed before another booking.</p>
        <button className="secondary" disabled={pending} onClick={() => { setUnknown(null); setSaved(null); setError(null); setReview(false) }}>Continue after checking</button></>}
    </section>}
  </>
}
