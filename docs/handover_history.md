# Team 10 handover note — 11 October 2026

Inherited repository: https://github.com/amaan070/Ride_Booking_21
Starting commit: `d0d5ad44ba4ab2f566cd965e055870ddd7e95697` (23 inherited commits).
Team fork: https://github.com/Atharvojha/Ride_Booking_21

## What worked

All six SQL scripts executed on PostgreSQL 17.11. The original seeders, pointed at isolated databases and reduced to 100 riders, 40 vehicles, 100 trip attempts and 1,000 telemetry pings, produced 94 completed trips and 62 reviews. This was a small test. We have not tested the full dataset yet.

The booking procedure deducted the fare and fired the wallet audit trigger. Insufficient funds and a second active trip returned failure without changing the wallet or adding an audit entry. Progressing a trip through REQUESTED → IN TRANSIT → COMPLETED released the rider for a new booking. The moving-average/ranking view returned rows, and refreshing the materialized view populated it. The Mongo review facet, geospatial index and two-hour telemetry TTL worked.

## What failed and what changed

1. The nearby-search file mixed `export` syntax with Mongo shell code and redeclared `db` using itself. It failed under the documented mongosh execution method. Converted it to a runnable shell function and added a Hyderabad demo call using configurable coordinates. It still returns one nearest ping; we will add a vehicle list and decide which location updates to show when building the map.
2. The metadata lookup index targeted `vehicleMetadata`, while records were stored in `VehicleMetadata`. Corrected the collection name and made collection creation safe to repeat. Existing accidentally created lowercase collections are not removed.
3. One seeder embedded a connection password; the other prompted during import. Both now use environment variables, optionally loaded from a git-ignored `.env`. Dataset sizes are configurable, and `.env.example` contains no secret.
4. The PostgreSQL seeder added wallet top-ups only to its Python balance cache. It now updates the database wallet first, allowing the existing trigger to record the credit. A targeted check verified a 10 balance + 500 credit − 100 fare = 410 balance, with both credit and booking audited.
5. The README referred to an ERD PNG that is actually a JPEG. Corrected that path and added current Team 10 setup instructions while retaining the original documentation for attribution.

## Verification and remaining issues

After these changes, 27 backend checks passed; see `docs/backend_verification.json` and `tests/backend_smoke.py`. Tests create new isolated database names and retain them for inspection. No existing database was reset.

Refresh the materialized view after adding sample data. The database does not save when it was last refreshed, so we need to add this when building the API. The revenue query currently averages seven nonempty revenue rows, not necessarily seven calendar days. Decide how days with no trips should be counted before building the chart. The procedures finish or undo their own database transactions. Call them directly from the API without wrapping them in another transaction. Completion failures currently return notices, so verify the resulting state rather than assuming success.

Trip statuses are only REQUESTED, IN TRANSIT and COMPLETED. Route fields, cancellation, real authentication and a currency definition are absent. Record these design assumptions before implementing the Figma screens. We still need to test the full dataset and bookings made at the same time, build the frontend and API, and prepare the submission.

## Suggestions for the original authors

Use a configuration file for connection settings and give clear setup steps. Show the order for adding data and refreshing views. Explain how the moving average works, how completion errors are returned, and which vehicle location updates count as current. Include tests for failures as well as successful bookings.


## First API step — 11 October 2026

Added browsing, booking, trip status and wallet-audit routes. Vehicle details also read MongoDB metadata. Analytics, nearby search, review summaries and web screens remain pending.

The booking procedure now checks fare limits and active vehicles, returns the exact audit row created by the wallet trigger, and keeps failed bookings from changing the wallet. This adds a third output argument; seed scripts and tests were updated. The seeder chooses active vehicles for trips. The earlier seeded counts in this note describe the original audit run; the independent small regression run produced 95 completed trips and 63 reviews. The separate demo seed produced 97 completed trips and 56 reviews.

Audit timestamps now use the actual write time. Completion locks the rider's wallet before changing the trip, using the same lock order as booking. This keeps its zero-change release entry in the right order when a top-up happens at the same time.

Checked 36 API cases and reran all 27 backend checks successfully. An independent verifier ran both suites and extra direct database and concurrency checks. The API test client gives one dependency warning. Large dataset and browser UI checks remain pending. See api_verification.json for this step's results and api/README.md for setup.


## Remaining API workflows — 11 October 2026

Added analytics, nearby vehicles and review routes. SQL 08 extends the inherited revenue window query with zero-revenue calendar days, six earlier days of history and whole-fleet ranks. The original view remains for attribution. SQL 07 saves the successful materialized-view refresh time inside the refresh function; a shared database lock prevents overlapping refreshes. A failed refresh keeps the earlier time and results.

Nearby search uses geoNear and checks every candidate against its vehicle's latest ping, including newer unavailable or distant positions. It ignores future and expired pings, gets active vehicle labels from SQL, and limits only the valid results. Mongo 04 adds lookup and review indexes. Review filters run before facets and pagination. Empty review summaries return no average rating and zero counts.

All 60 API tests and 29 backend checks passed in VS Code and in the independent verification run. The backend total now includes setup checks for SQL 07 and 08; the earlier 27-check report remains historical. The verifier also checked database calculations and a small Mongo query plan independently. No full-scale performance result is claimed.

The local demo passed six live read routes and a summary refresh. Existing SQL record counts stayed unchanged when the additions were applied. The original telemetry had expired, so the live nearby response was empty; isolated tests used fresh pings. The frontend, browser tests, large dataset checks, demo recording and submission package remain pending.
