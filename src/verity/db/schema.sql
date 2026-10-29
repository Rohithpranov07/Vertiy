-- VERITY schema (build spec B.4). No column can hold raw message text.
CREATE TABLE IF NOT EXISTS factchecks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_text TEXT NOT NULL,
    rating     TEXT NOT NULL CHECK (rating IN ('refuted', 'supported')),
    publisher  TEXT NOT NULL,
    url        TEXT NOT NULL,
    date       TEXT,
    lang       TEXT,
    UNIQUE (url, claim_text)
);

CREATE TABLE IF NOT EXISTS headlines (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    title  TEXT NOT NULL,
    domain TEXT NOT NULL,
    url    TEXT NOT NULL UNIQUE,
    date   TEXT
);

CREATE TABLE IF NOT EXISTS domains (
    domain TEXT PRIMARY KEY,
    class  TEXT NOT NULL CHECK (class IN ('trusted', 'low'))
);

CREATE TABLE IF NOT EXISTS feedback (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    message_hash TEXT NOT NULL,
    verdict      TEXT NOT NULL CHECK (verdict IN ('likely_false', 'unverified', 'likely_true')),
    user_label   TEXT NOT NULL CHECK (user_label IN ('right', 'wrong')),
    timestamp    TEXT NOT NULL
);

-- fingerprint is the 64-bit SimHash stored as 16 hex characters;
-- keywords is a JSON array of at most five non-personal keywords.
CREATE TABLE IF NOT EXISTS rumours (
    family_id           TEXT PRIMARY KEY,
    fingerprint         TEXT NOT NULL,
    keywords            TEXT NOT NULL,
    language            TEXT NOT NULL,
    linked_factcheck_id INTEGER,
    first_seen          TEXT NOT NULL,
    last_seen           TEXT NOT NULL,
    last_verdict        TEXT
);

-- hour is a UTC bucket such as 2026-10-29T14
CREATE TABLE IF NOT EXISTS rumour_hits (
    family_id    TEXT NOT NULL,
    hour         TEXT NOT NULL,
    message_hash TEXT NOT NULL,
    PRIMARY KEY (family_id, hour, message_hash)
);
