#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سنجش ردیابی صندوق‌های شاخصی در برابر شاخص مرجع → ui/data/funds.js (window.SIM_FUNDS)

    python tools/build_ui_funds.py

ورودی (از tools/fetch_index_funds.py): data/funds/funds.csv، nav_<نماد>.csv، price_<نماد>.csv.gz

روش (فصل ۳ §۳٫۶):
- بازده صندوق از NAV ابطال (اگر نبود NAV آماری) روی روزهای معاملاتی شاخص: NAV هر روز معاملاتی = آخرین NAV منتشرشده تا آن روز.
- دو ماه اول عمر صندوق (دورهٔ تشکیل سبد) کنار می‌رود.
- جهش |بازده فعال روزانه| > ۸٪ = رویداد (تجزیهٔ واحد، خطای NAV؛ برای صندوق شاخصی غیرممکن است) ← خنثی و فهرست می‌شود؛ ۳ تا ۸٪ فقط علامت می‌خورد. TE مقاوم (بر پایهٔ MAD) هم گزارش می‌شود.
- مرجع اصلی: سری رسمی TR شاخص اعلام‌شده. مرجع منصفانه: ماکت سرمایه‌پذیر همان شاخص با تأخیر ۹۰ روزهٔ سود (فصل ۳ §۳٫۵)
  ← تفاوت ردیابی به «اثر تأخیر سود» (ساختاری) و «کارمزد، نقد و اجرا» (قابل‌انتساب به مدیر) تجزیه می‌شود.
- TE روزانه × √۲۵۲ و TE هفتگی (بازده ۵ روزه) × √۵۲؛ هفتگی به ناهمزمانی انتشار NAV حساس نیست. TD با سال تقویمی.
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

import analyze_fund_holdings as ah
import fund_diagnostics as fd
import investable_replica as ir
import rebuild_ew_index as ew
import rebuild_ew_rebalanced as ewr

ROOT = ew.ROOT
FUNDS = Path(os.environ.get("SIM_FUNDS_DIR", ROOT / "data" / "funds"))
OUT = Path(os.environ.get("SIM_FUNDS_OUT", ROOT / "ui" / "data" / "funds.js"))
BENCH = {"K": ("32097828799138957", "«شاخص كل»"), "EW": ("67130298613737946", "«شاخص كل (هم وزن)»"),
         "I30": ("10523825119011581", "«شاخص ۳۰ شرکت بزرگ»")}
LAG = 90
WARMUP_DAYS = 60
EVENT, FLAG = 0.08, 0.03


def r(x, n=2):
    return None if x is None or pd.isna(x) else round(float(x), n)


def ann(ret: pd.Series) -> float:
    yrs = (ret.index[-1] - ret.index[0]).days / 365.25
    return ((1 + ret).prod() ** (1 / max(yrs, 1e-9)) - 1) * 100


