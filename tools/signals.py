#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""کتابخانهٔ معیارهای انتخاب (Signals) برای بورس و فرابورس ایران؛ فصل ۱۴.

هر معیار تابعی است از (بازار، روز ریبالانس a) ← بردار امتیاز خام برای همهٔ نمادها. **جهت قرارداد:** امتیاز بالاتر = بازده مورد انتظار بیشتر
بر پایهٔ ادبیات (مثلاً نوسان کمتر ⇒ امتیاز بالاتر). علامت واقعی در ایران را IC تجربی نشان می‌دهد؛ جهت را عوض نکنید، بیرون از این فایل علامت بگذارید.
همهٔ پنجره‌ها فقط تا بستهٔ روز a را می‌بینند (بدون نگاه به آینده). بنیادی‌ها فقط پس از تاریخ اعلام (point-in-time).

    python tools/signals.py --zoo        # جدول IC همهٔ معیارها ← data/research/signal_zoo.json + همبستگی‌ها
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import rebuild_ew_rebalanced as ewr  # noqa: E402

REG: dict = {}          # نام ← فراداده + تابع
EVAL_FROM = pd.Timestamp("2016-03-20")
WARM = 273              # روز لازم پیش از اولین ریبالانس (۲۵۲ + ۲۱)


def signal(name, family, fa, en, formula, ref, needs="price", window=252):
    def deco(fn):
        REG[name] = {"name": name, "family": family, "fa": fa, "en": en, "formula": formula, "ref": ref, "needs": needs, "window": window, "fn": fn}
        return fn
    return deco


def W(A, a, w, skip=0):
    """پنجرهٔ w روزه که به روز a−skip ختم می‌شود (شامل آن)؛ None اگر داده کافی نیست."""
    hi = a - skip + 1
    lo = hi - w
    return A[lo:hi] if lo >= 0 else None


def cnt(Z):
    return np.sum(~np.isnan(Z), axis=0)


def nanstd(Z, min_frac=0.6, ddof=1):
    n = cnt(Z)
    with np.errstate(all="ignore"):
        s = np.nanstd(Z, axis=0, ddof=ddof)
    return np.where(n >= min_frac * len(Z), s, np.nan)


def nanmean(Z, min_frac=0.6):
    n = cnt(Z)
    with np.errstate(all="ignore"):
        m = np.nanmean(Z, axis=0)
    return np.where(n >= min_frac * len(Z), m, np.nan)


class Market:
    """ماتریس‌های روزانهٔ تاریخ × نماد برای محاسبهٔ معیارها (بورس + فرابورس)."""

    def __init__(self, Ra: pd.DataFrame, info: pd.DataFrame):
        M = Ra.pivot_table(index="date", columns="ins_code", values="r_tr", aggfunc="last")
        M = M[M.index >= "2012-01-01"]
        self.dates, self.cols = M.index, M.columns
        n, k = M.shape
        self.n, self.k = n, k
        self.X = M.values                                           # بازده کل روزانه (TR)
        pv = lambda col: Ra.pivot_table(index="date", columns="ins_code", values=col, aggfunc="last").reindex(index=self.dates, columns=self.cols).values  # noqa: E731
        self.PR = pv("r_pr")
        self.Y = np.clip(np.nan_to_num(self.X - self.PR), 0, None)  # بازده سود نقدی روزانه (روز استحقاق)
        self.close = pv("pClosing")
        self.prev = pv("priceYesterday")
        self.shares = pv("shares")
        self.mcap = self.prev * self.shares
        self.LR = np.log1p(np.where(np.isnan(self.X), 0, self.X))   # لگاریتم بازده (۰ برای بی‌داده)
        self.mkt = np.nanmean(np.where(np.isnan(self.X), np.nan, self.X), axis=0 if False else 1)   # بازار هم‌وزن روزانه
        self._load_prices()
        jm = np.array([ewr.g2j(d.year, d.month, d.day)[0] * 100 + ewr.g2j(d.year, d.month, d.day)[1] for d in self.dates])
        self.month_end = np.where(jm[1:] != jm[:-1])[0]
        sec = info.drop_duplicates("ins_code").set_index("ins_code").sector_name.astype(str).str.strip()
        self.sector = sec.reindex(self.cols).fillna("؟").values
        self.sym = Ra.drop_duplicates("ins_code").set_index("ins_code").symbol.reindex(self.cols).values
        self.market = Ra.drop_duplicates("ins_code").set_index("ins_code").market.reindex(self.cols).values
        z = np.zeros(k)
        self.have = np.vstack([z, np.cumsum(~np.isnan(self.X), axis=0)])
        self.nz = np.vstack([z, np.cumsum(np.nan_to_num(self.X) != 0, axis=0)])
        self.fund = None                                            # بنیادی‌ها: set_fundamentals

    def _load_prices(self):
        cols = ["dEven", "priceFirst", "priceMax", "priceMin", "qTotTran5J", "qTotCap"]
        keep = {c: [] for c in cols[1:]}
        frames = {c: {} for c in cols[1:]}
        for code in self.cols:
            f = ROOT / "data" / "prices" / f"{code}.csv.gz"
            try:
                d = pd.read_csv(f, usecols=cols)
            except Exception:  # noqa: BLE001
                continue
            d["date"] = pd.to_datetime(d.dEven.astype(int).astype(str), format="%Y%m%d")
            d = d.drop_duplicates("date", keep="last").set_index("date")
            for c in cols[1:]:
                frames[c][code] = d[c]
        for c in cols[1:]:
            keep[c] = pd.DataFrame(frames[c]).reindex(index=self.dates, columns=self.cols).values.astype(float)
        self.open, self.hi, self.lo = keep["priceFirst"], keep["priceMax"], keep["priceMin"]
        self.vol, self.val = keep["qTotTran5J"], keep["qTotCap"]
        for A in (self.open, self.hi, self.lo):
            A[A <= 0] = np.nan

    # ── واجدیت قیمتی (همان قاعدهٔ موتور فاکتور) ──
    def eligible(self, a: int):
        i1, i0 = a + 1, a + 1 - 252
        ok = ((self.have[i1] - self.have[i0]) >= 0.8 * 252) & ((self.nz[i1] - self.nz[i0]) >= 0.5 * 252) & ~np.isnan(self.X[a])
        return ok

    def fwd(self, a: int, b: int, delay: int = 0):
        """بازدهٔ مرکب [a+1+delay, b+delay]؛ NaN اگر روز بعد یا پایان دوره داده ندارد."""
        lo, hi = a + 1 + delay, min(b + 1 + delay, self.n)
        seg = self.X[lo:hi]
        bad = np.isnan(self.X[a + 1]) | np.isnan(self.X[min(b, self.n - 1)])
        g = np.nanprod(1 + np.nan_to_num(seg), axis=0) - 1
        return np.where(bad, np.nan, g)


