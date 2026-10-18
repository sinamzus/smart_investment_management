/* ماکت — میز پژوهش (Lab) · معیارها (Signals) · برنامهٔ اقدام (Plan)  — فصل ۱۴
   داده: window.SIM_LAB (tools/build_lab.py)؛ موتور: labengine.js. هیچ عدد ثابتی در این فایل نیست مگر پیش‌فرض‌های کنترل‌ها. */
(function () {
'use strict';
const E = window.LabEngine;
const $$ = (sel, root) => (root || document).querySelector(sel);
const $$$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));
const jyf = new Intl.DateTimeFormat('fa-IR-u-ca-persian-nu-latn', { year: 'numeric' });
const jy = d => jyf.format(new Date(d + 'T00:00:00Z'));
const store = { get: k => { try { return JSON.parse(localStorage.getItem('sim.lab.' + k)); } catch (e) { return null; } }, set: (k, v) => { try { localStorage.setItem('sim.lab.' + k, JSON.stringify(v)); } catch (e) { /* بی‌اهمیت */ } } };
let L = null, CTX = null, pending = null;
const FAM = { momentum: 'مومنتوم و روند', risk: 'ریسک و نوسان', liquidity: 'نقدشوندگی و اندازه', investment: 'سرمایه‌گذاری و سود', quality: 'کیفیت (بنیادی)', value: 'ارزش (بنیادی)' };
const FAMCOL = { momentum: 'var(--ch-2)', risk: 'var(--ch-3)', liquidity: 'var(--warn)', investment: 'var(--up)', quality: 'var(--accent-tx)', value: 'var(--down)' };
const f1 = (x, d = 1) => x == null || x !== x ? '—' : fmt(x, d);
const sg1 = (x, d = 1) => x == null || x !== x ? '—' : sgn(x, d);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function sbars(el, labels, vals, f, mark, base) {
  const mx = Math.max(...vals, base ?? 0, 0), mn = Math.min(...vals, base ?? 0, 0), span = (mx - mn) || 1, zero = mx / span * 100;
  el.innerHTML = '<div class="sb-wrap">' + (base != null ? `<div class="sb-base" style="top:${(mx - base) / span * 100}%" title="مرجع: ${f(base)}"></div>` : '') + `<div class="sb-zero" style="top:${zero}%"></div>` + vals.map((v, i) => {
    const h = Math.abs(v) / span * 100, top = v >= 0 ? zero - h : zero;
    return `<div class="sb" title="${esc(labels[i])}: ${f(v)}"><div class="bar ${v >= 0 ? 'pos' : 'neg'} ${mark && mark(i) ? 'hi' : ''}" style="top:${top}%;height:${Math.max(h, 0.6)}%"></div><em style="top:${v >= 0 ? top : top + h}%;transform:translateY(${v >= 0 ? '-110%' : '4px'})">${f(v)}</em><span>${esc(labels[i])}</span></div>`;
  }).join('') + '</div>';
}
const tcls = t => t == null || t !== t ? '' : Math.abs(t) >= 3 ? (t > 0 ? 'up' : 'down') : Math.abs(t) >= 2 ? (t > 0 ? 'up' : 'down') : '';

function ensureData(cb) {
  if (L) return cb();
  if (pending) return pending.push(cb);
  pending = [cb];
  const s = document.createElement('script'); s.src = 'data/lab.js';
  s.onload = () => { L = window.SIM_LAB; CTX = E.load(L); const q = pending; pending = null; q.forEach(f => f()); };
  s.onerror = () => { pending = null; ['v-lab', 'v-sig', 'v-plan'].forEach(id => { const m = $(id); if (m && !m.dataset.ready) m.innerHTML = '<p style="padding:24px">ui/data/lab.js پیدا نشد. اجرا کنید: <code>python tools/build_lab.py</code></p>'; }); };
  document.head.appendChild(s);
}
const toRes = r => ({ cap: r.cap || [], toCap: (r.to_cap || []).map(v => v == null ? NaN : v), impact: (L.aums || []).map(a => ((r.impact || {})[String(a)] || []).map(v => v == null ? NaN : v)), end: r.end, ret: r.ret, all: r.all, to: r.to.map(v => v == null ? NaN : v), toAll: (r.to_all || r.all.map(() => 0)).map(v => v == null ? NaN : v), n: r.ret.map(() => r.stats.names), ic: (r.ic_series || r.ret.map(() => NaN)).map(v => v == null ? NaN : v) });
const sigName = n => (L.signals.find(s => s.name === n) || {}).fa || n;
const sigMeta = n => L.signals.find(s => s.name === n);
const isJS = spec => E.JS_ALGOS.includes(spec.algo) && !['fm_lib'].includes(spec.combine);

/* ════════════════════════════════ LAB ════════════════════════════════ */
const lab = { bench: 'eq', spec: null, res: null, st: null, tab: 'perf', saved: [], overlay: new Set(), trials: 0, view: null, dec: null, srLib: null, cost: 100 };
const DEFAULT = { signals: [['vol_252', 1], ['size', 1], ['div_yield', 1]], combine: 'equal', neutral: true, algo: 'topfrac', params: { entry: 0.2, exit: 0.3 }, universe: { markets: ['bourse', 'farabourse'], min_adv: 0 }, rebalance_every: 1, partial: 1, max_w: null, cost_bp: 100 };
const PRESETS = {
  'کم‌نوسان': { signals: [['vol_252', 1]], combine: 'equal' },
  'مومنتوم ۱۲−۱': { signals: [['mom_12_1', 1]], combine: 'equal' },
  'ارزش + سود': { signals: [['ep', 1], ['div_yield', 1]], combine: 'equal' },
  'کیفیت': { signals: [['q_roe', 1], ['q_roa', 1], ['q_low_da', 1]], combine: 'equal' },
  'چندعاملی: ریسک+اندازه+سود': { signals: [['vol_252', 1], ['size', 1], ['div_yield', 1]], combine: 'equal' },
  'کیفیت + ارزش + کم‌نوسان': { signals: [['q_roe', 1], ['ep', 1], ['vol_252', 1]], combine: 'rank' },
  'انتخاب پویای ۵ معیار': { signals: null, combine: 'topk_icir', topk: 5 },
};
const COMB = [['equal', 'میانگین وزنی Z'], ['rank', 'میانگین رتبه‌ای'], ['ic', 'وزن‌دهی با IC (۳۶ ماه)'], ['icir', 'وزن‌دهی با ICIR'], ['fm', 'وزن Fama–MacBeth'], ['ridge', 'ریج (FM با جریمه)'], ['topk_icir', 'انتخاب پویای k معیار برتر']];

