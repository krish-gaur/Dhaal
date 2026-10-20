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
    -- Clause ids (e.g. c_room_rent_01) are only unique within a session's
    -- document; two sessions loading the same fixture must not collide.
    id             TEXT NOT NULL,
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
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, id)
);

CREATE TABLE IF NOT EXISTS simulation_runs (
    id             TEXT PRIMARY KEY,
    session_id     TEXT NOT NULL REFERENCES sessions(id),
    inputs_json    TEXT NOT NULL,
    result_json    TEXT NOT NULL,
    invariants_ok  BOOLEAN NOT NULL,
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
