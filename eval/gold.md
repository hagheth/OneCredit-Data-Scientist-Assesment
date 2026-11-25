# Gold set: what a good summary MUST say

**Provenance:** first draft written by an AI assistant (Claude Code) from the full records, then reviewed and edited by
me. Each decision was made from the raw record, not from the rule-based flags in `src/explore.py`, so that evaluation
does not just check rules against rules. 

**Decision scale**
- **Proceed:** nothing found that should stop a normal vetting process.
- **Review closely:** gaps or weaknesses an analyst should look into before going ahead.
- **Red flags:** serious issues (insolvency signals, winding-up, unreliable accounts plus losses) that may rule the company out.
- **Insufficient information:** the record is too thin to judge (no financial statements at all). Get the accounts
  before deciding. This is kept apart from Red flags on purpose: "we found a problem" and "we can't tell" call for
  different actions.

**Rules for every company**
- If it has financials: say how old the latest accounts are. The latest year ends in 2024 for every company (between
  31 Mar and 31 Dec 2024), so on the record date (31 Dec 2025) the newest figures are 12 to 21 months old. Anything
  that happened in 2025, such as new court cases or a change of directors, is not reflected in them.
- Amounts in RM, rounded sensibly (e.g. RM 4.0m). People only by role name (Director 1).
- Never invent a link between companies, a reason for a case, or a figure not in the record.

---

## SYN-000029 - Unity Global Trading Sdn. Bhd. (Retail)

- **Decision:** Proceed
- **Must mention:** profitable all 3 years but very thin net margin (about 2%, PAT about RM 0.10m on RM 5.35m revenue); revenue growing slowly (RM 5.13m to RM 5.35m); free cash flow negative in all 3 years; no court cases; clean audits.
- **Should mention:** 2 directors appointed in Nov 2025, one of them (Director 4) holds 58.25%, so the majority owner joined the board only recently.
- **Must not claim:** any litigation or audit issue; that it is loss-making.
- **Notes:** clean control. Debt service coverage about 1.0 is tight but not alarming.

## SYN-000067 - Jaya Prima Travel Sdn. Bhd. (Hospitality)

- **Decision:** Red flags
- **Must mention:** losses in all 3 years and getting worse (PAT -RM 4.24m, -RM 6.12m, -RM 7.52m); revenue falling (RM 49.5m to RM 43.3m); negative operating cash flow every year; equity down from RM 31.2m to RM 17.6m; current liabilities exceed current assets in FY2024; interest not covered by operating profit.
- **Should mention:** no court cases; long history (incorporated 1995).
- **Must not claim:** that it is profitable or recovering; any litigation.
- **Notes:** a pure financial-distress case with no legal flags. Tests whether a summary catches risk from the numbers alone.

## SYN-000217 - Teguh Bestari Learning Sdn. Bhd. (Education)

- **Decision:** Review closely
- **Must mention:** FY2023 audit opinion was a **disclaimer of opinion**, so the FY2023 figures cannot be relied on; FY2022 and FY2024 unqualified; revenue growing fast (RM 2.98m to RM 5.61m) with profits rising (PAT RM 0.39m in FY2024); leverage rising (liabilities to equity about 1.6 to 2.6).
- **Should mention:** no court cases; stable 2-person ownership and board since the 1990s; current liabilities slightly exceed current assets in FY2024.
- **Must not claim:** that all audits were clean.
- **Notes:** good-looking financials with an unreliable year. Tests whether the audit issue gets buried.

## SYN-000267 - Global Everbright Store Sdn. Bhd. (Retail)

- **Decision:** Proceed
- **Must mention:** changed its name in June 2025 (formerly Sinar Industries Sdn. Bhd.); 5 court cases, all as **plaintiff** (the company is suing, not being sued), 1 still pending (RM 177k); profitable all 3 years (PAT RM 0.47m on RM 19.4m revenue); clean audits.
- **Should mention:** Director 1 holds 89.67% and became Managing Director in Jan 2024.
- **Must not claim:** that the company is being sued, or that the litigation is a risk to its solvency.
- **Notes:** tests whether a summary tells plaintiff from defendant. Counting cases alone would make it look risky.

## SYN-000282 - Delima Pacific Academy Sdn. Bhd. (Education)

- **Decision:** Proceed
- **Must mention:** steady growth (revenue RM 25.1m to RM 27.6m) and profitable all 3 years (PAT RM 1.87m in FY2024); strong cash generation (positive free cash flow every year); comfortable interest cover (about 8x); no court cases; clean audits.
- **Must not claim:** any risk flag that is not in the record.
- **Notes:** clean control. A good summary is short here.

## SYN-000286 - Cahaya Seri Catering Sdn. Bhd. (Food & Beverage)

- **Decision:** Red flags
- **Must mention:** a **winding-up petition** against it has been **pending since Sept 2022** (RM 355.9k); 6 cases, all as defendant, including a debt-recovery judgment against it (RM 97.6k, 2024) and a pending tenancy dispute (RM 110.6k); **FY2023 accounts are missing** (only FY2022 and FY2024).
- **Should mention:** small and modestly profitable (revenue RM 4.4m, PAT RM 0.18m); Director 1 owns 98.86%.
- **Must not claim:** that it has 3 years of accounts; that the winding-up petition is resolved.
- **Notes:** the profit looks fine; the risk is all in litigation and the missing year.

