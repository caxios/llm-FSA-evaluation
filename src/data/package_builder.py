"""Build input packages from P1 raw data (P2 Step 2.3).

The builder works on DataFrames as returned by DartClient (no network access of its own):
- statements: map accounts, assign each line to its subtotal using the DART `ord` grouping
  (a subtotal row is followed by its components), restore a readable display order,
  convert KRW to KRW million;
- shares, EPS, DPS, notes summary (derived from BS lines, D2.2);
- identity checks (D7: firms that fail a hard identity are excluded, not patched).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date

import pandas as pd

from src.data.account_map import (
    AccountMap,
    load_account_map,
    load_industry_labels,
    normalize_label,
)
from src.data.package_schema import (
    InputPackage,
    LineItem,
    NoteItem,
    NotesSummary,
    PackageMeta,
    PerShare,
    ShareInfo,
    Statement,
)
from src.data.parsing import parse_amount, parse_date
from src.data.universe import ksic_division
from src.perturb.consistency import cash_roll_ok, check_identities

BS_SECTIONS = ("current_assets", "non_current_assets", "current_liabilities",
               "non_current_liabilities", "total_equity")
BS_RESET = ("total_assets", "total_liabilities", "total_liabilities_and_equity")
EQUITY_COMPONENTS = ("issued_capital", "retained_earnings", "oci_reserve", "other_equity")
_EQUITY_ID = re.compile(r"CapitalSurplus|SharePremium|StockholdersEquity|TreasuryShares|"
                        r"OtherComprehensiveIncomeLossAccumulated|IssuedCapital|"
                        r"RetainedEarnings|CapitalAdjustment")
_EQUITY_LABEL = re.compile(r"(자본금|자본잉여금|주식발행초과금|자본조정|기타자본|"
                           r"기타포괄손익누계액|이익잉여금|결손금|자기주식|기타불입자본|신종자본증권)")
CF_SECTIONS = ("cfo", "cfi", "cff")
CF_RESET = ("beginning_cash", "ending_cash", "net_change_in_cash", "net_change_before_fx",
            "fx_effect_on_cash")

REQUIRED = {
    "BS": ("total_assets", "current_assets", "non_current_assets", "total_liabilities",
           "current_liabilities", "non_current_liabilities", "total_equity", "cash"),
    "IS": ("operating_income", "pretax_income", "net_income"),
    "CF": ("cfo", "cfi", "cff", "beginning_cash", "ending_cash"),
}

IS_RANK = {
    "revenue": 0, "cost_of_sales": 10, "gross_profit": 20, "sga": 30, "operating_expense": 35,
    "operating_income": 50, "finance_income": 60, "finance_costs": 61, "pretax_income": 70,
    "income_tax": 71, "net_income": 75, "net_income_owners": 76, "net_income_nci": 77,
    "eps_basic": 95, "eps_diluted": 96,
}
_OCI = re.compile(r"기타포괄|포괄손익|재분류|재측정|환산|지분법자본변동|세후")
_CONTINUING = re.compile(r"계속영업|중단영업")
TITLES = {"BS": "재무상태표", "IS": "손익계산서", "CIS": "포괄손익계산서", "CF": "현금흐름표"}
AMOUNT_COLS = ("bfefrmtrm_amount", "frmtrm_amount", "thstrm_amount")  # Y-2, Y-1, Y


class BuildError(ValueError):
    pass


@dataclass
class BuildResult:
    corp_code: str
    package: InputPackage | None
    status: str                                  # "ok" or an exclusion reason
    issues: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- statements


def _is_per_share(account_id: str, label: str) -> bool:
    return "PerShare" in account_id or "주당" in label


def _rows_for(fs: pd.DataFrame, code: str) -> tuple[pd.DataFrame, str]:
    if code == "IS":
        rows = fs[fs["sj_div"] == "IS"]
        if rows.empty:  # single statement of comprehensive income (P0 finding)
            return fs[fs["sj_div"] == "CIS"], TITLES["CIS"]
        return rows, TITLES["IS"]
    return fs[fs["sj_div"] == code], TITLES[code]


def _values(row, years: list[int], per_share: bool) -> dict[int, float | None]:
    out: dict[int, float | None] = {}
    for year, col in zip(years, AMOUNT_COLS, strict=True):
        v = row.get(col)
        v = parse_amount(v) if isinstance(v, str) else v
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out[year] = None
        else:
            out[year] = float(v) if per_share else float(v) / 1e6
    return out


def build_statement(fs: pd.DataFrame, code: str, years: list[int],
                    amap: AccountMap) -> tuple[Statement, list[str]]:
    rows, title = _rows_for(fs, code)
    rows = rows.assign(_i=range(len(rows))).sort_values(["ord", "_i"], kind="stable")
    issues: list[str] = []
    lines: list[LineItem] = []
    used: set[str] = set()
    sections = BS_SECTIONS if code == "BS" else CF_SECTIONS if code == "CF" else ()
    resets = BS_RESET if code == "BS" else CF_RESET if code == "CF" else ()
    section: str | None = None
    prefix = code.lower()

    for n, row in enumerate(rows.to_dict("records")):
        account_id = str(row.get("account_id") or "")
        label = str(row.get("account_nm") or "").strip()
        canonical = None
        for cand in amap.unique_candidates(code, account_id, label):
            if cand not in used:
                canonical = cand
                used.add(cand)
                break
        if canonical in sections:
            section = canonical
        elif canonical in resets:
            section = None
        parent = None
        if canonical is None or canonical not in sections + resets:
            parent = section
        per_share = _is_per_share(account_id, label)
        lines.append(LineItem(
            line_id=f"{prefix}_{n:03d}", label=label, account_id=account_id,
            canonical=canonical, parent=parent,
            category=amap.category(account_id, label, section) if code == "BS" else None,
            kind="per_share" if per_share else "monetary",
            values=_values(row, years, per_share), order=0,
        ))

    if code == "IS":
        _fix_income_statement(lines)

    # Some filers list equity components before the equity total in DART `ord`, so the
    # section tracking files them under the preceding asset or liability section.
    if code == "BS":
        for ln in lines:
            if ln.parent in BS_SECTIONS[:4] and _is_equity_component(ln):
                ln.parent = "total_equity"

    # Equity components roll into owners' equity when it is reported (consolidated).
    if code == "BS":
        has_owners = any(ln.canonical == "equity_owners" for ln in lines)
        for ln in lines:
            if ln.parent == "total_equity" and has_owners and ln.canonical not in (
                    "equity_owners", "non_controlling_interest"):
                ln.parent = "equity_owners"
            if ln.canonical in ("equity_owners", "non_controlling_interest"):
                ln.parent = None  # chained through config/ancestry.yaml

    _assign_order(code, lines)
    missing = [c for c in REQUIRED[code] if not any(ln.canonical == c for ln in lines)]
    if code == "IS" and not any(ln.canonical in ("revenue", "operating_expense")
                                for ln in lines):
        missing.append("revenue")
    if missing:
        issues.append(f"{code} missing required: {', '.join(missing)}")
    return Statement(code=code, title=title, lines=lines), issues


def _is_equity_component(ln: LineItem) -> bool:
    return (ln.canonical in EQUITY_COMPONENTS or bool(_EQUITY_ID.search(ln.account_id))
            or bool(_EQUITY_LABEL.match(normalize_label(ln.label))))


def _fix_income_statement(lines: list[LineItem]) -> None:
    """Known filer variations seen in the P2 build:
    - holding companies report revenue as '영업수익' under the GrossProfit account ID;
    - firms without non-controlling interests may report only the owners' net income line.
    """
    tags = {ln.canonical for ln in lines}
    if "revenue" not in tags:
        for ln in lines:
            if ln.canonical == "gross_profit" and normalize_label(ln.label) == "영업수익":
                ln.canonical = "revenue"
                break
    if "net_income" not in tags and "net_income_nci" not in tags:
        for ln in lines:
            if ln.canonical == "net_income_owners":
                ln.canonical = "net_income"
                break


def _assign_order(code: str, lines: list[LineItem]) -> None:
    """Restore a readable statement order; DART `ord` is not the filing's display order."""
    def key_bs(ln: LineItem) -> tuple:
        group = {"current_assets": 0, "non_current_assets": 1, "total_assets": 2,
                 "current_liabilities": 3, "non_current_liabilities": 4,
                 "total_liabilities": 5, "total_equity": 6,
                 "total_liabilities_and_equity": 8}
        if ln.canonical in group:
            g = group[ln.canonical]
            # subtotal header first, grand totals after their components
            sub = 0 if ln.canonical in BS_SECTIONS and ln.canonical != "total_equity" else 9
            if ln.canonical == "total_equity":
                g, sub = 6, 9
            return (g, sub)
        if ln.canonical == "equity_owners":
            return (6, 0)
        if ln.canonical == "non_controlling_interest":
            return (6, 5)
        if ln.parent in group:
            return (group[ln.parent], 1)
        if ln.parent == "equity_owners":
            return (6, 1)
        return (7, 1)

    def key_is(ln: LineItem) -> tuple:
        if ln.canonical in IS_RANK:
            return (IS_RANK[ln.canonical],)
        if ln.kind == "per_share":
            return (97,)
        if _OCI.search(ln.label):
            return (85,)
        if _CONTINUING.search(ln.label):
            return (74,)
        return (55,)

    def key_cf(ln: LineItem) -> tuple:
        group = {"cfo": 0, "cfi": 1, "cff": 2}
        tail = {"net_change_before_fx": 4, "fx_effect_on_cash": 5, "net_change_in_cash": 6,
                "beginning_cash": 7, "ending_cash": 8}
        if ln.canonical in group:
            return (group[ln.canonical], 0)
        if ln.canonical in tail:
            return (tail[ln.canonical], 0)
        if ln.parent in group:
            return (group[ln.parent], 1)
        return (3, 0)

    key = {"BS": key_bs, "IS": key_is, "CF": key_cf}[code]
    ranked = sorted(enumerate(lines), key=lambda t: (*key(t[1]), t[0]))
    for order, (_, ln) in enumerate(ranked):
        ln.order = order
        ln.indent = 1 if ln.parent else 0
    lines.sort(key=lambda ln: ln.order)


