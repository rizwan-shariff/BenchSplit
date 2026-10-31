PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS courts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    short_code TEXT NOT NULL,
    level TEXT NOT NULL CHECK (level IN ('HC', 'SC'))
);

CREATE TABLE IF NOT EXISTS judgments (
    id TEXT PRIMARY KEY,
    court_id TEXT NOT NULL REFERENCES courts(id),
    cnr TEXT NOT NULL,
    title TEXT NOT NULL,
    decision_date TEXT NOT NULL,
    s3_uri TEXT NOT NULL,
    local_pdf_path TEXT NOT NULL,
    pdf_sha256 TEXT NOT NULL,
    has_text_layer INTEGER NOT NULL DEFAULT 1,
    n_pages INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS propositions (
    id TEXT PRIMARY KEY,
    judgment_id TEXT NOT NULL REFERENCES judgments(id),
    statute_key TEXT NOT NULL,
    question TEXT NOT NULL,
    holding TEXT NOT NULL,
    quote TEXT NOT NULL,
    page INTEGER NOT NULL,
    char_start INTEGER NOT NULL,
    char_end INTEGER NOT NULL,
    verify_status TEXT NOT NULL CHECK (verify_status IN ('VERIFIED_EXACT', 'VERIFIED_FUZZY', 'DROPPED')),
    verify_score REAL NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    entailment_supported INTEGER NOT NULL DEFAULT 1,
    model_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL DEFAULT 'v1.0',
    embedding_q BLOB,
    embedding_h BLOB
);

CREATE TABLE IF NOT EXISTS clusters (
    id TEXT PRIMARY KEY,
    statute_key TEXT NOT NULL,
    canonical_question TEXT NOT NULL,
    method TEXT NOT NULL DEFAULT 'agglomerative_cosine',
    threshold REAL NOT NULL DEFAULT 0.35
);

CREATE TABLE IF NOT EXISTS cluster_members (
    cluster_id TEXT NOT NULL REFERENCES clusters(id),
    proposition_id TEXT NOT NULL REFERENCES propositions(id),
    PRIMARY KEY (cluster_id, proposition_id)
);

CREATE TABLE IF NOT EXISTS pair_labels (
    id TEXT PRIMARY KEY,
    statute_key TEXT NOT NULL,
    cluster_id TEXT NOT NULL REFERENCES clusters(id),
    prop_a_id TEXT NOT NULL REFERENCES propositions(id),
    prop_b_id TEXT NOT NULL REFERENCES propositions(id),
    candidate_score REAL NOT NULL,
    label TEXT NOT NULL CHECK (label IN ('CONFLICT', 'AGREE', 'DISTINGUISHABLE_ON_FACTS', 'UNRELATED')),
    reason TEXT NOT NULL,
    votes_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    sc_status TEXT NOT NULL,
    sc_prop_id TEXT REFERENCES propositions(id)
);

CREATE TABLE IF NOT EXISTS gold_pairs (
    id TEXT PRIMARY KEY,
    statute_key TEXT NOT NULL,
    prop_a_id TEXT NOT NULL REFERENCES propositions(id),
    prop_b_id TEXT NOT NULL REFERENCES propositions(id),
    annotator_1_label TEXT NOT NULL,
    annotator_2_label TEXT NOT NULL,
    final_gold_label TEXT NOT NULL,
    split TEXT NOT NULL CHECK (split IN ('tune', 'test'))
);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    filename TEXT,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    events_json TEXT NOT NULL DEFAULT '[]',
    metrics_json TEXT NOT NULL DEFAULT '{}'
);
