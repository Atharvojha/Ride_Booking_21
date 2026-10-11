"""Full-scale checks for the RideSync API and databases.

Run this only against isolated scale databases. Their names must contain "scale",
because the booking checks write real trips. Never point it at the demo database.

Two APIs are used so that the seeded databases stay unchanged:
  --api        reads the seeded PostgreSQL and MongoDB databases (read-only checks).
  --write-api  uses a disposable copy of the seeded PostgreSQL database in which trip
               dates were spread over 60 days (booking, refresh and revenue checks).
Make that copy with: createdb -T <seeded database> <copy name>, then spread the dates
as shown in docs/scale_verification.md. Both APIs read the same MongoDB database.

    python tests/scale_check.py --api http://127.0.0.1:8002 \
        --write-api http://127.0.0.1:8003 --write-db ridesync_scale_20261011_copy \
        --out docs/scale_verification.json

Expected values are calculated in plain Python from the raw rows, not by calling the
same SQL or API code that is being checked.
"""
import argparse
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
import psycopg2
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
IST = ZoneInfo('Asia/Kolkata')
EARTH_RADIUS_METRES = 6378100  # the radius MongoDB uses for spherical distances
ORIGIN = (78.4867, 17.3850)    # longitude, latitude
results = []
timings = {}
facts = {}


def record(name, ok, detail=''):
    results.append({'check': name, 'passed': bool(ok), 'detail': str(detail)})
    print(('PASS ' if ok else 'FAIL ') + name + (' - ' + str(detail) if detail else ''), flush=True)


def connect_postgres(dbname):
    return psycopg2.connect(host=os.getenv('PGHOST', 'localhost'), port=os.getenv('PGPORT', '5432'),
                            dbname=dbname, user=os.getenv('PGUSER', os.environ['USER']),
                            password=os.getenv('PGPASSWORD', ''))


def query(conn, text, values=()):
    with conn.cursor() as cur:
        cur.execute(text, values)
        return cur.fetchall()


def scalar(conn, text, values=()):
    return query(conn, text, values)[0][0]


class Api:
    """Small wrapper that remembers how long each call took."""

    def __init__(self, base):
        self.client = httpx.Client(base_url=base, timeout=60)

    def get(self, path, **params):
        started = time.perf_counter()
        reply = self.client.get(path, params=params)
        seconds = time.perf_counter() - started
        return reply.status_code, reply.json(), seconds, len(reply.content)

    def post_status(self, path, body):
        return self.client.post(path, json=body).status_code

    def send(self, method, path, body):
        reply = self.client.request(method, path, json=body)
        return reply.status_code, reply.json()


def time_endpoint(api, label, path, runs=3, **params):
    """Call a GET endpoint several times; keep the status, size and timings."""
    seconds, status, size = [], None, None
    for _ in range(runs):
        status, _, taken, size = api.get(path, **params)
        seconds.append(taken)
    timings[label] = {'path': path, 'params': params, 'status': status, 'bytes': size,
                      'runsSeconds': [round(s, 3) for s in seconds],
                      'medianSeconds': round(statistics.median(seconds), 3)}
    print(f'  timing {label}: {timings[label]["runsSeconds"]} s, {size} bytes', flush=True)
    return status


# ---------------------------------------------------------------- counts and sizes

def api_uses_database(api, pg):
    """True when the API's trip totals equal this PostgreSQL database's (all trips, and trips today).

    This stops --write-api from being pointed at an API that is backed by a different
    database, such as the demo database, before any booking is made.
    """
    today = datetime.now(IST).date().isoformat()
    in_kolkata_day = "(created_at AT TIME ZONE 'Asia/Kolkata')::date"
    all_trips = api.get('/api/trips', pageSize=1)[1]['total']
    today_trips = api.get('/api/trips', pageSize=1, **{'from': today, 'to': today})[1]['total']
    earlier_trips = api.get('/api/trips', pageSize=1, to=(date.fromisoformat(today) - timedelta(days=1)).isoformat())[1]['total']
    return (all_trips == scalar(pg, 'SELECT COUNT(*) FROM trips')
            and today_trips == scalar(pg, f'SELECT COUNT(*) FROM trips WHERE {in_kolkata_day} = %s', [today])
            and earlier_trips == scalar(pg, f'SELECT COUNT(*) FROM trips WHERE {in_kolkata_day} < %s', [today]))


def collect_counts(pg, mdb):
    facts['postgres'] = {
        'riders': scalar(pg, 'SELECT COUNT(*) FROM riders'),
        'vehicles': scalar(pg, 'SELECT COUNT(*) FROM vehicles'),
        'activeVehicles': scalar(pg, 'SELECT COUNT(*) FROM vehicles WHERE is_active'),
        'tripsByStatus': dict(query(pg, 'SELECT status, COUNT(*) FROM trips GROUP BY status')),
        'walletAuditByAction': dict(query(pg, 'SELECT action_type, COUNT(*) FROM wallet_audit_logs GROUP BY 1')),
        'databaseSize': scalar(pg, 'SELECT pg_size_pretty(pg_database_size(current_database()))'),
        'version': scalar(pg, 'SHOW server_version'),
    }
    facts['mongo'] = {name: mdb[name].count_documents({})
                      for name in ('VehicleMetadata', 'TripReviews', 'TelemetryPings')}
    facts['mongo']['databaseSizeBytes'] = mdb.command('dbStats')['dataSize']
    facts['mongo']['version'] = mdb.client.server_info()['version']
    record('Counts recorded', True, json.dumps({k: facts[k] for k in ('postgres', 'mongo')}, default=str))


