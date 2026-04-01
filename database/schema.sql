CREATE TABLE IF NOT EXISTS match_reports (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at       TIMESTAMPTZ DEFAULT now(),
    batting_team     TEXT,
    bowling_team     TEXT,
    venue            TEXT,
    toss_winner      TEXT,
    toss_decision    TEXT,
    match_date       DATE,
    predicted_score  INT,
    win_probability  JSONB,
    full_report      TEXT,
    actual_score     INT,
    actual_winner    TEXT
);
CREATE INDEX IF NOT EXISTS idx_match_reports_date ON match_reports(created_at DESC);
