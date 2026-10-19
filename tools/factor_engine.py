#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""موتور فاکتور برای «برنامهٔ اقدام»: دهک‌ها، IC، بافر ورود/خروج، تأخیر اجرا، آمار معناداری و وضعیت زنده (فصل ۵ §۵٫۶).

با گروه‌های ۵تایی، بدون بافر و بدون تأخیر، دقیقاً همان سری ماهانهٔ `build_ui_extra.factor` را می‌دهد (آزمون: `python tools/factor_engine.py --selftest`).

مفاهیم
------
سیگنال   : mom (مومنتوم ۱۲−۱)، lowvol (منفی نوسان ۲۵۲ روزه)، quality (امتیاز رهاورد؛ ماتریس qscore از tools/build_quality.py).
ریبالانس : آخرین روز معاملاتی هر ماه شمسی (روز a)؛ سیگنال تا بستهٔ روز a. سبد از بستهٔ روز a+delay خریداری و تا بستهٔ آخر دورهٔ بعد نگه داشته می‌شود.
دهک k   : k=1 ضعیف‌ترین امتیاز … k=G قوی‌ترین؛ هم‌وزن؛ درون ماه خرید و نگهداری (وزن‌ها با بازده رانش می‌کنند).
TOP      : سبد قابل‌اجرا = بالاترین top_frac از امتیازها با بافر (ورود اگر رتبهٔ درصدی ≤ entry؛ ماندن اگر ≤ exit).
گردش     : ½ Σ|وزن هدف − وزن رانش‌یافته|؛ هزینه = گردش × هزینهٔ رفت‌وبرگشت.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import rebuild_ew_rebalanced as ewr  # noqa: E402

START_EVAL = pd.Timestamp("2016-03-20")


class Panel:
    """پانل بازده روزانهٔ کل (TR) و مجموع‌های تجمعی برای محاسبهٔ سریع سیگنال."""

    def __init__(self, R: pd.DataFrame):
        M = R.pivot_table(index="date", columns="ins_code", values="r_tr", aggfunc="last")
        M = M[M.index >= "2012-01-01"]
        self.M, self.dates, self.cols = M, M.index, M.columns
        X = M.values
        self.X, n, k = X, *X.shape
        jm = np.array([ewr.g2j(d.year, d.month, d.day)[0] * 100 + ewr.g2j(d.year, d.month, d.day)[1] for d in self.dates])
        self.month_end = np.where(jm[1:] != jm[:-1])[0]            # آخرین روز هر ماه شمسی
        lr = np.log1p(np.where(np.isnan(X), 0, X))
        z = np.zeros(k)
        self.cum = np.vstack([z, np.cumsum(lr, axis=0)])
        self.nz = np.vstack([z, np.cumsum((np.nan_to_num(X) != 0), axis=0)])
        x0 = np.where(np.isnan(X), 0, X)
        self.c1 = np.vstack([z, np.cumsum(x0, axis=0)])
        self.c2 = np.vstack([z, np.cumsum(x0 ** 2, axis=0)])
        self.have = np.vstack([z, np.cumsum(~np.isnan(X), axis=0)])
        # حجم معامله: روز بی‌معامله (توقف/صف) قابل خرید و فروش نیست (ممیزی سوگیری ۲۰۲۶-۱۰-۱۹، A2)
        self.vol = R.pivot_table(index="date", columns="ins_code", values="zTotTran", aggfunc="last").reindex(index=self.dates, columns=self.cols).values if "zTotTran" in R.columns else np.ones_like(X)

    def traded_signal(self, a: int):
        """معامله در آخرین روز باز بازار تا a (روز سیگنال)."""
        self.traded(0)
        d, k = min(max(a, 0), len(self.dates) - 1), 0
        while d > 0 and not self._open[d] and k < 90:
            d -= 1
            k += 1
        return np.nan_to_num(self.vol[d]) > 0

    def traded(self, a: int):
        """معامله در روز a؛ اگر بازار آن روز سراسری بسته بود (کمتر از ۲۰٪ نمادها معامله)، نخستین روز بازگشایی (همان signals.Market.exec_day)."""
        n = len(self.dates)
        a = min(max(a, 0), n - 1)
        if not hasattr(self, "_open"):
            has = (~np.isnan(self.X)).sum(axis=1)
            self._open = (np.nan_to_num(self.vol) > 0).sum(axis=1) >= 0.2 * np.maximum(has, 1)
        k = 0
        while a < n - 1 and not self._open[a] and k < 90:
            a += 1
            k += 1
        return np.nan_to_num(self.vol[a]) > 0

    def score(self, signal: str, a: int, qscore=None):
        """(امتیاز، واجد) در روز a. واجدیت قیمتی: ≥۸۰٪ روز داده و ≥۵۰٪ روز غیرصفر در پنجره، و بازدهٔ روز a موجود."""
        i1, i0 = (a + 1 - 21, a + 1 - 252) if signal in ("mom", "quality") else (a + 1, a + 1 - 252)
        w = i1 - i0
        ok = ((self.have[i1] - self.have[i0]) >= 0.8 * w) & ((self.nz[i1] - self.nz[i0]) >= 0.5 * w) & ~np.isnan(self.X[a]) & self.traded_signal(a)
        if signal == "quality":
            d = self.dates[a]
            if qscore is None or d not in qscore.index:
                return np.full(self.X.shape[1], np.nan), np.zeros(self.X.shape[1], bool)
            s = qscore.loc[d].reindex(self.cols).values.astype(float)
            ok &= ~np.isnan(s)
            return s, ok
        if signal == "mom":
            return self.cum[i1] - self.cum[i0], ok
        nn = np.maximum(self.have[i1] - self.have[i0], 1)
        mu = (self.c1[i1] - self.c1[i0]) / nn
        return -np.sqrt(np.maximum((self.c2[i1] - self.c2[i0]) / nn - mu ** 2, 0)), ok