function initLab() {
  const m = $('v-lab'); m.dataset.ready = 1;
  m.innerHTML = `
  <section class="panel lb-builder" style="--lg:var(--lg-a)">
    <div class="panel-head"><span class="lg-badge">B</span><span class="panel-title">ساخت استراتژی</span>
      <div class="panel-tools"><button class="tool" id="lb-reset" title="بازنشانی به پیش‌فرض">بازنشانی</button></div></div>
    <div class="panel-body scroll lb-body">
      <div class="lb-presets" id="lb-presets"></div>
      <details open><summary>۱ · جهان سهام</summary><div class="lb-sec">
        <label class="lb-row"><input type="checkbox" id="lb-m0" checked> بورس</label><label class="lb-row"><input type="checkbox" id="lb-m1" checked> فرابورس</label>
        <label class="lb-row">حداقل ارزش معاملات روزانه <select id="lb-adv"><option value="0">بدون</option><option value="1e8">۱۰۰ میلیون ریال</option><option value="5e8">۵۰۰ میلیون ریال</option><option value="2e9">۲ میلیارد ریال</option><option value="1e10">۱۰ میلیارد ریال</option></select></label>
        <label class="lb-row">ریبالانس هر <select id="lb-every"><option value="1">۱ ماه</option><option value="3">۳ ماه</option><option value="6">۶ ماه</option></select></label></div></details>
      <details open><summary>۲ · معیارها</summary><div class="lb-sec">
        <div id="lb-sigs"></div>
        <div class="lb-add"><input id="lb-q" placeholder="جست‌وجوی معیار…" list="lb-dl" autocomplete="off"><datalist id="lb-dl"></datalist><button class="tool" id="lb-addbtn">+ افزودن</button></div>
        <div class="lb-hint">وزن منفی = معکوس‌کردن جهت. جهت پیش‌فرض هر معیار «بالاتر = بازده مورد انتظار بیشتر» بر پایهٔ ادبیات است.</div></div></details>
      <details open><summary>۳ · ترکیب</summary><div class="lb-sec">
        <label class="lb-row">روش <select id="lb-comb"></select></label>
        <label class="lb-row" id="lb-topk-row" hidden>k <input type="number" id="lb-topk" min="1" max="20" value="5"></label>
        <label class="lb-row"><input type="checkbox" id="lb-neu" checked> خنثی‌سازی صنعتی</label></div></details>
      <details open><summary>۴ · الگوریتم انتخاب و وزن‌دهی</summary><div class="lb-sec">
        <label class="lb-row">الگوریتم <select id="lb-algo"></select></label><div id="lb-params"></div><div class="lb-hint" id="lb-algodesc"></div>
        <div class="lb-hint">الگوریتم‌های ریسکی (min-var، ERC، HRP، max-div، MVO) به کوواریانس نیاز دارند و در تب «کتابخانه» از پیش محاسبه شده‌اند.</div></div></details>
      <details open><summary>۵ · اصطکاک</summary><div class="lb-sec">
        <label class="lb-row">هزینهٔ رفت‌وبرگشت <input type="number" id="lb-cost" min="0" max="500" step="10" value="100"> bp</label>
        <label class="lb-row">ریبالانس جزئی <input type="number" id="lb-part" min="10" max="100" step="10" value="100"> ٪</label>
        <label class="lb-row">سقف وزن هر نماد <input type="number" id="lb-maxw" min="0" max="100" step="1" value="0"> ٪ (۰ = بدون)</label></div></details>
      <div class="lb-run"><button class="btn" id="lb-run">اجرا</button><button class="tool" id="lb-save">ذخیرهٔ این اجرا</button><span class="lb-cnt" id="lb-cnt"></span></div>
    </div>
  </section>
  <section class="panel lb-main" style="--lg:var(--lg-b)">
    <div class="panel-head"><span class="lg-badge">R</span><span class="panel-title" id="lb-title">نتیجه</span><span class="chip" id="lb-chip"></span>
      <div class="seg" id="lb-tabs"><button data-t="perf" aria-pressed="true">عملکرد</button><button data-t="dec" aria-pressed="false">دهک‌ها</button><button data-t="ic" aria-pressed="false">IC و پریمیوم</button><button data-t="stab" aria-pressed="false">پایداری</button><button data-t="hard" aria-pressed="false">آمار سخت</button><button data-t="cap" aria-pressed="false">ظرفیت</button><button data-t="live" aria-pressed="false">پرتفوی زنده</button></div>
      <div class="panel-tools"><button class="tool" id="lb-csv">CSV</button></div></div>
    <div class="ctl"><label data-tip="مرجع سنجش برتری: هم‌وزن واجدان پریمیوم اندازه/نقدناپذیری را در خود دارد؛ ارزش‌وزن واجدان مرجع مدیرِ ارزش‌وزن است.">مرجع <span class="seg" id="lb-bench"><button data-b="eq" aria-pressed="true">هم‌وزن واجدان</button><button data-b="cap" aria-pressed="false">ارزش‌وزن واجدان</button></span></label>
      <span class="mute" data-tip="با تغییر مرجع، همهٔ ستون‌های برتری، آمار t، نسبت اطلاعاتی (IR)، نیمه‌ها و حکم دوباره نسبت به همان مرجع حساب می‌شوند؛ خود بازده استراتژی عوض نمی‌شود.">برتری، t، IR، پایداری و حکم همه نسبت به این مرجع‌اند</span></div>
    <details class="lb-flowbox"><summary data-tip="ترتیب دقیق محاسبه در هر ماه شبیه‌سازی؛ برای دیدن مقدار هر مرحله (از تنظیمات همین لحظهٔ سازنده) باز کنید؛ کلیک روی هر مرحله بخش مربوط را باز می‌کند."><span class="ttl">روند ساخت و ترتیب شبیه‌سازی</span><span class="lb-mini" id="lb-mini"></span></summary><div class="lb-flow" id="lb-flow"></div></details>
    <div class="kpis" id="lb-kpis"></div>
    <div class="panel-body scroll" id="lb-view"></div>
    <div class="lineage" id="lb-lin"></div>
  </section>
  <section class="panel lb-side" style="--lg:var(--lg-c)">
    <div class="panel-head"><span class="lg-badge">S</span><span class="panel-title">اجراها و کتابخانه</span>
      <div class="seg" id="lb-stabs"><button data-t="saved" aria-pressed="true">من</button><button data-t="lib" aria-pressed="false">کتابخانه</button></div></div>
    <div class="ctl" id="lb-libctl" hidden><label>گروه <select id="lb-libgrp"><option value="">همه</option><option value="sig">تک‌معیار</option><option value="algo">الگوریتم‌ها</option><option value="combo">ترکیب‌ها</option><option value="sens">حساسیت‌ها</option><option value="ref">مرجع Factor Lab</option></select></label>
      <label>مرتب <select id="lb-libsort"><option value="t_net">t خالص</option><option value="excess_net">برتری خالص</option><option value="ir">IR</option><option value="turn_ann">گردش</option></select></label></div>
    <div class="panel-body scroll"><table class="dt" id="lb-list"></table></div>
    <div class="lineage" id="lb-side-lin"></div>
  </section>`;
  // پیش‌تنظیم‌ها
  $('lb-presets').innerHTML = Object.keys(PRESETS).map(k => `<button class="tool pre" data-p="${esc(k)}" data-tip="پیش‌تنظیم «${esc(k)}»: معیارها و روش ترکیب را می‌چیند و اجرا می‌کند؛ بعد می‌توانید دست‌کاری کنید.">${esc(k)}</button>`).join('');
  $$$('#lb-presets .pre').forEach(b => b.onclick = () => applyPreset(b.dataset.p));
  $('lb-comb').innerHTML = COMB.map(([v, t]) => `<option value="${v}">${t}</option>`).join('');
  $('lb-algo').innerHTML = L.algos.filter(a => E.JS_ALGOS.includes(a.name)).map(a => `<option value="${a.name}">${a.fa}</option>`).join('');
  const fams = {}; L.signals.forEach(s => (fams[s.family] = fams[s.family] || []).push(s));
  $('lb-dl').innerHTML = L.signals.map(s => `<option value="${esc(s.fa)}">${esc(FAM[s.family] || s.family)} · ${s.name}</option>`).join('');
  $('lb-comb').onchange = syncBuilder; $('lb-algo').onchange = () => { lab.spec.algo = $('lb-algo').value; lab.spec.params = {}; renderParams(); };
  $('lb-addbtn').onclick = addSignalFromBox; $('lb-q').onkeydown = e => { if (e.key === 'Enter') addSignalFromBox(); };
  $('lb-run').onclick = () => runLab(true); $('lb-save').onclick = saveRun; $('lb-reset').onclick = () => { setSpec(JSON.parse(JSON.stringify(DEFAULT))); runLab(true); };
  $$$('#lb-tabs button').forEach(b => b.onclick = () => { lab.tab = b.dataset.t; $$$('#lb-tabs button').forEach(x => x.setAttribute('aria-pressed', x === b)); renderTab(); });
  $$$('#lb-stabs button').forEach(b => b.onclick = () => { lab.side = b.dataset.t; $$$('#lb-stabs button').forEach(x => x.setAttribute('aria-pressed', x === b)); renderSide(); });
  ['lb-libgrp', 'lb-libsort'].forEach(i => { $(i).onchange = renderSide; });
  $$$('#lb-bench button').forEach(b => b.onclick = () => { lab.bench = b.dataset.b; $$$('#lb-bench button').forEach(x => x.setAttribute('aria-pressed', x === b)); if (lab.res) { lab.st = E.stats(lab.res, lab.cost, jy, lab.bench); renderKPIs(); renderTab(); renderSide(); } });
  $('lb-csv').onclick = exportRunCSV;
  const bd = m.querySelector('.lb-body'); ['change', 'input', 'click'].forEach(ev => bd.addEventListener(ev, () => setTimeout(renderFlow, 0)));
  lab.side = 'saved';
  lab.saved = store.get('saved') || [];
  lab.srLib = L.library.map(r => { const c = lab.cost / 1e4, ex = r.ret.map((v, i) => v - (r.to[i] || 0) * c - (r.all[i] - (r.to_all && r.to_all[i] || 0) * c)); const m = ex.reduce((a, b) => a + b, 0) / ex.length, s = Math.sqrt(ex.reduce((a, b) => a + (b - m) ** 2, 0) / (ex.length - 1)); return s > 0 ? m / s : NaN; }).filter(x => x === x);
  const saved = store.get('spec');
  setSpec(saved && saved.signals && saved.signals.every(([n]) => CTX.Z[n]) ? saved : JSON.parse(JSON.stringify(DEFAULT)));
  runLab(false);
  renderSide();
  renderFlow();
}
function applyPreset(k) {
  const p = PRESETS[k], s = JSON.parse(JSON.stringify(lab.spec));
  if (p.signals) s.signals = p.signals.filter(([n]) => CTX.Z[n]); else s.signals = L.signals.filter(x => x.needs !== 'fund').map(x => [x.name, 1]);
  s.combine = p.combine; if (p.topk) s.topk = p.topk;
  setSpec(s); runLab(true);
}
function setSpec(s) {
  lab.spec = s;
  $('lb-m0').checked = !s.universe || !s.universe.markets || s.universe.markets.includes('bourse');
  $('lb-m1').checked = !s.universe || !s.universe.markets || s.universe.markets.includes('farabourse');
  $('lb-adv').value = String((s.universe && s.universe.min_adv) || 0).replace('000000000', 'e9').replace('00000000', 'e8');
  [...$('lb-adv').options].forEach(o => { if (+o.value === ((s.universe && s.universe.min_adv) || 0)) $('lb-adv').value = o.value; });
  $('lb-every').value = String(s.rebalance_every || 1); $('lb-comb').value = s.combine || 'equal'; $('lb-topk').value = s.topk || 5; $('lb-neu').checked = s.neutral !== false;
  $('lb-algo').value = E.JS_ALGOS.includes(s.algo) ? s.algo : 'topfrac'; $('lb-cost').value = s.cost_bp ?? 100; $('lb-part').value = Math.round((s.partial ?? 1) * 100); $('lb-maxw').value = Math.round((s.max_w || 0) * 100);
  renderSigs(); renderParams(); syncBuilder();
}
function syncBuilder() { $('lb-topk-row').hidden = $('lb-comb').value !== 'topk_icir'; }
function renderSigs() {
  const el = $('lb-sigs');
  el.innerHTML = lab.spec.combine === 'topk_icir' && lab.spec.signals.length > 12 ? `<div class="lb-hint">${lab.spec.signals.length} معیار نامزد (همهٔ معیارهای قیمتی)؛ k برتر هر ماه از روی ICIR ۳۶ ماه گذشته انتخاب می‌شود.</div>` :
    lab.spec.signals.map(([n, w], i) => { const m = sigMeta(n); return `<div class="lb-sig" data-i="${i}"><span class="fam" style="background:${FAMCOL[m.family]}"></span><span class="nm has-tip" data-tip="${esc(m.fa)} — ${esc(m.formula)} · مرجع: ${esc(m.ref)}">${esc(m.fa)}</span>
      <input type="range" min="-2" max="2" step="0.25" value="${w}" class="w"><output>${w}</output><button class="tool x" title="حذف">×</button></div>`; }).join('') || '<div class="lb-hint">معیاری انتخاب نشده.</div>';
  $$$('.lb-sig', el).forEach(r => { const i = +r.dataset.i; $$('.w', r).oninput = e => { lab.spec.signals[i][1] = +e.target.value; $$('output', r).textContent = e.target.value; }; $$('.x', r).onclick = () => { lab.spec.signals.splice(i, 1); renderSigs(); }; });
}
function addSignalFromBox() {
  const v = $('lb-q').value.trim(), s = L.signals.find(x => x.fa === v || x.name === v);
  if (!s) { toast('معیار پیدا نشد'); return; }
  if (lab.spec.signals.some(([n]) => n === s.name)) { toast('قبلاً افزوده شده'); return; }
  if (lab.spec.combine === 'topk_icir') lab.spec.combine = 'equal', $('lb-comb').value = 'equal', lab.spec.signals = [];
  lab.spec.signals.push([s.name, 1]); $('lb-q').value = ''; renderSigs();
}
const PARAMS = { quantile: [['G', 'تعداد گروه', 5, 2, 20, 1], ['k', 'گروه (G=بالاترین)', 5, 1, 20, 1]], topfrac: [['entry', 'ورود (سهم برتر)', 0.2, 0.02, 0.6, 0.02], ['exit', 'خروج (بافر)', 0.3, 0.02, 0.8, 0.02]],
  topn: [['N', 'تعداد نماد', 50, 10, 300, 5], ['buffer', 'بافر (رتبه)', 25, 0, 150, 5]], score_tilt: [['lam', 'شدت λ', 1, 0, 3, 0.25]], rank_weight: [], msci_tilt: [], inv_vol: [['entry', 'ورود', 0.3, 0.05, 0.6, 0.05], ['exit', 'خروج', 0.4, 0.05, 0.8, 0.05]] };
