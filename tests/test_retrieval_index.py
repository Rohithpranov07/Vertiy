from pathlib import Path

from eval.retrieval_precision import main as precision_main
from eval.retrieval_precision import precision_at_k

from verity import db
from verity.retrieval.build import FACTCHECK_INDEX, build_indexes
from verity.retrieval.index import TfidfIndex

# SYNTHETIC FIXTURE: made-up fact-check claims.
CLAIMS = [
    (1, "hot lemon water cures diabetes completely"),
    (2, "free recharge offered by government to every user"),
    (3, "banks will be closed for ten days next month"),
]


def test_search_best_first_and_ties_by_id() -> None:
    ix = TfidfIndex.build(CLAIMS + [(4, "hot lemon water cures diabetes completely")])
    top = ix.search("lemon water cures diabetes", 3)
    assert [i for i, _ in top][:2] == [1, 4]  # equal similarity -> ascending id
    assert top[0][1] >= top[1][1] >= (top[2][1] if len(top) > 2 else 0)
    assert ix.search("zzzz qqqq", 3) == [] and ix.search("", 3) == []


def test_build_is_deterministic_and_persists(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    for i, text in CLAIMS:
        db.add_factcheck(conn, text, "refuted", "p", f"http://f.example/{i}")
    assert build_indexes(conn, tmp_path / "ix1") == (3, 0)
    build_indexes(conn, tmp_path / "ix2")
    a = TfidfIndex.load(tmp_path / "ix1" / FACTCHECK_INDEX)
    b = TfidfIndex.load(tmp_path / "ix2" / FACTCHECK_INDEX)
    assert a.search("lemon diabetes", 3) == b.search("lemon diabetes", 3)
    print("top-3 'lemon diabetes':", a.search("lemon diabetes", 3))
    print("top-3 'free recharge':", a.search("free recharge government", 3))


def test_precision_at_k_and_test_split_refused(tmp_path: Path) -> None:
    ix = TfidfIndex.build(CLAIMS)
    urls = {i: f"http://f.example/{i}" for i, _ in CLAIMS}
    rows = [
        {
            "id": "a",
            "text": "lemon water cures diabetes",
            "language": "ta",
            "gold_factcheck_url": "http://f.example/1",
        },
        {
            "id": "b",
            "text": "banks closed ten days",
            "language": "ta",
            "gold_factcheck_url": "http://f.example/3",
        },
        {
            "id": "c",
            "text": "nothing relevant zzz",
            "language": "ta",
            "gold_factcheck_url": "http://f.example/2",
        },
        {"id": "d", "text": "no gold", "language": "ta", "gold_factcheck_url": ""},
    ]
    p, misses, n = precision_at_k(rows, ix, urls, 3)
    assert (n, misses) == (3, ["c"]) and abs(p - 2 / 3) < 1e-9  # type: ignore[operator]
    assert precision_main(["--split", "test", "--labelled-dir", str(tmp_path)]) == 2
