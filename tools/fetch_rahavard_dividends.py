#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ثبت پاسخ‌های JSON رهاورد۳۶۵ برای پیداکردن منبع «تاریخ پرداخت سود» (روی سیستم شما اجرا شود؛ محیط ابری به رهاورد دسترسی ندارد).

ساختار API رهاورد را نمی‌دانیم و حدس‌زدن آدرس‌ها ما را به 404 می‌رساند؛ پس مثل کدال اول «probe» می‌کنیم: مرورگر واقعی را باز می‌کنیم،
شما نماد را جست‌وجو و صفحهٔ سود نقدی/تقسیم سود (اطلاعات سود) را باز می‌کنید، و این ابزار فقط پاسخ‌های JSON شبکه را ذخیره می‌کند.
با آن آدرس دقیق API و ستون‌های «تاریخ پرداخت» معلوم می‌شود و collector نوشته می‌شود.

    pip install playwright          # فقط همین؛ مرورگر Chrome نصب‌شده روی ویندوز استفاده می‌شود (لازم به playwright install نیست)
    python tools/fetch_rahavard_dividends.py --capture فملی --log cap_rahavard.txt
        ← Chrome باز می‌شود؛ نماد را جست‌وجو کنید، صفحهٔ سهم را باز کنید و تب مربوط به «سود نقدی / تقسیم سود / رویدادهای سرمایه‌ای» را بزنید
          (۱ تا ۲ دقیقه کافی است)؛ سپس در ترمینال Enter بزنید.
    python tools/fetch_rahavard_dividends.py --har rahavard.har
        ← روش جایگزین بدون playwright: در Chrome → F12 → Network → (Preserve log) کار بالا را انجام دهید → راست‌کلیک → «Save all as HAR with content».

خروجی (قابل push؛ فقط پاسخ‌های JSON عمومی، بدون کوکی یا توکن):
    data/raw/rahavard/<نماد>/NNN_<host>_<path>.json    هر پاسخ JSON
    data/raw/rahavard/<نماد>/index.csv                  آدرس، وضعیت، اندازه، نشانهٔ «پرداخت/سود» در بدنه
و در ترمینال: پاسخ‌هایی که بدنه‌شان کلیدواژهٔ پرداخت/سود/dividend/payment دارد.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = ROOT / "data" / "raw" / "rahavard"
HINT = re.compile(r"پرداخت|سود|تقسیم|dividend|payment|pay_?date|dps|interest", re.I)
SKIP = re.compile(r"google|analytics|gtag|hotjar|clarity|doubleclick|yandex|sentry|fonts\.", re.I)


def _slug(url: str, n: int) -> str:
    u = urlparse(url)
    s = re.sub(r"[^0-9A-Za-z]+", "_", (u.netloc + u.path))[:70].strip("_")
    return f"{n:03d}_{s}.json"


