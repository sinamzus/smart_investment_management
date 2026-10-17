/* SIM — نماهای دوم: Dividend Lab · Factor Lab · Rebalance · Data QA · Reports
   داده: window.SIM_EXTRA (tools/build_ui_extra.py) و window.SIM_DATA. هیچ عدد ثابتی در این فایل نیست مگر متن توضیحی. */
(function () {
const X = window.SIM_EXTRA;
const VIEWS = { index: 'v-index', div: 'v-div', fac: 'v-fac', reb: 'v-reb', qa: 'v-qa', rep: 'v-rep', sym: 'v-sym', pf: 'v-pf', risk: 'v-risk', fnd: 'v-fnd' };
const JM = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
const inited = {}, redraws = {};
const jyear = new Intl.DateTimeFormat('fa-IR-u-ca-persian-nu-latn', { year: 'numeric' });
const cls = v => v == null ? '' : v >= 0 ? 'up' : 'down';
const chipTE = t => t == null ? '' : t < 1 ? 'ok' : t < 3 ? 'warn' : 'bad';

if (!X) {
  ['v-div', 'v-fac', 'v-reb', 'v-qa', 'v-rep', 'v-pf', 'v-risk'].forEach(id => { $(id).innerHTML = '<p style="padding:24px">ui/data/extra.js پیدا نشد. اجرا کنید: <code>python tools/build_ui_extra.py</code></p>'; });
}

/* ── نمودار چندپنلی ───────────────────────────────────── */
function paneChart(svg, dates, panes, st) {
  const W = svg.clientWidth || 800, H = svg.clientHeight || 300, m = { l: 8, r: 58, t: 30, b: 20 }, gap = 18;
  const N = dates.length, avail = H - m.t - m.b - gap * (panes.length - 1);
  const x = i => m.l + (W - m.l - m.r) * i / (N - 1);
  let out = '', top = m.t;
  panes.forEach(p => {
    const h = avail * p.frac, vals = p.series.flatMap(s => s.v.filter(v => v != null && isFinite(v)));
    let lo = Math.min(...vals), hi = Math.max(...vals);
    if (p.zero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
    const T = p.log ? Math.log : (v => v);
    const a = T(lo), b = T(hi), pad = (b - a) * .06 || 1;
    const y = v => top + h * (1 - (T(v) - (a - pad)) / ((b - a) + 2 * pad));
    let tv = [];
    if (p.log) { for (let e = Math.floor(Math.log10(lo)) - 1; e <= Math.ceil(Math.log10(hi)) + 1; e++) [1, 2, 5].forEach(mu => { const v = mu * 10 ** e; if (v >= lo * 0.97 && v <= hi * 1.03) tv.push(v); }); if (tv.length > 6) tv = tv.filter(v => Math.abs(Math.log10(v) - Math.round(Math.log10(v))) < 1e-9); }
    else { const raw = (hi - lo) / 4 || 1, p10 = 10 ** Math.floor(Math.log10(raw)), step = [1, 2, 2.5, 5, 10].map(q => q * p10).find(q => q >= raw); for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) tv.push(Math.abs(v) < 1e-9 ? 0 : v); }
    tv.forEach(v => { const yy = y(v); out += `<line class="grid" x1="${m.l}" x2="${W - m.r}" y1="${yy}" y2="${yy}"/><text x="${W - m.r + 6}" y="${yy + 3}">${p.fmt ? p.fmt(v) : fmt(v, 1)}</text>`; });
    if (p.zero) { const z = y(0); out += `<line class="axis" x1="${m.l}" x2="${W - m.r}" y1="${z}" y2="${z}"/>`; }
    p.series.forEach(s => {
      let d = '', pen = false;
      s.v.forEach((v, i) => { if (v == null || !isFinite(v)) { pen = false; return; } d += (pen ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(v).toFixed(1); pen = true; });
      out += `<path d="${d}" fill="none" stroke="${s.color}" stroke-width="${s.w || 1.4}" ${s.dash ? 'stroke-dasharray="3 2"' : ''}/>`;
    });
    top += h + gap;
  });
  let last = null, tk = '';
  dates.forEach((d, i) => { const k = jyear.format(new Date(d + 'T00:00:00Z')); if (k !== last) { last = k; const xx = x(i); if (xx > m.l + 24 && xx < W - m.r - 10) tk += `<line class="axis" x1="${xx}" x2="${xx}" y1="${H - m.b}" y2="${H - m.b + 4}"/><text x="${xx}" y="${H - 5}" text-anchor="middle">${k}</text>`; } });
  const hv = st && st.i != null ? `<line class="axis" x1="${x(st.i)}" x2="${x(st.i)}" y1="${m.t}" y2="${H - m.b}" stroke-dasharray="2 2"/>` : '';
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.innerHTML = out + tk + hv;
  svg._geom = { m, W, N };
}
function attachHover(svg, draw, onIdx) {
  svg.addEventListener('mousemove', e => {
    const g = svg._geom; if (!g) return; const r = svg.getBoundingClientRect(), px = (e.clientX - r.left) * (g.W / r.width);
    const i = Math.max(0, Math.min(g.N - 1, Math.round((px - g.m.l) / (g.W - g.m.l - g.m.r) * (g.N - 1)))); onIdx(i);
  });
  svg.addEventListener('mouseleave', () => onIdx(null));
}
function bars(el, labels, values, f, mark) {
  const mx = Math.max(...values.map(v => Math.abs(v || 0)), 1e-9);
  el.innerHTML = values.map((v, i) => `<div class="b" style="height:${Math.max(1, Math.abs(v || 0) / mx * 78)}%;${mark && mark(i, v) ? 'background:var(--lg-c)' : ''}"><em>${f(v)}</em><span>${labels[i]}</span></div>`).join('');
}

/* ══════════ Dividend Lab ══════════ */
const dv = { k: 'K', s: 'A', lag: 90, rb: 25, i: null, cur: null };
function divSim(ds, tr, pr, lag, rb) {
  const n = tr.length, day = ds.map(d => Date.parse(d) / 864e5), pay = new Int32Array(n), due = new Float64Array(n + 1), nav = new Float64Array(n);
  let k = 0; for (let t = 0; t < n; t++) { if (k < t) k = t; while (k < n && day[k] < day[t] + lag) k++; pay[t] = k; }
  let V = 1, A = 0, B = 0;
  for (let t = 0; t < n; t++) {
    const dd = t ? day[t] - day[t - 1] : 0;
    if (rb != null && B > 0) V -= B * rb * dd / 365;
    V *= 1 + pr[t];
    const y = tr[t] - pr[t];
    if (y !== 0) { const amt = V * y / (1 + pr[t]); due[pay[t]] += amt; A += amt; if (rb != null) { V += amt; B += amt; } }
    const p = due[t]; if (p !== 0) { A -= p; if (rb != null) B -= p; else V += p; }
    nav[t] = V + A - B;
  }
  return nav;
}
function divCompute() {
  const S = X.divlab[dv.k], rb = dv.s === 'B' ? dv.rb / 100 : null;
  const nav = divSim(S.dates, S.tr, S.pr, dv.lag, rb), n = nav.length;
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
    { frac: .68, log: true, series: [{ v: trl, color: 'var(--ch-2)', w: 1.6 }, { v: nav, color: 'var(--ch-1)', w: 1.1 }], fmt: v => fmt(v, 0) },
    { frac: .32, zero: true, series: [{ v: gp, color: 'var(--ch-3)', dash: true }], fmt: v => fmt(v, 1) + '%' }], dv);
  $('dv-readout').innerHTML = dv.i == null ? '' : `<b>${S.dates[dv.i]}</b> · ${jd(S.dates[dv.i])} &nbsp; TR نظری <b>${fmt(trl[dv.i], 1)}</b> &nbsp; NAV <b>${fmt(nav[dv.i], 1)}</b> &nbsp; شکاف <b>${sgn(gp[dv.i], 2)}%</b>`;
}
function divRender() {
  divCompute(); const c = dv.cur, S = c.S;
  $('dv-lag-o').textContent = dv.lag; $('dv-rb-o').textContent = dv.rb;
  $('dv-rb-w').style.display = dv.s === 'B' ? '' : 'none';
  document.querySelectorAll('#dv-idx button').forEach(b => b.setAttribute('aria-pressed', b.dataset.k === dv.k));
  document.querySelectorAll('#dv-str button').forEach(b => b.setAttribute('aria-pressed', b.dataset.s === dv.s));
  $('dv-title').textContent = (dv.k === 'K' ? 'شاخص كل' : 'كل (هم وزن)') + ' · ماکت سرمایه‌پذیر با تأخیر پرداخت سود';
  $('dv-kpis').innerHTML = [['تفاوت ردیابی سالانه', sgn(c.gap, 2) + '%', cls(c.gap)], ['نسبت سطح نهایی NAV / TR', fmt(c.ratio, 3), c.ratio >= 1 ? 'up' : 'down'],
    ['خطای ردیابی (TE سالانه)', fmt(c.te, 2) + '%', ''], ['سود نقدی ضمنی سالانه', fmt(S.y_ann_pct, 1) + '%', ''], ['بازه', S.from.slice(0, 4) + '→' + S.to.slice(0, 4), '']]
    .map(([k, v, cl]) => `<div class="kpi"><div class="k">${k}</div><div class="v ${cl}">${v}</div></div>`).join('');
  $('dv-lineage').innerHTML = `<span><b>مدل</b> NAV = ارزش پرتفوی + مطالبات سود − وام؛ سود روز استحقاق = TR − PR رسمی، پرداخت L روز بعد</span><span><b>L = ۰</b> دقیقاً TR رسمی (تأییدکنندهٔ مدل)</span><span><b>فرض</b> تأخیر یکسان L برای همهٔ شرکت‌ها و نرخ وام ثابت در کل دوره</span><span><b>روش‌شناسی</b> فصل ۰۳ §۳٫۵</span>`;
  // سناریوهای ثابت
  const near = S.scenarios.reduce((b, r) => Math.abs(r.lag - dv.lag) < Math.abs(b.lag - dv.lag) ? r : b);
  $('dv-scen').innerHTML = th([['L (روز)', 'n'], ['A: بدون وام — فاصله %/سال', 'n'], ['A: TE %', 'n'], ['B ۲۵٪ — فاصله', 'n'], ['B ۲۵٪ — TE', 'n'], ['B ۳۵٪ — فاصله', 'n'], ['B ۳۵٪ — TE', 'n']]) +
    '<tbody>' + S.scenarios.map(r => `<tr ${r === near ? 'aria-selected="true"' : ''}><td class="n">${r.lag}</td><td class="n ${cls(r.A.gap_pct_yr)}">${sgn(r.A.gap_pct_yr)}</td><td class="n">${fmt(r.A.te_pct)}</td><td class="n ${cls(r.B25.gap_pct_yr)}">${sgn(r.B25.gap_pct_yr)}</td><td class="n">${fmt(r.B25.te_pct, 3)}</td><td class="n ${cls(r.B35.gap_pct_yr)}">${sgn(r.B35.gap_pct_yr)}</td><td class="n">${fmt(r.B35.te_pct, 3)}</td></tr>`).join('') + '</tbody>';
  $('dv-lin-b').innerHTML = `<span>${dv.k === 'K' ? 'شاخص كل' : 'هم‌وزن'} · نسبت به TR نظری رسمی</span><span><b>خوانش</b> وام TE را تقریباً صفر می‌کند چون هزینه‌اش قطعی است (نرخ × سود × L/۳۶۵)؛ میانگین بهتر فقط اگر نرخ وام < بازده بازار</span>`;
  bars($('dv-bars'), JM.map(m => m.slice(0, 5)), S.month_share, v => fmt(v, 0), (i, v) => v === Math.max(...S.month_share));
  $('dv-lin-c').innerHTML = `<span><b>خوانش</b> سود در ${JM[S.month_share.indexOf(Math.max(...S.month_share))]} متمرکز است؛ تأخیر در همین ماه‌ها بیشترین مبلغ را معلق می‌کند</span><span><b>منبع</b> y = r<sub>TR</sub> − r<sub>PR</sub> رسمی</span>`;
  divDraw();
}
function divPayPanel() {
  const p = X.divlab.payment_data;
  $('dv-pay-chip').textContent = p.rows + ' زمان‌بندی · ' + p.agm_rows + ' مجمع';
  $('dv-pay').innerHTML = `<div class="note">تاریخ مجمع و سود هر سهم از ${p.agm_rows} مصوبهٔ مجمع کدال خوانده شده و با تعدیل قیمت TSETMC تطبیق کامل دارد. تاریخ پرداخت در نامه‌های «زمان‌بندی پرداخت سود» (${p.rows} نامه) به‌صورت پیوست تصویری منتشر می‌شود و در این نسخه به داده تبدیل نشده است؛ بنابراین مدل بالا تأخیر یکسان L را برای همهٔ شرکت‌ها به کار می‌برد.
    منبع: کدال، «زمان‌بندی پرداخت سود» (ن-۱۳) و «تصمیمات مجمع عادی سالیانه» (ن-۵۲).</div>
    <div class="prose"><b>به‌روزرسانی داده (روی سیستم شما؛ قابل‌ادامه پس از قطع):</b><div class="cmdline">python tools/fetch_dividend_payments.py --collect 30 --years 5 --log collect.txt\npython tools/fetch_dividend_payments.py --parse\ngit add -A; git commit -m "codal collect"; git push -u origin claude/charming-ptolemy-cyehmc</div>
    خروجی: <code>data/corporate_actions/codal_agm.csv</code> (${p.agm_rows} ردیف) و <code>codal_payment_schedule_raw.csv</code> (${p.rows} ردیف).</div>`;
}
function initDiv() {
  document.querySelectorAll('#dv-idx button').forEach(b => b.onclick = () => { dv.k = b.dataset.k; divRender(); });
  document.querySelectorAll('#dv-str button').forEach(b => b.onclick = () => { dv.s = b.dataset.s; divRender(); });
  $('dv-lag').oninput = e => { dv.lag = +e.target.value; divRender(); };
  $('dv-rb').oninput = e => { dv.rb = +e.target.value; divRender(); };
  attachHover($('dv-chart'), divDraw, i => { dv.i = i; divDraw(); });
  $('dv-csv').onclick = () => { const c = dv.cur; download(`div_lab_${dv.k}_L${dv.lag}${dv.s === 'B' ? '_rb' + dv.rb : ''}.csv`, [['date', 'tr_theory', 'nav', 'gap_pct'], ...c.S.dates.map((d, i) => [d, (c.trL[i] * 100).toFixed(3), (c.nav[i] * 100).toFixed(3), ((c.nav[i] / c.trL[i] - 1) * 100).toFixed(3)])]); };
  $('dv-csv-b').onclick = () => download(`div_scenarios_${dv.k}.csv`, [['lag', 'A_gap', 'A_te', 'B25_gap', 'B25_te', 'B35_gap', 'B35_te'], ...X.divlab[dv.k].scenarios.map(r => [r.lag, r.A.gap_pct_yr, r.A.te_pct, r.B25.gap_pct_yr, r.B25.te_pct, r.B35.gap_pct_yr, r.B35.te_pct])]);
  divPayPanel(); redraws.div = divDraw; divRender();
}

/* ══════════ Factor Lab ══════════ */
const facState = { i: null, sig: 'mom', cost: 100 };
const FAC_LAB = {
  mom: { title: 'مومنتوم ۱۲−۱ · پنج‌گانه‌ها', Q1: 'پنجک ۱ (ضعیف‌ترین مومنتوم)', Q5: 'پنجک ۵ (قوی‌ترین مومنتوم)', file: 'momentum' },
  lowvol: { title: 'کم‌نوسان ۲۵۲ روزه · پنج‌گانه‌ها', Q1: 'پنجک ۱ (پرنوسان‌ترین)', Q5: 'پنجک ۵ (کم‌نوسان‌ترین)', file: 'lowvol' }
};
function initFac() {
  document.querySelectorAll('#fc-sig button').forEach(b => b.onclick = () => { facState.sig = b.dataset.s; facState.i = null; renderFacSig(); });
  $('fc-cost').oninput = e => { facState.cost = Math.max(0, +e.target.value || 0); renderFacSig(); };
  renderFacSig();
}
/* آمار یک سری ماهانه (اعشاری) */
function mstats(x) {
  const n = x.length, mu = x.reduce((a, b) => a + b, 0) / n, e = x.map(v => v - mu);
  const sd = Math.sqrt(e.reduce((a, b) => a + b * b, 0) / (n - 1));
  let v = e.reduce((a, b) => a + b * b, 0) / n;                      // نیوی‌وست، ۳ وقفه
  for (let l = 1; l <= 3; l++) { let g = 0; for (let t = l; t < n; t++) g += e[t] * e[t - l]; v += 2 * (1 - l / 4) * g / n; }
  let c = 1, pk = 1, mdd = 0; x.forEach(r => { c *= 1 + r; pk = Math.max(pk, c); mdd = Math.min(mdd, c / pk - 1); });
  return { mu, sd, ann: (Math.pow(c, 12 / n) - 1) * 100, vol: sd * Math.sqrt(12) * 100, t: mu / Math.sqrt(v / n), ir: mu / sd * Math.sqrt(12), hit: x.filter(r => r > 0).length / n * 100, mdd: mdd * 100 };
}
function facNet(F, bp = facState.cost) {
  const M = F.monthly, c = bp / 1e4, Q = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'ALL'], net = {}, to = {};
  Q.forEach(q => { net[q] = M[q].map((g, i) => g / 100 - (M.to[q][i] || 0) / 100 * c); to[q] = M.to[q].reduce((a, b) => a + (b || 0), 0); });
  const yrs = (Date.parse(M.end[M.end.length - 1]) - Date.parse(M.end[0])) / 864e5 / 365.25 + 1 / 12;
  return { net, yrs, toAnn: Object.fromEntries(Q.map(q => [q, to[q] / yrs])), ex: net.Q5.map((v, i) => v - net.ALL[i]), ls: net.Q5.map((v, i) => v - net.Q1[i]) };
}
function renderFacSig() {
  document.querySelectorAll('#fc-sig button').forEach(b => b.setAttribute('aria-pressed', b.dataset.s === facState.sig));
  const qual = facState.sig === 'quality';
  $('fc-ctl').hidden = qual;
  if (qual) {
    $('fc-title').textContent = 'کیفیت'; $('fc-chip').textContent = 'دادهٔ بنیادی لازم است';
    ['fc-kpis', 'fc-legend', 'fc-chart', 'fc-bars', 'fc-year', 'fc-stats', 'fc-lineage', 'fc-lin-b'].forEach(k => $(k).innerHTML = ''); redraws.fac = null;
    $('fc-method').innerHTML = `<p><b>وضعیت:</b> فاکتور کیفیت (سودآوری، اهرم، ثبات سود — مطابق روش MSCI Quality، فصل ۱۱) بر صورت‌های مالی بنا می‌شود. منبع آن صورت‌های مالی میاندوره‌ای و سالانهٔ کدال (ن-۱۰) است که هنوز در مخزن نیست؛ به همین دلیل این نما عددی نشان نمی‌دهد.</p>
    <p><b>تعریف هدف:</b> امتیاز Z ترکیبی از بازده حقوق صاحبان سهام (ROE)، نسبت بدهی به حقوق صاحبان سهام (کمتر بهتر) و انحراف معیار رشد سود هر سهم در ۵ سال (کمتر بهتر)؛ پنج‌گانه‌ها و آزمون‌ها مثل مومنتوم و کم‌نوسان.</p>`;
    return;
  }
  const F = facState.sig === 'mom' ? X.factor : X.factor_lowvol, L = FAC_LAB[facState.sig];
  $('fc-title').textContent = L.title;
  $('fc-chip').textContent = `بک‌تست ماهانه · ${F.n_months} ماه · خالص هزینه`;
  renderFac(F, L);
}
function renderFac(F, L) {
  const N = facNet(F), M = F.monthly, S = { Q5ALL: mstats(N.ex), Q5Q1: mstats(N.ls) };
  const ann = q => mstats(N.net[q]).ann, cost = facState.cost;
  const col = { Q1: 'var(--down)', Q3: 'var(--ch-3)', Q5: 'var(--up)', ALL: 'var(--ch-2)' }, lab = { Q1: L.Q1, Q3: 'پنجک ۳', Q5: L.Q5, ALL: 'همهٔ واجدان شرایط (هم‌وزن)' };
  const sig = Math.abs(S.Q5ALL.t) >= 1.96;
  $('fc-kpis').innerHTML = [['پنجک ۵ نسبت به همه (سالانه)', sgn(ann('Q5') - ann('ALL'), 1) + '%', cls(ann('Q5') - ann('ALL'))], ['آمارهٔ t نیوی‌وست', fmt(S.Q5ALL.t, 2), sig ? cls(S.Q5ALL.t) : ''], ['نسبت اطلاعات (IR)', fmt(S.Q5ALL.ir, 2), ''], ['نرخ برد ماهانه', fmt(S.Q5ALL.hit, 0) + '%', ''], ['گردش سالانهٔ پنجک ۵', fmt(N.toAnn.Q5, 0) + '%', '']]
    .map(([k, v, cl]) => `<div class="kpi"><div class="k">${k}</div><div class="v ${cl}">${v}</div></div>`).join('');
  $('fc-legend').innerHTML = ['Q1', 'Q3', 'Q5', 'ALL'].map(q => `<span><i style="color:${col[q]}"></i>${lab[q]}</span>`).join('') + '<span class="readout" id="fc-readout"></span>';
  const curve = {}; ['Q1', 'Q3', 'Q5', 'ALL'].forEach(q => { let c = 100; curve[q] = [100, ...N.net[q].map(r => (c *= 1 + r))]; });
  const dates = [F.from, ...M.end], st = facState;
  const draw = () => { paneChart($('fc-chart'), dates, [{ frac: 1, log: true, series: ['Q1', 'Q3', 'Q5', 'ALL'].map(q => ({ v: curve[q], color: col[q], w: q === 'ALL' ? 1.6 : 1.2 })), fmt: v => fmt(v, 0) }], st);
    $('fc-readout').innerHTML = st.i == null ? '' : `<b>${dates[st.i]}</b> &nbsp; Q1 <b>${fmt(curve.Q1[st.i], 0)}</b> &nbsp; Q5 <b>${fmt(curve.Q5[st.i], 0)}</b> &nbsp; همه <b>${fmt(curve.ALL[st.i], 0)}</b>`; };
  if (!$('fc-chart')._hov) { $('fc-chart')._hov = true; attachHover($('fc-chart'), null, i => { facState.i = i; redraws.fac && redraws.fac(); }); }
  redraws.fac = draw; draw();
  $('fc-lineage').innerHTML = `<span><b>بازه</b> <span class="num">${F.from}</span> → <span class="num">${F.to}</span></span><span><b>بازده</b> TR، خرید و نگهداری در ماه</span><span><b>هزینه</b> ${cost} bp رفت‌وبرگشت × گردش واقعی</span><span><b>مبنا</b> فصل ۰۴ · ۰۵</span>`;
  const q = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'ALL'];
  bars($('fc-bars'), ['۱', '۲', '۳', '۴', '۵', 'همه'], q.map(ann), v => fmt(v, 1), i => i === 5);
  $('fc-lin-b').innerHTML = `<span><b>میانگین نماد</b> در هر پنجک ≈ ${F.avg_names.Q1} · کل واجد ≈ ${F.avg_names.ALL}</span><span><b>نوسان سالانه</b> ${['Q1', 'Q5', 'ALL'].map(k => (k === 'ALL' ? 'همه' : k) + ' ' + fmt(mstats(N.net[k]).vol, 1) + '٪').join(' · ')}</span>`;
  const by = {}; M.end.forEach((d, i) => { const y = jyear.format(new Date(d + 'T00:00:00Z')); (by[y] = by[y] || []).push(i); });
  const cmp = (arr, ix) => (ix.reduce((c, i) => c * (1 + arr[i]), 1) - 1) * 100;
  $('fc-year').innerHTML = th([['سال شمسی'], ['پنجک ۱ %', 'n'], ['پنجک ۵ %', 'n'], ['همه %', 'n'], ['۵ − همه', 'n'], ['۵ − ۱', 'n'], ['ماه', 'n']]) + '<tbody>' + Object.entries(by).map(([y, ix]) => {
    const a = cmp(N.net.Q1, ix), b = cmp(N.net.Q5, ix), c = cmp(N.net.ALL, ix);
    return `<tr><td class="num">${y}</td><td class="n ${cls(a)}">${sgn(a, 1)}</td><td class="n ${cls(b)}">${sgn(b, 1)}</td><td class="n ${cls(c)}">${sgn(c, 1)}</td><td class="n ${cls(b - c)}">${sgn(b - c, 1)}</td><td class="n ${cls(b - a)}">${sgn(b - a, 1)}</td><td class="n mute">${ix.length}</td></tr>`; }).join('') + '</tbody>';
  const half = Math.floor(N.ex.length / 2), h1 = mstats(N.ex.slice(0, half)), h2 = mstats(N.ex.slice(half));
  const row = (k, s) => `<tr><td>${k}</td><td class="n ${cls(s.mu)}">${sgn(s.mu * 100, 2)}</td><td class="n ${cls(s.ann)}">${sgn(s.ann, 1)}</td><td class="n">${fmt(s.vol, 1)}</td><td class="n ${Math.abs(s.t) >= 1.96 ? cls(s.t) : ''}">${fmt(s.t, 2)}</td><td class="n">${fmt(s.ir, 2)}</td><td class="n">${fmt(s.hit, 0)}</td><td class="n down">${fmt(s.mdd, 1)}</td></tr>`;
  $('fc-stats').innerHTML = th([['سری (خالص)'], ['میانگین ماهانه %', 'n'], ['سالانه %', 'n'], ['نوسان %', 'n'], ['t نیوی‌وست', 'n'], ['IR', 'n'], ['برد %', 'n'], ['بیشترین افت %', 'n']]) + '<tbody>' +
    row('پنجک ۵ − همه', S.Q5ALL) + row('پنجک ۵ − پنجک ۱', S.Q5Q1) + row(`نیمهٔ اول (تا ${M.end[half - 1]})`, h1) + row('نیمهٔ دوم', h2) + '</tbody>';
  const sigTxt = sig ? `در سطح ۵٪ معنادار است (|t| ≥ ۱٫۹۶)` : `در سطح ۵٪ معنادار نیست (|t| = ${fmt(Math.abs(S.Q5ALL.t), 2)} < ۱٫۹۶)`;
  const sign = S.Q5ALL.mu >= 0 ? 'بیشتر' : 'کمتر';
  $('fc-method').innerHTML = `<p><b>نتیجه:</b> پنجک ۵ پس از ${cost} bp هزینهٔ رفت‌وبرگشت، سالانه ${fmt(Math.abs(ann('Q5') - ann('ALL')), 1)} واحد درصد ${sign} از سبد هم‌وزن همهٔ واجدان شرایط بازده داده است؛ این تفاوت ${sigTxt}. ${facState.sig === 'lowvol' ? `نوسان پنجک ۵ (${fmt(mstats(N.net.Q5).vol, 1)}٪) از همه (${fmt(mstats(N.net.ALL).vol, 1)}٪) کمتر است؛ کاهش ریسک برقرار است حتی اگر بازده اضافه معنادار نباشد.` : 'الگوی پنجک‌ها کوهان‌شکل است: قوی‌ترین مومنتوم از میانهٔ بازار ضعیف‌تر است.'}</p>
  <ol><li><b>سیگنال:</b> ${facState.sig === 'mom' ? 'بازدهٔ لگاریتمی TR از ۲۵۲ تا ۲۱ روز معاملاتی پیش از آخرین روز هر ماه شمسی (ماه آخر کنار گذاشته می‌شود).' : 'انحراف معیار بازدهٔ روزانهٔ TR در ۲۵۲ روز معاملاتی پیش از آخرین روز هر ماه شمسی؛ پنجک ۵ کم‌نوسان‌ترین است.'}</li>
  <li><b>واجد شرایط:</b> دست‌کم ۸۰٪ روزهای پنجره داده و دست‌کم ۵۰٪ روزهایی با بازده غیرصفر (حذف نمادهای عملاً متوقف)، و دادهٔ روز بعد.</li>
  <li><b>سبد:</b> هم‌وزن درون هر پنجک در روز ریبالانس (آخرین روز معاملاتی هر ماه شمسی)؛ تا ریبالانس بعد وزن‌ها با بازده رانش می‌کنند (خرید و نگهداری).</li>
  <li><b>هزینه:</b> گردش یک‌طرفهٔ واقعی هر ماه (½ Σ|وزن هدف − وزن رانش‌یافته|) × هزینهٔ رفت‌وبرگشت ورودی؛ ساخت اولیه حساب نمی‌شود. همین هزینه به سبد «همه» هم اعمال می‌شود.</li>
  <li><b>آزمون:</b> t با خطای معیار نیوی‌وست (۳ وقفه) چون بازده ماهانهٔ بازار ایران خودهمبستگی مثبت دارد؛ سالانه‌سازی بازده با ۱۲ ماه، نوسان با √۱۲.</li>
  <li><b>بازه:</b> از ۱۳۹۵/۰۱؛ سیگنال از ۲۰۱۵ ساخته می‌شود.</li></ol>
  <p><b>محدودیت‌ها:</b> جهان شامل اعضای فعلی «شاخص كل» و ${X.qa.universe.extras} نماد حذف‌شدهٔ بازیابی‌شده است، نه همهٔ نمادهای تاریخی؛ «پنجک ۵ − پنجک ۱» به فروش استقراضی نیاز دارد که در بورس تهران عملاً در دسترس نیست و فقط شاخص تشخیصی فاکتور است؛ مدل هزینه خطی است و صف خرید/فروش و دامنهٔ نوسان را در نظر نمی‌گیرد (فصل ۶).</p>`;
  $('fc-csv').onclick = () => download(`factor_${L.file}_monthly_net_${cost}bp.csv`, [['month_end', 'Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'ALL', 'to_Q5_pct', 'to_ALL_pct'], ...M.end.map((d, i) => [d, ...q.map(k => (N.net[k][i] * 100).toFixed(3)), M.to.Q5[i] ?? '', M.to.ALL[i] ?? ''])]);
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
  $('qa-gaps').innerHTML = `<b>باز و شناخته‌شده</b><ul>
  <li><b>صنعت ۳۴ خودرو:</b> TE ۳٫۲٪ (همبستگی ۰٫۹۹۶)؛ فرضیهٔ زمان‌بندی/سهام شناور/توقف/فرابورس رد شد؛ خطا پراکنده است.</li>
  <li><b>تاریخ پرداخت سود:</b> ${X.divlab.payment_data.agm_rows} مصوبهٔ مجمع و ${X.divlab.payment_data.rows} نامهٔ زمان‌بندی پرداخت از کدال جمع‌آوری شد؛ متن زمان‌بندی‌ها عمدتاً تصویر اسکن‌شده است، پس Dividend Lab با تأخیر یکسان L محاسبه می‌کند.</li>
  <li><b>هم‌وزن TR رسمی:</b> نسبت سطح بازسازی به رسمی ${fmt(D.stats.EW.all.cum_ratio, 3)}؛ تفاوت از تفکیک سود و افزایش سرمایه در رویدادهای ترکیبی است.</li>
  <li><b>سهام کاملاً حذف‌شده:</b> فقط آن‌هایی که با جست‌وجوی نام صنعت پیدا شده‌اند (۱۳۶ نماد extras)؛ جهان کامل نیست.</li>
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
    ...[['مومنتوم ۱۲−۱', X.factor], ['کم‌نوسان ۲۵۲ روزه', X.factor_lowvol]].map(([n, G]) => { const N = facNet(G, 100), s = mstats(N.ex), a = mstats(N.net.Q5).ann - mstats(N.net.ALL).ann;
      return [n + ' (خالص ۱۰۰ bp)', `پنجک ۵ نسبت به همه ${sgn(a, 1)}٪ در سال · t نیوی‌وست ${fmt(s.t, 2)} · ${Math.abs(s.t) >= 1.96 ? 'معنادار' : 'غیرمعنادار'} در سطح ۵٪`, 'فصل ۵']; })];
  $('rp-sum').innerHTML = th([['نتیجه'], ['مقدار'], ['مرجع']]) + '<tbody>' + rows.map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td><td class="mute">${r[2]}</td></tr>`).join('') + '</tbody>';
  $('rp-text').innerHTML = `<b>وضعیت.</b> داده تا <span class="num">${D.meta.asof}</span>؛ ${fmt(D.meta.n_price_rows, 0)} ردیف قیمت. مرجع‌ها: «شاخص كل» و «كل (هم وزن)» رسمی. ماکت سرمایه‌پذیر با بازتولید کامل و بدون سقف سرمایه/وزن؛ تنها شکاف ساختاری، تأخیر پرداخت سود است و با تأخیر یکسان L مدل می‌شود. فاکتورها با بک‌تست ماهانهٔ خالص هزینه و آزمون نیوی‌وست سنجیده می‌شوند؛ بازده‌ها با سال تقویمی سالانه شده‌اند. «چاپ» ← PDF.`;
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
    attachHover($('sy-chart'), null, i => { sy.i = i; drawSym(); });
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
  $('sy-chip').textContent = d.alive ? 'عضو «شاخص كل»' : 'حذف‌شده/غیرفعال تا ' + d.last; $('sy-chip').className = 'chip ' + (d.alive ? 'ok' : 'warn');
  $('sy-kpis').innerHTML = [['بازده ۱ سال', sgn(d.ret1y, 1) + '%', cls(d.ret1y)], ['بازده سالانهٔ ۳ سال', d.ret3y_ann == null ? '—' : sgn(d.ret3y_ann, 1) + '%', cls(d.ret3y_ann)], ['نوسان ۱ سال', fmt(d.vol1y, 1) + '%', ''], ['افت از اوج (از ۲۰۱۴)', fmt(d.mdd, 1) + '%', 'down'], ['بتا به «شاخص كل»', d.beta1y == null ? '—' : fmt(d.beta1y, 2), '']]
    .map(([k, v, c]) => `<div class="kpi"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`).join('');
  const divs = d.events.filter(e => e[1] === 'div').length, caps = d.events.length - divs;
  $('sy-ev-chip').textContent = `${divs} سود · ${caps} سرمایه`;
  $('sy-ev').innerHTML = th([['تاریخ'], ['نوع'], ['قیمت قبل (U)', 'n'], ['بعد از تعدیل (A)', 'n'], ['سود هر سهم / نسبت', 'n'], ['بازده سود ٪', 'n']]) + '<tbody>' + d.events.slice().reverse().map(e => {
    const [dt, t, A, U] = e, isDiv = t === 'div';
    return `<tr><td class="num" title="${jd(dt)}">${dt}</td><td><span class="tag ${t}">${isDiv ? 'سود نقدی' : 'سرمایه'}</span></td><td class="n">${fmt(U, 0)}</td><td class="n">${fmt(A, 0)}</td><td class="n">${isDiv ? fmt(U - A, 0) : '×' + fmt(A / U, 3)}</td><td class="n">${isDiv ? fmt((U - A) / U * 100, 1) : '—'}</td></tr>`;
  }).join('') + '</tbody>';
  $('sy-info').innerHTML = '<tbody>' + [['نام', d.name], ['صنعت', d.sector], ['کد (insCode)', `<span class="num">${d.code}</span>`], ['داده', `<span class="num">${d.first} → ${d.last}</span>`], ['قیمت پایانی', fmt(d.price, 0) + ' ریال'],
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
  const ser = [{ v: kRel, color: 'var(--ch-3)', w: 1, dash: true }];
  if (sy.ser !== 'pr') ser.push({ v: d.tr, color: 'var(--ch-2)', w: 1.6 });
  if (sy.ser !== 'tr') ser.push({ v: d.pr, color: 'var(--ch-1)', w: 1.2 });
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
  paneChart($('rk-chart'), R.dates, [{ frac: .55, zero: true, series: [{ v: R.dd, color: 'var(--down)', w: 1.3 }], fmt: v => fmt(v, 0) + '%' }, { frac: .45, zero: true, series: [{ v: R.vol, color: 'var(--ch-2)', w: 1.2 }], fmt: v => fmt(v, 0) + '%' }], rk);
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
  attachHover($('rk-chart'), null, i => { rk.i = i; drawRisk(); });
  const C = X.risk.sector_corr;
  $('rk-cchip').textContent = C.months + ' ماه';
  const col = v => `background:color-mix(in srgb, var(--accent) ${Math.round(Math.max(0, v) * 85)}%, var(--bg-panel));color:${v > .6 ? 'var(--tx-1)' : 'var(--tx-2)'}`;
  $('rk-corr').innerHTML = `<table class="heat"><tr><th></th>${C.names.map((n, i) => `<th title="${n}">${i + 1}</th>`).join('')}</tr>` + C.m.map((row, i) => `<tr><th class="r" title="${n(C.names[i])}">${i + 1}. ${C.names[i].slice(0, 22)} <span class="num dim">${fmt(C.w[i], 0)}%</span></th>${row.map(v => `<td style="${col(v)}">${fmt(v, 2)}</td>`).join('')}</tr>`).join('') + '</table>';
  function n(x) { return x; }
  $('rk-csv').onclick = () => { const R = X.risk[rk.k]; download(`risk_${rk.k}.csv`, [['date', 'drawdown_pct', 'vol63_pct'], ...R.dates.map((d, i) => [d, R.dd[i], R.vol[i]])]); };
  redraws.risk = drawRisk; renderRisk();
}

/* ══════════ Index Funds ══════════ */
const fn = { sym: null, w: 'all', ref: 'tr', i: null };
const FB = () => (window.SIM_FUNDS && window.SIM_FUNDS.bench_names) || {};
const fnBench = k => FB()[k] || k;
function fnRows() {
  const w = fn.w;
  return window.SIM_FUNDS.funds.map(f => ({ f, m: (f.win[w] || {}).tr || {}, rp: (f.win[w] || {}).rep || {}, lag: (f.win[w] || {}).lag_cost })).filter(r => r.m.n)
    .sort((a, b) => (a.m.te_w ?? 1e9) - (b.m.te_w ?? 1e9));
}
function fnTable() {
  const F = window.SIM_FUNDS, rows = fnRows();
  const th_ = [['نماد'], ['مرجع'], ['از'], ['روز', 'n'], ['TE هفتگی %', 'n'], ['TE روزانه %', 'n'], ['TD سالانه %', 'n'], ['TD نسبت به ماکت %', 'n'], ['همبستگی هفتگی', 'n'], ['بتا', 'n'], ['R²', 'n'], ['پریمیوم میانگین %', 'n'], ['پریمیوم σ %', 'n'], ['رویداد', 'n']];
  const body = rows.map(({ f, m, rp }) => {
    const p = f.premium || {}, auto = f.benchmark_src === 'auto', odd = f.best_fit !== f.benchmark;
    return `<tr data-sym="${f.symbol}" ${f.symbol === fn.sym ? 'aria-selected="true"' : ''}><td><b>${f.symbol}</b></td><td>${fnBench(f.benchmark).replace(/[«»]/g, '')}${auto ? ' <span class="chip warn">حدسی</span>' : ''}${odd ? ` <span class="chip warn" data-tip="با این صندوق بهترین برازش را شاخص ${fnBench(f.best_fit)} دارد؛ مرجع اعلام‌شده را بررسی کنید.">برازش بهتر: ${fnBench(f.best_fit).replace(/[«»]/g, '')}</span>` : ''}</td><td class="num">${m.from}</td><td class="n">${m.n}</td><td class="n"><b>${fmt(m.te_w)}</b></td><td class="n">${fmt(m.te_d)}</td><td class="n ${cls(m.td)}">${sgn(m.td)}</td><td class="n ${cls(rp.td)}">${rp.td == null ? '—' : sgn(rp.td)}</td><td class="n">${fmt(m.corr_w, 4)}</td><td class="n">${fmt(m.beta, 3)}</td><td class="n">${fmt(m.r2, 4)}</td><td class="n ${cls(p.mean)}">${p.mean == null ? '—' : sgn(p.mean)}</td><td class="n">${p.std == null ? '—' : fmt(p.std)}</td><td class="n">${f.events.length || ''}</td></tr>`;
  }).join('');
  const ref = F.reference.map(x => `<tr class="mute"><td>ماکت SIM</td><td>${fnBench(x.benchmark).replace(/[«»]/g, '')}</td><td class="num">${x.from}</td><td class="n">${x.n}</td><td class="n">${fmt(x.te_w)}</td><td class="n">${fmt(x.te_d)}</td><td class="n ${cls(x.td)}">${sgn(x.td)}</td><td class="n">—</td><td class="n">${fmt(x.corr_w, 4)}</td><td class="n">${fmt(x.beta, 3)}</td><td class="n">${fmt(x.r2, 4)}</td><td class="n">—</td><td class="n">—</td><td class="n"></td></tr>`).join('');
  $('fn-tab').innerHTML = th(th_) + '<tbody>' + body + ref + '</tbody>';
  document.querySelectorAll('#fn-tab tr[data-sym]').forEach(tr => tr.onclick = () => { fn.sym = tr.dataset.sym; fn.i = null; fnRender(); });
}
function fnEmpty() {
  const F = window.SIM_FUNDS;
  $('fn-chip').textContent = 'منتظر دادهٔ NAV';
  $('fn-tab').innerHTML = th([['نماد'], ['نام'], ['مرجع']]) + '<tbody>' + F.missing.map(m => `<tr><td><b>${m.symbol}</b></td><td>${m.name}</td><td>${fnBench(m.benchmark).replace(/[«»]/g, '')}${m.benchmark_src === 'auto' ? ' <span class="chip warn">حدسی</span>' : ''}</td></tr>`).join('') + '</tbody>';
  ['fn-kpis', 'fn-chart', 'fn-lin-b'].forEach(k => $(k).innerHTML = '');
  $('fn-legend').innerHTML = '<span>نمودار NAV در برابر مرجع و TE غلتان پس از دریافت دادهٔ صندوق‌ها ساخته می‌شود (دستور در پنل D)</span>';
  $('fn-year').innerHTML = '<tbody><tr><td class="mute" style="white-space:normal;padding:10px">جدول سال‌ها پس از دریافت NAV.</td></tr></tbody>';
  $('fn-title').textContent = 'صندوق';
  $('fn-lin-a').innerHTML = `<span><b>وضعیت</b> NAV این صندوق‌ها هنوز در مخزن نیست؛ ${F.missing.length} صندوق شاخصی شناسایی شده است</span>`;
  $('fn-method').innerHTML = fnMethod(false);
}
function fnMethod(has) {
  const F = window.SIM_FUNDS;
  return `<p><b>داده:</b> قیمت بازار و NAV ابطال هر صندوق از TSETMC و فیپیران (یا سایت خود صندوق) با <code>tools/fetch_index_funds.py</code> روی سیستم شما گرفته می‌شود؛ سپس <code>python tools/build_ui_funds.py</code> این نما را می‌سازد.</p>
  ${has ? '' : `<div class="cmdline">python tools/fetch_index_funds.py --log funds_log.txt\npython tools/build_ui_funds.py\ngit add -A; git commit -m "index funds"; git push -u origin claude/charming-ptolemy-cyehmc</div>`}
  <p><b>روش:</b></p><ol>
  <li>بازده روزانهٔ صندوق از NAV ابطال (در نبود آن NAV آماری) روی روزهای معاملاتی شاخص؛ دو ماه اول عمر صندوق (تشکیل سبد) کنار می‌رود.</li>
  <li><b>TE هفتگی</b> = انحراف معیار بازده فعال ۵ روزهٔ غیرهم‌پوشان × √۵۲. معیار اصلی است، چون NAV و شاخص در بورس تهران هم‌زمان منتشر نمی‌شوند و TE روزانه را بالا می‌برد. <b>TE روزانه</b> برای مقایسه با ادبیات هم آمده است.</li>
  <li><b>TD</b> (تفاوت ردیابی) = بازده سالانهٔ صندوق منهای مرجع با سال تقویمی؛ منفی یعنی صندوق عقب مانده است.</li>
  <li><b>TD نسبت به ماکت</b> = بازده صندوق منهای ماکت سرمایه‌پذیر SIM (بازتولید کامل، بدون کارمزد، سود با تأخیر ${F.lag} روز). بخش ساختاری TD (تأخیر سود) را از سهم قابل‌انتساب به مدیر (کارمزد، نقدی، اجرا) جدا می‌کند؛ هر صندوقی که به‌خاطر تأخیر سود از TR رسمی عقب است، نسبت به ماکت منصفانه‌تر سنجیده می‌شود. ماکت فقط برای «شاخص كل» و هم‌وزن موجود است.</li>
  <li>جهش بازده فعال روزانه بیش از ۲۰٪ (تجزیهٔ واحد یا خطای NAV) رویداد حساب و خنثی می‌شود و در ستون «رویداد» می‌آید؛ ۵ تا ۲۰٪ فقط علامت می‌خورد.</li>
  <li><b>برازش بهتر:</b> NAV هر صندوق در برابر هر سه شاخص (كل، هم‌وزن، ۳۰ شرکت) سنجیده می‌شود؛ اگر شاخص دیگری TE کمتری بدهد، مرجع اعلام‌شده یا نوع صندوق باید بازبینی شود. <b>حدسی</b> یعنی مرجع را مالک پروژه اعلام نکرده و از نام صندوق حدس زده شده است.</li>
  <li><b>پریمیوم</b> = قیمت پایانی بازار ÷ NAV ابطال − ۱؛ هزینهٔ واقعی سرمایه‌گذار بازار ثانویه، جدا از خطای ردیابی NAV.</li></ol>
  <p><b>محدودیت‌ها:</b> NAV ابطال تحت‌تأثیر برآورد قیمت سهام متوقف و صف است؛ کارمزد سالانه از دادهٔ NAV جدا نشده و در TD دیده می‌شود؛ مرجع «شاخص ۳۰ شرکت» بازده کل بودنش از رفتار روز استحقاق تأیید شد، ولی ترکیب تاریخی آن بازسازی نشده است.</p>`;
}
function fnRender() {
  const F = window.SIM_FUNDS;
  if (!F.funds.length) { fnEmpty(); return; }
  document.querySelectorAll('#fn-win button').forEach(b => b.setAttribute('aria-pressed', b.dataset.w === fn.w));
  document.querySelectorAll('#fn-ref button').forEach(b => b.setAttribute('aria-pressed', b.dataset.r === fn.ref));
  const rows = fnRows();
  if (!rows.length) { $('fn-tab').innerHTML = ''; $('fn-lin-a').innerHTML = '<span>برای این بازه دادهٔ کافی نیست</span>'; return; }
  if (!rows.find(r => r.f.symbol === fn.sym)) fn.sym = rows[0].f.symbol;
  $('fn-chip').textContent = rows.length + ' صندوق';
  fnTable();
  $('fn-lin-a').innerHTML = `<span><b>مرتب</b> بر پایهٔ TE هفتگی (کمتر بهتر)</span><span><b>NAV</b> ابطال تا <span class="num">${rows.map(r => r.f.nav_to).sort().pop()}</span></span><span><b>ساخت</b> <span class="num">${F.built}</span></span><span><b>ردیف خاکستری</b> ماکت SIM در ۳ سال اخیر؛ کف ساختاری</span>`;
  const { f, m, rp } = rows.find(r => r.f.symbol === fn.sym), base = fn.ref === 'rep' && rp.n ? rp : m, nm = fn.ref === 'rep' && rp.n ? 'ماکت سرمایه‌پذیر ' + fnBench(f.benchmark) : fnBench(f.benchmark);
  $('fn-title').textContent = `${f.symbol} · ${f.name}`;
  $('fn-kpis').innerHTML = [['TE هفتگی', fmt(base.te_w) + '%', ''], ['TD سالانه', sgn(base.td) + '%', cls(base.td)], ['همبستگی هفتگی', fmt(base.corr_w, 4), ''], ['بتا', fmt(base.beta, 3), ''], ['پریمیوم میانگین', f.premium ? sgn(f.premium.mean) + '%' : '—', f.premium ? cls(f.premium.mean) : ''], ['خالص دارایی', f.aum_bn ? fmt(f.aum_bn, 0) + ' م.ر' : '—', '']]
    .map(([k, v, c]) => `<div class="kpi"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`).join('');
  const c = f.curve, st = fn;
  $('fn-legend').innerHTML = `<span><i style="color:var(--ch-1)"></i>صندوق (NAV)</span><span><i style="color:var(--ch-2)"></i>${nm.replace(/[«»]/g, '')}</span>${c.rep && fn.ref === 'tr' ? '<span><i style="color:var(--ch-3);border-top-style:dashed"></i>ماکت سرمایه‌پذیر</span>' : ''}<span><i style="color:var(--down)"></i>TE ۶۳ روزه (٪)</span><span class="readout" id="fn-readout"></span>`;
  const bser = fn.ref === 'rep' && c.rep ? c.rep : c.b, ser = [{ v: c.f, color: 'var(--ch-1)', w: 1.5 }, { v: bser, color: 'var(--ch-2)', w: 1.3 }];
  if (c.rep && fn.ref === 'tr') ser.push({ v: c.rep, color: 'var(--ch-3)', w: 1.1, dash: true });
  const draw = () => {
    paneChart($('fn-chart'), c.dates, [{ frac: .65, log: true, series: ser, fmt: v => fmt(v, 0) }, { frac: .35, zero: true, series: [{ v: c.te63, color: 'var(--down)', w: 1.2 }], fmt: v => fmt(v, 1) + '%' }], st);
    $('fn-readout').innerHTML = st.i == null ? '' : `<b>${c.dates[st.i]}</b> &nbsp; صندوق <b>${fmt(c.f[st.i], 1)}</b> &nbsp; مرجع <b>${fmt(bser[st.i], 1)}</b> &nbsp; TE₆₃ <b>${fmt(c.te63[st.i], 2)}%</b>`;
  };
  if (!$('fn-chart')._hov) { $('fn-chart')._hov = true; attachHover($('fn-chart'), null, i => { fn.i = i; redraws.fnd && redraws.fnd(); }); }
  redraws.fnd = draw; draw();
  $('fn-lin-b').innerHTML = `<span><b>${f.nav_col === 'ret_daily' ? 'بازده روزانهٔ NAV' : 'NAV'}</b> ${f.nav_col === 'nav_cancel' ? 'ابطال' : f.nav_col === 'nav_stat' ? 'آماری' : ''} · <span class="num">${f.nav_from}</span> → <span class="num">${f.nav_to}</span> · منبع ${f.nav_source === 'fipiran' ? 'فیپیران' : 'سایت صندوق'}</span><span><b>مرجع</b> ${nm}${f.benchmark_src === 'auto' ? ' (حدسی)' : ''}</span>${f.price_te != null ? `<span><b>TE قیمت بازار</b> ${fmt(f.price_te)}%</span>` : ''}`;
  $('fn-year').innerHTML = th([['سال شمسی'], ['صندوق %', 'n'], ['مرجع %', 'n'], ['تفاوت %', 'n'], ['TE سالانه %', 'n'], ['روز', 'n']]) + '<tbody>' + f.yearly.map(y => `<tr><td class="num">${y.jy}</td><td class="n ${cls(y.f)}">${sgn(y.f, 1)}</td><td class="n ${cls(y.b)}">${sgn(y.b, 1)}</td><td class="n ${cls(y.d)}">${sgn(y.d)}</td><td class="n">${fmt(y.te)}</td><td class="n mute">${y.days}</td></tr>`).join('') + '</tbody>';
  const evs = f.events.length ? `<p><b>رویدادهای خنثی‌شده برای ${f.symbol}:</b> ${f.events.map(e => `<span class="num">${e[0]}</span> (${sgn(e[1], 1)}٪)`).join('، ')}</p>` : '';
  const miss = F.missing.length ? `<p><b>NAV دریافت‌نشده:</b> ${F.missing.map(x => x.symbol).join('، ')}</p>` : '';
  $('fn-method').innerHTML = evs + miss + fnMethod(true);
}
function initFnd() {
  document.querySelectorAll('#fn-win button').forEach(b => b.onclick = () => { fn.w = b.dataset.w; fnRender(); });
  document.querySelectorAll('#fn-ref button').forEach(b => b.onclick = () => { fn.ref = b.dataset.r; fnRender(); });
  $('fn-csv').onclick = () => {
    const F = window.SIM_FUNDS; if (!F.funds.length) return download('index_funds_candidates.csv', [['symbol', 'name', 'benchmark'], ...F.missing.map(m => [m.symbol, m.name, m.benchmark])]);
    download(`index_funds_tracking_${fn.w}.csv`, [['symbol', 'benchmark', 'from', 'days', 'te_weekly_pct', 'te_daily_pct', 'td_pct', 'td_vs_replica_pct', 'corr_weekly', 'beta', 'r2', 'premium_mean_pct', 'premium_std_pct', 'events'], ...fnRows().map(({ f, m, rp }) => [f.symbol, f.benchmark, m.from, m.n, m.te_w, m.te_d, m.td, rp.td ?? '', m.corr_w, m.beta, m.r2, (f.premium || {}).mean ?? '', (f.premium || {}).std ?? '', f.events.length])]);
  };
  redraws.fnd = null; fnRender();
}

/* ══════════ تراکم، حافظهٔ تنظیمات، تاریخچهٔ فرمان، کلیک روی نماد ══════════ */
const LS = { get: k => { try { return localStorage.getItem('sim.' + k); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem('sim.' + k, v); } catch (e) { /* بی‌اهمیت */ } } };
const DENS = ['compact', 'default', 'comfortable'];
function setDensity(d) { if (d === 'compact') delete document.documentElement.dataset.density; else document.documentElement.dataset.density = d; LS.set('density', d); }
$('density').onclick = () => { const cur = document.documentElement.dataset.density || 'compact'; const nx = DENS[(DENS.indexOf(cur) + 1) % 3]; setDensity(nx); toast('تراکم: ' + nx); };
if (LS.get('density')) setDensity(LS.get('density'));
if (LS.get('theme')) document.documentElement.dataset.theme = LS.get('theme');
document.addEventListener('click', e => { const a = e.target.closest('.symlink'); if (a) { e.preventDefault(); window.openSym(a.dataset.sym); } });
const hist = JSON.parse(LS.get('hist') || '[]'); let hi = hist.length;
$('cmd').addEventListener('keydown', e => {
  if (e.key === 'Enter' && e.target.value.trim()) { hist.push(e.target.value.trim()); while (hist.length > 30) hist.shift(); LS.set('hist', JSON.stringify(hist)); hi = hist.length; }
  if (e.key === 'ArrowUp' && hist.length) { hi = Math.max(0, hi - 1); e.target.value = hist[hi]; e.preventDefault(); }
  if (e.key === 'ArrowDown' && hist.length) { hi = Math.min(hist.length, hi + 1); e.target.value = hist[hi] || ''; e.preventDefault(); }
}, true);

/* ══════════ Router ══════════ */
const INIT = { div: initDiv, fac: initFac, reb: initReb, qa: initQA, rep: initRep, sym: initSym, pf: initPf, risk: initRisk, fnd: initFnd };
function show(name) {
  if (!VIEWS[name]) return;
  Object.entries(VIEWS).forEach(([k, id]) => { $(id).hidden = k !== name; });
  document.querySelectorAll('#nav a').forEach(a => { if (a.dataset.view === name) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  if (X && INIT[name] && !inited[name]) { inited[name] = true; INIT[name](); }
  requestAnimationFrame(() => { if (name === 'index') drawChart(); else if (redraws[name]) redraws[name](); });
  history.replaceState(null, '', '#' + name); LS.set('view', name);
}
document.querySelectorAll('#nav a').forEach(a => a.addEventListener('click', e => { e.preventDefault(); show(a.dataset.view); }));
addEventListener('keydown', e => {
  if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName) || e.ctrlKey || e.metaKey) return;
  const n = '1234567890'.indexOf(e.key); if (n >= 0) show(Object.keys(VIEWS)[n]);
});
const _run = window.run;
window.run = function (cmd) {
  const [c, a] = cmd.trim().toLowerCase().split(/\s+/);
  if (c === 'go' || c === 'view') { if (VIEWS[a]) { show(a); toast('نما: ' + a); } else toast('نما: ' + Object.keys(VIEWS).join(' · ')); return; }
  if (c === 'help') { toast('GO INDEX|DIV|FAC|REB|QA|REP|SYM|PF|RISK|FND · SYM <نماد> · IDX K|EW · WIN 2014|2016 · THEME · DENSITY · ↑↓ تاریخچه'); return; }
  if (c === 'sym' && a) { window.openSym(cmd.trim().split(/\s+/)[1]); return; }
  if (c === 'density') { $('density').click(); return; }
  if (c === 'idx' || c === 'win') show('index');
  _run(cmd);
  if (c === 'theme') { LS.set('theme', document.documentElement.dataset.theme); const v = Object.keys(VIEWS).find(k => !$(VIEWS[k]).hidden); if (v && redraws[v]) redraws[v](); }
};
new ResizeObserver(() => { const v = Object.keys(VIEWS).find(k => !$(VIEWS[k]).hidden); if (v && redraws[v]) redraws[v](); }).observe(document.body);
const want = (location.hash || '').slice(1) || LS.get('view') || 'index';
show(want in VIEWS ? want : 'index');
})();
