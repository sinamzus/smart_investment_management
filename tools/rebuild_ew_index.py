#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""بازسازی «شاخص كل (هم وزن)» از قیمت‌های روزانهٔ نمادها و مقایسه با سری رسمی.

    python tools/rebuild_ew_index.py            # گزارش مقایسه
    python tools/rebuild_ew_index.py --save     # ذخیرهٔ سری بازسازی‌شده در data/derived/

قواعد (از آزمون روی داده، فصل ۰۳ §۳.۴):
  1. بازدهی روزانهٔ هر نماد = pClosing / priceYesterday − 1  (قیمت مبنای روز؛ فصل ۰۲ §۲.۴)
  2. فقط سهام بازار «bourse» (با افزودن فرابورس خطا بیشتر می‌شود)
     و بدون نمادهای تکراری با پسوند رقم (مثل «سخزر3» در کنار «سخزر»: همان سهم با قیمت
     یکسان؛ ۲۸۶ از ۶۵۲ نماد) — شمارش مضاعف و خطای ۲۰۲۶ را حذف می‌کند
  3. روز اول معامله هر نماد حذف می‌شود (مبنای قراردادی ۱۰۰۰ ریال، بازده بی‌معنی)
  4. ردیف‌های بدون معامله با بازده صفر می‌مانند (نماد در شاخص هست)
  5. ردیف‌های داده‌ای معیوب حذف می‌شوند: pClosing ≤ 1 یا بازده ≤ −۹۰٪ یا priceYesterday ≤ 0
  6. شاخص = میانگین ساده بازدهی نمادها در هر روز، تجمعی هندسی
