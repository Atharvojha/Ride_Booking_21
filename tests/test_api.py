import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
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
        client[name].create_collection('VehicleMetadata')
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
