from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter

from api.browse import read_trip
from api.common import (ApiError, Booking, DateInput, FromDate, Page, PageSize,
                        StatusChange, add_dates, audit, date_bounds, listing,
                        money, required, trip)
from api.database import one, postgres

router = APIRouter(prefix='/api')
BOOKING_ERRORS = {
    'INVALID_INPUT': (422, 'Enter a positive fare with at most two decimal places.'),
    'NOT_FOUND': (404, 'This rider or vehicle could not be found.'),
    'INSUFFICIENT_BALANCE': (409, 'This rider does not have enough wallet balance.'),
    'ACTIVE_TRIP_EXISTS': (409, "Complete this rider's active trip before booking another."),
    'VEHICLE_INACTIVE': (409, 'Choose an active vehicle.'),
}


@router.post('/trips', status_code=201)
def book_trip(booking: Booking):
    with postgres(write=True) as conn:
        result = one(conn, 'CALL sp_book_trip(%s,%s,%s,NULL,NULL,NULL)',
                     [booking.riderId, booking.vehicleId, Decimal(booking.fareAmount)])
        if result['p_status'] != 'BOOKED':
            code = result['p_status'].removeprefix('FAILED:').strip()
            status, message = BOOKING_ERRORS.get(code, (500, 'The booking could not be completed.'))
            raise ApiError(status, code if code in BOOKING_ERRORS else 'INTERNAL_ERROR', message)
        entry = one(conn, 'SELECT * FROM wallet_audit_logs WHERE id=%s', [result['p_audit_id']])
        if entry is None:
            raise ApiError(500, 'INTERNAL_ERROR', 'The booking audit entry could not be read.')
        return {'trip': trip(read_trip(conn, result['p_trip_id'])),
                'balanceBefore': money(entry['balance_after'] - entry['amount_changed']),
                'balanceAfter': money(entry['balance_after']), 'auditEntry': audit(entry)}


@router.patch('/trips/{trip_id}/status')
def change_status(trip_id: UUID, change: StatusChange):
    with postgres(write=True) as conn:
        current = read_trip(conn, trip_id)
        if change.status == 'IN TRANSIT':
            changed = one(conn, "UPDATE trips SET status='IN TRANSIT' WHERE id=%s AND status='REQUESTED' RETURNING id",
                          [trip_id])
            if changed is None:
                raise ApiError(409, 'INVALID_TRANSITION', 'Only a requested trip can be started.')
        else:
            if current['status'] != 'IN TRANSIT':
                raise ApiError(409, 'INVALID_TRANSITION', 'Start this trip before completing it.')
            conn.notices.clear()
            with conn.cursor() as cur:
                cur.execute('CALL sp_release_escrow(%s)', [trip_id])
            failures = [notice for notice in conn.notices if 'sp_release_escrow failed:' in notice]
            if failures:
                if 'not IN TRANSIT' in failures[-1]:
                    raise ApiError(409, 'INVALID_TRANSITION', 'This trip is no longer in transit.')
                raise ApiError(500, 'INTERNAL_ERROR', 'This trip could not be completed.')
        saved = read_trip(conn, trip_id)
        if change.status == 'COMPLETED' and saved['status'] != 'COMPLETED':
            raise ApiError(500, 'INTERNAL_ERROR', 'This trip could not be completed.')
        return {'trip': trip(saved)}


@router.get('/riders/{rider_id}/audit')
def wallet_audit(rider_id: UUID, from_date: FromDate = None, to: DateInput = None,
                 page: Page = 1, pageSize: PageSize = 25):
    lower, upper = date_bounds(from_date, to)
    conditions, values = ['rider_id=%s'], [rider_id]
    add_dates(conditions, values, 'timestamp', lower, upper)
    with postgres() as conn:
        current = required(one(conn, 'SELECT wallet_balance FROM riders WHERE id=%s', [rider_id]))
        result = listing(conn, 'wallet_audit_logs', '*', conditions, values,
                         'timestamp, id', page, pageSize, audit)
        opening = None
        if lower:
            before = one(conn, 'SELECT balance_after FROM wallet_audit_logs WHERE rider_id=%s AND timestamp<%s ORDER BY timestamp DESC, id DESC LIMIT 1',
                         [rider_id, lower])
            if before:
                opening = before['balance_after']
        if opening is None:
            first = one(conn, 'SELECT * FROM wallet_audit_logs WHERE ' + ' AND '.join(conditions)
                        + ' ORDER BY timestamp, id LIMIT 1', values)
            if first:
                opening = first['balance_after'] - first['amount_changed']
        result['currentBalance'] = money(current['wallet_balance'])
        result['openingBalance'] = money(opening) if opening is not None else None
        return result
