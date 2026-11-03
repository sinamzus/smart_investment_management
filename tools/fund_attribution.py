#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""تفکیک فاکتوری صندوق‌های سهامی (Fund factor attribution) — فصل ۷ §۷٫۹ → ui/data/fund_attr.js (window.SIM_FATTR)

    python tools/fund_attribution.py                      # پس از tools/fetch_active_funds.py (و برای بخش پرتفو: parse_fund_portfolio.py)
    python tools/fund_attribution.py --refactor           # سری روزانهٔ فاکتورها را هم از نو بساز (پیش‌فرض: data/derived/factors_daily.csv اگر به‌روز است)

دو نگاه مکمل:
۱. بر پایهٔ بازده (returns-based): بازده هفتگی صندوق (از سطح NAV ابطال) منهای نرخ بدون ریسک روی شش فاکتور رگرس می‌شود:
       R_f − rf = α + β_MKT·(R_K − rf) + β_SMB·SMB + β_HML·HML + β_MOM·MOM + β_LV·LV + β_ILQ·ILQ + e
   MKT = «شاخص كل» بازده کل رسمی. پنج فاکتور دیگر سبدهای صفر-هزینهٔ بلند−کوتاه با مرتب‌سازی دوگانهٔ ۲×۳ (Fama–French):
   اندازه در میانه × معیار در صدک ۳۰ و ۷۰ درون هر نیمهٔ اندازه (وابسته)، دست‌کم ۱۰ نماد در هر سبد؛ وزن ارزش بازاری درون هر سبد؛ تشکیل در آخرین روز معاملاتی هر ماه شمسی (داده تا بستهٔ همان روز)،
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
۳. مهارت (مدل ۵ فاکتوری تاریخچهٔ کامل): آلفا و ماندگاری، زمان‌بندی تریِنر–مازویی، سبک غالب؛ و آزمون شانس یا مهارت روی همهٔ صندوق‌های
   سهامی با دست‌کم MIN_SKILL_W هفته (بوت‌استرپ Fama–French 2010، π و FDR به روش Barras–Scaillet–Wermers 2010).
خروجی: خلاصهٔ همهٔ صندوق‌ها در ui/data/fund_attr.js و جزئیات هفتگی هر صندوق در ui/data/fattr/<شمارهٔ ثبت>.js.
نرخ بدون ریسک هر هفته: بازده تا سررسید اخزا (data/derived/rf_daily.csv از tools/build_rf.py، فصل ۷ §۷٫۱۰) در آخرین روز پیش از شروع هفته؛
اگر آن فایل نبود یا --rf داده شد، نرخ ثابت RF_ANN [تأیید لازم]. در صفحه می‌شود به نرخ ثابت رفت و رگرسیون در مرورگر دوباره حساب می‌شود.
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
DET = ROOT / "ui" / "data" / "fattr"            # جزئیات هفتگی هر صندوق، بارگذاری هنگام انتخاب: <شمارهٔ ثبت>.js
RF_ANN = 0.30                     # نرخ ثابت جایگزین وقتی سری اخزا نیست [تأیید لازم]
RF_CSV = ROOT / "data" / "derived" / "rf_daily.csv"
FAC_START = pd.Timestamp("2018-03-21")
EPOCH = pd.Timestamp("1970-01-01")
HAC_L = 4
MIN_BUCKET = 10                   # کمترین شمار نماد در هر سبد ۲×۳
CLOSE_DAYS = 14                   # هفتهٔ با فاصلهٔ بیش از این تا هفتهٔ باز قبلی = تعطیلی سراسری؛ نوروز (تا ۱۰ روز بسته، هفتهٔ ۱۴ روزه) می‌ماند
POST_CLOSE = 2                    # هفته‌های پس از بازگشایی که کنار می‌روند
MAX_GAP = 7                       # فاصلهٔ بیش از این (روز تقویمی) میان دو سطح NAV: بازدهٔ آن فاصله کنار می‌رود
ROLL = 52
MIN_SKILL_W = 104                 # کمترین هفته در مدل ۵ فاکتوری برای ورود به آزمون شانس یا مهارت [تأیید لازم]
N_BOOT = 1000
GAMMA = 0.10                      # سطح دوطرفهٔ آزمون در شمارش مثبت/منفی معنادار و FDR
FIP_LIST = ROOT / "data" / "raw" / "funds" / "fipiran_fund_fundcompare.json"
CHECK_TOL, CHECK_TOL_CUM = 0.05, 0.15   # راستی‌آزمایی با بازده اعلامی فیپیران: ۱۲ ماهه و از آغاز [تأیید لازم]
FACTORS = [("MKT", "بازار («شاخص كل» − rf)"), ("SMB", "اندازه: کوچک − بزرگ"), ("HML", "ارزش: E/P بالا − پایین"),
           ("MOM", "مومنتوم: برنده − بازنده"), ("LV", "کم‌نوسان − پرنوسان"), ("ILQ", "نقدناپذیر − نقدشونده")]
