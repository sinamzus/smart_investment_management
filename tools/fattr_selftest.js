// تفکیک فاکتوری صندوق در مرورگر (ui/fattr.js) = tools/fund_attribution.py (فصل ۷ §۷٫۹)
//   node tools/fattr_selftest.js
// ۱) رگرسیون شش‌فاکتوری و فقط-بازار با نرخ پیش‌فرض (سری هفتگی اخزا rf_w یا نرخ ثابت) همان عددهای پایتون؛ ۲) آخرین بتای غلتان همان؛ ۳) سهم‌ها + آلفا = بازده مازاد؛
// ۴) آزمون مصنوعی: سری ساخته‌شده از بتاهای معلوم را بازمی‌یابد؛ ۵) مدل ۵ فاکتوری بی‌HML همان پایتون.
const path = require('path');
global.window = global;
require(path.join(__dirname, '..', 'ui', 'data', 'fund_attr.js'));
require(path.join(__dirname, '..', 'ui', 'fattr.js'));
const E = global.FAttr, A = global.SIM_FATTR;
// جزئیات هفتگی هر صندوق در ui/data/fattr/<شمارهٔ ثبت>.js
for (const v of Object.values(A.funds)) require(path.join(__dirname, '..', 'ui', 'data', 'fattr', `${v.id}.js`));
let bad = 0;
const ok = (c, m) => { if (!c) { bad++; console.log('خطا:', m); } };
const near = (a, b, tol, m) => ok(Math.abs(a - b) <= tol, `${m}: ${a} ≠ ${b}`);
const codes = A.factors.map(x => x.code);
let n6 = 0;
for (const [sym, S] of Object.entries(A.funds)) {
  const F = Object.assign({}, S, global.SIM_FATTR_D[sym]);
  const r = E.regress(F, F.rf_w || A.rf_ann, codes, A.hac_lags), P = F.result;
  ok(!r === !P, `${sym}: مدل ۶ فاکتوری فقط یک‌طرف`);
  if (r && P) { n6++;
  ok(r.weeks === P.weeks, `${sym}: تعداد هفته`);
  for (const k of ['alpha_ann', 'alpha_t', 'r2', 'resid_vol_ann', 'excess_ann', 'vol_ann', 'dimson_beta']) near(r[k], P[k], 1e-3 * Math.max(1, Math.abs(P[k])), `${sym} ${k}`);
  r.factors.forEach((f, i) => { for (const k of ['beta', 't', 'factor_ann', 'contrib_ann']) near(f[k], P.factors[i][k], 2e-3 * Math.max(1, Math.abs(P.factors[i][k])), `${sym} ${f.code} ${k}`); });
  near(r.alpha_ann + r.factors.reduce((s, f) => s + f.contrib_ann, 0), r.excess_ann, 1e-9, `${sym} جمع سهم‌ها`);
  const m = E.regress(F, F.rf_w || A.rf_ann, ['MKT'], A.hac_lags);
  near(m.r2, F.market_only.r2, 1e-4, `${sym} R² فقط بازار`);
  const R = E.rolling(F, F.rf_w || A.rf_ann, codes, A.hac_lags, A.roll);
  ok(R.end.length === F.rolling.end.length, `${sym}: طول بتای غلتان`);
  if (R.end.length) codes.forEach((c, j) => near(R.beta[j][R.end.length - 1], F.rolling.beta[c][R.end.length - 1], 2e-3, `${sym} بتای غلتان ${c}`));
  }
  // مدل ۵ فاکتوری بدون HML روی کل تاریخچه
  const c5 = codes.filter(c => c !== 'HML'), r5 = E.regress(F, F.rf_w || A.rf_ann, c5, A.hac_lags, 0, F.y.length, c5), P5 = F.result5;
  ok(r5 && r5.weeks === P5.weeks, `${sym}: تعداد هفتهٔ ۵ فاکتوری`);
  for (const k of ['alpha_ann', 'r2', 'dimson_beta']) near(r5[k], P5[k], 1e-3 * Math.max(1, Math.abs(P5[k])), `${sym} ۵ف ${k}`);
  r5.factors.forEach((f, i) => near(f.beta, P5.factors[i].beta, 2e-3, `${sym} ۵ف ${f.code}`));
  near(E.regress(F, F.rf_w || A.rf_ann, ['MKT'], A.hac_lags, 0, F.y.length, c5).r2, F.market_only5.r2, 1e-4, `${sym} R² فقط بازار ۵ف`);
  const R5 = E.rolling(F, F.rf_w || A.rf_ann, c5, A.hac_lags, A.roll);
  ok(R5.end.length === F.rolling5.end.length, `${sym}: طول بتای غلتان ۵ف`);
}
console.log(`${Object.keys(A.funds).length} صندوق (${n6} با مدل ۶ فاکتوری) با پایتون مقایسه شد`);
// ۴) مصنوعی
let seed = 7; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647 - 0.5; };
const n = 300, beta = [0.9, 0.6, -0.3], Fm = { MKT_raw: [], SMB: [], HML: [] }, y = [];
for (let t = 0; t < n; t++) { const m = 0.03 * rnd(), s = 0.02 * rnd(), h = 0.02 * rnd(); Fm.MKT_raw.push(m); Fm.SMB.push(s); Fm.HML.push(h); y.push(0.001 + beta[0] * m + beta[1] * s + beta[2] * h + 0.002 * rnd()); }
const S = E.regress({ y, days: y.map(() => 7), F: Fm, w_end: y.map((_, i) => String(i)) }, 0, ['MKT', 'SMB', 'HML'], 4, 0, n, ['MKT', 'SMB', 'HML']);
S.factors.forEach((f, i) => near(f.beta, beta[i], 0.02, `مصنوعی β ${f.code}`));
near(S.alpha_ann, 5.2, 0.6, 'مصنوعی آلفا');
console.log(bad ? `${bad} خطا` : 'همه درست');
process.exit(bad ? 1 : 0);