# ═══════════════════ مومنتوم ═══════════════════
def _cum(mk, a, w, skip):
    Z = W(mk.LR, a, w, skip)
    return None if Z is None else Z.sum(axis=0)


@signal("mom_12_1", "momentum", "مومنتوم ۱۲−۱", "Momentum 12-1", "Σ ln(1+r) از ۲۵۱ تا ۲۱ روز پیش از a", "Jegadeesh & Titman (1993)", window=252)
def mom_12_1(mk, a):
    return _cum(mk, a, 231, 21)


@signal("mom_6_1", "momentum", "مومنتوم ۶−۱", "Momentum 6-1", "Σ ln(1+r) روی ۱۲۶ روز منتهی به ۲۱ روز پیش", "Jegadeesh & Titman (1993)", window=147)
def mom_6_1(mk, a):
    return _cum(mk, a, 126, 21)


@signal("mom_3_1", "momentum", "مومنتوم ۳−۱", "Momentum 3-1", "Σ ln(1+r) روی ۶۳ روز منتهی به ۲۱ روز پیش", "Jegadeesh & Titman (1993)", window=84)
def mom_3_1(mk, a):
    return _cum(mk, a, 63, 21)


@signal("mom_9_1", "momentum", "مومنتوم ۹−۱", "Momentum 9-1", "Σ ln(1+r) روی ۱۸۹ روز منتهی به ۲۱ روز پیش", "Jegadeesh & Titman (1993)", window=210)
def mom_9_1(mk, a):
    return _cum(mk, a, 189, 21)


@signal("mom_12_0", "momentum", "مومنتوم ۱۲ ماه بدون حذف ماه اخیر", "Momentum 12-0", "Σ ln(1+r) روی ۲۵۲ روز منتهی به a", "Jegadeesh & Titman (1993)", window=252)
def mom_12_0(mk, a):
    return _cum(mk, a, 252, 0)


@signal("mom_intermediate", "momentum", "مومنتوم میانی (۱۲−۷)", "Intermediate momentum", "Σ ln(1+r) از ۲۵۱ تا ۱۳۲ روز پیش", "Novy-Marx (2012)", window=252)
def mom_intermediate(mk, a):
    return _cum(mk, a, 120, 131)


@signal("mom_riskadj", "momentum", "مومنتوم تعدیل‌شده با نوسان", "Risk-adjusted momentum", "مومنتوم ۱۲−۱ ÷ انحراف معیار روزانهٔ همان پنجره", "Barroso & Santa-Clara (2015)؛ Hurst et al.", window=252)
def mom_riskadj(mk, a):
    m = _cum(mk, a, 231, 21)
    Z = W(mk.X, a, 231, 21)
    return None if m is None else m / nanstd(Z)


@signal("mom_resid", "momentum", "مومنتوم باقیمانده", "Residual momentum", "مجموع باقیماندهٔ مدل بازار (هم‌وزن) روی ۲۳۱ روز منتهی به ۲۱ روز پیش ÷ (σ باقیمانده·√n)", "Blitz, Huij & Martens (2011)", window=252)
def mom_resid(mk, a):
    Y, x = W(mk.X, a, 252), W(mk.mkt[:, None], a, 252)
    if Y is None:
        return None
    ok = ~np.isnan(Y)
    n = ok.sum(axis=0)
    Yz = np.where(ok, Y, 0)
    xm = np.where(ok, x, 0)
    sx, sy = xm.sum(axis=0), Yz.sum(axis=0)
    sxx, sxy = (xm * xm).sum(axis=0), (xm * Yz).sum(axis=0)
    with np.errstate(all="ignore"):
        beta = (n * sxy - sx * sy) / (n * sxx - sx * sx)
        alpha = (sy - beta * sx) / n
        res = Yz - beta * xm - alpha
        res = np.where(ok, res, 0)
        seg = res[: 252 - 21].sum(axis=0)                         # ۲۳۱ روز منتهی به ۲۱ روز پیش
        sd = np.sqrt((res ** 2).sum(axis=0) / np.maximum(n - 2, 1))
        out = seg / (sd * np.sqrt(231))
    return np.where(n >= 200, out, np.nan)


@signal("high52", "momentum", "نزدیکی به اوج ۵۲ هفته", "52-week high", "سطح TR ÷ بیشینهٔ سطح TR در ۲۵۲ روز", "George & Hwang (2004)", window=252)
def high52(mk, a):
    Z = W(mk.LR, a, 252)
    if Z is None:
        return None
    lv = np.cumsum(Z, axis=0)
    return np.exp(lv[-1] - np.max(lv, axis=0))


@signal("mom_industry", "momentum", "مومنتوم صنعت", "Industry momentum", "میانگین مومنتوم ۱۲−۱ نمادهای هم‌صنعت (هم‌وزن)", "Moskowitz & Grinblatt (1999)", window=252)
def mom_industry(mk, a):
    m = _cum(mk, a, 231, 21)
    if m is None:
        return None
    s = pd.Series(m).groupby(mk.sector).transform("mean").values
    return s


