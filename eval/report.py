"""Render eval results (a plain dict computed in the run) to report.md / report.json."""

import json
from pathlib import Path


def _f(v: object, digits: int = 3) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return "n/a" if v != v else f"{v:.{digits}f}"
    return str(v)


def render_markdown(r: dict[str, object]) -> str:  # noqa: C901 - flat report layout
    meta = r["meta"]
    assert isinstance(meta, dict)
    out = [
        "# VERITY evaluation report",
        "",
        f"- Split: **{meta['split']}** ({meta['rows']} labelled rows)",
        f"- Labelled file sha256: `{meta['labelled_sha256']}`",
        f"- Index version (full index): `{meta['index_version']}`",
        f"- CPT version: `{meta['cpt_version']}`",
        f"- Verdict threshold: {meta['threshold']}",
        f"- Generated: {meta['generated']}",
        "",
    ]
    if meta["split"] == "dev":
        out += [
            "> Dev-split numbers are optimistic for VERITY (CPTs and the tone model are learned on "
            "dev). The baseline column uses 5-fold cross-validation on dev. Use the one-time test "
            "run for claims.",
            "",
        ]
    conds = r["conditions"]
    assert isinstance(conds, dict)
    for name, c in conds.items():
        assert isinstance(c, dict)
        out += [
            f"## Index condition: {name}",
            "",
            f"- Rows evaluated: {c['evaluated']} (errors skipped: {c['errors']})",
            f"- Retrieval precision@3: {_f(c.get('precision_at_3'))} "
            f"(rows with a gold fact-check: {c.get('gold_rows', 'n/a')})",
            f"- Three-class macro-F1 (VERITY, all rows): {_f(c['macro_f1_3class'])}",
            f"- Decidable subset (true/false rows, n={c['decidable_n']}):",
            f"  - VERITY macro-F1 {_f(c['verity_macro_f1'])}, Brier {_f(c['verity_brier'])}",
            f"  - Baseline macro-F1 {_f(c['baseline_macro_f1'])}, Brier {_f(c['baseline_brier'])}",
            "  - The baseline cannot abstain; VERITY here uses a hard label from P(true) > 0.5.",
            f"- Abstention quality: {_f(c['abstention_quality'])} of {c['unverified_n']} "
            "Unverified verdicts have fact_check = none",
            f"- Latency (s): median {_f(c['latency_median'])}, p95 {_f(c['latency_p95'])}",
            "",
            "Ablation (three-class macro-F1 with the node marginalised out):",
            "",
            "| dropped node | macro-F1 | change |",
            "|---|---|---|",
        ]
        abl = c["ablation"]
        assert isinstance(abl, dict)
        for node, (score, delta) in abl.items():
            out.append(f"| {node} | {_f(score)} | {_f(delta)} |")
        out.append("")
    d = r["differentiators"]
    assert isinstance(d, dict)
    out += ["## Differentiator metrics", ""]
    for key, val in d.items():
        out += [f"- **{key}**: `{json.dumps(val, sort_keys=True)}`"]
    out += ["", "_Starter differentiator files are synthetic unless replaced by real ones._", ""]
    return "\n".join(out)


def write_reports(results: dict[str, object], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md, js = out_dir / "report.md", out_dir / "report.json"
    md.write_text(render_markdown(results), encoding="utf-8")
    js.write_text(
        json.dumps(results, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return md, js
