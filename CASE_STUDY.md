# Case study: company summaries for supplier vetting

## 1. What a good summary is for this team, and why

**The reader and the decision.** The team vets companies before choosing them as suppliers or project partners. The
summary is read *first*, before the long record, to answer one question: *is this company worth a closer look, and
what should I look at first?* It is a triage tool, not the final decision, and the full record sits right below it.

That gives two kinds of error, and both cost the team:
- **a missed red flag**: the analyst moves on with a supplier that is being wound up;
- **a false alarm**: the analyst drops a sound supplier, or wastes time on one.

So a good summary is **decision-first, risk-first, short, and never wrong about a fact**.

**How I worked out what matters.** I profiled all 50 records (`eval/data_profile.md`) and read 13 companies chosen to
cover every kind of risk in the data, plus 2 clean ones (`eval/sample.md`), writing down for each what an analyst would
need to know (`eval/gold.md`). What I found shaped the spec:

- **Profit and risk often disagree.** SYN-001389 made RM 4.0m profit in FY2024 but faces 3 winding-up petitions (1
  still pending). SYN-000545 is profitable on paper and is being wound up. A summary that starts with financials hides
  the risk, so **risks come first**, ordered by seriousness.
- **Case counts mislead.** 40 of the 72 court cases are against the company and 32 are brought by it. SYN-000267 has 5
  cases and is the plaintiff in every one. A summary must **say which side the company is on**.
- **The accounts are old.** Every company's latest accounts end in 2024, 12 to 21 months before the record date (31 Dec
  2025), and several companies had new cases or new directors in 2025. A summary must **state the age of the figures**.
- **Data is missing in different ways.** 3 companies have no accounts, 1 has a gap year, and 2 years are audited with a
  disclaimer of opinion (unverified figures). A summary must **say what is missing and never fill the gap**.
- **Trends beat single numbers.** All 11 companies with a loss in their latest year lost money in every year filed.
  Direction over the years tells the analyst more than one figure.
- **Some "risks" are normal here.** 42 of 50 companies have a shareholder above 50%, so ownership concentration alone is
  not flagged.

**The definition.** A good summary:
1. opens with a **verdict** on a 4-label scale: *Proceed*, *Review closely*, *Red flags*, or *Insufficient
   information*. The last is separate from Red flags on purpose: "we found a problem" and "we can't tell" call for
   different actions (investigate vs. request the accounts);
2. lists **key risks first**, most serious first, with year, amount and status;
3. then gives the business, the financial **trend**, ownership changes, and litigation **by role**;
4. uses **only facts in the record**, states the **age of the accounts** and any **gaps**;
5. stays **short** (100 to 180 words; a clean company shorter) and says plainly when nothing serious was found;
6. gives **no advice beyond triage**.

The full spec, with the evidence behind each rule and the scoring rubric, is in `eval/spec.md`. Each rule is tied to a
measurement, so section 3 tests exactly this definition.

**Trade-offs I chose.** Completeness was traded for speed: the summary leaves out most ratios, since the full record is
one scroll away. A verdict is included because it is the first thing the reader wants, but it is limited to triage
labels rather than a recommendation, because the summary is read before the review, not instead of it.

## 2. What you built

A small Python pipeline (`src/`) that writes one summary per company, plus an evaluation harness that scores every
version the same way. Everything runs with `uv run`. Every LLM response is cached in `runs/cache/`, so reruns are
free and repeatable.

```
companies.jsonl ──> facts.py ──> fact sheet ──> prompts.py + LLM ──> summaries/<version>.jsonl
                    (Python:      (red flags     (gpt-oss-120b)              │
                    trends,       first, then                                ▼
                    totals,       profile,                  evaluate.py       (automatic checks)
                    flags)        financials,               judge.py          (LLM judge vs gold set)
                                  ownership,                manual_review.md  (me, checking both)
                                  litigation)
```

