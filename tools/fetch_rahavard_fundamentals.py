#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""دریافت صورت‌های مالی سالانه از رهاورد۳۶۵ برای فاکتور کیفیت (روی سیستم شما اجرا شود؛ محیط ابری به رهاورد دسترسی ندارد).

API عمومی (بدون ورود) که ضبط مرورگر نشان داد (data/raw/rahavard/quality2/):
    /api/v2/fundamental/company-financial-ratios   نسبت‌های مالی (ROE، ROA، حاشیه، بدهی، نقدینگی، …)
    /api/v2/fundamental/company-profit-losses      صورت سود و زیان
    /api/v2/fundamental/company-balance-sheets     ترازنامه
    /api/v2/asset/<id>/eps                         EPS و DPS با تاریخ واقعی اعلام هر دوره (برای «زمان دانستن» داده)
    /api/v2/asset/<id>/header                      نماد و نوع دارایی (برای نگاشت نماد ← شناسهٔ رهاورد)

نگاشت نماد ← asset_id: فهرست نقطهٔ جست‌وجوی رهاورد معلوم نیست (marketscreener نیاز به ورود دارد)؛ پس
  (۱) چند آدرس جست‌وجوی محتمل با نماد «فملی» (باید شناسهٔ ۴۵۱ بدهد) آزموده می‌شود؛
  (۲) در نبود آن، شناسه‌ها پیمایش می‌شوند (header هر شناسه؛ فقط نوع «سهام» ذخیره می‌شود) و نگاشت در data/fundamentals/rahavard_asset_ids.csv می‌ماند
      (قابل‌ادامه؛ فقط یک بار لازم است).

    pip install requests playwright
    python tools/fetch_rahavard_fundamentals.py --test                  # یک نماد (فملی) را کامل می‌گیرد و حالت اتصال را گزارش می‌کند
    python tools/fetch_rahavard_fundamentals.py --resolve --log r.txt   # نگاشت نماد ← شناسه
    python tools/fetch_rahavard_fundamentals.py --log f.txt             # دریافت همهٔ نمادها (قابل‌ادامه)
    --browser   اتصال از راه Chrome واقعی (اگر requests ساده 403/خالی گرفت؛ خودکار هم به آن برمی‌گردد)

خروجی (قابل push):
    data/fundamentals/rahavard_asset_ids.csv   asset_id, trade_symbol, name, category
    data/fundamentals/rahavard_long.csv        ins_code, symbol, asset_id, stmt(ratio|pl|bs), row, fy, statement_date, audited, represented, value
    data/fundamentals/rahavard_eps.csv         ins_code, symbol, asset_id, fy, kind, period, date, audited, eps, dps
    data/fundamentals/rahavard_fail.csv        نمادهای ناموفق
