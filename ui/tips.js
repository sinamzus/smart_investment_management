/* همتا — راهنمای شناور (Tooltip)
   هر برچسب، ستون، شاخص، دکمه و نشانی که در واژه‌نامه (glossary.js) مدخل دارد، با نگه‌داشتن نشانگر
   (یا فوکوس صفحه‌کلید) توضیح، فرمول و مرجع سند را نشان می‌دهد. برچسب‌های دارای راهنما خط‌چین زیرشان دارند. */
(function () {
  const G = window.SIM_GLOSSARY; if (!G) return;
  const SEL = 'th, .kpi .k, .panel-title, .lineage b, .legend span:not(.readout), .seg button, button.tool, .chip, .nav a, .ctl label, .ctl .mute, .statusbar span, .topbar button, .lg-badge, .symlink, #dev td .chip, #dev td .num, #pf-tab td .chip, #qa-sec td .chip, #fn-tab td .chip, #rk-corr td, #sy-title, #sy-q, #sy-info td:first-child, summary, .lb-row, [data-tip]';
  const norm = t => t.replace(/\s+/g, ' ').trim().replace(/[\s%٪:.]+$/, '').replace(/(\D)\d+$/, '$1').trim();
  const E = {}; for (const k in G.E) E[norm(k)] = G.E[k];                 // کلیدهای واژه‌نامه هم یکسان‌سازی شوند
  const viewOf = el => { const m = el.closest('main.workspace'); return m ? m.id.replace(/^v-/, '') : ''; };

  /* منوی کشویی: توضیح گزینهٔ انتخاب‌شده (data-tip یا title روی <option>) کنار راهنمای خود منو می‌آید؛
     مرورگرها hover روی گزینه‌های باز منو را قابل‌اعتماد نشان نمی‌دهند، پس راهنمای منو همیشه گزینهٔ فعلی را هم می‌گوید. */
  function optNote(el) {
    const s = el.tagName === 'SELECT' ? el : (el.tagName === 'LABEL' ? el.querySelector('select') : null);
    if (!s) return '';
    const o = s.selectedOptions && s.selectedOptions[0], d = o && (o.dataset.tip || o.title);
    return d ? `«${o.textContent.trim()}»: ${d}` : '';
  }
  function lookup(el) {
    const r = lookup0(el), o = optNote(el);
    return o ? { ...(r || {}), d: (r && r.d) || '', o } : r;
  }
  function lookup0(el) {
    if (el.dataset.tip) return { d: el.dataset.tip, doc: el.dataset.doc };
    for (const [sel, fn] of G.RULES) if (el.matches(sel)) { const r = fn(el); if (r) return r; }
    if (el.matches('.nav a')) { const t = norm(el.textContent); return E[t] ? { ...E[t], t } : null; }
    let t = norm(el.matches('.ctl label') ? (el.firstChild && el.firstChild.textContent || el.textContent) : el.textContent);
    const v = viewOf(el);
    const e = E[v + ':' + t] || E[t];
    if (e) return { t, ...e };
    for (const [re, x] of G.PATTERNS) if (re.test(t)) return x ? { t, ...x } : null;
    return null;
  }

  /* علامت‌گذاری عناصر دارای راهنما (خط‌چین + نشانگر راهنما) */
  function scan(root) {
    (root || document).querySelectorAll(SEL).forEach(el => {
      if (el.dataset.tk !== undefined) return;
      const r = lookup(el); el.dataset.tk = r ? '1' : '';
      if (r) { el.classList.add('has-tip'); if (!el.hasAttribute('tabindex') && !/^(A|BUTTON|INPUT)$/.test(el.tagName) && !el.closest('a,button')) el.tabIndex = -1; }
    });
  }
  let pend = 0;
  new MutationObserver(ms => {
    let any = false;
    for (const m of ms) {
      const n = m.target.nodeType === 1 ? m.target : m.target.parentElement;
      if (!n || n.closest('#tip')) continue;
      any = true;
      const tk = n.closest('[data-tk]'); if (tk) delete tk.dataset.tk;     // متن عوض شد ← دوباره بسنج
    }
    if (any && !pend) pend = requestAnimationFrame(() => { pend = 0; scan(); });
  }).observe(document.body, { childList: true, subtree: true, characterData: true });

  /* پنجرهٔ راهنما */
  const tip = document.createElement('div');
  tip.id = 'tip'; tip.setAttribute('role', 'tooltip'); tip.hidden = true;
  document.body.appendChild(tip);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
  let cur = null, timer = 0;

  /* ارجاع‌های سند هر راهنما: data-doc عنصر، «فصل N §x» در مرجع (s) یا متن راهنما؛ پیوندشان کشوی سند را باز می‌کند (ui/docs.js) */
  function docRefs(r, el) {
    const A = window.SIM_DOCS_API; if (!A) return [];
    const own = r.doc || (el.closest('[data-doc]:not(.doclink)') || {}).dataset?.doc;
    const L = [...(own ? [A.parse(own)] : []), ...A.refs(r.s || ''), ...A.refs(r.d || '')], seen = new Set();
    return L.filter(x => { const k = A.refStr(x); if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, 3);
  }
  let curDocs = [];
  function show(el) {
    const r = lookup(el); if (!r) return;
    const A = window.SIM_DOCS_API; curDocs = el.matches('.doclink, .doc-btn') ? [] : docRefs(r, el);
    const dl = curDocs.length ? `<div class="tdoc">توضیح فنی در سند: ${curDocs.map(x => `<a data-doc="${esc(A.refStr(x))}">${esc(A.labelOf(x))}</a>`).join('، ')} <span class="k">F1</span></div>` : '';
    tip.innerHTML = `${r.t ? `<div class="tt">${esc(r.t)}</div>` : ''}${r.d ? `<div class="td">${esc(r.d)}</div>` : ''}${r.o ? `<div class="to">${esc(r.o)}</div>` : ''}${r.f ? `<div class="tf">${esc(r.f)}</div>` : ''}${r.s ? `<div class="ts">${esc(r.s)}</div>` : ''}${dl}`;
    tip.classList.toggle('live', !!dl);
    tip.hidden = false; tip.style.left = '0px'; tip.style.top = '0px';
    const b = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight, W = innerWidth, H = innerHeight, g = 8;
    let x = b.right - w; if (x < g) x = Math.min(b.left, W - w - g); x = Math.max(g, Math.min(x, W - w - g));
    let y = b.bottom + 6; if (y + h > H - g) y = b.top - h - 6; if (y < g) y = g;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
    el.setAttribute('aria-describedby', 'tip');
  }
  function hide() { clearTimeout(timer); tip.hidden = true; if (cur) cur.removeAttribute('aria-describedby'); cur = null; }
  const target = e => e.target.closest && e.target.closest('.has-tip');

  document.addEventListener('pointerover', e => {
    if (tip.contains(e.target)) { clearTimeout(lv); return; }           // روی خود راهنما (پیوند سند)
    const el = target(e); if (el === cur) return;
    if (!el && cur && !tip.hidden && tip.classList.contains('live')) return;   // در مسیر رسیدن به راهنمای دارای پیوند
    hide(); if (!el || e.pointerType === 'touch') return;
    cur = el; timer = setTimeout(() => show(el), 280);
  });
  // راهنمای دارای پیوند سند «قابل‌ورود» است: نشانگر از عنصر به خود راهنما برود، بسته نمی‌شود تا پیوند کلیک شود
  let lv = 0;
  document.addEventListener('pointerout', e => {
    if (!cur || cur.contains(e.relatedTarget) || tip.contains(e.relatedTarget)) return;
    if (tip.classList.contains('live') && !tip.contains(e.target)) { clearTimeout(lv); lv = setTimeout(hide, 220); } else hide();   // فرصت عبور از فاصلهٔ عنصر تا راهنما
  });
  tip.addEventListener('pointerleave', e => { if (!(cur && cur.contains(e.relatedTarget))) hide(); });
  tip.addEventListener('pointerenter', () => clearTimeout(lv));
  tip.addEventListener('click', e => { if (e.target.closest('.tdoc a')) setTimeout(hide, 0); });
  document.addEventListener('focusin', e => { const el = target(e); hide(); if (el) { cur = el; show(el); } });
  document.addEventListener('focusout', hide);
  document.addEventListener('change', e => { const el = target(e); if (el && el === cur) show(el); });   // گزینهٔ تازهٔ منو
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') hide();
    if (e.key === 'F1' && cur && !tip.hidden && curDocs.length && window.SIM_DOCS_API) { e.preventDefault(); window.SIM_DOCS_API.open(curDocs[0]); hide(); }
  });
  addEventListener('scroll', e => { if (!tip.contains(e.target)) hide(); }, true);
  /* لمس: نگه‌داشتن انگشت (۵۰۰ میلی‌ثانیه) راهنما را نشان می‌دهد */
  let lp = 0;
  document.addEventListener('touchstart', e => { const el = target(e); clearTimeout(lp); if (el) lp = setTimeout(() => { cur = el; show(el); }, 500); }, { passive: true });
  document.addEventListener('touchend', () => clearTimeout(lp), { passive: true });

  scan();
  window.SIM_TIPS = { scan, lookup };
})();