**The key design choice: Python does the facts, the LLM does the writing.** Given 2,000 tokens of raw JSON, the LLM
miscounted cases, mixed up plaintiff and defendant, and buried the worst risk (see v1 below). So `src/facts.py` first
turns each record into a short *fact sheet*, using fixed rules:

- **Computed figures:** multi-year trends, revenue change, net margin, account age in months, pending-claim totals
  and borrowing growth. Numbers are pre-formatted (RM 4.01m, RM 355.9k) so the model can copy them rather than
  compute them.
- **Rule-based red flags in order of severity:**
  - winding-up status and winding-up petitions
  - going-concern or disclaimer audit opinions, and no accounts on record
  - negative equity and persistent losses
  - judgments against the company and pending cases against it
  - negative cash flow, liquidity below 1 and debt service below 1
  - falling revenue and missing years

  They are listed most serious first, so code decides the order of risks in the summary, not the model.
- **"Other points to note", kept apart from red flags:** 2025 director or name changes, a company shareholder and
  sharp borrowing growth. These are context, not alarms.
- **Litigation by role and status** (v3): open against the company, decided against it, closed, and brought by it.

The prompt (`src/prompts.py`) then gives the model the section 1 spec as rules and a fixed Markdown template:
verdict line, key risks, business, financials (with the account age), ownership & control, litigation.

**Models and limits:**
- **Provider:** Groq free tier.
- **Generator:** `openai/gpt-oss-120b`, reasoning effort low, temperature 0.2.
- **Judge:** `qwen/qwen3.8-27b`, temperature 0, JSON output. I chose a different model family so the judge doesn't
  share the generator's habits. My first choice, Llama 3.3 70B, was no longer available.
- **Limits:** 8,000 tokens/minute and 1,000 requests/day per model. The judge model also has a 200,000 tokens/day
  limit, which I didn't plan for (see section 3).
- **Handling:** `src/llm.py` retries on rate limits with capped waits and a request timeout.

**Sample.** I used 13 of the 50 companies (`eval/sample.md`). Rules in `src/explore.py` picked them so that every kind
of risk in the data appears at least once: winding-up status, petitions, judgments, going concern, disclaimer,
missing accounts, a gap year, negative equity, losses, plaintiff-only litigation, a corporate owner and 2025 renames.
I added 2 clean companies to test for false alarms. With 13 I could read every summary by hand, which mattered more to
me than a larger sample I could only score automatically.

**Three versions, each built to fix what the previous one got wrong:**

| Version | What changed | Why |
|---|---|---|
| `v1_baseline` | Raw JSON plus a one-line instruction | Shows what you get without designing anything; it's the comparison point |
| `v2_factsheet` | Fact sheet, the spec as rules, and the template | v1 averaged 431 words, never gave a verdict or the account age, miscounted cases, and listed SYN-000267's own lawsuits as a red flag |
| `v3_grouped` | Litigation grouped by status; key risks only from the red-flag list; no claims about what the record doesn't cover; tighter length | v2 called a dismissed case "pending" and a judgment "pending", made one unsupported comparison ("current ratio stayed above 2.0") and ran over length |

Example: the start of v3's summary for SYN-000286, the company in the brief's viewer mock-up.

> **Verdict: Red flags**: winding‑up petition and judgment against the company, plus missing FY2023 accounts.
>
> **Key risks**
> - Winding‑up petition filed 2022‑09‑15, claim RM 355.9k (pending).
> - Judgment entered 2024‑10‑06 for debt recovery, claim RM 97.6k.
> - Other pending claim (tenancy dispute) RM 110.6k.
> - Accounts missing for FY2023.

Tokens used for the 13 summaries: v1 37.7k, v2 24.6k, v3 27.3k. The fact sheet is smaller than the raw record, so
the better versions are also cheaper.

## 3. How you know whether it's good

