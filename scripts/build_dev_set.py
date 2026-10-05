"""P7 Step 1 input: the dev set for prompt iteration (5 firms outside the 150-firm sample).

  X001, X002  large  KOSPI market-cap ranks 51-52 (just below the L group)
  X003        mid    KOSPI rank 101 that the M selection did not pick
  X004, X005  small  KOSDAQ CB issuers whose stock trades below half of every conversion
                     price: they cannot enter the S group (in-the-money CB required) even
                     when KRX KOSDAQ prices replace the provisional yfinance closes

Writes data/processed/dev/{sample.parquet, packages/X00n.json} and identifier files.
Uses cached OpenDART data only.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from src.conditions import pipeline as pl  # noqa: E402
from src.config import load_config  # noqa: E402
from src.data.cb_truth import build_cb_block, current_instruments  # noqa: E402
from src.data.dart_client import DartClient  # noqa: E402
from src.data.p2_inputs import P1Data, iter_builds  # noqa: E402

DEV = [("X001", "L", "00583424"), ("X002", "L", "00105961"), ("X003", "M", "00125521"),
       ("X004", "S", "01147487"), ("X005", "S", "00288343")]


def main() -> int:
    cfg = load_config()
    t_post = cfg.require_dates()[0]
    sample = set(pl.load_sample()["corp_code"])
    clash = [cc for _, _, cc in DEV if cc in sample]
    if clash:
        raise SystemExit(f"dev firms overlap the sample: {clash}")
    p1 = pl.PROCESSED / "p1"
    out, refix, terms = (pd.read_parquet(p1 / f"{n}.parquet")
                         for n in ("cb_outstanding", "cb_refixings", "cb_terms"))
    pkg_dir = pl.DEV_DIR / "packages"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    by_cc = {cc: (fid, grp) for fid, grp, cc in DEV}
    comp = pl.companies()
    rows = []
    for r in iter_builds(DartClient(), cfg, P1Data.load(), list(by_cc)):
        fid, grp = by_cc[r.corp_code]
        if r.package is None or r.status != "ok":
            raise SystemExit(f"{fid} ({r.corp_code}) failed to build: {r.status}")
        pkg = r.package
        pkg.meta.firm_id, pkg.meta.group = fid, "U"
        if grp == "S":
            cc = r.corp_code
            ins = current_instruments(out[out.corp_code == cc],
                                      refix[refix.corp_code == cc] if not refix.empty else refix,
                                      terms[terms.corp_code == cc], t_post)
            pkg.cb = build_cb_block(ins, t_post)
            if pkg.cb is None:
                raise SystemExit(f"{fid}: no outstanding CB at {t_post}")
        (pkg_dir / f"{fid}.json").write_text(pkg.to_json(), encoding="utf-8")
        c = comp.loc[r.corp_code]
        row = {"firm_id": fid, "group": grp, "corp_code": r.corp_code,
               "stock_code": c["stock_code"], "corp_name": c["corp_name"],
               "market": pkg.meta.market, "ksic2": (pkg.meta.ksic or "")[:2]}
        pl.save_identifiers(pl.identifiers_for(row))
        rows.append(row)
        print(f"{fid} {grp} {c['corp_name']} cb={pkg.cb is not None}")
    pd.DataFrame(rows).sort_values("firm_id").to_parquet(pl.DEV_DIR / "sample.parquet",
                                                         index=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
