"""LLM-as-judge: score each summary against the gold set and the rubric in eval/spec.md.

Run:  uv run python src/judge.py v1_baseline v2_factsheet
Writes eval/judge/<version>.json. A different model family (Qwen) judges the generator (GPT-OSS), so the judge
does not grade its own writing. Responses are cached like everything else (src/llm.py).

The judge gets the raw record (ground truth), the fact sheet (readable digest), the gold entry, and the summary.
A first run gave it only the fact sheet; it then counted correct figures from the raw record (e.g. quick ratio) as
errors, which made v1 look worse than it is. See NOTES.md.
Its job is the part regexes cannot do: is each must-mention item covered, is any must-not-claim item said, and
is any statement wrong (e.g. a dismissed case called pending).
"""

import json
import sys
from pathlib import Path
from statistics import mean

from evaluate import load_gold, load_summaries, normalise
from facts import build, load_records
from llm import complete

ROOT = Path(__file__).resolve().parent.parent
JUDGE_DIR = ROOT / "eval" / "judge"
JUDGE_MODEL = "qwen/qwen3.8-27b"
JUDGE_EXTRA = {"reasoning_effort": "none", "response_format": {"type": "json_object"}}
DIMENSIONS = ["faithfulness", "risk_coverage", "verdict", "prioritisation", "concision_format", "gap_honesty"]

SYSTEM = """You are a strict evaluator of company summaries written for analysts who vet suppliers and partners.

You get:
- RECORD: the full company record as JSON (as of 31 Dec 2025). This is the ground truth. Ratios are decimals \
(0.12 = 12%); amounts are in RM.
- FACT SHEET: a readable digest of the same record, with computed trends and totals. Also correct.
A statement is supported if the RECORD or the FACT SHEET supports it (including simple rounding or arithmetic on them).
- GOLD: what an expert says the summary must say (decision, must-mention items) and must not say (must-not-claim).
- SUMMARY: the text to evaluate.

Do these steps:
1. For each MUST MENTION item, decide if the summary conveys it: "yes" (clearly stated), "partly" (only some of it, \
or vague), or "no". Exact wording is not required; the meaning and the key numbers are.
2. List every MUST NOT CLAIM item the summary actually says or clearly implies. Quote the summary.
3. List every factual error: any statement that contradicts the record or is supported by neither the record nor the \
fact sheet. Check numbers, \
years, case statuses (pending vs settled vs dismissed vs judgment entered), roles (defendant vs plaintiff), counts, and \
claims of trends. Quote the summary and say what is wrong. Rounding (RM 4.01m written as RM 4.0m) is not an error. \
Do not list style issues here.
4. Score each dimension from 1 to 5:
   - faithfulness: 5 every fact correct and traceable; 3 one minor slip; 1 an invented or wrong material fact.
   - risk_coverage: 5 every must-mention item covered; 3 most covered but one important item missing; 1 the main risk \
missing.
   - verdict: 5 the summary's verdict label equals the gold decision; 3 one step off (e.g. Review closely vs Red \
flags); 1 two steps off or no verdict label at all.
   - prioritisation: 5 the most serious risk comes first and risks come before background; 3 risks present but buried; \
1 risk hidden behind positives.
   - concision_format: 5 short (about 100 to 180 words), scannable, verdict then risks then the rest; 3 some padding or \
structure issues; 1 long (over 300 words) or unstructured.
   - gap_honesty: 5 states the age of the accounts and every gap (missing accounts, missing years, unverified years) \
that applies; 3 some stated; 1 gaps ignored or filled with guesses.

Return only JSON in this shape:
{"must_mention": [{"item": "...", "covered": "yes|partly|no", "evidence": "short quote or 'not found'"}],
 "must_not_claim_violations": [{"item": "...", "quote": "..."}],
 "factual_errors": [{"quote": "...", "problem": "..."}],
 "scores": {"faithfulness": 0, "risk_coverage": 0, "verdict": 0, "prioritisation": 0, "concision_format": 0, \
"gap_honesty": 0},
 "comment": "one sentence"}"""


def judge_one(record: dict, gold: dict, summary: str, cache_only: bool = False) -> dict:
    gold_text = "\n".join([
        f"Decision: {gold['decision']}",
        "MUST MENTION:", *[f"- {i}" for i in gold["must_mention"]],
        "MUST NOT CLAIM:", *[f"- {i}" for i in gold["must_not_claim"]],
    ])
    user = (f"RECORD\n{json.dumps(record)}\n\nFACT SHEET\n{build(record).text()}\n\n"
            f"GOLD\n{gold_text}\n\nSUMMARY\n{normalise(summary)}")
    res = complete(JUDGE_MODEL, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                   temperature=0.0, max_tokens=2500, extra=JUDGE_EXTRA, cache_only=cache_only)
    if res is None:
        return {"skipped": "not judged (API call kept hanging; skipped)", "cached": False, "usage": None}
    try:
        out = json.loads(res["content"])
    except json.JSONDecodeError:
        out = {"error": "judge returned invalid JSON", "raw": res["content"]}
    return {**out, "cached": res["cached"], "usage": res["usage"]}


def summarise_judge(rows: list[dict]) -> dict[str, str]:
    ok = [r for r in rows if "scores" in r]
    items = [i for r in ok for i in r.get("must_mention", [])]
    cover = {"yes": 1.0, "partly": 0.5, "no": 0.0}
    stats = {
        "Judged": f"{len(ok)}/{len(rows)}",
        "Must-mention coverage (yes=1, partly=0.5)":
            f"{sum(cover.get(i.get('covered'), 0) for i in items) / len(items):.0%}" if items else "n/a",
        "Must-not-claim violations": str(sum(len(r.get("must_not_claim_violations", [])) for r in ok)),
        "Factual errors (judge)": str(sum(len(r.get("factual_errors", [])) for r in ok)),
        "Summaries with no factual error": f"{sum(not r.get('factual_errors') for r in ok)}/{len(ok)}",
    }
    for d in DIMENSIONS:
        vals = [r["scores"].get(d) for r in ok if isinstance(r["scores"].get(d), int | float)]
        stats[f"Mean {d} (1-5)"] = f"{mean(vals):.2f}" if vals else "n/a"
    return stats


def main() -> None:
    cache_only = "--cache-only" in sys.argv  # build results from saved responses only, no API calls
    versions = [a for a in sys.argv[1:] if not a.startswith("--")] or ["v1_baseline", "v2_factsheet"]
    records, gold = load_records(), load_gold()
    JUDGE_DIR.mkdir(parents=True, exist_ok=True)
    for v in versions:
        rows = []
        for i, (reg, summary) in enumerate(load_summaries(v).items(), 1):
            if reg not in gold:
                continue
            res = judge_one(records[reg], gold[reg], summary, cache_only=cache_only)
            rows.append({"registrationNumber": reg, **res})
            errs = len(res.get("factual_errors", []))
            print(f"[{v} {i}] {reg} {'(cached)' if res['cached'] else ''} scores={res.get('scores')} errors={errs}")
        (JUDGE_DIR / f"{v}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(v, summarise_judge(rows))


if __name__ == "__main__":
    main()
