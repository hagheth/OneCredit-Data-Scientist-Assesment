"""Turn one company record into a compact fact sheet with rule-based red flags. No LLM.

The fact sheet does the arithmetic (trends, totals, account age) in code, so the LLM only has to write.
It is also the reference the evaluation checks numbers against.
"""

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "companies.jsonl"
RECORD_DATE = date(2025, 12, 31)
RECENT_FROM = "2025-01-01"  # "recent" changes = during the record year

# Flag severity: lower number = more serious. Order follows rule R2 in eval/spec.md.
SEVERITY = {
    "winding_up_status": 1,
    "winding_up_petition": 2,
    "going_concern": 3,
    "audit_disclaimer": 3,
    "no_financials": 4,
    "negative_equity": 4,
    "losses": 5,
    "judgment_against": 6,
    "pending_defendant": 6,
    "cash_flow": 7,
    "liquidity": 7,
    "debt_service": 7,
    "revenue_decline": 8,
    "missing_year": 8,
    "borrowing_growth": 9,
    "recent_changes": 10,
    "corporate_owner": 10,
}
RED_FLAG_MAX = 8  # severity 9+ is context worth mentioning, not a red flag on its own


@dataclass
class Flag:
    code: str
    text: str

    @property
    def severity(self) -> int:
        return SEVERITY[self.code]


@dataclass
class FactSheet:
    registration_number: str
    company_name: str
    lines: list[str] = field(default_factory=list)  # the sheet, as text lines
    flags: list[Flag] = field(default_factory=list)
    numbers: set[float] = field(default_factory=set)  # every number shown, for the faithfulness check

    @property
    def red_flags(self) -> list[Flag]:
        return sorted((f for f in self.flags if f.severity <= RED_FLAG_MAX), key=lambda f: f.severity)

    @property
    def other_points(self) -> list[Flag]:
        return sorted((f for f in self.flags if f.severity > RED_FLAG_MAX), key=lambda f: f.severity)

    def text(self) -> str:
        red = [f"- {f.text}" for f in self.red_flags] or ["- None found."]
        other = [f"- {f.text}" for f in self.other_points] or ["- None."]
        return "\n".join(["RED FLAGS (most serious first):", *red, "",
                          "OTHER POINTS TO NOTE (not red flags on their own):", *other, "", *self.lines])


