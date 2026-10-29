# VERITY — Operating Contract (READ EVERY SESSION)

## What VERITY is
VERITY is an explainable misinformation-triage agent. A user pastes a forwarded
message (English, Tamil or Hindi). VERITY extracts the checkable claim, retrieves
matching published fact-checks, scores simple evidence cues, and combines it all
in a Bayesian belief network. It returns one of three verdicts (likely_false,
unverified, likely_true), a probability, ranked reasons, a what-if hint and a
polite reply card. Honest abstention ("unverified") is a first-class output.
Five differentiators go beyond asking a chatbot: D1 privacy shield (redaction on
the device), D2 rumour fingerprint (SimHash families), D3 lookalike-link guard,
D4 evidence passport (reproducible, sourced verdicts) and D5 Rumour Radar
(privacy-preserving surge list).

## GROUND TRUTH (never change without explicit human instruction)
- Architecture, stage responsibilities, data models, belief-network structure
  and the decision rule are FIXED by the PRD and Technical Deep-Dive. Do not
  redesign them.
- Component ownership is fixed:
  - spaCy + regex        = information extraction (claim, entities, numbers, links)
  - scikit-learn         = TF-IDF retrieval + naive Bayes tone model + baseline
  - pgmpy                = belief network, parameter learning, exact inference
  - hand-written Python  = likelihood weighting, decision rule, reasons, what-if
  - SQLite (stdlib)      = all persistence
  - Python re + hashlib  = privacy redaction (D1) and SimHash fingerprints (D2)
  - pure Python          = Levenshtein lookalike guard (D3), passport hashes (D4),
                           surge score (D5)
  - FastAPI + Streamlit  = API and UI
- Boundaries: shared models live ONLY in src/verity/schemas.py and are imported,
  never redefined. ALL database access goes ONLY through src/verity/db. ALL
  external HTTP (fact-check API, translation) goes ONLY through
  src/verity/clients, and every client function accepts ONLY the RedactedText
  type (mypy must reject a plain str). Redaction lives ONLY in
  src/verity/privacy.py, fingerprints and families ONLY in src/verity/rumour,
  the link guard ONLY in src/verity/cues/links.py. ALL probability logic lives ONLY in src/verity/bn and
  src/verity/explain. The UI talks to the API over HTTP and never imports the
  pipeline.

## ANTI-HALLUCINATION RULES (hard rules)
1. Never invent API endpoints, request/response shapes, SDK method names or
   package APIs. Before using ANY external API or library surface (Google Fact
   Check Tools API, translation provider, pgmpy, spaCy, Streamlit, feedparser,
   langdetect), open and read its official docs IN THIS SESSION and confirm the
   exact shapes. pgmpy in particular has changed class and estimator names
   between releases: check the installed version. If you cannot verify, STOP
   and ask — do not guess.
2. Never assume a package or version exists. Check pyproject.toml / the
   registry before importing. Pin the resolved version; commit the lock file.
3. If a type, constant or contract already exists in src/verity/schemas.py or
   §B of the build doc, IMPORT it. Never create a second definition.
4. Never fabricate data: no invented fact-check records, no invented source
   credibility ratings, no invented labelled messages or labels, no invented
   metrics. Synthetic fixtures are allowed ONLY under tests/ and must be marked
   `# SYNTHETIC FIXTURE`.
5. If a requirement is ambiguous or underspecified, ask ONE clarifying question
   instead of assuming. State any unavoidable assumption explicitly in the PR.
6. Do not fabricate test results, file contents or command output. Run things.

## ANTI-DRIFT RULES (hard rules)
7. Only create/modify the files listed in the task's "Files you may touch".
   If you must touch another file, list it and explain BEFORE editing.
8. Do not refactor unrelated code. Do not add features not in the task.
9. Keep every data model byte-aligned with §B. Field names and enum values must
   match exactly (e.g. verdict is 'likely_false'|'unverified'|'likely_true' —
   not synonyms; node names are source_cred, claim_true, fact_check,
   corroboration, sensational, specifics).
10. All tunable numbers (thresholds, k, sample counts) live in
    src/verity/config.py. No magic numbers elsewhere.

## QUALITY GATES (must hold at end of every task)
- Python 3.11+, mypy strict, no `Any` (use `object` + narrow). No secrets in code.
- Pydantic validates ALL external input and ALL external-API output at the
  boundary.
- Everything is deterministic given a seed. Seeds come from config.
- Errors are typed and structured; never swallow errors silently.
- PRIVACY INVARIANT: the full text of a user's message is never written to the
  database, logs or files. Only the SHA-256 hash of the REDACTED text, a
  fingerprint and up to five non-personal keywords are persisted. Nothing leaves
  the device unless it has passed through privacy.redact().
