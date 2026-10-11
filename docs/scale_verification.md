# Full-scale verification — 11 October 2026

This report covers the full-size dataset check for Team 10. All numbers come from our own runs on 11 October 2026. The machine-readable results are in [scale_verification.json](scale_verification.json) and the query plans are in [scale_explain_postgres.txt](scale_explain_postgres.txt) and [scale_explain_mongo.txt](scale_explain_mongo.txt).

The files in `performance/` are the original Assignment 1 team's measurements (on different data sizes). We did not change or reuse them. Nothing here comes from them.

## What we tested

We used the inherited seed sizes: `NUM_RIDERS=100000`, `NUM_VEHICLES=40000`, `NUM_TRIPS=50000`, `NUM_PINGS=520000`. `NUM_TRIPS` is the number of attempts, so we counted what was actually saved.

New databases were used, so the demo databases (`ridesync_team10`) were not touched:

| Database | Purpose |
| --- | --- |
| PostgreSQL `ridesync_scale_20261011` and MongoDB `ridesync_scale_20261011` | The seeded data. Used only for read checks. |
| PostgreSQL `ridesync_scale_20261011_copy` | A copy of the seeded PostgreSQL database. Used for checks that write (bookings, refresh) and for revenue checks. |

The seeder gives every trip the time it was created, so all 50,000 trips fall inside about four minutes on one day. The seeder does not spread trips across 60 days (its `random_past_timestamp()` function is never called). To check multi-day averages we made the copy by moving each trip back by a fixed amount, 0 to 59 days (the first byte of `md5(id)` modulo 60). **The copy is a test aid. It is not seeded data.**

```sh
createdb -T ridesync_scale_20261011 ridesync_scale_20261011_copy
psql -d ridesync_scale_20261011_copy -c "UPDATE trips SET created_at = created_at - (get_byte(decode(md5(id::text),'hex'),0) % 60) * interval '1 day'; ANALYZE;"
```

## Environment

| Item | Value |
| --- | --- |
| Machine | Apple M2, 8 cores, 8 GB memory, macOS |
| PostgreSQL | 17.11, default settings (`shared_buffers` 128 MB, `work_mem` 4 MB) |
| MongoDB | 7.0.43 |
| Python / Node | 3.13.1 / 26.8.2 |
| API | FastAPI with one Uvicorn process, run locally |

Limits that were in force during the tests: PostgreSQL statement timeout 10 s, lock timeout 5 s, MongoDB aggregation limit 5 s, browser request timeout 30 s. We did not change any of them.

## Seeding

| Step | Result |
| --- | --- |
| `postgres_seeder.py` (riders, vehicles, metadata, trips) | 226 s in total. The trip loop took 219.8 s (about 4.4 ms per attempt, steady from start to finish). |
| `mongo_seeder.py` (pings and reviews) | 8 s in total. Inserting the 520,000 pings took 7 s. |
| `refresh_mv_vehicle_lifetime_stats()` | under 1 s |

The trip seeder rebuilds its list of free riders for each attempt. With 100,000 riders we measured this and the speed did not get worse, so we left the seeder as it is.

### Actual counts

