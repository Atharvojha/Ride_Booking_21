# Team 10 API endpoints and remaining plan

The health, rider, vehicle, trip, booking, status and wallet-audit routes are implemented. Analytics, nearby search and review routes below are still planned. See [setup instructions](../api/README.md).

The browser talks only to the API. The API calls PostgreSQL procedures/views and MongoDB aggregations. Demo rider switching is sufficient; real login is outside the required scope. Validate IDs, coordinates, fares, filters and status transitions on the server.

| Method and path | Input | Output / inherited operation |
|---|---|---|
| GET /api/health | None | PostgreSQL/MongoDB connectivity |
| GET /api/riders | search, page, pageSize | Paginated rider IDs, names, balances and total |
| GET /api/riders/:id | Rider UUID | Rider details/current wallet balance |
| GET /api/vehicles | search, class, active, page, pageSize | Paginated vehicles and total |
| GET /api/vehicles/:id | Vehicle UUID | Vehicle details plus flexible VehicleMetadata document |
| GET /api/trips | riderId, vehicleId, status, dates, page, pageSize | Paginated trips with rider/vehicle labels |
| GET /api/trips/:id | Trip UUID | Trip details |
| POST /api/trips | riderId, vehicleId, fareAmount | CALL sp_book_trip; trip ID, balance before/after, newly created audit entry |
| PATCH /api/trips/:id/status | status=IN TRANSIT or COMPLETED | Conditional REQUESTED→IN TRANSIT update; completion via sp_release_escrow; updated trip |
| GET /api/riders/:id/audit | from, to, page, pageSize | Read-only audit rows with stored balance_after and date-filter opening balance |
| GET /api/analytics/revenue | vehicleId, from, to, page, pageSize | Moving-average series and DENSE_RANK from the inherited SQL query, extended for calendar days |
| GET /api/analytics/summary | Vehicle filters, page, pageSize | Materialized-view totals, paginated vehicle stats, persisted lastRefreshedAt |
| POST /api/analytics/refresh | None | Refresh materialized view; persist timestamp only after successful refresh |
| GET /api/vehicles/nearby | longitude, latitude | geoNear within 5,000m; distinct fresh vehicles sorted by distance, bounded result count |
| GET /api/reviews/summary | Optional vehicleId/date range | Mongo facet rating distribution, average/count, top tags |
| GET /api/reviews | Optional vehicleId/date range, page, pageSize | Paginated TripReviews |

## Response rules

- Lists default to 25 rows; cap pageSize at 100. Filter and paginate in the database. Keep the sort order consistent. Use the ID to sort records with the same value. The rider dropdown should also search and load one page at a time.
- Booking errors return `{error: {code, message}}`: e.g. INSUFFICIENT_BALANCE, ACTIVE_TRIP_EXISTS, INVALID_INPUT, NOT_FOUND. API code maps procedure output statuses/constraint names to friendly messages and does not expose raw database errors.
- The stored procedures finish their own transactions. Call them directly without starting another transaction around them (autocommit). A returned FAILED status is a failure even when the driver does not throw. Verify completion state because the inherited completion procedure uses notices on failure.
- Reject duplicate submission while booking is pending. If the connection fails, the booking may still have succeeded. Check the rider's trip and balance before allowing a retry. Concurrent booking, completion and wallet top-up cases are covered by tests/test_api.py. The web form retry behavior is still pending.
- The chart will use seven calendar days, including zero-revenue dates. The SQL view needs the change described below. Keep DENSE_RANK in SQL.
- Nearby search uses the latest ping per vehicle before applying availability, freshness and radius checks. Fresh means within two hours, matching the inherited TTL (automatic expiry). Poll every 10 seconds; do not overlap requests. Use $geoNear to calculate distance.
- Use GeoJSON coordinate order [longitude, latitude]. Default demo origin matches the Hyderabad seeder; no real user location is needed.
- Wallet running balances come from stored balance_after; a filtered period must not start its balance calculation at zero.
- Currency is not defined by the inherited schema. Team 10 demo assumption: INR. This plan does not include a route or distance estimation service. See docs/design/README.md for the screen plan.

## Shared input and response format

These contracts are used by the implemented routes. Analytics, nearby search and reviews are the next API step. Names in JSON use camelCase; database columns keep their current names. IDs below are UUIDs; MongoDB document IDs are strings.

