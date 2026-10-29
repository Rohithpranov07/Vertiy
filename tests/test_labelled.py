import csv
import filecmp
from pathlib import Path

from scripts.split_labelled import main as split_main
from scripts.split_labelled import split
from scripts.validate_labelled import COLUMNS, read_raw, validate

# SYNTHETIC FIXTURE: 12 made-up rows; none are real messages or labels.
_WORDS = [
    "alpha",
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
    "india",
    "juliet",
    "kilo",
    "lima",
]


def _rows() -> list[dict[str, str]]:
    out = []
    labels = ["false", "true", "unverifiable"] * 4
    langs = ["en", "en", "ta", "hi"] * 3
    for i in range(12):
        lab = labels[i]
        out.append(
            {
                "id": f"r{i:02d}",
                "text": f"synthetic message {_WORDS[i]} {_WORDS[(i * 5) % 12]} number {i * 7919}",
                "language": langs[i],
                "label": lab,
                "evidence_url": "" if lab == "unverifiable" else f"http://e.example/{i}",
                "gold_factcheck_url": "",
                "notes": "",
            }
        )
    return out


def _write(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return path


def test_valid_fixture_has_no_problems(tmp_path: Path) -> None:
    assert validate(_write(tmp_path / "a.csv", _rows())) == []


def test_validator_catches_bad_label_dup_id_missing_evidence(tmp_path: Path) -> None:
    rows = _rows()
    rows[1]["label"] = "maybe"
    rows[2]["id"] = rows[3]["id"]
    rows[4]["evidence_url"] = ""
    rows[4]["label"] = "true"
    problems = validate(_write(tmp_path / "b.csv", rows))
    text = "\n".join(problems)
    assert "r01: invalid label" in text
    assert "duplicate id" in text
    assert "r04: label 'true' requires evidence_url" in text


def test_validator_catches_near_duplicates_and_bad_header(tmp_path: Path) -> None:
    rows = _rows()
    rows[6]["text"] = rows[5]["text"] + "!"
    assert any("near-duplicate" in p for p in validate(_write(tmp_path / "c.csv", rows)))
    bad = tmp_path / "d.csv"
    bad.write_text("id,text\n1,x\n")
    assert validate(bad)[0].startswith("header")


def test_split_is_deterministic_and_stratified(tmp_path: Path) -> None:
    src = _write(tmp_path / "all.csv", _rows())
    for name in ("o1", "o2"):
        assert split_main([str(src), "--out", str(tmp_path / name), "--allow-small"]) == 0
    for f in ("dev.csv", "test.csv"):
        assert filecmp.cmp(tmp_path / "o1" / f, tmp_path / "o2" / f, shallow=False)
    _, rows = read_raw(src)
    dev, test = split(rows, 42)
    assert len(dev) + len(test) == 12 and len(test) == 4
    assert not {r["id"] for r in dev} & {r["id"] for r in test}


def test_split_refuses_small_without_flag(tmp_path: Path) -> None:
    src = _write(tmp_path / "all.csv", _rows())
    assert split_main([str(src), "--out", str(tmp_path / "o")]) == 1
    assert not (tmp_path / "o" / "dev.csv").exists()
