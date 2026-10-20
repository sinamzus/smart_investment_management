/* همتا — موتور بک‌تست مرورگری «میز پژوهش» (فصل ۱۴).
   همان قرارداد tools/construction.py: ریبالانس در پایان ماه شمسی، خرید و نگهداری درون ماه، گردش ½Σ|w−w_drift|، هزینه = گردش × رفت‌وبرگشت.
   فقط الگوریتم‌های بدون کوواریانس در مرورگر اجرا می‌شوند؛ min-var/ERC/HRP/MaxDiv/MVO در کتابخانهٔ پایتون (library) هستند.
   امتیازها با دقت 1/40 Z کوانتیزه‌اند (Int8)؛ برای هم‌ارزی با پایتون ← node tools/lab_selftest.js */
(function (root) {
'use strict';
const NaNv = NaN;

function b64(s, Type) { const bin = atob(s), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return new Type(u.buffer); }

function load(L) {
  const rows = L.rows, k = L.k;
  const ctx = { L, rows, k, Z: {}, sec: new Uint8Array(k), mkt: new Uint8Array(k), sym: L.codes.map(c => c.p || c.s), cache: { ic: {}, z: {} } };
  L.codes.forEach((c, i) => { ctx.sec[i] = c.sec; ctx.mkt[i] = c.m; });
  ctx.ok = b64(L.ok, Uint8Array);
  ctx.tr = L.tr ? b64(L.tr, Uint8Array) : null;                       // قابل‌معامله در روز اجرا (A2)؛ نبود = همه
  ctx.secHist = (L.sec_hist || []).map(h => ({ i: h.i, to: h.to, sec: h.sec }));   // تاریخچهٔ تغییر صنعت (B4)
  const fw = b64(L.fw, Float32Array); ctx.fw = fw;
  ctx.mcap = b64(L.mcap, Float32Array); ctx.vol = b64(L.vol, Float32Array); ctx.adv = b64(L.adv, Float32Array);
  L.signals.forEach(s => { ctx.Z[s.name] = { meta: s, z: b64(s.z, Int8Array) }; });
  ctx.use = L.use;                                   // سطرهای قابل‌ارزیابی (ماه‌های بعد از ۲۰۱۶-۰۳)
  return ctx;
}

const zAt = (ctx, name, r) => { const a = ctx.Z[name].z, out = new Float64Array(ctx.k), o = r * ctx.k; for (let i = 0; i < ctx.k; i++) { const v = a[o + i]; out[i] = v === -128 ? NaNv : v / 40; } return out; };
const fwAt = (ctx, r) => { const out = new Float64Array(ctx.k), o = r * ctx.k; for (let i = 0; i < ctx.k; i++) { const v = ctx.fw[o + i]; out[i] = v <= -5 ? NaNv : v; } return out; };
const okAt = (ctx, r) => { const out = new Uint8Array(ctx.k), o = r * ctx.k; for (let i = 0; i < ctx.k; i++) out[i] = ctx.ok[o + i]; return out; };
const trAt = (ctx, r) => { const out = new Uint8Array(ctx.k).fill(1); if (!ctx.tr) return out; const o = r * ctx.k; for (let i = 0; i < ctx.k; i++) out[i] = ctx.tr[o + i] & 1; return out; };
/* قفل صف در روز اجرا (بیت ۲: صف خرید، بیت ۴: صف فروش؛ tools/build_lab.export) — همان signals.Market.locks */
const lkAt = (ctx, r) => { const lb = new Uint8Array(ctx.k), ls = new Uint8Array(ctx.k); if (!ctx.tr) return { lb, ls }; const o = r * ctx.k; for (let i = 0; i < ctx.k; i++) { lb[i] = (ctx.tr[o + i] >> 1) & 1; ls[i] = (ctx.tr[o + i] >> 2) & 1; } return { lb, ls }; };
const secAt = (ctx, r) => { if (!ctx.secHist.length) return ctx.sec; const d = ctx.L.sig_dates[r], out = Uint8Array.from(ctx.sec); for (const h of ctx.secHist) if (d < h.to) out[h.i] = h.sec; return out; };
function freezeUntradable(w, prev, tr, k) {         // نماد نگه‌داشته‌شدهٔ بی‌معامله در روز اجرا فروختنی نیست (tools/construction.freeze_untradable)
  let fz = 0, any = false; for (let i = 0; i < k; i++) if (prev[i] > 0 && !tr[i]) { any = true; fz += prev[i]; }
  if (!any) return w;
  const out = new Float64Array(k); let s = 0; for (let i = 0; i < k; i++) { out[i] = (prev[i] > 0 && !tr[i]) ? 0 : w[i]; s += out[i]; }
  const sc = s > 0 ? Math.max(1 - fz, 0) / s : 0; for (let i = 0; i < k; i++) out[i] = (prev[i] > 0 && !tr[i]) ? prev[i] : out[i] * sc;
  return out;
}

/** همان construction.freeze_locked: بی‌معامله منجمد؛ صف خرید بیش از وزن فعلی خریده نمی‌شود؛ صف فروش کمتر از آن فروخته نمی‌شود */
function freezeLocked(w, prev, tr, lb, ls, k) {
  let out = freezeUntradable(w, prev, tr, k);
  if (!prev || !lb) return out;
  let ps = 0; for (let i = 0; i < k; i++) ps += prev[i]; if (ps <= 0) return out;
  const fixed = new Uint8Array(k); for (let i = 0; i < k; i++) fixed[i] = prev[i] > 0 && !tr[i] ? 1 : 0;
  for (let it = 0; it < 6; it++) {
    let added = false;
    for (let i = 0; i < k; i++) if (!fixed[i] && ((lb[i] && out[i] > prev[i] + 1e-12) || (ls[i] && out[i] < prev[i] - 1e-12))) { fixed[i] = 1; added = true; }
    if (!added) break;
    out = Float64Array.from(out); let s = 0, fz = 0;
    for (let i = 0; i < k; i++) { if (fixed[i]) { out[i] = prev[i]; fz += prev[i]; } else s += out[i]; }
    if (s > 0) { const sc = Math.max(1 - fz, 0) / s; for (let i = 0; i < k; i++) if (!fixed[i]) out[i] *= sc; }
  }
  return out;
}

function rankPct(v, mask) { // رتبهٔ درصدی (۰..۱) برای عناصر mask؛ پیوندها: میانگین
  const idx = []; for (let i = 0; i < v.length; i++) if (mask[i] && !isNaN(v[i])) idx.push(i);
  idx.sort((a, b) => v[a] - v[b] || a - b);
  const out = new Float64Array(v.length).fill(NaNv), n = idx.length;
  let i = 0; while (i < n) { let j = i; while (j + 1 < n && v[idx[j + 1]] === v[idx[i]]) j++; const r = (i + j) / 2 + 0.5; for (let t = i; t <= j; t++) out[idx[t]] = r / n; i = j + 1; }
  return out;
}
function topPct(v, mask) { // رتبهٔ درصدی از بالا، ترتیبی (بدون میانگین پیوندها) — همان tools/construction.py
  const idx = []; for (let i = 0; i < v.length; i++) if (mask[i] && !isNaN(v[i])) idx.push(i);
  idx.sort((a, b) => v[a] - v[b] || a - b);
  const out = new Float64Array(v.length).fill(NaNv), n = idx.length; for (let j = 0; j < n; j++) out[idx[n - 1 - j]] = (j + 0.5) / n; return out;
}
function spearman(x, y) {
  const m = new Uint8Array(x.length); let n = 0; for (let i = 0; i < x.length; i++) { m[i] = !isNaN(x[i]) && !isNaN(y[i]) ? 1 : 0; n += m[i]; }
  if (n < 20) return NaNv;
  const rx = rankPct(x, m), ry = rankPct(y, m); let sx = 0, sy = 0; for (let i = 0; i < x.length; i++) if (m[i]) { sx += rx[i]; sy += ry[i]; }
  sx /= n; sy /= n; let c = 0, vx = 0, vy = 0; for (let i = 0; i < x.length; i++) if (m[i]) { const a = rx[i] - sx, b = ry[i] - sy; c += a * b; vx += a * a; vy += b * b; }
  return c / Math.sqrt(vx * vy + 1e-18);
}
function icOf(ctx, name, r) {
  const key = name + '|' + r, C = ctx.cache.ic;
  if (!(key in C)) C[key] = (r < ctx.rows - 1) ? spearman(zAt(ctx, name, r), fwAt(ctx, r)) : NaNv;
  return C[key];
}
const histIC = (ctx, name, r, Lh = 36) => { const o = []; for (let j = Math.max(0, r - Lh); j < r; j++) { const v = icOf(ctx, name, j); if (v === v) o.push(v); } return o; };
const mean = a => a.reduce((s, x) => s + x, 0) / a.length;
const sd = a => { const m = mean(a); return Math.sqrt(a.reduce((s, x) => s + (x - m) * (x - m), 0) / (a.length - 1)); };

function neutralize(z, sec, k, minN = 6) {
  const sum = new Float64Array(256), cnt = new Int32Array(256);
  for (let i = 0; i < k; i++) if (!isNaN(z[i])) { sum[sec[i]] += z[i]; cnt[sec[i]]++; }
  const out = new Float64Array(k);
  for (let i = 0; i < k; i++) out[i] = isNaN(z[i]) ? NaNv : (cnt[sec[i]] >= minN ? z[i] - sum[sec[i]] / cnt[sec[i]] : z[i]);
  return out;
}
function solve(A, b) { // گاوس با محور جزئی
  const n = b.length, M = A.map((r, i) => [...r, b[i]]);
  for (let c = 0; c < n; c++) { let p = c; for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r; [M[c], M[p]] = [M[p], M[c]];
    const d = M[c][c] || 1e-12; for (let j = c; j <= n; j++) M[c][j] /= d; for (let r = 0; r < n; r++) if (r !== c) { const f = M[r][c]; for (let j = c; j <= n; j++) M[r][j] -= f * M[c][j]; } }
  return M.map(r => r[n]);
}
function fmWeights(ctx, names, r, ridge) {
  const B = [];
  for (let j = Math.max(0, r - 36); j < r; j++) {
    if (j >= ctx.rows - 1) continue;
    const Zs = names.map(n => zAt(ctx, n, j)), y = fwAt(ctx, j), ok = okAt(ctx, j), idx = [];
    for (let i = 0; i < ctx.k; i++) if (ok[i] && !isNaN(y[i]) && Zs.every(z => !isNaN(z[i]))) idx.push(i);
    if (idx.length < 50) continue;
    const my = idx.reduce((s, i) => s + y[i], 0) / idx.length, p = names.length, lam = (ridge ? 5 : 0.1) * idx.length / 100;
    const A = Array.from({ length: p }, () => new Array(p).fill(0)), b = new Array(p).fill(0);
    for (const i of idx) for (let a = 0; a < p; a++) { b[a] += Zs[a][i] * (y[i] - my); for (let c = 0; c < p; c++) A[a][c] += Zs[a][i] * Zs[c][i]; }
    for (let a = 0; a < p; a++) A[a][a] += lam;
    B.push(solve(A, b));
  }
  if (B.length < 12) return names.map(() => 1);
  const b = names.map((_, a) => mean(B.map(x => x[a]))), s = b.reduce((t, x) => t + Math.abs(x), 0) + 1e-12;
  return b.map(x => x / s * names.length);
}

/* امتیاز ترکیبی ماه r برای spec */
function score(ctx, spec, r) {
  const k = ctx.k, sigs = spec.signals.filter(([n]) => ctx.Z[n]), method = spec.combine || 'equal', neutral = spec.neutral !== false;
  if (!sigs.length) return new Float64Array(k).fill(NaNv);
  const secr = neutral ? secAt(ctx, r) : null;
  const Zs = sigs.map(([n]) => { let z = zAt(ctx, n, r); if (neutral) z = neutralize(z, secr, k); return z; });
  let ws = sigs.map(([, w]) => w);
  const names = sigs.map(([n]) => n);
  if (method === 'ic' || method === 'icir') {
    const h = names.map(n => histIC(ctx, n, r));
    if (h.every(x => x.length >= 12)) { let m = h.map(mean); if (method === 'icir') m = m.map((v, i) => v / Math.max(sd(h[i]), 1e-6)); const s = m.reduce((t, x) => t + Math.abs(x), 0) + 1e-12; ws = ws.map((w, i) => w * m[i] / s * m.length); }
  } else if (method === 'topk_icir') {
    const kk = spec.topk || 5, sc = names.map(n => { const h = histIC(ctx, n, r); return h.length >= 24 && sd(h) > 0 ? [Math.abs(mean(h) / sd(h)), Math.sign(mean(h))] : [0, 0]; });
    const ord = sc.map((x, i) => i).sort((a, b) => sc[b][0] - sc[a][0]).slice(0, kk); ws = names.map(() => 0); ord.forEach(i => { ws[i] = sc[i][1]; });
    if (!ws.some(x => x)) return new Float64Array(k).fill(NaNv);
  } else if ((method === 'fm' || method === 'ridge') && r >= 12) {
    const b = fmWeights(ctx, names, r, method === 'ridge'); ws = ws.map((w, i) => Math.sign(w || 1e-12) * b[i]);
  }
  const need = Math.max(1, Math.floor(0.6 * Zs.length)), out = new Float64Array(k);
  if (method === 'rank') {
    const allm = new Uint8Array(k).fill(1), R = Zs.map(z => rankPct(z, allm)), den = ws.reduce((t, x) => t + Math.abs(x), 0) || 1;
    for (let i = 0; i < k; i++) { let s = 0, c = 0; for (let a = 0; a < R.length; a++) if (!isNaN(R[a][i])) { s += ws[a] * R[a][i]; c++; } out[i] = c >= need ? s / den : NaNv; }
    out.ws = ws; out.wn = names;                                            // وزن مؤثر همین ماه (برای نمایش در سازنده)
    return out;
  }
  for (let i = 0; i < k; i++) { let s = 0, c = 0; for (let a = 0; a < Zs.length; a++) if (!isNaN(Zs[a][i])) { s += ws[a] * Zs[a][i]; c++; } out[i] = c >= need ? s : NaNv; }
  let m = 0, c = 0; for (let i = 0; i < k; i++) if (!isNaN(out[i])) { m += out[i]; c++; }
  m /= Math.max(c, 1); let v = 0; for (let i = 0; i < k; i++) if (!isNaN(out[i])) v += (out[i] - m) ** 2; const s = Math.sqrt(v / Math.max(c, 1)) || 1;
  for (let i = 0; i < k; i++) out[i] = isNaN(out[i]) ? NaNv : (out[i] - m) / s;
  out.ws = ws; out.wn = names;
  return out;
}

/** وزن مؤثر هر معیار در هر ماه بک‌تست و امروز: سهم علامت‌دار w_i ÷ Σ|w|. در روش‌های IC، ICIR، FM، ریج و انتخاب پویا وزن‌ها هر ماه
    از داده‌های گذشته برآورد می‌شوند و با وزن اسلایدر فرق دارند. خروجی: { n ماه، avg میانگین سهم، sel سهم ماه‌های با وزن غیرصفر، last امروز }. */
function effWeights(ctx, spec) {
  const rows = [...ctx.use, ctx.rows - 1], acc = {}, live = ctx.rows - 1; let n = 0, last = null;
  for (const r of rows) {
    const s = score(ctx, spec, r); if (!s.ws) continue;
    const tot = s.ws.reduce((t, x) => t + Math.abs(x), 0); if (!(tot > 0)) continue;
    const sh = s.ws.map(x => x / tot);
    if (r === live) { last = {}; s.wn.forEach((nm, i) => { last[nm] = sh[i]; }); continue; }
    s.wn.forEach((nm, i) => { const a = acc[nm] || (acc[nm] = { sum: 0, sel: 0 }); a.sum += sh[i]; if (s.ws[i] !== 0) a.sel++; });
    n++;
  }
  const avg = {}, sel = {}; for (const [nm, a] of Object.entries(acc)) { avg[nm] = n ? a.sum / n : NaNv; sel[nm] = n ? a.sel / n : NaNv; }
  return { n, avg, sel, last };
}

/* ── الگوریتم‌ها: ctx = {score, ok, held, mcap, vol} → وزن ── */
function capW(w, mx) {
  if (!mx) return w; let n = 0, s = 0; for (const x of w) if (x > 0) { n++; s += x; } if (n * mx < 1) return w.map(x => x > 0 ? 1 / n : 0);   // سقف ناممکن ⇒ هم‌وزن (همان construction._cap)
  w = Float64Array.from(w); for (let it = 0; it < 50; it++) { let ex = 0, free = 0; for (let i = 0; i < w.length; i++) { if (w[i] > mx) { ex += w[i] - mx; w[i] = mx; } }
    if (!ex) break; for (let i = 0; i < w.length; i++) if (w[i] > 0 && w[i] < mx) free += w[i]; if (!free) break; for (let i = 0; i < w.length; i++) if (w[i] > 0 && w[i] < mx) w[i] += ex * w[i] / free; }
  const t = w.reduce((a, b) => a + b, 0); return w.map(x => x / t);
}
function selected(c, entry, exit) {
  const m = new Uint8Array(c.k); let n = 0; for (let i = 0; i < c.k; i++) { m[i] = c.ok[i] && !isNaN(c.score[i]) ? 1 : 0; n += m[i]; }
  if (n < 30) return [];
  const pct = topPct(c.score, m), sel = [];     // رتبهٔ درصدی از بالا
  for (let i = 0; i < c.k; i++) if (m[i] && ((c.held[i] && pct[i] <= exit) || pct[i] <= entry)) sel.push(i);
  return sel;
}
const ALGO = {
  quantile(c, p) { const G = p.G || 5, kk = p.k || G, m = []; for (let i = 0; i < c.k; i++) if (c.ok[i] && !isNaN(c.score[i])) m.push(i); const w = new Float64Array(c.k); if (m.length < 30) return w;
    m.sort((a, b) => c.score[a] - c.score[b] || a - b); const n = m.length, base = Math.floor(n / G), ex = n % G; let lo = 0; for (let g = 1; g < kk; g++) lo += base + (g - 1 < ex ? 1 : 0);
    const sz = base + (kk - 1 < ex ? 1 : 0), grp = m.slice(lo, lo + sz); grp.forEach(i => { w[i] = 1 / grp.length; }); return w; },    // همان numpy.array_split
  topfrac(c, p) { const w = new Float64Array(c.k), sel = selected(c, p.entry ?? 0.2, Math.max(p.exit ?? 0.3, p.entry ?? 0.2)); sel.forEach(i => { w[i] = 1 / sel.length; }); return w; },
  topn(c, p) { let n = 0; for (let i = 0; i < c.k; i++) if (c.ok[i] && !isNaN(c.score[i])) n++; const N = p.N || 50, B = p.buffer ?? 25; return n < 30 ? new Float64Array(c.k) : ALGO.topfrac(c, { entry: Math.min(N / n, 1), exit: Math.min((N + B) / n, 1) }); },
  score_tilt(c, p) { const w = new Float64Array(c.k); let s = 0, n = 0; for (let i = 0; i < c.k; i++) if (c.ok[i] && !isNaN(c.score[i])) { w[i] = Math.exp((p.lam ?? 1) * Math.max(-3, Math.min(3, c.score[i]))); s += w[i]; n++; } if (n < 30) return new Float64Array(c.k); return w.map(x => x / s); },
  rank_weight(c) { const m = new Uint8Array(c.k); let n = 0; for (let i = 0; i < c.k; i++) { m[i] = c.ok[i] && !isNaN(c.score[i]) ? 1 : 0; n += m[i]; } const w = new Float64Array(c.k); if (n < 30) return w; const r = rankPct(c.score, m); let s = 0; for (let i = 0; i < c.k; i++) if (m[i]) { w[i] = Math.max(r[i] - 0.5, 0); s += w[i]; } return s ? w.map(x => x / s) : w; },
  msci_tilt(c) { const w = new Float64Array(c.k); let s = 0, n = 0; for (let i = 0; i < c.k; i++) if (c.ok[i] && !isNaN(c.score[i]) && c.mcap[i] > 0) { const z = Math.max(-3, Math.min(3, c.score[i])); w[i] = c.mcap[i] * (z > 0 ? 1 + z : 1 / (1 - z)); s += w[i]; n++; } return n < 30 ? new Float64Array(c.k) : w.map(x => x / s); },
  inv_vol(c, p) { const w = new Float64Array(c.k), sel = selected(c, p.entry ?? 0.3, Math.max(p.exit ?? 0.4, p.entry ?? 0.3)); let s = 0; sel.forEach(i => { if (c.vol[i] > 0) { w[i] = 1 / c.vol[i]; s += w[i]; } }); if (!s) { sel.forEach(i => { w[i] = 1 / (sel.length || 1); }); return w; } return w.map(x => x / s); },
};
const JS_ALGOS = Object.keys(ALGO);

/* ── بک‌تست ── */
function run(ctx, spec) {
  const k = ctx.k, algo = ALGO[spec.algo]; if (!algo) throw new Error('الگوریتم در مرورگر نیست: ' + spec.algo);
  const p = spec.params || {}, univ = spec.universe || {}, mk = univ.markets ? new Set(univ.markets.map(x => x === 'bourse' ? 0 : 1)) : new Set([0, 1]);
  const every = spec.rebalance_every || 1, kappa = spec.partial ?? 1, mx = spec.max_w, minAdv = univ.min_adv ? Math.log(univ.min_adv) : null, minW = spec.min_w ?? 0.0005;
  let prev = new Float64Array(k), held = new Uint8Array(k), prevAll = null, first = true, cnt = 0;
  const AUMS = ctx.L.aums || [], Y = ctx.L.y_impact || 1;
  const out = { end: [], ret: [], all: [], cap: [], to: [], toAll: [], toCap: [], n: [], ic: [], rows: [], impact: AUMS.map(() => []), W: spec._keepW ? [] : null };   // _keepW: وزن هدف هر ریبالانس (بخش «پرتفو»: هدف استراتژی در هر تاریخ)
  let prevCap = null;
  for (const r of ctx.use) {
    const okr = okAt(ctx, r), f = fwAt(ctx, r), ok = new Uint8Array(k), tr = trAt(ctx, r), lk = lkAt(ctx, r);
    for (let i = 0; i < k; i++) ok[i] = okr[i] && tr[i] && mk.has(ctx.mkt[i]) && (minAdv == null || ctx.adv[r * k + i] >= minAdv) ? 1 : 0;
    let nAll = 0; for (let i = 0; i < k; i++) nAll += ok[i];
    let allw = new Float64Array(k); for (let i = 0; i < k; i++) allw[i] = ok[i] ? 1 / Math.max(nAll, 1) : 0;
    const g = f.map(x => isNaN(x) ? 0 : x);
    let capw = new Float64Array(k); { let t = 0; for (let i = 0; i < k; i++) if (ok[i]) { const v = ctx.mcap[r * k + i]; capw[i] = v < -40 ? 0 : Math.exp(v); t += capw[i]; } if (t > 0) for (let i = 0; i < k; i++) capw[i] /= t; }
    const reb = (cnt % every === 0) || first; cnt++;
    if (reb && prevAll) allw = freezeLocked(allw, prevAll, tr, lk.lb, lk.ls, k);       // مرجع هم قاعدهٔ بی‌معامله و صف را دارد
    if (reb && prevCap) capw = freezeLocked(capw, prevCap, tr, lk.lb, lk.ls, k);
    let w = prev, to = 0, sc = null;
    if (reb) {
      sc = score(ctx, spec, r);
      const c = { k, score: sc, ok, held, mcap: ctx.mcap.subarray(r * k, (r + 1) * k).map(v => v < -40 ? 0 : Math.exp(v)), vol: ctx.vol.subarray(r * k, (r + 1) * k) };
      let wn = algo(c, p); let s = 0; for (const x of wn) s += x;
      if (s <= 0 && first) { cnt--; continue; }                                // پیش از نخستین سبد (مثلاً بنیادی بدون پوشش): نمونه هنوز شروع نشده (همان tools/construction.py)
      if (s <= 0) wn = Float64Array.from(prev);                               // بدون سبد در میانهٔ نمونه: سبد قبلی نگه داشته و ماه ثبت می‌شود
      else {
        if (mx) wn = capW(wn, mx);
        if (kappa < 1 && !first) { const ws = wn; wn = wn.map((x, i) => Math.max(prev[i] + kappa * (x - prev[i]), 0)); wn = wn.map((x, i) => x < minW && !(ws[i] > 0) ? 0 : x); const t = wn.reduce((a, b) => a + b, 0); wn = wn.map(x => x / t); }   // خروج کامل باقی‌ماندهٔ ناچیز
        wn = freezeLocked(wn, prev, tr, lk.lb, lk.ls, k);
      }
      w = wn; held = w.map(x => x > 0 ? 1 : 0);
      if (!first) { to = 0; for (let i = 0; i < k; i++) to += Math.abs(w[i] - prev[i]); to *= 0.5; } else to = NaNv;
    }
    let ret = 0; for (let i = 0; i < k; i++) ret += w[i] * g[i];
    let ra = 0; for (let i = 0; i < k; i++) ra += allw[i] * g[i];
    let toA = NaNv; if (prevAll) { toA = 0; for (let i = 0; i < k; i++) toA += Math.abs(allw[i] - prevAll[i]); toA *= 0.5; }
    let rc = 0; for (let i = 0; i < k; i++) rc += capw[i] * g[i];
    let toC = NaNv; if (prevCap) { toC = 0; for (let i = 0; i < k; i++) toC += Math.abs(capw[i] - prevCap[i]); toC *= 0.5; }
    out.cap.push(rc); out.toCap.push(toC);
    { let nc = new Float64Array(k), tc = 0; for (let i = 0; i < k; i++) { nc[i] = capw[i] * (1 + g[i]); tc += nc[i]; } prevCap = tc > 0 ? nc.map(x => x / tc) : nc; }
    AUMS.forEach((aum, j) => {                                           // اثر بازار Yσ√(Δw·AUM/ADV) به‌ازای هر نماد
      if (!reb || first) { out.impact[j].push(first ? NaNv : 0); return; }
      let c = 0; for (let i = 0; i < k; i++) { const dw = Math.abs(w[i] - prev[i]); if (dw <= 0) continue; const av = ctx.adv[r * k + i], adv = av < 0 ? 0 : Math.exp(av) - 1, sg = ctx.vol[r * k + i] > 0 ? ctx.vol[r * k + i] : 0; const part = adv > 0 ? dw * aum / adv : 0; c += dw * Y * sg * Math.sqrt(part); }   // بدون سقف مشارکت (همان construction)
      out.impact[j].push(c);
    });
    out.end.push(ctx.L.months_end[r]); out.ret.push(ret); out.all.push(ra); out.to.push(reb ? to : 0); out.toAll.push(toA); out.n.push(w.reduce((a, b) => a + (b > 0 ? 1 : 0), 0)); out.rows.push(r); if (out.W) out.W.push(reb ? Float64Array.from(w) : null);
    if (reb && sc) { const m = new Float64Array(k).fill(NaNv); for (let i = 0; i < k; i++) if (ok[i] && !isNaN(sc[i]) && !isNaN(f[i])) m[i] = f[i]; out.ic.push(spearman(sc, m)); } else out.ic.push(NaNv);
    let nw = new Float64Array(k), tot = 0; for (let i = 0; i < k; i++) { nw[i] = w[i] * (1 + g[i]); tot += nw[i]; } prev = tot > 0 ? nw.map(x => x / tot) : nw;
    let na = new Float64Array(k), ta = 0; for (let i = 0; i < k; i++) { na[i] = allw[i] * (1 + g[i]); ta += na[i]; } prevAll = ta > 0 ? na.map(x => x / ta) : na;
    if (tot > 0) first = false;                                              // تا نخستین سبد واقعی، گردش ماه بعد «ساخت اولیه» است
  }
  // وزن هدف زنده (آخرین سطر)
  const rl = ctx.rows - 1, okr = okAt(ctx, rl), okl = new Uint8Array(k); for (let i = 0; i < k; i++) okl[i] = okr[i] && mk.has(ctx.mkt[i]) && (minAdv == null || ctx.adv[rl * k + i] >= minAdv) ? 1 : 0;
  const scl = score(ctx, spec, rl), cl = { k, score: scl, ok: okl, held, mcap: ctx.mcap.subarray(rl * k, (rl + 1) * k).map(v => v < -40 ? 0 : Math.exp(v)), vol: ctx.vol.subarray(rl * k, (rl + 1) * k) };
  let wl = algo(cl, p); if (mx && wl.reduce((a, b) => a + b, 0) > 0) wl = capW(wl, mx);
  // رانش از آخرین پایان ماه تا امروز: بازده ماه ناتمام در fw سطر rows−2 نیست؛ در پایتون از mk.X می‌آید و اینجا سری روزانه نیست،
  // پس وزن رانش‌یافته تا آخرین پایان ماه است (ui/lab.js این را در متن رصد زنده می‌گوید)
  out.live = { target: wl, score: scl, drift: prev, driftAsOf: ctx.L.months_end[ctx.rows - 3] || null };
  return out;
}

/* ── آمار ── */
function nwT(x, L = 3) { x = x.filter(v => v === v); const T = x.length; if (T < 12) return NaNv; const m = mean(x), e = x.map(v => v - m); let v = e.reduce((s, a) => s + a * a, 0) / T;
  for (let l = 1; l <= L; l++) { let g = 0; for (let t = l; t < T; t++) g += e[t] * e[t - l]; v += 2 * (1 - l / (L + 1)) * g / T; } return v > 0 ? m / Math.sqrt(v / T) : NaNv; }
const annOf = x => (Math.pow(x.reduce((p, v) => p * (1 + v), 1), 12 / x.length) - 1) * 100;
const mddOf = x => { let c = 1, pk = 1, m = 0; for (const v of x) { c *= 1 + v; pk = Math.max(pk, c); m = Math.min(m, c / pk - 1); } return m * 100; };
function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
function bootMean(x, reps = 1000, block = 3, seed = 7) { const T = x.length, R = rng(seed), mu = new Float64Array(reps); for (let b = 0; b < reps; b++) { let i = Math.floor(R() * T), s = 0; for (let t = 0; t < T; t++) { s += x[i]; i = R() < 1 / block ? Math.floor(R() * T) : (i + 1) % T; } mu[b] = s / T; }
  const a = Array.from(mu).sort((p, q) => p - q); return { lo: a[Math.floor(reps * 0.025)] * 1200, hi: a[Math.floor(reps * 0.975)] * 1200, p: a.filter(v => v > 0).length / reps }; }
function stats(res, costBp = 125, jy, bench) {
  const cap = bench === 'cap' && res.cap && res.cap.length, c = costBp / 1e4, n = res.ret.length, r = res.ret, a = cap ? res.cap : res.all, to = res.to.map(v => isNaN(v) ? 0 : v), toa = (cap ? res.toCap : res.toAll).map(v => isNaN(v) ? 0 : v);
  const rn = r.map((v, i) => v - to[i] * c), an = a.slice(), anNet = a.map((v, i) => v - toa[i] * c), exn = rn.map((v, i) => v - an[i]),   // مرجع بدون هزینه (فصل ۷ §۷٫۴؛ ممیزی ۲۰۲۶-۱۰-۲۰)
    exg = r.map((v, i) => v - a[i]), h = Math.floor(n / 2);
  const m = mean(exn), s = sd(exn), bt = bootMean(exn), ic = res.ic.filter(v => v === v);
  const roll = []; for (let i = 0; i + 12 <= n; i++) roll.push(exn.slice(i, i + 12).reduce((p, v) => p * (1 + v), 1) - 1);
  const years = {}; res.end.forEach((d, i) => { const y = jy ? jy(d) : d.slice(0, 4); (years[y] = years[y] || []).push(exn[i]); });
  const yr = {}; Object.keys(years).forEach(y => { yr[y] = (years[y].reduce((p, v) => p * (1 + v), 1) - 1) * 100; });
  return { n, ann_gross: annOf(r), ann_net: annOf(rn), ann_all_net: annOf(an), excess_net: annOf(rn) - annOf(an), excess_gross: annOf(r) - annOf(a), excess_vs_netbench: annOf(rn) - annOf(anNet),
    vol: sd(r) * Math.sqrt(12) * 100, te: s * Math.sqrt(12) * 100, ir: s > 0 ? m / s * Math.sqrt(12) : NaNv, t_net: nwT(exn), t_gross: nwT(exg), hit: exn.filter(v => v > 0).length / n * 100,
    t_h1: nwT(exn.slice(0, h)), t_h2: nwT(exn.slice(h)), ex_h1: mean(exn.slice(0, h)) * 1200, ex_h2: mean(exn.slice(h)) * 1200, mdd_active: mddOf(exn), mdd: mddOf(rn),
    turn_ann: to.reduce((p, v) => p + v, 0) / (n / 12) * 100, names: mean(res.n), boot_lo: bt.lo, boot_hi: bt.hi, boot_p: bt.p,
    roll12_win: roll.length ? roll.filter(v => v > 0).length / roll.length * 100 : NaNv, roll12_worst: roll.length ? Math.min(...roll) * 100 : NaNv, years: yr,
    ic_mean: ic.length ? mean(ic) : NaNv, ic_t: nwT(ic), icir: ic.length > 2 ? mean(ic) / sd(ic) * Math.sqrt(12) : NaNv, exn, rn, an };
}
/* نرمال و DSR */
const Phi = x => { const t = 1 / (1 + 0.2316419 * Math.abs(x)), d = 0.3989423 * Math.exp(-x * x / 2), p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274)))); return x > 0 ? 1 - p : p; };
function PhiInv(p) { // Acklam
  const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239], b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572],
    c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783], d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];
  const pl = 0.02425; if (p < pl) { const q = Math.sqrt(-2 * Math.log(p)); return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
  if (p > 1 - pl) return -PhiInv(1 - p);
  const q = p - 0.5, r = q * q; return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
}
function dsr(exn, trialSR, N) {
  const T = exn.length, m = mean(exn), s = sd(exn), srr = m / s, z = exn.map(v => (v - m) / s), sk = mean(z.map(v => v ** 3)), ku = mean(z.map(v => v ** 4)), v = trialSR.length > 2 ? sd(trialSR) ** 2 : 0, g = 0.5772156649;
  const sr0 = Math.sqrt(v) * ((1 - g) * PhiInv(1 - 1 / N) + g * PhiInv(1 - 1 / (N * Math.E))), den = Math.sqrt(Math.max(1 - sk * srr + (ku - 1) / 4 * srr * srr, 1e-9));
  return { sr_annual: srr * Math.sqrt(12), sr0_monthly: sr0, dsr: Phi((srr - sr0) * Math.sqrt(T - 1) / den), N, T };
}
/** آستانهٔ t استقرار: بیشینهٔ ۳ و t بونفرونی ۵٪ دوطرفه برای N آزمایش (همان factor_engine.t_threshold؛ ممیزی ۲۰۲۶-۱۰-۲۰) */
const tThreshold = N => Math.max(3, Math.abs(PhiInv(1 - 0.05 / (2 * Math.max(N || 1, 1)))));
function verdict(st, spearmanDec, N) {
  const same = (st.ex_h1 > 0) === (st.ex_h2 > 0), t = st.t_net, bootOk = st.excess_net > 0 ? st.boot_lo > 0 : st.boot_hi < 0, thr = tThreshold(N);
  const mono = spearmanDec == null ? NaN : spearmanDec;                  // بدون دهک = یکنوایی نامعلوم ⇒ «استقرار» صادر نمی‌شود
  if (Math.abs(t) >= thr && same && bootOk && Math.abs(mono) >= 0.6) return st.excess_net > 0 ? { v: 'استقرار', why: `t خالص ≥ ${thr.toFixed(2)} (بونفرونی برای ${N || 1} آزمایش)، دو نیمه هم‌علامت، بوت‌استرپ بدون صفر، یکنوایی بالا`, cls: 'ok' } : { v: 'معکوس معنادار', why: 'برتری معنادار ولی منفی؛ فروش استقراضی لازم است', cls: 'warn' };
  if (Math.abs(t) >= 2 && same) return { v: 'شاهد ضعیف', why: 't خالص ≥ ۲ و دو نیمه هم‌علامت، ولی آستانهٔ آزمون‌های چندگانه رد نشده', cls: 'warn' };
  return { v: 'بدون برتری معنادار', why: 't خالص < ۲ یا ناپایدار بین دو نیمه', cls: 'bad' };
}
/* دهک‌ها برای یک spec (G=10) */
function deciles(ctx, spec, costBp = 125) {
  const res = [], ann = [], G = 10; let spread = null;
  for (let kk = 1; kk <= G; kk++) { const r = run(ctx, { ...spec, algo: 'quantile', params: { G, k: kk }, max_w: null, partial: 1, rebalance_every: 1 }); res.push(r); const c = costBp / 1e4; ann.push(annOf(r.ret.map((v, i) => v - (isNaN(r.to[i]) ? 0 : r.to[i]) * c))); }
  const c = costBp / 1e4, top = res[G - 1], bot = res[0], sp = top.ret.map((v, i) => v - (isNaN(top.to[i]) ? 0 : top.to[i]) * c - (bot.ret[i] - (isNaN(bot.to[i]) ? 0 : bot.to[i]) * c));
  // اسپیرمن رتبهٔ دهک با بازده
  const rk = a => { const o = a.map((v, i) => [v, i]).sort((x, y) => x[0] - y[0]), r = new Array(a.length); o.forEach(([, i], j) => { r[i] = j; }); return r; }, ra = rk(ann), rb = ann.map((_, i) => i), ma = mean(ra), mb = mean(rb);
  let cv = 0, va = 0, vb = 0; ra.forEach((x, i) => { cv += (x - ma) * (rb[i] - mb); va += (x - ma) ** 2; vb += (rb[i] - mb) ** 2; });
  return { ann, spread_t: nwT(sp), spread_ann: mean(sp) * 1200, spearman: cv / Math.sqrt(va * vb), up: ann.slice(1).filter((v, i) => v > ann[i]).length };
}

