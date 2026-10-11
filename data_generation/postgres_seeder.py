import random
import time
import datetime
import psycopg2
import psycopg2.extras as extras
from faker import Faker
from pymongo import MongoClient

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

NUM_RIDERS = int(os.getenv("NUM_RIDERS", "100000"))
NUM_VEHICLES = int(os.getenv("NUM_VEHICLES", "40000"))
NUM_TRIPS = int(os.getenv("NUM_TRIPS", "50000"))
DAYS_SPREAD = 60

fake = Faker("en_IN")   # Indian names/locale for realism

VEHICLE_CLASSES = [
    {"name": "Bike",        "weight": 30, "base_fare": (30, 90)},
    {"name": "Auto",        "weight": 25, "base_fare": (40, 120)},
    {"name": "Mini",        "weight": 20, "base_fare": (80, 220)},
    {"name": "Sedan",       "weight": 12, "base_fare": (120, 320)},
    {"name": "Prime Sedan", "weight": 6,  "base_fare": (180, 450)},
    {"name": "SUV",         "weight": 4,  "base_fare": (250, 600)},
    {"name": "Electric",    "weight": 2,  "base_fare": (100, 280)},
    {"name": "XL",          "weight": 1,  "base_fare": (300, 700)},
]

RTO_CODES = ["TS09", "TS07", "KA01", "KA05", "MH12", "MH01", "DL08", "AP09", "TN07", "UP32"]

# VehicleMetadata generation pools
INSPECTION_ITEMS = ["brakes", "tires", "lights", "engine", "suspension", "emissions"]
FEATURE_POOL = ["ac", "music_system", "phone_charger", "child_seat", "wheelchair_accessible", "wifi"]
PREMIUM_CLASSES = ("Prime Sedan", "SUV", "XL")

MONGO_METADATA_BATCH_SIZE = 2000


def connect():
    return psycopg2.connect(**PG_CONFIG)


def get_mongo_db():
    client = MongoClient(MONGO_URI)
    return client[MONGO_DB]


def weighted_class():
    classes = [c["name"] for c in VEHICLE_CLASSES]
    weights = [c["weight"] for c in VEHICLE_CLASSES]
    return random.choices(classes, weights=weights, k=1)[0]


def fare_for_class(vehicle_class):
    for c in VEHICLE_CLASSES:
        if c["name"] == vehicle_class:
            low, high = c["base_fare"]
            return round(random.uniform(low, high), 2)
    return round(random.uniform(50, 300), 2)


def seed_riders(conn):
    print(f"Creating {NUM_RIDERS} riders...")
    data = []
    for _ in range(NUM_RIDERS):
        name = fake.name()
        roll = random.random()
        if roll < 0.80:
            balance = round(random.uniform(1000, 4000), 2)
        elif roll < 0.95:
            balance = round(random.uniform(400, 1000), 2)
        else:
            balance = round(random.uniform(50, 400), 2)
        data.append((name, balance))
    with conn.cursor() as cur:
        rows = extras.execute_values(
            cur,
            "INSERT INTO riders (name, wallet_balance) VALUES %s RETURNING id, wallet_balance",
            data,
            fetch=True,
        )
    conn.commit()
    balances = {row[0]: float(row[1]) for row in rows}
    print(f"  done. {len(balances)} riders created.")
    return balances


def seed_vehicles(conn):
    print(f"Creating {NUM_VEHICLES} vehicles...")
    plates = set()
    data = []
    while len(data) < NUM_VEHICLES:
        rto = random.choice(RTO_CODES)
        series = f"{fake.random_uppercase_letter()}{fake.random_uppercase_letter()}"
        number = random.randint(1000, 9999999)
        plate = f"{rto}{series}{number}"
        if plate in plates:
            continue
        plates.add(plate)
        vehicle_class = weighted_class()
        is_active = random.random() < 0.92
        data.append((plate, vehicle_class, is_active))
    with conn.cursor() as cur:
        rows = extras.execute_values(
            cur,
            "INSERT INTO vehicles (license_plate, class, is_active) VALUES %s RETURNING id, class",
            data,
            fetch=True,
        )
    conn.commit()
    vehicles = [{"id": row[0], "class": row[1]} for row in rows]
    print(f"  done. {len(vehicles)} vehicles created.")
    return vehicles


