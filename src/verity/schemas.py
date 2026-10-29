"""Authoritative domain models (build spec B.2). Import these; never redefine them."""

from typing import Literal, NewType

from pydantic import BaseModel, ConfigDict


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# text that has passed through privacy.redact(); external clients accept ONLY this type
RedactedText = NewType("RedactedText", str)

# ----- enums -----
Language = Literal["en", "ta", "hi"]
SourceCredState = Literal["trusted", "unknown", "low"]
FactCheckState = Literal["refuted", "supported", "none"]
YesNo = Literal["yes", "no"]
ToneState = Literal["high", "low"]
Rating = Literal["refuted", "supported"]  # normalised fact-check rating
VerdictLabel = Literal["likely_false", "unverified", "likely_true"]
BNNode = Literal[
    "source_cred", "claim_true", "fact_check", "corroboration", "sensational", "specifics"
]
UserLabel = Literal["right", "wrong"]
GroundTruth = Literal["false", "true", "unverifiable"]  # labelled dataset only
RedactionType = Literal["PHONE", "EMAIL", "UPI", "CARD", "ID12"]  # D1
LinkKind = Literal["lookalike", "shortener"]  # D3
FamilySource = Literal["new", "existing", "variant"]  # D2


# ----- Stage 1 §3 : input -----
class PreparedText(Base):
    original: str  # the REDACTED text (never the raw message)
    language: Language
    english: str  # == original when language == 'en' or translation failed
    translation_ok: bool


# ----- Stage 2 §4 : claim record -----
class ClaimRecord(Base):
    text: str
    entities: list[str]
    numbers: list[str]
    links: list[str]


class ClaimSignals(Base):  # internal, feeds the 'specifics' cue
    has_person_org: bool
    has_date: bool
    has_place: bool
    has_link: bool


class ExtractedClaim(Base):
    claim: ClaimRecord
    signals: ClaimSignals


# ----- Stage 3 §5 : retrieval -----
class Match(Base):
    publisher: str
    rating: Rating
    url: str
    similarity: float


class HeadlineMatch(Base):
    title: str
    domain: str
    url: str
    similarity: float


# ----- Stage 5 §7 : belief network evidence -----
class Evidence(Base):
    source_cred: SourceCredState
    fact_check: FactCheckState
    corroboration: YesNo
    sensational: ToneState
    specifics: YesNo


class PartialEvidence(Base):  # None = unobserved (marginalised out)
    source_cred: SourceCredState | None = None
    fact_check: FactCheckState | None = None
    corroboration: YesNo | None = None
    sensational: ToneState | None = None
    specifics: YesNo | None = None


class Posterior(Base):
    p_true: float
    p_false: float


# ----- Stage 6 §8 : explanation -----
class Reason(Base):
    node: BNNode
    state: str
    shift: float  # p_true(all evidence) - p_true(without this node)


class WhatIf(Base):
    node: BNNode
    state: str
    p_true: float


# ----- D1..D5 : differentiators (TRD §10-§14) -----
class RedactionResult(Base):
    text: str  # redacted; wrap with RedactedText(...) at the single trusted call site
    counts: dict[RedactionType, int]


class LookalikeFlag(Base):
    domain: str
    lookalike_of: str | None
    distance: int | None
    kind: LinkKind


class FamilyInfo(Base):
    family_id: str
    hamming: int | None
    linked_rating: Rating | None
    source: FamilySource  # 'variant' only when the linked rating set the fact_check node


class Passport(Base):
    passport_id: str
    index_version: str
    cpt_version: str
    threshold: float
    created_at: str  # excluded from passport_id


class RadarItem(Base):
    family_id: str
    keywords: list[str]
    recent: int
    previous: int
    surge: float
    linked_url: str | None


# ----- Verdict record §15.2 -----
class VerdictRecord(Base):
    verdict: VerdictLabel
    p_true: float
    claim: ClaimRecord
    matches: list[Match]
    reasons: list[Reason]
    what_if: list[WhatIf]
    reply_card: str
    message_hash: str  # hash of the REDACTED text; RECONCILIATION ADDITION (see B.8)
    evidence: Evidence  # RECONCILIATION ADDITION (see B.8)
    redactions: dict[RedactionType, int]  # D1
    lookalikes: list[LookalikeFlag]  # D3
    family: FamilyInfo | None  # D2
    passport: Passport  # D4


# ----- API §15.2 -----
class CheckRequest(Base):
    text: str
    url: str | None = None


class FeedbackRequest(Base):
    message_hash: str
    verdict: VerdictLabel  # RECONCILIATION ADDITION (see B.8)
    user_label: UserLabel


class Ack(Base):
    ok: bool


class HealthResponse(Base):
    factchecks: int
    headlines: int
    domains: int
    last_refresh: str | None


# ----- Labelled dataset (eval only) -----
class LabelledRow(Base):
    id: str
    text: str
    language: Language
    label: GroundTruth
    evidence_url: str | None
    gold_factcheck_url: str | None
    notes: str | None