@signal("rev_1m", "momentum", "بازگشت کوتاه‌مدت (۱ ماه)", "Short-term reversal 1m", "منفی بازدهٔ ۲۱ روز اخیر", "Jegadeesh (1990)؛ Lehmann (1990)", window=21)
def rev_1m(mk, a):
    m = _cum(mk, a, 21, 0)
    return None if m is None else -m


@signal("rev_1w", "momentum", "بازگشت هفتگی", "Short-term reversal 1w", "منفی بازدهٔ ۵ روز اخیر", "Lehmann (1990)", window=5)
def rev_1w(mk, a):
    m = _cum(mk, a, 5, 0)
    return None if m is None else -m


@signal("mom_up_days", "momentum", "پیوستگی روند (سهم روزهای مثبت)", "Up-day share (continuity)", "سهم روزهای با بازده مثبت در پنجرهٔ ۱۲−۱ از روزهای غیرصفر", "Da, Gurun & Warachka (2014) — ساده‌شده", window=252)
def mom_up_days(mk, a):
    Z = W(mk.X, a, 231, 21)
    if Z is None:
        return None
    nz = (np.nan_to_num(Z) != 0).sum(axis=0)
    up = (np.nan_to_num(Z) > 0).sum(axis=0)
    return np.where(nz >= 60, up / np.maximum(nz, 1), np.nan)


@signal("max_lottery", "momentum", "اثر MAX (بخت‌آزمایی)", "MAX effect", "منفی میانگین سه بازده روزانهٔ بیشینه در ۲۱ روز اخیر (سقف نوسان MAX را اشباع می‌کند)", "Bali, Cakici & Whitelaw (2011)", window=21)
def max_lottery(mk, a):
    Z = W(mk.X, a, 21)
    if Z is None:
        return None
    with np.errstate(all="ignore"):
        S = np.sort(np.where(np.isnan(Z), -np.inf, Z), axis=0)[-3:]
        out = -np.where(np.isinf(S), np.nan, S).mean(axis=0)
    return np.where(cnt(Z) >= 15, out, np.nan)


# ═══════════════════ ریسک و نوسان ═══════════════════
def _vol(mk, a, w):
    Z = W(mk.X, a, w)
    return None if Z is None else nanstd(Z)


@signal("vol_252", "risk", "نوسان ۲۵۲ روزه (کم‌نوسان)", "Total volatility 252d", "منفی انحراف معیار بازده روزانه", "Ang, Hodrick, Xing & Zhang (2006)؛ Blitz & van Vliet (2007)", window=252)
def vol_252(mk, a):
    v = _vol(mk, a, 252)
    return None if v is None else -v


@signal("vol_126", "risk", "نوسان ۱۲۶ روزه", "Total volatility 126d", "منفی انحراف معیار ۱۲۶ روز", "Ang et al. (2006)", window=126)
def vol_126(mk, a):
    v = _vol(mk, a, 126)
    return None if v is None else -v


@signal("vol_63", "risk", "نوسان ۶۳ روزه", "Total volatility 63d", "منفی انحراف معیار ۶۳ روز", "Ang et al. (2006)", window=63)
def vol_63(mk, a):
    v = _vol(mk, a, 63)
    return None if v is None else -v


@signal("vol_ewma", "risk", "نوسان EWMA (λ=۰٫۹۴)", "EWMA volatility", "منفی √(Σ λ^k r²) با λ=۰٫۹۴ روی ۲۵۲ روز", "RiskMetrics (1996)", window=252)
def vol_ewma(mk, a):
    Z = W(mk.X, a, 252)
    if Z is None:
        return None
    lam = 0.94
    wts = lam ** np.arange(251, -1, -1)
    ok = ~np.isnan(Z)
    num = (np.where(ok, Z, 0) ** 2 * wts[:, None]).sum(axis=0)
    den = (ok * wts[:, None]).sum(axis=0)
    return np.where(ok.sum(axis=0) >= 150, -np.sqrt(num / np.maximum(den, 1e-12)), np.nan)


@signal("downside_dev", "risk", "انحراف نزولی", "Downside deviation", "منفی √میانگین min(r,0)² در ۲۵۲ روز", "Sortino & Price (1994)؛ Ang, Chen & Xing (2006)", window=252)
def downside_dev(mk, a):
    Z = W(mk.X, a, 252)
    if Z is None:
        return None
    with np.errstate(all="ignore"):
        d = np.sqrt(np.nanmean(np.minimum(Z, 0) ** 2, axis=0))
    return np.where(cnt(Z) >= 150, -d, np.nan)


@signal("cvar_5", "risk", "ریزش مورد انتظار ۵٪ (CVaR)", "Expected shortfall 5%", "منفی میانگین بدترین ۵٪ بازده روزانهٔ ۲۵۲ روز", "Acerbi & Tasche (2002)", window=252)
def cvar_5(mk, a):
    Z = W(mk.X, a, 252)
    if Z is None:
        return None
    out = np.full(Z.shape[1], np.nan)
    for j in range(Z.shape[1]):
        z = Z[:, j]
        z = z[~np.isnan(z)]
        if len(z) >= 150:
            q = max(int(len(z) * 0.05), 1)
            out[j] = np.sort(z)[:q].mean()
    return out


@signal("mdd_252", "risk", "بیشترین افت ۲۵۲ روزه", "Max drawdown 252d", "منفی بیشترین افت از اوج روی سطح TR", "Magdon-Ismail & Atiya (2004)", window=252)
def mdd_252(mk, a):
    Z = W(mk.LR, a, 252)
    if Z is None:
        return None
    lv = np.cumsum(Z, axis=0)
    dd = lv - np.maximum.accumulate(lv, axis=0)
    return dd.min(axis=0)           # منفی‌تر = بدتر؛ پس خود مقدار امتیاز است


