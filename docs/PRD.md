**Product Requirements Document**

# VERITY

**Privacy-First, Explainable Misinformation Triage Agent**

*Don't just say fake or real. Show how sure we are, and why.*

| | |
| --- | --- |
| **Document** | PRD v1.1 (companion to the TRD) |
| **Author** | V Rohith Pranov (24BCE0619) |
| **Scope** | Problem, users, goals, features, USPs, success metrics, scope and risks |
| **Course** | Artificial Intelligence, Modules 1 to 8 |
| **Project type** | Applied AI: misinformation triage for forwarded messages |
| **Core techniques** | TF-IDF retrieval, information extraction, Bayesian belief network, what-if inference, SimHash rumour fingerprints, edit-distance link guard, regex privacy redaction |
| **Core stack** | Python, FastAPI, spaCy, scikit-learn, pgmpy, Streamlit |
| **Date** | 29 October 2026 |

## Contents

1. Overview (including "Why not just ask a chatbot?" and the architecture at a glance)
2. Users and use cases
3. Goals and non-goals
4. Syllabus mapping
5. Features (MVP)
6. USPs and differentiators
7. User flow
8. Success metrics
9. Scope, priority and risks

---

## 1. Overview

VERITY is a small AI agent that checks a forwarded message and answers with a **verdict, a probability and the reasons behind it**, instead of a bare "fake" or "real". It is built on Modules 5, 7 and 8 of the syllabus (Bayesian reasoning, information retrieval and extraction, misinformation), with Module 1 framing it as an intelligent agent.

### 1.1 The problem

Health cures, scam offers and fake government-scheme messages spread through family WhatsApp groups faster than anyone can verify them. Fact-check articles exist, but they are long, mostly in English, and the person who received the forward rarely goes looking. Black-box classifiers that print "87% fake" do not help either: the user cannot tell why, so they ignore it.

### 1.2 The idea

Paste or forward a message. VERITY pulls out the checkable claim, searches published fact-checks for a match, scores simple evidence cues (source, wording, verifiable details), and feeds all of it into a Bayesian belief network. The output is one of three verdicts (**Likely false, Unverified, Likely true**), the probability behind it, and a plain-language list of what moved the number. Around that core sit five differentiating features (D1 to D5, section 5.1): a privacy shield, rumour fingerprints, a lookalike-link guard, an evidence passport and a Rumour Radar.

> **Why a Bayesian network**
>
> Evidence about a message is uncertain and partial, which is exactly what Module 5 teaches. A belief network also gives the project its main advantage over a text classifier: every probability can be traced to named evidence, and the agent is allowed to say "I don't know".

### 1.3 Why not just ask a chatbot?

Pasting a message into a general chatbot and asking "is this true?" is the obvious alternative, and it often gives a useful answer. VERITY is designed around what that single question typically does not give. The comparison is about defaults and guarantees, not about what is impossible.

| Aspect | Asking a chatbot | VERITY |
| --- | --- | --- |
| **Probability** | Often a confident sentence; any number is usually not calibrated or measured | Posterior from a belief network, evaluated with Brier score on a labelled set |
| **Not knowing** | May still produce an answer | Built-in Unverified verdict at a tuned threshold |
| **Sources** | May be missing or may not exist | Only retrieved fact-check records, each with link and similarity score (D4) |
| **Repeatability** | The answer can change between runs | Same input, same index and model versions give the same output (D4) |
| **What is circulating** | No view of what other users are checking | Rumour fingerprints and the Radar across all checks (D2, D5) |
| **Fake links** | Cannot reliably judge a domain it has not seen | Edit-distance and look-alike rules against a trusted list (D3) |
| **Privacy** | The full message, with personal data, goes to a third party | Personal data removed first; only the redacted claim leaves the device (D1) |

### 1.4 Architecture at a glance

Starred stages in the diagram are the differentiating features. The full diagram is in the TRD.

