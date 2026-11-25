# Working notes and time log

Setup (not timed): tools installed, repo linked, `uv sync`, viewer checked, Groq key in `.env`.

## Time log

| Session | Start | End | Hours | What |
|---|---|---|---|---|
| 1 | 2026-11-25 09:35 | | | B: understand the problem (profile data, pick sample, read companies) |

## Decisions

- Sample: 13 companies chosen by rules in `src/explore.py` so every kind of risk in the data appears at least once, plus 2 clean controls (see `eval/sample.md`). Clean controls test that the system does not invent risk.
- Decision scale has 4 labels: Proceed / Review closely / Red flags / Insufficient information. Companies with no financial statements (SYN-000302, SYN-001203) are "Insufficient information", not Red flags: Red flags means evidence of a problem; missing accounts means we can't tell (the cause could be non-filing or a data gap), and the analyst's action differs (request the accounts first).
- Gold set (`eval/gold.md`) is written by hand from the viewer, independently of the rule-based flags, so evaluation is not circular (rules checking rules).
- Observations from the profile (`eval/data_profile.md`):
  - All latest accounts end in 2024 (8 on 31 Mar, 8 on 30 Jun, 8 on 30 Sep, 23 on 31 Dec) but records are as of 31 Dec 2025, so the newest figures are 12 to 21 months old: a summary should say so.
  - Every company with a loss in the latest year had a loss in every year filed (11): persistent, not one-off.
  - Profit and risk can disagree: SYN-001389 is profitable (RM 4.0m) yet faces 3 winding-up petitions; SYN-000545 is winding up while profitable. A summary must not let good financials hide litigation.
  - 42 of 50 have a shareholder above 50%: concentration is normal here, so it is not a useful flag on its own.
- Found while writing the gold set:
  - Plaintiff vs defendant matters: SYN-000267 has 5 cases but is the plaintiff in all of them. Counting cases alone would mislabel it.
  - Gaps inside the years: SYN-000286 has FY2022 and FY2024 but no FY2023.
  - Similar names are not links: SYN-000451's former name "Gemilang Ventures" and SYN-001203's parent "Gemilang Holdings". A summary must not connect them.
  - The registered state often differs from where the business operates (e.g. registered in Selangor, hotel in Penang). Not a risk, but a summary should not confuse the two.

## Models

- Llama 3.3 70B (planned) is no longer on Groq. Available text models: openai/gpt-oss-120b, openai/gpt-oss-20b, qwen/qwen3.8-27b.
- Generator: openai/gpt-oss-120b, reasoning_effort=low, temperature 0.2. Judge (planned): qwen/qwen3.8-27b (different model family).
- Free-tier limits seen in headers: 1,000 requests/day, 8,000 tokens/minute per model. TPM is the bottleneck; llm.py waits on 429 and retries.
- v2 on 13 companies: ~24.6k tokens.

## First read of v1_baseline (manual)

- ~37.7k tokens for 13 companies (about 1.5x v2: the raw JSON is bigger than the fact sheet).
- Length 320 to 581 words (2 to 3x the target); big Markdown tables; no verdict label; account age never stated.
- Factual errors: SYN-000545 "7 cases" (8) and "pending claims ≈ RM 1.5m" (RM 2.50m); "free cash flow turned negative in FY2024" (it is +RM 0.61m). SYN-001389 "7 cases" (8).
- Risk buried: SYN-001389's "Potential red flags" lists ownership concentration and leverage but not the pending winding-up petition (only in the litigation row), and closes with "why it may be worth a deeper look: strong growth".
- Plaintiff misread: SYN-000267's plaintiff-only cases listed as a red flag ("may indicate contractual management issues").
- Advice beyond triage: SYN-000302 gives a recommendation and asks for ISO certifications.
- So the baseline fails on exactly the points the spec was written for: the comparison supports the design.

## First read of v2_factsheet (manual, before automatic evaluation)

- Verdicts: 13 of 13 match the gold set.
- Account age stated in all 13; plaintiff/defendant stated where there are cases.
- Errors found:
  - SYN-000451: calls a *dismissed* case "pending" (status mixed up).
  - SYN-000286: "pending debt recovery judgment": the judgment is entered, not pending.
  - SYN-000267: "current ratio stayed above 2.0" is false (1.74 in FY2023), i.e. a computed claim not in the fact sheet. Also lists negative free cash flow and a *plaintiff* case under "Key risks" while saying "no red-flag issues" (contradiction with rule 4/8).
  - SYN-001389: "No winding-up petitions have been resolved in the company's favour": an inference not in the record.
- Length: 3 of 13 over 180 words; SYN-001212 at 232 is over the 220 hard limit.
- Style: Key risks for SYN-000067 are grouped by year, repeating figures; SYN-001203 prints "N/A months" from the template.
- For the number check: the model writes "RM 5.13 m" (space) and uses non-breaking hyphens (U+2011); normalise before matching.

## Evaluation notes (Part E)

