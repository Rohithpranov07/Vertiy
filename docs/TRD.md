**Technical Deep-Dive: System & Stages**

# VERITY

**Anatomy of a Privacy-First, Explainable Misinformation Checker**

*Two independent checks, one belief network. Every probability traces back to named evidence.*

| | |
| --- | --- |
| **Document** | Technical Deep-Dive v1.1 (companion to the PRD) |
| **Author** | V Rohith Pranov (24BCE0619) |
| **Scope** | Full detail on every stage and the five differentiators (D1 to D5): purpose, mechanism, data, stack, demo |
| **Course** | Artificial Intelligence, Modules 1, 2, 5, 7, 8 |
| **Core stack** | Python · FastAPI · spaCy · scikit-learn · pgmpy · SQLite · Streamlit |
| **Date** | 29 October 2026 |

## Contents

1. The Unifying Thesis
2. System Topology
3. Stage 1: Input and Language
4. Stage 2: Information Extraction
5. Stage 3: Retrieval
6. Stage 4: Cue Scoring
7. Stage 5: The Bayesian Belief Network
8. Stage 6: Reasons and What-If
9. Stage 7: Reply Card
10. D1: Privacy Shield
11. D2: Rumour Fingerprint
12. D3: Lookalike-Link Guard
13. D4: Evidence Passport
14. D5: Rumour Radar
15. Data Model and API
16. Evaluation Plan
17. Risks, Build Plan and Priority
18. Demo Script

---

## 1. The Unifying Thesis

Misinformation triage looks like a classification problem, but the honest answer to "is this true?" is usually a degree of belief built from several weak signals. VERITY treats it that way: independent evidence is gathered, then combined by a Bayesian network that can also say "not enough evidence".

| Symptom | Is really a question about... |
| --- | --- |
| **Debunked rumour recirculating** | memory: has a fact-checker already ruled on this claim? |
| **Alarmist wording** | style: does the text read like persuasion rather than reporting? |
| **Unknown or low-quality link** | provenance: who is vouching for this? |
| **No names, dates or places** | verifiability: could anyone check this at all? |
| **Only one source says it** | corroboration: does a trusted outlet report the same thing? |
| **Same rumour back with emojis added** | identity: is this an edited copy of something already seen? (D2) |
| **Link that almost matches a trusted site** | impersonation: is the domain imitating a trusted one? (D3) |
| **Message contains a phone number or UPI handle** | privacy: what must never leave the device? (D1) |

> **Why a belief network, not a classifier**
>
> A classifier maps text to a label and hides the reasoning. A belief network keeps each piece of evidence as a named node with explicit probabilities, so the system can report which evidence mattered, what would change the answer, and when the evidence is too thin to answer at all.

### 1.1 The agent (PEAS, Module 1.5)

| Element | VERITY |
| --- | --- |
| **Performance** | Correct verdicts on labelled claims, calibrated probabilities, few confident errors, response under 3 seconds |
| **Environment** | Forwarded messages in English, Tamil and Hindi; a fact-check index; a trusted-source list |
| **Actuators** | Verdict card, reasons panel, what-if hint, reply card |
| **Sensors** | Pasted text, optional URL, and a "was this right?" tap |

### 1.2 Environment classification (Module 1.6)

| Property | Classification | Why it matters here |
| --- | --- | --- |
| **Observability** | Partially observable | The sender's origin and intent are hidden, so only cues are visible |
| **Determinism** | Stochastic | The same claim can carry mixed evidence, hence probabilities |
| **Episodic or sequential** | Episodic | Each message is judged on its own |
| **Static or dynamic** | Dynamic | New rumours and fact-checks keep arriving, so the index needs refreshing |
| **Agents** | Single agent | No other agents act on the same input |

### 1.3 Why not just ask a chatbot?

A general chatbot can often give a useful answer, so this table lists the technical guarantee VERITY adds, not what is impossible elsewhere.

