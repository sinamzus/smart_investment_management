#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""سند پروژه برای راهنمای درون‌برنامه → ui/data/docs.js (window.SIM_DOCS).

    python tools/build_ui_docs.py            # بساز
    python tools/build_ui_docs.py --check    # فقط بسنج که ui/data/docs.js با docs/*.md یکی است (کد خروج ۱ اگر کهنه است)

رابط به‌صورت فایل ایستا (file://) باز می‌شود و مرورگر اجازهٔ خواندن مستقیم docs/*.md را نمی‌دهد؛ پس متن فصل‌ها
بی‌تغییر در یک فایل JS بسته‌بندی می‌شود و ui/docs.js آن را فقط وقتی کاربر «راهنما» را باز کند بار می‌کند (فصل ۱۲ §۱۲٫۸).
هر بار سندی عوض شد این را هم اجرا کنید؛ tests/test_ui_docs.py کهنه‌بودن را می‌گیرد.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ui" / "data" / "docs.js"
CRLF, LF = chr(13) + chr(10), chr(10)


def read(p):
    """پایان سطر یکسان (LF) تا hash به تبدیل CRLF/LF گیت وابسته نباشد."""
    return p.read_text(encoding="utf-8").replace(CRLF, LF)


def title_of(md, default):
    return next((ln.lstrip("# ").strip() for ln in md.splitlines() if ln.startswith("# ")), default)


def collect():
    files = []
    for p in sorted((ROOT / "docs").glob("[0-9][0-9]-*.md")):
        md = read(p)
        files.append({"n": int(p.name[:2]), "file": p.name, "title": title_of(md, p.stem), "md": md})
    for name, key in (("README.md", "readme"), ("CHANGELOG.md", "changelog")):
        p = ROOT / "docs" / name
        if p.exists():
            md = read(p)
            files.append({"n": key, "file": name, "title": title_of(md, name), "md": md})
    return files


def render(files):
    h = hashlib.sha256("".join(f["md"] for f in files).encode("utf-8")).hexdigest()[:16]
    body = json.dumps({"hash": h, "files": files}, ensure_ascii=False, separators=(",", ":"))
    return h, "/* ساخته‌شده با tools/build_ui_docs.py — دستی ویرایش نکنید */\nwindow.SIM_DOCS = " + body + ";\n"


def main():
    files = collect()
    h, js = render(files)
    if "--check" in sys.argv:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        m = re.search(r'"hash":"([0-9a-f]+)"', cur)
        ok = bool(m) and m.group(1) == h
        print("docs.js به‌روز است" if ok else "docs.js کهنه است: python tools/build_ui_docs.py")
        sys.exit(0 if ok else 1)
    OUT.write_text(js, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(files)} سند، {len(js) / 1e3:.0f} KB، hash {h}")


if __name__ == "__main__":
    main()
