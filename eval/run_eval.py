"""Compute every PRD section 8 / TRD section 16 metric reproducibly.

  python -m eval.run_eval --split dev
  python -m eval.run_eval --split test --final     (see eval/final_run.py)

Each condition runs on a scratch copy of the database and indexes, so evaluation never writes
to the real rumour tables. Nothing is reported that was not computed in this run.
"""

import argparse
import csv
import hashlib
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from scripts.seed_rumour_families import seed_families

from eval import d_metrics
from eval.ablation import EvidenceRow, ablate
from eval.baseline import Baseline, cross_val_p_true
from eval.metrics import (
    TRUTH_TO_VERDICT,
    VERDICTS,
    abstention_quality,
    brier,
    macro_f1,
    percentile,
)
from eval.report import write_reports
from eval.retrieval_precision import precision_at_k
from verity import db
from verity.bn.version import cpt_version
from verity.config import get_settings
from verity.cues.tone import MODEL_FILE, reset_model_cache
from verity.errors import VerityError
from verity.explain.passport import read_index_version
from verity.pipeline import Pipeline
from verity.retrieval import Retriever, set_default_retriever
from verity.retrieval.build import build_indexes
from verity.schemas import CheckRequest, Evidence

LABELLED = Path(__file__).resolve().parent / "labelled"
WARMUP_TEXT = "warm up message to load models before timing"


@dataclass
class RowResult:
    id: str
    label: str
    verdict: str
    p_true: float
    evidence: Evidence
    seconds: float


@dataclass
class World:
    db_path: Path
    index_dir: Path
    retriever: Retriever


def build_world(workdir: Path, name: str, exclude_urls: set[str]) -> World:
    """Scratch copy of the current database/indexes, minus fact-checks with the given URLs."""
    db_path, index_dir = workdir / f"{name}.db", workdir / f"{name}_index"
    with db.session() as src, db.session(db_path) as dst:
        db.init_db(dst)
        for d in db.list_domains(src):
            db.add_domain(dst, d.domain, d.cls)  # type: ignore[arg-type]
        for h in db.list_headlines(src):
            db.add_headline(dst, h.title, h.domain, h.url, h.date)
        for f in db.list_factchecks(src):
            if f.url not in exclude_urls:
                db.add_factcheck(dst, f.claim_text, f.rating, f.publisher, f.url, f.date, f.lang)
        seed_families(dst)
        build_indexes(dst, index_dir)
        retriever = Retriever.load(dst, index_dir)
    tone_model = get_settings().index_dir / MODEL_FILE
    if tone_model.exists():
        shutil.copy(tone_model, index_dir / MODEL_FILE)
    return World(db_path, index_dir, retriever)


@contextmanager
def using_world(world: World) -> Iterator[Pipeline]:
    saved = {k: os.environ.get(k) for k in ("DB_PATH", "INDEX_DIR")}
    os.environ["DB_PATH"], os.environ["INDEX_DIR"] = str(world.db_path), str(world.index_dir)
    reset_model_cache()
    set_default_retriever(world.retriever)
    try:
        yield Pipeline(retriever=world.retriever)
    finally:
        set_default_retriever(None)
        reset_model_cache()
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run_rows(pipeline: Pipeline, rows: list[dict[str, str]]) -> tuple[list[RowResult], int]:
    pipeline.check(CheckRequest(text=WARMUP_TEXT))  # load models; not timed, not scored
    results: list[RowResult] = []
    errors = 0
    for r in rows:
        start = time.perf_counter()
        try:
            rec = pipeline.check(CheckRequest(text=r["text"]))
        except VerityError:
            errors += 1
            continue
        results.append(
            RowResult(
                r["id"],
                r["label"],
                rec.verdict,
                rec.p_true,
                rec.evidence,
                time.perf_counter() - start,
            )
        )
    return results, errors


def condition_metrics(
    results: list[RowResult],
    baseline_p: dict[str, float],
    threshold: float,
) -> dict[str, object]:
    truth3 = [TRUTH_TO_VERDICT[r.label] for r in results]
    decidable = [r for r in results if r.label in ("true", "false") and r.id in baseline_p]
    y = [r.label for r in decidable]
    v_pred = ["true" if r.p_true > 0.5 else "false" for r in decidable]
    b_pred = ["true" if baseline_p[r.id] > 0.5 else "false" for r in decidable]
    is_true = [r.label == "true" for r in decidable]
    quality, n_unv = abstention_quality(
        [r.verdict for r in results], [r.evidence.fact_check for r in results]
    )
    secs = [r.seconds for r in results]
    return {
        "evaluated": len(results),
        "macro_f1_3class": macro_f1(truth3, [r.verdict for r in results], VERDICTS),
        "decidable_n": len(decidable),
        "verity_macro_f1": macro_f1(y, v_pred, ["false", "true"]),
        "verity_brier": brier([r.p_true for r in decidable], is_true),
        "baseline_macro_f1": macro_f1(y, b_pred, ["false", "true"]),
        "baseline_brier": brier([baseline_p[r.id] for r in decidable], is_true),
        "abstention_quality": quality,
        "unverified_n": n_unv,
        "latency_median": percentile(secs, 50),
        "latency_p95": percentile(secs, 95),
        "ablation": ablate([EvidenceRow(r.label, r.evidence) for r in results], threshold),
    }


