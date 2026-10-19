/* همتا — نماهای دوم: Dividend Lab · Rebalance · Data QA · Reports · Symbol · Fund · Risk · Index Funds + روتر پنج‌بخشی
   داده: window.SIM_EXTRA (tools/build_ui_extra.py) و window.SIM_DATA. هیچ عدد ثابتی در این فایل نیست مگر متن توضیحی. */
(function () {
const X = window.SIM_EXTRA;
const VIEWS = { index: 'v-index', div: 'v-div', reb: 'v-reb', qa: 'v-qa', rep: 'v-rep', sym: 'v-sym', pf: 'v-pf', risk: 'v-risk', fnd: 'v-fnd' };
const JM = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
const inited = {}, redraws = {};
const jyear = new Intl.DateTimeFormat('fa-IR-u-ca-persian-nu-latn', { year: 'numeric' });
const cls = v => v == null ? '' : v >= 0 ? 'up' : 'down';
const chipTE = t => t == null ? '' : t < 1 ? 'ok' : t < 3 ? 'warn' : 'bad';

if (!X) {
  ['v-div', 'v-reb', 'v-qa', 'v-rep', 'v-pf', 'v-risk'].forEach(id => { $(id).innerHTML = '<p style="padding:24px">ui/data/extra.js پیدا نشد. اجرا کنید: <code>python tools/build_ui_extra.py</code></p>'; });
}

/* ── نمودار: موتور مشترک ui/chartkit.js (زوم، جابه‌جایی، هوور با برچسب روی محورها) ── */
const { paneChart, bars } = window.ChartKit;
const chartOn = (id, st, redraw, opts) => window.ChartKit.attach($(id), st, redraw, opts);

/* ══════════ Dividend Lab ══════════ */
const dv = { k: 'K', s: 'A', lag: 90, rb: 25, emp: false, i: null, cur: null };
function divSim(ds, tr, pr, lag, rb) {
  const mix = Array.isArray(lag) ? lag : [[lag, 1]];
  const n = tr.length, day = ds.map(d => Date.parse(d) / 864e5), due = new Float64Array(n + 1), nav = new Float64Array(n);
  const pays = mix.map(([L]) => { const pay = new Int32Array(n); let k = 0; for (let t = 0; t < n; t++) { if (k < t) k = t; while (k < n && day[k] < day[t] + L) k++; pay[t] = k; } return pay; });
  let V = 1, A = 0, B = 0;
  for (let t = 0; t < n; t++) {
    const dd = t ? day[t] - day[t - 1] : 0;
    if (rb != null && B > 0) V -= B * rb * dd / 365;
    V *= 1 + pr[t];
    const y = tr[t] - pr[t];
    if (y !== 0) { const amt = V * y / (1 + pr[t]); for (let a = 0; a < mix.length; a++) due[pays[a][t]] += amt * mix[a][1]; A += amt; if (rb != null) { V += amt; B += amt; } }
    const p = due[t]; if (p !== 0) { A -= p; if (rb != null) B -= p; else V += p; }
    nav[t] = V + A - B;
  }
  return nav;
}
function divCompute() {
  const S = X.divlab[dv.k], rb = dv.s === 'B' ? dv.rb / 100 : null;
  const nav = divSim(S.dates, S.tr, S.pr, dv.emp && S.empirical_mix ? S.empirical_mix : dv.lag, rb), n = nav.length;
  const trL = new Float64Array(n); let c = 1; for (let t = 0; t < n; t++) { c *= 1 + S.tr[t]; trL[t] = c; }
  const d = []; for (let t = 1; t < n; t++) d.push((nav[t] / nav[t - 1] - 1) - S.tr[t]);
  const mean = d.reduce((a, b) => a + b, 0) / d.length, sd = Math.sqrt(d.reduce((a, b) => a + (b - mean) ** 2, 0) / (d.length - 1));
  const ratio = nav[n - 1] / trL[n - 1], yrs = (Date.parse(S.dates[n - 1]) - Date.parse(S.dates[0])) / 864e5 / 365.25, gap = (Math.pow(ratio, 1 / yrs) - 1) * 100;
  dv.cur = { nav, trL, ratio, gap, te: sd * Math.sqrt(252) * 100, S };
}
function divDraw() {
  const c = dv.cur, S = c.S, svg = $('dv-chart');
  const nav = Array.from(c.nav).map(v => v * 100), trl = Array.from(c.trL).map(v => v * 100), gp = Array.from(c.nav).map((v, i) => (v / c.trL[i] - 1) * 100);
  paneChart(svg, S.dates, [
    { frac: .68, log: true, series: [{ v: trl, color: 'var(--ch-2)', w: 1.6, name: 'TR نظری', fmt: v => fmt(v, 2) }, { v: nav, color: 'var(--ch-1)', w: 1.1, name: 'NAV قابل‌اجرا', fmt: v => fmt(v, 2) }], fmt: v => fmt(v, 0) },
    { frac: .32, zero: true, series: [{ v: gp, color: 'var(--ch-3)', dash: true, name: 'شکاف', fmt: v => sgn(v, 2) + '%' }], fmt: v => fmt(v, 1) + '%' }], dv);
  $('dv-readout').innerHTML = dv.i == null ? '' : `<b>${S.dates[dv.i]}</b> · ${jd(S.dates[dv.i])} &nbsp; TR نظری <b>${fmt(trl[dv.i], 1)}</b> &nbsp; NAV <b>${fmt(nav[dv.i], 1)}</b> &nbsp; شکاف <b>${sgn(gp[dv.i], 2)}%</b>`;
}
function divRender() {
  divCompute(); const c = dv.cur, S = c.S;
  const PD = X.divlab.payment_data, hasEmp = !!S.empirical_mix, pm = dv.k === 'K' ? PD.k : PD.ew;
  $('dv-emp-w').hidden = !hasEmp; $('dv-emp').checked = dv.emp && hasEmp; $('dv-lag').disabled = dv.emp && hasEmp;
  $('dv-model-chip').textContent = dv.emp && hasEmp ? `مدل: توزیع واقعی تأخیر (${PD.with_ex} رویداد)` : 'مدل: تأخیر یکسان L';
  $('dv-lag-o').textContent = dv.emp && hasEmp ? `میانگین ${pm.mean}` : dv.lag; $('dv-rb-o').textContent = dv.rb;
  $('dv-rb-w').style.display = dv.s === 'B' ? '' : 'none';
  document.querySelectorAll('#dv-idx button').forEach(b => b.setAttribute('aria-pressed', b.dataset.k === dv.k));
  document.querySelectorAll('#dv-str button').forEach(b => b.setAttribute('aria-pressed', b.dataset.s === dv.s));
  $('dv-title').textContent = (dv.k === 'K' ? 'شاخص كل' : 'كل (هم وزن)') + ' · همتای سرمایه‌پذیر با تأخیر پرداخت سود';
  $('dv-kpis').innerHTML = [['تفاوت ردیابی سالانه', sgn(c.gap, 2) + '%', cls(c.gap)], ['نسبت سطح نهایی NAV / TR', fmt(c.ratio, 3), c.ratio >= 1 ? 'up' : 'down'],
    ['خطای ردیابی (TE سالانه)', fmt(c.te, 2) + '%', ''], ['سود نقدی ضمنی سالانه', fmt(S.y_ann_pct, 1) + '%', ''], ['بازه', jyr(S.from) + '→' + jyr(S.to), '']]
    .map(([k, v, cl]) => `<div class="kpi"><div class="k">${k}</div><div class="v ${cl}">${v}</div></div>`).join('');
  $('dv-lineage').innerHTML = `<span><b>مدل</b> NAV = ارزش پرتفوی + مطالبات سود − وام؛ سود روز استحقاق = TR − PR رسمی، پرداخت L روز بعد</span><span><b>L = ۰</b> دقیقاً TR رسمی (تأییدکنندهٔ مدل)</span><span><b>فرض</b> ${dv.emp && S.empirical_mix ? 'هر سود نقدی با تأخیر یکی از رویدادهای واقعی (کدال و فارابی) پرداخت می‌شود؛ وزن هر رویداد = سهمش از جریان سود همین شاخص' : 'تأخیر یکسان L برای همهٔ شرکت‌ها'}؛ نرخ وام ثابت در کل دوره</span><span><b>روش‌شناسی</b> فصل ۰۳ §۳٫۵</span>`;
  // سناریوهای ثابت
  const near = S.scenarios.reduce((b, r) => Math.abs(r.lag - dv.lag) < Math.abs(b.lag - dv.lag) ? r : b);
  $('dv-scen').innerHTML = th([['L (روز)', 'n'], ['A: بدون وام — فاصله %/سال', 'n'], ['A: TE %', 'n'], ['B ۲۵٪ — فاصله', 'n'], ['B ۲۵٪ — TE', 'n'], ['B ۳۵٪ — فاصله', 'n'], ['B ۳۵٪ — TE', 'n']]) +
    '<tbody>' + (S.empirical ? (e => `<tr ${dv.emp ? 'aria-selected="true"' : ''}><td class="n">توزیع واقعی (${PD.with_ex} رویداد؛ میانگین وزنی ${pm.mean}، میانه ${pm.median})</td><td class="n ${cls(e.A.gap_pct_yr)}">${sgn(e.A.gap_pct_yr)}</td><td class="n">${fmt(e.A.te_pct)}</td><td class="n ${cls(e.B25.gap_pct_yr)}">${sgn(e.B25.gap_pct_yr)}</td><td class="n">${fmt(e.B25.te_pct, 3)}</td><td class="n ${cls(e.B35.gap_pct_yr)}">${sgn(e.B35.gap_pct_yr)}</td><td class="n">${fmt(e.B35.te_pct, 3)}</td></tr>`)(S.empirical) : '') + S.scenarios.map(r => `<tr ${r === near && !dv.emp ? 'aria-selected="true"' : ''}><td class="n">${r.lag}</td><td class="n ${cls(r.A.gap_pct_yr)}">${sgn(r.A.gap_pct_yr)}</td><td class="n">${fmt(r.A.te_pct)}</td><td class="n ${cls(r.B25.gap_pct_yr)}">${sgn(r.B25.gap_pct_yr)}</td><td class="n">${fmt(r.B25.te_pct, 3)}</td><td class="n ${cls(r.B35.gap_pct_yr)}">${sgn(r.B35.gap_pct_yr)}</td><td class="n">${fmt(r.B35.te_pct, 3)}</td></tr>`).join('') + '</tbody>';
  $('dv-lin-b').innerHTML = `<span>${dv.k === 'K' ? 'شاخص كل' : 'هم‌وزن'} · نسبت به TR نظری رسمی</span><span><b>خوانش</b> وام TE را تقریباً صفر می‌کند چون هزینه‌اش قطعی است (نرخ × سود × L/۳۶۵)؛ میانگین بهتر فقط اگر نرخ وام < بازده بازار</span>`;
  bars($('dv-bars'), JM.map(m => m.slice(0, 5)), S.month_share, v => fmt(v, 0), (i, v) => v === Math.max(...S.month_share));
  $('dv-lin-c').innerHTML = `<span><b>خوانش</b> سود در ${JM[S.month_share.indexOf(Math.max(...S.month_share))]} متمرکز است؛ تأخیر در همین ماه‌ها بیشترین مبلغ را معلق می‌کند</span><span><b>منبع</b> y = r<sub>TR</sub> − r<sub>PR</sub> رسمی</span>`;
  divDraw();
}
function divPayPanel() {
  const p = X.divlab.payment_data, has = p.with_ex > 0;
  $('dv-pay-chip').textContent = has ? p.with_ex + ' رویداد با تاریخ پرداخت · ' + p.agm_rows + ' مجمع' : p.rows + ' زمان‌بندی · ' + p.agm_rows + ' مجمع';
  const hist = has ? `<table class="dt"><thead><tr><th>تأخیر از استحقاق (روز)</th>${p.hist.map(h => `<th class="n">${h[0]}</th>`).join('')}</tr></thead><tbody><tr><td>رویداد</td>${p.hist.map(h => `<td class="n">${h[1]}</td>`).join('')}</tr><tr><td>سهم از جریان سود «كل» ٪</td>${p.hist.map(h => `<td class="n">${fmt(h[2], 0)}</td>`).join('')}</tr></tbody></table>` : '';
  const yr = has ? `<table class="dt"><thead><tr><th>سال مجمع</th>${Object.keys(p.by_year).map(y => `<th class="n">${y}</th>`).join('')}</tr></thead><tbody><tr><td>میانهٔ تأخیر (روز)</td>${Object.values(p.by_year).map(o => `<td class="n">${o.median}</td>`).join('')}</tr><tr><td>رویداد</td>${Object.values(p.by_year).map(o => `<td class="n">${o.n}</td>`).join('')}</tr></tbody></table>` : '';
  const cv = has && p.coverage.length ? `<table class="dt"><thead><tr><th>سال شمسی استحقاق</th>${p.coverage.filter(c => c.events).map(c => `<th class="n">${c.year}</th>`).join('')}</tr></thead><tbody><tr><td>پوشش جریان سود «كل» ٪</td>${p.coverage.filter(c => c.events).map(c => `<td class="n">${fmt(c.cov_K * 100, 0)}</td>`).join('')}</tr><tr><td>پوشش جریان سود هم‌وزن ٪</td>${p.coverage.filter(c => c.events).map(c => `<td class="n">${fmt(c.cov_EW * 100, 0)}</td>`).join('')}</tr></tbody></table>` : '';
  $('dv-pay').innerHTML = `<div class="note">تاریخ مجمع و سود هر سهم از ${p.agm_rows} مصوبهٔ مجمع کدال خوانده شده و با تعدیل قیمت TSETMC تطبیق کامل دارد.
    ${has ? `تاریخ پرداخت سجامی از دو منبع آمده است: نامه‌های «زمان‌بندی پرداخت سود» کدال (ن-۱۳؛ فقط ${p.letters_text} از ${p.letters} پیوست متن‌دار است) و جدول‌های کارگزاری فارابی که همان نامه‌ها را برای همهٔ نمادها رونویسی می‌کند. ${p.events} رویداد (${p.symbols} نماد) داریم که ${p.with_ex} تای آن به روز استحقاق در پانل وصل شد.
    <b>تأخیر از استحقاق: میانهٔ همهٔ رویدادها ${p.median} روز (چارک‌ها ${p.q25}–${p.q75})؛ ولی وزن‌شده با جریان سود، میانگین «شاخص كل» ${p.k.mean} روز و هم‌وزن ${p.ew.mean} روز</b> — شرکت‌های بزرگ (بانک‌ها، فولاد، پالایشی‌ها) زودتر پرداخت می‌کنند؛ مدل از این توزیع وزنی استفاده می‌کند («توزیع واقعی تأخیر» را روشن کنید).` : 'تاریخ پرداخت هنوز در داده نیست؛ مدل تأخیر یکسان L را به کار می‌برد.'}
    فارابی منبع ثانویه (رونوشت کدال) است؛ در ۱۰ رویداد مشترک ۶ تا کاملاً یکی، ۲ تا ≤ ۷ روز اختلاف (اصلاحیه) و ۲ تا خطای پارسر کدال (نامهٔ مطالبات سنواتی) بود [راستی‌آزمایی نشده]. پوشش سال‌های قدیمی‌تر کم است (جدول پایین).</div>
  ${hist}${yr}${cv}
  <div class="prose"><b>به‌روزرسانی:</b><div class="cmdline">python tools/fetch_farabi_dividends.py\npython tools/parse_farabi_dividends.py\npython tools/merge_dividend_payments.py\npython tools/build_ui_extra.py\npython tools/build_ui_funds.py</div>
    خروجی: <code>data/corporate_actions/dividend_payment_events.csv</code>.</div>`;
}
function initDiv() {
  document.querySelectorAll('#dv-idx button').forEach(b => b.onclick = () => { dv.k = b.dataset.k; divRender(); });
  document.querySelectorAll('#dv-str button').forEach(b => b.onclick = () => { dv.s = b.dataset.s; divRender(); });
  $('dv-lag').oninput = e => { dv.lag = +e.target.value; divRender(); };
  $('dv-emp').onchange = e => { dv.emp = e.target.checked; divRender(); };
  $('dv-rb').oninput = e => { dv.rb = +e.target.value; divRender(); };
  chartOn('dv-chart', dv, divDraw);
  $('dv-csv').onclick = () => { const c = dv.cur; download(`div_lab_${dv.k}_${dv.emp ? 'emp' : 'L' + dv.lag}${dv.s === 'B' ? '_rb' + dv.rb : ''}.csv`, [['date', 'tr_theory', 'nav', 'gap_pct'], ...c.S.dates.map((d, i) => [d, (c.trL[i] * 100).toFixed(3), (c.nav[i] * 100).toFixed(3), ((c.nav[i] / c.trL[i] - 1) * 100).toFixed(3)])]); };
  $('dv-csv-b').onclick = () => download(`div_scenarios_${dv.k}.csv`, [['lag', 'A_gap', 'A_te', 'B25_gap', 'B25_te', 'B35_gap', 'B35_te'], ...(X.divlab[dv.k].empirical ? [['empirical', ...['A', 'B25', 'B35'].flatMap(k => [X.divlab[dv.k].empirical[k].gap_pct_yr, X.divlab[dv.k].empirical[k].te_pct])]] : []), ...X.divlab[dv.k].scenarios.map(r => [r.lag, r.A.gap_pct_yr, r.A.te_pct, r.B25.gap_pct_yr, r.B25.te_pct, r.B35.gap_pct_yr, r.B35.te_pct])]);
  divPayPanel(); redraws.div = divDraw; divRender();
}

/* ── آمار ماهانهٔ سبدهای پنجکی (برای خلاصهٔ Reports؛ نمای Factor Lab در بازچینی ۲۰۲۶-۱۰-۱۸ حذف شد) ── */
function mstats(x) {
  const n = x.length, mu = x.reduce((a, b) => a + b, 0) / n, e = x.map(v => v - mu);
  const sd = Math.sqrt(e.reduce((a, b) => a + b * b, 0) / (n - 1));
  let v = e.reduce((a, b) => a + b * b, 0) / n;                      // نیوی‌وست، ۳ وقفه
  for (let l = 1; l <= 3; l++) { let g = 0; for (let t = l; t < n; t++) g += e[t] * e[t - l]; v += 2 * (1 - l / 4) * g / n; }
  let c = 1, pk = 1, mdd = 0; x.forEach(r => { c *= 1 + r; pk = Math.max(pk, c); mdd = Math.min(mdd, c / pk - 1); });
  return { mu, sd, ann: (Math.pow(c, 12 / n) - 1) * 100, vol: sd * Math.sqrt(12) * 100, t: mu / Math.sqrt(v / n), ir: mu / sd * Math.sqrt(12), hit: x.filter(r => r > 0).length / n * 100, mdd: mdd * 100 };
}
function facNet(F, bp = 100) {
  const M = F.monthly, c = bp / 1e4, Q = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'ALL'], net = {}, to = {};
  Q.forEach(q => { net[q] = M[q].map((g, i) => g / 100 - (M.to[q][i] || 0) / 100 * c); to[q] = M.to[q].reduce((a, b) => a + (b || 0), 0); });
  const yrs = (Date.parse(M.end[M.end.length - 1]) - Date.parse(M.end[0])) / 864e5 / 365.25 + 1 / 12;
  return { net, yrs, toAnn: Object.fromEntries(Q.map(q => [q, to[q] / yrs])), ex: net.Q5.map((v, i) => v - net.ALL[i]), ls: net.Q5.map((v, i) => v - net.Q1[i]) };
}

/* ══════════ Rebalance ══════════ */
function rebRender() {
  const R = X.rebalance, cost = +$('rb-cost').value || 0, nm = { 'jalali-month': 'ماهانه (شمسی)', 'jalali-quarter': 'فصلی (شمسی)', 'jalali-halfyear': 'شش‌ماهه', 'jalali-year': 'سالانه' };
  const best = R.policies.reduce((b, p) => p.te < b.te ? p : b);
  $('rb-pol').innerHTML = th([['سیاست'], ['ریبالانس', 'n'], ['گردش هر بار %', 'n'], ['گردش سالانه %', 'n'], ['TE در برابر رسمی %', 'n'], ['همبستگی', 'n'], ['نسبت سطح', 'n'], ['هزینه bp/سال', 'n']]) + '<tbody>' + R.policies.map(p => `<tr ${p === best ? 'aria-selected="true"' : ''}><td>${nm[p.policy]}${p === best ? ' <span class="chip info">کمترین TE</span>' : ''}</td><td class="n">${p.n_rebal}</td><td class="n">${fmt(p.avg_turn_pct, 1)}</td><td class="n">${fmt(p.annual_turn_pct, 1)}</td><td class="n">${fmt(p.te)}</td><td class="n">${fmt(p.corr, 4)}</td><td class="n">${fmt(p.cum_ratio, 3)}</td><td class="n">${fmt(p.annual_turn_pct * cost / 100, 0)}</td></tr>`).join('') + '</tbody>';
  $('rb-lin-a').innerHTML = `<span><b>هدف</b> «كل (هم وزن)» TR رسمی</span><span><b>گردش</b> یک‌طرفه = ½ Σ|وزن هدف − وزن رانش‌یافته|</span><span><b>هزینه</b> گردش سالانه × هزینهٔ رفت‌وبرگشت (ورودی بالا)</span><span><b>روش</b> فصل ۰۳ §۳٫۴ · فصل ۰۶</span>`;
}
function initReb() {
  const R = X.rebalance;
  $('rb-cost').oninput = rebRender; rebRender();
  $('rb-last').innerHTML = th([['تاریخ'], ['نماد', 'n'], ['گردش %', 'n'], ['ورود', 'n'], ['خروج', 'n']]) + '<tbody>' + R.last.map(r => `<tr><td class="num" title="${jd(r.date)}">${r.date}</td><td class="n">${r.n}</td><td class="n">${fmt(r.turn_pct, 1)}</td><td class="n up">${r.in}</td><td class="n down">${r.out}</td></tr>`).join('') + '</tbody>';
  const cp = R.cap;
  $('rb-cap').innerHTML = th([['سیاست'], ['ریبالانس', 'n'], ['گردش هر بار %', 'n'], ['گردش سالانه %', 'n']]) + '<tbody>' + [['jalali-month', 'ماهانه'], ['jalali-quarter', 'فصلی']].map(([k, l]) => `<tr><td>${l}</td><td class="n">${cp[k].n}</td><td class="n">${fmt(cp[k].avg_turn_pct, 1)}</td><td class="n">${fmt(cp[k].annual_turn_pct, 1)}</td></tr>`).join('') + '</tbody>';
  $('rb-lin-c').innerHTML = `<span><b>خوانش</b> ارزش‌وزن بدون ریبالانس تقریباً بدون گردش است؛ این گردش فقط از ورود/خروج نماد، افزایش سرمایه و تعدیل سهام می‌آید</span>`;
  const b = R.policies.reduce((m, p) => p.te < m.te ? p : m), bq = R.policies.find(p => p.policy === 'jalali-quarter');
  $('rb-read').innerHTML = `<b>ریبالانس فصلی شمسی</b> بهترین مبادله بین ردیابی و گردش است: TE ${fmt(bq.te)}٪ با گردش سالانهٔ ${fmt(bq.annual_turn_pct, 0)}٪. ماهانه گردش را ${fmt(R.policies[0].annual_turn_pct / bq.annual_turn_pct, 1)} برابر می‌کند ولی TE بهتر نمی‌شود، چون شاخص رسمی هم‌وزن خودش فصلی ریبالانس می‌کند (فصل ۰۳). 
  <br><b>ارزش‌وزن:</b> ریبالانس ماهانه ≈ ${fmt(cp['jalali-month'].annual_turn_pct, 0)}٪ در سال و فصلی ≈ ${fmt(cp['jalali-quarter'].annual_turn_pct, 0)}٪؛ تقریباً ناچیز در برابر هم‌وزن.
  <br><b>ملاحظات اجرا:</b> گردش بالا در ایران یعنی صف خرید/فروش و سقف نوسان؛ برنامهٔ اجرا (چند روز) و اثر بازار هنوز مدل نشده (فصل ۰۶).`;
  $('rb-csv').onclick = () => download('rebalance_policies.csv', [['policy', 'n', 'avg_turn_pct', 'annual_turn_pct', 'te', 'corr', 'cum_ratio'], ...R.policies.map(p => [p.policy, p.n_rebal, p.avg_turn_pct, p.annual_turn_pct, p.te, p.corr, p.cum_ratio])]);
}

/* ══════════ Data QA ══════════ */
function initQA() {
  const Q = X.qa, s = Q.sector_summary;
  $('qa-chip').textContent = `${s.comparable} صنعت · همبستگی ≥ ۰٫۹۹: ${s.n_corr99} · میانهٔ TE ${fmt(s.median_te)}٪`; $('qa-chip').className = 'chip ok';
  const rows = Q.sectors.filter(r => r.te != null).sort((a, b) => Math.min(b.te, b.te_all ?? 1e9) - Math.min(a.te, a.te_all ?? 1e9));
  $('qa-sec').innerHTML = th([['کد'], ['صنعت'], ['عضو رسمی', 'n'], ['بدون قیمت', 'n'], ['همبستگی', 'n'], ['TE اعضای فعلی %', 'n'], ['نماد صنعت', 'n'], ['همبستگی', 'n'], ['TE با حذف‌شده‌ها %', 'n'], ['نسبت سطح', 'n']]) +
    '<tbody>' + rows.map(r => `<tr><td class="num">${r.sector}</td><td>${r.name}</td><td class="n">${r.n_last}</td><td class="n ${r.n_miss ? 'down' : ''}">${r.n_miss}</td><td class="n">${fmt(r.corr, 4)}</td><td class="n"><span class="chip ${chipTE(r.te)}">${fmt(r.te)}</span></td><td class="n">${r.n_all}</td><td class="n">${r.corr_all == null ? '—' : fmt(r.corr_all, 4)}</td><td class="n"><span class="chip ${chipTE(r.te_all)}">${r.te_all == null ? '—' : fmt(r.te_all)}</span></td><td class="n">${fmt(r.cum, 3)}</td></tr>`).join('') + '</tbody>';
  $('qa-lin-a').innerHTML = `<span><b>ستون ۱</b> فقط اعضای فعلی شاخص رسمی</span><span><b>ستون ۲</b> همهٔ سهام بورسی صنعت (با حذف‌شده‌ها) به‌علاوهٔ تاریخچهٔ عوض‌شدن صنعت (<code>fit_sector_history.py</code>)</span><span><b>رنگ</b> سبز &lt; ۱٪ · زرد &lt; ۳٪ · قرمز ≥ ۳٪</span><span><b>روش</b> فصل ۰۳ §۳٫۴</span>`;
  $('qa-gl').innerHTML = th([['سری'], ['مورد', 'n'], ['نوع'], ['اولین'], ['آخرین']]) + '<tbody>' + Q.glitches.map(g => `<tr><td>${g.name}</td><td class="n">${g.n}</td><td>${Object.entries(g.kinds).map(([k, v]) => `${k === 'glitch' ? 'پرش تک‌روزه' : k === 'rescale' ? 'تغییر مقیاس' : 'تیغه'} ${v}`).join(' · ')}</td><td class="num">${g.first}</td><td class="num">${g.last}</td></tr>`).join('') + '</tbody>';
  $('qa-lin-b').innerHTML = `<span><b>قاعده</b> نسبت سطح ≈ ۰٫۱ یا ۱۰ ← حذف جفت یا نرمال‌سازی مقیاس؛ جهش > ۷٪ که فردا برمی‌گردد ← تیغه</span><span><b>مورد</b> «شاخص كل» و دو هم‌وزن بدون هیچ مورد</span><span><b>TEDPIX</b> داده معیوب و کنار گذاشته شده</span>`;
  const u = Q.universe, rl = Q.rules;
  $('qa-kpis').innerHTML = [['اعضای «شاخص كل»', u.k_members], ['با فایل قیمت', u.k_with_prices], ['نمادهای extras', u.extras], ['نماد در بازده', u.stocks_bourse_in_returns], ['ردیف قاعدهٔ ۸', rl.rule8]].map(([k, v]) => `<div class="kpi"><div class="k">${k}</div><div class="v">${fmt(v, 0)}</div></div>`).join('');
  const s34 = Q.sectors.find(r => String(r.sector).replace(/^0+/, '') === '34'), covRows = (X.divlab.payment_data.coverage || []).filter(c => c.events), covLast = covRows[covRows.length - 1];   // اعداد از داده، نه ثابت در متن
  $('qa-gaps').innerHTML = `<b>باز و شناخته‌شده</b><ul>
  <li><b>صنعت ۳۴ خودرو:</b> TE ${s34 && s34.te != null ? fmt(Math.min(s34.te, s34.te_all ?? s34.te)) + '٪ (همبستگی ' + fmt(Math.max(s34.corr || 0, s34.corr_all || 0), 3) + ')' : '—'}؛ فرضیهٔ زمان‌بندی/سهام شناور/توقف/فرابورس رد شد؛ خطا پراکنده است.</li>
  <li><b>تاریخ پرداخت سود:</b> ${X.divlab.payment_data.with_ex || 0} رویداد (${X.divlab.payment_data.symbols || 0} نماد) تاریخ پرداخت سجامی دارند (کدال ن-۱۳ و رونوشت کارگزاری فارابی)؛ ${covLast ? `پوشش جریان سود «كل» در ${covLast.year} حدود ${fmt(covLast.cov_K * 100, 0)}٪ و در سال‌های قدیمی‌تر کمتر است` : 'جدول پوشش هنوز ساخته نشده'}؛ بقیه با توزیع تجربی وزنی مدل می‌شوند.</li>
  <li><b>هم‌وزن TR رسمی:</b> نسبت سطح بازسازی به رسمی ${fmt(D.stats.EW.all.cum_ratio, 3)}؛ تفاوت از تفکیک سود و افزایش سرمایه در رویدادهای ترکیبی است.</li>
  <li><b>سهام کاملاً حذف‌شده:</b> فقط آن‌هایی که با جست‌وجوی نام صنعت پیدا شده‌اند (${fmt(u.extras, 0)} نماد extras)؛ جهان کامل نیست.</li>
  <li><b>۴ صنعت بدون عضو فعلی (۳۳، ۳۵، ۳۶، ۴۵)</b> و ۲۶ با کمتر از ۲۰۰ روز هم‌پوشانی: قابل مقایسه نیستند.</li></ul>`;
  $('qa-csv').onclick = () => download('sector_qa.csv', [['sector', 'name', 'n_official', 'n_missing', 'corr', 'te_pct', 'n_all', 'corr_all', 'te_all_pct', 'cum_ratio'], ...rows.map(r => [r.sector, r.name, r.n_last, r.n_miss, r.corr, r.te, r.n_all, r.corr_all, r.te_all, r.cum])]);
}

/* ══════════ Reports ══════════ */
function initRep() {
  const st = D.stats, F = X.factor, dvK = X.divlab.K.scenarios.find(r => r.lag === 90), dvE = X.divlab.EW.scenarios.find(r => r.lag === 90), Q = X.qa.sector_summary;
  const rows = [
    ['«شاخص كل» ارزش‌وزن TR', `همبستگی ${fmt(st.K.all.corr, 4)} · TE ${fmt(st.K.all.te)}٪ · MAD ${fmt(st.K.all.mad_bp, 1)}bp · نسبت سطح ${fmt(st.K.all.cum_ratio, 3)}`, 'فصل ۳ §۳٫۴'],
    ['«كل (هم وزن)» TR فصلی شمسی', `همبستگی ${fmt(st.EW.all.corr, 4)} · TE ${fmt(st.EW.all.te)}٪ · نسبت سطح ${fmt(st.EW.all.cum_ratio, 3)}`, 'فصل ۳ §۳٫۴'],
    ['شاخص‌های صنعت', `${Q.comparable} قابل مقایسه · ${Q.n_corr99} با همبستگی ≥ ۰٫۹۹ · میانهٔ TE ${fmt(Q.median_te)}٪`, 'فصل ۳ §۳٫۴'],
    ['هزینهٔ تأخیر سود ۹۰ روزه (K / EW)', `${sgn(dvK.A.gap_pct_yr)}٪ / ${sgn(dvE.A.gap_pct_yr)}٪ در سال (بدون وام)`, 'فصل ۳ §۳٫۵'],
    ...(X.divlab.K.empirical ? [['هزینهٔ تأخیر سود با توزیع واقعی (K / EW)', `${sgn(X.divlab.K.empirical.A.gap_pct_yr)}٪ / ${sgn(X.divlab.EW.empirical.A.gap_pct_yr)}٪ در سال (بدون وام؛ ${X.divlab.payment_data.with_ex} رویداد، میانگین وزنی ${X.divlab.payment_data.k.mean} / ${X.divlab.payment_data.ew.mean} روز)`, 'فصل ۳ §۳٫۵']] : []),
    ...[['مومنتوم ۱۲−۱ (بورس+فرابورس)', X.factor], ['کم‌نوسان ۲۵۲ روزه (بورس+فرابورس)', X.factor_lowvol], ...(X.factor_quality ? [['کیفیت (رهاورد؛ بورس+فرابورس)', X.factor_quality]] : [])].map(([n, G]) => { const N = facNet(G, 100), s = mstats(N.ex), a = mstats(N.net.Q5).ann - mstats(N.net.ALL).ann;
      return [n + ' (خالص ۱۰۰ bp)', `پنجک ۵ نسبت به همه ${sgn(a, 1)}٪ در سال · t نیوی‌وست ${fmt(s.t, 2)} · ${Math.abs(s.t) >= 1.96 ? 'معنادار' : 'غیرمعنادار'} در سطح ۵٪`, 'فصل ۵']; })];
  $('rp-sum').innerHTML = th([['نتیجه'], ['مقدار'], ['مرجع']]) + '<tbody>' + rows.map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td><td class="mute">${r[2]}</td></tr>`).join('') + '</tbody>';
  $('rp-text').innerHTML = `<b>وضعیت.</b> داده تا <span class="num">${D.meta.asof}</span>؛ ${fmt(D.meta.n_price_rows, 0)} ردیف قیمت. مرجع‌ها: «شاخص كل» و «كل (هم وزن)» رسمی. همتای سرمایه‌پذیر با بازتولید کامل و بدون سقف سرمایه/وزن؛ تنها شکاف ساختاری، تأخیر پرداخت سود است و با تأخیر یکسان L مدل می‌شود. فاکتورها با بک‌تست ماهانهٔ خالص هزینه و آزمون نیوی‌وست سنجیده می‌شوند؛ بازده‌ها با سال تقویمی سالانه شده‌اند. «چاپ» ← PDF.`;
  $('rp-lin-a').innerHTML = `<span><b>ساخت</b> <span class="num">${X.built}</span></span><span><b>داده</b> <span class="num">${D.meta.built}</span></span><span><b>قاعدهٔ سند</b> هر تغییر روش‌شناسی ← فصل + CHANGELOG (<code>CLAUDE.md</code>)</span>`;
  const log = X.reports.changelog; $('rp-chip').textContent = log.length + ' ردیف';
  $('rp-log').innerHTML = th([['تاریخ'], ['تغییر'], ['فصل‌ها']]) + '<tbody>' + log.slice().reverse().map(r => `<tr><td class="num">${r.date}</td><td title="${r.text.replace(/"/g, '&quot;')}" style="white-space:normal;min-width:260px">${r.title}</td><td class="mute" style="white-space:normal">${r.chapters}</td></tr>`).join('') + '</tbody>';
  $('rp-docs').innerHTML = th([['فایل'], ['عنوان'], ['KB', 'n']]) + '<tbody>' + X.reports.docs.map(d => `<tr><td class="num">${d.file}</td><td>${d.title}</td><td class="n">${d.kb}</td></tr>`).join('') + '</tbody>';
  $('rp-tools').innerHTML = th([['ابزار'], ['کار']]) + '<tbody>' + X.reports.tools.map(t => `<tr><td class="num">${t.file}</td><td style="white-space:normal">${t.doc}</td></tr>`).join('') + '</tbody>';
  $('rp-print').onclick = () => window.print();
  $('rp-json').onclick = () => download('sim_report_summary.csv', [['item', 'value', 'ref'], ...rows]);
  $('rp-csv').onclick = () => download('changelog.csv', [['date', 'title', 'chapters'], ...log.map(r => [r.date, r.title, r.chapters])]);
}