def build_vehicle_metadata(vehicle_id, vehicle_class):
    """Build one VehicleMetadata doc matching mongo_schema_map.json's shape."""
    num_inspections = random.randint(1, 4)
    inspection_records = []
    for _ in range(num_inspections):
        inspection_records.append({
            "date": datetime.datetime.now() - datetime.timedelta(days=random.randint(0, 400)),
            "items_checked": random.sample(
                INSPECTION_ITEMS, k=random.randint(2, len(INSPECTION_ITEMS))
            ),
            "passed": random.random() < 0.9,
        })

    features = {f: True for f in random.sample(FEATURE_POOL, k=random.randint(1, 4))}
    if vehicle_class in PREMIUM_CLASSES:
        features["premium_interior"] = True

    return {
        "vehicle_id": str(vehicle_id),
        "inspection_records": inspection_records,
        "features": features,
        "created_at": datetime.datetime.now(),
    }


def seed_vehicle_metadata(mongo_db, vehicles):
    """
    vehicles: list of {"id": ..., "class": ...} returned by seed_vehicles().
    Inserted in batches to avoid building one giant list in memory
    for 40k+ vehicles.
    """
    print(f"Creating VehicleMetadata for {len(vehicles)} vehicles...")
    start = time.time()
    total_inserted = 0
    batch = []

    for v in vehicles:
        batch.append(build_vehicle_metadata(v["id"], v["class"]))
        if len(batch) >= MONGO_METADATA_BATCH_SIZE:
            result = mongo_db.VehicleMetadata.insert_many(batch)
            total_inserted += len(result.inserted_ids)
            batch = []
            print(f"  {total_inserted}/{len(vehicles)} metadata docs inserted...")

    if batch:
        result = mongo_db.VehicleMetadata.insert_many(batch)
        total_inserted += len(result.inserted_ids)

    print(f"  done. {total_inserted} VehicleMetadata documents created in {time.time() - start:.1f}s.")


def random_past_timestamp():
    days_ago = int(random.triangular(0, DAYS_SPREAD, 0))
    hour_weights = [1,1,1,1,1,2,4,7,9,8,5,4,4,5,5,4,5,7,9,8,6,4,2,1]
    hour = random.choices(range(24), weights=hour_weights, k=1)[0]
    minute = random.randint(0, 59)
    dt = datetime.datetime.now() - datetime.timedelta(days=days_ago)
    dt = dt.replace(hour=hour, minute=minute, second=random.randint(0, 59), microsecond=0)
    return dt