def _spearman(x, y):
    if len(x) < 10:
        return np.nan
    rx = pd.Series(x).rank().values
    ry = pd.Series(y).rank().values
    return float(np.corrcoef(rx, ry)[0, 1])


def run(P: Panel, signal: str, ngroups: int = 10, tops: dict | None = None, delay: int = 0, qscore=None, min_names: int = 50, live: bool = False):
    """ماه‌به‌ماه: گروه‌های ngroups‌تایی، ALL و سبدهای TOP با بافر.
    tops: {نام: (ورود، خروج)} رتبهٔ درصدی از بالا؛ مثلاً {"T20_30": (0.2, 0.3)} = ورود اگر در ۲۰٪ برتر، ماندن تا ۳۰٪.
    live=True: وضعیت امتیازها در آخرین روز داده (برای فهرست اقدام) هم در out["live"] می‌آید."""
    X, dates, n = P.X, P.dates, len(P.dates)
    tops = tops or {"TOP": (0.2, 0.2)}
    keys = [f"G{k}" for k in range(1, ngroups + 1)] + ["ALL"] + list(tops)
    mret, tov, nn = ({k: [] for k in keys} for _ in range(3))
    prev = {}
    held = {t: np.zeros(X.shape[1], bool) for t in tops}
    ic, ends, starts, starts1 = [], [], [], []
    me = P.month_end
    for a, b in zip(me[:-1], me[1:]):
        if a < 252 + 21:
            continue
        s, ok = P.score(signal, a, qscore)
        ok = ok & ~np.isnan(X[a + 1]) & P.traded(a + 1 + delay)   # فقط روز اجرا و معامله‌شده در آن روز؛ شرط «داده در پایان دوره» نگاه به آینده بود (فصل ۱۴ §۱۴٫۲٫۱)
        idx = np.where(ok)[0]
        if len(idx) < min_names:
            continue
        lo, hi = a + 1 + delay, min(b + 1 + delay, n)
        if hi - lo < 5:
            continue
        order = idx[np.argsort(s[idx], kind="stable")]
        groups = {f"G{k + 1}": g for k, g in enumerate(np.array_split(order, ngroups))}
        groups["ALL"] = idx
        pct = np.full(X.shape[1], np.nan)
        pct[order[::-1]] = (np.arange(len(order)) + 0.5) / len(order)       # رتبهٔ درصدی از بالا (۰ = بهترین)
        for t, (en, ex) in tops.items():
            keep = held[t] & ok & (pct <= ex)
            sel = np.where(keep | (ok & (pct <= en)))[0]
            held[t] = np.zeros(X.shape[1], bool)
            held[t][sel] = True
            groups[t] = sel
        seg_all = X[lo:hi]
        for q, g in groups.items():
            seg = seg_all[:, g]
            grow = np.nanprod(1 + np.nan_to_num(seg), axis=0)
            w_new = np.zeros(X.shape[1])
            w_new[g] = 1 / len(g)
            tov[q].append(0.5 * np.abs(w_new - prev[q]).sum() if q in prev else None)
            wd = np.zeros(X.shape[1])
            wd[g] = w_new[g] * grow
            prev[q] = wd / wd.sum() if wd.sum() > 0 else w_new
            mret[q].append(float(grow.mean() - 1))
            nn[q].append(len(g))
        g_all = np.nanprod(1 + np.nan_to_num(seg_all[:, idx]), axis=0) - 1
        ic.append(_spearman(s[idx], g_all))
        ends.append(dates[min(b + delay, n - 1)])
        starts.append(dates[a])
        starts1.append(dates[a + 1])
    keep_i = [i for i, d in enumerate(starts1) if d >= START_EVAL]
    out = {"end": [ends[i] for i in keep_i], "sig_date": [starts[i] for i in keep_i],
           "ret": {k: np.array([mret[k][i] for i in keep_i]) for k in keys},
           "to": {k: np.array([np.nan if tov[k][i] is None else tov[k][i] for i in keep_i]) for k in keys},
           "n": {k: float(np.mean([nn[k][i] for i in keep_i])) for k in keys},
           "ic": np.array([ic[i] for i in keep_i]), "ngroups": ngroups, "tops": tops}
    if keep_i:
        for k in keys:
            out["to"][k][0] = np.nan                 # ساخت اولیه جزو گردش جاری نیست
    if live:
        a = n - 1                                    # آخرین روز داده (نه لزوماً پایان ماه)
        s, ok = P.score(signal, a, qscore)
        idx = np.where(ok)[0]
        order = idx[np.argsort(s[idx], kind="stable")]
        pct = np.full(X.shape[1], np.nan)
        pct[order[::-1]] = (np.arange(len(order)) + 0.5) / len(order)
        out["live"] = {"date": dates[a], "score": s, "ok": ok, "pct": pct, "held_last_rebalance": held}
    return out


