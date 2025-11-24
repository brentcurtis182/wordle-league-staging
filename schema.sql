-- PostgreSQL Schema for Wordle League
-- This matches your SQLite schema but uses PostgreSQL data types

-- Players table
CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    phone_number VARCHAR(20),
    league_id INTEGER NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, league_id)
);

-- Scores table
CREATE TABLE IF NOT EXISTS scores (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id),
    wordle_number INTEGER NOT NULL,
    score INTEGER NOT NULL,
    date DATE NOT NULL,
    emoji_pattern TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, wordle_number)
);

-- Latest scores table (for quick lookups)
CREATE TABLE IF NOT EXISTS latest_scores (
    player_id INTEGER PRIMARY KEY REFERENCES players(id),
    league_id INTEGER NOT NULL,
    score INTEGER,
    wordle_number INTEGER,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Settings table
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Season winners table
CREATE TABLE IF NOT EXISTS season_winners (
    id SERIAL PRIMARY KEY,
    player_id INTEGER NOT NULL REFERENCES players(id),
    league_id INTEGER NOT NULL,
    season_number INTEGER NOT NULL,
    wins INTEGER DEFAULT 0,
    total_score INTEGER DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_scores_player_wordle ON scores(player_id, wordle_number);
CREATE INDEX IF NOT EXISTS idx_scores_league_date ON scores(player_id, date);
CREATE INDEX IF NOT EXISTS idx_players_league ON players(league_id);
CREATE INDEX IF NOT EXISTS idx_latest_scores_league ON latest_scores(league_id);

-- Insert League 6 Beta Test players
INSERT INTO players (name, phone_number, league_id, active) VALUES
    ('Brent', '18587359353', 6, TRUE),
    ('Matt', '17609082000', 6, TRUE),
    ('Rob', '17608156131', 6, TRUE),
    ('Jason', '16503468822', 6, TRUE)
ON CONFLICT (name, league_id) DO NOTHING;
