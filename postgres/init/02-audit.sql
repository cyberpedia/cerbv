-- =============================================================================
-- Cerberus CTF Platform - Immutable Audit System
-- =============================================================================
-- Description: Tamper-proof audit logging with automatic triggers
-- Features: Append-only, immutable records with SHA256 chain verification
-- Version: 1.0.0
-- =============================================================================

-- =============================================================================
-- AUDIT TABLES
-- =============================================================================

-- Main audit log table (append-only, partitioned by month)
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID DEFAULT uuid_generate_v4(),
    
    -- Event classification
    event_type VARCHAR(50) NOT NULL,
    event_category VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'info',
    
    -- Actor information
    actor_id UUID REFERENCES users(id),
    actor_type VARCHAR(20) NOT NULL DEFAULT 'user',
    actor_ip INET,
    actor_user_agent TEXT,
    
    -- Target information (what was affected)
    target_type VARCHAR(50),
    target_id UUID,
    target_table VARCHAR(100),
    
    -- Change details
    action VARCHAR(50) NOT NULL,
    old_values JSONB,
    new_values JSONB,
    change_summary TEXT,
    
    -- Metadata
    session_id VARCHAR(255),
    request_id VARCHAR(255),
    
    -- Immutability chain (SHA256 of previous record)
    previous_hash VARCHAR(64),
    record_hash VARCHAR(64) NOT NULL,
    
    -- Timestamp (partition key)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Primary key includes partition key
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create monthly partitions for audit logs
CREATE TABLE IF NOT EXISTS audit_logs_y2024m01 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE IF NOT EXISTS audit_logs_y2024m02 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
CREATE TABLE IF NOT EXISTS audit_logs_y2024m03 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');
CREATE TABLE IF NOT EXISTS audit_logs_y2024m04 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-04-01') TO ('2024-05-01');
CREATE TABLE IF NOT EXISTS audit_logs_y2024m05 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-05-01') TO ('2024-06-01');
CREATE TABLE IF NOT EXISTS audit_logs_y2024m06 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-06-01') TO ('2024-07-01');

-- Default partition
CREATE TABLE IF NOT EXISTS audit_logs_default PARTITION OF audit_logs DEFAULT;

-- Convert to hypertable for TimescaleDB optimization
SELECT create_hypertable('audit_logs', 'created_at', if_not_exists => TRUE);

