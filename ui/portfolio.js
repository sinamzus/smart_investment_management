/* همتا — بخش «پرتفو»: سبدهای ذخیره‌شده، پرتفوهای واقعی، انحراف از برنامه و ریبالانس با اقدامات شرکتی (فصل ۵ §۵٫۹)
   داده: window.SIM_PFX (tools/build_ui_portfolio.py: قیمت پایانی روزانه، معامله‌شدن، سود نقدی، افزایش سرمایه از ۱۳۹۹)؛ فقط با باز شدن این بخش بار می‌شود.
   ذخیره: localStorage مرورگر (کلید sim.pf.v1) + پشتیبان JSON قابل دانلود و بازیابی. هیچ داده‌ای به جایی فرستاده نمی‌شود.
   بخش اول (موتور) خالص است و در node آزمون می‌شود: node tools/portfolio_selftest.js */
(function (root) {
'use strict';

/* ═════════════════ موتور (بدون DOM) ═════════════════ */
function b64(s, T) { const bin = atob(s), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return T === Uint8Array ? u : new T(u.buffer); }
function prep(X) {
  if (X._p) return X._p;
  const K = X.codes.length;
  X._p = { K, px: X.pxArr || b64(X.px, Float32Array), tr: X.trArr || b64(X.tr, Uint8Array), ci: new Map(X.codes.map((c, i) => [String(c), i])) };
  return X._p;
}
/** اندیس آخرین روز معاملاتی ≤ d (−۱ اگر پیش از آغاز داده) */
function dayIdx(X, d) { let lo = 0, hi = X.dates.length - 1, r = -1; while (lo <= hi) { const m = (lo + hi) >> 1; if (X.dates[m] <= d) { r = m; lo = m + 1; } else hi = m - 1; } return r; }
function pxAt(X, k, d) { const p = prep(X), t = dayIdx(X, d); return t < 0 ? NaN : p.px[t * p.K + k]; }
/** معامله‌شدن در همان روز معاملاتی (اگر d روز معاملاتی نباشد، آخرین روز پیش از آن) */
function trAt(X, k, d) { const p = prep(X), t = dayIdx(X, d); return t >= 0 && p.tr[t * p.K + k] === 1; }
const evKey = (X, t, k, d) => `${t}:${X.codes[k]}:${d}`;

/** رویدادهای شرکتی میان (d1, d2] برای نمادهای دارای موجودی */
function eventsBetween(X, hold, d1, d2) {
  const p = prep(X), out = [], has = new Set(Object.keys(hold).filter(c => hold[c] > 0));
  for (const e of X.divs) if (e[1] > d1 && e[1] <= d2 && has.has(String(X.codes[e[0]]))) out.push({ t: 'div', d: e[1], k: e[0], e, key: evKey(X, 'div', e[0], e[1]) });
  for (const e of X.caps) if (e[1] > d1 && e[1] <= d2 && has.has(String(X.codes[e[0]]))) out.push({ t: 'cap', d: e[1], k: e[0], e, key: evKey(X, 'cap', e[0], e[1]) });
  out.sort((a, b) => a.d.localeCompare(b.d) || (a.t === 'div' ? -1 : 1));
  void p; return out;
}

/** وضعیت را از st.date تا d2 جلو می‌برد: سود نقدی ← طلب (و در روز پرداخت ← نقد)، سهام جایزه، حق‌تقدم (پذیره‌نویسی یا فروش).
    st = {date, hold: {ins_code: تعداد}, cash, recv: [{c, ex, pay, amt, est}]}؛ opt.rights[key] = 'sub' | 'sell' (پیش‌فرض sub)، opt.unsure: Set کلید رویدادهای نامطمئنی که اعمال شوند. */
const REG_DAYS = 60;   // روز تقریبی از ایکس‌دیت حق‌تقدم تا ثبت افزایش سرمایه و قابل‌فروش شدن سهم جدید [تأیید لازم]
const addDays = (d, n) => new Date(new Date(d + 'T00:00:00Z').getTime() + n * 864e5).toISOString().slice(0, 10);
function roll(X, st, d2, opt = {}) {
  const hold = { ...st.hold }, recv = (st.recv || []).map(r => ({ ...r })), log = [];
  const pend = (st.pend || []).map(r => ({ ...r }));
  let cash = +st.cash || 0;
  const par = X.par || 1000, rights = opt.rights || {}, unsure = opt.unsure || new Set();
  for (const v of eventsBetween(X, hold, st.date, d2)) {
    const c = String(X.codes[v.k]), q = hold[c] || 0; if (!(q > 0)) continue;
    if (v.t === 'div') {
      const [, ex, dps, pay, kind] = v.e, amt = q * dps;
      recv.push({ c, ex, pay, amt, est: kind === 'e' });
      log.push({ d: ex, t: 'div', c, q, dps, amt, pay, est: kind === 'e', key: v.key });
      continue;
    }
    const [, d, g, cs, status] = v.e;
    if (status === -1) { log.push({ d, t: 'glitch', c, q, g, key: v.key }); continue; }
    if (status === 0 && !unsure.has(v.key)) { log.push({ d, t: 'unsure', c, q, g, cs, key: v.key }); continue; }
    const bonus = Math.floor(q * (g - 1) * (1 - cs) + 1e-6), nR = Math.floor(q * (g - 1) * cs + 1e-6);   // +1e-6: خطای ممیز شناور (۱۰۰۰×۰٫۲ = ۱۹۹٫۹۹…)
    hold[c] = q + bonus;
    let how = null, rv = 0;
    if (nR > 0) {
      how = rights[v.key] || 'sub';
      if (how === 'sub') {
        if (cash < nR * par) log.push({ d, t: 'short', c, need: nR * par, have: cash, key: v.key });   // نقد برای پذیره‌نویسی کافی نیست
        cash -= nR * par; hold[c] += nR; pend.push({ c, n: nR, until: addDays(d, REG_DAYS) });       // تا ثبت افزایش سرمایه قابل‌فروش نیست
      }
      else { rv = Math.max(pxAt(X, v.k, d) - par, 0); cash += nR * rv; }                // ارزش نظری حق‌تقدم = قیمت پس از رویداد − ۱۰۰۰ [تأیید لازم]
    }
    log.push({ d, t: 'cap', c, q, g, cs, bonus, nR, how, rv, unsure: status === 0, key: v.key });
  }
  const left = [];
  for (const r of recv) { if (r.pay <= d2) { cash += r.amt; log.push({ d: r.pay, t: 'paid', c: r.c, amt: r.amt, est: r.est }); } else left.push(r); }
  Object.keys(hold).forEach(c => { if (!(hold[c] > 0)) delete hold[c]; });
  log.sort((a, b) => a.d.localeCompare(b.d));
  return { date: d2, hold, cash, recv: left, pend: pend.filter(r => r.until > d2 && hold[r.c] > 0), log };
}

/** ارزش‌گذاری در تاریخ d با قیمت پایانی آخرین روز معاملاتی ≤ d */
function value(X, st, d) {
  const p = prep(X), rows = [];
  let stock = 0;
  for (const [c, q] of Object.entries(st.hold || {})) {
    const k = p.ci.get(String(c)), px = k == null ? NaN : pxAt(X, k, d), v = q * (px > 0 ? px : 0);
    rows.push({ c, k, q, px, v, tr: k != null && trAt(X, k, d) }); stock += v;
  }
  const recv = (st.recv || []).reduce((s, r) => s + r.amt, 0), cash = +st.cash || 0;
  return { rows, stock, cash, recv, nav: stock + cash + recv };
}

/** سفارش‌های رسیدن از وضعیت st به وزن هدف w ({ins_code: وزن}) در تاریخ d.
    سرمایهٔ قابل‌سرمایه‌گذاری = سهام + نقد (+ طلب سود اگر o.useRecv). نماد بی‌معامله در d منجمد می‌ماند (نه خرید نه فروش). */
function orders(X, st, w, d, o = {}) {
  const V = value(X, st, d), base = V.stock + V.cash + (o.useRecv ? V.recv : 0) - (o.reserve || 0);
  // اگر هزینه یا گرد کردن نقد را منفی کند، سرمایهٔ قابل‌سرمایه‌گذاری به اندازهٔ کسری کم و دوباره حساب می‌شود
  let r = orders1(X, st, w, d, o, V, base);
  for (let i = 0; i < 4 && r.after.cash < -1 && !o.useRecv; i++) r = orders1(X, st, w, d, o, V, r.invest + r.after.cash * 1.02);
  return r;
}
function orders1(X, st, w, d, o, V, invest) {
  const p = prep(X), lot = o.lot || 1, minPct = o.minPct || 0;
  // هزینهٔ نامتقارن (ممیزی ۲۰۲۶-۱۰-۲۰): فروش مالیات نقل‌وانتقال هم دارد؛ اگر فقط costBp داده شود، نصف‌نصف (رفت‌وبرگشت)
  const cB = (o.costBuyBp != null ? o.costBuyBp : (o.costBp || 0) / 2) / 1e4, cS = (o.costSellBp != null ? o.costSellBp : (o.costBp || 0) / 2) / 1e4;
  const pendQ = {}; (st.pend || []).forEach(r => { if (r.until > d) pendQ[r.c] = (pendQ[r.c] || 0) + r.n; });
  const codes = new Set([...Object.keys(st.hold || {}), ...Object.keys(w).filter(c => w[c] > 0)]);
  // قاعدهٔ نماد بی‌معامله (همان freeze_untradable بک‌تست، فصل ۸ §۸٫۱): موجودی بی‌معامله با ارزش فعلی‌اش منجمد می‌ماند،
  // نماد تازهٔ بی‌معامله خریده نمی‌شود، و باقی سرمایه به نسبت وزن میان نمادهای قابل‌معامله پخش می‌شود.
  const info = new Map(); let wTr = 0, frozenV = 0;
  for (const c of codes) {
    const k = p.ci.get(String(c)), q = (st.hold || {})[c] || 0, px = k == null ? NaN : pxAt(X, k, d), tr = k != null && px > 0 && trAt(X, k, d);
    info.set(c, { k, q, px, tr });
    if (tr) wTr += Math.max(w[c] || 0, 0); else if (q > 0 && px > 0) frozenV += q * px;
  }
  const free = Math.max(invest - frozenV, 0);
  const out = [], hold2 = {}, frozen = [], missing = [];
  let buy = 0, sell = 0;
  for (const c of codes) {
    const { k, q, px, tr } = info.get(c), wt = tr && wTr > 0 ? Math.max(w[c] || 0, 0) / wTr : 0;
    if (k == null || !(px > 0)) { missing.push(c); if (q) hold2[c] = q; continue; }
    if (!tr) { if (q > 0 || (w[c] || 0) > 0) frozen.push(c); if (q) hold2[c] = q; continue; }
    let tq = Math.floor(wt * free / px / lot + 1e-9) * lot;
    if (pendQ[c] && tq < Math.min(q, pendQ[c])) { tq = Math.min(q, pendQ[c]); if (!frozen.includes(c)) frozen.push(c); }   // سهم حق‌تقدم ثبت‌نشده فروختنی نیست
    let dq = tq - q;
    if (dq !== 0 && Math.abs(dq * px) < minPct * invest && tq > 0) { dq = 0; tq = q; }       // معاملهٔ خیلی کوچک حذف (مگر فروش کامل)
    if (tq > 0) hold2[c] = tq;
    if (dq === 0) continue;
    const val = Math.abs(dq) * px;
    if (dq > 0) buy += val; else sell += val;
    out.push({ c, k, side: dq > 0 ? 'buy' : 'sell', qty: Math.abs(dq), px, val, q, tq, w_now: q * px / (V.stock + V.cash || 1), w_tgt: wt });
  }
  out.sort((a, b) => (a.side === b.side ? b.val - a.val : a.side === 'sell' ? -1 : 1));
  const fee = buy * cB + sell * cS;
  return { orders: out, buy, sell, fee, invest, V, after: { date: d, hold: hold2, cash: V.cash - buy + sell - fee, recv: st.recv || [], pend: st.pend || [] }, frozen, missing };
}

/** انحراف وضعیت واقعی از برنامه در تاریخ d (وزن هر دو با قیمت همان روز) */
function deviation(X, planHold, actual, d) {
  const p = prep(X), codes = new Set([...Object.keys(planHold || {}), ...Object.keys(actual.hold || {})]);
  const val = (h, c) => { const k = p.ci.get(String(c)); return k == null ? 0 : (h[c] || 0) * (pxAt(X, k, d) || 0); };
  let tp = 0, ta = 0; for (const c of codes) { tp += val(planHold || {}, c); ta += val(actual.hold || {}, c); }
  const rows = [...codes].map(c => ({ c, qp: (planHold || {})[c] || 0, qa: (actual.hold || {})[c] || 0, wp: tp ? val(planHold || {}, c) / tp : 0, wa: ta ? val(actual.hold || {}, c) / ta : 0 }))
    .map(r => ({ ...r, dw: r.wa - r.wp, dq: r.qa - r.qp })).sort((a, b) => Math.abs(b.dw) - Math.abs(a.dw));
  return { rows, active: rows.reduce((s, r) => s + Math.abs(r.dw), 0) / 2, valPlan: tp, valAct: ta };
}

const ENG = { prep, dayIdx, pxAt, trAt, eventsBetween, roll, value, orders, deviation };
if (typeof module !== 'undefined' && module.exports) { module.exports = ENG; return; }
root.SIM_PFENG = ENG;

/* ═════════════════ ذخیره (مرورگر + پشتیبان) ═════════════════ */
const KEY = 'sim.pf.v1';
const DB = { load() { try { const d = JSON.parse(localStorage.getItem(KEY)); if (d && d.v === 1) return d; } catch (e) { /* خالی */ } return { v: 1, baskets: [], ports: [] }; },
  save(d) { try { localStorage.setItem(KEY, JSON.stringify(d)); return true; } catch (e) { toast('ذخیره در مرورگر ممکن نشد؛ از «پشتیبان» استفاده کنید'); return false; } } };
let db = DB.load();
const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const tip = (t, d) => ` data-tip="${esc(t)}"${d ? ` data-doc="${d}"` : ''}`;
const DOCS = '5:5.9';
const f = (x, d = 0) => x == null || x !== x ? '—' : fmt(x, d);
const today = () => { const X = root.SIM_PFX; return X ? X.dates[X.dates.length - 1] : (root.SIM_LAB && root.SIM_LAB.asof) || new Date().toISOString().slice(0, 10); };
const jdate = iso => (iso && root.SIM_JDATE ? root.SIM_JDATE.j(iso) : iso) || '—';
const isoOf = s => { const t = String(s || '').trim(); if (/^\d{4}-\d\d-\d\d$/.test(t)) return t; return root.SIM_JDATE ? root.SIM_JDATE.g(t) : null; };
const SRC_FA = { index: 'شاخص', lab: 'استراتژی Lab', lib: 'کتابخانهٔ Lab', replica: 'همتاساز', enh: 'شاخص بهبودیافته', live: 'استراتژی قفل‌شده', manual: 'دستی' };

/** ذخیرهٔ سبد از وزن به ترتیب نمادهای Lab (Float64Array) یا {ins_code: وزن}. src: {kind, label, spec?, libId?, key?, idx?} */
function saveBasket(name, w, src, opt = {}) {
  const L = root.SIM_LAB, W = {};
  if (w && typeof w.length === 'number') { let s = 0; for (let i = 0; i < w.length; i++) if (w[i] > 0) { W[L.codes[i].c] = w[i]; s += w[i]; } Object.keys(W).forEach(c => { W[c] = +(W[c] / s).toFixed(8); }); }
  else Object.assign(W, w || {});
  const asof = (L && L.asof) || today(), sig = JSON.stringify([src && src.kind, src && (src.spec || src.libId || src.key || src.idx), asof]);
  const dup = db.baskets.find(b => b.sig === sig && JSON.stringify(b.w) === JSON.stringify(W));
  if (dup && !opt.force) { if (opt.name) { dup.name = opt.name; DB.save(db); } return dup; }
  const b = { id: uid(), name: opt.name || name, created: new Date().toISOString().slice(0, 16).replace('T', ' '), asof, src: src || { kind: 'manual' }, w: W, sig };
  db.baskets.unshift(b); DB.save(db); renderAll();
  return b;
}

/* ═════════════════ هدف سبد در هر تاریخ ═════════════════ */
const TCACHE = new Map();
/** وزن هدف سبد در تاریخ d، به‌صورت {ins_code: وزن}؛ برای منبع‌های قابل بازسازی (شاخص، استراتژی Lab با الگوریتم مرورگر، همتاساز) دوباره حساب می‌شود،
    وگرنه همان عکس لحظهٔ ذخیره. خروجی: {w, asOf (تاریخ سیگنال)، how ('recomputed' | 'snapshot'), note} */
function targetAt(b, d) {
  const L = root.SIM_LAB, CTX = root.SIM_LAB_CTX && root.SIM_LAB_CTX(), E = root.LabEngine, s = b.src || {};
  const snap = note => ({ w: b.w, asOf: b.asof, how: 'snapshot', note });
  if (!L || !CTX) return snap('Lab بارگذاری نشده');
  const sd = L.sig_dates, rl = L.rows - 1;
  const rowAt = dd => { let r = -1; for (let i = 0; i < sd.length; i++) if (sd[i] && sd[i] <= dd) r = i; return r; };
  if (s.kind === 'index') {
    const r = rowAt(d); if (r < 0) return snap('پیش از آغاز داده'); const k = L.k, W = {}; let t = 0;
    for (let i = 0; i < k; i++) if (!L.codes[i].m && CTX.ok[r * k + i]) { const v = s.idx === 'K' ? Math.exp(CTX.mcap[r * k + i]) : 1; W[L.codes[i].c] = v; t += v; }
    Object.keys(W).forEach(c => { W[c] /= t; }); return { w: W, asOf: sd[r], how: 'recomputed' };
  }
  if ((s.kind === 'lab' || s.kind === 'lib' || s.kind === 'live') && s.spec && E && E.JS_ALGOS.includes(s.spec.algo) && s.spec.combine !== 'fm_lib') {
    const key = JSON.stringify(s.spec);
    if (!TCACHE.has(key)) { try { TCACHE.set(key, E.run(CTX, { ...s.spec, _keepW: true })); } catch (e) { TCACHE.set(key, null); } }
    const res = TCACHE.get(key); if (!res) return snap('اجرای استراتژی در مرورگر ممکن نشد');
    const toW = x => { const W = {}; let t = 0; for (let i = 0; i < x.length; i++) if (x[i] > 0) { W[L.codes[i].c] = x[i]; t += x[i]; } Object.keys(W).forEach(c => { W[c] /= t; }); return W; };
    if (d >= sd[rl]) return { w: toW(res.live.target), asOf: sd[rl], how: 'recomputed' };
    let best = -1; res.rows.forEach((r, j) => { if (res.W[j] && sd[r] && sd[r] <= d) best = j; });
    return best < 0 ? snap('پیش از نخستین ریبالانس استراتژی') : { w: toW(res.W[best]), asOf: sd[res.rows[best]], how: 'recomputed' };
  }
  if (s.kind === 'replica' && root.SIM_REP && root.SIM_REP.configs[s.key]) {
    const R = root.SIM_REP, c = R.configs[s.key], dd = (new Date(d + 'T00:00:00Z').getTime()) / 864e5;
    let j = -1; R.sig.forEach((x, i) => { if (x <= dd) j = i; });
    const live = d >= R.asof, sel = live ? [c.live[0], c.live[1]] : (j >= 0 ? c.sel[j] : null); if (!sel) return snap('پیش از آغاز داده');
    const W = {}; sel[0].forEach((i, p) => { W[R.names[i].c] = sel[1][p] / 1e5; });
    return { w: W, asOf: live ? R.asof : new Date(R.sig[j] * 864e5).toISOString().slice(0, 10), how: 'recomputed' };
  }
  return snap(s.kind === 'enh' ? 'هدف تیلت‌شده با تاریخ بازسازی نمی‌شود' : s.kind === 'lib' ? 'الگوریتم این ردیف در مرورگر نیست' : 'وزن ثابت');
}

/* ═════════════════ رابط ═════════════════ */
let X = null;
function ensurePFX(cb) {
  if (root.SIM_PFX) { X = root.SIM_PFX; return root.SIM_ENSURE_LAB ? root.SIM_ENSURE_LAB(cb) : cb(); }
  const s = document.createElement('script'); s.src = 'data/portfolio.js';
  s.onload = () => { X = root.SIM_PFX; root.SIM_ENSURE_LAB ? root.SIM_ENSURE_LAB(cb) : cb(); };
  s.onerror = () => { document.querySelectorAll('#v-port, #v-bsk').forEach(m => { m.innerHTML = '<p style="padding:24px">دادهٔ پرتفو پیدا نشد. اجرا کنید: <code>python tools/build_ui_portfolio.py</code></p>'; }); };
  document.head.appendChild(s);
}
const symOf = c => { const p = X && prep(X), k = p ? p.ci.get(String(c)) : null; return k != null ? X.syms[k] : c; };
const norm = s => String(s || '').replace(/ي/g, 'ی').replace(/ك/g, 'ک').replace(/[\s‌]+/g, '').trim();
function codeOf(sym) {
  const p = prep(X), s = norm(sym); if (p.ci.has(s)) return s;
  const k = X.syms.findIndex(x => norm(x) === s); return k >= 0 ? String(X.codes[k]) : null;
}
function parseHold(txt) {
  const hold = {}, bad = [];
  String(txt || '').split(/\n+/).forEach(line => { const q = line.split(/[,،\t;]/).map(x => x.trim()); if (q.length < 2 || !q[0]) return; const n = parseFloat(q[1].replace(/[^\d.\-]/g, '')); const c = codeOf(q[0]); if (!c || !(n === n)) { bad.push(q[0]); return; } hold[c] = (hold[c] || 0) + n; });
  return { hold, bad };
}
const holdText = h => Object.entries(h || {}).sort((a, b) => b[1] - a[1]).map(([c, q]) => `${symOf(c)},${q}`).join('\n');
const advOf = c => { const L = root.SIM_LAB, CTX = root.SIM_LAB_CTX && root.SIM_LAB_CTX(); if (!L || !CTX) return NaN; const i = L.codes.findIndex(x => x.c === c); if (i < 0) return NaN; const a = CTX.adv[(L.rows - 1) * L.k + i]; return a > 0 ? Math.exp(a) : NaN; };
const port = () => db.ports.find(p => p.id === ui.pid) || null;
const lastOf = (p, t) => p ? [...p.events].reverse().find(e => e.type === t) || null : null;
const ui = { pid: null, bid: null, rb: { date: null, bid: null, lot: 1, min: 0.1, cb: 37, cs: 88, useRecv: false, rights: {}, unsure: new Set() }, res: null };

function renderAll() { if ($('v-bsk') && $('v-bsk').dataset.ready) renderBaskets(); if ($('v-port') && $('v-port').dataset.ready) renderPort(); }

/* ── سبدها ── */
function initBaskets() {
  const m = $('v-bsk'); m.dataset.ready = 1;
  m.innerHTML = `<section class="panel" style="--lg:var(--lg-a)"><div class="panel-head"><span class="lg-badge">A</span><span class="panel-title"${tip('هر وزن هدفی که از هر جای برنامه به «دستور اجرا» فرستاده شود (Lab، کتابخانه، همتاساز، شاخص بهبودیافته) یا در «دستور اجرا» با «ذخیره به‌عنوان سبد» ثبت شود، اینجا با نام ذخیره می‌شود. سبد «چگونه ساختن» را هم نگه می‌دارد تا در تاریخ دیگری دوباره حساب شود.', DOCS)}>سبدهای ذخیره‌شده</span>
      <div class="panel-tools"><button class="tool" id="bk-exp"${tip('همهٔ سبدها و پرتفوها را در یک فایل JSON دانلود می‌کند. ذخیرهٔ اصلی در همین مرورگر است؛ با پاک‌شدن دادهٔ مرورگر از بین می‌رود، پس گاهی پشتیبان بگیرید.')}>پشتیبان (JSON)</button><label class="tool" style="cursor:pointer"${tip('بازیابی از فایل پشتیبان: سبدها و پرتفوهای فایل به فهرست فعلی افزوده می‌شوند (شناسهٔ تکراری جایگزین می‌شود).')}>بازیابی<input type="file" id="bk-imp" accept=".json,application/json" hidden></label></div></div>
      <div class="panel-body scroll" style="max-height:420px"><table class="dt" id="bk-tab"></table></div>
      <div class="lineage"><span><b${tip('ذخیره در localStorage همین مرورگر (کلید sim.pf.v1). جای دیگری فرستاده نمی‌شود.')}>ذخیره</b> مرورگر + فایل پشتیبان</span><span><b${tip('شاخص، استراتژی Lab با الگوریتم مرورگر، و همتاساز در هر تاریخ دوباره ساخته می‌شوند؛ شاخص بهبودیافته و ردیف‌های کتابخانه با الگوریتم پایتونی همان وزن لحظهٔ ذخیره را نگه می‌دارند.')}>بازسازی در تاریخ دیگر</b> شاخص · Lab · همتاساز</span></div></section>
    <section class="panel" style="--lg:var(--lg-b)"><div class="panel-head"><span class="lg-badge">B</span><span class="panel-title" id="bk-dt"${tip('وزن‌های سبد انتخاب‌شده، به ترتیب وزن.')}>وزن‌های سبد</span></div>
      <div class="panel-body scroll" style="max-height:420px"><table class="dt" id="bk-w"></table></div></section>`;
  $('bk-exp').onclick = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(db, null, 1)], { type: 'application/json' })); a.download = `hamta_portfolios_${today()}.json`; a.click(); };
  $('bk-imp').onchange = e => { const fl = e.target.files[0]; if (!fl) return; fl.text().then(t => { try { const d = JSON.parse(t); if (d.v !== 1) throw new Error('نسخه'); const mg = (a, b) => { const ids = new Set(b.map(x => x.id)); return [...b, ...a.filter(x => !ids.has(x.id))]; }; db.baskets = mg(db.baskets, d.baskets || []); db.ports = mg(db.ports, d.ports || []); DB.save(db); renderAll(); toast('بازیابی شد'); } catch (er) { toast('فایل پشتیبان معتبر نیست'); } }); };
  renderBaskets();
}
function renderBaskets() {
  const B = db.baskets;
  $('bk-tab').innerHTML = `<thead><tr><th${tip('نام سبد؛ با «نام» عوض می‌شود.')}>نام</th><th${tip('از کجا آمده و آیا در تاریخ دیگر دوباره ساخته می‌شود.')}>منبع</th><th${tip('آخرین روز داده هنگام ذخیره.')}>تاریخ داده</th><th class="n"${tip('تعداد نمادهای دارای وزن.')}>نماد</th><th${tip('پنج نماد با بیشترین وزن.')}>وزن‌های برتر</th><th></th></tr></thead><tbody>` +
    (B.map(b => { const top = Object.entries(b.w).sort((x, y) => y[1] - x[1]).slice(0, 5).map(([c, w]) => `${symOf(c)} ${fmt(100 * w, 1)}٪`).join('، ');
      return `<tr${b.id === ui.bid ? ' aria-selected="true"' : ''} data-b="${b.id}"><td><a class="symlink" data-act="show">${esc(b.name)}</a></td><td>${esc(SRC_FA[b.src.kind] || b.src.kind)}</td><td class="num">${jdate(b.asof)}</td><td class="n">${Object.keys(b.w).length}</td><td>${esc(top)}</td><td><button class="tool" data-act="port"${tip('پرتفوی تازه با هدف این سبد می‌سازد.')}>پرتفو</button> <button class="tool" data-act="ren"${tip('تغییر نام')}>نام</button> <button class="tool" data-act="del"${tip('حذف سبد (پرتفوهایی که از آن ساخته شده‌اند می‌مانند).')}>×</button></td></tr>`; }).join('') ||
      '<tr><td colspan="6" class="mute" style="white-space:normal">هنوز سبدی نیست. از Lab (پرتفوی زنده ← «ارسال به برنامهٔ اقدام»)، همتاساز (پرتفوی امروز ← «ارسال به برنامهٔ اقدام») یا «دستور اجرا» (← «ذخیره به‌عنوان سبد») بفرستید.</td></tr>') + '</tbody>';
  $('bk-tab').querySelectorAll('[data-act]').forEach(a => a.onclick = () => {
    const b = db.baskets.find(x => x.id === a.closest('tr').dataset.b); if (!b) return;
    const act = a.dataset.act;
    if (act === 'show') { ui.bid = b.id; renderBaskets(); }
    if (act === 'ren') { const n = prompt('نام تازهٔ سبد', b.name); if (n && n.trim()) { b.name = n.trim(); DB.save(db); renderAll(); } }
    if (act === 'del' && confirm(`سبد «${b.name}» حذف شود؟`)) { db.baskets = db.baskets.filter(x => x.id !== b.id); DB.save(db); renderAll(); }
    if (act === 'port') { ui.newFrom = b.id; root.SIM_SHOW('port'); }
  });
  const b = db.baskets.find(x => x.id === ui.bid) || db.baskets[0];
  if (!b) { $('bk-w').innerHTML = ''; return; }
  $('bk-dt').textContent = 'وزن‌های سبد · ' + b.name;
  $('bk-w').innerHTML = th([['#', 'rank'], ['نماد'], ['وزن ٪', 'n']]) + '<tbody>' + Object.entries(b.w).sort((x, y) => y[1] - x[1]).map(([c, w], i) => `<tr><td class="rank">${i + 1}</td><td>${esc(symOf(c))}</td><td class="n">${fmt(100 * w, 2)}</td></tr>`).join('') + '</tbody>';
}

