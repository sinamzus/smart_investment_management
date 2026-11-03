#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تفکیک فاکتوری صندوق‌های سهامی (Fund factor attribution) — فصل ۷ §۷٫۹ → ui/data/fund_attr.js (window.SIM_FATTR)

    python tools/fund_attribution.py                      # پس از tools/fetch_active_funds.py (و برای بخش پرتفو: parse_fund_portfolio.py)
    python tools/fund_attribution.py --refactor           # سری روزانهٔ فاکتورها را هم از نو بساز (پیش‌فرض: data/derived/factors_daily.csv اگر به‌روز است)

دو نگاه مکمل:
۱. بر پایهٔ بازده (returns-based): بازده هفتگی صندوق منهای نرخ بدون ریسک روی شش فاکتور رگرس می‌شود:
       R_f − rf = α + β_MKT·(R_K − rf) + β_SMB·SMB + β_HML·HML + β_MOM·MOM + β_LV·LV + β_ILQ·ILQ + e
   MKT = «شاخص كل» بازده کل رسمی. پنج فاکتور دیگر سبدهای صفر-هزینهٔ بلند−کوتاه با مرتب‌سازی دوگانهٔ ۲×۳ (Fama–French):
   اندازه در میانه × معیار در صدک ۳۰ و ۷۰؛ وزن ارزش بازاری درون هر سبد؛ تشکیل در آخرین روز معاملاتی هر ماه شمسی (داده تا بستهٔ همان روز)،
   نگه‌داری (خرید و نگه‌داری) تا پایان ماه بعد. جهان = نمادهای عملیاتی واجد بورس و فرابورس (همان جهان Lab؛ فصل ۲ §۲٫۰).
     SMB  کوچک − بزرگ (میانگین سه سبد کوچک − سه سبد بزرگ، روی هر چهار مرتب‌سازی)
     HML  ارزشی − رشدی: E/P بالا − E/P پایین (signals.ep؛ EPS سالانهٔ اعلام‌شده)
     MOM  برنده − بازنده: مومنتوم ۱۲−۱
     LV   کم‌نوسان − پرنوسان: نوسان ۲۵۲ روزه
     ILQ  نقدناپذیر − نقدشونده: نسبت آمیهود ۱۲۶ روزه (در بازار ایران با «اندازه» همبسته است؛ هر دو گزارش می‌شوند)
   هفتگی (آخرین روز معاملاتی پیش از شنبه) تا ناهمزمانی NAV و قیمت‌های صف‌دار کمتر شود؛ خطای معیار نیوی‌وست با ۴ وقفه.
   بتای دیمسون (β_MKT + β هفتهٔ قبل) جدا گزارش می‌شود: اگر بزرگ‌تر از β_MKT باشد، صندوق با تأخیر به بازار واکنش می‌دهد.
   سهم هر فاکتور از میانگین بازده مازاد (سالانهٔ حسابی، ×۵۲): β_f·mean(F_f)·۵۲؛ با α·۵۲ جمعشان دقیقاً mean(R_f − rf)·۵۲ است.
   بتاهای غلتان ۵۲ هفته‌ای رانش سبک (style drift) را نشان می‌دهد.
۲. بر پایهٔ پرتفو (holdings-based، اگر data/funds/holdings_<نماد>.csv هست): در هر گزارش ماهانهٔ کدال، میانگین وزنی امتیاز z
   (اندازه، E/P، مومنتوم، نوسان، آمیهود؛ استانداردشده روی همان جهان با میانگین وزن‌بازاری صفر) برای صندوق و «شاخص كل»؛ وزن صنایع،
   سهم سهام از کل دارایی، سهم فرابورس، تمرکز.
نرخ بدون ریسک پیش‌فرض RF_ANN سالانه [تأیید لازم]؛ در صفحه قابل‌تغییر است و رگرسیون در مرورگر دوباره حساب می‌شود.
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
warnings.filterwarnings("ignore", category=RuntimeWarning)          # میانگین برش خالی در معیارهای نمادهای کم‌داده
from attribution import ols_hac  # noqa: E402