def baseline_probabilities(
    split: str, dev: list[dict[str, str]], rows: list[dict[str, str]], seed: int
) -> dict[str, float]:
    decidable = [r for r in rows if r["label"] in ("true", "false")]
    if split == "dev":  # out-of-fold, so the baseline is not scored on its own training rows
        return dict(
            zip((r["id"] for r in decidable), cross_val_p_true(decidable, seed), strict=True)
        )
    model = Baseline(seed).fit(dev)
    return dict(
        zip(
            (r["id"] for r in decidable),
            model.predict_proba([r["text"] for r in decidable]),
            strict=True,
        )
    )


def write_unverified(path: Path, results: list[RowResult], rows: list[dict[str, str]]) -> int:
    text = {r["id"]: r["text"] for r in rows}
    unv = [r for r in results if r.verdict == "unverified"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "ground_truth", "p_true", "fact_check", "corroboration", "text"])
        for r in unv:
            w.writerow(
                [
                    r.id,
                    r.label,
                    f"{r.p_true:.3f}",
                    r.evidence.fact_check,
                    r.evidence.corroboration,
                    text[r.id],
                ]
            )
    return len(unv)


def run(split: str, labelled_dir: Path, out_dir: Path) -> dict[str, object]:
    s = get_settings()
    path = labelled_dir / f"{split}.csv"
    raw = path.read_bytes()
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    with (labelled_dir / "dev.csv").open(newline="", encoding="utf-8") as fh:
        dev = list(csv.DictReader(fh))
    gold = {r["gold_factcheck_url"] for r in rows if r.get("gold_factcheck_url")}
    baseline_p = baseline_probabilities(split, dev, rows, s.random_seed)

    conditions: dict[str, object] = {}
    diff: dict[str, object] = {}
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for name, exclude in (("full index", set[str]()), ("gold fact-checks removed", gold)):
            world = build_world(work, name.split()[0], exclude)
            with using_world(world) as pipeline:
                results, errors = run_rows(pipeline, rows)
                metrics = condition_metrics(results, baseline_p, s.verdict_threshold)
                metrics["errors"] = errors
                if not exclude:
                    url_by_id = {i: f.url for i, f in world.retriever.fc_rows.items()}
                    p3, _, n_gold = precision_at_k(rows, world.retriever.fc_index, url_by_id, 3)
                    metrics["precision_at_3"], metrics["gold_rows"] = p3, n_gold
                    n_unv = write_unverified(out_dir / "unverified_cases.csv", results, rows)
                    metrics["unverified_cases_csv"] = f"unverified_cases.csv ({n_unv} rows)"
                    sample = [r["text"] for r in rows[:5]] or [WARMUP_TEXT]
                    diff["D4_reproducibility"] = d_metrics.d4_reproducibility(
                        lambda req, now: pipeline.check(req, now), sample
                    )
                    with db.session() as conn:
                        diff["D5_radar_privacy"] = d_metrics.d5_radar_privacy(conn)
                    meta_index = read_index_version(world.index_dir)
                conditions[name] = metrics
    diff["D1_redaction"] = d_metrics.d1_redaction()
    diff["D2_variants"] = d_metrics.d2_variants()
    diff["D3_lookalikes"] = d_metrics.d3_lookalikes()
    return {
        "meta": {
            "split": split,
            "rows": len(rows),
            "labelled_sha256": hashlib.sha256(raw).hexdigest(),
            "index_version": meta_index,
            "cpt_version": cpt_version(),
            "threshold": s.verdict_threshold,
            "generated": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "conditions": conditions,
        "differentiators": diff,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--labelled-dir", type=Path, default=LABELLED)
    ap.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args(argv)
    if args.split == "test" and not args.final:
        print("REFUSED: the test split is only evaluated with --final.", file=sys.stderr)
        return 2
    if (
        not (args.labelled_dir / f"{args.split}.csv").exists()
        or not (args.labelled_dir / "dev.csv").exists()
    ):
        print(
            "labelled dev/test files not found (build with scripts.split_labelled)", file=sys.stderr
        )
        return 1
    results = run(args.split, args.labelled_dir, args.out_dir)
    md, js = write_reports(results, args.out_dir)
    print(md.read_text(encoding="utf-8"))
    print("wrote", md, js)
    return 0


if __name__ == "__main__":
    sys.exit(main())