| Aspect | Chatbot prompt (typical default) | VERITY mechanism |
| --- | --- | --- |
| **Probability** | Not calibrated or measured | Posterior from a belief network; Brier score on a labelled set |
| **Abstention** | May answer anyway | Threshold rule in one function, `decide()` |
| **Sources** | Not guaranteed to exist | Only records in the local index, with link and similarity (D4) |
| **Repeatability** | Can change per run | Passport id from input hash and index, model and threshold versions (D4) |
| **Cross-user memory** | None | Rumour fingerprints and hourly counts (D2, D5) |
| **Link safety** | No domain-distance check | Edit-distance and look-alike rules against the trusted list (D3) |
| **Privacy** | Raw message sent to a third party | Redaction on the device first (D1) |

## 2. System Topology

A short pipeline. The privacy shield runs first. Retrieval, the rumour fingerprint and cue scoring run in parallel and never see each other's output. The belief network is the only place they meet. Starred boxes are the differentiators.

```
  External services (receive only the redacted claim):
  Google Fact Check API . translator . trusted feeds
                    :
 [User message] --> [*D1 Privacy shield*] --> [Language] --> [Extract claim]
  paste / API         redact phone, UPI,       detect +        spaCy + regex
                      IDs, cards               translate           |
                                                                   |
              +----------------------------+-----------------------+
              |                            |                       |
              v                            v                       v
     [Fact-check retrieval]    [*D2 Rumour fingerprint*]   [Cue scoring]
      TF-IDF cosine, top-k      SimHash, Hamming match      source + *D3 lookalike guard*
      fact-checks + headlines   -> family, variant link     tone, verifiable details
              |                            |                       |
              +----------------------------+-----------------------+
                                           |
                                           v
                         [ Bayesian belief network ]
                         6 nodes, exact inference, 3-way rule
                                           |
                      +--------------------+--------------------+
                      v                                         v
     [*D4 Explanation + Evidence passport*]          [*D5 Rumour Radar*]
      reasons, what-if, reply card,                   surge = (last 24h + 1)/(prev 24h + 1)
      index/model/threshold versions                  Unverified families, 3+ checks only

  SQLite (local): factchecks . headlines . domains . rumours . rumour_hits . feedback
  No message text is ever stored: only hashes, fingerprints and keywords.
```

| Layer | Role | Technology | Responsibility |
| --- | --- | --- | --- |
| **Privacy** | Protects the user | Python `re` | Redacts personal identifiers before anything is stored or sent (D1) |
| **Perception** | Reads the message | langdetect, spaCy | Language detection, entities, claim sentence |
| **Evidence** | Gathers signals | scikit-learn, SQLite, hashlib | Retrieval, cue models, rumour fingerprint (D2), lookalike guard (D3) |
| **Reasoning** | Combines signals | pgmpy | Belief network, inference, decision rule |
| **Explanation** | Shows its work | Python | Reasons, what-if, reply card, evidence passport (D4) |
| **Memory** | Remembers circulation | SQLite | Rumour families and hourly counts for the Radar (D5) |
| **Interface** | Talks to the user | FastAPI, Streamlit | Three endpoints and one page |

## 3. Stage 1: Input and Language

*Module 7.1: Communication and Language*

### The problem it owns

Many forwards are in Tamil or Hindi, but fact-check coverage and NLP tooling are strongest in English.

### How it works

0. **Input is the redacted text** produced by the privacy shield (D1); nothing personal is sent to a translator.
1. **Detect the language** of the pasted text.
2. **English passes straight through.**
3. **Tamil and Hindi are translated** to English with an open model such as AI4Bharat IndicTrans2 or a hosted translation API. The original text is kept for display.
4. **Fail safe:** if translation fails, the agent still runs on the cues that survive and will usually return Unverified.

### Stack mapping

| Tool | Role in this stage |
| --- | --- |
| **langdetect** | Language identification |
| **IndicTrans2 or hosted API** | Tamil and Hindi to English |

## 4. Stage 2: Information Extraction

*Module 7.4: Information Extraction*

### The problem it owns

A forward is mostly noise around a small checkable claim. Everything downstream needs that claim isolated.

