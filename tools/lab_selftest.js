// آزمون هم‌ارزی موتور مرورگر (ui/labengine.js) با کتابخانهٔ پایتون: node tools/lab_selftest.js
const fs = require('fs'), path = require('path');
const win = {}; global.window = win;
const ui = path.join(__dirname, '..', 'ui');
new Function('window', fs.readFileSync(path.join(ui, 'labengine.js'), 'utf8').replace('})(typeof window', '})(typeof window'))(win);
// labengine.js از root=window یا globalThis استفاده می‌کند
const E = win.LabEngine || globalThis.LabEngine;
new Function('window', fs.readFileSync(path.join(ui, 'data', 'lab.js'), 'utf8'))(win);
const L = win.SIM_LAB, ctx = E.load(L);
console.log('ردیف', L.rows, 'نماد', L.k, 'معیار', L.signals.length, 'کتابخانه', L.library.length);
let worst = 0;
for (const id of process.argv.slice(2).length ? process.argv.slice(2) : ['sig:vol_252', 'sig:size', 'sig:div_yield', 'sig:mom_12_1', 'combo:c1:equal', 'combo:c1:rank', 'combo:c1:icir', 'combo:c1:fm', 'algo:vol_252:score_tilt', 'algo:vol_252:rank_weight', 'algo:vol_252:msci_tilt', 'algo:vol_252:topn', 'algo:vol_252:inv_vol', 'meta:topk5']) {
  const r = L.library.find(x => x.id === id); if (!r) { console.log('نیست:', id); continue; }
  const spec = r.spec; if (!E.JS_ALGOS.includes(spec.algo)) { console.log('JS ندارد:', id); continue; }
  const t0 = Date.now(), res = E.run(ctx, spec), st = E.stats(res, r.spec.cost_bp ?? L.cost_bp ?? 125), dt = Date.now() - t0;
  const n = Math.min(res.ret.length, r.ret.length); let mx = 0; for (let i = 0; i < n; i++) mx = Math.max(mx, Math.abs(res.ret[i] - r.ret[i]));
  const py = r.stats; worst = Math.max(worst, Math.abs(st.excess_net - py.excess_net));
  console.log(id.padEnd(30), `ماه ${res.ret.length}/${r.ret.length}`, `max|Δret|=${(mx * 100).toFixed(2)}%`, `برتری JS ${st.excess_net.toFixed(1)} PY ${py.excess_net.toFixed(1)}`, `t JS ${st.t_net.toFixed(2)} PY ${py.t_net.toFixed(2)}`, `${dt}ms`);
}
console.log('بدترین اختلاف برتری سالانه (واحد درصد):', worst.toFixed(2));

// تفکیک فاکتوری: مرورگر (LabEngine.attribution) در برابر پایتون (tools/attribution.py → library[].attr)
let worstA = 0;
for (const id of ['combo:c1:rank', 'sens:partial50', 'combo:c1:fm', 'algo:vol_252:min_var', 'sig:q_roe', 'combo:c4:ridge']) {
  const r = L.library.find(x => x.id === id); if (!r || !r.attr) { console.log('تفکیک نیست:', id); continue; }
  const nan = v => v == null ? NaN : v, res = { ret: r.ret, all: r.all, to: r.to.map(nan), toAll: (r.to_all || r.all.map(() => 0)).map(nan), end: r.end };
  const a = E.attribution(L, res, (r.spec && r.spec.cost_bp) || L.cost_bp), p = r.attr;
  const d = Math.max(Math.abs(a.alpha_ann - p.alpha_ann), ...a.factors.map((f, k) => 10 * Math.abs(f.beta - p.factors[k].beta)), Math.abs(a.gross_excess_ann - p.gross_excess_ann));
  worstA = Math.max(worstA, d);
  console.log(id.padEnd(30), `α JS ${a.alpha_ann.toFixed(2)} PY ${p.alpha_ann.toFixed(2)} · β اندازه JS ${a.factors[1].beta.toFixed(3)} PY ${p.factors[1].beta.toFixed(3)} · R² ${a.r2.toFixed(2)}/${p.r2.toFixed(2)}`);
}
console.log('بدترین اختلاف تفکیک (واحد درصد؛ β × ۱۰):', worstA.toFixed(3));

// فاکتورهای هم‌جهانِ مرورگر (factorSeriesFor) با جهان پیش‌فرض باید همان ردیف‌های sig: کتابخانه باشند؛ و جهان دیگر باید فاکتور دیگری بدهد
{
  const t0 = Date.now(), f = E.factorSeriesFor(ctx, { universe: { markets: ['bourse', 'farabourse'], min_adv: 0 }, rebalance_every: 1, cost_bp: L.cost_bp }), dt = Date.now() - t0;
  let mx = 0;
  for (const [code, , sig] of E.FACTORS) {
    const r = sig ? L.library.find(x => x.id === 'sig:' + sig) : L.library.find(x => x.id === 'sig:size'), lib = sig ? r.ret.map((v, i) => v - r.all[i]) : r.all;
    const a = f[code], n = Math.min(a.length, lib.length); let s = 0; for (let i = 1; i <= n; i++) s += a[a.length - i] - lib[lib.length - i];
    mx = Math.max(mx, Math.abs(1200 * s / n));
  }
  const g = E.factorSeriesFor(ctx, { universe: { markets: ['farabourse'], min_adv: 0 }, rebalance_every: 1, cost_bp: L.cost_bp });
  const diff = Math.abs(g.SIZE.slice(-24).reduce((s, v) => s + v, 0) - f.SIZE.slice(-24).reduce((s, v) => s + v, 0));
  console.log(`فاکتور هم‌جهان در برابر کتابخانه: بیشترین اختلاف میانگین سالانه ${mx.toFixed(2)} واحد درصد · ${dt}ms · فقط‌فرابورس متفاوت: ${diff > 1e-6 ? 'بله' : 'خیر'}`);
}
