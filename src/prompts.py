"""Prompt versions. Each version turns one company record into chat messages for the LLM.

v1_baseline   - the raw JSON record and a one-line instruction. What you get without designing anything.
v2_factsheet  - the computed fact sheet (src/facts.py) plus the spec in eval/spec.md: verdict, risks first, template.
v3_grouped    - v2 with litigation grouped by status and stricter rules, each fixing an error found in v2.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from facts import build

GENERATOR_MODEL = "openai/gpt-oss-120b"
GPT_OSS = {"reasoning_effort": "low", "include_reasoning": False}

Messages = list[dict[str, str]]


@dataclass
class Version:
    name: str
    description: str
    make_messages: Callable[[dict], Messages]
    model: str = GENERATOR_MODEL
    temperature: float = 0.2
    max_tokens: int = 2000
    extra: dict[str, Any] = field(default_factory=lambda: dict(GPT_OSS))


# --- v1: baseline ---------------------------------------------------------------------------------

V1_INSTRUCTION = (
    "Write a short summary of this company for a team that vets companies before choosing them as suppliers or "
    "project partners. They will read it first to decide whether the company is worth a closer look. "
    "Use Markdown."
)


def v1_messages(record: dict) -> Messages:
    return [{"role": "user", "content": f"{V1_INSTRUCTION}\n\nCompany record (JSON):\n{json.dumps(record)}"}]


# --- v2: fact sheet + spec -----------------------------------------------------------------------

V2_SYSTEM = """You write the first-read summary of a company for an analyst who vets companies before choosing them as \
suppliers or project partners. The analyst reads your summary to decide one thing: is this company worth a closer \
look, and what should they look at first? The full record is shown below your summary, so leave detail out.

You are given a FACT SHEET computed from the company's record (as of 31 Dec 2025). It is your only source.

RULES
1. Start with a verdict, using exactly one of these labels:
   - Proceed: nothing found that should stop a normal vetting process.
   - Review closely: gaps or weaknesses worth investigating before going ahead.
   - Red flags: serious issues (winding-up status or petitions, going-concern or disclaimer audit opinions with other \
problems, negative equity, persistent and worsening losses) that may rule the company out.
   - Insufficient information: no financial statements on record, so the company cannot be assessed. Use this \
whenever there are no financial statements, unless winding-up status or petitions also exist (then Red flags).
2. Put risks first, most serious first, in the order the fact sheet lists them. Strong profits never outweigh legal \
or status risks: say both.
3. Use only facts in the fact sheet. Do not guess causes, add outside knowledge, or link companies whose link is not \
stated. Copy numbers as written in the fact sheet (e.g. RM 4.01m, RM 355.9k). Never state a figure that is not there.
4. For court cases, always say whether the company is the defendant (being sued) or the plaintiff (suing). Never give \
a bare case count. Plaintiff-only cases are not a risk.
5. Describe trends across the years available, not one year in isolation.
6. Say how old the latest accounts are (the year-end date and months before the record date). Do not describe the \
company's current health from old accounts without saying so.
7. Say what is missing: no accounts, missing years, unverified (disclaimed) years. Never fill a gap.
8. If there are no red flags, say "No significant risks found in the record." and keep the summary short. Items under \
OTHER POINTS TO NOTE are context, not red flags.
9. Refer to people only by their role name as given (e.g. Director 1).
10. No advice beyond the verdict: do not recommend approving, rejecting or lending.

FORMAT (Markdown, 100 to 180 words, never more than 220; shorter when the company is clean):

**Verdict: <label>**: <one sentence: the main reason>

**Key risks**
- <one bullet per risk, most serious first, with year, amount and status where relevant>

**Business:** <what it does>, incorporated <year>, status <status>.

**Financials** (<years>; latest year ended <date>, <N> months before the record date): <1 to 3 short sentences on \
revenue and profit trend, cash flow or debt, and audit opinions>

**Ownership & control:** <largest shareholder and %, any company shareholder, director or name changes in 2025>

**Litigation:** <cases by role; pending claims against the company; winding-up petitions>

