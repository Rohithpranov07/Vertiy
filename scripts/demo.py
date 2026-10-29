"""Seven-step demo (TRD section 18) against the running API; starts the API if needed.

  python -m scripts.demo [--no-spawn]

Steps whose data/demo file still holds a TODO placeholder are skipped, never invented.
"""

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

from verity.schemas import CheckRequest, RadarItem, VerdictRecord

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "data" / "demo"
FILES = {
    1: "1_debunked_with_phone.txt",
    2: "2_alarmist_unmatched.txt",
    3: "3_variant_of_1.txt",
    4: "4_lookalike_link.txt",
    5: "5_tamil.txt",
}
TITLES = {
    1: "Debunked forward with a phone number",
    2: "Alarmist message, no fact-check",
    3: "Edited copy of step 1",
    4: "Lookalike link",
    5: "Tamil message",
}


def load_message(step: int, demo_dir: Path = DEMO) -> str | None:
    """The message text, or None if the file is missing or still a TODO placeholder."""
    path = demo_dir / FILES[step]
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8").strip()
    return None if not text or "TODO" in text else text


def load_expected(demo_dir: Path = DEMO) -> dict[str, dict[str, str]]:
    path = demo_dir / "expected.json"
    if not path.exists():
        return {}
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if isinstance(v, dict)}


def _check(client: httpx.Client, text: str) -> VerdictRecord:
    resp = client.post("/check", json=CheckRequest(text=text).model_dump())
    resp.raise_for_status()
    return VerdictRecord.model_validate_json(resp.content)


def describe(step: int, record: VerdictRecord, expected: dict[str, str]) -> list[str]:
    want = expected.get("verdict", "TODO")
    verdict_line = f"verdict: {record.verdict} (p_true {record.p_true:.2f})"
    if want != "TODO":
        verdict_line += f" | expected {want}: {'MATCH' if want == record.verdict else 'DIFFERENT'}"
    lines = [
        verdict_line,
        f"redactions: {record.redactions or 'none'}",
        f"claim: {record.claim.text}",
    ]
    if record.reasons:
        r = record.reasons[0]
        lines.append(f"top reason: {r.node} = {r.state} ({r.shift:+.2f})")
    if record.what_if:
        w = record.what_if[0]
        lines.append(f"what-if: if {w.node} were '{w.state}', p_true -> {w.p_true:.2f}")
    if record.family:
        lines.append(f"family: {record.family.family_id} ({record.family.source})")
    for f in record.lookalikes:
        lines.append(
            f"link warning: {f.domain} is a {f.kind}"
            + (f" of {f.lookalike_of}" if f.lookalike_of else "")
        )
    lines.append(f"source_cred: {record.evidence.source_cred}")
    lines.append(f"passport: {record.passport.passport_id}")
    return lines


def run_demo(client: httpx.Client, demo_dir: Path = DEMO) -> int:
    expected = load_expected(demo_dir)
    records: dict[int, VerdictRecord] = {}
    skipped: list[int] = []
    for step in (1, 2, 3, 4, 5):
        print(f"\n=== Step {step}: {TITLES[step]} ===")
        text = load_message(step, demo_dir)
        if text is None:
            print("SKIPPED: data/demo file is missing or still a TODO placeholder")
            skipped.append(step)
            continue
        records[step] = _check(client, text)
        for line in describe(step, records[step], expected.get(str(step), {})):
            print(" ", line)
    if 1 in records and 3 in records:
        a, b = records[1].family, records[3].family
        same = a is not None and b is not None and a.family_id == b.family_id
        print(f"\nstep 3 joins step 1's family: {'YES' if same else 'NO'}")

    print("\n=== Step 6: Rumour Radar ===")
    radar = [RadarItem.model_validate(i) for i in client.get("/radar").json()]
    if not radar:
        print("  (no Unverified family has 3 checks yet)")
    for item in radar:
        print(
            f"  {item.family_id}: surge {item.surge:.2f} (recent {item.recent}, "
            f"previous {item.previous}) keywords {', '.join(item.keywords)}"
        )

    print("\n=== Step 7: Reply card and convergence plot ===")
    last = records[max(records)] if records else None
    print(" ", last.reply_card if last else "(no message was checked)")
    plot = ROOT / "eval" / "convergence.png"
    print(
        "  convergence plot:",
        plot if plot.exists() else "missing (run: python -m eval.convergence)",
    )
    if skipped:
        print(f"\nSkipped steps (placeholders): {skipped}. Fill data/demo/ to run them.")
    return 0


def is_verity(client: httpx.Client) -> bool:
    """True only if the service answers /health with VERITY's index counts."""
    try:
        body = client.get("/health").json()
    except (httpx.HTTPError, ValueError):
        return False
    return isinstance(body, dict) and {"factchecks", "headlines", "domains"} <= set(body)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-spawn", action="store_true")
    ap.add_argument("--base", default="http://localhost:8000")
    args = ap.parse_args(argv)
    proc: subprocess.Popen[bytes] | None = None
    client = httpx.Client(base_url=args.base, timeout=60.0)
    try:
        if not is_verity(client):
            if args.no_spawn:
                print("VERITY API not reachable; run `make api` first.", file=sys.stderr)
                return 1
            port = free_port()  # port 8000 may belong to something else; never touch it
            client.close()
            client = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=60.0)
            proc = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "verity.api.app:app", "--port", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(120):
                time.sleep(0.5)
                if is_verity(client):
                    break
            else:
                print("API did not start", file=sys.stderr)
                return 1
        return run_demo(client)
    finally:
        client.close()
        if proc is not None:
            proc.terminate()


if __name__ == "__main__":
    sys.exit(main())
