"""Add fresh vehicle pings so the Nearby Vehicles map has something to show.

The telemetry collection deletes pings after two hours, so a demo database goes quiet.
Do not rerun mongo_seeder.py to fix that: it also adds reviews, which would duplicate them.
This script only inserts new TelemetryPings documents. It never changes old pings,
reviews, vehicle metadata or anything in PostgreSQL.

    python data_generation/refresh_demo_pings.py --dry-run   # show the plan only
    python data_generation/refresh_demo_pings.py             # insert the pings

Each chosen vehicle gets one ping stamped with the current UTC time (a few seconds in the
past, never in the future). Some vehicles are placed on purpose where they should NOT appear
on the map, so the demo can show the rules:
  - "unavailable": inside the 5 km radius but is_available is false.
  - "outside": available but further than 5 km from the origin.
"""
import argparse
import math
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

RADIUS_METRES = 5000
METRES_PER_DEGREE_LATITUDE = 111320
INSIDE_RANGE = (300, 4000)     # kept well inside 5 km, so rounding never pushes a ping outside
OUTSIDE_RANGE = (7000, 9000)


def point_near(origin, distance_metres, bearing_degrees):
    """A (longitude, latitude) point this far from the origin, in the given direction.

    This flat-earth approximation is accurate to well under 1% at these distances.
    """
    longitude, latitude = origin
    bearing = math.radians(bearing_degrees)
    north = distance_metres * math.cos(bearing)
    east = distance_metres * math.sin(bearing)
    new_latitude = latitude + north / METRES_PER_DEGREE_LATITUDE
    new_longitude = longitude + east / (METRES_PER_DEGREE_LATITUDE * math.cos(math.radians(latitude)))
    return round(new_longitude, 6), round(new_latitude, 6)


def build_pings(vehicle_ids, origin, now, rng, unavailable=3, outside=3):
    """One ping per vehicle. Returns the documents to insert.

    The first `outside` vehicles are far away, the next `unavailable` are close but not
    available, and the rest are close and available.
    """
    if len(vehicle_ids) <= outside + unavailable:
        raise ValueError("Choose more vehicles than the unavailable and outside groups.")
    pings = []
    for index, vehicle_id in enumerate(vehicle_ids):
        is_far = index < outside
        is_available = not (outside <= index < outside + unavailable)
        low, high = OUTSIDE_RANGE if is_far else INSIDE_RANGE
        longitude, latitude = point_near(origin, rng.uniform(low, high), rng.uniform(0, 360))
        pings.append({
            "vehicle_id": str(vehicle_id),
            "is_available": is_available,
            "location": {"type": "Point", "coordinates": [longitude, latitude]},  # longitude first
            "created_at": now.replace(microsecond=0) - timedelta(seconds=rng.randint(0, 120)),
        })
    return pings


def choose_active_vehicles(conn, count):
    """Active vehicles from PostgreSQL, in a fixed order so repeated runs pick the same ones."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM vehicles WHERE is_active ORDER BY license_plate, id LIMIT %s", (count,))
        return [str(row[0]) for row in cur.fetchall()]


def read_origin():
    longitude = float(os.getenv("ORIGIN_LONGITUDE", "78.4867"))
    latitude = float(os.getenv("ORIGIN_LATITUDE", "17.3850"))
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        raise ValueError("ORIGIN_LONGITUDE or ORIGIN_LATITUDE is out of range.")
    return longitude, latitude


def main():
    parser = argparse.ArgumentParser(description="Insert fresh demo vehicle pings (telemetry only).")
    parser.add_argument("--count", type=int, default=25, help="vehicles to place (default 25)")
    parser.add_argument("--unavailable", type=int, default=3, help="close vehicles marked not available")
    parser.add_argument("--outside", type=int, default=3, help="available vehicles beyond 5 km")
    parser.add_argument("--seed", type=int, default=2026, help="random seed, so a plan can be repeated")
    parser.add_argument("--dry-run", action="store_true", help="print the plan without inserting")
    args = parser.parse_args()
    if not 1 <= args.count <= 1000:
        raise SystemExit("--count must be between 1 and 1000.")
    if args.unavailable < 0 or args.outside < 0:
        raise SystemExit("--unavailable and --outside cannot be negative.")
    if args.count <= args.unavailable + args.outside:
        raise SystemExit("--count must be larger than --unavailable plus --outside.")

    pg = psycopg2.connect(host=os.getenv("PGHOST", "localhost"), port=os.getenv("PGPORT", "5432"),
                          dbname=os.getenv("PGDATABASE", "ridesync_team10"), user=os.getenv("PGUSER", "postgres"),
                          password=os.getenv("PGPASSWORD", ""))
    vehicle_ids = choose_active_vehicles(pg, args.count)
    pg.close()

    origin = read_origin()
    try:
        pings = build_pings(vehicle_ids, origin, datetime.now(timezone.utc), random.Random(args.seed),
                            args.unavailable, args.outside)
    except ValueError:
        raise SystemExit(f"Only {len(vehicle_ids)} active vehicles were found. Lower --unavailable and --outside, or add vehicles.")
    shown = len(pings) - args.unavailable - args.outside
    print(f"PostgreSQL database: {os.getenv('PGDATABASE', 'ridesync_team10')}")
    print(f"MongoDB database:    {os.getenv('MONGO_DB', 'ridesync_team10')}")
    print(f"Origin (longitude, latitude): {origin}")
    print(f"Pings to add: {len(pings)} ({shown} should appear within 5 km, "
          f"{args.unavailable} unavailable, {args.outside} outside the radius)")
    if args.dry_run:
        print("Dry run: nothing was inserted.")
        return

    client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    collection = client[os.getenv("MONGO_DB", "ridesync_team10")]["TelemetryPings"]
    before = collection.count_documents({})
    collection.insert_many(pings)
    print(f"TelemetryPings: {before} -> {collection.count_documents({})} documents.")
    client.close()


if __name__ == "__main__":
    main()
