// بررسی فرمول‌های LaTeX سند (docs/*.md) با همان KaTeX رابط (ui/vendor/katex): هر $…$ و $$…$$ باید بی‌خطا رندر شود.
//   node tools/docs_math_check.js
const fs = require('fs'), path = require('path');
const katex = require(path.join(__dirname, '..', 'ui', 'vendor', 'katex', 'katex.min.js'));
const dir = path.join(__dirname, '..', 'docs');
// حروف فارسی درون \text{} متریک فونت KaTeX ندارند؛ با فونت متن نمایش داده می‌شوند و این هشدار خطا نیست
const warn = console.warn; console.warn = (...a) => { if (!/No character metrics/.test(String(a[0]))) warn(...a); };
let n = 0, bad = 0;
for (const f of fs.readdirSync(dir).filter(x => x.endsWith('.md')).sort()) {
  const L = fs.readFileSync(path.join(dir, f), 'utf8').replace(/\r/g, '').split('\n');
  const check = (tex, disp, line) => {
    n++;
    try { katex.renderToString(tex, { displayMode: disp, throwOnError: true, strict: 'ignore' }); }
    catch (e) { bad++; console.log(`${f}:${line}: ${e.message.split('\n')[0]}\n    ${tex.slice(0, 160)}`); }
  };
  let inCode = false;
  for (let i = 0; i < L.length; i++) {
    const l = L[i];
    if (/^```/.test(l)) { inCode = !inCode; continue; }
    if (inCode) continue;
    if (/^\s*\$\$/.test(l)) {                      // همان قاعدهٔ ui/docs.js
      const at = i + 1; let t = l.trim().slice(2);
      while (!/\$\$\s*$/.test(t) && i + 1 < L.length) t += '\n' + L[++i];
      check(t.replace(/\$\$\s*$/, '').trim(), true, at); continue;
    }
    const s = l.replace(/`[^`]+`/g, ' ');
    for (const m of s.matchAll(/\$([^$\n]+?)\$/g)) check(m[1].trim(), false, i + 1);
  }
}
console.log(`فرمول‌ها: ${n}؛ خطا: ${bad}`);
process.exit(bad ? 1 : 0);