@signal("neg_skew", "risk", "چولگی منفی (بخت‌آزمایی)", "Negative skewness", "منفی چولگی بازده روزانهٔ ۲۵۲ روز", "Harvey & Siddique (2000)؛ Boyer, Mitton & Vorkink (2010)", window=252)
def neg_skew(mk, a):
    Z = W(mk.X, a, 252)
    if Z is None:
        return None
    with np.errstate(all="ignore"):
        m = np.nanmean(Z, axis=0)
        s = np.nanstd(Z, axis=0)
        sk = np.nanmean(((Z - m) / s) ** 3, axis=0)
    return np.where(cnt(Z) >= 150, -sk, np.nan)


def _range_vol(mk, a, w, kind):
    H, L, O, C, P = (W(A, a, w) for A in (mk.hi, mk.lo, mk.open, mk.close, mk.prev))
    if H is None:
        return None
    with np.errstate(all="ignore"):
        hl = np.log(H / L)
        co = np.log(C / O)
        ho, lo_ = np.log(H / O), np.log(L / O)
        hc, lc = np.log(H / C), np.log(L / C)
        if kind == "park":
            v = hl ** 2 / (4 * np.log(2))
        elif kind == "gk":
            v = 0.5 * hl ** 2 - (2 * np.log(2) - 1) * co ** 2
        elif kind == "rs":
            v = ho * hc + lo_ * lc
        elif kind == "yz":
            on = np.log(O / P)
            n = np.sum(~np.isnan(on), axis=0)
            k = 0.34 / (1.34 + (n + 1) / np.maximum(n - 1, 1))
            so = np.nanvar(on, axis=0, ddof=1)
            sc = np.nanvar(co, axis=0, ddof=1)
            srs = np.nanmean(ho * hc + lo_ * lc, axis=0)
            var = so + k * sc + (1 - k) * srs
            ranged = np.nanmean((H > L).astype(float), axis=0)
            return np.where((n >= 0.6 * w) & (ranged >= 0.4) & (var > 0), -np.sqrt(var), np.nan)
        var = np.nanmean(v, axis=0)
        ranged = np.nanmean(np.where(np.isnan(hl), np.nan, (hl > 0).astype(float)), axis=0)
    ok = (np.sum(~np.isnan(v), axis=0) >= 0.6 * w) & (ranged >= 0.4) & (var > 0)       # روزهای قفل (H=L) برآورد را به پایین سوگیر می‌کنند
    return np.where(ok, -np.sqrt(var), np.nan)


@signal("vol_parkinson", "risk", "نوسان پارکینسون (بازه High-Low)", "Parkinson range volatility", "منفی √(میانگین ln²(H/L)/(4 ln2)) در ۱۲۶ روز", "Parkinson (1980)", needs="hilo", window=126)
def vol_parkinson(mk, a):
    return _range_vol(mk, a, 126, "park")


@signal("vol_gk", "risk", "نوسان گارمن–کلاس", "Garman–Klass volatility", "منفی √(½ln²(H/L) − (2ln2−1)ln²(C/O))", "Garman & Klass (1980)", needs="hilo", window=126)
def vol_gk(mk, a):
    return _range_vol(mk, a, 126, "gk")


@signal("vol_rs", "risk", "نوسان راجرز–ساچل", "Rogers–Satchell volatility", "منفی √میانگین [ln(H/O)ln(H/C)+ln(L/O)ln(L/C)]", "Rogers & Satchell (1991)", needs="hilo", window=126)
def vol_rs(mk, a):
    return _range_vol(mk, a, 126, "rs")


@signal("vol_yz", "risk", "نوسان یانگ–ژانگ", "Yang–Zhang volatility", "منفی √(σ²_شبانه + kσ²_باز-بسته + (1−k)σ²_RS)", "Yang & Zhang (2000)", needs="hilo", window=126)
def vol_yz(mk, a):
    return _range_vol(mk, a, 126, "yz")


def _mkt_stats(mk, a, w=252):
    Y, x = W(mk.X, a, w), W(mk.mkt[:, None], a, w)
    if Y is None:
        return None
    ok = ~np.isnan(Y)
    n = ok.sum(axis=0)
    Yz, xm = np.where(ok, Y, 0), np.where(ok, x, 0)
    sx, sy, sxx, sxy, syy = xm.sum(0), Yz.sum(0), (xm * xm).sum(0), (xm * Yz).sum(0), (Yz * Yz).sum(0)
    with np.errstate(all="ignore"):
        beta = (n * sxy - sx * sy) / (n * sxx - sx * sx)
        vy = (syy - sy * sy / n) / (n - 1)
        vx = (sxx - sx * sx / n) / (n - 1)
        idio = np.sqrt(np.maximum(vy - beta ** 2 * vx, 0))
    good = n >= 150
    return np.where(good, beta, np.nan), np.where(good, idio, np.nan)


@signal("beta_ols", "risk", "بتای کم (بتای OLS روزانه)", "Low beta (OLS)", "منفی شیب رگرسیون بازده روزانه بر بازار هم‌وزن، ۲۵۲ روز", "Frazzini & Pedersen (2014) BAB؛ Black, Jensen & Scholes (1972)", window=252)
def beta_ols(mk, a):
    r = _mkt_stats(mk, a)
    return None if r is None else -r[0]


@signal("beta_shrunk", "risk", "بتای کم (انقباض Vasicek)", "Low beta (shrunk)", "منفی (۰٫۶β + ۰٫۴·۱)", "Vasicek (1973)؛ Blume (1971)", window=252)
def beta_shrunk(mk, a):
    r = _mkt_stats(mk, a)
    return None if r is None else -(0.6 * r[0] + 0.4)


