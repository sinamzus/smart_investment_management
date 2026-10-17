#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""شبکهٔ پژوهش و دادهٔ «میز پژوهش» (Lab): ui/data/lab.js = window.SIM_LAB؛ فصل ۱۴ بخش ۱۴.۸.

    python tools/build_lab.py              # اجرای کامل (≈ ۳۰–۶۰ دقیقه؛ ذخیرهٔ میانی در data/derived/cache)
    python tools/build_lab.py --export     # فقط خروجی UI از نتایج ذخیره‌شده

مراحل: (۱) ماتریس معیارها (signals.py) ← (۲) جدول IC/FM همهٔ معیارها ← (۳) دهک‌های هر معیار ← (۴) شبکهٔ استراتژی‌ها (تک‌معیار، الگوریتم‌ها، ترکیب‌ها، حساسیت‌ها)
← (۵) آزمون‌های سخت (Bonferroni، DSR، PBO، Reality Check/SPA) ← (۶) خروجی.
"""
import base64
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_ui_extra as bx  # noqa: E402
import construction as cn  # noqa: E402
import factor_engine as fe  # noqa: E402
import research_stats as rs  # noqa: E402
import signals as sg  # noqa: E402

CACHE = ROOT / "data" / "derived" / "cache"
OUT_JS = ROOT / "ui" / "data" / "lab.js"
OUT_JSON = ROOT / "data" / "research" / "lab_results.json"
COST = 100.0
REP = {"momentum": "mom_12_1", "risk": "vol_252", "liquidity": "size", "yield": "div_yield", "quality": "q_roe", "value": "ep"}


def get_lab():
    _, info, Ra = bx.base_panel(bx.ALL_MARKETS)
    mk = sg.Market(Ra, info)
    mk.fund = sg.load_fund(mk.cols, mk.dates)
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / "signals_store.npz"
    if f.exists():
        z = np.load(f, allow_pickle=True)
        idx, names = list(z["idx"]), list(z["names"])
        S = {n: z["S_" + n] for n in names}
        print(f"ماتریس معیارها از حافظهٔ میانی: {len(S)} معیار")
    else:
        idx, S = sg.compute_store(mk, verbose=False)
        np.savez_compressed(f, idx=np.array(idx), names=np.array(list(S)), **{"S_" + n: v for n, v in S.items()})
    return mk, cn.Lab(mk, idx, S), info


def spec_sig(name, **kw):
    return {"signals": [[name, 1.0]], "combine": "equal", "neutral": True, "algo": "topfrac", "params": {"entry": 0.2, "exit": 0.3}, **kw}


def grid(S):
    G = []
    for n in S:                                         # الف) تک‌معیار
        G.append((f"sig:{n}", "sig", sg.REG[n]["fa"], spec_sig(n)))
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
            res = cn.backtest(lab, spec, live=(grp != "sig"))
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


def finalize(lab, S, R):
    """آمار خالص، حکم، DSR، PBO، RC/SPA؛ ورودی R از run_all."""
    runs = R["runs"]
    # دهک‌های ترکیب‌ها برای حکم
    for rid, r in runs.items():
        res = r["res"]
        r["stats"] = fe.stats_of(res, "S", COST)
        r["ic"] = fe.ic_stats({"ic": res["ic"]})
    # آزمون‌های چندگانه
    sr_list, ids, D = [], [], {}
    for rid, r in runs.items():
        res = r["res"]
        ex = fe.net(res["ret"]["S"], res["to"]["S"], COST) - fe.net(res["ret"]["ALL"], res["to"]["ALL"], COST)
        D[rid] = pd.Series(ex, index=pd.DatetimeIndex(res["end"]))
        sr_list.append(float(np.mean(ex) / np.std(ex, ddof=1)) if np.std(ex) > 0 else np.nan)
        ids.append(rid)
    M = pd.DataFrame(D)
    M = M.loc[:, M.notna().mean() >= 0.9].fillna(0.0)
    N = len(runs)
    R["multi"] = {"N": N, "bonferroni_t": rs.bonferroni_t(N)}
    pb = rs.pbo_cscv(M.values) if M.shape[1] >= 10 else {}
    spa = rs.reality_check(M.values) if M.shape[1] >= 10 else {}
    R["multi"].update({"pbo": pb, "rc_spa": {**spa, "best_id": (M.columns[spa["best_idx"]] if spa else None)}})
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
        dec = R["dec"].get(rid.split(":")[1], None) if rid.startswith("sig:") else None
        mono = {"spearman": float(pd.Series(dec["ann_net"]).corr(pd.Series(range(10)), method="spearman")) if dec else np.nan}
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
    i = np.argsort(-w)[:n]
    i = i[w[i] > 0]
    mk = lab.mk
    return {"date": str(L["date"].date()), "n": int((w > 0).sum()), "top": [[nrm(mk.sym[j]), round(float(w[j]) * 100, 3), None if np.isnan(L["score"][j]) else round(float(L["score"][j]), 2),
                                                                           str(mk.sector[j]), str(mk.market[j])] for j in i]}


def main(export_only=False):
    pk = CACHE / "lab_results.pkl"
    mk, lab, info = get_lab()
    S = lab.S
    if export_only and pk.exists():
        R = pickle.load(open(pk, "rb"))
    else:
        R = run_all(lab, S)
        zoo, (use, ok, fw) = sg.zoo(mk, lab.idx, S)
        R["zoo"] = zoo
        R["fm"] = fm_table(lab, S)
        names, C = sg.corr_matrix(mk, lab.idx, S, use, ok)
        R["corr"] = {"names": names, "m": np.round(C, 3).tolist()}
        R = finalize(lab, S, R)
        for r in R["runs"].values():
            r["live_top"] = top_holdings(lab, r["res"]) if r["group"] != "sig" else None
        pickle.dump(R, open(pk, "wb"))
    export(mk, lab, R)


def nrm(s):
    return str(s).replace("ي", "ی").replace("ك", "ک").strip()


def b64(a):
    return base64.b64encode(np.ascontiguousarray(a).tobytes()).decode()


def export(mk, lab, R):
    S = lab.S
    rows = len(lab.idx)                     # ماه‌ها + ردیف زنده
    k = mk.k
    ok = np.zeros((rows, k), np.uint8)
    for r in range(rows - 1):
        if r in lab.ok:
            ok[r] = lab.ok[r]
    ok[rows - 1] = lab.live_ok
    fw = np.full((rows, k), np.nan, np.float32)
    for r, f in lab.fw.items():
        fw[r] = f
    sig = []
    for n, M in S.items():
        Z = np.full((rows, k), -128, np.int8)
        for r in range(rows):
            z = sg.winsor_z(M[r], ok[r].astype(bool))
            m = ~np.isnan(z)
            Z[r, m] = np.clip(np.round(z[m] * 40), -127, 127).astype(np.int8)
        meta = {c: v for c, v in sg.REG[n].items() if c != "fn"}
        sig.append({**meta, "z": b64(Z)})
    mcap = np.log(np.where(mk.mcap[lab.idx] > 0, mk.mcap[lab.idx], np.nan)).astype(np.float32)
    vol = np.stack([sg.nanstd(sg.W(mk.X, a, 126)) if a >= 126 else np.full(k, np.nan) for a in lab.idx]).astype(np.float32)
    advs = []
    for a in lab.idx:
        v = sg.W(mk.val, a, 63)
        advs.append(np.log(np.nanmean(v, axis=0) + 1) if v is not None else np.full(k, np.nan))
    adv = np.stack(advs).astype(np.float32)
    sectors = sorted(set(map(str, mk.sector)))
    secidx = np.array([sectors.index(str(s)) for s in mk.sector], np.uint8)
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
    lib = []
    for rid, r in R["runs"].items():
        res, st = r["res"], r["stats"]
        lib.append({"id": rid, "group": r["group"], "name": r["name"], "spec": r["spec"],
                    "end": [str(d.date()) for d in res["end"]], "ret": [round(float(x), 5) for x in res["ret"]["S"]],
                    "all": [round(float(x), 5) for x in res["ret"]["ALL"]],
                    "to": [None if x != x else round(float(x), 4) for x in res["to"]["S"]], "to_all": [None if x != x else round(float(x), 4) for x in res["to"]["ALL"]],
                    "stats": {a: (None if (isinstance(b, float) and b != b) else b) for a, b in st.items()}, "ic": r["ic"], "dsr": r.get("dsr"), "verdict": r["verdict"],
                    "bhy": r.get("bhy"), "live": (top_holdings(lab, res) if r["group"] != "sig" else None), "ic_series": [None if x != x else round(float(x), 4) for x in res["ic"]]})
    data = {"use": [int(r) for r in lab.use], "built": time.strftime("%Y-%m-%d %H:%M"), "asof": str(mk.dates[-1].date()), "rows": rows, "k": k, "months_end": ends, "sig_dates": [str(mk.dates[a].date()) for a in lab.idx],
            "codes": codes, "divs": divs, "px": [0 if x != x else float(x) for x in mk.close[-1]], "sectors": sectors, "ok": b64(ok), "fw": b64(np.nan_to_num(fw, nan=-9).astype(np.float32)), "mcap": b64(np.nan_to_num(mcap, nan=-1)),
            "vol": b64(np.nan_to_num(vol, nan=-1)), "adv": b64(np.nan_to_num(adv, nan=-1)), "signals": sig,
            "zoo": R["zoo"], "fm": R["fm"], "corr": R["corr"], "dec": R["dec"], "library": lib, "multi": R["multi"], "cost_bp": COST,
            "algos": [{c: v for c, v in a.items() if c != "fn"} for a in cn.ALGOS.values()]}
    OUT_JS.write_text("window.SIM_LAB = " + json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=lambda o: None if o != o else (float(o) if hasattr(o, "item") else str(o))) + ";\n", encoding="utf-8")
    slim = {"zoo": R["zoo"], "fm": R["fm"], "multi": R["multi"], "dec": R["dec"],
            "library": [{k_: v for k_, v in x.items() if k_ not in ("end", "ret", "all", "to", "to_all")} for x in lib]}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(slim, ensure_ascii=False, default=lambda o: None if o != o else float(o)), encoding="utf-8")
    print(f"ذخیره شد: {OUT_JS} ({OUT_JS.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main(export_only="--export" in sys.argv)