```
 External (redacted claim only): Fact Check API . translator . trusted feeds
                                         :
 [User message] -> [*Privacy shield D1*] -> [Language] -> [Extract claim]
                                                                |
                 +----------------------+-----------------------+
                 v                      v                       v
        [Fact-check retrieval]  [*Rumour fingerprint D2*]  [Cue scoring:
         TF-IDF cosine, top-k    SimHash variant match      source + *lookalike D3*,
                 |                      |                   tone, details]
                 +----------------------+-----------------------+
                                        v
                          [ Bayesian belief network ]
                          6 nodes, exact inference, 3-way rule
                                        |
                      +-----------------+------------------+
                      v                                    v
      [*Explanation + Evidence passport D4*]      [*Rumour Radar D5*]
       reasons, what-if, reply card, versions      surging unverified families

 SQLite (local): factchecks, headlines, domains, rumours, rumour_hits, feedback
 (no message text is ever stored)
```

## 2. Users and use cases

The primary user is an ordinary smartphone user who receives forwards and wants a fast second opinion in under a minute, without reading a fact-check article.

| User | Situation | What they need |
| --- | --- | --- |
| **Family-group member** | Gets a "miracle cure" or "free recharge" forward | A quick verdict and a short reply to send back |
| **Student or journalist** | Wants to triage many claims | Evidence links and the reasoning, not just a label |
| **Course evaluator** | Wants to see AI concepts applied | A visible belief network and a clear module-to-feature mapping |

## 3. Goals and non-goals

### Goals

1. Return a verdict, a probability and a ranked list of reasons for any pasted message.
2. Abstain honestly when evidence is thin, using the Unverified verdict.
3. Work on English, Tamil and Hindi input.
4. Run end to end on a laptop with free or open tools.
5. Keep personal data on the user's device: nothing with a phone number, UPI handle or ID number is stored or sent to an outside service.
6. Recognise edited copies of a known rumour and show which unverified rumours are surging.

### Non-goals

- Not a general truth oracle. VERITY judges claims that have fact-check coverage or clear cues, and says so otherwise.
- No image, video or audio forensics in v1.
- No account system, no social-media crawling, no user tracking.
- No crowd verdicts. The Radar counts how often a rumour is checked; it never votes on whether it is true.

## 4. Syllabus mapping

VERITY is anchored in Module 5 (CO3) and Module 7 (CO6), framed by Module 1 (CO1) and justified by Module 8 (CO6). Modules 3, 4 and 6 are not needed, and the project does not force them in.