@signal("beta_dimson", "risk", "بتای کم (دیمسون؛ معاملات ناهمزمان)", "Low beta (Dimson)", "منفی مجموع شیب‌های رگرسیون بازده بر بازار با یک وقفه و یک پیش‌رو", "Dimson (1979)", window=252)
def beta_dimson(mk, a):
    w = 252
    if a - w < 0:
        return None
    Y = mk.X[a - w + 1: a]                                   # روزهای t ≤ a−1 تا پیش‌رو x_{t+1} ≤ x_a باشد (بدون نگاه به آینده)
    Xm = np.column_stack([mk.mkt[a - w: a - 1], mk.mkt[a - w + 1: a], mk.mkt[a - w + 2: a + 1]])
    ok = ~np.isnan(Y)
    out = np.full(Y.shape[1], np.nan)
    for j in range(Y.shape[1]):
        m = ok[:, j] & ~np.isnan(Xm).any(axis=1)
        if m.sum() < 150:
            continue
        A = np.column_stack([np.ones(m.sum()), Xm[m]])
        c, *_ = np.linalg.lstsq(A, Y[m, j], rcond=None)
        out[j] = -c[1:].sum()
    return out


@signal("idio_vol", "risk", "نوسان ایدیوسینکراتیک", "Idiosyncratic volatility", "منفی σ باقیماندهٔ مدل بازار، ۲۵۲ روز", "Ang, Hodrick, Xing & Zhang (2006)", window=252)
def idio_vol(mk, a):
    r = _mkt_stats(mk, a)
    return None if r is None else -r[1]


# ═══════════════════ نقدشوندگی، اندازه و تعلق ═══════════════════
@signal("size", "liquidity", "اندازه (کوچک‌ها)", "Size (small)", "منفی ln ارزش بازار (قیمت × تعداد سهام)", "Banz (1981)؛ Fama & French (1992)", needs="shares", window=1)
def size(mk, a):
    m = mk.mcap[a]
    with np.errstate(all="ignore"):
        return -np.log(np.where(m > 0, m, np.nan))


@signal("amihud", "liquidity", "نقدناپذیری آمیهود", "Amihud illiquidity", "میانگین |r| ÷ ارزش معامله، ۱۲۶ روز (بالاتر = نقدناپذیرتر ⇒ پریمیوم)", "Amihud (2002)", needs="volume", window=126)
def amihud(mk, a):
    r, v = W(mk.X, a, 126), W(mk.val, a, 126)
    if r is None:
        return None
    with np.errstate(all="ignore"):
        x = np.abs(r) / np.where(v > 0, v / 1e6, np.nan)
        m = np.nanmean(x, axis=0)
    return np.where(cnt(x) >= 60, np.log(m + 1e-12), np.nan)


@signal("adv_low", "liquidity", "ارزش معاملات پایین", "Low trading value", "منفی ln میانگین ارزش معاملات روزانه، ۶۳ روز", "Brennan, Chordia & Subrahmanyam (1998)", needs="volume", window=63)
def adv_low(mk, a):
    v = W(mk.val, a, 63)
    if v is None:
        return None
    with np.errstate(all="ignore"):
        m = np.nanmean(v, axis=0)
    return np.where(cnt(v) >= 30, -np.log(m + 1), np.nan)


@signal("turnover_low", "liquidity", "گردش معاملات پایین", "Low share turnover", "منفی ln (حجم ÷ تعداد سهام)، میانگین ۶۳ روز", "Datar, Naik & Radcliffe (1998)", needs="volume", window=63)
def turnover_low(mk, a):
    v, sh = W(mk.vol, a, 63), W(mk.shares, a, 63)
    if v is None:
        return None
    with np.errstate(all="ignore"):
        t = np.nanmean(v / sh, axis=0)
    return np.where(cnt(v) >= 30, -np.log(t + 1e-9), np.nan)


@signal("zero_days", "liquidity", "سهم روزهای بدون تغییر قیمت", "Zero-return days", "سهم روزهای با بازده صفر در ۱۲۶ روز (بالاتر = نقدناپذیرتر)", "Lesmond, Ogden & Trzcinka (1999)", window=126)
def zero_days(mk, a):
    Z = W(mk.X, a, 126)
    if Z is None:
        return None
    return np.where(cnt(Z) >= 90, np.nansum(Z == 0, axis=0) / np.maximum(cnt(Z), 1), np.nan)


@signal("price_low", "liquidity", "قیمت پایین", "Low price", "منفی ln قیمت پایانی", "Blume & Husic (1973)", window=1)
def price_low(mk, a):
    with np.errstate(all="ignore"):
        return -np.log(np.where(mk.close[a] > 0, mk.close[a], np.nan))


# ═══════════════════ سرمایه‌گذاری و تقسیم سود ═══════════════════
@signal("net_issue", "investment", "انتشار خالص سهام (کم)", "Net share issuance (low)", "منفی ln(سهام امروز ÷ سهام ۲۵۲ روز پیش)؛ سهام جایزه و نقدی از هم تفکیک نمی‌شود", "Pontiff & Woodgate (2008)", needs="shares", window=252)
def net_issue(mk, a):
    if a - 252 < 0:
        return None
    with np.errstate(all="ignore"):
        return -np.log(mk.shares[a] / mk.shares[a - 252])


@signal("div_yield", "investment", "بازده نقدی سود (۱۲ ماه)", "Trailing dividend yield", "Σ بازده سود نقدی روز استحقاق در ۲۵۲ روز (r_TR − r_PR)", "Fama & French (1988)", window=252)
def div_yield(mk, a):
    Y = W(mk.Y, a, 252)
    return None if Y is None else Y.sum(axis=0)


# ═══════════════════ بنیادی (point-in-time از رهاورد۳۶۵) ═══════════════════
FUND_KEYS = {
    "roe": lambda t: "ROE" in t, "roa": lambda t: "ROA" in t,
    "net_margin": lambda t: t.startswith("سودخالصبهفروش"), "op_margin": lambda t: t.startswith("حاشیهسودعملیاتی"),
    "d_a": lambda t: t == "نسبتبدهی", "d_e": lambda t: t == "نسبتبدهیبهارزشویژه",
    "current": lambda t: t == "نسبتجاری", "quick": lambda t: t == "نسبتآنی", "int_cov": lambda t: t.startswith("نسبتپوششبدهی"),
    "asset_turn": lambda t: t.startswith("گردشمجموعدارایی"),
}