- Money is a decimal string with two decimal places, such as "125.50". Validate with decimal arithmetic on the server. Fare must be greater than zero and at most 99,999,999.99. This fits both the fare column and the inherited wallet trigger DECIMAL(10,2) amount variable. Reject extra decimal places, NaN and infinity. Format INR only for display.
- page starts at 1; pageSize defaults to 25 and must be 1 to 100. Invalid values are errors. Lists return items, page, pageSize and total. A page beyond the end returns an empty items list.
- search is optional and at most 100 characters. Use query parameters safely; do not build SQL by joining user text. Search rider name/ID and vehicle plate/ID. Status, class and active filters must be validated.
- from and to are optional YYYY-MM-DD calendar dates in Asia/Kolkata, with both ends included. Convert them to a start time and the next day's start time in UTC for database comparisons. Reject reversed ranges; cap chart ranges at 90 days.
- Output timestamps use ISO 8601 UTC with Z. Display them in Asia/Kolkata. Analytics date labels are the same local calendar days.
- Default analytics dates are the last 30 calendar days through today. Empty revenue data is zero; an empty average review rating is null.
- Order riders by name then ID, vehicles by license plate then ID, trips by created_at descending then ID, audit by timestamp then ID, and reviews by created_at descending then document ID. The database applies filters and pagination.
- Vehicle/rider selectors use the same paginated list routes. Clear or reload rider-specific results when the demo rider changes. Cancel obsolete reads so old responses cannot replace a newer selection.

## Objects sent to the browser

| Object | Fields |
|---|---|
| Rider | id, name, walletBalance |
| Vehicle | id, licensePlate, class, isActive |
| Trip | id, riderId, vehicleId, fareAmount, status, createdAt; riderName and licensePlate from SQL joins |
| Audit entry | id, riderId, amountChanged, actionType, balanceAfter, timestamp |
| Review | id, tripId, vehicleId, rating, feedbackTags, createdAt |
| Vehicle metadata | vehicleId, features, inspectionRecords, createdAt; optional values shown only when present |

Example paginated rider result:

    {
      "items": [{"id": "<rider UUID>", "name": "Demo rider", "walletBalance": "500.00"}],
      "page": 1, "pageSize": 25, "total": 100
    }

GET /api/vehicles/:id returns {vehicle, metadata}. metadata is null when absent. If the metadata query fails, report a partial response with metadataError and let that section retry; do not call the failure an empty catalog.

GET /api/trips/:id returns {trip}. GET /api/riders/:id returns {rider}. GET /api/health returns {postgres: "ok", mongo: "ok"} with 200 only when both are reachable; otherwise 503 and the unavailable database marked "unavailable". No connection strings or raw errors are sent.

## Booking and status changes

POST /api/trips accepts:

    {"riderId": "<rider UUID>", "vehicleId": "<vehicle UUID>", "fareAmount": "120.00"}

On success it returns HTTP 201:

    {
      "trip": {"id": "<trip UUID>", "riderId": "<rider UUID>", "vehicleId": "<vehicle UUID>",
               "fareAmount": "120.00", "status": "REQUESTED", "createdAt": "<UTC time>"},
      "balanceBefore": "500.00", "balanceAfter": "380.00",
      "auditEntry": {"id": "<audit UUID>", "riderId": "<rider UUID>", "amountChanged": "-120.00",
                     "actionType": "ESCROW_HOLD", "balanceAfter": "380.00", "timestamp": "<UTC time>"}
    }

To identify this audit entry safely, the wallet trigger captures the inserted audit ID and stores it in a transaction-local setting. sp_book_trip reads that ID before COMMIT and returns it as a new OUT argument. On failure it returns no trip or audit ID. Seed scripts and tests now call the six-argument procedure: three inputs and three output placeholders. Do not guess the audit row by choosing the latest timestamp or matching amount.

The API derives the booking's balanceBefore as auditEntry.balanceAfter minus auditEntry.amountChanged. These are this transaction's balances. A later current-wallet read can differ if another update happens. The trigger still creates the audit row. The procedure still owns the booking transaction. The trigger and procedure changes are applied in this API step.

sp_book_trip rejects inactive vehicles, and the API returns a friendly error. This protects callers using the procedure directly too. is_active is not a per-trip availability lock; the inherited rules only prevent a rider having two active trips. Record any extra fleet rule before adding it.

PATCH /api/trips/:id/status accepts {"status": "IN TRANSIT"} or {"status": "COMPLETED"}, returns {trip}. Only REQUESTED -> IN TRANSIT -> COMPLETED is allowed. Use a conditional SQL update for the first transition, and sp_release_escrow for completion. Missing trips return 404; wrong current state returns 409. Verify the final status after the procedure; a NOTICE alone is not proof of completion.

## Wallet audit

GET /api/riders/:id/audit accepts from, to, page and pageSize. Return {items, page, pageSize, total, currentBalance, openingBalance}. Rows use the audit-entry fields above. openingBalance is the stored balance immediately before the selected period, not zero. If there is no preceding log but there is a first in-period entry, derive it as balanceAfter minus amountChanged. If the period is before all recorded history and there is no entry to derive from, return null and show Unknown. Use the stored balanceAfter for every displayed running balance. Do not recalculate it from the current page.

## Revenue and lifetime totals (planned)