# ---------------------------------------------------------------- other blocks


def _count(value) -> float:
    v = parse_amount(value)
    return 0.0 if math.isnan(v) else v


def _share_class(name: str) -> str | None:
    """Classify a share-total row name ('보통주(의결권있는주식)', '의결권이없는주식', ...)."""
    if name.startswith(("합계", "비고")):
        return None
    if "우선" in name or "종류" in name or "없는" in name:
        return "preferred"
    if "보통" in name or "있는" in name:
        return "common"
    return None


def build_shares(shares: pd.DataFrame) -> ShareInfo:
    if shares.empty:
        raise BuildError("no share totals")
    by_class: dict[str, dict] = {}
    for r in shares.to_dict("records"):
        cls = _share_class(re.sub(r"\s", "", str(r["se"])))
        if cls and cls not in by_class:
            by_class[cls] = r
    common = by_class.get("common")
    if common is None:
        raise BuildError(f"no common-share row in share totals: {list(shares['se'])}")
    pref = by_class.get("preferred", {})
    return ShareInfo(
        common_issued=_count(common.get("istc_totqy")),
        common_treasury=_count(common.get("tesstk_co")),
        preferred_issued=_count(pref.get("istc_totqy")),
        preferred_treasury=_count(pref.get("tesstk_co")),
        as_of=parse_date(str(common.get("stlm_dt") or "")),
    )