/* ── پرتفوها ── */
const bOpts = sel => db.baskets.map(b => `<option value="${b.id}"${b.id === sel ? ' selected' : ''} data-tip="${esc(SRC_FA[b.src.kind] + ' · ' + Object.keys(b.w).length + ' نماد · داده ' + jdate(b.asof))}">${esc(b.name)}</option>`).join('');
function initPort() {
  const m = $('v-port'); m.dataset.ready = 1;
  m.innerHTML = `
  <section class="panel" style="--lg:var(--lg-a)"><div class="panel-head"><span class="lg-badge">A</span><span class="panel-title"${tip('پرتفوی واقعی شما: از یک سبد (هدف) ساخته می‌شود، پرتفوی اجراشده را در هر تاریخ ثبت می‌کنید، انحراف از برنامه را می‌بینید و در هر تاریخ با همان سبد یا سبد دیگر ریبالانس می‌کنید. سود نقدی، سهام جایزه و حق‌تقدم میان دو تاریخ خودکار حساب می‌شود.', DOCS)}>پرتفو</span>
    <select id="pt-sel"${tip('پرتفوی فعال.')}></select><span class="spacer"></span><button class="tool" id="pt-new"${tip('پرتفوی تازه از یک سبد.')}>+ پرتفوی تازه</button><button class="tool" id="pt-del"${tip('حذف این پرتفو و همهٔ تاریخچه‌اش.')}>حذف</button></div>
    <div class="ctl" id="pt-newf" hidden><label${tip('نام پرتفو.')}>نام <input id="pt-name" style="width:180px"></label><label${tip('هدف اولیهٔ پرتفو.')}>سبد <select id="pt-bsk"></select></label>
      <label${tip('تاریخ شروع (شمسی). برنامهٔ خرید اولیه با قیمت پایانی این روز حساب می‌شود.')}>تاریخ <input id="pt-d0" style="width:100px" placeholder="1405/07/26"></label><label${tip('سرمایهٔ نقد اولیه به میلیارد ریال.')}>سرمایه (میلیارد ریال) <input type="number" id="pt-aum" value="100" min="0.01" step="10" style="width:90px"></label><button class="tool" id="pt-mk">ساخت</button></div>
    <div class="kpis" id="pt-kpi"></div><div class="lineage" id="pt-lin"></div></section>
  <section class="panel" style="--lg:var(--lg-b)"><div class="panel-head"><span class="lg-badge">B</span><span class="panel-title"${tip('پرتفوی واقعی (آخرین ثبت) در برابر آخرین برنامه، هر دو با قیمت همان روز: کدام نمادها کم یا زیاد خریده شده‌اند.', DOCS)}>انحراف از برنامه</span><span class="chip" id="pt-dchip"></span></div>
    <div class="panel-body scroll" style="max-height:360px"><table class="dt" id="pt-dev"></table></div></section>
  <section class="panel" style="--lg:var(--lg-c)"><div class="panel-head"><span class="lg-badge">C</span><span class="panel-title"${tip('در هر تاریخ: وضعیت از آخرین ثبت تا این تاریخ با اقدامات شرکتی جلو می‌رود، سپس با سبد انتخابی سفارش خرید و فروش پیشنهاد می‌شود.', DOCS)}>ریبالانس</span>
    <div class="panel-tools"><button class="tool" id="rb-csv2"${tip('سفارش‌ها به‌صورت CSV.')}>CSV</button><button class="tool" id="rb-json2"${tip('سفارش‌ها با همان طرح JSON «دستور اجرا» برای سامانهٔ الگوریتمی.')}>JSON</button><button class="tool" id="rb-saveplan"${tip('این ریبالانس را به‌عنوان «برنامه» در تاریخچه ثبت می‌کند و متن «ثبت اجرا» را با موجودی پس از سفارش‌ها پر می‌کند.')}>ثبت به‌عنوان برنامه</button></div></div>
    <div class="ctl"><label${tip('تاریخ ریبالانس (شمسی). قیمت‌ها پایانی آخرین روز معاملاتی تا این تاریخ‌اند؛ هدف سبد با آخرین سیگنال تا این تاریخ دوباره ساخته می‌شود.')}>تاریخ <input id="rb-d" style="width:100px"></label>
      <label${tip('استراتژی ریبالانس: همان سبد پرتفو یا هر سبد ذخیره‌شدهٔ دیگر.')}>سبد هدف <select id="rb-b"></select></label>
      <label${tip('کمترین معامله به درصد سرمایه؛ معاملهٔ کوچک‌تر حذف می‌شود (مگر فروش کامل).')}>حداقل معامله ٪ <input type="number" id="rb-min" value="0.1" min="0" step="0.05" style="width:70px"></label>
      <label${tip('هزینهٔ خرید به bp از ارزش معامله: کارمزد کارگزاری، بورس، سپرده‌گذاری و نظارت [تأیید لازم].', '6:6.1')}>هزینهٔ خرید bp <input type="number" id="rb-cb" value="37" min="0" step="1" style="width:60px"></label>
      <label${tip('هزینهٔ فروش به bp: کارمزدها + مالیات نقل‌وانتقال ۰٫۵٪ [تأیید لازم]. جمع خرید و فروش = هزینهٔ رفت‌وبرگشت پروژه (۱۲۵ bp).', '6:6.1')}>هزینهٔ فروش bp <input type="number" id="rb-cs" value="88" min="0" step="1" style="width:60px"></label>
      <label${tip('اگر روشن باشد، سود دریافت‌نشده هم بخشی از سرمایهٔ قابل‌سرمایه‌گذاری حساب می‌شود (یعنی پیش از وصول خرج می‌شود؛ نقد منفی ممکن است). پیش‌فرض خاموش: فقط سهام + نقد.')}><input type="checkbox" id="rb-recv"> سود دریافت‌نشده هم سرمایه‌گذاری شود</label></div>
    <div class="kpis" id="rb-kpi2"></div>
    <div class="lb-note" id="rb-evcap"></div><div class="panel-body scroll" style="max-height:260px"><table class="dt" id="rb-ev"></table></div>
    <div class="lb-note" id="rb-ordcap"></div><div class="panel-body scroll" style="max-height:420px"><table class="dt" id="rb-ord"></table></div>
    <div class="lineage" id="rb-lin2"></div></section>
  <section class="panel" style="--lg:var(--lg-d)"><div class="panel-head"><span class="lg-badge">D</span><span class="panel-title"${tip('موجودی واقعی پس از اجرای سفارش‌ها (یا هر زمان دیگر) را ثبت کنید؛ از این ثبت، انحراف و ریبالانس بعدی حساب می‌شود.', DOCS)}>ثبت پرتفوی اجراشده</span></div>
    <div class="ctl"><label${tip('تاریخ موجودی (شمسی).')}>تاریخ <input id="ac-d" style="width:100px"></label><label${tip('نقد پس از معاملات به ریال (کارمزد کسرشده).')}>نقد (ریال) <input type="number" id="ac-cash" style="width:150px"></label>
      <label${tip('هر خط: نماد،تعداد. با «ثبت به‌عنوان برنامه» با موجودی پس از سفارش‌ها پر می‌شود؛ اعداد را با اجرای واقعی اصلاح کنید.')}>موجودی <textarea id="ac-hold" rows="4" style="width:260px" placeholder="فولاد,120000&#10;فملی,50000"></textarea></label>
      <button class="tool" id="ac-calc"${tip('نقد را از روی تعدادهای بالا حساب می‌کند: نقد آخرین ثبت (با سود و حق‌تقدم تا این تاریخ) − ارزش خریدها + ارزش فروش‌ها با قیمت پایانی همین روز − هزینهٔ رفت‌وبرگشت پنل C. اگر قیمت واقعی اجرا فرق داشت، عدد را دستی اصلاح کنید.')}>محاسبهٔ نقد</button><button class="tool" id="ac-save">ثبت</button><span class="mute" id="ac-note"></span></div></section>
  <section class="panel" style="--lg:var(--lg-e)"><div class="panel-head"><span class="lg-badge">E</span><span class="panel-title"${tip('همهٔ ثبت‌های این پرتفو: برنامه‌ها و موجودی‌های اجراشده.')}>تاریخچه</span></div>
    <div class="panel-body scroll" style="max-height:300px"><table class="dt" id="pt-hist"></table></div></section>`;
  $('pt-sel').onchange = e => { ui.pid = e.target.value; ui.rb.rights = {}; ui.rb.unsure = new Set(); renderPort(); };
  $('pt-new').onclick = () => { $('pt-newf').hidden = !$('pt-newf').hidden; $('pt-bsk').innerHTML = bOpts(ui.newFrom); $('pt-d0').value = jdate(today()); };
  $('pt-del').onclick = () => { const p = port(); if (p && confirm(`پرتفوی «${p.name}» و تاریخچه‌اش حذف شود؟`)) { db.ports = db.ports.filter(x => x.id !== p.id); ui.pid = null; DB.save(db); renderPort(); } };
  $('pt-mk').onclick = makePort;
  ['rb-d', 'rb-b', 'rb-min', 'rb-cb', 'rb-cs', 'rb-recv'].forEach(i => { $(i).onchange = () => renderRebal(); });
  $('rb-saveplan').onclick = savePlan; $('ac-save').onclick = saveActual; $('ac-calc').onclick = calcCash;
  $('rb-csv2').onclick = () => { const r = ui.res; if (!r) return; download(`rebalance_${(port() || {}).name}_${r.date}.csv`, [['action', 'symbol', 'ins_code', 'qty', 'ref_price', 'value_rial', 'qty_now', 'qty_target'], ...r.o.orders.map(x => [x.side.toUpperCase(), symOf(x.c), x.c, x.qty, x.px, Math.round(x.val), x.q, x.tq])]); };
  $('rb-json2').onclick = () => { const r = ui.res, p = port(); if (!r || !p) return; const body = { schema: 'sim.trade_plan/1', plan_id: p.id + '-' + r.date, asof: r.date, created: new Date().toISOString(), target: r.bname, portfolio: p.name, aum_rial: Math.round(r.o.invest), cost_bp_buy: ui.rb.cb, cost_bp_sell: ui.rb.cs, orders: r.o.orders.map(x => ({ symbol: symOf(x.c), ins_code: x.c, side: x.side.toUpperCase(), qty: x.qty, ref_price: x.px, type: 'rebalance' })) }; const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(body, null, 1)], { type: 'application/json' })); a.download = `trade_plan_${p.name}_${r.date}.json`; a.click(); };
  if (ui.newFrom) { $('pt-newf').hidden = false; $('pt-bsk').innerHTML = bOpts(ui.newFrom); $('pt-d0').value = jdate(today()); }
  renderPort();
}
function makePort() {
  const b = db.baskets.find(x => x.id === $('pt-bsk').value); if (!b) { toast('اول یک سبد بسازید'); return; }
  const d0 = isoOf($('pt-d0').value); if (!d0 || dayIdx(X, d0) < 0) { toast('تاریخ نامعتبر یا پیش از ۱۳۹۹'); return; }
  const aum = (+$('pt-aum').value || 0) * 1e9; if (!(aum > 0)) { toast('سرمایه را وارد کنید'); return; }
  const p = { id: uid(), name: ($('pt-name').value || '').trim() || b.name, basketId: b.id, created: new Date().toISOString().slice(0, 16).replace('T', ' '), events: [] };
  const st0 = { date: d0, hold: {}, cash: aum, recv: [] }, t = targetAt(b, d0), o = orders(X, st0, t.w, d0, { minPct: 0, costBp: 125 });
  p.events.push({ type: 'actual', date: d0, hold: {}, cash: aum, recv: [], note: 'سرمایهٔ اولیه (نقد)' });
  p.events.push({ type: 'plan', date: d0, basketId: b.id, bname: b.name, hold: o.after.hold, cash: o.after.cash, how: t.how, sigAsOf: t.asOf, note: 'برنامهٔ ساخت اولیه' });
  db.ports.unshift(p); ui.pid = p.id; ui.newFrom = null; DB.save(db); $('pt-newf').hidden = true;
  $('ac-hold').value = holdText(o.after.hold); $('ac-cash').value = Math.round(o.after.cash); $('ac-d').value = jdate(d0);
  renderPort(); toast('پرتفو ساخته شد؛ پس از خرید، موجودی واقعی را در پنل D ثبت کنید');
}
function renderPort() {
  if (!$('pt-sel')) return;
  if (!ui.pid && db.ports[0]) ui.pid = db.ports[0].id;
  $('pt-sel').innerHTML = db.ports.map(p => `<option value="${p.id}"${p.id === ui.pid ? ' selected' : ''}>${esc(p.name)}</option>`).join('') || '<option value="">— هنوز پرتفویی نیست —</option>';
  $('rb-b').innerHTML = bOpts(ui.rb.bid || (port() || {}).basketId);
  const p = port();
  if (!p) { ['pt-kpi', 'pt-lin', 'pt-dev', 'rb-kpi2', 'rb-ev', 'rb-ord', 'rb-lin2', 'pt-hist'].forEach(i => { $(i).innerHTML = ''; }); $('pt-kpi').innerHTML = '<div class="lb-note">با «+ پرتفوی تازه» از یک سبد شروع کنید. سبدها از «ارسال به برنامهٔ اقدام» در Lab یا همتاساز، یا «ذخیره به‌عنوان سبد» در «دستور اجرا» ساخته می‌شوند.</div>'; return; }
  const act = lastOf(p, 'actual'), pl = lastOf(p, 'plan'), b = db.baskets.find(x => x.id === p.basketId);
  const d = today(), now = roll(X, act, d), V = value(X, now, d);
  $('pt-kpi').innerHTML = [['ارزش کل امروز (میلیارد ریال)', f(V.nav / 1e9, 2), 'سهام با قیمت پایانی آخرین روز داده + نقد + سود دریافت‌نشده، پس از اعمال اقدامات شرکتی از آخرین ثبت.'], ['سهام', f(V.stock / 1e9, 2), 'ارزش بازار موجودی.'], ['نقد', f(V.cash / 1e9, 2), 'نقد پس از وصول سودهای پرداخت‌شده و پذیره‌نویسی‌ها.'], ['سود دریافت‌نشده', f(V.recv / 1e9, 2), 'سودهایی که روز استحقاق‌شان گذشته ولی هنوز پرداخت نشده‌اند (طلب).'], ['نماد', Object.keys(now.hold).length, 'تعداد نمادهای موجودی.'], ['آخرین ثبت', jdate(act.date), 'تاریخ آخرین موجودی ثبت‌شده.']]
    .map(([k, v, t]) => `<div class="kpi"${tip(t, DOCS)}><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');
  $('pt-lin').innerHTML = `<span><b>سبد</b> ${esc(b ? b.name : '(حذف‌شده)')}</span><span><b>ساخته‌شده</b> <span class="num">${esc(p.created)}</span></span><span><b>داده تا</b> <span class="num">${jdate(d)}</span></span>`;
  // انحراف
  if (pl) {
    const dv = deviation(X, pl.hold, act, act.date >= pl.date ? act.date : d);
    $('pt-dchip').textContent = `سهم فعال ${fmt(100 * dv.active, 1)}٪`; $('pt-dchip').dataset.tip = 'نصف مجموع |وزن واقعی − وزن برنامه|: ۰ یعنی دقیقاً طبق برنامه.';
    $('pt-dev').innerHTML = `<thead><tr><th>نماد</th><th class="n"${tip('تعداد در برنامه (' + jdate(pl.date) + ')')}>تعداد برنامه</th><th class="n"${tip('تعداد در آخرین ثبت (' + jdate(act.date) + ')')}>تعداد واقعی</th><th class="n">اختلاف تعداد</th><th class="n">وزن برنامه ٪</th><th class="n">وزن واقعی ٪</th><th class="n"${tip('واقعی منهای برنامه (واحد درصد).')}>اختلاف وزن</th></tr></thead><tbody>` +
      dv.rows.filter(r => r.qp || r.qa).slice(0, 300).map(r => `<tr><td>${esc(symOf(r.c))}</td><td class="n">${f(r.qp)}</td><td class="n">${f(r.qa)}</td><td class="n ${r.dq > 0 ? 'up' : r.dq < 0 ? 'down' : ''}">${r.dq ? sgn(r.dq, 0) : '0'}</td><td class="n">${fmt(100 * r.wp, 2)}</td><td class="n">${fmt(100 * r.wa, 2)}</td><td class="n ${Math.abs(r.dw) > 0.005 ? (r.dw > 0 ? 'up' : 'down') : ''}">${sgn(100 * r.dw, 2)}</td></tr>`).join('') + '</tbody>';
  } else { $('pt-dev').innerHTML = ''; $('pt-dchip').textContent = ''; }
  if (!$('rb-d').value) $('rb-d').value = jdate(d);
  if (!$('ac-d').value) $('ac-d').value = jdate(d);
  renderRebal(); renderHist();
}
function renderRebal() {
  const p = port(); if (!p) return;
  const act = lastOf(p, 'actual'), d2 = isoOf($('rb-d').value) || today();
  if (d2 < act.date) { $('rb-ord').innerHTML = `<tbody><tr><td class="mute" style="white-space:normal">تاریخ ریبالانس پیش از آخرین ثبت (${jdate(act.date)}) است.</td></tr></tbody>`; return; }
  ui.rb.bid = $('rb-b').value || p.basketId; ui.rb.min = +$('rb-min').value || 0; ui.rb.cb = +$('rb-cb').value || 0; ui.rb.cs = +$('rb-cs').value || 0; ui.rb.useRecv = $('rb-recv').checked;
  const b = db.baskets.find(x => x.id === ui.rb.bid); if (!b) return;
  const st = roll(X, act, d2, { rights: ui.rb.rights, unsure: ui.rb.unsure }), t = targetAt(b, d2);
  const o = orders(X, st, t.w, d2, { minPct: ui.rb.min / 100, costBuyBp: ui.rb.cb, costSellBp: ui.rb.cs, useRecv: ui.rb.useRecv });
  ui.res = { date: d2, st, t, o, bid: b.id, bname: b.name };
  const V = o.V;
  $('rb-kpi2').innerHTML = [['ارزش کل (میلیارد ریال)', f(V.nav / 1e9, 2), 'سهام + نقد + سود دریافت‌نشده در تاریخ ریبالانس.'], ['قابل سرمایه‌گذاری', f(o.invest / 1e9, 2), 'پایهٔ وزن هدف: سهام + نقد' + (ui.rb.useRecv ? ' + سود دریافت‌نشده' : '') + '.'], ['خرید', f(o.buy / 1e9, 2), 'ارزش سفارش‌های خرید.'], ['فروش', f(o.sell / 1e9, 2), 'ارزش سفارش‌های فروش.'], ['هزینهٔ تخمینی (میلیون ریال)', f(o.fee / 1e6), 'خرید × هزینهٔ خرید + فروش × هزینهٔ فروش.'], ['نقد پس از اجرا (میلیون ریال)', f(Math.round(o.after.cash / 1e6) || 0), 'نقد فعلی − خرید + فروش − هزینه. منفی یعنی کسری نقد.'], ['سهم فعال پیش از ریبالانس', fmt(100 * deviation(X, o.after.hold, st, d2).active, 1) + '٪', 'فاصلهٔ موجودی فعلی تا هدف.']]
    .map(([k, v, tt]) => `<div class="kpi"${tip(tt, DOCS)}><div class="k">${k}</div><div class="v ${k.startsWith('نقد پس') && o.after.cash < 0 ? 'down' : ''}">${v}</div></div>`).join('');
  // رویدادهای شرکتی میان آخرین ثبت و تاریخ ریبالانس
  const L = st.log;
  $('rb-ev').innerHTML = `<thead><tr><th${tip('روز رویداد (استحقاق، افزایش سرمایه یا پرداخت سود).')}>روز</th><th>نماد</th><th>رویداد</th><th class="n"${tip('اثر بر تعداد سهم.')}>تعداد</th><th class="n"${tip('اثر بر نقد یا طلب (ریال).')}>مبلغ (میلیون ریال)</th><th${tip('برای حق‌تقدم: پذیره‌نویسی (پرداخت ۱۰۰۰ ریال به‌ازای هر سهم و دریافت سهم) یا فروش حق‌تقدم. برای رویداد نامطمئن: اعمال یا نه.')}>انتخاب</th></tr></thead><tbody>` +
    (L.map(e => { const sy = esc(symOf(e.c));
      if (e.t === 'div') return `<tr><td class="num">${jdate(e.d)}</td><td>${sy}</td><td>سود نقدی ${fmt(e.dps, 0)} ریال × ${f(e.q)} ← طلب تا ${jdate(e.pay)}${e.est ? ' <span class="chip warn" data-tip="روز پرداخت اعلام نشده؛ استحقاق + میانهٔ ۹۶ روز.">برآورد</span>' : ''}</td><td class="n"></td><td class="n">${f(e.amt / 1e6, 1)}</td><td></td></tr>`;
      if (e.t === 'paid') return `<tr><td class="num">${jdate(e.d)}</td><td>${sy}</td><td>وصول سود${e.est ? ' (روز برآوردی)' : ''}</td><td class="n"></td><td class="n up">+${f(e.amt / 1e6, 1)}</td><td></td></tr>`;
      if (e.t === 'short') return `<tr><td class="num">${jdate(e.d)}</td><td>${sy}</td><td data-tip="نقد پیش از پذیره‌نویسی کمتر از مبلغ لازم بود؛ یا نقد بیاورید یا «فروش حق‌تقدم» را انتخاب کنید.">⚠ کسری نقد برای پذیره‌نویسی</td><td class="n"></td><td class="n down">${f(e.need / 1e6, 1)}</td><td></td></tr>`;
      if (e.t === 'glitch') return `<tr class="weak"><td class="num">${jdate(e.d)}</td><td>${sy}</td><td data-tip="سرمایه چند روز قبل به همین نسبت کم و حالا برگشته؛ خطای دادهٔ TSETMC است و اعمال نمی‌شود.">بازگشت خطای دادهٔ سرمایه (اعمال نشد)</td><td class="n"></td><td class="n"></td><td></td></tr>`;
      if (e.t === 'unsure') return `<tr><td class="num">${jdate(e.d)}</td><td>${sy}</td><td data-tip="قیمت مرجع با نسبت افزایش سرمایه نمی‌خواند؛ ممکن است رویداد دیگری هم‌زمان بوده باشد. اگر از کدال مطمئنید اعمال کنید.">افزایش سرمایهٔ نامطمئن ${fmt(100 * (e.g - 1), 0)}٪</td><td class="n"></td><td class="n"></td><td><label><input type="checkbox" data-uns="${esc(e.key)}"> اعمال شود</label></td></tr>`;
      const parts = [e.bonus ? `جایزه +${f(e.bonus)}` : '', e.nR ? `حق‌تقدم ${f(e.nR)}` : ''].filter(Boolean).join('، ');
      const cashM = e.nR ? (e.how === 'sub' ? -e.nR * (X.par || 1000) : e.nR * e.rv) : 0;
      return `<tr><td class="num">${jdate(e.d)}</td><td>${sy}</td><td>افزایش سرمایه ${fmt(100 * (e.g - 1), 0)}٪ (${parts || '—'})${e.unsure ? ' <span class="chip warn">نامطمئن</span>' : ''}</td><td class="n up">+${f(e.bonus + (e.how === 'sub' ? e.nR : 0))}</td><td class="n ${cashM < 0 ? 'down' : cashM > 0 ? 'up' : ''}">${cashM ? sgn(cashM / 1e6, 1) : ''}</td><td>${e.nR ? `<select data-rt="${esc(e.key)}"><option value="sub"${e.how === 'sub' ? ' selected' : ''} data-tip="پرداخت ۱۰۰۰ ریال برای هر حق‌تقدم و دریافت سهم.">پذیره‌نویسی</option><option value="sell"${e.how === 'sell' ? ' selected' : ''} data-tip="فروش حق‌تقدم به ارزش نظری (قیمت پس از رویداد − ۱۰۰۰) [تأیید لازم].">فروش حق‌تقدم</option></select>` : ''}</td></tr>`; }).join('') ||
      `<tr><td colspan="6" class="mute">از آخرین ثبت (${jdate(act.date)}) تا این تاریخ رویداد شرکتی برای موجودی نیست.</td></tr>`) + '</tbody>';
  $('rb-ev').querySelectorAll('select[data-rt]').forEach(s => { s.onchange = () => { ui.rb.rights[s.dataset.rt] = s.value; renderRebal(); }; });
  $('rb-ev').querySelectorAll('input[data-uns]').forEach(c => { c.checked = ui.rb.unsure.has(c.dataset.uns); c.onchange = () => { if (c.checked) ui.rb.unsure.add(c.dataset.uns); else ui.rb.unsure.delete(c.dataset.uns); renderRebal(); }; });
  const nc = L.filter(e => e.t === 'cap'), nR = nc.filter(e => e.nR > 0).length;
  $('rb-evcap').innerHTML = `<b>اقدامات شرکتی از ${jdate(act.date)} تا ${jdate(d2)}:</b> ${L.filter(e => e.t === 'div').length} سود نقدی، ${L.filter(e => e.t === 'paid').length} وصول سود، ${nc.length} افزایش سرمایه (${nR} با حق‌تقدم؛ پیش‌فرض پذیره‌نویسی، در ستون «انتخاب» عوض کنید)${L.some(e => e.t === 'unsure') ? '، ' + L.filter(e => e.t === 'unsure').length + ' رویداد نامطمئن (اعمال نشده)' : ''}.`;
  // سفارش‌ها
  const tr = new Set(o.frozen);
  $('rb-ordcap').innerHTML = `<b>سفارش‌ها:</b> ${o.orders.filter(x => x.side === 'sell').length} فروش و ${o.orders.filter(x => x.side === 'buy').length} خرید برای رسیدن به «${esc(b.name)}»؛ فروش‌ها اول اجرا شوند تا نقد خرید فراهم شود.`;
  $('rb-ord').innerHTML = `<thead><tr><th>#</th><th>اقدام</th><th>نماد</th><th class="n"${tip('تعداد سفارش.')}>تعداد</th><th class="n"${tip('قیمت پایانی آخرین روز معاملاتی تا تاریخ ریبالانس؛ پیش از ثبت سفارش، قیمت روز را جایگزین کنید.')}>قیمت مرجع</th><th class="n">ارزش (میلیون ریال)</th><th class="n">موجودی فعلی</th><th class="n">موجودی هدف</th><th class="n">وزن هدف ٪</th><th class="n"${tip('ارزش سفارش ÷ میانهٔ ارزش معاملات روزانهٔ ۶۳ روز اخیر (Lab). بالای ۱۰٪ قرمز.')}>٪ ارزش معاملات روزانه</th></tr></thead><tbody>` +
    (o.orders.map((x, i) => { const adv = advOf(x.c), part = adv > 0 ? x.val / adv : NaN; return `<tr><td class="rank">${i + 1}</td><td><span class="chip ${x.side === 'buy' ? 'ok' : 'bad'}">${x.side === 'buy' ? 'خرید' : 'فروش'}</span></td><td>${esc(symOf(x.c))}</td><td class="n">${f(x.qty)}</td><td class="n">${f(x.px)}</td><td class="n">${f(x.val / 1e6)}</td><td class="n">${f(x.q)}</td><td class="n">${f(x.tq)}</td><td class="n">${fmt(100 * x.w_tgt, 2)}</td><td class="n ${part > 0.1 ? 'down' : ''}">${part === part ? fmt(100 * part, 1) : '—'}</td></tr>`; }).join('') ||
      '<tr><td colspan="10" class="mute">موجودی با هدف یکی است؛ سفارشی لازم نیست.</td></tr>') + '</tbody>';
  $('rb-lin2').innerHTML = `<span><b${tip('recomputed: هدف سبد با آخرین سیگنال تا این تاریخ دوباره ساخته شد. snapshot: همان وزن لحظهٔ ذخیره.')}>هدف</b> ${esc(b.name)} · ${t.how === 'recomputed' ? 'بازسازی‌شده با سیگنال ' + jdate(t.asOf) : 'وزن ثابت (' + esc(t.note || '') + ')'}</span><span><b>قیمت</b> پایانی <span class="num">${jdate(X.dates[dayIdx(X, d2)])}</span></span>${o.frozen.length ? `<span><b${tip('این نمادها در روز ریبالانس معامله نشده‌اند؛ موجودی‌شان دست نمی‌خورد.')}>منجمد</b> ${o.frozen.map(symOf).slice(0, 8).join('، ')}</span>` : ''}${o.missing.length ? `<span><b>بدون قیمت</b> ${o.missing.map(symOf).slice(0, 8).join('، ')}</span>` : ''}${st.recv.length ? `<span><b${tip('سودهای دریافت‌نشده پس از تاریخ ریبالانس؛ پس از وصول، با ریبالانس بعدی سرمایه‌گذاری می‌شوند.')}>طلب سود</b> ${f(st.recv.reduce((s, r) => s + r.amt, 0) / 1e6)} میلیون ریال</span>` : ''}`;
  void tr;
}
function savePlan() {
  const p = port(), r = ui.res; if (!p || !r) return;
  p.events.push({ type: 'plan', date: r.date, basketId: r.bid, bname: r.bname, hold: r.o.after.hold, cash: r.o.after.cash, recv: r.st.recv, how: r.t.how, sigAsOf: r.t.asOf, rights: { ...ui.rb.rights }, unsure: [...ui.rb.unsure], note: `ریبالانس با «${r.bname}»: ${r.o.orders.length} سفارش` });
  DB.save(db);
  $('ac-hold').value = holdText(r.o.after.hold); $('ac-cash').value = Math.round(r.o.after.cash); $('ac-d').value = jdate(r.date);
  renderPort(); toast('برنامه ثبت شد؛ پس از اجرا، موجودی واقعی را در پنل D ثبت کنید');
}
function saveActual() {
  const p = port(); if (!p) return;
  const d = isoOf($('ac-d').value), { hold, bad } = parseHold($('ac-hold').value);
  if (!d) { toast('تاریخ نامعتبر'); return; }
  if (bad.length) { $('ac-note').textContent = 'نماد ناشناخته: ' + bad.slice(0, 6).join('، '); return; }
  const act = lastOf(p, 'actual'); if (act && d < act.date) { toast('تاریخ پیش از آخرین ثبت است'); return; }
  const pl = lastOf(p, 'plan'), rolled = act ? roll(X, act, d, { rights: (pl && pl.rights) || {}, unsure: new Set((pl && pl.unsure) || []) }) : null;
  const cashIn = $('ac-cash').value === '' ? (rolled ? rolled.cash : 0) : +$('ac-cash').value;
  p.events.push({ type: 'actual', date: d, hold, cash: cashIn, recv: rolled ? rolled.recv : [], pend: rolled ? rolled.pend : [], note: `${Object.keys(hold).length} نماد` });
  DB.save(db); $('ac-note').textContent = 'ثبت شد'; renderPort();
}
function calcCash() {
  const p = port(); if (!p) return;
  const d = isoOf($('ac-d').value), { hold, bad } = parseHold($('ac-hold').value), act = lastOf(p, 'actual');
  if (!d || bad.length || d < act.date) { toast(bad.length ? 'نماد ناشناخته: ' + bad.slice(0, 4).join('، ') : 'تاریخ نامعتبر'); return; }
  const pl = lastOf(p, 'plan'), st = roll(X, act, d, { rights: (pl && pl.rights) || {}, unsure: new Set((pl && pl.unsure) || []) }), pr = prep(X);
  let trade = 0, gross = 0;
  for (const c of new Set([...Object.keys(st.hold), ...Object.keys(hold)])) { const k = pr.ci.get(String(c)), px = k == null ? 0 : pxAt(X, k, d) || 0, dq = (hold[c] || 0) - (st.hold[c] || 0); trade += dq * px; gross += Math.abs(dq * px); }
  let buyV = 0, sellV = 0; for (const c of new Set([...Object.keys(st.hold), ...Object.keys(hold)])) { const k = pr.ci.get(String(c)), px = k == null ? 0 : pxAt(X, k, d) || 0, dq = (hold[c] || 0) - (st.hold[c] || 0); if (dq > 0) buyV += dq * px; else sellV -= dq * px; }
  const cash = st.cash - trade - buyV * ((+$('rb-cb').value || 0) / 1e4) - sellV * ((+$('rb-cs').value || 0) / 1e4);
  $('ac-cash').value = Math.round(cash); $('ac-note').textContent = `نقد برآوردی ${fmt(cash / 1e6, 0)} میلیون ریال (معاملات ${fmt(gross / 1e9, 2)} میلیارد ریال)`;
}
function renderHist() {
  const p = port(); if (!p) return;
  $('pt-hist').innerHTML = `<thead><tr><th>تاریخ</th><th>نوع</th><th>شرح</th><th class="n">نماد</th><th class="n">نقد (میلیون ریال)</th><th></th></tr></thead><tbody>` +
    p.events.map((e, i) => `<tr><td class="num">${jdate(e.date)}</td><td><span class="chip ${e.type === 'plan' ? 'info' : 'ok'}">${e.type === 'plan' ? 'برنامه' : 'اجراشده'}</span></td><td style="white-space:normal">${esc(e.note || '')}${e.type === 'plan' && e.how === 'snapshot' ? ' · وزن ثابت' : ''}</td><td class="n">${Object.keys(e.hold || {}).length}</td><td class="n">${f((e.cash || 0) / 1e6)}</td><td>${i === p.events.length - 1 && i > 0 ? `<button class="tool" data-undo="1"${tip('حذف آخرین ثبت.')}>×</button>` : ''}</td></tr>`).reverse().join('') + '</tbody>';
  const u = $('pt-hist').querySelector('[data-undo]'); if (u) u.onclick = () => { if (confirm('آخرین ثبت حذف شود؟')) { p.events.pop(); DB.save(db); renderPort(); } };
}

/* ── ثبت در روتر و API برای نماهای دیگر ── */
root.SIM_PF = { saveBasket, targetAt, db: () => db };
root.SIM_NEWVIEWS = Object.assign(root.SIM_NEWVIEWS || {}, {
  port: { id: 'v-port', init: () => ensurePFX(initPort), redraw: () => { } },
  bsk: { id: 'v-bsk', init: () => ensurePFX(initBaskets), redraw: () => { } },
});
})(typeof window !== 'undefined' ? window : globalThis);
