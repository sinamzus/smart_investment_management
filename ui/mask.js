/* همتا — نام منبع‌های داده در سامانه دیده نمی‌شود (تصمیم مالک ۲۰۲۶-۱۰-۲۱؛ فصل ۱۲): جز کدال، نام هر منبع داده در متن صفحه،
   راهنماهای شناور، دادهٔ ساخته‌شدهٔ صفحه‌ها و سند درون‌برنامه هنگام نمایش با اصطلاح خنثی جایگزین می‌شود.
   سند مخزن (docs/*.md) و کد نام واقعی را برای ردیابی روش نگه می‌دارند؛ این فقط لایهٔ نمایش است.
   متن: SIM_MASK.text(s)؛ کد و خط فرمان: SIM_MASK.code(s)؛ مارک‌داون (کد درون بک‌تیک جدا): SIM_MASK.md(s)؛ DOM: SIM_MASK.dom(root). */
(function () {
'use strict';
// ترتیب مهم است: عبارت‌های بلندتر پیش از کوتاه‌تر
const TEXT = [
  [/RiskFree_Arbitrage/g, 'مخزن جمع‌آوری داده'], [/CLAUDE\.md/g, 'قواعد مخزن'], [/claude\/[\w./-]+/gi, 'main'],
  [/کارگزاری فارابی/g, 'کارگزاری'], [/رونوشت فارابی/g, 'رونوشت کارگزاری'], [/فارابی/g, 'منبع کارگزاری'], [/\bFarabi\b/g, 'broker source'], [/farabi/gi, 'broker'],
  [/رهاورد\s*۳۶۵/g, 'منبع بنیادی'], [/رهاورد/g, 'منبع بنیادی'], [/\bRahavard(365)?\b/g, 'fundamentals source'], [/rahavard(365)?/gi, 'fundsrc'],
  [/فیپیران/g, 'منبع NAV'], [/fipiran/gi, 'navsrc'], [/\bfundai\b/gi, 'منبع دوم'], [/fundai/gi, 'div2'],
  [/\bMarketWatch\b/g, 'دیده‌بان بازار'], [/\bTSETMC\b/g, 'بورس'], [/tsetmc/gi, 'market'], [/سمات/g, 'شرکت سپرده‌گذاری'],
];
// درون کد، مسیر فایل و خط فرمان: جایگزین لاتین تا نام فایل نیمه‌فارسی نشود
const CODE = [
  [/RiskFree_Arbitrage/g, 'collector'], [/CLAUDE\.md/g, 'RULES.md'], [/claude\/[\w./-]+/gi, 'main'],
  [/farabi/gi, 'broker'], [/rahavard(365)?/gi, 'fundsrc'], [/fipiran/gi, 'navsrc'], [/fundai/gi, 'div2'],
  [/MarketWatch/g, 'market_watch'], [/TSETMC/g, 'MARKET'], [/tsetmc/g, 'market'],
  [/فارابی/g, 'broker'], [/رهاورد/g, 'fundsrc'], [/فیپیران/g, 'navsrc'],
];
const ANY = /RiskFree|CLAUDE|claude\/|فارابی|farabi|Farabi|رهاورد|rahavard|Rahavard|فیپیران|fipiran|fundai|MarketWatch|TSETMC|tsetmc|سمات/i;
const run = (s, T) => { let x = String(s); for (const [re, to] of T) x = x.replace(re, to); return x; };
const text = s => (s && ANY.test(s) ? run(s, TEXT) : s);
const code = s => (s && ANY.test(s) ? run(s, CODE) : s);
// مارک‌داون: بک‌تیک‌ها و بلوک‌های کد با جایگزین لاتین، بقیه با متنی
function md(s) {
  if (!s || !ANY.test(s)) return s;
  return s.split(/(```[\s\S]*?```|`[^`\n]*`)/g).map((p, i) => (i % 2 ? code(p) : text(p))).join('');
}
const SKIP = 'script,style,textarea,input';
const CODEY = 'code,pre,.cmdline,kbd';
function dom(root) {
  if (!root) return;
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: n => (n.parentElement && !n.parentElement.closest(SKIP) && ANY.test(n.data)) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT });
  const todo = []; let n; while ((n = w.nextNode())) todo.push(n);
  for (const t of todo) t.data = t.parentElement.closest(CODEY) ? code(t.data) : text(t.data);
  (root.querySelectorAll ? root : document).querySelectorAll('[data-tip],[title],[placeholder],[aria-label]').forEach(el => {
    for (const a of ['data-tip', 'title', 'placeholder', 'aria-label']) { const v = el.getAttribute(a); if (v && ANY.test(v)) el.setAttribute(a, text(v)); }
  });
}
window.SIM_MASK = { text, code, md, dom, ANY };
})();
