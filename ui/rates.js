/* همتا — «نرخ بدون ریسک» (بخش داده و گزارش؛ فصل ۷ §۷٫۱۰)
   داده: window.SIM_RATES از tools/build_rf.py (قیمت روزانهٔ اخزاها از TSETMC، سررسید و YTM جاری از فرابورس). */
(function () {
'use strict';
const R = window.SIM_RATES;
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const f = (x, d = 1) => x == null || x !== x ? '—' : fmt(x, d);
const pc = (x, d = 1) => x == null || x !== x ? '—' : fmt(100 * x, d) + '٪';
const tip = t => ` data-tip="${esc(t)}"`;
const DOC = ' data-doc="7:7.10"';
const jd = d => d ? ChartKit.jstr(d) : '—';
const st = { per: 'all', day: null };

function init() {
  const m = document.getElementById('v-rf'); m.dataset.ready = 1;
  if (!R || !R.series) { m.innerHTML = '<p style="padding:24px">دادهٔ اخزا پیدا نشد. اجرا کنید: <code>python tools/fetch_treasury_bills.py</code> سپس <code>python tools/build_rf.py</code></p>'; return; }
  const days = Object.keys(R.curves); st.day = days[days.length - 1];
  m.innerHTML = `
  <section class="panel" style="--lg:var(--lg-a)">
    <div class="panel-head"><span class="lg-badge">1</span><span class="panel-title"${tip('بازده تا سررسید اسناد خزانهٔ اسلامی (اخزا) که در بازار ثانویهٔ فرابورس معامله می‌شوند. اخزا بی‌کوپن و با ضمانت دولت است؛ پس YTM آن نزدیک‌ترین عدد بازاری به «نرخ بدون ریسک» ریالی است. هر روز فقط اوراقِ سررسیدنشده‌ای که همان روز معامله شده‌اند وارد می‌شوند.')}${DOC}>نرخ بدون ریسک از اخزا</span><span class="chip" id="rf-chip"></span>
      <div class="panel-tools"><button class="tool" id="rf-csv"${tip('سری روزانه به‌صورت CSV.')}>CSV</button></div></div>
    <div class="kpis" id="rf-kpis"></div>
    <div class="ctl"><span class="seg" id="rf-per"><button data-v="all">کل</button><button data-v="3">۳ سال</button><button data-v="1">۱ سال</button></span>
      <span class="mute">روی نمودار بکشید تا زوم شود؛ دابل‌کلیک = بازنشانی</span></div>
    <div class="panel-body"><div class="legend" id="rf-leg"></div><svg class="chart" id="rf-chart" dir="ltr" style="height:320px;flex:none"></svg></div>
    <div class="lineage"><span><b${tip('فرمول بازده تا سررسید اوراق بی‌کوپن؛ همان فرمول جدول فرابورس.')}>YTM</b> ${ltr('(1,000,000 / P)^(365/d) − 1')}</span><span><b${tip('ورقه‌ای که کمتر از این تعداد روز به سررسیدش مانده، کنار می‌رود؛ چند ریال اختلاف قیمت در چند روز آخر YTM را بی‌معنا بزرگ می‌کند.')}>کنار</b> کمتر از ${R.min_days} روز تا سررسید، روز بی‌معامله، قیمت ≥ اسمی</span><span><b${tip('روز بی‌معاملهٔ اخزا نرخ ندارد؛ برای استفاده در محاسبات، آخرین نرخ معلوم تا این تعداد روز تقویمی ادامه می‌یابد.')}>پرکردن</b> تا ${R.ffill_days} روز</span><span><b>منبع</b> قیمت: TSETMC · سررسید و YTM مقایسه: فرابورس (${jd(R.ifb_asof)})</span><span><b>بازسازی</b> <code>python tools/fetch_treasury_bills.py</code> ← <code>python tools/build_rf.py</code></span></div>
  </section>
  <section class="panel" style="--lg:var(--lg-b)">
    <div class="panel-head"><span class="lg-badge">2</span><span class="panel-title"${tip('بازده تا سررسید هر ورقهٔ معامله‌شده در یک روز بر حسب روز تا سررسید. اندازهٔ دایره = ارزش معاملهٔ همان روز.')}${DOC}>منحنی بازده اخزا</span>
      <label style="margin-inline-start:auto"${tip('روز معامله (۲۶۰ روز معاملهٔ اخیر).')}>روز <select id="rf-day">${days.slice().reverse().map(d => `<option value="${d}">${jd(d)}</option>`).join('')}</select></label></div>
    <div class="panel-body"><svg id="rf-curve" dir="ltr" style="width:100%;height:280px;display:block"></svg></div>
    <div class="panel-body scroll" style="flex:none"><table class="dt" id="rf-live"></table></div>
  </section>
  <details class="sam-fold panel"><summary${tip('همهٔ اخزاهایی که تاکنون در بورس معامله شده‌اند، سررسیدشده هم: نخستین و آخرین روز معامله، شمار روزهای معامله و ارزش کل.')}>همهٔ اخزاها (${R.bills.length} ورقه؛ سررسیدشده هم)</summary>
    <div class="panel-body scroll" style="max-height:480px"><table class="dt" id="rf-all"></table></div></details>`;
  $('rf-per').querySelectorAll('button').forEach(b => { b.onclick = () => { st.per = b.dataset.v; drawSeries(); }; });
  $('rf-day').onchange = e => { st.day = e.target.value; drawCurve(); };
  $('rf-csv').onclick = () => { const S = R.series; download('rf_daily.csv', [['date', 'rf_vw', 'rf_median', 'rf_1y', 'rf_filled', 'n_bills', 'value_bn'], ...S.date.map((d, i) => [d, S.vw[i], S.med[i], S.y1[i], S.rf[i], S.n[i], S.value_bn[i]])]); };
  kpis(); drawSeries(); drawCurve(); allTable();
}
const ltr = s => `<span dir="ltr" style="unicode-bidi:isolate">${s}</span>`;

function kpis() {
  const S = R.series; let i = S.date.length - 1; while (i > 0 && S.vw[i] == null) i--;
  const yr = S.date.map((d, k) => [d, S.vw[k]]).filter(([d, v]) => v != null && d > S.date[i].replace(/^(\d{4})/, (_, y) => String(+y - 1)));
  const avg = yr.reduce((s, x) => s + x[1], 0) / Math.max(yr.length, 1);
  const cmp = R.bills.filter(b => b.ifb_ytm != null && b.ifb_check != null);
  const dmax = cmp.length ? Math.max(...cmp.map(b => Math.abs(b.ifb_check - b.ifb_ytm))) : NaN;
  const K = [['نرخ روز (وزن ارزش)', pc(S.vw[i], 2), jd(S.date[i]), 'میانگین YTM اخزاهای معامله‌شدهٔ آخرین روز، وزن‌گرفته با ارزش معامله. مبنای نرخ بدون ریسک در «تفکیک فاکتوری صندوق».'],
    ['میانه', pc(S.med[i], 2), `${S.n[i]} ورقه`, 'میانهٔ YTM همان اوراق؛ به یک معاملهٔ بزرگ حساس نیست.'],
    ['یک‌ساله (منحنی)', pc(S.y1[i], 2), 'درون‌یابی در ۳۶۵ روز', 'YTM روی منحنی در سررسید یک‌ساله؛ فقط اگر ورقه‌ای کوتاه‌تر و بلندتر از یک سال معامله شده باشد.'],
    ['میانگین ۱۲ ماه', pc(avg, 1), `${yr.length} روز معامله`, 'میانگین نرخ روزانهٔ وزن ارزش در ۱۲ ماه اخیر.'],
    ['ارزش معامله', f(S.value_bn[i], 0), 'میلیارد ریال', 'ارزش معاملهٔ اخزاهای واردشده در نرخ همان روز.'],
    ['اختلاف با فرابورس', isFinite(dmax) ? f(100 * dmax, 3) : '—', `بیشینه، ${cmp.length} ورقه`, 'YTM با فرمول و تاریخ سررسید ما روی قیمت و روز آخرین معاملهٔ جدول فرابورس، در برابر YTM همان جدول (واحد درصد). صفر یعنی فرمول و سررسید یکی است.']];
  $('rf-kpis').innerHTML = K.map(([k, v, s, t]) => `<div class="kpi"${tip(t)}${DOC}><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`).join('');
  $('rf-chip').textContent = `${jd(S.date[0])} تا ${jd(S.date[S.date.length - 1])}`;
}

function drawSeries() {
  const S = R.series, n = S.date.length;
  $('rf-per').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === st.per)));
  const cut = st.per === 'all' ? '' : (() => { const d = new Date(S.date[n - 1]); d.setFullYear(d.getFullYear() - +st.per); return d.toISOString().slice(0, 10); })();
  const lo = cut ? Math.max(0, S.date.findIndex(d => d >= cut)) : 0;
  const pick = a => a.slice(lo).map(v => v == null ? NaN : 100 * v);
  const ser = [{ v: pick(S.vw), color: 'var(--ch-1)', w: 1.6, name: 'وزن ارزش (سرخط)', fmt: x => f(x, 2) + '٪' },
    { v: pick(S.y1), color: 'var(--warn)', w: 1.1, name: 'یک‌ساله', fmt: x => f(x, 2) + '٪' },
    { v: pick(S.med), color: 'var(--tx-3)', w: 1, dash: '3 3', name: 'میانه', fmt: x => f(x, 2) + '٪' }];
  $('rf-leg').innerHTML = ser.map(s => `<span><i style="color:${s.color}"></i>${s.name}</span>`).join('') + `<span><i style="color:var(--ch-3)"></i>شمار ورقهٔ معامله‌شده</span>`;
  const cs = { i: null }, dates = S.date.slice(lo);
  const draw = () => ChartKit.paneChart($('rf-chart'), dates, [{ frac: 0.78, series: ser, fmt: x => fmt(x, 0) + '٪' },
    { frac: 0.22, zero: true, series: [{ v: S.n.slice(lo).map(v => v || NaN), color: 'var(--ch-3)', w: 1, name: 'شمار ورقه', fmt: x => f(x, 0) }], fmt: x => fmt(x, 0) }], cs);
  ChartKit.attach($('rf-chart'), cs, draw); draw();
}

