-- DHAAL initial schema
-- Single migration file. Run once at startup.

CREATE TABLE IF NOT EXISTS sessions (
    id            TEXT PRIMARY KEY,
    mode          TEXT NOT NULL CHECK (mode IN ('fixture', 'live')),
    goal          TEXT,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at    TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id),
    filename      TEXT NOT NULL,
    page_count    INT  NOT NULL,
    text_content  TEXT NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clauses (
    id             TEXT PRIMARY KEY,
    document_id    TEXT NOT NULL REFERENCES documents(id),
    session_id     TEXT NOT NULL REFERENCES sessions(id),
    page           INT,
    char_start     INT,
    char_end       INT,
    quote          TEXT,
    quote_hash     TEXT,
    rule_type      TEXT,
    rule_params    TEXT,
    status         TEXT NOT NULL,
    reason         TEXT,
    schema_valid   BOOLEAN,
    quote_found    BOOLEAN,
    numbers_ok     BOOLEAN,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id             TEXT PRIMARY KEY,
    session_id     TEXT NOT NULL REFERENCES sessions(id),
    inputs_json    TEXT NOT NULL,
    result_json    TEXT NOT NULL,
    invariants_ok  BOOLEAN NOT NULL,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