def check_money_invariants(pg, label):
    """Wallet audit rows must agree with trips and wallets for every rider."""
    holds = scalar(pg, "SELECT COUNT(*) FROM wallet_audit_logs WHERE action_type='ESCROW_HOLD'")
    trips = scalar(pg, 'SELECT COUNT(*) FROM trips')
    record(f'{label}: one ESCROW_HOLD audit row per trip', holds == trips, f'holds={holds} trips={trips}')
    released = scalar(pg, "SELECT COUNT(*) FROM wallet_audit_logs WHERE action_type='ESCROW_RELEASE'")
    completed = scalar(pg, "SELECT COUNT(*) FROM trips WHERE status='COMPLETED'")
    record(f'{label}: one ESCROW_RELEASE audit row per completed trip', released == completed,
           f'released={released} completed={completed}')
    held = scalar(pg, "SELECT COALESCE(SUM(-amount_changed),0) FROM wallet_audit_logs WHERE action_type='ESCROW_HOLD'")
    fares = scalar(pg, 'SELECT COALESCE(SUM(fare_amount),0) FROM trips')
    record(f'{label}: held money equals the sum of trip fares', held == fares, f'held={held} fares={fares}')
    mismatched = scalar(pg, '''
        SELECT COUNT(*) FROM riders r JOIN LATERAL (
            SELECT balance_after FROM wallet_audit_logs a WHERE a.rider_id = r.id
            ORDER BY a.timestamp DESC, a.id DESC LIMIT 1) last ON TRUE
        WHERE last.balance_after <> r.wallet_balance''')
    record(f'{label}: latest saved running balance equals the wallet for every rider', mismatched == 0,
           f'riders with a mismatch: {mismatched}')
    two_active = scalar(pg, '''SELECT COUNT(*) FROM (SELECT rider_id FROM trips
        WHERE status IN ('REQUESTED','IN TRANSIT') GROUP BY rider_id HAVING COUNT(*) > 1) x''')
    record(f'{label}: no rider has two active trips', two_active == 0)
    negative = scalar(pg, 'SELECT COUNT(*) FROM riders WHERE wallet_balance < 0')
    record(f'{label}: no negative wallet', negative == 0)


# ---------------------------------------------------------------- browsing

def check_browse(api, pg, mdb):
    total = api.get('/api/riders', pageSize=100)
    record('Browse: rider total matches SQL', total[1]['total'] == facts['postgres']['riders'] and len(total[1]['items']) == 100)
    status, body, _, _ = api.get('/api/riders', pageSize=101)
    record('Browse: page size above 100 is refused', status == 422, f'status {status}')
    status, body, _, _ = api.get('/api/riders', page=10 ** 9, pageSize=100)
    record('Browse: a page past the end is empty with the true total',
           status == 200 and body['items'] == [] and body['total'] == facts['postgres']['riders'])

    expected = scalar(pg, "SELECT COUNT(*) FROM riders WHERE name ILIKE %s OR id::text ILIKE %s", ['%Acharya%'] * 2)
    got = api.get('/api/riders', search='Acharya', pageSize=100)[1]['total']
    record('Browse: rider search count matches SQL', got == expected, f'{got} rows')

    expected = scalar(pg, "SELECT COUNT(*) FROM vehicles WHERE class='Bike' AND is_active AND license_plate ILIKE %s", ['%TS09%'])
    got = api.get('/api/vehicles', **{'class': 'Bike', 'active': 'true', 'search': 'TS09', 'pageSize': 100})[1]['total']
    record('Browse: vehicle class, active and search filters match SQL', got == expected, f'{got} rows')

    # Walk every page of the REQUESTED trips and compare with the SQL list.
    wanted = [str(r[0]) for r in query(pg, "SELECT id FROM trips WHERE status='REQUESTED' ORDER BY created_at DESC, id")]
    seen, page = [], 1
    while True:
        body = api.get('/api/trips', status='REQUESTED', page=page, pageSize=100)[1]
        seen += [item['id'] for item in body['items']]
        if len(body['items']) < 100:
            break
        page += 1
    record('Browse: all REQUESTED trip pages match SQL order, with no repeats', seen == wanted,
           f'{len(seen)} trips over {page} pages')

    day = scalar(pg, "SELECT (MAX(created_at) AT TIME ZONE 'Asia/Kolkata')::date FROM trips")
    expected = scalar(pg, "SELECT COUNT(*) FROM trips WHERE status='COMPLETED' AND (created_at AT TIME ZONE 'Asia/Kolkata')::date = %s", [day])
    got = api.get('/api/trips', status='COMPLETED', **{'from': day.isoformat(), 'to': day.isoformat()}, pageSize=100)[1]['total']
    record('Browse: one-day Asia/Kolkata trip filter matches SQL', got == expected, f'{got} trips on {day}')

    check_details(api, pg, mdb)


