# RideSync API setup

Run commands from the repository root in VS Code's terminal. Use Python 3.11 or newer. PostgreSQL and MongoDB must already be running; follow the main README for database setup and seed data.

~~~sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt -r data_generation/requirements.txt
~~~

The first file pins server and test packages. The second includes Faker for seed data and the existing backend checks. Copy .env.example to .env if needed, then fill in your local settings. The API reads .env automatically. Keep credentials out of Git.

For an already-seeded database, follow the main README commands for SQL 03, 04, 07 and 08, then mongo/04_api_indexes.js. They can be applied again without resetting data. Do not rerun table creation or materialized-view creation on that database.

~~~sh
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
~~~

Open http://127.0.0.1:8000/docs for the request forms. GET /api/health checks both databases. The server allows the web app at localhost:5173 and 127.0.0.1:5173; WEB_ORIGINS can set a comma-separated list of other local origins.

## What works

- Search and page through riders, vehicles and trips, then open a record.
- Read VehicleMetadata from MongoDB with vehicle details.
- Book a trip through sp_book_trip, including its exact wallet audit row and balances.
- Move a trip from REQUESTED to IN TRANSIT, then complete it through sp_release_escrow.
- Read wallet history with dates, pages and the stored running balance.
- Read seven-calendar-day revenue averages and daily fleet ranks from SQL.
- Read lifetime vehicle totals and refresh them with a saved successful time.
- Find fresh, available vehicles within 5 km using their latest ping and SQL vehicle labels.
- Read review pages, rating counts, average ratings and top feedback tags from MongoDB.
- Show useful errors for bad input, insufficient funds, duplicate active trips and unavailable databases.

Money is sent as text, for example "120.00", to keep decimal values exact. IDs are UUIDs. Dates are inclusive Asia/Kolkata dates; returned timestamps use UTC. Use the /docs examples and docs/api_endpoints.md for the full contract. Class values come from the inherited free-text column, so custom classes can be filtered too.

The API keeps business rules in the database. Each procedure call uses its own connection and lets the procedure commit or roll back. PostgreSQL read requests use one consistent snapshot. Filtering and pagination stay in PostgreSQL or MongoDB rather than loading every row into Python.

## Checks

~~~sh
python -m pytest tests/test_api.py -q
python tests/backend_smoke.py
~~~

The API suite needs a local PostgreSQL role that can create test databases. It creates unique ridesync_api_test_* PostgreSQL and MongoDB databases and removes only those databases at the end. The existing smoke test keeps its separate ridesync_verify_* databases for inspection.

The API suite currently passes 60 checks, including concurrent wallet updates, calendar-day revenue gaps, fleet-rank ties, refresh contention/failure, outdated pings, map result limits, review date boundaries and database outages. The backend suite passes 29 checks, including setup of the two new SQL scripts. A test-client dependency warning remains; it does not fail the tests. These checks use small datasets. Large dataset checks are still pending. Browser UI checks are documented in ../web/README.md.

The working assignment screens are in web/; run them at http://127.0.0.1:5173. The /docs page remains available for checking API requests. Nearby responses are empty after seeded pings expire; fresh pings are needed for a later demo. No seeded trips or wallets were changed by this API update.