ACTIVE = ROOT / "data" / "funds" / "active"
FUNDS = ROOT / "data" / "funds"
FAC_CSV = ROOT / "data" / "derived" / "factors_daily.csv"
OUT = ROOT / "ui" / "data" / "fund_attr.js"
RF_ANN = 0.30                     # نرخ بدون ریسک سالانه (بازده اسناد خزانه/صندوق درآمد ثابت) [تأیید لازم]
FAC_START = pd.Timestamp("2018-03-21")
EPOCH = pd.Timestamp("1970-01-01")
HAC_L = 4
ROLL = 52
FACTORS = [("MKT", "بازار («شاخص كل» − rf)"), ("SMB", "اندازه: کوچک − بزرگ"), ("HML", "ارزش: E/P بالا − پایین"),
           ("MOM", "مومنتوم: برنده − بازنده"), ("LV", "کم‌نوسان − پرنوسان"), ("ILQ", "نقدناپذیر − نقدشونده")]
SORTS = {"HML": ("ep", 1.0), "MOM": ("mom_12_1", 1.0), "LV": ("vol_252", 1.0), "ILQ": ("amihud", 1.0)}   # بالاتر = سبد بلند
CHARS = [("size", "اندازه (ln ارزش بازار)", 1.0), ("ep", "E/P", 1.0), ("mom_12_1", "مومنتوم ۱۲−۱", 1.0),
         ("vol_252", "نوسان", -1.0), ("amihud", "نقدناپذیری", 1.0)]                                     # علامت: z به زبان نام ستون (اندازه: ln ارزش بازار خام؛ vol_252 و ep از signals که نوسان را منفی می‌دهد)


# ═══════════════════ بازار و فاکتورها ═══════════════════
def load_market():
    import build_ui_extra as bx
    import signals as sg
    _, info, Ra = bx.base_panel(bx.ALL_MARKETS)
    Ra = bx.operating_view(Ra)
    mk = sg.Market(Ra, info)
    mk.fund = sg.load_fund(mk.cols, mk.dates)
    return mk


def bh_returns(X: np.ndarray, w: np.ndarray) -> np.ndarray:
    """بازده روزانهٔ سبد خرید و نگه‌داری با وزن آغازین w روی ردیف‌های X (بی‌داده = ۰، یعنی موقعیت منجمد)."""
    if w.sum() <= 0:
        return np.zeros(len(X))
    G = np.cumprod(1 + np.nan_to_num(X), axis=0)
    V = np.r_[1.0, (G * (w / w.sum())).sum(axis=1)]
    return V[1:] / V[:-1] - 1


def sort_2x3(size_v, sig_v, ok, mcap):
    """شش سبد (کوچک/بزرگ × پایین/میانه/بالا): فهرست اندیس‌ها و وزن ارزش بازاری؛ برش اندازه میانه، برش معیار صدک ۳۰ و ۷۰ (روی همهٔ واجدان)."""
    m = ok & np.isfinite(size_v) & np.isfinite(sig_v) & (mcap > 0)
    if m.sum() < 30:
        return None
    big = size_v >= np.median(size_v[m])
    lo, hi = np.percentile(sig_v[m], [30, 70])
    out = {}
    for sz, sm in (("S", ~big), ("B", big)):
        for g, gm in (("L", sig_v <= lo), ("M", (sig_v > lo) & (sig_v < hi)), ("H", sig_v >= hi)):
            out[sz + g] = np.where(m & sm & gm)[0]
    return out


def build_factors(mk) -> pd.DataFrame:
    """سری روزانهٔ SMB، HML، MOM، LV، ILQ از FAC_START تا آخرین روز پانل."""
    import signals as sg
    me = [int(a) for a in mk.month_end if mk.dates[a] >= FAC_START - pd.Timedelta(days=40) and a >= sg.WARM]
    ends = me + [mk.n - 1]
    rows = []
    for a, b in zip(ends[:-1], ends[1:]):
        ok = mk.eligible(a, require_trade=True)
        mc = np.nan_to_num(mk.mcap[a])
        lsz = np.log(np.where(mc > 0, mc, np.nan))
        X = mk.X[a + 1:b + 1]
        legs = {}
        smb = []
        for code, (sig, sgn) in SORTS.items():
            v = getattr(sg, sig)(mk, a)
            if v is None:
                legs[code] = None
                continue
            P = sort_2x3(lsz, sgn * np.asarray(v, float), ok, mc)
            if P is None:
                legs[code] = None
                continue
            R = {k: bh_returns(X[:, ix], mc[ix]) for k, ix in P.items()}
            legs[code] = 0.5 * (R["SH"] + R["BH"]) - 0.5 * (R["SL"] + R["BL"])
            smb.append((R["SL"] + R["SM"] + R["SH"]) / 3 - (R["BL"] + R["BM"] + R["BH"]) / 3)
        d = {"SMB": np.mean(smb, axis=0) if smb else np.full(b - a, np.nan)}
        for code in SORTS:
            d[code] = legs[code] if legs[code] is not None else np.full(b - a, np.nan)
        rows.append(pd.DataFrame(d, index=mk.dates[a + 1:b + 1]))
    F = pd.concat(rows)
    return F[F.index >= FAC_START]