| Item | Count |
| --- | --- |
| Riders | 100,000 |
| Vehicles | 40,000 (36,756 active) |
| Trips attempted / booked | 50,000 / 50,000 (the seeder picks a rider's fare so that booking always succeeds) |
| Trips by status | 47,404 COMPLETED, 1,596 IN TRANSIT, 1,000 REQUESTED |
| Wallet audit rows | 50,000 ESCROW_HOLD, 47,404 ESCROW_RELEASE, 194 CREDIT |
| VehicleMetadata documents | 40,000 |
| TripReviews documents | 28,163 (the seeder reviews about 60% of completed trips at random) |
| TelemetryPings documents | 520,000 |
| Materialized view | 40,000 rows, 50,000 trips, earnings 6,498,362.47 INR |

### Sizes

PostgreSQL: 57 MB (trips 12 MB, riders 11 MB, wallet audit 16 MB, materialized view 4.6 MB), as reported by `pg_size_pretty`, where 1 MB is 1,048,576 bytes. MongoDB: 118 MB of data, 51 MB on disk, 40 MB of indexes (TelemetryPings 41 MB on disk plus 35 MB of indexes), where 1 MB is 1,000,000 bytes.

## Correctness checks

`tests/scale_check.py` ran **75 checks. 75 passed, 0 failed** on the final code. The expected values are worked out in plain Python from the raw rows, not by calling the SQL or API code that is being tested.

| Area | What was compared |
| --- | --- |
| Money rules | For all riders: one ESCROW_HOLD row per trip; one ESCROW_RELEASE row per completed trip; the held money equals the sum of fares; the last saved running balance equals the wallet; no negative wallet; no rider with two active trips. Checked on the seeded data and again after the booking tests. |
| Browsing | Totals, search, class/active filters and a one-day Kolkata filter against SQL counts. All 11 pages of REQUESTED trips against the SQL list, with no repeats. A page size above 100 is refused. A page past the end is empty with the true total. Rider, trip and 10 vehicle-metadata details against SQL and Mongo. |
| Booking and wallet | Exact before/after balances and the exact audit row from the trigger. A second active trip, low balance, inactive vehicle and five invalid fares are all refused and change nothing. Start, complete (no refund, zero-amount release row) and book again. Wallet history, opening balance, running balances and date filters. 20 simultaneous bookings for one rider produced exactly one trip. 50 simultaneous bookings for different riders all succeeded (0.22 s in total). |
| Analytics | Summary totals equal the raw table. New bookings are not in the summary until a refresh. A refresh moved the saved time forward and made the totals match again. The SQL revenue function was compared with a Python calculation for **every one of the 40,000 vehicles** on three different days (0 differences). The API's first 100 whole-fleet ranks, a page that crosses from one day to the next, and the 30-day series for a best-ranked, a middle-ranked and a no-revenue vehicle all matched. The no-revenue vehicle kept its whole-fleet rank. 34,094 vehicles with equal zero averages shared one dense rank. The default range is the last 30 Kolkata days, 90 days works, 91 is refused. |
| Nearby | For three origins and limits 1, 10 and 50, the API list matched a Python calculation from every vehicle's newest ping plus the SQL active flag (same vehicles, same order, distances within 1 m). Limit 51 is refused. See below for how often the newest-ping rule matters. |
| Reviews | Summary (count, average, distribution, top 10 tags) for all reviews, for one vehicle and for a date range, matched Python totals. A vehicle with no reviews has no average. Walking all 282 pages returned each review once, newest first. |

For the demo origin, 4,162 vehicles had at least one available, fresh ping inside 5 km (27,713 pings), but only 1,967 of them passed the newest-ping and active-vehicle checks. So the newest-ping rule removes more than half of the candidates in this data.

We also looked at the real screens against the scale data (Browse, Vehicle Analytics, Nearby and Trip Reviews). They loaded and showed the expected totals. This was a manual look, not an automated test. The automated browser tests still use the small temporary databases.

## Timings

Median of three runs (five for Nearby and Reviews) through the real API, on a warm local machine.

| Request | Time | Response size |
| --- | --- | --- |
| Riders, 100 rows | 0.12 s | 9 KB |
| Rider search "Acharya" | 0.20 s | 2 KB |
| Riders, last page (offset 99,900) | 0.41 s | 9 KB |
| Vehicles, 100 rows | 0.02 s | 11 KB |
| Vehicles with class, active and search filters | 0.02 s | 3 KB |
| Trips, 100 rows | 0.06 s | 29 KB |
| Trips, completed, page 300 | 0.07 s | 29 KB |
| Wallet audit for one rider | 0.01 s | small |
| Lifetime summary, 100 rows | 0.02 s | 17 KB |
| Refresh the materialized view | 0.29 s | small |
| Revenue, default 30 days (copy) | **1.55 s** (was 3.72 s) | 8 KB |
| Revenue, maximum 90 days (copy) | **4.13 s** (was 10.58 s) | 15 KB |
| Nearby, limit 50 | 1.30 s | 10 KB |
| Nearby, limit 1 | 1.30 s | under 1 KB |
| Review summary | 0.04 s | under 1 KB |
| Review page, 100 rows | 0.03 s | 15–24 KB |

Every list has a page size of at most 100 rows, so responses stay under about 30 KB.

## Problems found and what we changed

### 1. The revenue screen was slow at full size (changed)

`api_vehicle_revenue()` builds one row per vehicle per day, including six warm-up days, then ranks the whole fleet for each day. For 40,000 vehicles over 30 days that is 1.2 million rows (3.6 million for 90 days). The API ran the function three times for each request: to count rows, to get a page and to get one vehicle's chart. The 90-day maximum took 10.6 s. Each separate query stayed under the 10 s PostgreSQL limit, but it was close, and a user would wait about 10 s.

We measured before changing anything. A bigger `work_mem` barely helped (3.9 s to 3.3 s), so the cost is sorting, not memory.

Change in `api/analytics.py`:

- The row total is now the number of vehicles times the number of days. It does not need the function.
- The ranking list is newest day first, and every day has one row per vehicle, so a page covers one day or the border between two. The API now asks the function only for those days. The function still ranks the whole fleet for each day it returns.
- The chart for the selected vehicle still needs every day in the range, so it still runs the function once for the full range.

Result: 30 days from 3.72 s to 1.55 s, 90 days from 10.58 s to 4.13 s. Two new API tests cover this: one needs no database and checks the days chosen for every page of several page sizes against a row-by-row list; the other walks every page of a three-day range, with a page size that does not divide the fleet (so pages straddle two days) and with a page larger than the fleet, and compares the result with the whole SQL list. We confirmed the tests fail when the page offset, the last day or the day count is deliberately broken. The scale check also compares a page that crosses a day border with the Python reference.

**What is still slow:** the chart query for the 90-day maximum needs the whole-fleet ranking, about 4 s. Its plan sorts 3.6 million rows and writes 176 MB to disk. A production system would store daily ranks in a table. We did not build that.

### 2. Nearby search time grows with the number of fresh pings (not changed)

The API's pipeline looks up the newest ping of every candidate before it sorts and limits. In our data 27,713 candidate pings need 27,713 lookups, about 1.3 s, whatever the limit. This is fine against the 5 s MongoDB limit, but a denser fleet would reach that limit. Each single lookup uses the vehicle/time index and examines one document. Changing the pipeline would need new design work, so we only recorded this.

### 3. Smaller observations (not changed)

- Rider search (`ILIKE '%text%'`) reads every rider: about 100 ms. Trip lists read every trip and sort it: about 40 ms. Both are fine at this size. Per-rider and per-vehicle lookups use indexes.
- Asking for one vehicle with a page size of 90 or more over 90 days still ranks 90 days of the whole fleet twice (once for the page, once for the chart), about 8 s. This is no slower than before. A page of 25 does not have this cost.
- The seeder's top-up counts and review rate are random, so a rerun gives slightly different counts.
- The browser shows "Page 1 of 48000" for the 30-day ranking. This is correct, but not something a person would read page by page.

## Not tested

- Many different users at once. Only the concurrent bookings above were tried.
- Performance on a different machine or with tuned PostgreSQL settings.
- The automated browser suite on the full-size data (it uses small temporary databases). We only looked at the screens by hand.
- Data older than the 2-hour ping lifetime. Pings are created with times in the last 30 minutes and are removed 2 hours after their time, so the Nearby checks are only valid shortly after seeding.
- A full-size run of `tests/backend_smoke.py`. It is a small-sample script.

## How to repeat

Create the databases and seed them, using new names that contain `scale`. The setup steps are in the root README.

```sh
export PGDATABASE=ridesync_scale_20261011 MONGO_DB=ridesync_scale_20261011
export NUM_RIDERS=100000 NUM_VEHICLES=40000 NUM_TRIPS=50000 NUM_PINGS=520000 BATCH_SIZE=5000
createdb "$PGDATABASE"
for script in sql/*.sql; do psql -v ON_ERROR_STOP=1 -f "$script" || break; done
mongosh "$MONGO_URI" --quiet --file mongo/01_collections_and_indexes.js
mongosh "$MONGO_URI" --quiet --file mongo/04_api_indexes.js
python data_generation/postgres_seeder.py
python data_generation/mongo_seeder.py
psql -c 'SELECT refresh_mv_vehicle_lifetime_stats();'
```

Make the copy (shown above), start one API for each database on ports 8002 and 8003, then run the check. Run the check soon after seeding, because pings expire after two hours.

```sh
python -m uvicorn api.main:app --port 8002 &
PGDATABASE=ridesync_scale_20261011_copy python -m uvicorn api.main:app --port 8003 &
python tests/scale_check.py --api http://127.0.0.1:8002 --write-api http://127.0.0.1:8003 \
    --write-db ridesync_scale_20261011_copy --out docs/scale_verification.json
```

The script refuses to run unless the database names contain `scale`, the write copy is a different database, and each API's trip totals match the database it is paired with.
