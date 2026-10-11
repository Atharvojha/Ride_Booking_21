-- Extend the inherited window query to include days with no completed trips.
CREATE OR REPLACE FUNCTION api_vehicle_revenue(p_from DATE, p_to DATE)
RETURNS TABLE (
    vehicle_id UUID, license_plate VARCHAR, revenue_date DATE,
    daily_revenue NUMERIC, moving_average NUMERIC, revenue_rank BIGINT
)
LANGUAGE sql STABLE AS $$
WITH days AS (
    SELECT p_from - 6 + n AS day
    FROM generate_series(0, p_to - p_from + 6) AS n
), daily AS (
    SELECT t.vehicle_id, (t.created_at AT TIME ZONE 'Asia/Kolkata')::date AS day,
           SUM(t.fare_amount) AS fare
    FROM trips t
    WHERE t.status = 'COMPLETED'
      AND t.created_at >= ((p_from - 6)::timestamp AT TIME ZONE 'Asia/Kolkata')
      AND t.created_at < ((p_to + 1)::timestamp AT TIME ZONE 'Asia/Kolkata')
    GROUP BY t.vehicle_id, (t.created_at AT TIME ZONE 'Asia/Kolkata')::date
), averages AS (
    SELECT v.id, v.license_plate, d.day, COALESCE(r.fare, 0) AS fare,
           AVG(COALESCE(r.fare, 0)) OVER (
               PARTITION BY v.id ORDER BY d.day
               ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
           ) AS average
    FROM vehicles v CROSS JOIN days d
    LEFT JOIN daily r ON r.vehicle_id = v.id AND r.day = d.day
), ranked AS (
    SELECT a.*, DENSE_RANK() OVER (PARTITION BY a.day ORDER BY a.average DESC) AS rank
    FROM averages a
)
SELECT r.id, r.license_plate, r.day, r.fare, ROUND(r.average, 2), r.rank
FROM ranked r WHERE r.day >= p_from;
$$;
