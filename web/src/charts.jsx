import { money } from './api'
import { Table } from './components'

export function RevenueChart({ rows }) {
  if (!rows.length) return <p className="muted">No chart data is available.</p>
  const maximum = Math.max(1, ...rows.flatMap(row => [Number(row.dailyRevenue), Number(row.movingAverage7Days)]))
  const x = index => 58 + index * 554 / Math.max(1, rows.length - 1)
  const y = value => 212 - Number(value) * 170 / maximum
  const line = field => rows.map((row, index) => (index ? 'L' : 'M') + x(index) + ',' + y(row[field])).join(' ')
  return <><div className="legend"><span><i className="daily" />Daily revenue</span><span><i />7-day average</span></div>
    <svg className="revenue-chart" viewBox="0 0 640 260" role="img" aria-label="Daily revenue and seven-day average chart">
      <title>Daily revenue and seven-day average</title><desc>Exact values are in the table below the chart.</desc>
      {[0, 0.5, 1].map(value => <g key={value}><line x1="58" x2="612" y1={y(maximum * value)} y2={y(maximum * value)} stroke="#e4e8f1" /><text x="48" y={y(maximum * value) + 4} textAnchor="end">{Math.round(maximum * value).toLocaleString('en-IN')}</text></g>)}
      <path d={line('dailyRevenue')} fill="none" stroke="#9eaec9" strokeWidth="2" />
      <path d={line('movingAverage7Days')} fill="none" stroke="#3567e8" strokeWidth="3" />
      {rows.length === 1 && <circle cx={x(0)} cy={y(rows[0].movingAverage7Days)} r="4" fill="#3567e8" />}
      {[...new Set([0, Math.floor((rows.length - 1) / 2), rows.length - 1])].map(index => <text key={index} x={x(index)} y="242" textAnchor={index === 0 ? 'start' : index === rows.length - 1 ? 'end' : 'middle'}>{rows[index].date}</text>)}
    </svg><p className="muted">Values in INR. Days without completed trips count as zero.</p>
    <details><summary>View chart values</summary><Table label="Revenue chart values" rows={rows} columns={[{ key: 'date', label: 'Date' }, { key: 'dailyRevenue', label: 'Daily revenue', render: row => money(row.dailyRevenue) }, { key: 'movingAverage7Days', label: '7-day average', render: row => money(row.movingAverage7Days) }]} /></details>
  </>
}

export function RatingChart({ rows }) {
  const maximum = Math.max(1, ...rows.map(row => row.count))
  return <div className="rating-bars" role="img" aria-label="Review counts by rating">{rows.map(row => <div className="rating-row" key={row.rating}>
    <span>{row.rating} star{row.rating === 1 ? '' : 's'}</span><div className="bar-track"><div style={{ width: row.count * 100 / maximum + '%' }} /></div><strong>{row.count}</strong>
  </div>)}</div>
}

export function TagChart({ rows }) {
  const maximum = Math.max(1, ...rows.map(row => row.count))
  return <div role="img" aria-label="Review counts by feedback tag">{rows.map(row => <div className="rating-row tag-row" key={row.tag}>
    <span className="wrap">{row.tag}</span><div className="bar-track"><div style={{ width: row.count * 100 / maximum + '%' }} /></div><strong>{row.count}</strong>
  </div>)}</div>
}
