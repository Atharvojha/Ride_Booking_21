DROP PROCEDURE IF EXISTS sp_book_trip(UUID, UUID, DECIMAL, UUID, TEXT, UUID);
DROP PROCEDURE IF EXISTS sp_book_trip(UUID, UUID, DECIMAL, UUID, TEXT);

CREATE OR REPLACE PROCEDURE sp_book_trip(
    IN p_rider_id UUID,
    IN p_vehicle_id UUID,
    IN p_fare_amount DECIMAL(10,2),
    OUT p_trip_id UUID,
    OUT p_status TEXT,
    OUT p_audit_id UUID
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_trip_id UUID;
    v_audit_id UUID;
    v_vehicle_active BOOLEAN;
    v_failed BOOLEAN := false;
    v_error_code TEXT;
    v_constraint TEXT;
BEGIN
    PERFORM set_config('ridesync.wallet_action', 'ESCROW_HOLD', true);
    PERFORM set_config('ridesync.wallet_audit_id', '', true);

    BEGIN
        IF p_fare_amount IS NULL OR p_fare_amount <= 0
           OR p_fare_amount > 99999999.99
           OR p_fare_amount <> ROUND(p_fare_amount, 2) THEN
            RAISE EXCEPTION 'INVALID_INPUT';
        END IF;

        -- Keep the vehicle active until this booking has finished.
        SELECT is_active INTO v_vehicle_active
        FROM vehicles WHERE id = p_vehicle_id FOR SHARE;
        IF NOT FOUND THEN
            RAISE no_data_found;
        END IF;
        IF NOT v_vehicle_active THEN
            RAISE EXCEPTION 'VEHICLE_INACTIVE';
        END IF;

        UPDATE riders SET wallet_balance = wallet_balance - p_fare_amount
        WHERE id = p_rider_id;
        IF NOT FOUND THEN
            RAISE no_data_found;
        END IF;
        v_audit_id := NULLIF(current_setting('ridesync.wallet_audit_id', true), '')::UUID;
        IF v_audit_id IS NULL THEN
            RAISE EXCEPTION 'Wallet audit trigger did not return an ID';
        END IF;

        INSERT INTO trips (rider_id, vehicle_id, fare_amount, status)
        VALUES (p_rider_id, p_vehicle_id, p_fare_amount, 'REQUESTED')
        RETURNING id INTO v_trip_id;
    EXCEPTION
        WHEN check_violation THEN
            GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
            v_failed := true;
            v_error_code := CASE WHEN v_constraint = 'riders_wallet_balance_nonnegative'
                THEN 'INSUFFICIENT_BALANCE' ELSE 'INVALID_INPUT' END;
        WHEN unique_violation THEN
            GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
            v_failed := true;
            v_error_code := CASE WHEN v_constraint = 'idx_one_active_trip_per_rider'
                THEN 'ACTIVE_TRIP_EXISTS' ELSE 'INTERNAL_ERROR' END;
        WHEN no_data_found THEN
            v_failed := true;
            v_error_code := 'NOT_FOUND';
        WHEN OTHERS THEN
            v_failed := true;
            v_error_code := CASE WHEN SQLERRM IN ('INVALID_INPUT', 'VEHICLE_INACTIVE')
                THEN SQLERRM ELSE 'INTERNAL_ERROR' END;
            IF v_error_code = 'INTERNAL_ERROR' THEN
                RAISE WARNING 'sp_book_trip failed: %', SQLERRM;
            END IF;
    END;

    IF v_failed THEN
        ROLLBACK;
        p_trip_id := NULL;
        p_audit_id := NULL;
        p_status := 'FAILED: ' || v_error_code;
    ELSE
        COMMIT;
        p_trip_id := v_trip_id;
        p_audit_id := v_audit_id;
        p_status := 'BOOKED';
    END IF;
END;
$$;

DROP PROCEDURE IF EXISTS sp_release_escrow(UUID);


CREATE OR REPLACE PROCEDURE sp_release_escrow(
    IN p_trip_id UUID
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_rider_id  UUID;
    v_balance   NUMERIC;
    v_failed    BOOLEAN := false;
    v_error_msg TEXT;
BEGIN
    PERFORM set_config('ridesync.wallet_action', 'ESCROW_RELEASE', true);
    BEGIN
        SELECT rider_id INTO v_rider_id FROM trips WHERE id = p_trip_id;
        IF v_rider_id IS NULL THEN
            RAISE EXCEPTION 'Trip % not found or not IN TRANSIT', p_trip_id
                USING ERRCODE = 'no_data_found';
        END IF;

        -- Lock the wallet before the trip, in the same order as booking.
        SELECT wallet_balance INTO STRICT v_balance
        FROM riders WHERE id = v_rider_id FOR UPDATE;

        UPDATE trips
           SET status = 'COMPLETED'
         WHERE id = p_trip_id
           AND status = 'IN TRANSIT'
        RETURNING rider_id INTO v_rider_id;

        IF v_rider_id IS NULL THEN
            RAISE EXCEPTION 'Trip % not found or not IN TRANSIT', p_trip_id
                USING ERRCODE = 'no_data_found';
        END IF;

        INSERT INTO wallet_audit_logs (rider_id, amount_changed, action_type, balance_after, "timestamp")
        VALUES (v_rider_id, 0.00, 'ESCROW_RELEASE', v_balance, clock_timestamp());

    EXCEPTION
        WHEN OTHERS THEN
            v_failed    := true;
            v_error_msg := SQLERRM;
    END;

    IF v_failed THEN
        ROLLBACK;
        RAISE NOTICE 'sp_release_escrow failed: %', v_error_msg;
    ELSE
        COMMIT;
    END IF;
END;
$$;