C5 = [c for c, _ in FACTORS if c != "HML"]                             # مدل تاریخچهٔ کامل (HML از مهر ۱۴۰۳)
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
    """شش سبد (کوچک/بزرگ × پایین/میانه/بالا): فهرست اندیس‌ها. برش اندازه میانه؛ برش معیار صدک ۳۰ و ۷۰ **درون هر نیمهٔ اندازه**
    (مرتب‌سازی وابسته). در ایران اندازه و نقدناپذیری (و کمتر، نوسان) چنان همبسته‌اند که با برش مستقل گوشهٔ «کوچک و نقدشونده»
    ۰ تا ۲۳ نماد داشت و سبد خالی بازده صفر می‌داد (ممیزی ۲۰۲۶-۱۱-۰۳). اگر سبدی کمتر از MIN_BUCKET نماد داشت، None."""
    m = ok & np.isfinite(size_v) & np.isfinite(sig_v) & (mcap > 0)
    if m.sum() < 6 * MIN_BUCKET:
        return None
    big = size_v >= np.median(size_v[m])
    out = {}
    for sz, sm in (("S", ~big), ("B", big)):
        lo, hi = np.percentile(sig_v[m & sm], [30, 70])
        for g, gm in (("L", sig_v <= lo), ("M", (sig_v > lo) & (sig_v < hi)), ("H", sig_v >= hi)):
            out[sz + g] = np.where(m & sm & gm)[0]
    return out if min(len(v) for v in out.values()) >= MIN_BUCKET else None


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
def fund_daily(sym: str, gaps: bool = True) -> pd.Series:
    """بازده روزانهٔ صندوق از سطح NAV ابطال (فیپیران getfundchart). ستون ret_daily (dailyEfficiency) در روزهایی که NAV به‌روز
    نشده ۰ است و آن حرکت گم می‌شود (ممیزی ۲۰۲۶-۱۱-۰۳). ret_daily فقط دو جا جای سطح را می‌گیرد:
      تقسیم یا تجمیع واحد (بازده سطح ≤ −۴۵٪ یا ≥ +۱۰۰٪): ret_daily اگر باورپذیر است (|x| < ۱۰٪)، وگرنه خالی. جهش‌های ۳۰ تا ۴۰٪ بازگشایی پس از
        تعطیلی جنگ واقعی‌اند و با بازده سالانهٔ اعلامی فیپیران جورند؛ مرز قبلی ۳۰٪ آن‌ها را حذف می‌کرد.
      تقسیم سود (صندوق‌های با پرداخت دوره‌ای): سطح بیش از ۲٪ می‌افتد، ret_daily (که سود پرداختی را دارد) دست‌کم ۱٫۵ واحد بالاتر است و
        در روز قبل و بعد با سطح هم‌خوان است (|اختلاف| < ۰٫۲ واحد؛ تا ret_daily خراب جای سطح را نگیرد).
    بازده روی فاصلهٔ بیش از MAX_GAP روز بین دو سطح NaN است. اگر سطح نبود، همان ret_daily (درصد یا کسر)."""
    p = next((d / f"nav_{sym}.csv{z}" for d in (ACTIVE, FUNDS) for z in ("", ".gz") if (d / f"nav_{sym}.csv{z}").exists()), ACTIVE / f"nav_{sym}.csv")
    d = pd.read_csv(p, parse_dates=["date"]).set_index("date").sort_index()
    eff = d.ret_daily
    eff = eff / 100 if eff.abs().median() > 0.05 else eff
    lv = d.nav_cancel.where(d.nav_cancel > 0).dropna() if "nav_cancel" in d else pd.Series(dtype=float)
    if len(lv) < 30:
        return eff.dropna().astype(float)
    r = lv.pct_change()
    e = eff.reindex(r.index)
    split = (r <= -0.45) | (r >= 1.0)
    agree = lambda k: (e.shift(k) - r.shift(k)).abs() < 0.002            # noqa: E731
    dist = (r < -0.02) & (e - r > 0.015) & ~split & agree(1) & agree(-1)
    r = r.where(~dist, e).where(~split, e.where(e.abs() < 0.1))
    gap = pd.Series(lv.index, index=lv.index).diff().dt.days
    return (r.where(gap <= MAX_GAP) if gaps else r).iloc[1:].astype(float)