def check_details(api, pg, mdb):
    rider_id, name, balance = query(pg, 'SELECT id, name, wallet_balance FROM riders ORDER BY id LIMIT 1')[0]
    rider = api.get(f'/api/riders/{rider_id}')[1]['rider']
    record('Details: rider matches SQL', rider['name'] == name and rider['walletBalance'] == format(balance, '.2f'))
    trip_id, fare, status = query(pg, 'SELECT id, fare_amount, status FROM trips ORDER BY id LIMIT 1')[0]
    trip = api.get(f'/api/trips/{trip_id}')[1]['trip']
    record('Details: trip matches SQL', trip['fareAmount'] == format(fare, '.2f') and trip['status'] == status)
    ids = [str(r[0]) for r in query(pg, 'SELECT id FROM vehicles ORDER BY id LIMIT 10')]
    same = 0
    for vehicle_id in ids:
        body = api.get(f'/api/vehicles/{vehicle_id}')[1]
        doc = mdb.VehicleMetadata.find_one({'vehicle_id': vehicle_id})
        same += (body['metadata'] is not None and body['metadata']['features'] == doc['features']
                 and len(body['metadata']['inspectionRecords']) == len(doc['inspection_records']))
    record('Details: vehicle metadata matches the Mongo document for 10 vehicles', same == 10, f'{same}/10')


# ---------------------------------------------------------------- booking and wallet

def free_rider(pg, minimum, maximum=None, skip=()):
    text = '''SELECT r.id, r.wallet_balance FROM riders r
        WHERE r.wallet_balance >= %s AND r.wallet_balance <= %s AND r.id <> ALL(%s::uuid[])
          AND NOT EXISTS (SELECT 1 FROM trips t WHERE t.rider_id = r.id AND t.status IN ('REQUESTED','IN TRANSIT'))
        ORDER BY r.id LIMIT 1'''
    row = query(pg, text, [minimum, maximum if maximum is not None else 10 ** 9, [str(s) for s in skip]])[0]
    return str(row[0]), row[1]


def wallet_state(pg, rider_id):
    return (scalar(pg, 'SELECT wallet_balance FROM riders WHERE id=%s', [rider_id]),
            scalar(pg, 'SELECT COUNT(*) FROM wallet_audit_logs WHERE rider_id=%s', [rider_id]),
            scalar(pg, 'SELECT COUNT(*) FROM trips WHERE rider_id=%s', [rider_id]))


