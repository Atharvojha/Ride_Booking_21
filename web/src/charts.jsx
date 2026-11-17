import { useState } from 'react'
import { money } from './api'
import { Table } from './components'

const NEGATIVE = /NOT|RASH|LATE|RUDE|DIRTY|UNSAFE|BAD|POOR|DELAY|SMELL|LOUD|WRONG|OVER|UNCOMFORT|UNPROFESSIONAL|CANCEL|BROKEN|NOIS/i
export function isNegativeTag(tag) { return NEGATIVE.test(tag) }
export function tagLabel(tag) {
  const words = tag.replaceAll('_', ' ')
  if (words !== words.toUpperCase()) return words
  return words.toLowerCase().replace(/^./, letter => letter.toUpperCase()).replace(/\bac\b/gi, 'AC').replace(/\bwifi\b/gi, 'Wi-Fi')
}

export function RevenueChart({ rows }) {
  const [hover, setHover] = useState(null)
  if (!rows.length) return <p className="muted">No chart data is available.</p>
  const peak = Math.max(1, ...rows.flatMap(row => [Number(row.dailyRevenue), Number(row.movingAverage7Days)]))
  const step = (() => { const raw = peak / 3, power = 10 ** Math.floor(Math.log10(raw)); return [1, 2, 2.5, 5, 10].map(f => f * power).find(v => v >= raw) })()
  const maximum = step * Math.ceil(peak / step)
  const activeDays = rows.filter(row => Number(row.dailyRevenue) > 0).length
  const left = 58, right = 612, top = 42, bottom = 212
  const x = index => left + index * (right - left) / Math.max(1, rows.length - 1)
  const y = value => bottom - Number(value) * (bottom - top) / maximum
  const line = field => rows.map((row, index) => (index ? 'L' : 'M') + x(index).toFixed(1) + ',' + y(row[field]).toFixed(1)).join(' ')
  const area = line('movingAverage7Days') + ` L${x(rows.length - 1)},${bottom} L${x(0)},${bottom} Z`
  function track(event) {
    const box = event.currentTarget.getBoundingClientRect()
    const position = (event.clientX - box.left) / box.width * 640
    setHover(Math.max(0, Math.min(rows.length - 1, Math.round((position - left) / ((right - left) / Math.max(1, rows.length - 1))))))
  }
  const point = hover === null ? null : rows[hover]
  return <><div className="legend"><span><i className="daily" />Daily revenue</span><span><i />7-day average</span></div>
    <div className="chart-wrap">
      <svg className="revenue-chart" viewBox="0 0 640 260" role="img" aria-label="Daily revenue and seven-day average chart" onPointerMove={track} onPointerLeave={() => setHover(null)}>
        <title>Daily revenue and seven-day average</title><desc>Exact values are in the table below the chart.</desc>
        <defs><linearGradient id="revenueFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#FF5BA8" stopOpacity=".32" /><stop offset="100%" stopColor="#8E7BFF" stopOpacity="0" /></linearGradient>
          <linearGradient id="revenueStroke" x1="0" x2="1" y1="0" y2="0"><stop offset="0%" stopColor="#FFB36B" /><stop offset="55%" stopColor="#FF5BA8" /><stop offset="100%" stopColor="#8E7BFF" /></linearGradient></defs>
        {Array.from({ length: Math.round(maximum / step) + 1 }, (_, index) => index * step).map(value => <g key={value}><line className="grid" x1={left} x2={right} y1={y(value)} y2={y(value)} /><text x="50" y={y(value) + 4} textAnchor="end">₹{value.toLocaleString('en-IN')}</text></g>)}
        <path className="area" d={area} />
        {rows.map((row, index) => { const slot = (right - left) / Math.max(1, rows.length - 1), width = Math.max(2, Math.min(18, slot * 0.6)); return Number(row.dailyRevenue) > 0 && <rect key={row.date} className="bar" x={x(index) - width / 2} y={y(row.dailyRevenue)} width={width} height={bottom - y(row.dailyRevenue)} rx="2" /> })}
        <path className="avg" d={line('movingAverage7Days')} fill="none" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
        {rows.length === 1 && <circle className="dot" cx={x(0)} cy={y(rows[0].movingAverage7Days)} r="4" />}
        {point && <g><line className="cursor" x1={x(hover)} x2={x(hover)} y1={top - 10} y2={bottom} /><circle className="dot" cx={x(hover)} cy={y(point.movingAverage7Days)} r="5" /></g>}
        {[...new Set([0, Math.floor((rows.length - 1) / 2), rows.length - 1])].map(index => <text key={index} x={x(index)} y="242" textAnchor={index === 0 ? 'start' : index === rows.length - 1 ? 'end' : 'middle'}>{rows[index].date}</text>)}
        <rect x={left} y={top - 10} width={right - left} height={bottom - top + 10} fill="transparent" />
      </svg>
      {point && <div className="chart-tooltip" aria-hidden="true" style={{ left: Math.min(88, Math.max(12, x(hover) / 6.4)) + '%' }}><b>{point.date}</b>Daily {money(point.dailyRevenue)} · 7-day {money(point.movingAverage7Days)}</div>}
    </div>
    <p className="muted">{activeDays} of {rows.length} days had completed trips. Values in INR; days without completed trips count as zero.</p>
    <details><summary>View chart values</summary><Table label="Revenue chart values" rows={rows} columns={[{ key: 'date', label: 'Date' }, { key: 'dailyRevenue', label: 'Daily revenue', align: 'right', render: row => money(row.dailyRevenue) }, { key: 'movingAverage7Days', label: '7-day average', align: 'right', render: row => money(row.movingAverage7Days) }]} /></details>
  </>
}

export function RatingChart({ rows }) {
  const maximum = Math.max(1, ...rows.map(row => row.count))
  const total = rows.reduce((sum, row) => sum + row.count, 0) || 1
  return <div className="rating-bars" role="img" aria-label="Review counts by rating">{[...rows].sort((a, b) => b.rating - a.rating).map(row => <div className="rating-row" key={row.rating}>
    <span>{row.rating} star{row.rating === 1 ? '' : 's'}</span><div className="bar-track"><div style={{ width: row.count * 100 / maximum + '%' }} /></div><strong title={Math.round(row.count * 100 / total) + '%'}>{row.count}</strong>
  </div>)}</div>
}

export function TagChart({ rows }) {
  const maximum = Math.max(1, ...rows.map(row => row.count))
  return <div role="img" aria-label="Review counts by feedback tag">{rows.map(row => <div className={'rating-row tag-row' + (isNegativeTag(row.tag) ? ' negative-tag' : '')} key={row.tag}>
    <span className="wrap">{tagLabel(row.tag)}</span><div className="bar-track"><div style={{ width: row.count * 100 / maximum + '%' }} /></div><strong>{row.count}</strong>
  </div>)}</div>
}
