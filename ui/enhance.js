/* ماکت — «شاخص بهبودیافته»: هدف را با تیلت (صنعت، معیار Lab، اندازه، نوسان، آمیخته با هم‌وزن) و سقف وزن تغییر بده، سپس با N سهم بساز
   (N بزرگ‌ترین / طبقه‌ای / بهینه‌سازی TE) — همه در مرورگر. داده: window.SIM_REPX (tools/build_replica_x.py)، معیارها: window.SIM_LAB (Lab).
   موتور خالص است و در node هم آزمون می‌شود: node tools/replica_selftest.js
   ترتیب تیلت: اندازه w∝cap^γ ← آمیخته با هم‌وزن ← ضریب صنعت ← نوسان σ^−κ ← معیار e^{λz} ← سقف وزن (تکرارشونده) ← بازنرمال.
   منابع: Grinold & Kahn (۲۰۰۰) شاخص‌سازی بهبودیافته؛ MSCI/S&P شاخص‌های سقف‌دار؛ Amenc & Goltz (۲۰۱۳) وزن‌دهی تنوع‌بخش؛ Ledoit & Wolf (۲۰۰۴) انقباض کوواریانس. */
(function (root) {
'use strict';

/* ═════════════════ موتور (بدون DOM) ═════════════════ */
function b64(s, T) { const bin = atob(s), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return new T(u.buffer); }
const LIQ = { 0: [0, 0], 1: [50, 0.20], 2: [56, 0.40], 3: [60, 0.60] };      // (حداقل روز معامله از ۶۳، صدک ADV) — همان tools/build_replica_panel.py
const PART = 0.10;

function loadX(X) {
  if (X._ctx) return X._ctx;
  X._ctx = { k: X.k, T: X.days, ret: b64(X.ret, Float32Array), K: b64(X.K, Float32Array), C: b64(X.C, Float32Array), dates: X.dates, names: X.names, sectors: X.sectors, nH: X.n_rebal,
    months: X.months.map(m => ({ a: m.a, d: m.d, mcap: b64(m.mcap, Float32Array), adv: b64(m.adv, Float32Array), td: b64(m.td, Uint8Array), tr: m.tr ? b64(m.tr, Uint8Array) : null })), asof: X.asof };
  return X._ctx;
}
const eligIdx = (ctx, j) => { const m = ctx.months[j].mcap, o = []; for (let i = 0; i < ctx.k; i++) if (m[i] > 0) o.push(i); return Int32Array.from(o); };

function neutral(tl) { return !tl || (((tl.gamma == null ? 1 : tl.gamma) === 1) && !tl.ew && !tl.kappa && !(tl.lam && tl.sig) && !(tl.cap > 0) && !Object.values(tl.sec || {}).some(v => v)); }

/** وزن هدف تیلت‌شده b′ و وزن رسمی b₀ در ماه j؛ z (اختیاری) = امتیاز معیار برای هر نماد (طول k، NaN مجاز). */
function tilted(ctx, j, tl, z) {
  const k = ctx.k, mc = ctx.months[j].mcap, idx = eligIdx(ctx, j), a = ctx.months[j].a, b0 = new Float64Array(k), w = new Float64Array(k);
  let s0 = 0; for (const i of idx) s0 += mc[i];
  for (const i of idx) b0[i] = mc[i] / s0;
  tl = tl || {};
  const g = tl.gamma == null ? 1 : tl.gamma;
  let s = 0; for (const i of idx) { w[i] = g === 1 ? b0[i] : Math.pow(mc[i], g); s += w[i]; }
  for (const i of idx) w[i] /= s;
  if (tl.ew > 0) for (const i of idx) w[i] = (1 - tl.ew) * w[i] + tl.ew / idx.length;
  if (tl.sec) for (const i of idx) { const t = tl.sec[ctx.names[i].sec]; if (t) w[i] *= Math.max(0, 1 + t / 100); }
  if (tl.kappa) {                                                           // σ روزانهٔ ۲۵۲ روز پیش از a
    const sg = new Float64Array(k), arr = [];
    for (const i of idx) { let m = 0, v = 0; for (let t = a - 251; t <= a; t++) m += ctx.ret[t * k + i]; m /= 252; for (let t = a - 251; t <= a; t++) { const d = ctx.ret[t * k + i] - m; v += d * d; } sg[i] = Math.sqrt(v / 251) + 1e-6; arr.push(sg[i]); }
    arr.sort((p, q) => p - q); const med = arr[arr.length >> 1];
    for (const i of idx) w[i] *= Math.pow(sg[i] / med, -tl.kappa);
  }
  if (tl.lam && z) for (const i of idx) { const v = z[i]; if (v === v) w[i] *= Math.exp(tl.lam * Math.max(-3, Math.min(3, v))); }
  s = 0; for (const i of idx) s += w[i]; for (const i of idx) w[i] /= s;
  if (tl.cap > 0 && tl.cap * idx.length > 1.0001) {
    for (let it = 0; it < 50; it++) {
      let over = 0, free = 0; for (const i of idx) { if (w[i] > tl.cap) { over += w[i] - tl.cap; w[i] = tl.cap; } else free += w[i]; }
      if (over < 1e-12) break;
      for (const i of idx) if (w[i] < tl.cap) w[i] += over * w[i] / free;
    }
  }
  return { b: w, b0, idx };
}

const pct = (a, p) => { const n = a.length; if (!n) return NaN; const q = p * (n - 1), lo = Math.floor(q), hi = Math.ceil(q); return a[lo] + (a[hi] - a[lo]) * (q - lo); };
function candidates(ctx, j, idx, liq) {
  if (!liq) return idx;
  const [dmin, p] = LIQ[liq], m = ctx.months[j], adv = Array.from(idx, i => m.adv[i]).sort((x, y) => x - y), thr = pct(adv, p);
  const c = idx.filter(i => m.td[i] >= dmin && m.adv[i] >= thr);
  return c.length >= 3 ? c : idx;
}
const byB = (b, arr) => Array.from(arr).sort((x, y) => b[y] - b[x] || x - y);

function pickStrat(ctx, b, idx, cand, N) {
  const ws = new Map(); for (const i of idx) { const s = ctx.names[i].sec; ws.set(s, (ws.get(s) || 0) + b[i]); }
  const secs = [...ws.entries()].sort((p, q) => q[1] - p[1] || p[0] - q[0]), tot = secs.reduce((a, x) => a + x[1], 0), quota = new Map(); let sum = 0;
  for (const [s, v] of secs) { const q = Math.floor(v / tot * N + 1e-12); quota.set(s, q); sum += q; }
  const extra = Math.max(1, N - sum); secs.slice(0, extra).forEach(([s]) => quota.set(s, quota.get(s) + 1));
  const sel = [], by = new Map(); for (const i of byB(b, cand)) { const s = ctx.names[i].sec; (by.get(s) || by.set(s, []).get(s)).push(i); }
  for (const [s] of secs) { const q = quota.get(s); if (q > 0 && by.has(s)) sel.push(...by.get(s).slice(0, q)); }
  return sel.length ? sel.slice(0, N) : byB(b, cand).slice(0, N);
}

function projSimplex(v) {
  const n = v.length, u = Float64Array.from(v).sort().reverse(); let css = 0, rho = 0, th = 0;
  for (let i = 0; i < n; i++) { css += u[i]; const t = (css - 1) / (i + 1); if (u[i] - t > 0) { rho = i + 1; th = t; } }
  const o = new Float64Array(n); for (let i = 0; i < n; i++) o[i] = Math.max(v[i] - th, 0); return o;
}
/** انقباض Ledoit–Wolf (همان فرمول sklearn) از ماتریس مرکزشدهٔ T×p. */
function lwShrink(X, T, p) {
  let n4 = 0, trS = 0; const nt = new Float64Array(T);
  for (let t = 0; t < T; t++) { let s = 0; for (let i = 0; i < p; i++) { const v = X[t * p + i]; s += v * v; } nt[t] = s; n4 += s * s; trS += s; }
  trS /= T; const mu = trS / p; let fro = 0;
  for (let t = 0; t < T; t++) for (let s = t; s < T; s++) { let g = 0; for (let i = 0; i < p; i++) g += X[t * p + i] * X[s * p + i]; fro += (s === t ? 1 : 2) * g * g; }
  fro /= T * T;
  const beta = (n4 - T * fro) / (T * T), delta = fro - 2 * mu * trS + p * mu * mu, bb = Math.min(beta, delta);
  return { sh: delta > 0 ? Math.max(0, bb / delta) : 0, mu };
}
/** min ½(w−b)ᵀΣ(w−b) روی سیمپلکس زیرمجموعه؛ Σ = (1−δ)S + δμI. R: ماتریس مرکزشدهٔ T×m (زیرمجموعه)، y = R_all·b، bs = b زیرمجموعه. */
function solveOpt(R, T, m, y, bs, sh, mu, iters) {
  if (m <= 1) return Float64Array.from({ length: m }, () => 1);
  const c1 = (1 - sh) / T;
  let v = new Float64Array(m).fill(1 / m), q = new Float64Array(m);
  for (let i = 0; i < 12; i++) {                                              // λmax(RᵀR) با توان
    const t = new Float64Array(T); for (let r = 0; r < T; r++) { let s = 0; for (let i2 = 0; i2 < m; i2++) s += R[r * m + i2] * v[i2]; t[r] = s; }
    q.fill(0); for (let r = 0; r < T; r++) for (let i2 = 0; i2 < m; i2++) q[i2] += R[r * m + i2] * t[r];
    let nr = 0; for (let i2 = 0; i2 < m; i2++) nr += q[i2] * q[i2]; nr = Math.sqrt(nr) || 1; for (let i2 = 0; i2 < m; i2++) v[i2] = q[i2] / nr;
  }
  let lam = 0; { const t = new Float64Array(T); for (let r = 0; r < T; r++) { let s = 0; for (let i2 = 0; i2 < m; i2++) s += R[r * m + i2] * v[i2]; t[r] = s; } for (let r = 0; r < T; r++) lam += t[r] * t[r]; }
  const Lc = c1 * lam + sh * mu + 1e-12, step = 1 / Lc;
  const bsum = bs.reduce((a, x) => a + x, 0) || 1;
  let w = Float64Array.from(bs, x => x / bsum), z = Float64Array.from(w), tk = 1;
  const grad = (x) => { const res = new Float64Array(T); for (let r = 0; r < T; r++) { let s = -y[r]; for (let i = 0; i < m; i++) s += R[r * m + i] * x[i]; res[r] = s; } const g = new Float64Array(m); for (let r = 0; r < T; r++) { const e = res[r]; for (let i = 0; i < m; i++) g[i] += R[r * m + i] * e; } for (let i = 0; i < m; i++) g[i] = c1 * g[i] + sh * mu * (x[i] - bs[i]); return g; };
  for (let it = 0; it < iters; it++) {
    const g = grad(z), wn = projSimplex(Float64Array.from(z, (x, i) => x - step * g[i])), tn = (1 + Math.sqrt(1 + 4 * tk * tk)) / 2;
    let d = 0; for (let i = 0; i < m; i++) d += Math.abs(wn[i] - w[i]);
    for (let i = 0; i < m; i++) z[i] = wn[i] + (tk - 1) / tn * (wn[i] - w[i]);
    w = wn; tk = tn; if (d < 1e-7) break;
  }
  return w;
}
function pickOpt(ctx, b, idx, cand, N, j, iters) {
  const k = ctx.k, a = ctx.months[j].a, T = 252, p = idx.length, t0 = a - 251;
  // مرکزسازی ماتریس کل واجدان (برای δ و y)
  const Xc = new Float64Array(T * p), mean = new Float64Array(p);
  for (let c = 0; c < p; c++) { let s = 0; for (let t = 0; t < T; t++) s += ctx.ret[(t0 + t) * k + idx[c]]; mean[c] = s / T; }
  for (let t = 0; t < T; t++) for (let c = 0; c < p; c++) Xc[t * p + c] = ctx.ret[(t0 + t) * k + idx[c]] - mean[c];
  const { sh, mu } = lwShrink(Xc, T, p), y = new Float64Array(T), col = new Map(Array.from(idx, (i, c) => [i, c]));
  for (let t = 0; t < T; t++) { let s = 0; for (let c = 0; c < p; c++) s += Xc[t * p + c] * b[idx[c]]; y[t] = s; }
  const sub = arr => { const m = arr.length, R = new Float64Array(T * m); arr.forEach((i, c2) => { const c = col.get(i); for (let t = 0; t < T; t++) R[t * m + c2] = Xc[t * p + c]; }); return R; };
  let pool = byB(b, cand).slice(0, 3 * N), sel;
  if (cand.length <= N) sel = Array.from(cand);
  else { const w0 = solveOpt(sub(pool), T, pool.length, y, pool.map(i => b[i]), sh, mu, iters); sel = pool.map((i, c) => [i, w0[c]]).sort((x, y2) => y2[1] - x[1]).slice(0, N).map(x => x[0]); }
  const w1 = solveOpt(sub(sel), T, sel.length, y, sel.map(i => b[i]), sh, mu, iters * 2);
  const keep = sel.map((i, c) => [i, w1[c]]).filter(x => x[1] > 1e-6), s = keep.reduce((aa, x) => aa + x[1], 0);
  return { sel: keep.map(x => x[0]), w: keep.map(x => x[1] / s) };
}
function select(ctx, method, N, liq, bt, j, iters) {
  const { b, idx } = bt, cand = candidates(ctx, j, idx, liq);
  if (method === 'opt') return pickOpt(ctx, b, idx, cand, N, j, iters || 120);
  const sel = method === 'strat' ? pickStrat(ctx, b, idx, cand, N) : byB(b, cand).slice(0, N);
  const s = sel.reduce((a, i) => a + b[i], 0);
  return { sel, w: sel.map(i => b[i] / s) };
}

/** سری ماهانه و روزانهٔ ماکت (بدون اهرم) و «هدف تیلت‌شده» (خرید همهٔ واجدان با b′)؛ فرمت سازگار با builder.js. progress(j, nm) اختیاری. */
async function runEnh(ctx, cfg, zFor, progress) {
  const k = ctx.k, nm = ctx.nH, d0 = ctx.months[0].a + 1, L = ctx.T - d0, r = new Float64Array(L), tr = new Float64Array(L);
  const to = [], beta = [], cap = [], sel = [], bsm = [], tto = [];
  let wp = new Float64Array(k), tp = new Float64Array(k);
  for (let j = 0; j < nm; j++) {
    const a = ctx.months[j].a, end = j + 1 < nm ? ctx.months[j + 1].a : ctx.T - 1;
    const bt = tilted(ctx, j, cfg.tilt, zFor ? zFor(j) : null), S0 = select(ctx, cfg.method, cfg.N, cfg.liq, bt, j, cfg.iters);
    let wf = new Float64Array(k); S0.sel.forEach((i, c) => { wf[i] = S0.w[c]; });
    const capT = Math.min(...S0.sel.map((i, c) => PART * ctx.months[j].adv[i] / Math.max(S0.w[c], 1e-9)));   // ظرفیت ساخت هدف از نقد (پیش از انجماد)
    const trm = ctx.months[j].tr;
    if (trm) {                                                     // قاعدهٔ A2 (همان tools/build_replica_panel.py و construction.freeze_untradable)
      let s = 0; for (let i = 0; i < k; i++) { if (!trm[i] && !(wp[i] > 0)) wf[i] = 0; s += wf[i]; }
      if (s > 0) for (let i = 0; i < k; i++) wf[i] /= s;
      let fz = 0, any = false; for (let i = 0; i < k; i++) if (wp[i] > 0 && !trm[i]) { any = true; fz += wp[i]; }
      if (any) {
        let s2 = 0; for (let i = 0; i < k; i++) { if (wp[i] > 0 && !trm[i]) wf[i] = 0; s2 += wf[i]; }
        const sc = s2 > 0 ? Math.max(1 - fz, 0) / s2 : 0; for (let i = 0; i < k; i++) wf[i] = (wp[i] > 0 && !trm[i]) ? wp[i] : wf[i] * sc;
      }
    }
    const S = { sel: [], w: [] }; for (let i = 0; i < k; i++) if (wf[i] > 0) { S.sel.push(i); S.w.push(wf[i]); }
    let tt = 0; for (let i = 0; i < k; i++) tt += Math.abs(wf[i] - wp[i]); to.push(0.5 * tt);
    let tt2 = 0; for (let i = 0; i < k; i++) tt2 += Math.abs(bt.b[i] - tp[i]); tto.push(0.5 * tt2);
    // بتای ۲۵۲ روزه روی شاخص رسمی
    const rs = new Float64Array(252), ri = new Float64Array(252); let ms = 0, mi = 0;
    for (let t = 0; t < 252; t++) { let s = 0; for (const i of S.sel) s += ctx.ret[(a - 251 + t) * k + i] * wf[i]; rs[t] = s; ri[t] = ctx.K[a - 251 + t]; ms += s; mi += ctx.K[a - 251 + t]; }
    ms /= 252; mi /= 252; let cv = 0, vi = 0; for (let t = 0; t < 252; t++) { cv += (rs[t] - ms) * (ri[t] - mi); vi += (ri[t] - mi) ** 2; } beta.push(cv / Math.max(vi, 1e-18));
    cap.push(capT);
    sel.push([S.sel.slice(), S.w.map(x => Math.round(x * 1e5))]);
    bsm.push([Array.from(bt.idx), Array.from(bt.idx, i => Math.round(bt.b[i] * 1e5)), Array.from(bt.idx, i => Math.round(bt.b0[i] * 1e5))]);
    const wv = Float64Array.from(wf), tv = Float64Array.from(bt.b);
    for (let t = a + 1; t <= end; t++) {
      let v0 = 0, v1 = 0; for (const i of S.sel) { v0 += wv[i]; wv[i] *= 1 + ctx.ret[t * k + i]; v1 += wv[i]; } r[t - d0] = v1 / v0 - 1;
      let u0 = 0, u1 = 0; for (const i of bt.idx) { u0 += tv[i]; tv[i] *= 1 + ctx.ret[t * k + i]; u1 += tv[i]; } tr[t - d0] = u1 / u0 - 1;
    }
    let sw = 0, st = 0; for (const i of S.sel) sw += wv[i]; for (const i of bt.idx) st += tv[i];
    wp = new Float64Array(k); for (const i of S.sel) wp[i] = wv[i] / sw;
    tp = new Float64Array(k); for (const i of bt.idx) tp[i] = tv[i] / st;
    if (progress && (j % 3 === 2 || j === nm - 1)) await progress(j + 1, nm);
  }
  // لایهٔ زنده (آخرین روز)
  const jl = nm, btl = tilted(ctx, jl, cfg.tilt, zFor ? zFor(jl) : null), Sl = select(ctx, cfg.method, cfg.N, cfg.liq, btl, jl, cfg.iters);
  const live = [Sl.sel.slice(), Sl.w.map(x => Math.round(x * 1e5)), Math.min(...Sl.sel.map((i, c) => PART * ctx.months[jl].adv[i] / Math.max(Sl.w[c], 1e-9)))];
  const adv = {}; for (const i of btl.idx) adv[i] = ctx.months[jl].adv[i];
  const R = {
    dates: ctx.dates.slice(d0), mstart: ctx.months.slice(0, nm).map(m => m.a - ctx.months[0].a), sig: ctx.months.slice(0, nm).map(m => m.d), asof: ctx.asof, part: PART,
    names: ctx.names.map(n => ({ c: n.c, s: n.s, sec: ctx.sectors[n.sec] })), b: bsm.map(x => [x[0], x[1]]), b0: bsm.map(x => [x[0], x[2]]),
    live_b: [Array.from(btl.idx), Array.from(btl.idx, i => Math.round(btl.b[i] * 1e5))], live_b0: [Array.from(btl.idx), Array.from(btl.idx, i => Math.round(btl.b0[i] * 1e5))], adv_live: adv,
    Ns: [cfg.N], liq: { 0: {}, 1: {}, 2: {}, 3: {} }, methods: ['top', 'strat', 'opt'], configs: { enh: { to, beta, cap, sel, live } }, n_elig: [],
    _p: { K: ctx.K.subarray(d0), C: ctx.C.subarray(d0), cfg: { enh: r } }, target: { r: tr, to: tto },
  };
  return R;
}

/* ═════════════════ رابط ═════════════════ */
if (typeof window === 'undefined' || typeof document === 'undefined') { root.SIM_ENH = { loadX, tilted, select, runEnh, neutral, candidates }; if (typeof module !== 'undefined' && module.exports) module.exports = root.SIM_ENH; return; }
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const tip = t => ` data-tip="${esc(t)}"`;
const f = (x, d = 1) => x == null || x !== x ? '—' : fmt(x, d);
const sg = (x, d = 1) => x == null || x !== x ? '—' : sgn(x, d);
const S = { gamma: 1, ew: 0, kappa: 0, sig: '', lam: 0.5, cap: 0, sec: {}, iters: 120 };
let ctx = null, host = null, run = null, labCtx = null;

function loadScript(src) { return new Promise((ok, no) => { const s = document.createElement('script'); s.src = src; s.onload = ok; s.onerror = () => no(new Error(src)); document.head.appendChild(s); }); }
async function needX() { if (!root.SIM_REPX) await loadScript('data/replica_x.js'); ctx = loadX(root.SIM_REPX); return ctx; }
async function needLab() {
  if (labCtx) return labCtx;
  await new Promise(ok => root.SIM_ENSURE_LAB(ok));
  const LE = root.LabEngine, L = root.SIM_LAB, c = LE.load(L), me = L.months_end.map(s => !s ? NaN : Math.round(Date.UTC(+s.slice(0, 4), +s.slice(5, 7) - 1, +s.slice(8, 10)) / 864e5));
  labCtx = { LE, L, c, me, byC: new Map(L.codes.map((x, i) => [String(x.c), i])) }; return labCtx;
}
function zProvider(name) {
  if (!name || !labCtx) return null;
  const { LE, c, me, byC, L } = labCtx, cache = new Map();
  return j => {
    if (cache.has(j)) return cache.get(j);
    const d = ctx.months[j].d; let r = me.indexOf(d); if (r < 0) r = j >= ctx.nH ? L.rows - 1 : me.reduce((bst, x, i) => Math.abs(x - d) < Math.abs(me[bst] - d) ? i : bst, 0);
    const zl = LE.zAt(c, name, r), z = new Float64Array(ctx.k).fill(NaN); ctx.names.forEach((n, i) => { const q = byC.get(String(n.c)); if (q != null) z[i] = zl[q]; });
    cache.set(j, z); return z;
  };
}

function mount(el, api) {
  host = el;
  el.innerHTML = `
  <section class="panel" style="--lg:var(--lg-d, var(--lg-a))">
    <div class="panel-head"><span class="lg-badge">+</span><span class="panel-title"${tip('هدف را از «شاخص كل» رسمی تغییر بده (تیلت صنعت یا معیار، سقف وزن، آمیخته با هم‌وزن…) و با همان N سهم بساز. TE هدف در برابر شاخص همان ریسک فعال شماست.')}>شاخص بهبودیافته · تیلت و قیدها</span><span class="chip" id="en-chip"${tip('وضعیت: شاخص رسمی یا هدف تیلت‌شده.')}>شاخص رسمی</span></div>
    <div class="lb-note">بالای نما: روش، تعداد سهام و نقدشوندگی همان است که در پنل ماکت‌ساز انتخاب کرده‌اید؛ اینجا فقط <b>هدف</b> را عوض می‌کنید. نتایج درون‌نمونه‌اند: تیلتی که پس از دیدن نتیجه انتخاب شود اعتبار آماری ندارد.</div>
    <div class="ctl">
      <label${tip('وزن ∝ ارزش بازار^γ. ۱ = ارزش‌وزن (شاخص)، ۰٫۵ = ریشهٔ ارزش بازار، ۰ = هم‌وزن. وزن‌دهی تنوع‌بخش در ادبیات.')}>توان اندازه γ <input type="number" id="en-gamma" value="1" min="0" max="1" step="0.1"></label>
      <label${tip('آمیختن با هم‌وزن: w = (۱−α)·شاخص + α·(۱/n). غلظت را کم و دم کوچک‌ها را زیاد می‌کند.')}>آمیخته با هم‌وزن α <input type="number" id="en-ew" value="0" min="0" max="1" step="0.1"></label>
      <label${tip('سقف وزن هر نماد پس از همهٔ تیلت‌ها (٪). ۰ = بدون سقف. شاخص‌های سقف‌دار MSCI/S&P.')}>سقف نماد ٪ <input type="number" id="en-cap" value="0" min="0" max="50" step="1"></label>
      <label${tip('تیلت کم‌نوسان: وزن × (σ/میانه)^−κ با σ روزانهٔ ۲۵۲ روز. κ مثبت کم‌نوسان‌ها را سنگین می‌کند (Haugen؛ Frazzini–Pedersen).')}>کم‌نوسان κ <input type="number" id="en-kappa" value="0" min="-2" max="3" step="0.25"></label>
    </div>
    <div class="ctl">
      <label${tip('تیلت بر پایهٔ یکی از معیارهای Lab (Z مقطعی هر ماه): وزن × e^{λz}. اولین استفاده Lab را بارگذاری می‌کند.')}>معیار <select id="en-sig"><option value="">— بدون —</option></select></label>
      <label${tip('شدت تیلت معیار؛ λ = ۰٫۵ یعنی یک انحراف معیار بالاتر، وزن ≈ ۱٫۶ برابر.')}>شدت λ <input type="number" id="en-lam" value="0.5" min="-2" max="2" step="0.25"></label>
      <button class="tool" id="en-run"${tip('هدف تیلت‌شده را می‌سازد و با N سهم ماکت می‌کند؛ بهینه‌سازی در مرورگر چند ثانیه طول می‌کشد.')}>محاسبه</button>
      <button class="tool" id="en-reset"${tip('بازگشت به «شاخص كل» رسمی بدون تیلت.')}>بازنشانی</button>
      <span class="mute" id="en-prog"></span>
    </div>
    <details><summary class="mute"${tip('ضریب نسبی هر صنعت روی وزن شاخص: ۰ بدون تغییر، ۵۰+ یعنی ۱٫۵ برابر، ۱۰۰− یعنی حذف.')} style="cursor:pointer;padding:6px 14px">تیلت صنعت (انحراف مثبت/منفی نسبت به وزن شاخص)</summary><div class="panel-body scroll" style="max-height:300px"><table class="dt" id="en-sec"></table></div></details>
    <div class="kpis" id="en-kpi"></div>
    <div class="lineage" id="en-lin"></div>
  </section>`;
  const num = (id, key, to) => { $(id).onchange = e => { S[key] = +e.target.value / (to || 1); }; };
  num('en-gamma', 'gamma'); num('en-ew', 'ew'); num('en-cap', 'cap', 100); num('en-kappa', 'kappa'); num('en-lam', 'lam');
  $('en-sig').onchange = e => { S.sig = e.target.value; };
  $('en-run').onclick = () => go(api);
  $('en-reset').onclick = () => { Object.assign(S, { gamma: 1, ew: 0, kappa: 0, cap: 0, sec: {}, sig: '' }); ['en-gamma', 'en-ew', 'en-cap', 'en-kappa'].forEach((i, n) => { $(i).value = [1, 0, 0, 0][n]; }); $('en-sig').value = ''; run = null; secTable(); api.set(null); $('en-chip').textContent = 'شاخص رسمی'; $('en-kpi').innerHTML = ''; $('en-lin').innerHTML = ''; };
  needX().then(secTable);
  if (root.SIM_REP && root.SIM_ENSURE_LAB) root.SIM_ENSURE_LAB(() => { const L = root.SIM_LAB; $('en-sig').innerHTML = '<option value="">— بدون —</option>' + L.signals.map(s => `<option value="${esc(s.name)}">${esc(s.fa || s.name)}</option>`).join(''); });
}
function secTable() {
  if (!ctx) return;
  const j = ctx.nH, mc = ctx.months[j].mcap, w = new Map(); let t = 0;
  for (let i = 0; i < ctx.k; i++) if (mc[i] > 0) { w.set(ctx.names[i].sec, (w.get(ctx.names[i].sec) || 0) + mc[i]); t += mc[i]; }
  const rows = [...w.entries()].sort((a, b) => b[1] - a[1]);
  $('en-sec').innerHTML = `<thead><tr><th${tip('صنعت.')}>صنعت</th><th class="n"${tip('وزن صنعت در شاخص (آخرین روز).')}>وزن شاخص ٪</th><th class="n"${tip('تیلت نسبی ٪: −۱۰۰ حذف، ۰ بدون تغییر، +۵۰ یعنی ۱٫۵ برابر.')}>تیلت ٪</th></tr></thead><tbody>` +
    rows.map(([s, v]) => `<tr><td>${esc(ctx.sectors[s])}</td><td class="n">${f(100 * v / t, 1)}</td><td class="n"><input type="number" data-s="${s}" value="${S.sec[s] || 0}" min="-100" max="300" step="10" style="width:70px"></td></tr>`).join('') + '</tbody>';
  $('en-sec').querySelectorAll('input').forEach(i => { i.onchange = e => { S.sec[+e.target.dataset.s] = +e.target.value; }; });
}

async function go(api) {
  const btn = $('en-run'); btn.disabled = true; const prog = $('en-prog');
  try {
    prog.textContent = 'بارگذاری داده…'; await needX();
    if (S.sig && S.lam) { prog.textContent = 'بارگذاری معیارهای Lab…'; await needLab(); }
    const st = api.state(), cfg = { tilt: { gamma: S.gamma, ew: S.ew, kappa: S.kappa, cap: S.cap, sig: S.sig, lam: S.sig ? S.lam : 0, sec: S.sec }, method: st.method, N: st.N, liq: st.liq, iters: S.iters };
    const t0 = performance.now();
    const R = await runEnh(ctx, cfg, S.sig ? zProvider(S.sig) : null, (j, n) => new Promise(ok => { prog.textContent = `ماه ${j}/${n}…`; setTimeout(ok, 0); }));
    prog.textContent = `انجام شد (${f((performance.now() - t0) / 1000, 1)} ثانیه)`;
    run = { R, cfg }; api.set(R); summary(R, cfg);
    $('en-chip').textContent = neutral(cfg.tilt) ? 'شاخص رسمی (محاسبهٔ مرورگر)' : 'هدف تیلت‌شده';
  } catch (e) { prog.textContent = 'خطا: ' + (e && e.message || e); console.error(e); }
  btn.disabled = false;
}
function summary(R, cfg) {
  const E = root.SIM_RB, o = { mode: 'none', L: 1, rb: 0.3, rc: 0, cost: 0, j0: 0 };
  const nav = new Float64Array(R.dates.length); let v = 1; nav[0] = 1; for (let t = 1; t < nav.length; t++) { v *= 1 + R.target.r[t]; nav[t] = v; }
  const mT = E.metrics(R, { nav, t0: 0 }), m = E.metrics(R, E.simulate(R, 'enh', { ...o, cost: 100 }));
  // سری ماهانهٔ تفاضل هدف−شاخص برای t ساده
  const p = E.prep(R), mon = [];
  for (let j = 0; j < R.mstart.length; j++) { const a = R.mstart[j], e = j + 1 < R.mstart.length ? R.mstart[j + 1] : R.dates.length; let g = 1, h = 1; for (let t = a; t < e; t++) { g *= 1 + R.target.r[t]; h *= 1 + p.K[t]; } mon.push(g - h); }
  const mu = mon.reduce((a, x) => a + x, 0) / mon.length, sd = Math.sqrt(mon.reduce((a, x) => a + (x - mu) ** 2, 0) / (mon.length - 1)), tstat = mu / (sd / Math.sqrt(mon.length));
  const to = R.target.to.slice(1); const tov = to.reduce((a, x) => a + x, 0) / to.length;
  const kp = [['TE هدف در برابر شاخص', f(mT.te, 2) + '٪', 'ریسک فعال تیلت: انحراف معیار تفاضل بازده روزانهٔ هدف تیلت‌شده (خرید همهٔ واجدان) و «شاخص كل» رسمی × √۲۵۲.'],
    ['بازده اضافی هدف (سالانه)', sg(mT.gap) + ' واحد', 'بازده سالانهٔ هدف منهای شاخص رسمی، بدون هزینه. درون‌نمونه است.'],
    ['نسبت اطلاعات', f(mT.gap / mT.te, 2), 'بازده اضافی ÷ TE. بالای ۰٫۵ در ادبیات خوب است، ولی اینجا درون‌نمونه است.'],
    ['t تفاضل ماهانه', f(tstat, 2), 'آمارهٔ t میانگین تفاضل ماهانهٔ هدف−شاخص (ساده، بدون تصحیح چندگانگی). |t| < ۲ یعنی بی‌معنا؛ تیلت‌های آزموده‌شده را در Lab با Bonferroni/DSR بسنجید.'],
    ['گردش ماهانهٔ هدف', f(100 * tov, 1) + '٪', 'گردش یک‌طرفهٔ ماهانهٔ خریدن همهٔ هدف (پیش از نمونه‌گیری).'],
    ['TE ماکت در برابر شاخص', f(m.te, 2) + '٪', 'ماکت N‌سهمی هدف در برابر «شاخص كل» (با هزینهٔ ۱۰۰bp، بدون اهرم).']];
  $('en-kpi').innerHTML = kp.map(([k, v, t]) => `<div class="kpi"${tip(t)}><div class="k"${tip(t)}>${k}</div><div class="v num">${v}</div></div>`).join('');
  const t = cfg.tilt, parts = [];
  if (t.gamma !== 1) parts.push(`توان اندازه ${t.gamma}`); if (t.ew) parts.push(`آمیخته با هم‌وزن ${f(100 * t.ew, 0)}٪`); if (t.cap) parts.push(`سقف ${f(100 * t.cap, 0)}٪`); if (t.kappa) parts.push(`کم‌نوسان κ=${t.kappa}`);
  if (t.lam && t.sig) parts.push(`معیار ${t.sig} λ=${t.lam}`);
  const sc = Object.entries(t.sec).filter(([, v]) => v).map(([s, v]) => `${ctx.sectors[s]} ${v > 0 ? '+' : ''}${v}٪`); if (sc.length) parts.push('صنعت: ' + sc.join('، '));
  $('en-lin').innerHTML = `<span><b${tip('تیلت‌های اعمال‌شده روی هدف.')}>تیلت</b> ${parts.length ? esc(parts.join(' · ')) : 'هیچ؛ هدف = شاخص رسمی'}</span><span><b${tip('خطاهای پایین‌تر (نمودار، KPI و جدول سال‌ها) اکنون ماکت را در برابر شاخص رسمی می‌سنجند، نه در برابر هدف تیلت‌شده.')}>مرجع</b> شاخص كل رسمی؛ «وزن شاخص» در جدول پرتفوی = وزن هدف تیلت‌شده</span>`;
}

root.SIM_ENH_MOUNT = mount;
root.SIM_ENH_STALE = () => { if (!host) return; $('en-chip').textContent = 'تنظیمات نمونه عوض شد؛ دوباره «محاسبه» بزنید'; $('en-kpi').innerHTML = ''; $('en-lin').innerHTML = ''; };
root.SIM_ENH = { loadX, tilted, select, runEnh, neutral, candidates };
})(typeof window !== 'undefined' ? window : globalThis);
