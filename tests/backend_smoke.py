import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import psycopg2
from psycopg2 import sql
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
NAME = 'ridesync_verify_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
PG = {'host': os.getenv('PGHOST','localhost'), 'port':os.getenv('PGPORT','5432'), 'dbname': NAME, 'user': os.getenv('PGUSER',os.environ['USER']), 'password':os.getenv('PGPASSWORD','')}
scratch_manager = tempfile.TemporaryDirectory(prefix='ridesync-smoke-')
scratch = Path(scratch_manager.name)
results = []
def record(name, ok, detail=''):
    results.append({'check': name, 'passed': bool(ok), 'detail': str(detail)})
    print(('PASS' if ok else 'FAIL') + ' ' + name + (' — ' + str(detail) if detail else ''), flush=True)
def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
admin = psycopg2.connect(**{**PG, 'dbname':'postgres'})
admin.autocommit = True
with admin.cursor() as c:
    c.execute('SELECT 1 FROM pg_database WHERE datname=%s', (NAME,))
    if not c.fetchone():
        c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(NAME)))
admin.close()
conn = psycopg2.connect(**PG)
conn.autocommit = True
with conn.cursor() as c:
    c.execute("SELECT to_regclass('public.riders')")
    if c.fetchone()[0] is None:
        for path in sorted((ROOT / 'sql').glob('*.sql')):
            c.execute(path.read_text())
            record('SQL setup: ' + path.name, True)
mc = MongoClient(os.getenv('MONGO_URI','mongodb://localhost:27017'))
mdb = mc[NAME]
if 'TelemetryPings' not in mdb.list_collection_names():
    setup = (ROOT / 'mongo/01_collections_and_indexes.js').read_text().replace('ridesync_mongo', NAME)
    path = scratch / 'mongo_setup.js'
    path.write_text(setup)
    r = subprocess.run(['mongosh', os.getenv('MONGO_URI','mongodb://localhost:27017'), '--quiet', '--file', str(path)], capture_output=True, text=True, env={**os.environ,'MONGO_DB':NAME})
    record('Mongo setup script', r.returncode == 0, r.stdout.strip() or r.stderr.strip())
with conn.cursor() as c:
    c.execute('SELECT count(*) FROM riders')
    empty = c.fetchone()[0] == 0
if empty:
    pgseed = module(ROOT / 'data_generation/postgres_seeder.py')
    pgseed.PG_CONFIG = PG
    pgseed.MONGO_DB = NAME
    pgseed.MONGO_URI = os.getenv('MONGO_URI','mongodb://localhost:27017')
    pgseed.NUM_RIDERS = 100
    pgseed.NUM_VEHICLES = 40
    pgseed.NUM_TRIPS = 100
    pgseed.random.seed(21)
    pgseed.fake.seed_instance(21)
    pgseed.main()
    record('PostgreSQL + metadata seeder (100 riders/40 vehicles/100 trip attempts)', True)
    mgseed = module(ROOT / 'data_generation/mongo_seeder.py')
    mgseed.PG_CONFIG = PG
    mgseed.MONGO_URI = os.getenv('MONGO_URI','mongodb://localhost:27017')
    mgseed.MONGO_DB = NAME
    mgseed.NUM_PINGS = 1000
    mgseed.BATCH_SIZE = 500
    mgseed.random.seed(21)
    mgseed.main()
    record('Mongo telemetry + review seeder (1000 pings)', True)
with conn.cursor() as c:
    c.execute("INSERT INTO riders(name,wallet_balance) VALUES ('Audit funded rider',1000) RETURNING id")
    rider = c.fetchone()[0]
    c.execute("INSERT INTO riders(name,wallet_balance) VALUES ('Audit low balance rider',10) RETURNING id")
    low = c.fetchone()[0]
    c.execute('SELECT id FROM vehicles WHERE is_active LIMIT 1')
    vehicle = c.fetchone()[0]
    def state(r):
        c.execute('SELECT wallet_balance FROM riders WHERE id=%s', (r,))
        balance = c.fetchone()[0]
        c.execute('SELECT count(*) FROM wallet_audit_logs WHERE rider_id=%s', (r,))
        return (balance, c.fetchone()[0])
    c.execute('CALL sp_book_trip(%s,%s,%s,NULL,NULL,NULL)', (rider,vehicle,100))
    trip, status, returned_audit = c.fetchone()
    record('Booking success', status == 'BOOKED' and state(rider) == (900,1), status)
    c.execute('SELECT action_type,amount_changed,balance_after FROM wallet_audit_logs WHERE rider_id=%s', (rider,))
    record('Wallet trigger', c.fetchone() == ('ESCROW_HOLD', -100, 900))
    before = state(rider)
    c.execute('CALL sp_book_trip(%s,%s,%s,NULL,NULL,NULL)', (rider,vehicle,50))
    failed_trip, status, returned_audit = c.fetchone()
    record('Duplicate active trip rejected without debit/audit', failed_trip is None and status.startswith('FAILED:') and state(rider) == before, status)
    before = state(low)
    c.execute('CALL sp_book_trip(%s,%s,%s,NULL,NULL,NULL)', (low,vehicle,100))
    failed_trip, status, returned_audit = c.fetchone()
    record('Insufficient funds rejected without debit/audit', failed_trip is None and status.startswith('FAILED:') and state(low) == before, status)
    c.execute("UPDATE trips SET status='IN TRANSIT' WHERE id=%s", (trip,))
    c.execute('CALL sp_release_escrow(%s)', (trip,))
    c.execute('SELECT status FROM trips WHERE id=%s', (trip,))
    record('Trip completion', c.fetchone()[0] == 'COMPLETED' and state(rider) == (900,2))
    c.execute('CALL sp_book_trip(%s,%s,%s,NULL,NULL,NULL)', (rider,vehicle,50))
    second_trip, status, returned_audit = c.fetchone()
    record('New booking allowed after completion', status == 'BOOKED' and state(rider) == (850,3))
    c.execute('SELECT count(*) FROM vw_vehicle_revenue_moving_avg WHERE revenue_rank_on_date >= 1')
    record('Moving average + DENSE_RANK results', c.fetchone()[0] > 0)
    c.execute('SELECT count(*) FROM mv_vehicle_lifetime_stats')
    record('Initial materialized view needs post-seed refresh', c.fetchone()[0] == 0)
    c.execute('SELECT refresh_mv_vehicle_lifetime_stats()')
    c.execute('SELECT count(*) FROM mv_vehicle_lifetime_stats')
    record('Materialized view refresh', c.fetchone()[0] == 40)