def load_fund(cols, dates):
    """{کلید: DataFrame[روز × نماد]} آخرین مقدار سالانهٔ شناخته‌شده و {کلید}_std (انحراف معیار ۵ سال اخیر)؛ و EPS آخرین ۱۲ماهه."""
    f1, f2 = ROOT / "data/fundamentals/rahavard_long.csv", ROOT / "data/fundamentals/rahavard_eps.csv"
    if not (f1.exists() and f2.exists()):
        return None
    from fetch_corporate_actions import j2g
    L = pd.read_csv(f1, dtype={"ins_code": str})
    L = L[L.stmt == "ratio"].copy()
    L["rn"] = L.row.str.replace(r"[‌\s]+", "", regex=True)
    E = pd.read_csv(f2, dtype={"ins_code": str})
    E["date"] = pd.to_datetime(E["date"])
    E["fy"] = pd.to_datetime(E["fy"])
    E12 = E[E.period == 12]
    first = E12.groupby(["ins_code", "fy"]).date.min()
    L["fy_end"] = L.fy.map({s: pd.Timestamp(str(j2g(*map(int, s.split("/"))))[:10]) for s in L.fy.unique()})
    out = {}
    didx = pd.DatetimeIndex(dates)
    for key, pred in FUND_KEYS.items():
        sub = L[L.rn.map(pred)].sort_values(["audited", "represented"])
        g = sub.groupby(["ins_code", "fy_end"]).value.last().reset_index()
        g["avail"] = [first.get((c, f), pd.NaT) for c, f in zip(g.ins_code, g.fy_end)]
        g["avail"] = g.avail.fillna(g.fy_end + pd.Timedelta(days=120)) + pd.Timedelta(days=1)
        out[key] = g
    out["_eps"] = E12.sort_values("date")
    # نمادهای بدون رهاورد: نسبت‌ها و EPS از کدال (tools/fetch_codal_fundamentals.py) اشتقاق می‌شود؛ مقیاس‌ها با رهاورد یکی است
    # (ROE/حاشیه به درصد؛ بدهی÷دارایی و گردش دارایی نسبت). جاری، پوشش بدهی از کدال ساخته نمی‌شود.
    import build_quality as bq
    C = bq.codal_base(set(L.ins_code))
    if len(C):
        def _put(key, val):
            g = C[["ins_code", "fy_end", "avail"]].assign(value=val).replace([np.inf, -np.inf], np.nan).dropna(subset=["value"])
            out[key] = pd.concat([out[key], g], ignore_index=True)
        ok = (C.equity > 0)
        _put("roe", np.where(ok, 100.0 * C.net_income / C.equity, np.nan))
        _put("roa", np.where(C.assets > 0, 100.0 * C.net_income / C.assets, np.nan))
        _put("net_margin", np.where(C.revenue > 0, 100.0 * C.net_income / C.revenue, np.nan))
        _put("op_margin", np.where(C.revenue > 0, 100.0 * C.op_profit / C.revenue, np.nan))
        _put("d_a", np.where(C.assets > 0, C.liabilities / C.assets, np.nan))
        _put("d_e", np.where(C.equity != 0, C.liabilities / C.equity, np.nan))
        _put("asset_turn", np.where(C.assets > 0, C.revenue / C.assets, np.nan))
        # EPS (ریال) ≈ سود خالص ÷ سرمایهٔ ثبت‌شده × ۱۰۰۰ (ارزش اسمی ۱۰۰۰ ریال [تأیید لازم]) — بی‌واحد از واحد پولی صورت مالی
        ce = C[(C.capital > 0) & C.net_income.notna()][["ins_code", "fy_end", "avail", "net_income", "capital"]].copy()
        ce["eps"] = ce.net_income / ce.capital * 1000.0
        ce["date"] = ce.avail
        out["_eps_codal"] = ce.sort_values("date")
    return out


def _fund_at(mk, key, a, std=False, diff=False):
    g = mk.fund.get(key) if mk.fund else None
    if g is None:
        return None
    t = mk.dates[a]
    res = np.full(mk.k, np.nan)
    gi = g[g.avail <= t]
    gi = gi[(t - gi.fy_end).dt.days <= 540] if len(gi) else gi
    pos = {c: i for i, c in enumerate(mk.cols)}
    for c, x in gi.groupby("ins_code"):
        i = pos.get(c)
        if i is None:
            continue
        x = x.sort_values("fy_end")
        if std:
            v = x.value.tail(5)
            if len(v) >= 3:
                res[i] = v.std(ddof=1)
        elif diff:
            if len(x) >= 2:
                res[i] = x.value.iloc[-1] - x.value.iloc[-2]
        else:
            res[i] = x.value.iloc[-1]
    return res


def _mk_fund(key, name, fa, en, formula, ref, sign=1.0, std=False, diff=False):
    @signal(name, "quality", fa, en, formula, ref, needs="fund", window=540)
    def f(mk, a, key=key, sign=sign, std=std, diff=diff):
        v = _fund_at(mk, key, a, std, diff)
        return None if v is None else sign * v
    return f


