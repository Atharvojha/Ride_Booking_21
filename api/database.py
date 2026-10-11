import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor, register_uuid
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parents[1] / '.env')
register_uuid()


@contextmanager
def postgres(write=False):
    conn = psycopg2.connect(
        host=os.getenv('PGHOST', 'localhost'),
        port=os.getenv('PGPORT', '5432'),
        dbname=os.getenv('PGDATABASE', 'ridesync_team10'),
        user=os.getenv('PGUSER', 'postgres'),
        password=os.getenv('PGPASSWORD', ''),
        connect_timeout=5,
        options='-c statement_timeout=10000 -c lock_timeout=5000',
    )
    try:
        if write:
            # CALL must own its transaction, with no outer BEGIN.
            conn.autocommit = True
        else:
            # Counts, rows and balances come from the same snapshot.
            conn.set_session(readonly=True, isolation_level='REPEATABLE READ')
        yield conn
    finally:
        conn.close()


@contextmanager
def mongo():
    client = MongoClient(os.getenv('MONGO_URI', 'mongodb://localhost:27017'),
                         serverSelectionTimeoutMS=2000, connectTimeoutMS=2000,
                         socketTimeoutMS=5000)
    try:
        yield client[os.getenv('MONGO_DB', 'ridesync_team10')]
    finally:
        client.close()


def one(conn, query, values=()):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, values)
        return cur.fetchone()


def many(conn, query, values=()):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, values)
        return cur.fetchall()
