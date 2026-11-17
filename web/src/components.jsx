import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { apiUrl, money, shortId, time } from './api'
import { useQuery } from './useQuery'

const paths = {
  browse: 'M4 5.5A1.5 1.5 0 0 1 5.5 4h13A1.5 1.5 0 0 1 20 5.5v13a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5z M4 10h16 M10 10v10',
  booking: 'M5 7.5A2.5 2.5 0 0 1 7.5 5h9A2.5 2.5 0 0 1 19 7.5v10a2.5 2.5 0 0 1-2.5 2.5h-9A2.5 2.5 0 0 1 5 17.5z M9 3v4 M15 3v4 M9 13.5l2 2 4-4.5',
  wallet: 'M4 7.5A2.5 2.5 0 0 1 6.5 5H18v3 M4 7.5v10A2.5 2.5 0 0 0 6.5 20H20V8H6.5A2.5 2.5 0 0 1 4 5.5 M16 14h.01',
  analytics: 'M4 4v16h16 M8 15l3.5-4 3 2.5L20 7',
  nearby: 'M12 21s7-6.2 7-11.5a7 7 0 0 0-14 0C5 14.8 12 21 12 21z M12 12.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  reviews: 'M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z',
  sun: 'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M12 2.5v2 M12 19.5v2 M4.6 4.6l1.4 1.4 M18 18l1.4 1.4 M2.5 12h2 M19.5 12h2 M4.6 19.4L6 18 M18 6l1.4-1.4',
  moon: 'M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z',
  menu: 'M4 7h16 M4 12h16 M4 17h10',
  chevron: 'M7 10l5 5 5-5',
  check: 'M5 12.5l4.5 4.5L19 7.5',
  alert: 'M12 8v5 M12 16.5h.01 M10.3 3.9L2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  info: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 11v5 M12 7.5h.01',
  arrow: 'M5 12h14 M13 6l6 6-6 6',
  down: 'M12 5v14 M6 13l6 6 6-6',
  up: 'M12 19V5 M6 11l6-6 6 6',
  refresh: 'M20 11a8 8 0 0 0-14.3-4.9L4 8 M4 4v4h4 M4 13a8 8 0 0 0 14.3 4.9L20 16 M20 20v-4h-4',
  inbox: 'M3 13l3-8h12l3 8 M3 13v5a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5 M3 13h5l1.5 3h5L16 13h5',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 7v5l3 2',
  bike: 'M5.5 18a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M18.5 18a3 3 0 1 0 0-6 3 3 0 0 0 0 6z M5.5 15l4-7h5l4 7 M9.5 8L8 5.5H6 M14.5 8l1-2.5H18',
  auto: 'M4 16V9.5A4.5 4.5 0 0 1 8.5 5H15l4 6v5 M3 16h18 M7 18.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4z M17 18.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4z M11 5v6h8',
  car: 'M5 16.5V12l2-5h10l2 5v4.5 M3.5 16.5h17 M7.5 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z M16.5 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z M5 12h14',
  suv: 'M3.5 16.5V11l2.5-5h11l3.5 5v5.5 M2.5 16.5h19 M7.5 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z M16.5 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z M3.5 11h17 M11.5 6v5',
}

