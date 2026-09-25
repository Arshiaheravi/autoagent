-- Autoagency council memory — persistent verdicts + vector recall.
-- Idempotent: safe to re-apply.
-- Target DB: autoagency_memory on redhunter-memory-pg (host:5433).

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS council_episodic (
    id                   BIGSERIAL PRIMARY KEY,
    ts                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    question             TEXT NOT NULL,
    question_hash        TEXT NOT NULL,
    context              TEXT NOT NULL DEFAULT '',
    context_hash         TEXT NOT NULL DEFAULT '',
    mode                 TEXT NOT NULL DEFAULT 'executive',
    stage1               JSONB NOT NULL DEFAULT '[]'::jsonb,
    stage2_aggregate     JSONB NOT NULL DEFAULT '[]'::jsonb,
    synthesis            TEXT NOT NULL DEFAULT '',
    winner               TEXT NOT NULL DEFAULT '',
    confidence           TEXT NOT NULL DEFAULT '',
    decision_id_legacy   BIGINT,
    project              TEXT,
    question_embedding   vector(1536),
    context_embedding    vector(1536)
);

CREATE INDEX IF NOT EXISTS council_episodic_ts_idx
    ON council_episodic (ts DESC);

CREATE INDEX IF NOT EXISTS council_episodic_qhash_idx
    ON council_episodic (question_hash);

-- ivfflat needs a populated table for the OPTIMAL `lists` setting; 100 is a
-- safe cold-start default. Re-tune after ~10k rows.
CREATE INDEX IF NOT EXISTS council_episodic_qemb_ivfflat
    ON council_episodic
    USING ivfflat (question_embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS council_episodic_cemb_ivfflat
    ON council_episodic
    USING ivfflat (context_embedding vector_cosine_ops)
    WITH (lists = 100);
