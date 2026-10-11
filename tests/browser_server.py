"""Temporary databases for browser tests. The demo database is never used."""
import os
import signal
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from pymongo import MongoClient
import uvicorn
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / '.env')


def stop(signum, frame):
    raise SystemExit(0)


def run():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    name = 'ridesync_browser_test_' + uuid4().hex
    pg = dict(host=os.getenv('PGHOST', 'localhost'), port=os.getenv('PGPORT', '5432'),
              user=os.getenv('PGUSER', os.environ['USER']), password=os.getenv('PGPASSWORD', ''))
    admin = psycopg2.connect(dbname='postgres', **pg)
    admin.autocommit = True
    client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'), serverSelectionTimeoutMS=2000)
    conn = None
    created = False
    try:
        with admin.cursor() as cur:
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        created = True
        os.environ.update(PGDATABASE=name, MONGO_DB=name, PGUSER=pg['user'])
        conn = psycopg2.connect(dbname=name, **pg)
        conn.autocommit = True
        with conn.cursor() as cur:
            for path in sorted((ROOT / 'sql').glob('*.sql')):
                cur.execute(path.read_text())
        for script in ('01_collections_and_indexes.js', '04_api_indexes.js'):
            subprocess.run(['mongosh', os.getenv('MONGO_URI', 'mongodb://localhost:27017'), '--quiet',
                            '--file', str(ROOT / 'mongo' / script)], check=True, capture_output=True)
        seed(conn, client[name])
        from api.main import app
        uvicorn.run(app, host='127.0.0.1', port=8001, log_level='warning')
    finally:
        if conn is not None:
            conn.close()
        if created:
            client.drop_database(name)
            with admin.cursor() as cur:
                cur.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
        client.close()
        admin.close()


def seed(conn, db):
    now = datetime.now(timezone.utc)
    rider_ids = [str(uuid4()) for _ in range(60)]
    vehicles = [str(uuid4()) for _ in range(28)]
    with conn.cursor() as cur:
        for index, rider in enumerate(rider_ids):
            title = ['A Booking Rider', 'B Low Balance Rider', 'C Recovery Rider',
                     'D Phone Rider With A Long Name For Testing'][index] if index < 4 else 'Demo Rider ' + str(index).zfill(2)
            balance = '10.00' if index == 1 else '9999999999.99' if index == 3 else '500.00'
            cur.execute('INSERT INTO riders(id,name,wallet_balance) VALUES(%s,%s,%s)', (rider, title, balance))
        for index, vehicle in enumerate(vehicles):
            cur.execute('INSERT INTO vehicles(id,license_plate,class,is_active) VALUES(%s,%s,%s,%s)',
                        (vehicle, 'TS-DEMO-' + str(index).zfill(2), 'Sedan', index != 27))
        for index in range(7):
            cur.execute("INSERT INTO trips(rider_id,vehicle_id,fare_amount,status,created_at) VALUES(%s,%s,70,'COMPLETED',%s) RETURNING id",
                        (rider_ids[10 + index], vehicles[0], now - timedelta(days=index)))
            trip = str(cur.fetchone()[0])
            db.TripReviews.insert_one(dict(trip_id=trip, vehicle_id=vehicles[0], rating=4 + index % 2,
                                           feedback_tags=['safe', 'on_time'], created_at=now - timedelta(days=index)))
        cur.execute('REFRESH MATERIALIZED VIEW mv_vehicle_lifetime_stats')
    db.VehicleMetadata.insert_one(dict(vehicle_id=vehicles[0], features=dict(wifi=True, pet_friendly=False),
                                       inspection_records=[dict(date=now, passed=True)], created_at=now))
    for index in range(3):
        db.TelemetryPings.insert_one(dict(vehicle_id=vehicles[index], location=dict(type='Point',
          coordinates=[78.4867 + index * .004, 17.3850]), is_available=True, created_at=now))


if __name__ == '__main__':
    run()
