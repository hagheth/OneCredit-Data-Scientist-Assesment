"""Score summary versions without an LLM, and build eval/results.md.

Run:  uv run python src/evaluate.py v1_baseline v2_factsheet
Writes:
  eval/checks/<version>.json  - per-company automatic check results
  eval/results.md             - one table across versions (+ LLM-judge scores if eval/judge/<version>.json exists)

Each check maps to a rule in eval/spec.md (see section 5 there).
"""

import json
import re
import sys
from pathlib import Path
from statistics import mean

from facts import build, load_records

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "eval" / "gold.md"
LABELS = ["Proceed", "Review closely", "Red flags", "Insufficient information"]
SEVERITY_ORDER = {"Proceed": 0, "Review closely": 1, "Insufficient information": 1, "Red flags": 2}

# Words that show a flag was mentioned (rule-based flags from facts.py). Lower-case regex on normalised text.
FLAG_PATTERNS = {
    "winding_up_status": r"winding[ -]up (status|\(status\))|status[^.\n]{0,15}winding[ -]up|in winding[ -]up|being wound up",
    "winding_up_petition": r"winding[ -]up petition|petition",
    "going_concern": r"going[ -]concern",
    "audit_disclaimer": r"disclaim",
    "no_financials": r"no financial (statements|figures|data|records|accounts)|no accounts",
    "negative_equity": r"negative equity|liabilities exceed (total )?assets",
    "losses": r"loss",
    "judgment_against": r"judg(e)?ment",
    "pending_defendant": r"pending",
    "cash_flow": r"operating cash flow|cash flow",
    "liquidity": r"current liabilities|current ratio|liquidity",
    "debt_service": r"debt[ -]service|dscr",
    "revenue_decline": r"revenue[^.\n]{0,40}(fell|fall|declin|drop|down|decreas)|(fell|declin|drop|decreas)[^.\n]{0,25}revenue",
    "missing_year": r"missing|not (filed|available) for fy|no fy\s?20\d\d",
}


# ---------------------------------------------------------------------------------------------------------------------
# Gold set


def split_items(text: str) -> list[str]:
    """Split on '; ' that is not inside parentheses."""
    items, depth, cur = [], 0, ""
    for ch in text:
        depth += ch == "("
        depth -= ch == ")"
        if ch == ";" and depth == 0:
            items.append(cur.strip())
            cur = ""
        else:
            cur += ch
    items.append(cur.strip())
    return [i.rstrip(".") for i in items if i]


def load_gold() -> dict[str, dict]:
    gold: dict[str, dict] = {}
    for block in re.split(r"^## ", GOLD.read_text(encoding="utf-8"), flags=re.MULTILINE)[1:]:
        m = re.match(r"(SYN-\d{6})", block)
        if not m:
            continue
        fields = dict(re.findall(r"^- \*\*(.+?):\*\* (.*)$", block, flags=re.MULTILINE))
        gold[m.group(1)] = {
            "decision": fields.get("Decision", "").strip(),
            "must_mention": split_items(fields.get("Must mention", "")),
            "should_mention": split_items(fields.get("Should mention", "")),
            "must_not_claim": split_items(fields.get("Must not claim", "")),
        }
    return gold


# ---------------------------------------------------------------------------------------------------------------------
# Text helpers


def normalise(text: str) -> str:
    for ch in "‐‑‒–—−":
        text = text.replace(ch, "-")
    return text.replace(" ", " ").replace(" ", " ")


def parse_verdict(text: str) -> str | None:
    m = re.search(r"verdict\W{0,5}(proceed|review closely|red flags|insufficient information)", text, flags=re.IGNORECASE)
    if not m:
        return None
    return next(label for label in LABELS if label.lower() == m.group(1).lower())


# ---------------------------------------------------------------------------------------------------------------------
# Number check (rule R3): every number in the summary should be traceable to the record