/* ══════════ Symbol ══════════ */
const sy = { s: null, ser: 'tr', i: null };
function loadSymbols(cb) {
  if (window.SIM_SYMBOLS) return cb();
  const sc = document.createElement('script'); sc.src = 'data/symbols.js';
  sc.onload = cb; sc.onerror = () => { $('sy-hint').textContent = 'ui/data/symbols.js پیدا نشد: python tools/build_ui_symbols.py'; };
  document.head.appendChild(sc);
}
window.openSym = function (s) { location.hash = '#sym'; show('sym'); loadSymbols(() => setSym(s)); };
function initSym() {
  $('sy-hint').textContent = 'در حال بارگذاری فهرست نمادها…';
  loadSymbols(() => {
    const S = window.SIM_SYMBOLS;
    $('sy-list').innerHTML = Object.keys(S.symbols).sort().map(k => `<option value="${k}">${S.symbols[k].name}</option>`).join('');
    $('sy-hint').textContent = `${S.n} نماد · داده تا ${S.asof} · یا روی نماد در جدول‌های دیگر کلیک کنید`;
    $('sy-q').onchange = e => setSym(e.target.value.trim());
    document.querySelectorAll('#sy-ser button').forEach(b => b.onclick = () => { sy.ser = b.dataset.s; drawSym(); });
    chartOn('sy-chart', sy, () => drawSym());
    $('sy-csv').onclick = () => { const d = S.symbols[sy.s]; if (d) download(`symbol_${sy.s}.csv`, [['date', 'tr_level', 'pr_level'], ...d.d.map((x, i) => [x, d.tr[i], d.pr[i]])]); };
    redraws.sym = drawSym;
    if (!sy.s) setSym(Object.entries(S.symbols).filter(([, v]) => v.w_k != null).sort((a, b) => b[1].w_k - a[1].w_k)[0][0]);
  });
}
function setSym(s) {
  const S = window.SIM_SYMBOLS; if (!S) return; const d = S.symbols[s];
  if (!d) { toast('نماد پیدا نشد: ' + s); return; }
  sy.s = s; sy.i = null; $('sy-q').value = s;
  $('sy-title').textContent = `${s} · ${d.name}`;
  $('sy-chip').textContent = d.alive ? (d.w_k != null ? 'بورس · در بازسازی «شاخص كل»' : d.market === 'farabourse' ? 'فرابورس · فعال' : 'فعال') : 'حذف‌شده/غیرفعال تا ' + d.last; $('sy-chip').className = 'chip ' + (d.alive ? 'ok' : 'warn');
  $('sy-kpis').innerHTML = [['بازده ۱ سال', sgn(d.ret1y, 1) + '%', cls(d.ret1y)], ['بازده سالانهٔ ۳ سال', d.ret3y_ann == null ? '—' : sgn(d.ret3y_ann, 1) + '%', cls(d.ret3y_ann)], ['نوسان ۱ سال', fmt(d.vol1y, 1) + '%', ''], ['افت از اوج (از ۲۰۱۴)', fmt(d.mdd, 1) + '%', 'down'], ['بتا به «شاخص كل»', d.beta1y == null ? '—' : fmt(d.beta1y, 2), '']]
    .map(([k, v, c]) => `<div class="kpi"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`).join('');
  const divs = d.events.filter(e => e[1] === 'div').length, caps = d.events.length - divs;
  $('sy-ev-chip').textContent = `${divs} سود · ${caps} سرمایه`;
  $('sy-ev').innerHTML = th([['تاریخ'], ['نوع'], ['قیمت قبل (U)', 'n'], ['بعد از تعدیل (A)', 'n'], ['سود هر سهم / نسبت', 'n'], ['بازده سود ٪', 'n']]) + '<tbody>' + d.events.slice().reverse().map(e => {
    const [dt, t, A, U] = e, isDiv = t === 'div';
    return `<tr><td class="num" title="${jd(dt)}">${dt}</td><td><span class="tag ${t}">${isDiv ? 'سود نقدی' : 'سرمایه'}</span></td><td class="n">${fmt(U, 0)}</td><td class="n">${fmt(A, 0)}</td><td class="n">${isDiv ? fmt(U - A, 0) : '×' + fmt(A / U, 3)}</td><td class="n">${isDiv ? fmt((U - A) / U * 100, 1) : '—'}</td></tr>`;
  }).join('') + '</tbody>';
  $('sy-info').innerHTML = '<tbody>' + [['نام', d.name], ['بازار', d.market === 'farabourse' ? 'فرابورس' : 'بورس'], ['صنعت', d.sector], ['کد (insCode)', `<span class="num">${d.code}</span>`], ['داده', `<span class="num">${d.first} → ${d.last}</span>`], ['قیمت پایانی', fmt(d.price, 0) + ' ریال'],
    ['ارزش بازار', fmt(d.mcap / 1e9, 0) + ' میلیارد ریال'], ['وزن در «شاخص كل» (بازسازی)', d.w_k == null ? '—' : fmt(d.w_k, 3) + '%'], ['وزن در هم‌وزن', d.w_ew == null ? '—' : fmt(d.w_ew, 3) + '%'], ['روزهای بدون معامله (۱ سال)', d.nontraded1y == null ? '—' : fmt(d.nontraded1y, 0) + '%']]
    .map(([k, v]) => `<tr><td class="mute">${k}</td><td>${v}</td></tr>`).join('') + '</tbody>';
  $('sy-agm').innerHTML = d.agm.length ? th([['سال مالی منتهی به'], ['تاریخ مجمع'], ['سود مصوب هر سهم (ریال)', 'n']]) + '<tbody>' + d.agm.slice().sort((a, b) => a[0] < b[0] ? 1 : -1).map(a => `<tr><td class="num">${a[0]}</td><td class="num">${a[1]}</td><td class="n">${a[2] ?? '—'}</td></tr>`).join('') + '</tbody>'
    : `<tbody><tr><td class="mute" style="white-space:normal">برای این نماد دادهٔ کدال جمع‌آوری نشده (فقط ۳۰ نماد بزرگ).</td></tr></tbody>`;
  $('sy-cap').innerHTML = th([['تاریخ'], ['سهام قبل', 'n'], ['سهام بعد', 'n'], ['تغییر ٪', 'n']]) + '<tbody>' + d.capchg.slice().reverse().map(c => `<tr><td class="num">${c[0]}</td><td class="n">${fmt(c[1], 0)}</td><td class="n">${fmt(c[2], 0)}</td><td class="n">${sgn((c[2] / c[1] - 1) * 100, 0)}</td></tr>`).join('') + '</tbody>';
  $('sy-lin').innerHTML = `<span><b>بازده کل</b> سود با استحقاق سرمایه‌گذاری مجدد (TR، همان قواعد بازسازی شاخص)</span><span><b>قیمت تعدیل‌شده</b> بدون سود نقدی (PR)</span><span><b>نمونه</b> هفتگی از ۲۰۱۴</span><span><b>روش</b> فصل ۰۲ §۲٫۴</span>`;
  drawSym();
}
function drawSym() {
  const S = window.SIM_SYMBOLS; if (!S || !sy.s) return; const d = S.symbols[sy.s];
  document.querySelectorAll('#sy-ser button').forEach(b => b.setAttribute('aria-pressed', b.dataset.s === sy.ser));
  const k = window.SIM_DATA.series, kd = k.dates;  // «شاخص كل» رسمی بر همان تاریخ‌ها برای مقایسه
  let p = 0; const kv = d.d.map(x => { while (p < kd.length - 1 && kd[p + 1] <= x) p++; return kd[p] <= x ? k.K_off[p] : null; });
  const k0 = kv.find(v => v != null), t0 = d.tr[kv.indexOf(k0)] || d.tr[0];
  const kRel = kv.map(v => v == null ? null : v / k0 * t0);
  const ser = [{ v: kRel, color: 'var(--ch-3)', w: 1, dash: true, name: '«شاخص كل» (هم‌مبدأ)', fmt: v => fmt(v, 1) }];
  if (sy.ser !== 'pr') ser.push({ v: d.tr, color: 'var(--ch-2)', w: 1.6, name: 'بازده کل', fmt: v => fmt(v, 2) });
  if (sy.ser !== 'tr') ser.push({ v: d.pr, color: 'var(--ch-1)', w: 1.2, name: 'قیمت تعدیل‌شده', fmt: v => fmt(v, 2) });
  paneChart($('sy-chart'), d.d, [{ frac: 1, log: true, series: ser, fmt: v => fmt(v, v < 10 ? 1 : 0) }], sy);
  $('sy-legend').innerHTML = `<span><i style="color:var(--ch-2)"></i>بازده کل</span><span><i style="color:var(--ch-1)"></i>قیمت تعدیل‌شده</span><span><i style="color:var(--ch-3);border-top-style:dashed"></i>«شاخص كل» رسمی (هم‌مبدأ)</span><span class="readout">${sy.i == null ? '' : `<b>${d.d[sy.i]}</b> · ${jd(d.d[sy.i])} &nbsp; TR <b>${fmt(d.tr[sy.i], 2)}</b> &nbsp; PR <b>${fmt(d.pr[sy.i], 2)}</b>`}</span>`;
}

