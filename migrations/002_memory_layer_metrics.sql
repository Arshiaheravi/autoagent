-- Recall telemetry on council_episodic so we can measure whether the
-- memory layer actually helps (recall rate + verdict stability deltas).
-- Idempotent: safe to re-apply.

ALTER TABLE council_episodic
    ADD COLUMN IF NOT EXISTS had_recall_block BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE council_episodic
    ADD COLUMN IF NOT EXISTS recalled_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE council_episodic
    ADD COLUMN IF NOT EXISTS recalled_ids BIGINT[] NOT NULL DEFAULT '{}'::bigint[];

-- Btree on had_recall_block lets the weekly rollup short-circuit cheaply.
CREATE INDEX IF NOT EXISTS council_episodic_recall_flag_idx
    ON council_episodic (had_recall_block, ts DESC);
