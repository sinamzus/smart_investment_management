// سیاست‌های ریبالانس همتاساز در موتور مرورگر (ui/builder.js؛ فصل ۳ «سیاست ریبالانس»)
//   node tools/rebal_selftest.js
// ۱) سیاستی با rbm همه ۱ و بدون tod همان ماهانهٔ پایه است؛ ۲) برای هر فایل سیاست ساخته‌شده: تعداد ریبالانس اجراشده = Σ rbm (پس از ماه شروع) + tod،
// هزینه فقط با ریبالانس، هزینهٔ بیشتر ⇒ NAV کمتر؛ ۳) هفتگی بیش از فصلی و فصلی بیش از سالانه ریبالانس دارد.
const fs = require('fs'), path = require('path');
global.window = global;
const E = require('../ui/builder.js');
let bad = 0;
const ok = (c, m) => { if (!c) { bad++; console.log('خطا:', m); } };
const D = path.join(__dirname, '..', 'ui', 'data');
for (const [tgt, base, name] of [['k', 'replica.js', 'SIM_REP'], ['ew', 'replica_ew.js', 'SIM_REP_EW']]) {
  if (!fs.existsSync(path.join(D, base))) continue;
  require(path.join(D, base));
  const B = global[name], keys = Object.keys(B.configs).filter(k => k.endsWith('|0')).slice(0, 6);
  const o = { mode: 'none', L: 1, loan: false, phi: 0.02, aum: 1000, rb: 0.3, rc: 0, cost: 125, j0: 0 };
  // ۱) هم‌ارزی با ماهانه
  const M = { ...B, _p: null, configs: Object.fromEntries(keys.map(k => [k, { ...B.configs[k], rbm: B.configs[k].to.map(() => 1), tod: [[], []] }])) };
  for (const k of keys) {
    const a = E.simulate(B, k, o), b = E.simulate(M, k, o);
    ok(Math.abs(a.nav[a.nav.length - 1] - b.nav[b.nav.length - 1]) < 1e-12, `${tgt} ${k}: rbm=1 با ماهانه نمی‌خواند`);
  }
  const cnt = {};
  for (const pol of ['w1', 'w2', 'q', 'h', 'y', 't5', 't10']) {
    const f = path.join(D, `replica${tgt === 'ew' ? '_ew' : ''}_rb_${pol}.js`);
    if (!fs.existsSync(f)) continue;
    require(f);
    const P = global.SIM_REP_RB[`${tgt}|${pol}`];
    if (P.asof !== B.asof) { console.log(`${tgt}|${pol}: تاریخ داده با پایه فرق دارد؛ رد شد`); continue; }
    const R = E.mergePol(B, P);
    let nr = 0;
    for (const k of keys) {
      const c = R.configs[k], s = E.simulate(R, k, o), s0 = E.simulate(R, k, { ...o, cost: 0 }), s2 = E.simulate(R, k, { ...o, cost: 250 });
      const want = c.rbm.slice(1).reduce((x, y) => x + y, 0) + c.tod[0].length;
      ok(s.nReb === want, `${tgt}|${pol} ${k}: ریبالانس ${s.nReb} ≠ ${want}`);
      ok(s0.cm.every(x => x === 0), `${tgt}|${pol} ${k}: هزینه با cost=0`);
      const e = x => x.nav[x.nav.length - 1];
      ok(e(s0) >= e(s) && e(s) >= e(s2), `${tgt}|${pol} ${k}: هزینهٔ بیشتر NAV بیشتر داد`);
      ok(c.sel.length === B.mstart.length && c.sel.every(([i, w]) => i.length === w.length && Math.abs(w.reduce((x, y) => x + y, 0) / 1e5 - 1) < 2e-3), `${tgt}|${pol} ${k}: وزن‌های آغاز ماه`);
      nr += s.nReb;
    }
    cnt[pol] = nr / keys.length;
  }
  if (cnt.w1 != null && cnt.q != null) ok(cnt.w1 > cnt.q, `${tgt}: هفتگی کمتر از فصلی ریبالانس دارد`);
  if (cnt.q != null && cnt.y != null) ok(cnt.q > cnt.y, `${tgt}: فصلی کمتر از سالانه ریبالانس دارد`);
  console.log(`${tgt}: میانگین ریبالانس اجراشده`, JSON.stringify(cnt));
}
console.log(bad ? `${bad} خطا` : 'همهٔ آزمون‌ها موفق');
process.exit(bad ? 1 : 0);
