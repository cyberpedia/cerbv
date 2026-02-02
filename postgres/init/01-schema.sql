-- =============================================================================
-- Cerberus CTF Platform - PostgreSQL 16 Schema with TimescaleDB
-- =============================================================================
-- Description: Complete database schema with RLS, partitioning, and pgcrypto
-- Version: 1.0.0
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "timescaledb";

-- =============================================================================
-- ENUM TYPES
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM ('admin', 'organizer', 'player', 'banned');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'challenge_difficulty') THEN
        CREATE TYPE challenge_difficulty AS ENUM ('easy', 'medium', 'hard', 'insane');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'challenge_category') THEN
        CREATE TYPE challenge_category AS ENUM (
            'web', 'pwn', 'crypto', 'forensics', 'reverse', 'misc', 
            'osint', 'blockchain', 'hardware', 'steganography'
        );
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'solve_status') THEN
        CREATE TYPE solve_status AS ENUM ('pending', 'correct', 'incorrect', 'first_blood');
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'flag_format') THEN
        CREATE TYPE flag_format AS ENUM ('static', 'dynamic', 'regex');
    END IF;
END $$;

-- =============================================================================
-- CORE TABLES
-- =============================================================================

-- Teams table (for team-based CTFs)
CREATE TABLE IF NOT EXISTS teams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    invite_code VARCHAR(64) UNIQUE DEFAULT encode(gen_random_bytes(24), 'base64'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

-- Users table with encrypted sensitive fields
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) NOT NULL UNIQUE,
    email BYTEA NOT NULL, -- Encrypted with pgcrypto
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'player',
    team_id UUID REFERENCES teams(id) ON DELETE SET NULL,
    
    -- Profile fields
    display_name VARCHAR(100),
    country_code CHAR(2),
    bio TEXT,
    avatar_url VARCHAR(500),
    
    -- Security fields
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    two_factor_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    two_factor_secret BYTEA, -- Encrypted
    last_login_at TIMESTAMPTZ,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    
    -- Constraints
    CONSTRAINT username_format CHECK (username ~* '^[a-zA-Z0-9_-]{3,50}$'),
    CONSTRAINT display_name_length CHECK (LENGTH(display_name) <= 100)
);

