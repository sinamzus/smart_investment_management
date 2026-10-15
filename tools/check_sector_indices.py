#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مقایسهٔ بازسازی صنعت‌به‌صنعت با شاخص‌های صنعت رسمی (برای یافتن نمادهای جاافتاده).

    python tools/check_sector_indices.py

برای هر شاخص صنعت رسمی (نام «NN-...» در data/indices)، شاخص ارزش‌وزن همان صنعت را از
جهان خودمان (بورس + extras) می‌سازد و همبستگی/TE/نسبت سطح را می‌دهد. صنعتی که خطایش بزرگ است
احتمالاً نمادهای جاافتاده (خارج از MarketWatch) دارد: --search نام شرکت‌ها را اجرا کنید.

اعضا از فهرست رسمی اعضای همان شاخص (data/index_constituents.csv) می‌آیند، نه از sector_code نمادها
(sector_code برای برخی صنایع مثل ۶۵ خالی بود). ستون n_off تعداد اعضای رسمی فعلی و n_miss تعدادی است
که قیمتشان در جهان من نیست. سری رسمی از ew.official() (با صافی خطای مقیاس ×۱۰ و تیغهٔ تک‌روزه) خوانده می‌شود.
"""
import numpy as np
import pandas as pd

import rebuild_cw_index as cw
import rebuild_ew_index as ew

ROOT = ew.ROOT
# کد شاخص رسمی → کد صنعت (cSecVal) — از فهرست --list کاربر
SECTORS = {
    "34408080767216529": "01", "19219679288446732": "10", "13235969998952202": "13", "62691002126902464": "14",
    "59288237226302898": "17", "69306841376553334": "19", "58440550086834602": "20", "30106839080444358": "21",
    "25766336681098389": "22", "12331083953323969": "23", "36469751685735891": "25", "47946228513774508": "26",
    "32453344048876642": "27", "1123534346391630": "28", "11451389074113298": "29", "33878047680249697": "31",
    "24733701189547084": "32", "61848754958448778": "33", "20213770409093165": "34", "58231368623465359": "35",
    "29331053506731535": "36", "21948907150049163": "38", "40355846462826897": "39", "54843635503648458": "40",
    "15508900928481581": "42", "3615666621538524": "43", "33626672012415176": "44", "41934470778361119": "45",
    "65986638607018835": "47", "57616105980228781": "49", "70077233737515808": "53", "14651627750314021": "54",
    "64514606457616199": "55", "34295935482222451": "56", "72002976013856737": "57", "25163959460949732": "58",
    "24187097921483699": "60", "41867092385281437": "64", "61247168213690670": "65", "61985386521682984": "67",
    "4654922806626448": "70", "8900726085939949": "72", "18780171241610744": "73", "47233872677452574": "74",
    "65675836323214668": "11", "59105676994811497": "66",
}


def main():
    sc = pd.read_csv(ROOT / "data/corporate_actions/share_change.csv", dtype={"ins_code": str})
    sc["date"] = pd.to_datetime(sc.dEven.astype(str), format="%Y%m%d")
    info = pd.read_csv(ROOT / "data/corporate_actions/instrument_info.csv", dtype={"ins_code": str})
    R = cw.classify_events(ew.daily_returns(ew.load_panel()), sc)
    R["shares"] = cw.shares_timeline(R, sc, info)
    R = R.dropna(subset=["shares"]).merge(info[["ins_code", "sector_code"]], on="ins_code", how="left")
    R["sec"] = R.sector_code.astype(str).str.strip().str.lstrip("0")
    R["w"] = R.priceYesterday * R.shares
    con = pd.read_csv(ROOT / "data/index_constituents.csv", dtype=str)
    rows = []
    for code, sec in SECTORS.items():
        f = ROOT / f"data/indices/index_{code}.csv"
        if not f.exists():
            continue
        off = ew.official(code)
        members = set(con[con.index_code == code].ins_code)
        n_miss = len(members - set(R.ins_code))
        res = {}
        for lab, S in (("m", R[R.ins_code.isin(members)] if members else R.iloc[0:0]),
                       ("s", R[R.sec == sec.lstrip("0")])):          # m = اعضای فعلی رسمی؛ s = همهٔ سهام بورسی صنعت (با حذف‌شده‌ها)
            best = None
            if not S.empty:
                den = S.groupby("date").w.sum()
                for col in ("r_tr", "r_pr"):
                    x = (S[col] * S.w).groupby(S.date).sum() / den
                    j = pd.concat([x, off], axis=1, join="inner").dropna()
                    j.columns = ["m", "o"]
                    j = j[j.index >= "2014-03-20"]
                    if len(j) < 200:
                        continue
                    d = j.m - j.o
                    r = (j.m.corr(j.o), d.std() * np.sqrt(252) * 100, (1 + j.m).prod() / (1 + j.o).prod())
                    if best is None or r[1] < best[1]:
                        best = (*r, col)
            res[lab] = (best, S.groupby("date").ins_code.nunique().iloc[-1] if not S.empty else 0, S.ins_code.nunique())
        bm, bs = res["m"][0], res["s"][0]
        nan3 = (np.nan, np.nan, np.nan, "")
        rows.append((sec, int(res["m"][1]), n_miss, *(bm or nan3), int(res["s"][2]), *(bs[:2] if bs else (np.nan, np.nan))))
    df = pd.DataFrame(rows, columns=["sector", "n_last", "n_miss", "corr", "te_pct", "cum_ratio", "best", "n_all", "corr_all", "te_all"]).sort_values("te_pct", ascending=False)
    pd.set_option("display.width", 140)
    print(df.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
