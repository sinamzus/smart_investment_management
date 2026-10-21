#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سیاست‌های ریبالانس «همتاساز» → ui/data/replica_rb_<سیاست>.js (و replica_ew_rb_<سیاست>.js) — فصل ۳ «سیاست ریبالانس».

    python tools/build_replica_rebal.py               # «شاخص كل»؛ پس از tools/build_replica_panel.py
    python tools/build_replica_rebal.py --target ew   # «شاخص كل (هم وزن)»؛ پس از build_replica_panel.py --target ew

ریبالانس = اجرای دوبارهٔ کامل ساخت (انتخاب N سهم و وزن، همان targets_at) با دادهٔ پایان روز بررسی و اجرا از روز بعد؛
بین دو ریبالانس وزن‌ها با بازده کل رانش می‌کنند. سیاست پایهٔ «ماهانه» همان ui/data/replica.js است (این ابزار آن را بازنمی‌سازد
و فقط هم‌ارزی شبیه‌سازی را با آن می‌سنجد). سیاست‌ها:
  w1 هفتگی: پایان هر هفتهٔ معاملاتی (آخرین روز معاملهٔ پیش از شنبه) · w2 دوهفتگی: یک هفته در میان
  q فصلی / h شش‌ماهه / y سالانه: پایان خرداد، شهریور، آذر، اسفند / شهریور و اسفند / اسفند
  t5 و t10 آستانه‌ای: بررسی هفتگی، ولی معامله فقط اگر گردش یک‌طرفهٔ لازم ½Σ|w_هدف − w_رانش| دست‌کم ۵٪ یا ۱۰٪ باشد.
