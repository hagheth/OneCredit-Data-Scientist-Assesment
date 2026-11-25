# What a good summary is: spec and rubric

This is the target every version of the system is built and scored against. Each rule below comes from something in
the data (`eval/data_profile.md`) or from reading the sample companies (`eval/gold.md`).

## 1. Reader and decision

- **Reader:** an analyst on a team that vets companies before choosing them as suppliers or project partners.
- **Decision the summary supports:** *is this company worth a closer look, and what should I look at first?* It is a
  triage step, not the final decision. The full record is right below the summary in the viewer.
- **So the summary must:** lead with the decision, surface every serious risk, be readable in under a minute, and never
  be wrong about a fact. A missed red flag (approving a failing supplier) and a false alarm (rejecting a fine one) both
  cost the team, so both are errors.

## 2. Format

Markdown, in this order. Target **100 to 180 words**; hard limit **220**. A clean company should be shorter.

```markdown
**Verdict: <Proceed | Review closely | Red flags | Insufficient information>**: <one sentence: the main reason>

**Key risks**
- <most serious first; each with year, amount in RM, and status where relevant>
- <"No significant risks found in the record." if none>

**Business:** <what it does>, <industry>, incorporated <year> (<age> years), status <status>.

**Financials** (<years available>; latest year ended <date>, <N> months before the record date):
<revenue trend, profit trend, cash flow / debt in 1 to 3 short points; audit opinions>

**Ownership & control:** <largest shareholder and %, corporate shareholders, director or name changes since 2024>

**Litigation:** <N cases: X as defendant, Y as plaintiff; pending as defendant and RM total; winding-up petitions>
```

## 3. Rules

| # | Rule | Why (evidence) |
|---|---|---|
| R1 | **Verdict first**, using the 4-label scale in `eval/gold.md`. | The reader's first question is "look closer or not?". |
| R2 | **Red flags first**, ordered by seriousness: Winding-up status → winding-up petitions → going-concern or disclaimer audit opinions → negative equity → repeated or worsening losses → pending claims as defendant → missing accounts or years. | SYN-000545 and SYN-001389 have strong profits but serious legal risk; listing financials first would hide it. |
| R3 | **Only facts from the record.** Every number, date and name must trace back to it. No guesses about causes, no outside knowledge, no links between companies that the record does not state. | A vetting decision based on an invented fact is worse than no summary. SYN-000451 / SYN-001203 have similar names but no stated link. |
| R4 | **Say whose side each case is on.** Defendant cases are risk; plaintiff cases are mentioned neutrally. Never report a bare case count. | 40 of 72 cases are as defendant, 32 as plaintiff. SYN-000267 has 5 cases, all as plaintiff. |
| R5 | **Show trends, not one year.** Give the direction across the years available (e.g. "losses widening: -RM 4.2m → -RM 7.5m"). | Every company with a loss in its latest year lost money in every year filed: the pattern matters more than one figure. |
| R6 | **State the age of the accounts.** Latest year-end date and how many months before 31 Dec 2025. Do not describe the company's *current* health from those figures without saying they are old. | All latest accounts end in 2024 (12 to 21 months old); SYN-000545's healthy FY2024 (Mar) accounts predate its 2025 cases. |
| R7 | **Say what is missing.** No accounts, a missing year, unverified (disclaimed) figures. Never fill a gap with numbers. | 3 companies have no accounts; SYN-000286 has no FY2023; 2 years are disclaimed. |
| R8 | **Don't invent risk for clean companies.** If nothing serious is found, say so plainly and keep it short. | Clean controls SYN-000029 and SYN-000282. |
| R9 | **Plain numbers.** RM with sensible rounding (RM 4.0m, RM 355.9k); ratios as % or x; people by role name only (Director 1). | The reader scans; precise-looking noise slows them down. |
| R10 | **No advice beyond triage.** No "approve this supplier" or credit recommendations; the verdict is about whether to look closer. | The summary is read *before* the full review, not instead of it. |

Not treated as a flag on its own: a single shareholder above 50% (42 of 50 companies have one, so it is normal here),
the registered state differing from where the business operates.

## 4. Scoring rubric (used by me and by the LLM judge)

**Hard fails.** A summary that has any of these fails, whatever its other scores:
- a number, date or fact that is not in the record (hallucination);
- any "Must not claim" item from `eval/gold.md`;
- a wrong verdict on a Red flags company (calling it Proceed).

**Scores** (1 to 5 each):

| Dimension | 5 | 3 | 1 |
|---|---|---|---|
| **Faithfulness** | every fact correct and traceable | one minor slip (rounding, wrong year) | invented or wrong material fact |
| **Risk coverage** | every "Must mention" item present | most present, one important one missing | the main risk missing |
| **Verdict** | matches gold | one step off (e.g. Review closely vs Red flags) | two or more steps off, or no verdict |
| **Prioritisation** | most serious risk first, flags before background | risks present but buried | risk hidden behind positives |
| **Concision & format** | follows the template, within word limit, easy to scan | some padding or a missing section | long, unstructured, or over the hard limit |
| **Honesty about gaps** | account age, missing years and unverified figures all stated | some stated | gaps ignored or filled with guesses |

## 5. How each rule is measured

| Rule | Measure | How | Step |
|---|---|---|---|
| R1 | Verdict accuracy | parse the verdict label, compare with gold | automatic |
| R2 | Flag position | rule-based flags found in "Key risks" vs only later | automatic |
| R3 | Unsupported-number rate | extract every number from the summary, match against the record (with rounding tolerance) | automatic |
| R3, R4 | "Must not claim" violations | judge model + my check on a subset | LLM judge + manual |
| R4 | Role stated for cases | litigation line mentions defendant/plaintiff when there are cases | automatic |
| R1-R8 | Gold recall | share of "Must mention" items covered | LLM judge + manual |
| R6, R7 | Gap honesty | account age stated; missing data stated where gold says so | automatic |
| R8 | False alarms on clean controls | verdict and "Key risks" for SYN-000029 / SYN-000282 | automatic + manual |
| R9, format | Format compliance | sections present, word count | automatic |
| All | Rubric scores | judge model on every summary; me on ~5 to check the judge | LLM judge + manual |
