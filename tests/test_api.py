import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from threading import Barrier, Event
from uuid import uuid4
from time import monotonic

import psycopg2
from psycopg2 import sql
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient

from api.analytics import days_for_page
from api.main import app

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def database():
    name = 'ridesync_api_test_' + uuid4().hex
    pg = {'host': os.getenv('PGHOST', 'localhost'), 'port': os.getenv('PGPORT', '5432'),
          'user': os.getenv('PGUSER', os.environ['USER']), 'password': os.getenv('PGPASSWORD', '')}
    admin = psycopg2.connect(dbname='postgres', **pg)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    conn = psycopg2.connect(dbname=name, **pg)
    conn.autocommit = True
    client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'), serverSelectionTimeoutMS=2000)
    saved = {key: os.environ.get(key) for key in ('PGDATABASE', 'MONGO_DB', 'PGUSER')}
    os.environ.update(PGDATABASE=name, MONGO_DB=name, PGUSER=pg['user'])
    try:
        with conn.cursor() as cur:
            for path in sorted((ROOT / 'sql').glob('*.sql')):
                cur.execute(path.read_text())
        for script in ('01_collections_and_indexes.js', '04_api_indexes.js'):
            subprocess.run(['mongosh', os.getenv('MONGO_URI', 'mongodb://localhost:27017'),
                            '--quiet', '--file', str(ROOT / 'mongo' / script)],
                           check=True, capture_output=True, text=True, env=os.environ.copy())
        yield conn, client[name]
    finally:
        conn.close()
        client.drop_database(name)
        client.close()
        with admin.cursor() as cur:
            cur.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
        admin.close()
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture
def browser(database):
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def records(database):
    conn, db = database
    rider_id, vehicle_id, inactive_id = [str(uuid4()) for _ in range(3)]
    with conn.cursor() as cur:
        cur.execute('INSERT INTO riders(id,name,wallet_balance) VALUES(%s,%s,500)', [rider_id, 'Test ' + rider_id])
        cur.execute('INSERT INTO vehicles(id,license_plate,class,is_active) VALUES(%s,%s,%s,TRUE),(%s,%s,%s,FALSE)',
                    [vehicle_id, 'T' + vehicle_id[:12], 'Custom class', inactive_id, 'T' + inactive_id[:12], 'Sedan'])
    return rider_id, vehicle_id, inactive_id


def book(browser, records, fare='120.00'):
    rider_id, vehicle_id, _ = records
    return browser.post('/api/trips', json={'riderId': rider_id, 'vehicleId': vehicle_id, 'fareAmount': fare})


def state(database, rider_id):
    with database[0].cursor() as cur:
        cur.execute('SELECT wallet_balance,(SELECT COUNT(*) FROM trips WHERE rider_id=%s),(SELECT COUNT(*) FROM wallet_audit_logs WHERE rider_id=%s) FROM riders WHERE id=%s',
                    [rider_id] * 3)
        return cur.fetchone()


def test_health_and_details(browser, records, database):
    assert browser.get('/api/health').json() == {'postgres': 'ok', 'mongo': 'ok'}
    rider_id, vehicle_id, _ = records
    assert browser.get('/api/riders/' + rider_id).json()['rider']['walletBalance'] == '500.00'
    assert browser.get('/api/vehicles/' + vehicle_id).json()['metadata'] is None
    database[1].VehicleMetadata.insert_one({'vehicle_id': vehicle_id, 'features': {'wifi': True},
                                          'inspection_records': [{'passed': True, 'date': datetime(2026, 10, 10, tzinfo=timezone.utc)}],
                                          'created_at': datetime(2026, 10, 11, tzinfo=timezone.utc)})
    detail = browser.get('/api/vehicles/' + vehicle_id).json()
    assert detail['metadata']['features'] == {'wifi': True}
    assert detail['metadata']['createdAt'].endswith('Z')
    assert detail['metadata']['inspectionRecords'][0]['date'].endswith('Z')


def test_browse_search_pages_and_filters(browser, records):
    rider_id, vehicle_id, inactive_id = records
    first = browser.get('/api/riders', params={'search': rider_id, 'pageSize': 1}).json()
    assert first['total'] == 1 and first['items'][0]['id'] == rider_id
    assert browser.get('/api/riders', params={'search': rider_id, 'page': 2, 'pageSize': 1}).json()['items'] == []
    assert browser.get('/api/riders', params={'search': "' OR 1=1 --"}).json()['total'] == 0
    assert browser.get('/api/vehicles', params={'class': 'Custom class', 'search': vehicle_id, 'active': True}).json()['total'] == 1
    assert browser.get('/api/vehicles', params={'search': inactive_id, 'active': True}).json()['total'] == 0