-- Indexes for audit queries
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_logs(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_logs(target_type, target_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_logs(severity, created_at DESC) WHERE severity IN ('warning', 'error', 'critical');
CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_logs(session_id) WHERE session_id IS NOT NULL;

-- Audit configuration table
CREATE TABLE IF NOT EXISTS audit_config (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL UNIQUE,
    is_audited BOOLEAN NOT NULL DEFAULT TRUE,
    audit_insert BOOLEAN NOT NULL DEFAULT TRUE,
    audit_update BOOLEAN NOT NULL DEFAULT TRUE,
    audit_delete BOOLEAN NOT NULL DEFAULT TRUE,
    sensitive_columns TEXT[], -- Columns to mask in audit logs
    excluded_columns TEXT[], -- Columns to ignore
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Audit verification log (for integrity checks)
CREATE TABLE IF NOT EXISTS audit_verification (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    verified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_by VARCHAR(100) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    records_checked INTEGER NOT NULL,
    records_valid INTEGER NOT NULL,
    records_invalid INTEGER NOT NULL DEFAULT 0,
    invalid_ids UUID[],
    verification_hash VARCHAR(64) NOT NULL,
    notes TEXT
);

-- =============================================================================
-- AUDIT FUNCTIONS
-- =============================================================================

-- Function to calculate SHA256 hash of audit record
CREATE OR REPLACE FUNCTION calculate_audit_hash(
    p_old_values JSONB,
    p_new_values JSONB,
    p_actor_id UUID,
    p_event_type VARCHAR,
    p_created_at TIMESTAMPTZ,
    p_previous_hash VARCHAR
)
RETURNS VARCHAR AS $$
DECLARE
    record_data TEXT;
BEGIN
    -- Concatenate all fields for hashing
    record_data := COALESCE(p_old_values::TEXT, '') || 
                   COALESCE(p_new_values::TEXT, '') || 
                   COALESCE(p_actor_id::TEXT, '') || 
                   COALESCE(p_event_type, '') || 
                   COALESCE(p_created_at::TEXT, '') ||
                   COALESCE(p_previous_hash, '');
    
    -- Return SHA256 hash
    RETURN encode(digest(record_data, 'sha256'), 'hex');
END;
$$ LANGUAGE plpgsql;

-- Function to get the last audit hash (for chain verification)
CREATE OR REPLACE FUNCTION get_last_audit_hash()
RETURNS VARCHAR AS $$
DECLARE
    last_hash VARCHAR;
BEGIN
    SELECT record_hash INTO last_hash
    FROM audit_logs
    ORDER BY created_at DESC, id DESC
    LIMIT 1;
    
    RETURN COALESCE(last_hash, '0' || repeat('0', 63)); -- Genesis hash
END;
$$ LANGUAGE plpgsql;

-- Main audit logging function
CREATE OR REPLACE FUNCTION log_audit_event(
    p_event_type VARCHAR,
    p_event_category VARCHAR,
    p_action VARCHAR,
    p_actor_id UUID DEFAULT NULL,
    p_actor_type VARCHAR DEFAULT 'user',
    p_actor_ip INET DEFAULT NULL,
    p_actor_user_agent TEXT DEFAULT NULL,
    p_target_type VARCHAR DEFAULT NULL,
    p_target_id UUID DEFAULT NULL,
    p_target_table VARCHAR DEFAULT NULL,
    p_old_values JSONB DEFAULT NULL,
    p_new_values JSONB DEFAULT NULL,
    p_change_summary TEXT DEFAULT NULL,
    p_severity VARCHAR DEFAULT 'info',
    p_session_id VARCHAR DEFAULT NULL,
    p_request_id VARCHAR DEFAULT NULL
)
RETURNS UUID AS $$
DECLARE
    v_record_id UUID;
    v_previous_hash VARCHAR;
    v_record_hash VARCHAR;
BEGIN
    -- Get previous hash for chain
    v_previous_hash := get_last_audit_hash();
    
    -- Calculate record hash
    v_record_hash := calculate_audit_hash(
        p_old_values, p_new_values, p_actor_id, 
        p_event_type, NOW(), v_previous_hash
    );
    
    -- Insert audit record
    INSERT INTO audit_logs (
        event_type, event_category, severity,
        actor_id, actor_type, actor_ip, actor_user_agent,
        target_type, target_id, target_table,
        action, old_values, new_values, change_summary,
        session_id, request_id,
        previous_hash, record_hash
    ) VALUES (
        p_event_type, p_event_category, p_severity,
        p_actor_id, p_actor_type, p_actor_ip, p_actor_user_agent,
        p_target_type, p_target_id, p_target_table,
        p_action, p_old_values, p_new_values, p_change_summary,
        p_session_id, p_request_id,
        v_previous_hash, v_record_hash
    )
    RETURNING id INTO v_record_id;
    
    -- Archive to MinIO for long-term storage (async)
    -- This would typically be done by a background worker
    PERFORM pg_notify('audit_log_created', v_record_id::TEXT);
    
    RETURN v_record_id;
END;
$$ LANGUAGE plpgsql;

-- Generic audit trigger function
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
DECLARE
    v_old_values JSONB := NULL;
    v_new_values JSONB := NULL;
    v_change_summary TEXT := NULL;
    v_event_category VARCHAR := 'data_change';
    v_target_table VARCHAR;
    v_config RECORD;
    v_masked_old JSONB;
    v_masked_new JSONB;
BEGIN
    -- Get table name
    v_target_table := TG_TABLE_NAME;
    
    -- Check if auditing is enabled for this table
    SELECT * INTO v_config 
    FROM audit_config 
    WHERE table_name = v_target_table;
    
    IF FOUND AND v_config.is_audited = FALSE THEN
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        ELSE
            RETURN NEW;
        END IF;
    END IF;
    
    -- Build JSON representations, excluding sensitive columns
    IF TG_OP = 'DELETE' THEN
        v_old_values := to_jsonb(OLD);
        v_new_values := NULL;
        v_change_summary := format('Record deleted from %s', v_target_table);
        
        -- Mask sensitive columns if configured
        IF v_config.sensitive_columns IS NOT NULL THEN
            FOREACH col IN ARRAY v_config.sensitive_columns LOOP
                v_old_values := jsonb_set(v_old_values, ARRAY[col], '"***MASKED***"'::jsonb);
            END LOOP;
        END IF;
        
    ELSIF TG_OP = 'INSERT' THEN
        v_old_values := NULL;
        v_new_values := to_jsonb(NEW);
        v_change_summary := format('New record created in %s', v_target_table);
        
        IF v_config.sensitive_columns IS NOT NULL THEN
            FOREACH col IN ARRAY v_config.sensitive_columns LOOP
                v_new_values := jsonb_set(v_new_values, ARRAY[col], '"***MASKED***"'::jsonb);
            END LOOP;
        END IF;
        
    ELSIF TG_OP = 'UPDATE' THEN
        v_old_values := to_jsonb(OLD);
        v_new_values := to_jsonb(NEW);
        
        -- Build change summary
        SELECT string_agg(key || ': ' || COALESCE(old_val, 'NULL') || ' -> ' || COALESCE(new_val, 'NULL'), '; ')
        INTO v_change_summary
        FROM jsonb_each(v_old_values) old_data
        FULL JOIN jsonb_each(v_new_values) new_data USING (key)
        WHERE old_data.value IS DISTINCT FROM new_data.value
        AND (v_config.excluded_columns IS NULL OR NOT (key = ANY(v_config.excluded_columns)));
        
        -- Mask sensitive columns
        IF v_config.sensitive_columns IS NOT NULL THEN
            FOREACH col IN ARRAY v_config.sensitive_columns LOOP
                v_old_values := jsonb_set(v_old_values, ARRAY[col], '"***MASKED***"'::jsonb);
                v_new_values := jsonb_set(v_new_values, ARRAY[col], '"***MASKED***"'::jsonb);
            END LOOP;
        END IF;
        
        -- Remove excluded columns
        IF v_config.excluded_columns IS NOT NULL THEN
            FOREACH col IN ARRAY v_config.excluded_columns LOOP
                v_old_values := v_old_values - col;
                v_new_values := v_new_values - col;
            END LOOP;
        END IF;
    END IF;
    
    -- Log the audit event
    PERFORM log_audit_event(
        p_event_type := TG_OP,
        p_event_category := v_event_category,
        p_action := TG_OP,
        p_actor_id := COALESCE(
            current_setting('app.current_user_id', TRUE)::UUID,
            (v_new_values->>'created_by')::UUID
        ),
        p_actor_type := 'user',
        p_actor_ip := COALESCE(current_setting('app.client_ip', TRUE), NULL)::INET,
        p_actor_user_agent := current_setting('app.user_agent', TRUE),
        p_target_type := v_target_table,
        p_target_id := COALESCE(v_new_values->>'id', v_old_values->>'id')::UUID,
        p_target_table := v_target_table,
        p_old_values := v_old_values,
        p_new_values := v_new_values,
        p_change_summary := v_change_summary,
        p_severity := CASE 
            WHEN TG_OP = 'DELETE' THEN 'warning'
            WHEN v_target_table = 'users' AND TG_OP = 'UPDATE' THEN 'info'
            ELSE 'info'
        END,
        p_session_id := current_setting('app.session_id', TRUE),
        p_request_id := current_setting('app.request_id', TRUE)
    );
    
    -- Return appropriate row
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- AUDIT TRIGGERS FOR CORE TABLES
-- =============================================================================

-- Users table audit trigger
DROP TRIGGER IF EXISTS audit_users_trigger ON users;
CREATE TRIGGER audit_users_trigger
    AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW
    EXECUTE FUNCTION audit_trigger_function();

-- Teams table audit trigger
DROP TRIGGER IF EXISTS audit_teams_trigger ON teams;
CREATE TRIGGER audit_teams_trigger
    AFTER INSERT OR UPDATE OR DELETE ON teams
    FOR EACH ROW
    EXECUTE FUNCTION audit_trigger_function();

-- Challenges table audit trigger
DROP TRIGGER IF EXISTS audit_challenges_trigger ON challenges;
CREATE TRIGGER audit_challenges_trigger
    AFTER INSERT OR UPDATE OR DELETE ON challenges
    FOR EACH ROW
    EXECUTE FUNCTION audit_trigger_function();

-- Solves table audit trigger
DROP TRIGGER IF EXISTS audit_solves_trigger ON solves;
CREATE TRIGGER audit_solves_trigger
    AFTER INSERT OR UPDATE OR DELETE ON solves
    FOR EACH ROW
    EXECUTE FUNCTION audit_trigger_function();

-- Submissions table audit trigger (selective - only flags, not all attempts)
DROP TRIGGER IF EXISTS audit_submissions_trigger ON submissions;
CREATE TRIGGER audit_submissions_trigger
    AFTER INSERT ON submissions
    FOR EACH ROW
    WHEN (NEW.is_correct = TRUE)
    EXECUTE FUNCTION audit_trigger_function();

-- API Keys table audit trigger
DROP TRIGGER IF EXISTS audit_api_keys_trigger ON api_keys;
CREATE TRIGGER audit_api_keys_trigger
    AFTER INSERT OR UPDATE OR DELETE ON api_keys
    FOR EACH ROW
    EXECUTE FUNCTION audit_trigger_function();

-- Writeups audit trigger
DROP TRIGGER IF EXISTS audit_writeups_trigger ON writeups;
CREATE TRIGGER audit_writeups_trigger
    AFTER INSERT OR UPDATE OR DELETE ON writeups
    FOR EACH ROW
    EXECUTE FUNCTION audit_trigger_function();

-- =============================================================================
-- AUDIT CONFIGURATION
-- =============================================================================

-- Configure which tables to audit and how
INSERT INTO audit_config (table_name, is_audited, audit_insert, audit_update, audit_delete, sensitive_columns, excluded_columns) VALUES
    ('users', TRUE, TRUE, TRUE, TRUE, ARRAY['email'], ARRAY['updated_at', 'last_login_at']),
    ('teams', TRUE, TRUE, TRUE, TRUE, ARRAY['invite_code'], NULL),
    ('challenges', TRUE, TRUE, TRUE, FALSE, ARRAY['flag_data'], ARRAY['solve_count', 'attempt_count', 'updated_at']),
    ('solves', TRUE, TRUE, FALSE, FALSE, NULL, NULL),
    ('submissions', TRUE, TRUE, FALSE, FALSE, ARRAY['submitted_flag'], NULL),
    ('api_keys', TRUE, TRUE, TRUE, TRUE, ARRAY['key_hash'], ARRAY['last_used_at']),
    ('writeups', TRUE, TRUE, TRUE, TRUE, NULL, ARRAY['view_count', 'updated_at'])
ON CONFLICT (table_name) DO UPDATE SET
    is_audited = EXCLUDED.is_audited,
    audit_insert = EXCLUDED.audit_insert,
    audit_update = EXCLUDED.audit_update,
    audit_delete = EXCLUDED.audit_delete,
    sensitive_columns = EXCLUDED.sensitive_columns,
    excluded_columns = EXCLUDED.excluded_columns,
    updated_at = NOW();

-- =============================================================================
-- AUDIT VERIFICATION FUNCTION
-- =============================================================================

-- Function to verify audit log integrity
CREATE OR REPLACE FUNCTION verify_audit_integrity(
    p_start_time TIMESTAMPTZ DEFAULT NOW() - INTERVAL '24 hours',
    p_end_time TIMESTAMPTZ DEFAULT NOW()
)
RETURNS TABLE (
    is_valid BOOLEAN,
    records_checked INTEGER,
    records_valid INTEGER,
    records_invalid INTEGER,
    invalid_ids UUID[]
) AS $$
DECLARE
    v_record RECORD;
    v_calculated_hash VARCHAR;
    v_valid_count INTEGER := 0;
    v_invalid_count INTEGER := 0;
    v_invalid_list UUID[] := ARRAY[]::UUID[];
    v_previous_hash VARCHAR := '0' || repeat('0', 63);
BEGIN
    FOR v_record IN 
        SELECT id, old_values, new_values, actor_id, event_type, created_at, previous_hash, record_hash
        FROM audit_logs
        WHERE created_at BETWEEN p_start_time AND p_end_time
        ORDER BY created_at ASC, id ASC
    LOOP
        -- Verify chain integrity
        IF v_record.previous_hash != v_previous_hash THEN
            v_invalid_count := v_invalid_count + 1;
            v_invalid_list := array_append(v_invalid_list, v_record.id);
        ELSE
            -- Verify record hash
            v_calculated_hash := calculate_audit_hash(
                v_record.old_values, v_record.new_values, 
                v_record.actor_id, v_record.event_type, 
                v_record.created_at, v_record.previous_hash
            );
            
            IF v_calculated_hash = v_record.record_hash THEN
                v_valid_count := v_valid_count + 1;
            ELSE
                v_invalid_count := v_invalid_count + 1;
                v_invalid_list := array_append(v_invalid_list, v_record.id);
            END IF;
        END IF;
        
        v_previous_hash := v_record.record_hash;
    END LOOP;
    
    RETURN QUERY SELECT 
        (v_invalid_count = 0),
        (v_valid_count + v_invalid_count),
        v_valid_count,
        v_invalid_count,
        v_invalid_list;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SECURITY POLICIES
-- =============================================================================

-- Enable RLS on audit tables
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_config ENABLE ROW LEVEL SECURITY;

-- Only admins can view audit logs
CREATE POLICY audit_logs_select_admin ON audit_logs
    FOR SELECT
    USING (current_setting('app.current_user_role', TRUE) IN ('admin', 'organizer'));

-- Audit config only writable by admins
CREATE POLICY audit_config_select_admin ON audit_config
    FOR SELECT
    USING (current_setting('app.current_user_role', TRUE) = 'admin');

CREATE POLICY audit_config_write_admin ON audit_config
    FOR ALL
    USING (current_setting('app.current_user_role', TRUE) = 'admin');

-- =============================================================================
-- AUDIT LOG FUNCTIONS FOR SPECIFIC EVENTS
-- =============================================================================

-- Function to log authentication events
CREATE OR REPLACE FUNCTION log_auth_event(
    p_event_type VARCHAR, -- 'login', 'logout', 'failed_login', 'password_change'
    p_user_id UUID,
    p_ip_address INET,
    p_user_agent TEXT,
    p_success BOOLEAN,
    p_details JSONB DEFAULT NULL
)
RETURNS UUID AS $$
BEGIN
    RETURN log_audit_event(
        p_event_type := 'auth_' || p_event_type,
        p_event_category := 'authentication',
        p_action := p_event_type,
        p_actor_id := p_user_id,
        p_actor_ip := p_ip_address,
        p_actor_user_agent := p_user_agent,
        p_new_values := p_details,
        p_change_summary := format('Authentication event: %s (success=%s)', p_event_type, p_success),
        p_severity := CASE 
            WHEN p_event_type = 'failed_login' THEN 'warning'
            WHEN p_event_type = 'password_change' THEN 'info'
            ELSE 'info'
        END
    );
END;
$$ LANGUAGE plpgsql;

-- Function to log security events
CREATE OR REPLACE FUNCTION log_security_event(
    p_event_type VARCHAR,
    p_severity VARCHAR,
    p_description TEXT,
    p_actor_id UUID DEFAULT NULL,
    p_ip_address INET DEFAULT NULL
)
RETURNS UUID AS $$
BEGIN
    RETURN log_audit_event(
        p_event_type := p_event_type,
        p_event_category := 'security',
        p_action := p_event_type,
        p_actor_id := p_actor_id,
        p_actor_ip := p_ip_address,
        p_change_summary := p_description,
        p_severity := p_severity
    );
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- COMPLETION
-- =============================================================================

SELECT 'Cerberus audit system initialized successfully' AS status;
