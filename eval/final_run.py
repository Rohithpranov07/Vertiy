"""Freeze thresholds on the DEV split, then run the TEST split exactly once.

Step 1 - print dev-tuned candidates (writes nothing):
    python -m eval.final_run --candidates
Step 2 - after YOU choose values, write them as the new defaults:
    python -m eval.final_run --apply FACTCHECK_MATCH_THRESHOLD=0.35 VERDICT_THRESHOLD=0.8 ...
Step 3 - the single test-split run (refuses if it was already used):
    python -m eval.final_run --final --confirm

No tuning script reads the test split; this is the only code path that does, and it records
the use in eval/test_split_used.json.
"""

import argparse
import csv
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

from eval.report import write_reports
from eval.retrieval_precision import _query
from eval.run_eval import LABELLED, run
from eval.threshold_sweep import THRESHOLDS, sweep
from verity import db
from verity.bn import infer
from verity.bn.evidence_table import evidence_for_text
from verity.cues.source import db_lookup
from verity.cues.tone import tone_score
from verity.errors import DataError
from verity.retrieval import Retriever
from verity.schemas import PartialEvidence

ROOT = Path(__file__).resolve().parents[1]
LOCK = Path(__file__).resolve().parent / "test_split_used.json"
TUNABLE = {
    "FACTCHECK_MATCH_THRESHOLD": "factcheck_match_threshold",
    "HEADLINE_MATCH_THRESHOLD": "headline_match_threshold",
    "TONE_THRESHOLD": "tone_threshold",
    "VERDICT_THRESHOLD": "verdict_threshold",
}
MATCH_GRID = [round(0.1 + 0.05 * i, 2) for i in range(13)]  # 0.10 .. 0.70
TONE_GRID = [round(0.3 + 0.05 * i, 2) for i in range(9)]  # 0.30 .. 0.70


def fact_check_sweep(
    rows: list[dict[str, str]], retriever: Retriever
) -> list[tuple[float, float | None, float | None]]:
    """(threshold, recall of gold fact-check, spurious-match rate on rows without a gold)."""
    url_by_id = {i: f.url for i, f in retriever.fc_rows.items()}
    hits = [(r, retriever.fc_index.search(_query(r["text"], r["language"]), 5)) for r in rows]
    out: list[tuple[float, float | None, float | None]] = []
    for th in MATCH_GRID:
        gold_rows = [(r, h) for r, h in hits if r.get("gold_factcheck_url")]
        plain = [(r, h) for r, h in hits if not r.get("gold_factcheck_url")]
        found = sum(
            any(url_by_id[i] == r["gold_factcheck_url"] and s >= th for i, s in h)
            for r, h in gold_rows
        )
        spurious = sum(any(s >= th for _, s in h) for _, h in plain)
        out.append(
            (
                th,
                found / len(gold_rows) if gold_rows else None,
                spurious / len(plain) if plain else None,
            )
        )
    return out


def headline_sweep(
    rows: list[dict[str, str]], retriever: Retriever
) -> list[tuple[float, float | None, float | None]]:
    """(threshold, share of TRUE rows corroborated, share of FALSE rows corroborated)."""
    sims = {
        r["id"]: max(
            (s for _, s in retriever.hl_index.search(_query(r["text"], r["language"]), 5)),
            default=0.0,
        )
        for r in rows
    }

    def share(label: str, th: float) -> float | None:
        ids = [r["id"] for r in rows if r["label"] == label]
        return sum(sims[i] >= th for i in ids) / len(ids) if ids else None

    return [(th, share("true", th), share("false", th)) for th in MATCH_GRID]


def tone_sweep(rows: list[dict[str, str]]) -> list[tuple[float, float | None]]:
    """(threshold, accuracy of 'high tone => false' on true/false rows)."""
    dec = [r for r in rows if r["label"] in ("true", "false")]
    scores = [(tone_score(r["text"]), r["label"]) for r in dec]
    return [
        (
            th,
            sum((s >= th) == (lab == "false") for s, lab in scores) / len(scores)
            if scores
            else None,
        )
        for th in TONE_GRID
    ]


