#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ممیزی پوشش اقدامات شرکتی (سود نقدی، افزایش سرمایه، تصویب، پرداخت) برای نمادهای فعال بورس و فرابورس — فصل ۲ §۲٫۴.

    python tools/audit_corporate_actions.py

خروجی: data/research/corporate_action_audit_symbols.csv (هر نماد) و corporate_action_audit_years.csv (هر سال) + خلاصهٔ روی صفحه.
تعریف‌ها:
  رویداد سود نقدی = تعدیل قیمت مرجع (price_adjust) که با افزایش سرمایه (share_change، ±۵ روز) نخوانده و نسبت قیمت ∈ (۰٫۴، ۱)؛ مبلغ = قیمت قبل − قیمت تعدیل‌شده.
  رکورد تصویب/پرداخت = ردیف dividend_payment_events (مجمع، مبلغ مصوب، تاریخ پرداخت) با ex-date در ±۶ روز.
  رکورد مجمع راهاورد = ردیف kind=meeting در data/fundamentals/rahavard_eps.csv (تاریخ مجمع + سود تقسیمی مصوب)؛ به رویداد وصل می‌شود اگر
  تاریخ مجمع در ۰ تا ۲۰۰ روز قبل از ex-date باشد و مبلغ مصوب با مبلغ مستخرج تا ±۱۵٪ بخواند (کم‌ترین فاصله).
  رکورد فاندای = data/corporate_actions/fundai_dividends.csv (tools/fetch_fundai_dividends.py: تاریخ مجمع، تاریخ پرداخت، سود هر سهم برای ۴ سال مالی)؛ شرط وصل:
  تاریخ پرداخت ۵− تا ۴۵۰ روز بعد از ex-date و مبلغ ±۱۵٪ مبلغ مستخرج.
خروجی ادغام: data/corporate_actions/dividend_events_merged.csv (هر رویداد با منبع تصویب/پرداخت).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
C = ROOT / "data" / "corporate_actions"
norm = lambda s: s.astype(str).str.replace("ي", "ی").str.replace("ك", "ک").str.replace(r"[\s‌]+", "", regex=True)  # noqa: E731


def load_fundai():
    f = C / "fundai_dividends.csv"
    if not f.exists():
        return pd.DataFrame(columns=["s", "pay", "agm", "dps"])
    from fetch_corporate_actions import j2g

    def cv(x):
        try:
            y, mo, d = map(int, str(x).split("/"))
        except ValueError:
            return pd.NaT
        for dd in (d, d - 1, d - 2):
            try:
                return pd.Timestamp(j2g(y, mo, dd))
            except Exception:  # noqa: BLE001
                pass
        return pd.NaT
    d = pd.read_csv(f, dtype=str)
    d["s"] = norm(d.symbol); d["pay"] = d.pay_from_j.map(cv); d["agm"] = d.agm_j.map(cv); d["dps"] = pd.to_numeric(d.dps_rial, errors="coerce")
    return d[d.pay.notna() & (d.dps > 0)].copy()