-- Create index on common queries
CREATE INDEX IF NOT EXISTS idx_users_team ON users(team_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_email_verified ON users(email_verified) WHERE deleted_at IS NULL;

-- Categories table for challenge organization
CREATE TABLE IF NOT EXISTS categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) NOT NULL UNIQUE,
    slug VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    icon VARCHAR(100),
    color VARCHAR(7) DEFAULT '#3B82F6', -- Hex color
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Challenges table
CREATE TABLE IF NOT EXISTS challenges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(200) NOT NULL,
    slug VARCHAR(200) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    
    -- Challenge details
    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE RESTRICT,
    difficulty challenge_difficulty NOT NULL DEFAULT 'medium',
    points INTEGER NOT NULL DEFAULT 100,
    
    -- Flag configuration (encrypted for dynamic flags)
    flag_format flag_format NOT NULL DEFAULT 'static',
    flag_data BYTEA NOT NULL, -- Encrypted flag or flag generation pattern
    flag_case_sensitive BOOLEAN NOT NULL DEFAULT TRUE,
    
    -- Challenge files
    file_urls TEXT[], -- Array of file URLs
    docker_image VARCHAR(255), -- Docker image for hosted challenges
    service_port INTEGER, -- Port for hosted challenges
    
    -- Hints (stored as JSONB for flexibility)
    hints JSONB DEFAULT '[]'::jsonb,
    
    -- Statistics
    solve_count INTEGER NOT NULL DEFAULT 0,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    
    -- Dynamic scoring
    is_dynamic_scoring BOOLEAN NOT NULL DEFAULT FALSE,
    dynamic_score_min INTEGER,
    dynamic_score_decay INTEGER,
    
    -- Status
    is_visible BOOLEAN NOT NULL DEFAULT FALSE,
    release_at TIMESTAMPTZ,
    
    -- Author information
    author_id UUID NOT NULL REFERENCES users(id),
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    
    -- Constraints
    CONSTRAINT points_positive CHECK (points > 0),
    CONSTRAINT dynamic_score_valid CHECK (
        (is_dynamic_scoring = FALSE) OR 
        (dynamic_score_min IS NOT NULL AND dynamic_score_decay IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_challenges_category ON challenges(category_id) WHERE deleted_at IS NULL AND is_visible = TRUE;
CREATE INDEX IF NOT EXISTS idx_challenges_difficulty ON challenges(difficulty) WHERE deleted_at IS NULL AND is_visible = TRUE;
CREATE INDEX IF NOT EXISTS idx_challenges_visible ON challenges(release_at) WHERE deleted_at IS NULL AND is_visible = TRUE;

-- Solves table (partitioned by month)
CREATE TABLE IF NOT EXISTS solves (
    id UUID DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    challenge_id UUID NOT NULL REFERENCES challenges(id),
    team_id UUID REFERENCES teams(id),
    
    -- Submission details
    submitted_flag TEXT NOT NULL,
    status solve_status NOT NULL DEFAULT 'pending',
    points_awarded INTEGER,
    solve_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Metadata
    ip_address INET,
    user_agent TEXT,
    
    -- Primary key includes partition key
    PRIMARY KEY (id, solve_time)
) PARTITION BY RANGE (solve_time);

-- Create monthly partitions (initial set)
CREATE TABLE IF NOT EXISTS solves_y2024m01 PARTITION OF solves
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE IF NOT EXISTS solves_y2024m02 PARTITION OF solves
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
CREATE TABLE IF NOT EXISTS solves_y2024m03 PARTITION OF solves
    FOR VALUES FROM ('2024-03-01') TO ('2024-04-01');

-- Default partition for future dates
CREATE TABLE IF NOT EXISTS solves_default PARTITION OF solves DEFAULT;

-- Indexes for solves
CREATE INDEX IF NOT EXISTS idx_solves_user ON solves(user_id, solve_time DESC);
CREATE INDEX IF NOT EXISTS idx_solves_challenge ON solves(challenge_id, solve_time DESC);
CREATE INDEX IF NOT EXISTS idx_solves_team ON solves(team_id, solve_time DESC) WHERE team_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_solves_status ON solves(status, solve_time DESC);

-- Submissions table (raw submission log for forensic analysis)
CREATE TABLE IF NOT EXISTS submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    challenge_id UUID NOT NULL REFERENCES challenges(id),
    submitted_flag TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    attempt_number INTEGER NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address INET,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_submissions_user_challenge ON submissions(user_id, challenge_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_submissions_time ON submissions(submitted_at DESC);

-- Feature flags for gradual rollouts
CREATE TABLE IF NOT EXISTS feature_flags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Targeting rules (JSONB)
    rules JSONB DEFAULT '{}'::jsonb,
    
    -- Percentage rollout (0-100)
    rollout_percentage INTEGER NOT NULL DEFAULT 0,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT rollout_percentage_range CHECK (rollout_percentage BETWEEN 0 AND 100)
);

-- Announcements table
CREATE TABLE IF NOT EXISTS announcements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    
    -- Visibility
    is_visible BOOLEAN NOT NULL DEFAULT TRUE,
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    
    -- Targeting
    target_roles user_role[] DEFAULT '{}'::user_role[], -- Empty = all roles
    target_categories UUID[], -- Empty = all categories
    
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Write-ups table (user-contributed solutions)
CREATE TABLE IF NOT EXISTS writeups (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    challenge_id UUID NOT NULL REFERENCES challenges(id),
    user_id UUID NOT NULL REFERENCES users(id),
    team_id UUID REFERENCES teams(id),
    
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL, -- Markdown content
    
    -- External links
    external_url VARCHAR(500),
    
    -- Status
    is_approved BOOLEAN NOT NULL DEFAULT FALSE,
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    
    -- Engagement
    view_count INTEGER NOT NULL DEFAULT 0,
    upvote_count INTEGER NOT NULL DEFAULT 0,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    
    CONSTRAINT unique_user_challenge_writeup UNIQUE (challenge_id, user_id)
);

-- API Keys for service accounts
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    
    -- Permissions
    scopes TEXT[] NOT NULL DEFAULT '{}'::text[],
    
    -- Limits
    rate_limit_requests INTEGER DEFAULT 1000, -- per minute
    
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    
    -- Owner
    created_by UUID NOT NULL REFERENCES users(id),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- HYERTABLE CONVERSION (TimescaleDB)
-- =============================================================================

-- Convert audit-related tables to hypertables for time-series optimization
SELECT create_hypertable('submissions', 'submitted_at', if_not_exists => TRUE);

-- =============================================================================
-- VIEWS
-- =============================================================================

-- Leaderboard view (individual)
CREATE OR REPLACE VIEW v_leaderboard AS
SELECT 
    u.id AS user_id,
    u.username,
    u.display_name,
    u.country_code,
    COALESCE(t.name, NULL) AS team_name,
    COUNT(DISTINCT s.challenge_id) AS challenges_solved,
    COALESCE(SUM(s.points_awarded), 0) AS total_points,
    MAX(s.solve_time) AS last_solve_time
FROM users u
LEFT JOIN teams t ON u.team_id = t.id
LEFT JOIN solves s ON u.id = s.user_id AND s.status = 'correct'
WHERE u.deleted_at IS NULL
    AND u.role NOT IN ('admin', 'organizer', 'banned')
GROUP BY u.id, u.username, u.display_name, u.country_code, t.name
ORDER BY total_points DESC, last_solve_time ASC;

-- Team leaderboard view
CREATE OR REPLACE VIEW v_team_leaderboard AS
SELECT 
    t.id AS team_id,
    t.name AS team_name,
    COUNT(DISTINCT s.user_id) AS members_solved,
    COUNT(DISTINCT s.challenge_id) AS challenges_solved,
    COALESCE(SUM(DISTINCT s.points_awarded), 0) AS total_points,
    MAX(s.solve_time) AS last_solve_time
FROM teams t
LEFT JOIN solves s ON t.id = s.team_id AND s.status = 'correct'
WHERE t.deleted_at IS NULL
GROUP BY t.id, t.name
ORDER BY total_points DESC, last_solve_time ASC;

-- Challenge statistics view
CREATE OR REPLACE VIEW v_challenge_stats AS
SELECT 
    c.id AS challenge_id,
    c.title,
    c.slug,
    cat.name AS category_name,
    c.difficulty,
    c.points,
    c.solve_count,
    c.attempt_count,
    CASE 
        WHEN c.attempt_count > 0 
        THEN ROUND((c.solve_count::NUMERIC / c.attempt_count::NUMERIC) * 100, 2)
        ELSE 0 
    END AS solve_rate,
    CASE 
        WHEN c.solve_count > 0 
        THEN COALESCE(
            (SELECT AVG(s.points_awarded) FROM solves s WHERE s.challenge_id = c.id AND s.status = 'correct'),
            c.points
        )
        ELSE c.points 
    END AS avg_points_awarded
FROM challenges c
JOIN categories cat ON c.category_id = cat.id
WHERE c.deleted_at IS NULL;

-- =============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- =============================================================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams ENABLE ROW LEVEL SECURITY;
ALTER TABLE challenges ENABLE ROW LEVEL SECURITY;
ALTER TABLE solves ENABLE ROW LEVEL SECURITY;
ALTER TABLE submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE writeups ENABLE ROW LEVEL SECURITY;

-- Users RLS policies
CREATE POLICY users_select_own ON users
    FOR SELECT
    USING (
        id = current_setting('app.current_user_id', TRUE)::UUID
        OR current_setting('app.current_user_role', TRUE) = 'admin'
    );

CREATE POLICY users_select_public ON users
    FOR SELECT
    USING (
        deleted_at IS NULL
        AND role NOT IN ('banned')
    );

CREATE POLICY users_update_own ON users
    FOR UPDATE
    USING (
        id = current_setting('app.current_user_id', TRUE)::UUID
        OR current_setting('app.current_user_role', TRUE) = 'admin'
    );

-- Teams RLS policies
CREATE POLICY teams_select_all ON teams
    FOR SELECT
    USING (deleted_at IS NULL);

CREATE POLICY teams_insert_admin ON teams
    FOR INSERT
    WITH CHECK (current_setting('app.current_user_role', TRUE) IN ('admin', 'organizer'));

CREATE POLICY teams_update_own ON teams
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM users u 
            WHERE u.team_id = teams.id 
            AND u.id = current_setting('app.current_user_id', TRUE)::UUID
        )
        OR current_setting('app.current_user_role', TRUE) = 'admin'
    );

