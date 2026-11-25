# Manual review

Two jobs: (1) check what the automatic checks flagged, so their precision is known; (2) score a few summaries myself
with the rubric (`eval/spec.md` section 4), to see whether the LLM judge can be trusted.

## 1. Automatic number check: every flag checked by hand

| Version | Company | Flagged | Context | Real error? |
|---|---|---|---|---|
| v1 | SYN-000029 | `0.22` | "cash ratio remains low (0.22-0.54)" | **Yes**: FY2022 cash ratio is 0.24 |
| v1 | SYN-000067 | `1.0` | "Liquidity ratios below the 1.0 benchmark" | No: a benchmark, not a fact |
| v1 | SYN-000286 | `RM 800 k` | "Ongoing litigation totalling > RM 800 k" | No: all claims sum to RM 892.5k, so "> RM 800k" is true |
| v1 | SYN-001389 | `28 %` | "Equity ≈ 28 % of assets" | No: 28.5%, rounded |
| v1 | SYN-000545 | `7 active/settled cases` | case count | **Yes**: 8 cases |
| v1 | SYN-001389 | `7 open/settled cases` | case count | **Yes**: 8 cases |

Precision of the automatic flags: **3 of 6 real (50%)**. Before two parser fixes (amounts written as "4.42 M" without
"RM", and exact half-up rounding), 11 flags were raised and only 3 were real (27%). The check is a cheap screen; every
flag needs a human look before it is counted as an error.

What it cannot catch (found by reading, not by the check): wrong statuses ("dismissed" called "pending"), wrong
comparisons ("current ratio stayed above 2.0"), and unsupported inferences. Those are for the judge and for me.

## 2. LLM judge findings on v2: each checked against my own reading

| Company | Judge said | Real? |
|---|---|---|
| SYN-000286 | error: judgment called "pending" | **Yes** |
| SYN-000451 | error: dismissed case called "pending" | **Yes** |
| SYN-000217 | error: "no shareholder changes in 2025" not supported | **Yes, minor**: the record has no dates for shareholder changes |
| SYN-001203 | error: "no shareholder changes in 2025" not supported | **Yes, minor** (same reason) |
| SYN-001203 | error: "no winding-up petitions" not supported | No: the record lists its only case, which is not a petition |
| SYN-000451 | must-not-claim: litigation framed as a risk | **Yes**: calling the dismissed case "pending" makes it look live |
| SYN-000286 | must-not-claim: "claims 3 years of accounts" | No: the summary says "FY2022, FY2024" |
| SYN-000286 | must-not-claim: "claims the petition is resolved" | No: the summary says "pending" |
| SYN-001203 | must-not-claim: "says more about the parent than name, country, stake" | No: it gives only the name and stake |

Errors I found that the judge missed: SYN-000267 "current ratio stayed above 2.0" (1.74 in FY2023); SYN-001389 "No
winding-up petitions have been resolved in the company's favour" (not in the record).

**Judge precision on v2:** factual errors 4 of 5 correct; must-not-claim violations 1 of 4 correct.
**Judge recall on v2:** caught 4 of the 6 errors I know of (2 major, 2 minor), missed 2.
So the judge is useful for factual errors but its must-not-claim calls need a human check before being counted.
SYN-001569 (v2) was not judged: the API call hung repeatedly and was skipped.

## 3. My rubric scores (to check the judge)

Score these with the rubric, *before* looking at the judge's scores in `eval/judge/`. Chosen to cover a clean company,
a hard legal case, a no-accounts case and a summary with a known error.

| Version | Company | Faithfulness | Risk coverage | Verdict | Prioritisation | Concision | Gap honesty | Errors I found |
|---|---|---|---|---|---|---|---|---|
| v2 | SYN-000029 | | | | | | | |
| v2 | SYN-000451 | | | | | | | |
| v2 | SYN-001389 | | | | | | | |
| v1 | SYN-001389 | | | | | | | |
| v1 | SYN-000302 | | | | | | | |

## 4. v3_grouped read by hand against the gold set (no LLM judge)

The judge could not run on v3 (Groq daily token limit for the judge model, see `NOTES.md`), so I checked all 13 v3
summaries myself, item by item, against `eval/gold.md` and each company's fact sheet (`python src/facts.py SYN-...`).
Same questions the judge answers: are the must-mention items covered, is any must-not-claim item broken, are there
factual errors.

