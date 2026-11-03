// تفکیک فاکتوری صندوق در مرورگر (ui/fattr.js) = tools/fund_attribution.py (فصل ۷ §۷٫۹)
//   node tools/fattr_selftest.js
// ۱) رگرسیون شش‌فاکتوری و فقط-بازار با نرخ پیش‌فرض همان عددهای پایتون؛ ۲) آخرین بتای غلتان همان؛ ۳) سهم‌ها + آلفا = بازده مازاد؛
// ۴) آزمون مصنوعی: سری ساخته‌شده از بتاهای معلوم را بازمی‌یابد.
const path = require('path');
global.window = global;
require(path.join(__dirname, '..', 'ui', 'data', 'fund_attr.js'));
require(path.join(__dirname, '..', 'ui', 'fattr.js'));
const E = global.FAttr, A = global.SIM_FATTR;
let bad = 0;
const ok = (c, m) => { if (!c) { bad++; console.log('خطا:', m); } };
const near = (a, b, tol, m) => ok(Math.abs(a - b) <= tol, `${m}: ${a} ≠ ${b}`);
const codes = A.factors.map(x => x.code);
for (const [sym, F] of Object.entries(A.funds)) {
  const r = E.regress(F, A.rf_ann, codes, A.hac_lags), P = F.result;
  ok(r && r.weeks === P.weeks, `${sym}: تعداد هفته`);
  for (const k of ['alpha_ann', 'alpha_t', 'r2', 'resid_vol_ann', 'excess_ann', 'vol_ann', 'dimson_beta']) near(r[k], P[k], 1e-3 * Math.max(1, Math.abs(P[k])), `${sym} ${k}`);
  r.factors.forEach((f, i) => { for (const k of ['beta', 't', 'factor_ann', 'contrib_ann']) near(f[k], P.factors[i][k], 2e-3 * Math.max(1, Math.abs(P.factors[i][k])), `${sym} ${f.code} ${k}`); });
  near(r.alpha_ann + r.factors.reduce((s, f) => s + f.contrib_ann, 0), r.excess_ann, 1e-9, `${sym} جمع سهم‌ها`);
  const m = E.regress(F, A.rf_ann, ['MKT'], A.hac_lags);
  near(m.r2, F.market_only.r2, 1e-4, `${sym} R² فقط بازار`);
  const R = E.rolling(F, A.rf_ann, codes, A.hac_lags, A.roll);
  ok(R.end.length === F.rolling.end.length, `${sym}: طول بتای غلتان`);
  if (R.end.length) codes.forEach((c, j) => near(R.beta[j][R.end.length - 1], F.rolling.beta[c][R.end.length - 1], 2e-3, `${sym} بتای غلتان ${c}`));
  console.log(`${sym}: ${r.weeks} هفته، α ${r.alpha_ann.toFixed(2)}٪، R² ${r.r2.toFixed(3)}، β_SMB ${r.factors[1].beta.toFixed(3)}`);
}
// ۴) مصنوعی
let seed = 7; const rnd = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647 - 0.5; };
const n = 300, beta = [0.9, 0.6, -0.3], Fm = { MKT_raw: [], SMB: [], HML: [] }, y = [];
for (let t = 0; t < n; t++) { const m = 0.03 * rnd(), s = 0.02 * rnd(), h = 0.02 * rnd(); Fm.MKT_raw.push(m); Fm.SMB.push(s); Fm.HML.push(h); y.push(0.001 + beta[0] * m + beta[1] * s + beta[2] * h + 0.002 * rnd()); }
const S = E.regress({ y, days: y.map(() => 7), F: Fm, w_end: y.map((_, i) => String(i)) }, 0, ['MKT', 'SMB', 'HML'], 4);
S.factors.forEach((f, i) => near(f.beta, beta[i], 0.02, `مصنوعی β ${f.code}`));
near(S.alpha_ann, 5.2, 0.6, 'مصنوعی آلفا');
console.log(bad ? `${bad} خطا` : 'همه درست');
process.exit(bad ? 1 : 0);