_mk_fund("roe", "q_roe", "سودآوری: ROE", "ROE", "آخرین ROE سالانهٔ اعلام‌شده", "Novy-Marx (2013)؛ MSCI Quality")
_mk_fund("roa", "q_roa", "سودآوری: ROA", "ROA", "آخرین ROA سالانهٔ اعلام‌شده", "Fama & French (2015) RMW")
_mk_fund("net_margin", "q_net_margin", "حاشیهٔ سود خالص", "Net margin", "سود خالص ÷ فروش", "Novy-Marx (2013)")
_mk_fund("op_margin", "q_op_margin", "حاشیهٔ سود عملیاتی", "Operating margin", "سود عملیاتی ÷ فروش", "Novy-Marx (2013)")
_mk_fund("d_a", "q_low_da", "اهرم پایین (بدهی ÷ دارایی)", "Low leverage D/A", "منفی نسبت بدهی", "Asness, Frazzini & Pedersen (2019) — safety")
_mk_fund("d_e", "q_low_de", "اهرم پایین (بدهی ÷ حقوق)", "Low leverage D/E", "منفی نسبت بدهی به ارزش ویژه", "MSCI Quality")
_mk_fund("current", "q_current", "نسبت جاری", "Current ratio", "دارایی جاری ÷ بدهی جاری", "Piotroski (2000) — ساده‌شده")
_mk_fund("asset_turn", "q_asset_turn", "گردش دارایی", "Asset turnover", "فروش ÷ دارایی", "Piotroski (2000)")
_mk_fund("int_cov", "q_int_cov", "پوشش بدهی", "Interest/debt coverage", "نسبت پوشش بدهی", "Altman (1968) — اشتقاق")
_mk_fund("roe", "q_roe_stab", "ثبات سودآوری", "ROE stability", "منفی انحراف معیار ROE (۵ سال مالی، دست‌کم ۳)", "MSCI Quality؛ AQR QMJ", sign=-1.0, std=True)
_mk_fund("roe", "q_droe", "بهبود ROE", "ROE change", "ROE جاری − ROE سال قبل", "Piotroski (2000) ΔROA", diff=True)


@signal("ep", "value", "بازده سود هر سهم (E/P)", "Earnings yield", "EPS آخرین ۱۲ماهه ÷ قیمت (EPS با نسبت تعداد سهام تعدیل می‌شود)", "Basu (1977)؛ Fama & French (1992)", needs="fund", window=540)
def ep(mk, a):
    if not mk.fund:
        return None
    E = mk.fund["_eps"]
    t = mk.dates[a]
    e = E[E.date <= t].groupby("ins_code").tail(1)
    e = e[(t - e.date).dt.days <= 540]
    Ec = mk.fund.get("_eps_codal")
    if Ec is not None and len(Ec):                               # نمادهای فقط-کدال
        ec = Ec[Ec.date <= t].groupby("ins_code").tail(1)
        ec = ec[(t - ec.date).dt.days <= 540]
        e = pd.concat([e, ec[~ec.ins_code.isin(set(e.ins_code))][["ins_code", "date", "eps"]]], ignore_index=True)
    out = np.full(mk.k, np.nan)
    pos = {c: i for i, c in enumerate(mk.cols)}
    for r in e.itertuples():
        i = pos.get(r.ins_code)
        if i is None or not (mk.close[a, i] > 0) or r.eps != r.eps:
            continue
        j = int(mk.dates.searchsorted(r.date))
        j = min(j, mk.n - 1)
        s0, s1 = mk.shares[j, i], mk.shares[a, i]
        adj = (s0 / s1) if (s0 > 0 and s1 > 0) else 1.0           # افزایش سرمایه پس از اعلام EPS آن را رقیق می‌کند
        out[i] = r.eps * adj / mk.close[a, i]
    return out


# ═══════════════════ ذخیره و آزمون ═══════════════════
def compute_store(mk: Market, names=None, verbose=True):
    """ماتریس خام S[name] با ردیف‌ها = ریبالانس‌های ماهانهٔ بعد از WARM + آخرین روز؛ بازمی‌گرداند (idx_list، dict)."""
    me = [int(a) for a in mk.month_end if a >= WARM]
    idx = me + [mk.n - 1]
    S = {}
    for nm, meta in REG.items():
        if names and nm not in names:
            continue
        if meta["needs"] == "fund" and not mk.fund:
            continue
        M = np.full((len(idx), mk.k), np.nan)
        for r, a in enumerate(idx):
            try:
                v = meta["fn"](mk, a)
            except Exception as e:  # noqa: BLE001
                v = None
                if verbose:
                    print("خطا", nm, a, type(e).__name__, e)
            if v is not None:
                M[r] = v
        S[nm] = M
        if verbose:
            print(f"  {nm:18s} پوشش میانگین {np.nanmean((~np.isnan(M)).sum(axis=1)):.0f}")
    return idx, S


def winsor_z(v, ok, lo=1, hi=99):
    x = np.where(ok & ~np.isnan(v), v, np.nan)
    if np.sum(~np.isnan(x)) < 30:
        return np.full_like(v, np.nan)
    a, b = np.nanpercentile(x, [lo, hi])
    x = np.clip(x, a, b)
    sd = np.nanstd(x)
    return (x - np.nanmean(x)) / sd if sd > 0 else np.full_like(v, np.nan)


def neutral(z, groups, min_n=6):
    """کسر میانگین درون گروه (صنعت)؛ گروه‌های کوچک‌تر از min_n دست‌نخورده."""
    s = pd.Series(z)
    g = s.groupby(groups)
    m = g.transform("mean")
    n = g.transform("count")
    return np.where(n >= min_n, s - m, s.values)


def spearman_rows(x, y):
    m = ~np.isnan(x) & ~np.isnan(y)
    if m.sum() < 20:
        return np.nan
    return float(np.corrcoef(pd.Series(x[m]).rank().values, pd.Series(y[m]).rank().values)[0, 1])


def nw_t(x, L=3):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    T = len(x)
    if T < 12:
        return np.nan
    e = x - x.mean()
    v = e @ e / T + 2 * sum((1 - l / (L + 1)) * (e[l:] @ e[:-l]) / T for l in range(1, L + 1))
    return float(x.mean() / np.sqrt(v / T)) if v > 0 else np.nan


