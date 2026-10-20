// هم‌ارزی موتور مرورگری همتاساز (ui/builder.js) با پایتون (tools/sampled_replica.py → data/research/sampled_replica.csv)
//   node tools/replica_selftest.js
// برای سطح نقدشوندگی ۰، نرخ وام ۳۰٪، هزینه ۱۰۰bp، شروع از نخستین ماه؛ هر دو حالت «بدون وام» و «تراز بتا».
global.window = global;
require('../ui/data/replica.js');
const E = require('../ui/builder.js');
const R = global.SIM_REP;
const rows = require('fs').readFileSync(__dirname + '/../data/research/sampled_replica.csv', 'utf8').replace(/^﻿/, '').trim().split('\n');
const h = rows[0].split(','), idx = n => h.indexOf(n);
let worst = 0, n = 0;
for (const line of rows.slice(1)) {
  const c = line.split(','), N = +c[idx('N')], m = c[idx('method')], lev = c[idx('leverage')];
  if (!R.Ns.includes(N)) continue;
  const sim = E.simulate(R, E.keyOf(m, N, 0), { mode: lev === 'beta' ? 'beta' : 'none', L: 1, loan: lev === 'bridge', q: 0, rb: 0.30, rc: 0, cost: 125, j0: 0 }), r = E.metrics(R, sim);
  const d = { ann: Math.abs(r.ann - +c[idx('ann_pct')]), te: Math.abs(r.te - +c[idx('te_vs_official_pct')]), teC: Math.abs(r.teC - +c[idx('te_vs_fullreplica_pct')]), beta: Math.abs(r.beta - +c[idx('beta')]) };
  const w = Math.max(d.ann, d.te, d.teC, d.beta * 10); worst = Math.max(worst, w); n++;
  if (w > 0.05) console.log('انحراف', N, m, lev, JSON.stringify(d));
}
console.log(`مقایسه: ${n} ترکیب؛ بیشترین انحراف ${worst.toFixed(4)} (درصد/واحد)`);
process.exit(worst > 0.1 ? 1 : 0);