/* ══════════ Fund ══════════ */
const pf = { k: 'K' };
function pfRows() {
  const F = X.fund, c = F.cols, nav = (+$('pf-nav').value || 0) * 1e9, part = (+$('pf-part').value || 10) / 100, advk = $('pf-adv').value;
  const n = F.rows.length;
  return F.rows.map(r => { const o = Object.fromEntries(c.map((k, i) => [k, r[i]])); const w = pf.k === 'K' ? o.w_k : 1 / n; const val = nav * w, adv = o[advk] || 0;
    return { ...o, w, val, sh: o.price ? Math.floor(val / o.price) : 0, days: adv > 0 ? val / (part * adv) : Infinity }; }).sort((a, b) => b.w - a.w);
}
function renderPf() {
  const rows = pfRows(), F = X.fund;
  document.querySelectorAll('#pf-idx button').forEach(b => b.setAttribute('aria-pressed', b.dataset.k === pf.k));
  $('pf-chip').textContent = `${F.n} نماد · قیمت‌ها ${F.asof}`;
  const tot = rows.reduce((a, r) => a + r.val, 0), within = d => rows.reduce((a, r) => a + Math.min(r.val, r.val / Math.max(r.days, 1e-9) * d), 0) / tot * 100;
  const wd = rows.reduce((a, r) => a + r.w * Math.min(r.days, 999), 0), over20 = rows.filter(r => r.days > 20).length, dead = rows.filter(r => !isFinite(r.days)).length;
  $('pf-kpis').innerHTML = [['ساخته‌شده در ۱ روز', fmt(within(1), 1) + '%'], ['در ۵ روز', fmt(within(5), 1) + '%'], ['در ۲۰ روز', fmt(within(20), 1) + '%'], ['میانگین وزنی روز', fmt(wd, 1)], ['نماد > ۲۰ روز', over20 + (dead ? ` (+${dead} بی‌معامله)` : '')]]
    .map(([k, v]) => `<div class="kpi"><div class="k">${k}</div><div class="v">${v}</div></div>`).join('');
  $('pf-tab').innerHTML = th([['#'], ['نماد'], ['صنعت'], ['وزن %', 'n'], ['مبلغ (م.ر)', 'n'], ['تعداد سهم', 'n'], ['ارزش معاملهٔ روزانه (م.ر)', 'n'], ['روز لازم', 'n'], ['روز معامله‌شده ۶۰ر', 'n']]) + '<tbody>' + rows.map((r, i) => {
    const dc = !isFinite(r.days) ? 'bad' : r.days > 20 ? 'bad' : r.days > 5 ? 'warn' : 'ok';
    return `<tr><td class="rank">${i + 1}</td><td><a class="symlink" data-sym="${r.sym}">${r.sym}</a></td><td class="mute">${r.sector}</td><td class="n">${fmt(r.w * 100, 3)}</td><td class="n">${fmt(r.val / 1e9, 1)}</td><td class="n">${fmt(r.sh, 0)}</td><td class="n">${fmt((r[$('pf-adv').value] || 0) / 1e9, 1)}</td><td class="n"><span class="chip ${dc}">${isFinite(r.days) ? fmt(r.days, 1) : '∞'}</span></td><td class="n">${r.traded_frac60 == null ? '—' : fmt(r.traded_frac60 * 100, 0) + '%'}</td></tr>`;
  }).join('') + '</tbody>';
  $('pf-lin').innerHTML = `<span><b>وزن</b> ${pf.k === 'K' ? 'ارزش بازار کل (بازسازی «شاخص كل»)' : 'برابر (۱/n)'}، روز ${F.asof}</span><span><b>روز لازم</b> مبلغ ÷ (مشارکت × ارزش معاملهٔ روزانه)</span><span><b>م.ر</b> میلیارد ریال</span><span><b>بی‌معامله</b> بدون معامله در ۶۰ روز (صف/توقف)</span>`;
  const bk = [1, 2, 5, 10, 20, 60, 120];
  bars($('pf-bars'), bk.map(d => d + 'روز'), bk.map(d => within(d)), v => fmt(v, 0) + '%', (i) => bk[i] === 20);
  $('pf-lin-b').innerHTML = `<span><b>فرض</b> هر روز حداکثر «مشارکت × ارزش معاملهٔ روزانه» از هر نماد خریده می‌شود؛ همهٔ نمادها موازی</span><span><b>مرجع</b> فصل ۰۶ (اجرا و هزینه)</span>`;
  const big = rows.filter(r => r.days > 20).slice(0, 6).map(r => `${r.sym} (${isFinite(r.days) ? fmt(r.days, 0) : '∞'} روز)`).join('، ');
  $('pf-read').innerHTML = `<b>این نما چه می‌گوید.</b> برای صندوقی به اندازهٔ ${fmt(+$('pf-nav').value, 0)} میلیارد ریال که ${pf.k === 'K' ? '«شاخص كل» را با وزن ارزش بازار' : 'هم‌وزن را'} کامل بازتولید کند، با مشارکت ${$('pf-part').value}٪ از ارزش معاملهٔ روزانهٔ هر نماد، ${fmt(within(5), 0)}٪ سبد در ۵ روز و ${fmt(within(20), 0)}٪ در ۲۰ روز ساخته می‌شود.
  <br><b>گلوگاه‌ها:</b> ${big || 'هیچ نمادی بیش از ۲۰ روز لازم ندارد.'}
  <br><b>آنچه مدل نشده:</b> صف خرید/فروش و سقف نوسان روزانه (اجرا در روزهای صف ممکن نیست)، اثر قیمتیِ خود سفارش، کارمزد و مالیات، و تغییر وزن‌ها در طول دورهٔ ساخت. «بدون محدودیت سرمایه» (تصمیم فصل ۳ §۳٫۵) برای خود شاخص است؛ این نما نشان می‌دهد اجرای واقعی در چه اندازه‌ای اصطکاک دارد.
  <br><b>دکمهٔ CSV:</b> فهرست سفارش‌های ساخت سبد از نقد (نماد، وزن، مبلغ، تعداد سهم، روز لازم).`;
}
function initPf() {
  document.querySelectorAll('#pf-idx button').forEach(b => b.onclick = () => { pf.k = b.dataset.k; renderPf(); });
  ['pf-nav', 'pf-part', 'pf-adv'].forEach(id => $(id).oninput = renderPf);
  $('pf-csv').onclick = () => download(`fund_orders_${pf.k}.csv`, [['symbol', 'sector', 'weight_pct', 'amount_rial', 'shares', 'price', 'adv_rial', 'days_needed'], ...pfRows().map(r => [r.sym, r.sector, (r.w * 100).toFixed(4), Math.round(r.val), r.sh, r.price, r[$('pf-adv').value], isFinite(r.days) ? r.days.toFixed(2) : 'inf'])]);
  renderPf();
}