### How it works

1. **Extract** people, organisations, places, dates, amounts, phone numbers and URLs with spaCy named-entity recognition plus regular expressions.
2. **Pick the claim:** the sentence with the highest check-worthiness score, meaning it contains a number, a named entity, or a cure, offer or warning verb.
3. **Emit a claim record** (claim text, entities, numbers, links) used by every later stage.

### Stack mapping

| Tool | Role in this stage |
| --- | --- |
| **spaCy** | Sentence splitting and named entities |
| **Regular expressions** | Numbers, dates, phone numbers, URLs |

## 5. Stage 3: Retrieval

*Modules 7.3 Information Retrieval and 2.4 Best-First Search*

### The problem it owns

Has someone already ruled on this claim, and is a trusted outlet reporting it?

### How it works

1. **Two indexes, one engine:** fact-checks (claim text, rating, publisher, link) and trusted-outlet headlines.
2. **Fact-check source:** the Google Fact Check Tools API claim search, cached locally in SQLite. Check its current terms and quotas before relying on it.
3. **Rank by TF-IDF cosine similarity**, and expand only the best five, a best-first top-k.
4. **Set the nodes:** a match above a tuned threshold sets Fact-check match (rating normalised to refuted or supported) or Corroboration. Below it, the node reads none or no.
5. **Variant channel (D2):** if no TF-IDF match is found but the claim's rumour family is linked to a fact-check, the linked rating sets the Fact-check match node and the record is marked `variant`.

### Data model (SQLite)

```
factchecks (id, claim_text, rating, publisher, url, date, lang)
headlines  (id, title, domain, url, date)
```

### Stack mapping

| Tool | Role in this stage |
| --- | --- |
| **scikit-learn** | TF-IDF vectoriser and cosine similarity |
| **SQLite** | Local cache of fact-checks and headlines |
| **Google Fact Check Tools API** | Source of fact-check records |

## 6. Stage 4: Cue Scoring

*Module 7.2: Probabilistic Language Processing*

### The problem it owns

When no fact-check exists, the message itself still carries weak evidence about its reliability.

### How it works

1. **Source credibility:** the domain of any link is looked up in a short curated list of trusted and low-credibility domains. No link means unknown. The lookalike-link guard (D3) can force the state to low.
2. **Sensational tone:** a unigram and bigram naive Bayes model trained on labelled messages, plus a small lexicon of alarm words and excess punctuation.
3. **Verifiable details:** at least two of named person or organisation, date, place or link.

### Data model (SQLite)

```
domains (domain, class)   -- class: trusted | low
```

### Stack mapping

| Tool | Role in this stage |
| --- | --- |
| **scikit-learn** | Naive Bayes tone model |
| **SQLite** | Curated domain list |
| **spaCy** | Entities for the details cue |

## 7. Stage 5: The Bayesian Belief Network

*Modules 5.1 to 5.5*

### The problem it owns

Five weak, partly conflicting signals have to become one calibrated belief, with the right to abstain.

### The structure

One hidden node (is the claim true) and five observed nodes. Source credibility sits upstream because who sends a claim changes how likely it is to be true. The truth of the claim then explains each piece of evidence.

```
                 [Source credibility]
                          |
                          v
                   [Claim is true]   (hidden)
                          |
     +-----------+--------+--------+-------------+
     v           v                 v             v
[Fact-check] [Corroboration] [Sensational] [Verifiable
   match                         tone        details]
```

| Node | States | How it is observed | Parent |
| --- | --- | --- | --- |
| **Source credibility** | trusted, unknown, low | Domain list lookup; lookalike guard (D3) forces low | none |
| **Claim is true** | true, false | Hidden, inferred | Source credibility |
| **Fact-check match** | refuted, supported, none | Rating of the best TF-IDF match above threshold, or the rating linked to a matching rumour family (D2) | Claim |
| **Corroboration** | yes, no | Trusted-outlet headline matches above threshold | Claim |
| **Sensational tone** | high, low | Cue model score above threshold | Claim |
| **Verifiable details** | yes, no | Count of names, dates, places, links | Claim |