def check_booking(api, pg):
    vehicle_id = str(scalar(pg, 'SELECT id FROM vehicles WHERE is_active ORDER BY id LIMIT 1'))
    inactive_id = str(scalar(pg, 'SELECT id FROM vehicles WHERE NOT is_active ORDER BY id LIMIT 1'))
    rider_id, _ = free_rider(pg, 2000)
    before = wallet_state(pg, rider_id)
    status, body = api.send('POST', '/api/trips', {'riderId': rider_id, 'vehicleId': vehicle_id, 'fareAmount': '123.45'})
    after = wallet_state(pg, rider_id)
    audit = query(pg, 'SELECT amount_changed, action_type, balance_after FROM wallet_audit_logs WHERE id=%s', [body['auditEntry']['id']])[0]
    record('Booking: 201 with exact saved balances and the exact trigger audit row',
           status == 201 and after[0] == before[0] - Decimal('123.45')
           and body['balanceBefore'] == format(before[0], '.2f') and body['balanceAfter'] == format(after[0], '.2f')
           and audit == (Decimal('-123.45'), 'ESCROW_HOLD', after[0]) and after[1] == before[1] + 1 and after[2] == before[2] + 1)
    trip_id = body['trip']['id']

    status, body = api.send('POST', '/api/trips', {'riderId': rider_id, 'vehicleId': vehicle_id, 'fareAmount': '10.00'})
    record('Booking: a second active trip is refused without changing the wallet',
           status == 409 and body['error']['code'] == 'ACTIVE_TRIP_EXISTS' and wallet_state(pg, rider_id) == after)

    status, body = api.send('PATCH', f'/api/trips/{trip_id}/status', {'status': 'COMPLETED'})
    record('Status: completing before starting is refused', status == 409 and body['error']['code'] == 'INVALID_TRANSITION')
    status, body = api.send('PATCH', f'/api/trips/{trip_id}/status', {'status': 'IN TRANSIT'})
    record('Status: REQUESTED to IN TRANSIT works', status == 200 and body['trip']['status'] == 'IN TRANSIT')
    status, body = api.send('PATCH', f'/api/trips/{trip_id}/status', {'status': 'IN TRANSIT'})
    record('Status: starting twice is refused', status == 409)
    status, body = api.send('PATCH', f'/api/trips/{trip_id}/status', {'status': 'COMPLETED'})
    released = wallet_state(pg, rider_id)
    release_row = query(pg, "SELECT amount_changed FROM wallet_audit_logs WHERE rider_id=%s AND action_type='ESCROW_RELEASE'", [rider_id])
    record('Status: completion releases escrow with no refund',
           status == 200 and body['trip']['status'] == 'COMPLETED' and released[0] == after[0]
           and release_row == [(Decimal('0.00'),)] and released[1] == after[1] + 1)
    status, body = api.send('POST', '/api/trips', {'riderId': rider_id, 'vehicleId': vehicle_id, 'fareAmount': '20.00'})
    record('Booking: the same rider can book again after completion', status == 201)

    low_rider, low_balance = free_rider(pg, 0, 300)
    low_before = wallet_state(pg, low_rider)
    status, body = api.send('POST', '/api/trips', {'riderId': low_rider, 'vehicleId': vehicle_id, 'fareAmount': str(low_balance + 1)})
    record('Booking: low balance is refused with no debit and no audit row',
           status == 409 and body['error']['code'] == 'INSUFFICIENT_BALANCE' and wallet_state(pg, low_rider) == low_before)
    other_rider, _ = free_rider(pg, 100, skip=[rider_id])
    other_before = wallet_state(pg, other_rider)
    status, body = api.send('POST', '/api/trips', {'riderId': other_rider, 'vehicleId': inactive_id, 'fareAmount': '10.00'})
    record('Booking: an inactive vehicle is refused with no debit',
           status == 409 and body['error']['code'] == 'VEHICLE_INACTIVE' and wallet_state(pg, other_rider) == other_before)
    bad = [api.send('POST', '/api/trips', {'riderId': other_rider, 'vehicleId': vehicle_id, 'fareAmount': fare})[0]
           for fare in ('0', '12.345', '100000000.00', '-5.00', 'abc')]
    record('Booking: invalid fares are refused', bad == [422] * 5 and wallet_state(pg, other_rider) == other_before, bad)

    check_wallet_audit(api, pg, rider_id)
    check_concurrent_bookings(api, pg, vehicle_id)


def check_wallet_audit(api, pg, rider_id):
    body = api.get(f'/api/riders/{rider_id}/audit', pageSize=100)[1]
    rows = [(str(r[0]), r[1], r[2]) for r in query(
        pg, 'SELECT id, amount_changed, balance_after FROM wallet_audit_logs WHERE rider_id=%s ORDER BY timestamp, id', [rider_id])]
    balance = Decimal(body['openingBalance'])
    running_ok = True
    for item, (row_id, change, saved) in zip(body['items'], rows):
        balance += change
        running_ok &= item['id'] == row_id and balance == saved == Decimal(item['balanceAfter'])
    record('Wallet audit: history, opening balance and saved running balances agree',
           running_ok and len(body['items']) == len(rows) and balance == Decimal(body['currentBalance']), f'{len(rows)} rows')
    today = datetime.now(IST).date()
    future = api.get(f'/api/riders/{rider_id}/audit', **{'from': (today + timedelta(days=1)).isoformat()})[1]
    record('Wallet audit: a later start date has no rows but keeps the opening balance',
           future['total'] == 0 and future['openingBalance'] == body['currentBalance'])
    day = api.get(f'/api/riders/{rider_id}/audit', **{'from': today.isoformat(), 'to': today.isoformat()})[1]
    record('Wallet audit: a one-day filter returns today\'s rows', day['total'] == len(rows))


def check_concurrent_bookings(api, pg, vehicle_id):
    same, _ = free_rider(pg, 1000)
    before = wallet_state(pg, same)

    def book_same(_):
        return api.post_status('/api/trips', {'riderId': same, 'vehicleId': vehicle_id, 'fareAmount': '50.00'})
    with ThreadPoolExecutor(20) as pool:
        codes = sorted(pool.map(book_same, range(20)))
    after = wallet_state(pg, same)
    record('Concurrency: 20 simultaneous bookings for one rider create exactly one trip',
           codes == [201] + [409] * 19 and after[0] == before[0] - 50 and after[2] == before[2] + 1, codes.count(201))

    riders, skip = [], []
    for _ in range(50):
        rider_id, _ = free_rider(pg, 1000, skip=skip + [same])
        skip.append(rider_id)
        riders.append(rider_id)
    started = time.perf_counter()

    def book_one(rider_id):
        return api.post_status('/api/trips', {'riderId': rider_id, 'vehicleId': vehicle_id, 'fareAmount': '30.00'})
    with ThreadPoolExecutor(25) as pool:
        codes = list(pool.map(book_one, riders))
    timings['50 simultaneous bookings for 50 riders'] = {'status': sorted(set(codes)), 'seconds': round(time.perf_counter() - started, 3)}
    record('Concurrency: 50 simultaneous bookings for different riders all succeed', set(codes) == {201}, f'{codes.count(201)}/50')


