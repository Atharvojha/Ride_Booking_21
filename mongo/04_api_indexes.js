use(process.env.MONGO_DB || "ridesync_mongo");

// Look up the latest ping for a vehicle without scanning its whole history.
db.TelemetryPings.createIndex({vehicle_id: 1, created_at: -1, _id: -1});
// Support review filters and stable page order.
db.TripReviews.createIndex({vehicle_id: 1, created_at: -1, _id: -1});
db.TripReviews.createIndex({created_at: -1, _id: -1});
