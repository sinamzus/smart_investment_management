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
  if (window.SIM_DOCS) return cb();
  if (pend) return pend.push(cb);
  pend = [cb];
  const s = document.createElement('script'); s.src = 'data/docs.js';
  s.onload = () => { const q = pend; pend = null; q.forEach(f => f()); };
  s.onerror = () => { pend = null; toastSafe('سند پیدا نشد: python tools/build_ui_docs.py'); };
  document.head.appendChild(s);
}
const toastSafe = m => (window.toast ? window.toast(m) : console.warn(m));

/* ── مارک‌داون کمینه: سرتیتر، پاراگراف، فهرست، جدول، کد، نقل‌قول، خط، پررنگ/مورب/کد/پیوند درون‌خطی ── */
const slug = t => t.toLowerCase().replace(/[`*_~«»"'()\[\]{}:;،؛,.!?؟/\\|<>=+٫]/g, '').trim().replace(/\s+/g, '-');
function inline(s) {
  const codes = [];
  s = s.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  s = esc(s)
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?!\w)/g, '$1<i>$2</i>')
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, t, h) => `<a class="dlink" data-href="${esc(h)}">${t}</a>`);
  return s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${esc(codes[+i])}</code>`);
}
function md2html(md) {
  const L = md.replace(/\r/g, '').split('\n'), out = [], heads = [];
  let i = 0;
  const isTableSep = l => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l);
  const cells = l => l.trim().replace(/^\|/, '').replace(/\|$/, '').split(/(?<!\\)\|/).map(c => c.trim().replace(/\\\|/g, '|'));
  while (i < L.length) {
    const l = L[i];
    if (/^```/.test(l)) { const buf = []; i++; while (i < L.length && !/^```/.test(L[i])) buf.push(L[i++]); i++; out.push(`<pre dir="ltr"><code>${esc(buf.join('\n'))}</code></pre>`); continue; }
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
    while (i < L.length && L[i].trim() && !/^(#{1,6}\s|```|\s*>|\s*([-*+]|\d+[.)])\s+|\s*(-{3,}|\*{3,})\s*$)/.test(L[i]) && !(/^\s*\|/.test(L[i]) && i + 1 < L.length && isTableSep(L[i + 1]))) buf.push(L[i++]);
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
function build() {
  box = document.createElement('aside'); box.id = 'docv'; box.hidden = true; box.setAttribute('aria-label', 'سند پروژه');
  box.innerHTML = `<div class="dv-head"><button class="tool" id="dv-back" title="بازگشت به جای قبلی" aria-label="بازگشت">→</button>
    <select id="dv-ch" aria-label="فصل"></select><select id="dv-toc" aria-label="بخش"></select><span class="spacer"></span>
    <span class="dv-src mute" id="dv-src"></span><button class="tool" id="dv-x" aria-label="بستن">×</button></div><div class="dv-body" id="dv-body"></div>`;
  document.body.appendChild(box);
  box.querySelector('#dv-x').onclick = close;
  box.querySelector('#dv-back').onclick = () => { const h = hist.pop(); if (h) show(h, true); };
  box.querySelector('#dv-ch').onchange = e => go({ ch: isNaN(+e.target.value) ? e.target.value : +e.target.value });
  box.querySelector('#dv-toc').onchange = e => { const el = box.querySelector('#' + e.target.value); if (el) flash(el); };
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
function flash(el) {
  el.scrollIntoView({ block: 'start' });
  box.querySelectorAll('.dv-hit').forEach(x => x.classList.remove('dv-hit'));
  el.classList.add('dv-hit');
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
    box.querySelector('#dv-toc').innerHTML = d.heads.filter(h => h.lv >= 2 && h.lv <= 4).map(h => `<option value="${h.id}">${'  '.repeat(h.lv - 2)}${esc(h.txt.replace(/`/g, '').slice(0, 90))}</option>`).join('');
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
