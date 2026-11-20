import { useState } from 'react'
import { apiUrl, shortId, time } from '../api'
import { useQuery } from '../useQuery'
import { Dates, Feedback, Icon, Notice, Pager, Picker, Stars, Table } from '../components'
import { RatingChart, TagChart, isNegativeTag, tagLabel } from '../charts'
import { MetadataCard } from '../details'

export default function Reviews() {
  const [vehicle, setVehicle] = useState(null)
  const [dates, setDates] = useState({ from: '', to: '' })
  const [page, setPage] = useState(1)
  const params = { vehicleId: vehicle?.id, ...dates }
  const summary = useQuery(apiUrl('/api/reviews/summary', params))
  const reviews = useQuery(apiUrl('/api/reviews', { ...params, page, pageSize: 25 }))
  return <><section className="card"><div className="filters"><Picker kind="vehicles" label="Review vehicle" optional value={vehicle} onChange={value => { setVehicle(value); setPage(1) }} />
    <Dates value={dates} onChange={value => { setDates(value); setPage(1) }} /><button className="secondary" disabled={summary.loading || reviews.loading} onClick={() => { summary.reload(); reviews.reload() }}><Icon name="refresh" size={16} />Reload reviews</button></div></section>
    <MetadataCard vehicle={vehicle} />
    <section className="card"><h2>What riders are saying</h2><Feedback query={summary} hasRows={summary.data?.reviewCount} empty="No reviews match these filters." />
      {summary.data && (() => { const issue = summary.data.topTags.find(row => isNegativeTag(row.tag) && row.count >= 3); return <>
        <div className="rating-hero"><span className="big">{summary.data.averageRating === null ? '—' : summary.data.averageRating.toFixed(2)}</span>
          <div><Stars value={summary.data.averageRating || 0} size={18} /><p className="muted" style={{ margin: '4px 0 0' }}>{summary.data.averageRating === null ? 'No ratings' : 'Average rating out of 5'} · {summary.data.reviewCount.toLocaleString('en-IN')} {summary.data.reviewCount === 1 ? 'review' : 'reviews'}</p></div></div>
        {summary.data.topTags.length > 0 && <div className="quiet-chips" aria-hidden="true">{summary.data.topTags.slice(0, 6).map(row => <span key={row.tag} className={isNegativeTag(row.tag) ? 'neg' : ''}>{tagLabel(row.tag)}<b>{row.count}</b></span>)}</div>}
        {issue && <div style={{ marginTop: 6 }}><Notice kind="warning">Most reported issue: <strong>{tagLabel(issue.tag)}</strong> ({issue.count})</Notice></div>}
        <div className="two-columns"><div><h3>Rating distribution</h3><RatingChart rows={summary.data.ratingDistribution} /></div><div><h3>Top feedback tags</h3><TagChart rows={summary.data.topTags} />{!summary.data.topTags.length && <p className="muted">No feedback tags.</p>}</div></div></> })()}
    </section><section className="card"><h2>Trip reviews</h2><Feedback query={reviews} hasRows={reviews.data?.items.length} empty="No individual reviews to show." />
      {reviews.data?.items.length > 0 && <Table label="Trip reviews" rows={reviews.data.items} columns={[{ key: 'tripId', label: 'Trip ID', render: row => <span className="id" title={row.tripId}>{shortId(row.tripId)}</span> }, { key: 'rating', label: 'Rating', render: row => <span className="class-chip"><b className="rating-num">{row.rating}</b><Stars value={row.rating} size={14} /><span className="sr-only">/ 5</span></span> }, { key: 'feedbackTags', label: 'Feedback', render: row => row.feedbackTags.length ? <span className="tags">{row.feedbackTags.map(tag => <span key={tag} className={isNegativeTag(tag) ? 'neg' : ''}>{tagLabel(tag)}</span>)}</span> : '—' }, { key: 'createdAt', label: 'Posted at', render: row => time(row.createdAt) }]} />}
      {reviews.data && <Pager page={page} total={reviews.data.total} onPage={setPage} disabled={reviews.loading} />}
    </section>
  </>
}