function drawCurve() {
  const C = R.curves[st.day] || [], svg = $('rf-curve'), W = svg.clientWidth || 800, H = 280, P = { l: 52, r: 16, t: 14, b: 34 };
  const live = R.bills.filter(b => b.live).sort((a, b) => (a.mat || '').localeCompare(b.mat || ''));
  if (!C.length) { svg.innerHTML = ''; return; }
  const xs = C.map(c => c[1]), ys = C.map(c => 100 * c[2]);
  const x0 = 0, x1 = Math.max(...xs) * 1.05, y0 = Math.floor(Math.min(...ys) - 2), y1 = Math.ceil(Math.max(...ys) + 2);
  const X = v => P.l + (v - x0) / (x1 - x0) * (W - P.l - P.r), Y = v => H - P.b - (v - y0) / (y1 - y0) * (H - P.t - P.b);
  const vmax = Math.max(...C.map(c => c[3]), 1e-9);
  const yt = []; for (let v = Math.ceil(y0 / 2) * 2; v <= y1; v += 2) yt.push(v);
  const xt = []; for (let v = 0; v <= x1; v += 180) xt.push(v);
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.innerHTML = `${yt.map(v => `<line x1="${P.l}" x2="${W - P.r}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)" stroke-width="0.5"/><text x="${P.l - 6}" y="${Y(v) + 4}" text-anchor="end" font-size="10" fill="var(--tx-3)">${v}%</text>`).join('')}
    ${xt.map(v => `<text x="${X(v)}" y="${H - P.b + 16}" text-anchor="middle" font-size="10" fill="var(--tx-3)">${v}</text>`).join('')}
    <text x="${(W + P.l) / 2}" y="${H - 4}" text-anchor="middle" font-size="10" fill="var(--tx-3)">روز تا سررسید</text>
    <line x1="${X(365)}" x2="${X(365)}" y1="${P.t}" y2="${H - P.b}" stroke="var(--warn)" stroke-dasharray="3 3" stroke-width="0.8"/>
    ${C.slice().sort((a, b) => a[1] - b[1]).map(c => `<g><circle cx="${X(c[1])}" cy="${Y(100 * c[2])}" r="${3 + 9 * Math.sqrt(c[3] / vmax)}" fill="var(--ch-1)" fill-opacity="0.35" stroke="var(--ch-1)"><title>${esc(c[0])} · ${c[1]} روز · ${f(100 * c[2], 2)}% · ${f(c[3], 1)} میلیارد ریال</title></circle><text x="${X(c[1])}" y="${Y(100 * c[2]) - 9}" text-anchor="middle" font-size="9" fill="var(--tx-2)">${esc(c[0].replace('اخزا', ''))}</text></g>`).join('')}`;
  const hd = [['نماد', ''], ['سررسید', ''], ['روز مانده', 'n'], ['قیمت پایانی', 'n'], ['YTM ما', 'n'], ['روز', ''], ['قیمت فرابورس', 'n'], ['YTM فرابورس', 'n'], ['روز فرابورس', '']];
  const TT = { 'قیمت پایانی': 'قیمت پایانی آخرین روز معامله در داده (ریال).', 'YTM ما': `بازده تا سررسید روی قیمت پایانی و روز تقویمی مانده از همان روز. ورقهٔ کمتر از ${R.min_days} روز مانده «—» است و در نرخ نمی‌آید.`,
    'روز': 'روز آخرین معامله در داده.', 'قیمت فرابورس': 'قیمت آخرین معامله در جدول اسناد خزانهٔ فرابورس؛ ممکن است روزی تازه‌تر از دادهٔ ما باشد، پس YTM دو ستون می‌تواند فرق کند.',
    'YTM فرابورس': 'عدد جدول فرابورس. فرمول و سررسید ما روی همین قیمت و روز همین عدد را می‌دهد (کارت «اختلاف با فرابورس»).', 'روز مانده': 'روز تقویمی از آخرین روز داده تا سررسید.' };
  const today = Date.parse(R.asof);
  $('rf-live').innerHTML = `<thead><tr>${hd.map(([t, c]) => `<th class="${c}"${tip(TT[t] || t)}>${t}</th>`).join('')}</tr></thead><tbody>
    ${live.map(b => { const short = b.last_days != null && b.last_days < R.min_days;
      return `<tr><td>${esc(b.s)}</td><td class="num">${esc(b.mat_j || jd(b.mat))}</td><td class="n">${b.mat ? f((Date.parse(b.mat) - today) / 864e5, 0) : '—'}</td><td class="n">${f(b.last_price, 0)}</td><td class="n"${short ? tip(`کمتر از ${R.min_days} روز به سررسید؛ YTM بی‌معنا بزرگ یا کوچک می‌شود و در نرخ نمی‌آید.`) : ''}>${short ? '—' : pc(b.last_ytm, 2)}</td><td class="num">${jd(b.last)}</td><td class="n">${f(b.ifb_price, 0)}</td><td class="n">${pc(b.ifb_ytm, 2)}</td><td class="num">${esc(b.ifb_last_j || '—')}</td></tr>`; }).join('')}</tbody>`;
}

