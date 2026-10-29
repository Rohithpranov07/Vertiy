from datetime import UTC, datetime
from pathlib import Path

from scripts.seed_rumour_families import seed_families

from verity import db
from verity.config import get_settings
from verity.retrieval import apply_variant
from verity.rumour import extract_keywords, fingerprint, hamming, match_family, record_hit
from verity.schemas import FamilyInfo, RedactedText

# SYNTHETIC FIXTURE: made-up rumour sentence and variants.
BASE = "hot lemon water cures diabetes"
VARIANTS = {
    "V1 greeting, emojis, forward to all": (
        "Good morning \U0001f64f\U0001f600 hot lemon water cures diabetes \U0001f525 forward to all"
    ),
    "V2 upper-case, punctuation": "HOT LEMON WATER CURES DIABETES!!!",
    "V3 sentences reordered": "cures diabetes hot lemon water",
    "V4 two words replaced": "warm lemon water heals diabetes",
    "V5 heavy rewrite": (
        "drinking a glass of citrus juice mixed in warm liquid removes sugar illness"
    ),
    "V6 unrelated": "bank accounts will be frozen tomorrow unless you update your card details",
}
LIGHT = [
    "V1 greeting, emojis, forward to all",
    "V2 upper-case, punctuation",
    "V3 sentences reordered",
    "V4 two words replaced",
]
TRD_REFERENCE = [11, 0, 8, 11, 33, 34]


def fp(text: str) -> int:
    return fingerprint(RedactedText(text))


def test_deterministic_and_short_text() -> None:
    assert fp(BASE) == fp(BASE)
    assert isinstance(fp("ab"), int) and 0 <= fp("ab") < 2**64
    assert fp("") == fp("")


def test_short_sentence_distance_table_reported_against_trd_reference() -> None:
    """The 30-character sentence is too short for a stable SimHash (about 26 shingles).

    The exact variant texts behind the TRD reference run are not given, so the numbers
    differ; they are printed for comparison and NOT adjusted. Only invariants are asserted.
    """
    base = fp(BASE)
    measured = {name: hamming(base, fp(text)) for name, text in VARIANTS.items()}
    print("\nvariant".ljust(40), "measured", "TRD ref")
    for (name, d), ref in zip(measured.items(), TRD_REFERENCE, strict=True):
        print(name.ljust(40), str(d).rjust(8), str(ref).rjust(7))
    assert measured["V2 upper-case, punctuation"] == 0
    assert measured["V6 unrelated"] > get_settings().simhash_max_hamming


LONG_BASE = (
    "URGENT news from the health ministry: drinking hot lemon water every morning on an empty "
    "stomach completely cures diabetes within two weeks and doctors are hiding this from you."
)
LONG_VARIANTS = {
    "greeting, emojis, forward to all": "Good morning \U0001f64f "
    + LONG_BASE
    + " \U0001f525 forward to all",
    "upper-case, punctuation changed": LONG_BASE.upper().replace(":", " -") + "!!!",
    "sentences reordered": "Doctors are hiding this from you. Drinking hot lemon water "
    "every morning on an empty stomach completely cures diabetes within two weeks. "
    "URGENT news from the health ministry.",
    "two words replaced": LONG_BASE.replace("drinking", "having").replace("completely", "fully"),
    "unrelated": "Your bank account will be frozen tomorrow unless you update your card details "
    "using the link below, the bank has announced new rules for every customer in the country.",
}


def test_long_forward_light_edits_within_threshold_unrelated_beyond() -> None:
    base = fp(LONG_BASE)
    th = get_settings().simhash_max_hamming
    dist = {name: hamming(base, fp(text)) for name, text in LONG_VARIANTS.items()}
    print("\nlong forward distances (threshold", th, "):", dist)
    for name, d in dist.items():
        if name == "unrelated":
            assert d > th, (name, d)
        else:
            assert d <= th, (name, d)


def test_family_matching_and_variant_link(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    db.add_factcheck(conn, LONG_BASE, "refuted", "Pub", "http://f.example/1", lang="en")
    assert seed_families(conn) == (1, 1)
    assert seed_families(conn) == (0, 1)  # idempotent
    variant = fp(LONG_VARIANTS["two words replaced"])
    fam = match_family(conn, variant)
    assert fam is not None and fam.linked_rating == "refuted" and fam.source == "existing"
    state, out = apply_variant("none", fam)
    assert state == "refuted" and out is not None and out.source == "variant"
    assert apply_variant("supported", fam) == ("supported", fam)
    assert match_family(conn, fp(LONG_VARIANTS["unrelated"])) is None


def test_unlinked_family_never_sets_verdict(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    now = datetime(2026, 10, 29, 10, 5, tzinfo=UTC)
    info = record_hit(conn, None, fp(BASE), "h1", "unverified", ["lemon"], "en", now)
    assert info.source == "new" and info.linked_rating is None
    fam = match_family(conn, fp(BASE))
    assert fam is not None and apply_variant("none", fam) == ("none", fam)


def test_record_hit_counts_once_per_hour_and_stores_no_text(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    t1 = datetime(2026, 10, 29, 10, 5, tzinfo=UTC)
    fam = record_hit(conn, None, fp(BASE), "h1", "unverified", ["lemon", "water"], "en", t1)
    again = match_family(conn, fp(BASE + " please share"))
    assert again is not None
    record_hit(conn, again, fp(BASE), "h1", "unverified", [], "en", t1)  # same hash, same hour
    record_hit(conn, again, fp(BASE), "h2", "unverified", [], "en", t1)
    assert db.count_hits(conn, fam.family_id) == 2
    row = db.get_family(conn, fam.family_id)
    assert row is not None and row.last_verdict == "unverified"
    blob = repr(conn.execute("SELECT * FROM rumours").fetchall())
    assert "diabetes" not in blob


def test_keywords_exclude_stopwords_tags_and_digit_strings() -> None:
    kw = extract_keywords(
        RedactedText("Call [PHONE] now: the 1234567890 miracle lemon lemon water cure")
    )
    assert "phone" not in kw and "1234567890" not in kw and "the" not in kw
    assert kw[0] == "lemon" and len(kw) <= 5


def test_family_info_type() -> None:
    assert FamilyInfo(family_id="x", hamming=None, linked_rating=None, source="new")
