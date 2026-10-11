# Team 10 API plan — not built yet

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

- Lists default to 25 rows; cap pageSize at 100. Filter and paginate in the database. Keep the sort order consistent. Use the ID to sort records with the same value. The rider dropdown should also search and load one page at a time.
- Booking errors return `{error: {code, message}}`: e.g. INSUFFICIENT_BALANCE, ACTIVE_TRIP_EXISTS, INVALID_INPUT, NOT_FOUND. API code maps procedure output statuses/constraint names to friendly messages and does not expose raw database errors.
- The stored procedures finish their own transactions. Call them directly without starting another transaction around them (autocommit). A returned FAILED status is a failure even when the driver does not throw. Verify completion state because the inherited completion procedure uses notices on failure.
- Reject duplicate submission while booking is pending. If the connection fails, the booking may still have succeeded. Check the rider's trip and balance before allowing a retry. Test bookings made at the same time before submission.
- Resolve the calendar-day moving-average requirement before implementing the chart. Keep DENSE_RANK in SQL.
- Nearby search must avoid returning multiple historical pings as different vehicles. Decide how old a location update can be and which update counts as the latest. Use geoNear to calculate distance. Polling every 5–10 seconds is a proposed UI choice.
- Use GeoJSON coordinate order [longitude, latitude]. Default demo origin matches the Hyderabad seeder; no real user location is needed.
- Wallet running balances come from stored balance_after; a filtered period must not start its balance calculation at zero.
- Currency is not defined by the inherited schema. Proposed assumption: INR, to be recorded in the design/README before implementation. This plan does not include a route or distance estimation service.
