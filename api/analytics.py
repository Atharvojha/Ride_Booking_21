from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter

from api.common import ApiError, DateInput, FromDate, Page, PageSize, listing, money, required, utc_time
from api.database import many, one, postgres

router = APIRouter(prefix='/api/analytics')


def chart_dates(start, end):
    try:
        last = date.fromisoformat(end) if end else datetime.now(ZoneInfo('Asia/Kolkata')).date()
        first = date.fromisoformat(start) if start else last - timedelta(days=29)
        if first > last or (last - first).days >= 90:
            raise ValueError()
        # Leave space for the six earlier days and the final exclusive date.
        first - timedelta(days=6)
        last + timedelta(days=1)
        return first, last
    except (ValueError, OverflowError):
        raise ApiError(422, 'INVALID_INPUT', 'Choose valid dates covering at most 90 days.')


def revenue_row(row):
    return {'vehicleId': str(row['vehicle_id']), 'licensePlate': row['license_plate'],
            'date': row['revenue_date'].isoformat(), 'dailyRevenue': money(row['daily_revenue']),
            'movingAverage7Days': money(row['moving_average']), 'rank': row['revenue_rank']}


@router.get('/revenue')
def revenue(vehicleId: UUID | None = None, from_date: FromDate = None,
            to: DateInput = None, page: Page = 1, pageSize: PageSize = 25):
    first, last = chart_dates(from_date, to)
    with postgres() as conn:
        selected = vehicleId
        if selected:
            required(one(conn, 'SELECT id FROM vehicles WHERE id=%s', [selected]))
        else:
            choice = one(conn, 'SELECT id FROM vehicles WHERE is_active ORDER BY license_plate,id LIMIT 1')
            selected = choice['id'] if choice else None
        conditions = ['vehicle_id=%s'] if vehicleId else []
        values = [first, last, vehicleId] if vehicleId else [first, last]
        result = listing(conn, 'api_vehicle_revenue(%s,%s)', '*', conditions, values,
                         'revenue_date DESC,revenue_rank,vehicle_id', page, pageSize, revenue_row)
        series = many(conn, 'SELECT * FROM api_vehicle_revenue(%s,%s) WHERE vehicle_id=%s ORDER BY revenue_date',
                      [first, last, selected]) if selected else []
        return {'series': [{key: value for key, value in revenue_row(row).items()
                            if key not in ('licensePlate', 'rank')} for row in series],
                'rankings': result['items'], 'page': page, 'pageSize': pageSize, 'total': result['total'],
                'from': first.isoformat(), 'to': last.isoformat(), 'timezone': 'Asia/Kolkata',
                'selectedVehicleId': str(selected) if selected else None}


def summary_row(row):
    return {'vehicleId': str(row['vehicle_id']), 'licensePlate': row['license_plate'],
            'class': row['class'], 'isActive': row['is_active'],
            'lifetimeTripCount': row['lifetime_trip_count'], 'lifetimeEarnings': money(row['lifetime_earnings'])}


@router.get('/summary')
def summary(vehicleId: UUID | None = None, page: Page = 1, pageSize: PageSize = 25):
    conditions = ['vehicle_id=%s'] if vehicleId else []
    values = [vehicleId] if vehicleId else []
    where = 'vehicle_id=%s' if vehicleId else 'TRUE'
    with postgres() as conn:
        if vehicleId:
            required(one(conn, 'SELECT id FROM vehicles WHERE id=%s', [vehicleId]))
        result = listing(conn, 'mv_vehicle_lifetime_stats', '*', conditions, values,
                         'license_plate,vehicle_id', page, pageSize, summary_row)
        totals = one(conn, 'SELECT COALESCE(SUM(lifetime_trip_count),0) AS trips, '
                     'COALESCE(SUM(lifetime_earnings),0) AS earnings FROM mv_vehicle_lifetime_stats WHERE '+where, values)
        stamp = one(conn, "SELECT last_refreshed_at FROM api_refresh_state WHERE name='vehicle_lifetime_stats'")
        result.update(totals={'lifetimeTripCount': int(totals['trips']), 'lifetimeEarnings': money(totals['earnings'])},
                      lastRefreshedAt=utc_time(stamp['last_refreshed_at']) if stamp['last_refreshed_at'] else None)
        return result


@router.post('/refresh')
def refresh():
    with postgres(write=True) as conn:
        conn.autocommit = False
        with conn:
            locked = one(conn, 'SELECT pg_try_advisory_xact_lock(10,6302) AS locked')['locked']
            if not locked:
                raise ApiError(409, 'REFRESH_IN_PROGRESS', 'A refresh is already running. Try again shortly.')
            one(conn, 'SELECT refresh_mv_vehicle_lifetime_stats()')
            stamp = one(conn, "SELECT last_refreshed_at FROM api_refresh_state WHERE name='vehicle_lifetime_stats'")
        return {'lastRefreshedAt': utc_time(stamp['last_refreshed_at'])}
