import { useState } from 'react'
import { apiUrl, money } from '../api'
import { useQuery } from '../useQuery'
import { Feedback, Icon, Notice, Pager, Stat, Table } from '../components'

const ACTIONS = { ESCROW_HOLD: 'Fare held for trip', ESCROW_RELEASE: 'Settled after trip' }
const istDay = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' })
const PRESETS = [['Today', 0], ['7 days', 6], ['30 days', 29]]
function daysAgo(n) { return istDay.format(new Date(Date.now() - n * 86400000)) }
const dayKey = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' })
const dayLabel = new Intl.DateTimeFormat('en-IN', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Kolkata' })
const clock = new Intl.DateTimeFormat('en-IN', { timeStyle: 'short', timeZone: 'Asia/Kolkata' })

function day(value) {
  const key = dayKey.format(new Date(value))
  if (key === dayKey.format(new Date())) return 'Today'
  if (key === dayKey.format(new Date(Date.now() - 86400000))) return 'Yesterday'
  return dayLabel.format(new Date(value))
}

function signed(value) {
  const number = Number(value)
  return number > 0 ? '+' + money(value) : number < 0 ? '−' + money(Math.abs(number)) : money(value)
}

export default function Wallet({ actor }) {
  const [dates, setDates] = useState({ from: '', to: '' })
  const [page, setPage] = useState(1)
  const query = useQuery(actor ? apiUrl('/api/riders/' + actor.id + '/audit', { ...dates, page, pageSize: 25 }) : null)
  if (!actor) return <section className="card"><Notice>Choose a demo rider to see wallet history.</Notice></section>
  const items = query.data?.items || []
  const today = daysAgo(0)
  const setRange = value => { setDates(value); setPage(1) }
  return <><section className="card">
    <div className="fare-chips date-presets" role="group" aria-label="Quick date ranges">{PRESETS.map(([name, n]) => <button key={name} type="button" className="small secondary" aria-pressed={dates.from === daysAgo(n) && dates.to === today} onClick={() => setRange({ from: daysAgo(n), to: today })}>{name}</button>)}
      <button type="button" className="small secondary" aria-pressed={!dates.from && !dates.to} onClick={() => setRange({ from: '', to: '' })}>All time</button></div>
    <div className="filters"><label>From date<input type="date" value={dates.from} max={dates.to || undefined} onChange={event => setRange({ ...dates, from: event.target.value })} /></label>
    <label>To date<input type="date" value={dates.to} min={dates.from || undefined} onChange={event => setRange({ ...dates, to: event.target.value })} /></label>
    {(dates.from || dates.to) && <button type="button" className="secondary" onClick={() => setRange({ from: '', to: '' })}>Clear dates</button>}
    <button className="secondary" disabled={query.loading} onClick={query.reload}><Icon name="refresh" size={16} />Reload wallet</button></div>
    <p className="muted">Wallet history for <strong>{actor.name}</strong>. Dates use Asia/Kolkata.</p>
    <Feedback query={query} hasRows={true} rows={2} />{query.data && <div className="stats"><div className="stat orb-stat"><span className="orb" aria-hidden="true" /><div><span>Current wallet</span><strong>{money(query.data.currentBalance)}</strong><small>Saved balance right now</small></div></div><Stat label="Opening balance for these dates" value={money(query.data.openingBalance)} note={query.data.openingBalance === null ? 'Unknown: there is no earlier saved balance to use.' : 'The saved balance just before these dates.'} /></div>}
  </section><section className="card"><div className="card-head"><div><h2>Wallet changes</h2><p className="muted">Each running balance is the value saved with that wallet change. "Held" is the fare taken when the trip was booked; "settled" closes the hold when the trip completes. Oldest first.</p></div></div>
    <Feedback query={query} hasRows={items.length} empty="No wallet changes in these dates." hint={dates.from || dates.to ? 'Clear the dates to see all history.' : 'Book a trip to create the first entry.'} quiet rows={5} />
    {items.length > 0 && <div className="ledger"><Table label="Wallet audit trail" rows={items}
      renderBefore={(row, index) => index === 0 || day(row.timestamp) !== day(items[index - 1].timestamp) ? day(row.timestamp) : null}
      columns={[
        { key: 'actionType', label: 'Action', render: row => { const amount = Number(row.amountChanged); return <span className="ledger-action"><span className={'ledger-icon ' + (amount < 0 ? 'debit' : amount > 0 ? 'credit' : '')}><Icon name={amount < 0 ? 'up' : amount > 0 ? 'down' : 'refresh'} size={15} strokeWidth={1.9} /></span><span>{ACTIONS[row.actionType] || 'Wallet change'}<small>{row.actionType.replaceAll('_', ' ')}</small></span></span> } },
        { key: 'timestamp', label: 'Recorded at', render: row => clock.format(new Date(row.timestamp)) },
        { key: 'amountChanged', label: 'Change', align: 'right', render: row => <span className={Number(row.amountChanged) > 0 ? 'positive' : 'negative'}>{signed(row.amountChanged)}</span> },
        { key: 'balanceAfter', label: 'Running balance', align: 'right', render: row => money(row.balanceAfter) }]} /></div>}
    {query.data && query.data.total > 0 && <Pager page={page} total={query.data.total} onPage={setPage} disabled={query.loading} />}
  </section></>
}