/* ══════════ Risk ══════════ */
const rk = { k: 'K', i: null };
function drawRisk() {
  const R = X.risk[rk.k];
  paneChart($('rk-chart'), R.dates, [{ frac: .55, zero: true, series: [{ v: R.dd, color: 'var(--down)', w: 1.3, name: 'افت از اوج', fmt: v => fmt(v, 2) + '%' }], fmt: v => fmt(v, 0) + '%' }, { frac: .45, zero: true, series: [{ v: R.vol, color: 'var(--ch-2)', w: 1.2, name: 'نوسان ۶۳ روزه', fmt: v => fmt(v, 2) + '%' }], fmt: v => fmt(v, 0) + '%' }], rk);
  $('rk-readout').innerHTML = rk.i == null ? '' : `<b>${R.dates[rk.i]}</b> · ${jd(R.dates[rk.i])} &nbsp; افت <b>${fmt(R.dd[rk.i], 1)}%</b> &nbsp; نوسان <b>${fmt(R.vol[rk.i], 1)}%</b>`;
}
function renderRisk() {
  const R = X.risk[rk.k];
  document.querySelectorAll('#rk-idx button').forEach(b => b.setAttribute('aria-pressed', b.dataset.k === rk.k));
  $('rk-kpis').innerHTML = [['بازده سالانه (TR)', sgn(R.ann, 1) + '%', cls(R.ann)], ['نوسان سالانه', fmt(R.vol_all, 1) + '%', ''], ['نوسان ۱ سال اخیر', fmt(R.vol_1y, 1) + '%', ''], ['بیشترین افت از اوج', fmt(R.max_dd, 1) + '%', 'down'], ['اوج → کف', jd(R.peak) + ' → ' + jd(R.trough), '']]
    .map(([k, v, c]) => `<div class="kpi"><div class="k">${k}</div><div class="v ${c}" style="${k === 'اوج → کف' ? 'font-size:12px' : ''}">${v}</div></div>`).join('');
  $('rk-lin').innerHTML = `<span><b>سری</b> ${rk.k === 'K' ? '«شاخص كل»' : '«كل (هم وزن)»'} رسمی TR، پس از صافی مقیاس</span><span><b>بازگشت به اوج</b> ${R.recovered ? jd(R.recovered) : 'هنوز نه'}</span><span><b>نوسان</b> انحراف معیار ۶۳ روزه × √۲۵۲</span><span><b>توجه</b> بازده اسمی ریالی؛ تورم کسر نشده</span>`;
  $('rk-year').innerHTML = th([['سال'], ['بازده %', 'n'], ['نوسان %', 'n'], ['افت درون‌سال %', 'n'], ['روز', 'n']]) + '<tbody>' + R.yearly.map(y => `<tr><td class="num">${y.jy}</td><td class="n ${cls(y.ret)}">${sgn(y.ret, 1)}</td><td class="n">${fmt(y.vol, 1)}</td><td class="n down">${fmt(y.mdd, 1)}</td><td class="n mute">${y.days}</td></tr>`).join('') + '</tbody>';
  drawRisk();
}
function initRisk() {
  document.querySelectorAll('#rk-idx button').forEach(b => b.onclick = () => { rk.k = b.dataset.k; rk.i = null; renderRisk(); });
  chartOn('rk-chart', rk, drawRisk);
  const C = X.risk.sector_corr;
  $('rk-cchip').textContent = C.months + ' ماه';
  const col = v => `background:color-mix(in srgb, var(--accent) ${Math.round(Math.max(0, v) * 85)}%, var(--bg-panel));color:${v > .6 ? 'var(--tx-1)' : 'var(--tx-2)'}`;
  $('rk-corr').innerHTML = `<table class="heat"><tr><th></th>${C.names.map((n, i) => `<th title="${n}">${i + 1}</th>`).join('')}</tr>` + C.m.map((row, i) => `<tr><th class="r" title="${n(C.names[i])}">${i + 1}. ${C.names[i].slice(0, 22)} <span class="num dim">${fmt(C.w[i], 0)}%</span></th>${row.map(v => `<td style="${col(v)}">${fmt(v, 2)}</td>`).join('')}</tr>`).join('') + '</table>';
  function n(x) { return x; }
  $('rk-csv').onclick = () => { const R = X.risk[rk.k]; download(`risk_${rk.k}.csv`, [['date', 'drawdown_pct', 'vol63_pct'], ...R.dates.map((d, i) => [d, R.dd[i], R.vol[i]])]); };
  redraws.risk = drawRisk; renderRisk();
}