## SYN-000302 - Global Pacific Perunding Sdn. Bhd. (Professional Services)

- **Decision:** Insufficient information
- **Must mention:** **no financial statements on record**, so its financial health cannot be assessed; no court cases.
- **Should mention:** incorporated 2014 (about 12 years old), so missing accounts are unusual; Director 2, appointed May 2024, holds the majority (58.7%).
- **Must not claim:** any financial figure, trend or ratio.
- **Notes:** tests whether the model makes up numbers when there are none.

## SYN-000451 - Mutiara Delima Bakery Sdn. Bhd. (Food & Beverage)

- **Decision:** Red flags
- **Must mention:** **negative equity** in FY2024 (liabilities exceed assets); losses in all 3 years and growing (PAT -RM 0.18m to -RM 0.28m); revenue falling (RM 2.32m to RM 2.08m); negative operating cash flow every year; **name changed in Nov 2025** (formerly Gemilang Ventures Sdn. Bhd.).
- **Should mention:** 2 cases, neither open (a claim against it was dismissed in 2025; one it brought was settled).
- **Must not claim:** that the litigation is a risk; a link to Gemilang Holdings (owner of SYN-001203). The names are similar, but the record shows no link.
- **Notes:** technically insolvent on the balance sheet, with a very recent rename.

## SYN-000545 - Cahaya Golden Systems Sdn. Bhd. (Technology)

- **Decision:** Red flags
- **Must mention:** **status is Winding up**; a winding-up petition ended in **judgment against it** (2023); **4 pending claims** as defendant totalling about **RM 2.5m**; FY2022 audit had **material uncertainty on going concern**.
- **Should mention:** the accounts look healthy (profitable, PAT RM 1.28m in FY2024; positive cash flow), but they end March 2024, before the 2025 cases; 2 of 3 directors appointed in 2025, including Director 2, who holds 52.17%.
- **Must not claim:** that it is a healthy or active going concern because profits are positive.
- **Notes:** the key "financials vs status" conflict. The winding-up status must lead the summary.

## SYN-001203 - Pacific Seri Freight Sdn. Bhd. (Logistics)

- **Decision:** Insufficient information
- **Must mention:** **no financial statements on record**; **70% owned by a company**, Gemilang Holdings Sdn. Bhd. (Malaysia), so the parent's standing matters.
- **Should mention:** long-established (incorporated 2007), share capital RM 5m; only 1 court case, as plaintiff, settled.
- **Must not claim:** any financial figure; anything about the parent beyond its name, country and stake.
- **Notes:** tests whether corporate ownership is surfaced.

## SYN-001212 - Sinar Sinar Pelancongan Sdn. Bhd. (Hospitality)

- **Decision:** Red flags
- **Must mention:** **status is Winding up**; **2 winding-up petitions ended in judgment against it** (2021, RM 9.47m; 2022, RM 300.8k); 2 employment claims still pending (about RM 479k in total); revenue and profit falling steadily (revenue RM 6.97m to RM 4.51m; PAT RM 0.41m to RM 0.04m).
- **Should mention:** a tenancy judgment against it (2024, RM 243.3k); debt service coverage below 1 in FY2024; balance sheet itself has low debt.
- **Must not claim:** that low leverage makes it safe.
- **Notes:** a clear decline story plus the formal status.

## SYN-001389 - Everbright Prima Homestay Sdn. Bhd. (Hospitality)

- **Decision:** Red flags
- **Must mention:** **3 winding-up petitions** against it since 2023: 1 settled (2023), **1 still pending** (filed Feb 2024), 1 filed Nov 2025 and withdrawn; 2 pending tenancy claims (RM 681.6k in total); all 8 cases as defendant.
- **Should mention:** strong growth and profits (revenue RM 30.8m to RM 59.1m; PAT RM 4.01m in FY2024); borrowings nearly doubled (RM 13.1m to RM 25.2m) with leverage rising; new Managing Director appointed Jan 2025.
- **Must not claim:** that strong profits rule out a credit risk.
- **Notes:** repeated winding-up petitions while profitable suggests late payment to creditors. Tests whether good numbers hide legal flags.

## SYN-001569 - Unity Maju Makanan Sdn. Bhd. (Food & Beverage)

- **Decision:** Review closely
- **Must mention:** FY2022 audit was a **disclaimer of opinion**; profitable but thin (PAT about RM 0.2m on RM 6.3m revenue); debt service coverage **below 1** in FY2024 (0.73), so operating cash may not cover debt payments.
- **Should mention:** no court cases; stable board and ownership; FY2023 and FY2024 audits clean.
- **Must not claim:** that all audits were clean; any litigation.
- **Notes:** an older audit issue and tight debt service; milder than SYN-000217.

---

## Decision counts

| Decision | Companies |
|---|---|
| Proceed | 3 (SYN-000029, SYN-000267, SYN-000282) |
| Review closely | 2 (SYN-000217, SYN-001569) |
| Red flags | 6 (SYN-000067, SYN-000286, SYN-000451, SYN-000545, SYN-001212, SYN-001389) |
| Insufficient information | 2 (SYN-000302, SYN-001203) |
