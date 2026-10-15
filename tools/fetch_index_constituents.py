#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اعضای هر شاخص رسمی از TSETMC (برای یافتن سهام جاافتاده از MarketWatch، با ~۵۰ درخواست).

    python tools/fetch_index_constituents.py                 # همهٔ شاخص‌های data/indices
    python tools/fetch_index_constituents.py --add-missing   # + افزودن اعضای ناموجود به data/instruments_extra.csv

مسیر: cdn.tsetmc.com/api/ClosingPrice/GetIndexCompany/{کد شاخص} (از سورس کتابخانهٔ tsetmc؛ ساختار پاسخ
تست نشده — کد به‌صورت بازگشتی دنبال insCode/lVal18AFC/lVal30 می‌گردد و پاسخ خام را هم ذخیره می‌کند).
خروجی: data/index_constituents.csv (index_code, ins_code, symbol, name) و data/raw/idxco_<code>.json
فقط اعضای فعلی را می‌دهد؛ نمادهایی که قبلاً از شاخص خارج شده‌اند در آن نیستند.
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path

import requests

import fetch_stock_daily as fsd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def walk(o, found):
    """ساختار واقعی: هر عضو {instrument: {insCode, lVal18AFC, lVal30, …}, …}؛ دیکشنری instrument اولویت دارد."""
    if isinstance(o, dict):
        inst = o.get("instrument")
        if isinstance(inst, dict) and inst.get("insCode"):
            found.append(inst)
            return
        if "insCode" in o and o.get("insCode") and (o.get("lVal18AFC") or o.get("lVal30")):
            found.append(o)
        for v in o.values():
            walk(v, found)
    elif isinstance(o, list):
        for v in o:
            walk(v, found)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--add-missing", action="store_true", help="سهام ناموجود در instruments.csv را به instruments_extra.csv اضافه کن")
    a = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    codes = sorted(p.stem.replace("index_", "") for p in (DATA / "indices").glob("index_*.csv"))
    (DATA / "raw").mkdir(parents=True, exist_ok=True)
    rows, seen = [], set()
    for k, c in enumerate(codes, 1):
        try:
            raw = fsd.get_json(f"{fsd.CDN}/ClosingPrice/GetIndexCompany/{c}")
        except Exception as e:  # noqa: BLE001
            print(f"  [{k}/{len(codes)}] {c}: خطا {e}", file=sys.stderr)
            continue
        (DATA / "raw" / f"idxco_{c}.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        items = []
        walk(raw.get("indexCompany", raw), items)
        n = 0
        for it in items:
            code = str(it["insCode"])
            sym = fsd.normalize(it.get("lVal18AFC") or it.get("lVal18") or "")
            name = fsd.normalize(it.get("lVal30") or "")
            if (c, code) in seen:
                continue
            seen.add((c, code))
            rows.append({"index_code": c, "ins_code": code, "symbol": sym, "name": name})
            n += 1
        print(f"  [{k}/{len(codes)}] {c}: {n} عضو")
    out = DATA / "index_constituents.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["index_code", "ins_code", "symbol", "name"])
        w.writeheader()
        w.writerows(rows)
    members = {r["ins_code"]: r for r in rows}
    known = {r["ins_code"] for r in csv.DictReader((DATA / "instruments.csv").open(encoding="utf-8"))}
    extra_p = fsd.EXTRA
    old = list(csv.DictReader(extra_p.open(encoding="utf-8"))) if extra_p.exists() else []
    have = known | {r["ins_code"] for r in old}
    missing = [r for c, r in members.items() if c not in have]
    print(f"\nاعضای یکتا: {len(members)}؛ ناموجود در instruments.csv/extras: {len(missing)} -> {out}")
    for r in missing[:40]:
        print(f"  {r['ins_code']:18s} {r['symbol']:12s} {r['name']}  [نوع={fsd.classify(r['symbol'], r['name'])}]")
    if a.add_missing and missing:
        add = [r for r in missing if fsd.classify(r["symbol"], r["name"]) == "stock"]
        with extra_p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["ins_code", "symbol", "name"])
            w.writeheader()
            w.writerows(old + [{"ins_code": r["ins_code"], "symbol": r["symbol"], "name": r["name"]} for r in add])
        print(f"{len(add)} سهم به {extra_p.name} اضافه شد")


if __name__ == "__main__":
    main()
