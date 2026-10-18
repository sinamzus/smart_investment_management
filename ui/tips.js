/* ماکت — راهنمای شناور (Tooltip)
   هر برچسب، ستون، شاخص، دکمه و نشانی که در واژه‌نامه (glossary.js) مدخل دارد، با نگه‌داشتن نشانگر
   (یا فوکوس صفحه‌کلید) توضیح، فرمول و مرجع سند را نشان می‌دهد. برچسب‌های دارای راهنما خط‌چین زیرشان دارند. */
(function () {
  const G = window.SIM_GLOSSARY; if (!G) return;
  const SEL = 'th, .kpi .k, .panel-title, .lineage b, .legend span:not(.readout), .seg button, button.tool, .chip, .nav a, .ctl label, .ctl .mute, .statusbar span, .topbar button, .cmd, .lg-badge, .symlink, #dev td .chip, #dev td .num, #pf-tab td .chip, #qa-sec td .chip, #fn-tab td .chip, #rk-corr td, #sy-title, #sy-q, #sy-info td:first-child';
  const norm = t => t.replace(/\s+/g, ' ').trim().replace(/[\s%٪:.]+$/, '').replace(/(\D)\d+$/, '$1').trim();
  const E = {}; for (const k in G.E) E[norm(k)] = G.E[k];                 // کلیدهای واژه‌نامه هم یکسان‌سازی شوند
  const viewOf = el => { const m = el.closest('main.workspace'); return m ? m.id.replace(/^v-/, '') : ''; };

  function lookup(el) {
    if (el.dataset.tip) return { d: el.dataset.tip };
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

  function show(el) {
    const r = lookup(el); if (!r) return;
    tip.innerHTML = `${r.t ? `<div class="tt">${esc(r.t)}</div>` : ''}<div class="td">${esc(r.d)}</div>${r.f ? `<div class="tf">${esc(r.f)}</div>` : ''}${r.s ? `<div class="ts">${esc(r.s)}</div>` : ''}`;
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
    const el = target(e); if (el === cur) return;
    hide(); if (!el || e.pointerType === 'touch') return;
    cur = el; timer = setTimeout(() => show(el), 280);
  });
  document.addEventListener('pointerout', e => { if (cur && !cur.contains(e.relatedTarget)) hide(); });
  document.addEventListener('focusin', e => { const el = target(e); hide(); if (el) { cur = el; show(el); } });
  document.addEventListener('focusout', hide);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') hide(); });
  addEventListener('scroll', hide, true);
  /* لمس: نگه‌داشتن انگشت (۵۰۰ میلی‌ثانیه) راهنما را نشان می‌دهد */
  let lp = 0;
  document.addEventListener('touchstart', e => { const el = target(e); clearTimeout(lp); if (el) lp = setTimeout(() => { cur = el; show(el); }, 500); }, { passive: true });
  document.addEventListener('touchend', () => clearTimeout(lp), { passive: true });

  scan();
  window.SIM_TIPS = { scan, lookup };
})();