def rm(x: float) -> str:
    """Format a ringgit amount the way summaries should: RM 4.01m, RM 355.9k, RM 950."""
    sign = "-" if x < 0 else ""
    a = abs(x)
    if a >= 1_000_000:
        return f"{sign}RM {a / 1_000_000:.2f}m"
    if a >= 1_000:
        return f"{sign}RM {a / 1_000:.1f}k"
    return f"{sign}RM {a:,.0f}"


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def num(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def months_between(earlier: date, later: date) -> int:
    return (later.year - earlier.year) * 12 + later.month - earlier.month


def litigation_grouped(cases: list[dict]) -> list[str]:
    """Cases grouped by what they mean for the company (used from v3). v2 mixed up statuses when cases were listed
    by date only, e.g. calling a dismissed case 'pending'."""
    def line(c: dict) -> str:
        return f"  - {c['filedOn']}: {c['caseType']}, {c['court']}, claim {rm(c['claimAmount'])}"

    def section(title: str, sel: list[dict]) -> list[str]:
        sel = sorted(sel, key=lambda c: c["filedOn"], reverse=True)
        return [f"- {title}: {len(sel)}", *[line(c) for c in sel]] if sel else [f"- {title}: none"]

    d = [c for c in cases if c["role"] == "defendant"]
    p = [c for c in cases if c["role"] == "plaintiff"]
    out = [f"- {len(cases)} cases in total: {len(d)} against the company (defendant), {len(p)} brought by the company "
           "(plaintiff). Use the group names below exactly; do not move a case to another group."]
    out += section("OPEN against the company (status Pending)", [c for c in d if c["status"] == "Pending"])
    out += section("DECIDED against the company (status Judgment entered)", [c for c in d if c["status"] == "Judgment entered"])
    for status in ("Settled", "Withdrawn", "Dismissed"):
        out += section(f"CLOSED against the company: {status}", [c for c in d if c["status"] == status])
    if p:
        out.append(f"- BROUGHT BY the company (plaintiff, not a risk): {len(p)}")
        out += [f"  - {c['filedOn']}: {c['caseType']}, status {c['status']}, claim {rm(c['claimAmount'])}"
                for c in sorted(p, key=lambda c: c["filedOn"], reverse=True)]
    return out


def build(record: dict, grouped_litigation: bool = False) -> FactSheet:
    p, rel = record["profile"], record["relationships"]
    years = sorted(record["financials"]["years"], key=lambda y: y["financialYear"])
    cases = record["litigation"]["cases"]
    fs = FactSheet(record["registrationNumber"], p["companyName"])
    add, flag = fs.lines.append, fs.flags.append

    # --- Profile
    inc = date.fromisoformat(p["incorporationDate"])
    age = RECORD_DATE.year - inc.year - ((RECORD_DATE.month, RECORD_DATE.day) < (inc.month, inc.day))
    add("PROFILE")
    add(f"- Name: {p['companyName']} ({record['registrationNumber']})")
    add(f"- Status: {p['status']}")
    add(f"- Business: {p['natureOfBusiness']} | Industry: {p['industry']} | Registered state: {p['state']}")
    add(f"- Incorporated: {inc.isoformat()} ({age} years before the record date) | Share capital: {rm(p['shareCapital'])}")
    for fn in p["formerNames"]:
        add(f"- Former name: {fn['name']} (changed {fn['changedOn']})")
    if p["status"] != "Active":
        flag(Flag("winding_up_status", f"Company status is '{p['status']}'."))

    # --- Financials
    add("")
    add("FINANCIALS")
    if not years:
        add("- No financial statements on record. Do not state any financial figures.")
        flag(Flag("no_financials", "No financial statements on record, so financial health cannot be assessed."))
    else:
        latest = years[-1]
        fye = date.fromisoformat(latest["financialYearEnd"])
        age_m = months_between(fye, RECORD_DATE)
        fys = [y["financialYear"] for y in years]
        add(f"- Years available: {', '.join(f'FY{y}' for y in fys)}. Latest year ended {fye.isoformat()}, "
            f"{age_m} months before the record date (31 Dec 2025).")
        missing = [y for y in range(fys[0], fys[-1] + 1) if y not in fys]
        if missing:
            flag(Flag("missing_year", f"Accounts missing for {', '.join(f'FY{y}' for y in missing)}."))

        for y in years:
            s, r = y["statements"], y["ratiosAndMetrics"]
            cap, liq = r["capitalStructure"], r["liquidityAndCashFlow"]
            cur_ratio = s["currentAssets"] / s["currentLiabilities"] if s["currentLiabilities"] else None
            add(f"- FY{y['financialYear']} (ended {y['financialYearEnd']}; audit: {y['audit']['opinion']}): "
                f"revenue {rm(s['revenue'])}, profit after tax {rm(s['profitAfterTax'])} "
                f"(net margin {pct(r['profitability']['netProfitMargin'])}), "
                f"operating cash flow {rm(s['operatingCashFlow'])}, "
                f"free cash flow {'n/a' if liq['freeCashFlow'] is None else rm(liq['freeCashFlow'])}, "
                f"cash {rm(s['cash'])}, borrowings {rm(s['borrowings'])}, total equity {rm(s['totalEquity'])}, "
                f"current ratio {num(cur_ratio)}, debt service coverage {num(cap['debtServiceCoverageRatio'])}, "
                f"interest cover {num(cap['interestCoverageRatio'])}")
            fs.numbers.update(v for v in [s["revenue"], s["profitAfterTax"], s["operatingCashFlow"], liq["freeCashFlow"],
                                          s["cash"], s["borrowings"], s["totalEquity"]] if v is not None)
            opinion = y["audit"]["opinion"]
            if "going concern" in opinion.lower():
                flag(Flag("going_concern", f"FY{y['financialYear']} audit: material uncertainty on going concern."))
            elif "disclaimer" in opinion.lower():
                flag(Flag("audit_disclaimer",
                          f"FY{y['financialYear']} audit: disclaimer of opinion, so FY{y['financialYear']} figures are unverified."))

        first_s, last_s = years[0]["statements"], latest["statements"]
        if len(years) > 1:
            g = last_s["revenue"] / first_s["revenue"] - 1
            add(f"- Revenue FY{fys[0]} to FY{fys[-1]}: {rm(first_s['revenue'])} to {rm(last_s['revenue'])} ({g:+.1%}).")
            if g < -0.10:
                flag(Flag("revenue_decline", f"Revenue fell {abs(g):.0%} from FY{fys[0]} to FY{fys[-1]}."))
            b0, b1 = first_s["borrowings"], last_s["borrowings"]
            if b0 and b1 / b0 - 1 > 0.5:
                flag(Flag("borrowing_growth", f"Borrowings up {b1 / b0 - 1:.0%} ({rm(b0)} to {rm(b1)})."))

        pats = [y["statements"]["profitAfterTax"] for y in years]
        loss_years = [y["financialYear"] for y in years if y["statements"]["profitAfterTax"] < 0]
        if loss_years:
            trend = " to ".join(rm(x) for x in pats)
            worse = len(pats) > 1 and all(b < a for a, b in zip(pats, pats[1:], strict=False))
            what = "every year filed" if len(loss_years) == len(years) else ", ".join(f"FY{y}" for y in loss_years)
            flag(Flag("losses", f"Losses in {what} (profit after tax {trend}){', getting worse' if worse else ''}."))
        if last_s["totalEquity"] < 0:
            flag(Flag("negative_equity", f"Negative equity in FY{fys[-1]} ({rm(last_s['totalEquity'])}): liabilities exceed assets."))
        if all(y["statements"]["operatingCashFlow"] < 0 for y in years):
            flag(Flag("cash_flow", "Operating cash flow negative in every year filed."))
        if last_s["currentLiabilities"] and last_s["currentAssets"] < last_s["currentLiabilities"]:
            flag(Flag("liquidity", f"FY{fys[-1]}: current liabilities ({rm(last_s['currentLiabilities'])}) exceed "
                                   f"current assets ({rm(last_s['currentAssets'])})."))
        dscr = latest["ratiosAndMetrics"]["capitalStructure"]["debtServiceCoverageRatio"]
        if dscr is not None and dscr < 1:
            flag(Flag("debt_service", f"FY{fys[-1]} debt service coverage {dscr:.2f}: earnings do not cover debt payments."))

    # --- Ownership and control
    add("")
    add("OWNERSHIP AND CONTROL")
    holders = sorted(rel["shareholders"], key=lambda s: -s["percentage"])
    for s in holders:
        kind = (f"company, registered {s.get('registrationNumber') or 'n/a'}, incorporated in {s.get('incorporatedIn') or 'n/a'}"
                if s["type"] == "company" else "individual")
        add(f"- Shareholder: {s['name']} ({kind}) {s['percentage']}%")
    for d in sorted(rel["directors"], key=lambda d: d["appointedOn"]):
        add(f"- Director: {d['name']}, {d['designation']}, appointed {d['appointedOn']}")
    for s in holders:
        if s["type"] == "company":
            flag(Flag("corporate_owner", f"{s['percentage']}% owned by a company, {s['name']} "
                                         f"({s.get('incorporatedIn') or 'country n/a'}); the parent's standing matters."))
    recent = [d for d in rel["directors"] if d["appointedOn"] >= RECENT_FROM]
    renamed = [fn for fn in p["formerNames"] if fn["changedOn"] >= RECENT_FROM]
    if recent or renamed:
        bits = [f"{d['name']} ({d['designation']}) appointed {d['appointedOn']}" for d in recent]
        bits += [f"renamed from {fn['name']} on {fn['changedOn']}" for fn in renamed]
        flag(Flag("recent_changes", "Changes in 2025: " + "; ".join(bits) + "."))

    # --- Litigation
    add("")
    add("LITIGATION")
    if not cases:
        add("- No court cases on record.")
    elif grouped_litigation:
        fs.lines.extend(litigation_grouped(cases))
        fs.numbers.update(c["claimAmount"] for c in cases)
    else:
        n_def = sum(c["role"] == "defendant" for c in cases)
        add(f"- {len(cases)} cases: {n_def} with the company as defendant (being sued), "
            f"{len(cases) - n_def} as plaintiff (the company is suing).")
        for c in sorted(cases, key=lambda c: c["filedOn"], reverse=True):
            add(f"- {c['filedOn']}: {c['caseType']}, company is {c['role']}, {c['court']}, "
                f"status {c['status']}, claim {rm(c['claimAmount'])}")
            fs.numbers.add(c["claimAmount"])

    # Litigation red flags: raised for every layout. (Bug found in v3's first run: these lines sat inside the
    # date-ordered branch only, so grouped fact sheets had no litigation flags. Caught by the flag-recall check.)
    if cases:
        wups = [c for c in cases if c["caseType"] == "Winding-up petition"]
        if wups:
            detail = "; ".join(f"filed {c['filedOn']}, {c['status']}, {rm(c['claimAmount'])}" for c in wups)
            flag(Flag("winding_up_petition", f"{len(wups)} winding-up petition(s) against the company: {detail}."))
        judg = [c for c in cases if c["role"] == "defendant" and c["status"] == "Judgment entered"
                and c["caseType"] != "Winding-up petition"]
        if judg:
            detail = "; ".join(f"{c['caseType']} {c['filedOn'][:4]}, {rm(c['claimAmount'])}" for c in judg)
            flag(Flag("judgment_against", f"Judgment entered against the company: {detail}."))
        pend = [c for c in cases if c["role"] == "defendant" and c["status"] == "Pending"
                and c["caseType"] != "Winding-up petition"]
        if pend:
            total = sum(c["claimAmount"] for c in pend)
            fs.numbers.add(total)
            flag(Flag("pending_defendant", f"{len(pend)} other pending claim(s) against the company, total {rm(total)}."))

    return fs


def load_records() -> dict[str, dict]:
    rows = [json.loads(line) for line in DATA.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {r["registrationNumber"]: r for r in rows}


if __name__ == "__main__":
    import sys

    reg = sys.argv[1] if len(sys.argv) > 1 else "SYN-001389"
    print(build(load_records()[reg]).text())
