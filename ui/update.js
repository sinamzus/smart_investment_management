/* همتا — پنل «داده و محاسبات»: تاریخ آخرین دریافت داده و آخرین بازسازی محاسبات، و راهنمای اجرای آن‌ها (فصل ۰۹ §۹٫۶)
   صفحه فایل ایستاست و خودش برنامه اجرا نمی‌کند؛ دکمه‌های «اجرا» پیوند hamta://fetch|fetch-full|rebuild هستند که پس از ثبت یک‌بارهٔ
   register_ui_actions.bat (ریشهٔ مخزن، فقط شاخهٔ کاربر ویندوز) tools/ui_action.bat را باز می‌کنند و او فقط همین سه کار را اجرا می‌کند؛
   بی‌ثبت، همان دوبارکلیک روی update_data.bat و rebuild_all.bat در ریشهٔ مخزن
   و وضعیت هر گام در ui/data/update_status.js (window.SIM_UPDATE، tools/update_pipeline.py) نوشته می‌شود.
   پس از «اجرا» صفحه همین فایل را هر چند ثانیه دوباره می‌خواند: اگر کار شروع شد پیشرفت گام‌ها زنده دیده می‌شود، و اگر تا ۲۵ ثانیه
   شروعی ثبت نشد (پیوند hamta:// ثبت نشده یا مرورگر اجازه نداد) پیام روشن می‌دهد؛ پیش‌تر دکمه بی‌صدا «شروع شد» می‌گفت (۲۰۲۶-۱۰-۲۱). */
