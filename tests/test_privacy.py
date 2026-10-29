import os
import subprocess
import sys
from pathlib import Path

import pytest

from verity.privacy import as_redacted, redact

# SYNTHETIC FIXTURE: all identifiers below are made up.


@pytest.mark.parametrize(
    ("text", "kind", "tag"),
    [
        ("call me on 9876543210 now", "PHONE", "[PHONE]"),
        ("call +91 98765 43210 now", "PHONE", "[PHONE]"),
        ("call 98765-43210 now", "PHONE", "[PHONE]"),
        ("pay to rahul.k@okaxis today", "UPI", "[UPI]"),
        ("mail me at someone@example.com please", "EMAIL", "[EMAIL]"),
        ("card 1234 5678 9012 3456 expires", "CARD", "[CARD]"),
        ("id 1234 5678 9012 here", "ID12", "[ID12]"),
    ],
)
def test_each_type(text: str, kind: str, tag: str) -> None:
    r = redact(text)
    assert r.counts == {kind: 1}
    assert tag in r.text


def test_two_phone_formats() -> None:
    r = redact("a 9876543210 and b +91-91234 56789")
    assert r.counts == {"PHONE": 2}
    assert r.text == "a [PHONE] and b [PHONE]"


@pytest.mark.parametrize("clean", ["Hot lemon water cures diabetes!", "Rs 5000 offer on 12 Nov"])
def test_clean_unchanged(clean: str) -> None:
    r = redact(clean)
    assert r.text == clean and r.counts == {}


def test_idempotent() -> None:
    once = redact("x 9876543210 y rahul@ybl z a@b.com 1234 5678 9012 3456").text
    twice = redact(once)
    assert twice.text == once and twice.counts == {}


def test_plain_str_rejected_by_mypy() -> None:
    bad = Path(__file__).with_name("_typecheck_bad.py.txt")
    src = bad.read_text()
    out = subprocess.run(
        [sys.executable, "-m", "mypy", "--config-file=", "--strict", "--no-incremental", "-c", src],
        env={**os.environ, "MYPYPATH": str(Path(__file__).parents[1] / "src")},
        capture_output=True,
        text=True,
        check=False,
    )
    print(out.stdout)
    assert out.returncode != 0 and "RedactedText" in out.stdout
    ok = as_redacted(redact("hi"))
    assert ok == "hi"