class Saver:
    def __init__(self, sym: str):
        self.dir = OUT / sym
        self.dir.mkdir(parents=True, exist_ok=True)
        self.rows, self.n, self.seen = [], 0, set()
        self.allf = open(self.dir / "all_urls.txt", "w", encoding="utf-8")   # هر پاسخ دیده‌شده، حتی اگر ذخیره نشود

    def log(self, url: str, status, ctype: str, rtype: str, note: str) -> None:
        self.allf.write(f"{status}\t{rtype}\t{ctype[:40]}\t{note}\t{url}\n")
        self.allf.flush()

    def add(self, url: str, status: int, body: str, kind: str = "json") -> None:
        if SKIP.search(url) or url in self.seen or not body:
            return
        if kind == "json":
            try:
                json.loads(body)
            except Exception:  # noqa: BLE001
                return
        self.seen.add(url)
        self.n += 1
        name = _slug(url, self.n)
        if kind == "html":
            name = name[:-5] + ".html"
        (self.dir / name).write_text(body, encoding="utf-8")
        hint = len(HINT.findall(body))
        self.rows.append({"file": name, "status": status, "bytes": len(body), "hint": hint, "url": url})
        flag = "★" if hint else " "
        print(f"  {flag} {status} {len(body):8d}B hint={hint:3d} {kind:4s} {url[:140]}")

    def finish(self) -> None:
        self.allf.close()
        with open(self.dir / "index.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["file", "status", "bytes", "hint", "url"])
            w.writeheader()
            w.writerows(self.rows)
        top = sorted(self.rows, key=lambda r: -r["hint"])[:8]
        print(f"\n{len(self.rows)} پاسخ (JSON/HTML) ذخیره شد در {self.dir}؛ فهرست همهٔ آدرس‌های دیده‌شده: all_urls.txt")
        print("بیشترین نشانهٔ «پرداخت/سود»:")
        for r in top:
            print(f"  hint={r['hint']:3d}  {r['file']}  {r['url'][:120]}")


def capture(sym: str) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("ابتدا:  pip install playwright   (یا از --har استفاده کنید)")
    sv = Saver(sym)
    with sync_playwright() as p:
        try:
            br = p.chromium.launch(channel="chrome", headless=False)       # Chrome نصب‌شدهٔ سیستم
        except Exception:  # noqa: BLE001
            br = p.chromium.launch(headless=False)                         # Chromium خود playwright (اگر نصب شده)
        ctx = br.new_context(locale="fa-IR")
        page = ctx.new_page()

        def on_resp(r):
            url, status = r.url, r.status
            try:
                ct = (r.headers.get("content-type") or "").lower()
                rt = r.request.resource_type
            except Exception:  # noqa: BLE001
                ct, rt = "", "?"
            if rt in ("image", "font", "stylesheet", "media") or SKIP.search(url):
                return
            try:
                body = r.text()
            except Exception as e:  # noqa: BLE001
                sv.log(url, status, ct, rt, "text-failed:" + type(e).__name__)
                return
            kind = "html" if ("html" in ct and len(body) < 3_000_000) else "json"
            sv.log(url, status, ct, rt, f"{len(body)}B")
            sv.add(url, status, body, kind)
        ctx.on("response", on_resp)            # همهٔ تب‌ها و پنجره‌های باز‌شده
        page.goto("https://rahavard365.com/", wait_until="domcontentloaded")
        print(f"\nمرورگر باز شد. نماد «{sym}» را جست‌وجو کنید، صفحهٔ سهم را باز کنید و تب «سود نقدی / تقسیم سود / رویدادها» را بزنید.\n"
              "(اگر چند سال یا چند صفحه دارد، صفحه‌بندی/«نمایش بیشتر» را هم بزنید.) تمام که شد اینجا Enter بزنید.")
        input()
        br.close()
    sv.finish()


def from_har(path: str, sym: str) -> None:
    har = json.loads(Path(path).read_text(encoding="utf-8"))
    sv = Saver(sym)
    for e in har["log"]["entries"]:
        c = e["response"]["content"]
        body = c.get("text") or ""
        if c.get("encoding") == "base64":
            import base64
            body = base64.b64decode(body).decode("utf-8", "replace")
        sv.add(e["request"]["url"], e["response"]["status"], body)
    sv.finish()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture", metavar="SYM", help="مرورگر را باز کن و پاسخ‌های JSON را ذخیره کن (نام پوشه = نماد)")
    ap.add_argument("--har", help="به‌جای مرورگر، فایل HAR ذخیره‌شده از Chrome را بخوان")
    ap.add_argument("--sym", default="har", help="با --har: نام پوشهٔ خروجی")
    ap.add_argument("--log", help="کپی خروجی در فایل UTF-8")
    a = ap.parse_args()
    if a.log:
        sys.path.insert(0, str(ROOT / "tools"))
        import fetch_dividend_payments as fdp
        sys.stdout = fdp.Tee(a.log)
    if a.capture:
        capture(a.capture)
    elif a.har:
        from_har(a.har, a.sym)
    else:
        ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