# Check that topping up a wallet changes its saved balance.
topup = psycopg2.connect(**PG)
pgseed = module(ROOT / 'data_generation/postgres_seeder.py')
pgseed.NUM_TRIPS = 1
pgseed.fare_for_class = lambda vehicle_class: 100.0
pgseed.seed_trips(topup, {low:10.0}, [{'id':vehicle,'class':'Sedan'}])
topup.close()
with conn.cursor() as c:
    c.execute('SELECT wallet_balance FROM riders WHERE id=%s', (low,))
    record('Seeder top-up persists before booking', c.fetchone()[0] == 410)
    c.execute("SELECT count(*) FROM wallet_audit_logs WHERE rider_id=%s AND ((action_type='CREDIT' AND amount_changed=500) OR (action_type='ESCROW_HOLD' AND amount_changed=-100))", (low,))
    record('Seeder top-up and booking both audited', c.fetchone()[0] == 2)
# Run the Mongo scripts on the test database.
for filename in ['02_workflow_geonear.js','03_workflow4_facet.js']:
    path = scratch / filename
    path.write_text((ROOT/'mongo'/filename).read_text().replace('ridesync_mongo', NAME))
    r = subprocess.run(['mongosh',os.getenv('MONGO_URI','mongodb://localhost:27017'),'--quiet','--file',str(path)],capture_output=True,text=True, env={**os.environ,'MONGO_DB':NAME})
    record('Inherited Mongo workflow: '+filename,r.returncode==0,(r.stderr or r.stdout).strip()[:1500])
record('VehicleMetadata records present', mdb.VehicleMetadata.count_documents({}) == 40)
indexes = mdb.VehicleMetadata.index_information()
record('VehicleMetadata lookup index on correct collection', any(i['key'] == [('vehicle_id',1)] for i in indexes.values()), list(indexes))
record('Telemetry 2dsphere index', any(i['key'] == [('location','2dsphere')] for i in mdb.TelemetryPings.index_information().values()))
record('Telemetry TTL 7200 seconds', any(i.get('expireAfterSeconds') == 7200 for i in mdb.TelemetryPings.index_information().values()))
# A ping at the chosen point should have a distance close to zero.
mdb.TelemetryPings.insert_one({'vehicle_id':vehicle,'is_available':True,'location':{'type':'Point','coordinates':[78.4867,17.3850]},'created_at':datetime.datetime.now(datetime.timezone.utc)})
near = list(mdb.TelemetryPings.aggregate([{'$geoNear':{'near':{'type':'Point','coordinates':[78.4867,17.3850]},'key':'location','distanceField':'distance_meters','maxDistance':5000,'spherical':True,'query':{'is_available':True}}},{'$limit':1}]))
record('Database geoNear at Hyderabad origin', len(near) == 1 and near[0]['distance_meters'] < 1)
try:
    source_commit = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
except (subprocess.CalledProcessError, FileNotFoundError):
    source_commit = 'unknown (this is not a Git checkout, for example an unzipped submission)'
summary = {'source_commit_before_verification': source_commit, 'database':NAME,'scale':'small sample dataset (full-size checks are in tests/scale_check.py)','results':results}
if os.getenv('VERIFICATION_REPORT'):
    Path(os.environ['VERIFICATION_REPORT']).write_text(json.dumps(summary,indent=2))
print(json.dumps({'passed':sum(r['passed'] for r in results),'failed':sum(not r['passed'] for r in results)}))
conn.close()
mc.close()

scratch_manager.cleanup()
raise SystemExit(0 if all(r['passed'] for r in results) else 1)