function renderParams() {
  const a = lab.spec.algo, ps = PARAMS[a] || [], meta = L.algos.find(x => x.name === a);
  $('lb-params').innerHTML = ps.map(([k, t, d, lo, hi, st]) => { const v = (lab.spec.params && lab.spec.params[k]) ?? d; return `<label class="lb-row">${t} <input type="number" data-k="${k}" min="${lo}" max="${hi}" step="${st}" value="${v}"></label>`; }).join('');
  $$$('#lb-params input').forEach(i => { i.oninput = () => { lab.spec.params = lab.spec.params || {}; lab.spec.params[i.dataset.k] = +i.value; }; });
  $('lb-algodesc').textContent = meta ? meta.desc + ' — ' + meta.ref : '';
}
function readSpec() {
  const s = lab.spec, mk = []; if ($('lb-m0').checked) mk.push('bourse'); if ($('lb-m1').checked) mk.push('farabourse');
  s.universe = { markets: mk.length ? mk : ['bourse', 'farabourse'], min_adv: +$('lb-adv').value || 0 };
  s.rebalance_every = +$('lb-every').value; s.combine = $('lb-comb').value; s.topk = +$('lb-topk').value; s.neutral = $('lb-neu').checked; s.algo = $('lb-algo').value;
  s.cost_bp = +$('lb-cost').value; s.partial = Math.max(0.1, (+$('lb-part').value || 100) / 100); s.max_w = (+$('lb-maxw').value || 0) / 100 || null;
  const ps = {}; (PARAMS[s.algo] || []).forEach(([k, , d]) => { const i = $$(`#lb-params input[data-k="${k}"]`); ps[k] = i ? +i.value : d; }); s.params = ps;
  return s;
}
const FLOW_SEC = { universe: 0, sigs: 1, comb: 2, algo: 3, fric: 4 };
function renderFlow() {
  const el = $('lb-flow'); if (!el || !lab.spec) return;
  let s; try { s = readSpec(); } catch (e) { return; }
  const al = (L.algos.find(a => a.name === s.algo) || {}).fa || s.algo;
  const ps = s.params && Object.keys(s.params).length ? ' (' + Object.entries(s.params).map(([k, v]) => k + '=' + v).join('، ') + ')' : '';
  const mk = (s.universe.markets.length === 2 ? 'بورس + فرابورس' : s.universe.markets[0] === 'bourse' ? 'فقط بورس' : 'فقط فرابورس');
  const adv = s.universe.min_adv ? ` · ADV ≥ ${f1(s.universe.min_adv / 1e6, 0)} میلیون ریال` : '';
  const comb = (COMB.find(c => c[0] === s.combine) || [0, s.combine])[1];
  const nsig = s.combine === 'topk_icir' ? `${s.topk} معیار پویا` : `${s.signals.length} معیار`;
  const kap = Math.round(s.partial * 100);
  const bench = lab.bench === 'cap' ? 'ارزش‌وزن واجدان' : 'هم‌وزن واجدان';
  const ST = [
    ['سیگنال', `پایان آخرین روز معاملاتی ماه جلالی · هر ${s.rebalance_every} ماه`, 'universe', 'همهٔ محاسبه‌ها با داده‌ای انجام می‌شود که تا پایان همان روز شناخته بوده است (بدون نگاه به آینده؛ بنیادی‌ها از تاریخ انتشار + ۱ روز). ریبالانس هر ۱، ۳ یا ۶ ماه است.'],
    ['واجدان', mk + adv, 'universe', 'فقط شرکت‌های عملیاتی (بدون صندوق، گواهی، امتیاز تسهیلات) که داده و قیمت کافی و معامله دارند؛ فیلتر حداقل ارزش معاملات روزانه (میانگین ۶۳ روز) اختیاری است.'],
    ['Z و خنثی‌سازی', 'وینزورایز ۱٪–۹۹٪ → Z' + (s.neutral ? ' → خنثی‌سازی صنعتی' : ' · بدون خنثی‌سازی'), 'comb', 'هر معیار جداگانه وینزورایز و استاندارد می‌شود (کوانتیزه به ۱/۴۰ برای هم‌ارزی با پایتون)؛ در خنثی‌سازی میانگین صنعت (دست‌کم ۶ نماد) کم می‌شود و نمادهای بی‌داده صفر شمرده نمی‌شوند.'],
    ['ترکیب معیارها', `${nsig} · ${comb}`, 'sigs', 'Zهای معیارها با روش انتخابی (میانگین وزنی، رتبه‌ای، وزن IC/ICIR/FM/ریج یا انتخاب پویای k معیار) به یک امتیاز تبدیل می‌شوند؛ وزن منفی جهت معیار را برعکس می‌کند.'],
    ['انتخاب', al + ps, 'algo', 'الگوریتم انتخاب بر پایهٔ امتیاز و فهرست دارایی‌های ماه قبل (برای بافر ورود/خروج) نمادهای پرتفوی را برمی‌گزیند؛ بافر گردش را کم می‌کند.'],
    ['وزن‌دهی و سقف', s.max_w ? `سقف ${f1(s.max_w * 100, 0)}٪ برای هر نماد` : 'بدون سقف وزن', 'fric', 'وزن‌ها طبق همان الگوریتم (هم‌وزن، امتیازی، ریسکی…) ساخته می‌شوند و در صورت وجود سقف، مازاد به بقیه پخش می‌شود.'],
    ['ریبالانس جزئی', kap >= 100 ? 'کامل (κ = 1)' : `κ = ${f1(s.partial, 2)}: ${kap}٪ راه تا هدف`, 'fric', 'وزن نهایی = وزن رانش‌یافتهٔ قبلی + κ × (هدف − قبلی)؛ κ کمتر گردش و هزینه را کم می‌کند و ریبالانس را آهسته‌تر.'],
    ['هزینه', `${s.cost_bp} bp رفت‌وبرگشت × گردش یک‌طرفه`, 'fric', 'گردش یک‌طرفه = نصف مجموع |Δوزن|؛ هزینهٔ ماه = گردش × هزینهٔ رفت‌وبرگشت (پیش‌فرض ۱۰۰ bp [تأیید لازم]). اثر بازار جدا در تب «ظرفیت» است.'],
    ['اجرا', 'روز معاملاتی بعد · بازده از روز بعد از سیگنال', null, 'سفارش‌ها روز معاملاتی بعد اجرا می‌شود (شنبه تا چهارشنبه؛ تعطیلات رسمی مدل نشده [تأیید لازم]) و بازده ماه از روز بعد از سیگنال تا سیگنال بعدی حساب می‌شود.'],
    ['رانش و مرجع', `وزن‌ها با بازده رانش می‌کنند · مرجع: ${bench}`, null, 'تا ریبالانس بعد وزن‌ها با بازده کل رانش می‌کنند؛ مرجع هم‌وزن یا ارزش‌وزن واجدان همان ماه است و برتری، t و حکم نسبت به آن سنجیده می‌شود.']];
  const mini = $('lb-mini'); if (mini && !mini.dataset.done) { mini.dataset.done = 1; mini.innerHTML = ST.map(([t], i) => `<i><em>${i + 1}</em>${esc(t)}</i>`).join(''); }
  el.innerHTML = ST.map(([t, sub, sec, tip], i) => `<button class="lb-step${sec == null ? ' static' : ''}" data-sec="${sec == null ? '' : FLOW_SEC[sec]}" data-tip="${esc(tip)}"><span class="no">${i + 1}</span><b>${esc(t)}</b><small>${esc(sub)}</small></button>`).join('');
  $$$('#lb-flow .lb-step').forEach(b => b.onclick = () => {
    if (b.dataset.sec === '') return;
    const d = $$$('.lb-body details')[+b.dataset.sec]; if (!d) return;
    d.open = true; d.scrollIntoView({ block: 'nearest', behavior: 'smooth' }); d.classList.add('flash'); setTimeout(() => d.classList.remove('flash'), 900);
  });
}
function runLab(count) {
  const s = readSpec();
  if (!s.signals.length) { toast('دست‌کم یک معیار لازم است'); return; }
  toast('در حال اجرا…');
  setTimeout(() => {
    try {
      const t0 = performance.now(); lab.res = E.run(CTX, s); lab.cost = s.cost_bp; lab.st = E.stats(lab.res, s.cost_bp, jy, lab.bench); lab.dec = null; lab.name = null;
      if (count) lab.trials++; store.set('spec', s);
      $('lb-cnt').textContent = `آزمایش‌های این نشست: ${lab.trials} · ${Math.round(performance.now() - t0)} ms`;
      renderKPIs(); renderTab(); toast('اجرا شد');
    } catch (e) { console.error(e); toast('خطا: ' + e.message); }
  }, 20);
}
function specText(s) {
  const sg = s.combine === 'topk_icir' ? `انتخاب پویای ${s.topk} معیار برتر ICIR` : s.signals.map(([n, w]) => (w !== 1 ? w + '×' : '') + sigName(n)).join(' + ');
  const al = (L.algos.find(a => a.name === s.algo) || {}).fa || s.algo, p = s.params && Object.keys(s.params).length ? ' (' + Object.entries(s.params).map(([k, v]) => k + '=' + v).join(', ') + ')' : '';
  return `${sg} · ${(COMB.find(c => c[0] === s.combine) || [0, s.combine])[1]} · ${al}${p}`;
}
function renderKPIs() {
  renderFlow();
  const st = lab.st, v = E.verdict(st, lab.dec ? lab.dec.spearman : null);
  const K = [['بازده خالص سالانه', f1(st.ann_net) + '٪', ''], [lab.bench === 'cap' ? 'مرجع (ارزش‌وزن واجدان)' : 'مرجع (هم‌وزن واجدان)', f1(st.ann_all_net) + '٪', ''], ['برتری خالص', sg1(st.excess_net) + '٪', st.excess_net >= 0 ? 'up' : 'down'], ['t خالص (نیوی‌وست)', f1(st.t_net, 2), tcls(st.t_net)],
    ['IR', f1(st.ir, 2), ''], ['TE سالانه', f1(st.te) + '٪', ''], ['بیشترین افت فعال', f1(st.mdd_active) + '٪', 'down'], ['گردش سالانه', f1(st.turn_ann, 0) + '٪', ''], ['تعداد نماد', f1(st.names, 0), '']];
  $('lb-kpis').innerHTML = K.map(([k, x, c]) => `<div class="kpi"><div class="k">${k}</div><div class="v ${c}">${x}</div></div>`).join('');
  $('lb-title').textContent = lab.name || 'نتیجهٔ اجرا'; $('lb-title').dataset.tip = specText(lab.spec);
  $('lb-chip').textContent = v.v; $('lb-chip').className = 'chip ' + v.cls; $('lb-chip').dataset.tip = v.why;
  $('lb-lin').innerHTML = `<span><b>استراتژی</b> ${esc(specText(lab.spec))}</span><span><b>بازه</b> <span class="num">${lab.res.end[0]}</span> → <span class="num">${lab.res.end[lab.res.end.length - 1]}</span></span><span><b>هزینه</b> ${lab.cost} bp رفت‌وبرگشت</span><span><b>منبع</b> ${lab.lib ? 'کتابخانهٔ پایتون' : 'اجرا در مرورگر'}</span>`;
}
function levels(r) { let c = 100; return [100, ...r.map(x => (c *= 1 + x))]; }
const dd = lv => { let pk = 0; return lv.map(v => { pk = Math.max(pk, v); return (v / pk - 1) * 100; }); };
function renderTab() {
  const host = $('lb-view'), st = lab.st, t = lab.tab; if (!st) return;
  if (t === 'perf') return tabPerf(host);
  if (t === 'dec') return tabDec(host);
  if (t === 'ic') return tabIC(host);
  if (t === 'stab') return tabStab(host);
  if (t === 'hard') return tabHard(host);
  if (t === 'cap') return tabCap(host);
  if (t === 'live') return tabLive(host);
}
const cst = { i: null };
function tabPerf(host) {
  host.innerHTML = `<div class="legend" id="lb-leg"></div><svg class="chart" id="lb-chart" dir="ltr"></svg>`;
  const st = lab.st, res = lab.res, dates = [res.end[0].slice(0, 8) + '01', ...res.end];
  const lv = levels(st.rn), la = levels(st.an), lg = levels(res.ret), ex = levels(st.exn).map(x => (x / 100 - 1) * 100), d = dd(lv);
  const over = [...lab.overlay].map(i => lab.saved[i]).filter(Boolean);
  const extra = over.map((o, j) => ({ v: alignSeries(o, dates), color: ['var(--ch-4)', 'var(--warn)', 'var(--up)', 'var(--down)'][j % 4], w: 1.1, name: o.name, fmt: v => f1(v, 1) }));
  $('lb-leg').innerHTML = `<span><i style="color:var(--ch-1)"></i>استراتژی (خالص)</span><span><i style="color:var(--ch-2)"></i>${lab.bench === 'cap' ? 'ارزش‌وزن واجدان (خالص)' : 'هم‌وزن واجدان (خالص)'}</span><span><i style="color:var(--ch-3)"></i>استراتژی (ناخالص)</span>` + over.map((o, j) => `<span><i style="color:${['var(--ch-4)', 'var(--warn)', 'var(--up)', 'var(--down)'][j % 4]}"></i>${esc(o.name)}</span>`).join('') + '<span class="readout" id="lb-ro"></span>';
  const draw = () => { ChartKit.paneChart($('lb-chart'), dates, [
    { frac: 0.55, log: true, series: [{ v: lv, color: 'var(--ch-1)', w: 1.7, name: 'استراتژی (خالص)', fmt: v => f1(v, 1) }, { v: la, color: 'var(--ch-2)', w: 1.2, name: 'هم‌وزن واجدان', fmt: v => f1(v, 1) }, { v: lg, color: 'var(--ch-3)', w: 1, dash: true, name: 'ناخالص', fmt: v => f1(v, 1) }, ...extra], fmt: v => fmt(v, 0) },
    { frac: 0.25, zero: true, series: [{ v: ex, color: 'var(--ch-1)', w: 1.3, name: 'بازده فعال تجمعی', fmt: v => sg1(v, 1) + '٪' }], fmt: v => fmt(v, 0) + '٪' },
    { frac: 0.2, zero: true, series: [{ v: d, color: 'var(--down)', w: 1.1, name: 'افت از اوج', fmt: v => f1(v, 1) + '٪' }], fmt: v => fmt(v, 0) + '٪' }], cst); };
  ChartKit.attach($('lb-chart'), cst, draw); draw();
}
function alignSeries(o, dates) { const m = new Map(); let c = 100; m.set(dates[0], 100); o.res.end.forEach((d, i) => { c *= 1 + o.net[i]; m.set(d, c); }); let last = 100; return dates.map(d => { if (m.has(d)) last = m.get(d); return last; }); }
function tabDec(host) {
  host.innerHTML = `<div class="lb-note" id="lb-dnote">در حال محاسبهٔ دهک‌ها…</div><div class="lb-bars" id="lb-dbars"></div><div id="lb-dtab"></div>`;
  setTimeout(() => {
    if (!lab.dec) { if (lab.lib) { lab.dec = null; $('lb-dnote').textContent = 'دهک‌های این اجرای کتابخانه‌ای را فقط برای تک‌معیارها داریم (تب کتابخانه ← تک‌معیار).'; return; } lab.dec = E.deciles(CTX, lab.spec, lab.cost); renderKPIs(); }
    const d = lab.dec, base = lab.st.ann_all_net;
    $('lb-dnote').innerHTML = `بازدهٔ سالانهٔ خالص هر دهک از امتیاز ترکیبی این استراتژی (هم‌وزن درون دهک، بدون بافر). اسپیرمن رتبهٔ دهک با بازده: <b class="${d.spearman > 0.6 ? 'up' : ''}">${f1(d.spearman, 2)}</b> · جفت‌های صعودی: <b>${d.up} از ۹</b> · دهک ۱۰ − دهک ۱: <b class="${d.spread_ann >= 0 ? 'up' : 'down'}">${sg1(d.spread_ann)}٪</b> (t = ${f1(d.spread_t, 2)}). خط مرجع: هم‌وزن واجدان ${f1(base)}٪.`;
    sbars($('lb-dbars'), d.ann.map((_, i) => 'D' + (i + 1)), d.ann, v => f1(v, 0), i => d.ann[i] > base, base);
    $('lb-dtab').innerHTML = `<table class="dt">${th([['دهک'], ['بازده خالص سالانه %', 'n'], ['نسبت به مرجع', 'n']])}<tbody>${d.ann.map((v, i) => `<tr><td>${i + 1}${i === 0 ? ' (ضعیف‌ترین امتیاز)' : i === 9 ? ' (قوی‌ترین امتیاز)' : ''}</td><td class="n">${f1(v)}</td><td class="n ${v >= base ? 'up' : 'down'}">${sg1(v - base)}</td></tr>`).join('')}</tbody></table>`;
  }, 20);
}
function tabIC(host) {
  const res = lab.res, ic = res.ic.map((v, i) => [v, res.end[i]]).filter(x => x[0] === x[0]);
  if (!ic.length) { host.innerHTML = '<div class="lb-note">سری IC برای این اجرا ذخیره نشده (اجرای کتابخانه‌ای). برای IC تک‌معیارها به نمای «معیارها» بروید.</div>'; return; }
  const v = ic.map(x => x[0]), m = v.reduce((a, b) => a + b, 0) / v.length;
  let c = 0; const cum = v.map(x => (c += x));
  host.innerHTML = `<div class="lb-note">IC ماهانه = همبستگی رتبه‌ای اسپیرمن امتیاز ترکیبی و بازدهٔ ماه بعد روی واجدان (جهان انتخاب‌شده). میانگین <b>${f1(m, 3)}</b> · t نیوی‌وست <b class="${tcls(lab.st.ic_t)}">${f1(lab.st.ic_t, 2)}</b> · ICIR <b>${f1(lab.st.icir, 2)}</b> · درصد ماه‌های مثبت <b>${f1(v.filter(x => x > 0).length / v.length * 100, 0)}٪</b>.</div><svg class="chart" id="lb-icchart" dir="ltr"></svg>`;
  const dates = ic.map(x => x[1]), st = { i: null };
  const draw = () => ChartKit.paneChart($('lb-icchart'), dates, [{ frac: 0.5, zero: true, series: [{ v, color: 'var(--ch-2)', w: 1, name: 'IC ماهانه', fmt: x => f1(x, 3) }], fmt: x => fmt(x, 2) }, { frac: 0.5, zero: true, series: [{ v: cum, color: 'var(--ch-1)', w: 1.4, name: 'IC تجمعی', fmt: x => f1(x, 2) }], fmt: x => fmt(x, 1) }], st);
  ChartKit.attach($('lb-icchart'), st, draw); draw();
}
function tabStab(host) {
  const st = lab.st, yrs = Object.entries(st.years).sort();
  host.innerHTML = `<div class="lb-grid2"><div><table class="dt">${th([['سال شمسی'], ['بازده فعال خالص %', 'n']])}<tbody>${yrs.map(([y, v]) => `<tr><td class="num">${y}</td><td class="n ${v >= 0 ? 'up' : 'down'}">${sg1(v)}</td></tr>`).join('')}</tbody></table></div>
    <div><table class="dt">${th([['شاخص پایداری'], ['مقدار', 'n']])}<tbody>
    <tr><td>برتری سالانه — نیمهٔ اول</td><td class="n ${st.ex_h1 >= 0 ? 'up' : 'down'}">${sg1(st.ex_h1)}٪ (t ${f1(st.t_h1, 2)})</td></tr>
    <tr><td>برتری سالانه — نیمهٔ دوم</td><td class="n ${st.ex_h2 >= 0 ? 'up' : 'down'}">${sg1(st.ex_h2)}٪ (t ${f1(st.t_h2, 2)})</td></tr>
    <tr><td>درصد ماه‌هایی که از مرجع بهتر بود</td><td class="n">${f1(st.hit, 0)}٪</td></tr>
    <tr><td>درصد پنجره‌های ۱۲ماههٔ مثبت</td><td class="n">${f1(st.roll12_win, 0)}٪</td></tr>
    <tr><td>بدترین پنجرهٔ ۱۲ماهه</td><td class="n down">${f1(st.roll12_worst)}٪</td></tr>
    <tr><td>بوت‌استرپ ایستا — فاصلهٔ ۹۵٪ برتری سالانه</td><td class="n">[${f1(st.boot_lo)} ، ${f1(st.boot_hi)}]٪</td></tr>
    <tr><td>احتمال برتری مثبت (بوت‌استرپ)</td><td class="n">${f1(st.boot_p * 100, 0)}٪</td></tr>
    <tr><td>بیشترین افت استراتژی (خالص)</td><td class="n down">${f1(st.mdd)}٪</td></tr></tbody></table></div></div>
    <div class="lb-note">نیمهٔ اول و دوم نمونه را جدا بخوانید: برتری‌ای که فقط در یک نیمه است معمولاً شاهد رژیم است نه ساختار. بوت‌استرپ ایستای بلوکی (بلوک میانگین ۳ ماه، ۱۰۰۰ تکرار) عدم‌قطعیت میانگین برتری را بدون فرض نرمال‌بودن می‌دهد.</div>`;
}
function tabHard(host) {
  const st = lab.st, N = L.multi.N + lab.trials, bt = Math.abs(E.PhiInv(1 - 0.05 / (2 * N))), d = E.dsr(st.exn, lab.srLib, N), v = E.verdict(st, lab.dec ? lab.dec.spearman : null), M = L.multi;
  const pbo = M.pbo || {}, rc = M.rc_spa || {};
  host.innerHTML = `<div class="lb-grid2"><div><table class="dt">${th([['آزمون'], ['نتیجه', 'n']])}<tbody>
    <tr><td>تعداد آزمایش‌ها N (کتابخانه + این نشست)</td><td class="n">${N}</td></tr>
    <tr><td>آستانهٔ |t| بونفرونی (۵٪ خانوادگی)</td><td class="n">${f1(bt, 2)}</td></tr>
    <tr><td>t خالص این استراتژی</td><td class="n ${Math.abs(st.t_net) >= bt ? 'up' : ''}">${f1(st.t_net, 2)} ${Math.abs(st.t_net) >= bt ? '✓ عبور' : '✗ زیر آستانه'}</td></tr>
    <tr><td>Sharpe فعال سالانه</td><td class="n">${f1(d.sr_annual, 2)}</td></tr>
    <tr><td>Sharpe آستانه SR₀ (حداکثر مورد انتظار از N شانس) — ماهانه</td><td class="n">${f1(d.sr0_monthly, 3)}</td></tr>
    <tr><td>Deflated Sharpe Ratio (احتمال Sharpe واقعی > ۰)</td><td class="n ${d.dsr >= 0.95 ? 'up' : d.dsr < 0.5 ? 'down' : ''}">${f1(d.dsr * 100, 0)}٪</td></tr>
    </tbody></table></div><div><table class="dt">${th([['آزمون سراسری کتابخانه'], ['نتیجه', 'n']])}<tbody>
    <tr><td>PBO (احتمال بیش‌برازش بک‌تست — CSCV)</td><td class="n ${pbo.pbo > 0.5 ? 'down' : ''}">${pbo.pbo == null ? '—' : f1(pbo.pbo * 100, 0) + '٪'}</td></tr>
    <tr><td>Sharpe بیرون‌نمونه بهترین درون‌نمونه (سالانه)</td><td class="n">${f1(pbo.oos_best_mean, 2)}</td></tr>
    <tr><td>White Reality Check — p</td><td class="n">${f1(rc.rc_p, 3)}</td></tr>
    <tr><td>Hansen SPA — p</td><td class="n">${f1(rc.spa_p, 3)}</td></tr>
    <tr><td>بهترین استراتژی کتابخانه</td><td class="n">${esc(rc.best_id || '—')}</td></tr></tbody></table></div></div>
    <div class="lb-note"><b>حکم: ${esc(v.v)}</b> — ${esc(v.why)}. هر بار «اجرا» می‌زنید N بزرگ‌تر و آستانه سخت‌تر می‌شود: این همان هزینهٔ جست‌وجوی پارامتر است. PBO بالای ۵۰٪ یعنی بهترین بک‌تست درون‌نمونه به‌طور متوسط بیرون‌نمونه زیر میانه است. Reality Check و SPA می‌پرسند آیا بهترین استراتژی کتابخانه را می‌توان از مرجع بهتر دانست؛ p بزرگ یعنی خیر.</div>`;
}
function buildDays(w, aum) {
  const k = L.k, rl = L.rows - 1; let tw = 0, wd = 0, n = 0, g1 = 0, mx = 0;
  for (let i = 0; i < k; i++) if (w[i] > 0) { const av = CTX.adv[rl * k + i], adv = av < 0 ? 0 : Math.exp(av) - 1, d = adv > 0 ? Math.ceil(w[i] * aum / adv / 0.1) : 99; tw += w[i]; wd += w[i] * d; n++; if (d > 1) g1++; mx = Math.max(mx, d); }
  return { wdays: wd / (tw || 1), pct_gt1: n ? g1 / n * 100 : NaN, max_days: mx };
}
function tabCap(host) {
  const res = lab.res, st = lab.st, aums = L.aums || [];
  if (!res.impact || !res.impact.length || !res.impact[0].length) { host.innerHTML = '<div class="lb-note">سری اثر بازار برای این اجرا نیست.</div>'; return; }
  const { w } = liveWeights(), rows = aums.map((aum, j) => {
    const x = st.rn.map((v, i) => v - (isNaN(res.impact[j][i]) ? 0 : res.impact[j][i]));
    const b = (lab.lib && lab.lib.live && lab.lib.live.build) ? lab.lib.live.build[String(aum)] : buildDays(w, aum);
    return { aum, ex: E.annOf(x) - E.annOf(st.an), cost: (E.annOf(st.rn) - E.annOf(x)), b };
  });
  const half = rows.find(r => r.ex < st.excess_net / 2), zero = rows.find(r => r.ex < 0);
  host.innerHTML = `<div class="lb-note">اثر بازار هر نماد = <b>Y·σ·√(Δw·سرمایه ÷ ADV)</b> (Y = ${L.y_impact} [تأیید لازم]؛ σ روزانهٔ ۱۲۶ روزه؛ ADV ارزش معاملات روزانهٔ ۶۳ روزه) روی هر معاملهٔ ریبالانس، افزون بر هزینهٔ رفت‌وبرگشت ${lab.cost} bp. ستون آخر: ساخت پرتفوی زندهٔ این استراتژی از نقد با سقف مشارکت ۱۰٪ ADV. این مدل ساده است؛ اثر صف و حد نوسان در فصل ۶ آمده و اینجا نیست.<br>
    <b>خوانش:</b> برتری خالص پایه ${sg1(st.excess_net)}٪ ${half ? `به نصف در ${fmt(half.aum / 1e9, 0)} میلیارد ریال می‌رسد` : 'در سطوح بررسی‌شده از نصف نمی‌افتد'}${zero ? ` و در ${fmt(zero.aum / 1e9, 0)} میلیارد ریال منفی می‌شود` : ''}.</div>
    <table class="dt">${th([['سرمایه (میلیارد ریال)', 'n'], ['برتری خالص پس از اثر بازار %', 'n'], ['هزینهٔ اثر بازار (واحد درصد در سال)', 'n'], ['روز لازم برای ساخت (وزنی)', 'n'], ['نمادهای نیازمند بیش از یک روز %', 'n'], ['بیشترین روز', 'n']])}<tbody>${rows.map(r => `<tr><td class="n">${fmt(r.aum / 1e9, 0)}</td><td class="n ${r.ex >= 0 ? 'up' : 'down'}">${sg1(r.ex)}</td><td class="n">${f1(r.cost)}</td><td class="n">${f1(r.b.wdays, 1)}</td><td class="n">${f1(r.b.pct_gt1, 0)}</td><td class="n ${r.b.max_days > 5 ? 'down' : ''}">${f1(r.b.max_days, 0)}</td></tr>`).join('')}</tbody></table>`;
}
function liveWeights() {
  if (lab.lib && lab.lib.live) { const w = new Float64Array(L.k); lab.lib.live.top.forEach(([s, wt]) => { const i = CTX.sym.indexOf(s); if (i >= 0) w[i] = wt / 100; }); return { w, score: null }; }
  return { w: lab.res.live.target, score: lab.res.live.score };
}
function tabLive(host) {
  const { w, score } = liveWeights(), k = L.k, rl = L.rows - 1, idx = [];
  for (let i = 0; i < k; i++) if (w[i] > 0) idx.push(i);
  idx.sort((a, b) => w[b] - w[a]);
  const tot = idx.reduce((s, i) => s + w[i], 0) || 1, effN = 1 / idx.reduce((s, i) => s + (w[i] / tot) ** 2, 0), top10 = idx.slice(0, 10).reduce((s, i) => s + w[i] / tot, 0) * 100;
  const sec = {}; idx.forEach(i => { const s = L.sectors[L.codes[i].sec]; sec[s] = (sec[s] || 0) + w[i] / tot * 100; });
  const aum = (+lab.aum || 100) * 1e9;
  let mon = '';
  if (!lab.lib && lab.res.live && lab.res.live.drift) {                     // رصد: اگر امروز ریبالانس بود چه کسی وارد/خارج می‌شد
    const dr = lab.res.live.drift, tg = lab.res.live.target, ent = [], ext = [];
    for (let i = 0; i < k; i++) { if (tg[i] > 0 && !(dr[i] > 0)) ent.push(i); if (dr[i] > 0 && !(tg[i] > 0)) ext.push(i); }
    const nm = a => a.slice(0, 14).map(i => L.codes[i].p || L.codes[i].s).join('، ') + (a.length > 14 ? ' …' : '') || '—';
    mon = `<div class="lb-note"><b>رصد زنده:</b> اگر امروز ریبالانس بود، <b class="up">${ent.length} نماد وارد</b> و <b class="down">${ext.length} نماد خارج</b> می‌شد (بقیه می‌مانند). ورود: ${nm(ent) || '—'}. خروج: ${nm(ext) || '—'}. اقدام واقعی فقط در روز ریبالانس است (فصل ۵ §۵٫۸٫۳)؛ این فهرست برای برنامه‌ریزی نقدینگی و رصد پیش از روز ریبالانس است.</div>`;
  }
  host.innerHTML = mon + `<div class="ctl"><label>سرمایه (میلیارد ریال) <input type="number" id="lv-aum" value="${lab.aum || 100}" min="1" step="10"></label><span class="mute">برای محاسبهٔ روز لازم برای ساخت با ۱۰٪ مشارکت در ارزش معاملات روزانه</span>
    <span class="spacer"></span><button class="tool" id="lv-plan">ارسال به برنامهٔ اقدام ←</button><button class="tool" id="lv-csv">CSV</button></div>
    <div class="lb-note">وزن هدف بر پایهٔ آخرین روز داده (<span class="num">${L.asof}</span>) · ${idx.length} نماد · تعداد مؤثر ${f1(effN, 0)} · ۱۰ نماد برتر ${f1(top10, 0)}٪.</div>
    <div class="lb-grid2"><div><table class="dt" id="lv-tab">${th([['#'], ['نماد'], ['بازار'], ['صنعت'], ['وزن %', 'n'], ['امتیاز Z', 'n'], ['ارزش معاملات روزانه (میلیون ریال)', 'n'], ['روز لازم (۱۰٪)', 'n']])}<tbody>${idx.slice(0, 80).map((i, j) => {
      const adv = Math.exp(CTX.adv[rl * k + i]) / 1e6, days = adv > 0 ? w[i] / tot * aum / 1e6 / (0.1 * adv) : NaN;
      return `<tr><td class="rank">${j + 1}</td><td><a class="symlink" onclick="openSym('${esc(L.codes[i].s)}')">${esc(L.codes[i].p || L.codes[i].s)}</a></td><td>${L.codes[i].m ? 'فرابورس' : 'بورس'}</td><td>${esc(L.sectors[L.codes[i].sec])}</td><td class="n">${f1(w[i] / tot * 100, 2)}</td><td class="n">${score ? f1(score[i], 2) : '—'}</td><td class="n">${f1(adv, 0)}</td><td class="n ${days > 5 ? 'down' : ''}">${f1(days, 1)}</td></tr>`;
    }).join('')}</tbody></table></div><div><table class="dt">${th([['صنعت'], ['وزن %', 'n']])}<tbody>${Object.entries(sec).sort((a, b) => b[1] - a[1]).slice(0, 14).map(([s, v]) => `<tr><td>${esc(s)}</td><td class="n">${f1(v, 1)}</td></tr>`).join('')}</tbody></table></div></div>`;
  $('lv-aum').onchange = e => { lab.aum = +e.target.value; tabLive(host); };
  $('lv-csv').onclick = () => download('live_target.csv', [['symbol', 'market', 'sector', 'weight_pct', 'score_z'], ...idx.map(i => [L.codes[i].p || L.codes[i].s, L.codes[i].m ? 'farabourse' : 'bourse', L.sectors[L.codes[i].sec], (w[i] / tot * 100).toFixed(4), score ? score[i].toFixed(3) : ''])]);
  $('lv-plan').onclick = () => sendToPlan(lab.name || specText(lab.spec), Float64Array.from(w).map(x => x / tot));
}
function exportRunCSV() {
  const r = lab.res, st = lab.st; if (!r) return;
  download('lab_run_monthly.csv', [['period_end', 'ret_gross', 'ret_net', 'all_net', 'excess_net', 'turnover'], ...r.end.map((d, i) => [d, r.ret[i].toFixed(5), st.rn[i].toFixed(5), st.an[i].toFixed(5), st.exn[i].toFixed(5), isNaN(r.to[i]) ? '' : r.to[i].toFixed(4)])]);
}
function saveRun() {
  if (!lab.res) return;
  const nm = prompt('نام این اجرا:', specText(lab.spec).slice(0, 60)); if (!nm) return;
  lab.saved.push({ name: nm, spec: JSON.parse(JSON.stringify(lab.spec)), st: { ann_net: lab.st.ann_net, excess_net: lab.st.excess_net, t_net: lab.st.t_net, ir: lab.st.ir, turn_ann: lab.st.turn_ann, mdd_active: lab.st.mdd_active }, cost: lab.cost });
  store.set('saved', lab.saved); renderSide(); toast('ذخیره شد');
}
function renderSide() {
  const host = $('lb-list'), side = lab.side; $('lb-libctl').hidden = side !== 'lib';
  if (side === 'saved') {
    host.innerHTML = th([[''], ['نام'], ['برتری %', 'n'], ['t', 'n'], ['IR', 'n'], ['گردش', 'n'], ['']]) + '<tbody>' + (lab.saved.map((o, i) => `<tr data-i="${i}"><td><input type="checkbox" data-o="${i}" ${lab.overlay.has(i) ? 'checked' : ''} title="نمایش روی نمودار"></td><td class="nm" title="${esc(specText(o.spec))}">${esc(o.name)}</td><td class="n ${o.st.excess_net >= 0 ? 'up' : 'down'}">${sg1(o.st.excess_net)}</td><td class="n ${tcls(o.st.t_net)}">${f1(o.st.t_net, 2)}</td><td class="n">${f1(o.st.ir, 2)}</td><td class="n">${f1(o.st.turn_ann, 0)}</td><td><button class="tool" data-d="${i}" title="حذف">×</button></td></tr>`).join('') || '<tr><td colspan="7" class="mute" style="white-space:normal">اجراهای ذخیره‌شدهٔ شما اینجا می‌آیند. با «ذخیرهٔ این اجرا» اضافه کنید و با تیک، روی نمودار عملکرد مقایسه کنید.</td></tr>') + '</tbody>';
    $$$('#lb-list tr[data-i]').forEach(tr => tr.onclick = e => { if (e.target.closest('input,button')) return; const o = lab.saved[+tr.dataset.i]; setSpec(JSON.parse(JSON.stringify(o.spec))); runLab(false); lab.name = o.name; });
    $$$('#lb-list input[data-o]').forEach(c => c.onchange = () => { const i = +c.dataset.o; if (c.checked) { lab.overlay.add(i); const o = lab.saved[i]; if (!o.net) { const r = E.run(CTX, o.spec); const st = E.stats(r, o.cost, jy, lab.bench); o.net = st.rn; o.res = r; } } else lab.overlay.delete(i); if (lab.tab === 'perf') tabPerf($('lb-view')); });
    $$$('#lb-list button[data-d]').forEach(b => b.onclick = () => { lab.saved.splice(+b.dataset.d, 1); lab.overlay.clear(); store.set('saved', lab.saved.map(o => ({ name: o.name, spec: o.spec, st: o.st, cost: o.cost }))); renderSide(); });
    lab.saved.forEach(o => { if (!o.net && lab.overlay.size) { /* بارگذاری تنبل */ } });
    $('lb-side-lin').innerHTML = '<span><b>ذخیره</b> در مرورگر (localStorage)</span>';
  } else {
    const g = $('lb-libgrp').value, key = $('lb-libsort').value, rows = L.library.filter(r => !g || r.group === g).slice().sort((a, b) => (b.stats[key] ?? -1e9) * (key === 'turn_ann' ? -1 : 1) - (a.stats[key] ?? -1e9) * (key === 'turn_ann' ? -1 : 1));
    host.innerHTML = th([['استراتژی'], ['برتری %', 'n'], ['t', 'n'], ['IR', 'n'], ['گردش', 'n'], ['حکم']]) + '<tbody>' + rows.map(r => `<tr data-id="${esc(r.id)}"><td class="nm" title="${esc(r.id)}">${esc(r.name)}</td><td class="n ${(lab.bench === 'cap' ? r.stats.excess_net_cap : r.stats.excess_net) >= 0 ? 'up' : 'down'}">${sg1(lab.bench === 'cap' ? r.stats.excess_net_cap : r.stats.excess_net)}</td><td class="n ${tcls(lab.bench === 'cap' ? r.stats.t_net_cap : r.stats.t_net)}">${f1(lab.bench === 'cap' ? r.stats.t_net_cap : r.stats.t_net, 2)}</td><td class="n">${f1(lab.bench === 'cap' ? r.stats.ir_cap : r.stats.ir, 2)}</td><td class="n">${f1(r.stats.turn_ann, 0)}</td><td><span class="chip ${r.verdict.verdict === 'استقرار' ? 'ok' : r.verdict.verdict === 'شاهد ضعیف' ? 'warn' : 'bad'}">${esc(r.verdict.verdict)}</span></td></tr>`).join('') + '</tbody>';
    $$$('#lb-list tr[data-id]').forEach(tr => tr.onclick = () => openLibrary(tr.dataset.id));
    $('lb-side-lin').innerHTML = `<span><b>N</b> ${L.multi.N} استراتژی</span><span><b>هزینه</b> ${L.cost_bp} bp</span><span>کلیک روی ردیف: نمایش نتیجه؛ برای الگوریتم‌های قابل اجرا در مرورگر spec هم بارگذاری می‌شود</span>`;
  }
}
function openLibrary(id) {
  const r = L.library.find(x => x.id === id); if (!r) return;
  lab.lib = r; lab.res = toRes(r); lab.cost = L.cost_bp; lab.st = E.stats(lab.res, lab.cost, jy, lab.bench); lab.dec = null; lab.name = r.name;
  if (r.id.startsWith('sig:') && L.dec[r.id.split(':')[1]]) { const d = L.dec[r.id.split(':')[1]]; lab.dec = { ann: d.ann_net, spread_t: d.spread_t, spread_ann: NaN, spearman: spearmanArr(d.ann_net), up: d.ann_net.slice(1).filter((v, i) => v > d.ann_net[i]).length }; }
  if (isJS(r.spec)) { try { setSpec(JSON.parse(JSON.stringify(r.spec))); } catch (e) { /* ممکن است معیار نباشد */ } }
  lab.spec = JSON.parse(JSON.stringify(r.spec));
  renderKPIs(); renderTab();
}
function spearmanArr(a) { const rk = x => { const o = x.map((v, i) => [v, i]).sort((p, q) => p[0] - q[0]), r = []; o.forEach(([, i], j) => { r[i] = j; }); return r; }, ra = rk(a), rb = a.map((_, i) => i), m = (a.length - 1) / 2; let c = 0, v = 0, w = 0; ra.forEach((x, i) => { c += (x - m) * (rb[i] - m); v += (x - m) ** 2; w += (rb[i] - m) ** 2; }); return c / Math.sqrt(v * w); }

