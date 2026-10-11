# RideSync frontend

Run the database setup and API steps in the root README first. Use two VS Code terminals: one for the API on port 8000, one for this app.

~~~sh
cd web
npm ci
npm run dev
~~~

Open http://127.0.0.1:5173. The app uses the real API through Vite's local proxy. There is no login; the header switches demo riders. The first rider is selected automatically. Lists fetch 25 rows per page; rider and vehicle selectors fetch 10 choices per page. Filters and details also come from the API.

React shares the forms, tables and dialogs. Vite runs the local app and build. Plain CSS follows the navy/blue Figma layout and stacks cards on phones. Native SVG/CSS charts draw the returned revenue, rating and tag values. Leaflet shows nearby coordinates; OpenStreetMap tiles need internet access and retain attribution. A failed basemap does not hide the result list. See the tile policy link in docs/design/README.md.

Booking uses a positive INR fare with up to two decimal places. It shows the actual saved balances and audit ID. A lost reply locks the rider, navigation and booking controls. After the database timeout window, the user reads saved trips and wallet before continuing; no second booking is sent automatically. Trip details provide REQUESTED, IN TRANSIT and COMPLETED status changes.

## Checks

From web/:

~~~sh
npm test
npm run build
RIDESYNC_TEST_PYTHON=../.venv/bin/python npm run test:browser
~~~

The Python path must point to the environment with api/requirements.txt installed. Google Chrome, PostgreSQL and MongoDB must be installed and running. The PostgreSQL role needs permission to create test databases. Ports 8001 and 5174 must be free. Node 26.8.2 and Chrome were used for these checks; package-lock.json pins the browser packages.

Unit checks cover fare precision, API failures/timeouts, old replies arriving late, stale reads, visible/idle polling and metadata. Browser checks start the real API against unique ridesync_browser_test_* databases, create a small fixture, use the actual procedures and pipelines, and remove only those temporary databases when the server stops. The existing demo database is untouched. Browser checks block public map tiles; they check the map markers and distance list rather than tile delivery.

Lost replies and read/refresh outages are deliberately intercepted in browser tests. Successful writes still reach the real temporary API. Do not count the intercepted failures as a live database outage test. API-level database outage and concurrency checks remain in tests/test_api.py.

The screen captures in docs/design/screenshots/ come from the browser fixture. Full-scale checks, demo recording, contribution details and the submission ZIP are still pending.
