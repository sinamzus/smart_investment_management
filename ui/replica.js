/* SIM — «نمونهٔ کوچک + وام» (بخش شاخص و ماکت) و «دفتر زنده» (بخش اجرا)
   داده: window.SIM_LIVE (tools/build_ui_live.py) از tools/sampled_replica.py و tools/live_ledger.py. هیچ عدد ثابتی در این فایل نیست مگر متن توضیحی. */
(function () {
'use strict';
const D = window.SIM_LIVE || {};
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const f = (x, d = 1) => x == null || x !== x ? '—' : fmt(x, d);
const sg = (x, d = 1) => x == null || x !== x ? '—' : sgn(x, d);
const tip = (t, extra) => ` data-tip="${esc(t)}"${extra || ''}`;
const missing = (id, what, cmd) => { $(id).innerHTML = `<p style="padding:24px">${what} پیدا نشد. اجرا کنید: <code>${cmd}</code></p>`; };

/* ═══════════════ نمونهٔ کوچک + وام ═══════════════ */
const sam = { method: 'opt', lev: 'none', metric: 'te_vs_official_pct' };
const METHODS = { top: 'N بزرگ‌ترین', strat: 'طبقه‌ای (صنعت)', opt: 'بهینه‌سازی TE' };
const COLORS = { top: 'var(--ch-2)', strat: 'var(--warn)', opt: 'var(--ch-1)' };
const METRICS = [['te_vs_official_pct', 'TE در برابر شاخص رسمی (٪)', 'خطای ردیابی سالانه (انحراف معیار بازده روزانهٔ تفاضلی × √۲۵۲) نسبت به «شاخص كل» رسمی؛ کمتر بهتر.'],
  ['te_vs_fullreplica_pct', 'TE در برابر ماکت کامل (٪)', 'فقط خطای نمونه‌گیری: نمونه در برابر خریدِ همهٔ واجدان با وزن بازار؛ خطای وزن/شناوری و داده را ندارد.'],
  ['gap_pct', 'فاصلهٔ بازده سالانه (واحد درصد)', 'بازده سالانهٔ نمونه منهای شاخص رسمی؛ منفی یعنی عقب‌ماندن. این فاصله ریسک نیست و ممکن است به‌علت حذف دم کوچک‌ها سیستماتیک باشد.']];
const STEPS = [
  ['وزن هدف', 'ارزش بازار نمادهای واجد بورس ÷ مجموع؛ تقریب وزن «شاخص كل» (شناور آزاد نداریم).'],
  ['انتخاب N سهم', 'N بزرگ‌ترین؛ یا طبقه‌ای (سهم هر صنعت از N ∝ وزنش)؛ یا بهینه‌سازی: min (w−b)ᵀΣ(w−b) روی ۳N بزرگ‌ترین، فقط‌خرید، Σ انقباضی Ledoit–Wolf روی ۲۵۲ روز، سپس N وزن برتر و حل دوباره.'],
  ['وام / اهرم', 'بدون وام (L = ۱)، یا «تراز بتا»: L = ۱/β با β نمونه روی شاخص (بُرش ۰٫۷ تا ۱٫۵). L > ۱ وام است با نرخ سالانه؛ L < ۱ بخشی نقد بدون بهره.'],
  ['ریبالانس', 'هر پایان ماه جلالی؛ وزن‌ها بین ریبالانس‌ها با بازده رانش می‌کنند؛ وام و L هر ماه بازتنظیم می‌شود.'],
  ['هزینه', 'گردش یک‌طرفه × هزینهٔ رفت‌وبرگشت؛ بهرهٔ وام روزانه از NAV کم می‌شود.'],
  ['ارزیابی', 'بازده روزانه در برابر «شاخص كل» رسمی (بازده کل) و در برابر ماکت ارزش‌وزن کاملِ خودمان (فقط خطای نمونه‌گیری).']];

function initSam() {
  const m = $('v-sam'); m.dataset.ready = 1;
  if (!D.replica) { missing('v-sam', 'نتیجهٔ بازسازی', 'python tools/sampled_replica.py ; python tools/build_ui_live.py'); return; }
  const M = D.replica_meta, FR = M.full_replica;
  m.innerHTML = `
  <section class="panel" style="--lg:var(--lg-a)">
    <div class="panel-head"><span class="lg-badge">1</span><span class="panel-title"${tip('بازسازی «شاخص كل» بدون خرید همهٔ سهام: چند سهم لازم است، چه روشی، و وام چه کاری می‌کند. مراحل به ترتیب اجرا در هر ماه.')}>مراحل بازسازی «شاخص كل» با نمونهٔ کوچک</span></div>
    <div class="lb-flow">${STEPS.map(([t, d], i) => `<div class="lb-step static" data-tip="${esc(d)}"><span class="no">${i + 1}</span><b>${t}</b><small>${esc(d)}</small></div>`).join('')}</div>
  </section>
  <section class="panel" style="--lg:var(--lg-b)">
    <div class="panel-head"><span class="lg-badge">2</span><span class="panel-title"${tip('خطای ردیابی در برابر تعداد سهام نمونه، برای هر روش و حالت اهرم.')}>نتیجه · خطای ردیابی در برابر تعداد سهام</span><span class="chip" id="sm-chip"${tip('بازه، نرخ وام و هزینه‌ای که نتایج با آن محاسبه شده‌اند.')}></span></div>
    <div class="ctl">
      <label${tip('کدام معیار روی نمودار و ستون برجسته نشان داده شود.')}>معیار <select id="sm-metric">${METRICS.map(([k, t]) => `<option value="${k}">${t}</option>`).join('')}</select></label>
      <label${tip('روش انتخاب سهام؛ «همه» هر سه را روی نمودار نشان می‌دهد.')}>روش <span class="seg" id="sm-method"><button data-v="all" aria-pressed="false"${tip('هر سه روش را با هم نشان بده.')}>همه</button>${Object.entries(METHODS).map(([k, t]) => `<button data-v="${k}" aria-pressed="false"${tip('روش انتخاب: ' + t)}>${t}</button>`).join('')}</span></label>
      <label${tip('بدون وام یعنی L = ۱؛ تراز بتا یعنی L = ۱/β (بُرش ۰٫۷–۱٫۵). L < ۱ نقدنگه‌داری است نه وام.')}>اهرم <span class="seg" id="sm-lev"><button data-v="none" aria-pressed="false"${tip('بدون وام و بدون نقد: کاملاً سرمایه‌گذاری‌شده.')}>بدون وام</button><button data-v="beta" aria-pressed="false"${tip('اهرم L = ۱/β هر ماه؛ اگر بتای نمونه > ۱ باشد L < ۱ و بخشی نقد می‌ماند.')}>تراز بتا</button></span></label>
    </div>
    <div class="kpis" id="sm-kpis"></div>
    <div class="panel-body" id="sm-chart" style="padding:var(--s-3)"></div>
    <div class="panel-body scroll" style="max-height:340px"><table class="dt" id="sm-table"></table></div>
    <div class="lineage" id="sm-read"></div>
  </section>`;
  const set = (id, key) => $(id).querySelectorAll('button').forEach(b => { b.onclick = () => { sam[key] = b.dataset.v; renderSam(); }; });
  set('sm-method', 'method'); set('sm-lev', 'lev');
  $('sm-metric').onchange = e => { sam.metric = e.target.value; renderSam(); };
  $('sm-chip').textContent = `${M.from} → ${M.to} · نرخ وام ${f(M.rate * 100, 0)}٪ · هزینه ${f(M.cost_bp, 0)} bp`;
  renderSam();
}
function renderSam() {
  const M = D.replica_meta, FR = M.full_replica, mt = METRICS.find(x => x[0] === sam.metric);
  $('sm-method').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b.dataset.v === (sam.method || 'all')));
  $('sm-lev').querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b.dataset.v === sam.lev));
  const rows = D.replica.filter(r => r.leverage === sam.lev && (sam.method === 'all' || r.method === sam.method));
  const Ns = [...new Set(D.replica.map(r => r.N))].sort((a, b) => a - b);
  const best = k => { const r = D.replica.filter(x => x.leverage === sam.lev && x.method === k && x.te_vs_official_pct <= 2).sort((a, b) => a.N - b.N)[0]; return r ? r.N : null; };
  $('sm-kpis').innerHTML = [['کف خطا (خرید همهٔ واجدان)', f(FR.te_vs_official_pct, 2) + '٪', 'TE ماکت کامل در برابر شاخص رسمی: تفاوت وزن شناور، ترکیب اعضا و داده؛ با نمونه‌گیری کمتر نمی‌شود.'],
    ['کمترین N با TE ≤ ۲٪ (بهینه‌سازی)', best('opt') ? best('opt') + ' سهم' : '—', 'کوچک‌ترین تعداد سهام که در این حالت اهرم، روش بهینه‌سازی TE را به ≤ ۲٪ می‌رساند.'],
    ['کمترین N با TE ≤ ۲٪ (N بزرگ‌ترین)', best('top') ? best('top') + ' سهم' : '—', 'همان برای روش ساده‌تر «N بزرگ‌ترین».'],
    ['نمونهٔ واجد در آخرین ماه', M.n_eligible_last + ' سهم', 'تعداد نمادهای واجد بورس در آخرین ماه (فهرست ماکت کامل).']]
    .map(([k, v, t]) => `<div class="kpi"${tip(t)}><div class="k"${tip(t)}>${k}</div><div class="v">${v}</div></div>`).join('');
  // نمودار خطی: محور x = N (رتبه‌ای)، y = معیار
  const W = 760, H = 220, pl = 46, pr = 14, pt = 12, pb = 26;
  const ms = sam.method === 'all' ? Object.keys(METHODS) : [sam.method];
  const ys = rows.map(r => r[sam.metric]).concat(sam.metric === 'te_vs_official_pct' ? [FR.te_vs_official_pct] : []);
  const lo = Math.min(0, ...ys), hi = Math.max(...ys) * 1.08 || 1, X = i => pl + (W - pl - pr) * (Ns.length > 1 ? i / (Ns.length - 1) : .5), Y = v => pt + (H - pt - pb) * (1 - (v - lo) / (hi - lo));
  let g = '';
  for (let k = 0; k <= 4; k++) { const v = lo + (hi - lo) * k / 4; g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(v)}" y2="${Y(v)}" stroke="var(--line)" stroke-width=".5"/><text x="${pl - 6}" y="${Y(v) + 3}" text-anchor="end" font-size="9" fill="var(--tx-3)">${f(v, 1)}</text>`; }
  g += Ns.map((n, i) => `<text x="${X(i)}" y="${H - 8}" text-anchor="middle" font-size="9" fill="var(--tx-3)">${n}</text>`).join('');
  if (sam.metric === 'te_vs_official_pct') g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(FR.te_vs_official_pct)}" y2="${Y(FR.te_vs_official_pct)}" stroke="var(--down)" stroke-dasharray="4 3"><title>کف خطا: ${f(FR.te_vs_official_pct, 2)}٪</title></line><text x="${W - pr}" y="${Y(FR.te_vs_official_pct) - 4}" text-anchor="end" font-size="9" fill="var(--down)">کف</text>`;
  if (sam.metric === 'gap_pct') g += `<line x1="${pl}" x2="${W - pr}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--tx-3)" stroke-width=".8"/>`;
  ms.forEach(k => {
    const pts = Ns.map((n, i) => { const r = rows.find(x => x.N === n && x.method === k); return r ? [X(i), Y(r[sam.metric]), r] : null; }).filter(Boolean);
    g += `<polyline fill="none" stroke="${COLORS[k]}" stroke-width="1.8" points="${pts.map(p => p[0] + ',' + p[1]).join(' ')}"/>` + pts.map(p => `<circle cx="${p[0]}" cy="${p[1]}" r="3" fill="${COLORS[k]}"><title>${METHODS[k]} · N=${p[2].N}: ${f(p[2][sam.metric], 2)}</title></circle>`).join('');
  });
  const leg = ms.map(k => `<span style="margin-inline-end:14px"><i style="display:inline-block;width:10px;height:3px;background:${COLORS[k]};vertical-align:middle;margin-inline-end:4px"></i>${METHODS[k]}</span>`).join('');
  $('sm-chart').innerHTML = `<div class="mute" style="font-size:var(--fs-xs);margin-bottom:4px" data-tip="${esc(mt[2])}">${mt[1]} · ${sam.lev === 'beta' ? 'تراز بتا' : 'بدون وام'}</div><svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px;direction:ltr">${g}</svg><div class="mute" style="font-size:var(--fs-2xs)">${leg}</div>`;
  const hd = [['N', 'n', 'تعداد سهام نمونه'], ['روش', '', 'روش انتخاب سهام'], ['L̄', 'n', 'میانگین اهرم؛ کمتر از ۱ یعنی بخشی نقد، بیشتر از ۱ یعنی وام.'], ['بازده سالانه', 'n', 'بازده سالانهٔ نمونه (خالص از هزینه و بهرهٔ وام).'], ['شاخص', 'n', 'بازده سالانهٔ شاخص كل رسمی (بازده کل) در همین بازه.'], ['فاصله', 'n', 'بازدهٔ نمونه منهای شاخص (واحد درصد).'], ['TE رسمی', 'n', 'خطای ردیابی در برابر شاخص رسمی (٪).'], ['TE ماکت', 'n', 'خطای نمونه‌گیری در برابر ماکت کامل (٪).'], ['بتا', 'n', 'بتای بازده روزانهٔ نمونه نسبت به شاخص.'], ['همبستگی', 'n', 'همبستگی بازده روزانه با شاخص.'], ['گردش', 'n', 'گردش یک‌طرفهٔ میانگین هر ریبالانس (٪).']];
  $('sm-table').innerHTML = `<thead><tr>${hd.map(([t, c, d]) => `<th class="${c}" data-tip="${esc(d)}">${t}</th>`).join('')}</tr></thead><tbody>` + rows.slice().sort((a, b) => a.N - b.N || a.method.localeCompare(b.method)).map(r => `<tr><td class="n">${r.N}</td><td>${METHODS[r.method]}</td><td class="n">${f(r.mean_L, 2)}</td><td class="n">${f(r.ann_pct)}٪</td><td class="n">${f(r.ann_index_pct)}٪</td><td class="n ${r.gap_pct >= 0 ? 'up' : 'down'}">${sg(r.gap_pct)}</td><td class="n">${f(r.te_vs_official_pct, 2)}</td><td class="n">${f(r.te_vs_fullreplica_pct, 2)}</td><td class="n">${f(r.beta, 2)}</td><td class="n">${f(r.corr, 3)}</td><td class="n">${f(r.turnover_oneway_pct, 0)}٪</td></tr>`).join('') + '</tbody>';
  const nb = D.replica.filter(r => r.leverage === 'beta'), nn = D.replica.filter(r => r.leverage === 'none');
  const dTE = (nn.reduce((a, r, i) => a + (r.te_vs_official_pct - (nb.find(x => x.N === r.N && x.method === r.method) || r).te_vs_official_pct), 0) / nn.length), dR = (nn.reduce((a, r) => a + (r.ann_pct - (nb.find(x => x.N === r.N && x.method === r.method) || r).ann_pct), 0) / nn.length);
  $('sm-read').innerHTML = `<span><b data-tip="برداشت خودکار از همین جدول؛ با تغییر داده دوباره حساب می‌شود.">خوانش</b> تعداد سهام در خطای ردیابی از اهرم مهم‌تر است؛ «تراز بتا» به‌طور میانگین TE را ${f(dTE, 1)} واحد کم و بازده را ${f(dR, 1)} واحد کم می‌کند (چون بتای نمونه > ۱ است و L < ۱ نقدنگه‌داری می‌شود، نه وام).</span><span><b data-tip="آنچه این نتایج را محدود می‌کند: بدون صف و حد نوسان، نرخ وام فرضی، درون‌نمونه.">محدودیت</b> بدون صف/حد نوسان؛ نرخ و دسترسی وام واقعی نیست <i>[تأیید لازم]</i>؛ عقب‌ماندن بازدهِ نمونه‌های بهینه نشانهٔ حذف دم کوچک‌هاست؛ جزئیات: فصل ۳ §۳٫۵.</span>`;
}

