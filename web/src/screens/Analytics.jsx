import { useState } from 'react'
import { apiUrl, money, request, shortId, time } from '../api'
import { useQuery } from '../useQuery'
import { ClassChip, Dates, Feedback, Icon, Notice, Pager, Picker, Stat, Table, ago, useNow } from '../components'

function Summary({ rows }) {
  const last = rows[rows.length - 1]
  if (!last) return null
  const daily = Number(last.dailyRevenue), average = Number(last.movingAverage7Days)
  const trend = daily > average ? 'above' : daily < average ? 'below' : 'level with'
  return <p className="insight"><span className={'trend ' + (daily > average ? 'up' : daily < average ? 'down' : '')}><Icon name={daily >= average ? 'up' : 'down'} size={14} strokeWidth={2} /></span>On {last.date}, revenue was <strong>{money(last.dailyRevenue)}</strong> — {trend} the 7-day average of <strong>{money(last.movingAverage7Days)}</strong>.</p>
}
import { RevenueChart } from '../charts'

export default function Analytics() {
  const now = useNow(30000)
  const [vehicle, setVehicle] = useState(null)
  const [dates, setDates] = useState({ from: '', to: '' })
  const [page, setPage] = useState(1)
  const [summaryPage, setSummaryPage] = useState(1)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshError, setRefreshError] = useState(null)
  const revenue = useQuery(apiUrl('/api/analytics/revenue', { vehicleId: vehicle?.id, ...dates, page, pageSize: 25 }))
  const summary = useQuery(apiUrl('/api/analytics/summary', { vehicleId: vehicle?.id, page: summaryPage, pageSize: 25 }))
  const chartVehicle = useQuery(revenue.data?.selectedVehicleId ? '/api/vehicles/' + revenue.data.selectedVehicleId : null)
  async function refresh() {
    if (refreshing) return
    setRefreshing(true); setRefreshError(null)
    try { await request('/api/analytics/refresh', { method: 'POST' }); summary.reload() }
    catch (error) { setRefreshError(error) }
    finally { setRefreshing(false) }
  }
  return <><section className="card"><div className="filters"><Picker kind="vehicles" label="Analytics vehicle" value={vehicle} optional onChange={value => { setVehicle(value); setPage(1); setSummaryPage(1); setRefreshError(null) }} />
    <Dates value={dates} onChange={value => { setDates(value); setPage(1) }} /><button className="secondary" disabled={revenue.loading} onClick={revenue.reload}><Icon name="refresh" size={16} />Reload revenue</button></div>
    <p className="muted">Default: last 30 days. Choose up to 90 calendar days. Dates use Asia/Kolkata.</p></section>
    <section className="card"><div className="card-head"><div><h2>Seven-day revenue average</h2>{revenue.data?.series.length > 0 && <Summary rows={revenue.data.series} />}</div>{revenue.loadedAt && <span className="freshness">Updated {ago(revenue.loadedAt, now)}</span>}</div><Feedback query={revenue} hasRows={revenue.data?.series.length} empty="No active vehicle is available for a chart." rows={4} />
      {revenue.data?.selectedVehicleId && <p className="muted">Chart vehicle: <strong>{chartVehicle.data?.vehicle.licensePlate || shortId(revenue.data.selectedVehicleId)}</strong>{!vehicle && ' (the first active vehicle). Choose an analytics vehicle above to chart another one. The ranking below covers the whole fleet.'}</p>}
      {revenue.data?.series.length > 0 && <RevenueChart rows={revenue.data.series} />}
    </section><section className="card"><h2>Daily vehicle ranking</h2><p className="muted">Click a plate to chart that vehicle. Rank is based on the seven-day average across the whole fleet. Equal averages share a rank. Vehicles with no revenue in the last seven days are greyed out.</p>
      <Feedback query={revenue} hasRows={revenue.data?.rankings.length} empty="No ranking rows match these dates." quiet />
      {revenue.data?.rankings.length > 0 && <Table label="Daily revenue ranks" rows={revenue.data.rankings} rowClass={row => [Number(row.dailyRevenue) === 0 && Number(row.movingAverage7Days) === 0 ? 'idle' : '', row.vehicleId === revenue.data.selectedVehicleId ? 'charted' : ''].join(' ').trim() || undefined} columns={[{ key: 'date', label: 'Date' }, { key: 'licensePlate', label: 'Vehicle', render: row => <button type="button" className="text-button plate" title="Chart this vehicle" onClick={() => { setVehicle({ id: row.vehicleId, licensePlate: row.licensePlate, class: row.class || 'vehicle' }); setPage(1); setSummaryPage(1); setRefreshError(null); window.scrollTo({ top: 0, behavior: 'smooth' }) }}>{row.licensePlate}</button> }, { key: 'dailyRevenue', label: 'Daily revenue', align: 'right', render: row => money(row.dailyRevenue) }, { key: 'movingAverage7Days', label: '7-day average', align: 'right', render: row => money(row.movingAverage7Days) }, { key: 'rank', label: 'Rank', align: 'right', render: row => <span className={'rank' + (row.rank <= 3 ? ' r' + row.rank : '')}>{row.rank}</span> }]} />}
      {revenue.data && <Pager page={page} total={revenue.data.total} onPage={setPage} disabled={revenue.loading} />}
    </section><section className="card"><div className="section-title spread"><div><h2>Lifetime vehicle totals</h2><p className="muted">All dates · Last successful refresh: {time(summary.data?.lastRefreshedAt)}</p></div>
      <button onClick={refresh} disabled={refreshing || summary.loading}>{refreshing ? 'Refreshing…' : 'Refresh totals'}</button></div>
      {refreshError && <Notice kind="error" onRetry={refresh}>{refreshError.message} The displayed totals may be out of date.</Notice>}
      <Feedback query={summary} hasRows={summary.data?.items.length} empty="No saved vehicle totals. Try refreshing." />
      {summary.data && <><div className="stats"><Stat label="Lifetime trips" value={summary.data.totals.lifetimeTripCount.toLocaleString('en-IN')} note="All statuses" /><Stat className="orb-stat-lite" label="Lifetime earnings" value={money(summary.data.totals.lifetimeEarnings)} note="Completed trips only" /></div>
        {summary.data.items.length > 0 && <Table label="Lifetime vehicle totals" rows={summary.data.items} columns={[{ key: 'licensePlate', label: 'Vehicle', render: row => <span className="plate">{row.licensePlate}</span> }, { key: 'class', label: 'Class', render: row => <ClassChip vehicleClass={row.class} /> }, { key: 'lifetimeTripCount', label: 'Trips (all statuses)', align: 'right' }, { key: 'lifetimeEarnings', label: 'Earnings (completed)', align: 'right', render: row => money(row.lifetimeEarnings) }]} />}
        <Pager page={summaryPage} total={summary.data.total} onPage={setSummaryPage} disabled={summary.loading} /></>}
    </section></>
}