-- Challenges RLS policies
CREATE POLICY challenges_select_visible ON challenges
    FOR SELECT
    USING (
        is_visible = TRUE
        AND deleted_at IS NULL
        AND (release_at IS NULL OR release_at <= NOW())
        OR current_setting('app.current_user_role', TRUE) IN ('admin', 'organizer')
    );

CREATE POLICY challenges_insert_admin ON challenges
    FOR INSERT
    WITH CHECK (current_setting('app.current_user_role', TRUE) IN ('admin', 'organizer'));

CREATE POLICY challenges_update_admin ON challenges
    FOR UPDATE
    USING (current_setting('app.current_user_role', TRUE) IN ('admin', 'organizer'));

-- Solves RLS policies
CREATE POLICY solves_select_own ON solves
    FOR SELECT
    USING (
        user_id = current_setting('app.current_user_id', TRUE)::UUID
        OR team_id IN (
            SELECT team_id FROM users WHERE id = current_setting('app.current_user_id', TRUE)::UUID
        )
        OR current_setting('app.current_user_role', TRUE) = 'admin'
    );

CREATE POLICY solves_select_correct_public ON solves
    FOR SELECT
    USING (status = 'correct');

-- Submissions RLS policies
CREATE POLICY submissions_select_own ON submissions
    FOR SELECT
    USING (
        user_id = current_setting('app.current_user_id', TRUE)::UUID
        OR current_setting('app.current_user_role', TRUE) = 'admin'
    );