export function Icon({ name, size = 20, strokeWidth = 1.6 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}

export function classIcon(vehicleClass = '') {
  const value = vehicleClass.toLowerCase()
  if (value.includes('bike')) return 'bike'
  if (value.includes('auto')) return 'auto'
  if (value.includes('suv') || value.includes('xl')) return 'suv'
  return 'car'
}

export function ClassChip({ vehicleClass }) {
  return <span className="class-chip"><Icon name={classIcon(vehicleClass)} size={18} />{vehicleClass}</span>
}

export function Notice({ children, kind = 'info', onRetry }) {
  const icon = kind === 'error' || kind === 'warning' ? 'alert' : kind === 'success' ? 'check' : 'info'
  return <div className={'notice ' + kind} role={kind === 'error' ? 'alert' : 'status'}>
    <span><Icon name={icon} size={16} strokeWidth={1.8} /><span>{children}</span></span>{onRetry && <button className="small secondary" onClick={onRetry}>Try again</button>}
  </div>
}

export function Skeleton({ rows = 3 }) {
  return <div className="skeleton-rows" role="status"><span className="sr-only">Loading…</span>
    {Array.from({ length: rows }, (_, index) => <div key={index} className="skeleton row" style={{ opacity: 1 - index * 0.18 }} />)}</div>
}

export function Feedback({ query, empty, hint, hasRows, quiet = false, rows = 3 }) {
  return <>{query.loading && !query.data && <Skeleton rows={rows} />}
    {query.error && !quiet && <Notice kind="error" onRetry={query.reload}>{query.error.message}{query.data ? ' Showing the last result; it may be out of date.' : ''}</Notice>}
    {!query.loading && !query.error && query.data && !hasRows && <div className="empty"><Icon name="inbox" size={26} strokeWidth={1.4} />{empty}{hint && <small>{hint}</small>}</div>}</>
}

export function Pager({ page, pageSize = 25, total, onPage, disabled = false }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return <div className="pager"><span>{total.toLocaleString('en-IN')} records · Page {page} of {pages}</span>
    <div><button className="secondary" disabled={disabled || page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
      <button className="secondary" disabled={disabled || page * pageSize >= total} onClick={() => onPage(page + 1)}>Next</button></div></div>
}

export function Table({ label, columns, rows, rowClass, renderBefore, onRowClick, dim = false }) {
  const cell = column => [column.sticky ? 'sticky-end' : '', column.align === 'right' ? 'amount' : ''].join(' ').trim() || undefined
  return <div className={'table-scroll' + (dim ? ' dim' : '')} tabIndex="0" role="region" aria-label={label} aria-busy={dim || undefined} aria-hidden={dim || undefined} inert={dim || undefined}>
    <table><caption className="sr-only">{label}</caption><thead><tr>{columns.map(column => <th key={column.key} scope="col" className={cell(column)}>{column.label}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => {
        const key = row.id || (row.vehicleId ? row.vehicleId + (row.date || '') : index)
        const before = renderBefore?.(row, index)
        const line = <tr key={key} className={[rowClass?.(row), onRowClick ? 'clickable' : ''].join(' ').trim() || undefined} onClick={onRowClick ? event => { if (!event.target.closest('button, a, input')) onRowClick(row) } : undefined}>{columns.map(column => <td key={column.key} className={cell(column)}>{column.render ? column.render(row) : row[column.key]}</td>)}</tr>
        return before ? [<tr key={key + '-before'} className="day-row"><th colSpan={columns.length} scope="colgroup">{before}</th></tr>, line] : line
      })}</tbody></table>
  </div>
}

export function Dates({ value, onChange }) {
  return <><label>From date<input type="date" value={value.from} onChange={event => onChange({ ...value, from: event.target.value })} /></label>
    <label>To date<input type="date" value={value.to} onChange={event => onChange({ ...value, to: event.target.value })} /></label></>
}

export function Stat({ label, value, note, hero = false, className = '', children }) {
  return <div className={'stat ' + (hero ? 'hero-card ' : '') + className}><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}{children}</div>
}

export function Badge({ status }) {
  const tone = status === 'COMPLETED' || status === 'Active' ? 'green' : status === 'IN TRANSIT' ? 'blue' : status === 'Inactive' ? 'grey' : 'amber'
  return <span className={'badge ' + tone}>{status}</span>
}

export function Stars({ value, size = 16 }) {
  return <span className="stars" aria-hidden="true">{[1, 2, 3, 4, 5].map(index => <svg key={index} width={size} height={size} viewBox="0 0 24 24" className={value >= index - 0.25 ? '' : 'off'} fill="currentColor"><path d={paths.reviews} /></svg>)}</span>
}

function prefers(query) { return typeof window !== 'undefined' && window.matchMedia?.(query).matches }

export function Modal({ title, onClose, children, locked = false }) {
  const ref = useRef(null)
  const timer = useRef(null)
  const id = useId()
  const [closing, setClosing] = useState(false)
  useEffect(() => { const dialog = ref.current; dialog.showModal(); return () => { clearTimeout(timer.current); dialog.close() } }, [])
  // Play the exit before unmounting; it never blocks focus or navigation for long.
  const close = useCallback(after => {
    if (closing) return
    setClosing(true)
    const delay = prefers('(prefers-reduced-motion: reduce)') ? 0 : prefers('(max-width: 760px)') ? 240 : 140
    timer.current = setTimeout(() => (typeof after === 'function' ? after : onClose)(), delay)
  }, [closing, onClose])
  return <dialog ref={ref} aria-labelledby={id} data-closing={closing || undefined} onCancel={event => { event.preventDefault(); if (!locked) close() }}
    onClick={event => {
      if (event.target !== ref.current || locked) return
      const box = ref.current.getBoundingClientRect()
      if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) close()
    }}>
    <div className="sheet-handle" aria-hidden="true" />
    <div className="modal-heading"><h2 id={id}>{title}</h2><button className="icon-button" disabled={locked} onClick={() => close()} aria-label="Close dialog">×</button></div>
    {typeof children === 'function' ? children(close) : children}
  </dialog>
}