# ── آمار ───────────────────────────────────────────────────────────────────────
def nw_t(x, L=3):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    T = len(x)
    if T < 12:
        return np.nan
    e = x - x.mean()
    v = e @ e / T + 2 * sum((1 - l / (L + 1)) * (e[l:] @ e[:-l]) / T for l in range(1, L + 1))
    return float(x.mean() / np.sqrt(v / T)) if v > 0 else np.nan


def ann(x):
    x = np.asarray(x, float)
    if len(x) == 0:
        return float('nan')
    return float(((1 + x).prod() ** (12 / len(x)) - 1) * 100)


def mdd_of(x):
    c = np.cumprod(1 + np.asarray(x, float))
    return float((c / np.maximum.accumulate(c) - 1).min() * 100)


def net(ret, to, cost_bp):
    t = np.nan_to_num(np.asarray(to, float))
    return np.asarray(ret, float) - t * cost_bp / 1e4


def boot_mean(x, reps=2000, block=3, seed=7):
    """بوت‌استرپ ایستای بلوکی: توزیع میانگین سری؛ (فاصلهٔ ۹۵٪، احتمال میانگین > ۰)."""
    x = np.asarray(x, float)
    T = len(x)
    rng = np.random.default_rng(seed)
    means = np.empty(reps)
    for r in range(reps):
        i = rng.integers(0, T)
        out = np.empty(T)
        for t in range(T):
            out[t] = x[i]
            i = rng.integers(0, T) if rng.random() < 1 / block else (i + 1) % T
        means[r] = out.mean()
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)), float((means > 0).mean())


def stats_of(res: dict, key: str, cost_bp: float = 125.0, bench: str = "ALL") -> dict:
    """آمار یک سبد (G1..Gn یا TOP) نسبت به ALL: ناخالص/خالص، t، IR، برد، افت، گردش، پایداری، بوت‌استرپ."""
    r, a = res["ret"][key], res["ret"][bench]
    to, toa = res["to"][key], res["to"][bench]
    rn, an = net(r, to, cost_bp), net(a, toa, cost_bp)
    ex_g, ex_n = r - a, rn - an
    half = len(ex_n) // 2
    lo, hi, p = boot_mean(ex_n)
    roll = np.array([np.prod(1 + ex_n[i:i + 12]) - 1 for i in range(len(ex_n) - 11)]) if len(ex_n) >= 12 else np.array([])
    by_year = {}
    for d, v in zip(res["end"], ex_n):
        by_year.setdefault(ewr.g2j(d.year, d.month, d.day)[0], []).append(v)
    return {
        "ann_gross": ann(r), "ann_net": ann(rn), "ann_all_net": ann(an), "excess_net": ann(rn) - ann(an), "excess_gross": ann(r) - ann(a),
        "vol": float(np.std(r, ddof=1) * np.sqrt(12) * 100), "te": float(np.std(ex_n, ddof=1) * np.sqrt(12) * 100),
        "ir": float(ex_n.mean() / ex_n.std(ddof=1) * np.sqrt(12)) if ex_n.std() > 0 else np.nan,
        "t_gross": nw_t(ex_g), "t_net": nw_t(ex_n), "hit": float((ex_n > 0).mean() * 100),
        "t_h1": nw_t(ex_n[:half]), "t_h2": nw_t(ex_n[half:]), "ex_h1": float(ex_n[:half].mean() * 1200), "ex_h2": float(ex_n[half:].mean() * 1200),
        "mdd_active": mdd_of(ex_n), "turn_ann": float(np.nansum(to) / (len(r) / 12) * 100),
        "names": res["n"][key], "boot_lo": lo * 1200, "boot_hi": hi * 1200, "boot_p": p,
        "roll12_win": float((roll > 0).mean() * 100) if len(roll) else np.nan, "roll12_worst": float(roll.min() * 100) if len(roll) else np.nan,
        "years": {str(y): round(float(np.prod(1 + np.array(v)) - 1) * 100, 1) for y, v in sorted(by_year.items())},
    }


