"""Generate summaries for one prompt version and write summaries/<version>.jsonl for the viewer.

Run:
  uv run python src/generate.py v2_factsheet            # the 13 sample companies (eval/sample.md)
  uv run python src/generate.py v2_factsheet --all      # all 50 companies

Raw responses are kept in runs/<version>/<registrationNumber>.json (and the cache in runs/cache/),
so summaries can be re-scored without calling the model again.
"""

import argparse
import json
import re
from pathlib import Path

from facts import load_records
from llm import complete
from prompts import VERSIONS

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "eval" / "sample.md"


def sample_ids() -> list[str]:
    return re.findall(r"^\|\s*(SYN-\d{6})", SAMPLE.read_text(encoding="utf-8"), flags=re.MULTILINE)


def clean(text: str) -> str:
    """Strip a ```markdown fence if the model wrapped its answer in one."""
    text = text.strip()
    m = re.fullmatch(r"```(?:markdown|md)?\s*\n(.*)\n```", text, flags=re.DOTALL)
    return m.group(1).strip() if m else text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("version", choices=sorted(VERSIONS))
    ap.add_argument("--all", action="store_true", help="all 50 companies instead of the sample")
    args = ap.parse_args()

    version = VERSIONS[args.version]
    records = load_records()
    ids = sorted(records) if args.all else sample_ids()
    run_dir = ROOT / "runs" / version.name
    run_dir.mkdir(parents=True, exist_ok=True)

    rows, tokens = [], 0
    for i, reg in enumerate(ids, 1):
        messages = version.make_messages(records[reg])
        res = complete(version.model, messages, temperature=version.temperature,
                       max_tokens=version.max_tokens, extra=version.extra)
        summary = clean(res["content"])
        used = (res["usage"] or {}).get("total_tokens", 0)
        tokens += 0 if res["cached"] else used
        flag = "" if res["finish_reason"] == "stop" else f"  WARNING finish_reason={res['finish_reason']}"
        print(f"[{i}/{len(ids)}] {reg} {'(cached)' if res['cached'] else f'{used} tokens'} "
              f"{len(summary.split())} words{flag}")
        (run_dir / f"{reg}.json").write_text(json.dumps(
            {"registrationNumber": reg, "version": version.name, "description": version.description,
             "messages": messages, "response": res}, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append({"registrationNumber": reg, "summary": summary})

    out = ROOT / "summaries" / f"{version.name}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)} ({len(rows)} summaries, {tokens} new tokens)")


if __name__ == "__main__":
    main()