### How it works

1. **Parameters:** about forty probabilities. Start from expert priors, then learn them from the labelled development set with pgmpy's Bayesian estimator, using the priors as pseudo-counts so empty cells never become zero.
2. **Exact inference:** variable elimination gives P(true) and P(false) for each message.
3. **Approximate inference (Module 5.4):** likelihood weighting, written by hand in about thirty lines, runs beside exact inference. A short plot of error against sample count shows it converging.
4. **Decision rule:** if P(false) is at least 0.75 the verdict is **Likely false**; if P(true) is at least 0.75 it is **Likely true**; otherwise **Unverified**. 0.75 is a starting value, tuned on the development set.

### Stack mapping

| Tool | Role in this stage |
| --- | --- |
| **pgmpy** | Network definition, parameter learning, variable elimination |
| **Python (hand-written)** | Likelihood weighting and the decision rule |

> **DEMO MOMENT**
>
> *The belief network is drawn on screen. A message goes in, the evidence nodes light up, and P(true) moves visibly as each piece of evidence is applied.*

## 8. Stage 6: Reasons and What-If

*USPs 2 and 3*

### The problem it owns

A probability alone is not trusted. People need to see why, and what would change it.

### How it works

1. **Reasons:** for each observed node, recompute the posterior with that node left out. The size of the change is that node's contribution; contributions are shown in order.
2. **What-if:** for each node, set it to its most informative alternative state and recompute. The largest shift becomes the hint, for example "a trusted outlet reporting this would raise P(true) substantially".

### Stack mapping

| Tool | Role in this stage |
| --- | --- |
| **pgmpy** | Repeated inference with evidence removed or changed |
| **Streamlit** | Reasons panel and what-if card |

## 9. Stage 7: Reply Card

*USP 5*

### How it works

A template fills in the verdict, one sentence of the top reason and the fact-check link. It is deliberately polite and short so a person can forward it to a family group without sounding accusatory.

## 10. D1: Privacy Shield

*Runs first, before Stage 1. Module 7.4: Information Extraction*

### The problem it owns

Forwards often contain phone numbers, payment handles and ID numbers. Sending the raw message to a translator, a fact-check search or a hosted model leaks them, and so does storing it.

### How it works

1. **Match identifiers** with fixed regular expressions for the types below.
2. **Replace** each match with a tag such as `[PHONE]`.
3. **Use only the redacted text** from here on: for the message hash, the fingerprint, translation and every external query.
4. **Report** the count per type in the verdict record (`redactions`) so the UI can show what was removed.
5. **State the limit:** this covers the listed identifier types only. Names and addresses are not removed, so it is redaction, not anonymisation.

| Type | Covers |
| --- | --- |
| **PHONE** | 10-digit mobile numbers starting 6 to 9, with or without +91 and with space or hyphen groups |
| **EMAIL** | Standard e-mail addresses |
| **UPI** | Handles of the form name@bank for a configured list of bank suffixes |
| **CARD** | 16 digits in groups of four |
| **ID12** | 12 digits in groups of four |

### Stack mapping

| Tool | Role in this stage |
| --- | --- |
| **Python `re`** | Pattern matching and replacement; no network, no model |

> **DEMO MOMENT**
>
> *Paste a forward containing a phone number. The UI shows it already replaced by [PHONE] and says how many items were removed before anything left the machine.*

## 11. D2: Rumour Fingerprint

*Module 7.3: Information Retrieval (near-duplicate detection)*

### The problem it owns

The same rumour is forwarded with greetings, emojis, small edits and reordered lines. Recognising these as one family needs an identity that survives edits and does not require keeping the text.

### How it works

