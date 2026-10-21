/* همتا — «همتاساز»: بازسازی شاخص كل با نمونهٔ کوچک، فیلتر نقدشوندگی، نقد و وام سود نقدی (نه اهرم)، و نگاه به گذشته (فصل ۳ §۳٫۷)
   داده: window.SIM_REP (tools/build_replica_panel.py). موتور (بخش اول) خالص است و در node هم آزمون می‌شود: node tools/replica_selftest.js
   فرمول درون هر ماه (خطی در بازده ناخالص G): NAV_t = L·nav₀·G_t + نقد − بدهیِ انباشته؛ هزینه = گردش × L × هزینهٔ رفت‌وبرگشت. */
(function (root) {
'use strict';

/* ═════════════════ موتور (بدون DOM) ═════════════════ */
function b64f(s) { const bin = atob(s), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return new Float32Array(u.buffer); }
function prep(R) {
  if (R._p) return R._p;
  R._p = { K: b64f(R.K), C: b64f(R.C), cfg: {} };
  R.sigList = R.sig;                                                   // روز سیگنال هر ماه (روز دوره‌ای از ۱۹۷۰)
  return R._p;
}
function seriesOf(R, key) { const p = prep(R); return p.cfg[key] || (p.cfg[key] = b64f(R.configs[key].r)); }
const keyOf = (m, N, q) => `${m}|${N}|${q}`;

/** برنامهٔ سود نقدی هر ترکیب: روز استحقاق ⇒ [[روز پرداخت، سهم سود از ارزش دیروز سبد]] (tools/build_replica_panel.py، dv). */
function divOf(R, key) {
  const p = prep(R), c = R.configs[key]; if (p.dv && p.dv[key]) return p.dv[key];
  const m = new Map();
  if (c && c.dv) { const ys = typeof c.dv[2] === 'string' ? b64f(c.dv[2]) : c.dv[2]; c.dv[0].forEach((t, i) => { if (!m.has(t)) m.set(t, []); m.get(t).push([c.dv[1][i], ys[i]]); }); }
  (p.dv || (p.dv = {}))[key] = m; return m;
}
/** رویدادهای لایهٔ عرضهٔ اولیه (tools/new_listings.py ← build_replica_panel، R.ipo.ev): نماد تازهٔ بزرگ با وزن شاخص بیرون از انتخاب. */
function ipoOf(R) {
  const p = prep(R); if (p.ipo) return p.ipo;
  p.ipo = R.ipo && R.ipo.ev ? R.ipo.ev.map(e => ({ ...e, r: b64f(e.r), w: b64f(e.w), v: b64f(e.v) })) : [];
  return p.ipo;
}
const atE = (a, e, t) => (t >= e.a && t - e.a < a.length ? a[t - e.a] : 0);
/** ریبالانس‌های میان‌ماه سیاست انتخابی (tools/build_replica_rebal.py): روز اجرا ⇒ گردش یک‌طرفه؛ null برای سیاست ماهانه. */
function todOf(R, key) {
  const p = prep(R), c = R.configs[key]; if (!c.tod || !c.tod[0].length) return null;
  const t = p.tod || (p.tod = {}); return t[key] || (t[key] = new Map(c.tod[0].map((d, i) => [d, c.tod[1][i]])));
}
/** شبیهٔ NAV (فصل ۳ §۳٫۵؛ همان tools/sampled_replica.step_day، ipo_rebalance و ipo_day).
 *  o = {mode:'none'|'fixed'|'beta', L, loan, rb, rc, cost, j0}
 *  • mode: none تمام سرمایه‌گذاری؛ fixed نقد ثابت (L = ۱ − نقد)؛ beta تراز بتا فقط نقد (L = clip(1/β, 0.7, 1)). وام برای اهرم مجاز نیست.
 *  • سود نقدی: روز استحقاق y·V از سهام جدا و «طلب» می‌شود و در روز پرداخت واقعی برمی‌گردد. بدون وام طلب بی‌بازده است.
 *  • loan = «وام سود نقدی»: در روز استحقاق دقیقاً به اندازهٔ طلب سود وام گرفته و سرمایه‌گذاری می‌شود؛ پرداخت سود وام را تسویه می‌کند؛
 *    بدهی هرگز از طلب بیشتر نمی‌شود (بهرهٔ مازاد از فروش سهام). لایهٔ عرضهٔ اولیه (فصل ۳ «تأخیر ورود عرضهٔ اولیه»): نماد تازهٔ بزرگ از روز پس از
 *    نخستین معامله با وزن شاخص هدف است؛ هر روز در پایانی حداکثر φ × ارزش معاملات ÷ اندازهٔ صندوق خریده می‌شود (صف خرید هم) تا ماهی که واجد عادی شود.
 *    o.phi (کسر)، o.aum (میلیارد ریال)؛ سری ipoB = Σ b(r_e − r) و ipoD = Σ (h − b)(r_e − r) برای تجزیهٔ اختلاف. پل تسویهٔ ابطال ۲۰۲۶-۱۰-۲۱ حذف شد (دادهٔ واقعی نداریم و منبع خطای همتا نیست).
 *  • سیاست ریبالانس (فصل ۳ «سیاست ریبالانس»): c.rbm[j] = ۰ یعنی آغاز ماه j ریبالانس نشد (نه هزینه، نه تنظیم دوبارهٔ L)؛ c.tod ریبالانس‌های میان‌ماه
 *    با گردش‌شان؛ در روز اجرا E −= گردش × L × هزینه × E و نسبت سهام/نقد دوباره L می‌شود. نبود rbm و tod یعنی ریبالانس ماهانه (سیاست پایه). */
function simulate(R, key, o) {
  const c = R.configs[key], r = seriesOf(R, key), dv = divOf(R, key), nm = R.mstart.length, n = R.dates.length;
  const nav = new Float64Array(n).fill(NaN), Ls = new Float64Array(nm).fill(NaN), cm = new Float64Array(nm), loan = !!o.loan, todm = todOf(R, key);
  let V = 1, cash = 0, D = 0, rcv = 0, sD = 0, sR = 0, cnt = 0, interest = 0, L = 1, nReb = 0, toSum = 0;
  const Lof = j => { if (o.mode === 'fixed') return Math.min(o.L, 1); if (o.mode === 'beta') { const be = c.beta[j]; return be > 0 ? Math.min(1, Math.max(0.7, 1 / be)) : 1; } return 1; };
  const sched = new Map();
  const EV = ipoOf(R), phi = o.phi == null ? (R.ipo ? R.ipo.phi : 0) : o.phi, aum = o.aum || (R.ipo ? R.ipo.aum : 1000), H = new Map();
  const ipoB = new Float64Array(n), ipoD = new Float64Array(n), mstate = [];
  const sumH = () => { let x = 0; for (const v of H.values()) x += v; return x; };
  for (let j = o.j0; j < nm; j++) {
    const t0 = R.mstart[j], t1 = j + 1 < nm ? R.mstart[j + 1] : n;
    const reb = j === o.j0 || !c.rbm || c.rbm[j];                        // آغاز این ماه ریبالانس می‌شود؟
    if (reb) L = Lof(j);
    Ls[j] = L;
    { const tot = V + sumH();                                          // لایهٔ عرضهٔ اولیه: رها کردن نماد واجدشده، کاستن مازاد وزن
      for (const e of EV) { if (!H.has(e.p)) continue; let x; if (e.j <= j) { x = H.get(e.p); H.delete(e.p); } else { x = Math.max(H.get(e.p) - atE(e.w, e, t0) * tot, 0); H.set(e.p, H.get(e.p) - x); } V += x - x * o.cost / 1e4; } }
    if (D > rcv) { V -= D - rcv; D = rcv; }                            // سقف بدهی = طلب سود
    if (reb) {
      let E = V + cash;
      const to = j === o.j0 ? 0.5 : c.to[j], x = to * L * o.cost / 1e4;
      E -= x * E; if (j > o.j0) { cm[j] += x; nReb++; toSum += to; }
      V = L * E; cash = E - V;
    }
    { const hs = sumH(), nv = V + cash + rcv - D + hs || 1;              // ترکیب واقعی آغاز ماه به نسبت NAV (پنل «جزئیات همین همتا»)
      mstate[j] = { L, rest: V / nv, cash: cash / nv, rcv: rcv / nv, debt: D / nv, ipo: [...H].map(([k, v]) => [k, v / nv]) }; }
    let prev = R.sig[j];
    for (let t = t0; t < t1; t++) {
      if (todm && todm.has(t)) {                                       // ریبالانس میان‌ماه سیاست انتخابی (اجرا در آغاز روز t)
        const to = todm.get(t); L = Lof(j); let E = V + cash; const x = to * L * o.cost / 1e4;
        E -= x * E; cm[j] += x; nReb++; toSum += to; V = L * E; cash = E - V;
      }
      const gap = R.dates[t] - prev; prev = R.dates[t];
      if (D > 0) { const d0 = D; D *= 1 + o.rb * gap / 365; interest += D - d0; }
      cash *= 1 + o.rc * gap / 365;
      const Vp = V, Hp = EV.length ? sumH() : 0;
      const paid = sched.get(t) || 0; sched.delete(t);
      let ytot = 0; const ev = dv.get(t);
      if (ev) for (const [p, y] of ev) { const A = y * V; sched.set(p, (sched.get(p) || 0) + A); rcv += A; ytot += y; if (loan) D += A; }
      V *= 1 + r[t] - (loan ? 0 : ytot);
      if (paid) { rcv -= paid; if (loan) D -= paid; else V += paid; }
      if (D > rcv) { V -= D - rcv; D = rcv; }                          // سقف روزانه: وام سود ≤ طلب سود (بهرهٔ مازاد از فروش سهام)
      if (EV.length) {
        const tp = Vp + Hp;
        for (const e of EV) { const re = atE(e.r, e, t), b = atE(e.w, e, t), h = tp > 0 ? (H.get(e.p) || 0) / tp : 0; if (b || h) { ipoB[t] += b * (re - r[t]); ipoD[t] += (h - b) * (re - r[t]); } }
        for (const [k, v] of H) { const e = EV.find(x => x.p === k); H.set(k, v * (1 + (e ? atE(e.r, e, t) : 0))); }
        const tot = V + sumH();
        for (const e of EV) {
          if (t < e.a || t - e.a >= e.w.length || (!H.has(e.p) && t >= e.end)) continue;
          const need = e.w[t - e.a] * tot - (H.get(e.p) || 0); if (need <= 0) continue;
          const amt = Math.min(need, phi * e.v[t - e.a] / aum, Math.max(V, 0));
          if (amt > 0) { H.set(e.p, (H.get(e.p) || 0) + amt); V -= amt + amt * o.cost / 1e4; }
        }
      }
      const nv = V + cash + rcv - D + sumH(); nav[t] = nv; sD += D / nv; sR += rcv / nv; cnt++;
    }
  }
  return { nav, t0: R.mstart[o.j0], Ls, debtAvg: cnt ? sD / cnt : 0, rcvAvg: cnt ? sR / cnt : 0, interest, hasDiv: dv.size > 0, ipoB, ipoD, mstate, cm, nReb, toSum, ipoNow: EV.length ? sumH() / Math.max(V + sumH(), 1e-12) : 0 };
}
const mean = a => a.reduce((s, x) => s + x, 0) / a.length;
function sd(a) { const m = mean(a); return Math.sqrt(a.reduce((s, x) => s + (x - m) * (x - m), 0) / (a.length - 1)); }
/** معیارهای خطا روی [t0+1, tEnd]؛ قرارداد پایتون (sampled_replica.evaluate): بازده روز اول NAV کنار گذاشته می‌شود. */
function metrics(R, sim, tEnd) {
  const p = prep(R), n = tEnd == null ? R.dates.length - 1 : Math.min(tEnd, R.dates.length - 1), t0 = sim.t0, rr = [], kk = [], cc = [];
  for (let t = t0 + 1; t <= n; t++) { rr.push(sim.nav[t] / sim.nav[t - 1] - 1); kk.push(p.K[t]); cc.push(p.C[t]); }
  const m = rr.length; if (m < 30) return null;
  const d1 = rr.map((x, i) => x - kk[i]), d2 = rr.map((x, i) => x - cc[i]), mk = mean(kk), mr = mean(rr);
  let cv = 0, vk = 0, vr = 0; for (let i = 0; i < m; i++) { cv += (rr[i] - mr) * (kk[i] - mk); vk += (kk[i] - mk) ** 2; vr += (rr[i] - mr) ** 2; }
  const yrs = (R.dates[n] - R.dates[t0]) / 365.25, gk = kk.reduce((a, x) => a * (1 + x), 1);   // سال تقویمی (فصل ۷ §۷٫۳)، همان tools/sampled_replica.evaluate
  const first = sim.nav[t0];
  const ann = Math.pow(sim.nav[n] / first, 1 / yrs) - 1, annk = Math.pow(gk, 1 / yrs) - 1;
  return { n: m, years: yrs, ann: 100 * ann, annk: 100 * annk, gap: 100 * (ann - annk), te: sd(d1) * Math.sqrt(252) * 100, teC: sd(d2) * Math.sqrt(252) * 100,
    beta: cv / vk, corr: cv / Math.sqrt(vk * vr), td: 100 * (sim.nav[n] / first / gk - 1), growth: sim.nav[n] / first, growthK: gk };
}
/** سری‌های نمودار از j0: NAV و شاخص به پایهٔ ۱۰۰، تفاوت تجمعی (واحد درصد)، TE غلتان ۲۵۲ روزه. */
function curves(R, sim) {
  const p = prep(R), n = R.dates.length, t0 = sim.t0, idx = [], a = [], k = [], td = [], te = [];
  let g = 1; const dif = [];
  for (let t = t0; t < n; t++) {
    if (t > t0) g *= 1 + p.K[t];
    idx.push(t); a.push(100 * sim.nav[t] / sim.nav[t0]); k.push(100 * g);
    td.push(100 * (a[a.length - 1] / k[k.length - 1] - 1));
    if (t > t0) dif.push(sim.nav[t] / sim.nav[t - 1] - 1 - p.K[t]);
    if (dif.length >= 126) { const w = dif.slice(-252); te.push(sd(w) * Math.sqrt(252) * 100); } else te.push(NaN);
  }
  return { idx, a, k, td, te };
}
const u16 = s => { const bin = atob(s), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return new Uint16Array(u.buffer); };
/** دادهٔ پایه (ماهانه) + فایل سیاست (tools/build_replica_rebal.py) ⇒ دادهٔ همتاساز همان سیاست؛ وزن‌های آغاز ماه (sel) فشرده‌اند: تعداد، اندیس نماد و وزن × ۶۵۵۳۵. */
function mergePol(B, P) {
  const cfg = {};
  for (const k in B.configs) {
    const q = P.configs[k]; if (!q) { cfg[k] = B.configs[k]; continue; }
    const cnt = u16(q.sel[0]), ids = u16(q.sel[1]), ws = u16(q.sel[2]), sel = []; let o = 0;
    for (const m of cnt) { sel.push([Array.from(ids.subarray(o, o + m)), Array.from(ws.subarray(o, o + m), x => Math.round(x / 65535 * 1e5))]); o += m; }
    cfg[k] = { ...B.configs[k], ...q, sel };
  }
  return { ...B, _p: null, configs: cfg, names: B.names.concat(P.names_extra), pol: P.pol };
}
const E = { simulate, metrics, curves, keyOf, prep, seriesOf, mergePol };
if (typeof module !== 'undefined' && module.exports) { module.exports = E; return; }
root.SIM_RB = E;

/* ═════════════════ رابط ═════════════════ */
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const f = (x, d = 1) => x == null || x !== x ? '—' : fmt(x, d);
const sg = (x, d = 1) => x == null || x !== x ? '—' : sgn(x, d);
const tip = (t, d) => ` data-tip="${esc(t)}"${d ? ` data-doc="${d}"` : ''}`;    // d: نشانی بند سند (ui/docs.js)
// بندهای سند این صفحه (فصل ۳ §۳٫۵ و فصل‌های ۶، ۷ و ۱۴)
const DOC = { rebal: '3:3.5/سیاست ریبالانس', samp: '3:3.5/نمونهٔ کوچک و وام', build: '3:3.5/همتاساز', loan: '3:3.5/وام سود نقدی', ew: '3:3.5/همتای هم‌وزن', ipo: '3:3.5/تأخیر ورود عرضهٔ اولیه', enh: '3:3.5/شاخص بهبودیافته', te: '3:3.5/خطای ردیابی', act: '7:7.4', ret: '7:7.3', cost: '6:6.1', cap: '14:14.2.6', plan: '5:5.8' };
const MTIP = {
  top: 'N بزرگ‌ترین: N سهم با بیشترین ارزش بازار، با وزن ارزش بازارشان (نرمال‌شده). ساده، کم‌گردش و قابل توضیح؛ ولی صنایعی که سهم بزرگ ندارند جا می‌مانند و بتا معمولاً بالای ۱ است.',
  strat: 'طبقه‌ای (صنعت): تعداد سهم هر صنعت از N به نسبت وزن آن صنعت در شاخص، و درون هر صنعت بزرگ‌ترین‌ها؛ وزن‌ها ارزش بازار نرمال‌شده. همهٔ صنایع بزرگ حاضرند، ولی در دادهٔ ما TE آن تقریباً هم‌اندازهٔ «N بزرگ‌ترین» است (فصل ۳ §۳٫۵، جدول).',
  opt: 'بهینه‌سازی TE: روی ۳N بزرگ‌ترین، وزن‌ها طوری انتخاب می‌شوند که (w − b)ᵀΣ(w − b) کمینه شود (فقط‌خرید، Σ انقباضی Ledoit–Wolf روی ۲۵۲ روز)، سپس N وزن برتر نگه داشته و دوباره حل می‌شود. کمترین TE، ولی گردش بیشتر و وابسته به برآورد کوواریانس.',
};
const jf = new Intl.DateTimeFormat('fa-IR-u-ca-persian-nu-latn', { year: 'numeric', month: '2-digit', day: '2-digit' });
const dj = d => jf.format(new Date(d * 864e5));
const jyear = d => +dj(d).split('/')[0], jmonth = d => +dj(d).split('/')[1];
const METHODS = { top: 'N بزرگ‌ترین', strat: 'طبقه‌ای (صنعت)', opt: 'بهینه‌سازی TE' };
// سیاست‌های ریبالانس (tools/build_replica_rebal.py؛ فصل ۳ «سیاست ریبالانس»): ریبالانس = ساخت دوبارهٔ کامل (انتخاب و وزن) با دادهٔ روز بررسی، اجرا روز بعد
const POLS = { w1: 'هفتگی', w2: 'دوهفتگی', m: 'ماهانه', q: 'فصلی', h: 'شش‌ماهه', y: 'سالانه', t5: 'آستانه‌ای ۵٪', t10: 'آستانه‌ای ۱۰٪' };
const PTIP = { w1: 'پایان هر هفتهٔ معاملاتی (آخرین روز معامله پیش از شنبه) سبد دوباره ساخته و روز بعد اجرا می‌شود. نزدیک‌ترین دنبال‌کردن، بیشترین گردش و هزینه.',
  w2: 'یک هفته در میان، پایان هفتهٔ معاملاتی.', m: 'پایان هر ماه شمسی (سیاست پایه).', q: 'فقط پایان خرداد، شهریور، آذر و اسفند؛ بین آن‌ها وزن‌ها با بازده رانش می‌کنند.',
  h: 'فقط پایان شهریور و اسفند.', y: 'فقط پایان اسفند.', t5: 'هر هفته هدف تازه حساب می‌شود، ولی فقط اگر گردش یک‌طرفهٔ لازم (نصف مجموع قدرمطلق تفاوت وزن هدف و وزن رانش‌یافته) دست‌کم ۵٪ باشد معامله می‌شود.',
  t10: 'مانند آستانه‌ای ۵٪ با آستانهٔ ۱۰٪: معاملهٔ کمتر، رانش بیشتر.' };
/** دادهٔ همتاساز سیاست انتخابی (پایه برای ماهانه)؛ ادغام با mergePol. */
const polFile = v => `data/replica${S.tgt === 'ew' ? '_ew' : ''}_rb_${v}.js`;
/** دادهٔ سیاست v برای پایهٔ B: B برای ماهانه، ادغام‌شده اگر فایلش بارگذاری شده و هم‌خوان است، null اگر بارگذاری نشده، false اگر ناهم‌خوان است. */
function polData(B, v) {
  if (v === 'm') return B;
  const P = (root.SIM_REP_RB || {})[`${S.tgt}|${v}`];
  if (!P) return null;
  if (P.asof !== B.asof || P.n_dates !== B.dates.length || P.n_names !== B.names.length) return false;
  return P._R || (P._R = mergePol(B, P));
}
function withPol(B) {
  const d = polData(B, S.pol);
  if (d) return d;
  if (d === null) { const v = S.pol; S.pol = 'm'; setTimeout(() => switchPol(v)); return B; }   // فایل این هدف هنوز بارگذاری نشده (مثلاً پس از تعویض هدف)
  if (root.toast) root.toast(`دادهٔ سیاست «${POLS[S.pol]}» با دادهٔ پایه هم‌خوان نیست؛ ماهانه نشان داده می‌شود. python tools/build_replica_rebal.py${S.tgt === 'ew' ? ' --target ew' : ''}`);
  S.pol = 'm'; return B;
}
/** جدول «مقایسهٔ سیاست‌های ریبالانس» با همین تنظیمات پنل ۱؛ فایل‌های سیاست بار اول بارگذاری می‌شوند. */
function renderCmp() {
  const box = $('rb-cmp-box'); if (!box || !box.open) return;
  const B = S.tgt === 'ew' && root.SIM_REP_EW ? root.SIM_REP_EW : root.SIM_REP, need = Object.keys(POLS).filter(v => polData(B, v) === null && !renderCmp.miss.has(polFile(v)));
  if (need.length) {
    $('rb-cmp').innerHTML = `<div class="mute" style="padding:8px">بارگذاری دادهٔ ${need.length} سیاست…</div>`;
    let left = need.length;
    need.forEach(v => { const sc = document.createElement('script'); sc.src = polFile(v); sc.onload = () => { if (--left === 0) renderCmp(); }; sc.onerror = () => { renderCmp.miss.add(polFile(v)); if (--left === 0) renderCmp(); }; document.head.appendChild(sc); });
    return;
  }
  const key = keyOf(S.method, S.N, S.liq), o = opts();
  const hd = [['سیاست', '', 'سیاست ریبالانس؛ روی ردیف کلیک کنید تا انتخاب شود.'], ['ریبالانس', 'n', 'تعداد ریبالانس اجراشده پس از خرید اولیه، از تاریخ شروع تا امروز.'], ['گردش ماهانه ٪', 'n', 'جمع گردش یک‌طرفهٔ همهٔ اجراها ÷ تعداد ماه‌ها.'],
    ['هزینه در سال', 'n', 'هزینهٔ معامله (گردش × L × هزینهٔ رفت‌وبرگشت) به درصد NAV در سال؛ واحد درصد.'], ['TE رسمی ٪', 'n', 'خطای ردیابی سالانه در برابر شاخص رسمی.'], ['فاصلهٔ بازده', 'n', 'بازده سالانهٔ همتا (پس از هزینه) منهای شاخص؛ واحد درصد در سال.'], ['رشد نسبی ٪', 'n', '(رشد همتا ÷ رشد شاخص) − ۱ از شروع تا امروز.']];
  const rows = Object.keys(POLS).map(v => {
    const Rv = polData(B, v);
    if (!Rv) return `<tr class="weak"><td>${POLS[v]}</td><td colspan="6" class="mute">${Rv === false ? 'داده با پایه هم‌خوان نیست' : 'داده ساخته نشده'} (python tools/build_replica_rebal.py${S.tgt === 'ew' ? ' --target ew' : ''})</td></tr>`;
    const sim = simulate(Rv, key, o), m = metrics(Rv, sim); if (!m) return '';
    const nm = Rv.mstart.length - S.j0, tcy = 100 * sim.cm.reduce((a, x) => a + x, 0) / Math.max(m.years, 1e-9);
    return `<tr data-v="${v}" style="cursor:pointer"${v === S.pol ? ' aria-current="true"' : ''}${tip(PTIP[v], DOC.rebal)}><td>${POLS[v]}</td><td class="n">${sim.nReb}</td><td class="n">${f(100 * sim.toSum / Math.max(nm - 1, 1), 1)}</td><td class="n">${f(tcy, 2)}</td><td class="n">${f(m.te, 2)}</td><td class="n ${m.gap >= 0 ? 'up' : 'down'}">${sg(m.gap)}</td><td class="n ${m.td >= 0 ? 'up' : 'down'}">${sg(m.td)}</td></tr>`;
  }).join('');
  $('rb-cmp').innerHTML = `<table class="dt" id="rb-cmpt"><thead><tr>${hd.map(([t, c, d]) => `<th class="${c}"${tip(d, DOC.rebal)}>${t}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>`;
  $('rb-cmpt').querySelectorAll('tr[data-v]').forEach(tr => { tr.onclick = () => { stale(); $('rb-rpol').value = tr.dataset.v; switchPol(tr.dataset.v); }; });
}
renderCmp.miss = new Set();
/** تعویض سیاست؛ فایل هر سیاست فقط بار اول بارگذاری می‌شود. */
function switchPol(v) {
  if (v === S.pol) return;
  const k = `${S.tgt}|${v}`;
  if (v !== 'm' && !(root.SIM_REP_RB && root.SIM_REP_RB[k])) {
    const s = document.createElement('script'); s.src = polFile(v);
    s.onload = () => { S.pol = v; mount(host); };
    s.onerror = () => { $('rb-rpol').value = S.pol; if (root.toast) root.toast(`دادهٔ سیاست «${POLS[v]}» پیدا نشد: python tools/build_replica_rebal.py${S.tgt === 'ew' ? ' --target ew' : ''}`); };
    document.head.appendChild(s); return;
  }
  S.pol = v; mount(host);
}
const LIQN = { 0: ['بدون فیلتر', 'فیلتر نقدشوندگی ۶۳ روزه اعمال نمی‌شود و همهٔ واجدان بورس نامزد نگهداری‌اند. ولی «بدون فیلتر» یعنی همهٔ نمادهای شاخص نیست:'], 1: ['ملایم', 'نماد باید دست‌کم ۵۰ روز از ۶۳ روز اخیر معامله شده و میانهٔ ارزش معاملاتش بالاتر از صدک ۲۰ واجدان باشد.'],
  2: ['متوسط', 'دست‌کم ۵۶ روز از ۶۳ روز معامله و میانهٔ ارزش معاملات بالاتر از صدک ۴۰ واجدان.'], 3: ['سخت', 'دست‌کم ۶۰ روز از ۶۳ روز معامله و میانهٔ ارزش معاملات بالاتر از صدک ۶۰ واجدان.'] };
// برچسب‌های وابسته به هدف (فصل ۳ «همتای هم‌وزن»): برای «شاخص كل (هم وزن)» روش اول «N نقدشونده‌ترین» است
const MLAB = { k: { top: METHODS.top, tip: MTIP.top, opt: MTIP.opt },
  ew: { top: 'N نقدشونده‌ترین', tip: 'N نقدشونده‌ترین: N سهم با بیشترین میانهٔ ۶۳ روزهٔ ارزش معاملات، با وزن هدف هم‌وزن (رانش‌یافته از آغاز فصل) نرمال‌شده. ساده و قابل‌اجرا؛ ولی سهام کوچک و کم‌معامله را که بخش بزرگ بازده هم‌وزن از آن‌هاست ندارد.',
    opt: 'بهینه‌سازی TE: روی ۳N نقدشونده‌ترین، وزن‌ها طوری انتخاب می‌شوند که (w − b)ᵀΣ(w − b) نسبت به هدف هم‌وزن کمینه شود (فقط‌خرید، Σ انقباضی Ledoit–Wolf ۲۵۲ روزه)؛ سپس N وزن برتر و حل دوباره.' } };
let TN = '«شاخص كل»';
const S = { tgt: 'k', pol: 'm', cmpOpen: false, method: 'opt', N: 30, liq: 0, mode: 'none', cash: 10, br: false, phi: 2, rb: 30, rc: 0, cost: 125, j0: null, pdate: 'live', aum: 1000 };
// فعلاً پنهان در پنل ۱ (تصمیم مالک ۲۰۲۶-۱۰-۲۱): روش «طبقه‌ای» و سهم سهام «تراز بتا»؛ موتور و داده‌شان دست نخورده است
const HIDE_METHOD = new Set(['strat']), HIDE_MODE = new Set(['beta']);
const J0_DEFAULT = 1403;                                                // شروع پیش‌فرض: خرید پایان اسفند ۱۴۰۲، یعنی سنجش از فروردین ۱۴۰۳
let R = null, R0 = null, host = null, last = null;

function mount(el) {
  host = el; const B = S.tgt === 'ew' && root.SIM_REP_EW ? root.SIM_REP_EW : root.SIM_REP;
  if (B !== root.SIM_REP_EW) S.tgt = 'k';
  R = R0 = B ? withPol(B) : B;
  const EWT = S.tgt === 'ew', L_ = MLAB[S.tgt]; METHODS.top = L_.top; MTIP.top = L_.tip; MTIP.opt = L_.opt; CONTRIB.clear();
  TN = EWT ? '«شاخص كل (هم وزن)»' : '«شاخص كل»';
  if (!R) { el.innerHTML = '<section class="panel"><div class="panel-body" style="padding:24px">دادهٔ همتاساز پیدا نشد. اجرا کنید: <code>python tools/build_replica_panel.py</code></div></section>'; return; }
  prep(R);
  if (!R.Ns.includes(S.N)) S.N = R.Ns[Math.floor(R.Ns.length / 2)];
  if (HIDE_METHOD.has(S.method)) S.method = 'opt';
  if (HIDE_MODE.has(S.mode)) S.mode = 'none';
  const nm = R.mstart.length;
  if (S.j0 == null || S.j0 >= nm) { let j = 0; R.sig.forEach((d, i) => { if (jyear(d) < J0_DEFAULT) j = i; }); S.j0 = j; }
  const startOpts = R.sig.map((d, j) => `<option value="${j}"${j === S.j0 ? ' selected' : ''}>${dj(d)}</option>`).join('');
  const dateOpts = `<option value="live">امروز (زنده) · ${esc(R.asof)}</option>` + R.sig.map((d, j) => `<option value="${j}">${dj(d)}</option>`).reverse().join('');
  el.innerHTML = `
  <section class="panel rb-panel" style="--lg:var(--lg-a)">
    <div class="panel-head"><span class="lg-badge">1</span><span class="panel-title"${tip('آزمایشگاه همتا: «شاخص كل» را با N سهم بسازید، فقط نمادهای نقدشونده را راه بدهید، بخشی را نقد نگه دارید یا برای تأخیر پرداخت سود نقدی وام بگیرید، و ببینید اگر از هر ماه گذشته شروع کرده بودید تا امروز چقدر از شاخص فاصله می‌گرفتید. همه‌چیز در مرورگر از سری‌های ازپیش‌ساختهٔ پایتون (tools/build_replica_panel.py و build_replica_rebal.py) حساب می‌شود: ریبالانس طبق سیاست انتخابی (پیش‌فرض ماهانه)، اجرا از روز بعد، بازده کل.', DOC.build)}>همتای خودتان را بسازید و بسنجید</span><span class="chip" id="rb-chip"${tip('نخستین ماه سیگنال تا آخرین روز داده، سیاست ریبالانس و تعداد ریبالانس‌هایی که از تاریخ شروع تا امروز اجرا شده است.', DOC.rebal)}></span></div>
    <div class="rb-grid">
      <div class="rb-ctl">
        <div class="rb-g"><div class="rb-gt"${tip('گام اول: از میان نمادهای واجد بورس، کدام و چند سهم خریده شوند. هرچه N بیشتر، خطای ردیابی کمتر ولی تعداد سفارش و نیاز به نقدشوندگی بیشتر.', DOC.samp)}>۱ · نمونه</div>
          <label${tip('کدام شاخص رسمی کپی شود. «شاخص كل» ارزش‌وزن است (وزن هر سهم ∝ ارزش بازار). «شاخص كل (هم وزن)» همهٔ سهام بورس را با وزن برابر در آغاز هر فصل شمسی دارد و تا فصل بعد با بازده رانش می‌کند؛ بخش بزرگ بازده آن از سهام کوچک و کم‌معامله است، پس با نمونهٔ کوچک بسیار سخت‌تر کپی می‌شود (فصل ۳ «همتای هم‌وزن»).', DOC.ew)}>هدف <span class="seg" id="rb-tgt"><button data-v="k" aria-pressed="false"${tip('«شاخص كل» ارزش‌وزن (TEDPIX با سود).', DOC.build)}>شاخص كل</button><button data-v="ew" aria-pressed="false"${tip('«شاخص كل (هم وزن)» با سود؛ دادهٔ آن بار اول بارگذاری می‌شود (ui/data/replica_ew.js).', DOC.ew)}>شاخص كل (هم وزن)</button></span></label>
          <label${tip('چطور N سهم انتخاب و وزن‌دهی شوند. «N بزرگ‌ترین» ساده و کم‌گردش است؛ «بهینه‌سازی TE» با کوواریانس، نوسان تفاضل با شاخص را کمینه می‌کند (کمترین TE ولی گردش بیشتر).', DOC.samp)}>روش <span class="seg" id="rb-method">${Object.entries(METHODS).filter(([k]) => !HIDE_METHOD.has(k)).map(([k, t]) => `<button data-v="${k}" aria-pressed="false"${tip(MTIP[k], DOC.samp)}>${t}</button>`).join('')}</span></label>
          <label${tip(`N: تعداد سهامی که واقعاً خریده می‌شود. خطای ردیابی با N تند پایین می‌آید و بعد به «کف خطا» نزدیک می‌شود (خطای خرید همهٔ واجدان در برابر شاخص رسمی از نخستین ماه داده: ${f(floorTE(R, 0), 2)}٪). برای انتخاب N، پاسخ پنل ۳ پایین صفحه را ببینید؛ توضیح هر گزینه در فهرست آمده است.`, DOC.samp)}>تعداد سهام <select id="rb-n">${R.Ns.map(n => `<option data-tip="نمونهٔ ${n} سهمی: ${nTip(R, n)}">${n}</option>`).join('')}</select></label>
          <label${tip('فیلتر ورود به نمونه بر پایهٔ ۶۳ روز باز اخیر: چند روز معامله شده و میانهٔ ارزش معاملات روزانه در چه صدکی از واجدان است. این فیلتر روی «واجدان» اعمال می‌شود که خودشان پیش‌تر کم‌سابقه‌ها و کم‌معامله‌های شدید را کنار گذاشته‌اند (راهنمای «بدون فیلتر»). هدف (وزن شاخص) عوض نمی‌شود، فقط نامزدها کم می‌شوند؛ پس TE کمی بالا می‌رود ولی همتا با سرمایهٔ بزرگ‌تر و بدون گیرکردن در صف ساخته می‌شود.', DOC.build)}>نقدشوندگی <span class="seg" id="rb-liq">${Object.keys(R.liq).map(q => `<button data-v="${q}" aria-pressed="false"${tip(q === '0' ? LIQN[q][1] + ' ' + eligTxt(R) : LIQN[q][1] + ' روی همان واجدان اعمال می‌شود.', DOC.build)}>${LIQN[q][0]}</button>`).join('')}</span></label>
        </div>
        <div class="rb-g"><div class="rb-gt"${tip('گام دوم: چه سهمی از سرمایه در سهام باشد (L ≤ ۱؛ وام برای اهرم مجاز نیست) و آیا برای تأخیر پرداخت سود نقدی وام گرفته شود. سود نقدی همیشه با تأخیر واقعی پرداخت حساب می‌شود: روز استحقاق از سهام جدا و «طلب» می‌شود و تا روز پرداخت (فارابی/fundai، وگرنه ۹۶ روز) بی‌بازده می‌ماند.', DOC.loan)}>۲ · نقد و وام سود</div>
          <label${tip('L = سهم سهام از سرمایهٔ قابل‌سرمایه‌گذاری، در هر ریبالانس (طبق سیاست ریبالانس گام ۳) دوباره تنظیم می‌شود. «تمام» یعنی L = ۱؛ «نقد ثابت» L = ۱ − نقد. هیچ گزینه‌ای L > ۱ (وام برای خرید بیشتر) نمی‌دهد.', DOC.build)}>سهم سهام <span class="seg" id="rb-mode">
        <button data-v="none" aria-pressed="false"${tip('L = ۱: همهٔ سرمایه (جز طلب سود) در سهام نمونه.', DOC.build)}>تمام</button><button data-v="cash" aria-pressed="false"${tip('L = ۱ − درصد نقد. نقد با «بازده نقد» رشد می‌کند. بتا و نوسان کم می‌شود ولی در بازار صعودی عقب می‌مانید.', DOC.build)}>نقد ثابت</button></span></label>
          <label id="rb-amt-l"${tip('درصد سرمایه که نقد نگه داشته می‌شود (L = ۱ − این عدد). حداکثر ۵۰٪.', DOC.build)}><span id="rb-amt-t">نقد ٪</span> <input type="number" id="rb-amt" value="10" min="0" max="50" step="5"></label>
          <label${tip('وام فقط برای تأخیر پرداخت سود نقدی، نه اهرم: روز استحقاق دقیقاً به اندازهٔ طلب سود وام گرفته و در سهام می‌ماند؛ روز پرداخت، سود وام را تسویه می‌کند. بدهی هرگز از طلب سود بیشتر نمی‌شود و بهرهٔ اضافه از فروش سهام پرداخت می‌شود. بدون وام، سود تا روز پرداخت بی‌بازده است.', DOC.loan)}>وام سود <span class="seg" id="rb-br"><button data-v="0" aria-pressed="false"${tip('بدون وام: طلب سود تا روز پرداخت بی‌بازده می‌ماند.', DOC.loan)}>بدون</button><button data-v="1" aria-pressed="false"${tip('وام سود نقدی با «نرخ وام»؛ سقف وام = طلب سود.', DOC.loan)}>وام سود نقدی</button></span></label>
          <label id="rb-rb-l"${tip('نرخ سادهٔ سالانهٔ وام سود؛ بهره هر روز به نسبت روزهای تقویمی به بدهی اضافه می‌شود. پیش‌فرض ۳۰٪ فرضی است [تأیید لازم]؛ نرخ اعتبار کارگزاری یا تأمین مالی صندوق را بگذارید. اگر نرخ از بازده بازار بیشتر باشد وام زیان می‌دهد.', DOC.loan)}>نرخ وام ٪ <input type="number" id="rb-rb" value="30" min="0" max="80" step="1"></label>
          <label${tip('بازده سالانهٔ بخش نقد، مثلاً صندوق درآمد ثابت [راستی‌آزمایی نشده]؛ صفر یعنی نقد بی‌بهره. فقط وقتی نقد نگه داشته می‌شود اثر دارد.', DOC.build)}>بازده نقد ٪ <input type="number" id="rb-rc" value="0" min="0" max="80" step="1"></label>
          <label${tip('نماد تازهٔ بزرگ (وزن روز دوم در شاخص ≥ ۰٫۳٪، مثل «تابان» ۱۴۰۵) از روز پس از عرضهٔ اولیه در «شاخص كل» است ولی معمولاً روزها در صف خرید می‌ماند. همتا هر روز سفارش خرید می‌گذارد و حداکثر این درصد از ارزش معاملات آن روز نماد را می‌گیرد (جای صندوق در صف نامعلوم است [تأیید لازم])، تا به وزن شاخص برسد. صفر یعنی تا واجدیت عادی (حدود ۲۰۰ روز) نخریدن، مثل قاعدهٔ پیشین.', DOC.ipo)}>نماد تازه: سهم از معاملات ٪ <input type="number" id="rb-phi" value="2" min="0" max="50" step="0.5"></label>
          <label${tip('اندازهٔ صندوق؛ سقف خرید روزانهٔ نماد تازه = سهم بالا × ارزش معاملات روز ÷ این عدد. صندوق بزرگ‌تر کندتر به وزن شاخص می‌رسد. همان عدد زبانهٔ «پرتفوی» است.', DOC.ipo)}>اندازهٔ صندوق (میلیارد ریال) <input type="number" id="rb-aum2" value="1000" min="1" step="100"></label>
        </div>
        <div class="rb-g"><div class="rb-gt"${tip('گام سوم: هر چند وقت سبد دوباره ساخته شود، با چه هزینه‌ای و از چه تاریخی بسنجیم. نتیجه همیشه «از شروع تا امروز» است؛ جدول «اگر از سال‌های گذشته شروع می‌کردیم» در پنل ۲ همین را برای همهٔ سال‌ها نشان می‌دهد.', DOC.build)}>۳ · ریبالانس و سنجش</div>
          <label${tip('سیاست ریبالانس: هر ریبالانس انتخاب N سهم و وزن‌ها را با دادهٔ همان روز از نو می‌سازد و روز بعد اجرا می‌کند؛ بین دو ریبالانس وزن‌ها با بازده رانش می‌کنند. ریبالانس بیشتر ⇒ دنبال‌کردن نزدیک‌تر ولی گردش و هزینهٔ معامله بیشتر؛ هزینهٔ هر اجرا = گردش × L × هزینهٔ رفت‌وبرگشت و در خود اعداد کسر شده است. «آستانه‌ای» هر هفته بررسی می‌کند ولی فقط وقتی فاصله از هدف زیاد شده معامله می‌کند. شاخص بهبودیافته (پنل ۴) همیشه ماهانه است.', DOC.rebal)}>سیاست ریبالانس <select id="rb-rpol">${Object.entries(POLS).map(([k, t]) => `<option value="${k}" data-tip="${esc(PTIP[k])}"${k === S.pol ? ' selected' : ''}>${t}</option>`).join('')}</select></label>
          <label${tip('هزینهٔ رفت‌وبرگشت (خرید + فروش) بر حسب واحد پایه؛ ۱۰۰ bp = ۱٪. در هر ریبالانس: هزینه = گردش یک‌طرفه × L × این عدد. کارمزد، مالیات فروش و لغزش قیمت را با هم بگیرید؛ پیش‌فرض همهٔ برنامه ۱۲۵ bp است [تأیید لازم].', DOC.cost)}>هزینه (bp) <input type="number" id="rbx-cost" value="125" min="0" step="5"></label>
          <label${tip('فرض کنید همتا را در پایان این ماه شمسی خریده بودید. همهٔ اعداد (TE، فاصله، تفاوت تجمعی، مقایسهٔ سیاست‌ها) از همین ماه تا آخرین روز داده حساب می‌شود. پیش‌فرض پایان اسفند ۱۴۰۲ است، یعنی سنجش از فروردین ۱۴۰۳. شروع‌های دیرتر کوتاه‌اند و نویز بیشتری دارند.', DOC.build)}>شروع از <select id="rb-j0">${startOpts}</select></label>
        </div>
      </div>
      <div class="rb-out">
        <div class="lineage rb-lead" id="rbx-read"></div>
        <div class="kpis" id="rb-kpi"></div>
        <details class="sam-fold sm"><summary${tip('عددهای تکمیلی: TE فقط از نمونه‌گیری (در برابر خرید همهٔ واجدان)، بتا و همبستگی با شاخص، میانگین L، گردش ماهانه و پوشش وزن شاخص.', DOC.build)}>شاخص‌های بیشتر</summary><div class="kpis" id="rb-kpi2"></div></details>
        <details class="sam-fold sm" id="rb-cmp-box"${S.cmpOpen ? ' open' : ''}><summary${tip('همین همتا (هدف، روش، N، نقدشوندگی، نقد، وام، هزینه و تاریخ شروع) با هر هشت سیاست ریبالانس، کنار هم: تعداد ریبالانس، گردش، هزینهٔ معامله در سال، TE و فاصلهٔ بازده. ریبالانس بیشتر TE را کم می‌کند ولی هزینه را بالا می‌برد؛ ستون «فاصلهٔ بازده» هر دو را با هم دارد.', DOC.rebal)}>مقایسهٔ سیاست‌های ریبالانس با همین تنظیمات</summary><div class="panel-body scroll" id="rb-cmp"></div></details>
    <div class="panel-body" style="padding:var(--s-3)"><div class="mute" style="font-size:var(--fs-xs)" id="rb-ch1-t"></div><div id="rb-ch1"></div><div class="mute" style="font-size:var(--fs-xs);margin-top:8px" id="rb-ch2-t"></div><div id="rb-ch2"></div><div class="mute" style="font-size:var(--fs-xs);margin-top:8px" id="rb-ch3-t" data-tip="هر ستون یک دورهٔ نگهداری (ریبالانس تا ریبالانس بعد): سبز یعنی همتا جلوتر از «شاخص كل» رسمی، قرمز یعنی عقب‌تر. با نگه‌داشتن نشانگر روی هر ستون، اختلاف به چهار جزء (انتخاب سهام، اعضا و داده، نقد/وام، هزینه) تقسیم و محتمل‌ترین علت با نمادهای مؤثر نشان داده می‌شود." data-doc="3:3.5/همتاساز">اختلاف هر دوره بین همتا و شاخص (واحد درصد؛ سبز جلوتر، قرمز عقب‌تر) — نشانگر را روی هر ستون نگه دارید تا علت تحلیل شود</div><div id="rb-ch3"></div><div class="mute" id="rb-hov" style="font-size:var(--fs-2xs);min-height:1.4em"></div></div>
      </div>
    </div>
  </section>
  <section class="panel" style="--lg:var(--lg-b)">
    <div class="panel-head"><span class="lg-badge">2</span><span class="panel-title"${tip('همان تنظیمات پنل ۱ از دو زاویهٔ دیگر: (۱) حساسیت به زمان شروع: اگر ابتدای هر سال شمسی شروع کرده بودید؛ (۲) خود پرتفوی: کدام سهم‌ها با چه وزنی در هر تاریخ، در برابر وزن شاخص.', DOC.build)}>جزئیات همین همتا</span>
      <div class="seg" id="rb-dtabs"><button data-t="port" aria-pressed="true"${tip('فهرست سهام و وزن‌هایی که در تاریخ سیگنال انتخاب‌شده می‌خریدید، کنار وزن همان سهم در شاخص. «امروز (زنده)» پرتفوی قابل اجرای روز کاری بعد است و می‌توان آن را به «پرتفو ← ۲ سفارش» فرستاد.', DOC.build)}>پرتفوی در یک تاریخ</button><button data-t="years" aria-pressed="false"${tip('هر ردیف: همین همتا اگر از پایان اسفند آن سال شروع شده بود، تا امروز. نشان می‌دهد نتیجهٔ پنل ۱ به تاریخ شروع حساس است یا نه. ردیف تاریخ شروع فعلی برجسته است.', DOC.build)}>اگر از سال‌های گذشته شروع می‌کردیم</button></div>
      <div class="panel-tools" id="rb-ptools"><button class="tool" id="rbx-csv"${tip('دریافت فهرست نماد، صنعت، وزن همتا و وزن شاخص همین تاریخ به‌صورت CSV.')}>CSV</button><button class="tool" id="rb-plan"${tip('فقط برای «امروز»: وزن‌ها (ضرب در L اگر نقد دارید) به «پرتفو ← ۲ سفارش» می‌رود تا با پرتفوی فعلی مقایسه و سفارش خرید و فروش با تعداد و قیمت مرجع ساخته شود.', DOC.plan)}>ارسال به سفارش ←</button></div></div>
    <div id="rb-d-years" hidden><div class="panel-body scroll" style="max-height:340px"><table class="dt" id="rb-years"></table></div></div>
    <div id="rb-d-port">
      <div class="ctl"><label${tip('تاریخ سیگنال (پایان ماه شمسی). پرتفوی فقط با داده‌ای که آن روز در دسترس بود ساخته می‌شود (بدون نگاه به آینده) و از روز کاری بعد اجرا می‌شود. برای تاریخ‌های گذشته، خطای ۲۵۲ روز بعدش هم نشان داده می‌شود.', DOC.build)}>تاریخ <select id="rb-date">${dateOpts}</select></label>
        <label${tip('اندازهٔ صندوق یا سبد شما. برای هر نماد: روز لازم = وزن × سرمایه ÷ (۱۰٪ × میانهٔ ارزش معاملات روزانه). بیش از ۵ روز قرمز می‌شود، یعنی خرید آن نماد قیمت را جابه‌جا می‌کند. فقط برای «امروز».', DOC.cap)}>سرمایه (میلیارد ریال) <input type="number" id="rb-aum" value="1000" min="1" step="10"></label></div>
      <div class="kpis" id="rb-pkpi"></div>
      <div class="panel-body scroll" style="max-height:440px"><table class="dt" id="rb-ptab"></table></div>
      <div class="lineage" id="rb-plin"></div>
    </div>
  </section>
  <details class="sam-fold panel" id="rb-enh-box"><summary${tip('پیشرفته: به‌جای کپی دقیق «شاخص كل»، هدف را آگاهانه عوض کنید (کم یا زیاد کردن صنعت، تیلت به یک معیار مثل کم‌نوسان، سقف وزن هر سهم، آمیختن با هم‌وزن) و با همان N سهم و روش بسازید. خروجی: هدف تازه چقدر از شاخص فاصله می‌گیرد و چه بازده اضافه‌ای داشته است.', DOC.enh)}><span class="lg-badge">4</span> شاخص بهبودیافته (پیشرفته): هدف را با تیلت و قید تغییر دهید</summary><div id="rb-enh"></div></details>`;
  const seg = (id, key, cb) => $(id).querySelectorAll('button').forEach(b => { b.onclick = () => { if (key !== 'mode') stale(); S[key] = key === 'liq' ? +b.dataset.v : b.dataset.v; cb && cb(); render(); }; });
  seg('rb-method', 'method'); seg('rb-liq', 'liq'); seg('rb-mode', 'mode');
  $('rb-tgt').querySelectorAll('button').forEach(b => { b.setAttribute('aria-pressed', String(b.dataset.v === S.tgt)); b.onclick = () => switchTgt(b.dataset.v); });
  $('rb-enh-box').hidden = EWT;                                         // شاخص بهبودیافته فقط روی هدف ارزش‌وزن
  { const slot = document.getElementById('rb-enh-slot'); if (slot) { slot.innerHTML = ''; slot.appendChild($('rb-enh-box')); } }   // پنل ۴ پس از پنل ۳ صفحه
  $('rb-br').querySelectorAll('button').forEach(b => { b.onclick = () => { S.br = b.dataset.v === '1'; render(); }; });

  $('rb-dtabs').querySelectorAll('button').forEach(b => { b.onclick = () => {                 // زبانه‌های «جزئیات همین همتا»
    const port = b.dataset.t === 'port';
    $('rb-dtabs').querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    $('rb-d-years').hidden = port; $('rb-d-port').hidden = !port; $('rb-ptools').hidden = !port;
  }; });
  $('rb-n').onchange = e => { stale(); S.N = +e.target.value; render(); };
  $('rb-amt').onchange = e => { S.cash = +e.target.value; render(); };
  $('rb-rb').onchange = e => { S.rb = +e.target.value; render(); }; $('rb-rc').onchange = e => { S.rc = +e.target.value; render(); };
  $('rbx-cost').onchange = e => { S.cost = +e.target.value; render(); };
  $('rb-j0').onchange = e => { S.j0 = +e.target.value; render(); };
  $('rb-rpol').onchange = e => { stale(); switchPol(e.target.value); };
  $('rb-cmp-box').ontoggle = () => { S.cmpOpen = $('rb-cmp-box').open; renderCmp(); };
  $('rb-date').onchange = e => { S.pdate = e.target.value; renderPort(); };
  $('rb-aum').onchange = e => { S.aum = +e.target.value; $('rb-aum2').value = S.aum; render(); };
  $('rb-aum2').onchange = e => { S.aum = Math.max(1, +e.target.value || 1); $('rb-aum').value = S.aum; render(); };
  $('rb-phi').onchange = e => { S.phi = Math.max(0, +e.target.value || 0); render(); };
  $('rb-n').value = S.N;
  if (root.SIM_ENH_MOUNT) root.SIM_ENH_MOUNT($('rb-enh'), root.SIM_RB_API);
  setChip();
  render();
}
const opts = () => ({ mode: S.mode === 'none' ? 'none' : S.mode === 'beta' ? 'beta' : 'fixed', L: S.mode === 'cash' ? 1 - S.cash / 100 : 1, loan: S.br, phi: S.phi / 100, aum: S.aum, rb: S.rb / 100, rc: S.rc / 100, cost: S.cost, j0: S.j0 });
const curKey = () => R === R0 ? keyOf(S.method, S.N, S.liq) : 'enh';
const stale = () => { if (R !== R0) { R = R0; if (root.SIM_ENH_STALE) root.SIM_ENH_STALE(); } };
root.SIM_RB_API = { set(Rx) { R = Rx || R0; if (host) render(); }, state: () => ({ method: S.method, N: S.N, liq: S.liq }) };

/** تعویض هدف همتا؛ دادهٔ هم‌وزن فقط بار اول بارگذاری می‌شود (tools/build_replica_panel.py --target ew) */
function switchTgt(v) {
  if (v === S.tgt) return;
  if (v === 'ew' && !root.SIM_REP_EW) {
    const s = document.createElement('script'); s.src = 'data/replica_ew.js';
    s.onload = () => { S.tgt = 'ew'; mount(host); };
    s.onerror = () => { if (root.toast) root.toast('دادهٔ همتای هم‌وزن پیدا نشد: python tools/build_replica_panel.py --target ew'); };
    document.head.appendChild(s); return;
  }
  S.tgt = v; mount(host);
}
/** واجدیت از دادهٔ صفحه: نمادهای «شاخص كل» امروز (R.live_b)، واجدان آخرین ماه (R.b) و وزن شاخص ناواجدان. */
function eligTxt(R) {
  const lb = R.live_b, bj = R.b[R.b.length - 1], el = new Set(bj[0]), nIdx = lb[0].length, nEl = bj[0].length;
  let wOut = 0; lb[0].forEach((i, p) => { if (!el.has(i)) wOut += lb[1][p] / 1e5; });
  return `«شاخص كل» امروز ${nIdx} نماد بورسی دارد؛ ${nEl} تای آن در آخرین ماه «واجد» بودند و ${nIdx - nEl} نماد (≈ ${f(100 * wOut, 1)}٪ وزن شاخص) حتی در حالت «بدون فیلتر» نامزد نمونه نیستند. قاعدهٔ واجدیت: در ۲۵۲ روز اخیر دست‌کم ۸۰٪ روزها قیمت و دست‌کم نیمی از روزها حرکت قیمت. جدا از این، ۲۷ شرکت سرمایه‌گذاری استانی سهام عدالت («وس…») هرگز نامزد نمونه نیستند (تصمیم ساخت)، ولی در هدف می‌مانند. پس دو گروه بیرون می‌مانند: نماد با سابقهٔ کوتاه (معمولاً عرضهٔ تازه) و نماد کم‌معامله یا طولانی متوقف. این نمادها در هدف و «همتای کامل» هستند و در کف خطا حساب می‌شوند؛ فقط نمونهٔ N سهمی آن‌ها را نمی‌خرد، جز نماد تازهٔ بزرگ که لایهٔ عرضهٔ اولیه حداکثر یک سال جدا نگه می‌دارد.`;
}
/** کف خطا: TE «همتای کامل» (خرید همهٔ واجدان، R.C) در برابر شاخص رسمی (R.K) از ماه j0 تا آخرین روز. */
function floorTE(R, j0) {
  const p = prep(R), d = []; for (let t = R.mstart[j0] + 1; t < R.dates.length; t++) d.push(p.C[t] - p.K[t]);
  return d.length > 30 ? sd(d) * Math.sqrt(252) * 100 : NaN;
}
/** راهنمای هر N از همین داده: TE «بهینه‌سازی TE»، بدون فیلتر، تمام در سهام، از نخستین ماه (پایهٔ ماهانه). */
function nTip(R, n) {
  const k = keyOf('opt', n, 0); if (!R.configs[k]) return '';
  const m = metrics(R, simulate(R, k, { mode: 'none', L: 1, loan: false, phi: S.phi / 100, aum: S.aum, rb: 0, rc: 0, cost: S.cost, j0: 0 }));
  return m ? `با «بهینه‌سازی TE»، بدون فیلتر، از نخستین ماه: TE ≈ ${f(m.te, 1)}٪ و فاصلهٔ بازده سالانه ${sg(m.gap)} واحد.${n < 30 ? ' ردیابی ضعیف؛ فقط برای سرمایهٔ خیلی کوچک.' : n >= 80 ? ' نزدیک کف خطا؛ نیاز به نقدشوندگی بیشتر.' : ''}` : '';
}
function setChip() { $('rb-chip').textContent = `${dj(R.sig[0])} → ${dj(R.dates[R.dates.length - 1])} · ریبالانس ${R === R0 ? POLS[S.pol] : 'ماهانه'}${last && last.sim ? ` (${last.sim.nReb + 1} بار)` : ''}${R === R0 ? '' : ' · هدف تیلت‌شده'}`; }
function render() {
  if (!host) return;
  setChip();
  ['rb-method', 'rb-liq', 'rb-mode'].forEach(id => $(id).querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v) === String({ 'rb-method': S.method, 'rb-liq': S.liq, 'rb-mode': S.mode }[id]))));
  $('rb-amt-l').style.display = S.mode === 'cash' ? '' : 'none'; $('rb-amt').value = S.cash;
  $('rb-br').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String((b.dataset.v === '1') === S.br)));
  $('rb-rb-l').style.display = S.br ? '' : 'none';
  const o = opts(), key = curKey(), sim = simulate(R, key, o), m = metrics(R, sim), cv = curves(R, sim), c = R.configs[key], nm = R.mstart.length;
  last = { sim, m, cv }; setChip();
  let sL = 0, cnt = 0; for (let j = S.j0; j < nm; j++) { sL += sim.Ls[j]; cnt++; }
  const sT = sim.toSum, tcy = m ? 100 * sim.cm.reduce((a, x) => a + x, 0) / Math.max(m.years, 1e-9) : NaN, m0 = metrics(R, simulate(R, key, { ...o, cost: 0 }));
  const capNow = c.live[2];
  const bj = R.b[nm - 1], bmap = new Map(bj[0].map((i, p) => [i, bj[1][p]])), covB = c.sel[nm - 1][0].reduce((a, i) => a + (bmap.get(i) || 0), 0) / 1e5;
  const yrs = m ? m.years : 0;
  const kp = m ? [['TE در برابر شاخص رسمی', f(m.te, 2) + '٪', `خطای ردیابی (Tracking Error) سالانه: انحراف معیار «بازده روزانهٔ همتا منهای شاخص» × √۲۵۲؛ یعنی در یک سال معمولی، بازده همتا حدوداً این‌قدر بالا یا پایین شاخص می‌افتد. زیر ۲٪ خوب، ۳ تا ۵٪ متوسط، بالای ۶٪ ضعیف. کف آن (خرید همهٔ واجدان) در همین بازه ${f(floorTE(R, S.j0), 2)}٪ است. هزینهٔ هر ریبالانس در روز همان ریبالانس از NAV کم می‌شود و جزئی از همین اختلاف روزانه است؛ برای همین در هدف پرگردش، کم‌کردن هزینه ممکن است TE را کمی بالا ببرد: اگر همتا در روزهای ریبالانس اتفاقاً جلوتر از شاخص بوده، کسر هزینه همان روزها را به میانگین نزدیک می‌کرد. «TE پیش از هزینه» (شاخص‌های بیشتر) همین را بدون هزینه نشان می‌دهد.`, DOC.te],
    ['TE در برابر همتای کامل', f(m.teC, 2) + '٪', 'همان TE ولی در برابر «همتای کامل» (خرید همهٔ واجدان با وزن بازار) نه شاخص رسمی؛ پس فقط هزینهٔ «کم‌خریدن» را می‌سنجد و خطای ناشی از تفاوت اعضا (شرط واجدیت همتا (سابقهٔ ۲۵۲ روزه؛ نماد تازه‌عرضه یا کم‌تحرک در همتا نیست ولی در شاخص هست) و به‌روزرسانی اعضا فقط در ریبالانس) و داده را ندارد. فاصلهٔ این با TE رسمی، سهم خطایی است که با N بیشتر حل نمی‌شود.', DOC.te],
    ['فاصلهٔ بازده سالانه (واحد درصد)', sg(m.gap), 'بازده مرکب سالانهٔ همتا (پس از هزینه و بهره) منهای بازده سالانهٔ «شاخص كل» رسمی با سود نقدی. منفی یعنی همتا هر سال به‌طور متوسط این‌قدر عقب ماند. TE نوسانِ این فاصله است؛ خود فاصله ممکن است سیستماتیک باشد، مثلاً چون نمونهٔ بزرگ‌ها دم سهام کوچک بازار را ندارد.', DOC.ret],
    ['هزینهٔ معامله در سال', f(tcy, 2), 'جمع هزینهٔ همهٔ ریبالانس‌ها (گردش × L × هزینهٔ رفت‌وبرگشت، بدون خرید اولیه) به درصد NAV، تقسیم بر سال‌ها؛ واحد درصد در سال. همین مقدار در «فاصلهٔ بازده سالانه» کسر شده است و اثرش بر بازده سالانه ≈ این عدد × (۱ + بازده سالانه) است، چون هزینه کسری از NAV است. برای مقایسهٔ سیاست‌ها کنار TE ببینید.', DOC.rebal],
    ['تفاوت تجمعی تا امروز', sg(m.td) + '٪', `به زبان پول: اگر از ${dj(R.sig[S.j0])} تا امروز (${f(yrs, 1)} سال) ۱۰۰ ریال در همتا و ۱۰۰ ریال در شاخص بود، همتا این‌قدر درصد بیشتر یا کمتر داشت: (رشد همتا ÷ رشد شاخص) − ۱. مثبت یعنی جلوتر از شاخص.`, DOC.build],
    ['بتا', f(m.beta, 2), 'شیب رگرسیون بازده روزانهٔ همتا روی شاخص: اگر شاخص ۱٪ بالا رود، همتا به‌طور متوسط β٪ بالا می‌رود. بالای ۱ یعنی پرنوسان‌تر از بازار (معمول در نمونهٔ کوچک)؛ نقد آن را پایین و وام بالا می‌برد.', DOC.act],
    ['TE پیش از هزینه', f(m0 ? m0.te : NaN, 2) + '٪', 'همان TE با هزینهٔ معامله صفر: فقط خطای ردیابی ناشی از ترکیب سبد، نقد/وام و تأخیر سود. فاصلهٔ آن با TE اصلی اثر افت‌های یک‌روزهٔ هزینه در روزهای ریبالانس است؛ اگر این عدد از TE اصلی بزرگ‌تر باشد، یعنی همتا در روزهای ریبالانس این بازه اتفاقاً جلوتر از شاخص بوده و کسر هزینه آن روزها را به میانگین نزدیک کرده است (اثر نمونه، نه سوگیری).', DOC.te],
    ['همبستگی', f(m.corr, 3), 'همبستگی بازده روزانهٔ همتا و شاخص (۱ یعنی هم‌حرکت کامل). بالای ۰٫۹۹ یعنی تقریباً همهٔ حرکت روزانهٔ شاخص را دارید؛ هرچه پایین‌تر، TE بیشتر.', DOC.act]] : [];
  const kp2 = [['میانگین L', f(sL / cnt, 2), 'میانگین سهم سهام از سرمایهٔ قابل‌سرمایه‌گذاری در ماه‌های آزمون: ۱ یعنی همه در سهام، زیر ۱ بخشی نقد (نقد ثابت). هرگز بالای ۱ نیست.', DOC.build],
    ...(R.ipo ? [['اثر تأخیر ورود عرضهٔ اولیه', sg(m ? 100 * sim.ipoD.slice(sim.t0 + 1).reduce((a, x) => a + x, 0) / Math.max(m.years, 1e-9) : NaN, 2) + ' در سال', 'واحد درصد در سال: (وزن خریده‌شدهٔ نماد تازه − وزنش در شاخص) × (بازده نماد − بازده بقیهٔ همتا)، جمع روزها ÷ سال. منفی یعنی رشد روزهای صف خرید را نداشتیم. با «سهم از معاملات» بیشتر یا صندوق کوچک‌تر کمتر می‌شود؛ بخشی (روز اول پس از عرضه) اجتناب‌ناپذیر است.', DOC.ipo],
      ['وزن نماد تازه در همتا (امروز)', f(100 * sim.ipoNow, 2) + '٪', 'سهم نمادهای تازهٔ بزرگ (لایهٔ عرضهٔ اولیه) از سهام همتا در آخرین روز؛ با وزنشان در شاخص مقایسه کنید (زبانهٔ «پرتفوی»).', DOC.ipo]] : []),
    ['طلب سود میانگین', f(100 * sim.rcvAvg, 2) + '٪ NAV', sim.hasDiv ? 'میانگین سود نقدیِ تصویب‌شده و هنوز پرداخت‌نشده نسبت به NAV. بدون وام این مبلغ بی‌بازده است (اصطکاک تأخیر سود)؛ با وام سود همین مبلغ وام گرفته و سرمایه‌گذاری می‌شود.' : 'این هدف برنامهٔ پرداخت سود ندارد (شاخص بهبودیافته)؛ سود نقدی مانند بازده کل همان روز استحقاق سرمایه‌گذاری می‌شود.', DOC.loan],
    ['وام سود میانگین', S.br ? f(100 * sim.debtAvg, 2) + '٪ NAV' : '—', 'میانگین وام سود نقدی نسبت به NAV؛ سقف آن همیشه طلب سود است. بهرهٔ کل پرداختی دورهٔ آزمون: ' + f(100 * sim.interest, 2) + '٪ سرمایهٔ اولیه.', DOC.loan], ['گردش ماهانهٔ یک‌طرفه', f(100 * sT / Math.max(cnt - 1, 1), 0) + '٪', 'گردش یک‌طرفه: نصف مجموع قدرمطلق تغییر وزن‌ها در هر ریبالانس؛ جمع همهٔ ریبالانس‌های اجراشده ÷ تعداد ماه‌ها (پیش از ضرب در L). هزینهٔ ماهانه ≈ این عدد × هزینهٔ رفت‌وبرگشت. «بهینه‌سازی TE» و ریبالانس پرتکرار گردش بیشتری دارند.', DOC.cost],
    ['ریبالانس اجراشده', `${sim.nReb}`, `تعداد ریبالانس‌های اجراشده پس از خرید اولیه با سیاست «${R === R0 ? POLS[S.pol] : 'ماهانه'}». در سیاست آستانه‌ای فقط بررسی‌هایی شمرده می‌شوند که به معامله رسیدند.`, DOC.rebal],
    ['ظرفیت امروز (میلیارد ریال)', f(capNow, 0), 'بزرگ‌ترین سرمایه‌ای که پرتفوی امروز را در یک روز می‌سازد، اگر از هر نماد بیش از ۱۰٪ ارزش معاملات روزانه‌اش (میانهٔ ۶۳ روز) نخرید؛ محدودکننده کم‌نقدشونده‌ترین نماد نسبت به وزنش است. برای سرمایهٔ بزرگ‌تر، فیلتر نقدشوندگی را سخت‌تر کنید یا ساخت را چندروزه ببینید.', DOC.cap],
    ['پوشش وزن شاخص (آخرین ماه)', f(100 * covB, 0) + '٪', 'چند درصد از وزن «شاخص كل» در سهام نمونه است. مثلاً ۷۰٪ یعنی ۳۰٪ از شاخص (معمولاً سهام کوچک‌تر) اصلاً خریده نشده و روش انتخاب باید با وزن‌دهی جبرانش کند.', DOC.build]];
  const kpiHtml = a => a.map(([k, v, t, d]) => `<div class="kpi"${tip(t, d || DOC.build)}><div class="k"${tip(t, d || DOC.build)}>${k}</div><div class="v num">${v}</div></div>`).join('');
  // چهار عدد اصلی: چقدر دقیق، چقدر عقب، از شروع تا امروز، چقدر قابل ساخت؛ بقیه در «شاخص‌های بیشتر»
  const MAIN = new Set(['TE در برابر شاخص رسمی', 'فاصلهٔ بازده سالانه (واحد درصد)', 'هزینهٔ معامله در سال', 'تفاوت تجمعی تا امروز', 'ظرفیت امروز (میلیارد ریال)']), all = [...kp, ...kp2];
  $('rb-kpi').innerHTML = kpiHtml(all.filter(x => MAIN.has(x[0]))); $('rb-kpi2').innerHTML = kpiHtml(all.filter(x => !MAIN.has(x[0])));
  if (m) {
    const ov = (S.mode === 'none' ? 'تمام در سهام' : S.mode === 'cash' ? `${S.cash}٪ نقد` : 'تراز بتا (فقط نقد)') + (S.br ? '، با وام سود نقدی' : '، بدون وام');
    $('rbx-read').innerHTML = `<span><b${tip('جمع‌بندی خودکار همین تنظیمات به زبان ساده؛ با هر تغییر دوباره نوشته می‌شود.', DOC.build)}>خوانش</b> اگر از ${dj(R.sig[S.j0])} همتایی با ${S.N} سهم (${METHODS[S.method]}، نقدشوندگی ${LIQN[S.liq][0]}، ریبالانس ${R === R0 ? POLS[S.pol] : 'ماهانه'}، ${ov}) ساخته بودیم، تا امروز (${f(yrs, 1)} سال) ارزش همتا نسبت به شاخص رسمی ${sg(m.td)}٪ تفاوت داشت و خطای ردیابی سالانه ${f(m.te, 1)}٪ بود.</span><span><b${tip('فرض‌های شبیه‌سازی: سود نقدی با تأخیر واقعی پرداخت (بدون وام تا روز پرداخت بی‌بازده؛ با وام سود سرمایه‌گذاری‌شده با هزینهٔ بهره)، ریبالانس طبق سیاست انتخابی و اجرا روز بعد، بدون صف خرید و فروش و حد نوسان. نبود صف و حد نوسان نتیجه را کمی خوش‌بینانه می‌کند.', DOC.build)}>فرض</b> بازده کل، ریبالانس ${R === R0 ? POLS[S.pol] : 'ماهانه'}، اجرا روز بعد، بدون صف و حد نوسان؛ نرخ وام ${S.rb}٪ و هزینه ${S.cost}bp [تأیید لازم].</span>`;
  }
  drawCharts(cv, m);
  renderCmp();
  renderYears(o, key);
  renderPort();
}

function chart(el, series, o) {
  const W = 980, H = o.h || 200, pl = 48, pr = 12, pt = 10, pb = 22, n = series[0].v.length;
  const T = o.log ? Math.log : (x => x), all = series.flatMap(s => s.v.filter(x => x === x)).map(T), lo = Math.min(...all), hi = Math.max(...all), pad = (hi - lo) * 0.06 || 1, y0 = lo - pad, y1 = hi + pad;
  const X = i => pl + (W - pl - pr) * i / (n - 1), Y = v => pt + (H - pt - pb) * (1 - (T(v) - y0) / (y1 - y0));
  let g = '';
  const ticks = o.log ? [100, 150, 200, 300, 500, 700, 1000, 1500, 2000, 3000, 5000, 7000, 10000, 20000, 50000, 100000].filter(v => T(v) > y0 && T(v) < y1) : Array.from({ length: 5 }, (_, k) => y0 + (y1 - y0) * k / 4);
  ticks.forEach(v => { g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)" stroke-width=".5"/><text x="${pl - 6}" y="${Y(v) + 3}" text-anchor="end" font-size="9" fill="var(--tx-3)">${f(v, o.d == null ? 0 : o.d)}</text>`; });
  let lastY = null; o.dates.forEach((d, i) => { const y = jyear(d); if (y !== lastY && jmonth(d) <= 1) { lastY = y; g += `<line x1="${X(i)}" x2="${X(i)}" y1="${pt}" y2="${H - pb}" stroke="var(--line)" stroke-width=".4"/><text x="${X(i)}" y="${H - 7}" text-anchor="middle" font-size="9" fill="var(--tx-3)">${y}</text>`; } });
  if (o.zero) g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--tx-3)" stroke-width=".8"/>`;
  series.forEach(s => { let d = '', pen = false; s.v.forEach((v, i) => { if (v !== v) { pen = false; return; } d += (pen ? 'L' : 'M') + X(i).toFixed(1) + ',' + Y(v).toFixed(1); pen = true; }); g += `<path d="${d}" fill="none" stroke="${s.c}" stroke-width="${s.w || 1.6}"${s.dash ? ' stroke-dasharray="4 3"' : ''}/>`; });
  const xh = `<g class="xh" style="display:none;pointer-events:none"><line y1="${pt}" y2="${H - pb}" stroke="var(--tx-3)" stroke-width=".7" stroke-dasharray="3 3"/>${series.map(s => `<circle r="3.2" fill="${s.c}" stroke="var(--bg-panel)" stroke-width="1.2"/>`).join('')}</g>`;
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="direction:ltr;display:block" data-n="${n}">${g}${xh}<rect class="hv" x="${pl}" y="${pt}" width="${W - pl - pr}" height="${H - pt - pb}" fill="transparent"/></svg>`;
  const svg = el.firstChild, hv = svg.querySelector('.hv'), xg = svg.querySelector('.xh'), dots = xg.querySelectorAll('circle'), tipEl = floatTip();
  const dg = o.td != null ? o.td : o.d == null ? 1 : o.d;
  // نشانگر: خط عمودی، نقطه روی هر سری و راهنمای شناور با تاریخ و مقدارها
  hv.onmousemove = e => {
    const r = svg.getBoundingClientRect(), i = Math.max(0, Math.min(n - 1, Math.round(((e.clientX - r.left) / r.width * W - pl) / (W - pl - pr) * (n - 1))));
    xg.style.display = ''; xg.querySelector('line').setAttribute('x1', X(i)); xg.querySelector('line').setAttribute('x2', X(i));
    series.forEach((s, k) => { const v = s.v[i]; dots[k].style.display = v === v ? '' : 'none'; if (v === v) { dots[k].setAttribute('cx', X(i)); dots[k].setAttribute('cy', Y(v)); } });
    $('rb-hov').textContent = `${dj(o.dates[i])} · ` + series.map(s => `${s.t}: ${f(s.v[i], dg)}`).join(' · ');
    tipEl.innerHTML = `<div class="tt">${dj(o.dates[i])}</div>` + series.map(s => `<div><span style="display:inline-block;width:10px;height:3px;background:${s.c};vertical-align:middle;margin-inline-end:6px"></span>${s.t}: <b class="num" dir="ltr">${s.v[i] === s.v[i] ? f(s.v[i], dg) + (s.u || '') : '—'}</b></div>`).join('') + (o.extra ? o.extra(i) : '');
    placeTip(tipEl, e);
  };
  hv.onmouseleave = () => { xg.style.display = 'none'; tipEl.hidden = true; };
}
// یک راهنمای شناور مشترک برای نمودارهای این صفحه؛ لایهٔ ثابت روی کل صفحه تا پنل‌ها یا اسکرول والد آن را نپوشانند
function floatTip() {
  let t = document.getElementById('rb-bartip');
  if (!t) { t = document.createElement('div'); t.id = 'rb-bartip'; t.className = 'rb-bartip'; t.hidden = true; document.body.appendChild(t); document.addEventListener('scroll', () => { t.hidden = true; }, true); }
  return t;
}
function placeTip(t, e) {
  t.hidden = false;
  const w = t.offsetWidth, h = t.offsetHeight, vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
  t.style.left = Math.max(8, Math.min(e.clientX - w / 2, vw - w - 8)) + 'px';
  t.style.top = (e.clientY - h - 14 >= 8 ? e.clientY - h - 14 : Math.min(e.clientY + 18, vh - h - 8)) + 'px';
}
function drawCharts(cv, m) {
  const dts = cv.idx.map(t => R.dates[t]);
  $('rb-ch1-t').innerHTML = `رشد ۱۰۰ واحد (مقیاس لگاریتمی): <b style="color:var(--ch-1)">━ همتا</b> در برابر <b style="color:var(--warn)">━ ${TN} رسمی (بازده کل)</b>`;
  chart($('rb-ch1'), [{ v: cv.k, c: 'var(--warn)', t: 'شاخص' }, { v: cv.a, c: 'var(--ch-1)', t: 'همتا', w: 1.8 }], { dates: dts, h: 210, d: 0, td: 1, log: true,
    extra: i => cv.k[i] > 0 && cv.a[i] === cv.a[i] ? `<div class="ts">رشد ۱۰۰ واحد از شروع · همتا نسبت به شاخص: <b dir="ltr" class="${cv.a[i] >= cv.k[i] ? 'up' : 'down'}">${sg(100 * (cv.a[i] / cv.k[i] - 1))}٪</b></div>` : '' });
  $('rb-ch2-t').textContent = 'رشد نسبی همتا به شاخص (٪، خط پُر) و TE غلتان تا ۲۵۲ روز (از ۱۲۶ روز به بعد؛ خط‌چین قرمز)';
  chart($('rb-ch2'), [{ v: cv.td, c: 'var(--ch-1)', t: 'رشد نسبی', u: '٪' }, { v: cv.te, c: 'var(--down)', t: 'TE غلتان', u: '٪', dash: true, w: 1.2 }], { dates: dts, h: 150, d: 1, td: 2, zero: true,
    extra: () => '<div class="ts">رشد نسبی = (رشد همتا ÷ رشد شاخص) − ۱ از شروع؛ TE = انحراف معیار سالانهٔ اختلاف روزانه در ۲۵۲ روز اخیر.</div>' });
  drawDiffBars();
}

/* ── اختلاف ماهانهٔ همتا با شاخص و تحلیل علت (۲۰۲۶-۱۰-۲۰؛ فصل ۳ §۳٫۵) ──
   هر ستون یک دورهٔ نگهداری (از ریبالانس تا ریبالانس بعد). اختلاف روزانه d = بازده همتا − بازده «شاخص كل» رسمی به چهار جزء جمع‌پذیر تقسیم می‌شود:
   انتخاب سهام = بازده سبد سهام همتا − همتای کامل (همهٔ واجدان با وزن بازار)؛ اعضا و داده = همتای کامل − شاخص رسمی؛
   هزینه = گردش ریبالانس × L × هزینهٔ رفت‌وبرگشت؛ نقد، تأخیر سود و وام سود = باقی‌مانده (اثر L < ۱، طلب سود بی‌بازده یا بهرهٔ وام سود، بازده نقد). جمع ماه = جمع ساده‌ی روزها (تقریب حسابی).
   سهم هر نماد در «انتخاب سهام» = Σ روزها (وزن همتا − وزن شاخص، هر دو رانش‌یافته) × بازده نماد؛ از SIM_REPX (همان بازده‌های روزانهٔ شاخص بهبودیافته). */
function monthParts() {
  if (!last || !last.sim) return [];
  const p = prep(R), key = curKey(), r = seriesOf(R, key), sim = last.sim, nm = R.mstart.length, n = R.dates.length, out = [];
  for (let j = S.j0; j < nm; j++) {
    const t0 = R.mstart[j], t1 = j + 1 < nm ? R.mstart[j + 1] : n;
    let tot = 0, samp = 0, memb = 0, other = 0, ipo = 0;
    for (let t = Math.max(t0, sim.t0 + 1); t < t1; t++) {
      const navR = sim.nav[t] / sim.nav[t - 1] - 1, d = navR - p.K[t], rf = r[t] + sim.ipoB[t];   // rf: سبد با نماد تازه در وزن کامل هدف
      tot += d; samp += rf - p.C[t]; memb += p.C[t] - p.K[t]; ipo += sim.ipoD[t]; other += navR - rf - sim.ipoD[t];
    }
    if (t1 - 1 <= sim.t0) continue;
    const L = sim.Ls[j] === sim.Ls[j] ? sim.Ls[j] : 1, cost = -sim.cm[j];   // هزینهٔ همهٔ ریبالانس‌های دوره؛ خرید اولیه در روز شروع است که در سنجش نیست
    out.push({ j, t0, t1, end: R.dates[t1 - 1], tot: 100 * tot, samp: 100 * samp, memb: 100 * memb, ipo: 100 * ipo, cost: 100 * cost, lev: 100 * (other - cost), L });
  }
  return out;
}
const CONTRIB = new Map();
/** بزرگ‌ترین سهم‌های نمادها در «انتخاب سهام» یک ماه (نیازمند SIM_REPX) */
function topContrib(m) {
  const X = root.SIM_REPX; if (!X || !R.b || R !== R0 || S.tgt === 'ew') return null;
  const k = `${curKey()}|${m.j}`; if (CONTRIB.has(k)) return CONTRIB.get(k);
  if (!X._ret) { const bin = atob(X.ret), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); X._ret = new Float32Array(u.buffer); X._di = new Map(X.dates.map((d, i) => [d, i])); }
  const K = X.k, c = R.configs[curKey()], sel = c.sel[m.j], bj = R.b[m.j];
  const w = new Map(), b = new Map();
  sel[0].forEach((i, q) => w.set(i, sel[1][q] / 1e5)); bj[0].forEach((i, q) => b.set(i, bj[1][q] / 1e5));
  const ids = [...new Set([...w.keys(), ...b.keys()])], ww = ids.map(i => w.get(i) || 0), bb = ids.map(i => b.get(i) || 0), con = ids.map(() => 0), cum = ids.map(() => 0);
  for (let t = m.t0 + 1; t < m.t1; t++) {                              // نماد افزودهٔ فایل سیاست (i ≥ K) در SIM_REPX نیست
    const xi = X._di.get(R.dates[t]); if (xi == null) continue;
    const sw = ww.reduce((s, v) => s + v, 0) || 1, sb = bb.reduce((s, v) => s + v, 0) || 1;
    ids.forEach((i, q) => { const x = i < K ? X._ret[xi * K + i] : NaN, rr = x === x ? x : 0; con[q] += (ww[q] / sw - bb[q] / sb) * rr; cum[q] = (1 + cum[q]) * (1 + rr) - 1; ww[q] *= 1 + rr; bb[q] *= 1 + rr; });
  }
  const all = ids.map((i, q) => ({ s: R.names[i].s, sec: R.names[i].sec, w: w.get(i) || 0, b: b.get(i) || 0, ret: cum[q], c: 100 * con[q] }));
  const out_ = all.filter(x => x.w === 0), sum = a => a.reduce((t, x) => t + x.c, 0);
  // نمادهای هم‌جهت با کل «انتخاب سهام» (علت اصلی)، به‌علاوهٔ اثر جمعی نمادهای شاخص که در همتا نبودند
  const sgn = Math.sign(sum(all)) || 1, top = all.filter(x => Math.sign(x.c) === sgn).sort((x, y) => sgn * (y.c - x.c)).slice(0, 4);
  const res = { top, total: sum(all), outN: out_.length, outC: sum(out_), outUp: out_.filter(x => x.ret > 0).length };
  CONTRIB.set(k, res); return res;
}
function ensureRepx(cb) {
  if (root.SIM_REPX) return cb();
  if (ensureRepx.p) { ensureRepx.p.push(cb); return; }
  ensureRepx.p = [cb]; const s = document.createElement('script'); s.src = 'data/replica_x.js';
  s.onload = () => { const q = ensureRepx.p; ensureRepx.p = null; q.forEach(f => f()); }; s.onerror = () => { ensureRepx.p = null; };
  document.head.appendChild(s);
}
const PART_FA = { samp: 'انتخاب سهام', memb: 'اعضا و داده', ipo: 'تأخیر ورود عرضهٔ اولیه', lev: 'نقد، تأخیر سود و وام سود', cost: 'هزینهٔ ریبالانس' };
function explain(m) {
  const parts = ['samp', 'memb', 'ipo', 'lev', 'cost'].map(k => [k, m[k] || 0]).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const [mk] = parts[0], dir = m.tot >= 0 ? 'جلو افتاد' : 'عقب ماند', pp = v => `<span dir="ltr" style="unicode-bidi:isolate">${sg(v, 2)}</span>`;
  let why = '';
  if (mk === 'samp') {
    const tc = topContrib(m);
    why = 'احتمالاً <b>انتخاب سهام</b>: وزن نمادها در همتا با وزنشان در شاخص فرق داشت و همین نمادها حرکت بزرگ داشتند.';
    if (tc) {
      why += '<ul>' + tc.top.map(x => `<li>${esc(x.s)}: همتا ${f(100 * x.w, 1)}٪ در برابر شاخص ${f(100 * x.b, 1)}٪، بازده دوره ${sg(100 * x.ret, 1)}٪ ⇒ ${pp(x.c)} واحد${x.w === 0 ? ' (در همتا نبود)' : x.w > x.b ? ' (بیش‌وزن)' : ' (کم‌وزن)'}</li>`).join('') + '</ul>';
      if (tc.outN) {
        const same = Math.sign(tc.outC) === Math.sign(tc.total);
        why += `<div>${tc.outN} نماد شاخص در همتا نبودند (${tc.outUp} تا بالا رفتند): اثر جمعی ${pp(tc.outC)} واحد${same && Math.abs(tc.outC) >= Math.abs(tc.total) / 2 ? ' — بیشترِ اختلاف از همین سهام نخریده است' : !same ? ' — در جهت مخالف؛ بیش‌وزن‌ها بیش از آن جبران کردند' : ''}.</div>`;
      }
    }
    else if (R !== R0) why += ' <span class="mute">(برای هدف تیلت‌شده جزئیات نماد محاسبه نمی‌شود.)</span>';
    else if (S.tgt === 'ew') why += ' <span class="mute">(برای هدف هم‌وزن جزئیات نماد محاسبه نمی‌شود.)</span>';
    else why += ' <span class="mute">(جزئیات نمادها در حال بارگذاری…)</span>';
  } else if (mk === 'ipo') { const names = ipoOf(R).filter(e => e.a < m.t1 && e.a + e.w.length > m.t0).map(e => esc(R.names[e.p].s)); why = `احتمالاً <b>تأخیر ورود عرضهٔ اولیه</b>: نماد تازه${names.length ? ' (' + names.join('، ') + ')' : ''} از روز پس از عرضه در شاخص بود ولی همتا به‌دلیل صف خرید و سقف «سهم از معاملات» فقط بخشی از وزنش را داشت.`; }
  else if (mk === 'memb') why = 'احتمالاً <b>تفاوت اعضا و داده</b>: حتی خرید همهٔ واجدان هم این ماه با شاخص رسمی فاصله داشت؛ «همتای کامل» نمادهای تازه را هم دارد، پس معمولاً بازگشایی پس از توقف، نماد کم‌سابقهٔ غیرتازه‌ای که هنوز واجد نیست، یا تفاوت ثبت سود و افزایش سرمایه.';
  else if (mk === 'lev') why = `احتمالاً <b>${m.L < 1 ? 'نقد' : S.br ? 'وام سود نقدی' : 'تأخیر پرداخت سود'}</b>: L این ماه ${f(m.L, 2)} بود؛ ${m.L < 1 ? 'بخشی از سرمایه بیرون بازار بود و بازار ' + (m.tot < 0 ? 'بالا رفت' : 'پایین آمد') : S.br ? 'طلب سود با وام سرمایه‌گذاری بود و بهرهٔ وام کسر شد' : 'سود تصویب‌شده تا روز پرداخت بی‌بازده ماند در حالی که شاخص رسمی آن را همان روز استحقاق دوباره سرمایه‌گذاری می‌کند'}.`;
  else why = `احتمالاً <b>هزینهٔ ریبالانس</b>: گردش سبد در این دوره زیاد بود (سیاست «${R === R0 ? POLS[S.pol] : 'ماهانه'}»).`;
  return `<div class="tt">دوره تا ${dj(m.end)}: همتا ${pp(m.tot)} واحد درصد از شاخص ${dir}</div>
    <div class="td">${why}</div>
    <div class="tf">${parts.map(([k, v]) => `${PART_FA[k]}: ${pp(v)}`).join(' · ')}</div>
    <div class="ts">جمع ساده‌ی اختلاف روزانه (تقریب حسابی)؛ «انتخاب سهام» = سبد همتا منهای خرید همهٔ واجدان، «اعضا و داده» = همهٔ واجدان منهای شاخص رسمی.</div>`;
}
function drawDiffBars() {
  const el = $('rb-ch3'); if (!el) return;
  const ms = monthParts(); if (!ms.length) { el.innerHTML = ''; return; }
  const W = 980, H = 140, pl = 48, pr = 12, pt = 8, pb = 22, n = ms.length;
  const mx = Math.max(0.5, ...ms.map(m => Math.abs(m.tot))) * 1.08, Y = v => pt + (H - pt - pb) * (1 - (v + mx) / (2 * mx)), bw = (W - pl - pr) / n;
  let g = '';
  [mx, mx / 2, 0, -mx / 2, -mx].forEach(v => { g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(v)}" y2="${Y(v)}" stroke="${v === 0 ? 'var(--tx-3)' : 'var(--line)'}" stroke-width="${v === 0 ? 0.8 : 0.5}"/><text x="${pl - 6}" y="${Y(v) + 3}" text-anchor="end" font-size="9" fill="var(--tx-3)">${f(v, 1)}</text>`; });
  let lastY = null; ms.forEach((m, i) => { const y = jyear(m.end); if (y !== lastY && jmonth(m.end) <= 1) { lastY = y; g += `<text x="${pl + bw * (i + 0.5)}" y="${H - 7}" text-anchor="middle" font-size="9" fill="var(--tx-3)">${y}</text>`; } });
  ms.forEach((m, i) => { const y0 = Y(0), y1 = Y(m.tot); g += `<rect data-i="${i}" x="${pl + bw * i + bw * 0.12}" y="${Math.min(y0, y1)}" width="${Math.max(bw * 0.76, 1)}" height="${Math.max(Math.abs(y1 - y0), 0.8)}" fill="${m.tot >= 0 ? 'var(--up)' : 'var(--down)'}" opacity=".85"/>`; });
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="direction:ltr;display:block">${g}<rect class="hv" x="${pl}" y="${pt}" width="${W - pl - pr}" height="${H - pt - pb}" fill="transparent"/></svg>`;
  const svg = el.firstChild, tipEl = floatTip();
  const show = e => {
    const r = svg.getBoundingClientRect(), i = Math.max(0, Math.min(n - 1, Math.floor(((e.clientX - r.left) / r.width * W - pl) / bw))), m = ms[i];
    svg.querySelectorAll('rect[data-i]').forEach(x => x.setAttribute('opacity', +x.dataset.i === i ? '1' : '.55'));
    const paint = () => { tipEl.innerHTML = explain(m); placeTip(tipEl, e); };
    paint();
    if (Math.abs(m.samp) >= Math.max(Math.abs(m.memb), Math.abs(m.lev), Math.abs(m.cost)) && !root.SIM_REPX && R === R0) ensureRepx(paint);
  };
  svg.querySelector('.hv').onmousemove = show;
  svg.querySelector('.hv').onmouseleave = () => { tipEl.hidden = true; svg.querySelectorAll('rect[data-i]').forEach(x => x.setAttribute('opacity', '.85')); };
}

function renderYears(o, key) {
  const nm = R.mstart.length, rows = [];
  for (let j = 0; j < nm; j++) if (j === 0 || jmonth(R.sig[j]) === 12) rows.push(j);
  const hd = [['شروع از', '', 'پایان اسفند هر سال شمسی (و نخستین ماه داده): تاریخ نخستین خرید همتا.'], ['سال', 'n', 'طول بازه از شروع تا آخرین روز داده، به سال تقویمی.'], ['بازده سالانهٔ همتا', 'n', 'بازده مرکب سالانهٔ همتا از شروع تا امروز، پس از هزینه و بهرهٔ وام.'], ['بازده سالانهٔ شاخص', 'n', 'بازده مرکب سالانهٔ «شاخص كل» رسمی با سود نقدی در همین بازه.'], ['فاصله', 'n', 'بازده سالانهٔ همتا منهای شاخص (واحد درصد در سال)؛ منفی یعنی عقب‌ماندن.'], ['TE رسمی ٪', 'n', 'خطای ردیابی سالانه در برابر شاخص رسمی در همین بازه.'], ['TE همتای کامل ٪', 'n', 'خطای ردیابی در برابر خرید همهٔ واجدان؛ فقط خطای نمونه‌گیری.'], ['رشد نسبی ٪', 'n', '(رشد همتا ÷ رشد شاخص) − ۱ از شروع تا امروز؛ به زبان پول، چند درصد بیشتر یا کمتر از شاخص داشتید.']];
  $('rb-years').innerHTML = `<thead><tr>${hd.map(([t, c, d]) => `<th class="${c}"${tip(d)}>${t}</th>`).join('')}</tr></thead><tbody>` + rows.map(j => {
    const s = simulate(R, key, { ...o, j0: j }), m = metrics(R, s); if (!m) return '';
    return `<tr${j === S.j0 ? ' aria-current="true"' : ''}><td class="num">${dj(R.sig[j])}</td><td class="n">${f(m.years, 1)}</td><td class="n">${f(m.ann)}٪</td><td class="n">${f(m.annk)}٪</td><td class="n ${m.gap >= 0 ? 'up' : 'down'}">${sg(m.gap)}</td><td class="n">${f(m.te, 2)}</td><td class="n">${f(m.teC, 2)}</td><td class="n ${m.td >= 0 ? 'up' : 'down'}">${sg(m.td)}</td></tr>`;
  }).join('') + '</tbody>';
}

function portOf() {
  const key = curKey(), c = R.configs[key], nm = R.mstart.length, live = S.pdate === 'live', j = live ? nm - 1 : +S.pdate;
  const sel = live ? [c.live[0], c.live[1]] : c.sel[j], bj = live ? R.live_b : R.b[j], bmap = new Map(bj[0].map((i, p) => [i, bj[1][p] / 1e5]));
  const b0j = R.b0 ? (live ? R.live_b0 : R.b0[j]) : null, b0map = b0j ? new Map(b0j[0].map((i, p) => [i, b0j[1][p] / 1e5])) : null;
  let rows = sel[0].map((i, p) => ({ i, w: sel[1][p] / 1e5, b: bmap.get(i) || 0, b0: b0map ? (b0map.get(i) || 0) : null, nm: R.names[i] }));
  // ترکیب واقعی با تنظیمات پنل ۱ (نقد/تراز بتا، وام سود، لایهٔ عرضهٔ اولیه): وزن هر ردیف = سهم از NAV
  const extra = [];
  if (live) {
    // امروز: هدف ریبالانس بعد — نماد تازهٔ فعال با وزن شاخص، سپس همه ضربدر L؛ بقیه نقد
    const IL = R.ipo && R.ipo.live ? R.ipo.live.filter(([i]) => !rows.some(r => r.i === i)) : [];
    if (IL.length) { const sb = IL.reduce((a, x) => a + x[1], 0); rows.forEach(r => { r.w *= 1 - sb; }); IL.forEach(([i, b]) => rows.push({ i, w: b, b: bmap.get(i) || b, b0: null, nm: R.names[i], ipo: true })); }
    const L = last && last.sim && last.sim.Ls[nm - 1] === last.sim.Ls[nm - 1] ? last.sim.Ls[nm - 1] : 1;
    rows.forEach(r => { r.w *= L; });
    if (L < 0.9995) extra.push({ kind: 'cash', w: 1 - L });
  } else {
    const sim = last && last.sim && j >= S.j0 ? last.sim : simulate(R, key, { ...opts(), j0: j }), st = sim.mstate[j];
    if (st) {
      rows.forEach(r => { r.w *= st.rest; });
      st.ipo.forEach(([i, h]) => { const r = rows.find(x => x.i === i); if (r) r.w += h; else rows.push({ i, w: h, b: bmap.get(i) || 0, b0: null, nm: R.names[i], ipo: true }); });
      if (st.cash > 5e-4) extra.push({ kind: 'cash', w: st.cash });
      if (st.rcv > 5e-4) extra.push({ kind: 'rcv', w: st.rcv });
      if (st.debt > 5e-4) extra.push({ kind: 'debt', w: -st.debt });
    }
  }
  rows.sort((a, b) => b.w - a.w);
  return { live, j, rows, extra, bmap, cap: live ? c.live[2] : c.cap[j], key, bj };
}
function renderPort() {
  if (!host) return;
  const P = portOf(), nmT = P.rows.length, nIpo = P.rows.filter(r => r.ipo).length, cov = P.rows.reduce((a, r) => a + r.b, 0), inSel = new Set(P.rows.map(r => r.i));
  const sw = P.rows.reduce((a, r) => a + r.w, 0) || 1;                // سهم فعال روی بخش سهام (نقد/طلب/وام شرط فعال نیست)
  let act = 0; P.rows.forEach(r => { act += Math.abs(r.w / sw - r.b); }); P.bj[0].forEach((i, p) => { if (!inSel.has(i)) act += P.bj[1][p] / 1e5; }); act /= 2;
  const aumR = S.aum * 1e9, adv = R.adv_live || {};
  const o = opts(); let after = null, Lm = null;
  if (!P.live) { const s = simulate(R, P.key, { ...o, j0: P.j }); Lm = s.Ls[P.j]; after = metrics(R, s, s.t0 + 252); }
  $('rb-pkpi').innerHTML = [['تعداد نماد', nIpo ? `${nmT - nIpo} + ${nIpo} نماد تازه` : nmT, 'تعداد سهامی که در این تاریخ خریده می‌شود: N سهم نمونه (ممکن است کمتر باشد اگر نامزد کافی نقدشونده نبود یا بهینه‌ساز به بعضی وزن صفر داد) به‌علاوهٔ نمادهای تازهٔ بزرگ لایهٔ عرضهٔ اولیه که جدا از N و با وزن شاخص نگه داشته می‌شوند، حداکثر یک سال پس از عرضه.'], ['پوشش وزن شاخص', f(100 * cov, 0) + '٪', 'چند درصد از وزن «شاخص كل» در همین سهام است؛ بقیه اصلاً خریده نشده.'], ['سهم فعال', f(100 * act, 0) + '٪', 'سهم فعال (Active share): نصف مجموع |وزن همتا − وزن شاخص| روی همهٔ نمادها؛ وزن همتا روی بخش سهام بازنرمال می‌شود تا نقد و طلب سود سهم فعال حساب نشوند. ۰٪ یعنی همان شاخص، ۱۰۰٪ یعنی هیچ اشتراکی. برای همتای خوب معمولاً زیر ۳۰٪.'],
    ['ظرفیت یک‌روزه (میلیارد ریال)', f(P.cap, 0), 'بزرگ‌ترین سرمایه‌ای که این پرتفوی را در یک روز می‌سازد، اگر از هر نماد بیش از ۱۰٪ ارزش معاملات روزانه‌اش نخرید.'],
    ...(after ? [['TE یک سال بعد', f(after.te, 2) + '٪', 'آزمون بیرون از تاریخ: اگر همتا از همین تاریخ ساخته و طبق سیاست ریبالانس پنل ۱ به‌روز می‌شد، خطای ردیابی واقعی ۲۵۲ روز کاری بعد چقدر بود.'], ['رشد نسبی یک سال بعد', sg(after.td) + '٪', '(رشد همتا ÷ رشد شاخص) − ۱ در ۲۵۲ روز کاری بعد از این تاریخ.'], ['L این ماه', f(Lm, 2), 'نسبت سهام به سرمایه در این ماه با تنظیمات نقد/وام فعلی (در «تراز بتا» از بتای همان ماه).']] : [])]
    .map(([k, v, t]) => `<div class="kpi"${tip(t, DOC.build)}><div class="k"${tip(t, DOC.build)}>${k}</div><div class="v num">${v}</div></div>`).join('');
  const hd = [['#', 'rank', 'رتبه بر پایهٔ وزن در همتا.'], ['نماد', '', 'نماد بورسی؛ فقط واجدان بورس (بدون فرابورس، مثل «شاخص كل»).'], ['صنعت', '', 'گروه صنعت TSETMC در همان تاریخ.'], ['وزن همتا ٪', 'n', 'وزن نماد به درصد کل دارایی (NAV)، از وضعیت شبیه‌سازی پنل ۱ در همین تاریخ؛ جمع سهام با ردیف‌های نقد، طلب و وام سود (پایین جدول) ۱۰۰٪ می‌شود.'], ['وزن ' + (R.b0 ? 'هدف' : 'شاخص') + ' ٪', 'n', 'وزن نماد در هدف: ارزش بازار ÷ مجموع ارزش واجدان (تقریب «شاخص كل» بدون شناوری آزاد)، یا هدف تیلت‌شدهٔ پنل ۴.'], ...(R.b0 ? [['وزن شاخص رسمی ٪', 'n', 'وزن ارزش‌بازاری نماد در «شاخص كل» رسمی (تقریب بدون شناوری).']] : []), ['اختلاف', 'n', 'وزن همتا منهای وزن شاخص (واحد درصد). مثبت یعنی بیش‌وزن: نمونه با این سهم جای سهم‌های نخریده را پر کرده است.'],
    ...(P.live ? [['ارزش معاملات روزانه (میلیارد ریال)', 'n', 'میانهٔ ارزش معاملات روزانه در ۶۳ روز اخیر.'], ['روز لازم', 'n', 'وزن × سرمایه ÷ (۱۰٪ × ارزش معاملات روزانه). بیش از ۵ روز قرمز می‌شود.']] : [])];
  $('rb-ptab').innerHTML = `<thead><tr>${hd.map(([t, c, d]) => `<th class="${c}"${tip(d)}>${t}</th>`).join('')}</tr></thead><tbody>` + P.rows.map((r, p) => {
    const ad = adv[r.i], days = ad ? r.w * aumR / 1e9 / (R.part * ad) : NaN;
    return `<tr><td class="rank">${p + 1}</td><td>${esc(r.nm.s)}${r.ipo ? ' <span class="chip warn"' + tip('نماد تازهٔ بزرگ (لایهٔ عرضهٔ اولیه): با وزن شاخص بیرون از روش انتخاب؛ اگر هنوز در صف خرید است، سفارش در قیمت سقف بگذارید و بخشی پر می‌شود.', DOC.ipo) + '>عرضهٔ اولیه</span>' : ''}</td><td>${esc(r.nm.sec)}</td><td class="n">${f(100 * r.w, 2)}</td><td class="n">${f(100 * r.b, 2)}</td>${R.b0 ? `<td class="n">${f(100 * r.b0, 2)}</td>` : ''}<td class="n ${r.w >= r.b ? 'up' : 'down'}">${sg(100 * (r.w - r.b), 2)}</td>` + (P.live ? `<td class="n">${f(ad, 1)}</td><td class="n ${days > 5 ? 'down' : ''}">${f(days, 1)}</td>` : '') + '</tr>';
  }).join('') + P.extra.map(x => `<tr class="weak"><td></td><td colspan="2"${tip({ cash: 'بخش نقد طبق «سهم سهام» پنل ۱ (نقد ثابت).', rcv: 'سود نقدی تصویب‌شده و هنوز پرداخت‌نشده (طلب)؛ تا روز پرداخت بی‌بازده است مگر «وام سود نقدی» روشن باشد.', debt: 'وام سود نقدی؛ هرگز بیش از طلب سود نیست.' }[x.kind], DOC.loan)}>${{ cash: 'نقد', rcv: 'طلب سود نقدی', debt: 'وام سود نقدی' }[x.kind]}</td><td class="n">${f(100 * x.w, 2)}</td><td class="n">—</td><td colspan="9"></td></tr>`).join('') + '</tbody>';
  const cfgTxt = `${S.tgt === 'ew' ? '«شاخص كل (هم وزن)»' : '«شاخص كل»'} · ${METHODS[S.method]} ${S.N} سهم · نقدشوندگی ${LIQN[S.liq][0]} · ریبالانس ${R === R0 ? POLS[S.pol] : 'ماهانه'} · ${S.mode === 'none' ? 'تمام در سهام' : S.mode === 'cash' ? S.cash + '٪ نقد' : 'تراز بتا'} · ${S.br ? 'وام سود نقدی' : 'بدون وام'}${R.ipo ? ' · نماد تازه ' + S.phi + '٪ از معاملات، صندوق ' + f(S.aum, 0) + ' میلیارد ریال' : ''}`;
  $('rb-plin').innerHTML = `<span><b${tip('همهٔ اعداد این پنل با همین تنظیمات پنل ۱ حساب می‌شوند؛ هر تغییری در پنل ۱ این جدول را هم دوباره می‌سازد. وزن‌ها سهم از کل دارایی (NAV) است: سهام به‌اضافهٔ نقد، طلب سود و منهای وام.', DOC.build)}>تنظیمات</b> ${esc(cfgTxt)}</span><span><b${tip('وزن هدف = ارزش بازار کل (قیمت × همهٔ سهام) نمادهای واجد بورس در روز سیگنال؛ همان روش وزن‌دهی «شاخص كل» رسمی (نه شناور آزاد؛ بازسازی کامل شاخص با این وزن TE حدود ۰٫۳٪ دارد). تفاوت با شاخص از اعضاست، نه روش وزن.', DOC.build)}>وزن شاخص</b> ارزش بازار کل، همان روش «شاخص كل»</span><span><b${tip('نمادهای واجد شاخص که در همتا نیستند و مجموع وزنشان در شاخص؛ منبع اصلی خطای نمونه‌گیری.', DOC.build)}>خارج از نمونه</b> ${P.bj[0].length - nmT} نماد با مجموع وزن ${f(100 * (1 - cov), 0)}٪</span>`;
  $('rb-plan').style.display = P.live ? '' : 'none';
  $('rbx-csv').onclick = () => download(`replica_${P.live ? R.asof : dj(R.sig[P.j]).replace(/\//g, '-')}.csv`, [['symbol', 'sector', 'w_replica_pct', 'w_index_pct'], ...P.rows.map(r => [r.nm.s, r.nm.sec, (100 * r.w).toFixed(3), (100 * r.b).toFixed(3)]), ...P.extra.map(x => [x.kind, '', (100 * x.w).toFixed(3), ''])]);
  $('rb-plan').onclick = () => {
    if (!root.SIM_ENSURE_LAB || !root.SIM_SEND_PLAN) { toast('Lab بارگذاری نشده'); return; }
    root.SIM_ENSURE_LAB(() => {
    const LAB = root.SIM_LAB, map = new Map(LAB.codes.map((c, i) => [String(c.c), i])), w = new Float64Array(LAB.k); let miss = 0;
    P.rows.forEach(r => { const i = map.get(r.nm.c); if (i == null) miss++; else w[i] = r.w; });   // وزن‌ها سهم از NAV‌اند (نقد بیرون)
    root.SIM_SEND_PLAN(`همتاساز${S.tgt === 'ew' ? ' هم‌وزن' : ''} · ${METHODS[S.method]} ${S.N} سهم · نقدشوندگی ${LIQN[S.liq][0]}`, w, R === R0 ? { kind: 'replica', key: curKey() } : { kind: 'enh' });
    if (miss) toast(`${miss} نماد در Lab نبود و کنار ماند`);
    });
  };
}
root.SIM_RB_MOUNT = mount;
})(typeof window !== 'undefined' ? window : globalThis);
