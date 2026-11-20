import { useEffect, useRef, useState } from 'react'
import { apiUrl, money, shortId, time } from '../api'
import { useQuery } from '../useQuery'
import { Badge, ClassChip, Icon, Dates, Feedback, Pager, Table } from '../components'
import { DetailDialog } from '../details'

export default function Browse({ actor, role = 'admin' }) {
  // Riders see their own trips and the fleet; admins also see every rider.
  const kinds = role === 'admin' ? ['riders', 'vehicles', 'trips'] : ['trips', 'vehicles']
  const [kind, setKind] = useState(kinds[0])
  const [search, setSearch] = useState('')
  const [typed, setTyped] = useState('')
  const [active, setActive] = useState('')
  const [vehicleClass, setVehicleClass] = useState('')
  const [status, setStatus] = useState('')
  const [mine, setMine] = useState(false)
  const [dates, setDates] = useState({ from: '', to: '' })
  const [page, setPage] = useState(1)
  const [detail, setDetail] = useState(null)
  const params = kind === 'trips' ? { status, ...dates, riderId: mine || role !== 'admin' ? actor?.id : null } :
    kind === 'vehicles' ? { search, active, class: vehicleClass } : { search }
  const query = useQuery(apiUrl('/api/' + kind, { ...params, page, pageSize: 25 }))
  useEffect(() => { if (typed === search) return; const timer = setTimeout(() => { setSearch(typed); setPage(1) }, 250); return () => clearTimeout(timer) }, [typed, search])
  // Keep the last rows on screen (dimmed) while the next page or search loads, instead of flashing a skeleton.
  const last = useRef({ kind: null, data: null })
  if (query.data) last.current = { kind, data: query.data }
  const shown = query.data || (query.loading && last.current.kind === kind ? last.current.data : null)
  const view = { ...query, data: shown }
  function reset(action) { action(); setPage(1) }
  const columns = [{ key: 'id', label: 'ID', render: row => <span className="id" title={row.id}>{shortId(row.id)}</span> }]
  if (kind === 'riders') columns.push({ key: 'name', label: 'Rider', render: row => <strong>{row.name}</strong> }, { key: 'walletBalance', label: 'Wallet balance', align: 'right', render: row => money(row.walletBalance) })
  if (kind === 'vehicles') columns.push({ key: 'licensePlate', label: 'License plate', render: row => <span className="plate">{row.licensePlate}</span> }, { key: 'class', label: 'Class', render: row => <ClassChip vehicleClass={row.class} /> }, { key: 'isActive', label: 'Fleet status', render: row => <Badge status={row.isActive ? 'Active' : 'Inactive'} /> })
  if (kind === 'trips') columns.push({ key: 'riderName', label: 'Rider' }, { key: 'licensePlate', label: 'Vehicle', render: row => <span className="plate">{row.licensePlate}</span> },
    { key: 'fareAmount', label: 'Fare', align: 'right', render: row => money(row.fareAmount) }, { key: 'status', label: 'Status', render: row => <Badge status={row.status} /> },
    { key: 'createdAt', label: 'Booked at', render: row => time(row.createdAt) })
  columns.push({ key: 'details', label: 'Details', sticky: true, render: row => <button className="text-button" onClick={() => setDetail(row.id)} aria-label={'Open details for ' + (row.name || row.licensePlate || shortId(row.id))}>Details →</button> })
  return <section className="card browse-card"><div className="tabs" role="group" aria-label="Browse entities" style={{ '--count': kinds.length, '--index': kinds.indexOf(kind) }}>
    <span className="seg-indicator" aria-hidden="true" />
    {kinds.map(value => <button className={kind === value ? 'selected' : ''} aria-pressed={kind === value} key={value} onClick={() => reset(() => { setKind(value); setDetail(null); setTyped(''); setSearch('') })}>{value[0].toUpperCase() + value.slice(1)}</button>)}</div>
    <div className="filters">
      {kind !== 'trips' && <label className="grow">Search {kind}<input placeholder={kind === 'riders' ? 'Name or rider ID' : 'License plate or vehicle ID'} value={typed} maxLength={100} onChange={event => setTyped(event.target.value)} /></label>}
      {kind === 'vehicles' && <><label>Fleet status<select value={active} onChange={event => reset(() => setActive(event.target.value))}><option value="">All vehicles</option><option value="true">Active</option><option value="false">Inactive</option></select></label>
        <label>Vehicle class<input value={vehicleClass} maxLength={30} placeholder="All classes" onChange={event => reset(() => setVehicleClass(event.target.value))} /></label></>}
      {kind === 'trips' && <><label>Trip status<select value={status} onChange={event => reset(() => setStatus(event.target.value))}><option value="">All statuses</option>{['REQUESTED', 'IN TRANSIT', 'COMPLETED'].map(value => <option key={value}>{value}</option>)}</select></label>
        <Dates value={dates} onChange={value => reset(() => setDates(value))} />
        {role === 'admin' && <label className="checkbox"><input type="checkbox" checked={mine} disabled={!actor} onChange={event => reset(() => setMine(event.target.checked))} />Selected rider only</label>}</>}
      <button className="secondary" onClick={query.reload} disabled={query.loading}><Icon name="refresh" size={16} />Reload</button>
    </div>
    <div className="card-body"><Feedback query={view} hasRows={shown?.items.length} empty="No records match these filters." hint="Clear the search or filters to see every record." rows={6} />
      {shown?.items.length > 0 && <Table label={'Browse ' + kind} columns={columns} rows={shown.items} dim={query.loading} onRowClick={row => setDetail(row.id)} />}
      {shown && <Pager page={page} total={shown.total} onPage={setPage} disabled={query.loading} />}</div>
    {detail && <DetailDialog kind={kind} id={detail} onClose={() => setDetail(null)} onChanged={query.reload} />}
  </section>
}