/* ══════════ Index Funds ══════════ */
/* بازهٔ انتخابی (r0..r1، رشتهٔ yymmdd) روی همهٔ پنل‌ها اثر می‌گذارد: جدول صندوق‌ها، نمودار، KPI و جدول دوره‌ها.
   زوم: کشیدن روی نمودار · چرخ موس (دسکتاپ) · دکمه‌های بازه · تاریخ دستی · کلیک روی ردیف دوره. دوبار کلیک = کل. */
const fn = { sym: null, ref: 'tr', i: null, r0: null, r1: null, per: 'year', drag: null };
const FB = () => (window.SIM_FUNDS && window.SIM_FUNDS.bench_names) || {};
const fnBench = k => FB()[k] || k;
const jyr = iso => (window.SIM_JDATE ? SIM_JDATE.j(iso) : iso).slice(0, 4);   // سال شمسی یک تاریخ ISO (ui/jdate.js)
const y2i = s => `20${s.slice(0, 2)}-${s.slice(2, 4)}-${s.slice(4, 6)}`;
const i2y = iso => iso.slice(2, 4) + iso.slice(5, 7) + iso.slice(8, 10);
const dayMs = s => Date.parse(y2i(s) + 'T00:00:00Z');
const jmon = new Intl.DateTimeFormat('fa-IR-u-ca-persian-nu-latn', { year: 'numeric', month: 'numeric' });
function jparts(s) { const p = jmon.formatToParts(new Date(y2i(s) + 'T00:00:00Z')); return [+p.find(x => x.type === 'year').value, +p.find(x => x.type === 'month').value]; }
const fnLast = () => window.SIM_FUNDS.funds.map(f => f.daily.d[f.daily.d.length - 1]).sort().pop();
const sd = (a) => { const n = a.length, m = a.reduce((x, y) => x + y, 0) / n; return Math.sqrt(a.reduce((x, y) => x + (y - m) ** 2, 0) / (n - 1)); };
const med = a => { const b = a.slice().sort((x, y) => x - y), k = b.length >> 1; return b.length % 2 ? b[k] : (b[k - 1] + b[k]) / 2; };
function fnIdx(f, a, b) { const D = f.daily.d; let lo = 0, hi = D.length - 1; while (lo <= hi && D[lo] < a) lo++; while (hi >= lo && D[hi] > b) hi--; return [lo, hi]; }
/* آمار یک بازه؛ ref = 'b' (مرجع رسمی) یا 'r' (همتا) */
function fnStats(f, lo, hi, ref = 'b') {
  const n = hi - lo + 1; if (n < 5) return null;
  const F = f.daily.f, B = ref === 'r' && f.daily.r ? f.daily.r : f.daily.b, R = f.daily.r;
  let pf = 1, pb = 1, pr = 1, hasR = !!R; const act = [], wf = [], wb = [];
  for (let i = lo; i <= hi; i++) { pf *= 1 + F[i]; pb *= 1 + B[i]; if (hasR) { if (R[i] == null) hasR = false; else pr *= 1 + R[i]; } act.push(F[i] - B[i]); }
  const wk = []; for (let i = lo; i + 4 <= hi; i += 5) { let a = 1, b = 1; for (let k = i; k < i + 5; k++) { a *= 1 + F[k]; b *= 1 + B[k]; } wk.push(a - b); wf.push(a - 1); wb.push(b - 1); }
  const days = (dayMs(f.daily.d[hi]) - dayMs(f.daily.d[lo])) / 864e5 || 1, yrs = days / 365.25;
  const o = { n, from: f.daily.d[lo], to: f.daily.d[hi], days, weeks: wk.length, diff: (pf / pb - 1) * 100, te_d: sd(act) * Math.sqrt(252) * 100 };
  if (wk.length >= 8) {
    o.te_w = sd(wk) * Math.sqrt(52) * 100; o.te_rob = 1.4826 * med(wk.map(x => Math.abs(x - med(wk)))) * Math.sqrt(52) * 100;
    const mf = wf.reduce((x, y) => x + y, 0) / wf.length, mb = wb.reduce((x, y) => x + y, 0) / wb.length;
    let sfb = 0, sbb = 0, sff = 0; for (let i = 0; i < wf.length; i++) { sfb += (wf[i] - mf) * (wb[i] - mb); sbb += (wb[i] - mb) ** 2; sff += (wf[i] - mf) ** 2; }
    o.corr_w = sfb / Math.sqrt(sbb * sff);
  }
  { const mf = F.slice(lo, hi + 1).reduce((x, y) => x + y, 0) / n, mb = B.slice(lo, hi + 1).reduce((x, y) => x + y, 0) / n; let c = 0, v = 0; for (let i = lo; i <= hi; i++) { c += (F[i] - mf) * (B[i] - mb); v += (B[i] - mb) ** 2; } o.beta = c / v; }
  if (days >= 180) o.td = (Math.pow(pf / pb, 1 / yrs) - 1) * 100;
  if (hasR && ref === 'b') { const dr = (pf / pr - 1) * 100; o.diff_rep = dr; if (days >= 180) o.td_rep = (Math.pow(pf / pr, 1 / yrs) - 1) * 100; }
  return o;
}
function fnBounds() { const a = fn.r0 || '000101', b = fn.r1 || '991231'; return [a, b]; }
function fnRows() {
  const [a, b] = fnBounds();
  return window.SIM_FUNDS.funds.map(f => { const [lo, hi] = fnIdx(f, a, b); const m = hi >= lo ? fnStats(f, lo, hi) : null; return { f, m, rp: m }; })
    .filter(r => r.m).sort((x, y) => (x.m.te_w ?? x.m.te_d + 1e3) - (y.m.te_w ?? y.m.te_d + 1e3));
}
function fnSetRange(a, b, keep) { fn.r0 = a; fn.r1 = b; fn.i = null; if (!keep) fn.drag = null; fnRender(); }
function fnPreset(k) {
  const last = fnLast(); if (k === 'all') return fnSetRange(null, null);
  const d = new Date(y2i(last) + 'T00:00:00Z'); const m = { '1m': 1, '3m': 3, '6m': 6, '1y': 12, '3y': 36 }[k]; d.setUTCMonth(d.getUTCMonth() - m);
  fnSetRange(i2y(d.toISOString().slice(0, 10)), last);
}
function fnTable() {
  const F = window.SIM_FUNDS, rows = fnRows(), na = '<td class="n mute">—</td>';
  const nf = (v, d, c) => v == null ? na : `<td class="n ${c || ''}">${fmt(v, d)}</td>`, sg = (v, d) => v == null ? na : `<td class="n ${cls(v)}">${sgn(v, d)}</td>`;
  const th_ = [['نماد'], ['مرجع'], ['از'], ['روز', 'n'], ['TE هفتگی %', 'n'], ['TE مقاوم %', 'n'], ['TE روزانه %', 'n'], ['تفاوت تجمعی %', 'n'], ['TD سالانه %', 'n'], ['TD نسبت به همتا %', 'n'], ['همبستگی هفتگی', 'n'], ['بتا', 'n'], ['پریمیوم لحظه‌ای %', 'n'], ['رویداد', 'n']];
  const body = rows.map(({ f, m }) => {
    const p = f.premium || {}, auto = f.benchmark_src === 'auto', odd = f.best_fit !== f.benchmark, [a, b] = fnBounds(), ev = f.events.filter(e => i2y(e[0]) >= a && i2y(e[0]) <= b).length;
    return `<tr data-sym="${f.symbol}" ${f.symbol === fn.sym ? 'aria-selected="true"' : ''}><td><b>${f.symbol}</b></td><td>${fnBench(f.benchmark).replace(/[«»]/g, '')}${auto ? ' <span class="chip warn">حدسی</span>' : ''}${odd ? ` <span class="chip warn" data-tip="با این صندوق بهترین برازش را شاخص ${fnBench(f.best_fit)} دارد؛ مرجع اعلام‌شده را بررسی کنید.">برازش بهتر: ${fnBench(f.best_fit).replace(/[«»]/g, '')}</span>` : ''}</td><td class="num">${y2i(m.from)}</td><td class="n">${m.n}</td>${nf(m.te_w, 2, '')}${nf(m.te_rob)}${nf(m.te_d)}${sg(m.diff)}${sg(m.td)}${sg(m.td_rep)}${nf(m.corr_w, 4)}${nf(m.beta, 3)}${p.last == null ? na : `<td class="n ${cls(p.last)}">${sgn(p.last)}</td>`}<td class="n">${ev || ''}</td></tr>`;
  }).join('');
  const refRows = F.reference.map(x => `<tr class="mute"><td>همتای سرمایه‌پذیر</td><td>${fnBench(x.benchmark).replace(/[«»]/g, '')}</td><td class="num">${x.from}</td><td class="n">${x.n}</td><td class="n">${fmt(x.te_w)}</td><td class="n">${fmt(x.te_w_rob)}</td><td class="n">${fmt(x.te_d)}</td><td class="n">—</td><td class="n ${cls(x.td)}">${sgn(x.td)}</td><td class="n">—</td><td class="n">${fmt(x.corr_w, 4)}</td><td class="n">${fmt(x.beta, 3)}</td><td class="n">—</td><td class="n"></td></tr>`).join('');
  $('fn-tab').innerHTML = th(th_) + '<tbody>' + body + refRows + '</tbody>';
  document.querySelectorAll('#fn-tab tr[data-sym]').forEach(tr => tr.onclick = () => { fn.sym = tr.dataset.sym; fn.i = null; fnRender(); });
}
function fnEmpty() {
  const F = window.SIM_FUNDS;
  $('fn-chip').textContent = 'منتظر دادهٔ NAV';
  $('fn-tab').innerHTML = th([['نماد'], ['نام'], ['مرجع']]) + '<tbody>' + F.missing.map(m => `<tr><td><b>${m.symbol}</b></td><td>${m.name}</td><td>${fnBench(m.benchmark).replace(/[«»]/g, '')}${m.benchmark_src === 'auto' ? ' <span class="chip warn">حدسی</span>' : ''}</td></tr>`).join('') + '</tbody>';
  ['fn-kpis', 'fn-chart', 'fn-lin-b', 'fn-per'].forEach(k => $(k).innerHTML = '');
  $('fn-legend').innerHTML = '<span>نمودار NAV در برابر مرجع و TE غلتان پس از دریافت دادهٔ صندوق‌ها ساخته می‌شود (دستور در پنل D)</span>';
  $('fn-title').textContent = 'صندوق';
  $('fn-lin-a').innerHTML = `<span><b>وضعیت</b> NAV این صندوق‌ها هنوز در مخزن نیست؛ ${F.missing.length} صندوق شاخصی شناسایی شده است</span>`;
  $('fn-method').innerHTML = fnMethod(false);
}
function fnMethod(has) {
  const F = window.SIM_FUNDS;
  return `<p><b>داده:</b> قیمت بازار و بازده روزانهٔ NAV هر صندوق از TSETMC و فیپیران با <code>tools/fetch_index_funds.py</code> روی سیستم شما گرفته می‌شود؛ سپس <code>python tools/build_ui_funds.py</code> این نما را می‌سازد.</p>
  ${has ? '' : `<div class="cmdline">python tools/fetch_index_funds.py --log funds_log.txt\npython tools/build_ui_funds.py\ngit add -A; git commit -m "index funds"; git push -u origin claude/charming-ptolemy-cyehmc</div>`}
  <p><b>روش:</b></p><ol>
  <li>بازده روزانهٔ NAV صندوق روی روزهای معاملاتی شاخص؛ دو ماه اول عمر صندوق (تشکیل سبد) کنار می‌رود.</li>
  <li><b>TE هفتگی</b> = انحراف معیار بازده فعال ۵ روزهٔ غیرهم‌پوشان × √۵۲ (در بازه‌های کوتاه‌تر از ۸ هفته محاسبه نمی‌شود). چون NAV و شاخص در بورس تهران هم‌زمان منتشر نمی‌شوند، معیار اصلی است. <b>TE روزانه</b> برای مقایسه با ادبیات هم آمده است. <b>TE مقاوم</b> = ۱٫۴۸۲۶ × MAD بازده فعال ۵ روزه × √۵۲، که به چند هفتهٔ پرت حساس نیست.</li>
  <li><b>تفاوت تجمعی</b> بازده مرکب صندوق منهای مرجع در همان بازه؛ <b>TD سالانه</b> همان با سال تقویمی و فقط برای بازه‌های ۱۸۰ روز و بیشتر.</li>
  <li><b>TD نسبت به همتا</b> = بازده صندوق منهای همتای سرمایه‌پذیر (بازتولید کامل، بدون کارمزد، سود با ${F.lag_mode === 'empirical' ? `توزیع واقعی تأخیر پرداخت (کدال و فارابی، ${F.lag_n} رویداد؛ میانگین وزنی ${F.lag} روز)` : `تأخیر ${F.lag} روز`})؛ بخش ساختاری TD را از سهم قابل‌انتساب به مدیر جدا می‌کند. همتا فقط برای «شاخص كل» و هم‌وزن موجود است.</li>
  <li>جهش بازده فعال روزانه بیش از ۸٪ رویداد حساب و خنثی می‌شود؛ اگر چند صندوق در یک تاریخ رویداد دارند (مثلاً اردیبهشت ۱۴۰۵)، مسئله بازار یا زمان‌بندی NAV است نه صندوق خاص.</li>
  <li><b>برازش بهتر:</b> NAV هر صندوق در برابر هر سه شاخص سنجیده می‌شود؛ اگر شاخص دیگری TE کمتری بدهد، مرجع اعلام‌شده بازبینی شود. <b>حدسی</b> یعنی مرجع اعلام نشده است.</li>
  <li><b>پریمیوم لحظه‌ای</b> = قیمت پایانی بازار در روز آخرین NAV ابطال ÷ همان NAV − ۱. میانگین تاریخی گزارش نمی‌شود چون سطح NAV از بازده روزانه با بازگشت در زمان خطا انباشته می‌کند.</li></ol>
  <p><b>زوم:</b> روی نمودار بکشید تا بازه انتخاب شود؛ چرخ موس بزرگ‌نمایی می‌کند؛ دوبار کلیک یا دکمهٔ «کل» بازمی‌گرداند؛ روی هر ردیف جدول دوره‌ها کلیک کنید تا همان دوره باز شود. جدول صندوق‌ها، KPI و نمودار همگی برای همان بازه دوباره محاسبه می‌شوند.</p>
  <p><b>تعریف NAV:</b> بازده روزانه از API فیپیران (dailyEfficiency) است. ضرب‌شدن آن از اول عمر صندوق به آخرین NAV ابطال می‌رسد (کاردان: واحد اولیه ۲۵۰ ریال دقیقاً؛ فیروزه ۳۵۰)، پس همان NAV ابطال است. NAV با قیمت آخرین معامله و در زمانی متفاوت از بستن شاخص محاسبه می‌شود؛ رگرسیون بازده کاردان روی شاخص: ۰٫۹۶ روز جاری، ۰٫۲۷ روز بعد و −۰٫۲۱ روز قبل ⇒ ناهمزمانی.</p>
  <p><b>محدودیت‌ها:</b> NAV ابطال تحت‌تأثیر برآورد قیمت سهام متوقف و صف است؛ کارمزد سالانه از NAV جدا نمی‌شود و در TD دیده می‌شود؛ ترکیب تاریخی شاخص ۳۰ شرکت بازسازی نشده است.</p>`;
}
/* ریشهٔ خطا: تأخیر سود یا چیز دیگر؟ (tools/fund_diagnostics.py؛ کل نمونه) */
function fnRoot(f) {
  const t = f.divtest; if (!t) return '<p class="mute">برای این صندوق دادهٔ کافی برای آزمون ریشهٔ خطا نیست (کمتر از ۱۵۰ روز).</p>';
  const b = t.best, share = t.r2_div_only * 100, unexpl = (1 - b.r2_full) * 100;
  const verdict = share >= 20 ? 'بخش مهمی از خطا با فاصلهٔ پرداخت سود جور است' : share >= 5 ? 'فاصلهٔ پرداخت سود بخش کوچکی از خطا را توضیح می‌دهد' : 'فاصلهٔ پرداخت سود تقریباً هیچ‌چیز از خطا را توضیح نمی‌دهد';
  const rows = t.scan.map(r => `<tr ${r[0] === b.L ? 'aria-selected="true"' : ''}><td class="n">${r[0]}</td><td class="n">${fmt(r[1] * 100, 1)}</td><td class="n">${fmt(r[2], 2)}</td><td class="n">${fmt(r[3], 2)}</td><td class="n">${fmt(r[4], 1)}</td></tr>`).join('');
  const sea = f.season;
  return `<p><b>ریشهٔ خطا — ${f.symbol}</b> <span class="mute">(کل نمونه، ${t.n_weeks} هفته)</span></p>
  <p>${verdict}: مدل «سود طلب‌شده و دریافت‌نشده» (بهترین تأخیر ${b.L} روز) فقط <b>${fmt(share, 1)}٪</b> از واریانس بازده فعال هفتگی را توضیح می‌دهد و <b>${fmt(unexpl, 0)}٪</b> بی‌توضیح می‌ماند؛ کمبود بتا (نقد یا ترکیب متفاوت) ${fmt(t.r2_c0 * 100, 1)}٪. TE هفتگی ${fmt(t.te)}٪ ← پس از حذف بخش توضیح‌داده‌شده ${fmt(b.te_resid)}٪. ضریب تأخیر سود c₁ = ${fmt(b.c1, 2)} (۱ = تأخیر سود دقیقاً برقرار) با t = ${fmt(b.t_c1, 1)}.</p>
  <table class="dt"><thead><tr><th class="n">تأخیر L (روز)</th><th class="n">R² مدل %</th><th class="n">c₁ سود</th><th class="n">c₀ بتا</th><th class="n">t(c₁)</th></tr></thead><tbody>${rows}</tbody></table>
  <p><b>فصلی‌بودن خطا</b> (بازده فعال ماهانهٔ مرکب، bp، میانگین سال‌ها): اگر ریشه فاصلهٔ پرداخت سود بود، خطا باید در خرداد تا مرداد (فصل سود) متمرکز می‌شد.</p><div class="bars" id="fn-season" style="height:110px"></div>
  ${fnHold(f)}`;
}
function fnHold(f) {
  const H = f.holdings;
  if (!H) return `<p><b>پرتفوی کدال:</b> برای جداکردن «ترکیب پرتفوی» از «زمان‌بندی سود» به پرتفوی ماهانهٔ صندوق از کدال نیاز است؛ هنوز برای این صندوق نیامده. ابزار آماده است: <code>python tools/fetch_fund_portfolio.py --probe ${f.symbol}</code>، سپس parser و <code>python tools/build_ui_funds.py</code>.</p>`;
  const nm = { composition: 'ترکیب پرتفو', cash: 'نقد', lag: 'تأخیر سود', residual: 'باقیمانده (کارمزد، NAV، معاملات)' };
  const top = Object.entries(H.share).sort((a, b) => b[1] - a[1])[0];
  const rows = H.rows.map(r => `<tr><td class="num">${r.date}</td><td class="n ${cls(r.active)}">${sgn(r.active)}</td><td class="n">${sgn(r.composition)}</td><td class="n">${sgn(r.cash)}</td><td class="n">${sgn(r.lag)}</td><td class="n">${sgn(r.residual)}</td><td class="n mute">${fmt(r.coverage, 0)}</td></tr>`).join('');
  return `<p><b>تجزیه با پرتفوی کدال — ${f.symbol}</b> <span class="mute">(${H.n} گزارش، ${H.from} تا ${H.to}، تأخیر سود ${H.actual_dates ? 'تاریخ واقعی کدال یا میانگین ' + H.lag : H.lag} روز، پوشش نمادها ${fmt(H.coverage, 0)}٪، نقد ${fmt(H.cash_pct, 1)}٪)</span></p>
  ${H.n < 6 ? `<p class="mute"><b>نمونه کوچک:</b> فقط ${H.n} گزارش پرتفو؛ تا دریافت ماه‌های بیشتر (<code>python tools/fetch_fund_portfolio.py --collect 24</code>) نتیجه‌گیری نشود.</p>` : ''}<p>بزرگ‌ترین سهم از مجموع مربعات بازده فعال ماهانه: <b>${nm[top[0]]}</b> (${fmt(top[1] * 100, 0)}٪). ${top[0] === 'lag' ? 'فاصلهٔ پرداخت سود ریشهٔ اصلی خطاست.' : top[0] === 'residual' ? 'ریشه نه ترکیب پرتفوی و نه تأخیر سود است؛ کارمزد، قیمت‌گذاری NAV یا معاملات درون ماه باید بررسی شود.' : top[0] === 'composition' ? 'ریشه تفاوت سهام نگه‌داشته‌شده با شاخص است، نه فاصلهٔ پرداخت سود.' : 'ریشه نقد نگه‌داشته‌شده است.'}</p>
  <table class="dt"><thead><tr><th>گزارش</th><th class="n">فعال %</th><th class="n">ترکیب</th><th class="n">نقد</th><th class="n">تأخیر سود</th><th class="n">باقیمانده</th><th class="n">پوشش %</th></tr></thead><tbody>${rows}</tbody></table>`;
}
function fnPeriods(f) {
  const [a, b] = fnBounds(), [lo, hi] = fnIdx(f, a, b); if (hi - lo < 5) { $('fn-per').innerHTML = ''; return; }
  const D = f.daily.d, key = s => { const [y, m] = jparts(s); return fn.per === 'year' ? `${y}` : fn.per === 'quarter' ? `${y}-${'۱۲۳۴'[Math.floor((m - 1) / 3)]}` : `${y}/${String(m).padStart(2, '0')}`; };
  const groups = []; let cur = null;
  for (let i = lo; i <= hi; i++) { const k = key(D[i]); if (!cur || cur.k !== k) { cur = { k, lo: i, hi: i }; groups.push(cur); } else cur.hi = i; }
  const rows = groups.map(g => ({ g, s: fnStats(f, g.lo, g.hi) })).filter(r => r.s);
  const na = '<td class="n mute">—</td>';
  $('fn-per').innerHTML = th([['دوره'], ['روز', 'n'], ['صندوق %', 'n'], ['مرجع %', 'n'], ['تفاوت %', 'n'], ['TE هفتگی %', 'n'], ['TE روزانه %', 'n']]) + '<tbody>' + rows.map(({ g, s }) => {
    let pf = 1, pb = 1; for (let i = g.lo; i <= g.hi; i++) { pf *= 1 + f.daily.f[i]; pb *= 1 + f.daily.b[i]; }
    return `<tr data-a="${D[g.lo]}" data-b="${D[g.hi]}" style="cursor:pointer"><td class="num">${g.k}</td><td class="n mute">${s.n}</td><td class="n ${cls(pf - 1)}">${sgn((pf - 1) * 100, 1)}</td><td class="n ${cls(pb - 1)}">${sgn((pb - 1) * 100, 1)}</td><td class="n ${cls(s.diff)}">${sgn(s.diff)}</td>${s.te_w == null ? na : `<td class="n">${fmt(s.te_w)}</td>`}<td class="n">${fmt(s.te_d)}</td></tr>`;
  }).join('') + '</tbody>';
  document.querySelectorAll('#fn-per tr[data-a]').forEach(tr => tr.onclick = () => fnSetRange(tr.dataset.a, tr.dataset.b));
  document.querySelectorAll('#fn-pergrp button').forEach(x => x.setAttribute('aria-pressed', x.dataset.p === fn.per));
}
function fnRender() {
  const F = window.SIM_FUNDS;
  if (!F.funds.length) { fnEmpty(); return; }
  document.querySelectorAll('#fn-ref button').forEach(b => b.setAttribute('aria-pressed', b.dataset.r === fn.ref));
  const [a, b] = fnBounds(), last = fnLast();
  $('fn-from').value = fn.r0 ? SIM_JDATE.j(y2i(fn.r0)) : ''; $('fn-to').value = fn.r1 ? SIM_JDATE.j(y2i(fn.r1)) : '';   // ورودی‌ها شمسی‌اند (ui/jdate.js)
  const rows = fnRows();
  if (!rows.length) { $('fn-tab').innerHTML = ''; $('fn-lin-a').innerHTML = '<span>برای این بازه دادهٔ کافی نیست</span>'; return; }
  if (!rows.find(r => r.f.symbol === fn.sym)) fn.sym = rows[0].f.symbol;
  $('fn-chip').textContent = rows.length + ' صندوق' + (fn.r0 || fn.r1 ? ' · ' + jd(y2i(fn.r0 || rows[0].m.from)) + ' ← ' + jd(y2i(fn.r1 || last)) : '');
  fnTable();
  $('fn-lin-a').innerHTML = `<span><b>مرتب</b> بر پایهٔ TE هفتگی (کمتر بهتر)</span><span><b>بازه</b> ${fn.r0 || fn.r1 ? 'انتخابی' : 'کل عمر هر صندوق'}</span><span><b>ردیف خاکستری</b> همتای سرمایه‌پذیر در ۳ سال اخیر؛ کف ساختاری</span><span><b>ساخت</b> <span class="num">${F.built}</span></span>`;
  const f = rows.find(r => r.f.symbol === fn.sym).f, [lo, hi] = fnIdx(f, a, b), ref = fn.ref === 'rep' && f.daily.r ? 'r' : 'b', m = fnStats(f, lo, hi, ref);
  const nm = ref === 'r' ? 'همتای سرمایه‌پذیر ' + fnBench(f.benchmark) : fnBench(f.benchmark);
  $('fn-title').textContent = `${f.symbol} · ${f.name}`;
  const na = '—';
  $('fn-kpis').innerHTML = [['TE هفتگی', m.te_w == null ? na : fmt(m.te_w) + '%', ''], ['TE مقاوم', m.te_rob == null ? na : fmt(m.te_rob) + '%', ''], ['TE روزانه', fmt(m.te_d) + '%', ''], ['تفاوت تجمعی', sgn(m.diff) + '%', cls(m.diff)], ['TD سالانه', m.td == null ? na : sgn(m.td) + '%', cls(m.td)], ['همبستگی هفتگی', m.corr_w == null ? na : fmt(m.corr_w, 4), ''], ['بتا', fmt(m.beta, 3), '']]
    .map(([k, v, c]) => `<div class="kpi"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`).join('');
  // نمودار: سطح بازنشانی‌شده در آغاز بازه
  const D = f.daily, step = Math.max(1, Math.ceil((hi - lo + 1) / 700)), dates = [], lf = [], lb = [], lr = [], te = [];
  if (!f._te63) { const act = D.f.map((v, i) => v - D.b[i]); f._te63 = act.map((_, i) => i < 62 ? null : sd(act.slice(i - 62, i + 1)) * Math.sqrt(252) * 100); }
  let cf = 100, cb = 100, cr = 100;
  for (let i = lo; i <= hi; i++) { cf *= 1 + D.f[i]; cb *= 1 + D.b[i]; if (D.r && D.r[i] != null) cr *= 1 + D.r[i]; if ((i - lo) % step === step - 1 || i === hi) { dates.push(y2i(D.d[i])); lf.push(cf); lb.push(ref === 'r' && D.r ? cr : cb); lr.push(cr); te.push(f._te63[i]); } }
  $('fn-legend').innerHTML = `<span><i style="color:var(--ch-1)"></i>صندوق (NAV)</span><span><i style="color:var(--ch-2)"></i>${nm.replace(/[«»]/g, '')}</span>${D.r && ref === 'b' ? '<span><i style="color:var(--ch-3);border-top-style:dashed"></i>همتای سرمایه‌پذیر</span>' : ''}<span><i style="color:var(--down)"></i>TE ۶۳ روزه (٪)</span><span class="readout" id="fn-readout"></span>`;
  const ser = [{ v: lf, color: 'var(--ch-1)', w: 1.5, name: 'صندوق', fmt: v => fmt(v, 2) }, { v: lb, color: 'var(--ch-2)', w: 1.3, name: nm.replace(/[«»]/g, ''), fmt: v => fmt(v, 2) }]; if (D.r && ref === 'b') ser.push({ v: lr, color: 'var(--ch-3)', w: 1.1, dash: true, name: 'همتای سرمایه‌پذیر', fmt: v => fmt(v, 2) });
  const st = fn;
  const draw = () => {
    paneChart($('fn-chart'), dates, [{ frac: .65, log: true, series: ser, fmt: v => fmt(v, 0) }, { frac: .35, zero: true, series: [{ v: te, color: 'var(--down)', w: 1.2, name: 'TE₆₃ (٪ سالانه)', fmt: v => fmt(v, 2) + '%' }], fmt: v => fmt(v, 1) + '%' }], st);
    $('fn-readout').innerHTML = st.i == null ? '' : `<b>${dates[st.i]}</b> · ${jd(dates[st.i])} &nbsp; صندوق <b>${fmt(lf[st.i], 1)}</b> &nbsp; مرجع <b>${fmt(lb[st.i], 1)}</b> &nbsp; TE₆₃ <b>${te[st.i] == null ? '—' : fmt(te[st.i], 2) + '%'}</b>`;
  };
  fn._dates = dates;
  redraws.fnd = draw; draw();
  $('fn-lin-b').innerHTML = `<span><b>بازه</b> <span class="num">${y2i(m.from)}</span> → <span class="num">${y2i(m.to)}</span> · ${m.n} روز</span><span><b>مرجع</b> ${nm}${f.benchmark_src === 'auto' ? ' (حدسی)' : ''}</span><span><b>NAV</b> بازده روزانهٔ ${f.nav_col === 'ret_daily' ? 'فیپیران' : 'NAV'}</span>${f.price_te != null ? `<span><b>TE قیمت بازار</b> ${fmt(f.price_te)}%</span>` : ''}<span><b>زوم</b> بکشید · چرخ موس · دوبار کلیک = کل</span>`;
  fnPeriods(f);
  const evs = f.events.length ? `<p><b>رویدادهای خنثی‌شده برای ${f.symbol}:</b> ${f.events.map(e => `<span class="num">${e[0]}</span> (${sgn(e[1], 1)}٪)`).join('، ')}</p>` : '';
  const miss = F.missing.length ? `<p><b>NAV دریافت‌نشده:</b> ${F.missing.map(x => x.symbol).join('، ')}</p>` : '';
  $('fn-method').innerHTML = fnRoot(f) + evs + miss + fnMethod(true);
  if (f.season && $('fn-season')) bars($('fn-season'), JM.map(x => x.slice(0, 3)), f.season.mean_bp.map(v => v ?? 0), v => fmt(v, 0), i => i >= 2 && i <= 4);
}
function initFnd() {
  document.querySelectorAll('#fn-pre button').forEach(b => b.onclick = () => fnPreset(b.dataset.k));
  document.querySelectorAll('#fn-ref button').forEach(b => b.onclick = () => { fn.ref = b.dataset.r; fnRender(); });
  document.querySelectorAll('#fn-pergrp button').forEach(b => b.onclick = () => { fn.per = b.dataset.p; fnRender(); });
  const dt = () => { const a = SIM_JDATE.g($('fn-from').value), b = SIM_JDATE.g($('fn-to').value); fnSetRange(a ? i2y(a) : null, b ? i2y(b) : null); };
  $('fn-from').onchange = dt; $('fn-to').onchange = dt;
  $('fn-csv').onclick = () => {
    const F = window.SIM_FUNDS; if (!F.funds.length) return download('index_funds_candidates.csv', [['symbol', 'name', 'benchmark'], ...F.missing.map(m => [m.symbol, m.name, m.benchmark])]);
    download(`index_funds_tracking_${fn.r0 || 'all'}_${fn.r1 || 'all'}.csv`, [['symbol', 'benchmark', 'from', 'to', 'days', 'te_weekly_pct', 'te_robust_pct', 'te_daily_pct', 'cum_diff_pct', 'td_pct', 'td_vs_replica_pct', 'corr_weekly', 'beta'], ...fnRows().map(({ f, m }) => [f.symbol, f.benchmark, m.from, m.to, m.n, m.te_w ?? '', m.te_rob ?? '', m.te_d, m.diff, m.td ?? '', m.td_rep ?? '', m.corr_w ?? '', m.beta])]);
  };
  chartOn('fn-chart', fn, () => redraws.fnd && redraws.fnd(), {
    onZoom: (lo, hi) => {                              // زوم = بازهٔ تازه؛ همهٔ آمار و جدول‌ها از نو محاسبه می‌شود (خارج از بازهٔ فعلی با درون‌یابی تاریخ)
      const ds = fn._dates; if (!ds) return; const n = ds.length, t0 = Date.parse(ds[0]), t1 = Date.parse(ds[n - 1]), dt = (t1 - t0) / (n - 1);
      const at = i => i <= 0 ? t0 + i * dt : i >= n - 1 ? t1 + (i - (n - 1)) * dt : Date.parse(ds[i]);
      const iso = t => new Date(t).toISOString().slice(0, 10);
      if (hi - lo >= (n - 1) * 3) return fnSetRange(null, null);
      fnSetRange(i2y(iso(at(lo))), i2y(iso(at(hi))), true);
    },
    onReset: () => fnSetRange(null, null) });
  redraws.fnd = null; fnRender();
}