نخستین روز (پایان نخستین ماه) همیشه خرید است. هزینه در مرورگر: گردش هر اجرا × L × هزینهٔ رفت‌وبرگشت، در روز همان اجرا.
وزن‌های هدف هر روز بررسی در data/derived/cache/replica_tg_<هدف>.pkl نگه داشته می‌شود (با اثر انگشت داده؛ اجرای قطع‌شده ادامه می‌یابد).
"""
import argparse
import hashlib
import json
import pickle
import sys
from base64 import b64encode
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import build_replica_panel as bp  # noqa: E402
import sampled_replica as sr  # noqa: E402
import dividend_pay as dp  # noqa: E402
import signals as sg  # noqa: E402

# (برچسب، نوع بررسی، آستانه)
POLICIES = {
    "w1": ("هفتگی", "week", None),
    "w2": ("دوهفتگی", "week2", None),
    "q": ("فصلی", (3, 6, 9, 12), None),
    "h": ("شش‌ماهه", (6, 12), None),
    "y": ("سالانه", (12,), None),
    "t5": ("آستانه‌ای ۵٪ (بررسی هفتگی)", "week", 0.05),
    "t10": ("آستانه‌ای ۱۰٪ (بررسی هفتگی)", "week", 0.10),
}
EPOCH = pd.Timestamp("1970-01-01")
CACHE_V = 2                                                             # ۲: پنجرهٔ نقدشوندگی روی روزهای باز بازار (۲۰۲۶-۱۰-۲۱)


def b16(a):
    return b64encode(np.asarray(a, dtype="<u2").tobytes()).decode()


def week_ends(dates):
    """آخرین روز معاملهٔ هر هفته (هفته از شنبه)؛ اندیس روز."""
    d = np.asarray((dates - EPOCH).days)
    wid = (d - 2) // 7                                                  # ۱۹۷۰-۰۱-۰۳ شنبه است
    return np.where(wid[1:] != wid[:-1])[0], wid


def checks_of(kind, me, dates, n):
    we, wid = week_ends(dates)
    we = we[(we >= me[0]) & (we < n - 1)]
    if kind == "week":
        c = set(we.tolist())
    elif kind == "week2":
        c = {int(x) for x in we if wid[x] % 2 == 0}
    else:
        jm = np.array([sg.ewr.g2j(dates[a].year, dates[a].month, dates[a].day)[1] for a in me])
        c = {a for a, m in zip(me, jm) if m in kind}
    c.add(me[0])
    return sorted(c)


def fingerprint(mk):
    h = hashlib.sha1()
    h.update(str((mk.n, mk.k, str(mk.dates[-1].date()))).encode())
    h.update(np.nan_to_num(mk.X[-260:]).astype("<f4").tobytes())
    h.update(np.asarray(mk.cols).astype(str).tobytes())
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["k", "ew"], default="k")
    ap.add_argument("--only", default="", help="فهرست سیاست‌ها با ویرگول، مثلاً w1,q")
    a = ap.parse_args()
    EWT = a.target == "ew"
    base_path = ROOT / "ui" / "data" / ("replica_ew.js" if EWT else "replica.js")
    s = base_path.read_text(encoding="utf-8")
    base = json.loads(s[s.index("=") + 1:].rstrip().rstrip(";"))
    mk, K = sr.load(a.target)
    K = K.fillna(0)
    n = mk.n
    me = [int(x) for x in mk.month_end if mk.dates[x] >= sr.START and x >= 252 and x + 1 < n]
    days0 = me[0] + 1
    if base["asof"] != str(mk.dates[n - 1].date()) or len(base["dates"]) != n - days0:
        sys.exit(f"دادهٔ پایه ({base_path.name}، تا {base['asof']}) با دادهٔ فعلی (تا {mk.dates[n - 1].date()}) هم‌خوان نیست؛ "
                 f"نخست python tools/build_replica_panel.py{' --target ew' if EWT else ''} را اجرا کنید.")
    pols = [p for p in POLICIES if not a.only or p in a.only.split(",")]
    CH = {p: checks_of(POLICIES[p][1], me, mk.dates, n) for p in pols}
    U = sorted(set().union(*CH.values()) | set(me))
    keys = [tuple([k.split("|")[0], int(k.split("|")[1]), int(k.split("|")[2])]) for k in base["configs"]]
    cx = bp.context(mk, K, a.target, U)
    pays = dp.pay_days(mk)
    # وزن‌های هدف روزهای بررسی (با نگه‌داری میانی)
    cache = ROOT / "data" / "derived" / "cache" / f"replica_tg_{a.target}.pkl"
    fp = fingerprint(mk)
    TG = {}
    if cache.exists():
        try:
            c = pickle.loads(cache.read_bytes())
            if c.get("fp") == fp and c.get("keys") == keys and c.get("v") == CACHE_V:
                TG = c["tg"]
        except Exception:  # noqa: BLE001
            TG = {}
    todo = [x for x in U if x not in TG]
    print(f"{len(U)} روز بررسی؛ {len(todo)} روز باید ساخته شود", flush=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    for i, x in enumerate(todo):
        TG[x] = bp.targets_at(cx, x, keys)[0]
        if (i + 1) % 25 == 0 or i + 1 == len(todo):
            cache.write_bytes(pickle.dumps({"fp": fp, "keys": keys, "tg": TG, "v": CACHE_V}))
            print(f"  {i + 1}/{len(todo)} {mk.dates[x].date()}", flush=True)
    # هم‌ارزی با سیاست پایهٔ ماهانه (همان شبیه‌سازی build_replica_panel)
    b64f = lambda z: np.frombuffer(__import__("base64").b64decode(z), dtype="<f4")  # noqa: E731
    dmax = 0.0
    for key in keys[:6]:
        P = bp.sim_policy(cx, key, me, me, TG, pays, days0)
        dmax = max(dmax, float(np.max(np.abs(P["r"].astype("<f4") - b64f(base["configs"]["|".join(map(str, key))]["r"])))))
    print(f"هم‌ارزی با ماهانهٔ پایه (۶ ترکیب): بیشینهٔ |Δr| = {dmax:.2e}")
    if dmax > 1e-5:
        sys.exit("شبیه‌سازی ماهانه با فایل پایه نمی‌خواند؛ نخست build_replica_panel را دوباره اجرا کنید.")
    pos = {c["c"]: i for i, c in enumerate(base["names"])}
    for p in pols:
        label, _, thr = POLICIES[p]
        extra, cfg, nreb = [], {}, []
        for key in keys:
            P = bp.sim_policy(cx, key, me, CH[p], TG, pays, days0, thr)
            cnt, ids, ws = [], [], []
            for s_, w_ in P["sel"]:
                for i in s_:
                    code = str(mk.cols[i])
                    if code not in pos:
                        pos[code] = len(base["names"]) + len(extra)
                        extra.append({"c": code, "s": str(mk.sym[i]), "sec": str(mk.sector[i])})
                cnt.append(len(s_)); ids += [pos[str(mk.cols[i])] for i in s_]; ws += [min(65535, int(round(x * 65535))) for x in w_]
            nreb.append(sum(P["rbm"]) + len(P["tod"]))
            cfg["|".join(map(str, key))] = {"r": bp.f32(P["r"]), "dv": bp.pack_dv(P["dv"]), "to": [round(x, 4) for x in P["to"]],
                                           "beta": [round(x, 3) for x in P["beta"]], "rbm": P["rbm"], "sel": [b16(cnt), b16(ids), b16(ws)],
                                           "tod": [[t for t, _ in P["tod"]], [round(x, 4) for _, x in P["tod"]]]}
        out = {"pol": p, "label": label, "thr": thr, "target": a.target, "asof": base["asof"], "n_dates": len(base["dates"]), "built": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
               "n_checks": len(CH[p]), "names_extra": extra, "n_names": len(base["names"]), "configs": cfg}
        path = ROOT / "ui" / "data" / f"replica{'_ew' if EWT else ''}_rb_{p}.js"
        path.write_text(f'window.SIM_REP_RB = window.SIM_REP_RB || {{}}; window.SIM_REP_RB["{a.target}|{p}"] = '
                        + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
        print(f"{label}: {len(CH[p])} روز بررسی، میانهٔ ریبالانس اجراشده {int(np.median(nreb))}؛ {path.name} ({path.stat().st_size / 1e6:.1f} MB)", flush=True)


if __name__ == "__main__":
    main()
