import random
import time
import datetime
import psycopg2
import pymongo
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
PG_CONFIG = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "dbname": os.getenv("PGDATABASE", "ridesync_db"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", ""),
}
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "ridesync_mongo")

NUM_PINGS = int(os.getenv("NUM_PINGS", "520000"))
TTL_WINDOW_SECONDS = int(os.getenv("TTL_WINDOW_SECONDS", "1800"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5000"))

# Roughly Hyderabad city bounds
CITY_CENTER = (78.4867, 17.3850)   # (longitude, latitude)

FEEDBACK_TAGS = [
    "CLEAN_VEHICLE", "FRIENDLY_DRIVER", "SAFE_DRIVING", "ON_TIME",
    "COMFORTABLE_RIDE", "RASH_DRIVING", "LATE_ARRIVAL", "AC_NOT_WORKING",
    "GOOD_MUSIC", "POLITE_DRIVER", "SMOOTH_RIDE", "OVERCHARGED",
]

def get_completed_trips_from_postgres():
    print("Fetching completed trips from PostgreSQL...")
    conn = psycopg2.connect(**PG_CONFIG)
    with conn.cursor() as cur:
        cur.execute("SELECT id, vehicle_id FROM trips WHERE status = 'COMPLETED';")
        trips = [{"trip_id": str(row[0]), "vehicle_id": str(row[1])} for row in cur.fetchall()]
    conn.close()
    print(f"  found {len(trips)} completed trips.")
    return trips

def generate_reviews(trips, review_rate=0.6):
    """Not every trip gets reviewed in real life — simulate ~60% review rate."""
    now = datetime.datetime.utcnow()
    batch = []
    for trip in trips:
        if random.random() > review_rate:
            continue
        # Realistic rating distribution: mostly 4-5 stars, few low ratings
        rating = random.choices([1, 2, 3, 4, 5], weights=[3, 5, 12, 35, 45], k=1)[0]
        num_tags = random.randint(1, 3)
        tags = random.sample(FEEDBACK_TAGS, num_tags)
        batch.append({
            "trip_id": trip["trip_id"],
            "vehicle_id": trip["vehicle_id"],
            "rating": rating,
            "feedback_tags": tags,
            "created_at": now - datetime.timedelta(days=random.randint(0, 60)),
        })
    return batch


def get_vehicle_ids_from_postgres():
    print("Fetching vehicle IDs from PostgreSQL...")
    conn = psycopg2.connect(**PG_CONFIG)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM vehicles;")
        ids = [str(row[0]) for row in cur.fetchall()]
    conn.close()
    print(f"  found {len(ids)} vehicles.")
    return ids


def build_vehicle_base_locations(vehicle_ids):
    """Give each vehicle a fixed 'home area' so its pings cluster together,
    like a real vehicle moving around one part of the city, not teleporting."""
    bases = {}
    for vid in vehicle_ids:
        lon_offset = random.uniform(-0.15, 0.15)
        lat_offset = random.uniform(-0.15, 0.15)
        bases[vid] = (CITY_CENTER[0] + lon_offset, CITY_CENTER[1] + lat_offset)
    return bases


def generate_pings(vehicle_ids, bases):
    now = datetime.datetime.utcnow()
    batch = []
    for _ in range(NUM_PINGS):
        vid = random.choice(vehicle_ids)
        base_lon, base_lat = bases[vid]
        # Small jitter around the vehicle's base location (simulates real movement)
        lon = round(base_lon + random.uniform(-0.01, 0.01), 6)
        lat = round(base_lat + random.uniform(-0.01, 0.01), 6)

        seconds_ago = random.randint(0, TTL_WINDOW_SECONDS)
        created_at = now - datetime.timedelta(seconds=seconds_ago)

        is_available = random.random() < 0.7  # 70% of pings show vehicle as available

        batch.append({
            "vehicle_id": vid,
            "is_available": is_available,
            "location": {"type": "Point", "coordinates": [lon, lat]},
            "created_at": created_at,
        })

        if len(batch) >= BATCH_SIZE:
            yield batch
            batch = []
    if batch:
        yield batch


def main():
    vehicle_ids = get_vehicle_ids_from_postgres()
    if not vehicle_ids:
        print("No vehicles found in Postgres — run postgres_seeder.py first!")
        return

    bases = build_vehicle_base_locations(vehicle_ids)

    client = pymongo.MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db["TelemetryPings"]

    print(f"Inserting {NUM_PINGS} telemetry pings...")
    start = time.time()
    inserted = 0
    for batch in generate_pings(vehicle_ids, bases):
        collection.insert_many(batch)
        inserted += len(batch)
        print(f"  {inserted}/{NUM_PINGS} pings inserted ({time.time()-start:.1f}s elapsed)")

    print(f"Done. {inserted} pings inserted in {time.time()-start:.1f}s.")
    trips = get_completed_trips_from_postgres()
    reviews = generate_reviews(trips)
    if reviews:
        db["TripReviews"].insert_many(reviews)
        print(f"Inserted {len(reviews)} trip reviews.")
    client.close()


if __name__ == "__main__":
    main()