/* ── تفکیک فاکتوری (همان tools/attribution.py؛ فصل ۱۴ §۱۴٫۷٫۸) ──
   برتری ناخالص ماهانه (S − ALL) روی MKT (هم‌وزن واجدان) و چهار فاکتور تک‌معیار کتابخانه (top-fraction منهای ALL) رگرس می‌شود؛
   خطای معیار نیوی‌وست ۳ وقفه؛ سهم‌ها α·۱۲ + Σβ·mean(F)·۱۲ = میانگین برتری ×۱۲ (حسابی). */
const FACTORS = [['MKT', 'بازار (هم‌وزن واجدان)', null], ['SIZE', 'اندازهٔ کوچک', 'size'], ['LOWVOL', 'کم‌نوسان', 'vol_252'], ['DIV', 'بازده نقدی سود', 'div_yield'], ['MOM', 'مومنتوم ۱۲−۱', 'mom_12_1']];
function invMat(A) {
  const n = A.length, M = A.map((r, i) => [...r, ...Array.from({ length: n }, (_, j) => (i === j ? 1 : 0))]);
  for (let c = 0; c < n; c++) {
    let p = c; for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
    if (Math.abs(M[p][c]) < 1e-14) return null;
    [M[c], M[p]] = [M[p], M[c]]; const d = M[c][c]; for (let j = 0; j < 2 * n; j++) M[c][j] /= d;
    for (let r = 0; r < n; r++) if (r !== c) { const f = M[r][c]; if (f) for (let j = 0; j < 2 * n; j++) M[r][j] -= f * M[c][j]; }
  }
  return M.map(r => r.slice(n));
}
function olsHac(y, F, L = 3) {
  const T = y.length, p = F[0].length + 1, X = F.map(r => [1, ...r]);
  const XtX = Array.from({ length: p }, () => new Array(p).fill(0)), Xty = new Array(p).fill(0);
  for (let t = 0; t < T; t++) for (let i = 0; i < p; i++) { Xty[i] += X[t][i] * y[t]; for (let j = 0; j < p; j++) XtX[i][j] += X[t][i] * X[t][j]; }
  const Q = invMat(XtX); if (!Q) return null;
  const b = Q.map(r => r.reduce((s, q, j) => s + q * Xty[j], 0)), e = y.map((v, t) => v - X[t].reduce((s, x, i) => s + x * b[i], 0));
  const u = X.map((r, t) => r.map(x => x * e[t])), S = Array.from({ length: p }, () => new Array(p).fill(0));
  for (let t = 0; t < T; t++) for (let i = 0; i < p; i++) for (let j = 0; j < p; j++) S[i][j] += u[t][i] * u[t][j];
  for (let l = 1; l <= L; l++) { const w = 1 - l / (L + 1); for (let t = l; t < T; t++) for (let i = 0; i < p; i++) for (let j = 0; j < p; j++) S[i][j] += w * (u[t][i] * u[t - l][j] + u[t - l][i] * u[t][j]); }
  const V = Q.map(r => S[0].map((_, j) => r.reduce((s, q, k) => s + q * S[k][j], 0))).map(r => Q[0].map((_, j) => r.reduce((s, v, k) => s + v * Q[k][j], 0)));
  const se = V.map((r, i) => Math.sqrt(Math.max(r[i], 0))), my = y.reduce((a, v) => a + v, 0) / T, sst = y.reduce((a, v) => a + (v - my) ** 2, 0), sse = e.reduce((a, v) => a + v * v, 0);
  return { b, se, r2: sst > 0 ? 1 - sse / sst : NaNv };
}
function factorSeries(L) {
  const lib = id => L.library.find(x => x.id === id), fac = {};
  for (const [code, , sig] of FACTORS) { if (!sig) continue; const r = lib('sig:' + sig); if (!r) return null; fac[code] = r.ret.map((v, i) => v - r.all[i]); if (!fac.MKT) fac.MKT = r.all.slice(); }
  return fac;
}
/** فاکتورهای هم‌جهانِ یک اجرای مرورگر: هر فاکتور همان تعریف ردیف «sig:» کتابخانه (top-fraction ۲۰٪/۳۰٪، خنثی از صنعت) است، ولی با
    جهان (بازارها، کف نقدشوندگی) و فاصلهٔ ریبالانس همین اجرا ساخته می‌شود؛ وگرنه برتری استراتژیِ مثلاً «فقط فرابورس» روی فاکتورهای کل بازار رگرس می‌شد.
    bench = 'cap' ⇒ MKT و مرجع برتری، ارزش‌وزن واجدان همان جهان است. */
