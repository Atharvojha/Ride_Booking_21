import { useState } from 'react'
import { apiUrl, money, time } from '../api'
import { useQuery } from '../useQuery'
import { Dates, Feedback, Notice, Pager, Stat, Table } from '../components'

export default function Wallet({ actor }) {
  const [dates, setDates] = useState({ from: '', to: '' })
  const [page, setPage] = useState(1)
  const query = useQuery(actor ? apiUrl('/api/riders/' + actor.id + '/audit', { ...dates, page, pageSize: 25 }) : null)
  if (!actor) return <section className="card"><Notice>Choose a demo rider to see wallet history.</Notice></section>
  return <><section className="card"><div className="filters"><Dates value={dates} onChange={value => { setDates(value); setPage(1) }} />
    <button className="secondary" disabled={query.loading} onClick={query.reload}>Reload wallet</button></div>
    <p className="muted">Wallet history for <strong>{actor.name}</strong>. Dates use Asia/Kolkata.</p>
    <Feedback query={query} hasRows={true} />{query.data && <div className="stats"><Stat label="Current wallet" value={money(query.data.currentBalance)} /><Stat label="Opening balance for these dates" value={money(query.data.openingBalance)} note="Unknown means there is no earlier saved balance to use." /></div>}
  </section><section className="card"><h2>Wallet changes</h2><p className="muted">Each running balance is the value saved with that wallet change.</p>
    <Feedback query={query} hasRows={query.data?.items.length} empty="No wallet changes in these dates." />
    {query.data?.items.length > 0 && <Table label="Wallet audit trail" rows={query.data.items} columns={[{ key: 'timestamp', label: 'Recorded at', render: row => time(row.timestamp) }, { key: 'actionType', label: 'Action', render: row => row.actionType.replaceAll('_', ' ') }, { key: 'amountChanged', label: 'Change', render: row => <span className={Number(row.amountChanged) < 0 ? 'negative' : 'positive'}>{money(row.amountChanged)}</span> }, { key: 'balanceAfter', label: 'Running balance', render: row => money(row.balanceAfter) }]} />}
    {query.data && <Pager page={page} total={query.data.total} onPage={setPage} disabled={query.loading} />}
  </section></>
}
