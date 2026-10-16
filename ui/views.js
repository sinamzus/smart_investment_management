/* SIM — نماهای دوم: Dividend Lab · Factor Lab · Rebalance · Data QA · Reports
   داده: window.SIM_EXTRA (tools/build_ui_extra.py) و window.SIM_DATA. هیچ عدد ثابتی در این فایل نیست مگر متن توضیحی. */
(function () {
const X = window.SIM_EXTRA;
const VIEWS = { index: 'v-index', div: 'v-div', fac: 'v-fac', reb: 'v-reb', qa: 'v-qa', rep: 'v-rep' };
const JM = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
const inited = {}, redraws = {};
const jyear = new Intl.DateTimeFormat('fa-IR-u-ca-persian-nu-latn', { year: 'numeric' });
const cls = v => v == null ? '' : v >= 0 ? 'up' : 'down';
const chipTE = t => t == null ? '' : t < 1 ? 'ok' : t < 3 ? 'warn' : 'bad';

if (!X) {
  ['v-div', 'v-fac', 'v-reb', 'v-qa', 'v-rep'].forEach(id => { $(id).innerHTML = '<p style="padding:24px">ui/data/extra.js پیدا نشد. اجرا کنید: <code>python tools/build_ui_extra.py</code></p>'; });
}

/* ── نمودار چندپنلی ───────────────────────────────────── */
function paneChart(svg, dates, panes, st) {
  const W = svg.clientWidth || 800, H = svg.clientHeight || 300, m = { l: 8, r: 58, t: 30, b: 20 }, gap = 8;
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
    if (p.log) { for (let e = Math.floor(Math.log10(lo)) - 1; e <= Math.ceil(Math.log10(hi)) + 1; e++) [1, 2, 5].forEach(mu => { const v = mu * 10 ** e; if (v >= lo * 0.97 && v <= hi * 1.03) tv.push(v); }); if (tv.length > 6) tv = tv.filter((v, i) => i % 2 === 0); }
    else for (let k = 0; k <= 3; k++) tv.push(Math.exp ? ((a - pad) + ((b - a) + 2 * pad) * k / 3) : 0);
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
  const ratio = nav[n - 1] / trL[n - 1], gap = (Math.pow(ratio, 252 / n) - 1) * 100;
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
  $('dv-lineage').innerHTML = `<span><b>مدل</b> NAV = ارزش پرتفوی + مطالبات سود − وام؛ سود روز استحقاق = TR − PR رسمی، پرداخت L روز بعد</span><span><b>L = ۰</b> دقیقاً TR رسمی (تأییدکنندهٔ مدل)</span><span><b>فرض</b> تأخیر ثابت و نرخ وام ثابت [راستی‌آزمایی نشده]</span><span><b>روش‌شناسی</b> فصل ۰۳ §۳٫۵</span>`;
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
  const p = X.divlab.payment_data, ok = p.available;
  $('dv-pay-chip').textContent = ok ? p.rows + ' زمان‌بندی · ' + p.agm_rows + ' مجمع' : (p.agm_rows ? p.agm_rows + ' مجمع؛ زمان‌بندی نه' : 'جمع‌آوری نشده');
  $('dv-pay-chip').className = 'chip ' + (ok ? 'ok' : 'warn');
  $('dv-pay').innerHTML = `<div class="note">${ok ? 'نامه‌های «زمان‌بندی پرداخت سود» کدال رسیده‌اند؛ استخراج تاریخ پرداخت از آن‌ها (اغلب پیوست) هنوز ساخته نشده.' : 'تاریخ واقعی پرداخت سود هنوز در داده نیست؛ مدل بالا با تأخیر ثابت L کار می‌کند.'}
    منبع: کدال، نامه‌های «زمان‌بندی پرداخت سود» (ن-۱۳، LetterType=30) و «تصمیمات مجمع عادی سالیانه» (ن-۵۲، LetterType=20؛ تاریخ مجمع و سود هر سهم). کدال نرخ درخواست را محدود می‌کند (429)؛ جمع‌آوری آهسته و قابل‌ادامه است.</div>
    <div class="prose"><b>جمع‌آوری (روی سیستم شما؛ هر بار قطع شد، همان دستور ادامه می‌دهد):</b><div class="cmdline">python tools/fetch_dividend_payments.py --collect 30 --years 5 --log collect.txt\npython tools/fetch_dividend_payments.py --parse\ngit add -A; git commit -m "codal collect"; git push -u origin claude/charming-ptolemy-cyehmc</div>
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
function initFac() {
  const F = X.factor, c = F.curve, N = c.dates.length;
  const col = { Q1: 'var(--down)', Q3: 'var(--ch-3)', Q5: 'var(--up)', ALL: 'var(--ch-2)' }, lab = { Q1: 'پنجک ۱ (ضعیف‌ترین)', Q3: 'پنجک ۳', Q5: 'پنجک ۵ (قوی‌ترین)', ALL: 'همهٔ واجدان شرایط (هم‌وزن)' };
  $('fc-kpis').innerHTML = [['پنجک ۵ − پنجک ۱ (سالانه)', sgn(F.ls_ann_pct, 1) + '%', cls(F.ls_ann_pct)], ['پنجک ۵ نسبت به همه', sgn(F.q5_excess_ann_pct, 1) + '%', cls(F.q5_excess_ann_pct)], ['TE پنجک ۵ به همه', fmt(F.q5_minus_all_te, 1) + '%', ''], ['گردش ماهانهٔ پنجک ۵', fmt(F.q5_monthly_turnover_pct, 0) + '%', ''], ['ماه ریبالانس', F.n_months, '']]
    .map(([k, v, cl]) => `<div class="kpi"><div class="k">${k}</div><div class="v ${cl}">${v}</div></div>`).join('');
  $('fc-legend').innerHTML = ['Q1', 'Q3', 'Q5', 'ALL'].map(q => `<span><i style="color:${col[q]}"></i>${lab[q]}</span>`).join('') + '<span class="readout" id="fc-readout"></span>';
  const st = { i: null };
  const draw = () => { paneChart($('fc-chart'), c.dates, [{ frac: 1, log: true, series: ['Q1', 'Q3', 'Q5', 'ALL'].map(q => ({ v: c[q], color: col[q], w: q === 'ALL' ? 1.6 : 1.2 })), fmt: v => fmt(v, 0) }], st);
    $('fc-readout').innerHTML = st.i == null ? '' : `<b>${c.dates[st.i]}</b> &nbsp; Q1 <b>${fmt(c.Q1[st.i], 0)}</b> &nbsp; Q5 <b>${fmt(c.Q5[st.i], 0)}</b> &nbsp; همه <b>${fmt(c.ALL[st.i], 0)}</b>`; };
  attachHover($('fc-chart'), draw, i => { st.i = i; draw(); }); redraws.fac = draw; draw();
  $('fc-lineage').innerHTML = `<span><b>بازه</b> <span class="num">${F.from}</span> → <span class="num">${F.to}</span></span><span><b>بازده</b> TR (سود با استحقاق سرمایه‌گذاری مجدد)</span><span><b>بدون</b> هزینه معامله، بدون محدودیت نقدشوندگی</span><span><b>مبنا</b> فصل ۰۴ · ۰۵</span>`;
  const q = ['Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'ALL'];
  bars($('fc-bars'), ['۱', '۲', '۳', '۴', '۵', 'همه'], q.map(k => F.ann[k]), v => fmt(v, 1), (i) => i === 5);
  $('fc-lin-b').innerHTML = `<span><b>میانگین نماد</b> در هر پنجک ≈ ${F.avg_names.Q1} · کل واجد ≈ ${F.avg_names.ALL}</span><span><b>خوانش</b> الگوی کوهان‌شکل؛ پنجک ۵ ضعیف‌ترین نیست ولی از همه کمتر است</span>`;
  $('fc-year').innerHTML = th([['سال شمسی'], ['پنجک ۱ %', 'n'], ['پنجک ۵ %', 'n'], ['همه %', 'n'], ['۵−۱', 'n'], ['روز', 'n']]) + '<tbody>' + F.yearly.map(r => `<tr><td class="num">${r.jy}</td><td class="n ${cls(r.Q1)}">${sgn(r.Q1, 1)}</td><td class="n ${cls(r.Q5)}">${sgn(r.Q5, 1)}</td><td class="n ${cls(r.ALL)}">${sgn(r.ALL, 1)}</td><td class="n ${cls(r.ls)}">${sgn(r.ls, 1)}</td><td class="n mute">${r.days}</td></tr>`).join('') + '</tbody>';
  $('fc-method').innerHTML = `<div class="note">پیش‌نمایش پژوهشی — نه توصیه و نه نتیجهٔ تأییدشده. هیچ آزمون معناداری (t-stat)، بدون هزینه، و با سوگیری بقای باقی‌ماندهٔ جهان (فقط بخشی از نمادهای حذف‌شده را داریم).</div>
  <ol><li><b>سیگنال:</b> مومنتوم ۱۲−۱؛ بازدهٔ لگاریتمی TR از ۲۵۲ تا ۲۱ روز معاملاتی پیش از آخرین روز هر ماه شمسی (ماه آخر کنار گذاشته می‌شود).</li>
  <li><b>واجد شرایط:</b> دست‌کم ۸۰٪ روزهای پنجره داده و دست‌کم ۵۰٪ روزهایی با بازده غیرصفر (حذف نمادهای عملاً متوقف)، و دادهٔ روز بعد.</li>
  <li><b>پنجک‌ها:</b> مرتب‌سازی ساده؛ هم‌وزن درون هر پنجک؛ ریبالانس هر ماه شمسی؛ بازده روزانه تا ریبالانس بعد.</li>
  <li><b>بازه:</b> ارزیابی از ۱۳۹۵/۰۱ (ردیف‌های ۲۰۱۲–۲۰۱۴ هنوز تعدیل‌نشدهٔ پراکنده دارند و سیگنال را آلوده می‌کنند).</li></ol>
  <b>خوانش صادقانه:</b> مومنتوم خام ۱۲−۱ در این نمونه پریمیوم مثبت نشان نمی‌دهد (پنجک ۵ از میانگین کمتر است). فرضیه‌های محتمل، آزموده‌نشده: بازگشت میانگین پس از جهش‌های بازگشایی با سقف نوسان، اثر بازار صعودی تورمی همگانی، و آلودگی توقف‌های طولانی. گام بعد: مومنتوم تعدیل‌شده با نوسان یا باقیمانده‌ای نسبت به بازار/صنعت، حذف سهام در صف، و فاکتور کیفیت/حداقل نوسان (فصل ۱۱).`;
  $('fc-csv').onclick = () => download('factor_momentum_curves.csv', [['date', 'Q1', 'Q3', 'Q5', 'ALL'], ...c.dates.map((d, i) => [d, c.Q1[i], c.Q3[i], c.Q5[i], c.ALL[i]])]);
}

/* ══════════ Rebalance ══════════ */
function rebRender() {
  const R = X.rebalance, cost = +$('rb-cost').value || 0, nm = { 'jalali-month': 'ماهانه (شمسی)', 'jalali-quarter': 'فصلی (شمسی)', 'jalali-halfyear': 'شش‌ماهه', 'jalali-year': 'سالانه' };
  const best = R.policies.reduce((b, p) => p.te < b.te ? p : b);
  $('rb-pol').innerHTML = th([['سیاست'], ['ریبالانس', 'n'], ['گردش هر بار %', 'n'], ['گردش سالانه %', 'n'], ['TE در برابر رسمی %', 'n'], ['همبستگی', 'n'], ['نسبت سطح', 'n'], ['هزینهٔ فرضی bp/سال', 'n']]) + '<tbody>' + R.policies.map(p => `<tr ${p === best ? 'aria-selected="true"' : ''}><td>${nm[p.policy]}${p === best ? ' <span class="chip info">کمترین TE</span>' : ''}</td><td class="n">${p.n_rebal}</td><td class="n">${fmt(p.avg_turn_pct, 1)}</td><td class="n">${fmt(p.annual_turn_pct, 1)}</td><td class="n">${fmt(p.te)}</td><td class="n">${fmt(p.corr, 4)}</td><td class="n">${fmt(p.cum_ratio, 3)}</td><td class="n">${fmt(p.annual_turn_pct * cost / 100, 0)}</td></tr>`).join('') + '</tbody>';
  $('rb-lin-a').innerHTML = `<span><b>هدف</b> «كل (هم وزن)» TR رسمی</span><span><b>گردش</b> یک‌طرفه = ½ Σ|وزن هدف − وزن رانش‌یافته|</span><span><b>هزینه</b> گردش سالانه × هزینهٔ رفت‌وبرگشت (ورودی بالا؛ فرضی)</span><span><b>روش</b> فصل ۰۳ §۳٫۴ · فصل ۰۶</span>`;
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
  <li><b>تاریخ پرداخت سود:</b> جمع‌آوری نشده ← Dividend Lab فقط سناریوی ثابت دارد.</li>
  <li><b>هم‌وزن TR رسمی:</b> سطح من ≈ ۴٫۹٪ کمتر (۰٫۹۵) و PR ≈ ۴٫۶٪ بیشتر؛ تفکیک سود/سرمایه در رویدادهای ترکیبی.</li>
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
    ['مومنتوم ۱۲−۱ (پیش‌نمایش)', `پنجک ۵ − ۱ = ${sgn(F.ls_ann_pct, 1)}٪ در سال؛ پنجک ۵ نسبت به همه ${sgn(F.q5_excess_ann_pct, 1)}٪`, 'فصل ۴ · ۵']];
  $('rp-sum').innerHTML = th([['نتیجه'], ['مقدار'], ['مرجع']]) + '<tbody>' + rows.map(r => `<tr><td>${r[0]}</td><td>${r[1]}</td><td class="mute">${r[2]}</td></tr>`).join('') + '</tbody>';
  $('rp-text').innerHTML = `<b>وضعیت.</b> داده تا <span class="num">${D.meta.asof}</span>؛ ${fmt(D.meta.n_price_rows, 0)} ردیف قیمت. مرجع‌ها: «شاخص كل» و «كل (هم وزن)» رسمی. ماکت سرمایه‌پذیر با بازتولید کامل و بدون سقف سرمایه/وزن؛ تنها شکاف ساختاری، تأخیر پرداخت سود است. تاریخ واقعی پرداخت هنوز جمع‌آوری نشده. این صفحه از همان دادهٔ UI ساخته می‌شود؛ «چاپ» ← PDF.`;
  $('rp-lin-a').innerHTML = `<span><b>ساخت</b> <span class="num">${X.built}</span></span><span><b>داده</b> <span class="num">${D.meta.built}</span></span><span><b>قاعدهٔ سند</b> هر تغییر روش‌شناسی ← فصل + CHANGELOG (<code>CLAUDE.md</code>)</span>`;
  const log = X.reports.changelog; $('rp-chip').textContent = log.length + ' ردیف';
  $('rp-log').innerHTML = th([['تاریخ'], ['تغییر'], ['فصل‌ها']]) + '<tbody>' + log.slice().reverse().map(r => `<tr><td class="num">${r.date}</td><td title="${r.text.replace(/"/g, '&quot;')}" style="white-space:normal;min-width:260px">${r.title}</td><td class="mute" style="white-space:normal">${r.chapters}</td></tr>`).join('') + '</tbody>';
  $('rp-docs').innerHTML = th([['فایل'], ['عنوان'], ['KB', 'n']]) + '<tbody>' + X.reports.docs.map(d => `<tr><td class="num">${d.file}</td><td>${d.title}</td><td class="n">${d.kb}</td></tr>`).join('') + '</tbody>';
  $('rp-tools').innerHTML = th([['ابزار'], ['کار']]) + '<tbody>' + X.reports.tools.map(t => `<tr><td class="num">${t.file}</td><td style="white-space:normal">${t.doc}</td></tr>`).join('') + '</tbody>';
  $('rp-print').onclick = () => window.print();
  $('rp-json').onclick = () => download('sim_report_summary.csv', [['item', 'value', 'ref'], ...rows]);
  $('rp-csv').onclick = () => download('changelog.csv', [['date', 'title', 'chapters'], ...log.map(r => [r.date, r.title, r.chapters])]);
}