def zoo(mk: Market, idx, S, cost_bp=100.0):
    """جدول IC و دهک برای همهٔ معیارها. بازده آینده: ماه شمسی بعد (a+1..b)."""
    rows = len(idx) - 1
    me = idx[:-1]
    fw = np.full((rows, mk.k), np.nan)
    ok = np.zeros((rows, mk.k), bool)
    use = []
    for r in range(rows):
        a = me[r]
        b = me[r + 1] if r + 1 < rows else None
        if b is None or mk.dates[a + 1] < EVAL_FROM:
            continue
        fw[r] = mk.fwd(a, b)
        ok[r] = mk.eligible(a) & ~np.isnan(fw[r])
        use.append(r)
    out = {}
    cum_h = {}
    for h in (3, 6, 12):
        F = np.full((rows, mk.k), np.nan)
        for r in use:
            seg = fw[r:r + h]
            if seg.shape[0] == h:
                F[r] = np.where(np.isnan(seg).any(axis=0), np.nan, np.prod(1 + seg, axis=0) - 1)
        cum_h[h] = F
    for nm, M in S.items():
        ics, ic3, ic6, ic12, spreads, q5, alls, to5, ncov, ics_n = [], [], [], [], [], [], [], [], [], []
        prev5 = None
        pct_prev = None
        autoc = []
        for r in use:
            v = np.where(ok[r], M[r], np.nan)
            m = ~np.isnan(v)
            if m.sum() < 50:
                continue
            ncov.append(int(m.sum()))
            ics.append(spearman_rows(v, fw[r]))
            ics_n.append(spearman_rows(neutral(winsor_z(M[r], ok[r]), mk.sector), neutral(winsor_z(fw[r], ok[r]), mk.sector)))
            for h, lst in ((3, ic3), (6, ic6), (12, ic12)):
                lst.append(spearman_rows(v, cum_h[h][r]))
            order = np.where(m)[0][np.argsort(v[m], kind="stable")]
            gs = np.array_split(order, 5)
            r5, r1 = fw[r][gs[4]].mean(), fw[r][gs[0]].mean()
            spreads.append(r5 - r1)
            q5.append(r5)
            alls.append(np.nanmean(fw[r][order]))
            cur = set(gs[4])
            to5.append(np.nan if prev5 is None else 1 - len(cur & prev5) / max(len(cur), 1))
            prev5 = cur
            pr = pd.Series(v).rank().values
            if pct_prev is not None:
                autoc.append(spearman_rows(pr, pct_prev))
            pct_prev = pr
        ics = np.array(ics)
        if len(ics) < 12:
            continue
        h = len(ics) // 2
        sp, q5a, ala = np.array(spreads), np.array(q5), np.array(alls)
        ex = q5a - ala
        out[nm] = {
            "n_months": int(len(ics)), "names": float(np.mean(ncov)),
            "ic": float(np.nanmean(ics)), "ic_t": nw_t(ics), "icir": float(np.nanmean(ics) / np.nanstd(ics, ddof=1) * np.sqrt(12)),
            "ic_hit": float(np.nanmean(ics > 0) * 100), "ic_h1": float(np.nanmean(ics[:h])), "ic_h2": float(np.nanmean(ics[h:])),
            "ic_neutral": float(np.nanmean(ics_n)), "ic_neutral_t": nw_t(np.array(ics_n)),
            "ic_3m": float(np.nanmean(ic3)), "ic_6m": float(np.nanmean(ic6)), "ic_12m": float(np.nanmean(ic12)),
            "q5_minus_q1_ann": float(sp.mean() * 1200), "q5_minus_q1_t": nw_t(sp),
            "q5_excess_ann": float(ex.mean() * 1200), "q5_excess_t": nw_t(ex),
            "q5_turn": float(np.nanmean(to5) * 100), "rank_autocorr": float(np.nanmean(autoc)) if autoc else np.nan,
        }
        out[nm]["q5_excess_net_ann"] = out[nm]["q5_excess_ann"] - float(np.nanmean(to5)) * cost_bp / 1e4 * 1200
    return out, (use, ok, fw)


def corr_matrix(mk, idx, S, use, ok):
    names = list(S)
    acc = np.zeros((len(names), len(names)))
    cntm = np.zeros_like(acc)
    for r in use[::3]:                     # هر سه ماه یک نمونه (سرعت)
        D = pd.DataFrame({n: np.where(ok[r], S[n][r], np.nan) for n in names})
        C = D.rank().corr().values
        m = ~np.isnan(C)
        acc[m] += C[m]
        cntm[m] += 1
    with np.errstate(all="ignore"):
        return names, np.where(cntm > 0, acc / cntm, np.nan)


def main():
    import build_ui_extra as bx
    _, info, Ra = bx.base_panel(bx.ALL_MARKETS)
    mk = Market(Ra, info)
    import build_quality as bq  # noqa: F401
    mk.fund = load_fund(mk.cols, mk.dates)
    print(f"{len(REG)} معیار ثبت‌شده؛ بنیادی {'هست' if mk.fund else 'نیست'}")
    idx, S = compute_store(mk)
    Z, (use, ok, fw) = zoo(mk, idx, S)
    names, C = corr_matrix(mk, idx, S, use, ok)
    meta = {n: {k: v for k, v in REG[n].items() if k != "fn"} for n in S}
    outd = ROOT / "data" / "research"
    outd.mkdir(parents=True, exist_ok=True)
    (outd / "signal_zoo.json").write_text(json.dumps({"meta": meta, "stats": Z, "corr": {"names": names, "m": np.round(C, 3).tolist()},
                                                      "asof": str(mk.dates[-1].date())}, ensure_ascii=False, default=lambda o: None if o != o else float(o)), encoding="utf-8")
    df = pd.DataFrame(Z).T
    df.insert(0, "family", [meta[n]["family"] for n in df.index])
    print(df.sort_values("ic_t", ascending=False).round(3)[["family", "names", "ic", "ic_t", "icir", "q5_excess_ann", "q5_excess_t", "q5_turn", "ic_h1", "ic_h2"]].to_string())
    df.to_csv(outd / "signal_zoo.csv", encoding="utf-8")


if __name__ == "__main__":
    if "--zoo" in sys.argv:
        main()
