import { useState } from 'react'
import { apiUrl, money, request, shortId, time } from '../api'
import { useQuery } from '../useQuery'
import { Dates, Feedback, Notice, Pager, Picker, Stat, Table } from '../components'
import { RevenueChart } from '../charts'

export default function Analytics() {
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
    <Dates value={dates} onChange={value => { setDates(value); setPage(1) }} /><button className="secondary" disabled={revenue.loading} onClick={revenue.reload}>Reload revenue</button></div>
    <p className="muted">Default: last 30 days. Choose up to 90 calendar days. Dates use Asia/Kolkata.</p></section>
    <section className="card"><h2>Seven-day revenue average</h2><Feedback query={revenue} hasRows={revenue.data?.series.length} empty="No active vehicle is available for a chart." />
      {revenue.data?.selectedVehicleId && <p className="muted">Chart vehicle: <strong>{chartVehicle.data?.vehicle.licensePlate || shortId(revenue.data.selectedVehicleId)}</strong>{!vehicle && ' (the first active vehicle). Choose an analytics vehicle above to chart another one. The ranking below covers the whole fleet.'}</p>}
      {revenue.data?.series.length > 0 && <RevenueChart rows={revenue.data.series} />}
    </section><section className="card"><h2>Daily vehicle ranking</h2><p className="muted">Rank is based on the seven-day average across the whole fleet. Equal averages share a rank. Vehicles with no revenue in the last seven days are greyed out.</p>
      <Feedback query={revenue} hasRows={revenue.data?.rankings.length} empty="No ranking rows match these dates." quiet />
      {revenue.data?.rankings.length > 0 && <Table label="Daily revenue ranks" rows={revenue.data.rankings} rowClass={row => Number(row.dailyRevenue) === 0 && Number(row.movingAverage7Days) === 0 ? 'idle' : undefined} columns={[{ key: 'date', label: 'Date' }, { key: 'licensePlate', label: 'Vehicle' }, { key: 'dailyRevenue', label: 'Daily revenue', render: row => money(row.dailyRevenue) }, { key: 'movingAverage7Days', label: '7-day average', render: row => money(row.movingAverage7Days) }, { key: 'rank', label: 'Rank' }]} />}
      {revenue.data && <Pager page={page} total={revenue.data.total} onPage={setPage} disabled={revenue.loading} />}
    </section><section className="card"><div className="section-title spread"><div><h2>Lifetime vehicle totals</h2><p className="muted">All dates · Last successful refresh: {time(summary.data?.lastRefreshedAt)}</p></div>
      <button onClick={refresh} disabled={refreshing || summary.loading}>{refreshing ? 'Refreshing…' : 'Refresh totals'}</button></div>
      {refreshError && <Notice kind="error" onRetry={refresh}>{refreshError.message} The displayed totals may be out of date.</Notice>}
      <Feedback query={summary} hasRows={summary.data?.items.length} empty="No saved vehicle totals. Try refreshing." />
      {summary.data && <><div className="stats"><Stat label="Lifetime trips" value={summary.data.totals.lifetimeTripCount.toLocaleString('en-IN')} note="All statuses" /><Stat label="Lifetime earnings" value={money(summary.data.totals.lifetimeEarnings)} note="Completed trips only" /></div>
        {summary.data.items.length > 0 && <Table label="Lifetime vehicle totals" rows={summary.data.items} columns={[{ key: 'licensePlate', label: 'Vehicle' }, { key: 'class', label: 'Class' }, { key: 'lifetimeTripCount', label: 'Trips (all statuses)' }, { key: 'lifetimeEarnings', label: 'Earnings (completed)', render: row => money(row.lifetimeEarnings) }]} />}
        <Pager page={summaryPage} total={summary.data.total} onPage={setSummaryPage} disabled={summary.loading} /></>}
    </section></>
}
