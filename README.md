# Team 10 — Assignment 2 setup

Team repository: [Atharvojha/Ride_Booking_21](https://github.com/Atharvojha/Ride_Booking_21). Inherited source: [amaan070/Ride_Booking_21](https://github.com/amaan070/Ride_Booking_21), starting commit `d0d5ad44ba4ab2f566cd965e055870ddd7e95697`. All 23 inherited commits are preserved.

We checked the database scripts and fixed the problems we found. The first API step is working: browsing, booking, trip status changes and wallet history. The web frontend is still pending. See [handover note](docs/handover_note.md), [verification results](docs/backend_verification.json), and [API endpoints and remaining plan](docs/api_endpoints.md). The Figma prototype is the design reference, not a connected application.

## Current setup (macOS/Linux)

Requires running PostgreSQL, MongoDB, mongosh, Python 3.11 or newer and Git. PostgreSQL needs a role that can create the development and smoke-test databases. Configure your local role/password; do not commit credentials.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt -r data_generation/requirements.txt
cp .env.example .env
# Edit .env for your local database role and connection settings.
set -a
source .env
set +a
createdb "$PGDATABASE"
for script in sql/*.sql; do
  psql -v ON_ERROR_STOP=1 -f "$script" || break
done
mongosh "$MONGO_URI" --quiet --file mongo/01_collections_and_indexes.js
python data_generation/postgres_seeder.py
python data_generation/mongo_seeder.py
psql -v ON_ERROR_STOP=1 -c 'SELECT refresh_mv_vehicle_lifetime_stats();'
mongosh "$MONGO_URI" --quiet --file mongo/02_workflow_geonear.js
mongosh "$MONGO_URI" --quiet --file mongo/03_workflow4_facet.js
```

Use a new database for initial setup; schema SQL is not a reset script. Stop if a step reports an error. Both databases must be running before the PostgreSQL seeder, because it also writes VehicleMetadata. Seeders append data; rerunning them is not a reset. Refresh the materialized view after seeding. Telemetry expires after two hours; regenerate pings for later map demonstrations.

`.env.example` uses a small development seed. For the inherited scale, set NUM_RIDERS=100000, NUM_VEHICLES=40000, NUM_TRIPS=50000 and NUM_PINGS=520000. Concurrent booking and completion tests pass. Large dataset checks are still pending.

## Run the API

For an already-seeded database, load your .env settings and apply only these two updated scripts:

~~~sh
set -a
source .env
set +a
psql -v ON_ERROR_STOP=1 -f sql/03_triggers_and_audit.sql
psql -v ON_ERROR_STOP=1 -f sql/04_stored_procedures.sql
~~~

These update the wallet trigger and booking/completion procedures without recreating tables. Stop on any error. New databases already receive them in the setup loop above.

~~~sh
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
~~~

Open [API docs](http://127.0.0.1:8000/docs) to try requests. See [API setup](api/README.md) and [API check results](docs/api_verification.json). FastAPI lets us keep the server small and reuse the inherited database procedures. React, Vite, plain CSS and Leaflet remain the frontend choices.

## Backend checks

```sh
python tests/backend_smoke.py
python -m pytest tests/test_api.py -q
```

The script creates unique `ridesync_verify_*` databases, uses a small sample dataset and checks booking, rollback, audit triggers, status progression, analytics, metadata indexes, TTL, geoNear and review facet execution. The test databases are kept so we can inspect the results. It exits nonzero if any check fails. The original checked-in report records 27 passing checks on PostgreSQL 17.11 and MongoDB 7.0. All 27 still pass after this API step. The API suite has 36 passing checks; it creates separate test databases and removes them afterwards. One dependency warning from the test client remains.

## Changes and assumptions

- Fixed mongosh execution of nearby search; default coordinates match Hyderabad seed data.
- Fixed case-sensitive VehicleMetadata index and repeatable Mongo collection setup.
- Replaced embedded/prompted connection settings with environment configuration.
- Fixed seeder top-ups to update the real wallet and fire its audit trigger.
- Added .env.example, ignored local credentials/dependencies, tests and handover/API documentation; corrected the inherited ERD filename.
- Booking now rejects inactive vehicles and invalid fares in the procedure, returns the exact trigger-created audit ID, and uses that row for before/after balances. Seeded trips use active vehicles. Completion locks the wallet before the trip and records the actual audit time, so a concurrent top-up does not reorder the running balance.
- The booking procedures finish their own database transactions. The API must call them directly, without starting another transaction around them. The current query averages seven revenue rows. The API plan changes this to seven calendar days, including days with no completed trips.
- Demo user switching is planned. Current trip statuses are REQUESTED, IN TRANSIT and COMPLETED. The design uses INR and a user-entered fare; route fields and cancellation are outside the required demo.

## Submission checklist (pending)

Wireframes and user descriptions are saved in docs/design/. Finish analytics, nearby search and review API routes, build web/, complete meaningful UI tests and scale checks, and record a demo of at most five minutes. Before submission, update the actual contribution table, demo link and final commit hash. Package one `10_a1b.zip` strictly under 20 MB, excluding dependencies, caches, build output, credentials and database dumps.

Team members will be added to the contribution table when details are provided; record each person's actual design and code work. Collaborator access is managed by the team owner.

---

# Inherited Assignment 1 documentation

The following original documentation is retained for attribution and background. Use the Team 10 setup steps above when running the project.

# RideSync – Ride Booking Database System

## Project Overview

RideSync is a database system designed for a ride-booking platform. The project demonstrates the use of both a relational database and a NoSQL database to manage different types of application data.

The system uses:

- **PostgreSQL** for structured, transactional, and relational data.
- **MongoDB** for flexible document data, GPS telemetry, geospatial queries, and review analytics.

The two databases are logically connected using shared UUID references.

This project demonstrates relational schema design, constraints, indexes, triggers, stored procedures, materialized views, window analytics, MongoDB geospatial queries, aggregation pipelines, TTL indexes, data generation, and performance analysis.

---

# Original Assignment 1 Team Members

| Team Member | Responsibility |
|---|---|
|**Amaan Ahmad**| MongoDB Collections, Indexes and Geospatial Queries |
|**Tarishi Hemani**|  PostgreSQL Schema Design |
|**Pal Shah**| Advanced PostgreSQL Features |
|**Sanjana Venkatesan** | Data Generation, Analytics and Performance Testing |

---

# Repository

GitHub Repository: https://github.com/amaan070/Ride_Booking_21

---

# Technologies Used

- PostgreSQL
- MongoDB Community Server
- MongoDB Shell (`mongosh`)
- Python 3

---

# Project Structure

```text
Ride_Booking_21/
│
├── README.md
│
├── sql/
│   ├── 01_schema_ddl.sql
│   ├── 02_indexes.sql
│   ├── 03_triggers_and_audit.sql
│   ├── 04_stored_procedures.sql
│   ├── 05_materialized_views.sql
│   └── 06_window_analytics.sql
│
├── mongo/
│   ├── 01_collections_and_indexes.js
│   ├── 02_workflow_geonear.js
│   └── 03_workflow4_facet.js
│
├── data_generation/
│   ├── postgres_seeder.py
│   ├── mongo_seeder.py
│   └── requirements.txt
│
├── performance/
│   ├── pg_explain_queries.sql
│   ├── mongo_execution_stats.js
│   └── mongo_output.txt
│
└── docs/
    ├── relational_erd.png
    └── mongo_schema_map.json
```

---

# 1. ERDs and Schema Maps

## PostgreSQL Relational Schema

The PostgreSQL database manages the structured transactional data of the system.

The main tables are:

- `riders`
- `vehicles`
- `trips`
- `wallet_audit_logs`

The relational Entity Relationship Diagram is available at:

```text
docs/relational_erd.jpeg
```

### Main Relationships

```text
riders
   │
   │ rider_id
   ▼
trips
   ▲
   │ vehicle_id
   │
vehicles


riders
   │
   │ rider_id
   ▼
wallet_audit_logs
```

The relational schema uses:

- UUID primary keys
- Foreign key relationships
- Check constraints
- Unique constraints
- Transactional integrity

---

## MongoDB Schema Map

The MongoDB schema map is available at:

```text
docs/mongo_schema_map.json
```

The MongoDB database contains the following collections:

### VehicleMetadata

Stores flexible and optional vehicle-related information.

### TelemetryPings

Stores high-frequency GPS and vehicle availability information.

Typical fields include:

- `vehicle_id`
- `is_available`
- `location`
- `created_at`

### TripReviews

Stores trip ratings and feedback.

Typical fields include:

- `trip_id`
- `vehicle_id`
- `rating`
- `feedback_tags`
- `created_at`

---

# PostgreSQL and MongoDB Integration

PostgreSQL and MongoDB are logically connected using UUID references.

```text
PostgreSQL                         MongoDB

vehicles.id
    │
    ├────────────────────► VehicleMetadata.vehicle_id
    │
    └────────────────────► TelemetryPings.vehicle_id


trips.id
    │
    └────────────────────► TripReviews.trip_id
```

PostgreSQL is responsible for core transactional operations, while MongoDB manages flexible and high-frequency operational data.

---

# 2. Setup Scripts

## PostgreSQL Setup

The PostgreSQL database setup scripts are located in the `sql/` directory.

They should be executed in the following order:

1. `01_schema_ddl.sql`
2. `02_indexes.sql`
3. `03_triggers_and_audit.sql`
4. `04_stored_procedures.sql`
5. `05_materialized_views.sql`
6. `06_window_analytics.sql`

### PostgreSQL Schema

The main relational schema is created using:

```text
sql/01_schema_ddl.sql
```

This script creates tables, primary keys, foreign keys, constraints, and default values.

### PostgreSQL Indexes

Indexes are created using:

```text
sql/02_indexes.sql
```

These indexes improve the performance of frequently executed queries.

---

## MongoDB Setup

MongoDB collections and indexes are created using:

```text
mongo/01_collections_and_indexes.js
```

This script creates:

- `VehicleMetadata`
- `TelemetryPings`
- `TripReviews`

It also creates the required MongoDB indexes.

### MongoDB Geospatial Index

A `2dsphere` index is created on the location field of telemetry documents. This supports:

- Finding nearby vehicles
- Distance-based vehicle searches
- Finding the nearest available vehicle

### MongoDB TTL Index

A TTL index is created on:

```text
TelemetryPings.created_at
```

Old GPS telemetry data is automatically removed after the configured expiration period.

---

# Installation Requirements

Install:

- PostgreSQL
- MongoDB Community Server
- MongoDB Shell (`mongosh`)
- Python 3

Install the required Python dependencies:

```bash
pip install -r data_generation/requirements.txt
```

---

# Running the PostgreSQL Setup

Create the PostgreSQL database using the database name configured for the project.

Run the SQL scripts in the required order, for example:

```bash
psql -U postgres -d <database_name> -f sql/01_schema_ddl.sql
psql -U postgres -d <database_name> -f sql/02_indexes.sql
psql -U postgres -d <database_name> -f sql/03_triggers_and_audit.sql
psql -U postgres -d <database_name> -f sql/04_stored_procedures.sql
psql -U postgres -d <database_name> -f sql/05_materialized_views.sql
psql -U postgres -d <database_name> -f sql/06_window_analytics.sql
```

Replace `<database_name>` with the PostgreSQL database name configured in the project.

---

# Running the MongoDB Setup

Ensure that MongoDB is running.

Verify the MongoDB connection:

```bash
mongosh
```

Then run:

```javascript
db.runCommand({ ping: 1 })
```

Create the MongoDB collections and indexes.

### Windows PowerShell

```powershell
Get-Content mongo/01_collections_and_indexes.js | mongosh
```

---

# 3. Workflow Scripts

The workflow scripts demonstrate advanced PostgreSQL and MongoDB functionality.

## PostgreSQL Workflow – Triggers and Audit Logging

Located at:

```text
sql/03_triggers_and_audit.sql
```

The wallet audit trigger automatically records wallet balance changes.

```text
Wallet Balance Changes
        │
        ▼
Database Trigger
        │
        ▼
wallet_audit_logs
```

Each audit record stores:

- Rider ID
- Amount changed
- Action type
- Balance after the transaction
- Timestamp

---

## PostgreSQL Workflow – Stored Procedures

Located at:

```text
sql/04_stored_procedures.sql
```

Stored procedures handle transactional operations related to the ride-booking workflow.

```text
Rider Books a Trip
        │
        ▼
Stored Procedure Starts Transaction
        │
        ▼
Wallet Balance Checked
        │
        ▼
Fare Deducted
        │
        ▼
Wallet Audit Trigger Executes
        │
        ▼
Trip Created
        │
        ▼
Transaction Committed
```

---

## PostgreSQL Workflow – Materialized Views

Located at:

```text
sql/05_materialized_views.sql
```

Materialized views store precomputed results to support analytical queries and reduce repeated computation.

---

## PostgreSQL Workflow – Window Analytics

Located at:

```text
sql/06_window_analytics.sql
```

This script demonstrates SQL window functions, including a 7-day moving average.

```text
Daily Revenue
      │
      ▼
Window Function
      │
      ▼
7-Day Moving Average
```

---

## MongoDB Workflow – Geospatial Search

Located at:

```text
mongo/02_workflow_geonear.js
```

This workflow uses MongoDB's `$geoNear` aggregation stage.

```text
Rider Location
      │
      ▼
$geoNear
      │
      ├── Geospatial Search
      ├── Availability Filter
      └── Maximum Distance Filter
      │
      ▼
Nearest Available Vehicle
```

The workflow uses the `2dsphere` index on the vehicle location field.

---

## MongoDB Workflow – Review Analytics

Located at:

```text
mongo/03_workflow4_facet.js
```

This workflow uses MongoDB's `$facet` aggregation stage to calculate multiple analytics in a single aggregation, including:

- Rating distribution
- Average rating
- Total reviews
- Feedback tag analysis

---

# 4. Data Generation

The data generation scripts are located in:

```text
data_generation/
```

The project contains:

```text
postgres_seeder.py
mongo_seeder.py
```

These scripts are used to seed the project databases with **100,000+ rows/documents of mock data overall**.

## PostgreSQL Data Generation

Run:

```bash
python data_generation/postgres_seeder.py
```

The PostgreSQL seeder generates data for:

- Riders
- Vehicles
- Trips

The generated data is used to test relational operations, workflows, analytics, and query performance.

## MongoDB Data Generation

Run:

```bash
python data_generation/mongo_seeder.py
```

The MongoDB seeder generates data for:

- Vehicle metadata
- GPS telemetry
- Trip reviews

The UUID references maintain logical relationships between PostgreSQL and MongoDB records.

---

# 5. Performance Proof

Performance testing verifies that the project's heavy workflows use appropriate indexes and avoid unnecessary sequential or collection scans.

The performance scripts are located in:

```text
performance/
├── pg_explain_queries.sql
└── mongo_execution_stats.js
```

## PostgreSQL Performance Testing

PostgreSQL performance analysis uses:

```sql
EXPLAIN ANALYZE
```

Run:

```bash
psql -U postgres -d <database_name> -f performance/pg_explain_queries.sql
```

The relevant `EXPLAIN ANALYZE` excerpts and explanations for the required heavy workflows will be added to this section before final submission.

## MongoDB Performance Testing

MongoDB performance analysis uses:

```javascript
explain("executionStats")
```

Run:

### Windows PowerShell

```powershell
Get-Content performance/mongo_execution_stats.js | mongosh
```

The relevant `executionStats` excerpts and explanations for the required heavy workflows will be added to this section before final submission.

### Performance Evidence

The final README will include concise excerpts showing the relevant execution-plan evidence, such as:

- PostgreSQL `Index Scan`, `Index Only Scan`, or `Bitmap Index Scan`
- Absence of unnecessary `Seq Scan` operations on heavy tables
- MongoDB indexed access such as `IXSCAN`
- Avoidance of unnecessary `COLLSCAN` operations

The full performance outputs may remain in the repository, while the README will contain the relevant proof excerpts required for evaluation.

---

# Testing Checklist

## PostgreSQL

Verify that:

- Tables are created successfully.
- Primary keys and foreign keys work correctly.
- Check constraints are enforced.
- Indexes are created successfully.
- Stored procedures execute correctly.
- Wallet changes create audit records.
- Materialized views return results.
- Window analytics return results.
- The 7-day moving average is generated.
- Performance queries produce `EXPLAIN ANALYZE` results.

## MongoDB

Verify that:

- Collections are created successfully.
- The `2dsphere` index exists.
- The TTL index exists.
- `$geoNear` returns nearby available vehicles.
- `$facet` returns review analytics.
- Old telemetry data is eligible for automatic TTL deletion.
- Performance queries produce `executionStats`.
- Indexed queries avoid unnecessary `COLLSCAN` operations.

---

# Complete Execution Order

```text
1. Start PostgreSQL
        │
        ▼
2. Create/configure the PostgreSQL database
        │
        ▼
3. Run PostgreSQL schema script
        │
        ▼
4. Run PostgreSQL index script
        │
        ▼
5. Run triggers and audit script
        │
        ▼
6. Run stored procedures script
        │
        ▼
7. Run materialized views script
        │
        ▼
8. Run window analytics script
        │
        ▼
9. Start MongoDB
        │
        ▼
10. Create MongoDB collections and indexes
        │
        ▼
11. Run PostgreSQL data seeder
        │
        ▼
12. Run MongoDB data seeder
        │
        ▼
13. Test PostgreSQL workflows
        │
        ▼
14. Test MongoDB workflows
        │
        ▼
15. Run PostgreSQL performance tests
        │
        ▼
16. Run MongoDB performance tests
```

---

# Overall System Flow

```text
Rider
   │
   ▼
PostgreSQL Rider Data
   │
   ▼
Vehicle Selection
   │
   ├───────────────────────────────┐
   │                               │
   ▼                               ▼
Trip Transaction              MongoDB GPS Telemetry
   │                               │
   │                               ▼
   │                            $geoNear
   │                               │
   │                               ▼
   │                       Nearest Vehicle
   │
   ▼
Stored Procedure
   │
   ▼
Wallet Update
   │
   ▼
Audit Trigger
   │
   ▼
Trip Created / Completed
   │
   ▼
Trip Review Stored in MongoDB
   │
   ▼
Review Analytics using $facet
   │
   ▼
PostgreSQL Revenue Analytics
   │
   ▼
7-Day Moving Average
   │
   ▼
Performance Analysis
```

---

# Documentation

Additional project documentation is available in:

- `docs/relational_erd.jpeg` – PostgreSQL Entity Relationship Diagram
- `docs/mongo_schema_map.json` – MongoDB document structure mapping

---

# Conclusion

RideSync demonstrates the use of PostgreSQL and MongoDB together in a ride-booking system.

PostgreSQL handles structured transactional data and relational integrity, while MongoDB handles flexible metadata, high-frequency GPS telemetry, geospatial operations, and review analytics.

The project demonstrates:

- Relational schema design
- NoSQL document modelling
- Database constraints
- Indexing
- Stored procedures
- Triggers and audit logging
- Materialized views
- Window functions
- 7-day moving averages
- MongoDB geospatial queries
- TTL indexes
- Aggregation pipelines
- Large-scale mock data generation
- Query performance analysis

OUTPUTS:

1. Ride_Booking_21\performance\query_stats.txt

 table_name | row_count 
------------+-----------
 riders     |    300000
(1 row)

 table_name | row_count 
------------+-----------
 vehicles   |     80000
(1 row)

 table_name | row_count 
------------+-----------
 trips      |     99568
(1 row)

    table_name     | row_count 
-------------------+-----------
 wallet_audit_logs |    194202
(1 row)

        table_name         | row_count 
---------------------------+-----------
 mv_vehicle_lifetime_stats |         0
(1 row)

          table_name           | row_count 
-------------------------------+-----------
 vw_vehicle_revenue_moving_avg |     55369
(1 row)

 table_name |   status   | row_count 
------------+------------+-----------
 trips      | COMPLETED  |     94634
 trips      | IN TRANSIT |      2965
 trips      | REQUESTED  |      1969
(3 rows)

    table_name     |  action_type   | row_count 
-------------------+----------------+-----------
 wallet_audit_logs | ESCROW_HOLD    |     99568
 wallet_audit_logs | ESCROW_RELEASE |     94634
(2 rows)

          table_name           | row_count 
-------------------------------+-----------
 mv_vehicle_lifetime_stats     |         0
 riders                        |    300000
 trips                         |     99568
 vehicles                      |     80000
 vw_vehicle_revenue_moving_avg |     55369
 wallet_audit_logs             |    194202
(6 rows)

                                                                   QUERY PLAN                                                                    
-------------------------------------------------------------------------------------------------------------------------------------------------
 Index Scan using vehicles_license_plate_key on vehicles  (cost=2073.42..2081.44 rows=1 width=34) (actual time=15.271..15.272 rows=1.00 loops=1)
   Index Cond: ((license_plate)::text = ((InitPlan 1).col1)::text)
   Index Searches: 1
   Buffers: shared hit=680
   InitPlan 1
     ->  Limit  (cost=2073.00..2073.00 rows=1 width=20) (actual time=15.175..15.176 rows=1.00 loops=1)
           Buffers: shared hit=676
           ->  Sort  (cost=2073.00..2273.00 rows=80000 width=20) (actual time=15.172..15.173 rows=1.00 loops=1)
                 Sort Key: (random())
                 Sort Method: top-N heapsort  Memory: 25kB
                 Buffers: shared hit=676
                 ->  Seq Scan on vehicles vehicles_1  (cost=0.00..1673.00 rows=80000 width=20) (actual time=0.038..7.088 rows=80000.00 loops=1)
                       Buffers: shared hit=673
 Planning:
   Buffers: shared hit=19
 Planning Time: 0.175 ms
 Execution Time: 15.299 ms
(17 rows)

                                                                       QUERY PLAN                                                                       
--------------------------------------------------------------------------------------------------------------------------------------------------------
 Limit  (cost=7845.43..7845.43 rows=3 width=64) (actual time=50.960..50.961 rows=0.00 loops=1)
   Buffers: shared hit=2575
   InitPlan 1
     ->  Limit  (cost=7829.24..7829.24 rows=1 width=24) (actual time=50.847..50.847 rows=1.00 loops=1)
           Buffers: shared hit=2569
           ->  Sort  (cost=7829.24..8580.70 rows=300585 width=24) (actual time=50.845..50.846 rows=1.00 loops=1)
                 Sort Key: (random())
                 Sort Method: top-N heapsort  Memory: 25kB
                 Buffers: shared hit=2569
                 ->  Seq Scan on riders  (cost=0.00..6326.31 rows=300585 width=24) (actual time=0.019..26.926 rows=300000.00 loops=1)
                       Buffers: shared hit=2569
   ->  Sort  (cost=16.19..16.19 rows=3 width=64) (actual time=50.959..50.959 rows=0.00 loops=1)
         Sort Key: wallet_audit_logs."timestamp" DESC
         Sort Method: quicksort  Memory: 25kB
         Buffers: shared hit=2575
         ->  Bitmap Heap Scan on wallet_audit_logs  (cost=4.44..16.16 rows=3 width=64) (actual time=50.937..50.938 rows=0.00 loops=1)
               Recheck Cond: (rider_id = (InitPlan 1).col1)
               Buffers: shared hit=2572
               ->  Bitmap Index Scan on idx_wallet_audit_logs_rider_id  (cost=0.00..4.44 rows=3 width=0) (actual time=50.882..50.882 rows=0.00 loops=1)
                     Index Cond: (rider_id = (InitPlan 1).col1)
                     Index Searches: 1
                     Buffers: shared hit=2572
 Planning:
   Buffers: shared hit=20
 Planning Time: 0.320 ms
 Execution Time: 50.993 ms
(26 rows)

                                                          QUERY PLAN                                                           
-------------------------------------------------------------------------------------------------------------------------------
 Hash Join  (cost=2473.00..6140.64 rows=94580 width=47) (actual time=21.694..86.958 rows=94634.00 loops=1)
   Hash Cond: (t.vehicle_id = v.id)
   Buffers: shared hit=2101
   ->  Seq Scan on trips t  (cost=0.00..3419.36 rows=94580 width=46) (actual time=0.013..25.663 rows=94634.00 loops=1)
         Filter: (((status)::text = 'COMPLETED'::text) AND (created_at >= (now() - '7 days'::interval)))
         Rows Removed by Filter: 4934
         Buffers: shared hit=1428
   ->  Hash  (cost=1473.00..1473.00 rows=80000 width=33) (actual time=21.405..21.406 rows=80000.00 loops=1)
         Buckets: 131072  Batches: 1  Memory Usage: 6216kB
         Buffers: shared hit=673
         ->  Seq Scan on vehicles v  (cost=0.00..1473.00 rows=80000 width=33) (actual time=0.007..6.963 rows=80000.00 loops=1)
               Buffers: shared hit=673
 Planning:
   Buffers: shared hit=30
 Planning Time: 0.502 ms
 Execution Time: 90.204 ms
(16 rows)

                                                                QUERY PLAN                                                                 
-------------------------------------------------------------------------------------------------------------------------------------------
 Sort  (cost=5905.06..5905.08 rows=8 width=45) (actual time=86.553..86.555 rows=8.00 loops=1)
   Sort Key: (round(avg(t.fare_amount), 2))
   Sort Method: quicksort  Memory: 25kB
   Buffers: shared hit=2101
   ->  HashAggregate  (cost=5904.82..5904.94 rows=8 width=45) (actual time=86.537..86.543 rows=8.00 loops=1)
         Group Key: v.class
         Batches: 1  Memory Usage: 32kB
         Buffers: shared hit=2101
         ->  Hash Join  (cost=2473.00..5158.06 rows=99568 width=11) (actual time=18.685..65.457 rows=99568.00 loops=1)
               Hash Cond: (t.vehicle_id = v.id)
               Buffers: shared hit=2101
               ->  Seq Scan on trips t  (cost=0.00..2423.68 rows=99568 width=22) (actual time=0.011..5.796 rows=99568.00 loops=1)
                     Buffers: shared hit=1428
               ->  Hash  (cost=1473.00..1473.00 rows=80000 width=21) (actual time=18.394..18.395 rows=80000.00 loops=1)
                     Buckets: 131072  Batches: 1  Memory Usage: 5209kB
                     Buffers: shared hit=673
                     ->  Seq Scan on vehicles v  (cost=0.00..1473.00 rows=80000 width=21) (actual time=0.010..6.532 rows=80000.00 loops=1)
                           Buffers: shared hit=673
 Planning:
   Buffers: shared hit=23
 Planning Time: 0.273 ms
 Execution Time: 87.267 ms
(22 rows)

                                                              QUERY PLAN                                                               
---------------------------------------------------------------------------------------------------------------------------------------
 Limit  (cost=21.38..21.40 rows=10 width=193) (actual time=0.023..0.023 rows=0.00 loops=1)
   ->  Sort  (cost=21.38..22.28 rows=360 width=193) (actual time=0.022..0.023 rows=0.00 loops=1)
         Sort Key: lifetime_earnings DESC
         Sort Method: quicksort  Memory: 25kB
         ->  Seq Scan on mv_vehicle_lifetime_stats  (cost=0.00..13.60 rows=360 width=193) (actual time=0.006..0.006 rows=0.00 loops=1)
 Planning:
   Buffers: shared hit=1
 Planning Time: 0.097 ms
 Execution Time: 0.038 ms
(9 rows)

                                                                                         QUERY PLAN                                                                                         
--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
 Subquery Scan on vw_vehicle_revenue_moving_avg  (cost=33528.91..42196.68 rows=473 width=109) (actual time=383.508..388.137 rows=1.00 loops=1)
   Filter: (vw_vehicle_revenue_moving_avg.vehicle_id = (InitPlan 1).col1)
   Rows Removed by Filter: 55368
   Buffers: shared hit=101334, temp read=976 written=978
   InitPlan 1
     ->  Limit  (cost=2073.00..2073.00 rows=1 width=24) (actual time=13.095..13.097 rows=1.00 loops=1)
           Buffers: shared hit=673
           ->  Sort  (cost=2073.00..2273.00 rows=80000 width=24) (actual time=13.093..13.094 rows=1.00 loops=1)
                 Sort Key: (random())
                 Sort Method: top-N heapsort  Memory: 25kB
                 Buffers: shared hit=673
                 ->  Seq Scan on vehicles  (cost=0.00..1673.00 rows=80000 width=24) (actual time=0.034..6.363 rows=80000.00 loops=1)
                       Buffers: shared hit=673
   ->  Incremental Sort  (cost=31455.91..38941.30 rows=94590 width=141) (actual time=364.851..371.741 rows=55369.00 loops=1)
         Sort Key: ((trips.created_at)::date), (dense_rank() OVER w1)
         Presorted Key: ((trips.created_at)::date)
         Full-sort Groups: 1  Sort Method: quicksort  Average Memory: 30kB  Peak Memory: 30kB
         Pre-sorted Groups: 1  Sort Method: external merge  Average Disk: 4424kB  Peak Disk: 4424kB
         Buffers: shared hit=100661, temp read=976 written=978
         ->  WindowAgg  (cost=31424.26..33552.51 rows=94590 width=141) (actual time=300.825..343.635 rows=55369.00 loops=1)
               Window: w1 AS (PARTITION BY ((trips.created_at)::date) ORDER BY (avg((sum(trips.fare_amount))) OVER w1) ROWS UNBOUNDED PRECEDING)
               Storage: Memory  Maximum Storage: 17kB
               Buffers: shared hit=100661, temp read=423 written=424
               ->  Sort  (cost=31424.24..31660.71 rows=94590 width=101) (actual time=300.804..310.160 rows=55369.00 loops=1)
                     Sort Key: ((trips.created_at)::date), (avg((sum(trips.fare_amount))) OVER w1) DESC
                     Sort Method: external merge  Disk: 3384kB
                     Buffers: shared hit=100661, temp read=423 written=424
                     ->  Hash Join  (cost=2473.79..18433.66 rows=94590 width=101) (actual time=24.060..234.410 rows=55369.00 loops=1)
                           Hash Cond: (trips.vehicle_id = v.id)
                           Buffers: shared hit=100661
                           ->  WindowAgg  (cost=0.79..15712.35 rows=94590 width=84) (actual time=0.102..182.063 rows=55369.00 loops=1)
                                 Window: w1 AS (PARTITION BY trips.vehicle_id ORDER BY ((trips.created_at)::date) ROWS BETWEEN '6'::bigint PRECEDING AND CURRENT ROW)
                                 Storage: Memory  Maximum Storage: 17kB
                                 Buffers: shared hit=99988
                                 ->  GroupAggregate  (cost=0.62..14057.02 rows=94590 width=52) (actual time=0.092..133.820 rows=55369.00 loops=1)
                                       Group Key: trips.vehicle_id, ((trips.created_at)::date)
                                       Buffers: shared hit=99988
                                       ->  Incremental Sort  (cost=0.62..11928.75 rows=94590 width=26) (actual time=0.086..98.813 rows=94634.00 loops=1)
                                             Sort Key: trips.vehicle_id, ((trips.created_at)::date)
                                             Presorted Key: trips.vehicle_id
                                             Full-sort Groups: 2903  Sort Method: quicksort  Average Memory: 26kB  Peak Memory: 26kB
                                             Buffers: shared hit=99988
                                             ->  Index Scan using idx_trips_vehicle_id on trips  (cost=0.42..9291.26 rows=94590 width=26) (actual time=0.017..81.658 rows=94634.00 loops=1)
                                                   Filter: ((status)::text = 'COMPLETED'::text)
                                                   Rows Removed by Filter: 4934
                                                   Index Searches: 1
                                                   Buffers: shared hit=99988
                           ->  Hash  (cost=1473.00..1473.00 rows=80000 width=33) (actual time=23.785..23.786 rows=80000.00 loops=1)
                                 Buckets: 131072  Batches: 1  Memory Usage: 6216kB
                                 Buffers: shared hit=673
                                 ->  Seq Scan on vehicles v  (cost=0.00..1473.00 rows=80000 width=33) (actual time=0.014..7.018 rows=80000.00 loops=1)
                                       Buffers: shared hit=673
 Planning:
   Buffers: shared hit=4
 Planning Time: 0.327 ms
 Execution Time: 390.674 ms
(56 rows)

                                                                         QUERY PLAN                                                                         
------------------------------------------------------------------------------------------------------------------------------------------------------------
 Limit  (cost=13126.93..13129.21 rows=20 width=35) (actual time=93.562..99.594 rows=20.00 loops=1)
   Buffers: shared hit=5175
   InitPlan 1
     ->  Finalize Aggregate  (cost=5779.41..5779.42 rows=1 width=32) (actual time=46.339..46.389 rows=1.00 loops=1)
           Buffers: shared hit=2569
           ->  Gather  (cost=5779.19..5779.40 rows=2 width=32) (actual time=46.156..46.381 rows=2.00 loops=1)
                 Workers Planned: 1
                 Workers Launched: 1
                 Buffers: shared hit=2569
                 ->  Partial Aggregate  (cost=4779.19..4779.20 rows=1 width=32) (actual time=25.311..25.312 rows=1.00 loops=2)
                       Buffers: shared hit=2569
                       ->  Parallel Seq Scan on riders riders_1  (cost=0.00..4337.15 rows=176815 width=6) (actual time=0.009..7.911 rows=150000.00 loops=2)
                             Buffers: shared hit=2569
   ->  Gather Merge  (cost=7347.51..18766.80 rows=100195 width=35) (actual time=93.561..99.540 rows=20.00 loops=1)
         Workers Planned: 1
         Workers Launched: 1
         Buffers: shared hit=5175
         ->  Sort  (cost=6347.50..6494.85 rows=58938 width=35) (actual time=30.691..30.692 rows=18.00 loops=2)
               Sort Key: riders.wallet_balance DESC
               Sort Method: top-N heapsort  Memory: 27kB
               Buffers: shared hit=2606
               Worker 0:  Sort Method: top-N heapsort  Memory: 27kB
               ->  Parallel Seq Scan on riders  (cost=0.00..4779.18 rows=58938 width=35) (actual time=0.013..21.078 rows=75267.00 loops=2)
                     Filter: (wallet_balance > (InitPlan 1).col1)
                     Rows Removed by Filter: 74733
                     Buffers: shared hit=2569
 Planning:
   Buffers: shared hit=6
 Planning Time: 0.160 ms
 Execution Time: 99.648 ms
(30 rows)


2. Ride_Booking_21\performance\mongo_explain_stats.txt


1. NEAREST AVAILABLE VEHICLE ($GEONEAR)

-- Key Metrics --
  Stage 1: $geoNearCursor
    Winning plan stage : FETCH
    Index used         : location_2dsphere
    Keys examined      : 0
    Docs examined      : 0
    Returned           : 0
  Stage 2: $limit

-- Full Explain Output (raw JSON) --
{
  "explainVersion": "1",
  "stages": [
    {
      "$geoNearCursor": {
        "queryPlanner": {
          "namespace": "ridesync_mongo.TelemetryPings",
          "parsedQuery": {
            "$and": [
              {
                "is_available": {
                  "$eq": true
                }
              },
              {
                "location": {
                  "$nearSphere": {
                    "type": "Point",
                    "coordinates": [
                      78.4867,
                      17.385
                    ]
                  },
                  "$maxDistance": 5000
                }
              }
            ]
          },
          "indexFilterSet": false,
          "queryHash": "E485BCD7",
          "planCacheShapeHash": "E485BCD7",
          "planCacheKey": "377DC922",
          "optimizationTimeMillis": 0,
          "cursorType": "regular",
          "maxIndexedOrSolutionsReached": false,
          "maxIndexedAndSolutionsReached": false,
          "maxScansToExplodeReached": false,
          "prunedSimilarIndexes": false,
          "winningPlan": {
            "isCached": false,
            "stage": "FETCH",
            "filter": {
              "is_available": {
                "$eq": true
              }
            },
            "nss": "ridesync_mongo.TelemetryPings",
            "inputStage": {
              "stage": "GEO_NEAR_2DSPHERE",
              "nss": "ridesync_mongo.TelemetryPings",
              "keyPattern": {
                "location": "2dsphere"
              },
              "indexName": "location_2dsphere",
              "indexVersion": 2,
              "inputStage": {
                "stage": "FETCH",
                "inputStage": {
                  "stage": "IXSCAN",
                  "keyPattern": {
                    "location": "2dsphere"
                  },
                  "indexName": "location_2dsphere",
                  "isMultiKey": false,
                  "multiKeyPaths": {
                    "location": []
                  },
                  "isUnique": false,
                  "isSparse": false,
                  "isPartial": false,
                  "indexVersion": 2,
                  "direction": "forward",
                  "indexBounds": {
                    "location": [
                      "[4251398048237748224, 4251398048237748224]",
                      "[4305441243766194176, 4305441243766194176]",
                      "[4308537468510011392, 4308537468510011392]",
                      "[4308695798184411136, 4308695798184411136]",
                      "[4308696528328851457, 4308696536918786047]",
                      "[4308696536918786048, 4308696536918786048]",
                      "[4308696554098655232, 4308696554098655232]",
                      "[4308696622818131968, 4308696622818131968]",
                      "[4308696897696038912, 4308696897696038912]",
                      "[4308700196230922240, 4308700196230922240]",
                      "[4308703494765805568, 4308703494765805568]",
                      "[4308703494765805569, 4308704044521619455]",
                      "[4308704044521619457, 4308704181960572927]",
                      "[4308704181960572929, 4308704319399526399]",
                      "[4308704319399526400, 4308704319399526400]",
                      "[4308704319399526401, 4308704321547010047]",
                      "[4308704323694493696, 4308704323694493696]",
                      "[4308704336579395584, 4308704336579395584]",
                      "[4308704388119003136, 4308704388119003136]",
                      "[4308704456838479873, 4308704594277433343]",
                      "[4308704594277433345, 4308705144033247231]",
                      "[4308705178392985601, 4308705212752723967]",
                      "[4308705212752723968, 4308705212752723968]",
                      "[4308705418911154176, 4308705418911154176]",
                      "[4308705556350107649, 4308705693789061119]",
                      "[4308705693789061120, 4308705693789061120]",
                      "[4308705693789061121, 4308705831228014591]",
                      "[4308705968666968064, 4308705968666968064]",
                      "[4308706174825398272, 4308706174825398272]",
                      "[4308706174825398273, 4308706209185136639]",
                      "[4308706243544875009, 4308706793300688895]",
                      "[4308706793300688897, 4308706827660427263]",
                      "[4308706862020165632, 4308706862020165632]",
                      "[4308706896379904001, 4308706930739642367]",
                      "[4308707068178595840, 4308707068178595840]",
                      "[4308707892812316672, 4308707892812316672]",
                      "[4308708992323944448, 4308708992323944448]",
                      "[4308748574742544384, 4308748574742544384]",
                      "[4308818943486722048, 4308818943486722048]",
                      "[4309944843393564672, 4309944843393564672]"
                    ]
                  }
                }
              }
            }
          },
          "rejectedPlans": []
        },
        "executionStats": {
          "executionSuccess": true,
          "nReturned": 0,
          "executionTimeMillis": 0,
          "totalKeysExamined": 0,
          "totalDocsExamined": 0,
          "executionStages": {
            "isCached": false,
            "stage": "FETCH",
            "filter": {
              "is_available": {
                "$eq": true
              }
            },
            "nReturned": 0,
            "executionTimeMillisEstimate": 0,
            "works": 18,
            "advanced": 0,
            "needTime": 17,
            "needYield": 0,
            "saveState": 2,
            "restoreState": 1,
            "isEOF": 1,
            "nss": "ridesync_mongo.TelemetryPings",
            "docsExamined": 0,
            "alreadyHasObj": 0,
            "inputStage": {
              "stage": "GEO_NEAR_2DSPHERE",
              "nReturned": 0,
              "executionTimeMillisEstimate": 0,
              "works": 18,
              "advanced": 0,
              "needTime": 17,
              "needYield": 0,
              "saveState": 2,
              "restoreState": 1,
              "isEOF": 1,
              "nss": "ridesync_mongo.TelemetryPings",
              "keyPattern": {
                "location": "2dsphere"
              },
              "indexName": "location_2dsphere",
              "indexVersion": 2,
              "searchIntervals": [
                {
                  "minDistance": 0,
                  "maxDistance": 5000,
                  "maxInclusive": true,
                  "nBuffered": 0,
                  "nReturned": 0
                }
              ],
              "usedDisk": false,
              "spills": 0,
              "spilledRecords": 0,
              "spilledBytes": 0,
              "spilledDataStorageSize": 0,
              "inputStage": {
                "stage": "FETCH",
                "nReturned": 0,
                "executionTimeMillisEstimate": 0,
                "works": 1,
                "advanced": 0,
                "needTime": 0,
                "needYield": 0,
                "saveState": 1,
                "restoreState": 0,
                "isEOF": 1,
                "docsExamined": 0,
                "alreadyHasObj": 0,
                "inputStage": {
                  "stage": "IXSCAN",
                  "nReturned": 0,
                  "executionTimeMillisEstimate": 0,
                  "works": 1,
                  "advanced": 0,
                  "needTime": 0,
                  "needYield": 0,
                  "saveState": 1,
                  "restoreState": 0,
                  "isEOF": 1,
                  "keyPattern": {
                    "location": "2dsphere"
                  },
                  "indexName": "location_2dsphere",
                  "isMultiKey": false,
                  "multiKeyPaths": {
                    "location": []
                  },
                  "isUnique": false,
                  "isSparse": false,
                  "isPartial": false,
                  "indexVersion": 2,
                  "direction": "forward",
                  "indexBounds": {
                    "location": [
                      "[4251398048237748224, 4251398048237748224]",
                      "[4305441243766194176, 4305441243766194176]",
                      "[4308537468510011392, 4308537468510011392]",
                      "[4308695798184411136, 4308695798184411136]",
                      "[4308696528328851457, 4308696536918786047]",
                      "[4308696536918786048, 4308696536918786048]",
                      "[4308696554098655232, 4308696554098655232]",
                      "[4308696622818131968, 4308696622818131968]",
                      "[4308696897696038912, 4308696897696038912]",
                      "[4308700196230922240, 4308700196230922240]",
                      "[4308703494765805568, 4308703494765805568]",
                      "[4308703494765805569, 4308704044521619455]",
                      "[4308704044521619457, 4308704181960572927]",
                      "[4308704181960572929, 4308704319399526399]",
                      "[4308704319399526400, 4308704319399526400]",
                      "[4308704319399526401, 4308704321547010047]",
                      "[4308704323694493696, 4308704323694493696]",
                      "[4308704336579395584, 4308704336579395584]",
                      "[4308704388119003136, 4308704388119003136]",
                      "[4308704456838479873, 4308704594277433343]",
                      "[4308704594277433345, 4308705144033247231]",
                      "[4308705178392985601, 4308705212752723967]",
                      "[4308705212752723968, 4308705212752723968]",
                      "[4308705418911154176, 4308705418911154176]",
                      "[4308705556350107649, 4308705693789061119]",
                      "[4308705693789061120, 4308705693789061120]",
                      "[4308705693789061121, 4308705831228014591]",
                      "[4308705968666968064, 4308705968666968064]",
                      "[4308706174825398272, 4308706174825398272]",
                      "[4308706174825398273, 4308706209185136639]",
                      "[4308706243544875009, 4308706793300688895]",
                      "[4308706793300688897, 4308706827660427263]",
                      "[4308706862020165632, 4308706862020165632]",
                      "[4308706896379904001, 4308706930739642367]",
                      "[4308707068178595840, 4308707068178595840]",
                      "[4308707892812316672, 4308707892812316672]",
                      "[4308708992323944448, 4308708992323944448]",
                      "[4308748574742544384, 4308748574742544384]",
                      "[4308818943486722048, 4308818943486722048]",
                      "[4309944843393564672, 4309944843393564672]"
                    ]
                  },
                  "keysExamined": 0,
                  "seeks": 1,
                  "dupsTested": 0,
                  "dupsDropped": 0,
                  "peakTrackedMemBytes": 0
                }
              }
            }
          },
          "allPlansExecution": []
        }
      },
      "nReturned": {
        "high": 0,
        "low": 0,
        "unsigned": false
      },
      "executionTimeMillisEstimate": {
        "high": 0,
        "low": 0,
        "unsigned": false
      }
    },
    {
      "$limit": {
        "high": 0,
        "low": 5,
        "unsigned": false
      },
      "nReturned": {
        "high": 0,
        "low": 0,
        "unsigned": false
      },
      "executionTimeMillisEstimate": {
        "high": 0,
        "low": 0,
        "unsigned": false
      }
    }
  ],
  "queryShapeHash": "121172F64792D4493E6BA8CC7FF12BB4047B688FCB1E037C39DFB2F225DE0358",
  "serverInfo": {
    "host": "DESKTOP-1QS0HPT",
    "port": 27017,
    "version": "8.3.8",
    "gitVersion": "35e8c8a57f78157ed9fac1a9e90ee6c1818adab6"
  },
  "serverParameters": {
    "internalQueryFacetBufferSizeBytes": 104857600,
    "internalDocumentSourceGroupMaxMemoryBytes": 104857600,
    "internalQueryMaxBlockingSortMemoryUsageBytes": 104857600,
    "internalDocumentSourceSetWindowFieldsMaxMemoryBytes": 104857600,
    "internalQueryFacetMaxOutputDocSizeBytes": 104857600,
    "internalLookupStageIntermediateDocumentMaxSizeBytes": 104857600,
    "internalQueryProhibitBlockingMergeOnMongoS": 0,
    "internalQueryMaxAddToSetBytes": 104857600,
    "internalQueryFrameworkControl": "trySbeRestricted",
    "internalQueryPlannerIgnoreIndexWithCollationForRegex": 1
  },
  "command": {
    "aggregate": "TelemetryPings",
    "pipeline": [
      {
        "$geoNear": {
          "near": {
            "type": "Point",
            "coordinates": [
              78.4867,
              17.385
            ]
          },
          "distanceField": "distance_meters",
          "maxDistance": 5000,
          "query": {
            "is_available": true
          },
          "spherical": true
        }
      },
      {
        "$limit": 5
      }
    ],
    "cursor": {},
    "$db": "ridesync_mongo"
  },
  "ok": 1
}

2. PINGS FOR VEHICLE VEH_001

-- Key Metrics --
  Winning plan stage : COLLSCAN
  Index used         : COLLSCAN / none
  Keys examined      : 0
  Docs examined      : 4
  Returned           : 1
  Execution time(ms) : 0

-- Full Explain Output (raw JSON) --
{
  "explainVersion": "1",
  "queryPlanner": {
    "namespace": "ridesync_mongo.TelemetryPings",
    "parsedQuery": {
      "vehicle_id": {
        "$eq": "veh_001"
      }
    },
    "indexFilterSet": false,
    "queryHash": "43A638CF",
    "planCacheShapeHash": "43A638CF",
    "planCacheKey": "78C8A740",
    "optimizationTimeMillis": 0,
    "maxIndexedOrSolutionsReached": false,
    "maxIndexedAndSolutionsReached": false,
    "maxScansToExplodeReached": false,
    "prunedSimilarIndexes": false,
    "winningPlan": {
      "isCached": false,
      "stage": "COLLSCAN",
      "filter": {
        "vehicle_id": {
          "$eq": "veh_001"
        }
      },
      "nss": "ridesync_mongo.TelemetryPings",
      "direction": "forward"
    },
    "rejectedPlans": []
  },
  "executionStats": {
    "executionSuccess": true,
    "nReturned": 1,
    "executionTimeMillis": 0,
    "totalKeysExamined": 0,
    "totalDocsExamined": 4,
    "executionStages": {
      "isCached": false,
      "stage": "COLLSCAN",
      "filter": {
        "vehicle_id": {
          "$eq": "veh_001"
        }
      },
      "nReturned": 1,
      "executionTimeMillisEstimate": 0,
      "works": 5,
      "advanced": 1,
      "needTime": 3,
      "needYield": 0,
      "saveState": 0,
      "restoreState": 0,
      "isEOF": 1,
      "nss": "ridesync_mongo.TelemetryPings",
      "direction": "forward",
      "docsExamined": 4
    }
  },
  "queryShapeHash": "EF48648FC230669790A288BB55855B4CCEB93C51DCD27B2445A3F4F26BB483E3",
  "command": {
    "find": "TelemetryPings",
    "filter": {
      "vehicle_id": "veh_001"
    },
    "$db": "ridesync_mongo"
  },
  "serverInfo": {
    "host": "DESKTOP-1QS0HPT",
    "port": 27017,
    "version": "8.3.8",
    "gitVersion": "35e8c8a57f78157ed9fac1a9e90ee6c1818adab6"
  },
  "serverParameters": {
    "internalQueryFacetBufferSizeBytes": 104857600,
    "internalDocumentSourceGroupMaxMemoryBytes": 104857600,
    "internalQueryMaxBlockingSortMemoryUsageBytes": 104857600,
    "internalDocumentSourceSetWindowFieldsMaxMemoryBytes": 104857600,
    "internalQueryFacetMaxOutputDocSizeBytes": 104857600,
    "internalLookupStageIntermediateDocumentMaxSizeBytes": 104857600,
    "internalQueryProhibitBlockingMergeOnMongoS": 0,
    "internalQueryMaxAddToSetBytes": 104857600,
    "internalQueryFrameworkControl": "trySbeRestricted",
    "internalQueryPlannerIgnoreIndexWithCollationForRegex": 1
  },
  "ok": 1
}

3. COUNT OF AVAILABLE VEHICLES

-- Key Metrics --
  Winning plan stage : COLLSCAN
  Index used         : COLLSCAN / none
  Keys examined      : 0
  Docs examined      : 4
  Returned           : 3
  Execution time(ms) : 0

-- Full Explain Output (raw JSON) --
{
  "explainVersion": "1",
  "queryPlanner": {
    "namespace": "ridesync_mongo.TelemetryPings",
    "parsedQuery": {
      "is_available": {
        "$eq": true
      }
    },
    "indexFilterSet": false,
    "queryHash": "F4DED026",
    "planCacheShapeHash": "F4DED026",
    "planCacheKey": "4ADB1B3C",
    "optimizationTimeMillis": 0,
    "maxIndexedOrSolutionsReached": false,
    "maxIndexedAndSolutionsReached": false,
    "maxScansToExplodeReached": false,
    "prunedSimilarIndexes": false,
    "winningPlan": {
      "isCached": false,
      "stage": "COLLSCAN",
      "filter": {
        "is_available": {
          "$eq": true
        }
      },
      "nss": "ridesync_mongo.TelemetryPings",
      "direction": "forward"
    },
    "rejectedPlans": []
  },
  "executionStats": {
    "executionSuccess": true,
    "nReturned": 3,
    "executionTimeMillis": 0,
    "totalKeysExamined": 0,
    "totalDocsExamined": 4,
    "executionStages": {
      "isCached": false,
      "stage": "COLLSCAN",
      "filter": {
        "is_available": {
          "$eq": true
        }
      },
      "nReturned": 3,
      "executionTimeMillisEstimate": 0,
      "works": 5,
      "advanced": 3,
      "needTime": 1,
      "needYield": 0,
      "saveState": 0,
      "restoreState": 0,
      "isEOF": 1,
      "nss": "ridesync_mongo.TelemetryPings",
      "direction": "forward",
      "docsExamined": 4
    }
  },
  "queryShapeHash": "65C561A373D8FEC1B159541545881DD86FDCA37BBEDD0199FD79A9C764ECCDFA",
  "command": {
    "find": "TelemetryPings",
    "filter": {
      "is_available": true
    },
    "$db": "ridesync_mongo"
  },
  "serverInfo": {
    "host": "DESKTOP-1QS0HPT",
    "port": 27017,
    "version": "8.3.8",
    "gitVersion": "35e8c8a57f78157ed9fac1a9e90ee6c1818adab6"
  },
  "serverParameters": {
    "internalQueryFacetBufferSizeBytes": 104857600,
    "internalDocumentSourceGroupMaxMemoryBytes": 104857600,
    "internalQueryMaxBlockingSortMemoryUsageBytes": 104857600,
    "internalDocumentSourceSetWindowFieldsMaxMemoryBytes": 104857600,
    "internalQueryFacetMaxOutputDocSizeBytes": 104857600,
    "internalLookupStageIntermediateDocumentMaxSizeBytes": 104857600,
    "internalQueryProhibitBlockingMergeOnMongoS": 0,
    "internalQueryMaxAddToSetBytes": 104857600,
    "internalQueryFrameworkControl": "trySbeRestricted",
    "internalQueryPlannerIgnoreIndexWithCollationForRegex": 1
  },
  "ok": 1
}

4. GEO + AVAILABILITY FILTER

-- Key Metrics --
  Winning plan stage : FETCH
  Index used         : location_2dsphere
  Keys examined      : 0
  Docs examined      : 0
  Returned           : 0
  Execution time(ms) : 0

-- Full Explain Output (raw JSON) --
{
  "explainVersion": "1",
  "queryPlanner": {
    "namespace": "ridesync_mongo.TelemetryPings",
    "parsedQuery": {
      "$and": [
        {
          "is_available": {
            "$eq": true
          }
        },
        {
          "location": {
            "$near": {
              "$geometry": {
                "type": "Point",
                "coordinates": [
                  78.4867,
                  17.385
                ]
              },
              "$maxDistance": 3000
            }
          }
        }
      ]
    },
    "indexFilterSet": false,
    "queryHash": "2EF3247F",
    "planCacheShapeHash": "2EF3247F",
    "planCacheKey": "F2D136A5",
    "optimizationTimeMillis": 0,
    "maxIndexedOrSolutionsReached": false,
    "maxIndexedAndSolutionsReached": false,
    "maxScansToExplodeReached": false,
    "prunedSimilarIndexes": false,
    "winningPlan": {
      "isCached": false,
      "stage": "FETCH",
      "filter": {
        "is_available": {
          "$eq": true
        }
      },
      "nss": "ridesync_mongo.TelemetryPings",
      "inputStage": {
        "stage": "GEO_NEAR_2DSPHERE",
        "nss": "ridesync_mongo.TelemetryPings",
        "keyPattern": {
          "location": "2dsphere"
        },
        "indexName": "location_2dsphere",
        "indexVersion": 2,
        "inputStage": {
          "stage": "FETCH",
          "inputStage": {
            "stage": "IXSCAN",
            "keyPattern": {
              "location": "2dsphere"
            },
            "indexName": "location_2dsphere",
            "isMultiKey": false,
            "multiKeyPaths": {
              "location": []
            },
            "isUnique": false,
            "isSparse": false,
            "isPartial": false,
            "indexVersion": 2,
            "direction": "forward",
            "indexBounds": {
              "location": [
                "[4251398048237748224, 4251398048237748224]",
                "[4305441243766194176, 4305441243766194176]",
                "[4308537468510011392, 4308537468510011392]",
                "[4308695798184411136, 4308695798184411136]",
                "[4308700196230922240, 4308700196230922240]",
                "[4308703494765805568, 4308703494765805568]",
                "[4308703769643712512, 4308703769643712512]",
                "[4308703838363189248, 4308703838363189248]",
                "[4308703872722927617, 4308703907082665983]",
                "[4308703907082665985, 4308704044521619455]",
                "[4308704044521619457, 4308704078881357823]",
                "[4308704078881357825, 4308704113241096191]",
                "[4308704113241096192, 4308704113241096192]",
                "[4308704147600834561, 4308704181960572927]",
                "[4308704319399526400, 4308704319399526400]",
                "[4308704662996910080, 4308704662996910080]",
                "[4308704680176779264, 4308704680176779264]",
                "[4308704688766713857, 4308704697356648447]",
                "[4308704697356648449, 4308704697893519359]",
                "[4308704698430390272, 4308704698430390272]",
                "[4308704701651615744, 4308704701651615744]",
                "[4308704714536517632, 4308704714536517632]",
                "[4308704731716386817, 4308704869155340287]",
                "[4308704869155340288, 4308704869155340288]",
                "[4308704869155340289, 4308704903515078655]",
                "[4308704903515078657, 4308704937874817023]",
                "[4308704937874817024, 4308704937874817024]",
                "[4308704937874817025, 4308704972234555391]",
                "[4308704982971973633, 4308704985119457279]",
                "[4308704985119457280, 4308704985119457280]",
                "[4308704989414424576, 4308704989414424576]",
                "[4308705693789061120, 4308705693789061120]",
                "[4308706312264351744, 4308706312264351744]",
                "[4308706312264351745, 4308706346624090111]",
                "[4308706380983828481, 4308706518422781951]",
                "[4308706518422781952, 4308706518422781952]",
                "[4308706518422781953, 4308706655861735423]",
                "[4308706655861735425, 4308706690221473791]",
                "[4308706690221473793, 4308706724581212159]",
                "[4308706724581212160, 4308706724581212160]",
                "[4308708992323944448, 4308708992323944448]",
                "[4308748574742544384, 4308748574742544384]",
                "[4308818943486722048, 4308818943486722048]",
                "[4309944843393564672, 4309944843393564672]"
              ]
            }
          }
        }
      }
    },
    "rejectedPlans": []
  },
  "executionStats": {
    "executionSuccess": true,
    "nReturned": 0,
    "executionTimeMillis": 0,
    "totalKeysExamined": 0,
    "totalDocsExamined": 0,
    "executionStages": {
      "isCached": false,
      "stage": "FETCH",
      "filter": {
        "is_available": {
          "$eq": true
        }
      },
      "nReturned": 0,
      "executionTimeMillisEstimate": 0,
      "works": 18,
      "advanced": 0,
      "needTime": 17,
      "needYield": 0,
      "saveState": 0,
      "restoreState": 0,
      "isEOF": 1,
      "nss": "ridesync_mongo.TelemetryPings",
      "docsExamined": 0,
      "alreadyHasObj": 0,
      "inputStage": {
        "stage": "GEO_NEAR_2DSPHERE",
        "nReturned": 0,
        "executionTimeMillisEstimate": 0,
        "works": 18,
        "advanced": 0,
        "needTime": 17,
        "needYield": 0,
        "saveState": 0,
        "restoreState": 0,
        "isEOF": 1,
        "nss": "ridesync_mongo.TelemetryPings",
        "keyPattern": {
          "location": "2dsphere"
        },
        "indexName": "location_2dsphere",
        "indexVersion": 2,
        "searchIntervals": [
          {
            "minDistance": 0,
            "maxDistance": 3000,
            "maxInclusive": true,
            "nBuffered": 0,
            "nReturned": 0
          }
        ],
        "usedDisk": false,
        "spills": 0,
        "spilledRecords": 0,
        "spilledBytes": 0,
        "spilledDataStorageSize": 0,
        "inputStage": {
          "stage": "FETCH",
          "nReturned": 0,
          "executionTimeMillisEstimate": 0,
          "works": 1,
          "advanced": 0,
          "needTime": 0,
          "needYield": 0,
          "saveState": 0,
          "restoreState": 0,
          "isEOF": 1,
          "docsExamined": 0,
          "alreadyHasObj": 0,
          "inputStage": {
            "stage": "IXSCAN",
            "nReturned": 0,
            "executionTimeMillisEstimate": 0,
            "works": 1,
            "advanced": 0,
            "needTime": 0,
            "needYield": 0,
            "saveState": 0,
            "restoreState": 0,
            "isEOF": 1,
            "keyPattern": {
              "location": "2dsphere"
            },
            "indexName": "location_2dsphere",
            "isMultiKey": false,
            "multiKeyPaths": {
              "location": []
            },
            "isUnique": false,
            "isSparse": false,
            "isPartial": false,
            "indexVersion": 2,
            "direction": "forward",
            "indexBounds": {
              "location": [
                "[4251398048237748224, 4251398048237748224]",
                "[4305441243766194176, 4305441243766194176]",
                "[4308537468510011392, 4308537468510011392]",
                "[4308695798184411136, 4308695798184411136]",
                "[4308700196230922240, 4308700196230922240]",
                "[4308703494765805568, 4308703494765805568]",
                "[4308703769643712512, 4308703769643712512]",
                "[4308703838363189248, 4308703838363189248]",
                "[4308703872722927617, 4308703907082665983]",
                "[4308703907082665985, 4308704044521619455]",
                "[4308704044521619457, 4308704078881357823]",
                "[4308704078881357825, 4308704113241096191]",
                "[4308704113241096192, 4308704113241096192]",
                "[4308704147600834561, 4308704181960572927]",
                "[4308704319399526400, 4308704319399526400]",
                "[4308704662996910080, 4308704662996910080]",
                "[4308704680176779264, 4308704680176779264]",
                "[4308704688766713857, 4308704697356648447]",
                "[4308704697356648449, 4308704697893519359]",
                "[4308704698430390272, 4308704698430390272]",
                "[4308704701651615744, 4308704701651615744]",
                "[4308704714536517632, 4308704714536517632]",
                "[4308704731716386817, 4308704869155340287]",
                "[4308704869155340288, 4308704869155340288]",
                "[4308704869155340289, 4308704903515078655]",
                "[4308704903515078657, 4308704937874817023]",
                "[4308704937874817024, 4308704937874817024]",
                "[4308704937874817025, 4308704972234555391]",
                "[4308704982971973633, 4308704985119457279]",
                "[4308704985119457280, 4308704985119457280]",
                "[4308704989414424576, 4308704989414424576]",
                "[4308705693789061120, 4308705693789061120]",
                "[4308706312264351744, 4308706312264351744]",
                "[4308706312264351745, 4308706346624090111]",
                "[4308706380983828481, 4308706518422781951]",
                "[4308706518422781952, 4308706518422781952]",
                "[4308706518422781953, 4308706655861735423]",
                "[4308706655861735425, 4308706690221473791]",
                "[4308706690221473793, 4308706724581212159]",
                "[4308706724581212160, 4308706724581212160]",
                "[4308708992323944448, 4308708992323944448]",
                "[4308748574742544384, 4308748574742544384]",
                "[4308818943486722048, 4308818943486722048]",
                "[4309944843393564672, 4309944843393564672]"
              ]
            },
            "keysExamined": 0,
            "seeks": 1,
            "dupsTested": 0,
            "dupsDropped": 0,
            "peakTrackedMemBytes": 0
          }
        }
      }
    }
  },
  "queryShapeHash": "55D0FD63A7C29446608F39B035477755E86DCE46CA295864FC33F565763AEFAB",
  "command": {
    "find": "TelemetryPings",
    "filter": {
      "location": {
        "$near": {
          "$geometry": {
            "type": "Point",
            "coordinates": [
              78.4867,
              17.385
            ]
          },
          "$maxDistance": 3000
        }
      },
      "is_available": true
    },
    "$db": "ridesync_mongo"
  },
  "serverInfo": {
    "host": "DESKTOP-1QS0HPT",
    "port": 27017,
    "version": "8.3.8",
    "gitVersion": "35e8c8a57f78157ed9fac1a9e90ee6c1818adab6"
  },
  "serverParameters": {
    "internalQueryFacetBufferSizeBytes": 104857600,
    "internalDocumentSourceGroupMaxMemoryBytes": 104857600,
    "internalQueryMaxBlockingSortMemoryUsageBytes": 104857600,
    "internalDocumentSourceSetWindowFieldsMaxMemoryBytes": 104857600,
    "internalQueryFacetMaxOutputDocSizeBytes": 104857600,
    "internalLookupStageIntermediateDocumentMaxSizeBytes": 104857600,
    "internalQueryProhibitBlockingMergeOnMongoS": 0,
    "internalQueryMaxAddToSetBytes": 104857600,
    "internalQueryFrameworkControl": "trySbeRestricted",
    "internalQueryPlannerIgnoreIndexWithCollationForRegex": 1
  },
  "ok": 1
}

5. REVIEWS FOR VEHICLE 34AB2D1E-C17B-4981-883D-20CCD95D62AB

-- Key Metrics --
  Winning plan stage : COLLSCAN
  Index used         : COLLSCAN / none
  Keys examined      : 0
  Docs examined      : 28388
  Returned           : 3
  Execution time(ms) : 19

-- Full Explain Output (raw JSON) --
{
  "explainVersion": "1",
  "queryPlanner": {
    "namespace": "ridesync_mongo.TripReviews",
    "parsedQuery": {
      "vehicle_id": {
        "$eq": "34ab2d1e-c17b-4981-883d-20ccd95d62ab"
      }
    },
    "indexFilterSet": false,
    "queryHash": "43A638CF",
    "planCacheShapeHash": "43A638CF",
    "planCacheKey": "78C8A740",
    "optimizationTimeMillis": 0,
    "maxIndexedOrSolutionsReached": false,
    "maxIndexedAndSolutionsReached": false,
    "maxScansToExplodeReached": false,
    "prunedSimilarIndexes": false,
    "winningPlan": {
      "isCached": false,
      "stage": "COLLSCAN",
      "filter": {
        "vehicle_id": {
          "$eq": "34ab2d1e-c17b-4981-883d-20ccd95d62ab"
        }
      },
      "nss": "ridesync_mongo.TripReviews",
      "direction": "forward"
    },
    "rejectedPlans": []
  },
  "executionStats": {
    "executionSuccess": true,
    "nReturned": 3,
    "executionTimeMillis": 19,
    "totalKeysExamined": 0,
    "totalDocsExamined": 28388,
    "executionStages": {
      "isCached": false,
      "stage": "COLLSCAN",
      "filter": {
        "vehicle_id": {
          "$eq": "34ab2d1e-c17b-4981-883d-20ccd95d62ab"
        }
      },
      "nReturned": 3,
      "executionTimeMillisEstimate": 14,
      "works": 28389,
      "advanced": 3,
      "needTime": 28385,
      "needYield": 0,
      "saveState": 1,
      "restoreState": 1,
      "isEOF": 1,
      "nss": "ridesync_mongo.TripReviews",
      "direction": "forward",
      "docsExamined": 28388
    }
  },
  "queryShapeHash": "2A67B0E82CB924D06BF3ECE3F6E99D94DA564005D3932CEC9A83237E64049694",
  "command": {
    "find": "TripReviews",
    "filter": {
      "vehicle_id": "34ab2d1e-c17b-4981-883d-20ccd95d62ab"
    },
    "$db": "ridesync_mongo"
  },
  "serverInfo": {
    "host": "DESKTOP-1QS0HPT",
    "port": 27017,
    "version": "8.3.8",
    "gitVersion": "35e8c8a57f78157ed9fac1a9e90ee6c1818adab6"
  },
  "serverParameters": {
    "internalQueryFacetBufferSizeBytes": 104857600,
    "internalDocumentSourceGroupMaxMemoryBytes": 104857600,
    "internalQueryMaxBlockingSortMemoryUsageBytes": 104857600,
    "internalDocumentSourceSetWindowFieldsMaxMemoryBytes": 104857600,
    "internalQueryFacetMaxOutputDocSizeBytes": 104857600,
    "internalLookupStageIntermediateDocumentMaxSizeBytes": 104857600,
    "internalQueryProhibitBlockingMergeOnMongoS": 0,
    "internalQueryMaxAddToSetBytes": 104857600,
    "internalQueryFrameworkControl": "trySbeRestricted",
    "internalQueryPlannerIgnoreIndexWithCollationForRegex": 1
  },
  "ok": 1
}

6. HIGH RATED REVIEWS (RATING >= 4)

-- Key Metrics --
  Winning plan stage : COLLSCAN
  Index used         : COLLSCAN / none
  Keys examined      : 0
  Docs examined      : 28388
  Returned           : 22761
  Execution time(ms) : 20

-- Full Explain Output (raw JSON) --
{
  "explainVersion": "1",
  "queryPlanner": {
    "namespace": "ridesync_mongo.TripReviews",
    "parsedQuery": {
      "rating": {
        "$gte": 4
      }
    },
    "indexFilterSet": false,
    "queryHash": "29785460",
    "planCacheShapeHash": "29785460",
    "planCacheKey": "7C128AC9",
    "optimizationTimeMillis": 0,
    "maxIndexedOrSolutionsReached": false,
    "maxIndexedAndSolutionsReached": false,
    "maxScansToExplodeReached": false,
    "prunedSimilarIndexes": false,
    "winningPlan": {
      "isCached": false,
      "stage": "COLLSCAN",
      "filter": {
        "rating": {
          "$gte": 4
        }
      },
      "nss": "ridesync_mongo.TripReviews",
      "direction": "forward"
    },
    "rejectedPlans": []
  },
  "executionStats": {
    "executionSuccess": true,
    "nReturned": 22761,
    "executionTimeMillis": 20,
    "totalKeysExamined": 0,
    "totalDocsExamined": 28388,
    "executionStages": {
      "isCached": false,
      "stage": "COLLSCAN",
      "filter": {
        "rating": {
          "$gte": 4
        }
      },
      "nReturned": 22761,
      "executionTimeMillisEstimate": 13,
      "works": 28389,
      "advanced": 22761,
      "needTime": 5627,
      "needYield": 0,
      "saveState": 1,
      "restoreState": 1,
      "isEOF": 1,
      "nss": "ridesync_mongo.TripReviews",
      "direction": "forward",
      "docsExamined": 28388
    }
  },
  "queryShapeHash": "177FBDBC36A42C5B8D410EF6F4275FF9881140A08AF4D4E194DE35244D74EAB1",
  "command": {
    "find": "TripReviews",
    "filter": {
      "rating": {
        "$gte": 4
      }
    },
    "$db": "ridesync_mongo"
  },
  "serverInfo": {
    "host": "DESKTOP-1QS0HPT",
    "port": 27017,
    "version": "8.3.8",
    "gitVersion": "35e8c8a57f78157ed9fac1a9e90ee6c1818adab6"
  },
  "serverParameters": {
    "internalQueryFacetBufferSizeBytes": 104857600,
    "internalDocumentSourceGroupMaxMemoryBytes": 104857600,
    "internalQueryMaxBlockingSortMemoryUsageBytes": 104857600,
    "internalDocumentSourceSetWindowFieldsMaxMemoryBytes": 104857600,
    "internalQueryFacetMaxOutputDocSizeBytes": 104857600,
    "internalLookupStageIntermediateDocumentMaxSizeBytes": 104857600,
    "internalQueryProhibitBlockingMergeOnMongoS": 0,
    "internalQueryMaxAddToSetBytes": 104857600,
    "internalQueryFrameworkControl": "trySbeRestricted",
    "internalQueryPlannerIgnoreIndexWithCollationForRegex": 1
  },
  "ok": 1
}

7. REVIEW ANALYSIS ($FACET)

-- Key Metrics --
  Stage 1: $cursor
    Winning plan stage : PROJECTION_SIMPLE
    Index used         : COLLSCAN / none
    Keys examined      : 0
    Docs examined      : 28388
    Returned           : 28388
  Stage 2: $facet

-- Full Explain Output (raw JSON) --
{
  "explainVersion": "1",
  "stages": [
    {
      "$cursor": {
        "queryPlanner": {
          "namespace": "ridesync_mongo.TripReviews",
          "parsedQuery": {},
          "indexFilterSet": false,
          "queryHash": "ED189398",
          "planCacheShapeHash": "ED189398",
          "planCacheKey": "E0E0064F",
          "optimizationTimeMillis": 0,
          "cursorType": "regular",
          "maxIndexedOrSolutionsReached": false,
          "maxIndexedAndSolutionsReached": false,
          "maxScansToExplodeReached": false,
          "prunedSimilarIndexes": false,
          "winningPlan": {
            "isCached": false,
            "stage": "PROJECTION_SIMPLE",
            "transformBy": {
              "feedback_tags": 1,
              "rating": 1,
              "_id": 0
            },
            "inputStage": {
              "stage": "COLLSCAN",
              "nss": "ridesync_mongo.TripReviews",
              "direction": "forward"
            }
          },
          "rejectedPlans": []
        },
        "executionStats": {
          "executionSuccess": true,
          "nReturned": 28388,
          "executionTimeMillis": 123,
          "totalKeysExamined": 0,
          "totalDocsExamined": 28388,
          "executionStages": {
            "isCached": false,
            "stage": "PROJECTION_SIMPLE",
            "nReturned": 28388,
            "executionTimeMillisEstimate": 15,
            "works": 28389,
            "advanced": 28388,
            "needTime": 0,
            "needYield": 0,
            "saveState": 12,
            "restoreState": 11,
            "isEOF": 1,
            "transformBy": {
              "feedback_tags": 1,
              "rating": 1,
              "_id": 0
            },
            "inputStage": {
              "stage": "COLLSCAN",
              "nReturned": 28388,
              "executionTimeMillisEstimate": 15,
              "works": 28389,
              "advanced": 28388,
              "needTime": 0,
              "needYield": 0,
              "saveState": 12,
              "restoreState": 11,
              "isEOF": 1,
              "nss": "ridesync_mongo.TripReviews",
              "direction": "forward",
              "docsExamined": 28388
            }
          },
          "allPlansExecution": []
        }
      },
      "nReturned": {
        "high": 0,
        "low": 28388,
        "unsigned": false
      },
      "executionTimeMillisEstimate": {
        "high": 0,
        "low": 22,
        "unsigned": false
      }
    },
    {
      "$facet": {
        "ratingStats": [
          {
            "$internalFacetTeeConsumer": {},
            "nReturned": {
              "high": 0,
              "low": 28388,
              "unsigned": false
            },
            "executionTimeMillisEstimate": {
              "high": 0,
              "low": 32,
              "unsigned": false
            }
          },
          {
            "$group": {
              "_id": "$rating",
              "count": {
                "$sum": {
                  "$const": 1
                }
              },
              "$willBeMerged": false
            },
            "nReturned": {
              "high": 0,
              "low": 5,
              "unsigned": false
            },
            "executionTimeMillisEstimate": {
              "high": 0,
              "low": 42,
              "unsigned": false
            },
            "maxAccumulatorMemoryUsageBytes": {
              "count": {
                "high": 0,
                "low": 1120,
                "unsigned": false
              }
            },
            "totalOutputDataSizeBytes": {
              "high": 0,
              "low": 1185,
              "unsigned": false
            },
            "usedDisk": false,
            "spills": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledDataStorageSize": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledBytes": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledRecords": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "peakTrackedMemBytes": {
              "high": 0,
              "low": 1200,
              "unsigned": false
            }
          },
          {
            "$sort": {
              "sortKey": {
                "_id": 1
              }
            },
            "totalDataSizeSortedBytesEstimate": {
              "high": 0,
              "low": 1225,
              "unsigned": false
            },
            "usedDisk": false,
            "spills": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledBytes": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledRecords": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledDataStorageSize": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "nReturned": {
              "high": 0,
              "low": 5,
              "unsigned": false
            },
            "executionTimeMillisEstimate": {
              "high": 0,
              "low": 42,
              "unsigned": false
            },
            "peakTrackedMemBytes": {
              "high": 0,
              "low": 1225,
              "unsigned": false
            }
          }
        ],
        "averageRating": [
          {
            "$internalFacetTeeConsumer": {},
            "nReturned": {
              "high": 0,
              "low": 28388,
              "unsigned": false
            },
            "executionTimeMillisEstimate": {
              "high": 0,
              "low": 0,
              "unsigned": false
            }
          },
          {
            "$group": {
              "_id": {
                "$const": null
              },
              "avgRating": {
                "$avg": "$rating"
              },
              "totalReviews": {
                "$sum": {
                  "$const": 1
                }
              },
              "$willBeMerged": false
            },
            "nReturned": {
              "high": 0,
              "low": 1,
              "unsigned": false
            },
            "executionTimeMillisEstimate": {
              "high": 0,
              "low": 10,
              "unsigned": false
            },
            "maxAccumulatorMemoryUsageBytes": {
              "avgRating": {
                "high": 0,
                "low": 200,
                "unsigned": false
              },
              "totalReviews": {
                "high": 0,
                "low": 224,
                "unsigned": false
              }
            },
            "totalOutputDataSizeBytes": {
              "high": 0,
              "low": 269,
              "unsigned": false
            },
            "usedDisk": false,
            "spills": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledDataStorageSize": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledBytes": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledRecords": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "peakTrackedMemBytes": {
              "high": 0,
              "low": 440,
              "unsigned": false
            }
          },
          {
            "$project": {
              "totalReviews": true,
              "avgRating": {
                "$round": [
                  "$avgRating",
                  {
                    "$const": 2
                  }
                ]
              },
              "_id": false
            },
            "nReturned": {
              "high": 0,
              "low": 1,
              "unsigned": false
            },
            "executionTimeMillisEstimate": {
              "high": 0,
              "low": 10,
              "unsigned": false
            }
          }
        ],
        "topFeedbackTags": [
          {
            "$internalFacetTeeConsumer": {},
            "nReturned": {
              "high": 0,
              "low": 28388,
              "unsigned": false
            },
            "executionTimeMillisEstimate": {
              "high": 0,
              "low": 10,
              "unsigned": false
            }
          },
          {
            "$unwind": {
              "path": "$feedback_tags"
            },
            "nReturned": {
              "high": 0,
              "low": 56661,
              "unsigned": false
            },
            "executionTimeMillisEstimate": {
              "high": 0,
              "low": 32,
              "unsigned": false
            }
          },
          {
            "$group": {
              "_id": "$feedback_tags",
              "count": {
                "$sum": {
                  "$const": 1
                }
              },
              "$willBeMerged": false
            },
            "nReturned": {
              "high": 0,
              "low": 12,
              "unsigned": false
            },
            "executionTimeMillisEstimate": {
              "high": 0,
              "low": 63,
              "unsigned": false
            },
            "maxAccumulatorMemoryUsageBytes": {
              "count": {
                "high": 0,
                "low": 2688,
                "unsigned": false
              }
            },
            "totalOutputDataSizeBytes": {
              "high": 0,
              "low": 3035,
              "unsigned": false
            },
            "usedDisk": false,
            "spills": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledDataStorageSize": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledBytes": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledRecords": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "peakTrackedMemBytes": {
              "high": 0,
              "low": 3071,
              "unsigned": false
            }
          },
          {
            "$sort": {
              "sortKey": {
                "count": -1
              },
              "limit": {
                "high": 0,
                "low": 10,
                "unsigned": false
              }
            },
            "totalDataSizeSortedBytesEstimate": {
              "high": 0,
              "low": 2567,
              "unsigned": false
            },
            "usedDisk": false,
            "spills": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledBytes": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledRecords": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "spilledDataStorageSize": {
              "high": 0,
              "low": 0,
              "unsigned": false
            },
            "nReturned": {
              "high": 0,
              "low": 10,
              "unsigned": false
            },
            "executionTimeMillisEstimate": {
              "high": 0,
              "low": 63,
              "unsigned": false
            },
            "peakTrackedMemBytes": {
              "high": 0,
              "low": 2641,
              "unsigned": false
            }
          }
        ]
      },
      "nReturned": {
        "high": 0,
        "low": 1,
        "unsigned": false
      },
      "executionTimeMillisEstimate": {
        "high": 0,
        "low": 115,
        "unsigned": false
      }
    }
  ],
  "queryShapeHash": "3CBC7A67227EBF0DDAC69E1BC97D5E950E3056E1D1494D35D91066D24190416A",
  "serverInfo": {
    "host": "DESKTOP-1QS0HPT",
    "port": 27017,
    "version": "8.3.8",
    "gitVersion": "35e8c8a57f78157ed9fac1a9e90ee6c1818adab6"
  },
  "serverParameters": {
    "internalQueryFacetBufferSizeBytes": 104857600,
    "internalDocumentSourceGroupMaxMemoryBytes": 104857600,
    "internalQueryMaxBlockingSortMemoryUsageBytes": 104857600,
    "internalDocumentSourceSetWindowFieldsMaxMemoryBytes": 104857600,
    "internalQueryFacetMaxOutputDocSizeBytes": 104857600,
    "internalLookupStageIntermediateDocumentMaxSizeBytes": 104857600,
    "internalQueryProhibitBlockingMergeOnMongoS": 0,
    "internalQueryMaxAddToSetBytes": 104857600,
    "internalQueryFrameworkControl": "trySbeRestricted",
    "internalQueryPlannerIgnoreIndexWithCollationForRegex": 1
  },
  "command": {
    "aggregate": "TripReviews",
    "pipeline": [
      {
        "$facet": {
          "ratingStats": [
            {
              "$group": {
                "_id": "$rating",
                "count": {
                  "$sum": 1
                }
              }
            },
            {
              "$sort": {
                "_id": 1
              }
            }
          ],
          "averageRating": [
            {
              "$group": {
                "_id": null,
                "avgRating": {
                  "$avg": "$rating"
                },
                "totalReviews": {
                  "$sum": 1
                }
              }
            },
            {
              "$project": {
                "_id": 0,
                "avgRating": {
                  "$round": [
                    "$avgRating",
                    2
                  ]
                },
                "totalReviews": 1
              }
            }
          ],
          "topFeedbackTags": [
            {
              "$unwind": "$feedback_tags"
            },
            {
              "$group": {
                "_id": "$feedback_tags",
                "count": {
                  "$sum": 1
                }
              }
            },
            {
              "$sort": {
                "count": -1
              }
            },
            {
              "$limit": 10
            }
          ]
        }
      }
    ],
    "cursor": {},
    "$db": "ridesync_mongo"
  },
  "ok": 1
}

8. VEHICLE METADATA FOR 550E8400-E29B-41D4-A716-446655440001

-- Key Metrics --
  Winning plan stage : COLLSCAN
  Index used         : COLLSCAN / none
  Keys examined      : 0
  Docs examined      : 80002
  Returned           : 1
  Execution time(ms) : 71

-- Full Explain Output (raw JSON) --
{
  "explainVersion": "1",
  "queryPlanner": {
    "namespace": "ridesync_mongo.VehicleMetadata",
    "parsedQuery": {
      "vehicle_id": {
        "$eq": "550e8400-e29b-41d4-a716-446655440001"
      }
    },
    "indexFilterSet": false,
    "queryHash": "43A638CF",
    "planCacheShapeHash": "43A638CF",
    "planCacheKey": "78C8A740",
    "optimizationTimeMillis": 0,
    "maxIndexedOrSolutionsReached": false,
    "maxIndexedAndSolutionsReached": false,
    "maxScansToExplodeReached": false,
    "prunedSimilarIndexes": false,
    "winningPlan": {
      "isCached": true,
      "stage": "COLLSCAN",
      "filter": {
        "vehicle_id": {
          "$eq": "550e8400-e29b-41d4-a716-446655440001"
        }
      },
      "nss": "ridesync_mongo.VehicleMetadata",
      "direction": "forward"
    },
    "rejectedPlans": []
  },
  "executionStats": {
    "executionSuccess": true,
    "nReturned": 1,
    "executionTimeMillis": 71,
    "totalKeysExamined": 0,
    "totalDocsExamined": 80002,
    "executionStages": {
      "isCached": true,
      "stage": "COLLSCAN",
      "filter": {
        "vehicle_id": {
          "$eq": "550e8400-e29b-41d4-a716-446655440001"
        }
      },
      "nReturned": 1,
      "executionTimeMillisEstimate": 57,
      "works": 80003,
      "advanced": 1,
      "needTime": 80001,
      "needYield": 0,
      "saveState": 4,
      "restoreState": 4,
      "isEOF": 1,
      "nss": "ridesync_mongo.VehicleMetadata",
      "direction": "forward",
      "docsExamined": 80002
    }
  },
  "queryShapeHash": "C64F12ED696686BCA01E084862181C8D163B503372BC9DB77C7FD8F9D3A16425",
  "command": {
    "find": "VehicleMetadata",
    "filter": {
      "vehicle_id": "550e8400-e29b-41d4-a716-446655440001"
    },
    "$db": "ridesync_mongo"
  },
  "serverInfo": {
    "host": "DESKTOP-1QS0HPT",
    "port": 27017,
    "version": "8.3.8",
    "gitVersion": "35e8c8a57f78157ed9fac1a9e90ee6c1818adab6"
  },
  "serverParameters": {
    "internalQueryFacetBufferSizeBytes": 104857600,
    "internalDocumentSourceGroupMaxMemoryBytes": 104857600,
    "internalQueryMaxBlockingSortMemoryUsageBytes": 104857600,
    "internalDocumentSourceSetWindowFieldsMaxMemoryBytes": 104857600,
    "internalQueryFacetMaxOutputDocSizeBytes": 104857600,
    "internalLookupStageIntermediateDocumentMaxSizeBytes": 104857600,
    "internalQueryProhibitBlockingMergeOnMongoS": 0,
    "internalQueryMaxAddToSetBytes": 104857600,
    "internalQueryFrameworkControl": "trySbeRestricted",
    "internalQueryPlannerIgnoreIndexWithCollationForRegex": 1
  },
  "ok": 1
}

8B. TOP RATED VEHICLES + METADATA (LOOKUP AFTER LIMIT)

-- Key Metrics --
  Stage 1: $cursor
    Index used         : COLLSCAN / none
    Keys examined      : 0
    Docs examined      : 28388
    Returned           : 20323
  Stage 2: $sort
  Stage 3: $lookup
  Stage 4: $project

-- Full Explain Output (raw JSON) --
{
  "explainVersion": "2",
  "stages": [
    {
      "$cursor": {
        "queryPlanner": {
          "namespace": "ridesync_mongo.TripReviews",
          "parsedQuery": {},
          "indexFilterSet": false,
          "queryHash": "1276CD45",
          "planCacheShapeHash": "1276CD45",
          "planCacheKey": "F7CF6913",
          "optimizationTimeMillis": 0,
          "cursorType": "regular",
          "maxIndexedOrSolutionsReached": false,
          "maxIndexedAndSolutionsReached": false,
          "maxScansToExplodeReached": false,
          "prunedSimilarIndexes": false,
          "winningPlan": {
            "isCached": false,
            "queryPlan": {
              "stage": "GROUP",
              "planNodeId": 3,
              "inputStage": {
                "stage": "COLLSCAN",
                "planNodeId": 1,
                "filter": {},
                "nss": "ridesync_mongo.TripReviews",
                "direction": "forward"
              }
            },
            "slotBasedPlan": {
              "slots": "$$RESULT=s10 env: {  }",
              "stages": "[3] project [s10 = newObj(\"_id\", s9, \"avgRating\", s5, \"reviewCount\", s7)] \n[3] group [s9] [s5 = _internalArithmeticAverage::accumulate(s5, s3), s7 = _internalCount::accumulate(s7, 1)] spillSlots[s6, s8] mergingExprs[_internalArithmeticAverage::merge(s6), _internalCount::merge(s8)] \n[3] project [s9 = (s4 ?: null)] \n[1] scan generic [s1 = record, s2 = recordId] [s3 = rating, s4 = vehicle_id] @\"721cc157-abd4-4a7c-b330-40efc29a63b3\" "
            }
          },
          "rejectedPlans": []
        },
        "executionStats": {
          "executionSuccess": true,
          "nReturned": 20323,
          "executionTimeMillis": 749,
          "totalKeysExamined": 0,
          "totalDocsExamined": 28388,
          "executionStages": {
            "stage": "project",
            "planNodeId": 3,
            "nReturned": 20323,
            "executionTimeMillisEstimate": 72,
            "opens": 1,
            "closes": 1,
            "saveState": 17,
            "restoreState": 16,
            "isEOF": 1,
            "projections": {
              "10": "newObj(\"_id\", s9, \"avgRating\", s5, \"reviewCount\", s7) "
            },
            "inputStage": {
              "stage": "group",
              "planNodeId": 3,
              "nReturned": 20323,
              "executionTimeMillisEstimate": 44,
              "opens": 1,
              "closes": 1,
              "saveState": 17,
              "restoreState": 16,
              "isEOF": 1,
              "groupBySlots": [
                {
                  "high": 0,
                  "low": 9,
                  "unsigned": false
                }
              ],
              "expressions": {
                "5": "_internalArithmeticAverage::accumulate(s5, s3) ",
                "7": "_internalCount::accumulate(s7, 1) ",
                "initExprs": {
                  "5": null,
                  "7": null,
                  "mergingExprs": {
                    "6": "_internalArithmeticAverage::merge(s6) ",
                    "8": "_internalCount::merge(s8) "
                  }
                }
              },
              "usedDisk": false,
              "spills": 0,
              "spilledBytes": 0,
              "spilledRecords": 0,
              "spilledDataStorageSize": 0,
              "peakTrackedMemBytes": 3851315,
              "inputStage": {
                "stage": "project",
                "planNodeId": 3,
                "nReturned": 28388,
                "executionTimeMillisEstimate": 4,
                "opens": 1,
                "closes": 1,
                "saveState": 17,
                "restoreState": 16,
                "isEOF": 1,
                "projections": {
                  "9": "(s4 ?: null) "
                },
                "inputStage": {
                  "stage": "scan",
                  "planNodeId": 1,
                  "nReturned": 28388,
                  "executionTimeMillisEstimate": 4,
                  "opens": 1,
                  "closes": 1,
                  "saveState": 17,
                  "restoreState": 16,
                  "isEOF": 1,
                  "numReads": 28388,
                  "recordSlot": 1,
                  "recordIdSlot": 2,
                  "scanFieldNames": [
                    "rating",
                    "vehicle_id"
                  ],
                  "scanFieldSlots": [
                    {
                      "high": 0,
                      "low": 3,
                      "unsigned": false
                    },
                    {
                      "high": 0,
                      "low": 4,
                      "unsigned": false
                    }
                  ]
                }
              }
            }
          },
          "allPlansExecution": []
        }
      },
      "nReturned": {
        "high": 0,
        "low": 20323,
        "unsigned": false
      },
      "executionTimeMillisEstimate": {
        "high": 0,
        "low": 94,
        "unsigned": false
      }
    },
    {
      "$sort": {
        "sortKey": {
          "avgRating": -1
        },
        "limit": {
          "high": 0,
          "low": 10,
          "unsigned": false
        }
      },
      "totalDataSizeSortedBytesEstimate": {
        "high": 0,
        "low": 4330,
        "unsigned": false
      },
      "usedDisk": false,
      "spills": {
        "high": 0,
        "low": 0,
        "unsigned": false
      },
      "spilledBytes": {
        "high": 0,
        "low": 0,
        "unsigned": false
      },
      "spilledRecords": {
        "high": 0,
        "low": 0,
        "unsigned": false
      },
      "spilledDataStorageSize": {
        "high": 0,
        "low": 0,
        "unsigned": false
      },
      "nReturned": {
        "high": 0,
        "low": 10,
        "unsigned": false
      },
      "executionTimeMillisEstimate": {
        "high": 0,
        "low": 108,
        "unsigned": false
      },
      "peakTrackedMemBytes": {
        "high": 0,
        "low": 4330,
        "unsigned": false
      }
    },
    {
      "$lookup": {
        "from": "VehicleMetadata",
        "as": "metadata",
        "localField": "_id",
        "foreignField": "vehicle_id",
        "unwinding": {
          "preserveNullAndEmptyArrays": false
        }
      },
      "nReturned": {
        "high": 0,
        "low": 10,
        "unsigned": false
      },
      "executionTimeMillisEstimate": {
        "high": 0,
        "low": 749,
        "unsigned": false
      },
      "totalDocsExamined": {
        "high": 0,
        "low": 800020,
        "unsigned": false
      },
      "totalKeysExamined": {
        "high": 0,
        "low": 0,
        "unsigned": false
      },
      "collectionScans": {
        "high": 0,
        "low": 10,
        "unsigned": false
      },
      "indexesUsed": []
    },
    {
      "$project": {
        "_id": true,
        "reviewCount": true,
        "avgRating": {
          "$round": [
            "$avgRating",
            {
              "$const": 2
            }
          ]
        },
        "features": "$metadata.features",
        "lastInspection": {
          "$max": [
            "$metadata.inspection_records.date"
          ]
        }
      },
      "nReturned": {
        "high": 0,
        "low": 10,
        "unsigned": false
      },
      "executionTimeMillisEstimate": {
        "high": 0,
        "low": 749,
        "unsigned": false
      }
    }
  ],
  "queryShapeHash": "85D3E25E9FF90875EBE98CC739E7B7AA5B9B63D5EA40335A884EF29B832B0C1C",
  "peakTrackedMemBytes": {
    "high": 0,
    "low": 3851315,
    "unsigned": false
  },
  "serverInfo": {
    "host": "DESKTOP-1QS0HPT",
    "port": 27017,
    "version": "8.3.8",
    "gitVersion": "35e8c8a57f78157ed9fac1a9e90ee6c1818adab6"
  },
  "serverParameters": {
    "internalQueryFacetBufferSizeBytes": 104857600,
    "internalDocumentSourceGroupMaxMemoryBytes": 104857600,
    "internalQueryMaxBlockingSortMemoryUsageBytes": 104857600,
    "internalDocumentSourceSetWindowFieldsMaxMemoryBytes": 104857600,
    "internalQueryFacetMaxOutputDocSizeBytes": 104857600,
    "internalLookupStageIntermediateDocumentMaxSizeBytes": 104857600,
    "internalQueryProhibitBlockingMergeOnMongoS": 0,
    "internalQueryMaxAddToSetBytes": 104857600,
    "internalQueryFrameworkControl": "trySbeRestricted",
    "internalQueryPlannerIgnoreIndexWithCollationForRegex": 1
  },
  "command": {
    "aggregate": "TripReviews",
    "pipeline": [
      {
        "$group": {
          "_id": "$vehicle_id",
          "avgRating": {
            "$avg": "$rating"
          },
          "reviewCount": {
            "$sum": 1
          }
        }
      },
      {
        "$sort": {
          "avgRating": -1
        }
      },
      {
        "$limit": 10
      },
      {
        "$lookup": {
          "from": "VehicleMetadata",
          "localField": "_id",
          "foreignField": "vehicle_id",
          "as": "metadata"
        }
      },
      {
        "$unwind": "$metadata"
      },
      {
        "$project": {
          "_id": 1,
          "avgRating": {
            "$round": [
              "$avgRating",
              2
            ]
          },
          "reviewCount": 1,
          "features": "$metadata.features",
          "lastInspection": {
            "$max": "$metadata.inspection_records.date"
          }
        }
      }
    ],
    "cursor": {},
    "$db": "ridesync_mongo"
  },
  "ok": 1
}

############################################################
END OF EXPLAIN STATS
############################################################

LAST COMMIT HASH:
61449f3fca545f7e0fe0b0a5a24897a2dbcd108f


## Team 10 design step

The [design plan](docs/design/README.md) records users, required screens, shared styles, phone layouts and changes from the Figma prototype. Open [the six wireframes](docs/design/wireframes.html) in a browser. The [API plan](docs/api_endpoints.md) now includes planned inputs, outputs and errors. These are design documents. The first API step now works; the web app is still pending.

Demo assumptions: INR, Asia/Kolkata date filters, a user-entered booking fare, a selectable demo rider, and a two-hour telemetry freshness limit matching the inherited expiry. Routes and real login are outside this step. Exact booking audit IDs are now implemented. Calendar-day revenue averages and persisted refresh times are still planned. The original team's commit history is preserved.