I used three layers, because each one catches different things and none is reliable on its own. Each rule in the spec
maps to a measurement (`eval/spec.md`, table at the end).

**1. A gold set** (`eval/gold.md`). For each of the 13 companies it gives:
- the right verdict;
- what the summary *must* mention;
- what it *should* mention;
- what it *must not* claim.

I wrote it from the raw record, not from my rule-based flags, so the evaluation isn't rules checking rules. Caveat:
an AI assistant drafted it and I reviewed it. No vetting analyst wrote it, so it may share blind spots with the
models it judges.

**2. Automatic checks** (`src/evaluate.py`, no LLM):
- the verdict compared with the gold set;
- a *hard fail* when a red-flag company is called Proceed, and a *false alarm* when a clean company isn't;
- red-flag recall, and whether each flag appears in the first third of the summary;
- every number in the summary checked against values derivable from the record, with a rounding tolerance;
- case counts;
- whether the account age and case role are stated and all sections are present;
- word limits.

**3. An LLM judge** (`src/judge.py`). It gets the raw record, the fact sheet, the gold items and the summary. It
marks each must-mention item yes, partly or no, lists must-not-claim breaches and factual errors, and scores 6 rubric
dimensions from 1 to 5.

**Then I checked the checkers** (`eval/manual_review.md`), because a metric I haven't validated is just a number:

- **The number check is a screen, not a verdict.** The first version had 27% precision (3 of its 11 flags were real).
  After I fixed the parser, 3 of its 6 flags on v1 were real (50%), so every flag gets a human look. It can't catch
  a wrong *status* or a wrong *direction* ("turned negative").
- **The judge needs the raw record.** In its first run it saw only the fact sheet, treated correct figures from the
  raw record as errors, and gave v1 49 "errors". With the raw record, v1 had 10.
- **The judge's must-not-claim calls are unreliable.** On v2, 4 of its 5 factual errors were correct, but only 1 of
  its 4 must-not-claim calls. It caught 4 of the 6 errors I found by reading. So I count a judge-reported error only
  after checking it, and I don't use its must-not-claim count without a human check.

**Results** for the 13 companies (full tables in `eval/results.md`):

| Measure | v1 | v2 | v3 |
|---|---|---|---|
| Verdict matches gold | 0/13 | 13/13 | 13/13 |
| Hard fails / false alarms | 0 / 3 | 0 / 0 | 0 / 0 |
| Red flags mentioned | 91% | 100% | 100% |
| Red flags in the first third | 15% | 88% | 85% |
| Account age stated | 2/13 | 13/13 | 13/13 |
| Mean words (within 180) | 431 (0/13) | 172 (8/13) | 140 (11/13) |
| Factual errors | 10 (judge) | 6 (checked by hand) | 4: 2 real, 2 minor (by hand) |
| Must-mention coverage | 88% (judge) | 87% (judge) | 82% full + 14% partly (by hand) |

v1's 0/13 means it never used one of the agreed verdict labels, not that its judgement was always wrong.

**How I read this:**
- **v2 is the big step.** The fact-sheet design fixes the verdict, the order of risks, the account age and the length.
- **v3 fixes all of v2's known errors:** wrong case statuses, plaintiff cases listed as risks, and the false
  comparison.
- **v3 still has two real errors, both new and with the same cause:** the model doing its own arithmetic or rewording
  a figure.
  - SYN-000545: it says "four open breach-of-contract cases, RM 2.46m". There are 3 breach-of-contract cases and 1 debt
    recovery, totalling RM 2.50m.
  - SYN-000029: it says "operating cash flow turned negative", when only free cash flow did.
- **Other v3 weaknesses:** it drops the cases a company brought itself, and clean-company summaries run over 120 words
  because it lists every director.

**What I couldn't do, and why:**
- **No judge run on v3.** The two earlier judge runs used up the judge model's 200,000 tokens/day, a limit I hadn't
  planned for. Instead I reviewed all 13 v3 summaries by hand with the same questions the judge answers, so the v3
  column is a human score, not a judge score. The judge can run once the tokens reset
  (`uv run python -u src/judge.py v3_grouped`); the one company already judged is cached.
