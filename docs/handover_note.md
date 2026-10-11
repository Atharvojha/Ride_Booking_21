# Team 10 handover note

Project P2, RideSync (ride booking). Assignment 2, Front End Design. Team repository: https://github.com/Atharvojha/Ride_Booking_21. Inherited from https://github.com/amaan070/Ride_Booking_21, starting commit `d0d5ad44ba4ab2f566cd965e055870ddd7e95697`. All 23 inherited commits are kept with their original authors. The day-by-day record is in [handover_history.md](handover_history.md); it still contains old "pending" statements because it records the time they were written.

## What worked

All six SQL scripts ran on PostgreSQL 17. With the original seeders on a small dataset, the booking procedure took the fare and the audit trigger wrote the wallet entry. A second active trip and too little money were refused without changing the wallet. A trip moved from REQUESTED to IN TRANSIT to COMPLETED and freed the rider to book again. The materialized view refreshed. In MongoDB, the geospatial index, the two-hour expiry index and the `$facet` review summary worked.

## What did not work, and what we changed

- **Nearby search** did not run under `mongosh`. It is now a runnable function.
- **Metadata index** named the collection with the wrong capital letter, so it indexed nothing. Fixed, and collection setup can now be repeated.
- **Passwords:** one seeder had a password in the code and the other asked for it. Both now read `.env`, which is not committed.
- **Seeder top-ups** only changed a number in memory, so the real wallet and the audit trigger never saw them. They now update the database.
- **Seven-day average** used seven rows, not seven days, so it could reach back weeks. `sql/08_api_revenue.sql` uses calendar days, counts empty days as zero and ranks the whole fleet. The original view is kept.
- **Booking** now checks the fare and the vehicle and returns the exact audit row it caused. Completion locks the wallet before the trip, like booking does. The refresh time is now saved. The README lists every changed file.

## What we built

A FastAPI server (`api/`, inputs and outputs in [api_endpoints.md](api_endpoints.md)) and a React app (`web/`) with the six required screens: Browse Data, Book a Trip, Wallet Audit, Vehicle Analytics, Nearby Vehicles and Trip Reviews. Business rules stay in the databases; the web app does not calculate money or ranks. Users and wireframes are in [design/](design/README.md). Setup is in the [README](../README.md). Tests: 62 API, 23 front-end, 9 browser tests and 75 full-size checks all pass. Full-size results are in [scale_verification.md](scale_verification.md).

## Assumptions

Money is INR. Dates use Asia/Kolkata. There is no real login. Trip statuses are only REQUESTED, IN TRANSIT and COMPLETED, so there is no cancellation or refund. The database has no driver, rider contact or route, so we did not invent them. A ping counts as current for 7,200 seconds, the same as the Mongo expiry.

## Known limits

The 90-day revenue chart takes about 4 seconds at full size because every vehicle is ranked for every day. Nearby search time grows with the number of fresh pings. Pings disappear after two hours, so a demo needs fresh ones (`data_generation/refresh_demo_pings.py`). The seeder gives all trips the same few minutes.

## Suggestions for the original authors

Keep connection settings in a configuration file and document the order for seeding and refreshing views. Test failures as well as successful bookings. Explain how the moving average and a vehicle's "current" position are decided. Say how procedure failures are reported (completion only prints a notice).
