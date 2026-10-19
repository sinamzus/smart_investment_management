/* همتا — «همتاساز»: بازسازی شاخص كل با نمونهٔ کوچک، فیلتر نقدشوندگی، نقد/وام/اهرم، و نگاه به گذشته (فصل ۳ §۳٫۷)
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

/** شبیهٔ NAV. o = {mode:'none'|'fixed'|'beta', L, rb, rc, cost, j0}. اهرم هر ماه بازتنظیم می‌شود. */
function simulate(R, key, o) {
  const c = R.configs[key], r = seriesOf(R, key), nm = R.mstart.length, n = R.dates.length, nav = new Float64Array(n).fill(NaN), Ls = new Float64Array(nm).fill(NaN);
  let cur = 1;
  for (let j = o.j0; j < nm; j++) {
    const t0 = R.mstart[j], t1 = j + 1 < nm ? R.mstart[j + 1] : n;
    let L = 1;
    if (o.mode === 'fixed') L = o.L; else if (o.mode === 'beta') { const be = c.beta[j]; L = be > 0 ? Math.min(1.5, Math.max(0.7, 1 / be)) : 1; }
    Ls[j] = L;
    const to = j === o.j0 ? 0.5 : c.to[j];
    cur -= to * L * cur * o.cost / 1e4;
    let V = L * cur, D = Math.max(L - 1, 0) * cur, cash = L < 1 ? cur - V : 0, prev = R.sig[j];
    for (let t = t0; t < t1; t++) {
      const gap = R.dates[t] - prev; prev = R.dates[t];
      V *= 1 + r[t]; D *= 1 + o.rb * gap / 365; cash *= 1 + o.rc * gap / 365;
      cur = V + cash - D; nav[t] = cur;
    }
  }
  return { nav, t0: R.mstart[o.j0], Ls };
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
const E = { simulate, metrics, curves, keyOf, prep, seriesOf };
if (typeof module !== 'undefined' && module.exports) { module.exports = E; return; }
root.SIM_RB = E;

/* ═════════════════ رابط ═════════════════ */
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const f = (x, d = 1) => x == null || x !== x ? '—' : fmt(x, d);
const sg = (x, d = 1) => x == null || x !== x ? '—' : sgn(x, d);
const tip = t => ` data-tip="${esc(t)}"`;
const jf = new Intl.DateTimeFormat('fa-IR-u-ca-persian-nu-latn', { year: 'numeric', month: '2-digit', day: '2-digit' });
const dj = d => jf.format(new Date(d * 864e5));
const jyear = d => +dj(d).split('/')[0], jmonth = d => +dj(d).split('/')[1];
const METHODS = { top: 'N بزرگ‌ترین', strat: 'طبقه‌ای (صنعت)', opt: 'بهینه‌سازی TE' };
const LIQN = { 0: ['بدون فیلتر', 'همهٔ واجدان بورس نامزد نگهداری‌اند.'], 1: ['ملایم', 'نماد باید دست‌کم ۵۰ روز از ۶۳ روز اخیر معامله شده و میانهٔ ارزش معاملاتش بالاتر از صدک ۲۰ واجدان باشد.'],
  2: ['متوسط', 'دست‌کم ۵۶ روز از ۶۳ روز معامله و میانهٔ ارزش معاملات بالاتر از صدک ۴۰ واجدان.'], 3: ['سخت', 'دست‌کم ۶۰ روز از ۶۳ روز معامله و میانهٔ ارزش معاملات بالاتر از صدک ۶۰ واجدان.'] };
const S = { method: 'opt', N: 30, liq: 0, mode: 'none', cash: 10, loan: 20, rb: 30, rc: 0, cost: 100, j0: 0, pdate: 'live', aum: 500 };
let R = null, R0 = null, host = null, last = null;

function mount(el) {
  host = el; R = R0 = root.SIM_REP;
  if (!R) { el.innerHTML = '<section class="panel"><div class="panel-body" style="padding:24px">دادهٔ همتاساز پیدا نشد. اجرا کنید: <code>python tools/build_replica_panel.py</code></div></section>'; return; }
  prep(R);
  if (!R.Ns.includes(S.N)) S.N = R.Ns[Math.floor(R.Ns.length / 2)];
  const nm = R.mstart.length;
  const startOpts = R.sig.map((d, j) => `<option value="${j}">${dj(d)}</option>`).join('');
  const dateOpts = `<option value="live">امروز (زنده) · ${esc(R.asof)}</option>` + R.sig.map((d, j) => `<option value="${j}">${dj(d)}</option>`).reverse().join('');
  el.innerHTML = `
  <section class="panel" style="--lg:var(--lg-a)">
    <div class="panel-head"><span class="lg-badge">2</span><span class="panel-title"${tip('شاخص كل را با تعدادی سهم بسازید، نقدشوندگی را فیلتر کنید، نقد یا وام اضافه کنید و ببینید اگر از هر تاریخ گذشته شروع می‌کردید تا امروز چقدر خطا داشتید.')}>همتاساز · بازسازی شاخص با نمونهٔ کوچک</span><span class="chip" id="rb-chip"${tip('بازه و دادهٔ این نما.')}></span></div>
    <div class="ctl">
      <label${tip('روش انتخاب سهام نمونه از میان نامزدهای نگهداری.')}>روش <span class="seg" id="rb-method">${Object.entries(METHODS).map(([k, t]) => `<button data-v="${k}" aria-pressed="false"${tip('روش انتخاب: ' + t)}>${t}</button>`).join('')}</span></label>
      <label${tip('تعداد سهام نمونه؛ هرچه بیشتر، خطای ردیابی کمتر و هزینهٔ اجرا بیشتر.')}>تعداد سهام <select id="rb-n">${R.Ns.map(n => `<option data-tip="نمونهٔ ${n} سهمی: ${n < 30 ? 'ردیابی ضعیف (TE بالای ۴٪)؛ فقط برای سرمایهٔ خیلی کوچک.' : n < 80 ? 'سازش خطای ردیابی و هزینه (TE ≈ ۳ تا ۴٪ با بهینه‌سازی).' : 'نزدیک کف خطا (TE ≈ ۲٪ با بهینه‌سازی)؛ نیاز به نقدشوندگی بیشتر.'}">${n}</option>`).join('')}</select></label>
      <label${tip('فقط نمادهای نقدشونده اجازهٔ ورود به نمونه دارند؛ وزن هدف همچنان از کل واجدان بورس است، پس خطا بالاتر می‌رود ولی اجرا شدنی‌تر می‌شود.')}>نقدشوندگی <span class="seg" id="rb-liq">${Object.keys(R.liq).map(q => `<button data-v="${q}" aria-pressed="false"${tip(LIQN[q][1])}>${LIQN[q][0]}</button>`).join('')}</span></label>
    </div>
    <div class="ctl">
      <label${tip('نقد ثابت: بخشی از سرمایه را بیرون از سهام نگه می‌دارد (L < ۱). وام ثابت: با نرخ وام به سهام اضافه می‌کند (L > ۱). تراز بتا: هر ماه L = ۱/β نمونه، بُرش ۰٫۷ تا ۱٫۵.')}>نقد / وام <span class="seg" id="rb-mode">
        <button data-v="none" aria-pressed="false"${tip('کاملاً سرمایه‌گذاری‌شده بدون وام و نقد.')}>بدون</button><button data-v="cash" aria-pressed="false"${tip('درصدی از سرمایه نقد می‌ماند.')}>نقد ثابت</button><button data-v="loan" aria-pressed="false"${tip('درصدی از سرمایه وام گرفته و در سهام می‌رود.')}>وام ثابت</button><button data-v="beta" aria-pressed="false"${tip('L = ۱/β هر ماه.')}>تراز بتا</button></span></label>
      <label id="rb-amt-l"${tip('درصد نقد یا وام نسبت به سرمایه.')}><span id="rb-amt-t">مقدار ٪</span> <input type="number" id="rb-amt" value="10" min="0" max="50" step="5"></label>
      <label${tip('نرخ سالانهٔ وام؛ بهره روزانه از NAV کم می‌شود. [تأیید لازم] دسترسی واقعی به وام و نرخ آن.')}>نرخ وام ٪ <input type="number" id="rb-rb" value="30" min="0" max="80" step="1"></label>
      <label${tip('بازدهٔ سالانهٔ نقد نگه‌داشته‌شده (مثلاً صندوق درآمد ثابت)؛ صفر یعنی بدون بهره.')}>بازده نقد ٪ <input type="number" id="rb-rc" value="0" min="0" max="80" step="1"></label>
      <label${tip('هزینهٔ رفت‌وبرگشت معامله بر حسب bp؛ در گردش یک‌طرفه × L ضرب می‌شود.')}>هزینه (bp) <input type="number" id="rb-cost" value="100" min="0" step="10"></label>
      <label${tip('اگر همتا را از این تاریخ ساخته بودیم؛ همهٔ خطاها تا امروز از همین ماه حساب می‌شود.')}>شروع از <select id="rb-j0">${startOpts}</select></label>
    </div>
    <div class="kpis" id="rb-kpi"></div>
    <div class="lineage" id="rb-read"></div>
    <div class="panel-body" style="padding:var(--s-3)"><div class="mute" style="font-size:var(--fs-xs)" id="rb-ch1-t"></div><div id="rb-ch1"></div><div class="mute" style="font-size:var(--fs-xs);margin-top:8px" id="rb-ch2-t"></div><div id="rb-ch2"></div><div class="mute" id="rb-hov" style="font-size:var(--fs-2xs);min-height:1.4em"></div></div>
  </section>
  <div id="rb-enh"></div>
  <section class="panel" style="--lg:var(--lg-b)">
    <div class="panel-head"><span class="lg-badge">3</span><span class="panel-title"${tip('همین تنظیمات را اگر از ابتدای هر سال شمسی شروع می‌کردیم: خطای ردیابی و تفاوت بازده تا امروز.')}>اگر از سال‌های گذشته شروع می‌کردیم</span></div>
    <div class="panel-body scroll" style="max-height:300px"><table class="dt" id="rb-years"></table></div>
  </section>
  <section class="panel" style="--lg:var(--lg-c)">
    <div class="panel-head"><span class="lg-badge">4</span><span class="panel-title"${tip('پرتفویی که در تاریخ سیگنال انتخاب‌شده می‌خریدید، با وزن شاخص مقایسه شده. «امروز» همان پرتفوی قابل اجراست.')}>پرتفوی در یک تاریخ</span>
      <div class="panel-tools"><button class="tool" id="rb-csv"${tip('وزن‌های این تاریخ به‌صورت CSV.')}>CSV</button><button class="tool" id="rb-plan"${tip('فقط برای «امروز»: وزن هدف را به نمای دستور اجرا می‌فرستد تا سفارش‌ها ساخته شود.')}>ارسال به برنامهٔ اقدام ←</button></div></div>
    <div class="ctl"><label${tip('تاریخ سیگنال (پایان ماه شمسی). پرتفوی با همان آگاهی آن روز انتخاب می‌شود.')}>تاریخ <select id="rb-date">${dateOpts}</select></label>
      <label${tip('سرمایهٔ فرضی برای محاسبهٔ روز لازم ساخت با ۱۰٪ مشارکت در ارزش معاملات روزانه (فقط «امروز»).')}>سرمایه (میلیارد ریال) <input type="number" id="rb-aum" value="500" min="1" step="10"></label></div>
    <div class="kpis" id="rb-pkpi"></div>
    <div class="panel-body scroll" style="max-height:440px"><table class="dt" id="rb-ptab"></table></div>
    <div class="lineage" id="rb-plin"></div>
  </section>`;
  const seg = (id, key, cb) => $(id).querySelectorAll('button').forEach(b => { b.onclick = () => { if (key !== 'mode') stale(); S[key] = key === 'liq' ? +b.dataset.v : b.dataset.v; cb && cb(); render(); }; });
  seg('rb-method', 'method'); seg('rb-liq', 'liq'); seg('rb-mode', 'mode');
  $('rb-n').onchange = e => { stale(); S.N = +e.target.value; render(); };
  $('rb-amt').onchange = e => { S[S.mode === 'loan' ? 'loan' : 'cash'] = +e.target.value; render(); };
  $('rb-rb').onchange = e => { S.rb = +e.target.value; render(); }; $('rb-rc').onchange = e => { S.rc = +e.target.value; render(); };
  $('rb-cost').onchange = e => { S.cost = +e.target.value; render(); };
  $('rb-j0').onchange = e => { S.j0 = +e.target.value; render(); };
  $('rb-date').onchange = e => { S.pdate = e.target.value; renderPort(); };
  $('rb-aum').onchange = e => { S.aum = +e.target.value; renderPort(); };
  $('rb-n').value = S.N;
  if (root.SIM_ENH_MOUNT) root.SIM_ENH_MOUNT($('rb-enh'), root.SIM_RB_API);
  setChip();
  render();
}
const opts = () => ({ mode: S.mode === 'none' ? 'none' : S.mode === 'beta' ? 'beta' : 'fixed', L: S.mode === 'cash' ? 1 - S.cash / 100 : S.mode === 'loan' ? 1 + S.loan / 100 : 1, rb: S.rb / 100, rc: S.rc / 100, cost: S.cost, j0: S.j0 });
const curKey = () => R === R0 ? keyOf(S.method, S.N, S.liq) : 'enh';
const stale = () => { if (R !== R0) { R = R0; if (root.SIM_ENH_STALE) root.SIM_ENH_STALE(); } };
root.SIM_RB_API = { set(Rx) { R = Rx || R0; if (host) render(); }, state: () => ({ method: S.method, N: S.N, liq: S.liq }) };

function setChip() { $('rb-chip').textContent = `${dj(R.sig[0])} → ${dj(R.dates[R.dates.length - 1])} · ${R.sig.length} ریبالانس ماهانه${R === R0 ? '' : ' · هدف تیلت‌شده'}`; }
function render() {
  if (!host) return;
  setChip();
  ['rb-method', 'rb-liq', 'rb-mode'].forEach(id => $(id).querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v) === String({ 'rb-method': S.method, 'rb-liq': S.liq, 'rb-mode': S.mode }[id]))));
  $('rb-amt-l').style.display = S.mode === 'cash' || S.mode === 'loan' ? '' : 'none';
  if (S.mode === 'cash' || S.mode === 'loan') { $('rb-amt-t').textContent = S.mode === 'cash' ? 'نقد ٪' : 'وام ٪'; $('rb-amt').value = S[S.mode]; $('rb-amt').max = S.mode === 'cash' ? 50 : 50; }
  const o = opts(), key = curKey(), sim = simulate(R, key, o), m = metrics(R, sim), cv = curves(R, sim), c = R.configs[key], nm = R.mstart.length;
  last = { sim, m, cv };
  let sL = 0, sT = 0, cnt = 0; for (let j = S.j0; j < nm; j++) { sL += sim.Ls[j]; sT += j === S.j0 ? 0 : c.to[j]; cnt++; }
  const capNow = c.live[2];
  const bj = R.b[nm - 1], bmap = new Map(bj[0].map((i, p) => [i, bj[1][p]])), covB = c.sel[nm - 1][0].reduce((a, i) => a + (bmap.get(i) || 0), 0) / 1e5;
  const yrs = m ? m.years : 0;
  const kp = m ? [['TE در برابر شاخص رسمی', f(m.te, 2) + '٪', 'خطای ردیابی سالانه‌شده: انحراف معیار تفاضل بازده روزانهٔ همتا و «شاخص كل» رسمی × √۲۵۲؛ کمتر بهتر.'],
    ['TE در برابر همتای کامل', f(m.teC, 2) + '٪', 'فقط خطای نمونه‌گیری: همتا در برابر خرید همهٔ واجدان با وزن بازار (خطای وزن شناور و داده را ندارد).'],
    ['فاصلهٔ بازده سالانه (واحد درصد)', sg(m.gap), 'بازده سالانهٔ همتا منهای شاخص رسمی؛ منفی یعنی عقب‌ماندن. ریسک نیست و ممکن است سیستماتیک باشد.'],
    ['تفاوت تجمعی تا امروز', sg(m.td) + '٪', `رشد نسبی همتا به شاخص: (رشد همتا ÷ رشد شاخص) − ۱، از ${dj(R.sig[S.j0])} تا امروز (${f(yrs, 1)} سال). منفی یعنی همتا عقب مانده است.`],
    ['بتا', f(m.beta, 2), 'بتای بازده روزانهٔ همتا روی شاخص رسمی؛ نقد آن را زیر ۱ و وام بالای ۱ می‌برد.'],
    ['همبستگی', f(m.corr, 3), 'همبستگی بازده روزانهٔ همتا و شاخص رسمی.']] : [];
  const kp2 = [['میانگین L', f(sL / cnt, 2), 'میانگین نسبت سهام به سرمایه: زیر ۱ نقد، بالای ۱ وام.'], ['گردش ماهانهٔ یک‌طرفه', f(100 * sT / Math.max(cnt - 1, 1), 0) + '٪', 'میانگین سهم پرتفوی که هر ماه خرید و فروش می‌شود (پیش از ضرب در L).'],
    ['ظرفیت امروز (میلیارد ریال)', f(capNow, 0), 'بزرگ‌ترین سرمایه‌ای که پرتفوی امروز را در یک روز با ۱۰٪ مشارکت در ارزش معاملات روزانهٔ ضعیف‌ترین نماد می‌سازد.'],
    ['پوشش وزن شاخص (آخرین ماه)', f(100 * covB, 0) + '٪', 'مجموع وزن شاخص نمادهای نمونه؛ هرچه بیشتر، نمونه به شاخص نزدیک‌تر.']];
  $('rb-kpi').innerHTML = [...kp, ...kp2].map(([k, v, t]) => `<div class="kpi"${tip(t)}><div class="k"${tip(t)}>${k}</div><div class="v num">${v}</div></div>`).join('');
  if (m) {
    const ov = S.mode === 'none' ? 'بدون وام و نقد' : S.mode === 'cash' ? `${S.cash}٪ نقد` : S.mode === 'loan' ? `${S.loan}٪ وام` : 'تراز بتا';
    $('rb-read').innerHTML = `<span><b${tip('جملهٔ خودکار از همین محاسبه.')}>خوانش</b> اگر از ${dj(R.sig[S.j0])} همتایی با ${S.N} سهم (${METHODS[S.method]}، نقدشوندگی ${LIQN[S.liq][0]}، ${ov}) ساخته بودیم، تا امروز (${f(yrs, 1)} سال) ارزش همتا نسبت به شاخص رسمی ${sg(m.td)}٪ تفاوت داشت و خطای ردیابی سالانه ${f(m.te, 1)}٪ بود.</span><span><b${tip('داده‌ها و فرض‌ها.')}>فرض</b> بازده کل، ریبالانس پایان ماه جلالی، اجرا روز بعد، بدون صف و حد نوسان؛ نرخ وام ${S.rb}٪ و هزینه ${S.cost}bp [تأیید لازم].</span>`;
  }
  drawCharts(cv, m);
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
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="direction:ltr;display:block" data-n="${n}">${g}<rect class="hv" x="${pl}" y="${pt}" width="${W - pl - pr}" height="${H - pt - pb}" fill="transparent"/></svg>`;
  const svg = el.firstChild;
  svg.querySelector('.hv').onmousemove = e => { const r = svg.getBoundingClientRect(), i = Math.max(0, Math.min(n - 1, Math.round(((e.clientX - r.left) / r.width * W - pl) / (W - pl - pr) * (n - 1)))); $('rb-hov').textContent = `${dj(o.dates[i])} · ` + series.map(s => `${s.t}: ${f(s.v[i], o.d == null ? 1 : o.d)}`).join(' · '); };
}
function drawCharts(cv, m) {
  const dts = cv.idx.map(t => R.dates[t]);
  $('rb-ch1-t').innerHTML = 'رشد ۱۰۰ واحد (مقیاس لگاریتمی): <b style="color:var(--ch-1)">━ همتا</b> در برابر <b style="color:var(--warn)">━ «شاخص كل» رسمی (بازده کل)</b>';
  chart($('rb-ch1'), [{ v: cv.k, c: 'var(--warn)', t: 'شاخص' }, { v: cv.a, c: 'var(--ch-1)', t: 'همتا', w: 1.8 }], { dates: dts, h: 210, d: 0, log: true });
  $('rb-ch2-t').textContent = 'رشد نسبی همتا به شاخص (٪، خط پُر) و TE غلتان تا ۲۵۲ روز (از ۱۲۶ روز به بعد؛ خط‌چین قرمز)';
  chart($('rb-ch2'), [{ v: cv.td, c: 'var(--ch-1)', t: 'تفاوت تجمعی' }, { v: cv.te, c: 'var(--down)', t: 'TE غلتان', dash: true, w: 1.2 }], { dates: dts, h: 150, d: 1, zero: true });
}

function renderYears(o, key) {
  const nm = R.mstart.length, rows = [];
  for (let j = 0; j < nm; j++) if (j === 0 || jmonth(R.sig[j]) === 12) rows.push(j);
  const hd = [['شروع از', '', 'تاریخ سیگنال نخستین ریبالانس.'], ['سال', 'n', 'مدت تا امروز.'], ['بازده سالانهٔ همتا', 'n', 'بازده سالانه‌شدهٔ همتا از شروع تا امروز.'], ['بازده سالانهٔ شاخص', 'n', 'بازده سالانه‌شدهٔ «شاخص كل» رسمی در همین بازه.'], ['فاصله', 'n', 'همتا منهای شاخص (واحد درصد در سال).'], ['TE رسمی ٪', 'n', 'خطای ردیابی در برابر شاخص رسمی.'], ['TE همتای کامل ٪', 'n', 'فقط خطای نمونه‌گیری.'], ['رشد نسبی ٪', 'n', 'رشد همتا ÷ رشد شاخص − ۱ از شروع تا امروز.']];
  $('rb-years').innerHTML = `<thead><tr>${hd.map(([t, c, d]) => `<th class="${c}"${tip(d)}>${t}</th>`).join('')}</tr></thead><tbody>` + rows.map(j => {
    const s = simulate(R, key, { ...o, j0: j }), m = metrics(R, s); if (!m) return '';
    return `<tr${j === S.j0 ? ' aria-current="true"' : ''}><td class="num">${dj(R.sig[j])}</td><td class="n">${f(m.years, 1)}</td><td class="n">${f(m.ann)}٪</td><td class="n">${f(m.annk)}٪</td><td class="n ${m.gap >= 0 ? 'up' : 'down'}">${sg(m.gap)}</td><td class="n">${f(m.te, 2)}</td><td class="n">${f(m.teC, 2)}</td><td class="n ${m.td >= 0 ? 'up' : 'down'}">${sg(m.td)}</td></tr>`;
  }).join('') + '</tbody>';
}

function portOf() {
  const key = curKey(), c = R.configs[key], nm = R.mstart.length, live = S.pdate === 'live', j = live ? nm - 1 : +S.pdate;
  const sel = live ? [c.live[0], c.live[1]] : c.sel[j], bj = live ? R.live_b : R.b[j], bmap = new Map(bj[0].map((i, p) => [i, bj[1][p] / 1e5]));
  const b0j = R.b0 ? (live ? R.live_b0 : R.b0[j]) : null, b0map = b0j ? new Map(b0j[0].map((i, p) => [i, b0j[1][p] / 1e5])) : null;
  const rows = sel[0].map((i, p) => ({ i, w: sel[1][p] / 1e5, b: bmap.get(i) || 0, b0: b0map ? (b0map.get(i) || 0) : null, nm: R.names[i] })).sort((a, b) => b.w - a.w);
  return { live, j, rows, bmap, cap: live ? c.live[2] : c.cap[j], key, bj };
}
function renderPort() {
  if (!host) return;
  const P = portOf(), nmT = P.rows.length, cov = P.rows.reduce((a, r) => a + r.b, 0), inSel = new Set(P.rows.map(r => r.i));
  let act = 0; P.rows.forEach(r => { act += Math.abs(r.w - r.b); }); P.bj[0].forEach((i, p) => { if (!inSel.has(i)) act += P.bj[1][p] / 1e5; }); act /= 2;
  const aumR = S.aum * 1e9, adv = R.adv_live || {};
  const o = opts(); let after = null, Lm = null;
  if (!P.live) { const s = simulate(R, P.key, { ...o, j0: P.j }); Lm = s.Ls[P.j]; after = metrics(R, s, s.t0 + 252); }
  $('rb-pkpi').innerHTML = [['تعداد نماد', nmT, 'تعداد سهام نمونه در این تاریخ.'], ['پوشش وزن شاخص', f(100 * cov, 0) + '٪', 'مجموع وزن شاخص نمادهای نمونه.'], ['سهم فعال', f(100 * act, 0) + '٪', 'نصف مجموع |وزن همتا − وزن شاخص| روی همهٔ نمادها؛ هرچه کمتر، نمونه به شاخص نزدیک‌تر.'],
    ['ظرفیت یک‌روزه (میلیارد ریال)', f(P.cap, 0), 'بزرگ‌ترین سرمایه‌ای که این پرتفوی را در یک روز با ۱۰٪ مشارکت در ارزش معاملات روزانهٔ ضعیف‌ترین نماد می‌سازد.'],
    ...(after ? [['TE یک سال بعد', f(after.te, 2) + '٪', 'خطای ردیابی واقعی در ۲۵۲ روز پس از این تاریخ با تنظیمات فعلی (اگر پرتفوی هر ماه به‌روز می‌شد).'], ['رشد نسبی یک سال بعد', sg(after.td) + '٪', 'رشد همتا ÷ رشد شاخص − ۱ در ۲۵۲ روز بعد از این تاریخ.'], ['L این ماه', f(Lm, 2), 'نسبت سهام به سرمایه در این ماه با تنظیمات نقد/وام فعلی.']] : [])]
    .map(([k, v, t]) => `<div class="kpi"${tip(t)}><div class="k"${tip(t)}>${k}</div><div class="v num">${v}</div></div>`).join('');
  const hd = [['#', 'rank', 'رتبه بر پایهٔ وزن همتا.'], ['نماد', '', 'نماد.'], ['صنعت', '', 'صنعت.'], ['وزن همتا ٪', 'n', 'وزن نماد در پرتفوی نمونه.'], ['وزن ' + (R.b0 ? 'هدف' : 'شاخص') + ' ٪', 'n', 'وزن نماد در هدف (شاخص رسمی یا هدف تیلت‌شده).'], ...(R.b0 ? [['وزن شاخص رسمی ٪', 'n', 'وزن ارزش‌بازاری نماد در «شاخص كل» رسمی (تقریب بدون شناوری).']] : []), ['اختلاف', 'n', 'وزن همتا منهای وزن شاخص (واحد درصد).'],
    ...(P.live ? [['ارزش معاملات روزانه (میلیارد ریال)', 'n', 'میانهٔ ۶۳ روزهٔ ارزش معاملات.'], ['روز لازم', 'n', 'روز لازم برای ساخت با سرمایهٔ ورودی و ۱۰٪ مشارکت.']] : [])];
  $('rb-ptab').innerHTML = `<thead><tr>${hd.map(([t, c, d]) => `<th class="${c}"${tip(d)}>${t}</th>`).join('')}</tr></thead><tbody>` + P.rows.map((r, p) => {
    const ad = adv[r.i], days = ad ? r.w * aumR / 1e9 / (R.part * ad) : NaN;
    return `<tr><td class="rank">${p + 1}</td><td>${esc(r.nm.s)}</td><td>${esc(r.nm.sec)}</td><td class="n">${f(100 * r.w, 2)}</td><td class="n">${f(100 * r.b, 2)}</td>${R.b0 ? `<td class="n">${f(100 * r.b0, 2)}</td>` : ''}<td class="n ${r.w >= r.b ? 'up' : 'down'}">${sg(100 * (r.w - r.b), 2)}</td>` + (P.live ? `<td class="n">${f(ad, 1)}</td><td class="n ${days > 5 ? 'down' : ''}">${f(days, 1)}</td>` : '') + '</tr>';
  }).join('') + '</tbody>';
  $('rb-plin').innerHTML = `<span><b${tip('وزن هدف از ارزش بازار نمادهای واجد بورس در آخرین روز سیگنال.')}>وزن شاخص</b> تقریب ارزش‌وزن بدون شناوری آزاد</span><span><b${tip('نمادهایی از شاخص که در نمونه نیستند.')}>خارج از نمونه</b> ${P.bj[0].length - nmT} نماد با مجموع وزن ${f(100 * (1 - cov), 0)}٪</span>`;
  $('rb-plan').style.display = P.live ? '' : 'none';
  $('rb-csv').onclick = () => download(`replica_${P.live ? R.asof : dj(R.sig[P.j]).replace(/\//g, '-')}.csv`, [['symbol', 'sector', 'w_replica_pct', 'w_index_pct'], ...P.rows.map(r => [r.nm.s, r.nm.sec, (100 * r.w).toFixed(3), (100 * r.b).toFixed(3)])]);
  $('rb-plan').onclick = () => {
    if (!root.SIM_ENSURE_LAB || !root.SIM_SEND_PLAN) { toast('Lab بارگذاری نشده'); return; }
    root.SIM_ENSURE_LAB(() => {
    const LAB = root.SIM_LAB, map = new Map(LAB.codes.map((c, i) => [String(c.c), i])), w = new Float64Array(LAB.k); let miss = 0;
    const L = last && last.sim ? last.sim.Ls[R.mstart.length - 1] : 1, ex = Math.min(1, L > 0 ? L : 1);
    P.rows.forEach(r => { const i = map.get(r.nm.c); if (i == null) miss++; else w[i] = r.w * ex; });
    root.SIM_SEND_PLAN(`همتاساز · ${METHODS[S.method]} ${S.N} سهم · نقدشوندگی ${LIQN[S.liq][0]}`, w);
    if (miss) toast(`${miss} نماد در Lab نبود و کنار ماند`);
    });
  };
}
root.SIM_RB_MOUNT = mount;
})(typeof window !== 'undefined' ? window : globalThis);
