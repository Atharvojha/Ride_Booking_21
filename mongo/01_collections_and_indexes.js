use(process.env.MONGO_DB || "ridesync_mongo");

for (const name of ["VehicleMetadata", "TripReviews", "TelemetryPings"]) {
    if (!db.getCollectionNames().includes(name)) db.createCollection(name);
}

// Geospatial index for finding nearby vehicles
db.TelemetryPings.createIndex({
    location: "2dsphere"
});

// TTL index: automatically delete telemetry data after 2 hours
db.TelemetryPings.createIndex(
    {
        created_at: 1
    },
    {
        expireAfterSeconds: 7200
    }
);

db.VehicleMetadata.createIndex({
    vehicle_id: 1
});
