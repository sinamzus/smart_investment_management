#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دادهٔ بخش «پرتفو» رابط → ui/data/portfolio.js (window.SIM_PFX) — فصل ۵ §۵٫۹.

    python tools/build_ui_portfolio.py

برای ثبت پرتفوی واقعی در هر تاریخ، سنجش انحراف و ریبالانس با اقدامات شرکتی، مرورگر به این‌ها نیاز دارد (از ۱۳۹۹/۰۱/۰۱ تا آخرین روز داده):
  dates   روزهای معاملاتی (روزی که دست‌کم ۲۰٪ نمادها معامله داشته‌اند؛ تعطیلی سراسری حذف)
  px      قیمت پایانی تعدیل‌نشده (pClosing) هر نماد × روز، Float32 به base64 (پیش‌پرشده از آخرین روز معامله؛ پیش از عرضه NaN)
  tr      معامله‌شدن (zTotTran > 0) هر نماد × روز، یک بیت در هر بایت به base64؛ نماد بی‌معامله آن روز قابل خرید و فروش نیست
  divs    سود نقدی: [اندیس نماد، روز استحقاق ISO، سود هر سهم ریال، روز پرداخت ISO، "a" اعلام‌شده | "e" برآورد]
          روز پرداخت: فارابی، سپس fundai؛ نبود ⇒ استحقاق + میانهٔ تأخیر همهٔ رویدادها (۹۶ روز، فصل ۳ §۳٫۵) با برچسب "e"
  caps    افزایش سرمایه: [اندیس، روز ISO، g (سهام نو ÷ قدیم)، cs (سهم نقدی/حق‌تقدم)، وضعیت ۱ مطمئن / ۰ نامطمئن / −۱ بازگشت خطای داده، قیمت پیش از رویداد]
          به‌ازای هر سهم قدیم: جایزه (g−1)(1−cs) سهم مجانی؛ حق‌تقدم (g−1)·cs با پذیره‌نویسی ۱۰۰۰ ریال [تأیید لازم] (tools/build_issue_split.py)
