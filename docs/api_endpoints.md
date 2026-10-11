# Team 10 API outline — proposed, not implemented

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
| GET /api/analytics/revenue | vehicleId, from, to, page, pageSize | Moving-average series and DENSE_RANK results from the SQL view |
| GET /api/analytics/summary | Vehicle filters, page, pageSize | Materialized-view totals, paginated vehicle stats, persisted lastRefreshedAt |
| POST /api/analytics/refresh | None | Refresh materialized view; persist timestamp only after successful refresh |
| GET /api/vehicles/nearby | longitude, latitude | geoNear within 5,000m; distinct fresh vehicles sorted by distance, bounded result count |
| GET /api/reviews/summary | Optional vehicleId/date range | Mongo facet rating distribution, average/count, top tags |
| GET /api/reviews | Optional vehicleId/date range, page, pageSize | Paginated TripReviews |

## Response rules

- Lists default to 25 rows; cap pageSize at 100. Filter and paginate in the database. Use stable ordering with ID tie-breakers. Actor selectors also search/paginate; do not download every rider.
- Business failures return `{error: {code, message}}`: e.g. INSUFFICIENT_BALANCE, ACTIVE_TRIP_EXISTS, INVALID_INPUT, NOT_FOUND. API code maps procedure output statuses/constraint names to friendly messages and does not expose raw database errors.
- Stored procedures commit internally. Use a dedicated top-level CALL on an autocommit connection. A returned FAILED status is a failure even when the driver does not throw. Verify completion state because the inherited completion procedure uses notices on failure.
- Reject duplicate submission while booking is pending. A transport failure can have an uncertain result; refetch the rider's active trip/balance before offering retry. Test concurrent bookings before final submission.
- Resolve the calendar-day moving-average requirement before implementing the chart. Keep DENSE_RANK in SQL.
- Nearby search must avoid returning multiple historical pings as different vehicles. Define freshness/latest-ping behavior explicitly and preserve geoNear as the source of distance. Polling every 5–10 seconds is a proposed UI choice.
- Use GeoJSON coordinate order [longitude, latitude]. Default demo origin matches the Hyderabad seeder; no real user location is needed.
- Wallet running balances come from stored balance_after; a filtered period must not start its balance calculation at zero.
- Currency is not defined by the inherited schema. Proposed assumption: INR, to be recorded in the design/README before implementation. No route estimation service is included in this contract.
