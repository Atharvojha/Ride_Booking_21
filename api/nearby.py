from datetime import datetime, timedelta, timezone
from itertools import islice
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from api.common import utc_time
from api.database import many, mongo, postgres

router = APIRouter(prefix='/api/vehicles')
Longitude = Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)]
Latitude = Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)]
ResultLimit = Annotated[int, Query(ge=1, le=50)]


def nearby_pipeline(longitude, latitude, checked_at):
    return [
        {'$geoNear': {'near': {'type': 'Point', 'coordinates': [longitude, latitude]},
                      'key': 'location', 'distanceField': 'distance_meters',
                      'maxDistance': 5000, 'spherical': True,
                      'query': {'is_available': True, 'created_at': {
                          '$gte': checked_at - timedelta(seconds=7200), '$lte': checked_at}}}},
        # Check candidates against all pings, including unavailable and distant ones.
        {'$lookup': {'from': 'TelemetryPings', 'localField': 'vehicle_id',
                     'foreignField': 'vehicle_id', 'pipeline': [
                         {'$sort': {'created_at': -1, '_id': -1}}, {'$limit': 1},
                         {'$project': {'_id': 1}}], 'as': 'latest'}},
        {'$match': {'$expr': {'$eq': ['$_id', {'$arrayElemAt': ['$latest._id', 0]}]}}},
        {'$sort': {'distance_meters': 1, 'vehicle_id': 1}},
        {'$project': {'vehicle_id': 1, 'location': 1, 'distance_meters': 1, 'created_at': 1}},
    ]


def ping_item(row, label):
    longitude, latitude = row['location']['coordinates']
    stamp = row['created_at']
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return {'vehicleId': str(label['id']), 'licensePlate': label['license_plate'],
            'class': label['class'], 'longitude': longitude, 'latitude': latitude,
            'distanceMeters': round(row['distance_meters'], 2), 'pingAt': utc_time(stamp)}


@router.get('/nearby')
def nearby(longitude: Longitude, latitude: Latitude, limit: ResultLimit = 50):
    checked_at = datetime.now(timezone.utc)
    items = []
    with mongo() as db, postgres() as conn:
        with db.TelemetryPings.aggregate(nearby_pipeline(longitude, latitude, checked_at),
                                        maxTimeMS=5000, allowDiskUse=True).batch_size(100) as cursor:
            while len(items) < limit:
                batch = list(islice(cursor, 100))
                if not batch:
                    break
                valid = []
                for row in batch:
                    try:
                        valid.append((row, UUID(row['vehicle_id'])))
                    except (ValueError, TypeError, KeyError):
                        continue
                labels = {row['id']: row for row in many(conn,
                          'SELECT id,license_plate,class FROM vehicles WHERE is_active AND id=ANY(%s)',
                          [[vehicle_id for _, vehicle_id in valid]])} if valid else {}
                # Limit only after missing/inactive SQL vehicles have been removed.
                for row, vehicle_id in valid:
                    if vehicle_id in labels and len(items) < limit:
                        items.append(ping_item(row, labels[vehicle_id]))
    return {'origin': {'longitude': longitude, 'latitude': latitude}, 'radiusMeters': 5000,
            'freshnessSeconds': 7200, 'checkedAt': utc_time(checked_at), 'items': items}
