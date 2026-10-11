from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator
from typing import Annotated, Literal
from uuid import UUID

from api.database import many, one

Page = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str, Query(max_length=100)]
DateInput = Annotated[str | None, Query(pattern=r'^\d{4}-\d{2}-\d{2}$')]
FromDate = Annotated[str | None, Query(alias='from', pattern=r'^\d{4}-\d{2}-\d{2}$')]
TripStatus = Literal['REQUESTED', 'IN TRANSIT', 'COMPLETED']


class ApiError(Exception):
    def __init__(self, status, code, message):
        self.status = status
        self.code = code
        self.message = message


class Booking(BaseModel):
    model_config = ConfigDict(extra='forbid')
    riderId: UUID
    vehicleId: UUID
    fareAmount: StrictStr = Field(pattern=r'^\d{1,8}(\.\d{1,2})?$')

    @field_validator('fareAmount')
    @classmethod
    def check_fare(cls, value):
        if Decimal(value) <= 0:
            raise ValueError('Enter a positive fare.')
        return value


class StatusChange(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['IN TRANSIT', 'COMPLETED']


def money(value):
    return format(value, '.2f')


def utc_time(value):
    return value.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')


def rider(row):
    return {'id': str(row['id']), 'name': row['name'],
            'walletBalance': money(row['wallet_balance'])}


def vehicle(row):
    return {'id': str(row['id']), 'licensePlate': row['license_plate'],
            'class': row['class'], 'isActive': row['is_active']}


def trip(row):
    return {'id': str(row['id']), 'riderId': str(row['rider_id']),
            'vehicleId': str(row['vehicle_id']), 'fareAmount': money(row['fare_amount']),
            'status': row['status'], 'createdAt': utc_time(row['created_at']),
            'riderName': row['rider_name'], 'licensePlate': row['license_plate']}


def audit(row):
    return {'id': str(row['id']), 'riderId': str(row['rider_id']),
            'amountChanged': money(row['amount_changed']), 'actionType': row['action_type'],
            'balanceAfter': money(row['balance_after']), 'timestamp': utc_time(row['timestamp'])}


def required(row):
    if row is None:
        raise ApiError(404, 'NOT_FOUND', 'This rider, vehicle or trip could not be found.')
    return row


def date_bounds(from_date, to_date):
    local = ZoneInfo('Asia/Kolkata')
    try:
        start = date.fromisoformat(from_date) if from_date else None
        end = date.fromisoformat(to_date) if to_date else None
        if start and end and start > end:
            raise ValueError()
        lower = datetime.combine(start, time.min, local) if start else None
        upper = datetime.combine(end + timedelta(days=1), time.min, local) if end else None
        return lower, upper
    except (ValueError, OverflowError):
        raise ApiError(422, 'INVALID_INPUT', 'Choose valid dates with the start before the end.')


def add_dates(conditions, values, column, lower, upper):
    if lower:
        conditions.append(column + ' >= %s')
        values.append(lower)
    if upper:
        conditions.append(column + ' < %s')
        values.append(upper)


def listing(conn, source, fields, conditions, values, order, page, page_size, convert):
    # source, fields and order are fixed in our code; user inputs are parameters.
    where = ' AND '.join(conditions) if conditions else 'TRUE'
    total = one(conn, 'SELECT COUNT(*) AS total FROM ' + source + ' WHERE ' + where, values)['total']
    if (page - 1) * page_size >= total:
        return {'items': [], 'page': page, 'pageSize': page_size, 'total': total}
    rows = many(conn, 'SELECT ' + fields + ' FROM ' + source + ' WHERE ' + where
                + ' ORDER BY ' + order + ' LIMIT %s OFFSET %s',
                [*values, page_size, (page - 1) * page_size])
    return {'items': [convert(row) for row in rows], 'page': page,
            'pageSize': page_size, 'total': total}
