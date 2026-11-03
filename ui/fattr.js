/* همتا — «تفکیک فاکتوری صندوق» (بخش صندوق‌ها؛ فصل ۷ §۷٫۹)
   داده: window.SIM_FATTR از tools/fund_attribution.py (بازده هفتگی صندوق و شش فاکتور، و نمای پرتفوی کدال).
   رگرسیون در مرورگر دوباره حساب می‌شود (نرخ بدون ریسک و بازه قابل‌تغییر)؛ همان ols_hac پایتون ← node tools/fattr_selftest.js */
(function (root) {
'use strict';

/* ═══════════════ موتور (بدون DOM) ═══════════════ */
function inv(A) {
  const n = A.length, M = A.map((r, i) => [...r, ...Array.from({ length: n }, (_, j) => +(i === j))]);
  for (let c = 0; c < n; c++) {
    let p = c; for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
    [M[c], M[p]] = [M[p], M[c]];
    const d = M[c][c]; if (Math.abs(d) < 1e-300) return null;
    for (let j = 0; j < 2 * n; j++) M[c][j] /= d;
    for (let r = 0; r < n; r++) if (r !== c) { const f = M[r][c]; if (f) for (let j = 0; j < 2 * n; j++) M[r][j] -= f * M[c][j]; }
  }
  return M.map(r => r.slice(n));
}
/** OLS با خطای معیار نیوی‌وست (بارتلت 1 − l/(L+1))؛ ستون ثابت اینجا افزوده می‌شود. همان tools/attribution.ols_hac. */
function olsHac(y, X, L) {
  const T = y.length, Z = X.map(r => [1, ...r]), k = Z[0].length;
  const XtX = Array.from({ length: k }, (_, i) => Array.from({ length: k }, (_, j) => Z.reduce((s, r) => s + r[i] * r[j], 0)));
  const Q = inv(XtX); if (!Q) return null;
  const Xty = Array.from({ length: k }, (_, i) => Z.reduce((s, r, t) => s + r[i] * y[t], 0));
  const b = Q.map(r => r.reduce((s, v, j) => s + v * Xty[j], 0));
  const e = Z.map((r, t) => y[t] - r.reduce((s, v, j) => s + v * b[j], 0));
  const u = Z.map((r, t) => r.map(v => v * e[t]));
  const S = Array.from({ length: k }, (_, i) => Array.from({ length: k }, (_, j) => u.reduce((s, r) => s + r[i] * r[j], 0)));
  for (let l = 1; l <= L; l++) {
    const w = 1 - l / (L + 1);
    for (let i = 0; i < k; i++) for (let j = 0; j < k; j++) { let g = 0; for (let t = l; t < T; t++) g += u[t][i] * u[t - l][j] + u[t][j] * u[t - l][i]; S[i][j] += w * g; }
  }
  const QS = Q.map(r => Array.from({ length: k }, (_, j) => r.reduce((s, v, m) => s + v * S[m][j], 0)));
  const V = QS.map(r => Array.from({ length: k }, (_, j) => r.reduce((s, v, m) => s + v * Q[m][j], 0)));
  const ym = y.reduce((s, v) => s + v, 0) / T, sst = y.reduce((s, v) => s + (v - ym) ** 2, 0), sse = e.reduce((s, v) => s + v * v, 0);
  return { b, se: V.map((r, i) => Math.sqrt(Math.max(r[i], 0))), r2: sst > 0 ? 1 - sse / sst : NaN, e };
}
const mean = a => a.reduce((s, v) => s + v, 0) / a.length;
const sd = (a, ddof = 1) => { const m = mean(a); return Math.sqrt(a.reduce((s, v) => s + (v - m) ** 2, 0) / (a.length - ddof)); };

/** fund: {y, days, F:{MKT_raw, SMB…}}؛ همان fund_attribution.regress. rfAnn: عدد ثابت یا آرایهٔ هفتگی (rf_w). lo/hi = بازهٔ اندیس هفته‌ها [lo, hi). */
function regress(fund, rfAnn, codes, L, lo = 0, hi = fund.y.length) {
  const y = [], X = [], idx = [];
  for (let t = lo; t < hi; t++) {
    const rf = Math.pow(1 + (typeof rfAnn === 'number' ? rfAnn : rfAnn[t]), fund.days[t] / 365) - 1, row = codes.map(c => c === 'MKT' ? fund.F.MKT_raw[t] - rf : fund.F[c][t]);
    const v = fund.y[t] - rf;
    if (!isFinite(v) || row.some(x => x == null || !isFinite(x))) continue;
    y.push(v); X.push(row); idx.push(t);
  }
  if (y.length < codes.length + 10) return null;
  const R = olsHac(y, X, L); if (!R) return null;
  const k = codes.length, t = R.b.map((b, i) => R.se[i] > 0 ? b / R.se[i] : NaN), mF = codes.map((_, i) => mean(X.map(r => r[i])));
  const ssr = Math.sqrt(R.e.reduce((s, v) => s + v * v, 0) / (y.length - k - 1));
  const D = olsHac(y.slice(1), X.slice(1).map((r, i) => [...r, X[i][0]]), L);
  return { weeks: y.length, idx, alpha_ann: 5200 * R.b[0], alpha_t: t[0], r2: R.r2, resid_vol_ann: 100 * ssr * Math.sqrt(52), excess_ann: 5200 * mean(y), vol_ann: 100 * sd(y) * Math.sqrt(52),
    dimson_beta: D ? D.b[1] + D.b[k + 1] : NaN, dimson_lag: D ? D.b[k + 1] : NaN, dimson_lag_t: D && D.se[k + 1] > 0 ? D.b[k + 1] / D.se[k + 1] : NaN,
    factors: codes.map((c, i) => ({ code: c, beta: R.b[i + 1], t: t[i + 1], factor_ann: 5200 * mF[i], contrib_ann: 5200 * R.b[i + 1] * mF[i] })),
    y, X, e: R.e, b: R.b };
}
function rolling(fund, rfAnn, codes, L, n, lo = 0, hi = fund.y.length) {
  const out = { end: [], beta: codes.map(() => []) };
  for (let i = lo + n; i <= hi; i++) {
    const r = regress(fund, rfAnn, codes, L, i - n, i); if (!r) continue;
    out.end.push(fund.w_end[i - 1]); r.factors.forEach((f, j) => out.beta[j].push(f.beta));
  }
  return out;
}
const FAttr = { inv, olsHac, regress, rolling };
root.FAttr = FAttr;
if (typeof document === 'undefined') return;

/* ═══════════════ نما ═══════════════ */
const A = root.SIM_FATTR;
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const f = (x, d = 1) => x == null || x !== x ? '—' : fmt(x, d);
const sg = (x, d = 1) => x == null || x !== x ? '—' : sgn(x, d);
const ltr = s => `<span dir="ltr" style="unicode-bidi:isolate">${s}</span>`;
const tip = t => ` data-tip="${esc(t)}"`;
const tcls = t => t == null || t !== t || Math.abs(t) < 2 ? '' : t > 0 ? 'up' : 'down';
const DOC = ' data-doc="7:7.9"';
const FCOL = { MKT: 'var(--tx-3)', SMB: 'var(--warn)', HML: 'var(--up)', MOM: 'var(--ch-2)', LV: 'var(--ch-3)', ILQ: 'var(--down)' };
const FTIP = {
  MKT: '«شاخص كل» بازده کل رسمی منهای نرخ بدون ریسک. β کمتر از ۱ یعنی صندوق در بالا و پایین بازار کمتر از شاخص حرکت می‌کند (نقد، سهام کم‌بتا، قیمت‌های کهنه).',
  SMB: 'کوچک منهای بزرگ: میانگین سه سبد زیر میانهٔ ارزش بازار منهای سه سبد بالای میانه (مرتب‌سازی ۲×۳ Fama–French، وزن ارزش بازاری). β مثبت = شرط روی کوچک‌ها.',
  HML: 'ارزشی منهای رشدی: سبدهای E/P بالای صدک ۷۰ منهای زیر صدک ۳۰ (درون کوچک و بزرگ). β مثبت = سهام ارزان نسبت به سود.',
  MOM: 'برنده منهای بازنده: مومنتوم ۱۲−۱ (بازده ۱۲ ماه بدون ماه آخر). β مثبت = دنبال‌کردن روند.',
  LV: 'کم‌نوسان منهای پرنوسان: نوسان روزانهٔ ۲۵۲ روزه. β مثبت = سهام آرام.',
  ILQ: 'نقدناپذیر منهای نقدشونده: نسبت آمیهود ۱۲۶ روزه (|بازده| ÷ ارزش معامله). در ایران با اندازه همبسته است (≈ ۰٫۴۸ هفتگی).',
};
const TILT = { SMB: ['کوچک‌ها', 'بزرگ‌ها'], HML: ['سهام ارزشی (E/P بالا)', 'سهام رشدی/گران (E/P پایین)'], MOM: ['برنده‌های ۱۲ ماه اخیر', 'بازنده‌های ۱۲ ماه اخیر'],
  LV: ['سهام کم‌نوسان', 'سهام پرنوسان'], ILQ: ['سهام کم‌معامله (نقدناپذیر)', 'سهام پرمعامله'] };
const CHTIP = { size: 'z لگاریتم ارزش بازار؛ منفی = کوچک‌تر از میانگین وزن‌بازاری بازار.', ep: 'z نسبت سود به قیمت (E/P)؛ مثبت = ارزان‌تر.', mom_12_1: 'z مومنتوم ۱۲−۱؛ مثبت = برنده‌تر.',
  vol_252: 'z نوسان ۲۵۲ روزه؛ مثبت = پرنوسان‌تر.', amihud: 'z نسبت آمیهود؛ مثبت = نقدناپذیرتر.' };
const st = { sym: null, rf: null, rfMode: 'bills', per: 'all', rep: null };
const rfArg = fund => st.rfMode === 'bills' && fund.rf_w ? fund.rf_w : st.rf;

function missing(m) { m.innerHTML = '<p style="padding:24px">دادهٔ تفکیک فاکتوری پیدا نشد. اجرا کنید: <code>python tools/fetch_active_funds.py</code> سپس <code>python tools/fund_attribution.py</code></p>'; }

function init() {
  const m = document.getElementById('v-fat'); m.dataset.ready = 1;
  if (!A || !A.funds || !Object.keys(A.funds).length) { missing(m); return; }
  st.sym = Object.keys(A.funds)[0]; st.rf = A.rf_ann; st.rfMode = A.rf_src === 'bills' ? 'bills' : 'const';
  m.innerHTML = `
  <section class="panel" style="--lg:var(--lg-a)">
    <div class="panel-head"><span class="lg-badge">1</span><span class="panel-title"${tip('بازده هفتگی صندوق (NAV) منهای نرخ بدون ریسک روی شش فاکتور رگرس می‌شود: بازار، اندازه، ارزش، مومنتوم، کم‌نوسان و نقدناپذیری. β می‌گوید صندوق در عمل روی کدام سبک شرط بسته است، چه در امیدنامه گفته باشد چه نه؛ آلفا بخشی است که هیچ فاکتوری توضیحش نمی‌دهد.')}${DOC}>صندوق در عمل روی چه چیزی شرط بسته است؟</span><span class="chip" id="fa-chip"></span></div>
    <div class="ctl">
      <label${tip('صندوق سهامی فعال. صندوق تازه با افزودن به ACTIVE در tools/fetch_active_funds.py اضافه می‌شود.')}>صندوق <select id="fa-sym">${Object.entries(A.funds).map(([k, v]) => `<option value="${esc(k)}">${esc(k)} · ${esc(v.style)}</option>`).join('')}</select></label>
      <label${tip('نرخ بدون ریسک. «اخزا»: بازده تا سررسید اسناد خزانه در آخرین روز پیش از هر هفته (صفحهٔ «داده و گزارش ← نرخ بدون ریسک»). «ثابت»: یک عدد سالانه برای همهٔ هفته‌ها. فقط آلفا و β بازار را جابه‌جا می‌کند؛ βهای سبک (بلند−کوتاه) به آن حساس نیستند.')}${DOC}>نرخ بدون ریسک <select id="fa-rfm"><option value="bills"${A.rf_src === 'bills' ? '' : ' disabled'}>اخزا (هفتگی)</option><option value="const">ثابت</option></select> <input type="number" id="fa-rf" step="1" min="0" max="80" style="width:64px;direction:ltr">٪</label>
      <span class="seg" id="fa-per"><button data-v="all"${tip('همهٔ هفته‌های عمر صندوق (پس از دو ماه تشکیل سبد).')}>کل عمر</button><button data-v="52"${tip('فقط ۵۲ هفتهٔ اخیر: سبک امروز صندوق.')}>۵۲ هفتهٔ اخیر</button></span>
    </div>
    <div class="kpis" id="fa-kpis"></div>
    <div class="lb-note" id="fa-read"></div>
    <div class="panel-body scroll"><table class="dt" id="fa-tab"></table></div>
    <div class="lineage" id="fa-lin"></div>
  </section>
  <section class="panel" style="--lg:var(--lg-b)">
    <div class="panel-head"><span class="lg-badge">2</span><span class="panel-title"${tip('سهم تجمعی هر فاکتور از بازده مازاد صندوق در طول زمان: β (کل بازه) × بازده هفتگی فاکتور، جمع‌شده. خط «آلفا + باقیمانده» هرچه فاکتورها توضیح نمی‌دهند.')}${DOC}>بازده مازاد از کجا آمد؟ (سهم تجمعی، واحد درصد)</span></div>
    <div class="panel-body"><div class="legend" id="fa-leg1"></div><svg class="chart" id="fa-ch1" dir="ltr" style="height:280px;flex:none"></svg></div>
  </section>
  <section class="panel" style="--lg:var(--lg-c)">
    <div class="panel-head"><span class="lg-badge">3</span><span class="panel-title"${tip('رگرسیون روی پنجرهٔ غلتان ۵۲ هفته‌ای: آیا سبک صندوق در زمان عوض شده است (style drift)؟')}${DOC}>رانش سبک: بتاهای غلتان ۵۲ هفته‌ای</span></div>
    <div class="panel-body" id="fa-rollbox"><div class="legend" id="fa-leg2"></div><svg class="chart" id="fa-ch2" dir="ltr" style="height:240px;flex:none"></svg></div>
  </section>
  <section class="panel" style="--lg:var(--lg-e)" id="fa-hold"></section>`;
  $('fa-rf').value = Math.round(st.rf * 100); $('fa-rfm').value = st.rfMode; $('fa-rf').disabled = st.rfMode === 'bills';
  $('fa-rfm').onchange = e => { st.rfMode = e.target.value; $('fa-rf').disabled = st.rfMode === 'bills'; render(); };
  $('fa-sym').onchange = e => { st.sym = e.target.value; st.rep = null; render(); };
  $('fa-rf').onchange = e => { const v = +e.target.value; if (isFinite(v)) { st.rf = v / 100; render(); } };
  $('fa-per').querySelectorAll('button').forEach(b => { b.onclick = () => { st.per = b.dataset.v; render(); }; });
  render();
}

function reading(r, fund, hold) {
  const F = r.factors, mk = F.find(x => x.code === 'MKT'), sig = F.filter(x => x.code !== 'MKT' && Math.abs(x.t) >= 2), weak = F.filter(x => x.code !== 'MKT' && Math.abs(x.t) < 2);
  const b = x => ltr(`β = ${f(x.beta, 2)}, t = ${f(x.t, 1)}`);
  const P = [];
  P.push(`بازار: β = ${ltr(f(mk.beta, 2))}${r.dimson_lag_t != null && Math.abs(r.dimson_lag_t) >= 2 ? `، ولی با تأخیر هم واکنش می‌دهد (بتای دیمسون ${ltr(f(r.dimson_beta, 2))})؛ قیمت‌های کهنهٔ سهام کوچک و صف` : `؛ بتای دیمسون ${ltr(f(r.dimson_beta, 2))}`}. ${mk.beta < 0.95 ? 'کمتر از ۱ یعنی بخشی از دارایی بیرون از سهام (نقد، اوراق) یا سهام کم‌بتاست.' : ''}`);
  if (sig.length) P.push(`شرط‌های معنادار: ${sig.map(x => `${x.beta > 0 ? TILT[x.code][0] : TILT[x.code][1]} (${b(x)})`).join('، ')}.`);
  if (weak.length) P.push(`بی‌اثر (|t| < ۲): ${weak.map(x => `«${A.factors.find(z => z.code === x.code).fa}»`).join('، ')}.`);
  const top = F.filter(x => x.code !== 'MKT').slice().sort((a, c) => Math.abs(c.contrib_ann) - Math.abs(a.contrib_ann))[0];
  if (top) P.push(`بزرگ‌ترین اثر سبکی روی بازده در این بازه از «${A.factors.find(z => z.code === top.code).fa}» بوده: ${ltr(sg(top.contrib_ann, 1))} واحد درصد در سال (فاکتور خودش ${ltr(sg(top.factor_ann, 1))}).`);
  P.push(Math.abs(r.alpha_t) >= 2 ? `آلفا ${ltr(sg(r.alpha_ann, 1) + '٪')} در سال و معنادار است (t = ${ltr(f(r.alpha_t, 2))}).` : `آلفا ${ltr(sg(r.alpha_ann, 1) + '٪')} در سال از صفر جدا نیست (t = ${ltr(f(r.alpha_t, 2))})؛ با ${r.weeks} هفته داده، آلفای کمتر از حدود ${ltr(f(2 * r.resid_vol_ann / Math.sqrt(r.weeks / 52), 0) + '٪')} قابل‌تشخیص نیست.`);
  if (hold && hold.reports.length) {
    const h = hold.reports[hold.reports.length - 1], e = h.expo.size;
    if (e && e.fund != null) P.push(`پرتفوی کدال (${esc(h.date)}) همین را تأیید ${e.fund < e.index - 0.3 ? 'می‌کند' : 'نمی‌کند'}: z اندازهٔ صندوق ${ltr(f(e.fund, 2))} در برابر ${ltr(f(e.index, 2))} «شاخص كل».`);
  }
  return `<b>خوانش:</b> ${P.join(' ')}`;
}

function render() {
  const fund = A.funds[st.sym], codes = A.factors.map(x => x.code), n = fund.y.length;
  const lo = st.per === '52' ? Math.max(0, n - 52) : 0;
  $('fa-per').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === st.per)));
  const r = regress(fund, rfArg(fund), codes, A.hac_lags, lo, n), r1 = regress(fund, rfArg(fund), ['MKT'], A.hac_lags, lo, n);
  if (!r) { $('fa-tab').innerHTML = '<tbody><tr><td class="mute">داده برای رگرسیون کافی نیست.</td></tr></tbody>'; return; }
  $('fa-chip').textContent = `${ChartKit.jstr(fund.w_end[r.idx[0]])} تا ${ChartKit.jstr(fund.w_end[r.idx[r.idx.length - 1]])} · ${r.weeks} هفته`;
  const K = [['بازده مازاد سالانه', sg(r.excess_ann, 1) + '٪', `نوسان ${f(r.vol_ann, 0)}٪`, 'میانگین بازده هفتگی صندوق منهای نرخ بدون ریسک × ۵۲ (حسابی، جمع‌پذیر با سهم‌های جدول).'],
    ['آلفای سالانه', sg(r.alpha_ann, 1) + '٪', 't = ' + f(r.alpha_t, 2), 'عرض از مبدأ × ۵۲: بازده‌ای که با داشتن همین شش سبد فاکتوری به دست نمی‌آمد. |t| ≥ ۲ یعنی از صفر جداست. شامل کارمزد صندوق (NAV خالص است).'],
    ['R²', f(r.r2, 2), `فقط بازار ${f(r1 ? r1.r2 : NaN, 2)}`, 'سهم نوسان هفتگی صندوق که فاکتورها توضیح می‌دهند؛ فاصله با «فقط بازار» = آنچه سبک (نه بازار) توضیح می‌دهد.'],
    ['بتای دیمسون', f(r.dimson_beta, 2), 'β بازار + β هفتهٔ قبل', 'اگر از β بازار بزرگ‌تر باشد صندوق با یک هفته تأخیر به بازار واکنش می‌دهد (قیمت‌های کهنه، صف، سهام کم‌معامله).'],
    ['ریسک فعال باقیمانده', f(r.resid_vol_ann, 1) + '٪', 'سالانه', 'انحراف معیار باقیماندهٔ رگرسیون × √۵۲: ریسکی که از انتخاب سهم (نه فاکتور) می‌آید.']];
  $('fa-kpis').innerHTML = K.map(([k, v, s, t]) => `<div class="kpi"${tip(t)}${DOC}><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`).join('');
  $('fa-read').innerHTML = reading(r, fund, fund.holdings);
  const tot = r.excess_ann, sh = c => tot ? ltr(f(100 * c / tot, 0) + '٪') : '—';
  const row = (name, t0, b, t, fr, c, cls) => `<tr class="${cls || ''}"><td${t0 ? tip(t0) : ''}>${name}</td><td class="n">${b == null ? '' : f(b, 2)}</td><td class="n ${tcls(t)}">${t == null ? '' : f(t, 2)}</td><td class="n">${fr == null ? '' : ltr(sg(fr, 1))}</td><td class="n">${ltr(sg(c, 1))}</td><td class="n">${sh(c)}</td></tr>`;
  $('fa-tab').innerHTML = `<thead><tr><th${tip('جزء بازده مازاد.')}>جزء</th><th class="n"${tip('بار فاکتور: بازده صندوق به‌ازای ۱ واحد بازده فاکتور.')}>β</th><th class="n"${tip(`آمار t نیوی‌وست با ${A.hac_lags} وقفه؛ رنگی یعنی |t| ≥ ۲.`)}>t</th><th class="n"${tip('میانگین بازده هفتگی فاکتور × ۵۲ (واحد درصد) در همین بازه.')}>بازده فاکتور</th><th class="n"${tip('β × بازده فاکتور: سهم این فاکتور از بازده مازاد سالانه (واحد درصد).')}>سهم</th><th class="n"${tip('سهم از بازده مازاد.')}>از کل</th></tr></thead><tbody>
    ${r.factors.map(x => row(`<span class="fam" style="background:${FCOL[x.code]}"></span>${esc(A.factors.find(z => z.code === x.code).fa)}`, FTIP[x.code], x.beta, x.t, x.factor_ann, x.contrib_ann)).join('')}
    ${row('آلفا (توضیح‌داده‌نشده)', 'عرض از مبدأ × ۵۲.', null, r.alpha_t, null, r.alpha_ann)}
    ${row('<b>بازده مازاد صندوق</b>', 'جمع ردیف‌های بالا = میانگین بازده هفتگی منهای rf × ۵۲.', null, null, null, r.excess_ann, 'tot')}</tbody>`;
  $('fa-lin').innerHTML = `<span><b${tip('منبع بازده صندوق.')}>صندوق</b> ${esc(fund.name)} · بازده روزانهٔ NAV (فیپیران)، مرکب هفتگی</span><span><b${tip('جهان و روش ساخت فاکتورها.')}>فاکتورها</b> مرتب‌سازی ۲×۳ وزن‌بازاری، ماهانه، روی واجدان بورس و فرابورس</span><span><b${tip('نرخ بدون ریسک کم‌شده از بازده صندوق و بازار در همین بازه.')}>rf</b> ${st.rfMode === 'bills' && fund.rf_w ? `اخزا هفتگی، میانگین ${f(100 * mean(fund.rf_w.slice(lo, n)), 1)}٪ (${f(100 * Math.min(...fund.rf_w.slice(lo, n)), 0)} تا ${f(100 * Math.max(...fund.rf_w.slice(lo, n)), 0)})` : `ثابت ${f(100 * st.rf, 0)}٪`}</span><span><b${tip('آخرین روز دادهٔ قیمت سهام که فاکتورها تا آن ساخته شده‌اند.')}>داده تا</b> ${esc(A.asof)}</span><span><b>بازسازی</b> <code>python tools/fund_attribution.py</code></span>`;
  drawContrib(fund, r, codes); drawRolling(fund, codes, lo, n); renderHold(fund);
}