def build_dps(dividends: pd.DataFrame, years: list[int]) -> dict[int, float | None]:
    """Cash dividend per common share for (Y-2, Y-1, Y); '-' means no dividend (0)."""
    out: dict[int, float | None] = {y: None for y in years}
    if dividends.empty:
        return out
    rows = [r for r in dividends.to_dict("records")
            if str(r.get("se", "")).replace(" ", "").startswith("주당현금배당금")]
    if not rows:
        return out
    common = [r for r in rows if str(r.get("stock_knd", "")).strip() in ("보통주", "-", "")]
    row = (common or rows)[0]
    for year, col in zip(years, ("lwfr", "frmtrm", "thstrm"), strict=True):
        v = parse_amount(str(row.get(col, "")))
        out[year] = 0.0 if math.isnan(v) else v
    return out


def build_notes(bs: Statement, year: int) -> NotesSummary:
    def items(prefix: str) -> list[NoteItem]:
        out = []
        for ln in bs.by_category(prefix):
            v = ln.values.get(year)
            if v:
                out.append(NoteItem(label=ln.label, amount=v, line_id=ln.line_id,
                                    category=ln.category or ""))
        return out

    return NotesSummary(borrowings=items("debt:"), non_operating_assets=items("nonop:"))


def outflow_sign(cf: Statement, year: int) -> int:
    """+1 if the firm reports cash outflows as positive numbers, -1 if negative."""
    votes = []
    for canonical in ("capex_ppe", "capex_intangibles", "dividends_paid"):
        ln = cf.find(canonical)
        v = ln.values.get(year) if ln else None
        if v:
            votes.append(1 if v > 0 else -1)
    return 1 if sum(votes) >= 0 else -1