def market_series(dates) -> pd.Series:
    import investable_replica as ir
    return ir.load_pair("K").tr.reindex(dates)


# ═══════════════════ صندوق ═══════════════════
def fund_daily(sym: str) -> pd.Series:
    """بازده روزانهٔ NAV (فیپیران، درصد یا کسر) بدون ردیف‌های خالی."""
    p = ACTIVE / f"nav_{sym}.csv"
    if not p.exists():
        p = FUNDS / f"nav_{sym}.csv"
    d = pd.read_csv(p, parse_dates=["date"]).set_index("date")
    x = d.ret_daily.dropna()
    return (x / 100 if x.abs().median() > 0.05 else x).astype(float)


def week_id(dates) -> np.ndarray:
    return ((pd.DatetimeIndex(dates) - EPOCH).days.values - 2) // 7        # ۱۹۷۰-۰۱-۰۳ شنبه است


def weekly(fund: pd.Series, mkt: pd.Series, F: pd.DataFrame, open_days: pd.DatetimeIndex, skip_days: int = 60):
    """هم‌ترازی هفتگی: بازده مرکب هر هفتهٔ شمسی (شنبه تا جمعه) برای صندوق، بازار و فاکتورها. هفتهٔ بدون روز باز بازار کنار می‌رود.
    دو ماه نخست عمر صندوق (تشکیل سبد) کنار می‌رود. خروجی: DataFrame با ستون‌های y (صندوق)، MKT_raw، فاکتورها، days (روز تقویمی هفته)."""
    start = fund.index.min() + pd.Timedelta(days=skip_days)
    fund = fund[fund.index >= start]
    lo, hi = fund.index.min(), min(fund.index.max(), mkt.dropna().index.max(), F.dropna(how="all").index.max())
    D = pd.DataFrame({"y": fund}).join(pd.DataFrame({"MKT_raw": mkt}), how="outer").join(F, how="outer")
    D = D[(D.index >= lo) & (D.index <= hi)]
    D["open"] = D.index.isin(open_days)
    D["w"] = week_id(D.index)
    g = D.groupby("w")
    cols = ["y", "MKT_raw"] + list(F.columns)
    W = g[cols].apply(lambda x: (1 + x.fillna(0)).prod() - 1)
    W["n_open"] = g.open.sum()
    W["end"] = g.apply(lambda x: x.index.max())
    W = W[W.n_open > 0]
    W = W.set_index("end")
    W["days"] = np.r_[7, np.diff(W.index.values).astype("timedelta64[D]").astype(int)]
    return W.drop(columns="n_open")


def regress(W: pd.DataFrame, rf_ann: float, codes=None) -> dict:
    codes = codes or [c for c, _ in FACTORS]
    rf = (1 + rf_ann) ** (W.days.values / 365.0) - 1
    y = W.y.values - rf
    F = np.column_stack([W.MKT_raw.values - rf if c == "MKT" else W[c].values for c in codes])
    ok = np.isfinite(y) & np.isfinite(F).all(axis=1)
    y, F = y[ok], F[ok]
    b, se, r2 = ols_hac(y, F, HAC_L)
    t = b / np.where(se > 0, se, np.nan)
    e = y - np.column_stack([np.ones(len(y)), F]) @ b
    mF = F.mean(axis=0)
    # بتای دیمسون: MKT هفتهٔ جاری + هفتهٔ قبل
    Fl = np.column_stack([F, np.r_[np.nan, F[:-1, 0]]])[1:]
    bd, sed, _ = ols_hac(y[1:], Fl, HAC_L)
    k = len(codes)
    return {"weeks": int(len(y)), "alpha_ann": float(52 * 100 * b[0]), "alpha_t": float(t[0]), "r2": float(r2),
            "resid_vol_ann": float(100 * e.std(ddof=k + 1) * np.sqrt(52)), "excess_ann": float(52 * 100 * y.mean()),
            "vol_ann": float(100 * y.std(ddof=1) * np.sqrt(52)),
            "dimson_beta": float(bd[1] + bd[k + 1]), "dimson_lag": float(bd[k + 1]), "dimson_lag_t": float(bd[k + 1] / sed[k + 1]) if sed[k + 1] > 0 else None,
            "factors": [{"code": c, "beta": float(b[i + 1]), "t": float(t[i + 1]), "factor_ann": float(52 * 100 * mF[i]),
                         "contrib_ann": float(52 * 100 * b[i + 1] * mF[i])} for i, c in enumerate(codes)]}