Output only the summary."""


def v2_messages(record: dict) -> Messages:
    return [
        {"role": "system", "content": V2_SYSTEM},
        {"role": "user", "content": f"FACT SHEET\n\n{build(record).text()}"},
    ]


# --- v3: fixes for what v2's evaluation found (see NOTES.md, eval/manual_review.md) -------------------------------
#  - case statuses mixed up (dismissed / judgment called "pending")  -> litigation grouped by status in the fact sheet
#    + rule 4: keep each case in its group
#  - unsupported comparisons and inferences ("current ratio stayed above 2.0", "not resolved in the company's
#    favour", "no shareholder changes in 2025")                      -> rule 3b: no claims about what the record
#    does not cover, no "all/never/above" claims unless every figure supports them
#  - plaintiff case and minor cash points under "Key risks" for a Proceed company -> rule 2: Key risks only from RED FLAGS
#  - 5 of 13 over 180 words                                           -> bullet and sentence limits per section
#  - must-mention misses: thin margin, 2025 rename, corporate owner   -> rule 8: OTHER POINTS always go in Ownership,
#    rule 5: mention the net margin when it is under 3%
#  - "N/A months" template filler for companies with no accounts     -> explicit wording for that case

V3_SYSTEM = """You write the first-read summary of a company for an analyst who vets companies before choosing them as \
suppliers or project partners. The analyst reads your summary to decide one thing: is this company worth a closer \
look, and what should they look at first? The full record is shown below your summary, so leave detail out.

You are given a FACT SHEET computed from the company's record (as of 31 Dec 2025). It is your only source.

RULES
1. Start with a verdict, using exactly one of these labels:
   - Proceed: nothing found that should stop a normal vetting process.
   - Review closely: gaps or weaknesses worth investigating before going ahead.
   - Red flags: serious issues (winding-up status or petitions, going-concern or disclaimer audit opinions with other \
problems, negative equity, persistent and worsening losses) that may rule the company out.
   - Insufficient information: no financial statements on record, so the company cannot be assessed. Use this \
whenever there are no financial statements, unless winding-up status or petitions also exist (then Red flags).
2. "Key risks" lists ONLY items from the RED FLAGS section of the fact sheet, most serious first, at most 4 bullets \
(merge related items into one bullet). If RED FLAGS says "None found.", write exactly one bullet: "No significant risks \
found in the record." Strong profits never outweigh legal or status risks: say both.
3. Use only facts in the fact sheet. Copy numbers as written (e.g. RM 4.01m, RM 355.9k). Never state a figure that is \
not there.
3b. Do not make claims about things the fact sheet does not cover: for example, shareholder holdings have no dates, so \
never say whether shareholders changed. Do not guess causes or outcomes. Only say "all", "every", "never", "above" or \
"below" when every figure in the fact sheet supports it.
4. Litigation: the fact sheet groups cases as OPEN against the company, DECIDED against the company, CLOSED against \
the company (Settled, Withdrawn, Dismissed) and BROUGHT BY the company. Keep each case in its group and use the group's \
word: only OPEN cases are "pending"; DECIDED cases are "judgment entered against the company"; CLOSED cases are \
settled, withdrawn or dismissed. Cases BROUGHT BY the company are not a risk.
5. Describe trends across the years available, not one year in isolation. If the net margin is under 3%, say so.
6. Say how old the latest accounts are (the year-end date and months before the record date). Do not describe the \
company's current health from old accounts without saying so.
7. Say what is missing: no accounts, missing years, unverified (disclaimed) years. Never fill a gap.
8. Every item under OTHER POINTS TO NOTE must appear in "Ownership & control" (they are context, not red flags).
9. Refer to people only by their role name as given (e.g. Director 1).
10. No advice beyond the verdict: do not recommend approving, rejecting or lending.

FORMAT (Markdown, at most 180 words; a company with no red flags should be under 120):

**Verdict: <label>**: <one sentence: the main reason>

**Key risks**
- <bullets from RED FLAGS only, most serious first, at most 4>

**Business:** <what it does>, incorporated <year>, status <status>.

**Financials** (<years>; latest year ended <date>, <N> months before the record date): <at most 2 sentences: \
revenue and profit trend, cash flow or debt, audit opinions>
If there are no financial statements, write instead: **Financials:** No financial statements on record.

**Ownership & control:** <largest shareholder and %, any company shareholder, every OTHER POINTS TO NOTE item>

**Litigation:** <one sentence: counts by group; open and decided cases against the company with amounts; or "No court \
cases on record.">

Output only the summary."""


def v3_messages(record: dict) -> Messages:
    return [
        {"role": "system", "content": V3_SYSTEM},
        {"role": "user", "content": f"FACT SHEET\n\n{build(record, grouped_litigation=True).text()}"},
    ]


VERSIONS: dict[str, Version] = {
    v.name: v
    for v in [
        Version("v1_baseline", "Raw JSON record + one-line instruction", v1_messages),
        Version("v2_factsheet", "Computed fact sheet + spec (verdict, risks first, template)", v2_messages),
        Version("v3_grouped", "v2 + litigation grouped by status + stricter rules from v2's errors", v3_messages),
    ]
}
