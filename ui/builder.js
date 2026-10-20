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
const tip = (t, d) => ` data-tip="${esc(t)}"${d ? ` data-doc="${d}"` : ''}`;    // d: نشانی بند سند (ui/docs.js)
// بندهای سند این صفحه (فصل ۳ §۳٫۵ و فصل‌های ۶، ۷ و ۱۴)
const DOC = { samp: '3:3.5/نمونهٔ کوچک و وام', build: '3:3.5/همتاساز', enh: '3:3.5/شاخص بهبودیافته', te: '3:3.5/خطای ردیابی', act: '7:7.4', ret: '7:7.3', cost: '6:6.1', cap: '14:14.2.6', plan: '5:5.8' };
const MTIP = {
  top: 'N بزرگ‌ترین: N سهم با بیشترین ارزش بازار، با وزن ارزش بازارشان (نرمال‌شده). ساده، کم‌گردش و قابل توضیح؛ ولی صنایعی که سهم بزرگ ندارند جا می‌مانند و بتا معمولاً بالای ۱ است.',
  strat: 'طبقه‌ای (صنعت): تعداد سهم هر صنعت از N به نسبت وزن آن صنعت در شاخص، و درون هر صنعت بزرگ‌ترین‌ها؛ وزن‌ها ارزش بازار نرمال‌شده. همهٔ صنایع بزرگ حاضرند، ولی در دادهٔ ما TE آن تقریباً هم‌اندازهٔ «N بزرگ‌ترین» است (فصل ۳ §۳٫۵، جدول).',
  opt: 'بهینه‌سازی TE: روی ۳N بزرگ‌ترین، وزن‌ها طوری انتخاب می‌شوند که (w − b)ᵀΣ(w − b) کمینه شود (فقط‌خرید، Σ انقباضی Ledoit–Wolf روی ۲۵۲ روز)، سپس N وزن برتر نگه داشته و دوباره حل می‌شود. کمترین TE، ولی گردش بیشتر و وابسته به برآورد کوواریانس.',
};
const jf = new Intl.DateTimeFormat('fa-IR-u-ca-persian-nu-latn', { year: 'numeric', month: '2-digit', day: '2-digit' });
const dj = d => jf.format(new Date(d * 864e5));
const jyear = d => +dj(d).split('/')[0], jmonth = d => +dj(d).split('/')[1];
const METHODS = { top: 'N بزرگ‌ترین', strat: 'طبقه‌ای (صنعت)', opt: 'بهینه‌سازی TE' };
const LIQN = { 0: ['بدون فیلتر', 'همهٔ واجدان بورس نامزد نگهداری‌اند.'], 1: ['ملایم', 'نماد باید دست‌کم ۵۰ روز از ۶۳ روز اخیر معامله شده و میانهٔ ارزش معاملاتش بالاتر از صدک ۲۰ واجدان باشد.'],
  2: ['متوسط', 'دست‌کم ۵۶ روز از ۶۳ روز معامله و میانهٔ ارزش معاملات بالاتر از صدک ۴۰ واجدان.'], 3: ['سخت', 'دست‌کم ۶۰ روز از ۶۳ روز معامله و میانهٔ ارزش معاملات بالاتر از صدک ۶۰ واجدان.'] };
