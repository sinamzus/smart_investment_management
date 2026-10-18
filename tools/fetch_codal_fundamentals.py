#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دریافت صورت‌های مالی سالانه از کدال برای نمادهایی که رهاورد۳۶۵ ندارد (روی سیستم شما، با اینترنت ایران اجرا شود؛
محیط ابری به codal.ir دسترسی ندارد — آزموده‌شده: ۴۰۳ پراکسی).

    pip install requests
    python tools/fetch_codal_fundamentals.py --selftest              # آزمون تجزیهٔ HTML بدون شبکه
    python tools/fetch_codal_fundamentals.py --test فملی             # یک نماد را کامل می‌گیرد و گزارش می‌دهد
    python tools/fetch_codal_fundamentals.py --log c.txt             # نمادهای فهرست شکاف (data/research/fund_gap_active_operating.csv)
    python tools/fetch_codal_fundamentals.py --symbols-file x.csv    # فهرست دلخواه با ستون‌های ins_code,symbol
    --delay 3        فاصلهٔ ثانیه‌ای بین درخواست‌ها (کدال پس از ~۴۰ درخواست پیاپی ۴۲۹ می‌دهد؛ مقدار پایین‌تر از ۲ توصیه نمی‌شود)

مسیر (API عمومی search.codal.ir، سند: amirziveh/codal-skill و mostafaasadi/codaler؛ هر دو [راستی‌آزمایی نشده] روی این مخزن):
    GET /api/search/v2/q?Symbol=…&Category=1&LetterCode=ن-10&Length=12&Childs=false&Mains=true&…   فهرست «صورت مالی سالانه» (Accept: application/json)
    ExcelUrl هر نامه (excel.codal.ir/service/Excel/GetAll/<serial>/0)  ← جدول‌های HTML (۱۳۹۷ به بعد؛ پیش از آن OLE2 دودویی که رد می‌شود)

خروجی (قابل push):
    data/fundamentals/codal_letters.csv   ins_code, symbol, tracing_no, title, fy_end, audited, consolidated, published, excel_url
    data/fundamentals/codal_long.csv      ins_code, symbol, tracing_no, fy_year, fy_end, col, stmt(bs|pl), key, label, value
                                          col = cur (سال مالی نامه) | prev (ستون سال قبل همان نامه)؛ مقدار به میلیون ریال [تأیید لازم]
    data/fundamentals/codal_done.csv      نمادهای کامل‌شده (برای ادامه)

tools/build_quality.py اگر این فایل‌ها را ببیند، برای نمادهایی که رهاورد ندارد ROE و D/E را از آن می‌سازد و
«تاریخ دانستن» را از زمان نخستین انتشار کدال (published) می‌گیرد، نه تقریب ۱۲۰ روزه.
"""
import argparse
import csv
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = ROOT / "data" / "fundamentals"
GAP = ROOT / "data" / "research" / "fund_gap_active_operating.csv"
API = "https://search.codal.ir/api/search/v2/q"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "application/json", "Accept-Language": "fa-IR,fa;q=0.9"}
FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# برچسب (نرمال‌شده) ← (صورت، کلید). فقط پیشوند؛ نخستین رخداد هر کلید در هر نامه می‌ماند (ترازنامه/سود‌وزیان اول فایل = معمولاً تلفیقی در صورت وجود).
LABELS = [
    ("bs", "assets", "جمعدارایی"),
    ("bs", "liabilities", "جمعبدهی"),
    ("bs", "equity", "جمعحقوقمالکانه"),
    ("bs", "equity", "جمعحقوقصاحبانسهام"),
    ("bs", "capital", "سرمایه"),
    ("pl", "revenue", "درآمدهایعملیاتی"),
    ("pl", "revenue", "فروشخالص"),
    ("pl", "op_profit", "سودزیانعملیاتی"),
    ("pl", "net_income", "سودزیانخالص"),
]


def norm(s: str) -> str:
    s = (s or "").translate(FA).replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"[\s‌‏‎()\[\]:،,\-–—.]+", "", s)


def num(s: str):
    s = (s or "").translate(FA).replace("٬", ",").strip()
    if not s or s in {"-", "—", "–"}:
        return None
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-")
    s = re.sub(r"[^\d.]", "", s.replace(",", ""))
    if not s:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


class Tables(HTMLParser):
    """تجزیهٔ ساده بدون وابستگی: فهرست جدول‌ها، هر کدام فهرست ردیف‌ها، هر ردیف فهرست متن سلول‌ها."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self._row, self._cell, self._depth = [], None, None, 0

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._depth += 1
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self.tables:
            if any(self._row):
                self.tables[-1].append(self._row)
            self._row = None
        elif tag == "table":
            self._depth -= 1

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_statements(html: str):
    """[(stmt, key, label, cur, prev)] — نخستین رخداد هر (stmt,key)؛ ستون نخست عددی = سال جاری، دومین = سال قبل."""
    p = Tables()
    p.feed(html)
    out, seen = [], set()
    for tbl in p.tables:
        blob = norm(" ".join(c for r in tbl[:6] for c in r))
        stmt_hint = "pl" if ("سودوزیان" in blob or "سودزیان" in blob) and "ترازنامه" not in blob else ("bs" if "ترازنامه" in blob or "وضعیتمالی" in blob else None)
        for row in tbl:
            lab = next((c for c in row if num(c) is None and norm(c)), None)
            if lab is None:
                continue
            vals = [v for v in (num(c) for c in row[row.index(lab) + 1:]) if v is not None]
            if not vals:
                continue
            nl = norm(lab)
            for stmt, key, pref in LABELS:
                if nl.startswith(pref) and (stmt_hint in (None, stmt)) and (stmt, key) not in seen:
                    # «سرمایه» دقیق (نه «سرمایه‌گذاری…»): برچسب کوتاه
                    if key == "capital" and len(nl) > 12:
                        continue
                    seen.add((stmt, key))
                    out.append((stmt, key, lab, vals[0], vals[1] if len(vals) > 1 else None))
                    break
    return out