def record_values(record: dict) -> tuple[list[float], list[float], list[float]]:
    """Money values (RM), percentages (in %), and plain ratios that a summary could legitimately quote."""
    money: list[float] = [record["profile"]["shareCapital"]]
    pcts: list[float] = [s["percentage"] for s in record["relationships"]["shareholders"]]
    ratios: list[float] = []
    years = sorted(record["financials"]["years"], key=lambda y: y["financialYear"])
    cases = record["litigation"]["cases"]
    money += [c["claimAmount"] for c in cases]
    for role in ("defendant", "plaintiff"):
        for status in {c["status"] for c in cases}:
            sel = [c["claimAmount"] for c in cases if c["role"] == role and c["status"] == status]
            if sel:
                money.append(sum(sel))
    pend = [c["claimAmount"] for c in cases if c["role"] == "defendant" and c["status"] == "Pending"]
    if pend:
        money.append(sum(pend))
        money.append(sum(c["claimAmount"] for c in cases if c["role"] == "defendant" and c["status"] == "Pending"
                         and c["caseType"] != "Winding-up petition"))
    for y in years:
        st = y["statements"]
        money += [float(v) for v in st.values()]
        for group in y["ratiosAndMetrics"].values():
            for v in group.values():
                if v is None:
                    continue
                if abs(v) >= 1000:
                    money.append(v)
                else:
                    ratios.append(v)
                    pcts.append(v * 100)
        if st["currentLiabilities"]:
            ratios.append(st["currentAssets"] / st["currentLiabilities"])
        if st["totalAssets"]:
            pcts.append(st["totalEquity"] / st["totalAssets"] * 100)
    # growth between any two years for the main lines
    for key in ("revenue", "profitAfterTax", "borrowings", "totalEquity", "cash", "operatingCashFlow"):
        for i, a in enumerate(years):
            for b in years[i + 1:]:
                va, vb = a["statements"][key], b["statements"][key]
                if va:
                    pcts.append((vb / va - 1) * 100)
                    pcts.append(abs(vb / va - 1) * 100)
                money.append(vb - va)
    return money, pcts, ratios


NUM = r"(\d[\d,]*(?:\.\d+)?)"
# "RM 4.01m", "RM 355.9 k", and ranges "RM 1.1-1.3 m" (the unit applies to both ends)
MONEY_RE = re.compile(r"\bRM\s?" + NUM + r"(?:\s?-\s?" + NUM + r")?\s?([mM]|mil|million|[kK]|thousand|[bB])?\b"
                      # also "4.42 M" / "-0.02 M" without the RM prefix (v1 writes money this way in tables)
                      r"|(?<![\w.])-?" + NUM.replace("(", "(?P<bare>", 1) + r"\s?(?P<bareunit>M|mil|million)\b")
PCT_RE = re.compile(NUM + r"\s?%")
RATIO_RE = re.compile(r"(?<![\w.,])" + NUM + r"\s?(x|×)?(?![\w%.,])")


def _close(value: float, decimals: int, candidates: list[float], scale: float = 1.0) -> bool:
    tol = max(0.5 * 10 ** (-decimals) * scale, abs(value) * 0.015) * 1.0001  # x1.0001: allow exact half-up rounding
    return any(abs(abs(value) - abs(c)) <= tol for c in candidates)


def unsupported_numbers(text: str, record: dict) -> list[str]:
    money, pcts, ratios = record_values(record)
    bad: list[str] = []
    for m in MONEY_RE.finditer(text):
        unit = (m.group(3) or m.group("bareunit") or "").lower()
        mult = 1e6 if unit in ("m", "mil", "million") else 1e3 if unit in ("k", "thousand") else 1e9 if unit == "b" else 1
        for raw in (m.group(1), m.group(2), m.group("bare")):
            if raw is None:
                continue
            raw = raw.replace(",", "")
            dec = len(raw.split(".")[1]) if "." in raw else 0
            if not _close(float(raw) * mult, dec, money, scale=mult):
                bad.append(m.group(0))
                break
    for m in PCT_RE.finditer(text):
        raw = m.group(1).replace(",", "")
        dec = len(raw.split(".")[1]) if "." in raw else 0
        if not _close(float(raw), dec, pcts) and float(raw) not in (100.0,):
            bad.append(m.group(0))
    # plain decimals such as ratios ("0.87", "2.5x"); skip integers (years, counts, days)
    stripped = MONEY_RE.sub(" ", PCT_RE.sub(" ", text))
    stripped = re.sub(r"\d{4}-\d{2}-\d{2}|FY\s?\d{4}|\d{1,2} \w{3,9} \d{4}", " ", stripped)
    for m in RATIO_RE.finditer(stripped):
        raw = m.group(1).replace(",", "")
        if "." not in raw:
            continue
        if not _close(float(raw), len(raw.split(".")[1]), ratios + [abs(r) for r in ratios]):
            bad.append(m.group(0).strip())
    return bad