/* ══════════ تراکم، حافظهٔ تنظیمات، تاریخچهٔ فرمان، کلیک روی نماد ══════════ */
const LS = { get: k => { try { return localStorage.getItem('sim.' + k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem('sim.' + k, v); } catch (e) { /* بی‌اهمیت */ } } };
const DENS = ['calm', 'default', 'compact'], DENS_FA = { calm: 'آرام', default: 'استاندارد', compact: 'فشرده' };
function setDensity(d) { if (d === 'calm') delete document.documentElement.dataset.density; else document.documentElement.dataset.density = d; LS.set('density2', d); }
$('density').onclick = () => { const cur = document.documentElement.dataset.density || 'calm'; const nx = DENS[(DENS.indexOf(cur) + 1) % 3]; setDensity(nx); toast('تراکم: ' + DENS_FA[nx]); };
if (LS.get('density2')) setDensity(LS.get('density2'));
/* تم شب/روز: اگر انتخاب ذخیره نشده، از ترجیح سیستم‌عامل؛ دکمه آیکن وضعیت را نشان می‌دهد */
const html = document.documentElement;
html.dataset.theme = LS.get('theme') || (matchMedia && matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
const themeIcon = () => { const b = $('theme'); b.textContent = html.dataset.theme === 'dark' ? '☀' : '☾'; b.title = html.dataset.theme === 'dark' ? 'تم روز' : 'تم شب'; b.dataset.tip = html.dataset.theme === 'dark' ? 'تغییر به تم روز (THEME)' : 'تغییر به تم شب (THEME)'; };
new MutationObserver(() => { LS.set('theme', html.dataset.theme); themeIcon(); const v = Object.keys(VIEWS).find(k => !$(VIEWS[k]).hidden); if (v) setTimeout(() => { if (v === 'index') drawChart(); else if (redraws[v]) redraws[v](); else if (NV[v] && NV[v].redraw) NV[v].redraw(); }, 30); }).observe(html, { attributes: true, attributeFilter: ['data-theme'] });
themeIcon();
document.addEventListener('click', e => { const a = e.target.closest('.symlink'); if (a) { e.preventDefault(); window.openSym(a.dataset.sym); } });
const hist = JSON.parse(LS.get('hist') || '[]'); let hi = hist.length;
$('cmd').addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target.value.trim()) { hist.push(e.target.value.trim()); while (hist.length > 30) hist.shift(); LS.set('hist', JSON.stringify(hist)); hi = hist.length; }
  if (e.key === 'ArrowUp' && hist.length) { hi = Math.max(0, hi - 1); e.target.value = hist[hi]; e.preventDefault(); }
  if (e.key === 'ArrowDown' && hist.length) { hi = Math.min(hist.length, hi + 1); e.target.value = hist[hi] || ''; e.preventDefault(); }
}, true);