const S = { method: 'opt', N: 30, liq: 0, mode: 'none', cash: 10, loan: 20, rb: 30, rc: 0, cost: 125, j0: 0, pdate: 'live', aum: 500 };
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
  <section class="panel rb-panel" style="--lg:var(--lg-a)">
    <div class="panel-head"><span class="lg-badge">2</span><span class="panel-title"${tip('آزمایشگاه همتا: «شاخص كل» را با N سهم بسازید، فقط نمادهای نقدشونده را راه بدهید، بخشی را نقد نگه دارید یا وام بگیرید، و ببینید اگر از هر ماه گذشته شروع کرده بودید تا امروز چقدر از شاخص فاصله می‌گرفتید. همه‌چیز در مرورگر از سری‌های ازپیش‌ساختهٔ پایتون (tools/build_replica_panel.py) حساب می‌شود: هر ماه ریبالانس، اجرا از روز بعد، بازده کل.', DOC.build)}>همتای خودتان را بسازید و بسنجید</span><span class="chip" id="rb-chip"${tip('نخستین ماه سیگنال تا آخرین روز داده، و تعداد ریبالانس‌های ماهانه‌ای که در این بازه شبیه‌سازی شده است.', DOC.build)}></span></div>
    <div class="rb-grid">
      <div class="rb-ctl">
        <div class="rb-g"><div class="rb-gt"${tip('گام اول: از میان نمادهای واجد بورس، کدام و چند سهم خریده شوند. هرچه N بیشتر، خطای ردیابی کمتر ولی تعداد سفارش و نیاز به نقدشوندگی بیشتر.', DOC.samp)}>۱ · نمونه</div>
          <label${tip('چطور N سهم انتخاب و وزن‌دهی شوند. «N بزرگ‌ترین» ساده و کم‌گردش است؛ «طبقه‌ای» سهم هر صنعت را حفظ می‌کند؛ «بهینه‌سازی TE» با کوواریانس، نوسان تفاضل با شاخص را کمینه می‌کند (کمترین TE ولی گردش بیشتر).', DOC.samp)}>روش <span class="seg" id="rb-method">${Object.entries(METHODS).map(([k, t]) => `<button data-v="${k}" aria-pressed="false"${tip(MTIP[k], DOC.samp)}>${t}</button>`).join('')}</span></label>
          <label${tip('N: تعداد سهامی که واقعاً خریده می‌شود. خطای ردیابی با N تند پایین می‌آید و بعد به «کف خطا» نزدیک می‌شود (خطای خرید همهٔ واجدان در برابر شاخص رسمی، حدود ۱٫۴٪). برای انتخاب N، پاسخ پنل ۱ بالای صفحه را ببینید؛ توضیح هر گزینه در فهرست آمده است.', DOC.samp)}>تعداد سهام <select id="rb-n">${R.Ns.map(n => `<option data-tip="نمونهٔ ${n} سهمی: ${n < 30 ? 'ردیابی ضعیف (TE بالای ۴٪)؛ فقط برای سرمایهٔ خیلی کوچک.' : n < 80 ? 'سازش خطای ردیابی و هزینه (TE ≈ ۳ تا ۴٪ با بهینه‌سازی).' : 'نزدیک کف خطا (TE ≈ ۲٪ با بهینه‌سازی)؛ نیاز به نقدشوندگی بیشتر.'}">${n}</option>`).join('')}</select></label>
          <label${tip('فیلتر ورود به نمونه بر پایهٔ ۶۳ روز اخیر: چند روز معامله شده و میانهٔ ارزش معاملات روزانه در چه صدکی از واجدان است. هدف (وزن شاخص) عوض نمی‌شود، فقط نامزدها کم می‌شوند؛ پس TE کمی بالا می‌رود ولی همتا با سرمایهٔ بزرگ‌تر و بدون گیرکردن در صف ساخته می‌شود.', DOC.build)}>نقدشوندگی <span class="seg" id="rb-liq">${Object.keys(R.liq).map(q => `<button data-v="${q}" aria-pressed="false"${tip(LIQN[q][1])}>${LIQN[q][0]}</button>`).join('')}</span></label>
        </div>
        <div class="rb-g"><div class="rb-gt"${tip('گام دوم: نسبت سهام به سرمایه L. ‏L = ۱ یعنی همهٔ پول در سهام؛ L < ۱ بخشی نقد (بازده و نوسان کمتر)؛ L > ۱ وام (بهره هر روز از ارزش کم می‌شود). L هر ماه در روز ریبالانس دوباره تنظیم می‌شود.', DOC.build)}>۲ · سرمایه: نقد یا وام</div>
          <label${tip('نقد ثابت: درصدی از سرمایه بیرون از سهام (L < ۱). وام ثابت: درصدی وام و خرید سهام بیشتر (L > ۱). تراز بتا: هر ماه L = ۱/β که β بتای ۲۵۲ روزهٔ نمونه روی شاخص است (بُرش ۰٫۷ تا ۱٫۵)؛ نمونهٔ کوچک معمولاً β > ۱ دارد، پس تراز بتا بیشتر نقد نگه می‌دارد تا وام بگیرد. ارزش = L·سهام + نقد − بدهی.', DOC.build)}>نقد / وام <span class="seg" id="rb-mode">
        <button data-v="none" aria-pressed="false"${tip('L = ۱: همهٔ سرمایه در سهام نمونه، بدون نقد و وام. مرجع مقایسهٔ دو حالت دیگر.', DOC.build)}>بدون</button><button data-v="cash" aria-pressed="false"${tip('L = ۱ − درصد نقد. نقد با «بازده نقد» رشد می‌کند. بتا و نوسان کم می‌شود ولی در بازار صعودی عقب می‌مانید؛ برای ورود و خروج وجوه صندوق مفید است.', DOC.build)}>نقد ثابت</button><button data-v="loan" aria-pressed="false"${tip('L = ۱ + درصد وام. وام با «نرخ وام» روزانه بهره می‌خورد. اگر بازده سهام از نرخ وام بیشتر باشد سود می‌دهد، ولی بتا و افت را بالا می‌برد. دسترسی و نرخ واقعی وام [تأیید لازم].', DOC.build)}>وام ثابت</button><button data-v="beta" aria-pressed="false"${tip('هر ماه L = ۱/β نمونه (بُرش ۰٫۷ تا ۱٫۵) تا حساسیت همتا به بازار حدود ۱ بماند. TE را کم می‌کند، ولی چون بتای نمونه معمولاً بالای ۱ است بخشی نقد می‌ماند و بازده کمی پایین می‌آید.', DOC.build)}>تراز بتا</button></span></label>
          <label id="rb-amt-l"${tip('درصد نقد (یا وام) نسبت به کل سرمایه؛ مثلاً ۲۰٪ وام یعنی به‌ازای هر ۱۰۰ ریال سرمایه ۱۲۰ ریال سهام. حداکثر ۵۰٪.', DOC.build)}><span id="rb-amt-t">مقدار ٪</span> <input type="number" id="rb-amt" value="10" min="0" max="50" step="5"></label>
          <label${tip('نرخ سادهٔ سالانهٔ وام؛ بهره هر روز به نسبت روزهای تقویمی به بدهی اضافه و از ارزش همتا کم می‌شود. پیش‌فرض ۳۰٪ فرضی است [تأیید لازم]؛ نرخ اعتبار کارگزاری یا تأمین مالی خودتان را بگذارید.', DOC.build)}>نرخ وام ٪ <input type="number" id="rb-rb" value="30" min="0" max="80" step="1"></label>
          <label${tip('بازده سالانهٔ بخش نقد، مثلاً صندوق درآمد ثابت [راستی‌آزمایی نشده]؛ صفر یعنی نقد بی‌بهره. فقط وقتی L < ۱ است اثر دارد.', DOC.build)}>بازده نقد ٪ <input type="number" id="rb-rc" value="0" min="0" max="80" step="1"></label>
        </div>
        <div class="rb-g"><div class="rb-gt"${tip('گام سوم: با چه هزینه‌ای و از چه تاریخی بسنجیم. نتیجه همیشه «از شروع تا امروز» است؛ جدول «اگر از سال‌های گذشته شروع می‌کردیم» در پنل ۳ همین را برای همهٔ سال‌ها نشان می‌دهد.', DOC.build)}>۳ · سنجش</div>
          <label${tip('هزینهٔ رفت‌وبرگشت (خرید + فروش) بر حسب واحد پایه؛ ۱۰۰ bp = ۱٪. هر ماه: هزینه = گردش یک‌طرفه × L × این عدد. کارمزد، مالیات فروش و لغزش قیمت را با هم بگیرید؛ پیش‌فرض همهٔ برنامه ۱۲۵ bp است [تأیید لازم].', DOC.cost)}>هزینه (bp) <input type="number" id="rbx-cost" value="125" min="0" step="5"></label>
          <label${tip('فرض کنید همتا را در پایان این ماه شمسی خریده بودید. همهٔ اعداد (TE، فاصله، تفاوت تجمعی) از همین ماه تا آخرین روز داده حساب می‌شود. شروع‌های دیرتر کوتاه‌اند و نویز بیشتری دارند.', DOC.build)}>شروع از <select id="rb-j0">${startOpts}</select></label>
        </div>
      </div>
      <div class="rb-out">
        <div class="lineage rb-lead" id="rbx-read"></div>
        <div class="kpis" id="rb-kpi"></div>
        <details class="sam-fold sm"><summary${tip('عددهای تکمیلی: TE فقط از نمونه‌گیری (در برابر خرید همهٔ واجدان)، بتا و همبستگی با شاخص، میانگین L، گردش ماهانه و پوشش وزن شاخص.', DOC.build)}>شاخص‌های بیشتر</summary><div class="kpis" id="rb-kpi2"></div></details>
    <div class="panel-body" style="padding:var(--s-3)"><div class="mute" style="font-size:var(--fs-xs)" id="rb-ch1-t"></div><div id="rb-ch1"></div><div class="mute" style="font-size:var(--fs-xs);margin-top:8px" id="rb-ch2-t"></div><div id="rb-ch2"></div><div class="mute" style="font-size:var(--fs-xs);margin-top:8px" id="rb-ch3-t" data-tip="هر ستون یک دورهٔ نگهداری (ریبالانس تا ریبالانس بعد): سبز یعنی همتا جلوتر از «شاخص كل» رسمی، قرمز یعنی عقب‌تر. با نگه‌داشتن نشانگر روی هر ستون، اختلاف به چهار جزء (انتخاب سهام، اعضا و داده، نقد/وام، هزینه) تقسیم و محتمل‌ترین علت با نمادهای مؤثر نشان داده می‌شود." data-doc="3:3.5/همتاساز">اختلاف هر دوره بین همتا و شاخص (واحد درصد؛ سبز جلوتر، قرمز عقب‌تر) — نشانگر را روی هر ستون نگه دارید تا علت تحلیل شود</div><div id="rb-ch3"></div><div class="mute" id="rb-hov" style="font-size:var(--fs-2xs);min-height:1.4em"></div></div>
      </div>
    </div>
  </section>
  <section class="panel" style="--lg:var(--lg-b)">
    <div class="panel-head"><span class="lg-badge">3</span><span class="panel-title"${tip('همان تنظیمات پنل ۲ از دو زاویهٔ دیگر: (۱) حساسیت به زمان شروع: اگر ابتدای هر سال شمسی شروع کرده بودید؛ (۲) خود پرتفوی: کدام سهم‌ها با چه وزنی در هر تاریخ، در برابر وزن شاخص.', DOC.build)}>جزئیات همین همتا</span>
      <div class="seg" id="rb-dtabs"><button data-t="years" aria-pressed="true"${tip('هر ردیف: همین همتا اگر از پایان اسفند آن سال شروع شده بود، تا امروز. نشان می‌دهد نتیجهٔ پنل ۲ به تاریخ شروع حساس است یا نه. ردیف تاریخ شروع فعلی برجسته است.', DOC.build)}>اگر از سال‌های گذشته شروع می‌کردیم</button><button data-t="port" aria-pressed="false"${tip('فهرست سهام و وزن‌هایی که در تاریخ سیگنال انتخاب‌شده می‌خریدید، کنار وزن همان سهم در شاخص. «امروز (زنده)» پرتفوی قابل اجرای روز کاری بعد است و می‌توان آن را به «دستور اجرا» فرستاد.', DOC.build)}>پرتفوی در یک تاریخ</button></div>
      <div class="panel-tools" id="rb-ptools" hidden><button class="tool" id="rbx-csv"${tip('دریافت فهرست نماد، صنعت، وزن همتا و وزن شاخص همین تاریخ به‌صورت CSV.')}>CSV</button><button class="tool" id="rb-plan"${tip('فقط برای «امروز»: وزن‌ها (ضرب در L اگر نقد دارید) به «اجرا ← دستور اجرا» می‌رود تا با پرتفوی فعلی مقایسه و سفارش خرید و فروش با تعداد و قیمت مرجع ساخته شود.', DOC.plan)}>ارسال به برنامهٔ اقدام ←</button></div></div>
    <div id="rb-d-years"><div class="panel-body scroll" style="max-height:340px"><table class="dt" id="rb-years"></table></div></div>
    <div id="rb-d-port" hidden>
      <div class="ctl"><label${tip('تاریخ سیگنال (پایان ماه شمسی). پرتفوی فقط با داده‌ای که آن روز در دسترس بود ساخته می‌شود (بدون نگاه به آینده) و از روز کاری بعد اجرا می‌شود. برای تاریخ‌های گذشته، خطای ۲۵۲ روز بعدش هم نشان داده می‌شود.', DOC.build)}>تاریخ <select id="rb-date">${dateOpts}</select></label>
        <label${tip('اندازهٔ صندوق یا سبد شما. برای هر نماد: روز لازم = وزن × سرمایه ÷ (۱۰٪ × میانهٔ ارزش معاملات روزانه). بیش از ۵ روز قرمز می‌شود، یعنی خرید آن نماد قیمت را جابه‌جا می‌کند. فقط برای «امروز».', DOC.cap)}>سرمایه (میلیارد ریال) <input type="number" id="rb-aum" value="500" min="1" step="10"></label></div>
      <div class="kpis" id="rb-pkpi"></div>
      <div class="panel-body scroll" style="max-height:440px"><table class="dt" id="rb-ptab"></table></div>
      <div class="lineage" id="rb-plin"></div>
    </div>
  </section>
  <details class="sam-fold panel" id="rb-enh-box"><summary${tip('پیشرفته: به‌جای کپی دقیق «شاخص كل»، هدف را آگاهانه عوض کنید (کم یا زیاد کردن صنعت، تیلت به یک معیار مثل کم‌نوسان، سقف وزن هر سهم، آمیختن با هم‌وزن) و با همان N سهم و روش بسازید. خروجی: هدف تازه چقدر از شاخص فاصله می‌گیرد و چه بازده اضافه‌ای داشته است.', DOC.enh)}><span class="lg-badge">4</span> شاخص بهبودیافته (پیشرفته): هدف را با تیلت و قید تغییر دهید</summary><div id="rb-enh"></div></details>`;
  const seg = (id, key, cb) => $(id).querySelectorAll('button').forEach(b => { b.onclick = () => { if (key !== 'mode') stale(); S[key] = key === 'liq' ? +b.dataset.v : b.dataset.v; cb && cb(); render(); }; });
  seg('rb-method', 'method'); seg('rb-liq', 'liq'); seg('rb-mode', 'mode');
  $('rb-dtabs').querySelectorAll('button').forEach(b => { b.onclick = () => {                 // زبانه‌های «جزئیات همین همتا»
    const port = b.dataset.t === 'port';
    $('rb-dtabs').querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
    $('rb-d-years').hidden = port; $('rb-d-port').hidden = !port; $('rb-ptools').hidden = !port;
  }; });
  $('rb-n').onchange = e => { stale(); S.N = +e.target.value; render(); };
  $('rb-amt').onchange = e => { S[S.mode === 'loan' ? 'loan' : 'cash'] = +e.target.value; render(); };
  $('rb-rb').onchange = e => { S.rb = +e.target.value; render(); }; $('rb-rc').onchange = e => { S.rc = +e.target.value; render(); };
  $('rbx-cost').onchange = e => { S.cost = +e.target.value; render(); };
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
  const kp = m ? [['TE در برابر شاخص رسمی', f(m.te, 2) + '٪', 'خطای ردیابی (Tracking Error) سالانه: انحراف معیار «بازده روزانهٔ همتا منهای شاخص» × √۲۵۲؛ یعنی در یک سال معمولی، بازده همتا حدوداً این‌قدر بالا یا پایین شاخص می‌افتد. زیر ۲٪ خوب، ۳ تا ۵٪ متوسط، بالای ۶٪ ضعیف. کف آن با خرید همهٔ واجدان حدود ۱٫۴٪ است.', DOC.te],
    ['TE در برابر همتای کامل', f(m.teC, 2) + '٪', 'همان TE ولی در برابر «همتای کامل» (خرید همهٔ واجدان با وزن بازار) نه شاخص رسمی؛ پس فقط هزینهٔ «کم‌خریدن» را می‌سنجد و خطای ناشی از تفاوت اعضا (شرط واجدیت همتا (سابقهٔ ۲۵۲ روزه؛ نماد تازه‌عرضه یا کم‌تحرک در همتا نیست ولی در شاخص هست) و به‌روزرسانی ماهانهٔ اعضا) و داده را ندارد. فاصلهٔ این با TE رسمی، سهم خطایی است که با N بیشتر حل نمی‌شود.', DOC.te],
    ['فاصلهٔ بازده سالانه (واحد درصد)', sg(m.gap), 'بازده مرکب سالانهٔ همتا (پس از هزینه و بهره) منهای بازده سالانهٔ «شاخص كل» رسمی با سود نقدی. منفی یعنی همتا هر سال به‌طور متوسط این‌قدر عقب ماند. TE نوسانِ این فاصله است؛ خود فاصله ممکن است سیستماتیک باشد، مثلاً چون نمونهٔ بزرگ‌ها دم سهام کوچک بازار را ندارد.', DOC.ret],
    ['تفاوت تجمعی تا امروز', sg(m.td) + '٪', `به زبان پول: اگر از ${dj(R.sig[S.j0])} تا امروز (${f(yrs, 1)} سال) ۱۰۰ ریال در همتا و ۱۰۰ ریال در شاخص بود، همتا این‌قدر درصد بیشتر یا کمتر داشت: (رشد همتا ÷ رشد شاخص) − ۱. مثبت یعنی جلوتر از شاخص.`, DOC.build],
    ['بتا', f(m.beta, 2), 'شیب رگرسیون بازده روزانهٔ همتا روی شاخص: اگر شاخص ۱٪ بالا رود، همتا به‌طور متوسط β٪ بالا می‌رود. بالای ۱ یعنی پرنوسان‌تر از بازار (معمول در نمونهٔ کوچک)؛ نقد آن را پایین و وام بالا می‌برد.', DOC.act],
    ['همبستگی', f(m.corr, 3), 'همبستگی بازده روزانهٔ همتا و شاخص (۱ یعنی هم‌حرکت کامل). بالای ۰٫۹۹ یعنی تقریباً همهٔ حرکت روزانهٔ شاخص را دارید؛ هرچه پایین‌تر، TE بیشتر.', DOC.act]] : [];
  const kp2 = [['میانگین L', f(sL / cnt, 2), 'میانگین L در ماه‌های آزمون: ۱ یعنی همه در سهام، زیر ۱ بخشی نقد، بالای ۱ وام. در «تراز بتا» خودکار تعیین می‌شود.', DOC.build], ['گردش ماهانهٔ یک‌طرفه', f(100 * sT / Math.max(cnt - 1, 1), 0) + '٪', 'گردش یک‌طرفه: نصف مجموع قدرمطلق تغییر وزن‌ها در هر ریبالانس، میانگین ماه‌ها (پیش از ضرب در L). هزینهٔ ماهانه ≈ این عدد × هزینهٔ رفت‌وبرگشت. «بهینه‌سازی TE» معمولاً گردش بیشتری از «N بزرگ‌ترین» دارد.', DOC.cost],
    ['ظرفیت امروز (میلیارد ریال)', f(capNow, 0), 'بزرگ‌ترین سرمایه‌ای که پرتفوی امروز را در یک روز می‌سازد، اگر از هر نماد بیش از ۱۰٪ ارزش معاملات روزانه‌اش (میانهٔ ۶۳ روز) نخرید؛ محدودکننده کم‌نقدشونده‌ترین نماد نسبت به وزنش است. برای سرمایهٔ بزرگ‌تر، فیلتر نقدشوندگی را سخت‌تر کنید یا ساخت را چندروزه ببینید.', DOC.cap],
    ['پوشش وزن شاخص (آخرین ماه)', f(100 * covB, 0) + '٪', 'چند درصد از وزن «شاخص كل» در سهام نمونه است. مثلاً ۷۰٪ یعنی ۳۰٪ از شاخص (معمولاً سهام کوچک‌تر) اصلاً خریده نشده و روش انتخاب باید با وزن‌دهی جبرانش کند.', DOC.build]];
  const kpiHtml = a => a.map(([k, v, t, d]) => `<div class="kpi"${tip(t, d || DOC.build)}><div class="k"${tip(t, d || DOC.build)}>${k}</div><div class="v num">${v}</div></div>`).join('');
  // چهار عدد اصلی: چقدر دقیق، چقدر عقب، از شروع تا امروز، چقدر قابل ساخت؛ بقیه در «شاخص‌های بیشتر»
  const MAIN = new Set(['TE در برابر شاخص رسمی', 'فاصلهٔ بازده سالانه (واحد درصد)', 'تفاوت تجمعی تا امروز', 'ظرفیت امروز (میلیارد ریال)']), all = [...kp, ...kp2];
  $('rb-kpi').innerHTML = kpiHtml(all.filter(x => MAIN.has(x[0]))); $('rb-kpi2').innerHTML = kpiHtml(all.filter(x => !MAIN.has(x[0])));
  if (m) {
    const ov = S.mode === 'none' ? 'بدون وام و نقد' : S.mode === 'cash' ? `${S.cash}٪ نقد` : S.mode === 'loan' ? `${S.loan}٪ وام` : 'تراز بتا';
    $('rbx-read').innerHTML = `<span><b${tip('جمع‌بندی خودکار همین تنظیمات به زبان ساده؛ با هر تغییر دوباره نوشته می‌شود.', DOC.build)}>خوانش</b> اگر از ${dj(R.sig[S.j0])} همتایی با ${S.N} سهم (${METHODS[S.method]}، نقدشوندگی ${LIQN[S.liq][0]}، ${ov}) ساخته بودیم، تا امروز (${f(yrs, 1)} سال) ارزش همتا نسبت به شاخص رسمی ${sg(m.td)}٪ تفاوت داشت و خطای ردیابی سالانه ${f(m.te, 1)}٪ بود.</span><span><b${tip('فرض‌های شبیه‌سازی: بازده کل (سود نقدی روز استحقاق دوباره سرمایه‌گذاری می‌شود)، ریبالانس پایان ماه شمسی و اجرا روز بعد، بدون صف خرید و فروش و حد نوسان. این‌ها نتیجه را کمی خوش‌بینانه می‌کنند.', DOC.build)}>فرض</b> بازده کل، ریبالانس پایان ماه جلالی، اجرا روز بعد، بدون صف و حد نوسان؛ نرخ وام ${S.rb}٪ و هزینه ${S.cost}bp [تأیید لازم].</span>`;
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
  $('rb-ch1-t').innerHTML = 'رشد ۱۰۰ واحد (مقیاس لگاریتمی): <b style="color:var(--ch-1)">━ همتا</b> در برابر <b style="color:var(--warn)">━ «شاخص كل» رسمی (بازده کل)</b>';
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
   هزینه = گردش ریبالانس × L × هزینهٔ رفت‌وبرگشت؛ نقد/وام = باقی‌مانده (اثر L ≠ ۱ و بهرهٔ وام/نقد). جمع ماه = جمع ساده‌ی روزها (تقریب حسابی).
   سهم هر نماد در «انتخاب سهام» = Σ روزها (وزن همتا − وزن شاخص، هر دو رانش‌یافته) × بازده نماد؛ از SIM_REPX (همان بازده‌های روزانهٔ شاخص بهبودیافته). */
function monthParts() {
  if (!last || !last.sim) return [];
  const p = prep(R), key = curKey(), r = seriesOf(R, key), c = R.configs[key], sim = last.sim, nm = R.mstart.length, n = R.dates.length, out = [];
  for (let j = S.j0; j < nm; j++) {
    const t0 = R.mstart[j], t1 = j + 1 < nm ? R.mstart[j + 1] : n;
    let tot = 0, samp = 0, memb = 0, other = 0;
    for (let t = Math.max(t0, sim.t0 + 1); t < t1; t++) {
      const navR = sim.nav[t] / sim.nav[t - 1] - 1, d = navR - p.K[t];
      tot += d; samp += r[t] - p.C[t]; memb += p.C[t] - p.K[t]; other += navR - r[t];
    }
    if (t1 - 1 <= sim.t0) continue;
    const L = sim.Ls[j] === sim.Ls[j] ? sim.Ls[j] : 1, cost = j === S.j0 ? 0 : -c.to[j] * L * S.cost / 1e4;   // هزینهٔ خرید اولیه در روز شروع است که در سنجش نیست
    out.push({ j, t0, t1, end: R.dates[t1 - 1], tot: 100 * tot, samp: 100 * samp, memb: 100 * memb, cost: 100 * cost, lev: 100 * (other - cost), L });
  }
  return out;
}
const CONTRIB = new Map();
/** بزرگ‌ترین سهم‌های نمادها در «انتخاب سهام» یک ماه (نیازمند SIM_REPX) */
function topContrib(m) {
  const X = root.SIM_REPX; if (!X || !R.b || R !== R0) return null;
  const k = `${curKey()}|${m.j}`; if (CONTRIB.has(k)) return CONTRIB.get(k);
  if (!X._ret) { const bin = atob(X.ret), u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); X._ret = new Float32Array(u.buffer); X._di = new Map(X.dates.map((d, i) => [d, i])); }
  const K = X.k, c = R.configs[curKey()], sel = c.sel[m.j], bj = R.b[m.j];
  const w = new Map(), b = new Map();
  sel[0].forEach((i, q) => w.set(i, sel[1][q] / 1e5)); bj[0].forEach((i, q) => b.set(i, bj[1][q] / 1e5));
  const ids = [...new Set([...w.keys(), ...b.keys()])], ww = ids.map(i => w.get(i) || 0), bb = ids.map(i => b.get(i) || 0), con = ids.map(() => 0), cum = ids.map(() => 0);
  for (let t = m.t0 + 1; t < m.t1; t++) {
    const xi = X._di.get(R.dates[t]); if (xi == null) continue;
    const sw = ww.reduce((s, v) => s + v, 0) || 1, sb = bb.reduce((s, v) => s + v, 0) || 1;
    ids.forEach((i, q) => { const x = X._ret[xi * K + i], rr = x === x ? x : 0; con[q] += (ww[q] / sw - bb[q] / sb) * rr; cum[q] = (1 + cum[q]) * (1 + rr) - 1; ww[q] *= 1 + rr; bb[q] *= 1 + rr; });
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
const PART_FA = { samp: 'انتخاب سهام', memb: 'اعضا و داده', lev: 'نقد/وام', cost: 'هزینهٔ ریبالانس' };
function explain(m) {
  const parts = ['samp', 'memb', 'lev', 'cost'].map(k => [k, m[k]]).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
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
    else why += ' <span class="mute">(جزئیات نمادها در حال بارگذاری…)</span>';
  } else if (mk === 'memb') why = 'احتمالاً <b>تفاوت اعضا و داده</b>: حتی خرید همهٔ واجدان هم این ماه با شاخص رسمی فاصله داشت؛ معمولاً نماد تازه‌عرضه یا کم‌سابقه که در شاخص رسمی هست ولی هنوز واجد همتا نیست، بازگشایی پس از توقف، یا تفاوت ثبت سود و افزایش سرمایه.';
  else if (mk === 'lev') why = `احتمالاً <b>${m.L < 1 ? 'نقد' : m.L > 1 ? 'وام' : 'نقد/وام'}</b>: L این ماه ${f(m.L, 2)} بود؛ ${m.L < 1 ? 'بخشی از سرمایه بیرون بازار بود و بازار ' + (m.tot < 0 ? 'بالا رفت' : 'پایین آمد') : 'وام اثر حرکت بازار را بزرگ کرد و بهرهٔ وام هم کم شد'}.`;
  else why = 'احتمالاً <b>هزینهٔ ریبالانس</b>: گردش سبد در ابتدای این دوره زیاد بود.';
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
  $('rb-pkpi').innerHTML = [['تعداد نماد', nmT, 'تعداد سهامی که در این تاریخ خریده می‌شود (ممکن است از N کمتر باشد اگر نامزد کافی نقدشونده نبود).'], ['پوشش وزن شاخص', f(100 * cov, 0) + '٪', 'چند درصد از وزن «شاخص كل» در همین سهام است؛ بقیه اصلاً خریده نشده.'], ['سهم فعال', f(100 * act, 0) + '٪', 'سهم فعال (Active share): نصف مجموع |وزن همتا − وزن شاخص| روی همهٔ نمادها. ۰٪ یعنی همان شاخص، ۱۰۰٪ یعنی هیچ اشتراکی. برای همتای خوب معمولاً زیر ۳۰٪.'],
    ['ظرفیت یک‌روزه (میلیارد ریال)', f(P.cap, 0), 'بزرگ‌ترین سرمایه‌ای که این پرتفوی را در یک روز می‌سازد، اگر از هر نماد بیش از ۱۰٪ ارزش معاملات روزانه‌اش نخرید.'],
    ...(after ? [['TE یک سال بعد', f(after.te, 2) + '٪', 'آزمون بیرون از تاریخ: اگر همتا از همین تاریخ ساخته و هر ماه به‌روز می‌شد، خطای ردیابی واقعی ۲۵۲ روز کاری بعد چقدر بود.'], ['رشد نسبی یک سال بعد', sg(after.td) + '٪', '(رشد همتا ÷ رشد شاخص) − ۱ در ۲۵۲ روز کاری بعد از این تاریخ.'], ['L این ماه', f(Lm, 2), 'نسبت سهام به سرمایه در این ماه با تنظیمات نقد/وام فعلی (در «تراز بتا» از بتای همان ماه).']] : [])]
    .map(([k, v, t]) => `<div class="kpi"${tip(t, DOC.build)}><div class="k"${tip(t, DOC.build)}>${k}</div><div class="v num">${v}</div></div>`).join('');
  const hd = [['#', 'rank', 'رتبه بر پایهٔ وزن در همتا.'], ['نماد', '', 'نماد بورسی؛ فقط واجدان بورس (بدون فرابورس، مثل «شاخص كل»).'], ['صنعت', '', 'گروه صنعت TSETMC در همان تاریخ.'], ['وزن همتا ٪', 'n', 'وزن نماد در پرتفوی نمونه (جمع ۱۰۰٪ پیش از ضرب در L).'], ['وزن ' + (R.b0 ? 'هدف' : 'شاخص') + ' ٪', 'n', 'وزن نماد در هدف: ارزش بازار ÷ مجموع ارزش واجدان (تقریب «شاخص كل» بدون شناوری آزاد)، یا هدف تیلت‌شدهٔ پنل ۴.'], ...(R.b0 ? [['وزن شاخص رسمی ٪', 'n', 'وزن ارزش‌بازاری نماد در «شاخص كل» رسمی (تقریب بدون شناوری).']] : []), ['اختلاف', 'n', 'وزن همتا منهای وزن شاخص (واحد درصد). مثبت یعنی بیش‌وزن: نمونه با این سهم جای سهم‌های نخریده را پر کرده است.'],
    ...(P.live ? [['ارزش معاملات روزانه (میلیارد ریال)', 'n', 'میانهٔ ارزش معاملات روزانه در ۶۳ روز اخیر.'], ['روز لازم', 'n', 'وزن × سرمایه ÷ (۱۰٪ × ارزش معاملات روزانه). بیش از ۵ روز قرمز می‌شود.']] : [])];
  $('rb-ptab').innerHTML = `<thead><tr>${hd.map(([t, c, d]) => `<th class="${c}"${tip(d)}>${t}</th>`).join('')}</tr></thead><tbody>` + P.rows.map((r, p) => {
    const ad = adv[r.i], days = ad ? r.w * aumR / 1e9 / (R.part * ad) : NaN;
    return `<tr><td class="rank">${p + 1}</td><td>${esc(r.nm.s)}</td><td>${esc(r.nm.sec)}</td><td class="n">${f(100 * r.w, 2)}</td><td class="n">${f(100 * r.b, 2)}</td>${R.b0 ? `<td class="n">${f(100 * r.b0, 2)}</td>` : ''}<td class="n ${r.w >= r.b ? 'up' : 'down'}">${sg(100 * (r.w - r.b), 2)}</td>` + (P.live ? `<td class="n">${f(ad, 1)}</td><td class="n ${days > 5 ? 'down' : ''}">${f(days, 1)}</td>` : '') + '</tr>';
  }).join('') + '</tbody>';
  $('rb-plin').innerHTML = `<span><b${tip('وزن هدف = ارزش بازار کل (قیمت × همهٔ سهام) نمادهای واجد بورس در روز سیگنال؛ همان روش وزن‌دهی «شاخص كل» رسمی (نه شناور آزاد؛ بازسازی کامل شاخص با این وزن TE حدود ۰٫۳٪ دارد). تفاوت با شاخص از اعضاست، نه روش وزن.', DOC.build)}>وزن شاخص</b> ارزش بازار کل، همان روش «شاخص كل»</span><span><b${tip('نمادهای واجد شاخص که در همتا نیستند و مجموع وزنشان در شاخص؛ منبع اصلی خطای نمونه‌گیری.', DOC.build)}>خارج از نمونه</b> ${P.bj[0].length - nmT} نماد با مجموع وزن ${f(100 * (1 - cov), 0)}٪</span>`;
  $('rb-plan').style.display = P.live ? '' : 'none';
  $('rbx-csv').onclick = () => download(`replica_${P.live ? R.asof : dj(R.sig[P.j]).replace(/\//g, '-')}.csv`, [['symbol', 'sector', 'w_replica_pct', 'w_index_pct'], ...P.rows.map(r => [r.nm.s, r.nm.sec, (100 * r.w).toFixed(3), (100 * r.b).toFixed(3)])]);
  $('rb-plan').onclick = () => {
    if (!root.SIM_ENSURE_LAB || !root.SIM_SEND_PLAN) { toast('Lab بارگذاری نشده'); return; }
    root.SIM_ENSURE_LAB(() => {
    const LAB = root.SIM_LAB, map = new Map(LAB.codes.map((c, i) => [String(c.c), i])), w = new Float64Array(LAB.k); let miss = 0;
    const L = last && last.sim ? last.sim.Ls[R.mstart.length - 1] : 1, ex = Math.min(1, L > 0 ? L : 1);
    P.rows.forEach(r => { const i = map.get(r.nm.c); if (i == null) miss++; else w[i] = r.w * ex; });
    root.SIM_SEND_PLAN(`همتاساز · ${METHODS[S.method]} ${S.N} سهم · نقدشوندگی ${LIQN[S.liq][0]}`, w, R === R0 ? { kind: 'replica', key: curKey() } : { kind: 'enh' });
    if (miss) toast(`${miss} نماد در Lab نبود و کنار ماند`);
    });
  };
}
root.SIM_RB_MOUNT = mount;
})(typeof window !== 'undefined' ? window : globalThis);