/* ═══════════════ دفتر زنده ═══════════════ */
function initLive() {
  const m = $('v-live'); m.dataset.ready = 1;
  const S = D.strategy, O = D.orders;
  if (!S) { missing('v-live', 'استراتژی قفل‌شده', 'python tools/live_ledger.py freeze ; python tools/build_ui_live.py'); return; }
  const B = S.backtest_in_sample, sp = S.spec;
  const specTxt = `${sp.signals.map(([n]) => n).join(' + ')} · ${sp.combine === 'rank' ? 'امتیاز رتبه‌ای' : sp.combine} · ${sp.algo} (ورود ${sp.params.entry}، خروج ${sp.params.exit}) · κ = ${sp.partial} · ${sp.universe.markets.join('+')}`;
  const track = D.track || [], closed = track.filter(r => r.open !== 'True' && r.open !== true && r.open !== 'true');
  m.innerHTML = `
  <section class="panel" style="--lg:var(--lg-a)">
    <div class="panel-head"><span class="lg-badge">1</span><span class="panel-title"${tip('استراتژی نامزدی که مشخصاتش یک‌بار قفل و هش شده؛ تغییر آن نسخهٔ جدید می‌خواهد. شواهد بیرون‌نمونه فقط از همین دفتر می‌آید.')}>استراتژی قفل‌شده</span><span class="chip warn"${tip('پیش از ۶ ریبالانس رسمی قضاوت و تغییر مشخصات مجاز نیست.')}>${esc(S.id)}</span></div>
    <div class="kpis">${[['هش مشخصات', S.spec_hash, 'SHA-256 کوتاه‌شدهٔ مشخصات؛ ابزار هنگام اجرا آن را بازبینی می‌کند.'], ['قفل شده', (S.frozen_at || '').slice(0, 10), 'تاریخ قفل‌کردن مشخصات.'], ['داده تا', S.data_through, 'آخرین روز دادهٔ هنگام قفل.'],
      ['برتری درون‌نمونه', sg(B.excess_net) + '٪', 'برتری خالص سالانه نسبت به هم‌وزن واجدان در بک‌تست؛ درون‌نمونه است و شاهد بیرون‌نمونه نیست.'], ['t درون‌نمونه', f(B.t_net, 2), 'آمارهٔ t نیوی‌وست برتری خالص (درون‌نمونه؛ آزمایش ۱۲۱ام).'], ['برتری ماهانهٔ مورد انتظار', sg(B.monthly_mean_excess_net * 100, 2) + '٪', 'میانگین برتری ماهانه در بک‌تست؛ مبنای مقایسه در رهگیری.']]
      .map(([k, v, t]) => `<div class="kpi"${tip(t)}><div class="k"${tip(t)}>${k}</div><div class="v num">${v}</div></div>`).join('')}</div>
    <div class="lineage"><span><b data-tip="ترکیب معیارها، روش ترکیب، الگوریتم انتخاب و پارامترهای قفل‌شده.">مشخصات</b> ${esc(specTxt)}</span><span><b data-tip="قاعدهٔ زمانی و ریبالانس استراتژی: سیگنال، اجرا، شروع سرد و ریبالانس جزئی.">قاعده</b> سیگنال: آخرین روز معاملاتی ماه جلالی · اجرا: روز بعد · شروع سرد κ=۱ سپس ${sp.partial}</span><span><b data-tip="چه زمانی و چگونه می‌شود استراتژی را بازبینی کرد: پس از ۶ ریبالانس رسمی.">بازنگری</b> ${esc(S.rules.review)}</span></div>
  </section>
  <section class="panel" style="--lg:var(--lg-b)">
    <div class="panel-head"><span class="lg-badge">2</span><span class="panel-title"${tip('آخرین دستور اجرای ساخته‌شده؛ پیش‌نویس میان‌ماه ثبت رسمی نمی‌شود و فقط برای دیدن است.')}>آخرین دستور اجرا</span>${O ? `<span class="chip ${O.official_month_end ? 'ok' : 'warn'}"${tip(O.official_month_end ? 'ریبالانس رسمی پایان ماه؛ قابل ثبت در دفتر.' : 'پیش‌نویس میان‌ماه: ثبت رسمی ندارد.')}>${O.official_month_end ? 'رسمی' : 'پیش‌نویس میان‌ماه'}</span>` : ''}
      <div class="panel-tools"><button class="tool" id="lv-csv"${tip('دستورهای خرید و فروش به‌صورت CSV.')}>CSV</button><button class="tool" id="lv-json"${tip('فایل sim.trade_plan/1 برای سامانهٔ الگوریتمی (فصل ۹ §۹٫۲٫۱).')}>JSON برای سامانهٔ الگوریتمی</button></div></div>
    <div class="panel-body scroll" style="max-height:420px"><table class="dt" id="lv-orders"></table></div>
    <div class="lineage" id="lv-orders-lin"></div>
  </section>
  <section class="panel" style="--lg:var(--lg-c)">
    <div class="panel-head"><span class="lg-badge">3</span><span class="panel-title"${tip('برتری واقعی پرتفوی کاغذی نسبت به هم‌وزن واجدان در هر ریبالانس رسمی، در برابر برتری مورد انتظار بک‌تست.')}>رهگیری بیرون‌نمونه</span></div>
    <div class="panel-body scroll" id="lv-track" style="padding:var(--s-3)"></div>
    <div class="lineage"><span><b data-tip="دستورهایی که باید روی سیستم خودتان اجرا کنید تا این صفحه به‌روز شود.">به‌روزرسانی (روی سیستم شما)</b> <code>python tools/live_ledger.py orders --aum 1e11 --accept</code> سپس <code>python tools/live_ledger.py track</code> و <code>python tools/build_ui_live.py</code> و push</span></div>
  </section>`;
  if (O) {
    const rows = O.orders.slice().sort((a, b) => a.side.localeCompare(b.side) || b.value_rial - a.value_rial);
    const hd = [['عملیات', '', 'خرید یا فروش برای رسیدن به وزن هدف.'], ['نماد', '', 'نماد.'], ['بازار', '', 'بورس یا فرابورس.'], ['تعداد', 'n', 'تعداد سهم = ارزش ÷ قیمت مرجع.'], ['قیمت مرجع', 'n', 'آخرین بسته؛ سامانه باید با قیمت زنده و دامنهٔ مجاز نوسان جایگزین کند.'], ['ارزش (میلیون ریال)', 'n', '|Δوزن| × ارزش پرتفوی.'], ['وزن فعلی ٪', 'n', 'وزن رانش‌یافتهٔ فعلی.'], ['وزن هدف ٪', 'n', 'وزن پس از معامله.'], ['مشارکت ADV', 'n', 'ارزش معامله ÷ میانگین ارزش معاملات ۶۳ روز؛ بالای ۰٫۱ یعنی چندروزه.'], ['روز', 'n', 'روزهای لازم با سقف ۱۰٪ ADV.']];
    $('lv-orders').innerHTML = `<thead><tr>${hd.map(([t, c, d]) => `<th class="${c}" data-tip="${esc(d)}">${t}</th>`).join('')}</tr></thead><tbody>` + rows.map(o => `<tr><td class="${o.side === 'BUY' ? 'up' : 'down'}">${o.side === 'BUY' ? 'خرید' : 'فروش'}</td><td><a class="symlink" data-sym="${esc(o.symbol)}" href="#">${esc(o.symbol)}</a></td><td>${o.market === 'bourse' ? 'بورس' : 'فرابورس'}</td><td class="n">${f(o.qty, 0)}</td><td class="n">${f(o.ref_price, 0)}</td><td class="n">${f(o.value_rial / 1e6, 1)}</td><td class="n">${f(o.w_now_pct, 2)}</td><td class="n">${f(o.w_target_pct, 2)}</td><td class="n">${o.adv_participation == null ? '—' : f(o.adv_participation, 3)}</td><td class="n">${o.split_days}</td></tr>`).join('') + '</tbody>';
    $('lv-orders-lin').innerHTML = `<span><b data-tip="آخرین روز دادهٔ این دستور؛ سیگنال در پایان همین روز.">تاریخ سیگنال</b> <span class="num">${O.asof}</span></span><span><b data-tip="ارزش فرضی پرتفوی که سفارش‌ها برایش اندازه شده‌اند.">ارزش پرتفوی</b> ${f(O.aum_rial / 1e9, 0)} میلیارد ریال</span><span><b data-tip="تعداد نمادهای پرتفوی هدف.">نماد در پرتفوی</b> ${O.n_hold}</span><span><b data-tip="مجموع خریدها (= فروش‌ها) به‌صورت سهمی از ارزش پرتفوی.">گردش یک‌طرفه</b> ${f(O.turnover_oneway * 100, 0)}٪</span><span><b data-tip="${O.cold_start ? 'نخستین ریبالانس: کل وزن هدف خریده می‌شود (κ = ۱).' : 'ریبالانس جزئی: فقط بخشی (κ) از فاصلهٔ وزن فعلی تا هدف.'}">${O.cold_start ? 'شروع سرد (κ = 1)' : 'ریبالانس جزئی'}</b></span>`;
    $('lv-csv').onclick = () => download(`orders_${O.asof}.csv`, [['action', 'symbol', 'market', 'qty', 'ref_price', 'value_rial', 'w_now_pct', 'w_target_pct', 'adv_participation', 'split_days'], ...rows.map(o => [o.side, o.symbol, o.market, o.qty, o.ref_price, Math.round(o.value_rial), o.w_now_pct.toFixed(3), o.w_target_pct.toFixed(3), o.adv_participation == null ? '' : o.adv_participation.toFixed(4), o.split_days])]);
    $('lv-json').onclick = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(O, null, 1)], { type: 'application/json' })); a.download = `trade_plan_${O.plan_id}.json`; a.click(); };
  } else $('lv-orders').innerHTML = '<tbody><tr><td class="mute">هنوز دستوری ساخته نشده: <code>python tools/live_ledger.py orders</code></td></tr></tbody>';
  if (!track.length) $('lv-track').innerHTML = `<p class="mute">دفتر خالی است؛ هنوز ریبالانس رسمی ثبت نشده. نخستین دستور رسمی را در آخرین روز معاملاتی ماه جلالی (پایان مهر ۱۴۰۵) بگیرید و با <code>--accept</code> ثبت کنید. تا ۶ ریبالانس رسمی استراتژی را قضاوت یا تغییر ندهید.</p>`;
  else {
    const mu = B.monthly_mean_excess_net, sd = B.monthly_std_excess_net, n = closed.length, cum = closed.reduce((a, r) => a + r.excess_net_vs_ALL, 0), z = n ? (cum - n * mu) / (sd * Math.sqrt(n)) : NaN;
    $('lv-track').innerHTML = `<div class="kpis"><div class="kpi"${tip('تعداد ریبالانس‌های رسمی کامل‌شده.')}><div class="k"${tip('تعداد ریبالانس‌های رسمی کامل‌شده.')}>دوره‌ها</div><div class="v">${n}</div></div><div class="kpi"${tip('مجموع برتری خالص دوره‌ها نسبت به هم‌وزن واجدان.')}><div class="k"${tip('مجموع برتری خالص دوره‌ها نسبت به هم‌وزن واجدان.')}>برتری تجمعی</div><div class="v">${sg(cum * 100, 2)}٪</div></div><div class="kpi"${tip('برتری تجمعی مورد انتظار = تعداد دوره × میانگین ماهانهٔ بک‌تست.')}><div class="k"${tip('برتری تجمعی مورد انتظار = تعداد دوره × میانگین ماهانهٔ بک‌تست.')}>مورد انتظار</div><div class="v">${sg(n * mu * 100, 2)}٪</div></div><div class="kpi"${tip('z = (تجمعی واقعی − n·μ) ÷ (σ·√n)؛ زیر −۲ نشانهٔ ناپایداری و مبنای بازبینی است، نه حذف خودکار.')}><div class="k"${tip('z = (تجمعی واقعی − n·μ) ÷ (σ·√n)؛ زیر −۲ نشانهٔ ناپایداری و مبنای بازبینی است، نه حذف خودکار.')}>z</div><div class="v">${f(z, 2)}</div></div></div>
      <table class="dt"><thead><tr>${['سیگنال', 'تا تاریخ', 'روز', 'بازده استراتژی ٪', 'هم‌وزن ٪', 'ارزش‌وزن ٪', 'برتری خالص ٪', 'گردش'].map(t => `<th data-tip="${esc(t)} در این دوره">${t}</th>`).join('')}</tr></thead><tbody>${track.map(r => `<tr><td class="num">${r.signal_date}</td><td class="num">${r.to_date}</td><td class="n">${r.days}</td><td class="n">${f(r.ret_S * 100, 2)}</td><td class="n">${f(r.ret_ALL * 100, 2)}</td><td class="n">${f(r.ret_CAP * 100, 2)}</td><td class="n ${r.excess_net_vs_ALL >= 0 ? 'up' : 'down'}">${sg(r.excess_net_vs_ALL * 100, 2)}</td><td class="n">${r.turnover_oneway == null || r.turnover_oneway !== r.turnover_oneway ? '—' : f(r.turnover_oneway * 100, 0) + '٪'}</td></tr>`).join('')}</tbody></table>`;
  }
}

window.SIM_NEWVIEWS = Object.assign(window.SIM_NEWVIEWS || {}, {
  sam: { id: 'v-sam', init: initSam, redraw: () => { } },
  live: { id: 'v-live', init: initLive, redraw: () => { } },
});
})();
