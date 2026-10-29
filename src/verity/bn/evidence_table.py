"""Run extraction, retrieval and cues over labelled rows to build (Evidence, claim_true) pairs."""

from collections.abc import Collection
from typing import Literal, cast

from verity.clients.translate import Translator
from verity.cues import lookalike_flags, source_cred, specifics, tone
from verity.cues.source import DomainLookup
from verity.extract import extract_claim
from verity.lang import prepare
from verity.privacy import as_redacted, redact
from verity.retrieval import (
    Retriever,
    match_factchecks,
    match_headlines,
    to_corroboration,
    to_fact_check_state,
)
from verity.schemas import Evidence, FactCheckState, YesNo

Truth = Literal["true", "false"]


def evidence_for_text(
    text: str,
    retriever: Retriever,
    lookup: DomainLookup,
    trusted: Collection[str],
    translator: Translator | None = None,
) -> Evidence:
    """Evidence for one message, mirroring the pipeline (without the rumour-family step)."""
    safe = as_redacted(redact(text))
    prepared = prepare(safe, translator)
    extracted = extract_claim(prepared)
    claim = extracted.claim
    flags = lookalike_flags(claim, None, trusted)
    fact_check: FactCheckState
    corroboration: YesNo
    if prepared.language != "en" and not prepared.translation_ok:
        fact_check, corroboration = "none", "no"
    else:
        fact_check = to_fact_check_state(match_factchecks(claim, retriever))
        corroboration = to_corroboration(match_headlines(claim, retriever))
    return Evidence(
        source_cred=source_cred(claim, None, flags, lookup),
        fact_check=fact_check,
        corroboration=corroboration,
        sensational=tone(prepared.english),
        specifics=specifics(extracted.signals),
    )


def build_table(
    rows: list[dict[str, str]],
    retriever: Retriever,
    lookup: DomainLookup,
    trusted: Collection[str],
    translator: Translator | None = None,
) -> list[tuple[Evidence, Truth]]:
    """Only `true`/`false` rows; `unverifiable` rows have no ground truth and are excluded."""
    return [
        (
            evidence_for_text(r["text"], retriever, lookup, trusted, translator),
            cast(Truth, r["label"]),
        )
        for r in rows
        if r["label"] in ("true", "false")
    ]
