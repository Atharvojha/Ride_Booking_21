# Demo video script (target 4 minutes 45 seconds, limit 5 minutes)

**Status: the video has not been recorded yet.** This is the plan and the exact steps. After recording, put the link in the README submission section.

Use one person's voice for the whole video, but every member should be able to take any part. Say what is on the screen; do not read the code.

## Before recording

Records come from the demo database `ridesync_team10` (100 riders, 40 vehicles, 100 trips, 56 reviews, as counted on 11 October 2026). Booking changes balances, so **record on a fresh copy of the PostgreSQL demo database each time**. The MongoDB data is only read during the demo (and the telemetry helper only adds pings), so both takes can share it.

1. Make a fresh copy for this take (change the number for each retake). `createdb -T` fails if anything is connected to the demo database (a `psql` session, or a server still running on it), so close those first:

   ```sh
   set -a; source .env; set +a
   createdb -T ridesync_team10 ridesync_team10_take1
   ```

2. Add fresh vehicle pings. Pings last two hours, so do this just before recording. First look at the plan, then insert:

   ```sh
   python data_generation/refresh_demo_pings.py --dry-run
   python data_generation/refresh_demo_pings.py
   ```

   This adds 25 pings (19 should appear on the map, 3 are unavailable and 3 are more than 5 km away). It adds nothing else. Do not run `mongo_seeder.py`, which would add reviews again.

3. Start the API and the web app on spare ports, so earlier servers are not disturbed:

   ```sh
   PGDATABASE=ridesync_team10_take1 python -m uvicorn api.main:app --host 127.0.0.1 --port 8100
   ```

   In a second terminal:

   ```sh
   cd web
   RIDESYNC_API_TARGET=http://127.0.0.1:8100 npx vite --host 127.0.0.1 --port 5180 --strictPort
   ```

4. Open http://127.0.0.1:5180 in Chrome. Check `http://127.0.0.1:5180/api/health` shows `ok` for both databases.
5. Recording: press Cmd+Shift+5 (macOS screen recording) and record the Chrome window, or use QuickTime Player: File, New Screen Recording. Use a window about 1280 px wide, turn on Do Not Disturb, close other tabs and keep your voice clear. Rehearse once first.
6. The map needs an internet connection for the OpenStreetMap tiles while recording.
7. Upload the finished file (Google Drive or an unlisted YouTube video), check the link opens in a private window, then record the link.

## Demo records

| Use | Record | Why |
| --- | --- | --- |
| Rider who can book | Thomas Pant, 3,831.34 INR, ID starts `37798930`, no active trip | Plenty of money |
| Rider with low balance | Kala Sahni, 22.99 INR, ID starts `094debd7` | Cannot afford a 100 INR fare |
| Rider with an active trip | Meghana Sharma, ID starts `5a8d58b5`, trip IN TRANSIT | Cannot book again |
| Vehicle with revenue | `TS07RZ3369201` (Sedan), 5 trips, 1,324.77 INR | Top earner on the lifetime list |
| Inactive vehicle | `KA05JB9220213` (Sedan) | Marked inactive; the booking list offers only active vehicles |

These come from the demo database on 11 October 2026. Check them again before recording. All 100 demo trips were created within one second, so wallet history and revenue are all on one day. Say so honestly if asked.

## Timed script

| Time | Screen | Do | Say |
| --- | --- | --- | --- |
| 0:00 | Header | Show the sidebar and the demo rider selector | "RideSync has six screens. The browser shows what the database returns. The header lets us pick a demo rider; there is no real login." |
| 0:15 | Browse Data | Riders tab: search "Pant". Vehicles tab: filter by class and active. Trips tab: filter by status. Use Next/Previous. Open one trip's details. | "Searching, filtering and paging all happen in the database. Pages are at most 100 rows." |
| 0:50 | Book a Trip | Select Thomas Pant. Choose an active vehicle. Enter fare `150.00`. Click Review booking, then Confirm booking. | "Fares are exact decimals. The `sp_book_trip` procedure does the booking inside one transaction." |
| 1:15 | Booking result | Point at the balance before and after and the audit entry | "The audit row is the exact one made by the database trigger: ESCROW_HOLD, minus 150." |
| 1:30 | Errors | Book again as Thomas Pant: the app says "Complete this rider's active trip before booking another." Switch to Kala Sahni, fare `100.00`: "This rider does not have enough wallet balance." | "The partial unique index allows one active trip per rider. The wallet can never go below zero. In both cases nothing is charged." |
| 1:55 | Browse, Trips | Open Thomas Pant's new trip. Click Start trip, then Complete trip. Return to Book a Trip and book `80.00` again. | "A trip goes REQUESTED, IN TRANSIT, COMPLETED. Completing releases the held money. It is not a refund. Now the rider can book again." |
| 2:30 | Wallet Audit | Thomas Pant. Show rows, opening and current balance. Set a start date later than today, then clear it. | "Each row stores the balance after the change. A later start date shows no rows, but still shows the opening balance." |
| 3:00 | Vehicle Analytics | Choose `TS07RZ3369201`. Show the chart, then the ranking table (point at equal ranks) and the lifetime totals. Click Refresh totals and show the new time. | "The average covers seven calendar days, including days with no trips. Equal averages share a rank. Totals come from a materialized view, which only changes when we refresh it." |
| 3:30 | Nearby Vehicles | Click Find vehicles for the default origin. Change the longitude or latitude slightly and search again. Click Refresh positions. | "MongoDB `geoNear` finds pings within 5 km. We only trust each vehicle's newest ping. The map polls while the page is visible." |
| 4:00 | Trip Reviews | Show the average, the distribution and the tags. Pick a vehicle. Show its features and inspection records. | "The summary comes from a Mongo `$facet` query. Vehicle metadata is flexible, so only real fields are shown." |
| 4:30 | Phone layout | In Chrome DevTools (Cmd+Option+I), turn on the device toolbar and choose a 390 px wide phone. Open the menu and show the wallet table scrolling sideways. | "On a phone the menu collapses and tables scroll sideways." |
| 4:45 | End | Return to the full window | "That is RideSync. The code, tests and documentation are in the repository." |

If something fails on camera, stop, restore from a fresh copy (step 1 with a new number) and start again. Do not edit the video to hide a failure.

## After the take

Stop both servers with Ctrl+C. The copy `ridesync_team10_take1` may be dropped with `dropdb` once you are done. Check the name first, so you only drop your own copy.
