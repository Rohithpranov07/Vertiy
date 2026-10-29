"""One-shot, re-runnable setup: database, domains, fact-checks, headlines, families, indexes,
tone model and learned CPTs. Steps whose inputs are missing are skipped with a clear notice."""

import sys
from pathlib import Path

from scripts import (
    ingest_factchecks,
    ingest_headlines,
    load_domains,
    seed_rumour_families,
)
from verity import db
from verity.bn import learn
from verity.config import get_settings
from verity.cues import train_tone
from verity.errors import VerityError
from verity.retrieval import build

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DEV = ROOT / "eval" / "labelled" / "dev.csv"


def _has_lines(path: Path) -> bool:
    return path.exists() and any(
        ln.strip() and not ln.startswith("#")
        for ln in path.read_text(encoding="utf-8").splitlines()
    )


def run_step(name: str, fn: object) -> bool:
    assert callable(fn)
    try:
        result = fn()
    except VerityError as exc:
        print(f"[FAIL] {name}: {exc.code}: {exc.message}")
        return False
    if result:  # steps that skip themselves print their own [skip] line and return ""
        print(f"[ ok ] {name}: {result}")
    return True


def setup() -> int:
    settings = get_settings()
    failures = 0

    def init() -> str:
        with db.session() as conn:
            db.init_db(conn)
        return str(settings.db_path)

    def domains() -> str:
        with db.session() as conn:
            added = load_domains.load_domains(conn, DATA / "domains.csv")
            return f"{added} new, {db.count_domains(conn)} total"

    def factchecks() -> str:
        if settings.factcheck_api_key and _has_lines(DATA / "seed_queries.txt"):
            code = ingest_factchecks.main([])
            return f"online ingest exit {code}"
        if (DATA / "seed_factchecks.jsonl").exists():
            code = ingest_factchecks.main(["--offline"])
            return f"offline seed exit {code}"
        print(
            "[skip] fact-checks: set FACTCHECK_API_KEY and fill data/seed_queries.txt, "
            "or supply data/seed_factchecks.jsonl"
        )
        return ""

    def headlines() -> str:
        if not _has_lines(DATA / "feeds.txt"):
            print("[skip] headlines: data/feeds.txt has no feeds")
            return ""
        return f"exit {ingest_headlines.main([])}"

    def families() -> str:
        with db.session() as conn:
            added, total = seed_rumour_families.seed_families(conn)
        return f"{added} new from {total} fact-checks"

    def indexes() -> str:
        with db.session() as conn:
            n_fc, n_hl = build.build_indexes(conn)
        return f"{n_fc} fact-checks, {n_hl} headlines"

    def tone() -> str:
        if not DEV.exists():
            print("[skip] tone model: eval/labelled/dev.csv not found (style score only)")
            return ""
        return f"exit {train_tone.main(['--csv', str(DEV)])}"

    def params() -> str:
        if not DEV.exists():
            print("[skip] learned CPTs: eval/labelled/dev.csv not found (priors are used)")
            return ""
        return f"exit {learn.main(['--csv', str(DEV)])}"

    for name, fn in (
        ("init database", init),
        ("load domains", domains),
        ("fact-checks", factchecks),
        ("headlines", headlines),
        ("rumour families", families),
        ("build indexes", indexes),
        ("tone model", tone),
        ("learn CPTs", params),
    ):
        if not run_step(name, fn):
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(setup())