def validate(sym: str, x: dict) -> dict:
    """راستی‌آزمایی سری بازده با عدد اعلامی فیپیران (fund/fundcompare): بازده ۱۲ ماهه (annualEfficiency) و از آغاز (efficiency، فقط اگر
    سری ما از آغاز صندوق است). ok = نسبت رشد ما به فیپیران در ±CHECK_TOL (۱۲ ماه) و ±CHECK_TOL_CUM (از آغاز)."""
    r = fund_daily(sym, gaps=False).fillna(0)
    out, end = {}, r.index[-1]
    if x.get("annualEfficiency") and r.index[0] <= end - pd.Timedelta(days=330):
        g = float((1 + r[r.index > end - pd.Timedelta(days=365)]).prod())
        out.update({"r12": round(100 * (g - 1), 1), "fip12": round(float(x["annualEfficiency"]), 1),
                    "ok12": bool(abs(g / (1 + x["annualEfficiency"] / 100) - 1) <= CHECK_TOL)})
    init = pd.Timestamp(x["initiationDate"][:10]) if x.get("initiationDate") else None
    if x.get("efficiency") and init is not None and abs((r.index[0] - init).days) <= 30:
        g = float((1 + r).prod())
        out.update({"rcum": round(100 * (g - 1)), "fipcum": round(float(x["efficiency"])),
                    "okcum": bool(abs(g / (1 + x["efficiency"] / 100) - 1) <= CHECK_TOL_CUM)})
    out["ok"] = out.get("ok12", True) and out.get("okcum", True)
    return out


def week_id(dates) -> np.ndarray:
    return ((pd.DatetimeIndex(dates) - EPOCH).days.values - 2) // 7        # ۱۹۷۰-۰۱-۰۳ شنبه است