/* ════════════════════════════════ SIGNALS ════════════════════════════════ */
const sg = { fam: '', q: '', sort: 'ic_t', dir: -1, sel: null, view: 'table' };
function initSig() {
  const m = $('v-sig'); m.dataset.ready = 1;
  m.innerHTML = `
  <section class="panel" style="--lg:var(--lg-a)">
    <div class="panel-head"><span class="lg-badge">A</span><span class="panel-title">باغ‌وحش معیارها · IC و پریمیوم</span><span class="chip" id="sg-chip"></span>
      <div class="seg" id="sg-view"><button data-v="table" aria-pressed="true">جدول</button><button data-v="corr" aria-pressed="false">همبستگی</button></div>
      <div class="panel-tools"><button class="tool" id="sg-csv">CSV</button></div></div>
    <div class="ctl"><label>خانواده <select id="sg-fam"><option value="">همه</option>${Object.entries(FAM).map(([k, v]) => `<option value="${k}">${v}</option>`).join('')}</select></label><label>جست‌وجو <input id="sg-q" placeholder="نام یا مرجع" style="width:140px"></label><span class="mute" id="sg-note"></span></div>
    <div class="panel-body scroll"><table class="dt" id="sg-tab"></table><div id="sg-corr" hidden></div></div>
    <div class="lineage" id="sg-lin"></div></section>
  <section class="panel" style="--lg:var(--lg-b)">
    <div class="panel-head"><span class="lg-badge">B</span><span class="panel-title" id="sg-title">جزئیات معیار</span>
      <div class="panel-tools"><button class="tool" id="sg-lab">آزمون در Lab ←</button></div></div>
    <div class="panel-body scroll"><div class="prose" id="sg-detail"></div><div class="lb-bars" id="sg-bars"></div><table class="dt" id="sg-hz"></table></div>
    <div class="lineage" id="sg-dlin"></div></section>`;
  $('sg-fam').onchange = e => { sg.fam = e.target.value; renderSigTable(); };
  $('sg-q').oninput = e => { sg.q = e.target.value.trim().toLowerCase(); renderSigTable(); };
  $$$('#sg-view button').forEach(b => b.onclick = () => { sg.view = b.dataset.v; $$$('#sg-view button').forEach(x => x.setAttribute('aria-pressed', x === b)); $('sg-tab').hidden = sg.view !== 'table'; $('sg-corr').hidden = sg.view !== 'corr'; if (sg.view === 'corr') renderCorr(); });
  $('sg-csv').onclick = () => download('signal_zoo.csv', [['signal', 'family', 'names', 'ic', 'ic_t', 'icir', 'ic_neutral_t', 'fm_premium_ann', 'fm_t', 'q5_excess_ann', 'q5_excess_t', 'q5_turn', 'ic_h1', 'ic_h2'], ...L.signals.filter(s => L.zoo[s.name]).map(s => { const z = L.zoo[s.name], f = (L.fm[s.name] || {}).fm || {}; return [s.name, s.family, z.names, z.ic, z.ic_t, z.icir, z.ic_neutral_t, f.premium_ann, f.t, z.q5_excess_ann, z.q5_excess_t, z.q5_turn, z.ic_h1, z.ic_h2]; })]);
  $('sg-lab').onclick = () => { if (!sg.sel) return; const s = JSON.parse(JSON.stringify(lab.spec || DEFAULT)); s.signals = [[sg.sel, 1]]; s.combine = 'equal'; if (!lab.spec) lab.spec = s; window.SIM_SHOW('lab'); setSpec(s); runLab(true); };
  renderSigTable(); selectSig(L.signals.slice().sort((a, b) => Math.abs((L.zoo[b.name] || {}).ic_t || 0) - Math.abs((L.zoo[a.name] || {}).ic_t || 0))[0].name);
}
function renderSigTable() {
  const N = L.multi.N, bt = Math.abs(E.PhiInv(1 - 0.05 / (2 * N)));
  let rows = L.signals.filter(s => L.zoo[s.name] && (!sg.fam || s.family === sg.fam) && (!sg.q || (s.fa + s.name + s.en + s.ref).toLowerCase().includes(sg.q)));
  const val = (s, k) => { const z = L.zoo[s.name], f = (L.fm[s.name] || {}).fm || {}; return k === 'fa' ? s.fa : k === 'fm' ? f.t : k === 'fmp' ? f.premium_ann : z[k]; };
  rows.sort((a, b) => { const x = val(a, sg.sort), y = val(b, sg.sort); return ((typeof x === 'string' ? x.localeCompare(y) : (x ?? -1e9) - (y ?? -1e9))) * sg.dir; });
  const cols = [['fa', 'معیار', ''], ['names', 'نماد', 'n'], ['ic', 'IC', 'n'], ['ic_t', 't', 'n'], ['icir', 'ICIR', 'n'], ['ic_neutral_t', 't خنثی', 'n'], ['fmp', 'پریمیوم FM %', 'n'], ['fm', 't FM', 'n'], ['q5_excess_ann', 'پنجک ۵ − همه %', 'n'], ['q5_excess_t', 't پنجک', 'n'], ['q5_turn', 'گردش ماهانه %', 'n'], ['ic_h1', 'IC نیمهٔ ۱', 'n'], ['ic_h2', 'IC نیمهٔ ۲', 'n']];
  $('sg-tab').innerHTML = `<thead><tr>${cols.map(([k, t, c]) => `<th class="${c} sortable ${sg.sort === k ? (sg.dir > 0 ? 'sorted asc' : 'sorted desc') : ''}" data-k="${k}">${t}</th>`).join('')}</tr></thead><tbody>` + rows.map(s => {
    const z = L.zoo[s.name], f = (L.fm[s.name] || {}).fm || {}, sig = Math.abs(z.ic_t) >= bt;
    const sameSign = (z.ic_h1 > 0) === (z.ic_h2 > 0);
    return `<tr data-s="${s.name}" ${sg.sel === s.name ? 'aria-selected="true"' : ''}><td><span class="fam" style="background:${FAMCOL[s.family]}"></span>${esc(s.fa)}</td><td class="n">${f1(z.names, 0)}</td><td class="n ${z.ic >= 0 ? 'up' : 'down'}">${f1(z.ic, 3)}</td><td class="n ${tcls(z.ic_t)}">${f1(z.ic_t, 2)}${sig ? ' ✓' : ''}</td><td class="n">${f1(z.icir, 2)}</td><td class="n ${tcls(z.ic_neutral_t)}">${f1(z.ic_neutral_t, 2)}</td><td class="n">${sg1(f.premium_ann)}</td><td class="n ${tcls(f.t)}">${f1(f.t, 2)}</td><td class="n ${z.q5_excess_ann >= 0 ? 'up' : 'down'}">${sg1(z.q5_excess_ann)}</td><td class="n ${tcls(z.q5_excess_t)}">${f1(z.q5_excess_t, 2)}</td><td class="n">${f1(z.q5_turn, 0)}</td><td class="n ${z.ic_h1 >= 0 ? 'up' : 'down'}">${f1(z.ic_h1, 3)}</td><td class="n ${sameSign ? (z.ic_h2 >= 0 ? 'up' : 'down') : 'warn'}">${f1(z.ic_h2, 3)}</td></tr>`;
  }).join('') + '</tbody>';
  $$$('#sg-tab th.sortable').forEach(h => h.onclick = () => { const k = h.dataset.k; if (sg.sort === k) sg.dir *= -1; else { sg.sort = k; sg.dir = k === 'fa' ? 1 : -1; } renderSigTable(); });
  $$$('#sg-tab tr[data-s]').forEach(tr => tr.onclick = () => selectSig(tr.dataset.s));
  $('sg-chip').textContent = `${rows.length} از ${L.signals.length} معیار`;
  $('sg-note').textContent = `✓ = |t| بالاتر از آستانهٔ بونفرونی ${f1(bt, 2)} برای N=${N}`;
  $('sg-lin').innerHTML = `<span><b>جهان</b> بورس+فرابورس، واجدان قیمتی</span><span><b>IC</b> اسپیرمن با بازده ماه بعد</span><span><b>t</b> نیوی‌وست ۳ وقفه</span><span><b>FM</b> Fama–MacBeth با کنترل اندازه و بتا</span><span><b>داده تا</b> <span class="num">${L.asof}</span></span>`;
}
function selectSig(n) {
  sg.sel = n; $$$('#sg-tab tr[data-s]').forEach(tr => tr.setAttribute('aria-selected', tr.dataset.s === n ? 'true' : 'false'));
  const m = sigMeta(n), z = L.zoo[n], fm = L.fm[n] || {}, d = L.dec[n];
  $('sg-title').textContent = `${m.fa} · ${m.en}`; $('sg-title').dataset.tip = `${m.fa} (${m.en}) — ${m.formula} · مرجع: ${m.ref}`;
  const corr = L.corr.names.indexOf(n), cr = corr >= 0 ? L.corr.m[corr].map((v, j) => [v, L.corr.names[j]]).filter(x => x[1] !== n && x[0] === x[0]).sort((a, b) => Math.abs(b[0]) - Math.abs(a[0])).slice(0, 5) : [];
  $('sg-detail').innerHTML = `<p><b>خانواده:</b> ${esc(FAM[m.family])} &nbsp; <b>داده لازم:</b> ${esc(m.needs)} &nbsp; <b>پنجره:</b> ${m.window} روز</p><p><b>تعریف:</b> ${esc(m.formula)}</p><p><b>مرجع:</b> ${esc(m.ref)}</p>
    <p><b>همبسته‌ترین‌ها:</b> ${cr.map(([v, nm]) => `<a class="symlink" data-s="${nm}">${esc(sigName(nm))}</a> (${f1(v, 2)})`).join(' · ') || '—'}</p>
    ${z ? `<p><b>IC افق‌ها:</b> ۱ماه ${f1(z.ic, 3)} · ۳ماه ${f1(z.ic_3m, 3)} · ۶ماه ${f1(z.ic_6m, 3)} · ۱۲ماه ${f1(z.ic_12m, 3)} (زوال/ماندگاری سیگنال) &nbsp; <b>ماندگاری رتبه (خودهمبستگی ماه به ماه):</b> ${f1(z.rank_autocorr, 2)}</p>` : ''}`;
  $$$('#sg-detail a[data-s]').forEach(a => a.onclick = () => selectSig(a.dataset.s));
  if (d) { const base = ((z && z.q5_excess_ann != null) ? 0 : 0); sbars($('sg-bars'), d.ann_net.map((_, i) => 'D' + (i + 1)), d.ann_net, v => f1(v, 0), i => i === 9); $('sg-hz').innerHTML = `<tbody><tr><td>اسپیرمن رتبهٔ دهک با بازده</td><td class="n">${f1(spearmanArr(d.ann_net), 2)}</td></tr><tr><td>دهک ۱۰ − دهک ۱ (t)</td><td class="n ${tcls(d.spread_t)}">${f1(d.spread_t, 2)}</td></tr><tr><td>ماه‌های ارزیابی</td><td class="n">${d.n_months}</td></tr></tbody>`; } else { $('sg-bars').innerHTML = ''; $('sg-hz').innerHTML = ''; }
  $('sg-dlin').innerHTML = '<span><b>دهک‌ها</b> بازده خالص (۱۰۰ bp)، خام (بدون خنثی‌سازی)، هم‌وزن</span>';
}
function renderCorr() {
  const names = L.corr.names, host = $('sg-corr'); const col = v => v == null ? 'transparent' : v >= 0 ? `rgba(47,194,123,${Math.min(Math.abs(v), 1) * .85})` : `rgba(240,97,95,${Math.min(Math.abs(v), 1) * .85})`;
  const order = names.map((n, i) => [sigMeta(n).family, n, i]).sort((a, b) => a[0].localeCompare(b[0]) || a[1].localeCompare(b[1]));
  host.innerHTML = `<div class="lb-note">همبستگی رتبه‌ای میانگین مقطعی (هر سه ماه یک نمونه). معیارهای هم‌خانواده معمولاً ≥ ۰٫۷ هماند: برای ترکیب از هر خانواده یکی بردارید.</div><div class="heat-wrap"><table class="heat"><thead><tr><th class="r"></th>${order.map(([, n]) => `<th title="${esc(sigName(n))}"><div class="vt">${esc(sigName(n).slice(0, 14))}</div></th>`).join('')}</tr></thead><tbody>` +
    order.map(([, n, i]) => `<tr><th class="r">${esc(sigName(n))}</th>${order.map(([, , j]) => { const v = L.corr.m[i][j]; return `<td style="background:${col(v)}" title="${esc(sigName(n))} × ${esc(sigName(names[j]))}: ${f1(v, 2)}">${v == null ? '' : Math.round(v * 100)}</td>`; }).join('')}</tr>`).join('') + '</tbody></table></div>';
}