function drawContrib(fund, r, codes) {
  const dates = r.idx.map(i => fund.w_end[i]), cum = a => { let s = 0; return a.map(v => (s += 100 * v)); };
  const ser = [{ v: cum(r.y), color: 'var(--tx-1)', w: 2, name: 'بازده مازاد صندوق', fmt: x => f(x, 1) }];
  codes.forEach((c, j) => ser.push({ v: cum(r.X.map(row => r.b[j + 1] * row[j])), color: FCOL[c], w: 1.3, name: A.factors[j].fa, fmt: x => f(x, 1) }));
  ser.push({ v: cum(r.y.map((y, t) => y - r.X[t].reduce((s, v, j) => s + r.b[j + 1] * v, 0))), color: 'var(--accent)', w: 1.3, dash: '4 3', name: 'آلفا + باقیمانده', fmt: x => f(x, 1) });
  $('fa-leg1').innerHTML = ser.map(s => `<span><i style="color:${s.color}"></i>${esc(s.name)}</span>`).join('');
  const cs = { i: null }, draw = () => ChartKit.paneChart($('fa-ch1'), dates, [{ frac: 1, zero: true, series: ser, fmt: x => fmt(x, 0) }], cs);
  ChartKit.attach($('fa-ch1'), cs, draw); draw();
}

