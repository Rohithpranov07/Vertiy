import json
import re
from datetime import UTC, datetime
from pathlib import Path

from verity import db
from verity.bn.network import PRIORS_FILE
from verity.explain import ReplyParts, build_passport, reply_card
from verity.explain.passport import ungrounded_urls
from verity.explain.reply import CLOSING, OPENING, REASON_TEXT
from verity.retrieval.build import INDEX_META, build_indexes
from verity.schemas import (
    ClaimRecord,
    Evidence,
    Match,
    Passport,
    Reason,
    VerdictRecord,
)

# SYNTHETIC FIXTURE: made-up index contents.
T1 = datetime(2026, 10, 29, 10, 0, tzinfo=UTC)
T2 = datetime(2026, 10, 29, 11, 0, tzinfo=UTC)


def _index(tmp_path: Path, extra: bool = False) -> Path:
    name = "ix_b" if extra else "ix_a"
    conn = db.connect(tmp_path / f"{name}.db")
    db.init_db(conn)
    db.add_factcheck(conn, "claim a", "refuted", "P", "http://f.example/1")
    if extra:
        db.add_factcheck(conn, "claim b", "supported", "P", "http://f.example/2")
    d = tmp_path / name
    build_indexes(conn, d)
    conn.commit()
    conn.close()
    return d


def test_index_meta_written(tmp_path: Path) -> None:
    d = _index(tmp_path)
    assert len(json.loads((d / INDEX_META).read_text())["index_version"]) == 64


def test_same_inputs_same_id_changes_change_id(tmp_path: Path) -> None:
    ix = _index(tmp_path)
    a = build_passport("hash1", 0.75, ix, now=T1)
    b = build_passport("hash1", 0.75, ix, now=T2)
    assert a.passport_id == b.passport_id and a.created_at != b.created_at
    print("same input:", a.passport_id, b.passport_id)
    other_thr = build_passport("hash1", 0.80, ix, now=T1)
    other_msg = build_passport("hash2", 0.75, ix, now=T1)
    other_ix = build_passport("hash1", 0.75, _index(tmp_path, extra=True), now=T1)
    cpt_copy = tmp_path / "cpt.json"
    cpt_copy.write_text(PRIORS_FILE.read_text().replace("expert-prior-v0", "expert-prior-v1"))
    other_cpt = build_passport("hash1", 0.75, ix, cpt_path=cpt_copy, now=T1)
    print("threshold changed:", other_thr.passport_id)
    ids = {
        a.passport_id,
        other_thr.passport_id,
        other_msg.passport_id,
        other_ix.passport_id,
        other_cpt.passport_id,
    }
    assert len(ids) == 5


def _record(url: str) -> VerdictRecord:
    return VerdictRecord(
        verdict="likely_false",
        p_true=0.1,
        claim=ClaimRecord(text="c", entities=[], numbers=[], links=[]),
        matches=[Match(publisher="P", rating="refuted", url=url, similarity=0.9)],
        reasons=[Reason(node="fact_check", state="refuted", shift=-0.5)],
        what_if=[],
        reply_card="",
        message_hash="h",
        evidence=Evidence(
            source_cred="unknown",
            fact_check="refuted",
            corroboration="no",
            sensational="low",
            specifics="no",
        ),
        redactions={},
        lookalikes=[],
        family=None,
        passport=Passport(
            passport_id="x", index_version="i", cpt_version="c", threshold=0.75, created_at="t"
        ),
    )


def test_grounded_urls_only() -> None:
    known = {"http://f.example/1"}
    assert ungrounded_urls(_record("http://f.example/1"), known) == []
    assert ungrounded_urls(_record("http://invented.example/x"), known) == [
        "http://invented.example/x"
    ]


def test_reply_card_is_template_text_only() -> None:
    for verdict in ("likely_false", "unverified", "likely_true"):
        for (node, state), phrase in REASON_TEXT.items():
            card = reply_card(
                ReplyParts(
                    verdict=verdict,  # type: ignore[arg-type]
                    reasons=[Reason(node=node, state=state, shift=-0.3)],
                    matches=[
                        Match(
                            publisher="Pub",
                            rating="refuted",
                            url="http://f.example/1",
                            similarity=0.8,
                        )
                    ],
                )
            )
            rest = card.replace(OPENING[verdict], "").replace(phrase, "")
            rest = rest.replace(CLOSING[verdict], "").replace(
                "Fact-check (Pub): http://f.example/1", ""
            )
            assert re.sub(r"[\s.:]+", "", rest) == "", (verdict, node, state, rest)
