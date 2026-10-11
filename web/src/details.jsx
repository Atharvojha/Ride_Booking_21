import { useState } from 'react'
import { money, request, time } from './api'
import { useQuery } from './useQuery'
import { Badge, Feedback, Modal, Notice } from './components'

function label(value) { return value.replaceAll('_', ' ').replace(/([a-z])([A-Z])/g, '$1 $2') }
function display(value) {
  if (value === true) return 'Yes'
  if (value === false) return 'No'
  if (value === null || value === undefined) return 'Not recorded'
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value) && !Number.isNaN(Date.parse(value))) return time(value)
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

export function Metadata({ data, error, retry }) {
  if (error) return <Notice kind="error" onRetry={retry}>{error.message}</Notice>
  if (!data) return <p className="muted">No vehicle metadata is recorded.</p>
  const features = Object.entries(data.features || {}).filter(([, value]) => value === true)
  return <><h3>Vehicle features</h3>
    {features.length ? <div className="tags">{features.map(([key]) => <span key={key}>{label(key)}</span>)}</div> : <p className="muted">No features listed.</p>}
    <h3>Inspection records</h3>
    {data.inspectionRecords?.length ? data.inspectionRecords.map((record, index) => <div className="inspection" key={index}>
      <strong>Inspection {index + 1}</strong>{record && typeof record === 'object' && !Array.isArray(record) ?
        <dl>{Object.entries(record).map(([key, value]) => <div key={key}><dt>{label(key)}</dt><dd className="wrap">{display(value)}</dd></div>)}</dl> : <p>{display(record)}</p>}
    </div>) : <p className="muted">No inspections recorded.</p>}
  </>
}

export function MetadataCard({ vehicle }) {
  const query = useQuery(vehicle ? '/api/vehicles/' + vehicle.id : null)
  return <section className="card"><h2>Vehicle metadata</h2>
    {!vehicle ? <p className="muted">Choose a vehicle to see its features and inspections.</p> : <>
      <Feedback query={query} hasRows={true} />{query.data && <Metadata data={query.data.metadata} error={query.data.metadataError} retry={query.reload} />}
    </>}
  </section>
}

export function DetailDialog({ kind, id, onClose, onChanged }) {
  const query = useQuery('/api/' + kind + '/' + id)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)
  const [uncertain, setUncertain] = useState(false)
  const record = query.data?.[kind === 'riders' ? 'rider' : kind === 'vehicles' ? 'vehicle' : 'trip']
  async function changeStatus() {
    if (pending || uncertain) return
    setPending(true); setError(null)
    try {
      await request('/api/trips/' + id + '/status', { method: 'PATCH', body: {
        status: record.status === 'REQUESTED' ? 'IN TRANSIT' : 'COMPLETED' } })
      query.reload(); onChanged()
    } catch (failure) { setError(failure); setUncertain(failure.uncertain) }
    finally { setPending(false) }
  }
  async function checkStatus() {
    setPending(true)
    try { await request('/api/trips/' + id); setUncertain(false); setError(null); query.reload(); onChanged() }
    catch (failure) { setError(failure) }
    finally { setPending(false) }
  }
  return <Modal title={kind === 'riders' ? 'Rider details' : kind === 'vehicles' ? 'Vehicle details' : 'Trip details'} onClose={onClose} locked={pending}>
    <Feedback query={query} hasRows={true} />
    {record && <dl className="record">{Object.entries(record).map(([key, value]) => <div key={key}><dt>{label(key)}</dt><dd className="wrap">{key === 'walletBalance' || key === 'fareAmount' ? money(value) : key === 'createdAt' ? time(value) : key === 'status' ? <Badge status={value} /> : display(value)}</dd></div>)}</dl>}
    {kind === 'vehicles' && query.data && <Metadata data={query.data.metadata} error={query.data.metadataError} retry={query.reload} />}
    {error && <Notice kind="error">{error.message}</Notice>}
    {kind === 'trips' && record && !query.error && !query.loading && record.status !== 'COMPLETED' &&
      <button disabled={pending || uncertain} onClick={changeStatus}>{pending ? 'Saving…' : record.status === 'REQUESTED' ? 'Start trip' : 'Complete trip'}</button>}
    {uncertain && <button className="secondary" disabled={pending} onClick={checkStatus}>Check saved trip status</button>}
  </Modal>
}