/* ════════════════════════════════ PLAN ════════════════════════════════ */
const plan = { src: 'lab', aum: 100, lot: 1, min_trade: 0.001, hold: [], cost: 100 };
/* ارسال وزن هدف از هر نما به «دستور اجرا»: گزینهٔ «ارسال‌شده» را می‌سازد، انتخاب می‌کند و نما را باز می‌کند (چه نما قبلاً ساخته شده باشد چه نه) */
function sendToPlan(name, w) {
  window.SIM_PLAN_SRC = { name, w };
  window.SIM_SHOW('plan');
  if ($('pl-src')) { fillPlanSrc(); $('pl-src').value = 'sent'; renderPlan(); }
  toast('وزن هدف به «دستور اجرا» فرستاده شد: ' + name);
}
window.SIM_SEND_PLAN = sendToPlan;
function fillPlanSrc() {
  const cur = $('pl-src').value, sent = window.SIM_PLAN_SRC;
  const opts = [...(sent ? [['sent', 'ارسال‌شده: ' + sent.name]] : []), ['K', 'شاخص كل (ارزش‌وزن، بورس)'], ['EW', 'كل (هم وزن) (بورس)'], ['lab', 'خروجی فعلی Lab'], ...L.library.filter(r => r.live && r.live.top && r.live.top.length).map(r => ['lib:' + r.id, 'کتابخانه · ' + r.name])];
  $('pl-src').innerHTML = opts.map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join('');
  if (opts.some(o => o[0] === cur)) $('pl-src').value = cur;
}
function initPlan() {
  const m = $('v-plan'); m.dataset.ready = 1;
  m.innerHTML = `
  <section class="panel" style="--lg:var(--lg-a)">
    <div class="panel-head"><span class="lg-badge">A</span><span class="panel-title">برنامهٔ اقدام · سفارش‌ها برای رسیدن به پرتفوی هدف</span><span class="chip" id="pl-chip"></span>
      <div class="panel-tools"><button class="tool" id="pl-csv">CSV</button><button class="tool" id="pl-json">JSON برای سامانهٔ الگوریتمی</button></div></div>
    <div class="ctl" id="pl-ctl"><label>هدف <select id="pl-src"></select></label><label>سرمایه (میلیارد ریال) <input type="number" id="pl-aum" value="100" min="1" step="10"></label>
      <label>حداقل معامله (٪ سرمایه) <input type="number" id="pl-min" value="0.1" min="0" step="0.05"></label><label>هزینهٔ رفت‌وبرگشت (bp) <input type="number" id="pl-cost" value="100" min="0" step="10"></label></div>
    <div class="ctl"><label>پرتفوی فعلی (نماد،تعداد — هر خط یک نماد؛ خالی = شروع از نقد) <textarea id="pl-hold" rows="2" placeholder="فولاد,120000&#10;فملی,50000" style="width:360px"></textarea></label><button class="tool" id="pl-apply">محاسبه</button><span class="mute" id="pl-note"></span></div>
    <div class="kpis" id="pl-kpis"></div>
    <div class="panel-body scroll"><table class="dt" id="pl-tab"></table></div>
    <div class="lineage" id="pl-lin"></div></section>
  <section class="panel" style="--lg:var(--lg-b)">
    <div class="panel-head"><span class="lg-badge">B</span><span class="panel-title">تقویم اقدام‌ها</span></div>
    <div class="panel-body scroll"><div class="prose" id="pl-cal"></div><table class="dt" id="pl-div"></table></div>
    <div class="lineage" id="pl-cal-lin"></div></section>`;
  fillPlanSrc();
  if (window.SIM_PLAN_SRC) $('pl-src').value = 'sent';
  ['pl-src', 'pl-aum', 'pl-min', 'pl-cost'].forEach(i => { $(i).onchange = renderPlan; }); $('pl-apply').onclick = renderPlan;
  plan.hold = store.get('hold') || ''; $('pl-hold').value = plan.hold;
  $('pl-csv').onclick = () => exportPlan('csv'); $('pl-json').onclick = () => exportPlan('json');
  renderPlan();
}
function targetFor(src) {
  const k = L.k, rl = L.rows - 1, w = new Float64Array(k);
  if (src === 'K' || src === 'EW') { let s = 0; for (let i = 0; i < k; i++) if (!L.codes[i].m && CTX.ok[rl * k + i]) { w[i] = src === 'K' ? Math.exp(CTX.mcap[rl * k + i]) : 1; s += w[i]; } return { name: src === 'K' ? 'شاخص كل (ارزش‌وزن)' : 'كل (هم وزن)', w: w.map(x => x / s) }; }
  if (src === 'sent') { const p = window.SIM_PLAN_SRC; return p ? { name: p.name, w: p.w } : { name: '—', w }; }
  if (src === 'lab') { if (lab.res && lab.res.live) { const x = lab.res.live.target, s = x.reduce((a, b) => a + b, 0) || 1; return { name: lab.name || specText(lab.spec), w: x.map(v => v / s) }; } return { name: '—', w }; }
  const r = L.library.find(x => 'lib:' + x.id === src); if (!r || !r.live) return { name: '—', w };
  let s = 0; r.live.top.forEach(([sym, wt]) => { const i = CTX.sym.indexOf(sym); if (i >= 0) { w[i] = wt; s += wt; } });
  return { name: r.name, w: w.map(x => x / (s || 1)) };
}
function parseHold(txt) {
  const m = new Map(); txt.split(/\n+/).forEach(line => { const p = line.split(/[,،\t;]/).map(x => x.trim()); if (p.length >= 2 && p[0]) { const q = parseFloat(p[1].replace(/[^\d.\-]/g, '')); if (q === q) m.set(p[0].replace(/ي/g, 'ی').replace(/ك/g, 'ک'), q); } });
  return m;
}
function renderPlan() {
  const k = L.k, rl = L.rows - 1, tgt = targetFor($('pl-src').value), aum = (+$('pl-aum').value || 100) * 1e9, minT = (+$('pl-min').value || 0) / 100, cost = (+$('pl-cost').value || 0) / 1e4;
  const txt = $('pl-hold').value; store.set('hold', txt); const hold = parseHold(txt);
  const px = i => L.px[i], symIdx = new Map(CTX.sym.map((s, i) => [s, i]));
  const cur = new Float64Array(k); let unknown = [];
  hold.forEach((q, s) => { const i = symIdx.get(s); if (i == null) unknown.push(s); else cur[i] = q; });
  let curVal = 0; for (let i = 0; i < k; i++) curVal += cur[i] * px(i);
  const base = hold.size ? Math.max(curVal, 0) : aum, V = hold.size ? aum : aum;     // سرمایه کل = ورودی کاربر (نقد + سهام)
  const orders = [];
  for (let i = 0; i < k; i++) {
    const wt = tgt.w[i] || 0, p = px(i); if (!(p > 0)) continue;
    const tq = Math.floor(wt * V / p / plan.lot) * plan.lot, dq = tq - cur[i], val = dq * p;
    if (dq === 0 || Math.abs(val) < minT * V) continue;
    const adv = Math.exp(CTX.adv[rl * k + i]), part = adv > 1 ? Math.abs(val) / adv : NaN;
    orders.push({ i, sym: L.codes[i].p || L.codes[i].s, raw: L.codes[i].s, name: L.codes[i].n || '', side: dq > 0 ? 'خرید' : 'فروش', qty: Math.abs(dq), px: p, val: Math.abs(val), w_now: cur[i] * p / V * 100, w_tgt: tq * p / V * 100, part, days: Math.max(1, Math.ceil(part / 0.1)), mkt: L.codes[i].m });
  }
  orders.sort((a, b) => (a.side === b.side ? b.val - a.val : a.side === 'فروش' ? -1 : 1));
  const buy = orders.filter(o => o.side === 'خرید').reduce((s, o) => s + o.val, 0), sell = orders.filter(o => o.side === 'فروش').reduce((s, o) => s + o.val, 0);
  plan.orders = orders; plan.meta = { target: tgt.name, aum: V, buy, sell, cost: (buy + sell) * cost / 2, n: orders.length };
  $('pl-chip').textContent = tgt.name;
  $('pl-kpis').innerHTML = [['سفارش‌ها', orders.length], ['خرید (میلیارد ریال)', f1(buy / 1e9)], ['فروش (میلیارد ریال)', f1(sell / 1e9)], ['گردش یک‌طرفه', f1(Math.max(buy, sell) / V * 100) + '٪'], ['هزینهٔ تخمینی (میلیون ریال)', f1((buy + sell) * cost / 2 / 1e6, 0)], ['سفارش‌های نیازمند چند روز', orders.filter(o => o.days > 1).length]]
    .map(([a, b]) => `<div class="kpi"><div class="k">${a}</div><div class="v">${b}</div></div>`).join('');
  $('pl-tab').innerHTML = th([['#'], ['اقدام'], ['نماد'], ['بازار'], ['تعداد', 'n'], ['قیمت مرجع', 'n'], ['ارزش (میلیون ریال)', 'n'], ['وزن فعلی %', 'n'], ['وزن هدف %', 'n'], ['٪ از ارزش معاملات روزانه', 'n'], ['اجرا در (روز)', 'n']]) + '<tbody>' + orders.slice(0, 400).map((o, j) => `<tr><td class="rank">${j + 1}</td><td><span class="chip ${o.side === 'خرید' ? 'ok' : 'bad'}">${o.side}</span></td><td><a class="symlink" onclick="openSym('${esc(o.raw)}')">${esc(o.sym)}</a></td><td>${o.mkt ? 'فرابورس' : 'بورس'}</td><td class="n">${fmt(o.qty, 0)}</td><td class="n">${fmt(o.px, 0)}</td><td class="n">${f1(o.val / 1e6, 0)}</td><td class="n">${f1(o.w_now, 2)}</td><td class="n">${f1(o.w_tgt, 2)}</td><td class="n ${o.part > 0.1 ? 'down' : ''}">${o.part === o.part ? f1(o.part * 100, 1) : '—'}</td><td class="n">${o.days}</td></tr>`).join('') + '</tbody>';
  $('pl-note').textContent = unknown.length ? 'نماد ناشناخته: ' + unknown.slice(0, 6).join('، ') : (hold.size ? `${hold.size} نماد فعلی خوانده شد` : 'شروع از نقد');
  $('pl-lin').innerHTML = `<span><b>قیمت مرجع</b> آخرین بستهٔ <span class="num">${L.asof}</span> — پیش از ثبت سفارش قیمت روز را جایگزین کنید</span><span><b>گرد کردن</b> به سهم کامل</span><span><b>سقف مشارکت</b> ۱۰٪ ارزش معاملات روزانهٔ ۶۳ روز</span>`;
  renderCal(tgt, cur);
}
const MS = 864e5, jmf = new Intl.DateTimeFormat('fa-IR-u-ca-persian-nu-latn', { year: 'numeric', month: '2-digit', day: '2-digit', weekday: 'long' });
function nextMonthEnds(n) {
  const out = [], key = d => jyf.format(d) + new Intl.DateTimeFormat('fa-IR-u-ca-persian-nu-latn', { month: '2-digit' }).format(d);
  let d = new Date(); d.setUTCHours(12, 0, 0, 0); let prev = key(d);
  for (let i = 0; i < 400 && out.length < n; i++) { const nx = new Date(d.getTime() + MS), kn = key(nx); if (kn !== prev) { let e = new Date(d.getTime()); while ([4, 5].includes(e.getUTCDay())) e = new Date(e.getTime() - MS); out.push(e); } d = nx; prev = kn; }
  return out;
}
function renderCal(tgt, cur) {
  const ends = nextMonthEnds(4), nextDay = d => { let e = new Date(d.getTime() + MS); while ([4, 5].includes(e.getUTCDay())) e = new Date(e.getTime() + MS); return e; };
  $('pl-cal').innerHTML = `<p><b>ریبالانس ماهانه (فاکتورها و هم‌وزن فصلی/ماهانه):</b> سیگنال در پایان آخرین روز معاملاتی هر ماه شمسی محاسبه می‌شود؛ سفارش‌ها روز معاملاتی بعد اجرا شوند (فرض بک‌تست: خرید در بستهٔ همان روز؛ تأخیر یک‌روزه حساسیت را در کتابخانه ببینید).</p>
    <table class="dt">${th([['ماه'], ['روز سیگنال (تقریبی)'], ['روز اجرا (تقریبی)']])}<tbody>${ends.map(e => `<tr><td>${jmf.format(e).split(' ').slice(-2).join(' ')}</td><td class="num">${jmf.format(e)}</td><td class="num">${jmf.format(nextDay(e))}</td></tr>`).join('')}</tbody></table>
    <p class="mute" style="margin-top:6px">تعطیلات رسمی در تقویم لحاظ نشده است [تأیید لازم]؛ روز معاملاتی واقعی را از تقویم بورس تأیید کنید. هم‌وزن «كل»: ریبالانس در نخستین روز معاملاتی هر فصل شمسی (فصل ۳).</p>
    <p><b>سود نقدی:</b> سود تصویب‌شده در مجمع در «روز استحقاق» از قیمت کم می‌شود (شاخص بازده کل آن را همان روز سرمایه‌گذاری مجدد حساب می‌کند)، ولی نقد بعداً می‌رسد. جدول زیر سودهای اعلام‌شدهٔ نمادهای هدف/فعلی را با تاریخ پرداخت نشان می‌دهد؛ در روز پرداخت، نقد را به نسبت وزن هدف سرمایه‌گذاری کنید.</p>`;
  const tw = tgt.w, rows = (L.divs || []).map(d => { const i = CTX.sym.indexOf(d.sym); return { ...d, i, w: i >= 0 ? tw[i] : 0, q: i >= 0 ? cur[i] : 0 }; }).filter(d => d.i >= 0 && (d.w > 0 || d.q > 0)).sort((a, b) => a.pay.localeCompare(b.pay));
  $('pl-div').innerHTML = th([['نماد'], ['سود هر سهم (ریال)', 'n'], ['تاریخ پرداخت'], ['نوع'], ['نقد مورد انتظار (میلیون ریال)', 'n']]) + '<tbody>' + (rows.map(d => { const q = d.q || Math.floor(d.w * (+$('pl-aum').value || 100) * 1e9 / (L.px[d.i] || 1)); return `<tr><td>${esc(d.sym)}</td><td class="n">${fmt(d.dps, 0)}</td><td class="num" title="${jd(d.pay)}">${d.pay}</td><td>${d.kind === 'announced' ? 'اعلام‌شده' : 'برآورد'}</td><td class="n">${f1(q * d.dps / 1e6, 1)}</td></tr>`; }).join('') || '<tr><td colspan="5" class="mute">سود اعلام‌شده‌ای برای نمادهای این پرتفوی در افق نیست.</td></tr>') + '</tbody>';
  $('pl-cal-lin').innerHTML = `<span><b>منبع</b> کدال + فارابی (فصل ۳ §۳٫۵)</span><span><b>نقد مورد انتظار</b> تعداد (فعلی یا هدف) × سود هر سهم</span>`;
}
function exportPlan(kind) {
  const o = plan.orders || [], m = plan.meta; if (!o.length) { toast('سفارشی نیست'); return; }
  if (kind === 'csv') { download('trade_plan.csv', [['action', 'symbol', 'qty', 'ref_price', 'value_rial', 'w_now_pct', 'w_target_pct', 'adv_participation', 'days'], ...o.map(x => [x.side === 'خرید' ? 'BUY' : 'SELL', x.sym, x.qty, x.px, Math.round(x.val), x.w_now.toFixed(3), x.w_tgt.toFixed(3), x.part === x.part ? x.part.toFixed(4) : '', x.days])]); return; }
  const id = (s, d) => { let h = 0; const t = s + d; for (let i = 0; i < t.length; i++) h = (h * 31 + t.charCodeAt(i)) >>> 0; return h.toString(16); }, plan_id = id(m.target, L.asof + m.aum);
  const body = { schema: 'sim.trade_plan/1', plan_id, asof: L.asof, created: new Date().toISOString(), target: m.target, aum_rial: m.aum, cost_bp_roundtrip: +$('pl-cost').value,
    execution: { convention: 'signal at last trading day close; execute next trading day', participation_cap: 0.1, price_basis: 'last_close_ref', note: 'قیمت مرجع آخرین بسته است؛ سامانه باید با قیمت زنده/محدودهٔ مجاز نوسان جایگزین کند' },
    orders: o.map(x => ({ id: id(plan_id, x.sym + x.side), symbol: x.sym, ins_code: L.codes[x.i].c, side: x.side === 'خرید' ? 'BUY' : 'SELL', qty: x.qty, ref_price: x.px, split_days: x.days, type: 'rebalance' })) };
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(body, null, 1)], { type: 'application/json' })); a.download = `trade_plan_${plan_id}.json`; a.click();
}

/* ════════════ ثبت در روتر views.js ════════════ */
const wrap = f => () => ensureData(f);
window.SIM_NEWVIEWS = {
  lab: { id: 'v-lab', init: wrap(initLab), redraw: () => { if (lab.res && lab.tab === 'perf' && $('lb-chart')) tabPerf($('lb-view')); } },
  sig: { id: 'v-sig', init: wrap(initSig), redraw: () => { } },
  plan: { id: 'v-plan', init: wrap(() => { L.px = window.SIM_LAB.px ? Float64Array.from(window.SIM_LAB.px) : new Float64Array(L.k); initPlan(); }), redraw: () => { } },
};
})();
