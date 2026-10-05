"""Per-firm identifier dictionary (P4 §5.2).

Sources: DART company info (names, English name, CEO, address, homepage, ticker) and the
annual report's investment table (`otrCprInvstmntSttus`: subsidiaries and affiliates).
Brands start empty and are filled from the LLM residual check after human review
(config/redaction_overrides.yaml).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

import pandas as pd
from pydantic import BaseModel, Field

LEGAL_FORMS = re.compile(
    r"㈜|\(주\)|\(유\)|\(사\)|\(재\)|주식회사|유한회사|유한책임회사|"
    r"\b(?:co|corp|corporation|inc|ltd|limited|llc|plc|gmbh|s\.a|b\.v|pte|pty)\b\.?",
    re.IGNORECASE)
HOLDING_SUFFIX = re.compile(r"(홀딩스|지주|holdings?)$", re.IGNORECASE)
# Business-group prefixes (D4: matched as whole tokens only when short). Spelled-out forms
# map to the Latin abbreviation used in stock names.
GROUP_PREFIXES = (
    "HD현대", "삼성", "현대", "LG", "SK", "롯데", "한화", "GS", "CJ", "포스코", "POSCO",
    "두산", "한진", "효성", "LS", "DB", "코오롱", "OCI", "HL", "KT", "카카오", "네이버",
    "신세계", "아모레", "농심", "오리온", "한솔", "대상", "동원", "하림", "영풍", "태광",
    "SPC", "KCC", "LX", "HDC", "BGF", "SM", "JYP", "F&F", "CS", "한국타이어", "금호",
    "대우", "동국", "세아", "풍산", "애경", "삼양", "넥센", "한미", "녹십자", "GC", "셀트리온",
)
SPELLED = {"에스케이": "SK", "엘지": "LG", "지에스": "GS", "씨제이": "CJ", "엘에스": "LS",
           "디비": "DB", "케이티": "KT", "에이치디": "HD", "엘엑스": "LX", "에이치엘": "HL",
           "케이씨씨": "KCC", "비지에프": "BGF", "에스엠": "SM", "에스피씨": "SPC"}
# Investee entries that are not names (table totals, placeholders).
NOT_A_NAME = {"기타", "합계", "소계", "계", "총계", "-", "기타법인", "기타회사", "그외", "외"}
# A term made only of these words is generic (it would match standard account labels).
GENERIC_WORDS = re.compile(
    r"투자|금융|에너지|시스템|리스|기술|산업|개발|서비스|홀딩스|파트너스|펀드|조합|신탁|"
    r"증권|보험|은행|캐피탈|자산운용|운용|사모|전자|화학|건설|제약|바이오|글로벌|코리아|"
    r"한국|인터내셔널|international|global|korea|fund|partners|investment|"
    r"[0-9호제차기]|\s|[()\-·.,&]", re.IGNORECASE)


class FirmIdentifiers(BaseModel):
    firm_id: str
    names: list[str] = Field(default_factory=list)
    ticker: str = ""
    ceo: list[str] = Field(default_factory=list)
    address_tokens: list[str] = Field(default_factory=list)
    homepage: str | None = None
    investees: list[str] = Field(default_factory=list)
    brands: list[str] = Field(default_factory=list)
    group_names: list[str] = Field(default_factory=list)
    segments: list[str] = Field(default_factory=list)

    def all_terms(self) -> list[str]:
        """Every searchable token (for automated leak checks)."""
        terms = [*self.names, *self.investees, *self.brands, *self.group_names, *self.ceo]
        if self.ticker:
            terms.append(self.ticker)
        if self.homepage:
            terms.append(self.homepage)
        return _unique(terms)


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def strip_legal(name: str) -> str:
    """Remove legal-form markers and surrounding punctuation: '삼성전자(주)' -> '삼성전자'."""
    out = LEGAL_FORMS.sub(" ", nfc(name))
    out = re.sub(r"[,.]+\s*$", "", out)
    return re.sub(r"\s+", " ", out).strip(" ,.")


def _unique(items: Iterable[str]) -> list[str]:
    seen, out = set(), []
    for it in items:
        it = it.strip()
        if it and it.casefold() not in seen:
            seen.add(it.casefold())
            out.append(it)
    return out


def is_generic(term: str) -> bool:
    return not GENERIC_WORDS.sub("", term)


def name_variants(*names: str | None) -> list[str]:
    """Legal-form-free names plus variants: without spaces, without a holding suffix, and
    with spelled-out group prefixes in Latin letters ('에스케이하이닉스' -> 'SK하이닉스')."""
    out: list[str] = []
    for raw in names:
        if not raw or not str(raw).strip():
            continue
        base = strip_legal(str(raw))
        cands = [base, base.replace(" ", "")]
        for c in list(cands):
            stripped = HOLDING_SUFFIX.sub("", c).strip()
            if stripped and stripped != c:
                cands.append(stripped)
            for spelled, latin in SPELLED.items():
                if c.startswith(spelled):
                    cands.append(latin + c[len(spelled):])
        out += cands
    return _unique(n for n in out if len(n) >= 2)


def group_prefix(names: Iterable[str]) -> list[str]:
    out = []
    for n in names:
        for g in sorted(GROUP_PREFIXES, key=len, reverse=True):
            if n.upper().startswith(g.upper()) and len(n) > len(g):
                out.append(g)
                break
    return _unique(out)


def ceo_names(ceo_nm: str | None) -> list[str]:
    if not ceo_nm:
        return []
    text = re.sub(r"\(.*?\)|각자\s*대표|공동\s*대표|대표이사|대표|사내이사|외\s*\d+\s*명", " ",
                  nfc(ceo_nm))
    parts = re.split(r"[,/·、\s]+", text)
    return _unique(p for p in parts if re.fullmatch(r"[가-힣]{2,4}|[A-Za-z][A-Za-z.\- ]{2,}", p)
                   and not LEGAL_FORMS.search(p))


def address_tokens(adres: str | None) -> list[str]:
    """City, county and district names: '경기도 화성시 동부대로970번길 110' -> ['화성시']."""
    if not adres:
        return []
    toks = re.findall(r"[가-힣]{1,6}(?:특별자치시|특별시|광역시|시|군|구)(?![가-힣])", nfc(adres))
    return _unique(t for t in toks if len(t) >= 2)


def homepage_domain(hm_url: str | None) -> str | None:
    if not hm_url or not str(hm_url).strip():
        return None
    d = re.sub(r"^(https?://)?(www\.)?", "", str(hm_url).strip(), flags=re.IGNORECASE)
    d = d.split("/")[0].lower()
    return d if re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", d) else None


def investee_names(investments: pd.DataFrame | None, own: Iterable[str] = ()) -> list[str]:
    if investments is None or investments.empty or "inv_prm" not in investments:
        return []
    own_keys = {o.casefold() for o in own}
    out = []
    for raw in investments["inv_prm"].dropna().astype(str):
        for n in name_variants(raw):
            if n in NOT_A_NAME or is_generic(n) or n.casefold() in own_keys:
                continue
            out.append(n)
    return _unique(out)


def build_identifiers(firm_id: str, company: dict, investments: pd.DataFrame | None = None,
                      overrides: dict | None = None) -> FirmIdentifiers:
    names = name_variants(company.get("corp_name"), company.get("stock_name"),
                          company.get("corp_name_eng"))
    ov = overrides or {}
    ids = FirmIdentifiers(
        firm_id=firm_id,
        names=_unique([*names, *ov.get("names", [])]),
        ticker=str(company.get("stock_code") or "").strip(),
        ceo=ceo_names(company.get("ceo_nm")),
        address_tokens=address_tokens(company.get("adres")),
        homepage=homepage_domain(company.get("hm_url")),
        investees=_unique([*investee_names(investments, names), *ov.get("investees", [])]),
        brands=_unique(ov.get("brands", [])),
        group_names=_unique([*group_prefix(names), *ov.get("group_names", [])]),
        segments=_unique(ov.get("segments", [])),
    )
    return ids