function drawRolling(fund, codes, lo, n) {
  const R = rolling(fund, rfArg(fund), codes, A.hac_lags, A.roll, 0, n);
  if (R.end.length < 3) { $('fa-rollbox').innerHTML = `<p class="mute" style="padding:12px">برای پنجرهٔ ${A.roll} هفته‌ای دادهٔ کافی نیست.</p>`; return; }
  const ser = codes.map((c, j) => ({ v: R.beta[j], color: FCOL[c], w: c === 'MKT' ? 1 : 1.4, dash: c === 'MKT' ? '3 3' : null, name: A.factors[j].fa, fmt: x => f(x, 2) }));
  $('fa-leg2').innerHTML = ser.map(s => `<span><i style="color:${s.color}"></i>${esc(s.name)}</span>`).join('');
  const cs = { i: null }, draw = () => ChartKit.paneChart($('fa-ch2'), R.end, [{ frac: 1, zero: true, series: ser, fmt: x => fmt(x, 1) }], cs);
  ChartKit.attach($('fa-ch2'), cs, draw); draw();
}

function renderHold(fund) {
  const H = fund.holdings, host = $('fa-hold');
  const head = `<div class="panel-head"><span class="lg-badge">4</span><span class="panel-title"${tip('همان پرسش از راه موجودی: پرتفوی ماهانهٔ صندوق در کدال با امتیاز z هر سهم (استانداردشده روی جهان واجدان با میانگین وزن‌بازاری صفر) سنجیده می‌شود. نگاه بازده‌ای می‌گوید صندوق چطور حرکت کرده؛ این نگاه می‌گوید چه خریده است.')}${DOC}>از راه پرتفو: صندوق چه خریده است؟</span>`;
  if (!H || !H.reports.length) { host.innerHTML = head + `</div><p class="mute" style="padding:16px">پرتفوی کدال این صندوق هنوز تبدیل نشده است: <code>python tools/fetch_fund_portfolio.py --collect 24 --symbols "${esc(st.sym)}"</code> سپس <code>python tools/parse_fund_portfolio.py</code> و <code>python tools/fund_attribution.py</code></p>`; return; }
  if (!st.rep || !H.reports.some(x => x.date === st.rep)) st.rep = H.reports[H.reports.length - 1].date;
  const h = H.reports.find(x => x.date === st.rep);
  const zc = z => z == null ? '' : z > 0.25 ? 'up' : z < -0.25 ? 'down' : '';
  const secs = h.sectors.slice().sort((a, b) => Math.abs(b.f - b.b) - Math.abs(a.f - a.b)).slice(0, 12);
  host.innerHTML = head + `<label style="margin-inline-start:auto"${tip('تاریخ گزارش ماهانهٔ پرتفو (پایان ماه).')}>گزارش <select id="fa-rep">${H.reports.map(x => `<option${x.date === st.rep ? ' selected' : ''}>${x.date}</option>`).join('')}</select></label></div>
    <div class="kpis">${[['سهام از کل دارایی', f(h.equity_pct, 1) + '٪', 'جمع وزن سهام در گزارش کدال؛ بقیه نقد، سپرده، اوراق یا صندوق.'], ['تعداد نماد', f(h.n, 0), 'نمادهای سهام تطبیق‌یافته با پانل ما.'],
      ['فرابورس', f(h.fara_pct, 0) + '٪', 'سهم فرابورس از بخش سهام. «شاخص كل» فرابورس ندارد.'], ['ده سهم اول', f(h.top10_pct, 0) + '٪', 'تمرکز: سهم ده نماد بزرگ از بخش سهام.']]
      .map(([k, v, t]) => `<div class="kpi"${tip(t)}><div class="k">${k}</div><div class="v">${v}</div></div>`).join('')}</div>
    <div class="panel-body scroll" style="flex:none"><table class="dt"><thead><tr><th${tip('ویژگی سهم‌ها.')}>ویژگی (z)</th><th class="n"${tip('میانگین وزنی z بخش سهام صندوق.')}>صندوق</th><th class="n"${tip('میانگین وزنی z «شاخص كل» (ارزش بازاری بورس).')}>«شاخص كل»</th><th class="n"${tip('صندوق منهای شاخص.')}>فاصله</th><th class="n"${tip('سهمی از وزن سهام که این ویژگی برایش محاسبه‌پذیر بود (مثلاً E/P برای سهم بی‌سود اعلام‌شده نیست).')}>پوشش</th></tr></thead><tbody>
      ${H.chars.map(c => { const e = h.expo[c.code]; return `<tr><td${tip(CHTIP[c.code])}>${esc(c.fa)}</td><td class="n">${f(e.fund, 2)}</td><td class="n">${f(e.index, 2)}</td><td class="n ${zc(e.fund - e.index)}">${e.fund == null ? '—' : ltr(sg(e.fund - e.index, 2))}</td><td class="n">${f(100 * e.cover, 0)}٪</td></tr>`; }).join('')}</tbody></table></div>
    <div class="panel-body scroll" style="flex:none"><table class="dt"><thead><tr><th${tip('صنعت (۱۲ صنعت با بیشترین فاصله).')}>صنعت</th><th class="n"${tip('وزن در بخش سهام صندوق.')}>صندوق ٪</th><th class="n"${tip('وزن در «شاخص كل».')}>شاخص ٪</th><th class="n"${tip('بیش‌وزن (+) یا کم‌وزن (−).')}>فاصله</th></tr></thead><tbody>
      ${secs.map(s => `<tr><td>${esc(s.s)}</td><td class="n">${f(s.f, 1)}</td><td class="n">${f(s.b, 1)}</td><td class="n ${s.f - s.b > 0 ? 'up' : 'down'}">${ltr(sg(s.f - s.b, 1))}</td></tr>`).join('')}</tbody></table></div>
    <div class="panel-body scroll" style="flex:none"><table class="dt"><thead><tr><th>نماد</th><th>صنعت</th><th class="n"${tip('وزن در بخش سهام.')}>وزن ٪</th>${H.chars.map(c => `<th class="n"${tip(CHTIP[c.code])}>${esc(c.fa)}</th>`).join('')}</tr></thead><tbody>
      ${h.top.map(t => `<tr><td><a class="symlink" data-sym="${esc(t.s)}" href="#">${esc(t.s)}</a></td><td>${esc(t.sec)}</td><td class="n">${f(t.w, 1)}</td>${H.chars.map(c => `<td class="n ${zc(t.z[c.code])}">${f(t.z[c.code], 2)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  $('fa-rep').onchange = e => { st.rep = e.target.value; renderHold(fund); };
}

root.SIM_NEWVIEWS = Object.assign(root.SIM_NEWVIEWS || {}, { fat: { id: 'v-fat', init, redraw: () => { if (document.getElementById('v-fat').dataset.ready && A) render(); } } });
})(typeof window !== 'undefined' ? window : globalThis);
