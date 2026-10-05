"""Render input packages into the user prompt of research plan Appendix B (P2 Step 2.4).

Rendering is deterministic: the same package always yields the same string. Monetary values
are shown as integer KRW million with thousands separators; per-share values in KRW.
Tables are pipe-separated so that Korean double-width characters do not break alignment.
"""

from __future__ import annotations

from typing import Literal

from src.data.package_schema import InputPackage, Statement

Condition = Literal["A", "B", "D", "C"]
HIDDEN = "(비공개)"

CATEGORY_KO = {
    "debt:borrowings": "차입금", "debt:bonds": "사채", "debt:convertible": "전환사채",
    "debt:bond_with_warrant": "신주인수권부사채", "debt:exchangeable": "교환사채",
    "debt:lease": "리스부채", "debt:rcps": "상환전환우선주부채",
    "nonop:fvpl": "당기손익-공정가치 금융자산", "nonop:fvoci": "기타포괄손익-공정가치 금융자산",
    "nonop:equity_method": "관계기업·공동기업 투자", "nonop:investment_property": "투자부동산",
    "nonop:lt_investments": "장기투자증권",
}

USER_TEMPLATE_V1 = """[기업 정보]
{company_block}

[재무제표] (단위: 백만 원, 주당 금액은 원)
{financial_statements}

[주식 정보]
{share_info}

[주석 요약]
{notes}

[추가 공시]
{additional_filings}"""


def fmt_amount(v: float | None) -> str:
    if v is None:
        return "-"
    return f"{round(v):,}"


def render_statement(st: Statement, years: list[int]) -> str:
    header = "| 계정 | " + " | ".join(f"FY{y}" for y in years) + " |"
    out = [f"<{st.title}>", header, "|" + "---|" * (len(years) + 1)]
    for ln in sorted(st.lines, key=lambda x: x.order):
        label = ("  " * ln.indent) + ln.label + (" (원)" if ln.kind == "per_share" else "")
        cells = " | ".join(fmt_amount(ln.values.get(y)) for y in years)
        out.append(f"| {label} | {cells} |")
    return "\n".join(out)


def render_financials(pkg: InputPackage) -> str:
    return "\n\n".join(render_statement(st, pkg.years) for st in pkg.statements())


def render_share_info(pkg: InputPackage) -> str:
    s = pkg.shares
    as_of = f" (기준일 {s.as_of.isoformat()})" if s.as_of else ""
    lines = [f"보통주: 발행주식 {fmt_amount(s.common_issued)}주, 자기주식 "
             f"{fmt_amount(s.common_treasury)}주, 유통주식 {fmt_amount(s.common_outstanding)}주"
             f"{as_of}"]
    if s.preferred_issued > 0:
        lines.append(f"우선주: 발행주식 {fmt_amount(s.preferred_issued)}주, 자기주식 "
                     f"{fmt_amount(s.preferred_treasury)}주, 유통주식 "
                     f"{fmt_amount(s.preferred_outstanding)}주")
    dps = " / ".join(f"FY{y} {fmt_amount(pkg.per_share.dps_common.get(y))}"
                     for y in pkg.years)
    lines.append(f"보통주 1주당 현금배당금(원): {dps}")
    return "\n".join(lines)


def render_notes(pkg: InputPackage) -> str:
    y = pkg.latest_year

    def block(title: str, items) -> list[str]:
        out = [f"{title} (FY{y} 말, 단위: 백만 원)"]
        if not items:
            out.append("- 해당 없음")
        for it in items:
            out.append(f"- {it.label} [{CATEGORY_KO.get(it.category, it.category)}]: "
                       f"{fmt_amount(it.amount)}")
        return out

    return "\n".join(block("차입금·사채 내역", pkg.notes.borrowings)
                     + [""] + block("비영업자산 내역", pkg.notes.non_operating_assets))


def render_additional_filings(pkg: InputPackage, include_cb: bool) -> str:
    if include_cb and pkg.cb is not None:
        return f"{pkg.cb.filing_text}\n\n{pkg.cb.outstanding_table_text}"
    return "없음"


def render_company_block(pkg: InputPackage, condition: Condition,
                         fake_name: str | None = None) -> str:
    """Same two-line structure in every condition (D4.1)."""
    label = pkg.meta.industry_label or HIDDEN
    if condition == "A":
        name, industry = HIDDEN, HIDDEN
    elif condition == "B":
        name, industry = HIDDEN, label
    elif condition == "D":
        if not fake_name:
            raise ValueError("condition D needs a fake name")
        name, industry = fake_name, label
    elif condition == "C":
        name, industry = pkg.meta.real_name, label
    else:
        raise ValueError(f"unknown condition {condition}")
    return f"기업명: {name}\n업종: {industry}"


def render_user_prompt(pkg: InputPackage, condition: Condition = "C",
                       fake_name: str | None = None, include_cb: bool = False,
                       template_version: str = "v1") -> str:
    if template_version != "v1":
        raise ValueError(f"unknown template version {template_version}")
    return USER_TEMPLATE_V1.format(
        company_block=render_company_block(pkg, condition, fake_name),
        financial_statements=render_financials(pkg),
        share_info=render_share_info(pkg),
        notes=render_notes(pkg),
        additional_filings=render_additional_filings(pkg, include_cb),
    )
