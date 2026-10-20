/* همتا — پنل «داده و محاسبات»: تاریخ آخرین دریافت داده و آخرین بازسازی محاسبات، و راهنمای اجرای آن‌ها (فصل ۰۹ §۹٫۶)
   صفحه فایل ایستاست و نمی‌تواند برنامه اجرا کند؛ دریافت و بازسازی با دوبارکلیک روی update_data.bat و rebuild_all.bat در ریشهٔ مخزن انجام می‌شود
   و وضعیت هر گام در ui/data/update_status.js (window.SIM_UPDATE، tools/update_pipeline.py) نوشته می‌شود. «بارگذاری دوباره» آخرین وضعیت را نشان می‌دهد. */
(function () {
'use strict';
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const U = window.SIM_UPDATE || {};
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
    ${files.map(([f, d]) => `<div class="upd-file"><code dir="ltr">${esc(fileOf(f))}</code><button class="tool" data-copy="${esc(fileOf(f))}" data-tip="مسیر فایل را کپی می‌کند؛ در File Explorer باز کنید و دوبار کلیک کنید.">کپی مسیر</button><span class="mute">${d}</span></div>`).join('')}
    ${steps ? `<ul class="upd-steps">${steps}</ul>` : ''}
  </section>`;
}
function open_() {
  let m = document.getElementById('upd-panel');
  if (!m) { m = document.createElement('div'); m.id = 'upd-panel'; m.className = 'upd-overlay'; document.body.appendChild(m); m.addEventListener('click', e => { if (e.target === m) m.hidden = true; }); }
  const f = U.fetch, r = U.rebuild;
  const stale = f && f.finished && (!r || !r.finished || r.finished < f.finished);
  m.innerHTML = `<div class="upd-box" role="dialog" aria-label="داده و محاسبات">
    <div class="upd-top"><b>داده و محاسبات</b><span class="spacer"></span><button class="tool" id="upd-reload" data-tip="صفحه را دوباره بار می‌کند تا آخرین وضعیت و دادهٔ ساخته‌شده دیده شود.">بارگذاری دوباره</button><button class="tool" id="upd-x" aria-label="بستن">×</button></div>
    <p class="mute">صفحه یک فایل ایستاست و نمی‌تواند برنامه اجرا کند. برای هر کار، فایل مربوط را در پوشهٔ پروژه دوبار کلیک کنید؛ پنجرهٔ سیاهی باز می‌شود که پیشرفت را نشان می‌دهد. وضعیت هر گام همین‌جا ثبت می‌شود؛ پس از پایان «بارگذاری دوباره» را بزنید. هم‌زمان با جمع‌آوری کدال اجرا کردن مشکلی ندارد (این ابزار به کدال درخواست نمی‌فرستد).</p>
    ${stale ? '<div class="lb-note"><b>داده تازه‌تر از محاسبات است.</b> پس از دریافت داده، «محاسبهٔ دوباره» را هم اجرا کنید تا اعداد صفحه‌ها به‌روز شوند.</div>' : ''}
    ${card('fetch', '۱ · دریافت داده', f, [['update_data.bat', 'روزانه: نمادهای تازه، قیمت ۳۰ روز آخر، شاخص‌های رسمی، اقدامات شرکتی نمادهای تغییرکرده'], ['update_data_full.bat', 'کامل: به‌علاوهٔ همهٔ اقدامات شرکتی، سودهای فارابی و NAV صندوق‌ها (کند)']], 'از TSETMC و منابع سود؛ پروکسی محیط خودکار خالی می‌شود.', 'زمان تقریبی: روزانه ۱۰ تا ۳۰ دقیقه، کامل چند ساعت [برآورد].')}
    ${card('rebuild', '۲ · محاسبهٔ دوباره', r, [['rebuild_all.bat', 'همهٔ محاسبات و دادهٔ صفحه‌ها: شاخص‌ها، آزمایشگاه و کتابخانه، همتاها، Factor Lab، دفتر زنده، پرتفو، سند']], 'از دادهٔ موجود؛ به اینترنت نیاز ندارد. دستور اجرای پیش‌نویس هم ساخته می‌شود ولی در دفتر زنده ثبت نمی‌شود.', 'زمان تقریبی: ۳۰ تا ۶۰ دقیقه [برآورد].')}
  </div>`;
  m.hidden = false;
  m.querySelector('#upd-x').onclick = () => { m.hidden = true; };
  m.querySelector('#upd-reload').onclick = () => location.reload();
  m.querySelectorAll('[data-copy]').forEach(b => { b.onclick = () => copy(b.dataset.copy, b); });
}
function copy(t, b) {
  const done = () => { b.textContent = 'کپی شد'; setTimeout(() => { b.textContent = 'کپی مسیر'; }, 1500); };
  if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(t).then(done, () => fallback()); return; }
  fallback();
  function fallback() { const x = document.createElement('textarea'); x.value = t; document.body.appendChild(x); x.select(); try { document.execCommand('copy'); done(); } catch (e) { /* کپی دستی */ } x.remove(); }
}
// دکمه کنار «داده تا» در نوار بالا + برچسب وضعیت
function mount() {
  const chip = document.getElementById('asof-chip'); if (!chip || document.getElementById('upd-btn')) return;
  const f = U.fetch, r = U.rebuild, run = (f && f.running) || (r && r.running), bad = (f && f.ok === false) || (r && r.ok === false);
  const b = document.createElement('button'); b.className = 'tool' + (run ? ' upd-run' : bad ? ' upd-bad' : ''); b.id = 'upd-btn'; b.textContent = run ? 'در حال به‌روزرسانی…' : 'داده و محاسبات';
  b.dataset.tip = `آخرین دریافت داده: ${jdt(f && f.finished)}${f ? ' (' + state(f)[1] + ')' : ''} · آخرین محاسبهٔ دوباره: ${jdt(r && r.finished)}${r ? ' (' + state(r)[1] + ')' : ''}. برای دریافت داده یا محاسبهٔ دوباره کلیک کنید.`;
  b.onclick = open_;
  chip.after(b);
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') { const m = document.getElementById('upd-panel'); if (m) m.hidden = true; } });
mount();
window.SIM_UPDATE_OPEN = open_;
})();