"""
import argparse
import csv
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = "https://rahavard365.com"
OUT = ROOT / "data" / "fundamentals"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "application/json, text/plain, */*", "Accept-Language": "fa-IR,fa;q=0.9,en;q=0.8", "Referer": BASE + "/"}
STMT = {"ratio": "company-financial-ratios", "pl": "company-profit-losses", "bs": "company-balance-sheets"}
Q = ("report_type_id=1&view_currency_id=1&view_type_id=1&combination_state_id=2&audit_state_id=2&representation_state_id=2"
     "&start_date={start}T00:00:00.000Z&end_date={end}T00:00:00.000Z&fiscal_year_order=ASC&font_type=FA&detail_state={detail}"
     "&ratio_category_ids=1,2,3,4&sale_type_ids=4&detail_type_id=1&no_change_in_view_type=true")
SEARCH = ["/api/v2/search?query={q}", "/api/v2/search?q={q}", "/api/v2/search/assets?query={q}", "/api/v2/asset/search?query={q}",
          "/api/v2/search/global?query={q}", "/api/v2/search/autocomplete?query={q}", "/api/v2/assets/search?query={q}",
          "/api/v2/search/suggest?query={q}", "/api/v2/asset?search={q}", "/api/v2/asset?query={q}"]
RATIO_KEEP = ("ROE", "ROA", "سود خالص به فروش", "حاشیه سود عملیاتی", "نسبت بدهی", "نسبت جاری", "نسبت آنی", "نسبت مالکانه", "نسبت پوشش بدهی",
              "گردش مجموع دارایی")


def norm(s: str) -> str:
    return re.sub(r"[‌‏‎\s]+", "", (s or "")).replace("ي", "ی").replace("ك", "ک")


# ── اتصال ─────────────────────────────────────────────────────────────────────────
class Http:
    def __init__(self, browser: bool):
        self.mode = "browser" if browser else "requests"
        self.last = ""
        self.nav = False          # True: جدول نسبت‌ها را از پاسخ خود صفحهٔ سایت می‌گیریم (fetch مستقیم 403 می‌گیرد)
        self.pw = self.page = None
        if self.mode == "requests":
            import requests
            self.s = requests.Session()
            self.s.headers.update(HEADERS)
        else:
            self._open()

    def _open(self):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        try:
            br = self.pw.chromium.launch(channel="chrome", headless=False)
        except Exception:  # noqa: BLE001
            br = self.pw.chromium.launch(headless=False)
        self.page = br.new_context(locale="fa-IR").new_page()
        self.page.goto(BASE + "/", wait_until="domcontentloaded", timeout=60000)
        self.page.wait_for_timeout(6000)

    def get(self, path: str):
        """(status, json|None)"""
        if self.mode == "requests":
            try:
                r = self.s.get(BASE + path, timeout=60)
                self.last = r.text[:160]
                return r.status_code, (r.json() if r.status_code == 200 and "json" in r.headers.get("content-type", "") else None)
            except Exception as e:  # noqa: BLE001
                return 0, None
        res = self.page.evaluate("""async (u) => { try { const r = await fetch(u, {credentials: 'include', headers: {'Accept': 'application/json'}});
            const t = await r.text(); return [r.status, t]; } catch (e) { return [0, '']; } }""", BASE + path)
        self.last = res[1][:160]
        try:
            return res[0], (json.loads(res[1]) if res[0] == 200 else None)
        except Exception:  # noqa: BLE001
            return res[0], None

    def get_many(self, paths: list):
        if self.mode == "requests":
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(6) as ex:
                return list(ex.map(self.get, paths))
        res = self.page.evaluate("""async (us) => Promise.all(us.map(async u => { try { const r = await fetch(u, {credentials: 'include', headers: {'Accept': 'application/json'}});
            return [r.status, await r.text()]; } catch (e) { return [0, '']; } }))""", [BASE + p for p in paths])
        out = []
        for st, t in res:
            try:
                out.append((st, json.loads(t) if st == 200 else None))
            except Exception:  # noqa: BLE001
                out.append((st, None))
        return out


def connect(force_browser: bool) -> Http:
    h = Http(force_browser)
    st, j = h.get("/api/v2/asset/451/header")
    if st == 200 and j and (j.get("data", {}).get("asset", {}) or {}).get("trade_symbol"):
        print(f"اتصال: {h.mode} ✓ (فملی = {j['data']['asset']['trade_symbol']})")
        return h
    print(f"اتصال {h.mode} ناموفق (وضعیت {st})", end="")
    if h.mode == "requests":
        print(" ← می‌روم سراغ Chrome")
        return connect(True)
    sys.exit("\nاتصال با Chrome هم ناموفق بود؛ اینترنت/فیلترشکن را بررسی کنید.")


# ── تجزیه ────────────────────────────────────────────────────────────────────────
def leaves(cols, path=()):
    for c in cols or []:
        p = path + (c.get("header_name"),)
        if c.get("children"):
            yield from leaves(c["children"], p)
        elif c.get("field") and c["field"] != "row_title":
            yield p, c["field"]


def parse_table(j, stmt: str):
    """ردیف‌های بلند [(row, fy, statement_date, audited, represented, value)] از پاسخ ratios/pl/bs."""
    d = (j or {}).get("data") or {}
    cols = d.get("column_definitions")
    if not cols:
        return []
    fmap = {}
    for p, f in leaves(cols):
        p = [x for x in p if x is not None]
        if len(p) >= 6 and re.match(r"1[34]\d\d/\d+/\d+", str(p[0])):
            fmap[f] = (p[0], p[1], p[3] == "✔️", p[4] == "✔️", p[5])      # سال مالی، نوع گزارش، حسابرسی‌شده، تجدیدارائه، تاریخ
    out = []
    for row in d.get("row_data") or []:
        t = row.get("row_title")
        t = t.get("title") if isinstance(t, dict) else t
        prop = row.get("row_properties") or {}
        if not t:
            continue
        if stmt == "ratio":
            if not any(k in t for k in RATIO_KEEP):
                continue
        elif not (prop.get("is_parent") or "EPS" in t):
            continue
        for f, (fy, rt, aud, rep, sd) in fmap.items():
            v = row.get(f)
            if isinstance(v, (int, float)) and "سالانه" in str(rt):
                out.append((t, fy, sd, int(aud), int(rep), v))
    return out


def parse_eps(j):
    out = []
    for fy in ((j or {}).get("data") or {}).get("eps_fiscal_years") or []:
        for e in fy.get("epses") or []:
            out.append((fy["fiscal_year"][:10], e.get("announcement_type"), e.get("fiscal_period"), e["date_time"][:10], int(bool(e.get("is_audited"))),
                        e.get("pure_realized_eps"), e.get("pure_dps")))
    return out


# ── نگاشت نماد ← شناسه ───────────────────────────────────────────────────────────────
def load_ids() -> dict:
    f = OUT / "rahavard_asset_ids.csv"
    if not f.exists():
        return {}
    with f.open(encoding="utf-8") as fh:
        return {norm(r["trade_symbol"]): r for r in csv.DictReader(fh)}


def find_ids(obj, out):
    if isinstance(obj, dict):
        if obj.get("id") and (obj.get("trade_symbol") or obj.get("symbol")):
            out.append((str(obj["id"]), obj.get("trade_symbol") or obj.get("symbol")))
        for v in obj.values():
            find_ids(v, out)
    elif isinstance(obj, list):
        for v in obj:
            find_ids(v, out)


def try_search(h: Http):
    """آدرس جست‌وجویی که برای «فملی» شناسهٔ ۴۵۱ بدهد."""
    for tpl in SEARCH:
        st, j = h.get(tpl.format(q="%D9%81%D9%85%D9%84%D9%8C"))
        hits = []
        find_ids(j, hits)
        ok = any(i == "451" for i, _ in hits)
        print(f"  جست‌وجو {tpl}: {st} {'✓' if ok else ''}")
        if ok:
            return tpl
    return None


def resolve_by_search(h: Http, tpl: str, gap: float):
    from urllib.parse import quote
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / "rahavard_asset_ids.csv"
    rows, miss = {}, []
    for code, sym in universe():
        st, j = h.get(tpl.format(q=quote(sym)))
        hits = []
        find_ids(j, hits)
        m = [i for i, s in hits if norm(s) == norm(sym)]
        if m:
            rows[norm(sym)] = (m[0], sym)
        else:
            miss.append(sym)
        time.sleep(gap)
    with f.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["asset_id", "trade_symbol", "name", "category", "scanned_to"])
        for aid, sym in rows.values():
            w.writerow([aid, sym, "", "", ""])
    print(f"نگاشت با جست‌وجو: {len(rows)} نماد، بی‌نگاشت {len(miss)}: {'؛ '.join(miss[:20])} ← {f}")
    return miss


def resolve(h: Http, lo: int, hi: int, gap: float):
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / "rahavard_asset_ids.csv"
    have = set()
    if f.exists():
        with f.open(encoding="utf-8") as fh:
            have = {int(r["scanned_to"]) for r in csv.DictReader(fh) if r.get("scanned_to")}
    new = not f.exists()
    fh = f.open("a", newline="", encoding="utf-8")
    w = csv.writer(fh)
    if new:
        w.writerow(["asset_id", "trade_symbol", "name", "category", "scanned_to"])
    start = max([lo] + [x + 1 for x in have])
    step, n = 12, 0
    for a in range(start, hi + 1, step):
        ids = list(range(a, min(a + step, hi + 1)))
        res = h.get_many([f"/api/v2/asset/{i}/header" for i in ids])
        for i, (st, j) in zip(ids, res):
            asset = ((j or {}).get("data") or {}).get("asset")
            if asset and str(asset.get("type_id")) == "1" and asset.get("trade_symbol"):
                w.writerow([i, asset["trade_symbol"], asset.get("name", ""), (asset.get("category") or {}).get("name", ""), ""])
                n += 1
        w.writerow(["", "", "", "", ids[-1]])               # علامت پیشرفت (برای ادامه)
        fh.flush()
        if (a - start) % (step * 25) == 0:
            print(f"  پیمایش شناسه‌ها تا {ids[-1]} — {n} سهم تازه")
        time.sleep(gap)
    fh.close()
    print(f"نگاشت: {n} سهم ← {f}")


# ── دریافت ─────────────────────────────────────────────────────────────────────────
def universe():
    with (ROOT / "data" / "index_constituents.csv").open(encoding="utf-8") as fh:
        seen, out = set(), []
        for r in csv.DictReader(fh):
            if r["ins_code"] not in seen:
                seen.add(r["ins_code"])
                out.append((r["ins_code"], r["symbol"]))
    return out


def fetch_asset(h: Http, aid: str, start: str = "2011-03-21"):
    """(داده|None، وضعیت‌های چهار درخواست، بدنهٔ خطا)"""
    end = date.today().isoformat()
    paths = [f"/api/v2/fundamental/{STMT['ratio']}?asset_id={aid}&" + Q.format(start=start, end=end, detail="detailed"),
             f"/api/v2/fundamental/{STMT['pl']}?asset_id={aid}&" + Q.format(start=start, end=end, detail="summary"),
             f"/api/v2/fundamental/{STMT['bs']}?asset_id={aid}&" + Q.format(start=start, end=end, detail="summary"),
             f"/api/v2/asset/{aid}/eps"]
    res = h.get_many(paths)
    sts = [st for st, _ in res]
    if any(st != 200 for st in sts):
        bad = next(p for p, (st, _) in zip(paths, res) if st != 200)
        _, _ = h.get(bad)                                   # دوباره برای دیدن بدنهٔ خطا
        return None, sts, h.last
    return {"ratio": parse_table(res[0][1], "ratio"), "pl": parse_table(res[1][1], "pl"), "bs": parse_table(res[2][1], "bs"), "eps": parse_eps(res[3][1])}, sts, ""


def nav_ratios(h: Http, aid: str):
    """پاسخ company-financial-ratios را همان‌طور که خود صفحهٔ سایت می‌گیرد ضبط می‌کند (توکن/هدرهای SPA را خودش دارد)."""
    try:
        with h.page.expect_response(lambda r: "company-financial-ratios" in r.url and r.request.method == "GET", timeout=45000) as ri:
            h.page.goto(f"{BASE}/asset/{aid}/financialratios", wait_until="domcontentloaded", timeout=60000)
        r = ri.value
        return r.status, (r.json() if r.status == 200 else None)
    except Exception as e:  # noqa: BLE001
        return 0, None


def fetch_nav(h: Http, aid: str, diag: list):
    st, j = nav_ratios(h, aid)
    st_e, je = h.get(f"/api/v2/asset/{aid}/eps")
    if st != 200 or st_e != 200:
        diag.append(f"nav: ratios {st} eps {st_e}")
        return None
    return {"ratio": parse_table(j, "ratio"), "pl": [], "bs": [], "eps": parse_eps(je)}


def fetch_robust(h: Http, aid: str, diag: list):
    """چند راهبرد: (۱) fetch با بازهٔ بلند ← (۲) بازهٔ ۵ ساله مثل سایت ← (۳) در 403 سوییچ به Chrome و fetch ← (۴) ضبط پاسخ خود صفحه.
    (h, داده) برمی‌گرداند؛ h ممکن است عوض شده باشد."""
    five = date(date.today().year - 5, date.today().month, 1).isoformat()
    if not h.nav:
        for start in ("2011-03-21", five):
            d, sts, body = fetch_asset(h, aid, start)
            if d is not None:
                return h, d
            diag.append(f"{h.mode} start={start} وضعیت‌ها {sts} {body!r}")
            if not any(x in (401, 403, 0) for x in sts[:3]):
                break
        if h.mode == "requests":
            print("  requests رد شد ← Chrome")
            h = Http(True)
            for start in ("2011-03-21", five):
                d, sts, body = fetch_asset(h, aid, start)
                if d is not None:
                    return h, d
                diag.append(f"browser start={start} وضعیت‌ها {sts} {body!r}")
                if not any(x in (401, 403, 0) for x in sts[:3]):
                    break
        print("  fetch مستقیم رد شد ← ضبط پاسخ خود صفحه (کندتر: جدول سه‌گانهٔ نسبت‌ها فقط؛ ترازنامه/سود‌وزیان لازم نیست)")
        h.nav = True
    return h, fetch_nav(h, aid, diag)


def run(h: Http, only: str, n: int, gap: float):
    ids = load_ids()
    if not ids:
        sys.exit("ابتدا:  python tools/fetch_rahavard_fundamentals.py --resolve")
    OUT.mkdir(parents=True, exist_ok=True)
    fl, fe, ff = OUT / "rahavard_long.csv", OUT / "rahavard_eps.csv", OUT / "rahavard_fail.csv"
    done = set()
    if fl.exists():
        with fl.open(encoding="utf-8") as fh:
            done = {r["ins_code"] for r in csv.DictReader(fh)}
    new = not fl.exists()
    L, E, F = (open(p, "a", newline="", encoding="utf-8") for p in (fl, fe, ff))
    wl, we, wf = csv.writer(L), csv.writer(E), csv.writer(F)
    if new:
        wl.writerow(["ins_code", "symbol", "asset_id", "stmt", "row", "fy", "statement_date", "audited", "represented", "value"])
        we.writerow(["ins_code", "symbol", "asset_id", "fy", "kind", "period", "date", "audited", "eps", "dps"])
        wf.writerow(["ins_code", "symbol", "why"])
    todo = [(c, s) for c, s in universe() if c not in done and (not only or norm(s) == norm(only))]
    if n:
        todo = todo[:n]
    print(f"{len(todo)} نماد برای دریافت ({len(done)} قبلاً)")
    ok = miss = 0
    for k, (code, sym) in enumerate(todo, 1):
        row = ids.get(norm(sym))
        if not row:
            wf.writerow([code, sym, "نگاشت شناسه نیست"]); miss += 1; continue
        diag = []
        h, d = fetch_robust(h, row["asset_id"], diag)
        if d is None:
            if miss < 6:
                print(f"  ✖ {sym} (asset {row['asset_id']}):", " | ".join(diag))
            wf.writerow([code, sym, "پاسخ ناموفق"]); miss += 1; continue
        for stmt in ("ratio", "pl", "bs"):
            for t, fy, sd, aud, rep, v in d[stmt]:
                wl.writerow([code, sym, row["asset_id"], stmt, t, fy, sd, aud, rep, v])
        for e in d["eps"]:
            we.writerow([code, sym, row["asset_id"], *e])
        if not d["ratio"] and not d["pl"]:
            wf.writerow([code, sym, "جدول خالی"])
        wl.writerow([code, sym, row["asset_id"], "mark", "", "", "", "", "", ""])        # علامت انجام‌شدن نماد (حتی اگر خالی باشد)
        ok += 1
        if k % 10 == 0:
            print(f"  [{k}/{len(todo)}] {sym}: ratio {len(d['ratio'])} pl {len(d['pl'])} bs {len(d['bs'])} eps {len(d['eps'])}")
            for fh in (L, E, F):
                fh.flush()
        time.sleep(gap)
    for fh in (L, E, F):
        fh.close()
    print(f"تمام: {ok} نماد گرفته شد، {miss} ناموفق/بی‌نگاشت ← {OUT}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--test", action="store_true", help="فقط فملی (۴۵۱) را بگیر و خلاصه چاپ کن")
    ap.add_argument("--resolve", action="store_true", help="نگاشت نماد ← شناسه (جست‌وجو یا پیمایش شناسه‌ها)")
    ap.add_argument("--id-from", type=int, default=1)
    ap.add_argument("--id-to", type=int, default=8000)
    ap.add_argument("--browser", action="store_true", help="اتصال با Chrome واقعی")
    ap.add_argument("--symbol", help="فقط یک نماد")
    ap.add_argument("--n", type=int, default=0, help="حداکثر تعداد نماد")
    ap.add_argument("--gap", type=float, default=0.6)
    ap.add_argument("--log", help="کپی خروجی در فایل UTF-8")
    a = ap.parse_args()
    if a.log:
        sys.path.insert(0, str(ROOT / "tools"))
        import fetch_dividend_payments as fdp
        sys.stdout = fdp.Tee(a.log)
    h = connect(a.browser)
    if a.test:
        diag = []
        h, d = fetch_robust(h, "451", diag)
        if not d:
            sys.exit("دریافت فملی ناموفق: " + " | ".join(diag))
        print({k: len(v) for k, v in d.items()})
        for t, fy, sd, aud, rep, v in d["ratio"][:8]:
            print("  ", t, fy, sd, aud, rep, round(v, 2))
        print("EPS:", d["eps"][:3])
        return 0
    if a.resolve:
        tpl = try_search(h)
        print("آدرس جست‌وجوی کارا:", tpl or "ندارد ← پیمایش شناسه‌ها")
        if tpl and not resolve_by_search(h, tpl, a.gap):
            return 0
        resolve(h, a.id_from, a.id_to, a.gap)
        return 0
    run(h, a.symbol, a.n, a.gap)
    return 0


if __name__ == "__main__":
    sys.exit(main())