CREATE POLICY submissions_insert_own ON submissions
    FOR INSERT
    WITH CHECK (
        user_id = current_setting('app.current_user_id', TRUE)::UUID
    );

-- Writeups RLS policies
CREATE POLICY writeups_select_visible ON writeups
    FOR SELECT
    USING (
        (is_approved = TRUE OR is_approved IS NULL)
        AND deleted_at IS NULL
        OR user_id = current_setting('app.current_user_id', TRUE)::UUID
        OR current_setting('app.current_user_role', TRUE) IN ('admin', 'organizer')
    );

-- =============================================================================
-- FUNCTIONS AND TRIGGERS
-- =============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_teams_updated_at BEFORE UPDATE ON teams
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_challenges_updated_at BEFORE UPDATE ON challenges
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_feature_flags_updated_at BEFORE UPDATE ON feature_flags
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_announcements_updated_at BEFORE UPDATE ON announcements
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_writeups_updated_at BEFORE UPDATE ON writeups
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_api_keys_updated_at BEFORE UPDATE ON api_keys
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to generate dynamic points based on solve count
CREATE OR REPLACE FUNCTION calculate_dynamic_points(challenge_uuid UUID)
RETURNS INTEGER AS $$
DECLARE
    challenge_record RECORD;
    decay_points INTEGER;
BEGIN
    SELECT * INTO challenge_record FROM challenges WHERE id = challenge_uuid;
    
    IF challenge_record.is_dynamic_scoring = FALSE THEN
        RETURN challenge_record.points;
    END IF;
    
    -- Decay formula: max_points - (solve_count * decay_amount)
    decay_points := challenge_record.points - (challenge_record.solve_count * challenge_record.dynamic_score_decay);
    
    -- Ensure minimum points
    IF decay_points < challenge_record.dynamic_score_min THEN
        RETURN challenge_record.dynamic_score_min;
    END IF;
    
    RETURN GREATEST(decay_points, challenge_record.dynamic_score_min);
END;
$$ LANGUAGE plpgsql;

-- Function to create new monthly partition
CREATE OR REPLACE FUNCTION create_solves_partition()
RETURNS void AS $$
DECLARE
    partition_date DATE;
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
BEGIN
    partition_date := DATE_TRUNC('month', NOW() + INTERVAL '1 month');
    partition_name := 'solves_y' || TO_CHAR(partition_date, 'YYYY') || 'm' || TO_CHAR(partition_date, 'MM');
    start_date := partition_date;
    end_date := partition_date + INTERVAL '1 month';
    
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF solves FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date
    );
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- APPLICATION FUNCTIONS
-- =============================================================================

-- Function to check and submit flag
CREATE OR REPLACE FUNCTION submit_flag(
    p_user_id UUID,
    p_challenge_id UUID,
    p_flag TEXT,
    p_ip_address INET DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL
)
RETURNS TABLE (
    status TEXT,
    points_awarded INTEGER,
    is_first_blood BOOLEAN
) AS $$
DECLARE
    v_challenge RECORD;
    v_decrypted_flag TEXT;
    v_attempt_number INTEGER;
    v_is_correct BOOLEAN;
    v_points INTEGER;
    v_is_first_blood BOOLEAN := FALSE;
