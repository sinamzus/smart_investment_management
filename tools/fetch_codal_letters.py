#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اطلاعیه‌های افزایش سرمایه (و مجمع فوق‌العاده) کدال → جدول ساخت‌یافته — تکمیل شکاف بند ۷l فصل ۱۰.

    python tools/fetch_codal_letters.py --selftest          # آزمون تجزیه بدون شبکه
    python tools/fetch_codal_letters.py --test              # شبکه: چند نامهٔ ن-67 + نمایش متن و فیلدهای استخراج‌شده
    python tools/fetch_codal_letters.py --test-code ن-57    # نمونه‌برداری از یک کد دیگر (ن-57، ن-64، ن-60، ن-66)
    python tools/fetch_codal_letters.py --log l.txt         # اجرای کامل (قابل ادامه؛ چند ساعت)
    python tools/fetch_codal_letters.py --codes ن-67 --log l.txt   # فقط یک نوع اطلاعیه
    python tools/fetch_codal_letters.py --reparse           # فقط از متن خام دوباره استخراج کن (بدون شبکه)

روش: برای هر کد اطلاعیه (بدون نماد) فهرست همهٔ نامه‌ها صفحه‌به‌صفحه خوانده می‌شود (جدیدترین اول؛ توقف پس از سال --since)، نمادهای خارج از
فهرست نمادهای فعال کنار می‌روند، و صفحهٔ HTML هر نامه (نه PDF، نه OCR) دانلود و به متن تبدیل می‌شود. متن خام (هرچه تجزیه‌گر بعداً بهتر شود) در
data/corporate_actions/codal_letters_raw.csv.gz ذخیره می‌شود؛ جدول استخراج‌شده: codal_capital_events.csv.
کدهای اطلاعیه (فهرست رسمی کدال): ن-60 پیشنهاد هیئت‌مدیره · ن-61 اظهارنظر حسابرس · ن-62 مدارک درخواست · ن-63 تمدید مجوز · ن-64 مهلت حق تقدم ·
ن-65 اعلامیه پذیره‌نویسی · ن-66 نتایج فروش حق تقدم‌های استفاده‌نشده · ن-67 آگهی ثبت افزایش سرمایه · ن-70/73 تصمیم هیئت‌مدیره (تفویض) ·
ن-56 دعوت مجمع فوق‌العاده · ن-57 تصمیمات مجمع فوق‌العاده. ن-68 (آگهی مطالبهٔ مبلغ پرداخت‌نشدهٔ سرمایه) به کار ما نمی‌آید.
"""
import argparse
import csv
import gzip
import html as htmllib
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
OUT = ROOT / "data" / "corporate_actions"
API = "https://search.codal.ir/api/search/v2/q"
SITE = "https://codal.ir"
DEFAULT_CODES = ["ن-67", "ن-57", "ن-64", "ن-60", "ن-66", "ن-65", "ن-73"]
FA = {**{ord(c): str(i % 10) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩")}, ord("٬"): ",", ord("ي"): "ی", ord("ك"): "ک", 0x200c: " "}
SRC = [("claims_cash", r"مطالبات\s*(?:حال\s*شده\s*سهامداران)?\s*و\s*آورده\s*نقدی"), ("cash_waived", r"آورده\s*نقدی\s*با\s*سلب\s*حق\s*تقدم"),
       ("retained", r"سود\s*انباشته"), ("reserves", r"اندوخته"), ("reval", r"مازاد\s*تجدید\s*ارزیابی"), ("premium", r"صرف\s*سهام")]
FIELDS = ["tracing_no", "symbol", "code", "kind", "publish", "title", "license_no", "license_date", "egm_date", "board_date", "old_capital_m", "new_capital_m", "inc_m", "pct",
          "src_claims_cash_m", "src_cash_waived_m", "src_retained_m", "src_reserves_m", "src_reval_m", "src_premium_m", "approval", "rights_from", "rights_to", "reg_date",
          "unused_rights", "per_right_rial", "purpose", "superseded", "amends"]


def jdate(s):
    m = re.search(r"(\d{4})/(\d{1,2})/(\d{1,2})", str(s or ""))
    return "%04d/%02d/%02d" % tuple(map(int, m.groups())) if m else ""


def num(s):
    s = re.sub(r"[^\d.]", "", str(s or "").replace(",", ""))
    try:
        return float(s) if s else None
    except ValueError:
        return None


def html_text(h):
    """HTML → متن تخت: سلول‌ها با « | »، ارقام لاتین، بدون برچسب."""
    h = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?i)</t[dh]\s*>", " | ", h)
    h = re.sub(r"(?i)</tr\s*>|<br\s*/?>|</(p|h\d|li|div|table)\s*>", "\n", h)
    h = re.sub(r"<[^>]+>", " ", h)
    t = htmllib.unescape(h).translate(FA)
    t = re.sub(r"[ \t\r\f\v\xa0]+", " ", t)
    return re.sub(r"\n\s*(?:\n\s*)+", "\n", t)                                  # خط‌های خالی پشت‌سرهم → یکی


def flat(t):
    return re.sub(r"\s+", " ", t.replace("|", " | "))


def to_million(v, unit):
    if v is None:
        return None
    u = re.sub(r"\s+", "", unit or "")
    return v / 1e6 if u == "ریال" else v * 1000 if u.startswith("میلیارد") else v


def sources(t):
    """«از محل X مبلغ N میلیون ریال» و «از آورده نقدی با سلب حق تقدم … مبلغ N» → {نام: میلیون ریال}."""
    out = {}
    for key, pat in SRC:
        m = re.search(r"(?:از\s*محل\s*|و\s*از\s*|،\s*)?(?:" + pat + r")(?:[^\d()|]{0,40}?)مبلغ\s*([\d,]+)\s*(میلیارد\s*ریال|میلیون\s*ریال|ریال)", t)
        if m:
            out[key] = to_million(num(m.group(1)), m.group(2))
    return out


def lic(t):
    m = re.search(r"(?:شماره\s*مجوز|کد:?)\s*\|?\s*([A-Z]{2,}[A-Z0-9\-]+)\s*\|?\s*(?:مورخ|تاریخ:?)\s*\|?\s*(\d{4}/\d{1,2}/\d{1,2})", t)
    if not m:
        m2, m3 = re.search(r"(DPM-[A-Z0-9\-]+)", t), re.search(r"تاریخ:?\s*\|?\s*(\d{4}/\d{1,2}/\d{1,2})", t)
        return (m2.group(1) if m2 else "", jdate(m3.group(1)) if m3 else "")
    return m.group(1), jdate(m.group(2))


def parse_letter(code, title, text):
    """-> dict از FIELDS (فقط فیلدهای یافت‌شده). نوع نامه از عنوان تشخیص داده می‌شود (کد ممکن است برای چند نوع مشترک باشد)."""
    t = flat(text)
    r, ti = {}, re.sub(r"\s+", "", title or "")
    if re.search(r"این\s*اطلاعیه\s*نسخه\s*جدیدتری", t):
        r["superseded"] = 1                                                          # نسخهٔ جدیدتر (اصلاحیه) دارد؛ در جدول نهایی کنار گذاشته شود
    m = re.search(r"اصلاحیه\s*اطلاعیه\s*شماره\s*\(?\s*(\d+)", t)
    if m:
        r["amends"] = m.group(1)
    no, ld = lic(t)
    if no:
        r["license_no"], r["license_date"] = no, ld
    m = re.search(r"مجمع\s*عمومی\s*فوق\s*العاده[^.]{0,200}?مورخ\s*(\d{4}/\d{1,2}/\d{1,2})", t)
    if m:
        r["egm_date"] = jdate(m.group(1))
    m = re.search(r"از\s*مبلغ\s*([\d,]+)\s*(میلیارد\s*ریال|میلیون\s*ریال|ریال)\s*به\s*[‌ ]?مبلغ\s*([\d,]+)\s*(میلیارد\s*ریال|میلیون\s*ریال|ریال)", t)
    if m:
        r["old_capital_m"], r["new_capital_m"] = to_million(num(m.group(1)), m.group(2)), to_million(num(m.group(3)), m.group(4))
        r["inc_m"] = r["new_capital_m"] - r["old_capital_m"]
    for k, v in sources(t).items():
        r["src_" + k + "_m"] = v
    if "آگهیثبتافزایشسرمایه" in ti:
        r["kind"] = "registered"
        m = re.search(r"در\s*تاریخ\s*(\d{4}/\d{1,2}/\d{1,2})\s*در\s*مرجع\s*ثبت", t)
        if m:
            r["reg_date"] = jdate(m.group(1))
    elif "مهلتاستفادهازحقتقدم" in ti:
        r["kind"] = "rights_deadline"
        m = re.search(r"از\s*تاریخ\s*(\d{4}/\d{1,2}/\d{1,2})\s*لغایت\s*(?:تاریخ\s*)?(\d{4}/\d{1,2}/\d{1,2})", t)
        if m:
            r["rights_from"], r["rights_to"] = jdate(m.group(1)), jdate(m.group(2))
    elif "پیشنهادهیئتمدیره" in ti and "افزایشسرمایه" in ti:
        r["kind"] = "board_proposal"
        m = re.search(r"که\s*در\s*تاریخ\s*(\d{4}/\d{1,2}/\d{1,2})\s*به\s*تصویب", t)
        if m:
            r["board_date"] = jdate(m.group(1))
        m = re.search(r"از\s*محل\s*([^،.]*?(?:،[^،.]*?)*?)\s*به\s*منظور\s*([^.\d]*?)\s*که\s*در\s*تاریخ", t)
        if m:
            r["purpose"] = m.group(2).strip()
            for key, pat in SRC:
                if re.search(pat, m.group(1)) and ("src_" + key + "_m") not in r:
                    r["src_" + key + "_m"] = 0.0                                     # منبع اعلام شده، مبلغ ندارد
    elif "نتایجحاصلازفروشحقتقدم" in ti:
        r["kind"] = "unused_rights_result"
        m = re.search(r"تعداد\s*حق\s*تقدم[^|]*?\|\s*([\d,]+)", t)
        r["unused_rights"] = num(m.group(1)) if m else None
        m = re.search(r"مبلغ\s*متعلق\s*به\s*هر\s*حق\s*تقدم\s*\|\s*([\d,]+)", t)
        r["per_right_rial"] = num(m.group(1)) if m else None
    elif "صدورمجوزافزایشسرمایه" in ti:
        r["kind"] = "license"
        m = re.search(r"سرمایه\s*فعلی:?\s*\|?\s*([\d,]+)\s*ریال", t)
        old = num(m.group(1)) / 1e6 if m else None
        m = re.search(r"مبلغ\s*افزایش\s*سرمایه:?\s*\|?\s*([\d,]+)\s*ریال", t)
        inc = num(m.group(1)) / 1e6 if m else None
        if old is not None and inc is not None:
            r["old_capital_m"], r["inc_m"], r["new_capital_m"] = old, inc, old + inc
        for key, pat in SRC:
            mm = re.search(r"([\d,]+)\s*ریال\s*از\s*محل\s*(?:" + pat + ")", t)
            if mm:
                r["src_" + key + "_m"] = num(mm.group(1)) / 1e6
        m = re.search(r"موضوع\s*افزایش\s*سرمایه:?\s*\|?\s*([^|]+?)\s*(?:همچنین|\|)", t)
        if m:
            r["purpose"] = m.group(1).strip()
    elif "تصمیماتمجمععمومیفوقالعاده" in ti or "تصمیماتمجمعفوق" in ti:
        r["kind"] = "egm_decision"
        k = t.find("قطعی")
        if k > 0:                                                                    # ۱۱ سلول عددی (تعداد سهام … درصد) پیش از «قطعی» در متن تخت
            cells = [c.strip() for c in t[max(0, k - 600):k].split("|")]
            while cells and not cells[-1]:
                cells.pop()
            nums = [num(c) for c in cells[-11:] if re.fullmatch(r"[\d,]*(\.\d+)?", c)]
            if len(nums) == 11 and all(v is not None for v in nums[:3]):
                sh, par, cap, cc, re_, rs, rv, pr, cw, inc, pct = [v or 0.0 for v in nums]
                r.update({"old_capital_m": cap, "inc_m": inc, "new_capital_m": cap + inc, "pct": pct, "src_claims_cash_m": cc, "src_retained_m": re_,
                          "src_reserves_m": rs, "src_reval_m": rv, "src_premium_m": pr, "src_cash_waived_m": cw, "approval": "قطعی"})
        if "approval" not in r:
            r["approval"] = "بدون افزایش سرمایه" if "افزایشسرمایه" not in re.sub(r"\s+", "", t) else "نامشخص"
    elif "پذیرهنویسی" in ti:
        r["kind"] = "public_offering"
    r.setdefault("kind", "other")
    return r


SAMPLES = {
    "ثبت": ("ن-67", "آگهی ثبت افزایش سرمایه", "آگهی ثبت افزایش سرمایه شرکت توليد و توسعه سرب و روي ايرانيان - نماد: فتوسا | موضوع: آگهی ثبت افزایش سرمایه | با عنایت به مجوز افزایش سرمایه به شماره مجوز DPM-IOP-03A-230 مورخ 1403/12/12 بر اساس تصمیمات مجمع عمومی فوق العاده مورخ 1403/12/25 افزایش سرمایۀ شرکت از مبلغ 1,425,000 میلیون ریال به‌مبلغ 1,800,000 میلیون ریال ( از محل سود انباشته مبلغ 375000 میلیون ریال ، میلیون ریال و از آورده نقدی با سلب حق تقدم از سهامداران فعلی مبلغ میلیون ریال ) در در تاریخ 1403/12/28 در مرجع ثبت شرکت ها به ثبت رسیده است."),
    "حق تقدم": ("ن-64", "مهلت استفاده از حق تقدم خرید سهام", "با عنایت به مجوز افزایش سرمایه به شماره مجوز DPM-IOP-03A-073 مورخ 1403/07/01 و بر اساس تصمیمات مجمع عمومی فوق العاده مورخ 1403/08/15 با توجه به افزایش سرمایهُ شرکت از مبلغ 1,200,000 میلیون ریال به‌مبلغ 3,400,000 میلیون ریال ( از محل مطالبات و آورده نقدی مبلغ 1,500,000 میلیون ریال، از محل سود انباشته مبلغ 700,000 میلیون ریال، ) ، مهلت استفاده از حق تقدم خرید سهام از تاریخ 1403/08/27 لغایت تاریخ 1403/09/26 و شماره حسابهای زیر"),
    "پیشنهاد": ("ن-60", "پیشنهاد هیئت مدیره به مجمع عمومی فوق العاده در خصوص افزایش سرمایه", "گزارش توجیهی هیئت مدیرة به منظور پیشنهادافزایش سرمایه از مبلغ 1,696,407,000,000 ریال به مبلغ 4,798,207,000,000 ریال از محل سود انباشته ،مازاد تجدید ارزیابی دارایی ها به منظور اصلاح ساختار مالي که در تاریخ 1403/12/12 به تصویب هیئت مدیره رسیده و جهت اظهارنظر"),
    "نتایج": ("ن-66", "نتایج حاصل از فروش حق تقدم های استفاده نشده", "| شرح | مبلغ (ریال) |\n| مبلغ فروش حق تقدم های استفاده نشده | 250,140,363,227 |\n| تعداد حق تقدم های استفاده نشده | 340,235,247 |\n| مبلغ متعلق به هر حق تقدم | 726 |"),
    "مجوز": ("ن-68", "صدور مجوز افزایش سرمایه", "| تاریخ: | 1404/01/27 |\n| کد: | DPM-IOP-04A-004 |\n سرمایه فعلی: \n 14,040,000,000,000 ریال \n تعداد سهام قابل انتشار: \n 4,760,000,000 سهم \n مبلغ افزایش سرمایه: \n 4,760,000,000,000 ریال \n منبع تأمین افزایش سرمایه: \n- 4,760,000,000,000 ریال از محل سود انباشته،\n موضوع افزایش سرمایه: \n اصلاح ساختار مالي و جلوگيري از خروج نقدينگي \n همچنین مجمع"),
    "مجمع": ("ن-57", "تصمیمات مجمع عمومی فوق العاده دوره 12 ماهه منتهی به 1404/03/31", "با عنایت به مجوز افزایش سرمایه به شماره مجوز DPM-IOP-03A-229 مورخ 1403/12/12، مجمع عمومی فوق‌العاده صاحبان سهام شرکت، بر اساس آگهی منتشره در سامانه کدال در تاریخ 1403/12/13 در خصوص دعوت به مجمع عمومی فوق العاده راُس ساعت 10:00 روز یکشنبه مورخ 1403/12/26 درمحل میدان شهدا برگزار گردید\n| 750,000,000,000 | 1,000 | 750,000,000 | 0 | 250,000,000 | 0 | 0 | 0 | 0 | 250,000,000 | 33 | قطعی |\n| | | | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | در اختیار هیئت‌مدیره |"),
}


def selftest():
    p = {k: parse_letter(*v) for k, v in SAMPLES.items()}
    a = p["ثبت"]
    assert a["kind"] == "registered" and a["license_no"] == "DPM-IOP-03A-230" and a["license_date"] == "1403/12/12" and a["egm_date"] == "1403/12/25" and a["reg_date"] == "1403/12/28", a
    assert a["old_capital_m"] == 1425000 and a["new_capital_m"] == 1800000 and a["inc_m"] == 375000 and a["src_retained_m"] == 375000, a
    b = p["حق تقدم"]
    assert b["rights_from"] == "1403/08/27" and b["rights_to"] == "1403/09/26" and b["src_claims_cash_m"] == 1500000 and b["src_retained_m"] == 700000 and b["inc_m"] == 2200000, b
    c = p["پیشنهاد"]
    assert c["kind"] == "board_proposal" and c["board_date"] == "1403/12/12" and c["old_capital_m"] == 1696407 and c["new_capital_m"] == 4798207 and c["src_retained_m"] == 0.0 and c["src_reval_m"] == 0.0, c
    d = p["نتایج"]
    assert d["unused_rights"] == 340235247 and d["per_right_rial"] == 726, d
    e = p["مجوز"]
    assert e["kind"] == "license" and e["license_no"] == "DPM-IOP-04A-004" and e["license_date"] == "1404/01/27" and e["old_capital_m"] == 14040000 and e["src_retained_m"] == 4760000, e
    f = p["مجمع"]
    assert f["kind"] == "egm_decision" and f["egm_date"] == "1403/12/26" and f["pct"] == 33 and f["src_retained_m"] == 250000000 and f["approval"] == "قطعی", f
    g = parse_letter("ن-67", "آگهی ثبت افزایش سرمایه", "این اطلاعیه نسخه جدیدتری به شماره ( 1612358 ) دارد. | با عنایت به مجوز افزایش سرمایه به شماره مجوز DPM-IOP-93A-137 مورخ 1393/10/14")
    assert g.get("superseded") == 1, g
    h2 = parse_letter("ن-67", "آگهی ثبت افزایش سرمایه(اصلاحیه)", "این اطلاعیه اصلاحیه اطلاعیه شماره ( 1611885 ) می باشد.")
    assert h2.get("amends") == "1611885", h2
    print("selftest OK")


# ── شبکه ─────────────────────────────────────────────────────────────────────
def list_page(h, code, page):
    return h.get(API, params={"Symbol": "", "Category": -1, "LetterCode": code, "Length": -1, "Audited": "true", "NotAudited": "true", "Consolidatable": "true",
                              "NotConsolidatable": "true", "Childs": "true", "Mains": "true", "Publisher": "false", "AuditorRef": -1, "CompanyState": -1,
                              "CompanyType": -1, "LetterType": -1, "TracingNo": -1, "IsNotAudited": "false", "PageNumber": page, "search": "true"})


def universe():
    f = ROOT / "data" / "research" / "coverage_audit.csv"
    import pandas as pd
    A = pd.read_csv(f, dtype={"ins_code": str})
    A["last"] = pd.to_datetime(A["last"])
    act = A[(A.operating == True) & (A["last"] >= A["last"].max() - pd.Timedelta(days=400))]  # noqa: E712  (نمادهای ۲۰۲۵ به بعد؛ نماد ازدست‌رفته هم برای افزایش‌های قدیمی لازم است)
    return {re.sub(r"[\s‌]+", "", str(s).translate(FA)) for s in act.symbol}


def get_html(h, url):
    b = h.get(url if url.startswith("http") else SITE + url, binary=True)
    return b.decode("utf-8", errors="replace") if b else None


def run(a):
    from fetch_codal_fundamentals import Http
    h = Http(a.delay)
    OUT.mkdir(parents=True, exist_ok=True)
    raw, done_f = OUT / "codal_letters_raw.csv.gz", OUT / "codal_letters_done.csv"
    done = set(done_f.read_text(encoding="utf-8").split()) if done_f.exists() else set()
    uni = universe()
    print(f"نمادهای هدف: {len(uni)}؛ انجام‌شده: {len(done)}", flush=True)
    for code in a.codes:
        page, seen, stop = 1, 0, False
        while not stop and page <= a.max_pages:
            d = list_page(h, code, page)
            for k in range(4):                                                       # خطا (None) با «پایان فهرست» (Letters خالی) فرق دارد: خطا → ۱۰ دقیقه صبر و تلاش دوباره
                if d is not None:
                    break
                print(f"{code}: صفحه {page} پاسخ نداد (محدودیت نرخ/شبکه)؛ {10 * (k + 1)} دقیقه صبر", flush=True)
                time.sleep(600 * (k + 1))
                d = list_page(h, code, page)
            if d is None:
                print(f"{code}: صفحه {page} هنوز پاسخ نمی‌دهد؛ اجرا را بعداً با همان دستور ادامه دهید", flush=True)
                return
            L = d.get("Letters") or []
            if not L:
                print(f"{code}: صفحه {page} خالی؛ پایان این کد", flush=True)
                break
            for x in L:
                y = int((jdate(x.get("PublishDateTime") or x.get("SentDateTime")) or "0000")[:4])
                if y and y < a.since:
                    stop = True
                    continue
                sym = re.sub(r"[\s‌]+", "", str(x.get("Symbol", "")).translate(FA))
                tn = str(x.get("TracingNo"))
                if sym not in uni or tn in done:
                    continue
                t = get_html(h, x.get("Url") or "")
                if not t:
                    h.delay = min(h.delay * 2, 20.0)                                 # تطبیق‌پذیر: پس از شکست، تأخیر دو برابر
                    print(f"  بدون HTML: {sym} {tn}؛ تأخیر → {h.delay:.1f}s", flush=True)
                    continue
                h.delay = max(a.delay, h.delay * 0.92)                              # پس از موفقیت، آرام‌آرام کمتر
                text = html_text(t)[:12000]
                with gzip.open(raw, "at", encoding="utf-8", newline="") as z:
                    csv.writer(z).writerow([tn, sym, code, jdate(x.get("PublishDateTime") or x.get("SentDateTime")), x.get("Title", ""), text.replace("\n", "\\n")])
                with open(done_f, "a", encoding="utf-8") as g:
                    g.write(tn + "\n")
                done.add(tn); seen += 1
            print(f"{code}: صفحه {page}/{-(-int(d.get('Total', 0)) // 20)}؛ ذخیره‌شده {seen}", flush=True)
            page += 1
    reparse()


def reparse():
    raw = OUT / "codal_letters_raw.csv.gz"
    if not raw.exists():
        print("متن خامی نیست")
        return
    rows = []
    csv.field_size_limit(10 ** 8)
    with gzip.open(raw, "rt", encoding="utf-8", newline="") as z:
        for tn, sym, code, pub, title, text in csv.reader(z):
            r = parse_letter(code, title, text.replace("\\n", "\n"))
            rows.append({"tracing_no": tn, "symbol": sym, "code": code, "publish": pub, "title": title, **r})
    with open(OUT / "codal_capital_events.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, FIELDS, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    import collections
    print(f"{len(rows)} نامه؛ نوع‌ها:", dict(collections.Counter(r["kind"] for r in rows)))


def test(a):
    from fetch_codal_fundamentals import Http
    h = Http(a.delay)
    d = list_page(h, "ن-67", 1)
    L = (d or {}).get("Letters") or []
    print("Total:", (d or {}).get("Total"), "· نامه‌های صفحهٔ ۱:", len(L))
    for x in L[:3]:
        print(" ", x.get("Symbol"), x.get("PublishDateTime"), x.get("Title"), x.get("Url"))
    if not L:
        print("نامه‌ای نیامد؛ خروجی بالا را بفرستید (ممکن است پارامتر یا مسدودی باشد)")
        return
    for x in L[:2]:
        t = get_html(h, x.get("Url") or "")
        if not t:
            print("HTML نیامد برای", x.get("Url")); continue
        text = html_text(t)
        print("\n--- متن (۱۲۰۰ نویسهٔ اول) ---\n", text[:1200], "\n--- استخراج ---\n", parse_letter("ن-67", x.get("Title", ""), text))
    for code in ("ن-57", "ن-64", "ن-60"):
        d = list_page(h, code, 1)
        print(code, "Total:", (d or {}).get("Total"), [ (z.get("Symbol"), z.get("Title")) for z in ((d or {}).get("Letters") or [])[:2]])


def test_code(a):
    """نمونه‌برداری از یک کد: ۸ نامهٔ نخست (برای ن-57 فقط نامه‌هایی که متنشان «افزایش سرمایه» دارد) و استخراج‌شان."""
    from fetch_codal_fundamentals import Http
    h = Http(a.delay)
    d = list_page(h, a.test_code, 1)
    L = (d or {}).get("Letters") or []
    print(a.test_code, "Total:", (d or {}).get("Total"), "· صفحهٔ ۱:", len(L))
    shown = 0
    for x in L:
        if shown >= 3:
            break
        t = get_html(h, x.get("Url") or "")
        if not t:
            continue
        text = html_text(t)
        if a.test_code == "ن-57" and "افزایش سرمایه" not in text:
            continue
        shown += 1
        fl = flat(text); k = fl.find("قطعی")
        print("\n===", x.get("Symbol"), x.get("PublishDateTime"), x.get("Title"), "\n متن (۹۰۰ نویسه):", fl[:900], "\n اطراف «قطعی»:", fl[max(0, k - 300):k + 40] if k > 0 else "(نیست)", "\n استخراج:", parse_letter(a.test_code, x.get("Title", ""), text))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-code", help="نمونه‌برداری از یک کد، مثلاً ن-57")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--reparse", action="store_true")
    ap.add_argument("--codes", default=",".join(DEFAULT_CODES))
    ap.add_argument("--since", type=int, default=1399, help="قدیمی‌ترین سال انتشار (جلالی)")
    ap.add_argument("--delay", type=float, default=6.0, help="کف تأخیر بین درخواست‌ها (ثانیه)؛ پس از ۴۲۹ خودکار بیشتر می‌شود")
    ap.add_argument("--max-pages", type=int, default=400)
    ap.add_argument("--log")
    a = ap.parse_args()
    a.codes = [c.strip() for c in a.codes.split(",") if c.strip()]
    if a.selftest:
        return selftest()
    if a.reparse:
        return reparse()
    if a.log:
        sys.stdout = sys.stderr = open(a.log, "a", encoding="utf-8", buffering=1)
    if a.test_code:
        return test_code(a)
    return test(a) if a.test else run(a)


if __name__ == "__main__":
    main()
