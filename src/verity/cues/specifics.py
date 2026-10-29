"""Verifiable-details cue: at least two of person/org, date, place, link."""

from verity.schemas import ClaimSignals, YesNo

MIN_SIGNALS = 2


def specifics(signals: ClaimSignals) -> YesNo:
    count = sum((signals.has_person_org, signals.has_date, signals.has_place, signals.has_link))
    return "yes" if count >= MIN_SIGNALS else "no"
