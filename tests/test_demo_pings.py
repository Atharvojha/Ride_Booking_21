import importlib.util
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest
from psycopg2 import sql
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = (78.4867, 17.3850)  # longitude, latitude


def load_helper():
    path = ROOT / 'data_generation' / 'refresh_demo_pings.py'
    spec = importlib.util.spec_from_file_location('refresh_demo_pings', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = load_helper()


def metres_between(longitude, latitude):
    """Distance from the origin using the haversine formula (MongoDB's earth radius)."""
    p1, p2 = math.radians(ORIGIN[1]), math.radians(latitude)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(longitude - ORIGIN[0]) / 2) ** 2
    return 2 * 6378100 * math.asin(math.sqrt(a))


def make_pings(count=20, unavailable=3, outside=3):
    import random
    now = datetime.now(timezone.utc)
    ids = [str(uuid4()) for _ in range(count)]
    return ids, now, helper.build_pings(ids, ORIGIN, now, random.Random(1), unavailable, outside)


def test_pings_are_placed_where_the_plan_says():
    ids, now, pings = make_pings()
    assert [p['vehicle_id'] for p in pings] == ids
    distances = [metres_between(*p['location']['coordinates']) for p in pings]
    assert all(d > 5000 for d in distances[:3]) and all(p['is_available'] for p in pings[:3])
    assert all(d < 4100 for d in distances[3:])
    assert [p['is_available'] for p in pings[3:6]] == [False] * 3
    assert all(p['is_available'] for p in pings[6:])


def test_pings_have_geojson_order_and_safe_timestamps():
    _, now, pings = make_pings()
    for ping in pings:
        longitude, latitude = ping['location']['coordinates']
        assert ping['location']['type'] == 'Point'
        assert abs(longitude - ORIGIN[0]) < 0.2 and abs(latitude - ORIGIN[1]) < 0.2  # longitude comes first
        assert now - timedelta(seconds=121) <= ping['created_at'] <= now  # never in the future
        assert set(ping) == {'vehicle_id', 'is_available', 'location', 'created_at'}


def test_too_few_vehicles_is_refused():
    with pytest.raises(ValueError):
        make_pings(count=6, unavailable=3, outside=3)


@pytest.fixture
def databases():
    name = 'ridesync_pings_test_' + uuid4().hex
    pg = {'host': os.getenv('PGHOST', 'localhost'), 'port': os.getenv('PGPORT', '5432'),
          'user': os.getenv('PGUSER', os.environ['USER']), 'password': os.getenv('PGPASSWORD', '')}
    admin = psycopg2.connect(dbname='postgres', **pg)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    conn = psycopg2.connect(dbname=name, **pg)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute((ROOT / 'sql' / '01_schema_ddl.sql').read_text())
    client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'), serverSelectionTimeoutMS=2000)
    try:
        yield name, conn, client[name]
    finally:
        conn.close()
        client.drop_database(name)
        client.close()
        with admin.cursor() as cur:
            cur.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
        admin.close()


def add_vehicles(conn, count, inactive=2):
    ids = [str(uuid4()) for _ in range(count)]
    with conn.cursor() as cur:
        for number, vehicle_id in enumerate(ids):
            cur.execute('INSERT INTO vehicles(id, license_plate, class, is_active) VALUES (%s, %s, %s, %s)',
                        [vehicle_id, f'TEST{number:04d}', 'Mini', number >= inactive])
    return ids


def test_only_active_vehicles_are_chosen(databases):
    _, conn, _ = databases
    ids = add_vehicles(conn, 6, inactive=2)
    assert helper.choose_active_vehicles(conn, 10) == ids[2:]
    assert helper.choose_active_vehicles(conn, 2) == ids[2:4]


def test_running_the_helper_adds_only_telemetry(databases, monkeypatch):
    name, conn, mdb = databases
    ids = add_vehicles(conn, 12, inactive=2)
    old_ping = {'vehicle_id': ids[5], 'is_available': True, 'created_at': datetime(2026, 1, 1),
                'location': {'type': 'Point', 'coordinates': [78.5, 17.4]}}
    mdb.TelemetryPings.insert_one(old_ping)
    mdb.TripReviews.insert_many([{'trip_id': 'a', 'vehicle_id': ids[5], 'rating': 5, 'feedback_tags': ['ON_TIME']}])
    mdb.VehicleMetadata.insert_one({'vehicle_id': ids[5], 'features': {'ac': True}})
    before = {c: list(mdb[c].find().sort('_id')) for c in ('TripReviews', 'VehicleMetadata')}
    with conn.cursor() as cur:
        cur.execute('SELECT (SELECT COUNT(*) FROM vehicles), (SELECT COUNT(*) FROM trips), (SELECT COUNT(*) FROM riders)')
        sql_before = cur.fetchone()

    monkeypatch.setenv('PGDATABASE', name)
    monkeypatch.setenv('MONGO_DB', name)
    monkeypatch.setattr(sys, 'argv', ['refresh_demo_pings.py', '--count', '8', '--unavailable', '2', '--outside', '2'])
    helper.main()

    pings = list(mdb.TelemetryPings.find({'_id': {'$ne': old_ping['_id']}}))
    assert len(pings) == 8 and mdb.TelemetryPings.find_one({'_id': old_ping['_id']}) == old_ping
    assert {p['vehicle_id'] for p in pings} <= set(ids[2:])        # only active vehicles
    assert {c: list(mdb[c].find().sort('_id')) for c in ('TripReviews', 'VehicleMetadata')} == before
    with conn.cursor() as cur:
        cur.execute('SELECT (SELECT COUNT(*) FROM vehicles), (SELECT COUNT(*) FROM trips), (SELECT COUNT(*) FROM riders)')
        assert cur.fetchone() == sql_before
    inside = [p for p in pings if metres_between(*p['location']['coordinates']) <= 5000 and p['is_available']]
    assert len(inside) == 4


def test_dry_run_inserts_nothing(databases, monkeypatch):
    name, conn, mdb = databases
    add_vehicles(conn, 12)
    monkeypatch.setenv('PGDATABASE', name)
    monkeypatch.setenv('MONGO_DB', name)
    monkeypatch.setattr(sys, 'argv', ['refresh_demo_pings.py', '--count', '8', '--dry-run'])
    helper.main()
    assert mdb.TelemetryPings.count_documents({}) == 0


@pytest.mark.parametrize('arguments', [['--unavailable', '-2'], ['--count', '6'], ['--count', '0']])
def test_bad_options_give_a_short_message_and_insert_nothing(arguments, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['refresh_demo_pings.py', *arguments])
    with pytest.raises(SystemExit) as stopped:
        helper.main()
    assert isinstance(stopped.value.code, str)  # a message, not a traceback