@pytest.mark.parametrize('fare', ['0', '-1', '1.001', 'NaN', 'Infinity', '100000000.00', 'abc', '1e2', 120, None])
def test_invalid_fares_do_not_change_wallet(browser, records, database, fare):
    response = book(browser, records, fare)
    assert response.status_code == 422 and response.json()['error']['code'] == 'INVALID_INPUT'
    assert state(database, records[0]) == (Decimal('500.00'), 0, 0)


def test_number_fare_message_says_to_send_text(browser, records, database):
    message = book(browser, records, 120).json()['error']['message']
    assert 'as text' in message and '"120.00"' in message
    assert state(database, records[0]) == (Decimal('500.00'), 0, 0)


@pytest.mark.parametrize('path', ['/api/riders/not-a-uuid', '/api/vehicles/not-a-uuid', '/api/trips/not-a-uuid', '/api/riders?pageSize=101', '/api/riders?page=0', '/api/vehicles?active=maybe', '/api/trips?status=CANCELLED', '/api/trips?from=2026-02-30', '/api/trips?from=2026-10-12&to=2026-10-11'])
def test_bad_filters_have_friendly_errors(browser, path):
    response = browser.get(path)
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'INVALID_INPUT'


def test_missing_records(browser):
    missing = str(uuid4())
    for path in ['/api/riders/', '/api/vehicles/', '/api/trips/']:
        assert browser.get(path + missing).status_code == 404
    assert browser.get('/api/riders/' + missing + '/audit').status_code == 404


def test_booking_returns_exact_trigger_row(browser, records, database):
    result = book(browser, records)
    assert result.status_code == 201, result.text
    data = result.json()
    assert (data['balanceBefore'], data['balanceAfter']) == ('500.00', '380.00')
    assert data['auditEntry']['actionType'] == 'ESCROW_HOLD'
    with database[0].cursor() as cur:
        cur.execute('SELECT amount_changed,balance_after,rider_id FROM wallet_audit_logs WHERE id=%s', [data['auditEntry']['id']])
        row = cur.fetchone()
        assert row[:2] == (Decimal('-120.00'), Decimal('380.00'))
        assert str(row[2]) == records[0]
    assert state(database, records[0]) == (Decimal('380.00'), 1, 1)
    assert browser.get('/api/trips/' + data['trip']['id']).json()['trip']['status'] == 'REQUESTED'
    listed = browser.get('/api/trips', params={'riderId': records[0], 'vehicleId': records[1], 'status': 'REQUESTED'}).json()
    assert listed['total'] == 1 and listed['items'][0]['id'] == data['trip']['id']


def test_failed_bookings_leave_no_debit(browser, records, database):
    low = book(browser, records, '501.00')
    assert low.status_code == 409 and low.json()['error']['code'] == 'INSUFFICIENT_BALANCE'
    inactive = browser.post('/api/trips', json={'riderId': records[0], 'vehicleId': records[2], 'fareAmount': '20.00'})
    assert inactive.status_code == 409 and inactive.json()['error']['code'] == 'VEHICLE_INACTIVE'
    missing = browser.post('/api/trips', json={'riderId': records[0], 'vehicleId': str(uuid4()), 'fareAmount': '20.00'})
    assert missing.status_code == 404
    assert state(database, records[0]) == (Decimal('500.00'), 0, 0)
    assert book(browser, records).status_code == 201
    duplicate = book(browser, records)
    assert duplicate.status_code == 409 and duplicate.json()['error']['code'] == 'ACTIVE_TRIP_EXISTS'
    assert state(database, records[0]) == (Decimal('380.00'), 1, 1)


def test_trip_statuses_release_once_and_allow_next_booking(browser, records, database):
    trip_id = book(browser, records).json()['trip']['id']
    path = '/api/trips/' + trip_id + '/status'
    assert browser.patch(path, json={'status': 'COMPLETED'}).status_code == 409
    assert browser.patch(path, json={'status': 'IN TRANSIT'}).json()['trip']['status'] == 'IN TRANSIT'
    assert browser.patch(path, json={'status': 'IN TRANSIT'}).status_code == 409
    assert browser.patch(path, json={'status': 'COMPLETED'}).json()['trip']['status'] == 'COMPLETED'
    assert browser.patch(path, json={'status': 'COMPLETED'}).status_code == 409
    assert state(database, records[0]) == (Decimal('380.00'), 1, 2)
    assert book(browser, records).status_code == 201