/* ══════════ Router ══════════ */
const INIT = { div: initDiv, fac: initFac, reb: initReb, qa: initQA, rep: initRep };
function show(name) {
  if (!VIEWS[name]) return;
  Object.entries(VIEWS).forEach(([k, id]) => { $(id).hidden = k !== name; });
  document.querySelectorAll('#nav a').forEach(a => { if (a.dataset.view === name) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  if (X && INIT[name] && !inited[name]) { inited[name] = true; INIT[name](); }
  requestAnimationFrame(() => { if (name === 'index') drawChart(); else if (redraws[name]) redraws[name](); });
  history.replaceState(null, '', '#' + name);
}
document.querySelectorAll('#nav a').forEach(a => a.addEventListener('click', e => { e.preventDefault(); show(a.dataset.view); }));
addEventListener('keydown', e => {
  if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName) || e.ctrlKey || e.metaKey) return;
  const n = '123456'.indexOf(e.key); if (n >= 0) show(Object.keys(VIEWS)[n]);
});
const _run = window.run;
window.run = function (cmd) {
  const [c, a] = cmd.trim().toLowerCase().split(/\s+/);
  if (c === 'go' || c === 'view') { if (VIEWS[a]) { show(a); toast('نما: ' + a); } else toast('نما: ' + Object.keys(VIEWS).join(' · ')); return; }
  if (c === 'help') { toast('GO INDEX|DIV|FAC|REB|QA|REP · IDX K|EW · WIN 2014|2016 · THEME'); return; }
  if (c === 'idx' || c === 'win') show('index');
  _run(cmd);
  if (c === 'theme') { const v = Object.keys(VIEWS).find(k => !$(VIEWS[k]).hidden); if (v && redraws[v]) redraws[v](); }
};
new ResizeObserver(() => { const v = Object.keys(VIEWS).find(k => !$(VIEWS[k]).hidden); if (v && redraws[v]) redraws[v](); }).observe(document.body);
show((location.hash || '#index').slice(1) in VIEWS ? (location.hash || '#index').slice(1) : 'index');
})();