def seed_trips(conn, rider_balances, vehicles):
    """
    Forces a 100% booking rate:
      - Picks an eligible, currently-free rider FIRST, then clamps the
        fare to what that rider can afford -> insufficient funds can
        never occur.
      - If every rider currently has an active trip (blocked by
        idx_one_active_trip_per_rider), force-releases one rider's
        open trip via sp_release_escrow before continuing, so the
        free-rider pool never runs dry.
      - Net effect: sp_book_trip can never return anything other than
        'BOOKED'. NOTE: this makes the dataset unrealistic (see caveat
        below) — fine for a happy-path smoke test, not for data meant
        to resemble real production traffic.
    """
    print(f"Attempting {NUM_TRIPS} trips via sp_book_trip/sp_release_escrow...")
    start = time.time()

    conn.autocommit = True

    eligible_riders = dict(rider_balances)  # rider_id -> current balance
    riders_with_active_trip = set()

    booked = 0
    completed = 0
    in_transit = 0
    requested = 0
    forced_releases = 0

    with conn.cursor() as cur:

        for i in range(1, NUM_TRIPS + 1):

            free_riders = [
                rider_id for rider_id in eligible_riders
                if rider_id not in riders_with_active_trip
            ]

            # If nobody is free, force-complete one rider's open trip.
            if not free_riders:
                stuck_rider = next(iter(riders_with_active_trip))
                cur.execute(
                    """
                    SELECT id FROM trips
                    WHERE rider_id = %s AND status IN ('REQUESTED', 'IN TRANSIT')
                    LIMIT 1
                    """,
                    (stuck_rider,)
                )
                row = cur.fetchone()
                if row:
                    open_trip_id = row[0]
                    cur.execute(
                        "UPDATE trips SET status = 'IN TRANSIT' WHERE id = %s AND status = 'REQUESTED'",
                        (open_trip_id,)
                    )
                    cur.execute("CALL sp_release_escrow(%s)", (open_trip_id,))
                    forced_releases += 1
                riders_with_active_trip.discard(stuck_rider)
                free_riders = [stuck_rider]

            rider_id = random.choice(free_riders)

            # Top up anyone whose balance has drifted too low, so the
            # fare clamp below never has to deal with near-zero funds.
            if eligible_riders[rider_id] < 30:
                cur.execute(
                    "UPDATE riders SET wallet_balance = wallet_balance + 500 WHERE id = %s RETURNING wallet_balance",
                    (rider_id,),
                )
                eligible_riders[rider_id] = float(cur.fetchone()[0])

            vehicle = random.choice(vehicles)
            fare = fare_for_class(vehicle["class"])
            fare = round(min(fare, eligible_riders[rider_id]), 2)
            fare = max(fare, 1.00)

            cur.execute(
                "CALL sp_book_trip(%s, %s, %s, NULL, NULL)",
                (rider_id, vehicle["id"], fare)
            )
            trip_id, status = cur.fetchone()

            if status != "BOOKED":
                # Should not happen given the guarantees above — log
                # loudly if it ever does, since it means an assumption broke.
                continue

            booked += 1
            eligible_riders[rider_id] -= fare

            status_roll = random.random()

            if status_roll < 0.95:
                cur.execute(
                    "UPDATE trips SET status = 'IN TRANSIT' WHERE id = %s",
                    (trip_id,)
                )
                cur.execute("CALL sp_release_escrow(%s)", (trip_id,))
                completed += 1

            elif status_roll < 0.98:
                cur.execute(
                    "UPDATE trips SET status = 'IN TRANSIT' WHERE id = %s",
                    (trip_id,)
                )
                in_transit += 1
                riders_with_active_trip.add(rider_id)

            else:
                requested += 1
                riders_with_active_trip.add(rider_id)

            if i % 2000 == 0 or i == NUM_TRIPS:
                elapsed = time.time() - start
                print(
                    f"  {i}/{NUM_TRIPS} attempted | booked={booked} | "
                    f"completed={completed} | in_transit={in_transit} | "
                    f"requested={requested} | forced_releases={forced_releases} | "
                    f"{elapsed:.1f}s"
                )

    conn.autocommit = False

    booked_pct = (booked / NUM_TRIPS * 100) if NUM_TRIPS else 0

    print("\nTrip seeding complete!")
    print(f"  Attempted        : {NUM_TRIPS}")
    print(f"  Booked           : {booked} ({booked_pct:.1f}%)")
    print(f"  Completed        : {completed}")
    print(f"  In Transit       : {in_transit}")
    print(f"  Requested        : {requested}")
    print(f"  Forced releases  : {forced_releases}")
    print(f"  Time             : {time.time() - start:.1f}s")


def main():
    conn = connect()
    mongo_db = get_mongo_db()

    balances = seed_riders(conn)
    vehicles = seed_vehicles(conn)
    seed_vehicle_metadata(mongo_db, vehicles)   # same vehicle_id as Postgres FK
    seed_trips(conn, balances, vehicles)
    print("All done!")


if __name__ == "__main__":
    main()