(function () {
'use strict';
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const UU = () => window.SIM_UPDATE || {};                              // وضعیت ثبت‌شده؛ با پایش دوباره خوانده می‌شود
const D = window.SIM_DATA || { meta: {} };
const jdt = s => { if (!s) return '—'; const [d, t] = String(s).split(' '); const j = window.SIM_JDATE ? window.SIM_JDATE.j(d) : d; return j + (t ? ' ' + t.slice(0, 5) : ''); };
const dur = s => s == null ? '' : s < 90 ? `${s} ثانیه` : `${Math.round(s / 60)} دقیقه`;
// مسیر ریشهٔ مخزن از نشانی همین صفحه (file:///C:/…/ui/index.html)
const root = (() => { try { const p = decodeURIComponent(location.pathname).replace(/^\/([A-Za-z]:)/, '$1').replace(/\/ui\/[^/]*$/, ''); return location.protocol === 'file:' ? p.replace(/\//g, '\\') : ''; } catch (e) { return ''; } })();
const fileOf = n => (root ? root + (root.includes('\\') ? '\\' : '/') : '') + n;
// زمان ساخت هر فایل داده (قدیمی‌ترین = آخرین بازسازی کامل در عمل)
const built = [['شاخص‌ها', D.meta && D.meta.built], ['Factor Lab و کیفیت داده', (window.SIM_EXTRA || {}).built], ['همتاساز', (window.SIM_REP || {}).built], ['صندوق‌ها', (window.SIM_FUNDS || {}).built]].filter(x => x[1]);
const oldest = built.length ? built.reduce((a, b) => (a[1] < b[1] ? a : b)) : null;

function state(rec) {
  if (!rec || !rec.started) return ['', 'ثبت نشده'];
  if (rec.running) return ['warn', 'در حال اجرا…'];
  return rec.ok ? ['ok', 'موفق'] : ['bad', 'با خطا'];
}
function card(kind, title, rec, files, what, eta) {
  const [cls, txt] = state(rec);
  const steps = (rec && rec.steps || []).map(s => `<li><span class="${s.ok === true ? 'up' : s.ok === false ? 'down' : 'mute'}">${s.ok === true ? '✓' : s.ok === false ? '✗' : '…'}</span> ${esc(s.name)} <span class="mute">${dur(s.seconds)}${s.note ? ' · ' + esc(s.note) : ''}</span>${s.ok === false && s.last_line ? `<div class="mute" dir="auto">${esc(s.last_line)}</div>` : ''}</li>`).join('');
  return `<section class="upd-card">
    <div class="upd-h"><b>${title}</b><span class="chip ${cls}">${txt}</span></div>
    <div class="upd-meta"><span>آخرین اجرا: <b>${jdt(rec && (rec.finished || rec.started))}</b></span>${kind === 'fetch' ? `<span>داده تا: <b>${jdt((rec && rec.data_asof) || D.meta.asof)}</b></span>` : `<span>قدیمی‌ترین دادهٔ ساخته‌شده: <b>${oldest ? jdt(oldest[1]) + ' (' + esc(oldest[0]) + ')' : '—'}</b></span>`}${rec && rec.log ? `<span class="mute">گزارش: <code>${esc(rec.log)}</code></span>` : ''}</div>
    ${rec && rec.note ? `<p class="mute">${esc(rec.note)}</p>` : ''}
    <p class="mute">${what} ${eta}</p>
    ${files.map(([f, d, act]) => `<div class="upd-file"><a class="tool upd-go" href="hamta://${act}" data-act="${act}" data-tip="${esc(f)} را در پنجرهٔ جدا شروع می‌کند (پیوند hamta://${act}). بار اول یک‌بار register_ui_actions.bat را اجرا کنید؛ مرورگر می‌پرسد «باز شود؟» — تأیید کنید. وضعیت هر گام همین‌جا ثبت می‌شود؛ پس از پایان «بارگذاری دوباره».">▶ اجرا</a><code dir="ltr">${esc(fileOf(f))}</code><button class="tool" data-copy="${esc(fileOf(f))}" data-tip="مسیر فایل را کپی می‌کند؛ بدون ثبت پیوند، در File Explorer باز کنید و دوبار کلیک کنید.">کپی مسیر</button><span class="mute">${d}</span></div>`).join('')}
    ${steps ? `<ul class="upd-steps">${steps}</ul>` : ''}
  </section>`;
}
/** خواندن دوبارهٔ ui/data/update_status.js (بی‌کش؛ در file:// هم کار می‌کند) */
function reloadStatus(cb) {
  const sc = document.createElement('script'); sc.src = 'data/update_status.js?t=' + Date.now();
  sc.onload = sc.onerror = () => { sc.remove(); cb && cb(); }; document.head.appendChild(sc);
}
const tOf = x => (x ? new Date(String(x).replace(' ', 'T')).getTime() : 0);   // زمان محلی نوشته‌شده با update_pipeline.now()
const KIND = { fetch: 'fetch', 'fetch-full': 'fetch', rebuild: 'rebuild' };
let watch = null;                                                       // {act، t0، seen}
function poll() {
  if (!watch) return;
  reloadStatus(() => {
    const rec = UU()[KIND[watch.act]], w = watch;
    if (!w.seen && rec && rec.started && tOf(rec.started) >= w.t0 - 10000) w.seen = true;
    const m = document.getElementById('upd-panel'), open = m && !m.hidden;
    if (!w.seen && Date.now() - w.t0 > 25000) { w.fail = true; watch = null; if (open) open_(); refreshBtn(); return; }
    if (w.seen && rec && !rec.running) { w.done = true; watch = null; if (open) open_(); refreshBtn(); return; }
    if (open) open_(); refreshBtn();
    setTimeout(poll, w.seen ? 5000 : 3000);
  });
}
let last = null;                                                        // آخرین «اجرا» برای پیام بعد از پایان یا شکست
function open_() {
  const U = UU();
  let m = document.getElementById('upd-panel');
  if (!m) { m = document.createElement('div'); m.id = 'upd-panel'; m.className = 'upd-overlay'; document.body.appendChild(m); m.addEventListener('click', e => { if (e.target === m) m.hidden = true; }); }
  const f = U.fetch, r = U.rebuild;
  const stale = f && f.finished && (!r || !r.finished || r.finished < f.finished);
  m.innerHTML = `<div class="upd-box" role="dialog" aria-label="داده و محاسبات">
    <div class="upd-top"><b>داده و محاسبات</b><span class="spacer"></span><button class="tool" id="upd-reload" data-tip="صفحه را دوباره بار می‌کند تا آخرین وضعیت و دادهٔ ساخته‌شده دیده شود.">بارگذاری دوباره</button><button class="tool" id="upd-x" aria-label="بستن">×</button></div>
    <p class="mute">با «▶ اجرا» هر کار در پنجرهٔ سیاه جدایی شروع می‌شود و پیشرفتش را نشان می‌دهد؛ وضعیت هر گام همین‌جا ثبت می‌شود و پس از پایان «بارگذاری دوباره» را بزنید. هم‌زمان با جمع‌آوری کدال اجرا کردن مشکلی ندارد (این ابزار به کدال درخواست نمی‌فرستد).</p>
    <div class="upd-file"><b>یک‌بار، پیش از نخستین «اجرا»:</b><code dir="ltr">${esc(fileOf('register_ui_actions.bat'))}</code><button class="tool" data-copy="${esc(fileOf('register_ui_actions.bat'))}" data-tip="مسیر را کپی کنید، در File Explorer باز و دوبار کلیک کنید. پیوندهای hamta:// را فقط برای کاربر فعلی ویندوز ثبت می‌کند (بدون دسترسی مدیر) و فقط سه کار دریافت، دریافت کامل و محاسبهٔ دوباره را اجرا می‌کند. حذف: register_ui_actions.bat /u">کپی مسیر</button><span class="mute">اگر «اجرا» کاری نکرد، این را یک‌بار دوبار کلیک کنید؛ یا خود فایل هر کار را دوبار کلیک کنید.</span></div>
    ${last && last.fail ? `<div class="lb-note bad"><b>«اجرا» کاری شروع نکرد.</b> در ۲۵ ثانیه هیچ شروعی ثبت نشد. معمولاً یعنی پیوند <code dir="ltr">hamta://</code> روی این ویندوز ثبت نشده یا مرورگر اجازهٔ باز کردن نداد. یک‌بار فایل <code dir="ltr">register_ui_actions.bat</code> (بالا، «کپی مسیر») را در File Explorer دوبار کلیک کنید و دوباره «اجرا» بزنید؛ اگر مرورگر پرسید «باز شود؟» تأیید کنید. راه دیگر: خود فایل همان کار (مثلاً <code dir="ltr">update_data.bat</code>) را دوبار کلیک کنید.</div>` : ''}
    ${watch ? `<div class="lb-note"><b>${watch.seen ? 'در حال اجرا…' : 'در انتظار شروع…'}</b> ${watch.seen ? 'پنجرهٔ سیاه کار را باز نگه دارید؛ گام‌ها این‌جا خودکار به‌روز می‌شوند.' : 'اگر مرورگر پرسید «باز شود؟» تأیید کنید.'}</div>` : ''}
    ${last && last.done ? '<div class="lb-note"><b>کار تمام شد.</b> «بارگذاری دوباره» را بزنید تا دادهٔ تازه در صفحه‌ها دیده شود.</div>' : ''}
    ${stale ? '<div class="lb-note"><b>داده تازه‌تر از محاسبات است.</b> پس از دریافت داده، «محاسبهٔ دوباره» را هم اجرا کنید تا اعداد صفحه‌ها به‌روز شوند.</div>' : ''}
    ${card('fetch', '۱ · دریافت داده', f, [['update_data.bat', 'روزانه: نمادهای تازه، قیمت ۳۰ روز آخر، شاخص‌های رسمی، اقدامات شرکتی نمادهای تغییرکرده', 'fetch'], ['update_data_full.bat', 'کامل: به‌علاوهٔ همهٔ اقدامات شرکتی، سودهای فارابی و NAV صندوق‌ها (کند)', 'fetch-full']], 'از TSETMC و منابع سود؛ پروکسی محیط خودکار خالی می‌شود.', 'زمان تقریبی: روزانه ۱۰ تا ۳۰ دقیقه، کامل چند ساعت [برآورد].')}
    ${card('rebuild', '۲ · محاسبهٔ دوباره', r, [['rebuild_all.bat', 'همهٔ محاسبات و دادهٔ صفحه‌ها: شاخص‌ها، آزمایشگاه و کتابخانه، همتاها، Factor Lab، دفتر زنده، پرتفو، سند', 'rebuild']], 'از دادهٔ موجود؛ به اینترنت نیاز ندارد. سفارش پیش‌نویس دفتر زنده هم ساخته می‌شود ولی در دفتر زنده ثبت نمی‌شود.', 'زمان تقریبی: ۳۰ تا ۶۰ دقیقه [برآورد].')}
  </div>`;
  m.hidden = false;
  m.querySelector('#upd-x').onclick = () => { m.hidden = true; };
  m.querySelector('#upd-reload').onclick = () => location.reload();
  m.querySelectorAll('[data-copy]').forEach(b => { b.onclick = () => copy(b.dataset.copy, b); });
  // هم‌زمان دو کار سنگین نه: اگر کاری در حال اجراست، پیش از شروع تأیید بگیر
  m.querySelectorAll('a.upd-go').forEach(a => { a.onclick = e => {
    const busy = (U.fetch && U.fetch.running) || (U.rebuild && U.rebuild.running);
    if (busy && !confirm('طبق آخرین وضعیت ثبت‌شده یک کار هنوز در حال اجراست. اجرای هم‌زمان ممکن است داده را نیمه‌کاره بخواند. باز هم شروع شود؟')) { e.preventDefault(); return; }
    last = watch = { act: a.dataset.act, t0: Date.now(), seen: false };
    a.textContent = '⏳ در انتظار شروع…';
    setTimeout(() => { open_(); poll(); }, 1500);                       // پیوند را مرورگر باز می‌کند؛ بعد وضعیت پایش می‌شود
  }; });
  // اگر کاری از پیش در حال اجراست (مثلاً با دوبارکلیک فایل)، پیشرفتش را هم زنده نشان بده
  if (!watch && ((U.fetch && U.fetch.running) || (U.rebuild && U.rebuild.running))) { watch = { act: U.fetch && U.fetch.running ? 'fetch' : 'rebuild', t0: 0, seen: true }; setTimeout(poll, 5000); }
}
function copy(t, b) {
  const done = () => { b.textContent = 'کپی شد'; setTimeout(() => { b.textContent = 'کپی مسیر'; }, 1500); };
  if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(t).then(done, () => fallback()); return; }
  fallback();
  function fallback() { const x = document.createElement('textarea'); x.value = t; document.body.appendChild(x); x.select(); try { document.execCommand('copy'); done(); } catch (e) { /* کپی دستی */ } x.remove(); }
}
// دکمه کنار «داده تا» در نوار بالا + برچسب وضعیت
function refreshBtn() {
  const b = document.getElementById('upd-btn'); if (!b) return;
  const U = UU(), f = U.fetch, r = U.rebuild, run = (f && f.running) || (r && r.running), bad = (f && f.ok === false) || (r && r.ok === false);
  b.className = 'tool' + (run ? ' upd-run' : bad ? ' upd-bad' : ''); b.textContent = run ? 'در حال به‌روزرسانی…' : 'داده و محاسبات';
  b.dataset.tip = `آخرین دریافت داده: ${jdt(f && f.finished)}${f ? ' (' + state(f)[1] + ')' : ''} · آخرین محاسبهٔ دوباره: ${jdt(r && r.finished)}${r ? ' (' + state(r)[1] + ')' : ''}. برای دریافت داده یا محاسبهٔ دوباره کلیک کنید.`;
}
function mount() {
  const chip = document.getElementById('asof-chip'); if (!chip || document.getElementById('upd-btn')) return;
  const b = document.createElement('button'); b.id = 'upd-btn'; b.onclick = open_;
  chip.after(b); refreshBtn();
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') { const m = document.getElementById('upd-panel'); if (m) m.hidden = true; } });
mount();
window.SIM_UPDATE_OPEN = open_;
})();