BEGIN
    -- Get challenge
    SELECT * INTO v_challenge FROM challenges WHERE id = p_challenge_id AND deleted_at IS NULL;
    
    IF NOT FOUND THEN
        RETURN QUERY SELECT 'error'::TEXT, 0, FALSE;
        RETURN;
    END IF;
    
    -- Decrypt flag
    v_decrypted_flag := pgp_sym_decrypt(v_challenge.flag_data, current_setting('app.encryption_key', TRUE));
    
    -- Check if flag matches
    IF v_challenge.flag_case_sensitive THEN
        v_is_correct := (p_flag = v_decrypted_flag);
    ELSE
        v_is_correct := (LOWER(p_flag) = LOWER(v_decrypted_flag));
    END IF;
    
    -- Calculate attempt number
    SELECT COALESCE(MAX(attempt_number), 0) + 1 INTO v_attempt_number
    FROM submissions
    WHERE user_id = p_user_id AND challenge_id = p_challenge_id;
    
    -- Log submission
    INSERT INTO submissions (user_id, challenge_id, submitted_flag, is_correct, attempt_number, ip_address, user_agent)
    VALUES (p_user_id, p_challenge_id, p_flag, v_is_correct, v_attempt_number, p_ip_address, p_user_agent);
    
    -- If correct and not already solved by this user
    IF v_is_correct THEN
        IF NOT EXISTS (
            SELECT 1 FROM solves 
            WHERE user_id = p_user_id 
            AND challenge_id = p_challenge_id 
            AND status = 'correct'
        ) THEN
            -- Check for first blood
            IF v_challenge.solve_count = 0 THEN
                v_is_first_blood := TRUE;
            END IF;
            
            -- Calculate points
            v_points := calculate_dynamic_points(p_challenge_id);
            
            -- Record solve
            INSERT INTO solves (user_id, challenge_id, team_id, submitted_flag, status, points_awarded, ip_address, user_agent)
            SELECT 
                p_user_id, 
                p_challenge_id, 
                u.team_id, 
                p_flag, 
                CASE WHEN v_is_first_blood THEN 'first_blood'::solve_status ELSE 'correct'::solve_status END,
                v_points,
                p_ip_address,
                p_user_agent
            FROM users u WHERE u.id = p_user_id;
            
            -- Update challenge stats
            UPDATE challenges 
            SET solve_count = solve_count + 1, 
                attempt_count = attempt_count + 1
            WHERE id = p_challenge_id;
        END IF;
    ELSE
        -- Update attempt count
        UPDATE challenges SET attempt_count = attempt_count + 1 WHERE id = p_challenge_id;
    END IF;
    
    RETURN QUERY SELECT 
        CASE 
            WHEN v_is_correct AND EXISTS (SELECT 1 FROM solves WHERE user_id = p_user_id AND challenge_id = p_challenge_id AND status IN ('correct', 'first_blood'))
            THEN 'already_solved'
            WHEN v_is_correct THEN 'correct'
            ELSE 'incorrect'
        END::TEXT,
        COALESCE(v_points, 0),
        v_is_first_blood;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- INSERT DEFAULT DATA
-- =============================================================================

-- Default categories
INSERT INTO categories (name, slug, description, color, sort_order) VALUES
    ('Web Exploitation', 'web', 'Web application security challenges', '#E34C26', 1),
    ('Binary Exploitation', 'pwn', 'Buffer overflows, format strings, and more', '#8B4513', 2),
    ('Cryptography', 'crypto', 'Breaking ciphers and encryption', '#FFD700', 3),
    ('Forensics', 'forensics', 'Digital forensics and incident response', '#228B22', 4),
    ('Reverse Engineering', 'reverse', 'Disassembly and deobfuscation', '#4169E1', 5),
    ('Miscellaneous', 'misc', 'Everything else', '#708090', 6),
    ('OSINT', 'osint', 'Open source intelligence gathering', '#FF6347', 7),
    ('Blockchain', 'blockchain', 'Smart contract and blockchain challenges', '#8A2BE2', 8)
ON CONFLICT (slug) DO NOTHING;

-- Default admin user (password should be changed immediately)
-- Note: This is a placeholder - in production, use proper password hashing
INSERT INTO users (username, email, password_hash, role, email_verified, display_name)
VALUES (
    'admin',
    pgp_sym_encrypt('admin@cerberus.local', 'change-me-in-production'),
    '$argon2id$v=19$m=65536,t=3,p=4$c29tZXNhbHRzb21lc2FsdA$hashplaceholder', -- Placeholder - must be regenerated
    'admin',
    TRUE,
    'System Administrator'
)
ON CONFLICT (username) DO NOTHING;

-- =============================================================================
-- GRANTS
-- =============================================================================

-- Create application role
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'cerberus_app') THEN
        CREATE ROLE cerberus_app WITH LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO cerberus_app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO cerberus_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO cerberus_app;

-- =============================================================================
-- COMPLETION
-- =============================================================================

SELECT 'Cerberus schema initialized successfully' AS status;
