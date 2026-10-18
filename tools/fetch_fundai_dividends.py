#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""جمع‌آوری تقویم مجمع و پرداخت سود از فاندای (fundai.ir) — تکمیل شکاف «تاریخ پرداخت» و «تصویب» (فصل ۲ §۲٫۴، بند ۷l فصل ۱۰).

    python tools/fetch_fundai_dividends.py --selftest        # آزمون تجزیه (بدون شبکه)
    python tools/fetch_fundai_dividends.py --test            # شبکه: sitemap + یک صفحه
    python tools/fetch_fundai_dividends.py --log f.txt       # اجرای کامل (قابل ادامه)

روش: نقشهٔ سایت (sitemap) را می‌خواند و همهٔ آدرس‌های /company/<slug>/dividend-calendar را برمی‌دارد؛ نماد از عنوان صفحه «(نماد)» می‌آید،
پس نقشهٔ slug لازم نیست. robots.txt فاندای این مسیر را مجاز کرده است. تأخیر پیش‌فرض ۱٫۵ ثانیه.
خروجی (data/corporate_actions/):
  fundai_dividends.csv  — symbol, slug, fy_end_j, agm_j, pay_from_j, pay_to_j, dps_rial
  fundai_done.csv       — slug های انجام‌شده (برای ادامه)
  fundai_raw.csv.gz     — slug, symbol, متن خام ردیف‌های جدول (برای --reparse)
