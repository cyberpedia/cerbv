-- Cerberus CTF Platform - PostgreSQL Initialization
-- Run on first cluster initialization

-- Create cerberus database and user
CREATE USER cerberus WITH PASSWORD '${DB_PASSWORD}';
CREATE DATABASE cerberus OWNER cerberus;
GRANT ALL PRIVILEGES ON DATABASE cerberus TO cerberus;

-- Connect to cerberus database
\c cerberus

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "hstore";

-- Create schemas
CREATE SCHEMA IF NOT EXISTS public;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS analytics;

-- Set default privileges
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO cerberus;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO cerberus;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO cerberus;

-- Create audit logging table
CREATE TABLE IF NOT EXISTS audit.logs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id UUID,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(255),
    details JSONB,
    ip_address INET
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit.logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit.logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit.logs(action);

-- Create performance monitoring view
CREATE OR REPLACE VIEW analytics.performance_metrics AS
SELECT
    schemaname,
    relname AS table_name,
    seq_scan,
    seq_tup_read,
    idx_scan,
    idx_tup_fetch,
    n_tup_ins,
    n_tup_upd,
    n_tup_del,
    n_live_tup,
    n_dead_tup,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze
FROM pg_stat_user_tables
ORDER BY seq_scan DESC;

-- Create replication status view
CREATE OR REPLACE VIEW analytics.replication_status AS
SELECT
    client_addr,
    state,
    sync_state,
    sent_lsn,
    write_lsn,
    flush_lsn,
    replay_lsn,
    write_lag,
    flush_lag,
    replay_lag,
    pid
FROM pg_stat_replication;

-- Function to get database size
CREATE OR REPLACE FUNCTION analytics.database_size()
RETURNS TABLE (
    database_name NAME,
    size_bytes BIGINT,
    size_human TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        datname::NAME,
        pg_database_size(datname),
        CASE
            WHEN pg_database_size(datname) > 1024^3 THEN (pg_database_size(datname) / 1024^3)::TEXT || ' GB'
            WHEN pg_database_size(datname) > 1024^2 THEN (pg_database_size(datname) / 1024^2)::TEXT || ' MB'
            ELSE (pg_database_size(datname) / 1024)::TEXT || ' KB'
        END
    FROM pg_database
    WHERE datname = current_database();
END;
$$ LANGUAGE plpgsql;

-- Function to get active connections
CREATE OR REPLACE FUNCTION analytics.active_connections()
RETURNS TABLE (
    state TEXT,
    count BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        state,
        COUNT(*)::BIGINT
    FROM pg_stat_activity
    WHERE datname = current_database()
    GROUP BY state;
END;
$$ LANGUAGE plpgsql;

-- Set up row-level security
ALTER TABLE audit.logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_logs_select_policy ON audit.logs
    FOR SELECT
    USING (true);  -- Adjust based on your RBAC requirements

CREATE POLICY audit_logs_insert_policy ON audit.logs
    FOR INSERT
    WITH CHECK (true);  -- Application should control insert permissions

-- Grant permissions
GRANT USAGE ON SCHEMA audit TO cerberus;
GRANT USAGE ON SCHEMA analytics TO cerberus;
GRANT SELECT ON audit.logs TO cerberus;
GRANT SELECT ON analytics.performance_metrics TO cerberus;
GRANT SELECT ON analytics.replication_status TO cerberus;
GRANT EXECUTE ON FUNCTION analytics.database_size() TO cerberus;
GRANT EXECUTE ON FUNCTION analytics.active_connections() TO cerberus;

-- Create a function to log actions (for application use)
CREATE OR REPLACE FUNCTION audit.log_action(
    p_action VARCHAR,
    p_resource_type VARCHAR,
    p_resource_id VARCHAR,
    p_details JSONB DEFAULT '{}'::JSONB
) RETURNS BIGINT AS $$
DECLARE
    v_log_id BIGINT;
    v_user_id UUID;
BEGIN
    -- Get current user ID if available
    -- This depends on your session management
    -- v_user_id := auth.uid();
    
    INSERT INTO audit.logs (user_id, action, resource_type, resource_id, details, ip_address)
    VALUES (v_user_id, p_action, p_resource_type, p_resource_id, p_details, inet_client_addr())
    RETURNING id INTO v_log_id;
    
    RETURN v_log_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Comment on created objects
COMMENT ON TABLE audit.logs IS 'Centralized audit logging for GDPR compliance';
COMMENT ON FUNCTION audit.log_action IS 'Log an action for audit trail (GDPR Article 30)';
COMMENT ON SCHEMA analytics IS 'Analytics and monitoring views';