def test_simultaneous_bookings_charge_once(browser, records, database):
    barrier = Barrier(2)
    def submit():
        barrier.wait(timeout=5)
        return book(browser, records)
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: submit(), range(2)))
    assert sorted(reply.status_code for reply in replies) == [201, 409]
    failed = next(reply for reply in replies if reply.status_code == 409)
    assert failed.json()['error']['code'] == 'ACTIVE_TRIP_EXISTS'
    assert state(database, records[0]) == (Decimal('380.00'), 1, 1)


def test_simultaneous_completion_has_one_release(browser, records, database):
    trip_id = book(browser, records).json()['trip']['id']
    path = '/api/trips/' + trip_id + '/status'
    assert browser.patch(path, json={'status': 'IN TRANSIT'}).status_code == 200
    barrier = Barrier(2)
    def complete():
        barrier.wait(timeout=5)
        return browser.patch(path, json={'status': 'COMPLETED'})
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda _: complete(), range(2)))
    assert sorted(reply.status_code for reply in replies) == [200, 409]
    assert state(database, records[0]) == (Decimal('380.00'), 1, 2)


def test_audit_dates_and_page_keep_stored_balance(browser, records, database):
    rider_id = records[0]
    entries = [('2026-10-10T18:29:59Z', '50.00', '550.00'),
               ('2026-10-10T18:30:00Z', '-20.00', '530.00'),
               ('2026-10-11T18:29:59Z', '-30.00', '500.00'),
               ('2026-10-11T18:30:00Z', '10.00', '510.00')]
    with database[0].cursor() as cur:
        for timestamp, amount, balance in entries:
            cur.execute('INSERT INTO wallet_audit_logs(rider_id,amount_changed,action_type,balance_after,timestamp) VALUES(%s,%s,%s,%s,%s)',
                        [rider_id, amount, 'CREDIT' if Decimal(amount) > 0 else 'DEBIT', balance, timestamp])
    params = {'from': '2026-10-11', 'to': '2026-10-11', 'page': 2, 'pageSize': 1}
    data = browser.get('/api/riders/' + rider_id + '/audit', params=params).json()
    assert data['total'] == 2 and data['openingBalance'] == '550.00'
    assert data['items'][0]['balanceAfter'] == '500.00'
    assert data['items'][0]['timestamp'].endswith('Z')
    earlier = browser.get('/api/riders/' + rider_id + '/audit', params={'to': '2020-01-01'}).json()
    assert earlier['items'] == [] and earlier['openingBalance'] is None


def test_empty_audit_does_not_invent_opening_balance(browser, records):
    data = browser.get('/api/riders/' + records[0] + '/audit').json()
    assert data['items'] == [] and data['openingBalance'] is None and data['currentBalance'] == '500.00'


def test_database_outage_is_friendly(browser, monkeypatch):
    monkeypatch.setenv('PGDATABASE', 'ridesync_missing_' + uuid4().hex)
    result = browser.get('/api/riders')
    assert result.status_code == 503 and result.json()['error']['code'] == 'DATABASE_UNAVAILABLE'
    assert 'password' not in result.text.lower()
    assert browser.get('/api/health').json()['postgres'] == 'unavailable'


def test_metadata_outage_is_separate(browser, records, monkeypatch):
    monkeypatch.setenv('MONGO_URI', 'mongodb://127.0.0.1:1')
    result = browser.get('/api/vehicles/' + records[1])
    assert result.status_code == 200 and result.json()['vehicle']['id'] == records[1]
    assert result.json()['metadataError']['code'] == 'DATABASE_UNAVAILABLE'


def test_migration_can_be_reapplied(database):
    with database[0].cursor() as cur:
        for name in ['03_triggers_and_audit.sql', '04_stored_procedures.sql']:
            cur.execute((ROOT / 'sql' / name).read_text())


def test_huge_empty_page_does_not_overflow(browser):
    response = browser.get('/api/riders', params={'page': 10**30, 'pageSize': 100})
    assert response.status_code == 200 and response.json()['items'] == []