جهان نمادها همان جهان Lab است (ui/data/lab.js → codes) تا وزن هر استراتژی مستقیم به قیمت و رویداد برسد.
"""
import base64
import glob
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from jalali import j2g_str  # noqa: E402

OUT = ROOT / "ui" / "data" / "portfolio.js"
START = "2020-03-20"                      # ۱۳۹۹/۰۱/۰۱
PAY_LAG_DAYS = 96                         # میانهٔ تأخیر استحقاق تا پرداخت (فصل ۳ §۳٫۵)


def lab_codes():
    t = (ROOT / "ui" / "data" / "lab.js").read_text(encoding="utf-8")
    d = json.loads(t[t.index("{"): t.rindex("}") + 1])
    return [c["c"] for c in d["codes"]], [c.get("p") or c["s"] for c in d["codes"]], d["asof"]


def jiso(s):
    try:
        y, m, d = (int(x) for x in str(s).split("/"))
        return j2g_str(y, m, d, strict=False)
    except Exception:                    # noqa: BLE001
        return None


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode("ascii")


def main():
    codes, syms, asof = lab_codes()
    idx = {c: i for i, c in enumerate(codes)}
    frames = []
    for f in glob.glob(str(ROOT / "data/prices/*.csv.gz")):
        c = os.path.basename(f).split(".")[0]
        if c not in idx:
            continue
        d = pd.read_csv(f, usecols=["dEven", "pClosing", "zTotTran"])
        d = d[d.dEven >= int(START.replace("-", ""))]
        d["k"] = idx[c]
        frames.append(d)
    P = pd.concat(frames, ignore_index=True)
    P["date"] = pd.to_datetime(P.dEven.astype(int).astype(str), format="%Y%m%d")
    P = P[P.date <= pd.Timestamp(asof)]
    traded = P[P.zTotTran > 0].groupby("date").size()
    open_days = traded[traded >= 0.2 * traded.rolling(20, min_periods=1).median()].index.sort_values()
    D, K = len(open_days), len(codes)
    di = {d: i for i, d in enumerate(open_days)}
    px = np.full((D, K), np.nan, dtype=np.float32)
    tr = np.zeros((D, K), dtype=np.uint8)
    Q = P[P.date.isin(di)]
    r = Q.date.map(di).to_numpy()
    px[r, Q.k.to_numpy()] = Q.pClosing.to_numpy(dtype=np.float32)
    tr[r, Q.k.to_numpy()] = (Q.zTotTran.to_numpy() > 0).astype(np.uint8)
    px = pd.DataFrame(px).ffill().to_numpy(dtype=np.float32)           # روز بی‌ردیف: آخرین قیمت

    # سود نقدی
    M = pd.read_csv(ROOT / "data/corporate_actions/dividend_events_merged.csv", dtype={"ins_code": str})
    M = M[(M.ex_date >= START) & M.ins_code.isin(idx)]
    divs = []
    for x in M.itertuples():
        dps = next((v for v in (x.farabi_dps, x.rv_dps, x.fd_dps, x.dps_implied) if pd.notna(v) and v > 0), None)
        if not dps:
            continue
        pay, kind = (jiso(x.farabi_pay_j) if pd.notna(x.farabi_pay_j) else None), "a"
        if not pay and pd.notna(x.fd_pay):
            pay = str(x.fd_pay)[:10]
        if not pay or pay < x.ex_date:
            pay, kind = (pd.Timestamp(x.ex_date) + pd.Timedelta(days=PAY_LAG_DAYS)).strftime("%Y-%m-%d"), "e"
        divs.append([idx[x.ins_code], x.ex_date, float(dps), pay, kind])

    # افزایش سرمایه (جایزه / حق‌تقدم)
    S = pd.read_csv(ROOT / "data/corporate_actions/issue_split.csv", dtype={"ins_code": str})
    S["date"] = pd.to_datetime(S.dEven.astype(int).astype(str), format="%Y%m%d")
    S = S[(S.date >= START) & (S.date <= pd.Timestamp(asof)) & S.ins_code.isin(idx) & (S.g > 1.0001)]
    # «بازگشت خطای داده»: سرمایه چند روز قبل به همین نسبت کم شده و حالا برمی‌گردد (مثلاً بفجر ۱۴۰۳/۰۷: نصف و دو برابر) — هرگز اعمال نمی‌شود.
    C = pd.read_csv(ROOT / "data/corporate_actions/share_change.csv", dtype={"ins_code": str})
    C["date"] = pd.to_datetime(C.dEven.astype(int).astype(str), format="%Y%m%d")
    C["g"] = C.shares_new / C.shares_old
    dec = C[C.g < 0.999]

    def glitch(x):
        w = dec[(dec.ins_code == x.ins_code) & (dec.date < x.date) & (dec.date >= x.date - pd.Timedelta(days=30))]
        return bool(((w.g * x.g - 1).abs() < 0.05).any())
    # وضعیت: 1 مطمئن (خودکار اعمال)، 0 نامطمئن (نمایش، اعمال دستی)، -1 بازگشت خطای داده (هرگز)
    caps = [[idx[x.ins_code], x.date.strftime("%Y-%m-%d"), round(float(x.g), 6), round(float(min(max(x.cs, 0.0), 1.0)), 4),
             -1 if glitch(x) else int(bool(x.reliable)), float(x.P)]
            for x in S.itertuples() if pd.notna(x.cs)]

    out = {"asof": asof, "start": START, "built": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "codes": codes, "syms": syms,
           "dates": [d.strftime("%Y-%m-%d") for d in open_days], "px": b64(px), "tr": b64(tr), "divs": sorted(divs, key=lambda v: v[1]),
           "caps": sorted(caps, key=lambda v: v[1]), "par": 1000, "pay_lag": PAY_LAG_DAYS}
    js = "/* ساخته‌شده با tools/build_ui_portfolio.py */\nwindow.SIM_PFX = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n"
    OUT.write_text(js, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {D} روز × {K} نماد، {len(divs)} سود نقدی، {len(caps)} افزایش سرمایه، {len(js) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
