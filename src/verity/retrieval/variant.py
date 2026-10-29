"""Variant channel (D2): a linked rumour family can supply the fact-check rating."""

from verity.schemas import FactCheckState, FamilyInfo


def apply_variant(
    state: FactCheckState, family: FamilyInfo | None
) -> tuple[FactCheckState, FamilyInfo | None]:
    """Keep a TF-IDF state if there is one. Otherwise use the family's linked rating (marking
    the family source 'variant'). A family without a linked fact-check can NEVER set a verdict."""
    if state != "none":
        return state, family
    if family is not None and family.linked_rating is not None:
        return family.linked_rating, family.model_copy(update={"source": "variant"})
    return "none", family
