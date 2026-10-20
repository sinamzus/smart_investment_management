#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دریافت داده و بازسازی محاسبات، با ثبت وضعیت برای رابط (فصل ۰۹ §۹٫۶).

    python tools/update_pipeline.py fetch        # دریافت: نمادهای تازه، قیمت روزانه (۳۰ روز آخر ادغام)، شاخص‌های رسمی، اقدامات شرکتی نمادهای تغییرکرده
    python tools/update_pipeline.py fetch --full # + سودهای اعلام‌شده (فارابی) و بازسازی کامل اقدامات شرکتی همهٔ نمادها
    python tools/update_pipeline.py rebuild      # بازسازی همهٔ محاسبات و دادهٔ رابط (۳۰ تا ۶۰ دقیقه)
    python tools/update_pipeline.py status       # چاپ آخرین وضعیت

دو فایل دوبارکلیک در ریشهٔ مخزن همین‌ها را اجرا می‌کنند: update_data.bat و rebuild_all.bat (پروکسی محیط را خالی و UTF-8 را روشن می‌کنند).
وضعیت پس از هر گام در ui/data/update_status.js (window.SIM_UPDATE) نوشته می‌شود تا صفحه با «بارگذاری دوباره» پیشرفت و نتیجه را نشان دهد.
این ابزار به کدال درخواست نمی‌فرستد (جمع‌آوری نامه‌های کدال جداست و فقط یک فرایند کدال در یک زمان مجاز است).
"""
import gzip
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "ui" / "data" / "update_status.js"
LOGS = ROOT / "logs"
PY = sys.executable

FETCH = [
    ("نمادهای تازه (MarketWatch)", ["tools/fetch_stock_daily.py", "--discover"]),
    ("قیمت روزانه (۳۰ روز آخر، ادغام)", ["tools/fetch_stock_daily.py", "--collect", "--update", "30"]),
    ("شاخص‌های رسمی", ["tools/fetch_official_indices.py", "--fetch"]),
    ("اقدامات شرکتی نمادهای تغییرکرده", "corporate"),
]
FETCH_FULL = [
    ("اقدامات شرکتی همهٔ نمادها", ["tools/fetch_corporate_actions.py", "--collect-adjust", "--collect-shares", "--collect-info", "--force"]),
    ("سودهای اعلام‌شده (فارابی)", ["tools/fetch_farabi_dividends.py"]),
    ("تجزیهٔ سودهای فارابی", ["tools/parse_farabi_dividends.py"]),
    ("ادغام تاریخ پرداخت سود", ["tools/merge_dividend_payments.py"]),
    ("خالص ارزش دارایی صندوق‌های شاخصی", ["tools/fetch_index_funds.py"]),
]
REBUILD = [
    ("کنترل دامنهٔ نوسان", ["tools/qa_price_limits.py"]),
    ("شاخص‌ها (صفحهٔ اول)", ["tools/build_ui_data.py"]),
    ("آزمایشگاه و کتابخانه", ["tools/build_lab.py"]),
    ("همتاهای نمونه", ["tools/sampled_replica.py"]),
    ("همتاساز", ["tools/build_replica_panel.py"]),
    ("شاخص بهبودیافته", ["tools/build_replica_x.py"]),
    ("Factor Lab، کیفیت داده، ریسک", ["tools/build_ui_extra.py"]),
    ("صندوق‌های شاخصی", ["tools/build_ui_funds.py"]),
    ("دستور اجرای پیش‌نویس (بدون ثبت)", ["tools/live_ledger.py", "orders", "--aum", "1e11"]),
    ("دفتر زنده", ["tools/build_ui_live.py"]),
    ("قیمت‌ها و رویدادهای بخش پرتفو", ["tools/build_ui_portfolio.py"]),
    ("سند درون‌برنامه", ["tools/build_ui_docs.py"]),
]


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_status():
    if STATUS.exists():
        t = STATUS.read_text(encoding="utf-8")
        try:
            return json.loads(t[t.index("{"): t.rindex("}") + 1])
        except ValueError:
            pass
    return {}


def save_status(st):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text("/* ساخته‌شده با tools/update_pipeline.py */\nwindow.SIM_UPDATE = " + json.dumps(st, ensure_ascii=False, indent=1) + ";\n", encoding="utf-8")


def data_asof():
    """رایج‌ترین روزِ آخر در فایل‌های قیمت (میانه گمراه می‌کند: فایل نمادهای حذف‌شده و بی‌معامله سال‌ها پیش تمام شده‌اند)."""
    from collections import Counter
    last = Counter()
    for f in (ROOT / "data" / "prices").glob("*.csv.gz"):
        try:
            with gzip.open(f, "rt", encoding="utf-8") as g:
                rows = list(csv.DictReader(g))
            if rows:
                last[str(int(float(rows[-1]["dEven"])))] += 1
        except Exception:  # noqa: BLE001
            pass
    if not last:
        return None
    d = last.most_common(1)[0][0]
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def changed_codes(days=30):
    """نمادهایی که در N روز آخر مبنای قیمت‌شان تغییر کرده (priceYesterday ≠ پایانی روز قبل): احتمال افزایش سرمایه یا سود."""
    out = []
    for f in (ROOT / "data" / "prices").glob("*.csv.gz"):
        try:
            with gzip.open(f, "rt", encoding="utf-8") as g:
                rows = list(csv.DictReader(g))[-(days + 1):]
        except Exception:  # noqa: BLE001
            continue
        for a, b in zip(rows[:-1], rows[1:]):
            try:
                pc, py = float(a["pClosing"]), float(b["priceYesterday"])
            except (KeyError, ValueError):
                continue
            if pc > 0 and abs(py / pc - 1) > 1e-3:
                out.append(f.name.split(".")[0])
                break
    return out


def run_steps(kind, steps):
    LOGS.mkdir(exist_ok=True)
    log = LOGS / f"{kind}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    st = load_status()
    rec = {"started": now(), "finished": None, "ok": None, "running": True, "log": str(log.relative_to(ROOT)), "steps": []}
    st[kind] = rec
    save_status(st)
    env = {k: v for k, v in os.environ.items() if k.lower() not in ("http_proxy", "https_proxy")}   # TSETMC با پروکسی محیط وصل نمی‌شود
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    ok_all = True
    with open(log, "a", encoding="utf-8") as L:
        for name, cmd in steps:
            t0 = time.time()
            step = {"name": name, "ok": None, "seconds": None, "started": now()}
            rec["steps"].append(step)
            save_status(st)
            print(f"\n=== {name}", flush=True)
            L.write(f"\n=== {now()} {name}\n")
            L.flush()
            if cmd == "corporate":
                codes = changed_codes()
                f = ROOT / "data" / "derived" / "refresh_codes.txt"
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text("\n".join(codes), encoding="utf-8")
                step["note"] = f"{len(codes)} نماد با تغییر مبنا در ۳۰ روز اخیر"
                print(step["note"], flush=True)
                cmd = ["tools/fetch_corporate_actions.py", "--collect-adjust", "--collect-shares", "--collect-info", "--refresh-file", str(f)]
            p = subprocess.run([PY, "-u", *cmd], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            L.write(p.stdout)
            tail = [ln for ln in p.stdout.strip().splitlines() if ln.strip() and "Warning" not in ln][-1:]
            print(p.stdout[-1500:], flush=True)   # خروجی کامل در فایل گزارش
            step.update(ok=p.returncode == 0, seconds=round(time.time() - t0), last_line=(tail[0][:200] if tail else ""))
            ok_all &= step["ok"]
            save_status(st)
    rec.update(finished=now(), ok=ok_all, running=False)
    if kind == "fetch":
        rec["data_asof"] = data_asof()
    save_status(st)
    print(f"\n{'پایان موفق' if ok_all else 'پایان با خطا'} — {kind}؛ گزارش: {log}", flush=True)
    return 0 if ok_all else 1


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    a = sys.argv[1:] or ["status"]
    if a[0] == "fetch":
        return run_steps("fetch", FETCH + (FETCH_FULL if "--full" in a else []))
    if a[0] == "rebuild":
        return run_steps("rebuild", REBUILD)
    print(json.dumps(load_status(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
