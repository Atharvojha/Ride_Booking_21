CREATE TABLE IF NOT EXISTS api_refresh_state (
    name TEXT PRIMARY KEY,
    last_refreshed_at TIMESTAMPTZ
);
INSERT INTO api_refresh_state(name) VALUES ('vehicle_lifetime_stats')
ON CONFLICT (name) DO NOTHING;

CREATE OR REPLACE FUNCTION refresh_mv_vehicle_lifetime_stats()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    -- One refresh at a time, including calls made outside the API.
    IF NOT pg_try_advisory_xact_lock(10, 6302) THEN
        RAISE EXCEPTION 'A vehicle summary refresh is already running'
            USING ERRCODE = '55P03';
    END IF;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_vehicle_lifetime_stats;
    UPDATE api_refresh_state SET last_refreshed_at = clock_timestamp()
    WHERE name = 'vehicle_lifetime_stats';
END;
$$;
