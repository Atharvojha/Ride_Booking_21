# Viva notes — every member should be able to explain all of this

Any member may be asked about any part. Read the file named in each section while you read the notes. The words "inherited" and "ours" mean the Assignment 1 team's work and Team 10's work.

## The big picture

RideSync keeps two kinds of data in two databases.

- **PostgreSQL** holds money and trips: riders, vehicles, trips and the wallet audit log. These need strict rules (a wallet can never go below zero), so we use a relational database with transactions.
- **MongoDB** holds data that is flexible or very frequent: vehicle metadata (a different shape per vehicle), GPS pings (millions of small records that expire), and trip reviews. A vehicle is linked across the two databases by its UUID, stored as text in Mongo.

Our API (FastAPI) sits between the web app and the databases. The web app (React) never calculates money or ranks. It shows what the database returned.

## PostgreSQL (inherited), file by file

### Tables — `sql/01_schema_ddl.sql`
- `riders` has `wallet_balance` with a CHECK that it is never negative. This single rule is what turns "not enough money" into a database error.
- `vehicles` has a unique `license_plate` and an `is_active` flag.
- `trips` has `status` limited by a CHECK to REQUESTED, IN TRANSIT or COMPLETED, and foreign keys to a rider and a vehicle.
- `wallet_audit_logs` records every wallet change: the amount, the action type (CREDIT, ESCROW_HOLD, ESCROW_RELEASE, DEBIT) and the balance after the change.

### Indexes — `sql/02_indexes.sql`
- Normal indexes on `trips(rider_id)`, `trips(vehicle_id)` and `wallet_audit_logs(rider_id)` make "this rider's trips" and "this rider's history" fast.
- **Partial unique index** `idx_one_active_trip_per_rider` is `UNIQUE (rider_id) WHERE status IN ('REQUESTED','IN TRANSIT')`. It only indexes active trips, so a rider can have at most one active trip but any number of completed ones. The database enforces this even if two requests arrive at the same moment. We do not rely on application code.

### Trigger — `sql/03_triggers_and_audit.sql`
A trigger is code the database runs by itself when data changes. `trg_wallet_audit` runs after any change to `riders.wallet_balance` (only when the value really changed). It writes one audit row with the difference and the new balance. It reads the action name (for example ESCROW_HOLD) from a session setting that the procedure sets, and defaults to CREDIT or DEBIT. It also stores the new audit row's ID in a setting, so the booking procedure can return the exact row. We never guess "the latest row".

### Stored procedures and transactions — `sql/04_stored_procedures.sql`
A transaction is a group of changes that either all happen or none do.

`sp_book_trip(rider, vehicle, fare)`:
1. Checks the fare (positive, at most two decimals, at most 99,999,999.99).
2. Reads the vehicle with `FOR SHARE`, a lock that stops someone from deactivating it while this booking finishes. Refuses inactive vehicles.
3. Subtracts the fare from the wallet. The trigger writes the ESCROW_HOLD audit row. If the balance would go below zero, the CHECK fails and we report INSUFFICIENT_BALANCE.
4. Inserts the trip as REQUESTED. If the rider already has an active trip, the partial unique index fails and we report ACTIVE_TRIP_EXISTS.
5. On any failure it rolls back, so no money moves and no audit row is left. Otherwise it commits and returns the trip ID, the status and the audit ID.

"Escrow" means the fare is held (taken from the wallet) when the trip is booked, and released when it completes.

`sp_release_escrow(trip)` marks an IN TRANSIT trip COMPLETED and adds a zero-amount ESCROW_RELEASE row. It does **not** refund the fare. The money was already spent. On failure it only prints a notice, so the API checks the saved state instead of assuming success.

**Why a procedure and not a function?** A procedure may commit or roll back by itself. Because of that, the API calls it with `CALL` on a connection with no outer transaction. Wrapping it in another transaction would break this.

**Lock order.** Booking changes the rider's wallet before it inserts the trip. Completion locks the rider's wallet (`FOR UPDATE`) before it changes the trip. Both take the rider first and the trip second. When all code takes locks in the same order, two requests cannot wait for each other forever (a deadlock). Locking the wallet first in completion was our change, so that a wallet top-up at the same moment cannot put audit rows in the wrong order.

### Window function and ranks — `sql/06_window_analytics.sql` (inherited) and `sql/08_api_revenue.sql` (ours)
- A **window function** calculates across related rows without collapsing them into one row. `AVG(...) OVER (PARTITION BY vehicle ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)` is a moving average: for each vehicle and day it averages that day and the 6 before it.
- The inherited view only has rows for days that had completed trips, so "6 preceding rows" could reach back many weeks. Ours is a **calendar** window: we first build one row for every vehicle and every day (`generate_series` of dates cross-joined with vehicles, then a left join to revenue), with 0 for days without trips. Six extra days before the chosen start give the first day a full window. Days are Asia/Kolkata days.
- `DENSE_RANK() OVER (PARTITION BY day ORDER BY average DESC)` ranks vehicles on each day. Equal averages get the same rank, and the next rank is not skipped (`RANK` would skip: 1, 1, 3). We rank the whole fleet first and filter to one vehicle afterwards, so a single vehicle keeps its true fleet rank.

