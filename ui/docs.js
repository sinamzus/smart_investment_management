/* همتا — راهنمای فنی درون‌برنامه: سند پروژه (docs/*.md) در کشوی کناری، دقیقاً روی بخش مربوط
   داده: ui/data/docs.js (tools/build_ui_docs.py)؛ فقط بار اولی که راهنما باز شود بار می‌شود.
   نشانی بخش (data-doc): «شمارهٔ فصل:شمارهٔ بخش/کلیدواژه»، مثلاً "3:3.5/همتاساز" یا "14:14.7.8"؛ هر جزء اختیاری است.
   سه راه ورود: (۱) دکمهٔ «؟ راهنما» در سر هر پنل؛ (۲) هر «فصل N §x» در متن صفحه پیوند می‌شود؛ (۳) پیوند «سند» در راهنمای شناور (یا کلید F1).
   ارجاع دکمهٔ پنل به ترتیب: data-doc عنوان پنل، نخستین «فصل N §x» درون پنل، پیش‌فرض نما (VIEW_DOC). */
(function () {
'use strict';
const FA = '۰۱۲۳۴۵۶۷۸۹', toEn = s => String(s).replace(/[۰-۹]/g, d => FA.indexOf(d)).replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
const toFa = s => String(s).replace(/\d/g, d => FA[d]);
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const normSec = s => toEn(s || '').replace(/[٫,]/g, '.').replace(/\.+$/, '');

/* پیش‌فرض هر نما وقتی پنل ارجاع خودش را ندارد */
const VIEW_DOC = {
  lab: '14:14.5', sig: '14:14.3', index: '3:3.4', sam: '3:3.5/نمونهٔ کوچک و وام', div: '3:3.5/تأخیر سود', reb: '3:3.5/ریبالانس، گردش', risk: '7:7.3',
  plan: '5:5.8', live: '14:14.9', port: '5:5.9', bsk: '5:5.9/سبد', pf: '3:3.5/ETF در ایران', fnd: '3:3.5/سنجش ردیابی صندوق', qa: '2:2.8', sym: '2:2.4', rep: 'readme',
};

/* «فصل ۳ §۳٫۵»، «فصل ۱۴ §۱۴٫۷٫۸»، «فصل ۰۲» → [{ch, sec, label, i, len}] */
const RE_REF = /فصل\s*([۰-۹0-9]{1,2})(?![۰-۹0-9])(?:\s*§\s*([۰-۹0-9]{1,2}(?:[٫.][۰-۹0-9]+)*))?/g;
function refs(text) {
  const out = []; if (!text) return out; let m; RE_REF.lastIndex = 0;
  while ((m = RE_REF.exec(text))) out.push({ ch: +toEn(m[1]), sec: m[2] ? normSec(m[2]) : null, label: m[0], i: m.index, len: m[0].length });
  return out;
}
const refStr = r => `${r.ch}${r.sec ? ':' + r.sec : ''}${r.kw ? '/' + r.kw : ''}`;
function parse(ref) {
  if (!ref) return null; if (typeof ref === 'object') return ref;
  const [a, kw] = String(ref).split('/'), [ch, sec] = a.split(':');
  return { ch: /^\d+$/.test(toEn(ch)) ? +toEn(ch) : ch, sec: sec ? normSec(sec) : null, kw: kw || null };
}
function labelOf(ref) {
  const r = parse(ref); if (!r) return '';
  if (r.ch === 'readme') return 'راهنمای سند'; if (r.ch === 'changelog') return 'تاریخچهٔ تغییرات';
  return `فصل ${toFa(r.ch)}${r.sec ? ' §' + toFa(r.sec).replace(/\./g, '٫') : ''}${r.kw ? ' · ' + r.kw : ''}`;
}

/* ── بارگذاری دادهٔ سند ── */
let pend = null;
function ensure(cb) {
  loadKatex();
  if (window.SIM_DOCS) return cb();
  if (pend) return pend.push(cb);
  pend = [cb];
  const s = document.createElement('script'); s.src = 'data/docs.js';
  s.onload = () => { const q = pend; pend = null; q.forEach(f => f()); };
  s.onerror = () => { pend = null; toastSafe('سند پیدا نشد: python tools/build_ui_docs.py'); };
  document.head.appendChild(s);
}
// KaTeX (ui/vendor/katex، بدون اینترنت) فقط با نخستین باز شدن سند بار می‌شود؛ تا آماده شود فرمول به‌صورت متن TeX دیده می‌شود
let katexState = 0;
function loadKatex() {
  if (katexState) return; katexState = 1;
  const c = document.createElement('link'); c.rel = 'stylesheet'; c.href = 'vendor/katex/katex.min.css'; document.head.appendChild(c);
  const s = document.createElement('script'); s.src = 'vendor/katex/katex.min.js';
  s.onload = () => { katexState = 2; if (box) typeset(box.querySelector('#dv-body')); };
  s.onerror = () => { katexState = 3; };
  document.head.appendChild(s);
}
function typeset(root) {
  if (!root || !window.katex) return;
  const warn = console.warn; console.warn = (...a) => { if (!/No character metrics/.test(String(a[0]))) warn(...a); };   // حروف فارسی درون \text{}
  root.querySelectorAll('[data-tex]:not([data-done])').forEach(el => {
    const tex = el.dataset.tex, disp = el.classList.contains('dv-math');
    try { window.katex.render(tex, el, { displayMode: disp, throwOnError: false, strict: 'ignore', output: 'htmlAndMathml' }); }
    catch (e) { el.textContent = tex; el.classList.add('bad'); }
    el.dataset.done = '1'; el.title = 'TeX: ' + tex;
  });
  console.warn = warn;
}
const toastSafe = m => (window.toast ? window.toast(m) : console.warn(m));

/* ── مارک‌داون کمینه: سرتیتر، پاراگراف، فهرست، جدول، کد، نقل‌قول، خط، پررنگ/مورب/کد/پیوند درون‌خطی ── */
const slug = t => t.toLowerCase().replace(/[`*_~«»"'()\[\]{}:;،؛,.!?؟/\\|<>=+٫]/g, '').trim().replace(/\s+/g, '-');
// فرمول: $…$ درون‌خطی و $$…$$ نمایشی (LaTeX؛ با KaTeX در ui/vendor/katex رندر می‌شود، فصل ۱۳)
const mathEl = (tex, disp) => `<${disp ? 'div' : 'span'} class="${disp ? 'dv-math' : 'dv-m'}" data-tex="${esc(tex)}" dir="ltr">${esc(tex)}</${disp ? 'div' : 'span'}>`;
// برچسب‌های قرارداد سند ([تأیید لازم]، [راستی‌آزمایی نشده]، [برآورد]، …) نشان رنگی می‌شوند
const RE_FLAG = /\[([^\]]*(?:تأیید لازم|راستی‌آزمایی نشده|برآورد|اندازه‌گیری نشده|بررسی نشده)[^\]]*)\](?!\()/g;
function inline(s) {
  const keep = [];
  const hold = h => { keep.push(h); return `\u0000${keep.length - 1}\u0000`; };
  s = s.replace(/`([^`]+)`/g, (_, c) => hold(`<code dir="ltr">${esc(c)}</code>`))
    .replace(/\$([^$\n]+?)\$/g, (_, t) => hold(mathEl(t.trim(), false)));
  s = esc(s)
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?!\w)/g, '$1<i>$2</i>')
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, t, h) => `<a class="dlink" data-href="${esc(h)}">${t}</a>`)
    .replace(RE_FLAG, (_, t) => `<span class="dv-flag${/تأیید لازم/.test(t) ? ' req' : ''}">${t}</span>`);
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => keep[+i]);
}
function md2html(md) {
  const L = md.replace(/\r/g, '').split('\n'), out = [], heads = [];
  let i = 0;
  const isTableSep = l => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l);
  const cells = l => l.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map(c => c.trim().replace(/\\\|/g, '|'));
  while (i < L.length) {
    const l = L[i];
    if (/^```/.test(l)) { const buf = []; i++; while (i < L.length && !/^```/.test(L[i])) buf.push(L[i++]); i++; out.push(`<pre dir="ltr"><code>${esc(buf.join('\n'))}</code></pre>`); continue; }
    if (/^\s*\$\$/.test(l)) {                         // فرمول نمایشی: از $$ تا $$ (یک یا چند خط)
      let t = l.trim().slice(2); i++;
      while (!/\$\$\s*$/.test(t) && i < L.length) t += '\n' + L[i++];
      out.push(mathEl(t.replace(/\$\$\s*$/, '').trim(), true)); continue;
    }
    const h = /^(#{1,6})\s+(.*)$/.exec(l);
    if (h) { const lv = h[1].length, txt = h[2].trim(), id = 'd-' + heads.length; heads.push({ id, lv, txt, norm: toEn(txt).replace(/[٫]/g, '.'), slug: slug(txt) }); out.push(`<h${lv} id="${id}">${inline(txt)}</h${lv}>`); i++; continue; }
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(l)) { out.push('<hr>'); i++; continue; }
    if (/^\s*\|/.test(l) && i + 1 < L.length && isTableSep(L[i + 1])) {
      const hd = cells(l); i += 2; const rows = [];
      while (i < L.length && /^\s*\|/.test(L[i])) rows.push(cells(L[i++]));
      out.push(`<div class="dtbl"><table><thead><tr>${hd.map(c => `<th>${inline(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
      continue;
    }
    if (/^\s*>/.test(l)) { const buf = []; while (i < L.length && /^\s*>/.test(L[i])) buf.push(L[i++].replace(/^\s*>\s?/, '')); out.push(`<blockquote>${inline(buf.join(' '))}</blockquote>`); continue; }
    if (/^\s*([-*+]|\d+[.)])\s+/.test(l)) {
      const ord = /^\s*\d+[.)]/.test(l), items = [];
      while (i < L.length && (/^\s*([-*+]|\d+[.)])\s+/.test(L[i]) || (/^\s{2,}\S/.test(L[i]) && items.length))) {
        const m = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/.exec(L[i]);
        if (m) items.push({ d: m[1].length >= 2 ? 1 : 0, t: m[3] }); else items[items.length - 1].t += ' ' + L[i].trim();
        i++;
      }
      out.push(`<${ord ? 'ol' : 'ul'}>${items.map(x => `<li${x.d ? ' class="sub"' : ''}>${inline(x.t)}</li>`).join('')}</${ord ? 'ol' : 'ul'}>`);
      continue;
    }
    if (!l.trim()) { i++; continue; }
    const buf = [];
    while (i < L.length && L[i].trim() && !/^(#{1,6}\s|```|\s*\$\$|\s*>|\s*([-*+]|\d+[.)])\s+|\s*(-{3,}|\*{3,})\s*$)/.test(L[i]) && !(/^\s*\|/.test(L[i]) && i + 1 < L.length && isTableSep(L[i + 1]))) buf.push(L[i++]);
    out.push(`<p>${inline(buf.join(' '))}</p>`);
  }
  return { html: out.join('\n'), heads };
}