def weekly(fund: pd.Series, mkt: pd.Series, F: pd.DataFrame, open_days: pd.DatetimeIndex, skip_days: int = 60):
    """هم‌ترازی هفتگی: بازده مرکب هر هفتهٔ شمسی (شنبه تا جمعه) برای صندوق، بازار و فاکتورها. هفتهٔ بدون روز باز بازار کنار می‌رود.
    دو ماه نخست عمر صندوق (تشکیل سبد) و هفته‌های پیش از آغاز فاکتورها کنار می‌رود؛ هفته‌ای که برای ستونی هیچ داده‌ای ندارد آن ستون را NaN دارد. خروجی: DataFrame با ستون‌های y (صندوق)، MKT_raw، فاکتورها، days (روز تقویمی هفته)."""
    start = fund.index.min() + pd.Timedelta(days=skip_days)
    fund = fund[fund.index >= start]
    lo, hi = max(fund.dropna().index.min(), F.dropna(how="all").index.min()), min(fund.index.max(), mkt.dropna().index.max(), F.dropna(how="all").index.max())
    D = pd.DataFrame({"y": fund}).join(pd.DataFrame({"MKT_raw": mkt}), how="outer").join(F, how="outer")
    D = D[(D.index >= lo) & (D.index <= hi)]
    if D.empty:                                                          # صندوق تازه‌تر از دادهٔ فاکتورها
        return pd.DataFrame(columns=["y", "MKT_raw", *F.columns, "days"], dtype=float)
    D["open"] = D.index.isin(open_days)
    D["w"] = week_id(D.index)
    g = D.groupby("w")
    cols = ["y", "MKT_raw"] + list(F.columns)
    # هفتهٔ بی‌دادهٔ یک ستون NaN است، نه صفر (پیش از ممیزی ۲۰۲۶-۱۱-۰۳ هفته‌های پیش از آغاز فاکتورها با فاکتور ۰ وارد رگرسیون می‌شدند)
    W = g[cols].apply(lambda x: (1 + x.fillna(0)).prod().where(x.notna().any()) - 1)
    W["n_open"] = g.open.sum()
    W["end"] = g.apply(lambda x: x.index.max())
    W = W[W.n_open > 0]
    W = W.set_index("end")
    W["days"] = np.r_[7, np.diff(W.index.values).astype("timedelta64[D]").astype(int)]
    # تعطیلی سراسری غیرعادی (جنگ خرداد ۱۴۰۴: ۱۷ روز؛ اسفند ۱۴۰۴ تا اردیبهشت ۱۴۰۵: ۸۳ روز): NAV صندوق‌ها در تعطیلی و بازگشایی ارزش‌گذاری می‌شود ولی
    # «شاخص كل» با صف و دامنهٔ نوسان هفته‌ها بعد می‌رسد؛ هفتهٔ دربرگیرندهٔ تعطیلی و POST_CLOSE هفتهٔ بعد کنار می‌رود (ممیزی ۲۰۲۶-۱۱-۰۳:
    # یک هفتهٔ بازگشایی بتای صندوق‌های شاخصی «شاخص كل» را به ۱٫۱۷ و β نقدناپذیری را به ۰٫۴ می‌برد).
    span = np.flatnonzero(W.days.values > CLOSE_DAYS)
    drop = np.unique(np.concatenate([span + k for k in range(POST_CLOSE + 1)])) if len(span) else np.array([], int)
    W = W.drop(index=W.index[drop[drop < len(W)]])
    return W.drop(columns="n_open")


def rf_weekly(W: pd.DataFrame) -> np.ndarray | None:
    """نرخ سالانهٔ اخزا برای هر هفته: آخرین نرخ معلوم تا پایان هفتهٔ قبل (پیش از شروع هفته)."""
    if not RF_CSV.exists():
        return None
    s = pd.read_csv(RF_CSV, parse_dates=["date"]).set_index("date").rf.dropna()
    start = W.index - pd.to_timedelta(W.days.values, unit="D")
    return s.reindex(s.index.union(start)).ffill().reindex(start).values.astype(float)


def regress(W: pd.DataFrame, rf_ann=None, codes=None, need=None) -> dict:
    """rf_ann: عدد ثابت، آرایهٔ هفتگی، یا None = ستون rf_ann درون W. need: ستون‌هایی که هفته باید برایشان داده داشته باشد
    (پیش‌فرض همهٔ فاکتورها، تا مدل «فقط بازار» روی همان هفته‌های مدل کامل برازش شود)."""
    codes = codes or [c for c, _ in FACTORS]
    need = need or [c for c, _ in FACTORS]
    rf_ann = W.rf_ann.values if rf_ann is None else rf_ann
    rf = (1 + rf_ann) ** (W.days.values / 365.0) - 1
    y = W.y.values - rf
    col = lambda c: W.MKT_raw.values - rf if c == "MKT" else W[c].values  # noqa: E731
    F = np.column_stack([col(c) for c in codes])
    ok = np.isfinite(y) & np.isfinite(np.column_stack([col(c) for c in need])).all(axis=1)
    lag = np.r_[np.nan, col("MKT")[:-1]]                               # MKT هفتهٔ قبل در ردیف‌های پیوستهٔ W (نه پس از حذف ردیف‌ها)
    lag_ok = ok & np.isfinite(lag)
    yl, Fl = y[lag_ok], np.column_stack([F[lag_ok], lag[lag_ok]])
    y, F = y[ok], F[ok]
    if len(y) < len(codes) + 10:                                       # همان کف ui/fattr.js
        return None
    b, se, r2 = ols_hac(y, F, HAC_L)
    t = b / np.where(se > 0, se, np.nan)
    e = y - np.column_stack([np.ones(len(y)), F]) @ b
    mF = F.mean(axis=0)
    # بتای دیمسون: MKT هفتهٔ جاری + هفتهٔ قبل
    bd, sed, _ = ols_hac(yl, Fl, HAC_L)
    k = len(codes)
    return {"weeks": int(len(y)), "alpha_ann": float(52 * 100 * b[0]), "alpha_t": float(t[0]), "r2": float(r2),
            "resid_vol_ann": float(100 * e.std(ddof=k + 1) * np.sqrt(52)), "excess_ann": float(52 * 100 * y.mean()),
            "vol_ann": float(100 * y.std(ddof=1) * np.sqrt(52)),
            "dimson_beta": float(bd[1] + bd[k + 1]), "dimson_lag": float(bd[k + 1]), "dimson_lag_t": float(bd[k + 1] / sed[k + 1]) if sed[k + 1] > 0 else None,
            "factors": [{"code": c, "beta": float(b[i + 1]), "t": float(t[i + 1]), "factor_ann": float(52 * 100 * mF[i]),
                         "contrib_ann": float(52 * 100 * b[i + 1] * mF[i])} for i, c in enumerate(codes)]}


