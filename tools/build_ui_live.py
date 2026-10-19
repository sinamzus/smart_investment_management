#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دادهٔ دو نمای UI «بازسازی شاخص» و «دفتر زنده» → ui/data/live.js (window.SIM_LIVE).

    python tools/build_ui_live.py

ورودی: data/research/sampled_replica.csv و sampled_replica_meta.json (tools/sampled_replica.py)،
       data/live/strategy_v1.json، آخرین orders_*.json، ledger.csv و track.csv (tools/live_ledger.py).
"""
import csv
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ui" / "data" / "live.js"


def rd(p):
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def num(r):
    return {k: (float(v) if v not in ("", None) and k not in ("method", "leverage", "signal_date", "to_date", "symbol", "ins_code", "plan_id", "open") else v) for k, v in r.items()}


def main():
    D = {"replica": None, "replica_meta": None, "strategy": None, "orders": None, "ledger": [], "track": []}
    f = ROOT / "data/research/sampled_replica.csv"
    if f.exists():
        D["replica"] = [num(r) for r in rd(f)]
        D["replica_meta"] = json.load(open(ROOT / "data/research/sampled_replica_meta.json", encoding="utf-8"))
    s = ROOT / "data/live/strategy_v1.json"
    if s.exists():
        D["strategy"] = json.load(open(s, encoding="utf-8"))
    files = sorted(glob.glob(str(ROOT / "data/live/orders_*.json")))
    official = [x for x in files if "_interim" not in x]
    pick = (official or files or [None])[-1]
    if pick:
        D["orders"] = json.load(open(pick, encoding="utf-8"))
    lg = ROOT / "data/live/ledger.csv"
    if lg.exists():
        D["ledger"] = [num(r) for r in rd(lg)]
    tr = ROOT / "data/live/track.csv"
    if tr.exists():
        D["track"] = [num(r) for r in rd(tr)]
    OUT.write_text("window.SIM_LIVE = " + json.dumps(D, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"ذخیره شد: {OUT} ({OUT.stat().st_size / 1e3:.0f} KB)؛ replica={'بله' if D['replica'] else 'خیر'} · استراتژی={'بله' if D['strategy'] else 'خیر'} · سفارش={len(D['orders']['orders']) if D['orders'] else 0} · دفتر={len(D['ledger'])} · رهگیری={len(D['track'])}")


if __name__ == "__main__":
    main()