### Factual errors

| Company | Summary says | Record says | Severity |
|---|---|---|---|
| SYN-000029 | "operating cash flow turned negative in FY2024" | OCF is +RM 113.6k in FY2024 (it is *free* cash flow that is negative) | **Real**: makes a clean company look worse |
| SYN-000545 | "four open breach-of-contract cases (claims totalling RM 2.46 m)", repeated in Litigation | 3 breach of contract + 1 debt recovery, total RM 2.50m; contradicts its own bullet above ("total RM 2.50 m") | **Real**: wrong amount, wrong case type, said twice |
| SYN-001203 | "1 case brought by the company settled for RM 22.5k" | RM 22.5k is the claim amount; the settlement amount is not in the record | Minor |
| SYN-001389 | open claims "totalling RM 731.6k" | RM 122.1k + RM 559.5k + RM 50.1k = RM 731.7k | Minor (model's own arithmetic) |

v2 had 6 errors I know of (2 status mix-ups, 1 false comparison, 1 inference, 2 minor); v3 has 4 (2 real, 2 minor).
All of v2's errors are gone; the two real v3 errors are new. Both come from the model doing its own arithmetic or
wording a figure the fact sheet did not state in that form.

### Must-mention coverage (50 items across 13 companies)

| Company | Covered | Partly | Missed | Notes |
|---|---|---|---|---|
| SYN-000029 | 5 | 0 | 0 | |
| SYN-000067 | 4 | 2 | 0 | equity fall given without figures; interest cover shown only as negative DSCR |
| SYN-000217 | 2 | 1 | 1 | **missed rising leverage** (borrowings +88% was an OTHER POINT and was dropped); FY2022/FY2024 clean audits not stated |
| SYN-000267 | 3 | 0 | 1 | **missed the 5 cases it brought as plaintiff** ("No court cases on record against the company" is true but hides them) |
| SYN-000282 | 5 | 0 | 0 | |
| SYN-000286 | 3 | 0 | 0 | |
| SYN-000302 | 2 | 0 | 0 | |
| SYN-000451 | 5 | 0 | 0 | |
| SYN-000545 | 3 | 1 | 0 | pending total right in one bullet, wrong in two other places |
| SYN-001203 | 2 | 0 | 0 | |
| SYN-001212 | 4 | 0 | 0 | |
| SYN-001389 | 1 | 2 | 0 | petition statuses right but no dates; "8 cases" without saying all are as defendant |
| SYN-001569 | 2 | 1 | 0 | margin figures given but not called thin |
| **Total** | **41 (82%)** | **7 (14%)** | **2 (4%)** | |

Must-not-claim violations: **0 of 13**. Verdicts: **13 of 13** match the gold set.

### Rule compliance (from `eval/spec.md` / the v3 prompt)

- Rule 8, every OTHER POINT in Ownership: broken in 2 of 8 companies that have one (SYN-000217 drops the borrowing
  rise; SYN-001389 replaces the new Managing Director with "other directors appointed 2014-2025 as listed").
- Length: 2 of 13 over 180 words (SYN-000545 199, SYN-001212 200). Clean companies should be under 120: only 1 of 3
  (SYN-000029 144, SYN-000267 127). The main cause is Ownership listing every director and appointment date.
- Litigation by group: correct statuses in every summary (v2's main error is fixed), but rule 4 ("cases brought by the
  company are not a risk") led the model to leave plaintiff cases out entirely (SYN-000267).

### What the automatic checks caught on v3

Number check: 3 flags; 2 real (both the SYN-000545 "RM 2.46 m"), 1 false alarm (SYN-000067 "margins below -8%":
every margin is -8.6% or lower, so it is true). It missed SYN-000029 (a wrong *direction*, not a wrong number) and
SYN-001389 (RM 0.1k off, inside the rounding tolerance by design). So the number check found 1 of the 2 real errors.

### What to fix in a v4

1. Give the model the totals it needs (open-claim total by case type) so it never adds up figures itself.
2. Ownership: largest shareholder, any company shareholder and 2025 changes only, not every director (saves ~30 words).
3. Litigation line must always state cases brought by the company (count and any pending), labelled "not a risk".
4. Say "free cash flow" and "operating cash flow" explicitly in the fact sheet's trend lines, and add a check that
   compares the sign of any cash-flow claim with the record.
