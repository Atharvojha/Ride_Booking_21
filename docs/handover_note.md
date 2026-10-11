# Team 10 handover note

Project P2, RideSync (ride booking). Assignment 2, Front End Design. Team repository: https://github.com/Atharvojha/Ride_Booking_21. Inherited from https://github.com/amaan070/Ride_Booking_21, starting commit `d0d5ad44ba4ab2f566cd965e055870ddd7e95697`. All 23 inherited commits are kept, with their original authors. The detailed day-by-day record is in [handover_history.md](handover_history.md), which still contains old "pending" statements because it is a record of the time.

## What we inherited

A PostgreSQL schema with a wallet audit trigger, booking and escrow-release procedures, a partial unique index and a materialized view, plus MongoDB collections for vehicle metadata, GPS pings and reviews. Seed scripts, SQL and Mongo scripts for the heavy queries, and no application on top.

## What we found and fixed

- The nearby-search script did not run under `mongosh`. It is now a runnable function.
- A metadata index named a collection with the wrong capital letter, so it indexed nothing. Collection setup can now be repeated safely.
- A password was written in one seeder and typed at a prompt in the other. Both now read environment settings (`.env`, not committed).
- The seeder added wallet credits only in memory, so the real wallet and its audit trigger never saw them. They now update the database.
- The seven-day average used seven rows, not seven days. `sql/08_api_revenue.sql` uses calendar days, counts days with no trips as zero and ranks the whole fleet.
- The booking procedure now checks the fare and the vehicle, and returns the exact audit row it caused. Completion locks the wallet before the trip, like booking does. Refresh times are now saved.

## What we built

A FastAPI server in `api/` (inputs and outputs in [api_endpoints.md](api_endpoints.md)) and a React web app in `web/` with the six required screens: Browse Data, Book a Trip, Wallet Audit, Vehicle Analytics, Nearby Vehicles and Trip Reviews. Wireframes and user descriptions are in [design/](design/README.md). Business rules stay in the databases. The web app does not calculate money or ranks.

## How to run it

Follow the Team 10 setup at the top of the root [README.md](../README.md): create a database, run `sql/*.sql` in order, run the Mongo scripts, seed, start the API on port 8000 and the web app on port 5173.

## Tests

| Check | Result |
| --- | --- |
| API tests (`tests/test_api.py`) | 62 pass |
| Telemetry helper tests (`tests/test_demo_pings.py`) | 9 pass |
| Frontend unit tests (`npm test`) | 23 pass |
| Browser tests (`npm run test:browser`, real API and temporary databases) | 9 pass |
| Full-size checks (`tests/scale_check.py`, see [scale_verification.md](scale_verification.md)) | 75 pass |

The backend smoke script (`tests/backend_smoke.py`) and the original 27-check report are described in the README. Some browser failures (lost replies, outages) are deliberately simulated.

## Assumptions

Money is INR (the schema has no currency). Fares are typed in by the user. Dates use Asia/Kolkata. A rider has one demo identity at a time, with no real login. Trip statuses are only REQUESTED, IN TRANSIT and COMPLETED, so there is no cancellation or refund. There is no driver table, rider contact, route or pickup place in the database, so we did not invent them. A ping counts as fresh for 7,200 seconds, the same as the Mongo expiry.

## Why these technologies

PostgreSQL for money and trips because it has transactions, constraints and triggers. MongoDB for flexible metadata, expiring pings and map queries. FastAPI because it is small and reuses the stored procedures. React with Vite and plain CSS for shared screens without a heavy toolkit. Leaflet with OpenStreetMap for the map, small SVG charts instead of a chart package.

## Known limits

The 90-day revenue chart takes about 4 seconds at full size because every vehicle is ranked for every day. Nearby search time grows with the number of fresh pings. Pings disappear after two hours, so a demo needs fresh ones (`data_generation/refresh_demo_pings.py`). The seeder gives all trips the same few minutes. See [scale_verification.md](scale_verification.md).

## Still to do before submission

Record the demo video ([demo_script.md](demo_script.md)), add each member's real contributions, the video link and the final commit hash, and build the ZIP.

## Suggestions for the original authors

Keep connection settings in a configuration file and document the order for seeding and refreshing views. Test failures as well as successful bookings. Explain how the moving average and the "current" vehicle position are decided.