def ic_stats(res: dict) -> dict:
    ic = res["ic"][~np.isnan(res["ic"])]
    if len(ic) < 12:
        return {}
    return {"ic_mean": float(ic.mean()), "ic_t": nw_t(ic), "icir": float(ic.mean() / ic.std(ddof=1) * np.sqrt(12)), "ic_hit": float((ic > 0).mean() * 100), "n": int(len(ic))}


def monotonicity(res: dict, cost_bp: float = 125.0) -> dict:
    """یکنوایی دهک‌ها: Spearman رتبهٔ دهک با بازده سالانه، تعداد جفت‌های متوالی صعودی، و تفاوت G_n − G_1 (آماره t)."""
    g = res["ngroups"]
    annr = [ann(net(res["ret"][f"G{k}"], res["to"][f"G{k}"], cost_bp)) for k in range(1, g + 1)]
    spread = net(res["ret"][f"G{g}"], res["to"][f"G{g}"], cost_bp) - net(res["ret"]["G1"], res["to"]["G1"], cost_bp)
    return {"ann_net": annr, "spearman": _spearman(np.arange(g), annr), "up_pairs": int(sum(b > a for a, b in zip(annr[:-1], annr[1:]))),
            "pairs": g - 1, "spread_t": nw_t(spread), "spread_ann": ann(spread + 1e-12) if False else float(spread.mean() * 1200)}


def verdict(st: dict, mono: dict, ic: dict, trials: int = 60) -> dict:
    """حکم سخت‌گیرانه، با قاعدهٔ از پیش‌تعیین‌شده (نه انتخاب پس از دیدن نتیجه):
    استقرار پیشنهادی فقط اگر |t خالص| ≥ آستانهٔ تعدیل‌شده برای آزمون‌های چندگانه (≈ ۳٫۰، Harvey–Liu–Zhu) [تأیید لازم]، علامت دو نیمه یکسان،
    بوت‌استرپ ۹۵٪ صفر را در بر نگیرد و یکنوایی دهک‌ها Spearman ≥ ۰٫۶ باشد؛ «شاهد ضعیف» اگر t خالص ≥ ۲ و دو نیمه هم‌علامت؛ وگرنه «بدون برتری معنادار»."""
    t, same = st["t_net"], (st["ex_h1"] > 0) == (st["ex_h2"] > 0)
    boot_ok = st["boot_lo"] > 0 if st["excess_net"] > 0 else st["boot_hi"] < 0
    if abs(t) >= 3 and same and boot_ok and abs(mono["spearman"]) >= 0.6:
        v, why = ("استقرار", "t خالص ≥ ۳، دو نیمه هم‌علامت، بوت‌استرپ بدون صفر، یکنوایی بالا") if st["excess_net"] > 0 else ("معکوس معنادار", "برتری معنادار ولی منفی؛ فروش استقراضی لازم است")
    elif abs(t) >= 2 and same:
        v, why = "شاهد ضعیف", "t خالص ≥ ۲ و دو نیمه هم‌علامت، ولی آستانهٔ آزمون‌های چندگانه رد نشده"
    else:
        v, why = "بدون برتری معنادار", "t خالص < ۲ یا ناپایدار بین دو نیمه"
    return {"verdict": v, "why": why, "t_net": round(t, 2), "trials": trials}


# ── خودآزمایی ───────────────────────────────────────────────────────────────────
def _selftest():
    sys.path.insert(0, str(ROOT / "tools"))
    import build_ui_extra as bx
    _, _, Ra = bx.base_panel(bx.ALL_MARKETS)
    F = bx.factor(Ra, "mom")
    P = Panel(Ra)
    res = run(P, "mom", ngroups=5)
    a = np.array(F["monthly"]["Q5"]) / 100
    b = res["ret"]["G5"]
    print("n ماه:", len(a), len(b), "حداکثر اختلاف G5 با factor():", float(np.max(np.abs(a[: len(b)] - b[: len(a)]))) if len(a) and len(b) else None)
    print("میانگین گردش G5:", float(np.nanmean(res["to"]["G5"]) * 100), "در برابر", np.nanmean([x for x in F["monthly"]["to"]["Q5"] if x is not None]))


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
