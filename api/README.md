# RideSync API setup

Run commands from the repository root in VS Code's terminal. Use Python 3.11 or newer. PostgreSQL and MongoDB must already be running; follow the main README for database setup and seed data.

~~~sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r api/requirements.txt -r data_generation/requirements.txt
~~~

The first file pins server and test packages. The second includes Faker for seed data and the existing backend checks. Copy .env.example to .env if needed, then fill in your local settings. The API reads .env automatically. Keep credentials out of Git.

For a database seeded before this API step, load .env into the terminal and run sql/03_triggers_and_audit.sql followed by sql/04_stored_procedures.sql with psql -v ON_ERROR_STOP=1. See the exact commands in the main README. These two scripts can be applied again. Do not rerun the table-creation script on that database.

~~~sh
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
~~~

Open http://127.0.0.1:8000/docs for the request forms. GET /api/health checks both databases. The server allows the future web app at localhost:5173 and 127.0.0.1:5173; WEB_ORIGINS can set a comma-separated list of other local origins.

## What works

- Search and page through riders, vehicles and trips, then open a record.
- Read VehicleMetadata from MongoDB with vehicle details.
- Book a trip through sp_book_trip, including its exact wallet audit row and balances.
- Move a trip from REQUESTED to IN TRANSIT, then complete it through sp_release_escrow.
- Read wallet history with dates, pages and the stored running balance.
- Show useful errors for bad input, insufficient funds, duplicate active trips and unavailable databases.

Money is sent as text, for example "120.00", to keep decimal values exact. IDs are UUIDs. Dates are inclusive Asia/Kolkata dates; returned timestamps use UTC. Use the /docs examples and docs/api_endpoints.md for the full contract. Class values come from the inherited free-text column, so custom classes can be filtered too.

The API keeps business rules in the database. Each procedure call uses its own connection and lets the procedure commit or roll back. Read requests use one consistent database snapshot. Pagination happens in SQL rather than loading every row into Python.

## Checks

~~~sh
python -m pytest tests/test_api.py -q
python tests/backend_smoke.py
~~~

The API suite needs a local PostgreSQL role that can create test databases. It creates unique ridesync_api_test_* PostgreSQL and MongoDB databases and removes only those databases at the end. The existing smoke test keeps its separate ridesync_verify_* databases for inspection.

The API suite currently passes 36 checks, including concurrent bookings/completions, a wallet top-up during booking, and completion waiting for a top-up. The existing backend suite passes 27 checks. A test-client dependency warning remains; it does not fail the tests. These checks use small datasets. Large dataset checks and browser UI tests are still pending.

Analytics, nearby search, review summaries and the actual web screens are the next steps. The /docs page is for checking the API, not the assignment's finished frontend.