function allTable() {
  const rows = R.bills.slice().sort((a, b) => (b.mat || '').localeCompare(a.mat || ''));
  $('rf-all').innerHTML = `<thead><tr><th>نماد</th><th${tip('سررسید شمسی (فرابورس، وگرنه از نام TSETMC).')}>سررسید</th><th>وضعیت</th><th>نخستین معامله</th><th>آخرین معامله</th><th class="n"${tip('شمار روزهای دارای معامله.')}>روز معامله</th><th class="n"${tip('جمع ارزش معاملات، میلیارد ریال.')}>ارزش (میلیارد ریال)</th><th class="n"${tip('YTM در آخرین روز معامله (برای ورقهٔ سررسیدشده، نزدیک سررسید و پرنوسان است).')}>آخرین YTM</th></tr></thead><tbody>
    ${rows.map(b => `<tr><td>${esc(b.s)}</td><td class="num">${esc(b.mat_j || '—')}</td><td>${b.live ? '<span class="chip ok">فعال</span>' : '<span class="chip">سررسیدشده</span>'}</td><td class="num">${jd(b.first)}</td><td class="num">${jd(b.last)}</td><td class="n">${f(b.ndays, 0)}</td><td class="n">${f(b.value_bn, 0)}</td><td class="n">${pc(b.last_ytm, 1)}</td></tr>`).join('')}</tbody>`;
}

window.SIM_NEWVIEWS = Object.assign(window.SIM_NEWVIEWS || {}, { rf: { id: 'v-rf', init, redraw: () => { if (document.getElementById('v-rf').dataset.ready && R && R.series) { drawSeries(); drawCurve(); } } } });
})();
