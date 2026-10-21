// هم‌ارزی موتور مرورگری همتاساز (ui/builder.js) با پایتون (tools/sampled_replica.py → data/research/sampled_replica*.csv)
//   node tools/replica_selftest.js
// هر دو هدف («شاخص كل» و، اگر داده‌اش ساخته شده، «شاخص كل (هم وزن)»)؛ سطح نقدشوندگی ۰، نرخ وام ۳۰٪، هزینه ۱۲۵bp،
// لایهٔ عرضهٔ اولیه φ = ۲٪ و صندوق ۱٬۰۰۰ میلیارد ریال، شروع از نخستین ماه؛ هر سه حالت «بدون وام»، «وام سود» و «تراز بتا».
const fs = require('fs'), path = require('path');
global.window = global;
const E = require('../ui/builder.js');
let worst = 0, n = 0;
for (const [data, csv, name] of [['replica.js', 'sampled_replica.csv', 'SIM_REP'], ['replica_ew.js', 'sampled_replica_ew.csv', 'SIM_REP_EW']]) {
  const dp = path.join(__dirname, '..', 'ui', 'data', data), cp = path.join(__dirname, '..', 'data', 'research', csv);
  if (!fs.existsSync(dp) || !fs.existsSync(cp)) { if (name === 'SIM_REP') { console.log('دادهٔ همتاساز پیدا نشد'); process.exit(1); } continue; }
  require(dp);
  const R = global[name];
  const rows = fs.readFileSync(cp, 'utf8').replace(/^﻿/, '').trim().split('\n');
  const h = rows[0].split(','), idx = k => h.indexOf(k);
  let m0 = 0;
  for (const line of rows.slice(1)) {
    const c = line.split(','), N = +c[idx('N')], m = c[idx('method')], lev = c[idx('leverage')];
    if (!R.Ns.includes(N)) continue;
    const sim = E.simulate(R, E.keyOf(m, N, 0), { mode: lev === 'beta' ? 'beta' : 'none', L: 1, loan: lev === 'bridge', phi: 0.02, aum: 1000, rb: 0.30, rc: 0, cost: 125, j0: 0 }), r = E.metrics(R, sim);
    const d = { ann: Math.abs(r.ann - +c[idx('ann_pct')]), te: Math.abs(r.te - +c[idx('te_vs_official_pct')]), teC: Math.abs(r.teC - +c[idx('te_vs_fullreplica_pct')]), beta: Math.abs(r.beta - +c[idx('beta')]) };
    const w = Math.max(d.ann, d.te, d.teC, d.beta * 10); worst = Math.max(worst, w); m0 = Math.max(m0, w); n++;
    if (w > 0.05) console.log('انحراف', name, N, m, lev, JSON.stringify(d));
  }
  console.log(`${name === 'SIM_REP' ? 'ارزش‌وزن' : 'هم‌وزن'}: بیشترین انحراف ${m0.toFixed(4)}`);
}
console.log(`مقایسه: ${n} ترکیب؛ بیشترین انحراف ${worst.toFixed(4)} (درصد/واحد)`);
process.exit(worst > 0.1 ? 1 : 0);
