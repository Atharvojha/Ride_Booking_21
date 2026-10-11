from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from pymongo.errors import PyMongoError

from api.common import (DateInput, FromDate, Page, PageSize, Search, TripStatus, add_dates,
                        date_bounds, listing, required, rider, trip, utc_time, vehicle)
from api.database import mongo, one, postgres

router = APIRouter(prefix='/api')
TRIPS = 'trips t JOIN riders r ON r.id=t.rider_id JOIN vehicles v ON v.id=t.vehicle_id'
TRIP_FIELDS = 't.*, r.name AS rider_name, v.license_plate'


def metadata_value(value):
    if isinstance(value, datetime):
        return utc_time(value if value.tzinfo else value.replace(tzinfo=timezone.utc))
    if isinstance(value, dict):
        return {key: metadata_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [metadata_value(item) for item in value]
    return value


@router.get('/riders')
def riders(search: Search = '', page: Page = 1, pageSize: PageSize = 25):
    with postgres() as conn:
        return listing(conn, 'riders', '*', ['(name ILIKE %s OR id::text ILIKE %s)'],
                       ['%' + search + '%'] * 2, 'name, id', page, pageSize, rider)


@router.get('/riders/{rider_id}')
def rider_detail(rider_id: UUID):
    with postgres() as conn:
        return {'rider': rider(required(one(conn, 'SELECT * FROM riders WHERE id=%s', [rider_id])))}


@router.get('/vehicles')
def vehicles(search: Search = '', vehicle_class: Annotated[str | None, Query(alias='class', max_length=30)] = None,
             active: bool | None = None, page: Page = 1, pageSize: PageSize = 25):
    conditions = ['(license_plate ILIKE %s OR id::text ILIKE %s)']
    values = ['%' + search + '%'] * 2
    if vehicle_class is not None:
        conditions.append('class=%s')
        values.append(vehicle_class)
    if active is not None:
        conditions.append('is_active=%s')
        values.append(active)
    with postgres() as conn:
        return listing(conn, 'vehicles', '*', conditions, values, 'license_plate, id',
                       page, pageSize, vehicle)


@router.get('/vehicles/{vehicle_id}')
def vehicle_detail(vehicle_id: UUID):
    with postgres() as conn:
        result = {'vehicle': vehicle(required(one(conn, 'SELECT * FROM vehicles WHERE id=%s', [vehicle_id]))),
                  'metadata': None}
    try:
        with mongo() as db:
            doc = db.VehicleMetadata.find_one({'vehicle_id': str(vehicle_id)}, {'_id': 0})
        if doc:
            result['metadata'] = {'vehicleId': doc['vehicle_id'], 'features': metadata_value(doc.get('features', {})),
                                  'inspectionRecords': metadata_value(doc.get('inspection_records', [])),
                                  'createdAt': utc_time(doc['created_at'].replace(tzinfo=timezone.utc)) if doc.get('created_at') else None}
    except PyMongoError:
        result['metadataError'] = {'code': 'DATABASE_UNAVAILABLE',
                                   'message': 'Vehicle metadata is unavailable. Try again shortly.'}
    return result


@router.get('/trips')
def trips(riderId: UUID | None = None, vehicleId: UUID | None = None,
          status: TripStatus | None = None, from_date: FromDate = None,
          to: DateInput = None, page: Page = 1, pageSize: PageSize = 25):
    lower, upper = date_bounds(from_date, to)
    conditions, values = [], []
    for column, value in [('t.rider_id', riderId), ('t.vehicle_id', vehicleId), ('t.status', status)]:
        if value is not None:
            conditions.append(column + '=%s')
            values.append(value)
    add_dates(conditions, values, 't.created_at', lower, upper)
    with postgres() as conn:
        return listing(conn, TRIPS, TRIP_FIELDS, conditions, values, 't.created_at DESC, t.id',
                       page, pageSize, trip)


def read_trip(conn, trip_id):
    return required(one(conn, 'SELECT ' + TRIP_FIELDS + ' FROM ' + TRIPS + ' WHERE t.id=%s', [trip_id]))


@router.get('/trips/{trip_id}')
def trip_detail(trip_id: UUID):
    with postgres() as conn:
        return {'trip': trip(read_trip(conn, trip_id))}
