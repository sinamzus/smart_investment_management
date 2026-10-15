#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بررسی کیفیت و رابطهٔ سری‌های رسمی شاخص (خروجی fetch_official_indices.py).

    python tools/analyze_index_series.py

بررسی‌ها: بازهٔ زمانی و تکرار، رابطهٔ «كل» با «قيمت» و «TEDPIX»، فصل‌بندی
اختلاف (نشانهٔ سود نقدی)، روزهای تخت و جهش‌های مقیاس ۱۰ برابری.
"""
import csv
import collections
import datetime
import statistics as st
from pathlib import Path

D = Path(__file__).resolve().parent.parent / "data" / "indices"
CODES = {
    "kol": "32097828799138957", "tedpix": "30655480864841493", "price_vw": "5798407779416661",
    "ew": "67130298613737946", "price_ew": "8384385859414435",
}


def load(code):
    return {r["date"]: float(r["close"]) for r in csv.DictReader(open(D / f"index_{code}.csv", encoding="utf-8"))}


def rets(d):
    ks = sorted(d)
    return {ks[i]: d[ks[i]] / d[ks[i - 1]] - 1 for i in range(1, len(ks)) if d[ks[i - 1]] > 0}


def compare(a, b, name):
    ra, rb = rets(a), rets(b)
    ks = sorted(set(ra) & set(rb))
    diff = [ra[k] - rb[k] for k in ks]
    print(f"{name}: n={len(ks)} corr={st.correlation([ra[k] for k in ks], [rb[k] for k in ks]):.5f} "
          f"mean_diff={st.mean(diff)*1e4:.2f}bp  days|diff|>10bp={sum(abs(x) > 1e-3 for x in diff)}")


def main():
    S = {k: load(v) for k, v in CODES.items()}
    for k, d in S.items():
        ds = sorted(d)
        print(f"{k:9s} {len(d):5d} ردیف  {ds[0]} → {ds[-1]}  min={min(d.values()):.1f}")
    print()
    compare(S["kol"], S["price_vw"], "كل vs قيمت(وزني)")
    compare(S["ew"], S["price_ew"], "هم‌وزن(كل) vs هم‌وزن(قيمت)")
    compare(S["kol"], S["tedpix"], "كل vs TEDPIX (به‌خاطر جهش‌های داده بی‌معنی است)")
    ratio = {k: S["kol"][k] / S["tedpix"][k] for k in S["kol"] if S["tedpix"].get(k, 0) > 0}
    med = sorted(ratio.values())[len(ratio) // 2]
    bad = [k for k in ratio if abs(ratio[k] / med - 1) > 0.01]
    print(f"\nTEDPIX ≈ {1/med:.4f} × كل ؛ روزهای ناسازگار (>۱٪): {len(bad)} از {len(ratio)}")
    for name, a, b in (("كل/قيمت(وزني)", "kol", "price_vw"), ("هم‌وزن كل/قيمت", "ew", "price_ew")):
        ks = sorted(set(S[a]) & set(S[b]))
        r0 = S[a][ks[0]] / S[b][ks[0]]
        r1 = S[a][ks[-1]] / S[b][ks[-1]]
        yrs = (datetime.date.fromisoformat(ks[-1]) - datetime.date.fromisoformat(ks[0])).days / 365.25
        print(f"{name}: نسبت {r0:.3f} → {r1:.3f} در {yrs:.1f} سال ⇒ ~{((r1/r0)**(1/yrs)-1)*100:.1f}% در سال (نشانهٔ سود نقدی)")
    ra, rp = rets(S["kol"]), rets(S["price_vw"])
    m = collections.defaultdict(float)
    for k in ra:
        if k in rp:
            m[k[5:7]] += ra[k] - rp[k]
    print("\nمجموع اختلاف بازده (كل − قيمت) به تفکیک ماه میلادی:",
          {k: round(v * 100, 1) for k, v in sorted(m.items())})
    ks = sorted(S["kol"])
    flat = [ks[i] for i in range(1, len(ks)) if S["kol"][ks[i]] == S["kol"][ks[i - 1]]]
    print(f"\nروزهای تخت در «كل»: {len(flat)}؛ ۱۰ مورد آخر: {flat[-10:]}")
    wd = collections.Counter(datetime.date.fromisoformat(k).strftime("%a") for k in ks)
    print("روز هفته:", dict(wd))


if __name__ == "__main__":
    main()