def rolling(W: pd.DataFrame, rf_ann: float, n: int = ROLL) -> dict:
    out = {"end": [], "beta": {c: [] for c, _ in FACTORS}, "alpha_ann": [], "r2": []}
    for i in range(n, len(W) + 1):
        r = regress(W.iloc[i - n:i], rf_ann)
        out["end"].append(str(W.index[i - 1].date()))
        for f in r["factors"]:
            out["beta"][f["code"]].append(round(f["beta"], 3))
        out["alpha_ann"].append(round(r["alpha_ann"], 2))
        out["r2"].append(round(r["r2"], 3))
    return out


# ═══════════════════ پرتفو ═══════════════════
def zscore(v, ok, w):
    """z با میانگین وزن‌بازاری صفر و انحراف معیار مقطعی (برش ۱ و ۹۹ درصد) روی واجدان."""
    m = ok & np.isfinite(v)
    if m.sum() < 30:
        return np.full(len(v), np.nan)
    lo, hi = np.percentile(v[m], [1, 99])
    x = np.clip(v, lo, hi)
    mu = np.average(x[m], weights=w[m])
    sd = x[m].std()
    return np.where(m, (x - mu) / (sd if sd > 0 else 1), np.nan)


def holdings_view(mk, sym: str) -> dict | None:
    import signals as sg
    p = FUNDS / f"holdings_{sym}.csv"
    if not p.exists():
        return None
    H = pd.read_csv(p, parse_dates=["date"])
    if "weight_src" in H:                                                  # ماهِ بازسازی‌شده از ارزش (جدول تکراری در Excel، نقد نامعلوم) کنار می‌رود
        H = H[H.weight_src != "value_norm"]
    pos = {}
    for i, s in enumerate(mk.sym):
        pos.setdefault(str(s), i)
    kw = np.where(np.asarray(mk.market) == "bourse", 1.0, 0.0)               # «شاخص كل»: ارزش بازاری بورس
    reps = []
    for d, h in H.groupby("date"):
        a = int(mk.dates.searchsorted(d, side="right")) - 1
        if a < 260:
            continue
        ok = mk.eligible(a, require_trade=False)
        mc = np.nan_to_num(mk.mcap[a])
        Z = {}
        for nm, _, sgn in CHARS:
            v = np.log(np.where(mc > 0, mc, np.nan)) if nm == "size" else getattr(sg, nm)(mk, a)
            Z[nm] = np.full(mk.k, np.nan) if v is None else zscore(sgn * np.asarray(v, float), ok, mc)
        h = h.assign(i=h.symbol.astype(str).map(pos))
        stock = h[h.i.notna()].groupby("i").weight_pct.sum()
        ix = stock.index.astype(int).values
        w = stock.values / 100
        bw = mc * kw * (mc > 0)
        bw = bw / bw.sum()
        expo = {}
        for nm, _, _ in CHARS:
            z = Z[nm]
            f_ok = np.isfinite(z[ix])
            b_ok = np.isfinite(z) & (bw > 0)
            expo[nm] = {"fund": float(np.average(z[ix][f_ok], weights=w[f_ok])) if f_ok.any() else None,
                        "index": float(np.average(z[b_ok], weights=bw[b_ok])) if b_ok.any() else None,
                        "cover": float(w[f_ok].sum() / w.sum()) if w.sum() > 0 else 0.0}
        sec = mk.sector_at(a)
        fs = pd.Series(w, index=sec[ix]).groupby(level=0).sum() / w.sum()
        bs = pd.Series(bw, index=sec).groupby(level=0).sum()
        allsec = sorted(set(fs.index) | set(bs[bs > 0.002].index), key=lambda s: -(fs.get(s, 0) - bs.get(s, 0)))
        o = np.argsort(-w)
        reps.append({"date": str(pd.Timestamp(d).date()), "equity_pct": round(float(h.weight_pct.sum()), 2),
                     "matched_pct": round(float(stock.sum()), 2), "n": int(len(ix)),
                     "fara_pct": round(float(100 * w[np.asarray(mk.market)[ix] == "farabourse"].sum() / max(w.sum(), 1e-12)), 1),
                     "top10_pct": round(float(100 * np.sort(w)[::-1][:10].sum() / max(w.sum(), 1e-12)), 1),
                     "expo": expo,
                     "sectors": [{"s": str(s), "f": round(100 * float(fs.get(s, 0)), 2), "b": round(100 * float(bs.get(s, 0)), 2)} for s in allsec],
                     "top": [{"s": str(mk.sym[ix[j]]), "w": round(100 * float(w[j] / w.sum()), 2), "sec": str(sec[ix[j]]),
                              "z": {nm: (None if not np.isfinite(Z[nm][ix[j]]) else round(float(Z[nm][ix[j]]), 2)) for nm, _, _ in CHARS}}
                             for j in o[:15]]})
    return {"reports": reps, "chars": [{"code": c, "fa": fa} for c, fa, _ in CHARS]} if reps else None