def rolling(W: pd.DataFrame, rf_ann=None, n: int = ROLL, codes=None) -> dict:
    codes = codes or [c for c, _ in FACTORS]
    out = {"end": [], "beta": {c: [] for c in codes}, "alpha_ann": [], "r2": []}
    for i in range(n, len(W) + 1):
        r = regress(W.iloc[i - n:i], rf_ann, codes, codes)
        if r is None:
            continue
        out["end"].append(str(W.index[i - 1].date()))
        for f in r["factors"]:
            out["beta"][f["code"]].append(round(f["beta"], 3))
        out["alpha_ann"].append(round(r["alpha_ann"], 2))
        out["r2"].append(round(r["r2"], 3))
    return out


# ═══════════════════ مهارت ═══════════════════
def design(W: pd.DataFrame, codes) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """y (بازده مازاد)، X (فاکتورها به ترتیب codes) و شمارهٔ هفته (week_id) فقط برای هفته‌هایی که همه را دارند."""
    rf = (1 + W.rf_ann.values) ** (W.days.values / 365.0) - 1
    y = W.y.values - rf
    X = np.column_stack([W.MKT_raw.values - rf if c == "MKT" else W[c].values for c in codes])
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
    return y[ok], X[ok], week_id(W.index[ok])


def alpha_t(y, X) -> tuple[float, float]:
    b, se, _ = ols_hac(y, X, HAC_L)
    return float(b[0]), float(b[0] / se[0]) if se[0] > 0 else np.nan


def skill(W: pd.DataFrame) -> dict:
    """سنجه‌های مهارت روی مدل ۵ فاکتوری تاریخچهٔ کامل (بی‌HML):
    انتخاب سهم = α؛ ماندگاری = α نیمهٔ اول و دوم؛ زمان‌بندی بازار = γ تریِنر–مازویی (جملهٔ MKT²)؛ شرط سبکی = سهم فاکتورهای غیربازار."""
    y, X, _ = design(W, C5)
    n = len(y)
    out = {"weeks": int(n), "eligible": bool(n >= MIN_SKILL_W)}
    if n < len(C5) + 10:
        return out
    b, se, _ = ols_hac(y, X, HAC_L)
    t = b / np.where(se > 0, se, np.nan)
    e = y - np.column_stack([np.ones(n), X]) @ b
    rv = e.std(ddof=len(C5) + 1) * np.sqrt(52)
    mF = X.mean(axis=0)
    out.update({"alpha_ann": 5200 * b[0], "alpha_t": float(t[0]), "ir": float(52 * b[0] / rv) if rv > 0 else None,
                "vs_mkt_ann": 5200 * float(np.mean(y - X[:, 0])),                  # بازده صندوق منهای «شاخص كل» (خام، بی‌تعدیل ریسک)
                "style_ann": 5200 * float(sum(b[i + 1] * mF[i] for i, c in enumerate(C5) if c != "MKT")),
                "tilts": [{"code": c, "beta": float(b[i + 1]), "t": float(t[i + 1]), "contrib_ann": 5200 * float(b[i + 1] * mF[i])}
                          for i, c in enumerate(C5) if c != "MKT"]})
    h = n // 2                                                               # ماندگاری: دو نیمهٔ زمانی
    if h >= len(C5) + 10:
        (a1, t1), (a2, t2) = alpha_t(y[:h], X[:h]), alpha_t(y[h:], X[h:])
        out.update({"alpha1_ann": 5200 * a1, "alpha1_t": t1, "alpha2_ann": 5200 * a2, "alpha2_t": t2})
    bt, st, _ = ols_hac(y, np.column_stack([X, X[:, 0] ** 2]), HAC_L)      # تریِنر–مازویی (Treynor & Mazuy 1966)
    out.update({"tm_gamma": float(bt[-1]), "tm_t": float(bt[-1] / st[-1]) if st[-1] > 0 else None,
                "tm_ann": 5200 * float(bt[-1] * np.mean(X[:, 0] ** 2)), "tm_alpha_ann": 5200 * float(bt[0])})
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in out.items()}


