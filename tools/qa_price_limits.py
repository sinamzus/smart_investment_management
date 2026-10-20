#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""کنترل دامنهٔ مجاز نوسان (فصل ۰۲ §۲٫۸) → data/derived/limit_breaches.csv

    python tools/qa_price_limits.py [--thr 0.12]

ردیفی پرچم می‌خورد که |قیمت پایانی ÷ مبنا − ۱| از آستانه بیشتر است **و** نماد روز معاملاتی قبل هم معامله شده (یعنی بازگشایی پس از توقف نیست؛
بازگشایی‌ها در TSE دامنهٔ آزاد دارند و طبیعی‌اند) و در ±۳ روز رویداد تعدیل TSETMC یا تغییر سرمایه ثبت نشده. آستانهٔ ۱۲٪ از بیشترین دامنهٔ
روزانهٔ تاریخی بالاتر است [تأیید لازم: جدول تاریخی دامنه‌ها]. ممیزی ۲۰۲۶-۱۰-۲۰: از ۲۰۱۶ ۸۰۹ حرکت بالای ۱۲٪ بود که ۶۹۵ تای آن بازگشایی بود؛
بقیه اینجا فهرست می‌شوند. بازده‌ها **تغییر نمی‌کنند** (ممکن است رویداد واقعی ثبت‌نشده باشد)؛ این فهرست برای بازبینی دستی و صفحهٔ کیفیت داده است.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import rebuild_ew_index as ew  # noqa: E402

OUT = ROOT / "data" / "derived" / "limit_breaches.csv"


def breaches(R: pd.DataFrame, thr: float = 0.12, since: str = "2016-01-01") -> pd.DataFrame:
    R = R.sort_values(["ins_code", "date"]).copy()
    R["prev_traded"] = R.groupby("ins_code").zTotTran.shift(1).fillna(0) > 0
    big = R[(R.r.abs() > thr) & (R.date >= since) & R.prev_traded & (R.zTotTran > 0)].copy()
    ev = {}
    for f, col in (("price_adjust.csv", "dEven"), ("share_change.csv", "dEven")):
        p = ROOT / "data/corporate_actions" / f
        if p.exists():
            E = pd.read_csv(p, dtype={"ins_code": str})
            E["d"] = pd.to_datetime(E[col].astype(int).astype(str), format="%Y%m%d")
            for c, g in E.groupby("ins_code"):
                ev.setdefault(c, []).extend(g.d.values)
    ev = {c: np.array(v) for c, v in ev.items()}

    def has_event(c, d):
        a = ev.get(c)
        return a is not None and (np.abs((a - np.datetime64(d)).astype("timedelta64[D]").astype(int)) <= 3).any()
    big["event_near"] = [has_event(c, d) for c, d in zip(big.ins_code, big.date)]
    return big[~big.event_near][["date", "ins_code", "symbol", "market", "r", "pClosing", "priceYesterday"]].sort_values("date")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thr", type=float, default=0.12)
    a = ap.parse_args()
    R = ew.daily_returns(ew.load_panel())
    B = breaches(R, a.thr)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    B.to_csv(OUT, index=False, encoding="utf-8-sig")
    print(f"{OUT.relative_to(ROOT)}: {len(B)} ردیف بیرون از دامنه (|r| > {a.thr:.0%}) پس از روز معامله‌شده و بدون رویداد؛ سال‌ها: "
          f"{B.date.dt.year.value_counts().sort_index().to_dict()}")


if __name__ == "__main__":
    main()