"""
import argparse
import glob
import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OFFICIAL = {"TR": "67130298613737946", "PR": "8384385859414435"}  # كل (هم وزن) / قيمت (هم وزن)


# پیشوند ISIN سهم = بازار پذیرش [تأیید لازم؛ از جدول flow × ISIN و نام‌ها استنباط شد، ۲۰۲۶-۱۰-۱۹]:
# IRO1 سهام بورس، IROT کد قدیمی سهام بورس (مثل نبروج، کاصفا)، IRO3 و IRO5 سهام فرابورس، IRO7 بازار پایه.
# هر پیشوند دیگر (IRB اوراق، IRK گواهی کالا، IRT صندوق، IRO6 تسهیلات مسکن، IRO4/IRO8/IRE9 انرژی و سایر) سهم عملیاتی نیست ⇒ «other».
ISIN_MARKET = {"IRO1": "bourse", "IROT": "bourse", "IRO3": "farabourse", "IRO5": "farabourse", "IRO7": "paye"}


def apply_isin_market(inst: pd.DataFrame) -> pd.DataFrame:
    """بازار هر سهم از پیشوند ISIN (بازار پذیرش)، نه flow امروز: نماد حذف‌شده امروز flow ۴ («سایر») دارد ولی تا روز حذف
    در بورس/فرابورس معامله می‌شد و باید در جهان آن دوره باشد (ممیزی سوگیری ۲۰۲۶-۱۰-۱۹، A1/B4). ISIN ناشناخته ⇒ بازار فهرست."""
    info_p = ROOT / "data/corporate_actions/instrument_info.csv"
    if not info_p.exists():
        return inst
    info = pd.read_csv(info_p, dtype={"ins_code": str}).drop_duplicates("ins_code").set_index("ins_code")
    pre = info.cIsin.where(info.cIsin.notna() & (info.cIsin.astype(str).str.len() >= 4)).astype(str).str[:4]
    pre = pre[pre != "nan"]
    m = inst.ins_code.map(pre.map(lambda x: ISIN_MARKET.get(x, "other")))   # ISIN معلوم و ناشناخته ⇒ غیرسهم
    cons_p = ROOT / "data/index_constituents.csv"
    kmem = set()
    if cons_p.exists():                                  # اعضای رسمی «شاخص كل» دست نمی‌خورند (load_panel آن‌ها را بورس/سهم می‌کند)
        cons = pd.read_csv(cons_p, dtype={"ins_code": str, "index_code": str})
        kmem = set(cons[cons.index_code == "32097828799138957"].ins_code)
    inst = inst.copy()
    use = m.notna() & (inst.type == "stock") & ~inst.ins_code.isin(kmem)
    inst.loc[use, "market"] = m[use]
    return inst


def trim_thin_tail(P: pd.DataFrame, frac: float = 0.5, look: int = 20) -> pd.DataFrame:
    """روزهای پایانی که کمتر از frac × میانهٔ شمار نماد ۲۰ روز قبل ردیف دارند حذف می‌شوند (دریافت ناقص: بخشی از فایل‌ها به‌روزتر از بقیه‌اند).
    بدون این، آخرین روز پانل فقط چند نماد داشت و واجدان روز زنده تهی می‌شد (۲۰۲۶-۱۰-۱۹)."""
    cnt = P.groupby("date").size().sort_index()
    if len(cnt) <= look:
        return P
    cut = None
    for d in cnt.index[::-1]:
        ref = cnt[cnt.index < d].tail(look).median()
        if cnt[d] >= frac * ref:
            break
        cut = d
    if cut is not None:
        dropped = cnt[cnt.index >= cut]
        print(f"هشدار: {len(dropped)} روز پایانی کم‌پوشش حذف شد (از {cut.date()}؛ ردیف‌ها {dropped.tolist()}، میانهٔ قبل {int(cnt[cnt.index < cut].tail(look).median())})")
        P = P[P.date < cut]
    return P


def load_panel() -> pd.DataFrame:
    inst = pd.read_csv(ROOT / "data/instruments.csv", dtype={"ins_code": str})
    extra_p = ROOT / "data/instruments_extra.csv"
    if extra_p.exists():  # سهام خارج از MarketWatch (fetch_stock_daily.py --search)
        ex = pd.read_csv(extra_p, dtype={"ins_code": str})
        ex = ex[~ex.ins_code.isin(inst.ins_code) & ~ex.name.fillna("").str.startswith("آتی")].assign(market="bourse", type="stock", base_volume=0)
        inst = pd.concat([inst, ex[["ins_code", "symbol", "name", "market", "type", "base_volume"]]], ignore_index=True)
    inst = apply_isin_market(inst)
    cols = ["dEven", "pClosing", "priceYesterday", "zTotTran"]
    frames = []
    for f in glob.glob(str(ROOT / "data/prices/*.csv.gz")):
        d = pd.read_csv(f, usecols=cols, dtype=float)
        d["ins_code"] = os.path.basename(f).split(".")[0]
        frames.append(d)
    P = pd.concat(frames, ignore_index=True)
    P["date"] = pd.to_datetime(P["dEven"].astype(int).astype(str), format="%Y%m%d")
    P = trim_thin_tail(P)
    P = P.merge(inst[["ins_code", "symbol", "market", "type", "name"]], on="ins_code", how="left")
    # تصحیح طبقه‌بندی با فهرست رسمی اعضای «شاخص كل» (data/index_constituents.csv):
    # شرکت‌هایی مثل «وصندوق» (سرمایه‌گذاری صندوق بازنشستگی) و «بورس» به‌خطا صندوق/اوراق شمرده می‌شدند.
    cons_p = ROOT / "data/index_constituents.csv"
    if cons_p.exists():
        cons = pd.read_csv(cons_p, dtype={"ins_code": str, "index_code": str})
        kmem = set(cons[cons.index_code == "32097828799138957"].ins_code)
        P.loc[P.ins_code.isin(kmem) & (P.type != "stock"), ["market", "type"]] = ["bourse", "stock"]
    P.loc[P.name.fillna("").str.startswith("ص ") & ~P.ins_code.isin(kmem if cons_p.exists() else set()), "type"] = "fund"
    return P


def daily_returns(P: pd.DataFrame, markets=("bourse",)) -> pd.DataFrame:
    P = P[P.market.isin(markets) & (P.type == "stock")].copy()
    syms = set(P.symbol)
    dup = P.symbol.str.contains(r"\d$") & P.symbol.str.replace(r"\d+$", "", regex=True).isin(syms)
    P = P[~dup].copy()                                  # قاعدهٔ ۲ (تکراری‌های رقمی)
    P["traded"] = P.zTotTran > 0
    first = P[P.traded].groupby("ins_code").date.min().rename("first_trade")
    P = P.merge(first, on="ins_code", how="left")
    P = P[P.date > P.first_trade]                      # قاعدهٔ ۳
    P = P[(P.priceYesterday > 0) & (P.pClosing > 1)]    # قاعدهٔ ۵
    P = fill_gaps(P)                                    # قاعدهٔ ۹
    P["r"] = P.pClosing / P.priceYesterday - 1          # قاعدهٔ ۱
    P = fix_unapplied_adjustments(P)                    # قاعدهٔ ۸
    return P[P.r > -0.9]


def fill_gaps(P: pd.DataFrame, start: str = "2014-03-19") -> pd.DataFrame:
    """قاعدهٔ ۹: روز بدون ردیف برای نمادی که زنده است = روز بدون معامله با بازده صفر.

    در روزهایی مثل ۲۰۲۴-۰۸-۰۷ (۲۵۸ از ۳۸۴ نماد ردیف ندارند) و ۲۰۲۳-۰۳-۲۷ (۱۱۳ نماد) خوراک ناقص است. بدون پر کردن،
    نمادِ بدون ردیف از وزن‌های رانش‌یافتهٔ هم‌وزن تا ریبالانس بعد حذف می‌شد. فقط از `start` به بعد و فقط بین اولین و
    آخرین ردیف هر نماد (قبل از ۲۰۱۴ ردیف روزهای بدون معامله اصلاً ثبت نشده و مقایسه‌ای نداریم).
    """
    Q = P[P.date >= start]
    dates = np.sort(Q.date.unique())
    if len(dates) == 0:
        return P
    key = Q.groupby("ins_code").date.agg(["min", "max", "count"])
    cand = key[(np.searchsorted(dates, key["max"].values, side="right") - np.searchsorted(dates, key["min"].values, side="left")) > key["count"].values]
    if cand.empty:
        return P
    have = set(zip(Q.ins_code, Q.date))
    miss = []
    for code, row in cand.iterrows():
        lo, hi = np.searchsorted(dates, row["min"], side="left"), np.searchsorted(dates, row["max"], side="right")
        miss += [(code, d) for d in dates[lo:hi] if (code, d) not in have]
    if not miss:
        return P
    F = pd.DataFrame(miss, columns=["ins_code", "date"]).sort_values("date")
    base = P.sort_values("date")
    F = pd.merge_asof(F, base, on="date", by="ins_code", direction="backward")
    F["priceYesterday"] = F.pClosing
    F["zTotTran"] = 0.0
    F["dEven"] = F.date.dt.strftime("%Y%m%d").astype(float)
    out = pd.concat([P, F[P.columns]], ignore_index=True)
    print(f"قاعدهٔ ۹: {len(F)} ردیف روز-بدون-ردیف (نماد زنده) با بازده صفر پر شد")
    return out


def fix_unapplied_adjustments(P: pd.DataFrame, window_days: int = 7, max_abs: float = 0.25) -> pd.DataFrame:
    """قاعدهٔ ۸: تعدیل قیمتِ اعمال‌نشده در مبنا.

    فهرست تعدیل (price_adjust.csv) برای هر رویداد قیمت تعدیل‌شده A و تعدیل‌نشده U را می‌دهد. در برخی ردیف‌ها
    (عمدتاً ۲۰۱۴–۲۰۱۸) مبنای روز (priceYesterday) هنوز U است نه A:
      • روز بدون معامله که pClosing را به A برده ولی مبنا U مانده ⇒ بازدهٔ خام −۱۵٪ی کاذب (افت سود/سرمایه)؛
      • روز معامله با مبنای U ⇒ بازده باید C/A − 1 باشد.
    در هر دو حالت r = C/A − 1 (حالت اول صفر می‌شود). ستون‌های adjA/adjU برای طبقه‌بندی سود/سرمایه نگه داشته می‌شوند.
    """
    pa_p = ROOT / "data/corporate_actions/price_adjust.csv"
    P["adjA"] = np.nan
    P["adjU"] = np.nan
    if not pa_p.exists():
        return P
    pa = pd.read_csv(pa_p, dtype={"ins_code": str}, usecols=["ins_code", "dEven", "pClosing", "pClosingNotAdjusted"])
    pa = pa.dropna()
    pa["D"] = pd.to_datetime(pa.dEven.astype(int).astype(str), format="%Y%m%d", errors="coerce")
    pa = pa[(pa.pClosing > 1) & (pa.pClosingNotAdjusted > 1) & ((pa.pClosing - pa.pClosingNotAdjusted).abs() > 0.5)].dropna(subset=["D"])
    idx = {c: g for c, g in P.groupby("ins_code")}
    n = 0
    for code, ev in pa.groupby("ins_code"):
        g = idx.get(code)
        if g is None:
            continue
        for D, A, U in zip(ev.D, ev.pClosing, ev.pClosingNotAdjusted):
            if not 0.1 <= A / U < 1:
                continue
            base_unadj = ((g.priceYesterday - U).abs() <= 0.5) & ((g.priceYesterday - A).abs() > 0.5)
            in_win = (g.date >= D - pd.Timedelta(days=window_days)) & (g.date <= D + pd.Timedelta(days=window_days))
            adj_day = (g.zTotTran == 0) & ((g.pClosing - A).abs() <= 0.5)     # روز بدون معاملهٔ تعدیل
            first_trade = (g.zTotTran > 0) & (g.date >= D)                    # اولین معاملهٔ بعد از استحقاق
            m = g[base_unadj & in_win & (adj_day | first_trade)]
            if len(m) > 1 and (m.zTotTran > 0).any():   # فقط اولین ردیف معاملهٔ پس از D
                m = pd.concat([m[m.zTotTran == 0], m[m.zTotTran > 0].sort_values("date").head(1)])
            if m.empty:
                continue
            r_new = P.loc[m.index, "pClosing"] / A - 1
            m = m[r_new.abs() <= max_abs]          # رویدادهای متناقض/برگشتی در فهرست (مثل قثابت ۲۰۱۴) رد می‌شوند
            if m.empty:
                continue
            P.loc[m.index, "r"] = r_new[m.index]
            P.loc[m.index, "adjA"] = A
            P.loc[m.index, "adjU"] = U
            n += len(m)
    print(f"قاعدهٔ ۸: {n} ردیف با مبنای تعدیل‌نشده (تعدیل A در فهرست) اصلاح شد")
    return P


def clean_level(d: pd.Series) -> tuple[pd.Series, list]:
    """رفع جهش‌های ×۱۰ / ÷۱۰ در سطح شاخص رسمی (خطای دادهٔ منبع).

    - جفتِ «افت ~÷۱۰ و بازگشت ~×۱۰» ظرف ۳ ردیف = ردیف‌های وسط خطای تک‌روزه‌اند → حذف.
    - افت ÷۱۰ بدون بازگشت = تغییر مقیاس دائمی → بقیهٔ سری ×۱۰ می‌شود (و برعکس).
    """
    d = d[d > 0].copy()                      # سطح صفر = شاخص بدون عضو (روزهای قبل از شروع)
    events = []
    i = 1
    while i < len(d):
        r = d.iloc[i] / d.iloc[i - 1]
        if 0.07 <= r <= 0.13 or 7.5 <= r <= 13.0:
            f = 10.0 if r < 1 else 0.1
            back = None
            for k in range(i + 1, min(i + 4, len(d))):
                rr = d.iloc[k] / d.iloc[k - 1]
                if (r < 1 and 7.5 <= rr <= 13.0) or (r > 1 and 0.07 <= rr <= 0.13):
                    back = k
                    break
            if back is not None:
                events.append((d.index[i], "glitch", back - i))
                d = d.drop(d.index[i:back])
                continue
            events.append((d.index[i], "rescale", f))
            d.iloc[i:] = d.iloc[i:] * f
        i += 1
    # تیغهٔ تک‌روزه: جهش > ۷٪ که فردا کامل برمی‌گردد (سطح فردا ≈ سطح دیروز) — سقف نوسان روزانه ۵٪ چنین شاخصی را ممکن نمی‌کند
    # مگر در صنعت‌های بسیار کم‌عضو؛ نمونه: صنعت ۵۴ در ۲۰۱۶-۱۰-۲۵ (۲۴۳۷ ← ۲۸۰۵ ← ۲۴۷۴)
    i = 1
    while i < len(d) - 1:
        r = d.iloc[i] / d.iloc[i - 1] - 1
        back = d.iloc[i + 1] / d.iloc[i - 1] - 1
        if abs(r) > 0.07 and abs(back) < 0.3 * abs(r):
            events.append((d.index[i], "spike", r))
            d = d.drop(d.index[i])
            continue
        i += 1
    return d, events


def official(code: str) -> pd.Series:
    d = pd.read_csv(ROOT / f"data/indices/index_{code}.csv", parse_dates=["date"]).set_index("date").close
    d, _ = clean_level(d)
    return d.pct_change().dropna()


def compare(mine: pd.Series, off: pd.Series, name: str) -> pd.DataFrame:
    j = pd.concat([mine, off], axis=1, join="inner").dropna()
    j.columns = ["mine", "official"]
    j = j[j.index >= "2014-03-20"]
    d = j.mine - j.official
    print(f"{name}: n={len(j)} corr={j.mine.corr(j.official):.4f} mean={d.mean()*1e4:.2f}bp "
          f"MAD={d.abs().mean()*1e4:.2f}bp TE={d.std()*np.sqrt(252)*100:.2f}% "
          f"days>50bp={(d.abs() > 5e-3).sum()} cum_ratio={(1+j.mine).prod()/(1+j.official).prod():.3f}")
    return j


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    R = daily_returns(load_panel())
    mine = R.groupby("date").r.mean()
    n = R.groupby("date").ins_code.nunique()
    print(f"روز: {len(mine)}، میانگین تعداد نماد در روز: {n.mean():.0f}\n")
    jt = compare(mine, official(OFFICIAL["TR"]), "در برابر كل (هم وزن)    [TR]")
    jp = compare(mine, official(OFFICIAL["PR"]), "در برابر قيمت (هم وزن)  [PR]")
    d = (jp.mine - jp.official)
    print("\nMAD سالانه در برابر PR (bp):", {y: round(v * 1e4, 1) for y, v in d.abs().groupby(d.index.year).mean().items()})
    print("میانگین اختلاف سالانه (bp):  ", {y: round(v * 1e4, 1) for y, v in d.groupby(d.index.year).mean().items()})
    print("\nبیشترین اختلاف‌ها در برابر PR:")
    print((d.abs().sort_values(ascending=False).head(8) * 1e4).round(1).to_string())
    if a.save:
        out = ROOT / "data/derived"
        out.mkdir(parents=True, exist_ok=True)
        s = pd.DataFrame({"ret": mine, "n_symbols": n})
        s["index"] = 10000 * (1 + s.ret).cumprod()
        s.to_csv(out / "ew_rebuilt_bourse.csv", index_label="date")
        print("ذخیره شد:", out / "ew_rebuilt_bourse.csv")


if __name__ == "__main__":
    main()
