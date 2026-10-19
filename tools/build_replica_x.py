#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دادهٔ موتور مرورگری «شاخص بهبودیافته» (تیلت صنعت/معیار، سقف، آمیخته با هم‌وزن، بهینه‌سازی در مرورگر) → ui/data/replica_x.js (window.SIM_REPX).

    python tools/build_replica_x.py

ماتریس بازده روزانهٔ کل (TR) نمادهای واجد بورس از ۲۵۲ روز پیش از نخستین ریبالانس، و برای هر ریبالانس ماهانه (و آخرین روز): ارزش بازار، میانهٔ ۶۳ روزهٔ ارزش
معاملات، تعداد روز معامله از ۶۳. همان واجدیت و قرارداد tools/build_replica_panel.py (واجدیت قیمتی، بورس، شرکت عملیاتی).
"""
import json
import sys
from base64 import b64encode
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import sampled_replica as sr  # noqa: E402

EPOCH = pd.Timestamp("1970-01-01")


def f32(a):
    return b64encode(np.ascontiguousarray(a, dtype="<f4").tobytes()).decode()


def main():
    mk, K = sr.load()
    K = K.fillna(0)
    n, k = mk.n, mk.k
    X = np.nan_to_num(mk.X)
    mc = np.nan_to_num(mk.mcap)
    ok_all = np.isin(mk.market, ["bourse"])
    val = pd.DataFrame(mk.val)
    adv = val.rolling(63, min_periods=30).median().values
    td = (val.fillna(0) > 0).astype(float).rolling(63, min_periods=30).sum().values
    me = [int(x) for x in mk.month_end if mk.dates[x] >= sr.START and x >= 252 and x + 1 < n]
    ends = me + [n - 1]
    elig = {a: np.where(mk.eligible(a, require_trade=False) & ok_all & (mc[a] > 0))[0] for a in ends}   # هدف شاخص از همهٔ واجدان (همان build_replica_panel)
    used = sorted({int(i) for a in ends for i in elig[a]})
    pos = {i: p for p, i in enumerate(used)}
    d0 = me[0] - 251
    Cfull = np.zeros(n)
    for t in range(1, n):
        i = np.where(mk.eligible(t - 1, require_trade=False) & ok_all & (mc[t - 1] > 0))[0]
        if len(i):
            Cfull[t] = float((mc[t - 1, i] / mc[t - 1, i].sum()) @ X[t, i])
    sectors = sorted({str(mk.sector[i]) for i in used})
    sid = {s: j for j, s in enumerate(sectors)}
    months = []
    for a in ends:
        m = np.zeros(len(used), dtype=np.float32); ad = np.zeros(len(used), dtype=np.float32); tdv = np.zeros(len(used), dtype=np.uint8)
        trv = mk.tradable(a)[used].astype(np.uint8)            # قابل‌معامله در روز اجرا (قاعدهٔ A2؛ ui/enhance.js آن را اعمال می‌کند)
        for i in elig[a]:
            m[pos[int(i)]] = mc[a, i]; ad[pos[int(i)]] = (adv[a, i] if np.isfinite(adv[a, i]) else 0) / 1e9; tdv[pos[int(i)]] = int(td[a, i]) if np.isfinite(td[a, i]) else 0
        months.append({"a": a - d0, "d": int((mk.dates[a] - EPOCH).days), "mcap": f32(m), "adv": f32(ad), "td": b64encode(tdv.tobytes()).decode(), "tr": b64encode(trv.tobytes()).decode()})
    ret = X[d0:][:, used]
    out = {"built": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "asof": str(mk.dates[-1].date()), "k": len(used), "days": n - d0,
           "dates": [int((d - EPOCH).days) for d in mk.dates[d0:]], "ret": f32(ret), "K": f32(K.values[d0:]), "C": f32(Cfull[d0:]),
           "names": [{"c": str(mk.cols[i]), "s": str(mk.sym[i]), "sec": sid[str(mk.sector[i])]} for i in used], "sectors": sectors, "months": months, "n_rebal": len(me)}
    path = ROOT / "ui" / "data" / "replica_x.js"
    path.write_text("window.SIM_REPX = " + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"ذخیره شد: {path} ({path.stat().st_size / 1e6:.1f} MB)؛ {len(used)} نماد × {n - d0} روز؛ {len(months)} ماه (آخرین = زنده)")


if __name__ == "__main__":
    main()
