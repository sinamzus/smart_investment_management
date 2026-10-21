// آزمون موتور «شاخص بهبودیافته» (ui/enhance.js) در برابر خروجی پایتون (ui/data/replica.js) و ویژگی‌های تیلت
//   node tools/enhance_selftest.js
global.window = global;
require('../ui/data/replica.js'); require('../ui/data/replica_x.js');
const EN = require('../ui/enhance.js'), RB = require('../ui/builder.js');
const R = global.SIM_REP, X = global.SIM_REPX, ctx = EN.loadX(X);
let bad = 0; const ok = (c, m) => { if (!c) { bad++; console.log('✗', m); } else console.log('✓', m); };
(async () => {
  // ۱) تیلت صفر: top و strat باید همان انتخاب و بازده پایتون را بدهند
  for (const [method, N, liq] of [['top', 30, 0], ['strat', 30, 1], ['top', 50, 2]]) {
    const E = await EN.runEnh(ctx, { tilt: {}, method, N, liq }, null, null), P = R.configs[`${method}|${N}|${liq}`];
    let maxd = 0; const rp = RB.seriesOf(R, `${method}|${N}|${liq}`); for (let t = 0; t < rp.length; t++) maxd = Math.max(maxd, Math.abs(E._p.cfg.enh[t] - rp[t]));
    ok(maxd < 2e-5, `${method} N=${N} liq=${liq}: بیشینهٔ تفاوت بازده روزانه با پایتون ${maxd.toExponential(2)}`);
    const nm = P.to.length; let dto = 0; for (let j = 1; j < nm; j++) dto = Math.max(dto, Math.abs(E.configs.enh.to[j] - P.to[j]));
    ok(dto < 5e-4, `${method} N=${N} liq=${liq}: گردش ماهانه (بیشینه تفاوت ${dto.toExponential(2)})`);
  }
  // ۲) opt: TE نزدیک به پایتون (لایهٔ عرضهٔ اولیه خاموش: هدف تیلت‌شده آن را ندارد)
  const t0 = Date.now(), Eo = await EN.runEnh(ctx, { tilt: {}, method: 'opt', N: 30, liq: 0, iters: 120 }, null, null);
  const mo = RB.metrics(Eo, RB.simulate(Eo, 'enh', { mode: 'none', L: 1, phi: 0, rb: .3, rc: 0, cost: 100, j0: 0 })), mp = RB.metrics(R, RB.simulate(R, 'opt|30|0', { mode: 'none', L: 1, phi: 0, rb: .3, rc: 0, cost: 100, j0: 0 }));
  ok(Math.abs(mo.te - mp.te) < 0.15, `opt N=30: TE مرورگر ${mo.te.toFixed(2)} در برابر پایتون ${mp.te.toFixed(2)} (${((Date.now() - t0) / 1000).toFixed(1)}s)`);
  // ۳) ویژگی‌های تیلت
  const j = 60;
  const t1 = EN.tilted(ctx, j, { cap: 0.05 }, null); ok(Math.abs(t1.idx.reduce((s, i) => s + t1.b[i], 0) - 1) < 1e-9 && Math.max(...t1.idx.map(i => t1.b[i])) <= 0.05 + 1e-9, 'سقف ۵٪ رعایت و مجموع ۱');
  const sec0 = ctx.names[t1.idx[0]].sec, t2 = EN.tilted(ctx, j, { sec: { [sec0]: -100 } }, null); ok(t2.idx.filter(i => ctx.names[i].sec === sec0).every(i => t2.b[i] === 0) && Math.abs(t2.idx.reduce((s, i) => s + t2.b[i], 0) - 1) < 1e-9, 'تیلت −۱۰۰٪ صنعت آن را حذف می‌کند');
  const t3 = EN.tilted(ctx, j, { gamma: 0 }, null), n = t3.idx.length; ok(t3.idx.every(i => Math.abs(t3.b[i] - 1 / n) < 1e-9), 'γ=۰ هم‌وزن است');
  const t4 = EN.tilted(ctx, j, { ew: 1 }, null); ok(t4.idx.every(i => Math.abs(t4.b[i] - 1 / n) < 1e-9), 'α=۱ هم‌وزن است');
  const t0w = EN.tilted(ctx, j, {}, null); ok(t0w.idx.every(i => Math.abs(t0w.b[i] - t0w.b0[i]) < 1e-12), 'بدون تیلت: هدف = شاخص رسمی');
  console.log(bad ? `\n${bad} آزمون ناموفق` : '\nهمهٔ آزمون‌ها موفق'); process.exit(bad ? 1 : 0);
})();