def jdate(s: str):
    m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", (s or "").translate(FA))
    return tuple(map(int, m.groups())) if m else None


def selftest():
    html = """<html><body>
    <table><tr><th>ترازنامه</th></tr><tr><td>شرح</td><td>۱۴۰۳/۱۲/۳۰</td><td>۱۴۰۲/۱۲/۲۹</td></tr>
    <tr><td>جمع دارایی‌ها</td><td>۱,۲۰۰,۰۰۰</td><td>(۹۰۰,۰۰۰)</td></tr>
    <tr><td>جمع بدهی‌ها</td><td>۷۰۰,۰۰۰</td><td>۶۰۰,۰۰۰</td></tr>
    <tr><td>جمع حقوق مالکانه</td><td>۵۰۰,۰۰۰</td><td>۳۰۰,۰۰۰</td></tr>
    <tr><td>سرمایه</td><td>۱۰۰,۰۰۰</td><td>۱۰۰,۰۰۰</td></tr></table>
    <table><tr><td>صورت سود و زیان</td></tr>
    <tr><td>درآمدهای عملیاتی</td><td>۸۰۰,۰۰۰</td><td>۵۰۰,۰۰۰</td></tr>
    <tr><td>سود (زیان) خالص</td><td>۱۵۰,۰۰۰</td><td>-</td></tr></table></body></html>"""
    got = {(s, k): (c, p) for s, k, _l, c, p in parse_statements(html)}
    assert got[("bs", "assets")] == (1200000.0, -900000.0), got
    assert got[("bs", "equity")] == (500000.0, 300000.0) and got[("bs", "liabilities")][0] == 700000.0, got
    assert got[("pl", "net_income")] == (150000.0, None) and got[("pl", "revenue")][0] == 800000.0, got
    assert got[("bs", "capital")][0] == 100000.0
    assert jdate("۱۴۰۴/۰۳/۱۵ ۱۲:۲۶") == (1404, 3, 15)
    print("selftest OK:", len(got), "کلید")


class Http:
    def __init__(self, delay):
        import requests
        self.s, self.delay, self.last = requests.Session(), delay, 0.0
        self.s.headers.update(HEADERS)

    def get(self, url, params=None, binary=False, tries=6):
        wait = 30
        for i in range(tries):
            gap = self.delay - (time.time() - self.last)
            if gap > 0:
                time.sleep(gap)
            self.last = time.time()
            try:
                r = self.s.get(url, params=params, timeout=60)
            except Exception as e:                       # noqa: BLE001
                print(f"   خطای شبکه: {str(e)[:80]}؛ {wait}s", flush=True)
                time.sleep(wait)
                wait = min(wait * 2, 600)
                continue
            if r.status_code == 429:
                print(f"   ۴۲۹ (محدودیت نرخ)؛ {wait}s صبر", flush=True)
                time.sleep(wait)
                wait = min(wait * 2, 900)
                continue
            if r.status_code != 200:
                return None
            return r.content if binary else r.json()
        return None