function factorSeriesFor(ctx, spec, bench = 'eq') {
  const fac = {}; let base = null;
  for (const [code, , sig] of FACTORS) {
    if (!sig) continue;
    const r = run(ctx, { signals: [[sig, 1]], combine: 'equal', neutral: true, algo: 'topfrac', params: { entry: 0.2, exit: 0.3 }, universe: spec.universe, rebalance_every: spec.rebalance_every || 1, partial: 1, max_w: null, cost_bp: spec.cost_bp });
    fac[code] = r.ret.map((v, i) => v - r.all[i]); if (!base) base = r;
  }
  fac.MKT = (bench === 'cap' ? base.cap : base.all).slice(); return fac;
}
/** res: {ret, all, to, toAll} یک اجرا؛ خروجی هم‌شکل attribution.attribute پایتون + بتاهای غلتان ۳۶ ماهه.
    opt.fac: فاکتورهای factorSeriesFor (پیش‌فرض: ردیف‌های ثابت کتابخانه، برای برابری با پایتون)؛ opt.bench = 'cap' ⇒ برتری نسبت به ارزش‌وزن. */
function attribution(L, res, costBp, roll = 36, opt = {}) {
  const fac = opt.fac || factorSeries(L); if (!fac) return null;
  const cap = opt.bench === 'cap' && res.cap && res.cap.length === res.ret.length;
  const codes = FACTORS.map(f => f[0]), n = Math.min(res.ret.length, ...codes.map(c => fac[c].length)), tail = a => a.slice(a.length - n);
  const rs = tail(res.ret), ra = tail(cap ? res.cap : res.all), ts = tail(res.to), ta = tail(cap ? (res.toCap || res.cap.map(() => 0)) : (res.toAll || res.all.map(() => 0))), Fc = codes.map(c => tail(fac[c])), c = costBp / 1e4;
  const y = [], F = [], drag = [], idx = [];
  for (let i = 0; i < n; i++) { const yy = rs[i] - ra[i], ff = Fc.map(a => a[i]); if (isNaN(yy) || ff.some(isNaN)) continue; y.push(yy); F.push(ff); drag.push((isNaN(ts[i]) ? 0 : ts[i]) * c); idx.push(i); }   // drag: هزینهٔ استراتژی؛ مرجع بدون هزینه (فصل ۷ §۷٫۴)
  if (y.length < 24) return null;
  const o = olsHac(y, F); if (!o) return null;
  const self = o.r2 > 0.9999, T = y.length, mean = a => a.reduce((s, v) => s + v, 0) / a.length;
  const tt = i => (self || !(o.se[i] > 1e-12)) ? null : o.b[i] / o.se[i];
  const mF = codes.map((_, k) => mean(F.map(r => r[k])));
  const rolling = []; if (T >= roll + 6) for (let e = roll; e <= T; e++) { const q = olsHac(y.slice(e - roll, e), F.slice(e - roll, e), 3); rolling.push(q ? q.b.slice(1) : codes.map(() => NaNv)); }
  return { months: T, alpha_ann: 1200 * o.b[0], alpha_t: tt(0), r2: o.r2, self_factor: self,
    factors: FACTORS.map(([code, fa], k) => ({ code, fa, beta: o.b[k + 1], t: tt(k + 1), factor_ann: 1200 * mF[k], contrib_ann: 1200 * o.b[k + 1] * mF[k] })),
    gross_excess_ann: 1200 * mean(y), cost_ann: -1200 * mean(drag), net_excess_ann: 1200 * (mean(y) - mean(drag)),
    rolling: { win: roll, end: idx.slice(roll - 1).map(i => (res.end || [])[res.end ? res.end.length - n + i : 0]), beta: rolling } };
}

root.LabEngine = { load, run, stats, deciles, verdict, tThreshold, dsr, nwT, annOf, JS_ALGOS, zAt, fwAt, okAt, score, effWeights, attribution, factorSeriesFor, FACTORS, spearman, Phi, PhiInv };
})(typeof window !== 'undefined' ? window : globalThis);
