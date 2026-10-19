/* همتا — تاریخ شمسی در همهٔ صفحه
   دادهٔ رابط (ui/data/*.js) تاریخ‌ها را میلادی ISO (YYYY-MM-DD) نگه می‌دارد تا محاسبه، مرتب‌سازی و خروجی CSV/JSON ماشینی بماند؛
   این ماژول هر تاریخ میلادی را که در متن صفحه یا راهنمای شناور (data-tip، title) ظاهر شود به شمسی (YYYY/MM/DD) برمی‌گرداند:
   - رقم لاتین: 2026-10-18 → 1405/07/26 (ساعت اختیاری بعدش دست نمی‌خورد)
   - رقم فارسی: ۲۰۲۶-۱۰-۱۸ → ۱۴۰۵/۰۷/۲۶
   نام فایل‌ها (orders_2026-10-18_interim) و متن <code>/<input>/<textarea> عوض نمی‌شوند. با MutationObserver، هر محتوای تازه هم تبدیل می‌شود. */
(function () {
  const F = new Intl.DateTimeFormat('fa-IR-u-ca-persian-nu-latn', { year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'UTC' });
  const FA = '۰۱۲۳۴۵۶۷۸۹', toFa = s => s.replace(/\d/g, d => FA[d]), fromFa = s => s.replace(/[۰-۹]/g, d => String(FA.indexOf(d)));
  function j(y, m, d) {
    const t = Date.UTC(+y, +m - 1, +d), x = new Date(t);
    if (isNaN(t) || x.getUTCMonth() !== +m - 1) return null;                 // تاریخ نامعتبر را دست نزن
    return F.format(x).replace(/[‎‏]/g, '');
  }
  const RE_L = /(^|[^\w\/_.-])((?:19|20)\d\d)-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?![\w_.]|-\d)/g;
  const RE_P = /(^|[^۰-۹\w\/_.-])([۱][۹][۰-۹]{2}|[۲][۰][۰-۹]{2})-([۰-۹]{2})-([۰-۹]{2})(?![۰-۹\w_.]|-[۰-۹])/g;
  const TEST = /(?:19|20)\d\d-\d\d-\d\d|[۱۲][۹۰][۰-۹]{2}-[۰-۹]{2}-[۰-۹]{2}/;
  function fix(s) {
    if (!s || !TEST.test(s)) return s;
    return s.replace(RE_L, (m0, pre, y, mo, d) => { const r = j(y, mo, d); return r ? pre + r : m0; })
            .replace(RE_P, (m0, pre, y, mo, d) => { const r = j(fromFa(y), fromFa(mo), fromFa(d)); return r ? pre + toFa(r) : m0; });
  }
  const SKIP = new Set(['SCRIPT', 'STYLE', 'CODE', 'TEXTAREA', 'INPUT', 'PRE']);
  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) { if (!SKIP.has(root.parentNode && root.parentNode.nodeName)) { const v = fix(root.data); if (v !== root.data) root.data = v; } return; }
    if (root.nodeType !== 1 || SKIP.has(root.nodeName)) return;
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: n => (n.parentNode && SKIP.has(n.parentNode.nodeName) || n.parentNode.closest && n.parentNode.closest('code,pre,textarea')) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT });
    let n; while ((n = w.nextNode())) { if (TEST.test(n.data)) { const v = fix(n.data); if (v !== n.data) n.data = v; } }
    const els = root.querySelectorAll ? [root, ...root.querySelectorAll('[data-tip],[title]')] : [];
    for (const e of els) {
      if (e.dataset && e.dataset.tip && TEST.test(e.dataset.tip)) e.dataset.tip = fix(e.dataset.tip);
      if (e.title && TEST.test(e.title)) e.title = fix(e.title);
    }
  }
  let pend = new Set(), raf = 0;
  new MutationObserver(ms => {
    for (const m of ms) { if (m.type === 'characterData') pend.add(m.target); else m.addedNodes.forEach(x => pend.add(x)); if (m.type === 'attributes') pend.add(m.target); }
    if (!raf) raf = setTimeout(() => { raf = 0; const s = pend; pend = new Set(); s.forEach(walk); }, 0);   // setTimeout نه rAF: rAF در برگهٔ پنهان اجرا نمی‌شود
  }).observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['data-tip', 'title'] });
  document.title = fix(document.title);
  walk(document.body);
  /* شمسی → میلادی ISO (برای ورودی‌های تاریخ): «1402/01/01» یا «۱۴۰۲/۱/۱» → «2023-03-21»؛ نامعتبر ⇒ null */
  function g(js) {
    const m = /^\s*(\d{4})[\/\-.](\d{1,2})[\/\-.](\d{1,2})\s*$/.exec(fromFa(js || '')); if (!m) return null;
    const [jy, jm, jd] = [+m[1], +m[2], +m[3]]; if (jm < 1 || jm > 12 || jd < 1 || jd > 31) return null;
    const doy = (jm <= 6 ? (jm - 1) * 31 : 186 + (jm - 7) * 30) + jd - 1, base = Date.UTC(jy + 621, 2, 20) + doy * 864e5;
    const want = `${jy}/${String(jm).padStart(2, '0')}/${String(jd).padStart(2, '0')}`;
    for (let k = -3; k <= 3; k++) { const x = new Date(base + k * 864e5); if (F.format(x).replace(/[‎‏]/g, '') === want) return x.toISOString().slice(0, 10); }
    return null;
  }
  window.SIM_JDATE = { fix, g, j: iso => { const m = /^(\d{4})-(\d\d)-(\d\d)/.exec(iso || ''); return m ? j(m[1], m[2], m[3]) : iso; } };
})();
