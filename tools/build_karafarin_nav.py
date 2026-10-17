#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NAV روزانهٔ خودِ صندوق کارآفرین (سایت صندوق) ← data/funds/nav_own_کارآفرین.csv  (فصل ۳ §۳٫۶؛ جایگزین/مکمل سری فیپیران).

ورودی (به ترتیب اولویت): data/raw/karafarin/{navPerShare,nav}.json (tools/fetch_karafarin_portfolio.py --nav)
                         data/raw/rahavard/karafarin_site/011_*navPerShare*.json و 013_*_nav_1.json (ضبط مرورگر ۲۰۲۶-۱۰-۱۷)
خروجی:  date, ret_daily (٪؛ بازده روزانهٔ NAV ابطال)، nav_cancel, nav_issue, nav_stat, aum (ریال), units, shareholders, source
build_ui_funds.load_nav این فایل را با سری فیپیران ادغام می‌کند (سایت صندوق از ۱۳۸۹ دارد؛ فیپیران از ۲۰۱۹).
نقطهٔ پرت: در سری سایت صندوق دو روز با −۹۰٪ هست (۲۰۲۳-۰۱-۲۵ و ۲۰۲۳-۰۷-۲۳؛ فیپیران بازده معقول دارد) ⇒ هنگام ادغام اگر |اختلاف با فیپیران| > ۲٪ بازدهٔ فیپیران می‌آید.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from fetch_corporate_actions import j2g  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = ROOT / "data" / "funds" / "nav_own_کارآفرین.csv"


def pick(name: str, cap_glob: str):
    f = ROOT / "data" / "raw" / "karafarin" / f"{name}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    c = next(iter(sorted((ROOT / "data" / "raw" / "rahavard" / "karafarin_site").glob(cap_glob))), None)
    if not c:
        sys.exit(f"ورودی نیست: {name}")
    return json.loads(c.read_text(encoding="utf-8"))


def g(jd: str):
    return pd.Timestamp(j2g(*map(int, jd.split("/"))))


def main():
    P = pd.DataFrame(pick("navPerShare", "011_*navPerShare*"))
    N = pd.DataFrame(pick("nav", "013_*_nav_1*"))
    P["date"] = [g(x) for x in P.jalaliDate]
    N["date"] = [g(x) for x in N.jalaliDate]
    P = P.drop_duplicates("date", keep="last").set_index("date").sort_index()
    N = N.drop_duplicates("date", keep="last").set_index("date").sort_index()
    for c in ("purchaseNAVPerShare", "sellNAVPerShare", "statisticalNAVPerShare"):
        P[c] = pd.to_numeric(P[c], errors="coerce")
    D = pd.DataFrame({"ret_daily": P.sellNAVPerShare.pct_change() * 100, "nav_cancel": P.sellNAVPerShare, "nav_issue": P.purchaseNAVPerShare,
                      "nav_stat": P.statisticalNAVPerShare})
    # تجزیهٔ واحد: افت یک‌روزهٔ NAV هر واحد به ~۱/k (k صحیح) که بازده واقعی نیست
    r_ = D.ret_daily / 100
    for dt in r_.index[r_ < -0.5]:
        f = round(1 / (1 + r_[dt]))
        if f >= 2 and abs((1 + r_[dt]) * f - 1) < 0.15:
            print(f"  تجزیهٔ واحد {f}:۱ در {dt.date()}: بازده خام {r_[dt]*100:.1f}٪ ← {((1 + r_[dt]) * f - 1) * 100:.2f}٪")
            D.loc[dt, "ret_daily"] = ((1 + r_[dt]) * f - 1) * 100
    D["aum"] = pd.to_numeric(N.nav, errors="coerce").reindex(D.index)
    D["units"] = pd.to_numeric(N.units, errors="coerce").reindex(D.index)
    D["shareholders"] = pd.to_numeric(N.shareholder, errors="coerce").reindex(D.index)
    D["source"] = "fund_site"
    D = D.iloc[1:]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    D.to_csv(OUT, encoding="utf-8")
    big = D[D.ret_daily.abs() > 15]
    print(f"{len(D)} روز از {D.index[0].date()} تا {D.index[-1].date()}؛ NAV ابطال آخر {D.nav_cancel.iloc[-1]:,.0f}؛ روز با |بازده| > ۱۵٪ پس از تعدیل: {len(big)} {[str(x.date()) for x in big.index]}")
    print(f"→ {OUT}")


if __name__ == "__main__":
    main()
