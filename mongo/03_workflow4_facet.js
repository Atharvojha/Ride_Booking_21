use(process.env.MONGO_DB || "ridesync_mongo");


const result = db.TripReviews.aggregate([
    {
        $facet: {
            ratingStats: [
                {
                    $group: {
                        _id: "$rating",
                        count: { $sum: 1 }
                    }
                },
                { $sort: { _id: 1 } }
            ],

            averageRating: [
                {
                    $group: {
                        _id: null,
                        avgRating: { $avg: "$rating" },
                        totalReviews: { $sum: 1 }
                    }
                },
                { $project: { _id: 0, avgRating: { $round: ["$avgRating", 2] }, totalReviews: 1 } }
            ],

        
            topFeedbackTags: [
                { $unwind: "$feedback_tags" },
                {
                    $group: {
                        _id: "$feedback_tags",
                        count: { $sum: 1 }
                    }
                },
                { $sort: { count: -1 } },
                { $limit: 10 }
            ]
        }
    }
]).toArray();

printjson(result);
