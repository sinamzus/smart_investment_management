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