def main():
    A = pd.read_csv(ROOT / "data/research/coverage_audit.csv", dtype={"ins_code": str})
    A["last"] = pd.to_datetime(A["last"])
    act = A[(A.operating == True) & (A.in_returns == True) & (A["last"] >= A["last"].max() - pd.Timedelta(days=45))].copy()  # noqa: E712
    act["s"] = norm(act.symbol)
    pa = pd.read_csv(C / "price_adjust.csv", dtype={"ins_code": str})
    sc = pd.read_csv(C / "share_change.csv", dtype={"ins_code": str})
    pa["d"] = pd.to_datetime(pa.dEven.astype(str)); sc["d"] = pd.to_datetime(sc.dEven.astype(str)); sc["g"] = sc.shares_new / sc.shares_old
    inc = sc[sc.g > 1.0001]
    cap = {k: g.d.values for k, g in inc.groupby("ins_code")}

    def is_cap(r):
        a = cap.get(r.ins_code)
        return a is not None and (np.abs((a - np.datetime64(r.d)).astype("timedelta64[D]").astype(int)) <= 5).any()
    pa["cap"] = pa.apply(is_cap, axis=1)
    pa["ratio"] = pa.pClosing.astype(float) / pa.pClosingNotAdjusted.astype(float)
    div = pa[(~pa.cap) & (pa.ratio < 1) & (pa.ratio > 0.4)].copy()
    div["s"] = norm(div.symbol); div["dps_implied"] = div.pClosingNotAdjusted.astype(float) - div.pClosing.astype(float)
    ev = pd.read_csv(C / "dividend_payment_events.csv"); ev["s"] = norm(ev.symbol); ev["ex"] = pd.to_datetime(ev.ex_date, errors="coerce"); ev = ev[ev.ex.notna()].sort_values("ex")
    div = div.sort_values("d")
    m = pd.merge_asof(div, ev[["s", "ex", "agm_j", "dps_rial", "pay_j"]], left_on="d", right_on="ex", by="s", tolerance=pd.Timedelta(days=6), direction="nearest")
    rv = pd.read_csv(ROOT / "data/fundamentals/rahavard_eps.csv", dtype={"ins_code": str})
    rv = rv[rv.kind == "meeting"].copy(); rv["agm"] = pd.to_datetime(rv.date, errors="coerce"); rv = rv[rv.agm.notna() & (rv.dps > 0)]
    by = {k: g for k, g in rv.groupby("ins_code")}

    def rv_match(r):
        g = by.get(r.ins_code)
        if g is None:
            return pd.Series({"rv_agm": pd.NaT, "rv_dps": np.nan, "rv_fy": None})
        lag = (r.d - g.agm).dt.days; ok = g[(lag >= 0) & (lag <= 200) & ((g.dps / r.dps_implied - 1).abs() <= 0.15)]
        if ok.empty:
            return pd.Series({"rv_agm": pd.NaT, "rv_dps": np.nan, "rv_fy": None})
        b = ok.assign(l=(r.d - ok.agm).dt.days).sort_values("l").iloc[0]
        return pd.Series({"rv_agm": b.agm, "rv_dps": float(b.dps), "rv_fy": b.fy})
    m = m.reset_index(drop=True)
    m = pd.concat([m, m.apply(rv_match, axis=1)], axis=1)
    fd = load_fundai()
    fdb = {k: g for k, g in fd.groupby("s")}

    def fd_match(r):
        g = fdb.get(r.s)
        if g is None:
            return pd.Series({"fd_pay": pd.NaT, "fd_agm": pd.NaT, "fd_dps": np.nan})
        lag = (g.pay - r.d).dt.days
        ok = g[(lag >= -5) & (lag <= 450) & ((g.dps / r.dps_implied - 1).abs() <= 0.15)]
        if ok.empty:
            return pd.Series({"fd_pay": pd.NaT, "fd_agm": pd.NaT, "fd_dps": np.nan})
        b = ok.assign(l=(ok.pay - r.d).abs().dt.days).sort_values("l").iloc[0]
        return pd.Series({"fd_pay": b.pay, "fd_agm": b.agm, "fd_dps": float(b.dps)})
    m = pd.concat([m, m.apply(fd_match, axis=1)], axis=1) if len(fd) else m.assign(fd_pay=pd.NaT, fd_agm=pd.NaT, fd_dps=np.nan)
    m["has_pay"] = m.pay_j.notna() | m.fd_pay.notna()
    m["has_agm"] = m.rv_agm.notna() | m.agm_j.notna() | m.fd_agm.notna()
    m["has_any"] = m.has_agm | m.has_pay
    m[["ins_code", "symbol", "d", "dps_implied", "agm_j", "dps_rial", "pay_j", "rv_agm", "rv_dps", "rv_fy", "fd_agm", "fd_pay", "fd_dps", "has_agm", "has_pay", "has_any"]].rename(columns={"d": "ex_date", "agm_j": "farabi_agm_j", "dps_rial": "farabi_dps", "pay_j": "farabi_pay_j"}).to_csv(C / "dividend_events_merged.csv", index=False, encoding="utf-8-sig")
    # سال به سال
    rows = []
    for y in range(2019, 2027):
        x = m[m.d.dt.year == y]; c = inc[inc.d.dt.year == y]
        rows.append({"year": y, "div_events": len(x), "div_symbols": x.ins_code.nunique(), "with_payment_record": int(x.has_pay.sum()), "with_agm_record": int(x.has_agm.sum()), "with_any_record": int(x.has_any.sum()), "share_any": round(float(x.has_any.mean()), 3) if len(x) else 0.0,
                     "capital_increases": len(c), "capital_symbols": c.ins_code.nunique()})
    Y = pd.DataFrame(rows); Y.to_csv(ROOT / "data/research/corporate_action_audit_years.csv", index=False, encoding="utf-8-sig")
    # هر نماد
    r5 = m[m.d >= "2021-10-01"]; c5 = inc[inc.d >= "2021-10-01"]
    S = act[["ins_code", "symbol", "market2"]].copy()
    S["div_events_5y"] = S.ins_code.map(r5.groupby("ins_code").size()).fillna(0).astype(int)
    S["div_with_payment_5y"] = S.ins_code.map(r5[r5.has_pay].groupby("ins_code").size()).fillna(0).astype(int)
    S["div_with_agm_5y"] = S.ins_code.map(r5[r5.has_agm].groupby("ins_code").size()).fillna(0).astype(int)
    S["div_with_any_5y"] = S.ins_code.map(r5[r5.has_any].groupby("ins_code").size()).fillna(0).astype(int)
    S["capital_increases_5y"] = S.ins_code.map(c5.groupby("ins_code").size()).fillna(0).astype(int)
    S.to_csv(ROOT / "data/research/corporate_action_audit_symbols.csv", index=False, encoding="utf-8-sig")
    print(f"نمادهای فعال عملیاتی: {len(S)} (بورس {int((S.market2 == 'bourse').sum())} · فرابورس {int((S.market2 == 'farabourse').sum())})")
    print(f"≥۱ سود نقدی در ۵ سال: {int((S.div_events_5y > 0).sum())} ({(S.div_events_5y > 0).mean():.0%}) · ≥۱ افزایش سرمایه: {int((S.capital_increases_5y > 0).sum())} ({(S.capital_increases_5y > 0).mean():.0%})")
    l24 = m[m.d >= m.d.max() - pd.Timedelta(days=730)]
    print(f"۲۴ ماه اخیر (n={len(l24)}): با مجمع {l24.has_agm.mean():.0%} · با پرداخت {l24.has_pay.mean():.0%} · هر کدام {l24.has_any.mean():.0%}")
    mm = m.dropna(subset=["dps_rial"]); r = mm.dps_implied / mm.dps_rial.astype(float)
    print(f"مبلغ مستخرج از قیمت مرجع در برابر مبلغ مصوب (n={len(mm)}): میانه {float(r.median()):.3f}، در ±۵٪: {((r - 1).abs() <= .05).mean():.0%}")
    print(Y.to_string(index=False))


if __name__ == "__main__":
    main()
