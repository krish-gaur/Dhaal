-- DHAAL 002: policy identification + document provenance.
--
-- Applied by session_store.init_db(), which tolerates "duplicate column"
-- errors so this file is safe to run against a database that already has
-- these columns (SQLite has no ADD COLUMN IF NOT EXISTS).

ALTER TABLE sessions ADD COLUMN catalogue_product_id TEXT;
ALTER TABLE sessions ADD COLUMN catalogue_version TEXT;
ALTER TABLE sessions ADD COLUMN insurer_name TEXT;
ALTER TABLE sessions ADD COLUMN product_name TEXT;
ALTER TABLE sessions ADD COLUMN identification_status TEXT;

ALTER TABLE documents ADD COLUMN source_kind TEXT;
ALTER TABLE documents ADD COLUMN source_url TEXT;
ALTER TABLE documents ADD COLUMN doc_version TEXT;
ALTER TABLE documents ADD COLUMN effective_date TEXT;
ALTER TABLE documents ADD COLUMN uin TEXT;
ALTER TABLE documents ADD COLUMN sha256 TEXT;
ALTER TABLE documents ADD COLUMN retrieved_at TEXT;