def metrics(f: pd.Series, b: pd.Series) -> dict:
    j = pd.concat([f, b], axis=1, join="inner").dropna()
    j.columns = ["f", "b"]
    if len(j) < 40:
        return {"n": len(j)}
    a = j.f - j.b
    w = (1 + j).groupby(np.arange(len(j)) // 5).prod() - 1           # بازده ۵ روزهٔ غیرهم‌پوشان
    aw = w.f - w.b
    beta = np.cov(j.f, j.b)[0, 1] / j.b.var()
    yrs = (j.index[-1] - j.index[0]).days / 365.25
    td = (((1 + j.f).prod() / (1 + j.b).prod()) ** (1 / yrs) - 1) * 100
    return {"n": len(j), "from": str(j.index[0].date()), "to": str(j.index[-1].date()),
            "te_d": r(a.std() * np.sqrt(252) * 100), "te_w": r(aw.std() * np.sqrt(52) * 100),
            "te_w_rob": r(1.4826 * (aw - aw.median()).abs().median() * np.sqrt(52) * 100),
            "td": r(td), "ann_f": r(ann(j.f), 1), "ann_b": r(ann(j.b), 1),
            "corr": r(j.f.corr(j.b), 4), "corr_w": r(w.f.corr(w.b), 4), "beta": r(beta, 3), "r2": r(j.f.corr(j.b) ** 2, 4),
            "mad_bp": r(a.abs().mean() * 1e4, 1)}


def load_nav(sym: str) -> pd.DataFrame | None:
    p = FUNDS / f"nav_{sym}.csv"
    if not p.exists():
        return None
    d = pd.read_csv(p, parse_dates=["date"]).set_index("date").sort_index()
    d = d[~d.index.duplicated(keep="last")]
    return d


def load_price(sym: str) -> pd.DataFrame | None:
    p = FUNDS / f"price_{sym}.csv.gz"
    if not p.exists():
        return None
    d = pd.read_csv(p, parse_dates=["date"]).set_index("date").sort_index()
    return d[~d.index.duplicated(keep="last")]


def fund_returns(nav: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    nav = nav[nav > 0].dropna()
    s = nav.reindex(dates.union(nav.index)).ffill(limit=6).reindex(dates)
    s = s[s.index >= nav.index[0] + pd.Timedelta(days=WARMUP_DAYS)]
    return s.pct_change().dropna()


def jyear(d):
    return ewr.g2j(d.year, d.month, d.day)[0]


def analyze_fund(m: dict, bench: dict, repl: dict, ys: dict) -> dict | None:
    sym = m["symbol"]
    nd = load_nav(sym)
    if nd is None or nd.empty:
        return None
    has = lambda c: nd.get(c) is not None and nd[c].notna().sum() > 30
    col = "nav_cancel" if has("nav_cancel") else "nav_stat" if has("nav_stat") else "ret_daily" if has("ret_daily") else None
    if col is None:
        return None
    k = m["benchmark"]
    btr = bench[k]
    if col == "ret_daily":      # بازده روزانهٔ منتشرشدهٔ فیپیران (dailyEfficiency)؛ مقیاس خودکار: درصد یا کسر
        x = nd.ret_daily.dropna()
        x = x / 100 if x.abs().median() > 0.05 else x
        x = x[x.index >= x.index[0] + pd.Timedelta(days=WARMUP_DAYS)]
        fr = x.reindex(btr.index.intersection(x.index))
    else:
        fr = fund_returns(nd[col], btr.index)
    # رویدادهای واحد
    a = (fr - btr.reindex(fr.index)).dropna()
    ev = a[a.abs() > EVENT]
    flags = a[(a.abs() > FLAG) & (a.abs() <= EVENT)]
    fr = fr.copy()
    fr[ev.index] = btr.reindex(ev.index)
    out = {"symbol": sym, "name": m["name"], "benchmark": k, "benchmark_src": m.get("benchmark_src", "declared"),
           "nav_col": col, "nav_source": m.get("nav_source", ""), "nav_from": str(nd.index[0].date()), "nav_to": str(nd.index[-1].date()),
           "events": [[str(d.date()), r(v * 100, 1)] for d, v in ev.items()],
           "flags": [[str(d.date()), r(v * 100, 1)] for d, v in flags.items()][:30]}
    last = fr.index[-1]
    wins = {"all": fr.index[0], "3y": last - pd.DateOffset(years=3), "1y": last - pd.DateOffset(years=1)}
    out["win"] = {}
    for w, start in wins.items():
        f = fr[fr.index > start]
        if len(f) < 40:
            continue
        x = {"tr": metrics(f, btr)}
        if k in repl:
            x["rep"] = metrics(f, repl[k])
            x["lag_cost"] = metrics(repl[k][repl[k].index > start].reindex(f.index).dropna(), btr).get("td")
        for kk, s in bench.items():                                    # مرجع با بهترین برازش
            x.setdefault("fit", {})[kk] = metrics(f, s).get("te_w")
        out["win"][w] = x
    fit = out["win"]["all"]["fit"]
    out["best_fit"] = min((v, kk) for kk, v in fit.items() if v is not None)[1]
    # ریشهٔ خطا: تأخیر سود یا چیز دیگر؟ (fund_diagnostics.py)
    out["divtest"] = fd.divlag_test(fr, btr, ys[k])
    out["holdings"] = ah.analyze(sym, fr, btr) if (FUNDS / f"holdings_{sym}.csv").exists() else None   # پرتفوی کدال (اگر parse شده باشد)
    out["season"] = fd.seasonality(fr, btr, lambda d: ewr.g2j(d.year, d.month, d.day)[1])
    # سری روزانه برای زوم و محاسبهٔ خطا در هر بازهٔ دلخواه (UI)
    jd_ = pd.concat([fr, btr], axis=1, join="inner").dropna()
    rp_ = repl[k].reindex(jd_.index) if k in repl else None
    out["daily"] = {"d": [d.strftime("%y%m%d") for d in jd_.index], "f": [round(float(v), 6) for v in jd_.iloc[:, 0]],
                    "b": [round(float(v), 6) for v in jd_.iloc[:, 1]],
                    "r": [None if pd.isna(v) else round(float(v), 6) for v in rp_] if rp_ is not None else None}
    # سال شمسی
    j = pd.concat([fr, btr], axis=1, join="inner").dropna()
    j.columns = ["f", "b"]
    out["yearly"] = [{"jy": int(y), "f": r(((1 + g.f).prod() - 1) * 100, 1), "b": r(((1 + g.b).prod() - 1) * 100, 1),
                      "d": r((((1 + g.f).prod() / (1 + g.b).prod()) - 1) * 100, 2), "te": r((g.f - g.b).std() * np.sqrt(252) * 100, 2), "days": len(g)}
                     for y, g in j.groupby(j.index.map(jyear))]
    # منحنی‌ها (هفتگی)
    idx = sorted(set(list(range(0, len(j), 5)) + [len(j) - 1]))
    lvl_f, lvl_b = (1 + j.f).cumprod() * 100, (1 + j.b).cumprod() * 100
    cur = {"dates": [str(j.index[i].date()) for i in idx], "f": [r(lvl_f.iloc[i], 2) for i in idx], "b": [r(lvl_b.iloc[i], 2) for i in idx]}
    if k in repl:
        rp = repl[k].reindex(j.index).fillna(0)
        lv = (1 + rp).cumprod() * 100
        cur["rep"] = [r(lv.iloc[i], 2) for i in idx]
    roll = (j.f - j.b).rolling(63).std() * np.sqrt(252) * 100
    cur["te63"] = [r(roll.iloc[i], 2) for i in idx]
    out["curve"] = cur
    # قیمت بازار در برابر NAV
    pr = load_price(sym)
    nav_lvl = None
    if col == "ret_daily" and m.get("last_cancel_nav") and m.get("last_nav_date"):
        # سطح NAV از بازده روزانه، لنگرشده به آخرین NAV ابطال فیپیران: NAV_t = NAV_آخر ÷ Π(1+r بعد از t)
        x_ = (nd.ret_daily.dropna() / 100 if nd.ret_daily.abs().median() > 0.05 else nd.ret_daily.dropna())
        x_ = x_[x_.index <= pd.Timestamp(m["last_nav_date"])]
        after = (1 + x_)[::-1].cumprod()[::-1].shift(-1).fillna(1.0)
        nav_lvl = float(m["last_cancel_nav"]) / after
    if pr is not None and not pr.empty and (col != "ret_daily" or nav_lvl is not None):
        px = pr.close.where(pr.close > 0)
        src_ = nav_lvl if nav_lvl is not None else nd[col]
        nv = src_.reindex(px.index.union(src_.index)).ffill(limit=3).reindex(px.index)
        prem = (px / nv - 1).dropna()
        prem = prem[prem.abs() < 0.5]                     # تجزیهٔ واحد در قیمت بازار (سطح ناسازگار) کنار می‌رود
        prem = prem[prem.index >= nd.index[0] + pd.Timedelta(days=WARMUP_DAYS)]
        if nav_lvl is not None:
            # فقط پریمیوم لحظه‌ای: قیمت پایانی همان روزِ آخرین NAV ابطال ÷ آن NAV − ۱. سطح NAV بازسازی‌شده از بازده روزانه با بازگشت
            # در زمان خطا انباشته می‌کند (آزموده شد: میانگین ۹۰ روزه تا ۸٪ انحراف) و برای آمار پریمیوم قابل اتکا نیست.
            d0 = pd.Timestamp(m["last_nav_date"])
            ppx = px[px.index <= d0].dropna()
            if len(ppx) and (d0 - ppx.index[-1]).days <= 4:
                out["premium"] = {"last": r((ppx.iloc[-1] / float(m["last_cancel_nav"]) - 1) * 100), "mean": None, "std": None, "n": 1,
                                  "from": str(ppx.index[-1].date()), "adv_1y": r(pr.value[pr.index > pr.index[-1] - pd.DateOffset(years=1)].mean() / 1e10, 1)}
        elif len(prem) > 20:
            p1 = prem[prem.index > prem.index[-1] - pd.DateOffset(years=1)]
            out["premium"] = {"mean": r(prem.mean() * 100), "std": r(prem.std() * 100), "abs1": r((prem.abs() > 0.01).mean() * 100, 0),
                              "mean_1y": r(p1.mean() * 100), "last": r(prem.iloc[-1] * 100), "n": len(prem), "from": str(prem.index[0].date()),
                              "adv_1y": r(pr.value[pr.index > pr.index[-1] - pd.DateOffset(years=1)].mean() / 1e10, 1)}
            pm = prem.reindex(prem.index.union(pd.DatetimeIndex(cur["dates"]))).ffill(limit=5).reindex(pd.DatetimeIndex(cur["dates"]))
            out["curve"]["prem"] = [r(v * 100, 2) for v in pm]
            prr = px.pct_change().dropna()
            prr = prr[prr.index.isin(fr.index)]
            out["price_te"] = metrics(prr, btr).get("te_w")
    if col == "ret_daily":
        out["nav_col_note"] = "dailyEfficiency"
        if nav_lvl is not None:
            out["last_nav"] = [m["last_nav_date"], float(m["last_cancel_nav"])]
    if nd.get("aum") is not None and nd.aum.notna().any():
        out["aum_bn"] = r(nd.aum.dropna().iloc[-1] / 1e9, 0)          # خالص دارایی، میلیارد ریال
    return out


def replica_reference(bench: dict, repl: dict) -> list:
    """ماکت SIM (بازتولید کامل، بدون کارمزد، سود با تأخیر ۹۰ روز) در برابر TR رسمی، ۳ سال اخیر."""
    rows = []
    for k in repl:
        b = bench[k]
        last = b.index[-1]
        f = repl[k][repl[k].index > last - pd.DateOffset(years=3)]
        rows.append({"benchmark": k, **metrics(f, b)})
    return rows


def issue_navs() -> dict:
    """آخرین NAV ابطال هر صندوق از پاسخ خام فیپیران (fundlistissue): regNo → (NAV، تاریخ)."""
    p = ROOT / "data" / "raw" / "funds" / "fipiran_fund_fundlistissue.json"
    out = {}
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        rows = next((v for v in d.values() if isinstance(v, list)), []) if isinstance(d, dict) else d
        for r_ in rows:
            if r_.get("cancelNav") and r_.get("date"):
                out[str(r_["regNo"])] = (float(r_["cancelNav"]), str(r_["date"])[:10])
    return out


def main():
    iss = issue_navs()
    ys = {"K": ir.load_pair("K").y, "EW": ir.load_pair("EW").y}
    ys["I30"] = ys["K"]            # برای شاخص ۳۰ شرکت، نسخهٔ قیمتی جدا نداریم؛ بازده سود «شاخص كل» جانشین است
    bench = {k: ew.official(c) for k, (c, _) in BENCH.items()}
    repl = {}
    for k in ("K", "EW"):
        j = ir.load_pair(k)
        nav = ir.simulate(j, LAG)
        repl[k] = nav.pct_change().fillna(nav.iloc[0] - 1)
    rows = pd.read_csv(FUNDS / "funds.csv", dtype=str).fillna("").to_dict("records") if (FUNDS / "funds.csv").exists() else []
    if not rows:                                  # هنوز دادهای نیامده: صندوق‌های شناخته‌شدهٔ مخزن (بدون NAV)
        import fetch_index_funds as fx
        rows = [{"symbol": x["symbol"], "name": x["name"], "benchmark": x["benchmark"], "benchmark_src": x["benchmark_src"]} for x in fx.discover_local()]
    funds, missing = [], []
    for m in rows:
        if not m.get("last_cancel_nav") and m.get("fipiran_regno") in iss:
            m["last_cancel_nav"], m["last_nav_date"] = iss[m["fipiran_regno"]]
        res = analyze_fund(m, bench, repl, ys)
        (funds.append(res) if res else missing.append({"symbol": m["symbol"], "name": m["name"], "benchmark": m["benchmark"]}))
        if res:
            t = res["win"].get("all", {})
            print(f"{m['symbol']:8s} {m['benchmark']:4s} TE_w={t.get('tr', {}).get('te_w')}% TD={t.get('tr', {}).get('td')}% "
                  f"TD_vs_rep={t.get('rep', {}).get('td')}% best_fit={res['best_fit']} events={len(res['events'])}")
    data = {"built": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "lag": LAG,
            "bench_names": {k: v[1] for k, v in BENCH.items()}, "funds": funds, "missing": missing,
            "reference": replica_reference(bench, repl)}
    OUT.write_text("window.SIM_FUNDS = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"ذخیره شد: {OUT} — {len(funds)} صندوق با NAV، {len(missing)} بدون NAV")


if __name__ == "__main__":
    main()
