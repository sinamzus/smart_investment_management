#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تفکیک افزایش سرمایهٔ نقدی (حق‌تقدم) از سهام جایزه برای هر رویداد share_change — برای معیارهای net_issue_cash / net_issue_bonus (فصل ۱۴ §۱۴٫۳٫۴).

روش: در روز ایکس-دیت قیمت مرجع (priceYesterday) بورس برای افزایش سرمایه تعدیل می‌شود. با g = سهام نو ÷ سهام قدیم، P = آخرین قیمت پایانی پیش از رویداد
و ρ = priceYesterday ÷ P:
    جایزه محض:       ρ·g = ۱
    حق‌تقدم نقدی:     ρ = (P + c) ÷ (g·P)  ← c = P·(ρ·g − ۱) نقد دریافتی به‌ازای هر سهم قدیم
    سهم نقدی افزایش:  cs = c ÷ (K·(g − ۱))،  K = قیمت پذیره‌نویسی = ارزش اسمی ۱۰۰۰ ریال [تأیید لازم]
cs به [۰، ۱] بُرش می‌خورد؛ رویدادی که cs آن از [−۰٫۱، ۱٫۱] بیرون باشد (برخورد با رویداد دیگر در پنجره) «نامطمئن» است و در هیچ‌یک از دو معیار نمی‌آید.
توزیع cs دوقله‌ای است (≈ ۶۰٪ جایزه، ≈ ۲۹٪ نقدی، ≈ ۱۱٪ ترکیبی) که اعتبار روش را نشان می‌دهد؛ ۸۶٪ رویدادها مطمئن‌اند.

خروجی: data/corporate_actions/issue_split.csv (ins_code, symbol, dEven, g, rho, P, cs, reliable)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_ui_extra as bx  # noqa: E402

K_PAR = 1000.0


def main():
    _, _, Ra0 = bx.base_panel(bx.ALL_MARKETS)
    s = pd.read_csv(ROOT / "data/corporate_actions/share_change.csv", dtype={"ins_code": str})
    s = s[(s.shares_new > s.shares_old * 1.0001) & (s.shares_new / s.shares_old < 50)].copy()
    s["g"] = s.shares_new / s.shares_old
    s["d"] = pd.to_datetime(s.dEven.astype(str))
    P = Ra0[["ins_code", "date", "priceYesterday", "prevC"]].dropna().copy()
    P["rho"] = P.priceYesterday / P.prevC
    grp = {k: v for k, v in P.groupby("ins_code")}
    rows = []
    for r in s.itertuples():
        g = grp.get(r.ins_code)
        if g is None:
            continue
        w = g[(g.date >= r.d - pd.Timedelta(days=3)) & (g.date <= r.d + pd.Timedelta(days=7))]
        if not len(w):
            continue
        x = w.loc[(w.rho - 1).abs().idxmax()]            # روز ایکس-دیت = بیشترین انحراف قیمت مرجع
        cs_raw = x.prevC * (x.rho * r.g - 1) / (K_PAR * (r.g - 1))
        rows.append({"ins_code": r.ins_code, "symbol": r.symbol, "dEven": r.dEven, "g": r.g, "rho": x.rho, "P": x.prevC,
                     "cs": float(np.clip(cs_raw, 0, 1)), "reliable": bool(-0.1 <= cs_raw <= 1.1)})
    o = pd.DataFrame(rows).drop_duplicates(["ins_code", "dEven"])
    o.to_csv(ROOT / "data/corporate_actions/issue_split.csv", index=False, encoding="utf-8-sig")
    rel = o[o.reliable]
    print(f"{len(o)} رویداد؛ مطمئن {len(rel)} ({100 * len(rel) / len(o):.0f}٪)")
    print("توزیع سهم نقدی (مطمئن): جایزه ≤۰٫۰۵:", int((rel.cs <= 0.05).sum()), "| ترکیبی:", int(((rel.cs > 0.05) & (rel.cs < 0.95)).sum()), "| نقدی ≥۰٫۹۵:", int((rel.cs >= 0.95).sum()))


if __name__ == "__main__":
    main()