# ---------------------------------------------------------------- package


def build_package(
    *,
    corp_code: str,
    fs: pd.DataFrame,
    fs_div: str,
    company: dict,
    shares: pd.DataFrame,
    dividends: pd.DataFrame,
    fiscal_year: int,
    eval_date: date,
    market: str,
    amap: AccountMap | None = None,
) -> BuildResult:
    amap = amap or load_account_map()
    issues: list[str] = []
    if fs.empty:
        return BuildResult(corp_code, None, "no_statements")
    if "currency" in fs and set(fs["currency"].dropna()) - {"KRW"}:
        return BuildResult(corp_code, None, "non_krw")
    years = [fiscal_year - 2, fiscal_year - 1, fiscal_year]
    statements = {}
    for code in ("BS", "IS", "CF"):
        st, st_issues = build_statement(fs, code, years, amap)
        statements[code] = st
        issues += st_issues
    if any("missing required" in i for i in issues):
        return BuildResult(corp_code, None, "missing_required", issues)

    try:
        share_info = build_shares(shares)
    except BuildError as exc:
        return BuildResult(corp_code, None, "no_shares", issues + [str(exc)])
    if share_info.common_issued <= 0:
        return BuildResult(corp_code, None, "no_shares", issues + ["zero common shares"])

    eps_line = statements["IS"].find("eps_basic")
    ksic = company.get("induty_code") or None
    flags = []
    if eps_line is None:
        flags.append("no_eps_line")
    if statements["BS"].find("retained_earnings") is None:
        flags.append("no_retained_earnings")
    if statements["CF"].find("depreciation") is None:
        flags.append("no_depreciation_line")
    meta = PackageMeta(
        firm_id=f"U{corp_code}", corp_code=corp_code, ticker=str(company.get("stock_code", "")),
        real_name=str(company.get("corp_name", "")), ksic=ksic,
        industry_label=load_industry_labels().get(ksic_division(ksic) or "", None),
        group="U", market=market, eval_date=eval_date, fiscal_year=fiscal_year,
        source_rcept_no=str(fs["rcept_no"].iloc[0]), fs_div=fs_div, flags=flags,
    )
    pkg = InputPackage(
        meta=meta, years=years, bs=statements["BS"], is_=statements["IS"], cf=statements["CF"],
        per_share=PerShare(eps={y: (eps_line.values.get(y) if eps_line else None) for y in years},
                           dps_common=build_dps(dividends, years)),
        shares=share_info,
        notes=build_notes(statements["BS"], fiscal_year),
    )
    _, includes_fx = cash_roll_ok(pkg, fiscal_year)
    pkg.meta.net_change_includes_fx = includes_fx
    pkg.meta.flags.append(f"cf_outflow_sign={outflow_sign(pkg.cf, fiscal_year):+d}")

    violations = check_identities(pkg)
    if violations:
        detail = "; ".join(f"{v.check}@{v.year} gap={v.gap:,.1f}" for v in violations[:6])
        return BuildResult(corp_code, pkg, "identity_failure", issues + [detail])
    soft = check_identities(pkg, include_soft=True)
    if soft:
        pkg.meta.flags.append("cf_ending_cash_differs_from_bs_cash")
    return BuildResult(corp_code, pkg, "ok", issues)