# ---------------------------------------------------------------- analytics

def check_summary(api, pg, label):
    body = api.get('/api/analytics/summary', pageSize=100)[1]
    raw_trips = scalar(pg, 'SELECT COUNT(*) FROM trips')
    raw_fares = scalar(pg, "SELECT COALESCE(SUM(fare_amount),0) FROM trips WHERE status='COMPLETED'")
    record(label + ' - Summary: lifetime totals equal the raw trips table (all statuses counted, completed earnings)',
           body['totals']['lifetimeTripCount'] == raw_trips and Decimal(body['totals']['lifetimeEarnings']) == raw_fares,
           f"{body['totals']} stamp={body['lastRefreshedAt']}")
    record(label + ' - Summary: one row per vehicle', body['total'] == facts['postgres']['vehicles'])
    return body['lastRefreshedAt']


def check_refresh_after_writes(api, pg, old_stamp):
    stale = api.get('/api/analytics/summary', pageSize=1)[1]['totals']['lifetimeTripCount']
    raw = scalar(pg, 'SELECT COUNT(*) FROM trips')
    record('Summary: new bookings are not shown until a refresh', stale < raw, f'summary {stale}, raw {raw}')
    started = time.perf_counter()
    status, body = api.send('POST', '/api/analytics/refresh', None)
    seconds = round(time.perf_counter() - started, 3)
    timings['materialized view refresh'] = {'status': status, 'seconds': seconds}
    fresh = api.get('/api/analytics/summary', pageSize=1)[1]
    record('Refresh: saved time moves forward and totals now equal the raw table',
           status == 200 and body['lastRefreshedAt'] > old_stamp and fresh['totals']['lifetimeTripCount'] == raw,
           f'{seconds} s')


def completed_cents_by_vehicle_day(pg):
    """Daily completed revenue in whole paise, with the day worked out in Python."""
    daily = defaultdict(lambda: defaultdict(int))
    for vehicle_id, created_at, fare in query(pg, "SELECT vehicle_id, created_at, fare_amount FROM trips WHERE status='COMPLETED'"):
        daily[str(vehicle_id)][created_at.astimezone(IST).date()] += int(fare * 100)
    return daily


def reference_day(daily, vehicle_ids, day):
    """Seven calendar days ending on `day`: {vehicle: (daily paise, sum of 7 days, dense rank)}."""
    sums = {v: sum(daily[v].get(day - timedelta(days=k), 0) for k in range(7)) if v in daily else 0 for v in vehicle_ids}
    ranks = {total: place for place, total in enumerate(sorted(set(sums.values()), reverse=True), start=1)}
    return {v: (daily[v].get(day, 0) if v in daily else 0, sums[v], ranks[sums[v]]) for v in vehicle_ids}