def test_booking_and_topup_keep_the_exact_charge(browser, records, database):
    from api.database import postgres
    barrier = Barrier(2)
    def submit():
        barrier.wait(timeout=5)
        return book(browser, records)
    def topup():
        barrier.wait(timeout=5)
        with postgres(write=True) as conn:
            with conn.cursor() as cur:
                cur.execute('UPDATE riders SET wallet_balance=wallet_balance+50 WHERE id=%s', [records[0]])
    with ThreadPoolExecutor(max_workers=2) as pool:
        booked = pool.submit(submit)
        credited = pool.submit(topup)
        response = booked.result()
        credited.result()
    assert response.status_code == 201
    data = response.json()
    assert Decimal(data['balanceBefore']) - Decimal(data['balanceAfter']) == Decimal('120.00')
    assert data['auditEntry']['amountChanged'] == '-120.00'
    assert data['auditEntry']['actionType'] == 'ESCROW_HOLD'
    assert state(database, records[0]) == (Decimal('430.00'), 1, 2)


def test_booking_without_audit_trigger_rolls_back(browser, records, database):
    conn = database[0]
    with conn.cursor() as cur:
        cur.execute('ALTER TABLE riders DISABLE TRIGGER trg_wallet_audit')
    try:
        response = book(browser, records)
        assert response.status_code == 500 and response.json()['error']['code'] == 'INTERNAL_ERROR'
        assert state(database, records[0]) == (Decimal('500.00'), 0, 0)
    finally:
        with conn.cursor() as cur:
            cur.execute('ALTER TABLE riders ENABLE TRIGGER trg_wallet_audit')


def test_completion_waiting_for_topup_keeps_audit_order(browser, records, database):
    rider_id = records[0]
    trip_id = book(browser, records, '100.00').json()['trip']['id']
    path = '/api/trips/' + trip_id + '/status'
    assert browser.patch(path, json={'status': 'IN TRANSIT'}).status_code == 200
    holder = psycopg2.connect(database[0].dsn)
    try:
        with holder.cursor() as cur:
            cur.execute('SELECT id FROM riders WHERE id=%s FOR UPDATE', [rider_id])
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(browser.patch, path, json={'status': 'COMPLETED'})
            try:
                deadline = monotonic() + 3
                waiting = False
                while monotonic() < deadline:
                    with database[0].cursor() as cur:
                        cur.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'CALL sp_release_escrow%%')")
                        waiting = cur.fetchone()[0]
                    if waiting:
                        break
                    Event().wait(0.02)
                assert waiting, 'Completion did not reach the locked wallet'
                with holder.cursor() as cur:
                    cur.execute("SELECT set_config('ridesync.wallet_action','CREDIT',true)")
                    cur.execute('UPDATE riders SET wallet_balance=wallet_balance+50 WHERE id=%s', [rider_id])
                holder.commit()
                assert pending.result(timeout=5).status_code == 200
            finally:
                holder.rollback()
    finally:
        holder.close()
    data = browser.get('/api/riders/' + rider_id + '/audit').json()
    assert [(row['actionType'], row['amountChanged'], row['balanceAfter']) for row in data['items']] == [
        ('ESCROW_HOLD', '-100.00', '400.00'), ('CREDIT', '50.00', '450.00'),
        ('ESCROW_RELEASE', '0.00', '450.00')]



def test_calendar_revenue_and_whole_fleet_ranks(browser, records, database):
    rider, vehicle, tied = records
    high = str(uuid4())
    with database[0].cursor() as cur:
        cur.execute("INSERT INTO vehicles(id,license_plate,class) VALUES(%s,%s,'Sedan')", [high, 'H' + high[:12]])
        for chosen, fare, stamp, status in [
            (vehicle, 70, '2026-09-01T12:00:00Z', 'COMPLETED'),
            (tied, 70, '2026-09-01T12:00:00Z', 'COMPLETED'),
            (high, 140, '2026-09-07T12:00:00Z', 'COMPLETED'),
            (vehicle, 999, '2026-09-07T12:00:00Z', 'REQUESTED'),
        ]:
            cur.execute('INSERT INTO trips(rider_id,vehicle_id,fare_amount,created_at,status) VALUES(%s,%s,%s,%s,%s)',
                        [rider, chosen, fare, stamp, status])
    params = {'vehicleId': vehicle, 'from': '2026-09-07', 'to': '2026-09-09', 'pageSize': 1}
    result = browser.get('/api/analytics/revenue', params=params).json()
    assert result['selectedVehicleId'] == vehicle and result['timezone'] == 'Asia/Kolkata'
    assert result['total'] == 3 and len(result['rankings']) == 1
    assert [row['dailyRevenue'] for row in result['series']] == ['0.00'] * 3
    assert [row['movingAverage7Days'] for row in result['series']] == ['10.00', '0.00', '0.00']
    params['page'] = 3
    row = browser.get('/api/analytics/revenue', params=params).json()['rankings'][0]
    assert row['date'] == '2026-09-07' and row['rank'] == 2
    params.update(vehicleId=tied)
    assert browser.get('/api/analytics/revenue', params=params).json()['rankings'][0]['rank'] == 2
    params['page'] = 4
    assert browser.get('/api/analytics/revenue', params=params).json()['rankings'] == []