- RADAR INVARIANT: a rumour family is shown only after RADAR_MIN_COUNT checks,
  only with keywords and any linked fact-check, and never changes a verdict.
- PASSPORT INVARIANT: every verdict carries a passport; the same input with the
  same index, model and threshold gives the same passport_id and verdict. No
  factual sentence is generated; text comes from templates or retrieved records.
- EXPLAINABILITY INVARIANT: every verdict returned carries reasons, and carries
  the fact-check link whenever a match exists. Neither UI nor reply card ever
  shows a bare "FAKE" or "REAL".
- ABSTENTION INVARIANT: the verdict label is computed in exactly one place,
  bn.decide(). Anything not clearly above threshold is 'unverified'.

## WORKING METHOD (every task)
A. First output a SHORT PLAN: the files you'll create/modify and the approach.
   For any task touching >1 file, WAIT for "go" before writing (unless told to
   run autonomously).
B. Implement only what the task asks.
C. Run the task's VERIFY commands. Paste real output. If anything fails, fix it
   before claiming done. Do NOT mark done on unverified work.
D. Extend tests. New behaviour ships with a test.
E. Commit once, message: `feat(<TASKID>): <summary>` (or fix/chore as apt).

## DEFINITION OF DONE
A task is done only when: `make lint` and `make typecheck` pass, its VERIFY
block passes with pasted output, `make test` passes, the data model matches §B
exactly, and only the permitted files changed.

---

# Project map

## Repo structure

```
verity/
├── src/verity/
│   ├── schemas.py          # B.2 — import only
│   ├── errors.py
│   ├── config.py           # all tunables (B.1)
│   ├── privacy.py          # redact() (D1), message_hash()
│   ├── db/                 # SQLite access only
│   ├── clients/            # external HTTP only (factcheck, translate, feeds)
│   ├── lang/               # detect + translate orchestration
│   ├── extract/            # spaCy + regex
│   ├── retrieval/          # TF-IDF indexes, matching, node mapping
│   ├── cues/               # source_cred, links (D3), tone, specifics
│   ├── rumour/             # fingerprint, family, radar (D2, D5)
│   ├── bn/                 # network, learn, infer, sample, decide
│   ├── explain/            # reasons, what_if, reply_card, passport (D4)
│   ├── pipeline.py         # pipeline.check()
│   └── api/                # FastAPI app (port 8000)
├── ui/app.py               # Streamlit (port 8501), HTTP client only
├── ui/pages/radar.py       # Rumour Radar page (D5)
├── data/                   # domains.csv, rating_map.json, cpt_priors.json, lexicons, seed files
├── eval/                   # labelled/, baseline, metrics, ablation, convergence
├── scripts/                # ingest, split, setup, demo
├── tests/
├── CONTRACT.md
├── pyproject.toml
├── Makefile
├── .env.example
└── README.md
```

## SQLite tables

```
factchecks (id, claim_text, rating, publisher, url, date, lang)
headlines  (id, title, domain, url, date)
domains    (domain, class)                       -- class: 'trusted' | 'low'
feedback   (id, message_hash, verdict, user_label, timestamp)
rumours    (family_id, fingerprint, keywords, language, linked_factcheck_id,
            first_seen, last_seen, last_verdict)                  -- D2
rumour_hits(family_id, hour, message_hash)                       -- D5, unique per row
```

## Belief network

```
Nodes and states
  source_cred    : trusted | unknown | low          (observed; no parent)
  claim_true     : true | false                     (hidden; parent: source_cred)
  fact_check     : refuted | supported | none       (observed; parent: claim_true)
  corroboration  : yes | no                         (observed; parent: claim_true)
  sensational    : high | low                       (observed; parent: claim_true)
  specifics      : yes | no                         (observed; parent: claim_true)

Edges (5)
  source_cred -> claim_true
  claim_true  -> fact_check
  claim_true  -> corroboration
  claim_true  -> sensational
  claim_true  -> specifics

Parameters   about 40 probabilities. Priors in data/cpt_priors.json, learned
             values in data/cpt_learned.json (Bayesian estimation with the
             priors as pseudo-counts).
Decision     if p_false >= VERDICT_THRESHOLD -> 'likely_false'
             elif p_true >= VERDICT_THRESHOLD -> 'likely_true'
             else 'unverified'
Differentiator links (no change to the network structure)
             D3: a lookalike link forces source_cred = low
             D2: a matching family with a linked rating sets fact_check only
                 when TF-IDF found none (FamilyInfo.source = 'variant')
Reasons      shift(node) = p_true(all evidence) - p_true(evidence without node)
Ablation     "without node" means the node is unobserved and marginalised out
```