/* ── یافتن بخش ── */
function findDoc(ch) { const F = window.SIM_DOCS.files; return F.find(f => f.n === ch) || F.find(f => String(f.n) === String(ch)) || null; }
function target(heads, root, r) {
  let from = 0, end = heads.length, hit = null;
  if (r.sec) {
    const k = heads.findIndex(h => h.norm.startsWith(r.sec + ' ') || h.norm === r.sec);
    if (k >= 0) { hit = heads[k]; from = k; end = heads.findIndex((h, j) => j > k && h.lv <= heads[k].lv); if (end < 0) end = heads.length; }
  }
  if (r.kw) {
    const kw = r.kw.replace(/\s+/g, ' ');
    const k = heads.slice(from, end).findIndex(h => h.txt.includes(kw));
    if (k >= 0) return { el: root.querySelector('#' + heads[from + k].id) };
    for (const el of root.querySelectorAll('p, li, td, blockquote')) if (el.textContent.includes(kw)) return { el, inner: true };
  }
  return hit ? { el: root.querySelector('#' + hit.id) } : null;
}

/* ── کشوی سند ── */
let box = null, cache = new Map(), curCh = null, hist = [];
// ترجیح‌های خواندن (فقط همین مرورگر؛ بدون آن هم کار می‌کند)
const pref = { get: (k, d) => { try { const v = localStorage.getItem('sim.docv.' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
  set: (k, v) => { try { localStorage.setItem('sim.docv.' + k, JSON.stringify(v)); } catch (e) { /* بدون ذخیره */ } } };
function build() {
  box = document.createElement('aside'); box.id = 'docv'; box.hidden = true; box.setAttribute('aria-label', 'سند پروژه');
  box.innerHTML = `<div class="dv-head"><button class="tool" id="dv-back" title="بازگشت به جای قبلی" aria-label="بازگشت">→</button>
    <select id="dv-ch" aria-label="فصل"></select><select id="dv-toc" aria-label="بخش"></select>
    <span class="dv-find"><input id="dv-q" type="search" placeholder="جست‌وجو در فصل" aria-label="جست‌وجو در فصل"><span class="mute" id="dv-qn"></span></span>
    <span class="spacer"></span>
    <button class="tool" id="dv-fsm" title="متن کوچک‌تر" aria-label="متن کوچک‌تر">−</button><button class="tool" id="dv-fsp" title="متن بزرگ‌تر" aria-label="متن بزرگ‌تر">+</button>
    <button class="tool" id="dv-wide" title="حالت خواندن: تمام‌صفحه با فهرست بخش‌ها" aria-label="حالت خواندن">⤢</button>
    <span class="dv-src mute" id="dv-src"></span><button class="tool" id="dv-x" aria-label="بستن">×</button></div>
    <div class="dv-main"><nav class="dv-nav" id="dv-nav" aria-label="فهرست بخش‌ها"></nav><div class="dv-body" id="dv-body"></div></div>`;
  document.body.appendChild(box);
  const body = box.querySelector('#dv-body');
  const applyPref = () => { box.classList.toggle('wide', !!pref.get('wide', false)); body.style.fontSize = (pref.get('fs', 1) * 100).toFixed(0) + '%'; };
  applyPref();
  box.querySelector('#dv-x').onclick = close;
  box.querySelector('#dv-back').onclick = () => { const h = hist.pop(); if (h) show(h, true); };
  box.querySelector('#dv-ch').onchange = e => go({ ch: isNaN(+e.target.value) ? e.target.value : +e.target.value });
  box.querySelector('#dv-toc').onchange = e => { const el = box.querySelector('#' + e.target.value); if (el) flash(el); };
  box.querySelector('#dv-wide').onclick = () => { pref.set('wide', !pref.get('wide', false)); applyPref(); };
  box.querySelector('#dv-fsm').onclick = () => { pref.set('fs', Math.max(0.8, +(pref.get('fs', 1) - 0.1).toFixed(1))); applyPref(); };
  box.querySelector('#dv-fsp').onclick = () => { pref.set('fs', Math.min(1.6, +(pref.get('fs', 1) + 0.1).toFixed(1))); applyPref(); };
  box.querySelector('#dv-nav').addEventListener('click', e => { const a = e.target.closest('a[data-id]'); if (!a) return; e.preventDefault(); const el = box.querySelector('#' + a.dataset.id); if (el) flash(el); });
  // بخش جاری در فهرست و انتخاب‌گر (هنگام پیمایش)
  let raf = 0;
  body.addEventListener('scroll', () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; spy(); }); });
  // جست‌وجو: Enter = مورد بعد، Shift+Enter = قبلی
  const q = box.querySelector('#dv-q');
  q.addEventListener('input', () => find(q.value, 0));
  q.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); find(q.value, e.shiftKey ? -1 : 1); } });
  body.addEventListener('click', e => { const m = e.target.closest('.dv-math'); if (m && m.dataset.tex && e.altKey) { navigator.clipboard && navigator.clipboard.writeText(m.dataset.tex); toastSafe('TeX کپی شد'); } });
  box.querySelector('#dv-body').addEventListener('click', e => {
    const a = e.target.closest('a.dlink'); if (!a) return;
    const h = a.dataset.href, m = /^(?:\.\/)?(?:docs\/)?(\d\d)-[^#]*\.md(?:#(.*))?$/.exec(h) || /^#(.*)$/.exec(h);
    if (m && m.length === 3) { go({ ch: +m[1], slug: m[2] ? decodeURIComponent(m[2]) : null }); e.preventDefault(); }
    else if (m) { const s = decodeURIComponent(m[1]), d = cache.get(curCh), x = d && d.heads.find(q => q.slug === s); if (x) flash(box.querySelector('#' + x.id)); }
    else if (/^https?:/.test(h)) window.open(h, '_blank', 'noopener');
    else if (/CHANGELOG\.md$/.test(h)) go({ ch: 'changelog' });
    else if (/README\.md$/.test(h)) go({ ch: 'readme' });
  });
}
function close() { if (box) box.hidden = true; document.body.classList.remove('docv-open'); }
function spy() {
  const body = box.querySelector('#dv-body'), d = cache.get(curCh); if (!d) return;
  const top = body.getBoundingClientRect().top + 24; let cur = null;
  for (const h of d.heads) { if (h.lv < 2 || h.lv > 4) continue; const el = body.querySelector('#' + h.id); if (!el) continue; if (el.getBoundingClientRect().top <= top) cur = h; else break; }
  box.querySelectorAll('#dv-nav a.on').forEach(a => a.classList.remove('on'));
  if (!cur) return;
  const a = box.querySelector(`#dv-nav a[data-id="${cur.id}"]`);
  if (a) { a.classList.add('on'); const nav = box.querySelector('#dv-nav'), r = a.getBoundingClientRect(), n = nav.getBoundingClientRect(); if (r.top < n.top || r.bottom > n.bottom) a.scrollIntoView({ block: 'nearest' }); }
  const toc = box.querySelector('#dv-toc'); if (toc.querySelector(`option[value="${cur.id}"]`)) toc.value = cur.id;
}
let hits = [], hitAt = -1;
function find(q, step) {
  const body = box.querySelector('#dv-body'), qn = box.querySelector('#dv-qn');
  if (!step) {
    body.querySelectorAll('mark.dv-q').forEach(m => m.replaceWith(document.createTextNode(m.textContent)));
    body.normalize(); hits = []; hitAt = -1;
    q = (q || '').trim(); if (q.length < 2) { qn.textContent = ''; return; }
    const w = document.createTreeWalker(body, NodeFilter.SHOW_TEXT, { acceptNode: n => n.parentElement.closest('.katex, .dv-m, .dv-math') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
    const nodes = []; let n; while ((n = w.nextNode())) nodes.push(n);
    for (const t of nodes) {
      let s = t.data, at = s.indexOf(q), node = t;
      while (at >= 0) { const rest = node.splitText(at); node = rest.splitText(q.length); const m = document.createElement('mark'); m.className = 'dv-q'; rest.replaceWith(m); m.textContent = q; hits.push(m); s = node.data; at = s.indexOf(q); }
    }
    step = 1;
  }
  if (!hits.length) { qn.textContent = (q || '').trim().length >= 2 ? '۰' : ''; return; }
  hits.forEach(m => m.classList.remove('on'));
  hitAt = (hitAt + step + hits.length) % hits.length;
  hits[hitAt].classList.add('on'); hits[hitAt].scrollIntoView({ block: 'center' });
  qn.textContent = toFa(`${hitAt + 1}/${hits.length}`);
}
function flash(el) {
  el.scrollIntoView({ block: 'start' });
  box.querySelectorAll('.dv-hit').forEach(x => x.classList.remove('dv-hit'));
  el.classList.add('dv-hit');
  box.querySelectorAll('.dv-tgt').forEach(x => x.classList.remove('dv-tgt')); el.classList.add('dv-tgt');
  // سرتیتر هدف تا سرتیتر هم‌سطح بعدی برجسته می‌شود تا روشن باشد کدام بند مربوط است
  if (/^H[1-6]$/.test(el.tagName)) { const lv = +el.tagName[1]; let n = el.nextElementSibling; while (n && !(/^H[1-6]$/.test(n.tagName) && +n.tagName[1] <= lv)) { n.classList.add('dv-hit'); n = n.nextElementSibling; } }
  const toc = box.querySelector('#dv-toc'); if (el.id && toc.querySelector(`option[value="${el.id}"]`)) toc.value = el.id;
}
function go(r) { if (curCh != null && !box.hidden) hist.push({ ch: curCh, top: box.querySelector('#dv-body').scrollTop }); show(r); }
function show(r, back) {
  const doc = findDoc(r.ch); if (!doc) { toastSafe('این فصل در سند نیست: ' + labelOf(r)); return; }
  if (!cache.has(doc.n)) cache.set(doc.n, md2html(doc.md));
  const d = cache.get(doc.n), body = box.querySelector('#dv-body');
  if (curCh !== doc.n) {
    body.innerHTML = d.html; curCh = doc.n;
    const hs = d.heads.filter(h => h.lv >= 2 && h.lv <= 4), plain = t => t.replace(/`|\*\*|\$/g, '');
    box.querySelector('#dv-toc').innerHTML = hs.map(h => `<option value="${h.id}">${'  '.repeat(h.lv - 2)}${esc(plain(h.txt).slice(0, 90))}</option>`).join('');
    const h1 = d.heads.find(h => h.lv === 1);
    box.querySelector('#dv-nav').innerHTML = (h1 ? `<div class="dv-nav-t">${esc(plain(h1.txt))}</div>` : '') + hs.map(h => `<a href="#" data-id="${h.id}" class="l${h.lv}">${esc(plain(h.txt))}</a>`).join('');
    const q = box.querySelector('#dv-q'); q.value = ''; box.querySelector('#dv-qn').textContent = ''; hits = []; hitAt = -1;
    typeset(body);
  }
  box.querySelector('#dv-ch').value = String(doc.n);
  box.querySelector('#dv-src').textContent = 'docs/' + doc.file;
  box.querySelector('#dv-back').disabled = !hist.length;
  box.hidden = false; document.body.classList.add('docv-open');
  if (back) { body.scrollTop = r.top || 0; return; }
  let t = null;
  if (r.slug) { const x = d.heads.find(q => q.slug === r.slug); if (x) t = { el: body.querySelector('#' + x.id) }; }
  if (!t) t = target(d.heads, body, r);
  if (t && t.el) flash(t.el); else { body.scrollTop = 0; body.querySelectorAll('.dv-hit').forEach(x => x.classList.remove('dv-hit')); if (r.sec || r.kw) toastSafe('بخش دقیق پیدا نشد؛ ابتدای ' + labelOf({ ch: r.ch }) + ' باز شد'); }
}
function open(ref) {
  const r = parse(ref); if (!r) return;
  ensure(() => {
    if (!box) build();
    const sel = box.querySelector('#dv-ch');
    if (!sel.options.length) sel.innerHTML = window.SIM_DOCS.files.map(f => `<option value="${esc(f.n)}">${esc(typeof f.n === 'number' ? toFa(String(f.n).padStart(2, '0')) + ' — ' : '')}${esc(f.title.replace(/^[۰-۹0-9]+\s*—\s*/, ''))}</option>`).join('');
    go(r);
  });
}

/* ── پیوندسازی «فصل N §x» در متن صفحه و دکمهٔ راهنمای پنل‌ها ── */
const SKIP = 'code,pre,textarea,input,select,option,script,style,svg,#docv,#tip,a,button,.doclink';
function linkText(root) {
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: n => (!n.parentElement || n.parentElement.closest(SKIP)) ? NodeFilter.FILTER_REJECT : (/فصل/.test(n.data) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP) });
  const todo = []; let n; while ((n = w.nextNode())) todo.push(n);
  for (const t of todo) {
    const rs = refs(t.data); if (!rs.length) continue;
    const frag = document.createDocumentFragment(); let p = 0;
    for (const r of rs) {
      if (r.i > p) frag.appendChild(document.createTextNode(t.data.slice(p, r.i)));
      const a = document.createElement('a'); a.className = 'doclink'; a.dataset.doc = refStr(r); a.textContent = r.label; a.dataset.tip = 'این بخش از سند پروژه را کنار صفحه باز می‌کند.';
      frag.appendChild(a); p = r.i + r.len;
    }
    if (p < t.data.length) frag.appendChild(document.createTextNode(t.data.slice(p)));
    t.parentNode.replaceChild(frag, t);
  }
}
const viewOf = el => { const m = el.closest('main.workspace'); return m ? m.id.replace(/^v-/, '') : ''; };
function panelRef(head) {
  const pt = head.querySelector('[data-doc]'); if (pt) return pt.dataset.doc;
  const panel = head.closest('.panel, details.sam-fold') || head.parentElement;
  const a = panel && panel.querySelector('.doclink'); if (a) return a.dataset.doc;
  const r = panel && refs(panel.textContent)[0]; if (r) return refStr(r);
  return VIEW_DOC[viewOf(head)] || 'readme';
}
function addButtons(root) {
  (root.querySelectorAll ? root : document).querySelectorAll('.panel-head').forEach(h => {
    if (h.querySelector(':scope > .doc-btn, :scope > .panel-tools > .doc-btn') || h.closest('#docv')) return;
    const b = document.createElement('button'); b.className = 'tool doc-btn'; b.type = 'button'; b.textContent = '؟ راهنما';
    b.dataset.tip = 'راهنمای فنی و مالی این بخش: سند پروژه کنار صفحه، دقیقاً روی بند مربوط باز می‌شود (روش محاسبه، فرض‌ها، منابع). کلید F1 روی هر برچسب هم همین کار را برای همان برچسب می‌کند.';
    const tools = h.querySelector(':scope > .panel-tools'); if (tools) tools.appendChild(b); else h.appendChild(b);
  });
}
let tm = 0;
const run = () => { tm = 0; const m = document.querySelector('.app') || document.body; linkText(m); addButtons(m); };
new MutationObserver(ms => { if (ms.every(m => m.target.closest && m.target.closest('#docv,#tip'))) return; if (!tm) tm = setTimeout(run, 60); })
  .observe(document.body, { childList: true, subtree: true, characterData: true });
document.addEventListener('click', e => {
  const a = e.target.closest('.doclink, .doc-btn, #tip .tdoc a'); if (!a) return;
  e.preventDefault(); e.stopPropagation();
  open(a.classList.contains('doc-btn') ? panelRef(a.closest('.panel-head')) : a.dataset.doc);
}, true);
document.addEventListener('keydown', e => { if (e.key === 'Escape' && box && !box.hidden) close(); });
run();

window.SIM_DOCS_API = { open, refs, parse, labelOf, refStr, md2html, VIEW_DOC };
})();