1. **Normalise:** Unicode NFKC, lower-case, drop punctuation and emoji, collapse whitespace.
2. **Shingle:** character 5-grams of the normalised claim.
3. **Hash and combine:** each shingle is hashed to 64 bits (blake2b, 8 bytes); each bit position gets a vote of +1 or -1 by shingle; the sign of each total gives one bit of the 64-bit SimHash.
4. **Match:** the Hamming distance to every stored fingerprint is computed; a distance at or below `SIMHASH_MAX_HAMMING` (initial value 14, to be tuned on development data) puts the claim in that family.
5. **Record:** a new family is created if none match; otherwise the family gets another hit.
6. **Link:** a family created from a cached fact-check carries `linked_factcheck_id`, which lets a variant set the Fact-check match node when TF-IDF finds nothing.
7. **Store only:** the fingerprint, up to five non-personal keywords, the language, hourly hits and the latest verdict. Never the text.

### Reference run (synthetic text, illustration of the method)

A made-up rumour sentence ("hot lemon water cures diabetes") and six variants, compared with the original:

| Variant | Hamming distance | TF-IDF cosine |
| --- | --- | --- |
| V1 greeting, emojis and "forward to all" added | 11 | 0.777 |
| V2 upper-case, punctuation changed | 0 | 1.000 |
| V3 sentences reordered | 8 | 1.000 |
| V4 two words replaced | 11 | 0.821 |
| V5 heavy rewrite, same meaning | 33 | 0.143 |
| V6 unrelated message (control) | 34 | 0.050 |

Four unrelated scam or hoax sentences used as distractors lay at 24 to 36. On this tiny set a threshold of 14 separates light edits from unrelated text; it must be tuned on real data. The heavy rewrite is not matched. TF-IDF also matched the light edits, so the fingerprint is **not** claimed to be more accurate; its value is a compact, text-free identity for family counting.

### Data model (SQLite)

```
rumours (family_id, fingerprint, keywords, language, linked_factcheck_id,
         first_seen, last_seen, last_verdict)
```

### Stack mapping

| Tool | Role in this stage |
| --- | --- |
| **Python `hashlib`** | 64-bit shingle hashes |
| **scikit-learn** | TF-IDF weights for keyword selection |
| **SQLite** | Fingerprint and family storage |

## 12. D3: Lookalike-Link Guard

*Module 7.4 (domain extraction) feeding Module 5 (source node)*

### The problem it owns

Scam and phishing forwards often link to a domain that imitates a trusted site by one changed character, a swapped letter or an added hyphen.

### How it works

1. **Extract** the domain of every link in the claim and in the optional request URL; strip `www.`.
2. **Trusted:** the domain equals, or is a subdomain of, an entry in the trusted list.
3. **Shortener:** a known shortener domain is marked `shortener`, state unknown, because the target is hidden.
4. **Look-alike characters:** replace 0 with o, 1 with l, 5 with s, rn with m and vv with w, remove hyphens, and compare with each trusted domain.
5. **Edit distance:** the Levenshtein distance to a trusted domain of at least 6 characters at or below `LOOKALIKE_MAX_EDIT` (2) also counts.
6. **Result:** a lookalike sets `source_cred = low`. Low dominates trusted if both appear.

### Reference run (hand-made domains, 7 trusted entries)

| Tested | Result | Correct |
| --- | --- | --- |
| pib-gov.in, wh0.int, thehindu.co, thehlndu.com, reuters.corn | Lookalike | 5 of 5 |
| ndtv.in (three edits from ndtv.com) | Not flagged | Missed |
| bbc.com, news.bbc.com, indianexpress.com, who.int | Trusted | 4 of 4 |
| wikipedia.org, example.org | Unlisted | 2 of 2 |
| bit.ly | Shortener, unknown | Yes |

5 true flags, 0 false flags, 1 miss. A distance-2 rule misses distant spellings, and a legitimate sister domain of a trusted site would be a false flag, so the trusted list must include known sister domains.

### Stack mapping

| Tool | Role in this stage |
| --- | --- |
| **Pure Python** | Levenshtein distance and character mapping; no network, no model |
| **SQLite `domains`** | Trusted and low-credibility entries |

## 13. D4: Evidence Passport

*Modules 5.2 and 8.2: Applying Bayes' Rule, Critical Evaluation*

### The problem it owns