def luck_vs_skill(panels: dict, n_boot: int = N_BOOT, seed: int = 7) -> dict:
    """شانس یا مهارت (Fama & French 2010؛ Barras, Scaillet & Wermers 2010). panels: {نماد: (y, X, week_id)} مدل ۵ فاکتوری.
    هر صندوق با α صفر بازسازی می‌شود (y − α̂)؛ هفته‌های تقویم با جایگذاری و برای همهٔ صندوق‌ها با هم بازنمونه‌گیری می‌شوند (همبستگی
    میان صندوق‌ها می‌ماند) و t(α) هر صندوق از نو حساب می‌شود. خروجی: صدک‌های t واقعی در برابر شبیه‌سازی، p یک‌طرفهٔ هر صندوق،
    سهم صندوق‌های بی‌مهارت (π0)، مثبت و منفی واقعی (π+، π−) و نرخ کشف نادرست (FDR) در سطح GAMMA، و q-value مثبت هر صندوق."""
    syms = list(panels)
    cal = np.unique(np.concatenate([panels[s][2] for s in syms]))
    pos = {}
    y0, Xs, t_act = {}, {}, {}
    for s in syms:
        y, X, wk = panels[s]
        a, t = alpha_t(y, X)
        y0[s], Xs[s], t_act[s] = y - a, X, t
        p = np.full(len(cal), -1)
        p[np.searchsorted(cal, wk)] = np.arange(len(wk))
        pos[s] = p
    rng = np.random.default_rng(seed)
    T = np.full((n_boot, len(syms)), np.nan)
    for k in range(n_boot):
        draw = rng.integers(0, len(cal), len(cal))
        for j, s in enumerate(syms):
            r = pos[s][draw]
            r = r[r >= 0]
            if len(r) >= MIN_SKILL_W // 2:
                T[k, j] = alpha_t(y0[s][r], Xs[s][r])[1]
    ta = np.array([t_act[s] for s in syms])
    p_pos = np.array([np.mean(T[np.isfinite(T[:, j]), j] >= ta[j]) for j in range(len(syms))])
    p_two = 2 * np.minimum(p_pos, 1 - p_pos)
    N, lam = len(syms), 0.5
    pi0 = float(min(1.0, np.mean(p_two > lam) / (1 - lam)))
    sp, sn = int(np.sum((p_two < GAMMA) & (ta > 0))), int(np.sum((p_two < GAMMA) & (ta < 0)))
    fp = pi0 * N * GAMMA / 2                                                 # مثبت یا منفی تصادفی مورد انتظار در هر دم
    o = np.argsort(p_pos)                                                    # q-value مثبت (Storey 2002)
    q = np.empty(N)
    q[o] = np.minimum.accumulate((pi0 * N * p_pos[o] / np.arange(1, N + 1))[::-1])[::-1]
    pct = [1, 5, 10, 20, 30, 50, 70, 80, 90, 95, 99]
    act = np.percentile(ta, pct)
    sim = np.array([np.nanpercentile(T[k], pct) for k in range(n_boot)])
    return {"n": N, "boot": n_boot, "min_weeks": MIN_SKILL_W, "gamma": GAMMA, "pct": pct,
            "t_actual": [round(float(x), 3) for x in act], "t_sim": [round(float(x), 3) for x in np.nanmean(sim, axis=0)],
            "below": [round(float(x), 3) for x in np.mean(sim < act, axis=0)],     # سهم شبیه‌سازی‌هایی که صدکشان زیر صدک واقعی است
            "pi0": round(pi0, 3), "sig_pos": sp, "sig_neg": sn, "false_exp": round(fp, 2),
            "pi_pos": round(max(0.0, (sp - fp) / N), 3), "pi_neg": round(max(0.0, (sn - fp) / N), 3),
            "fdr_pos": round(min(1.0, fp / sp), 3) if sp else None,
            "funds": {s: {"p": round(float(p_pos[j]), 4), "q": round(float(min(q[j], 1.0)), 4)} for j, s in enumerate(syms)}}


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
    codes_of = {}
    for i, s in enumerate(mk.sym):
        codes_of.setdefault(str(s), []).append(i)
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
        # نماد دوکدی (تنزل به پایه کد تازه می‌سازد): کدی که در روز a ارزش بازار دارد
        pick = lambda s: next((i for i in codes_of.get(s, []) if mc[i] > 0), (codes_of.get(s) or [np.nan])[0])  # noqa: E731
        h = h.assign(i=h.symbol.astype(str).map(pick))
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
    ap.add_argument("--rf", type=float, default=None, help="نرخ ثابت سالانه به‌جای سری اخزا")
    ap.add_argument("--only", action="append", help="فقط این صندوق(ها)؛ آزمون مهارت و پاک‌سازی فایل‌های جزئیات اجرا نمی‌شود")
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
    meta = pd.read_csv(ACTIVE / "funds.csv", dtype=str).fillna("")
    if a.only:
        meta = meta[meta.symbol.isin(a.only)]
    funds, panels = {}, {}
    DET.mkdir(parents=True, exist_ok=True)
    fip = {str(x["regNo"]): x for x in json.loads(FIP_LIST.read_text(encoding="utf-8"))["items"]} if FIP_LIST.exists() else {}
    # زیرصندوق‌های یک صندوق چندبخشی از فیپیران سطح NAV یکسان (صندوق مادر) می‌گیرند: دادهٔ هیچ‌کدام مال خودش نیست؛ همه کنار
    sig = {}
    for sym in meta.symbol:
        try:
            sig.setdefault(tuple(fund_daily(sym, gaps=False).iloc[-30:].round(6)), []).append(sym)
        except Exception:  # noqa: BLE001
            pass
    dup = {s for g in sig.values() if len(g) > 1 for s in g}
    if dup:
        print(f"سری NAV یکسان (زیرصندوق‌های چندبخشی؛ کنار): {len(dup)} صندوق در {sum(len(g) > 1 for g in sig.values())} گروه")
    for m in meta.to_dict("records"):
        sym, fid = m["symbol"], m.get("fipiran_regno") or m["symbol"]
        if sym in dup:
            continue
        try:
            W = weekly(fund_daily(sym), K, F, open_days)
        except Exception as e:  # noqa: BLE001
            print(f"  {sym}: {str(e)[:120]}")
            continue
        if len(W) < len(C5) + 10:
            print(f"  {sym}: {len(W)} هفته؛ کنار")
            continue
        rw = None if a.rf is not None else rf_weekly(W)
        if rw is not None and not np.isfinite(rw).all():
            print(f"  {sym}: سری اخزا همهٔ هفته‌ها را نمی‌پوشاند؛ نرخ ثابت")
            rw = None
        W["rf_ann"] = rw if rw is not None else (a.rf if a.rf is not None else RF_ANN)
        res5 = regress(W, None, C5, C5)
        if res5 is None:
            print(f"  {sym}: دادهٔ کافی برای رگرسیون نیست؛ کنار")
            continue
        res, res_k, res5_k = regress(W), regress(W, None, ["MKT"]), regress(W, None, ["MKT"], C5)
        sk = skill(W)
        x = fip.get(m.get("fipiran_regno", ""), {})
        sk["check"] = validate(sym, x) if x else {"ok": True}
        sk["payer"] = bool(x.get("dividendIntervalPeriod"))
        kind = m.get("fund_type") or "6"
        sk["tested"] = bool(sk.get("eligible") and kind == "6" and sk["check"]["ok"])
        if sk["tested"]:
            panels[sym] = design(W, C5)
        elif sk.get("eligible") and not sk["check"]["ok"]:
            print(f"  ✗ راستی‌آزمایی: {sk['check']}")
        print(f"{sym}: {res5['weeks']} هفته از {W.index.min().date()}، ۵ف α {res5['alpha_ann']:+.1f}٪ (t {res5['alpha_t']:+.2f})، R² {res5['r2']:.2f}"
              + (f" · ۶ف {res['weeks']} هفته α {res['alpha_ann']:+.1f}٪ (t {res['alpha_t']:+.2f})" if res else "")
              + (f" · TM t {sk['tm_t']:+.2f}" if sk.get("tm_t") is not None else ""), flush=True)
        hv = holdings_view(mk, sym)
        funds[sym] = {"id": fid, "name": m["name"], "style": m.get("style", ""), "kind": kind, "invest": m.get("invest", ""), "manager": m.get("manager", ""),
                      "start": str(W.index.min().date()), "end": str(W.index.max().date()), "hold": bool(hv),
                      "result": res, "market_only": res_k, "result5": res5, "market_only5": res5_k, "skill": sk}
        det = {"y": [round(float(x), 6) for x in W.y.values], "w_end": [str(d.date()) for d in W.index], "days": W.days.astype(int).tolist(),
               "F": {c: [None if x != x else round(float(x), 6) for x in W[c].values] for c in ["MKT_raw", *F.columns]},
               "rf_w": [round(float(x), 5) for x in W.rf_ann.values], "rolling": rolling(W), "rolling5": rolling(W, codes=C5), "holdings": hv}
        (DET / f"{fid}.js").write_text("(window.SIM_FATTR_D = window.SIM_FATTR_D || {})[" + json.dumps(sym, ensure_ascii=False) + "] = "
                                       + json.dumps(det, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    if not a.only:
        keep = {f"{v['id']}.js" for v in funds.values()}
        for p in DET.glob("*.js"):
            if p.name not in keep:
                p.unlink()
    test = None
    if len(panels) >= 10:
        print(f"\nآزمون شانس یا مهارت: {len(panels)} صندوق سهامی با دست‌کم {MIN_SKILL_W} هفته، {N_BOOT} بازنمونه …", flush=True)
        test = luck_vs_skill(panels)
        for s, v in test["funds"].items():
            funds[s]["skill"].update(v)
        print(f"  π0 {test['pi0']:.2f}، معنادار مثبت {test['sig_pos']} و منفی {test['sig_neg']} (تصادفی مورد انتظار {test['false_exp']:.1f} در هر دم)، "
              f"π+ {test['pi_pos']:.2f}، π− {test['pi_neg']:.2f}، FDR+ {test['fdr_pos']}")
        print("  صدک t(α): " + "، ".join(f"{p}٪ {x:+.2f} (شبیه‌سازی {s_:+.2f}، {100 * b:.0f}٪ زیر)" for p, x, s_, b in zip(test["pct"], test["t_actual"], test["t_sim"], test["below"])))
    if a.only:                                                           # فهرست کامل (fund_attr.js) فقط با اجرای همهٔ صندوق‌ها بازنویسی می‌شود
        return
    out = {"asof": str(last.date()), "rf_ann": a.rf if a.rf is not None else RF_ANN, "rf_src": "const" if a.rf is not None or not RF_CSV.exists() else "bills", "hac_lags": HAC_L, "roll": ROLL,
           "factors": [{"code": c, "fa": fa} for c, fa in FACTORS], "min_skill_w": MIN_SKILL_W, "skill_test": test, "funds": funds}
    OUT.write_text("window.SIM_FATTR = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"\n→ {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