def average_text(total_paise):
    return str((Decimal(total_paise) / 7 / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def revenue_reference(pg):
    """Python reference for the latest 30 Kolkata days: the vehicle ids, the days and each day's values."""
    vehicle_ids = [str(r[0]) for r in query(pg, 'SELECT id FROM vehicles')]
    daily = completed_cents_by_vehicle_day(pg)
    last = datetime.now(IST).date()
    days = [last - timedelta(days=29 - i) for i in range(30)]
    reference = {day: reference_day(daily, vehicle_ids, day) for day in days}
    facts['revenueCopyDistinctTripDays'] = scalar(
        pg, "SELECT COUNT(DISTINCT (created_at AT TIME ZONE 'Asia/Kolkata')::date) FROM trips WHERE status='COMPLETED'")
    return vehicle_ids, days, reference


def check_revenue_function(pg, vehicle_ids, days, reference):
    """Compare every vehicle's values from the SQL function with the reference, on three days."""
    for day in (days[0], days[15], days[-1]):
        rows = query(pg, 'SELECT vehicle_id, daily_revenue, moving_average, revenue_rank FROM api_vehicle_revenue(%s,%s)', [day, day])
        wrong = 0
        for vehicle_id, daily_revenue, average, rank in rows:
            paise, total, expected_rank = reference[day][str(vehicle_id)]
            wrong += not (int(daily_revenue * 100) == paise and format(average, '.2f') == average_text(total) and rank == expected_rank)
        record(f'Revenue SQL: all {len(rows)} vehicles match the Python reference on {day}',
               wrong == 0 and len(rows) == len(vehicle_ids), f'{wrong} differences')


def check_revenue_pages(api, vehicle_ids, days, reference):
    """The default API response, the first ranking page and a page that crosses from one day to the next."""
    last = days[-1]
    status, body, _, _ = api.get('/api/analytics/revenue', pageSize=100)
    record('Revenue API: default range is the latest 30 Kolkata days',
           status == 200 and body['from'] == days[0].isoformat() and body['to'] == last.isoformat())
    record('Revenue API: row total is vehicles x days', body['total'] == len(vehicle_ids) * 30, body['total'])
    best = sorted(reference[last].items(), key=lambda item: (item[1][2], item[0]))[:100]
    got = [(row['vehicleId'], row['rank'], row['movingAverage7Days'], row['dailyRevenue']) for row in body['rankings']]
    want = [(v, rank, average_text(total), format(Decimal(paise) / 100, '.2f')) for v, (paise, total, rank) in best]
    record('Revenue API: first 100 whole-fleet ranks for the latest day match the reference', got == want)

    # Rows are listed newest day first; 99 per page does not divide the fleet, so this page holds two days.
    per_page = 99
    page_number = len(vehicle_ids) // per_page + 1
    start = (page_number - 1) * per_page
    ordered = []
    for day in (last, last - timedelta(days=1)):
        ordered += sorted((rank, v, day) for v, (_, _, rank) in reference[day].items())
    want = [(v, day.isoformat(), rank) for rank, v, day in ordered[start:start + per_page]]
    body = api.get('/api/analytics/revenue', page=page_number, pageSize=per_page)[1]
    got = [(row['vehicleId'], row['date'], row['rank']) for row in body['rankings']]
    record('Revenue API: a page that crosses from one day to the next matches the reference',
           got == want and len({date for _, date, _ in got}) == 2 and len(got) == per_page,
           f'page {page_number} of size {per_page}')


def check_revenue_one_vehicle(api, vehicle_ids, days, reference):
    """A single vehicle keeps its whole-fleet rank on all 30 days."""
    last = days[-1]
    zero = [v for v in vehicle_ids if reference[last][v][1] == 0]
    earning = sorted((v for v in vehicle_ids if reference[last][v][1] > 0), key=lambda v: (reference[last][v][2], v))
    picks = {'best-ranked': earning[0], 'middle-ranked': earning[len(earning) // 2], 'no revenue': zero[0]}
    for label, vehicle_id in picks.items():
        body = api.get('/api/analytics/revenue', vehicleId=vehicle_id, pageSize=100)[1]
        got = [(r['date'], r['rank'], r['movingAverage7Days'], r['dailyRevenue']) for r in body['rankings']]
        want = []
        for day in reversed(days):
            paise, total, rank = reference[day][vehicle_id]
            want.append((day.isoformat(), rank, average_text(total), format(Decimal(paise) / 100, '.2f')))
        record(f'Revenue API: {label} vehicle keeps its whole-fleet rank on all 30 days', got == want and body['total'] == 30)
    record('Revenue API: vehicles with equal averages share a dense rank',
           len({reference[last][v][2] for v in zero}) == 1, f'{len(zero)} vehicles share the zero-revenue rank')


def check_revenue_limits(api, last):
    """Timings for the default and the 90-day maximum, and the 91-day refusal."""
    time_endpoint(api, 'revenue default 30 days, 25 rows', '/api/analytics/revenue', pageSize=25)
    ninety = {'from': (last - timedelta(days=89)).isoformat(), 'to': last.isoformat()}
    status = time_endpoint(api, 'revenue maximum 90 days, 25 rows', '/api/analytics/revenue', pageSize=25, **ninety)
    record('Revenue API: the 90-day maximum succeeds', status == 200)
    body = api.get('/api/analytics/revenue', pageSize=25, **ninety)[1]
    record('Revenue API: a 90-day response has 90 series days and a bounded size', len(body['series']) == 90 and len(body['rankings']) == 25)
    too_long = api.get('/api/analytics/revenue', **{'from': (last - timedelta(days=90)).isoformat(), 'to': last.isoformat()})[0]
    record('Revenue API: 91 days is refused', too_long == 422, f'status {too_long}')


def check_revenue(api, pg):
    vehicle_ids, days, reference = revenue_reference(pg)
    check_revenue_function(pg, vehicle_ids, days, reference)
    check_revenue_pages(api, vehicle_ids, days, reference)
    check_revenue_one_vehicle(api, vehicle_ids, days, reference)
    check_revenue_limits(api, days[-1])


# ---------------------------------------------------------------- nearby vehicles

def haversine(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_METRES * math.asin(math.sqrt(a))


def latest_pings(mdb):
    """The newest ping of every vehicle, newest by created_at and then _id."""
    pipeline = [{'$sort': {'vehicle_id': 1, 'created_at': -1, '_id': -1}},
                {'$group': {'_id': '$vehicle_id', 'ping': {'$first': '$$ROOT'}}}]
    return [row['ping'] for row in mdb.TelemetryPings.aggregate(pipeline, allowDiskUse=True)]


def expected_nearby(latest, active, origin, checked_at):
    oldest = checked_at - timedelta(seconds=7200)
    found = []
    for ping in latest:
        created = ping['created_at'].replace(tzinfo=timezone.utc)
        longitude, latitude = ping['location']['coordinates']
        distance = haversine(origin[0], origin[1], longitude, latitude)
        if ping['is_available'] and oldest <= created <= checked_at and distance <= 5000 and ping['vehicle_id'] in active:
            found.append((distance, ping['vehicle_id']))
    return sorted(found)


def check_nearby(api, pg, mdb):
    latest = latest_pings(mdb)
    active = {str(r[0]) for r in query(pg, 'SELECT id FROM vehicles WHERE is_active')}
    reference_size = len(expected_nearby(latest, active, ORIGIN, datetime.now(timezone.utc)))
    record('Nearby: fresh pings exist, so the comparisons below are not empty against empty',
           reference_size > 0, f'{reference_size} valid vehicles; pings expire 2 hours after seeding')
    if reference_size == 0:
        return
    for label, origin in {'Hyderabad demo origin': ORIGIN, 'city edge': (78.60, 17.50), 'far from any vehicle': (0.0, 0.0)}.items():
        for limit in (1, 10, 50):
            status, body, _, _ = api.get('/api/vehicles/nearby', longitude=origin[0], latitude=origin[1], limit=limit)
            checked_at = datetime.fromisoformat(body['checkedAt'].replace('Z', '+00:00'))
            want = expected_nearby(latest, active, origin, checked_at)
            got = [(item['vehicleId'], item['distanceMeters']) for item in body['items']]
            same_vehicles = [v for v, _ in got] == [v for _, v in want[:limit]]
            close = all(abs(d - w[0]) < 1 for (_, d), w in zip(got, want[:limit]))
            record(f'Nearby: {label}, limit {limit} matches the latest-ping reference',
                   status == 200 and same_vehicles and close and len(got) == min(limit, len(want)),
                   f'API {len(got)} items, reference has {len(want)} valid vehicles')
    status = api.get('/api/vehicles/nearby', longitude=ORIGIN[0], latitude=ORIGIN[1], limit=51)[0]
    record('Nearby: a limit above 50 is refused', status == 422)

    # How often does the latest-ping rule remove a vehicle that has an older valid ping?
    now = datetime.now(timezone.utc)
    candidates = list(mdb.TelemetryPings.aggregate([
        {'$geoNear': {'near': {'type': 'Point', 'coordinates': list(ORIGIN)}, 'key': 'location', 'distanceField': 'd',
                      'maxDistance': 5000, 'spherical': True,
                      'query': {'is_available': True, 'created_at': {'$gte': now - timedelta(seconds=7200), '$lte': now}}}},
        {'$group': {'_id': '$vehicle_id', 'pings': {'$sum': 1}}}], allowDiskUse=True))
    valid = len(expected_nearby(latest, active, ORIGIN, now))
    facts['nearby'] = {'vehiclesWithAnyAvailableFreshPingInRadius': len(candidates),
                       'candidatePings': sum(c['pings'] for c in candidates), 'validAfterLatestPingAndActiveChecks': valid}
    record('Nearby: the latest-ping rule removes vehicles whose older pings looked valid',
           valid < len(candidates), json.dumps(facts['nearby']))
    time_endpoint(api, 'nearby origin, limit 50', '/api/vehicles/nearby', runs=5, longitude=ORIGIN[0], latitude=ORIGIN[1], limit=50)
    time_endpoint(api, 'nearby origin, limit 1', '/api/vehicles/nearby', runs=5, longitude=ORIGIN[0], latitude=ORIGIN[1], limit=1)


# ---------------------------------------------------------------- reviews

def expected_summary(reviews):
    ratings = [r['rating'] for r in reviews]
    tags = defaultdict(int)
    for review in reviews:
        for tag in review.get('feedback_tags', []):
            tags[tag] += 1
    top = sorted(tags.items(), key=lambda item: (-item[1], item[0]))[:10]
    # MongoDB's $round sends an exact half to the even digit, so the expected value does too.
    average = None if not ratings else float((Decimal(sum(ratings)) / len(ratings)).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN))
    return len(ratings), average, [ratings.count(n) for n in range(1, 6)], top


def summary_matches(body, reviews):
    count, average, distribution, top = expected_summary(reviews)
    return (body['reviewCount'] == count and body['averageRating'] == average
            and [row['count'] for row in body['ratingDistribution']] == distribution
            and [(row['tag'], row['count']) for row in body['topTags']] == top)


def check_reviews(api, mdb):
    everything = list(mdb.TripReviews.find())
    record('Reviews: all-review summary matches Python totals', summary_matches(api.get('/api/reviews/summary')[1], everything), f'{len(everything)} reviews')

    counts = defaultdict(int)
    for review in everything:
        counts[review['vehicle_id']] += 1
    busiest = max(counts, key=counts.get)
    mine = [r for r in everything if r['vehicle_id'] == busiest]
    record('Reviews: one-vehicle summary matches', summary_matches(api.get('/api/reviews/summary', vehicleId=busiest)[1], mine), f'{len(mine)} reviews')

    today = datetime.now(IST).date()
    start, end = today - timedelta(days=20), today - timedelta(days=10)
    lower = datetime.combine(start, datetime.min.time(), IST).astimezone(timezone.utc).replace(tzinfo=None)
    upper = datetime.combine(end + timedelta(days=1), datetime.min.time(), IST).astimezone(timezone.utc).replace(tzinfo=None)
    window = [r for r in everything if lower <= r['created_at'] < upper]
    record('Reviews: a date filter is applied before the summary',
           summary_matches(api.get('/api/reviews/summary', **{'from': start.isoformat(), 'to': end.isoformat()})[1], window), f'{len(window)} reviews')

    no_review = next(v for v in (str(r['vehicle_id']) for r in mdb.VehicleMetadata.find({}, {'vehicle_id': 1})) if v not in counts)
    empty = api.get('/api/reviews/summary', vehicleId=no_review)[1]
    record('Reviews: no reviews gives no average rating, not zero', empty['reviewCount'] == 0 and empty['averageRating'] is None)

    ordered = [str(r['_id']) for r in sorted(everything, key=lambda r: (r['created_at'], r['_id']), reverse=True)]
    seen, page = [], 1
    while True:
        body = api.get('/api/reviews', page=page, pageSize=100)[1]
        seen += [item['id'] for item in body['items']]
        if len(body['items']) < 100:
            break
        page += 1
    record('Reviews: walking every page returns each review once, newest first', seen == ordered, f'{page} pages')
    time_endpoint(api, 'reviews summary, all', '/api/reviews/summary', runs=5)
    time_endpoint(api, 'reviews page 1, 100 rows', '/api/reviews', runs=5, pageSize=100)
    time_endpoint(api, 'reviews last page, 100 rows', '/api/reviews', runs=5, page=page, pageSize=100)


# ---------------------------------------------------------------- timings of the other screens

def time_screens(api, pg):
    rider_id = str(scalar(pg, 'SELECT id FROM riders ORDER BY id LIMIT 1'))
    for label, path, params in [
        ('riders page 1, 100 rows', '/api/riders', {'pageSize': 100}),
        ('riders search "Acharya"', '/api/riders', {'search': 'Acharya', 'pageSize': 25}),
        ('riders last page', '/api/riders', {'page': 1000, 'pageSize': 100}),
        ('vehicles page 1, 100 rows', '/api/vehicles', {'pageSize': 100}),
        ('vehicles class+active+search', '/api/vehicles', {'class': 'Bike', 'active': 'true', 'search': 'TS09', 'pageSize': 25}),
        ('trips page 1, 100 rows', '/api/trips', {'pageSize': 100}),
        ('trips COMPLETED page 300', '/api/trips', {'status': 'COMPLETED', 'page': 300, 'pageSize': 100}),
        ('wallet audit for one rider', f'/api/riders/{rider_id}/audit', {}),
        ('analytics summary, 100 rows', '/api/analytics/summary', {'pageSize': 100}),
        ('revenue default 30 days, as-seeded single-day data', '/api/analytics/revenue', {'pageSize': 25}),
    ]:
        time_endpoint(api, label, path, **params)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--api', required=True, help='API using the seeded scale databases (read-only checks)')
    parser.add_argument('--write-api', required=True, help='API using the disposable PostgreSQL copy')
    parser.add_argument('--write-db', required=True, help='name of that PostgreSQL copy')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    names = [os.getenv('PGDATABASE', ''), os.getenv('MONGO_DB', ''), args.write_db]
    if not all('scale' in name for name in names) or args.write_db == os.getenv('PGDATABASE'):
        sys.exit('Refusing to run: use scale databases, and a write copy that is not the seeded database.')
    if args.api.rstrip('/') == args.write_api.rstrip('/'):
        sys.exit('Refusing to run: --api and --write-api must be different servers.')

    pg = connect_postgres(os.environ['PGDATABASE'])
    pg.autocommit = True
    copy = connect_postgres(args.write_db)
    copy.autocommit = True
    client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'))
    mdb = client[os.environ['MONGO_DB']]
    api, write_api = Api(args.api), Api(args.write_api)
    if not (api_uses_database(api, pg) and api_uses_database(write_api, copy)):
        sys.exit('Refusing to run: an API does not serve the database it was paired with.')
    facts['startedAt'] = datetime.now(timezone.utc).isoformat()

    # Read-only checks on the seeded databases.
    collect_counts(pg, mdb)
    check_money_invariants(pg, 'As seeded')
    time_screens(api, pg)
    check_browse(api, pg, mdb)
    check_summary(api, pg, 'As seeded')
    check_nearby(api, pg, mdb)
    check_reviews(api, mdb)

    # Checks that write, on the disposable copy.
    stamp = check_summary(write_api, copy, 'Copy before writes')
    check_booking(write_api, copy)
    check_refresh_after_writes(write_api, copy, stamp)
    check_money_invariants(copy, 'Copy after booking tests')
    check_revenue(write_api, copy)
    facts['finishedAt'] = datetime.now(timezone.utc).isoformat()

    failed = [r for r in results if not r['passed']]
    Path(args.out).write_text(json.dumps({'facts': facts, 'timings': timings, 'checks': results,
                                          'passed': len(results) - len(failed), 'failed': len(failed)},
                                         indent=2, default=str))
    print(f'\n{len(results) - len(failed)} passed, {len(failed)} failed')
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