export function Picker({ kind, label, value, onChange, disabled = false, active, optional = false, title, params = {} }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const query = useQuery(open ? apiUrl('/api/' + kind, { search, page, pageSize: 10, active, ...params }) : null)
  const name = row => kind === 'riders' ? row.name : row.licensePlate + ' · ' + row.class
  return <div className="picker"><span className="field-label">{label}</span>
    <button className="picker-button" title={title} aria-label={label + ": " + (value ? name(value) : "Choose")} disabled={disabled} onClick={() => { setSearch(''); setPage(1); setOpen(true) }}>
      <span>{value ? name(value) : optional ? 'All vehicles' : 'Choose ' + (kind === 'riders' ? 'a rider' : 'a vehicle')}</span><span className="chev"><Icon name="chevron" size={16} /></span></button>
    {open && <Modal title={label} onClose={() => setOpen(false)}>{close => <>
      <label>Search {kind}<input autoFocus value={search} maxLength={100} placeholder={kind === 'riders' ? 'Name or rider ID' : 'Plate or vehicle ID'} onChange={event => { setSearch(event.target.value); setPage(1) }} /></label>
      {optional && <button className="secondary" onClick={() => { onChange(null); close(() => setOpen(false)) }}>All vehicles</button>}
      <Feedback query={query} hasRows={query.data?.items.length} empty={'No ' + kind + ' match your search.'} rows={4} />
      <ul className="choice-list">{query.data?.items.map(row => <li key={row.id}><button onClick={() => { onChange(row); close(() => setOpen(false)) }}>
        <span><strong>{name(row)}</strong><small>{shortId(row.id)}{kind === 'riders' ? ' · Wallet ' + money(row.walletBalance) : row.isActive ? ' · Active' : ' · Inactive'}</small></span>
        {kind === 'vehicles' && <Icon name={classIcon(row.class)} />}</button></li>)}</ul>
      {query.data && <Pager page={page} pageSize={10} total={query.data.total} onPage={setPage} disabled={query.loading} />}
    </>}</Modal>}
  </div>
}

export function useNow(interval = 1000) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), interval); return () => clearInterval(timer) }, [interval])
  return now
}

export function ago(value, now = Date.now()) {
  if (!value) return 'Unknown'
  const seconds = Math.max(0, Math.round((now - Date.parse(value)) / 1000))
  if (seconds < 5) return 'just now'
  if (seconds < 60) return seconds + 's ago'
  if (seconds < 3600) return Math.floor(seconds / 60) + ' min ago'
  if (seconds < 86400) return Math.floor(seconds / 3600) + ' h ago'
  return time(value)
}

/* Counts a money value from `from` to `to` once, after a user action. Works in paise. */
export function CountUp({ from, to }) {
  const [shown, setShown] = useState(from ?? to)
  useEffect(() => {
    if (from === null || from === undefined || prefers('(prefers-reduced-motion: reduce)')) { setShown(to); return }
    const start = Math.round(Number(from) * 100), end = Math.round(Number(to) * 100)
    let frame, begin
    const step = stamp => {
      begin ??= stamp
      const t = Math.min(1, (stamp - begin) / 650)
      setShown(((start + (end - start) * (1 - (1 - t) ** 3)) / 100).toFixed(2))
      if (t < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [from, to])
  return <><span aria-hidden="true">{money(shown)}</span><span className="sr-only">{money(to)}</span></>
}

/* Split-flap departure-board digits. Characters that change flip once. */
export function SplitFlap({ value, size = 'big' }) {
  const text = String(value)
  const [flips, setFlips] = useState({ value: text, key: 0, changed: [] })
  useEffect(() => {
    setFlips(old => {
      if (old.value === text) return old
      const before = old.value.padStart(text.length, ' ')
      return { value: text, key: old.key + 1, changed: text.split('').map((char, index) => char !== before[index]) }
    })
  }, [text])
  const ready = flips.value === text
  return <span className={'flap ' + size}>{text.split('').map((char, index) => {
    const flip = ready && flips.changed[index]
    return <span key={index + '-' + (flip ? flips.key : 0)} className={flip ? 'flip' : undefined} style={flip ? { animationDelay: index * 35 + 'ms' } : undefined}>{char}</span>
  })}</span>
}