# ═══════════════════ اجرا ═══════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refactor", action="store_true")
    ap.add_argument("--rf", type=float, default=RF_ANN)
    a = ap.parse_args()
    mk = load_market()
    last = mk.dates[-1]
    if a.refactor or not FAC_CSV.exists() or pd.read_csv(FAC_CSV, usecols=["date"]).date.max() < str(last.date()):
        print("ساخت سری روزانهٔ فاکتورها …", flush=True)
        F = build_factors(mk)
        FAC_CSV.parent.mkdir(parents=True, exist_ok=True)
        F.round(7).to_csv(FAC_CSV, index_label="date")
    F = pd.read_csv(FAC_CSV, parse_dates=["date"]).set_index("date")
    print(f"فاکتورها: {F.index.min().date()} تا {F.index.max().date()}؛ میانگین سالانه (٪): "
          + "، ".join(f"{c} {100 * ((1 + F[c].fillna(0)).prod() ** (252 / len(F)) - 1):.1f}" for c in F.columns))
    print("همبستگی روزانهٔ فاکتورها:\n" + F.corr().round(2).to_string())
    open_days = mk.dates[[mk.market_open(d) for d in range(mk.n)]]
    K = market_series(mk.dates)
    meta = pd.read_csv(ACTIVE / "funds.csv", dtype=str)
    funds = {}
    for m in meta.to_dict("records"):
        sym = m["symbol"]
        W = weekly(fund_daily(sym), K, F, open_days)
        res = regress(W, a.rf)
        res_k = regress(W, a.rf, ["MKT"])
        print(f"\n══ {sym}: {res['weeks']} هفته ({W.index.min().date()} تا {W.index.max().date()})")
        print(f"  بازده مازاد سالانه {res['excess_ann']:.1f}٪، α {res['alpha_ann']:.1f}٪ (t={res['alpha_t']:.2f})، R² {res['r2']:.2f} (فقط بازار {res_k['r2']:.2f})، "
              f"بتای دیمسون {res['dimson_beta']:.2f}")
        for f in res["factors"]:
            print(f"  {f['code']:4s} β={f['beta']:+.2f} t={f['t']:+.2f}  فاکتور {f['factor_ann']:+.1f}٪  سهم {f['contrib_ann']:+.1f}٪")
        hv = holdings_view(mk, sym)
        if hv:
            r0 = hv["reports"][-1]
            print(f"  پرتفو {r0['date']}: سهام {r0['equity_pct']}٪، {r0['n']} نماد، فرابورس {r0['fara_pct']}٪، ده‌تای اول {r0['top10_pct']}٪")
            for nm, e in r0["expo"].items():
                print(f"    z {nm:9s} صندوق {e['fund'] if e['fund'] is None else round(e['fund'], 2)}  شاخص {e['index'] if e['index'] is None else round(e['index'], 2)}")
        funds[sym] = {"name": m["name"], "style": m.get("style", ""), "start": str(W.index.min().date()), "end": str(W.index.max().date()),
                      "y": [round(float(x), 6) for x in W.y.values], "w_end": [str(d.date()) for d in W.index], "days": W.days.astype(int).tolist(),
                      "F": {c: [None if x != x else round(float(x), 6) for x in W[c].values] for c in ["MKT_raw", *F.columns]},
                      "result": res, "market_only": res_k, "rolling": rolling(W, a.rf), "holdings": hv}
    out = {"asof": str(last.date()), "rf_ann": a.rf, "hac_lags": HAC_L, "roll": ROLL, "factors": [{"code": c, "fa": fa} for c, fa in FACTORS],
           "funds": funds}
    OUT.write_text("window.SIM_FATTR = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"\n→ {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
