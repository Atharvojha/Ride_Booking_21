// Run with mongosh --file mongo/02_workflow_geonear.js.
use(process.env.MONGO_DB || "ridesync_mongo");


function findNearestVehicle(
    longitude,
    latitude,
    maxDistanceMeters = 5000
) {
    const rider_location = {
        type: "Point",
        coordinates: [longitude, latitude]
    };

    const result = db.TelemetryPings.aggregate([
        {
            $geoNear: {
                near: rider_location,
                key: "location",
                distanceField: "distance_meters",
                maxDistance: maxDistanceMeters,
                spherical: true,
                query: {
                    is_available: true
                }
            }
        },
        {
            $limit: 1
        }
    ]).toArray();

    return result.length > 0 ? result[0] : null;
}

// The inherited telemetry seeder generates points around Hyderabad.
printjson(findNearestVehicle(
    Number(process.env.ORIGIN_LONGITUDE || 78.4867),
    Number(process.env.ORIGIN_LATITUDE || 17.3850)
));