| Module | Topic (Bloom's level) | Where it appears in VERITY | Weight |
| --- | --- | --- | --- |
| 1 | 1.3 Applications of AI (Apply) | Real-world use case: misinformation triage | Core |
| 1 | 1.5 Intelligent Agents (Apply), 1.6 Environments (Evaluate) | PEAS description and environment classification (TRD) | Core |
| 2 | 2.4 Best-First Search (Evaluate) | Candidate fact-checks ranked and expanded best-first, top-k only | Light |
| 5 | 5.1 Uncertainty and Bayes' Rule (Understand) | Verdict is a posterior probability, not a hard label | Core |
| 5 | 5.2 Applying Bayes' Rule (Apply) | CPT design and posterior update from evidence | Core |
| 5 | 5.3 Building Bayesian Belief Networks (Analyze) | The six-node network (TRD) | Core |
| 5 | 5.4 Approximate Inference (Evaluate) | Exact inference compared with likelihood weighting | Core |
| 5 | 5.5 Case Study and Application (Create) | The whole project is the case study | Core |
| 7 | 7.1 Communication and Language (Understand) | Language detection, Tamil/Hindi/English handling | Light |
| 7 | 7.2 Probabilistic Language Processing (Analyze) | N-gram sensational-wording score | Core |
| 7 | 7.3 Information Retrieval (Evaluate) | TF-IDF retrieval over fact-checks, judged by precision@k | Core |
| 7 | 7.4 Information Extraction (Create) | Claim, entity, number, date and link extraction | Core |
| 7 | 7.3 Information Retrieval (Evaluate) | D2 rumour fingerprint (SimHash near-duplicate matching) and D5 Radar families | Core |
| 7 | 7.4 Information Extraction (Create) | D1 privacy shield (identifier extraction and redaction) and D3 link and domain extraction | Core |
| 5 | 5.2 Applying Bayes' Rule (Apply) | D3 sets the source_cred node; D4 reasons and what-if reuse the same inference | Core |
| 8 | 8.1 and 8.2 Misinformation, Critical Evaluation (Understand, Analyze) | The problem domain and the "what to check next" advice | Core |

## 5. Features (MVP)

Seven features, all reachable from one screen.

| ID | Feature | Behaviour |
| --- | --- | --- |
| **F1** | Message input | Paste text in English, Tamil or Hindi; optional URL |
| **F2** | Claim extraction | Pulls the core claim, entities, numbers, dates and links |
| **F3** | Fact-check match | Retrieves the closest published fact-checks with a similarity score |
| **F4** | Evidence cues | Scores source credibility, sensational wording, verifiable details |
| **F5** | Bayesian verdict | Likely false, Unverified or Likely true, with probability |
| **F6** | Reasons panel | Ranked list of which evidence moved the verdict and by how much |
| **F7** | Reply card | Short, polite text the user can send back to the group |

### 5.1 Differentiating features (D1 to D5)

| ID | Feature | Behaviour |
| --- | --- | --- |
| **D1** | Privacy shield | Redacts phone numbers, e-mail, UPI handles, 16-digit card and 12-digit ID numbers on the user's device before anything is stored, fingerprinted, translated or sent out |
| **D2** | Rumour fingerprint | A 64-bit SimHash of the claim; edited forwards within a Hamming threshold join the same rumour family; a family linked to a fact-check can set the fact-check evidence even when TF-IDF misses |
| **D3** | Lookalike-link guard | Flags a link within edit distance 2 of a trusted domain, or equal to one after look-alike character replacement; marks shorteners as unknown; feeds the source node |
| **D4** | Evidence passport | Each verdict carries sources, scores, index version, model version, threshold, time and a passport id; all text shown comes from templates or retrieved records, never generated facts |
| **D5** | Rumour Radar | Hourly counts per rumour family; lists Unverified families ranked by surge = (last 24 h + 1) / (previous 24 h + 1); a family is shown only after at least 3 checks |

## 6. USPs and differentiators

The first five USPs cost little because the Bayesian network already holds the information. The five differentiators that follow are what separate VERITY from simply asking a chatbot.

1. **Honest abstention.** The Unverified verdict is a first-class output. If no fact-check matches and cues are mixed, VERITY says so instead of guessing.
2. **Reasons, not just a score.** Each evidence node's effect is measured by recomputing the posterior with and without it, then ranked.
3. **What-if hints.** "If a trusted outlet reported this, the probability of Likely true would rise from X to Y." The user learns what to look for next (Module 8.2). Real values come from the network.
4. **Regional language input.** Tamil and Hindi messages are handled, since that is where many forwards live.
5. **Reply card.** One tap produces a calm, non-confrontational reply with the evidence link, which is the step that actually stops a forward.

### The five differentiators

6. **Privacy shield (D1).** Personal identifiers never leave the device, which matters because forwards often contain phone numbers and payment handles.
7. **Rumour fingerprint (D2).** Edited copies of the same rumour are recognised as one family without storing the text.
8. **Lookalike-link guard (D3).** A link such as a trusted site with one changed letter is treated as low credibility by rule, which is checkable and does not depend on a guess.
9. **Evidence passport (D4).** A verdict can be reproduced and audited, and nothing in it is an unsourced statement.
10. **Rumour Radar (D5).** A privacy-preserving early warning of which unverified claims are spreading right now. A one-off chatbot question cannot see this because it has no view across users.

> **DEMO MOMENT**
>
> *A forward with a phone number is pasted and the number is shown redacted. A debunked one comes back "Likely false" with the fact-check link and ranked reasons; an alarmist one with no match comes back "Unverified" with a what-if hint. A lookalike link is flagged, an edited copy of a known rumour lands in the same family, and the Radar shows which unverified rumour is surging. The tool shows its work, and admits when it cannot.*

## 7. User flow

1. User pastes a message (and optionally a link).
2. The privacy shield redacts personal identifiers and shows what it removed.
3. VERITY shows the extracted claim, so the user can confirm it read the right thing.
4. VERITY returns the verdict card: verdict, probability, matched fact-checks, any lookalike-link warning and the rumour family it belongs to.
5. User opens the reasons panel, the what-if hint and the evidence passport.
6. User taps the reply card to copy a ready-made response.
7. User taps "was this right?" so the thresholds can be re-tuned later.
8. Anyone can open the Rumour Radar to see which unverified rumours are surging.

## 8. Success metrics

Targets, to be measured on the team's own labelled test set.

| Metric | Target | How measured |
| --- | --- | --- |
| **Retrieval precision@3** | 0.70 or higher | Correct fact-check in top 3 on labelled claims |
| **Verdict macro-F1** | Beats a TF-IDF + logistic regression baseline | Same 100-message test set |
| **Calibration (Brier score)** | Lower than the baseline | Predicted probability vs actual label |
| **Abstention quality** | Most Unverified cases are ones with no matching fact-check | Manual review of Unverified outputs |
| **Response time** | Under 3 seconds per message on a laptop | Timed end to end |
| **Variant recall (D2)** | Most light edits of a known rumour land in its family, with few false family matches | Synthetic set of edited variants plus unrelated messages |
| **Lookalike guard (D3)** | High precision and recall on a hand-made list of lookalike and legitimate domains | Small labelled domain list; misses and false flags reported |
| **Redaction recall (D1)** | Every supported identifier type removed on a test set | Synthetic strings, including clean ones that must stay unchanged |
| **Reproducibility (D4)** | Same input and versions give an identical verdict record | Repeated runs compared |
| **Radar privacy (D5)** | No family shown with fewer than 3 checks; no message text in storage | Automated test |

## 9. Scope, priority and risks

### 9.1 Build priority

| Component | v1 | Demo weight |
| --- | --- | --- |
| **Belief network with reasons panel** | Build fully | Primary: a verdict with its reasons |
| **Fact-check retrieval** | Build fully | Primary: the matched fact-check link |
| **What-if hint and reply card** | Build fully | Primary: the moment it becomes useful |
| **Cue scoring** | Build core | Secondary |
| **Tamil and Hindi path** | Translation route | Secondary |
| **Likelihood weighting plot** | Build | Secondary: shows Module 5.4 |
| **Privacy shield (D1)** | Build fully | Primary: redaction shown live |
| **Rumour fingerprint (D2)** | Build fully | Primary: edited copy joins the family |
| **Lookalike-link guard (D3)** | Build fully | Primary: a fake link flagged |
| **Evidence passport (D4)** | Build core | Secondary: expandable panel |
| **Rumour Radar (D5)** | Build fully | Primary: surging list |

Stretch, only if time allows: a Telegram bot, text extraction from forwarded images, a feedback-driven threshold re-tuning loop.

### 9.2 Product risks

| Risk | Effect | Mitigation |
| --- | --- | --- |
| New rumours have no fact-check yet | Many messages return Unverified | By design; show cues and the what-if hint |
| Users over-trust the verdict | Harm from a wrong call | Always show reasons and links; never a single word like "FAKE" |
| Biased trusted-source list | Skewed verdicts | Keep the list public and editable |
| Radar shows one user's message | Privacy harm | Store keywords, not text; show a family only after 3 checks |
| Radar counts gamed by repeated checks | False surge | Deduplicate by hour and message hash; treat Radar as triage only, never as truth |
| Fingerprint matches an unrelated message | Wrong family or verdict | Conservative Hamming threshold tuned on development data; a family can set a verdict only when linked to a fact-check |
| Lookalike rule flags a legitimate sister domain | Wrongly low credibility | Keep the trusted list including known sister domains |
| Redactor misses names or addresses | Personal data retained | State the covered identifier types; never claim full anonymisation |

**VERITY** *: a misinformation checker that shows its work, and admits when it does not know.*
