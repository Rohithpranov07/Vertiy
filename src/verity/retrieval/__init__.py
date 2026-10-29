"""Stage 3: retrieval and mapping to belief-network evidence."""

from verity.retrieval.match import (
    Retriever,
    match_factchecks,
    match_headlines,
    set_default_retriever,
    to_corroboration,
    to_fact_check_state,
)

__all__ = [
    "Retriever",
    "match_factchecks",
    "match_headlines",
    "set_default_retriever",
    "to_corroboration",
    "to_fact_check_state",
]