def list_letters(h: Http, symbol: str):
    """نامه‌های «صورت مالی سالانهٔ ۱۲ماهه» (ن-۱۰) شرکت اصلی؛ زیرمجموعه‌ها کنار می‌روند."""
    letters, page = [], 1
    while page <= 12:
        d = h.get(API, params={"Symbol": symbol, "Category": 1, "LetterCode": "ن-10", "Length": 12, "Audited": "true", "NotAudited": "true",
                               "Consolidatable": "true", "NotConsolidatable": "true", "Childs": "false", "Mains": "true", "Publisher": "false",
                               "AuditorRef": -1, "CompanyState": -1, "CompanyType": -1, "LetterType": -1, "TracingNo": -1,
                               "IsNotAudited": "false", "PageNumber": page, "search": "true"})
        if not d or not d.get("Letters"):
            break
        letters += d["Letters"]
        if len(letters) >= d.get("Total", 0):
            break
        page += 1
    out = []
    for L in letters:
        t = norm(L.get("Title", ""))
        if "صورتهایمالی" not in t or "سالمالی" not in t or "(شرکت" in (L.get("Title", "")).replace("‌", ""):
            continue
        fy = jdate(L.get("Title", ""))
        if not fy or not L.get("HasExcel") or not L.get("ExcelUrl"):
            continue
        out.append({"tracing_no": L.get("TracingNo"), "title": L["Title"], "fy_end": "%04d/%02d/%02d" % fy,
                    "audited": int("حسابرسیشده" in t and "حسابرسینشده" not in t), "consolidated": int("تلفیقی" in t),
                    "published": "%04d/%02d/%02d" % (jdate(L.get("PublishDateTime") or L.get("SentDateTime")) or (0, 0, 0)),
                    "excel_url": L["ExcelUrl"]})
    return out


def pick(letters):
    """برای هر سال مالی: انتشار نخست (تاریخ دانستن) + نامهٔ ارزشمندتر برای مقدار (حسابرسی‌شده، سپس تلفیقی، سپس جدیدتر)."""
    by = {}
    for L in letters:
        by.setdefault(L["fy_end"][:4], []).append(L)
    res = []
    for fy, g in sorted(by.items()):
        first = min(x["published"] for x in g)
        best = sorted(g, key=lambda x: (x["audited"], x["consolidated"], x["published"]))[-1]
        res.append({**best, "first_published": first})
    return res


def rows_for(L, ins, sym, content: bytes):
    if content[:4] == b"\xd0\xcf\x11\xe0":
        print("   فایل قدیمی OLE2؛ رد شد")
        return []
    html = content.decode("utf-8", errors="replace")
    fy = int(L["fy_end"][:4])
    out = []
    for stmt, key, label, cur, prev in parse_statements(html):
        out.append([ins, sym, L["tracing_no"], fy, L["fy_end"], "cur", stmt, key, label, cur])
        if prev is not None:
            out.append([ins, sym, L["tracing_no"], fy - 1, "", "prev", stmt, key, label, prev])
    return out


def append(path, header, rows):
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(header)
        w.writerows(rows)


def do_symbol(h, ins, sym, dry=False):
    ls = pick(list_letters(h, sym))
    print(f"{sym}: {len(ls)} سال مالی", flush=True)
    longs = []
    for L in ls:
        c = h.get(L["excel_url"], binary=True)
        if not c:
            print(f"   {L['fy_end']}: دریافت ناموفق", flush=True)
            continue
        r = rows_for(L, ins, sym, c)
        keys = {x[7] for x in r}
        print(f"   {L['fy_end']} {'ح' if L['audited'] else 'غ'}{'ت' if L['consolidated'] else ''}: {len(r)} ردیف؛ کلیدها {sorted(keys)}", flush=True)
        longs += r
    if not dry:
        append(OUT / "codal_letters.csv", ["ins_code", "symbol", "tracing_no", "title", "fy_end", "audited", "consolidated", "published", "excel_url", "first_published"],
               [[ins, sym] + [L[k] for k in ("tracing_no", "title", "fy_end", "audited", "consolidated", "published", "excel_url", "first_published")] for L in ls])
        append(OUT / "codal_long.csv", ["ins_code", "symbol", "tracing_no", "fy_year", "fy_end", "col", "stmt", "key", "label", "value"], longs)
        append(OUT / "codal_done.csv", ["ins_code", "symbol", "n_years"], [[ins, sym, len(ls)]])
    return len(ls)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--test", metavar="SYMBOL")
    ap.add_argument("--symbols-file")
    ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--log")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.log:
        sys.stdout = sys.stderr = open(a.log, "a", encoding="utf-8", buffering=1)
    OUT.mkdir(parents=True, exist_ok=True)
    h = Http(a.delay)
    if a.test:
        n = do_symbol(h, "", a.test, dry=True)
        print("نتیجه:", "کدال پاسخ داد" if n else "هیچ نامه‌ای نیامد (مسدودی/نماد/پارامتر)؛ خروجی بالا را بفرستید")
        return
    src = Path(a.symbols_file) if a.symbols_file else GAP
    rows = list(csv.DictReader(open(src, encoding="utf-8-sig")))
    done = set()
    if (OUT / "codal_done.csv").exists():
        done = {r["ins_code"] for r in csv.DictReader(open(OUT / "codal_done.csv", encoding="utf-8-sig"))}
    todo = [r for r in rows if r["ins_code"] not in done]
    print(f"{len(todo)} نماد برای دریافت ({len(done)} قبلاً انجام شده)", flush=True)
    for i, r in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}]", end=" ", flush=True)
        do_symbol(h, r["ins_code"], r["symbol"])


if __name__ == "__main__":
    main()
