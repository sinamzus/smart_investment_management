#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""شبکهٔ پژوهش و دادهٔ «میز پژوهش» (Lab): ui/data/lab.js = window.SIM_LAB؛ فصل ۱۴ بخش ۱۴.۸.

    python tools/build_lab.py              # اجرای کامل (≈ ۳۰–۶۰ دقیقه؛ ذخیرهٔ میانی در data/derived/cache)
    python tools/build_lab.py --export     # فقط خروجی UI از نتایج ذخیره‌شده

مراحل: (۱) ماتریس معیارها (signals.py) ← (۲) جدول IC/FM همهٔ معیارها ← (۳) دهک‌های هر معیار ← (۴) شبکهٔ استراتژی‌ها (تک‌معیار، الگوریتم‌ها، ترکیب‌ها، حساسیت‌ها)
← (۵) آزمون‌های سخت (Bonferroni، DSR، PBO، Reality Check/SPA) ← (۶) خروجی.
"""
import base64
import hashlib
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import attribution as at  # noqa: E402
import build_ui_extra as bx  # noqa: E402
import construction as cn  # noqa: E402
import factor_engine as fe  # noqa: E402
import research_stats as rs  # noqa: E402
import signals as sg  # noqa: E402

CACHE = ROOT / "data" / "derived" / "cache"
OUT_JS = ROOT / "ui" / "data" / "lab.js"
OUT_JSON = ROOT / "data" / "research" / "lab_results.json"
COST = 125.0                                     # رفت‌وبرگشت؛ کارمزد خرید + فروش + مالیات فروش ≈ ۱٫۲۵٪ [تأیید لازم] (فصل ۶ §۶٫۱)
REP = {"momentum": "mom_12_1", "risk": "vol_252", "liquidity": "size", "yield": "div_yield", "quality": "q_roe", "value": "ep"}


def store_signature(mk: sg.Market) -> str:
    """امضای حافظهٔ میانی: تاریخ‌ها، نمادها و کد معیارها. هر تغییری در داده یا signals.py کش را باطل می‌کند
    (وگرنه idx به روزهای قدیمی اشاره می‌کرد و دستور اجرای زنده با ماتریس ناهم‌تراز ساخته می‌شد)."""
    h = hashlib.sha256()
    h.update(f"{mk.n}|{mk.k}|{mk.dates[0].date()}|{mk.dates[-1].date()}|".encode())
    h.update("|".join(map(str, mk.cols)).encode())
    h.update((ROOT / "tools" / "signals.py").read_bytes())
    fund_files = [ROOT / "data/fundamentals" / x for x in ("rahavard_long.csv", "rahavard_eps.csv", "codal_long.csv", "codal_letters.csv")]
    h.update("|".join(f"{p.name}:{p.stat().st_size}:{int(p.stat().st_mtime)}" if p.exists() else p.name for p in fund_files).encode())
    return h.hexdigest()[:16]


def get_lab():
    _, info, Ra = bx.base_panel(bx.ALL_MARKETS)
    Ra = bx.operating_view(Ra)                      # بدون صندوق/گواهی/امتیاز تسهیلات (فصل ۲ §۲٫۰)
    mk = sg.Market(Ra, info)
    mk.fund = sg.load_fund(mk.cols, mk.dates)
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / "signals_store.npz"
    sig = store_signature(mk)
    S = None
    if f.exists():
        z = np.load(f, allow_pickle=True)
        if "sig" in z.files and str(z["sig"]) == sig:
            idx, names = [int(a) for a in z["idx"]], list(z["names"])
            S = {n: z["S_" + n] for n in names}
            print(f"ماتریس معیارها از حافظهٔ میانی: {len(S)} معیار (امضا {sig})")
        else:
            print("حافظهٔ میانی معیارها با دادهٔ فعلی نمی‌خواند (داده یا signals.py عوض شده)؛ دوباره ساخته می‌شود")
    if S is None:
        idx, S = sg.compute_store(mk, verbose=False)
        np.savez_compressed(f, idx=np.array(idx), names=np.array(list(S)), sig=np.array(sig), **{"S_" + n: v for n, v in S.items()})
    return mk, cn.Lab(mk, idx, S), info


def spec_sig(name, **kw):
    return {"signals": [[name, 1.0]], "combine": "equal", "neutral": True, "algo": "topfrac", "params": {"entry": 0.2, "exit": 0.3}, **kw}


def grid(S):
    G = []
    for n in S:                                         # الف) تک‌معیار
        G.append((f"sig:{n}", "sig", sg.REG[n]["fa"], spec_sig(n)))
    for tag, nm, sigs in (("mom", "مرجع Factor Lab: مومنتوم ۱۲−۱ (پنجک ۵، بدون بافر)", [["mom_12_1", 1.0]]), ("lowvol", "مرجع Factor Lab: کم‌نوسان ۲۵۲ روزه (پنجک ۵، بدون بافر)", [["vol_252", 1.0]]),
                          ("quality", "کیفیت (ROE + اهرم پایین)، پنجک ۵ بدون بافر", [["q_roe", 1.0], ["q_low_de", 1.0]])):
        if all(n in S for n, _ in sigs):
            G.append((f"ref:{tag}", "ref", nm, {"signals": sigs, "combine": "equal", "neutral": False, "algo": "topfrac", "params": {"entry": 0.2, "exit": 0.2}}))
    refs = {"vol_252": "کم‌نوسان", "q_roe": "ROE", "size": "اندازهٔ کوچک"}
    algos = [("topfrac", {"entry": 0.2, "exit": 0.3}), ("topn", {"N": 50, "buffer": 25}), ("score_tilt", {"lam": 1.0}), ("rank_weight", {}),
             ("msci_tilt", {}), ("inv_vol", {"entry": 0.3, "exit": 0.4}), ("min_var", {"entry": 0.4, "exit": 0.5, "max_w": 0.05}),
             ("erc", {"entry": 0.4, "exit": 0.5}), ("hrp", {"entry": 0.4, "exit": 0.5}), ("max_div", {"entry": 0.4, "exit": 0.5}),
             ("mvo_te", {})]
    for r_, lab_ in refs.items():                       # ب) الگوریتم‌ها
        if r_ not in S:
            continue
        for a, p in algos:
            G.append((f"algo:{r_}:{a}", "algo", f"{lab_} · {cn.ALGOS[a]['fa']}",
                      {"signals": [[r_, 1.0]], "combine": "equal", "neutral": True, "algo": a, "params": p, "max_w": 0.06 if a in ("score_tilt", "rank_weight", "msci_tilt") else None}))
    base = [REP["risk"], REP["liquidity"], REP["yield"]]
    c1 = [[n, 1.0] for n in base if n in S]
    c2 = c1 + [[REP["momentum"], 1.0]]
    c3 = c2 + [[REP["quality"], 1.0]]
    c4 = [[n, 1.0] for n in (REP["risk"], REP["liquidity"], REP["yield"], REP["quality"], REP["value"]) if n in S]
    for tag, lab_, sigs in (("c1", "کم‌نوسان+اندازه+سود", c1), ("c2", "+مومنتوم", c2), ("c3", "+ROE", c3), ("c4", "ریسک+اندازه+سود+ROE+E/P", c4)):
        for m in ("equal", "rank", "ic", "icir", "fm", "ridge"):
            G.append((f"combo:{tag}:{m}", "combo", f"{lab_} · {m}", {"signals": sigs, "combine": m, "neutral": True, "algo": "topfrac", "params": {"entry": 0.2, "exit": 0.3}}))
    cand = [n for n in S if sg.REG[n]["needs"] != "fund"]
    for k in (3, 5, 8):                                 # انتخاب پویای معیار (meta-selection)
        G.append((f"meta:topk{k}", "combo", f"انتخاب پویای {k} معیار برتر ICIR (همهٔ معیارهای قیمتی)",
                  {"signals": [[n, 1.0] for n in cand], "combine": "topk_icir", "topk": k, "neutral": True, "algo": "topfrac", "params": {"entry": 0.2, "exit": 0.3}}))
    # ج) حساسیت: تأخیر اجرا، جهان، بافر، ریبالانس جزئی، فصلی
    ref = {"signals": c1, "combine": "equal", "neutral": True, "algo": "topfrac", "params": {"entry": 0.2, "exit": 0.3}}
    G.append(("sens:delay1", "sens", "ترکیب c1 · تأخیر اجرا ۱ روز", {**ref, "delay": 1}))
    G.append(("sens:bourse", "sens", "ترکیب c1 · فقط بورس", {**ref, "universe": {"markets": ["bourse"]}}))
    G.append(("sens:nobuffer", "sens", "ترکیب c1 · بدون بافر", {**ref, "params": {"entry": 0.2, "exit": 0.2}}))
    G.append(("sens:widebuffer", "sens", "ترکیب c1 · بافر پهن (۲۰/۴۰)", {**ref, "params": {"entry": 0.2, "exit": 0.4}}))
    G.append(("sens:partial50", "sens", "ترکیب c1 · ریبالانس جزئی ۵۰٪", {**ref, "partial": 0.5}))
    G.append(("sens:quarterly", "sens", "ترکیب c1 · فصلی", {**ref, "rebalance_every": 3}))
    G.append(("sens:adv", "sens", "ترکیب c1 · حداقل ارزش معاملات ۵۰۰ میلیون ریال", {**ref, "universe": {"min_adv": 5e8}}))
    G.append(("sens:no_neutral", "sens", "ترکیب c1 · بدون خنثی‌سازی صنعتی", {**ref, "neutral": False}))
    return G


def run_all(lab: cn.Lab, S):
    t0 = time.time()
    R = {}
    # دهک‌ها برای هر معیار (خام، بدون خنثی‌سازی) و برای هر ترکیب
    print("دهک‌ها…")
    dec = {}
    for n in S:
        d = {}
        for k in range(1, 11):
            res = cn.backtest(lab, {"signals": [[n, 1.0]], "neutral": False, "algo": "quantile", "params": {"G": 10, "k": k}}, live=False)
            d[k] = res
        if len(d[1]["ret"]["S"]) < 24:                  # پوشش ناکافی (مثلاً ثبات ROE: ۱ نماد)
            print(f"  {n}: کمتر از ۲۴ ماه ← کنار رفت")
            continue
        dec[n] = d
    R["dec"] = {n: {"ann_net": [fe.ann(fe.net(d[k]["ret"]["S"], d[k]["to"]["S"], COST)) for k in range(1, 11)],
                    "ann_gross": [fe.ann(d[k]["ret"]["S"]) for k in range(1, 11)],
                    "spread_t": fe.nw_t(fe.net(d[10]["ret"]["S"], d[10]["to"]["S"], COST) - fe.net(d[1]["ret"]["S"], d[1]["to"]["S"], COST)),
                    "n_months": int(len(d[1]["ret"]["S"]))} for n, d in dec.items()}
    print(f"  دهک‌ها {time.time() - t0:.0f}s")
    S = {n: v for n, v in S.items() if n in dec}
    G = grid(S)
    runs = {}
    for i, (rid, grp, name, spec) in enumerate(G):
        t1 = time.time()
        try:
            res = cn.backtest(lab, spec, live=True)
        except Exception as e:  # noqa: BLE001
            print(f"  خطا {rid}: {type(e).__name__} {e}")
            continue
        if len(res["ret"]["S"]) < 24:
            continue
        runs[rid] = {"id": rid, "group": grp, "name": name, "spec": spec, "res": res}
        if (i + 1) % 10 == 0 or time.time() - t1 > 10:
            print(f"  [{i + 1}/{len(G)}] {rid} ({time.time() - t1:.1f}s) کل {time.time() - t0:.0f}s")
    R["runs"] = runs
    return R


def decile_table(lab, spec, cost):
    """دهک‌های امتیاز ترکیبی همین استراتژی (همان معیارها/ترکیب/خنثی‌سازی/جهان؛ الگوریتم quantile با G=۱۰، هم‌وزن درون دهک):
    بازده خالص سالانهٔ هر دهک، اسپیرمن رتبهٔ دهک با بازده، t اختلاف دهک ۱۰ − ۱. برای حکم «استقرار» لازم است (فصل ۱۴ §۱۴٫۷٫۶).
    پیش از این فقط تک‌معیارها دهک داشتند و ترکیب‌ها/الگوریتم‌ها ساختاراً نمی‌توانستند «استقرار» بگیرند."""
    ann, first, last = [], None, None
    for k in range(1, 11):
        q = {"signals": spec["signals"], "combine": spec.get("combine", "equal"), "neutral": spec.get("neutral", True), "topk": spec.get("topk", 5),
             "universe": spec.get("universe", {}), "algo": "quantile", "params": {"G": 10, "k": k}}
        res = cn.backtest(lab, q, live=False)
        if len(res["ret"]["S"]) < 24:
            return None
        net = fe.net(res["ret"]["S"], res["to"]["S"], cost)
        ann.append(fe.ann(net))
        first, last = (net if k == 1 else first), (net if k == 10 else last)
    sp = fe._spearman(np.arange(10), ann)
    return {"ann_net": ann, "spearman": float(sp) if sp == sp else np.nan, "spread_t": fe.nw_t(last - first), "n_months": int(len(first))}


def finalize(lab, S, R):
    """آمار خالص، حکم، DSR، PBO، RC/SPA؛ ورودی R از run_all."""
    runs = R["runs"]
    cost_of = lambda r: float(r["spec"].get("cost_bp", COST))          # noqa: E731  هزینهٔ مشخصات (پیش‌فرض کتابخانه COST)
    t0 = time.time()
    for i, (rid, r) in enumerate(runs.items()):                        # دهک‌های امتیاز ترکیبی برای همهٔ اجراها (تک‌معیار از R["dec"] می‌آید)
        if rid.startswith("sig:"):
            d = R["dec"].get(rid.split(":")[1])
            r["dec"] = {"ann_net": d["ann_net"], "spearman": float(pd.Series(d["ann_net"]).corr(pd.Series(range(10)), method="spearman")), "spread_t": d["spread_t"], "n_months": d["n_months"]} if d else None
        elif "dec" not in r:
            r["dec"] = decile_table(lab, r["spec"], cost_of(r))
            if (i + 1) % 20 == 0:
                print(f"  دهک‌های ترکیب‌ها [{i + 1}/{len(runs)}] {time.time() - t0:.0f}s")
    # دهک‌های ترکیب‌ها برای حکم
    for rid, r in runs.items():
        res, c = r["res"], cost_of(r)
        r["stats"] = fe.stats_of(res, "S", c)
        sc = fe.stats_of(res, "S", c, bench="CAP")                         # مرجع دوم: ارزش‌وزن واجدان
        r["stats"].update({"excess_net_cap": sc["excess_net"], "t_net_cap": sc["t_net"], "ir_cap": sc["ir"], "ann_cap_net": sc["ann_all_net"],
                           "t_h1_cap": sc["t_h1"], "t_h2_cap": sc["t_h2"], "ex_h1_cap": sc["ex_h1"], "ex_h2_cap": sc["ex_h2"],
                           "frozen_w": float(np.nanmean(res["frozen"])) if len(res.get("frozen", [])) else 0.0})   # سهم وزن غیرقابل‌فروش در روز اجرا (A2)
        rn = fe.net(res["ret"]["S"], res["to"]["S"], c)
        an = fe.net(res["ret"]["ALL"], res["to"]["ALL"], c)
        r["capacity"] = {str(int(a_)): fe.ann(rn - np.nan_to_num(imp)) - fe.ann(an) for a_, imp in res["impact"].items()}   # برتری خالص پس از اثر بازار
        r["ic"] = fe.ic_stats({"ic": res["ic"]})
    # آزمون‌های چندگانه
    sr_list, ids, D = [], [], {}
    for rid, r in runs.items():
        res, c = r["res"], cost_of(r)
        ex = fe.net(res["ret"]["S"], res["to"]["S"], c) - fe.net(res["ret"]["ALL"], res["to"]["ALL"], c)
        D[rid] = pd.Series(ex, index=pd.DatetimeIndex(res["sig_date"]))      # کلید = روز سیگنال (در برابر تأخیر اجرا ثابت)
        sr_list.append(float(np.mean(ex) / np.std(ex, ddof=1)) if np.std(ex) > 0 else np.nan)
        ids.append(rid)
    M = pd.DataFrame(D)
    full = M.notna().sum().max()
    M = M.loc[:, M.notna().sum() >= 0.9 * full].fillna(0.0)             # فقط استراتژی‌های با پوشش کامل؛ بنیادی‌ها (۶۲ ماه) خارج از PBO/RC
    N = len(runs)
    R["multi"] = {"N": N, "bonferroni_t": rs.bonferroni_t(N)}
    pb = rs.pbo_cscv(M.values) if M.shape[1] >= 10 else {}
    spa = rs.reality_check(M.values) if M.shape[1] >= 10 else {}
    R["multi"].update({"n_used": int(M.shape[1]), "months": int(M.shape[0]), "pbo": pb, "rc_spa": {**spa, "best_id": (M.columns[spa["best_idx"]] if spa else None)}})
    pvals = []
    for rid, r in runs.items():
        st = r["stats"]
        ex = D[rid].dropna().values
        r["dsr"] = rs.deflated_sharpe(ex, [x for x in sr_list if x == x]) if len(ex) > 24 else {}
        r["p_t"] = rs.t_to_p(st["t_net"]) if st["t_net"] == st["t_net"] else 1.0
        pvals.append(r["p_t"])
    rej = rs.bhy_pvals(pvals, 0.05)
    for (rid, r), j in zip(runs.items(), rej):
        r["bhy"] = bool(j)
        mono = {"spearman": r["dec"]["spearman"] if r.get("dec") else np.nan}
        r["verdict"] = fe.verdict(r["stats"], mono, r["ic"], N)
    return R


def fm_table(lab, S):
    out = {}
    for n in S:
        out[n] = {"fm": rs.fama_macbeth(lab, n), "fm_ctrl": rs.fama_macbeth(lab, n, controls=tuple(c for c in ("size", "beta_ols") if c in S and c != n))}
    return out


def top_holdings(lab, res, n=400):
    L = res.get("live")
    if not L:
        return None
    w = L["target"]
    if not (w > 0).any():                    # سبد زندهٔ تهی (مثلاً معیار بنیادی بدون پوشش در روز آخر)
        return None
    i = np.argsort(-w)[:n]
    i = i[w[i] > 0]
    mk = lab.mk
    vv = sg.W(mk.val, mk.n - 1, 63)
    adv = np.nan_to_num(np.nanmean(vv, axis=0)) if vv is not None else np.zeros(mk.k)
    build = {}
    for a_ in cn.AUMS:
        pos = w > 0
        days = np.where(adv[pos] > 0, np.ceil(w[pos] * a_ / np.maximum(adv[pos], 1) / 0.1), 99)
        build[str(int(a_))] = {"wdays": float((w[pos] * days).sum() / w[pos].sum()), "pct_gt1": float((days > 1).mean() * 100), "max_days": float(days.max())}
    return {"build": build, "date": str(L["date"].date()), "n": int((w > 0).sum()), "top": [[nrm(mk.sym[j]), round(float(w[j]) * 100, 3), None if np.isnan(L["score"][j]) else round(float(L["score"][j]), 2),
                                                                           str(mk.sector[j]), str(mk.market[j])] for j in i]}


def main(export_only=False):
    pk = CACHE / "lab_results.pkl"
    mk, lab, info = get_lab()
    S = lab.S
    if export_only and pk.exists():
        R = pickle.load(open(pk, "rb"))
        if "--refinalize" in sys.argv:
            R = finalize(lab, S, R)
            pickle.dump(R, open(pk, "wb"))
    else:
        R = run_all(lab, S)
        zoo, (use, ok, fw) = sg.zoo(mk, lab.idx, S, cost_bp=COST)
        R["zoo"] = zoo
        R["fm"] = fm_table(lab, S)
        names, C = sg.corr_matrix(mk, lab.idx, S, use, ok)
        R["corr"] = {"names": names, "m": np.round(C, 3).tolist()}
        R = finalize(lab, S, R)
        pickle.dump(R, open(pk, "wb"))              # پرتفوی زنده (top_holdings) فقط در export ساخته می‌شود
    export(mk, lab, R)


def nrm(s):
    return str(s).replace("ي", "ی").replace("ك", "ک").strip()


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()


def json_default(o):
    """numpy → JSON: NaN به null، bool به bool (نه 1.0)، عدد به float، بقیه به رشته."""
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if o != o else float(o)
    if hasattr(o, "item"):
        return json_default(o.item())
    return str(o)


def export(mk, lab, R):
    S = lab.S
    rows = len(lab.idx)                     # ماه‌ها + ردیف زنده
    k = mk.k
    ok = np.zeros((rows, k), np.uint8)
    for r in range(rows - 1):
        if r in lab.ok:
            ok[r] = lab.ok[r]
    ok[rows - 1] = lab.live_ok
    tr = np.ones((rows, k), np.uint8)              # قابل‌معامله در روز اجرا (A2)؛ ردیف زنده: ناشناخته ⇒ همه
    for r in range(rows - 1):
        tr[r] = mk.tradable(lab.idx[r])
    fw = np.full((rows, k), np.nan, np.float32)
    for r, f in lab.fw.items():
        fw[r] = f
    sig = []
    for n, M in S.items():
        Z = np.full((rows, k), -128, np.int8)
        for r in range(rows):
            z = cn.quant(sg.winsor_z(M[r], ok[r].astype(bool)))
            m = ~np.isnan(z)
            Z[r, m] = np.round(z[m] * 40).astype(np.int8)
        meta = {c: v for c, v in sg.REG[n].items() if c != "fn"}
        sig.append({**meta, "z": b64(Z)})
    mcap = np.log(np.where(mk.mcap[lab.idx] > 0, mk.mcap[lab.idx], np.nan)).astype(np.float32)
    vol = np.stack([sg.nanstd(sg.W(mk.X, a, 126)) if a >= 126 else np.full(k, np.nan) for a in lab.idx]).astype(np.float32)
    advs = []
    for a in lab.idx:
        v = sg.W(mk.val, a, 63)
        advs.append(np.log(np.nanmean(v, axis=0) + 1) if v is not None else np.full(k, np.nan))
    adv = np.stack(advs).astype(np.float32)
    sectors = sorted(set(map(str, mk.sector)) | {nm for _, _, nm in mk.sector_hist})
    secidx = np.array([sectors.index(str(s)) for s in mk.sector], np.uint8)
    sec_hist = [{"i": int(i), "to": str(to.date()), "sec": sectors.index(str(nm))} for i, to, nm in mk.sector_hist]
    nm = {}
    for f in ("instruments.csv", "instruments_extra.csv"):
        d = pd.read_csv(ROOT / "data" / f, dtype={"ins_code": str})
        nm.update(dict(zip(d.ins_code, d.name.astype(str))))
    codes = [{"c": str(c), "s": str(s), "p": nrm(s), "n": nrm(nm.get(c, "")), "m": 0 if m == "bourse" else 1, "sec": int(si)} for c, s, m, si in zip(mk.cols, mk.sym, mk.market, secidx)]
    from fetch_corporate_actions import j2g
    ev = pd.read_csv(ROOT / "data/corporate_actions/dividend_payment_events.csv", dtype=str)
    divs = []
    for r in ev.itertuples():
        try:
            pay = str(j2g(*map(int, r.pay_j.split("/"))))[:10]
        except Exception:  # noqa: BLE001
            continue
        if pay >= str((mk.dates[-1] - pd.Timedelta(days=14)).date()):
            divs.append({"sym": nrm(r.symbol), "dps": float(r.dps_rial) if r.dps_rial == r.dps_rial else None, "pay": pay, "agm_j": r.agm_j, "kind": "announced"})
    ends = [str(mk.dates[min(lab.me[r + 1], mk.n - 1)].date()) for r in range(rows - 2)] + [None]
    # تفکیک فاکتوری هر استراتژی (فصل ۱۴ §۱۴٫۷٫۸): فاکتورها همان ردیف‌های تک‌معیار کتابخانه‌اند
    runs = R["runs"]
    fac = at.factor_series(lambda s: (runs[f"sig:{s}"]["res"]["ret"]["S"], runs[f"sig:{s}"]["res"]["ret"]["ALL"])) if all(f"sig:{s}" in runs for _, _, s in at.FACTORS if s) else None
    lib = []
    for rid, r in R["runs"].items():
        res, st = r["res"], r["stats"]
        lib.append({"id": rid, "group": r["group"], "name": r["name"], "spec": r["spec"],
                    "end": [str(d.date()) for d in res["end"]], "ret": [round(float(x), 5) for x in res["ret"]["S"]],
                    "all": [round(float(x), 5) for x in res["ret"]["ALL"]], "cap": [round(float(x), 5) for x in res["ret"]["CAP"]],
                    "to_cap": [None if x != x else round(float(x), 4) for x in res["to"]["CAP"]],
                    "impact": {str(int(a_)): [None if x != x else round(float(x), 5) for x in v] for a_, v in res["impact"].items()}, "capacity": r.get("capacity"),
                    "to": [None if x != x else round(float(x), 4) for x in res["to"]["S"]], "to_all": [None if x != x else round(float(x), 4) for x in res["to"]["ALL"]],
                    "stats": {a: (None if (isinstance(b, float) and b != b) else b) for a, b in st.items()}, "ic": r["ic"], "dsr": r.get("dsr"), "verdict": r["verdict"], "dec": r.get("dec"),
                    "attr": (at.attribute(res["ret"]["S"], res["ret"]["ALL"], res["to"]["S"], res["to"]["ALL"], (r["spec"].get("cost_bp") or COST), fac) if fac else None),
                    "bhy": r.get("bhy"), "live": (top_holdings(lab, res) if r["group"] != "sig" else None), "ic_series": [None if x != x else round(float(x), 4) for x in res["ic"]]})
    data = {"use": [int(r) for r in lab.use], "built": time.strftime("%Y-%m-%d %H:%M"), "asof": str(mk.dates[-1].date()), "rows": rows, "k": k, "months_end": ends, "sig_dates": [str(mk.dates[a].date()) for a in lab.idx],
            "codes": codes, "divs": divs, "px": [0 if x != x else float(x) for x in mk.close[-1]], "sectors": sectors, "sec_hist": sec_hist, "ok": b64(ok), "tr": b64(tr), "fw": b64(np.nan_to_num(fw, nan=-9).astype(np.float32)), "mcap": b64(np.nan_to_num(mcap, nan=-99)),
            "vol": b64(np.nan_to_num(vol, nan=-1)), "adv": b64(np.nan_to_num(adv, nan=-1)), "signals": sig,
            "zoo": R["zoo"], "fm": R["fm"], "corr": R["corr"], "dec": R["dec"], "library": lib, "multi": R["multi"], "cost_bp": COST,
            "aums": [int(a_) for a_ in cn.AUMS], "y_impact": cn.Y_IMPACT, "algos": [{c: v for c, v in a.items() if c != "fn"} for a in cn.ALGOS.values()]}
    OUT_JS.write_text("window.SIM_LAB = " + json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=json_default) + ";\n", encoding="utf-8")
    slim = {"zoo": R["zoo"], "fm": R["fm"], "multi": R["multi"], "dec": R["dec"],
            "library": [{k_: v for k_, v in x.items() if k_ not in ("end", "ret", "all", "to", "to_all")} for x in lib]}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(slim, ensure_ascii=False, default=json_default), encoding="utf-8")
    print(f"ذخیره شد: {OUT_JS} ({OUT_JS.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main(export_only="--export" in sys.argv)
