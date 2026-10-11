# Team 10 handover note — 11 October 2026

Inherited repository: https://github.com/amaan070/Ride_Booking_21
Baseline commit: `d0d5ad44ba4ab2f566cd965e055870ddd7e95697` (23 inherited commits).
Team fork: https://github.com/Atharvojha/Ride_Booking_21

## What worked

All six SQL scripts executed on PostgreSQL 17.11. The original seeders, pointed at isolated databases and reduced to 100 riders, 40 vehicles, 100 trip attempts and 1,000 telemetry pings, produced 94 completed trips and 62 reviews. These are smoke-test figures, not scale or performance evidence.

The booking procedure deducted the fare and fired the wallet audit trigger. Insufficient funds and a second active trip returned failure without changing the wallet or adding an audit entry. Progressing a trip through REQUESTED → IN TRANSIT → COMPLETED released the rider for a new booking. The moving-average/ranking view returned rows, and refreshing the materialized view populated it. The Mongo review facet, geospatial index and two-hour telemetry TTL worked.

## What failed and what changed

1. The nearby-search file mixed `export` syntax with Mongo shell code and redeclared `db` using itself. It failed under the documented mongosh execution method. Converted it to a runnable shell function and added a Hyderabad demo call using configurable coordinates. It still returns one nearest ping; a list of distinct vehicles and latest-ping semantics belong in the API/map stage.
2. The metadata lookup index targeted `vehicleMetadata`, while records were stored in `VehicleMetadata`. Corrected the collection name and made collection creation safe to repeat. Existing accidentally created lowercase collections are not removed.
3. One seeder embedded a connection password; the other prompted during import. Both now use environment variables, optionally loaded from a git-ignored `.env`. Dataset sizes are configurable, and `.env.example` contains no secret.
4. The PostgreSQL seeder added wallet top-ups only to its Python balance cache. It now updates the database wallet first, allowing the existing trigger to record the credit. A targeted check verified a 10 balance + 500 credit − 100 fare = 410 balance, with both credit and booking audited.
5. The README referred to an ERD PNG that is actually a JPEG. Corrected that path and added current Team 10 setup instructions while retaining the original documentation for attribution.

## Verification and remaining issues

After these changes, 27 backend checks passed; see `docs/backend_verification.json` and `tests/backend_smoke.py`. Tests create new isolated database names and retain them for inspection. No existing database was reset.

The materialized view must be refreshed after seeding. Its refresh time is not stored by the inherited schema; the API must persist the last successful refresh time. The revenue query currently averages seven nonempty revenue rows, not necessarily seven calendar days. Decide and document the required calendar-day behavior before chart integration. Procedures commit/roll back internally, so call them at the top level with autocommit rather than inside an API-managed transaction. Completion failures currently return notices, so verify the resulting state rather than assuming success.

Trip statuses are only REQUESTED, IN TRANSIT and COMPLETED. Route fields, cancellation, real authentication and a currency definition are absent. Record these design assumptions before implementing the Figma screens. Large-dataset tests, concurrent booking tests, frontend/API implementation and final packaging are still pending.

## Suggestions for the original authors

Provide environment-based configuration, portable setup commands, executable workflow examples and explicit seeding/refresh ordering. Document the moving-average definition, notice-based completion errors, ping freshness semantics and procedure transaction requirements. Add reproducible failure-case checks alongside the generated happy-path dataset.