A probability is only useful if a user or an examiner can check where it came from, and a verdict that cannot be reproduced cannot be audited.

### How it works

1. **Grounded-only rule:** every sentence shown comes from a template or from a retrieved record (publisher, rating, link, similarity). No factual sentence is generated.
2. **Passport fields:** `index_version` (hash of the fact-check and headline data at index build), `cpt_version` (hash of the CPT file in use), `threshold`, `created_at` and `passport_id`.
3. **Passport id:** a hash of the message hash, index version, CPT version and threshold. The same input with the same versions gives the same id and the same verdict record.
4. **Display:** an expandable panel lists every match with its link and score, then the version stamps.

### Stack mapping

| Tool | Role in this stage |
| --- | --- |
| **Python `hashlib`** | Version hashes and passport id |
| **Streamlit** | Passport panel |

## 14. D5: Rumour Radar

*Modules 7.3 and 8.2*

### The problem it owns

Fact-checkers and users cannot see which unverified rumours are spreading right now. A one-off question to a chatbot has no view across users.

### How it works

1. **Count:** each check adds one row to `rumour_hits(family_id, hour, message_hash)`; the same message hash in the same hour counts once.
2. **Surge:** (checks in the last 24 hours + 1) divided by (checks in the previous 24 hours + 1).
3. **List:** families whose latest verdict is Unverified, ranked by surge, then by recent count.
4. **Privacy rules:** a family appears only after at least `RADAR_MIN_COUNT` (3) checks; only keywords and any linked fact-check are shown; time is bucketed by hour; no message text exists to show.
5. **Scope:** the Radar is triage, not truth. It never changes a verdict.

```
 [Claim, redacted] -> [normalise, 5-grams] -> [SimHash 64-bit] -> [Hamming vs stored]
                                                                      |
                              +---------------------------------------+
                              v                                       v
                 [within threshold: same family,         [beyond threshold: new family]
                  add hit]                                            |
                              +---------------------------------------+
                                                v
                              [rumours + rumour_hits (SQLite)]
                                                v
                              [Radar: surge, 3+ checks, Unverified only]
```

### Reference run (simulated counts, not measured usage)

| Family (simulated) | Previous 24 h | Last 24 h | Surge |
| --- | --- | --- | --- |
| F3 scheme money claim | 0 | 12 | 13.00 |
| F1 miracle cure forward | 3 | 40 | 10.25 |
| F2 recharge scam | 25 | 28 | 1.12 |
| F4 old hoax | 10 | 2 | 0.27 |

A small, fast-rising family outranks a larger, steady one, which is the intended early-warning behaviour.

### Stack mapping

| Tool | Role in this stage |
| --- | --- |
| **SQLite** | `rumours` and `rumour_hits` |
| **FastAPI** | `GET /radar` |
| **Streamlit** | Radar page |

> **DEMO MOMENT**
>
> *Check the same unverified rumour from several edited copies. They land in one family, and the Radar lists it near the top with its surge score and keywords, but no message text.*

## 15. Data Model and API

Everything runs locally. The full message text is never stored. Only a hash of the redacted text, a fingerprint and a few keywords are kept, so no table can be used to reconstruct what people pasted.

### 15.1 Tables

| Table | Columns | Purpose |
| --- | --- | --- |
| **factchecks** | id, claim_text, rating, publisher, url, date, lang | Cached fact-check records |
| **headlines** | id, title, domain, url, date | Trusted-outlet headlines |
| **domains** | domain, class | Curated source-credibility list |
| **feedback** | id, message_hash, verdict, user_label, timestamp | "Was this right?" taps for threshold tuning |
| **rumours** | family_id, fingerprint, keywords, language, linked_factcheck_id, first_seen, last_seen, last_verdict | Rumour families (D2) |
| **rumour_hits** | family_id, hour, message_hash | One row per distinct check per hour, for the Radar (D5) |

### 15.2 Endpoints

