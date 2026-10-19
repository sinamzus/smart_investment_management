#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دفتر زندهٔ استراتژی قفل‌شده (ثبت پیشینی + دنبال‌کردن بیرون‌نمونه) — فصل ۱۴ §۱۴٫۹٫۱ و فصل ۸.

چرا: همهٔ شواهد فصل ۱۴ درون‌نمونه‌اند (۱۲۰ آزمایش، DSR ≤ ۰٫۲۷). تنها شاهد بیرون‌نمونه ماه‌های آینده است. این ابزار
  ۱) مشخصات استراتژی را یک‌بار قفل و هش می‌کند (`freeze`)،
  ۲) در هر ماه دستور اجرای تاریخ‌دار می‌سازد (`orders`) و با `--accept` در دفتر ثبت می‌کند،
  ۳) بازده پرتفوی کاغذی را با برتری مورد انتظار بک‌تست مقایسه می‌کند (`track`).

    python tools/live_ledger.py freeze                      # فقط یک‌بار؛ data/live/strategy_v1.json
    python tools/live_ledger.py orders --aum 1e11           # پیش‌نویس دستور اجرا (data/live/orders_<تاریخ>.json|csv)
    python tools/live_ledger.py orders --aum 1e11 --accept  # ثبت در دفتر (data/live/ledger.csv) — فقط روز رسمی پایان ماه
    python tools/live_ledger.py track                       # برتری واقعی در برابر مورد انتظار