### Materialized view — `sql/05_materialized_views.sql`, `sql/07_api_refresh_state.sql`
A normal view re-runs its query each time. A **materialized view** stores the result like a table, so reading it is fast, but it goes stale until refreshed. `mv_vehicle_lifetime_stats` stores each vehicle's trip count and earnings. `REFRESH ... CONCURRENTLY` rebuilds it without blocking readers; it needs the unique index on `vehicle_id`. Ours: the refresh function saves the time in `api_refresh_state` only after the refresh succeeds, and an advisory lock (a named lock the application chooses) stops two refreshes running at once. If a refresh fails, the old data and old time stay.

## MongoDB

### Collections and indexes — `mongo/01_collections_and_indexes.js`, `mongo/04_api_indexes.js`
- `TelemetryPings`: `{vehicle_id, is_available, location, created_at}`. The location is **GeoJSON**: `{type: "Point", coordinates: [longitude, latitude]}`. Mongo puts longitude first. The map library (Leaflet) wants latitude first, so the frontend swaps them.
- A **2dsphere index** on `location` lets Mongo find points near a position.
- A **TTL index** on `created_at` with `expireAfterSeconds: 7200` deletes each ping about two hours after its `created_at`. A background task checks about once a minute, so removal is not instant. That is why a demo database's map goes empty and why we have a script that adds fresh pings.
- Our compound index `{vehicle_id, created_at: -1, _id: -1}` finds one vehicle's newest ping quickly.

### `$geoNear` — `mongo/02_workflow_geonear.js`
`$geoNear` must be the first stage of an aggregation. It uses the 2dsphere index, returns documents sorted by distance and adds the distance. `maxDistance` is in metres and `spherical: true` uses the curved earth. Its `query` option filters while searching.

### The latest-ping rule (ours) — `api/nearby.py`
A vehicle sends many pings. Only its newest ping says where it is now and whether it is available. Without this rule, a vehicle that was available an hour ago but has since gone unavailable (or driven away) would still show on the map. So: `$geoNear` finds candidate pings, then `$lookup` fetches each vehicle's newest ping (by `created_at`, then `_id` to break ties), and we keep a candidate only if it **is** that newest ping. Then we remove vehicles that are inactive or missing in PostgreSQL, and only then apply the result limit. At full size, 27,713 candidate pings came from 4,162 vehicles, and only 1,967 passed. Note that `is_active` (the fleet record in PostgreSQL) and `is_available` (a ping) are different things.

### `$facet` — `mongo/03_workflow4_facet.js`, `api/reviews.py`
`$facet` runs several sub-pipelines on the same input documents in one pass. The review summary uses it to get rating counts, the average and the top feedback tags together. We put `$match` (the vehicle and date filters) before `$facet`, so the summary only covers the chosen reviews. With no reviews, there is no average (not "0").

## Our API and the choices behind it
- **FastAPI** is small, validates input and documents itself at `/docs`. **psycopg2** and **PyMongo** are the standard drivers.
- Money travels as text such as `"120.00"`, never as a floating-point number, so there are no rounding errors. The web app counts whole paise (hundredths of a rupee).
- Read requests use one read-only `REPEATABLE READ` snapshot, so a page's counts, rows and balances agree. Write requests use a connection with autocommit, so the procedures own their transactions.
- Limits: PostgreSQL 10 s statement timeout, 5 s lock timeout, MongoDB 5 s aggregation limit. They stop a slow request from piling up work.
- Everything is filtered and paged in the database, at most 100 rows per page.
- `docs/api_endpoints.md` lists every request, input, output and error.

## Our web app
- React with Vite and plain CSS. Leaflet draws the map with OpenStreetMap tiles. The attribution must stay visible and we do not download tiles in bulk. The charts are small SVG/CSS.
- A booking button is disabled while the request is running. If the reply is lost, we do not guess: we wait, then read the rider's trips and wallet, and only then let the user continue. We never send a second booking automatically.
- The map refreshes every 10 seconds only while the page is visible, and never overlaps requests.
- Header "demo rider" switching is not a login.

## What we measured at full size
See [scale_verification.md](scale_verification.md). The shortest version: 100,000 riders, 40,000 vehicles, 50,000 trips and 520,000 pings; 75 checks passed; most requests took about 0.4 s or less, Nearby about 1.3 s, and the revenue screen needed a fix (90 days went from 10.6 s to 4.1 s). The 90-day chart is still the slowest part because every vehicle must be ranked for every day.

## Questions to practise
1. Why can't a rider have two active trips, and where is that rule enforced?
2. What happens, step by step, when a rider with too little money books a trip?
3. Why does `sp_book_trip` use `COMMIT` and `ROLLBACK`, and what does that mean for how the API calls it?
4. Why does completion not refund the fare?
5. Which lock is taken first in booking and in completion, and why does the order matter?
6. What is the difference between `RANK` and `DENSE_RANK`? Why do many vehicles share a rank?
7. What is wrong with averaging "the last 7 rows" for a 7-day average? How do we fix it?
8. Why is a materialized view fast but possibly out of date? What does `CONCURRENTLY` need?
9. Which comes first in a `$geoNear` pipeline and why? Why longitude first?
10. Why does a TTL index not remove documents at exactly two hours?
11. Why do we check each vehicle's newest ping, and what does the demo show if we skip that?
12. What does `$facet` do, and why is `$match` placed before it?
13. Why is the revenue chart the slowest request, and what would you build to make it faster?
14. Which parts of the Figma prototype could we not build from the database, and why?