| Endpoint | Input | Output |
| --- | --- | --- |
| **POST /check** | text, optional url | Verdict record |
| **POST /feedback** | message_hash, verdict, user_label | Acknowledgement |
| **GET /radar** | optional window_hours, limit | Surging Unverified families with keywords and surge score (D5) |
| **GET /health** | none | Index sizes and last refresh time |

A verdict record, with illustrative values:

```json
{
  "verdict": "likely_false",
  "p_true": 0.09,
  "claim": {"text": "...", "entities": ["..."], "numbers": ["..."], "links": []},
  "matches": [{"publisher": "...", "rating": "refuted", "url": "...", "similarity": 0.81}],
  "reasons": [{"node": "fact_check", "state": "refuted", "shift": -0.62}],
  "what_if": [{"node": "corroboration", "state": "yes", "p_true": 0.35}],
  "reply_card": "...",
  "message_hash": "...",
  "evidence": {"source_cred": "unknown", "fact_check": "refuted", "corroboration": "no", "sensational": "high", "specifics": "no"},
  "redactions": {"PHONE": 1},
  "lookalikes": [{"domain": "...", "lookalike_of": "...", "distance": 1, "kind": "lookalike"}],
  "family": {"family_id": "...", "hamming": 3, "linked_rating": "refuted", "source": "variant"},
  "passport": {"passport_id": "...", "index_version": "...", "cpt_version": "...", "threshold": 0.75, "created_at": "..."}
}
```

### 15.3 Stack

| Layer | Tool | Role |
| --- | --- | --- |
| **Language and API** | Python, FastAPI | Pipeline and the three endpoints |
| **UI** | Streamlit | Paste box, verdict card, reasons panel, network view |
| **NLP** | spaCy, langdetect | Entities, sentence splitting, language detection |
| **Retrieval and cue model** | scikit-learn | TF-IDF index, cosine similarity, naive Bayes tone model |
| **Privacy and fingerprints** | Python `re`, `hashlib` | Redaction patterns, 64-bit SimHash, version hashes |
| **Belief network** | pgmpy | Network definition, parameter learning, variable elimination |
| **Translation** | IndicTrans2 or a hosted API | Tamil and Hindi to English |
| **Storage** | SQLite | Caches, domain list, feedback, rumour families and hits |
| **Testing** | pytest | Unit tests per stage, plus an end-to-end test set |

## 16. Evaluation Plan

The project is judged on whether the Bayesian agent is measurably better calibrated than a plain classifier, and on whether its reasons make sense to a non-expert.

- **Dataset:** target of 300 labelled messages, split 200 for development and 100 for testing, built from published fact-checks and verified true items, with a Tamil and Hindi subset.
- **Baseline:** TF-IDF plus logistic regression on the same split.
- **Metrics:** retrieval precision@3, macro-F1, Brier score and abstention quality.
- **Differentiator metrics:** variant recall and false family matches for D2 on a set of edited and unrelated messages; precision, recall and misses for D3 on a hand-made domain list; redaction recall for D1 on synthetic strings including clean ones that must stay unchanged; identical verdict records on repeated runs for D4; and an automated check that the Radar never shows a family with fewer than 3 checks and no table holds message text for D5.
- **Ablation:** drop each evidence node in turn and record the change in macro-F1, to show what each cue contributes.
- **Inference check:** error of likelihood weighting against exact inference at increasing sample counts.

## 17. Risks, Build Plan and Priority

### 17.1 Risks and mitigations