داده ثانویه است: پیش از استفاده با کدال/راهاورد سنجیده شود (tools/audit_corporate_actions.py).
"""
import argparse
import csv
import gzip
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "corporate_actions"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = "https://fundai.ir"
UA = {"User-Agent": "Mozilla/5.0 (research; contact: soorininvesting@gmail.com)", "Accept-Language": "fa,en;q=0.8", "Accept-Encoding": "gzip"}
DIG = {**{ord(c): str(i % 10) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩")}, ord("٬"): None, ord(","): None, ord("٫"): "."}
FIELDS = ["symbol", "slug", "fy_end_j", "agm_j", "pay_from_j", "pay_to_j", "dps_rial"]
DATE = re.compile(r"\d{4}/\d{1,2}/\d{1,2}")


def get(url, retries=4):
    for k in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                b = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or b[:2] == b"\x1f\x8b":
                    b = gzip.decompress(b)
                return b.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None)
            if code == 404:
                return None
            wait = 30 * (k + 1) if code == 429 else 4 * (k + 1)
            print(f"  ! {url}: {e}؛ {wait}s صبر", flush=True)
            time.sleep(wait)
    return None


def sitemap_urls(url, depth=0):
    """همهٔ <loc> ها؛ نقشه‌های تو‌در‌تو را دنبال می‌کند."""
    x = get(url)
    if not x:
        return []
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", x)
    out = []
    for u in locs:
        if u.endswith(".xml") and depth < 2:
            out += sitemap_urls(u, depth + 1)
        else:
            out.append(u)
    return out


def company_pages():
    urls = []
    for s in (BASE + "/sitemap-index.xml", BASE + "/sitemap.xml"):
        urls += sitemap_urls(s)
    slugs = {}
    for u in urls:
        m = re.search(r"/company/([^/?#]+)(?:/([^/?#]*))?/?$", u)
        if m:
            slugs.setdefault(m.group(1), None)
    return sorted(slugs), urls


def to_text(html):
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    h = re.sub(r"(?i)</t[dh]\s*>", " | ", h)
    h = re.sub(r"(?i)</tr\s*>|<br\s*/?>|</(p|h\d|li|div|table)\s*>", "\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    h = h.replace("&nbsp;", " ").replace("&amp;", "&").replace("‌", " ")
    return h.translate(DIG)


def table_text(html):
    """متن ردیف‌های جدول (برای ذخیرهٔ خام و تجزیهٔ دوباره بدون خزش)."""
    return "\n".join(l for l in (re.sub(r"[ \t]+", " ", x).strip() for x in to_text(html).split("\n")) if "|" in l and ("سال مالی" in l or l.startswith(("تاریخ مجمع", "زمان پرداخت", "سود نقدی", "| تاریخ", "| زمان", "| سود"))))


def parse(html, slug):
    """-> (symbol, rows) ؛ هر ردیف یک سال مالی."""
    t = to_text(html)
    m = re.search(r"<title>[^<]*\(([^)<]+)\)[^<]*</title>", html) or re.search(r"\(([^()\n]{1,20})\)\s*\|\s*فاندای", t)
    symbol = m.group(1).strip() if m else None
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in t.split("\n")]
    hdr = next((l for l in lines if "|" in l and "سال مالی منتهی به" in l), None)
    if not hdr:
        return symbol, []
    fys = re.findall(r"منتهی به\s*(\d{4}/\d{1,2}/\d{1,2})", hdr)

    def cells(key):
        l = next((x for x in lines if "|" in x and (x.startswith(key) or x.startswith("| " + key))), None)   # فقط ردیف جدول، نه زیرعنوان صفحه
        if not l:
            return [None] * len(fys)
        c = [x.strip() for x in l.split("|") if x.strip()][1:]
        c = (c + [None] * len(fys))[:len(fys)]
        return c
    agm, pay, dps = cells("تاریخ مجمع"), cells("زمان پرداخت سود"), cells("سود نقدی هر سهم")
    rows = []
    for i, fy in enumerate(fys):
        a = DATE.findall(agm[i] or "")
        p = DATE.findall(pay[i] or "")
        d = re.search(r"([\d.]+)\s*ریال", dps[i] or "")
        rows.append({"symbol": symbol, "slug": slug, "fy_end_j": fy, "agm_j": a[0] if a else "", "pay_from_j": p[0] if p else "",
                     "pay_to_j": p[-1] if p else "", "dps_rial": d.group(1) if d else ""})
    return symbol, rows


SAMPLE = """<html><head><title>مجمع و پرداخت سود ملی صنایع مس ایران (فملی) | فاندای</title></head><body><h1>x</h1><p>تاریخ مجمع سالیانه، زمان پرداخت سود نقدی و فاصله میان آن دو در هر سال</p>
<table><tr><th>عنوان</th><th>سال مالی منتهی به ۱۴۰۴/۱۲/۲۹</th><th>سال مالی منتهی به ۱۴۰۳/۱۲/۳۰</th><th>سال مالی منتهی به ۱۴۰۲/۱۲/۲۹</th></tr>
<tr><td>تاریخ مجمع</td><td>۱۴۰۵/۰۴/۳۱</td><td>۱۴۰۴/۰۴/۳۱</td><td>۱۴۰۳/۰۴/۳۱</td></tr>
<tr><td>زمان پرداخت سود</td><td>۱۴۰۵/۰۶/۲۵</td><td>۱۴۰۴/۰۷/۰۱ تا ۱۴۰۴/۰۷/۳۰</td><td>-</td></tr>
<tr><td>سود نقدی هر سهم</td><td>۴۵۰ ریال</td><td>۱٬۰۷۰ ریال</td><td>-</td></tr></table></body></html>"""


def selftest():
    s, r = parse(SAMPLE, "femely")
    assert s == "فملی", s
    assert len(r) == 3, r
    assert r[0] == {"symbol": "فملی", "slug": "femely", "fy_end_j": "1404/12/29", "agm_j": "1405/04/31", "pay_from_j": "1405/06/25", "pay_to_j": "1405/06/25", "dps_rial": "450"}, r[0]
    assert r[1]["pay_from_j"] == "1404/07/01" and r[1]["pay_to_j"] == "1404/07/30" and r[1]["dps_rial"] == "1070", r[1]
    assert r[2]["pay_from_j"] == "" and r[2]["dps_rial"] == "", r[2]
    print("selftest OK")


def reparse():
    fr, fo = OUT / "fundai_raw.csv.gz", OUT / "fundai_dividends.csv"
    n = 0
    with gzip.open(fr, "rt", encoding="utf-8", newline="") as z, open(fo, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, FIELDS); w.writeheader()
        for sl, sym, txt in csv.reader(z):
            _, rows = parse("<table>" + "".join(f"<tr><td>{l}</td></tr>" for l in txt.split("\\n")) + "</table>", sl)
            for r in rows:
                r["symbol"] = sym; w.writerow(r); n += 1
    print(f"تجزیهٔ دوباره: {n} ردیف")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--log", default=None)
    ap.add_argument("--reparse", action="store_true", help="فقط از fundai_raw.csv.gz دوباره تجزیه کن (بدون شبکه)")
    ap.add_argument("--limit", type=int, default=0, help="فقط N صفحهٔ اول (برای آزمون)")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.reparse:
        return reparse()
    if a.log:
        sys.stdout = open(a.log, "a", encoding="utf-8", buffering=1)
    slugs, urls = company_pages()
    print(f"sitemap: {len(urls)} آدرس، {len(slugs)} slug شرکت")
    if a.test:
        print("نمونهٔ آدرس‌ها:", urls[:5])
        print("نمونهٔ slug:", slugs[:8])
        for sl in (slugs[:1] or ["femely"]):
            h = get(f"{BASE}/company/{sl}/dividend-calendar")
            print(sl, "->", (parse(h, sl) if h else "صفحه خوانده نشد"))
        return
    OUT.mkdir(parents=True, exist_ok=True)
    fo, fd, fr = OUT / "fundai_dividends.csv", OUT / "fundai_done.csv", OUT / "fundai_raw.csv.gz"
    done = set(l.strip() for l in fd.read_text(encoding="utf-8").splitlines()) if fd.exists() else set()
    new = not fo.exists()
    todo = [s for s in slugs if s not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"انجام‌شده {len(done)}؛ باقی {len(todo)}")
    with open(fo, "a", encoding="utf-8-sig", newline="") as f, open(fd, "a", encoding="utf-8") as g:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()
        for i, sl in enumerate(todo, 1):
            h = get(f"{BASE}/company/{sl}/dividend-calendar")
            if h is None:
                print(f"[{i}/{len(todo)}] {sl}: بدون صفحه", flush=True)
            else:
                sym, rows = parse(h, sl)
                with gzip.open(fr, "at", encoding="utf-8", newline="") as z:
                    csv.writer(z).writerow([sl, sym, table_text(h).replace("\n", "\\n")])
                for r in rows:
                    w.writerow(r)
                f.flush()
                print(f"[{i}/{len(todo)}] {sl} ({sym}): {len(rows)} سال", flush=True)
            g.write(sl + "\n"); g.flush()
            time.sleep(a.delay)
    print("پایان")


if __name__ == "__main__":
    main()
