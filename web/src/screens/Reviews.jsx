import { useState } from 'react'
import { apiUrl, shortId, time } from '../api'
import { useQuery } from '../useQuery'
import { Dates, Feedback, Pager, Picker, Stat, Table } from '../components'
import { RatingChart, TagChart } from '../charts'
import { MetadataCard } from '../details'

export default function Reviews() {
  const [vehicle, setVehicle] = useState(null)
  const [dates, setDates] = useState({ from: '', to: '' })
  const [page, setPage] = useState(1)
  const params = { vehicleId: vehicle?.id, ...dates }
  const summary = useQuery(apiUrl('/api/reviews/summary', params))
  const reviews = useQuery(apiUrl('/api/reviews', { ...params, page, pageSize: 25 }))
  return <><section className="card"><div className="filters"><Picker kind="vehicles" label="Review vehicle" optional value={vehicle} onChange={value => { setVehicle(value); setPage(1) }} />
    <Dates value={dates} onChange={value => { setDates(value); setPage(1) }} /><button className="secondary" disabled={summary.loading || reviews.loading} onClick={() => { summary.reload(); reviews.reload() }}>Reload reviews</button></div></section>
    <section className="card"><h2>What riders are saying</h2><Feedback query={summary} hasRows={summary.data?.reviewCount} empty="No reviews match these filters." />
      {summary.data && <><div className="stats"><Stat label="Average rating" value={summary.data.averageRating === null ? 'No ratings' : summary.data.averageRating.toFixed(2) + ' / 5'} /><Stat label="Reviews" value={summary.data.reviewCount.toLocaleString('en-IN')} /></div>
        <div className="two-columns"><div><h3>Rating distribution</h3><RatingChart rows={summary.data.ratingDistribution} /></div><div><h3>Top feedback tags</h3><TagChart rows={summary.data.topTags} />{!summary.data.topTags.length && <p className="muted">No feedback tags.</p>}</div></div></>}
    </section><section className="card"><h2>Trip reviews</h2><Feedback query={reviews} hasRows={reviews.data?.items.length} empty="No individual reviews to show." />
      {reviews.data?.items.length > 0 && <Table label="Trip reviews" rows={reviews.data.items} columns={[{ key: 'tripId', label: 'Trip ID', render: row => <span className="id" title={row.tripId}>{shortId(row.tripId)}</span> }, { key: 'rating', label: 'Rating', render: row => row.rating + ' / 5' }, { key: 'feedbackTags', label: 'Feedback', render: row => row.feedbackTags.join(', ') || '—' }, { key: 'createdAt', label: 'Posted at', render: row => time(row.createdAt) }]} />}
      {reviews.data && <Pager page={page} total={reviews.data.total} onPage={setPage} disabled={reviews.loading} />}
    </section><MetadataCard vehicle={vehicle} />
  </>
}
