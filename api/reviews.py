from datetime import timezone
from uuid import UUID

from fastapi import APIRouter

from api.common import DateInput, FromDate, Page, PageSize, date_bounds, utc_time
from api.database import mongo

router = APIRouter(prefix='/api/reviews')


def review_filter(vehicle_id, start, end):
    lower, upper = date_bounds(start, end)
    match = {'vehicle_id': str(vehicle_id)} if vehicle_id else {}
    if lower or upper:
        match['created_at'] = {}
        if lower:
            match['created_at']['$gte'] = lower
        if upper:
            match['created_at']['$lt'] = upper
    return match


def summary_pipeline(match):
    # Keep the inherited facet workflow; filter before grouping its results.
    return [{'$match': match}, {'$facet': {
        'ratingStats': [{'$group': {'_id': '$rating', 'count': {'$sum': 1}}}, {'$sort': {'_id': 1}}],
        'averageRating': [{'$group': {'_id': None, 'avgRating': {'$avg': '$rating'},
                                     'totalReviews': {'$sum': 1}}},
                          {'$project': {'_id': 0, 'avgRating': {'$round': ['$avgRating', 2]}, 'totalReviews': 1}}],
        'topFeedbackTags': [{'$unwind': '$feedback_tags'},
                            {'$group': {'_id': '$feedback_tags', 'count': {'$sum': 1}}},
                            {'$sort': {'count': -1, '_id': 1}}, {'$limit': 10}],
    }}]


@router.get('/summary')
def review_summary(vehicleId: UUID | None = None, from_date: FromDate = None, to: DateInput = None):
    match = review_filter(vehicleId, from_date, to)
    with mongo() as db:
        result = next(db.TripReviews.aggregate(summary_pipeline(match), maxTimeMS=5000))
    averages = result['averageRating']
    counts = {row['_id']: row['count'] for row in result['ratingStats']}
    return {'reviewCount': averages[0]['totalReviews'] if averages else 0,
            'averageRating': averages[0]['avgRating'] if averages else None,
            'ratingDistribution': [{'rating': rating, 'count': counts.get(rating, 0)} for rating in range(1, 6)],
            'topTags': [{'tag': row['_id'], 'count': row['count']} for row in result['topFeedbackTags']]}


def review_item(row):
    stamp = row['created_at']
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return {'id': str(row['_id']), 'tripId': row['trip_id'], 'vehicleId': row['vehicle_id'],
            'rating': row['rating'], 'feedbackTags': row.get('feedback_tags', []), 'createdAt': utc_time(stamp)}


@router.get('')
def reviews(vehicleId: UUID | None = None, from_date: FromDate = None,
            to: DateInput = None, page: Page = 1, pageSize: PageSize = 25):
    match = review_filter(vehicleId, from_date, to)
    offset = (page - 1) * pageSize
    # Mongo skip accepts a 64-bit value. An even larger page is necessarily empty.
    rows = [{'$match': {'_id': {'$exists': False}}}] if offset >= 2**63 else [
        {'$sort': {'created_at': -1, '_id': -1}}, {'$skip': offset}, {'$limit': pageSize}]
    pipeline = [{'$match': match}, {'$facet': {'count': [{'$count': 'total'}], 'items': rows}}]
    with mongo() as db:
        result = next(db.TripReviews.aggregate(pipeline, maxTimeMS=5000, allowDiskUse=True))
    return {'items': [review_item(row) for row in result['items']], 'page': page, 'pageSize': pageSize,
            'total': result['count'][0]['total'] if result['count'] else 0}