GET /api/analytics/revenue accepts vehicleId, from, to, page and pageSize. Return {series, rankings, page, pageSize, total, from, to, timezone}. series is for one selected vehicle, with entries {vehicleId, date, dailyRevenue, movingAverage7Days}. If vehicleId is omitted, select the first active vehicle by license plate and ID and return selectedVehicleId; the UI then makes that selection visible. This bounds chart size. rankings are paginated entries {vehicleId, licensePlate, date, dailyRevenue, movingAverage7Days, rank}, ordered by date descending, rank then vehicle ID. With a vehicleId filter they retain that vehicle's rank among the whole fleet.

Adapt the inherited SQL window query during the API step as a parameterized query (a regular view does not accept date arguments): create one row for every vehicle/date in the requested range plus the preceding six days, fill missing revenue with zero, and average the current day and preceding six calendar days. Use only COMPLETED fares, consistent with the inherited query. Rank each day's movingAverage7Days across the whole fleet using DENSE_RANK, preserving the inherited ranking metric, before selecting a vehicle or trimming display dates. Equal moving averages give equal rank. Do not calculate either result in browser code.

GET /api/analytics/summary accepts vehicleId, page and pageSize. Return {items, page, pageSize, total, totals, lastRefreshedAt}. Items have vehicleId, licensePlate, class, isActive, lifetimeTripCount and lifetimeEarnings. totals has lifetimeTripCount and lifetimeEarnings for all matching vehicles, not only the current page. Label trip count as all statuses and earnings as completed trips only. These are lifetime values, not the chart's date-filtered totals.

POST /api/analytics/refresh accepts no body; call the inherited refresh function and return {lastRefreshedAt}. During the API step add a small table to persist the last successful refresh time, initially null (Unknown). Call the existing refresh function and update the timestamp in one database transaction, only after refresh succeeds. Refresh failure keeps the previous time. Serialize refresh requests; while one is running return 409 REFRESH_IN_PROGRESS. GET summary must read totals and their refresh time in one SQL statement or a transaction with a repeatable-read snapshot, so they describe the same refresh.

## Nearby vehicles

GET /api/vehicles/nearby accepts longitude (-180 to 180), latitude (-90 to 90) and limit (1 to 50, default 50). Radius is fixed at 5000 metres. Return {origin: {longitude, latitude}, radiusMeters: 5000, freshnessSeconds: 7200, checkedAt, items}. Each item has vehicleId, licensePlate, class, longitude, latitude, distanceMeters and pingAt. Order by distance then vehicle ID. The response is bounded; it is not a dump of all telemetry.

Extend the inherited nearest-one pipeline during implementation. First establish each vehicle's latest ping globally, using created_at descending and _id as a tie-breaker. Only then test its availability, age and distance. If $geoNear runs first, verify every candidate against the globally latest ping before applying the result limit; a newer unavailable or outside-radius ping must exclude the older candidate. Do not group only available or nearby pings and call those latest. MongoDB determines the distance with $geoNear, using GeoJSON [longitude, latitude]. SQL can supply vehicle labels and exclude inactive/missing vehicles. Document and inspect the query plan at scale.

The UI uses a Hyderabad demo origin from the seeder, with editable coordinates. No real user location permission is needed. Poll every 10 seconds and display the last successful response time. Pause polling while the screen is hidden. Two hours is a demo assumption matching the telemetry expiry; this is not a claim that such positions are suitable for a real ride service.

## Reviews and flexible metadata

GET /api/reviews/summary accepts vehicleId, from and to. Put these filters before the inherited $facet stage. Return {reviewCount, averageRating, ratingDistribution, topTags}. ratingDistribution is [{rating: 1, count: 0}, ..., {rating: 5, count: 0}] with actual counts filled in; topTags is [{tag, count}] sorted by count descending then tag, limited to 10. No reviews gives reviewCount 0, averageRating null and topTags [].

GET /api/reviews uses the same filters plus page and pageSize and returns the shared list format. VehicleMetadata is read using vehicle_id as the SQL UUID converted to a string. inspectionRecords preserves the actual flexible item values. Features are listed only when their stored flag is true.

## Friendly errors

All errors use {error: {code, message}}. Treat FAILED procedure output as an error even if the database driver does not throw. Map known constraint/procedure failures; log unexpected details on the server only.

| HTTP status | Code | Message example |
|---|---|---|
| 422 | INVALID_INPUT | Enter a positive fare with at most two decimal places. |
| 404 | NOT_FOUND | This rider, vehicle or trip could not be found. |
| 409 | INSUFFICIENT_BALANCE | This rider does not have enough wallet balance. |
| 409 | ACTIVE_TRIP_EXISTS | Complete this rider's active trip before booking another. |
| 409 | VEHICLE_INACTIVE | Choose an active vehicle. |
| 409 | INVALID_TRANSITION | This trip cannot move to that status from its current state. |
| 409 | REFRESH_IN_PROGRESS | A refresh is already running. Try again shortly. |
| 503 | DATABASE_UNAVAILABLE | The data service is unavailable. Try again shortly. |
| 500 | INTERNAL_ERROR | The request could not be completed. |

The core browsing, booking, status and wallet routes are implemented and tested. Analytics, nearby search and review routes remain planned.
