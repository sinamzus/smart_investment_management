#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ممیزی پوشش جهان سهام (بورس + فرابورس): هر نماد دارای قیمت چرا وارد پانل بازده نمی‌شود و چرا صورت مالی ندارد؟
خروجی: data/research/coverage_audit.csv و خلاصهٔ چاپی."""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import rebuild_cw_index as cw  # noqa: E402
import rebuild_ew_index as ew  # noqa: E402

norm = lambda s: re.sub(r"[‌\s]+", "", str(s)).replace("ي", "ی").replace("ك", "ک")  # noqa: E731


def main():
    inst = pd.read_csv(ROOT / "data/instruments.csv", dtype=str)
    ex = pd.read_csv(ROOT / "data/instruments_extra.csv", dtype=str)
    ex = ex[~ex.ins_code.isin(inst.ins_code)].assign(market="bourse", type="stock")
    allI = pd.concat([inst, ex[["ins_code", "symbol", "name", "market", "type"]]], ignore_index=True)
    info = pd.read_csv(ROOT / "data/corporate_actions/instrument_info.csv", dtype={"ins_code": str})
    fl = info.set_index("ins_code").flow
    allI["market2"] = [("bourse" if fl.get(c) == 1 else "farabourse" if fl.get(c) == 2 else m) if t == "stock" and c in set(ex.ins_code) else m for c, m, t in zip(allI.ins_code, allI.market, allI.type)]
    S = allI[(allI.type == "stock") & allI.market2.isin(["bourse", "farabourse"])].copy()
    have_px = {p.name.split(".")[0] for p in (ROOT / "data/prices").glob("*.csv.gz")}
    S = S[S.ins_code.isin(have_px)]
    syms = set(S.symbol.map(norm))
    S["digit_dup"] = [bool(re.search(r"\d+$", s)) and norm(re.sub(r"\d+$", "", s)) in syms for s in S.symbol]
    panel = ew.load_panel()
    sc = pd.read_csv(ROOT / "data/corporate_actions/share_change.csv", dtype={"ins_code": str})
    sc["date"] = pd.to_datetime(sc.dEven.astype(str), format="%Y%m%d")
    R0 = cw.classify_events(ew.daily_returns(panel, ("bourse", "farabourse")), sc)
    R0["shares"] = cw.shares_timeline(R0, sc, info)
    in_ret = set(R0.dropna(subset=["shares"]).ins_code)
    in_ret_raw = set(R0.ins_code)
    pr = panel.groupby("ins_code").agg(rows=("date", "size"), first=("date", "min"), last=("date", "max"), traded=("zTotTran", lambda x: (x > 0).sum()))
    S = S.join(pr, on="ins_code")
    reasons = []
    for r in S.itertuples():
        if r.ins_code in in_ret:
            reasons.append("")
        elif r.digit_dup:
            reasons.append("رقم‌دار تکراری (قاعدهٔ ۲)")
        elif r.traded == 0 or pd.isna(r.traded):
            reasons.append("هیچ معاملهٔ ثبت‌شده")
        elif r.ins_code in in_ret_raw:
            reasons.append("تعداد سهام نامعلوم (share_change/info)")
        else:
            reasons.append("حذف در پاک‌سازی (اولین معامله/قیمت صفر/بازده <−۹۰٪)")
    import build_ui_extra as bx
    S["operating"] = ~S["name"].fillna("").str.contains(bx.NONOP)
    S["in_returns"] = S.ins_code.isin(in_ret)
    S["reason_returns"] = reasons
    ids = pd.read_csv(ROOT / "data/fundamentals/rahavard_asset_ids.csv", dtype=str).dropna(subset=["trade_symbol"])
    idset = {norm(x) for x in ids.trade_symbol}
    L = pd.read_csv(ROOT / "data/fundamentals/rahavard_long.csv", dtype={"ins_code": str})
    hasdata = set(L[L.stmt == "ratio"].ins_code)
    marked = set(L[L.stmt == "mark"].ins_code)
    S["rahavard_mapped"] = S.symbol.map(norm).isin(idset)
    S["fund_data"] = S.ins_code.isin(hasdata)
    fr = []
    for r in S.itertuples():
        if r.fund_data:
            fr.append("")
        elif r.digit_dup:
            fr.append("رقم‌دار تکراری")
        elif not r.rahavard_mapped:
            fr.append("نماد در فهرست رهاورد نیست (حذف‌شده/تغییرنام/نمادِ فنی)")
        elif r.ins_code in marked:
            fr.append("در رهاورد هست ولی جدول نسبت‌ها خالی است")
        else:
            fr.append("هنوز دریافت نشده")
    S["reason_fund"] = fr
    out = ROOT / "data" / "research" / "coverage_audit.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    S[["ins_code", "symbol", "name", "market2", "rows", "first", "last", "operating", "in_returns", "reason_returns", "rahavard_mapped", "fund_data", "reason_fund"]].to_csv(out, index=False, encoding="utf-8")
    print("جهان:", S.groupby("market2").size().to_dict())
    print("\nوارد پانل بازده:\n", S.groupby(["market2", "in_returns"]).size().unstack(fill_value=0))
    print("\nعلت نبودن در بازده:\n", S[~S.in_returns].groupby(["market2", "reason_returns"]).size())
    print("\nصورت مالی (نسبت‌ها):\n", S.groupby(["market2", "fund_data"]).size().unstack(fill_value=0))
    print("\nعلت نبود صورت مالی:\n", S[~S.fund_data].groupby(["market2", "reason_fund"]).size())
    act = S[S["last"] >= S["last"].max() - pd.Timedelta(days=30)]
    print("\nنمادهای فعال (آخرین قیمت ≤ ۳۰ روز):", len(act), "؛ با صورت مالی:", int(act.fund_data.sum()), "؛ بدون:", int((~act.fund_data).sum()))
    print(act.groupby(["market2", "fund_data"]).size().unstack(fill_value=0))
    print("\nفعال بدون صورت مالی، نمونه:", "؛ ".join(act[~act.fund_data].symbol.head(40)))


if __name__ == "__main__":
    main()
