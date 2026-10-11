DROP TRIGGER IF EXISTS trg_wallet_audit ON riders;
DROP FUNCTION IF EXISTS fn_wallet_audit_log();

CREATE OR REPLACE FUNCTION fn_wallet_audit_log()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_action_type    VARCHAR(30);
    v_amount_changed DECIMAL(10,2);
    v_audit_id UUID;
BEGIN

    v_amount_changed := NEW.wallet_balance - OLD.wallet_balance;

    v_action_type := NULLIF(current_setting('ridesync.wallet_action', true), '');

    IF v_action_type IS NULL THEN
        IF v_amount_changed >= 0 THEN
            v_action_type := 'CREDIT';
        ELSE
            v_action_type := 'DEBIT';
        END IF;
    END IF;

    INSERT INTO wallet_audit_logs (rider_id, amount_changed, action_type, balance_after, "timestamp")
    VALUES (NEW.id, v_amount_changed, v_action_type, NEW.wallet_balance, clock_timestamp())
    RETURNING id INTO v_audit_id;

    -- The booking procedure reads this ID before it commits.
    PERFORM set_config('ridesync.wallet_audit_id', v_audit_id::text, true);


    RETURN NEW;
END;
$$;


CREATE TRIGGER trg_wallet_audit
AFTER UPDATE OF wallet_balance ON riders
FOR EACH ROW

WHEN (OLD.wallet_balance IS DISTINCT FROM NEW.wallet_balance)
EXECUTE FUNCTION fn_wallet_audit_log();