def test_days_for_page_matches_a_row_by_row_list():
    # No database: list every row (newest day first, `per_day` rows a day) and check the days chosen for each page.
    first, last = date(2026, 9, 1), date(2026, 9, 12)
    days = (last - first).days + 1
    for per_day in (1, 2, 5, 7, 40):
        rows = [(last - timedelta(days=index // per_day), index % per_day) for index in range(days * per_day)]
        for page_size in (1, 3, 10, 25, 100):
            for page in range(1, len(rows) // page_size + 2):
                start = (page - 1) * page_size
                wanted = rows[start:start + page_size]
                if not wanted:
                    continue
                low, high, skip = days_for_page(first, last, per_day, page, page_size)
                available = [row for row in rows if low <= row[0] <= high]
                assert available[skip:skip + page_size] == wanted
                assert low >= first and high <= last


def walk_revenue_pages(browser, params, page_size):
    seen, page = [], 1
    while True:
        body = browser.get('/api/analytics/revenue', params={**params, 'page': page, 'pageSize': page_size}).json()
        if not body['rankings']:
            return seen, body['total']
        seen += [(row['vehicleId'], row['date'], row['rank']) for row in body['rankings']]
        page += 1


def test_revenue_pages_match_the_whole_list_across_day_borders(browser, records, database):
    # Make sure the fleet is big enough, whatever other tests left behind.
    with database[0].cursor() as cur:
        for _ in range(10):
            vehicle_id = str(uuid4())
            cur.execute("INSERT INTO vehicles(id,license_plate,class) VALUES(%s,%s,'Mini')", [vehicle_id, 'B' + vehicle_id[:12]])
        cur.execute('SELECT COUNT(*) FROM vehicles')
        fleet = cur.fetchone()[0]
        params = {'from': '2026-09-07', 'to': '2026-09-09'}
        cur.execute('SELECT vehicle_id::text, revenue_date::text, revenue_rank FROM api_vehicle_revenue(%s,%s) '
                    'ORDER BY revenue_date DESC, revenue_rank, vehicle_id', [params['from'], params['to']])
        expected = cur.fetchall()
    # A page size that does not divide the fleet makes pages hold the end of one day and the
    # start of the next. A page larger than the fleet covers all three days at once.
    border_size = next(size for size in (7, 6, 5, 4, 3) if fleet % size)
    for page_size in (border_size, 100):
        seen, total = walk_revenue_pages(browser, params, page_size)
        assert total == len(expected) == fleet * 3
        assert seen == expected


def test_revenue_uses_local_days(browser, records, database):
    rider, vehicle, _ = records
    with database[0].cursor() as cur:
        cur.execute("INSERT INTO trips(rider_id,vehicle_id,fare_amount,status,created_at) VALUES(%s,%s,7,'COMPLETED','2026-08-31T18:30:00Z')", [rider, vehicle])
    result = browser.get('/api/analytics/revenue', params={'vehicleId': vehicle, 'from': '2026-08-31', 'to': '2026-09-01'}).json()
    assert [row['dailyRevenue'] for row in result['series']] == ['0.00', '7.00']
    assert result['series'][1]['movingAverage7Days'] == '1.00'


def test_summary_refresh_and_unknown_time(browser, records, database):
    rider, vehicle, _ = records
    params = {'vehicleId': vehicle}
    before = browser.get('/api/analytics/summary', params=params).json()
    assert before['lastRefreshedAt'] is None and before['total'] == 0
    with database[0].cursor() as cur:
        for status, fare in [('COMPLETED', 12), ('REQUESTED', 100)]:
            cur.execute('INSERT INTO trips(rider_id,vehicle_id,fare_amount,status) VALUES(%s,%s,%s,%s)', [rider, vehicle, fare, status])
    response = browser.post('/api/analytics/refresh')
    assert response.status_code == 200
    stamp = response.json()['lastRefreshedAt']
    assert stamp.endswith('Z')
    result = browser.get('/api/analytics/summary', params=params).json()
    assert result['lastRefreshedAt'] == stamp and result['total'] == 1
    assert result['totals'] == {'lifetimeTripCount': 2, 'lifetimeEarnings': '12.00'}
    assert result['items'][0]['lifetimeTripCount'] == 2
    params.update(page=2, pageSize=1)
    later = browser.get('/api/analytics/summary', params=params).json()
    assert later['items'] == [] and later['totals'] == result['totals']


def test_refresh_lock_and_failed_refresh_keep_stamp(browser, database):
    conn = database[0]
    before = browser.get('/api/analytics/summary').json()['lastRefreshedAt']
    with conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_lock(10,6302)')
        try:
            response = browser.post('/api/analytics/refresh')
            assert response.status_code == 409 and response.json()['error']['code'] == 'REFRESH_IN_PROGRESS'
        finally:
            cur.execute('SELECT pg_advisory_unlock(10,6302)')
        cur.execute('DROP INDEX idx_mv_vehicle_lifetime_stats_vehicle_id')
        try:
            assert browser.post('/api/analytics/refresh').status_code == 503
            assert browser.get('/api/analytics/summary').json()['lastRefreshedAt'] == before
        finally:
            cur.execute('CREATE UNIQUE INDEX idx_mv_vehicle_lifetime_stats_vehicle_id ON mv_vehicle_lifetime_stats(vehicle_id)')
        cur.execute((ROOT / 'sql/07_api_refresh_state.sql').read_text())
    assert browser.get('/api/analytics/summary').json()['lastRefreshedAt'] == before


def test_nearby_uses_latest_ping_before_filters_and_limit(browser, records, database):
    _, vehicle, inactive = records
    db = database[1]
    now = datetime.now(timezone.utc) - timedelta(seconds=5)
    ids = [str(uuid4()) for _ in range(5)]
    with database[0].cursor() as cur:
        for chosen in ids:
            cur.execute("INSERT INTO vehicles(id,license_plate,class) VALUES(%s,%s,'Sedan')", [chosen, 'N' + chosen[:12]])
    def ping(chosen, seconds=0, available=True, longitude=78.4867):
        return {'vehicle_id': chosen, 'created_at': now + timedelta(seconds=seconds),
                'is_available': available, 'location': {'type': 'Point', 'coordinates': [longitude, 17.3850]}}
    rows = [ping(inactive), ping('bad-id'), ping(str(uuid4())), ping(vehicle, longitude=78.4877)]
    rows += [ping(ids[0], -10), ping(ids[0], available=False)]
    rows += [ping(ids[1], -10), ping(ids[1], longitude=79.4867)]
    rows += [ping(ids[2], -7300), ping(ids[3], 100)]
    rows += [ping(ids[4]), ping(ids[4], available=False)]
    db.TelemetryPings.insert_many(rows)
    result = browser.get('/api/vehicles/nearby', params={'longitude': 78.4867, 'latitude': 17.3850, 'limit': 1}).json()
    assert result['radiusMeters'] == 5000 and result['freshnessSeconds'] == 7200
    assert [row['vehicleId'] for row in result['items']] == [vehicle]
    assert 100 < result['items'][0]['distanceMeters'] < 110
    assert result['items'][0]['pingAt'].endswith('Z')
    db.TelemetryPings.delete_many({})


def test_nearby_handles_batches_of_missing_vehicles(browser, records, database):
    _, vehicle, _ = records
    now = datetime.now(timezone.utc) - timedelta(seconds=1)
    ids = [str(uuid4()) for _ in range(105)] + [vehicle]
    database[1].TelemetryPings.insert_many([
        {'vehicle_id': chosen, 'created_at': now, 'is_available': True,
         'location': {'type': 'Point', 'coordinates': [78.4867 + index * 0.00001, 17.3850]}}
        for index, chosen in enumerate(ids)])
    response = browser.get('/api/vehicles/nearby', params={'longitude': 78.4867, 'latitude': 17.3850, 'limit': 1})
    assert response.status_code == 200
    assert [row['vehicleId'] for row in response.json()['items']] == [vehicle]
    database[1].TelemetryPings.delete_many({})


def test_review_facets_local_dates_and_stable_pages(browser, records, database):
    _, vehicle, _ = records
    docs = []
    for rating, stamp, tags in [(1, '2026-09-01T18:29:59+00:00', ['early']),
                                (5, '2026-09-01T18:30:00+00:00', ['clean', 'safe']),
                                (3, '2026-09-02T18:29:59+00:00', ['clean']),
                                (5, '2026-09-02T18:29:59+00:00', ['safe']),
                                (1, '2026-09-02T18:30:00+00:00', ['late'])]:
        docs.append({'trip_id': str(uuid4()), 'vehicle_id': vehicle, 'rating': rating,
                     'feedback_tags': tags, 'created_at': datetime.fromisoformat(stamp)})
    inserted = database[1].TripReviews.insert_many(docs).inserted_ids
    params = {'vehicleId': vehicle, 'from': '2026-09-02', 'to': '2026-09-02'}
    result = browser.get('/api/reviews/summary', params=params).json()
    assert result['reviewCount'] == 3 and result['averageRating'] == 4.33
    assert [row['count'] for row in result['ratingDistribution']] == [0, 0, 1, 0, 2]
    assert result['topTags'] == [{'tag': 'clean', 'count': 2}, {'tag': 'safe', 'count': 2}]
    params.update(pageSize=1)
    first = browser.get('/api/reviews', params=params).json()
    assert first['total'] == 3 and first['items'][0]['id'] == str(inserted[3])
    assert first['items'][0]['createdAt'] == '2026-09-02T18:29:59Z'
    params['page'] = 2
    assert browser.get('/api/reviews', params=params).json()['items'][0]['id'] == str(inserted[2])
    params['page'] = 10**30
    last = browser.get('/api/reviews', params=params).json()
    assert last['items'] == [] and last['total'] == 3


def test_empty_review_results(browser, records):
    params = {'vehicleId': records[1]}
    result = browser.get('/api/reviews/summary', params=params).json()
    assert result['reviewCount'] == 0 and result['averageRating'] is None and result['topTags'] == []
    assert all(row['count'] == 0 for row in result['ratingDistribution'])
    assert browser.get('/api/reviews', params=params).json()['items'] == []


@pytest.mark.parametrize('path,params', [
    ('/api/analytics/revenue', {'from': '2026-01-01', 'to': '2026-04-01'}),
    ('/api/analytics/revenue', {'from': '0001-01-01', 'to': '0001-01-07'}),
    ('/api/analytics/revenue', {'from': '9999-12-31', 'to': '9999-12-31'}),
    ('/api/analytics/revenue', {'from': '2026-02-30'}),
    ('/api/analytics/revenue', {'vehicleId': 'bad'}),
    ('/api/analytics/summary', {'pageSize': 101}),
    ('/api/reviews', {'from': '2026-09-03', 'to': '2026-09-01'}),
    ('/api/reviews/summary', {'to': '9999-12-31'}),
    ('/api/vehicles/nearby', {'longitude': 'NaN', 'latitude': 17}),
    ('/api/vehicles/nearby', {'longitude': 'Infinity', 'latitude': 17}),
    ('/api/vehicles/nearby', {'longitude': 181, 'latitude': 17}),
    ('/api/vehicles/nearby', {'longitude': 78, 'latitude': 91}),
    ('/api/vehicles/nearby', {'longitude': 78, 'latitude': 17, 'limit': 51}),
])
def test_new_routes_reject_invalid_input(browser, path, params):
    response = browser.get(path, params=params)
    assert response.status_code == 422 and response.json()['error']['code'] == 'INVALID_INPUT'


@pytest.mark.parametrize('path,params', [
    ('/api/reviews', {}), ('/api/reviews/summary', {}),
    ('/api/vehicles/nearby', {'longitude': 78.4867, 'latitude': 17.3850}),
])
def test_new_routes_report_mongo_outage(browser, monkeypatch, path, params):
    monkeypatch.setenv('MONGO_URI', 'mongodb://127.0.0.1:27099')
    response = browser.get(path, params=params)
    assert response.status_code == 503 and response.json()['error']['code'] == 'DATABASE_UNAVAILABLE'
