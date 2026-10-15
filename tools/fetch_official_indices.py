#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
دریافت تاریخچهٔ شاخص‌های رسمی بورس تهران از TSETMC
================================================
اسکریپت مستقل (فقط requests). باید روی سیستم خودتان اجرا شود؛ TSETMC از IP
دیتاسنتر ۴۰۳ می‌دهد.

هشدار: کدهای نماد شاخص‌ها و نام فیلدهای پاسخ از حافظه نوشته شده و از این
محیط تست نشده‌اند. برای همین:
  * --list همهٔ شاخص‌ها را با کد چاپ می‌کند تا کد درست را خودتان تأیید کنید.
  * پاسخ خام همیشه در data/raw/ ذخیره می‌شود، حتی اگر نرمال‌سازی ناقص باشد.
  * خروجی نهایی را حتماً با نمودار سایت TSETMC مقایسه کنید.

استفاده
-------
    pip install requests
    python tools/fetch_official_indices.py --list
    python tools/fetch_official_indices.py --list --grep هم
    python tools/fetch_official_indices.py --fetch                     # دو شاخص پیش‌فرض
    python tools/fetch_official_indices.py --fetch --code 32097828799138957 --code 67130298613737946

خروجی
-----
    data/raw/index_<code>.json     پاسخ خام
    data/indices/index_<code>.csv  date,close + سایر ستون‌های عددی پاسخ (نام اصلی فیلد)
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "indices"

CDN = "https://cdn.tsetmc.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8",
    "Referer": "https://main.tsetmc.com/",
}
TIMEOUT = 30
MIN_INTERVAL = 1.5  # ثانیه بین درخواست‌ها

# [راستی‌آزمایی نشده] کدهای پیش‌فرض از حافظه‌اند؛ با --list تأیید شوند.
DEFAULT_CODES = {
    "32097828799138957": "شاخص کل",
    "67130298613737946": "شاخص کل (هم وزن)",
}

_last = 0.0


def _get(url: str, retries: int = 3):
    global _last
    err = None
    for k in range(retries):
        wait = MIN_INTERVAL - (time.monotonic() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.monotonic()
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            err = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            err = repr(e)
        time.sleep(2 ** (k + 1))
    raise RuntimeError(f"{url} -> {err}")


def _find_list(obj):
    """اولین لیست از دیکشنری‌ها را در پاسخ پیدا می‌کند (نام کلید ثابت فرض نمی‌شود)."""
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        return obj
    if isinstance(obj, dict):
        for v in obj.values():
            r = _find_list(v)
            if r:
                return r
    return []


def _name_of(row: dict) -> str:
    for k, v in row.items():
        if isinstance(v, str) and any("؀" <= c <= "ۿ" for c in v):
            return v
    return ""


def list_indices(grep: str | None) -> None:
    data = _get(f"{CDN}/Index/GetIndexB1LastAll/All/1")
    rows = _find_list(data)
    if not rows:
        print("ساختار پاسخ ناشناخته؛ نمونهٔ خام:", json.dumps(data, ensure_ascii=False)[:800])
        return
    print(f"{len(rows)} شاخص. کلیدهای نمونه: {list(rows[0].keys())}")
    for row in rows:
        code = row.get("insCode") or row.get("InsCode") or ""
        name = _name_of(row)
        if grep and grep not in name:
            continue
        print(f"{code}\t{name}")


def _to_iso(d) -> str:
    return datetime.strptime(str(int(d)), "%Y%m%d").strftime("%Y-%m-%d")


def normalize(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        d = r.get("dEven") or r.get("DEven")
        if not d:
            continue
        rec = {"date": _to_iso(d)}
        # [راستی‌آزمایی نشده] فیلد close احتمالاً xNivInuClMresIbs است.
        for k, v in r.items():
            if k in ("dEven", "DEven", "insCode", "InsCode"):
                continue
            if isinstance(v, (int, float)):
                rec[k] = v
        close = r.get("xNivInuClMresIbs")
        rec = {"date": rec["date"], "close": close, **{k: v for k, v in rec.items() if k != "date"}}
        out.append(rec)
    out.sort(key=lambda x: x["date"])
    return out


def fetch_index(code: str) -> Path:
    data = _get(f"{CDN}/Index/GetIndexB1History/{code}")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"index_{code}.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8")
    rows = normalize(_find_list(data))
    if not rows:
        raise RuntimeError(f"{code}: ردیفی نرمال‌سازی نشد؛ پاسخ خام را بررسی کنید")
    cols = list(dict.fromkeys(k for r in rows for k in r))
    path = OUT_DIR / f"index_{code}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    nclose = sum(1 for r in rows if r.get("close") is not None)
    print(f"{code}: {len(rows)} ردیف، {rows[0]['date']} تا {rows[-1]['date']}، "
          f"{nclose} ردیف با close -> {path}")
    if nclose == 0:
        print("  هشدار: ستون close خالی است؛ نام فیلد را از CSV/JSON خام بردارید و به ما بگویید.")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="فهرست شاخص‌ها با کد")
    ap.add_argument("--grep", help="فیلتر نام برای --list")
    ap.add_argument("--fetch", action="store_true", help="دریافت تاریخچه")
    ap.add_argument("--code", action="append", help="کد شاخص (قابل تکرار)؛ پیش‌فرض دو شاخص اصلی")
    a = ap.parse_args()
    if not (a.list or a.fetch):
        ap.print_help()
        return 1
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8")
    if a.list:
        list_indices(a.grep)
    if a.fetch:
        codes = a.code or list(DEFAULT_CODES)
        for c in codes:
            try:
                fetch_index(c)
            except Exception as e:  # noqa: BLE001
                print(f"{c}: خطا: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