| Risk | Effect | Mitigation |
| --- | --- | --- |
| **New rumours have no fact-check yet** | Many messages return Unverified | By design; show cues and the what-if hint, refresh the cache regularly |
| **Fact-check API quota or terms change** | Retrieval stalls | Local cache plus a bundled seed set of fact-checks |
| **Translation errors in Tamil or Hindi** | Wrong match or cue | Show the translated claim; lean to Unverified when unsure |
| **Users over-trust the verdict** | Harm from a wrong call | Always show reasons and links; never a single word like "FAKE" |
| **Biased trusted-source list** | Skewed verdicts | Keep the list public and editable; the reasons panel shows when it mattered |
| **Small labelled set** | Noisy probabilities | Expert priors as pseudo-counts; report the test-set size with results |
| **Fingerprint matches an unrelated message** | Wrong family or verdict | Conservative Hamming threshold tuned on development data; a family sets a verdict only when linked to a fact-check |
| **Heavy rewrites escape the fingerprint** | Variant not recognised | TF-IDF retrieval remains the main channel; report variant recall honestly |
| **Lookalike rule flags a legitimate sister domain** | Wrongly low credibility | Keep known sister domains in the trusted list |
| **Redactor misses names or addresses** | Personal data retained | State the covered types; never claim anonymisation |
| **Radar shows one user's message** | Privacy harm | Keywords only; minimum 3 checks; hourly buckets |
| **Radar counts gamed by repeated checks** | False surge | One count per message hash per hour; Radar is triage, never truth |

### 17.2 Build plan

1. **Week 1, data and retrieval:** SQLite schema, fact-check cache, TF-IDF retrieval, precision@3 measured, privacy shield (D1).
2. **Week 2, extraction and cues:** spaCy extraction, tone model, domain list, lookalike-link guard (D3), labelled set assembled.
3. **Week 3, belief network:** parameters learned, exact and likelihood-weighted inference, decision rule, reasons and what-if, rumour fingerprint (D2).
4. **Week 4, UI, languages and evaluation:** Streamlit page, Tamil and Hindi path, evidence passport (D4), Rumour Radar (D5), ablation and baseline comparison, demo rehearsal.

### 17.3 Build priority

| Component | v1 | Demo weight |
| --- | --- | --- |
| **Belief network with reasons panel** | Build fully | Primary: a verdict with its reasons |
| **Fact-check retrieval** | Build fully | Primary: the matched fact-check link |
| **What-if hint and reply card** | Build fully | Primary: the moment it becomes useful |
| **Cue scoring** | Build core | Secondary |
| **Tamil and Hindi path** | Translation route | Secondary |
| **Likelihood weighting plot** | Build | Secondary: shows Module 5.4 |
| **Privacy shield (D1)** | Build fully | Primary: redaction shown live |
| **Rumour fingerprint (D2)** | Build fully | Primary: an edited copy joins the family |
| **Lookalike-link guard (D3)** | Build fully | Primary: a fake link flagged |
| **Evidence passport (D4)** | Build core | Secondary: expandable panel |
| **Rumour Radar (D5)** | Build fully | Primary: surging list |

Stretch, only if time allows: a Telegram bot, text extraction from forwarded images, a feedback-driven threshold re-tuning loop.

### 17.4 References to confirm before building

These were not re-opened while writing this document, so check current terms and install steps first.

- Google Fact Check Tools API: https://developers.google.com/fact-check/tools/api
- pgmpy documentation: https://pgmpy.org
- AI4Bharat IndicTrans2: https://github.com/AI4Bharat/IndicTrans2
- spaCy: https://spacy.io

## 18. Demo Script

1. Paste a widely debunked health forward that contains a phone number. The number appears as [PHONE], and VERITY returns **Likely false** with the fact-check link.
2. Open the reasons panel and the evidence passport, and show which evidence moved the number most and which versions produced it.
3. Paste an alarmist message with no fact-check. VERITY returns **Unverified** and shows the what-if hint.
4. Paste an edited copy of the first forward (greeting and emojis added). It joins the same rumour family.
5. Paste a message with a link that imitates a trusted site. The lookalike warning appears and the source drops to low.
6. Paste a Tamil message and show the translated claim and the verdict.
7. Open the Rumour Radar and show the surging Unverified family, then the reply card and the likelihood-weighting convergence plot.

> **The loop**
>
> **Redact** protects the user → **Extract** isolates the claim → **Retrieve, fingerprint and score cues** gather independent evidence → **Belief network** combines it all → **Reasons, what-if and passport** explain and certify the answer → **Reply card** helps the user act on it → **Radar** shows what is spreading.

**VERITY** *: a misinformation checker that shows its work, and admits when it does not know.*
