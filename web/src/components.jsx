import { useEffect, useId, useRef, useState } from 'react'
import { apiUrl, money, shortId } from './api'
import { useQuery } from './useQuery'

export function Icon({ name }) {
  const paths = {
    browse: 'M4 4h16v16H4z M4 10h16 M10 4v16',
    booking: 'M5 5h14v15H5z M8 2v6 M16 2v6 M8 13l3 3 5-6',
    wallet: 'M3 6h18v14H3z M3 6V4h15 M16 12h5v4h-5z',
    analytics: 'M4 3v17h17 M7 15l4-5 4 3 5-7',
    nearby: 'M12 21s7-7 7-12a7 7 0 0 0-14 0c0 5 7 12 7 12z M12 6a3 3 0 1 0 0 6 3 3 0 0 0 0-6',
    reviews: 'M12 3l3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z',
  }
  return <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>
}

export function Notice({ children, kind = 'info', onRetry }) {
  return <div className={'notice ' + kind} role={kind === 'error' ? 'alert' : 'status'}>
    <span>{children}</span>{onRetry && <button className="small secondary" onClick={onRetry}>Try again</button>}
  </div>
}

export function Feedback({ query, empty, hasRows, quiet = false }) {
  return <>{query.loading && <p className="muted" role="status">Loading…</p>}
    {query.error && !quiet && <Notice kind="error" onRetry={query.reload}>{query.error.message}{query.data ? ' Showing the last result; it may be out of date.' : ''}</Notice>}
    {!query.loading && !query.error && query.data && !hasRows && <div className="empty">{empty}</div>}</>
}

export function Pager({ page, pageSize = 25, total, onPage, disabled = false }) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  return <div className="pager"><span>{total.toLocaleString('en-IN')} records · Page {page} of {pages}</span>
    <div><button className="secondary" disabled={disabled || page <= 1} onClick={() => onPage(page - 1)}>Previous</button>
      <button className="secondary" disabled={disabled || page * pageSize >= total} onClick={() => onPage(page + 1)}>Next</button></div></div>
}

export function Table({ label, columns, rows, rowClass }) {
  return <div className="table-scroll" tabIndex="0" role="region" aria-label={label}>
    <table><caption className="sr-only">{label}</caption><thead><tr>{columns.map(column => <th key={column.key} scope="col" className={column.sticky ? 'sticky-end' : undefined}>{column.label}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={row.id || (row.vehicleId ? row.vehicleId + (row.date || '') : index)} className={rowClass?.(row)}>{columns.map(column => <td key={column.key} className={column.sticky ? 'sticky-end' : undefined}>{column.render ? column.render(row) : row[column.key]}</td>)}</tr>)}</tbody></table>
  </div>
}

export function Dates({ value, onChange }) {
  return <><label>From date<input type="date" value={value.from} onChange={event => onChange({ ...value, from: event.target.value })} /></label>
    <label>To date<input type="date" value={value.to} onChange={event => onChange({ ...value, to: event.target.value })} /></label></>
}

export function Stat({ label, value, note }) {
  return <div className="stat"><span>{label}</span><strong>{value}</strong>{note && <small>{note}</small>}</div>
}

export function Badge({ status }) {
  return <span className={'badge ' + (status === 'COMPLETED' || status === 'Active' ? 'green' : status === 'IN TRANSIT' ? 'blue' : 'amber')}>{status}</span>
}

export function Modal({ title, onClose, children, locked = false }) {
  const ref = useRef(null)
  const id = useId()
  useEffect(() => { const dialog = ref.current; dialog.showModal(); return () => dialog.close() }, [])
  return <dialog ref={ref} aria-labelledby={id} onCancel={event => { event.preventDefault(); if (!locked) onClose() }}>
    <div className="modal-heading"><h2 id={id}>{title}</h2><button className="secondary" disabled={locked} onClick={onClose} aria-label="Close dialog">×</button></div>
    {children}
  </dialog>
}

export function Picker({ kind, label, value, onChange, disabled = false, active, optional = false }) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const query = useQuery(open ? apiUrl('/api/' + kind, { search, page, pageSize: 10, active }) : null)
  const name = row => kind === 'riders' ? row.name : row.licensePlate + ' · ' + row.class
  function choose(row) { onChange(row); setOpen(false) }
  return <div className="picker"><span className="field-label">{label}</span>
    <button className="picker-button" aria-label={label + ": " + (value ? name(value) : "Choose")} disabled={disabled} onClick={() => { setSearch(''); setPage(1); setOpen(true) }}>
      <span>{value ? name(value) : optional ? 'All vehicles' : 'Choose ' + (kind === 'riders' ? 'a rider' : 'a vehicle')}</span><span aria-hidden="true">⌄</span></button>
    {open && <Modal title={label} onClose={() => setOpen(false)}>
      <label>Search {kind}<input autoFocus value={search} maxLength={100} placeholder={kind === 'riders' ? 'Name or rider ID' : 'Plate or vehicle ID'} onChange={event => { setSearch(event.target.value); setPage(1) }} /></label>
      {optional && <button className="secondary" onClick={() => choose(null)}>All vehicles</button>}
      <Feedback query={query} hasRows={query.data?.items.length} empty={'No ' + kind + ' match your search.'} />
      <ul className="choice-list">{query.data?.items.map(row => <li key={row.id}><button onClick={() => choose(row)}><strong>{name(row)}</strong><small>{shortId(row.id)}{kind === 'riders' ? ' · Wallet ' + money(row.walletBalance) : row.isActive ? ' · Active' : ' · Inactive'}</small></button></li>)}</ul>
      {query.data && <Pager page={page} pageSize={10} total={query.data.total} onPage={setPage} disabled={query.loading} />}
    </Modal>}
  </div>
}
