CREATE TABLE IF NOT EXISTS targets (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS checks (
    id SERIAL PRIMARY KEY,
    target_id INT REFERENCES targets(id) ON DELETE CASCADE,
    status_code INT,
    is_up BOOLEAN NOT NULL,
    latency_ms NUMERIC,
    checked_at TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_checks_target_time ON checks (target_id, checked_at DESC);