def print_candidates(dev_path: Path) -> None:
    with dev_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    with db.session() as conn:
        retriever = Retriever.load(conn)
        trusted = [d.domain for d in db.list_domains(conn) if d.cls == "trusted"]
        lookup = db_lookup(conn)
        posteriors = [
            (
                infer(
                    PartialEvidence(
                        **evidence_for_text(r["text"], retriever, lookup, trusted).model_dump()
                    )
                ),
                r["label"],
            )
            for r in rows
        ]
    f = lambda v: "  n/a" if v is None else f"{v:5.3f}"  # noqa: E731
    print(f"DEV split: {len(rows)} rows. Nothing below is written anywhere.\n")
    print("FACTCHECK_MATCH_THRESHOLD   threshold  gold-recall  spurious-rate")
    for th, rec, sp in fact_check_sweep(rows, retriever):
        print(f"{'':28}{th:9.2f}  {f(rec):>11}  {f(sp):>13}")
    print("\nHEADLINE_MATCH_THRESHOLD    threshold  true-corroborated  false-corroborated")
    for th, t, fl in headline_sweep(rows, retriever):
        print(f"{'':28}{th:9.2f}  {f(t):>17}  {f(fl):>18}")
    print("\nTONE_THRESHOLD              threshold  accuracy(high tone => false)")
    for th, acc in tone_sweep(rows):
        print(f"{'':28}{th:9.2f}  {f(acc):>10}")
    print("\nVERDICT_THRESHOLD           threshold  coverage  confident-error")
    for th, cov, err, _ in sweep(posteriors, THRESHOLDS):
        print(f"{'':28}{th:9.2f}  {cov:8.3f}  {f(err):>15}")
    print("\nChoose values, then run:  python -m eval.final_run --apply NAME=value ...")


def apply_defaults(values: dict[str, float], env_path: Path, config_path: Path) -> None:
    """Rewrite the defaults in .env.example and in config.py for the chosen tunables."""
    env_text = env_path.read_text(encoding="utf-8")
    cfg_text = config_path.read_text(encoding="utf-8")
    for name, value in values.items():
        if name not in TUNABLE:
            raise DataError(f"{name} is not a tunable I may change", code="bad_tunable")
        if not 0.0 < value <= 1.0:
            raise DataError(f"{name}={value} is outside (0, 1]", code="bad_tunable")
        env_text, n1 = re.subn(rf"^({name}=)[0-9.]+", rf"\g<1>{value}", env_text, flags=re.M)
        field = TUNABLE[name]
        cfg_text, n2 = re.subn(
            rf"^(\s+{field}: float = Field\()[0-9.]+", rf"\g<1>{value}", cfg_text, flags=re.M
        )
        if n1 != 1 or n2 != 1:
            raise DataError(
                f"could not locate {name} in .env.example/config.py", code="bad_tunable"
            )
    env_path.write_text(env_text, encoding="utf-8")
    config_path.write_text(cfg_text, encoding="utf-8")


def final(labelled_dir: Path, out_dir: Path, lock: Path = LOCK) -> int:
    if lock.exists():
        print(
            f"REFUSED: the test split was already used ({lock.read_text().strip()[:120]}...).",
            file=sys.stderr,
        )
        return 3
    results = run("test", labelled_dir, out_dir)
    md, js = write_reports(results, out_dir)
    meta = results["meta"]
    assert isinstance(meta, dict)
    lock.write_text(
        json.dumps(
            {
                "used_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "labelled_sha256": meta["labelled_sha256"],
                "cpt_version": meta["cpt_version"],
                "index_version": meta["index_version"],
                "threshold": meta["threshold"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    print(md.read_text(encoding="utf-8"))
    print("test split used once; recorded in", lock)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidates", action="store_true")
    ap.add_argument("--apply", nargs="+", metavar="NAME=VALUE")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--labelled-dir", type=Path, default=LABELLED)
    ap.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args(argv)
    if args.candidates:
        print_candidates(args.labelled_dir / "dev.csv")
        return 0
    if args.apply:
        values = {k: float(v) for k, v in (a.split("=", 1) for a in args.apply)}
        apply_defaults(values, ROOT / ".env.example", ROOT / "src" / "verity" / "config.py")
        print("updated defaults:", values)
        return 0
    if args.final:
        if not args.confirm:
            print(
                "REFUSED: pass --confirm once thresholds are frozen and you are ready.",
                file=sys.stderr,
            )
            return 2
        return final(args.labelled_dir, args.out_dir)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