قرارداد (همان فصل ۱۴ §۱۴٫۲٫۲): سیگنال در پایان آخرین روز معاملاتی ماه جلالی، اجرا روز معاملاتی بعد؛ بازده از روز بعد از سیگنال.
شروع سرد: اگر دفتر خالی باشد، نخستین ریبالانس κ = ۱ (کل هدف) است؛ از آن به بعد κ = ۰٫۵ (ریبالانس جزئی).
دستور اجرا «پیشنهاد» است؛ هیچ سفارشی به کارگزار ارسال نمی‌شود.
"""
import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import attribution as at  # noqa: E402
import build_lab as bl  # noqa: E402
import construction as cn  # noqa: E402
import factor_engine as fe  # noqa: E402
import signals as sg  # noqa: E402

LIVE = ROOT / "data" / "live"
STRAT = LIVE / "strategy_v1.json"
LEDGER = LIVE / "ledger.csv"
MIN_TRADE_W = 0.0005          # معاملهٔ کمتر از ۰٫۰۵٪ وزن انجام نمی‌شود (گرد و خاک)
PARTICIPATION = 0.10


def frozen_spec():
    """c1 (کم‌نوسان ۲۵۲ + اندازه + بازده نقدی سود)، امتیاز رتبه‌ای، top-fraction بافر ۲۰/۳۰، ریبالانس جزئی ۵۰٪، بورس+فرابورس،
    هزینهٔ رفت‌وبرگشت ۱۲۵ bp [تأیید لازم]، اجرا با تأخیر یک روز (سیگنال در بستهٔ روز a، خرید در بستهٔ روز a+1 — همان قاعدهٔ زنده؛ ممیزی سوگیری ۲۰۲۶-۱۰-۱۹ B2/B3)."""
    return {"signals": [["vol_252", 1.0], ["size", 1.0], ["div_yield", 1.0]], "combine": "rank", "neutral": True,
            "algo": "topfrac", "params": {"entry": 0.2, "exit": 0.3}, "partial": 0.5,
            "universe": {"markets": ["bourse", "farabourse"], "min_adv": 0}, "cost_bp": 125, "delay": 1}


def spec_hash(spec):
    return hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def git_rev():
    try:
        return subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def load_strategy():
    if not STRAT.exists():
        sys.exit("ابتدا: python tools/live_ledger.py freeze")
    S = json.load(open(STRAT, encoding="utf-8"))
    if spec_hash(S["spec"]) != S["spec_hash"]:
        sys.exit("هش مشخصات با فایل قفل‌شده نمی‌خواند — فایل دست‌کاری شده است.")
    return S


def cmd_freeze(a):
    if STRAT.exists():
        sys.exit("استراتژی قبلاً قفل شده است (strategy_v1.json). تغییر مشخصات = نسخهٔ جدید با شناسهٔ دیگر، نه بازنویسی.")
    LIVE.mkdir(parents=True, exist_ok=True)
    mk, lab, _ = bl.get_lab()
    spec = frozen_spec()
    res = cn.backtest(lab, spec, live=False)
    st = fe.stats_of(res, "S", spec["cost_bp"])
    stc = fe.stats_of(res, "S", spec["cost_bp"], bench="CAP")
    ex = fe.net(res["ret"]["S"], res["to"]["S"], spec["cost_bp"]) - fe.net(res["ret"]["ALL"], res["to"]["ALL"], spec["cost_bp"])
    keep = {k: (float(st[k]) if isinstance(st[k], (int, float, np.floating)) else st[k]) for k in
            ("excess_net", "t_net", "ir", "te", "vol", "turn_ann", "ex_h1", "ex_h2", "boot_lo", "boot_hi", "hit", "mdd_active") if k in st}
    keep["frozen_w_mean"] = float(np.nanmean(res["frozen"])) if len(res.get("frozen", [])) else 0.0   # سهم وزن نگه‌داشته‌شدهٔ غیرقابل‌فروش در روز اجرا
    # تفکیک فاکتوری درون‌نمونه (فصل ۱۴ §۱۴٫۷٫۸): فاکتورها همان ردیف‌های تک‌معیار کتابخانه (top-fraction ۲۰/۳۰، بدون تأخیر)
    fruns = {sig: cn.backtest(lab, bl.spec_sig(sig), live=False) for _, _, sig in at.FACTORS if sig}
    fac = at.factor_series(lambda s: (fruns[s]["ret"]["S"], fruns[s]["ret"]["ALL"]))
    keep["attribution"] = at.attribute(res["ret"]["S"], res["ret"]["ALL"], res["to"]["S"], res["to"]["ALL"], spec["cost_bp"], fac)
    imp = res["impact"].get(1e11)
    keep["impact_ann_at_1e11"] = float(np.nansum(imp) / max(len(ex), 1) * 12 * 100) if imp is not None else None   # اثر بازار سالانه (واحد درصد) در ۱۰۰ میلیارد ریال
    S = {"id": "c1-rank-partial50-v1", "frozen_at": pd.Timestamp.now(tz="UTC").isoformat(), "code_commit": git_rev(),
         "data_through": str(mk.dates[-1].date()), "spec": spec, "spec_hash": spec_hash(spec),
         "note": ("ترکیب c1 با امتیاز رتبه‌ای و ریبالانس جزئی ۵۰٪ — این ترکیب دقیق در شبکهٔ ۱۲۰ آزمایش فصل ۱۴ نبود (c1:rank با κ=۱ و c1:equal با κ=۰٫۵ بودند)؛ "
                  "پس آزمایش ۱۲۱ام است و DSR باید با N=۱۲۱ خوانده شود. آمار زیر درون‌نمونه است."),
         "backtest_in_sample": {**keep, "excess_net_vs_cap": float(stc["excess_net"]), "t_net_vs_cap": float(stc["t_net"]),
                                 "months": int(len(ex)), "monthly_mean_excess_net": float(np.mean(ex)), "monthly_std_excess_net": float(np.std(ex, ddof=1)),
                                 "from": str(res["end"][0].date()), "to": str(res["end"][-1].date())},
         "benchmarks": {"ALL": "هم‌وزن واجدان (ریبالانس ماهانه)", "CAP": "ارزش‌وزن واجدان"},
         "rules": {"signal": "آخرین روز معاملاتی ماه جلالی (پایان روز)", "execute": "روز معاملاتی بعد", "kappa_first": 1.0, "kappa": 0.5,
                   "min_trade_w": MIN_TRADE_W, "participation_cap": PARTICIPATION, "review": "پس از ۶ ماه (دست‌کم ۶ ریبالانس رسمی)؛ بازنگری مشخصات پیش از آن مجاز نیست"}}
    json.dump(S, open(STRAT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"قفل شد: {S['id']} هش {S['spec_hash']}\n  درون‌نمونه: برتری خالص {st['excess_net']:+.1f}٪ (t = {st['t_net']:.2f})، نسبت به ارزش‌وزن {stc['excess_net']:+.1f}٪ (t = {stc['t_net']:.2f})، {len(ex)} ماه")


def read_ledger():
    if not LEDGER.exists():
        return pd.DataFrame(columns=["signal_date", "ins_code", "symbol", "w_post", "px_ref", "plan_id", "aum_rial"])
    return pd.read_csv(LEDGER, dtype={"ins_code": str})


def drift_weights(mk, w, a0, a1):
    """وزن‌ها از پایان روز a0 تا پایان روز a1 با بازده کل رانش می‌کنند و نرمال می‌شوند."""
    if a1 <= a0:
        return w
    seg = mk.X[a0 + 1: a1 + 1]
    g = np.nanprod(1 + np.nan_to_num(seg), axis=0) - 1
    v = w * (1 + g)
    return v / v.sum() if v.sum() > 0 else v


def cmd_orders(a):
    S = load_strategy()
    spec = S["spec"]
    mk, lab, _ = bl.get_lab()
    n = mk.n - 1
    asof = mk.dates[n]
    led = read_ledger()
    pos = {c: i for i, c in enumerate(mk.cols)}
    prev = np.zeros(mk.k)
    kappa = float(S["rules"]["kappa_first"])
    last_sig = None
    if len(led):
        last_sig = led.signal_date.max()
        for r in led[led.signal_date == last_sig].itertuples():
            if r.ins_code in pos:
                prev[pos[r.ins_code]] = r.w_post
        a0 = int(mk.dates.searchsorted(pd.Timestamp(last_sig)))
        prev = drift_weights(mk, prev, a0, n)
        kappa = float(S["rules"]["kappa"])
    # روز آخر داده در mk.month_end نیست (آن آرایه فقط تا n−۲ را می‌شناسد)؛ پایان ماه از تقویم جلالی تشخیص داده می‌شود
    official = mk.last_day_is_month_end()
    algo_ = cn.ALGOS[spec["algo"]]
    params = {**algo_["params"], **spec.get("params", {})}
    mk_ok = np.isin(mk.market, spec["universe"]["markets"])
    tgt = cn.live_target(lab, spec, algo_, params, prev, prev > 0, ok_univ=(mk_ok, spec["universe"].get("min_adv", 0)))
    w_star = tgt["target"]
    if w_star.sum() <= 0:
        sys.exit("وزن هدف تهی است.")
    w = prev + kappa * (w_star - prev) if prev.sum() > 0 and kappa < 1 else w_star.copy()
    w = np.maximum(w, 0)
    small = (np.abs(w - prev) < MIN_TRADE_W) & (prev > 0)
    w[small] = prev[small]                           # معاملهٔ ناچیز انجام نمی‌شود
    w[(w < MIN_TRADE_W) & (prev == 0)] = 0           # ورود ناچیز انجام نمی‌شود
    w = w / w.sum()
    # نماد نگه‌داشته‌شده‌ای که در روز سیگنال معامله نشده فروختنی فرض نمی‌شود (A2): وزن فعلی‌اش می‌ماند و بقیه بازنرمال می‌شود
    traded = mk.traded(mk.last_open(n))
    w = cn.freeze_untradable(w, prev, traded)
    aum = float(a.aum)
    v63 = sg.W(mk.val, n, 63)
    adv = np.nan_to_num(np.nanmean(v63, axis=0)) if v63 is not None else np.zeros(mk.k)
    px = np.nan_to_num(mk.close[n])
    orders = []
    for i in np.where((np.abs(w - prev) > 1e-9))[0]:
        d = w[i] - prev[i]
        val = abs(d) * aum
        qty = int(round(val / px[i])) if px[i] > 0 else 0
        part = val / adv[i] if adv[i] > 0 else float("nan")
        orders.append({"symbol": str(mk.sym[i]), "ins_code": str(mk.cols[i]), "side": "BUY" if d > 0 else "SELL", "qty": qty, "ref_price": float(px[i]),
                       "value_rial": float(val), "w_now_pct": float(100 * prev[i]), "w_target_pct": float(100 * w[i]),
                       "adv_participation": None if part != part else float(part),
                       "split_days": int(np.ceil(part / PARTICIPATION)) if part == part and part > 0 else 1,
                       "market": str(mk.market[i]), "traded_signal_day": bool(traded[i])})
    orders.sort(key=lambda o: (o["side"], -o["value_rial"]))
    plan_id = hashlib.sha256(f"{S['spec_hash']}|{asof.date()}|{aum}".encode()).hexdigest()[:12]
    body = {"schema": "sim.trade_plan/1", "plan_id": plan_id, "strategy": S["id"], "spec_hash": S["spec_hash"], "code_commit": git_rev(),
            "asof": str(asof.date()), "created": pd.Timestamp.now(tz="UTC").isoformat(), "official_month_end": official, "cold_start": bool(prev.sum() == 0),
            "kappa": kappa, "aum_rial": aum, "cost_bp_roundtrip": spec["cost_bp"],
            "execution": {"convention": "signal at last trading day close; execute next trading day", "participation_cap": PARTICIPATION,
                          "price_basis": "last_close_ref", "note": "قیمت مرجع آخرین بسته است؛ سامانه باید با قیمت زنده/محدودهٔ مجاز نوسان جایگزین کند"},
            "n_hold": int((w > 0).sum()), "turnover_oneway": float(np.maximum(w - prev, 0).sum()),
            "frozen_w": float(prev[(prev > 0) & ~traded].sum()), "n_frozen": int(((prev > 0) & ~traded).sum()),
            "orders": [{"id": hashlib.sha256((plan_id + o["ins_code"] + o["side"]).encode()).hexdigest()[:10], "type": "rebalance", **o} for o in orders]}   # ins_code یکتاست؛ نماد ممکن است تکراری باشد
    LIVE.mkdir(parents=True, exist_ok=True)
    tag = ("" if official else "_interim")
    fj = LIVE / f"orders_{asof.date()}{tag}.json"
    json.dump(body, open(fj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(LIVE / f"orders_{asof.date()}{tag}.csv", "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.writer(f)
        wr.writerow(["action", "symbol", "market", "qty", "ref_price", "value_rial", "w_now_pct", "w_target_pct", "adv_participation", "split_days"])
        for o in orders:
            wr.writerow([o["side"], o["symbol"], o["market"], o["qty"], o["ref_price"], round(o["value_rial"]), round(o["w_now_pct"], 3), round(o["w_target_pct"], 3),
                         "" if o["adv_participation"] is None else round(o["adv_participation"], 4), o["split_days"]])
    nb = sum(o["side"] == "BUY" for o in orders)
    print(f"{fj.name}: {body['n_hold']} نماد در پرتفوی، {nb} خرید، {len(orders) - nb} فروش، گردش یک‌طرفه {100 * body['turnover_oneway']:.1f}٪، "
          f"{'شروع سرد' if body['cold_start'] else 'ریبالانس جزئی'}، {'رسمی' if official else 'میان‌ماه (پیش‌نویس؛ ثبت رسمی نمی‌شود)'}")
    if a.accept:
        if not official:
            sys.exit("--accept فقط برای روز رسمی پایان ماه (آخرین روز دادهٔ ماه جلالی) مجاز است؛ پیش‌نویس ثبت نشد.")
        if len(led) and str(asof.date()) <= str(last_sig):
            sys.exit("برای این تاریخ پیشتر ثبت شده است.")
        rows = [[str(asof.date()), str(mk.cols[i]), str(mk.sym[i]), float(w[i]), float(px[i]), plan_id, aum] for i in np.where(w > 0)[0]]
        new = not LEDGER.exists()
        with open(LEDGER, "a", newline="", encoding="utf-8-sig") as f:
            wr = csv.writer(f)
            if new:
                wr.writerow(["signal_date", "ins_code", "symbol", "w_post", "px_ref", "plan_id", "aum_rial"])
            wr.writerows(rows)
        print("در دفتر ثبت شد:", LEDGER.name)


def cmd_track(a):
    S = load_strategy()
    led = read_ledger()
    if not len(led):
        print("دفتر خالی است؛ هنوز ریبالانس رسمی ثبت نشده. نخستین دستور رسمی: آخرین روز دادهٔ ماه جلالی.")
        return
    mk, lab, _ = bl.get_lab()
    spec = S["spec"]
    cost = spec["cost_bp"] / 1e4
    pos = {c: i for i, c in enumerate(mk.cols)}
    mk_ok = np.isin(mk.market, spec["universe"]["markets"])
    dates = sorted(led.signal_date.unique())
    bt = S["backtest_in_sample"]
    rows, prev_w, prev_all, prev_a0 = [], None, None, None
    last_is_end = mk.last_day_is_month_end()
    for j, d in enumerate(dates):
        a0 = int(mk.dates.searchsorted(pd.Timestamp(d)))
        a1 = int(mk.dates.searchsorted(pd.Timestamp(dates[j + 1]))) if j + 1 < len(dates) else mk.n - 1
        if a1 <= a0:
            continue
        w = np.zeros(mk.k)
        for r in led[led.signal_date == d].itertuples():
            if r.ins_code in pos:
                w[pos[r.ins_code]] = r.w_post
        fwd = mk.fwd(a0, a1)
        f = np.where(np.isnan(fwd), 0, fwd)
        ok = mk.eligible(a0) & mk_ok & ~np.isnan(fwd)
        allw = ok / max(ok.sum(), 1)
        mc = np.where(ok, np.nan_to_num(mk.mcap[a0]), 0.0)
        cw = mc / mc.sum() if mc.sum() > 0 else mc
        # هر دو وزن قبلی (استراتژی و مرجع هم‌وزن) تا a0 رانش می‌کنند — همان قرارداد construction.backtest
        d_prev = drift_weights(mk, prev_w, prev_a0, a0) if prev_w is not None else np.zeros(mk.k)
        d_all = drift_weights(mk, prev_all, prev_a0, a0) if prev_all is not None else None
        to = 0.5 * np.abs(w - d_prev).sum() if prev_w is not None else np.nan
        toa = 0.5 * np.abs(allw - d_all).sum() if d_all is not None else np.nan
        r_s, r_a, r_c = float((w * f).sum()), float((allw * f).sum()), float((cw * f).sum())
        net_s = r_s - (0 if to != to else to * cost)       # هزینهٔ رفت‌وبرگشت × گردش یک‌طرفه (همان fe.net)
        net_a = r_a - (0 if toa != toa else toa * cost)
        rows.append({"signal_date": d, "to_date": str(mk.dates[a1].date()), "days": a1 - a0, "ret_S": r_s, "ret_ALL": r_a, "ret_CAP": r_c,
                     "excess_net_vs_ALL": net_s - net_a, "excess_vs_CAP": r_s - r_c, "turnover_oneway": to,
                     "open": bool(a1 == mk.n - 1 and not last_is_end)})
        prev_w, prev_all, prev_a0 = w, allw, a0
    T = pd.DataFrame(rows)
    if T.empty:
        print("هنوز دورهٔ کاملی نیست.")
        return
    T.to_csv(LIVE / "track.csv", index=False, encoding="utf-8-sig")
    Tc = T[~T.open]                                    # دورهٔ جاری ناتمام در آزمون z نمی‌آید
    n = len(Tc)
    mu, sd = bt["monthly_mean_excess_net"], bt["monthly_std_excess_net"]
    cum = float(Tc.excess_net_vs_ALL.sum())
    z = (cum - n * mu) / (sd * np.sqrt(n)) if n else float("nan")
    print(T.assign(**{c: (T[c] * 100).round(2) for c in ("ret_S", "ret_ALL", "ret_CAP", "excess_net_vs_ALL", "excess_vs_CAP")}).to_string(index=False))
    print(f"\n{n} دوره: برتری خالص تجمعی نسبت به هم‌وزن واجدان {100 * cum:+.2f}٪؛ مورد انتظار (بک‌تست) {100 * n * mu:+.2f}٪؛ z = {z:+.2f}")
    print("بازنگری مشخصات پیش از ۶ دورهٔ رسمی مجاز نیست." if n < 6 else "≥ ۶ دوره: بازبینی رسمی مجاز است (فصل ۱۴ §۱۴٫۹٫۱).")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("freeze")
    o = sub.add_parser("orders")
    o.add_argument("--aum", type=float, default=1e11, help="ارزش پرتفوی (ریال)")
    o.add_argument("--accept", action="store_true")
    sub.add_parser("track")
    a = ap.parse_args()
    {"freeze": cmd_freeze, "orders": cmd_orders, "track": cmd_track}[a.cmd](a)


if __name__ == "__main__":
    main()