def wrong_case_count(text: str, record: dict) -> list[str]:
    cases = record["litigation"]["cases"]
    n_def = sum(c["role"] == "defendant" for c in cases)
    allowed = {len(cases), n_def, len(cases) - n_def}
    allowed |= {sum(c["status"] == s for c in cases) for s in {c["status"] for c in cases}}
    allowed |= {sum(c["caseType"] == t for c in cases) for t in {c["caseType"] for c in cases}}
    allowed |= {sum(c["role"] == "defendant" and c["status"] == "Pending" for c in cases)}
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
    bad = []
    for m in re.finditer(r"\b(\d+|one|two|three|four|five|six|seven|eight)\s+(?:[\w/-]+\s+){0,2}(cases|claims|lawsuits|suits)\b",
                         text, flags=re.IGNORECASE):
        n = int(m.group(1)) if m.group(1).isdigit() else words[m.group(1).lower()]
        if n not in allowed:
            bad.append(m.group(0))
    return bad


# ---------------------------------------------------------------------------------------------------------------------
# Per-summary checks


def check(reg: str, summary: str, record: dict, gold: dict | None) -> dict:
    text = normalise(summary)
    low = text.lower()
    fs = build(record)
    words = len(text.split())

    verdict = parse_verdict(text)
    gold_dec = gold["decision"] if gold else None
    flags = [f.code for f in fs.red_flags]
    found = {c: bool(re.search(FLAG_PATTERNS[c], low)) for c in flags}
    head = low[: max(1, len(low) // 3)]  # first third of the summary
    early = {c: bool(re.search(FLAG_PATTERNS[c], head)) for c in flags}
    cases = record["litigation"]["cases"]

    return {
        "registrationNumber": reg,
        "words": words,
        "within_target": words <= 180,
        "within_hard_limit": words <= 220,
        "verdict": verdict,
        "gold_decision": gold_dec,
        "verdict_correct": verdict == gold_dec if gold_dec else None,
        "verdict_steps_off": (abs(SEVERITY_ORDER[verdict] - SEVERITY_ORDER[gold_dec])
                              if verdict and gold_dec else None),
        "red_flags": flags,
        "flags_mentioned": found,
        "flags_in_first_third": early,
        "account_age_stated": (not record["financials"]["years"]) or bool(re.search(r"\d+\s?months", low)),
        "role_stated": (not cases) or bool(re.search(r"defendant|plaintiff|being sued|suing|brought by|against the company", low)),
        "sections_present": all(s in low for s in ("key risks", "business", "financials", "ownership", "litigation")),
        "unsupported_numbers": unsupported_numbers(text, record),
        "wrong_case_counts": wrong_case_count(text, record),
    }


def rate(values: list[bool]) -> str:
    return f"{sum(values)}/{len(values)} ({sum(values) / len(values):.0%})" if values else "n/a"


def summarise_version(rows: list[dict]) -> dict[str, str]:
    flag_total = sum(len(r["red_flags"]) for r in rows)
    flag_hit = sum(sum(r["flags_mentioned"].values()) for r in rows)
    flag_early = sum(sum(r["flags_in_first_third"].values()) for r in rows)
    with_verdict = [r for r in rows if r["verdict_correct"] is not None]
    clean = [r for r in rows if r["gold_decision"] == "Proceed"]
    return {
        "Summaries": str(len(rows)),
        "Verdict matches gold": rate([r["verdict_correct"] for r in with_verdict]),
        "Red-flag company called Proceed (hard fail)": str(sum(r["gold_decision"] == "Red flags" and r["verdict"] == "Proceed"
                                                            for r in rows)),
        "Clean company not called Proceed (false alarm)": str(sum(r["verdict"] != "Proceed" for r in clean)),
        "Red flags mentioned (recall)": f"{flag_hit}/{flag_total} ({flag_hit / flag_total:.0%})" if flag_total else "n/a",
        "Red flags in first third": f"{flag_early}/{flag_total} ({flag_early / flag_total:.0%})" if flag_total else "n/a",
        "Unsupported numbers (auto, total)": str(sum(len(r["unsupported_numbers"]) for r in rows)),
        "Summaries with an unsupported number": rate([bool(r["unsupported_numbers"]) for r in rows]),
        "Wrong case counts": str(sum(len(r["wrong_case_counts"]) for r in rows)),
        "Account age stated": rate([r["account_age_stated"] for r in rows]),
        "Case role stated (when cases exist)": rate([r["role_stated"] for r in rows]),
        "All sections present": rate([r["sections_present"] for r in rows]),
        "Mean words": f"{mean(r['words'] for r in rows):.0f}",
        "Within 180 words": rate([r["within_target"] for r in rows]),
        "Within 220 words (hard limit)": rate([r["within_hard_limit"] for r in rows]),
    }


# ---------------------------------------------------------------------------------------------------------------------


def load_summaries(version: str) -> dict[str, str]:
    path = ROOT / "summaries" / f"{version}.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {r["registrationNumber"]: r["summary"] for r in rows}


def judge_table(versions: list[str]) -> list[str]:
    judge_dir = ROOT / "eval" / "judge"
    present = [v for v in versions if (judge_dir / f"{v}.json").exists()]
    if not present:
        return []
    from judge import JUDGE_DIR, summarise_judge  # noqa: PLC0415 - only needed once judge results exist

    stats = {v: summarise_judge(json.loads((JUDGE_DIR / f"{v}.json").read_text(encoding="utf-8"))) for v in present}
    keys = list(next(iter(stats.values())))
    lines = ["", "## LLM judge (qwen/qwen3.8-27b, rubric in eval/spec.md section 4)", "",
             "| Measure | " + " | ".join(present) + " |", "|---|" + "---|" * len(present)]
    lines += [f"| {k} | " + " | ".join(stats[v][k] for v in present) + " |" for k in keys]
    for v in present:
        skipped = [r["registrationNumber"] for r in json.loads((JUDGE_DIR / f"{v}.json").read_text(encoding="utf-8"))
                   if "skipped" in r]
        if skipped:
            lines.append(f"\nNot judged for {v}: {', '.join(skipped)} (the API call kept hanging; skipped).")
    return lines


def main() -> None:
    versions = sys.argv[1:] or ["v1_baseline", "v2_factsheet"]
    records, gold = load_records(), load_gold()
    out_dir = ROOT / "eval" / "checks"
    out_dir.mkdir(parents=True, exist_ok=True)

    tables: dict[str, dict[str, str]] = {}
    for v in versions:
        summaries = load_summaries(v)
        rows = [check(reg, s, records[reg], gold.get(reg)) for reg, s in summaries.items()]
        (out_dir / f"{v}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        tables[v] = summarise_version(rows)

    keys = list(next(iter(tables.values())))
    lines = ["# Results", "", "Generated by `src/evaluate.py` (automatic checks) and `src/judge.py` (LLM judge).",
             "Per-company details: `eval/checks/<version>.json`, `eval/judge/<version>.json`.", "",
             "## Automatic checks (no LLM)", "",
             "| Measure | " + " | ".join(versions) + " |", "|---|" + "---|" * len(versions)]
    lines += [f"| {k} | " + " | ".join(tables[v][k] for v in versions) + " |" for k in keys]
    lines += judge_table(versions)
    (ROOT / "eval" / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