- **One skipped v2 judgment.** The judge call for SYN-001569 kept hanging, so I skipped it.
- **A bug in my own code.** Adding grouped litigation dropped the litigation red flags, and v3's first run called
  SYN-001389, a company facing 3 winding-up petitions, "Proceed". The hard-fail check flagged it at once. The buggy
  output is kept in `runs/`.

**Is it good enough to use?**
- **For triage on this sample, yes:**
  - every verdict matched the gold set;
  - no red-flag company was called Proceed and no clean one was flagged;
  - every red flag was mentioned.

  The remaining errors are in secondary detail, and the full record sits right below the summary.
- **Not yet unsupervised on all 50:**
  - the sample is 13 companies;
  - the gold set isn't from a real analyst;
  - 2 of the 13 summaries still contain a wrong figure.

## 4. What you'd do next, and how you'd keep improving it

**Next, in order:**

1. **Stop the model doing arithmetic.** This fixes both real v3 errors. Put every total the summary might need in the
   fact sheet: open claims by case type, totals per group, the pending total in one place. Then tell the model to
   quote them and never add them up.
2. **Make the v4 prompt fixes the v3 review found:**
   - in ownership, give only the largest shareholder, company shareholders and 2025 changes. This cuts about 30 words
     and should bring clean companies under 120;
   - always state the cases a company brought itself, labelled "not a risk";
   - write "free cash flow" or "operating cash flow" explicitly.
3. **Add automatic checks for the errors that slipped through:**
   - compare the sign of every cash-flow or profit claim with the record (to catch "turned negative");
   - check that case types and counts match the record;
   - flag a summary that gives two different totals for the same thing.
4. **Run the judge on v3 and v4** when tokens allow, and check its calls by hand again.
5. **Run the best version on all 50** and read the 37 unseen summaries for new kinds of error. The sample covers
   every risk type, but not every combination.

**How I'd keep improving it once real analysts use it:**

- **Get a real gold set.** Have 2 analysts label verdicts and must-mention items for 30 or more companies, and
  measure how often they agree with each other. That agreement is the ceiling for any metric, and their labels would
  replace my AI-drafted gold set.
- **Measure what matters in use:**
  - whether the analyst opened the full record, and how long they spent;
  - whether the verdict matched their final decision.

  A missed red flag (a company the summary called Proceed and the team went ahead with) is the costliest error, so I
  would track it separately and review every case.
- **Treat the checks as a regression suite.** Every error found becomes a test case: a company and a claim that must
  not appear. Any change to the prompt, the model or `facts.py` must pass all of them before it ships. It's cheap,
  and it's how the v3 bug was caught.
- **Calibrate the judge before scaling it up.** Keep a human-scored set (started in `eval/manual_review.md`
  section 3), measure how well the judge agrees on each dimension, and use only the dimensions where it does.
- **Re-tune the red-flag rules with the team.** The severity order and thresholds (for example, debt service below 1)
  are my judgement. Analysts should set them, since they decide what "serious" means.

**What's left:**
- the v3 judge run;
- a v4;
- the full 50-company run;
- my own rubric scores for checking the judge (the table in `eval/manual_review.md` section 3 is still empty);
- a gold set from someone who does this job.

## Tools and models used

- **LLM provider:** Groq free tier. Generator `openai/gpt-oss-120b`; judge `qwen/qwen3.8-27b`.
- **Python:** 3.14 with `uv`; libraries `groq`, `python-dotenv` and `pandas`.
- **AI tools:** Claude Code helped write the profiling script and the pipeline and evaluation code, drafted the gold
  set and the spec (reviewed and edited by me), and helped draft this document. My working notes and decisions are in
  `NOTES.md`.
