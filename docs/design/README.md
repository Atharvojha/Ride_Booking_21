# RideSync design plan

Team 10, Assignment 2. These are the planned screens. All required API routes now work; the web app is still to be built.

## Design reference

We reviewed the six required screens in the [Figma prototype](https://www.figma.com/make/wwotVWxHR3U34BWh4h4qeo/Complete-RideSync-UI-UX-Design) in Chrome on 11 October 2026. Its values and booking outcomes are sample data. Its build claims do not describe this repository.

[Open the six wireframes](wireframes.html) in a browser. These are simple drawings of the planned screens, with placeholder values. They are saved here so the submission does not depend on access to Figma. The layout follows the prototype, with fields adjusted to the inherited database.

## Main users

- Rider: choose a vehicle, book a trip, see the wallet charge, and inspect their trips and wallet history.
- Fleet operator: browse riders, vehicles and trips, move a trip through its demo statuses, inspect revenue, find nearby vehicles, and read review summaries and vehicle metadata.

The header has a searchable demo rider selector. This changes which rider is used by booking and wallet screens. It is not a login or a permission system. Both views are available for the assignment demo. There is no driver table in the inherited database.

## Screens and database work

| Screen | What the user does | API and database |
|---|---|---|
| Browse Data | Search Riders, Vehicles or Trips; filter; change page; open a record | GET riders/vehicles/trips and their detail routes; SQL tables |
| Book a Trip | Choose rider and active vehicle, enter demo fare, review and book | POST trips; sp_book_trip; wallet trigger creates an audit entry |
| Wallet Audit | Choose rider and dates; inspect changes and stored running balance | GET riders/:id/audit; wallet_audit_logs |
| Vehicle Analytics | Choose vehicle/date range; inspect seven-day chart and moving-average ranking; refresh lifetime totals | GET analytics/revenue and summary; SQL window query, DENSE_RANK (tied values share a rank) and materialized view (saved summary); POST refresh |
| Nearby Vehicles | Select an origin; see vehicles within 5 km, sorted by distance | GET vehicles/nearby; MongoDB $geoNear; poll every 10 seconds |
| Trip Reviews | Filter by vehicle/date; see rating counts, average and tags; open vehicle metadata | GET reviews/summary and reviews; $facet; GET vehicles/:id for VehicleMetadata |

Full paths and inputs are in [the API plan](../api_endpoints.md).

## Booking and trip states

1. Choose a rider and search for an active vehicle. Load choices a page at a time.
2. Enter a positive demo fare in INR, with at most two decimal places, up to 99,999,999.99 to fit the inherited trigger. This is an input to the inherited procedure, not a route estimate.
3. Show the selected rider, vehicle, current wallet balance, fare and projected balance. Ask the user to review them.
4. Submit once; disable submission while waiting. On success show the trip ID, actual wallet balance before and after, and the new audit entry.
5. Show plain errors for low balance, an existing active trip, an inactive/missing vehicle, invalid input or an unavailable server. A failed transaction must not be shown as successful.
6. If the reply is lost, explain that the result is unknown. Reload the rider's trips and wallet before enabling a retry.

Trip details offer REQUESTED -> IN TRANSIT -> COMPLETED. Completion calls sp_release_escrow and verifies the saved trip status. A second booking stays blocked during REQUESTED and IN TRANSIT; it can succeed after completion. No cancellation or refund flow is planned because these are not inherited statuses. Vehicle is_active is a fleet flag, not proof that the vehicle is free for another trip.

## Changes from the prototype

- Show actual UUIDs, names, license plates, class, wallet balance and trip fields. Remove rider contact and account-status columns because they do not exist. Use short IDs in tables and the full ID in details.
- Replace dollars with INR as a documented demo assumption; the schema does not specify a currency.
- Remove pickup, destination and calculated distance from booking. There is no route service or storage for those fields. The nearby origin is a separate coordinate input.
- Remove the selectable prototype booking result; show the real database result instead.
- Use actual metadata fields when present: features and inspection records. Do not invent battery/range specifications.
- Wallet rows have no related-trip field. The booking procedure now returns the exact audit ID, which the API uses to show the new entry.
- Leave Overview, Settings, Add record, saved drafts, CSV export, global search, notifications and comparison percentages for later. The six required screens take priority.

## Shared look and components

Keep the prototype's navy sidebar, blue main buttons, pale page background and white cards. Planned colours: sidebar #17233f, action #3567e8, background #f4f6fb, text #172033, border #dce2eb, success #18794e, error #b42318. These are chosen values, not extracted Figma tokens.

Use the system font at 16 px, clear headings, spacing in multiples of 8 px, and a visible keyboard focus outline. Share buttons, labelled inputs, searchable selectors, status badges, tables, page controls, detail drawers, charts and feedback messages. Show status text alongside colour. Keep database query names in documentation; screen labels should explain the result.

## Loading, empty and error cases

| Screen | Loading | Empty | Error |
|---|---|---|---|
| Browse | Table placeholders; keep filters visible | No records match; clear filters | Message and retry; keep chosen filters |
| Booking | Disable submit and show Booking... | No active vehicles; explain and retry list | Field message or booking error; preserve inputs |
| Wallet | Table placeholders | No wallet changes in these dates | Message and retry; no invented balance |
| Analytics | Chart placeholder; disable refresh while running | No completed revenue; chart values zero | Keep last good totals with a stale label and retry |
| Nearby | Map placeholder and loading list | No fresh available vehicles within 5 km | Keep last result marked stale; show last successful update and retry |
| Reviews | Chart placeholders | Zero counts, average shown as No ratings; no metadata message | Separate review/metadata errors with retry |

Every list uses server-side search and pagination, default 25 and maximum 100 rows. The API does the filtering before sending a page. Details are loaded on request.

## Laptop and phone layout

At laptop width, use a sidebar, header and two-column booking/map layouts. Below 760 px, use a menu button, put the rider selector below the title, and stack cards, map and results. Keep tables in a labelled horizontal scroll area. Detail drawers fill the phone width. Controls should have a 44 px minimum touch height. Keyboard users can move between fields, open details and close them with Escape.

## Build choices and checks still needed

Planned stack: React with [Vite](https://vite.dev/guide/) for the browser, ordinary CSS for shared styles, [FastAPI](https://fastapi.tiangolo.com/) for a small Python API, a chart library for revenue/reviews, and [Leaflet](https://leafletjs.com/) for the map. Python fits the existing seed scripts. Leaflet can show MongoDB results without a paid map SDK; choose and document a tile provider's usage terms before implementation. FastAPI is used by the working API. The frontend libraries will be added when we build the web app.

Before submission, test a successful booking, low balance, an active trip, inactive vehicle, status changes, simultaneous bookings, a lost reply, wallet date filters, seven calendar days with gaps, tied rankings, refresh failures, stale/newer-unavailable pings, empty reviews, pagination and phone layouts. API-level cases are covered by the 60 tests in tests/test_api.py. Lost-reply handling in the web form, browser checks and phone layouts still need testing after the frontend is built. Everyone must be able to explain the stored procedures, trigger, SQL query and MongoDB pipelines for the viva.
