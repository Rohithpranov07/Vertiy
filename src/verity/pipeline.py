"""pipeline.check(): wires every stage together (build spec B.3 / T7.1)."""

import logging
import sqlite3
from datetime import datetime

from verity import db
from verity.bn import decide, infer
from verity.clients.translate import Translator
from verity.config import Settings, get_settings
from verity.cues import lookalike_flags, source_cred, specifics, tone
from verity.cues.source import db_lookup
from verity.errors import InputError
from verity.explain import ReplyParts, build_passport, reasons, reply_card, what_if
from verity.extract import extract_claim, ranked_sentences
from verity.lang import prepare
from verity.privacy import as_redacted, derive, message_hash, redact
from verity.retrieval import (
    Retriever,
    apply_variant,
    match_factchecks,
    match_headlines,
    to_corroboration,
    to_fact_check_state,
)
from verity.rumour import extract_keywords, fingerprint, match_family, record_hit
from verity.schemas import (
    CheckRequest,
    ClaimRecord,
    Evidence,
    FactCheckState,
    HeadlineMatch,
    Match,
    PartialEvidence,
    PreparedText,
    VerdictRecord,
    YesNo,
)

log = logging.getLogger(__name__)


class Pipeline:
    """Holds the heavy, shareable state (indexes); each check opens its own DB session."""

    def __init__(
        self,
        retriever: Retriever | None = None,
        translator: Translator | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._retriever = retriever
        self._translator = translator
        self._settings = settings

    @property
    def settings(self) -> Settings:
        return self._settings or get_settings()

    def retriever(self, conn: sqlite3.Connection) -> Retriever:
        if self._retriever is None:
            self._retriever = Retriever.load(conn)
        return self._retriever

    def _retry_sentences(
        self, prepared: PreparedText, claim: ClaimRecord, retriever: Retriever
    ) -> tuple[ClaimRecord, list[Match]]:
        """Try the other check-worthy sentences; the first that matches becomes the claim."""
        tried = 0
        for sentence in ranked_sentences(prepared):
            if sentence == claim.text:
                continue
            if tried >= self.settings.claim_extra_candidates:
                break
            tried += 1
            candidate = claim.model_copy(update={"text": sentence})
            found = match_factchecks(candidate, retriever)
            if found:
                return candidate, found
        return claim, []

    def check(self, request: CheckRequest, now: datetime | None = None) -> VerdictRecord:
        s = self.settings
        if not request.text.strip():
            raise InputError("message text is empty", code="empty_text")
        if len(request.text) > s.max_message_chars:
            raise InputError(
                f"message longer than {s.max_message_chars} characters", code="message_too_long"
            )

        # D1: redact first; everything after this sees only the redacted text
        redaction = redact(request.text)
        safe = as_redacted(redaction)
        mhash = message_hash(safe)

        prepared = prepare(safe, self._translator)
        extracted = extract_claim(prepared)
        claim = extracted.claim
        blocked = prepared.language != "en" and not prepared.translation_ok

        with db.session() as conn:
            db.init_db(conn)
            retriever = self.retriever(conn)

            matches: list[Match] = []
            headlines: list[HeadlineMatch] = []
            if not blocked:
                matches = match_factchecks(claim, retriever)
                if not matches:  # the chosen sentence found nothing: try the next best ones
                    claim, matches = self._retry_sentences(prepared, claim, retriever)
                headlines = match_headlines(claim, retriever)
            fact_check: FactCheckState = "none" if blocked else to_fact_check_state(matches)
            corroboration: YesNo = "no" if blocked else to_corroboration(headlines)

            safe_claim = derive(safe, claim.text)
            fp = fingerprint(safe_claim)
            family = match_family(conn, fp)
            fact_check, family = apply_variant(fact_check, family)

            trusted = [d.domain for d in db.list_domains(conn) if d.cls == "trusted"]
            flags = lookalike_flags(claim, request.url, trusted)
            evidence = Evidence(
                source_cred=source_cred(claim, request.url, flags, db_lookup(conn)),
                fact_check=fact_check,
                corroboration=corroboration,
                sensational=tone(prepared.english),
                specifics=specifics(extracted.signals),
            )

            posterior = infer(PartialEvidence(**evidence.model_dump()))
            verdict = decide(posterior, s.verdict_threshold)
            why = reasons(evidence)
            hints = what_if(evidence)
            card = reply_card(ReplyParts(verdict=verdict, reasons=why, matches=matches))
            passport = build_passport(mhash, s.verdict_threshold, now=now)

            info = record_hit(
                conn,
                family,
                fp,
                mhash,
                verdict,
                extract_keywords(safe_claim),
                prepared.language,
                now,
            )

        return VerdictRecord(
            verdict=verdict,
            p_true=posterior.p_true,
            claim=claim,
            matches=matches,
            reasons=why,
            what_if=hints,
            reply_card=card,
            message_hash=mhash,
            evidence=evidence,
            redactions=redaction.counts,
            lookalikes=flags,
            family=info,
            passport=passport,
        )


_default: Pipeline | None = None


def get_pipeline() -> Pipeline:
    global _default
    if _default is None:
        _default = Pipeline()
    return _default


def set_pipeline(pipeline: Pipeline | None) -> None:
    global _default
    _default = pipeline


def check(request: CheckRequest) -> VerdictRecord:
    return get_pipeline().check(request)


__all__ = ["Pipeline", "check", "get_pipeline", "set_pipeline"]
