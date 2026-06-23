-- Part 7: storage for cleaned records + per-record verdicts (rule AND LLM side by side)
-- + aggregated metrics. SQLite-flavored; trivially portable to Postgres.

-- Cleaned, promoted events
CREATE TABLE IF NOT EXISTS clean_events (
    event_id        TEXT PRIMARY KEY,
    category        TEXT NOT NULL,
    summary         TEXT NOT NULL,
    found_at        TEXT,
    confidence      REAL,
    human_approved  INTEGER,
    company1_id     TEXT,
    company2_id     TEXT,
    source_id       TEXT,
    promoted_at     TEXT NOT NULL
);

-- One row per (event, check). check_kind tells rule vs LLM apart -> side-by-side reporting.
CREATE TABLE IF NOT EXISTS quality_verdicts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT NOT NULL,
    found_at        TEXT,            -- event date, carried on every verdict so DQ trends include
                                     -- failed records too (not only promoted ones)
    check_kind      TEXT NOT NULL,   -- 'rule' | 'llm'
    check_name      TEXT NOT NULL,   -- e.g. 'date_sane' | 'semantic_accuracy'
    verdict         TEXT NOT NULL,   -- 'pass' | 'fail' | 'needs_human_review'
    reason          TEXT,
    confidence      REAL,
    model           TEXT,            -- NULL for rules
    prompt_version  TEXT,            -- NULL for rules
    cost_usd        REAL DEFAULT 0,
    latency_ms      INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_verdicts_event ON quality_verdicts(event_id);
CREATE INDEX IF NOT EXISTS idx_verdicts_check ON quality_verdicts(check_name, verdict);

-- Human review backlog
CREATE TABLE IF NOT EXISTS review_queue (
    event_id        TEXT PRIMARY KEY,
    reason          TEXT,
    proposed_action TEXT,            -- from remediation skill
    status          TEXT DEFAULT 'pending',  -- pending | approved | rejected
    enqueued_at     TEXT NOT NULL
);

-- Daily rollups for the dashboard (rule vs LLM trend, cost/latency).
CREATE TABLE IF NOT EXISTS daily_metrics (
    day             TEXT NOT NULL,
    check_kind      TEXT NOT NULL,
    check_name      TEXT NOT NULL,
    n_total         INTEGER,
    n_fail          INTEGER,
    avg_confidence  REAL,
    total_cost_usd  REAL,
    avg_latency_ms  REAL,
    PRIMARY KEY (day, check_kind, check_name)
);
