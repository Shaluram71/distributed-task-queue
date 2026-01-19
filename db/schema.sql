CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY,
    payload JSONB,
    status TEXT NOT NULL DEFAULT 'PENDING',
    error_message TEXT,
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    locked_at TIMESTAMPTZ,
    locked_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
