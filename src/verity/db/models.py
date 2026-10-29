"""Row models returned by the repository (typed rows, never raw tuples)."""

from pydantic import BaseModel, ConfigDict

from verity.schemas import Language, Rating, UserLabel, VerdictLabel


class Row(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FactCheckRow(Row):
    id: int
    claim_text: str
    rating: Rating
    publisher: str
    url: str
    date: str | None
    lang: str | None


class HeadlineRow(Row):
    id: int
    title: str
    domain: str
    url: str
    date: str | None


class DomainRow(Row):
    domain: str
    cls: str  # 'trusted' | 'low' (column name is `class`)


class FeedbackRow(Row):
    id: int
    message_hash: str
    verdict: VerdictLabel
    user_label: UserLabel
    timestamp: str


class RumourRow(Row):
    family_id: str
    fingerprint: int
    keywords: list[str]
    language: Language
    linked_factcheck_id: int | None
    first_seen: str
    last_seen: str
    last_verdict: VerdictLabel | None


class HealthCounts(Row):
    factchecks: int
    headlines: int
    domains: int
    last_refresh: str | None