- Automatic number check: first version raised 11 flags on v1, only 3 real (27% precision). After fixing the parser
  ("4.42 M" without "RM") and exact half-up rounding: 6 flags, 3 real (50%). Every flag checked by hand in
  `eval/manual_review.md`. It cannot catch wrong statuses or comparisons; those need the judge or a human.
- Judge, first run (kept in `eval/judge_factsheet_only/`): given only the fact sheet as ground truth. It counted v1's
  correct figures from the raw record (quick ratio, gross margin, cash conversion cycle, audit firm name) as "not
  supported", giving v1 49 "errors". Unfair to v1. Second run gives the judge the raw record too.
- Judge false positives seen in the first run on v2: "70% owned by Gemilang Holdings" flagged as a must-not-claim
  breach (it is exactly what the gold set asks for); "FY2022, FY2024" read as "claims 3 years of accounts"; "petition
  ... pending" read as "claims the petition is resolved". So the judge's must-not-claim count needs a human check.
- Judge true positives on v2: both status mix-ups (SYN-000451 dismissed called pending; SYN-000286 judgment called
  pending). It missed SYN-000267 "current ratio stayed above 2.0".

- Judge, second run (raw record + fact sheet): v1 errors fell from 49 to 10 once correct figures from the record were
  accepted. v2: 5 errors (4 real), 4 must-not-claim violations (1 real); missed 2 errors I found by reading. Checked
  item by item in `eval/manual_review.md` section 2.
- One judge call (v2, SYN-001569) hung repeatedly (25+ min with no timeout, then repeated slow retries). Added a
  120s request timeout and a 90s cap on rate-limit waits to `src/llm.py`, then skipped that company (`--cache-only`).

## v3_grouped (fixes for v2's errors)

- Changes, each tied to a v2 error: litigation grouped by status in the fact sheet (OPEN / DECIDED / CLOSED / BROUGHT
  BY); Key risks only from RED FLAGS; no claims about what the record does not cover; no "all/above" claims unless
  every figure supports them; OTHER POINTS always in Ownership; net margin stated when under 3%; tighter length limits.
- **Bug caught by the evaluation:** v3's first run called SYN-001389 "Proceed" with "no red flags". Cause was my code:
  adding the grouped layout moved the litigation red-flag rules into the old layout's branch only, so grouped fact
  sheets had no petition/judgment/pending flags. The flag-recall check and the hard-fail check exposed it at once.
  Fixed in `src/facts.py` (flags raised for every layout; both layouts now give identical flags for all 13) and v3
  regenerated (only 4 companies changed). Buggy output kept in `runs/v3_grouped_buggy_run.jsonl`.
  Lesson: run the automatic checks after every change, not just prompt changes.
- After the fix (automatic): verdicts 13/13, flag recall 33/33, all 13 within 220 words, 11/13 within 180,
  mean 140 words (v2: 172).
- Read by hand: SYN-000451 now says "One dismissed case" (fixed); SYN-000286 now "1 decided judgment" (fixed);
  SYN-000267 no longer lists plaintiff cases as risks and mentions the 2025 rename (fixed). New error: SYN-000545
  "four open breach-of-contract cases (claims totalling RM 2.46 m)": 3 breach of contract + 1 debt recovery, total
  RM 2.50m, and the point is repeated in two bullets. SYN-001389 sums open claims to RM 731.6k (true total RM 731.7k).
- Checker fixes: "debt-service" (hyphen) was missed by the flag regex; "margins below -8%" was a false alarm.

- Judge on v3 stopped after 1 of 13: Groq daily token limit for qwen/qwen3.8-27b (200,000 tokens/day; 198,291 used
  by the two v1/v2 judge runs, each call sending the full record). The per-minute limit (8k) was planned for; the
  daily one was not. Lesson: estimate daily tokens per model before a run (13 judge calls with the raw record ~65k).
- So v3 was checked by hand instead (`eval/manual_review.md` section 4): must-mention 41/50 covered, 7 partly, 2
  missed; 0 must-not-claim breaches; 4 factual errors (2 real: SYN-000029 says operating cash flow turned negative,
  it is free cash flow; SYN-000545 RM 2.46m / "four breach-of-contract"; 2 minor). v2's errors are all gone.
  New weaknesses: plaintiff cases dropped entirely (SYN-000267), OTHER POINTS dropped in 2 of 8, clean summaries
  still over 120 words because Ownership lists every director. These are the v4 targets.
- The number check caught only 1 of v3's 2 real errors: a wrong direction ("turned negative") is not a wrong number.

## AI tools used

- Claude Code: data profiling script, sample selection, project scaffolding. (Keep this list updated.)
- Claude Code drafted the summary spec and rubric (`eval/spec.md`) and section 1 of `CASE_STUDY.md`; to be reviewed and edited by me.
- Claude Code drafted the gold set (`eval/gold.md`) from the full records; I reviewed and edited it. Limitation to state in the case study: the gold labels are not from a real vetting analyst, and an AI draft may share blind spots with the LLM being evaluated.

## What failed / surprises

-