/* ══════════ Router ══════════ */
const INIT = { div: initDiv, reb: initReb, qa: initQA, rep: initRep, sym: initSym, pf: initPf, risk: initRisk, fnd: initFnd };
const NV = window.SIM_NEWVIEWS || {};                                   // نماهای lab.js: Lab · Signals · Plan
Object.keys(NV).forEach(k => { VIEWS[k] = NV[k].id; INIT[k] = NV[k].init; });
/* پنج بخش بر پایهٔ کار کاربر؛ هر بخش زیرتب‌های خودش را دارد. کلید ۱–۵ بخش‌ها، L استراتژی، G معیارها، A دستور اجرا. */
const SECTIONS = [
  { id: 'strategy', fa: 'استراتژی', why: 'معیار ← ترکیب ← الگوریتم ← ریبالانس و هزینه ← آمار سخت', views: [['lab', 'آزمایشگاه استراتژی'], ['sig', 'معیارها']] },
  { id: 'index', fa: 'شاخص و همتا', why: 'شاخص رسمی را بسازید یا در «بازسازی شاخص» با چند سهم و وام دنبالش کنید', views: [['index', 'شاخص‌های رسمی و همتا'], ['sam', 'بازسازی شاخص'], ['div', 'اثر تأخیر سود'], ['reb', 'سیاست ریبالانس'], ['risk', 'ریسک']] },
  { id: 'exec', fa: 'اجرا', why: 'از پرتفوی هدف تا سفارش، و رصد استراتژی قفل‌شده', views: [['plan', 'دستور اجرا'], ['live', 'دفتر زنده']] },
  { id: 'funds', fa: 'صندوق‌ها', why: 'سبد هدف صندوق شاخصی و ردیابی صندوق‌های موجود', views: [['pf', 'سبد صندوق شاخصی'], ['fnd', 'ردیابی صندوق‌ها']] },
  { id: 'data', fa: 'داده و گزارش', why: 'اعتماد: کیفیت داده، نماد، گزارش و تاریخچهٔ روش‌شناسی', views: [['qa', 'کیفیت داده'], ['sym', 'نماد'], ['rep', 'گزارش‌ها']] },
];
const SUBTIP = {"lab": "میز پژوهش: استراتژی را از معیارها، روش ترکیب، الگوریتم انتخاب، ریبالانس و هزینه بسازید و در مرورگر بک\u200cتست کنید؛ کتابخانهٔ ۱۲۲ استراتژی از پیش محاسبه\u200cشده هم اینجاست. کلید L.", "sig": "باغ\u200cوحش معیارها: هر معیار جداگانه — IC، آمار t، پریمیوم Fama–MacBeth، پنجک\u200cها، دو نیمهٔ نمونه و همبستگی معیارها. کلید G.", "index": "بازسازی «شاخص كل» و «كل (هم وزن)» از قیمت تک\u200cتک سهام و مقایسهٔ روزبه\u200cروز با سری رسمی TSETMC.", "sam": "بازسازی شاخص: دنبال\u200cکردن «شاخص كل» با تعداد محدودی سهم (N)، فیلتر نقدشوندگی، نقد یا وام؛ و «شاخص بهبودیافته» با تیلت\u200cهای کنترل\u200cشده.", "div": "هزینهٔ اینکه سود نقدی روز استحقاق طلب می\u200cشود ولی ماه\u200cها بعد می\u200cرسد: همتای سرمایه\u200cپذیر با تأخیر پرداخت سود در برابر شاخص بازده کل رسمی.", "reb": "هر چند وقت یک\u200cبار وزن\u200cهای هم\u200cوزن برابر شوند؟ دقت ردیابی در برابر گردش و هزینهٔ معامله برای هر سیاست ریبالانس.", "risk": "ریسک سری\u200cهای رسمی: افت از اوج، نوسان غلتان، عملکرد هر سال شمسی و همبستگی صنایع بزرگ.", "plan": "برنامهٔ اقدام: سبد هدف منهای پرتفوی فعلی ⇒ سفارش خرید و فروش با تعداد، قیمت مرجع و مشارکت در ارزش معاملات؛ خروجی CSV و JSON برای سامانهٔ الگوریتمی. کلید A.", "live": "دفتر زندهٔ استراتژی قفل\u200cشده (نمونهٔ بیرونی): مشخصات و هش، آمار درون\u200cنمونه، دستورهای ثبت\u200cشده و رهگیری برتری واقعی پس از هر ریبالانس رسمی.", "pf": "سبد هدف یک صندوق شاخصی با اندازهٔ دلخواه: مبلغ و تعداد سهم هر نماد و تعداد روز لازم برای خرید با توجه به نقدشوندگی.", "fnd": "صندوق\u200cهای شاخصی بورس در برابر شاخص مرجعشان: خطای ردیابی، تفاوت بازده، سهم تأخیر سود و فاصلهٔ قیمت بازار با NAV.", "qa": "کنترل کیفیت داده: بازسازی هر شاخص صنعت در برابر سری رسمی، خطاهای شناخته\u200cشده و جهان سهام استفاده\u200cشده.", "sym": "صفحهٔ هر نماد: بازده کل و قیمت تعدیل\u200cشده، سودهای نقدی، افزایش سرمایه\u200cها، مجامع و مشخصات.", "rep": "خلاصهٔ نتایج قابل چاپ، تاریخچهٔ تغییرات روش\u200cشناسی و فهرست فصل\u200cهای سند و ابزارها."};
const SEC_OF = {}; SECTIONS.forEach(sc => sc.views.forEach(([k]) => { SEC_OF[k] = sc.id; }));
const LEGACY = { fac: 'lab' };                                          // پیوندهای قدیمی (Factor Lab حذف شد)
function renderSubnav(name) {
  const sc = SECTIONS.find(x => x.id === SEC_OF[name]); if (!sc) return;
  $('subnav').innerHTML = sc.views.map(([k, t]) => `<a href="#${k}" data-view="${k}"${SUBTIP[k] ? ` data-tip="${SUBTIP[k]}"` : ''}${k === name ? ' aria-current="page"' : ''}>${t}</a>`).join('') + `<span class="why" data-tip="مسیر کار این بخش، به ترتیب گام‌ها.">${sc.why}</span>`;
  $('subnav').querySelectorAll('a').forEach(a => a.addEventListener('click', e => { e.preventDefault(); show(a.dataset.view); }));
}
function show(name) {
  name = LEGACY[name] || name;
  if (!VIEWS[name]) return;
  Object.entries(VIEWS).forEach(([k, id]) => { $(id).hidden = k !== name; });
  document.querySelectorAll('#nav a').forEach(a => { if (a.dataset.sec === SEC_OF[name]) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  renderSubnav(name); LS.set('last.' + SEC_OF[name], name);
  if (X && INIT[name] && !inited[name]) { inited[name] = true; INIT[name](); }
  requestAnimationFrame(() => { if (name === 'index') drawChart(); else if (redraws[name]) redraws[name](); else if (NV[name] && NV[name].redraw) NV[name].redraw(); });
  window.SIM_CUR = name;
  history.replaceState(null, '', '#' + name); LS.set('view', name);
}
window.SIM_SHOW = show;
document.querySelectorAll('#nav a').forEach(a => a.addEventListener('click', e => { e.preventDefault(); const sc = SECTIONS.find(x => x.id === a.dataset.sec); const last = LS.get('last.' + sc.id); show(last && SEC_OF[last] === sc.id ? last : sc.views[0][0]); }));
addEventListener('keydown', e => {
  if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName) || e.ctrlKey || e.metaKey) return;
  const n = '12345'.indexOf(e.key); if (n >= 0) { const sc = SECTIONS[n], last = LS.get('last.' + sc.id); show(last && SEC_OF[last] === sc.id ? last : sc.views[0][0]); }
  const lk = { l: 'lab', g: 'sig', a: 'plan' }[e.key.toLowerCase()]; if (lk && VIEWS[lk]) show(lk);
});
const _run = window.run;
window.run = function (cmd) {
  const [c, a] = cmd.trim().toLowerCase().split(/\s+/);
  if (c === 'go' || c === 'view') { if (VIEWS[LEGACY[a] || a]) { show(a); toast('نما: ' + (LEGACY[a] || a)); } else toast('نما: ' + Object.keys(VIEWS).join(' · ')); return; }
  if (c === 'help') { toast('GO LAB|SIG|INDEX|SAM|DIV|REB|RISK|PLAN|LIVE|PF|FND|QA|SYM|REP · SYM <نماد> · IDX K|EW · WIN 2014|2016 · THEME · DENSITY · ↑↓ تاریخچه · کلید ۱–۵ بخش‌ها'); return; }
  if (c === 'sym' && a) { window.openSym(cmd.trim().split(/\s+/)[1]); return; }
  if (c === 'density') { $('density').click(); return; }
  if (c === 'idx' || c === 'win') show('index');
  _run(cmd);
  if (c === 'theme') { LS.set('theme', document.documentElement.dataset.theme); const v = Object.keys(VIEWS).find(k => !$(VIEWS[k]).hidden); if (v && redraws[v]) redraws[v](); }
};
new ResizeObserver(() => { const v = Object.keys(VIEWS).find(k => !$(VIEWS[k]).hidden); if (v && redraws[v]) redraws[v](); }).observe(document.body);
const want0 = (location.hash || '').slice(1) || LS.get('view') || 'index', want = LEGACY[want0] || want0;
show(want in VIEWS ? want : 'index');
})();
