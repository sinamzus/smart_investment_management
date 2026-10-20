// آزمون موتور بخش «پرتفو» (ui/portfolio.js) روی بازار ساختگی: node tools/portfolio_selftest.js
// سود نقدی (طلب ← نقد)، سهام جایزه، حق‌تقدم (پذیره‌نویسی / فروش)، رویداد نامطمئن و بازگشت خطای داده، نماد بی‌معامله، سفارش‌ها و انحراف.
const path = require('path');
const P = require(path.join(__dirname, '..', 'ui', 'portfolio.js'));
let fail = 0;
const ok = (c, m) => { if (!c) { fail++; console.log('✗', m); } else console.log('✓', m); };
const near = (a, b, e = 1e-6) => Math.abs(a - b) <= e * Math.max(1, Math.abs(b));

// دو نماد A و B، شش روز معاملاتی؛ B در روز ۲۰۲۴-۰۱-۰۵ معامله نشده
const dates = ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05', '2024-01-06'];
const pxA = [1000, 1000, 1100, 1100, 1200, 1200], pxB = [5000, 5000, 5000, 4000, 4000, 4500];
const K = 2, px = new Float32Array(dates.length * K), tr = new Uint8Array(dates.length * K);
dates.forEach((_, t) => { px[t * K] = pxA[t]; px[t * K + 1] = pxB[t]; tr[t * K] = 1; tr[t * K + 1] = t === 4 ? 0 : 1; });
const X = { codes: ['A1', 'B1'], syms: ['آلفا', 'بتا'], dates, pxArr: px, trArr: tr, par: 1000,
  divs: [[0, '2024-01-02', 50, '2024-01-05', 'a']],                                  // A: سود ۵۰ ریال، استحقاق ۰۲، پرداخت ۰۵
  caps: [[1, '2024-01-04', 1.5, 0.4, 1, 5000],                                      // B: افزایش ۵۰٪: ۶۰٪ جایزه، ۴۰٪ حق‌تقدم (مطمئن)
         [0, '2024-01-03', 2.0, 1.0, -1, 1000],                                     // A: بازگشت خطای داده → اعمال نمی‌شود
         [0, '2024-01-06', 1.2, 0.0, 0, 1200]] };                                   // A: نامطمئن → فقط با انتخاب

const st0 = { date: '2024-01-01', hold: { A1: 1000, B1: 100 }, cash: 0, recv: [] };

// ۱) تا ۰۴: سود A طلب است (هنوز پرداخت نشده)، B: جایزه ۱۰۰×۰٫۵×۰٫۶ = ۳۰، حق‌تقدم ۱۰۰×۰٫۵×۰٫۴ = ۲۰ پذیره‌نویسی (−۲۰٬۰۰۰ نقد)
let s = P.roll(X, st0, '2024-01-04');
ok(s.hold.A1 === 1000, 'بازگشت خطای داده اعمال نشد (A همان ۱۰۰۰)');
ok(s.hold.B1 === 150, `B پس از جایزه و پذیره‌نویسی = ۱۵۰ (${s.hold.B1})`);
ok(near(s.cash, -20000), `نقد = −۲۰٬۰۰۰ برای پذیره‌نویسی (${s.cash})`);
ok(s.recv.length === 1 && near(s.recv[0].amt, 50000) && s.recv[0].pay === '2024-01-05', 'طلب سود ۵۰٬۰۰۰ تا ۰۵');
ok(s.log.some(e => e.t === 'glitch') && s.log.some(e => e.t === 'div') && s.log.some(e => e.t === 'cap'), 'گزارش رویدادها کامل');

// ۲) فروش حق‌تقدم: ارزش نظری = قیمت پس از رویداد (۴۰۰۰) − ۱۰۰۰ = ۳۰۰۰ × ۲۰
const key = s.log.find(e => e.t === 'cap').key;
s = P.roll(X, st0, '2024-01-04', { rights: { [key]: 'sell' } });
ok(s.hold.B1 === 130 && near(s.cash, 60000), `فروش حق‌تقدم: B = ۱۳۰، نقد = ۶۰٬۰۰۰ (${s.hold.B1}، ${s.cash})`);

// ۳) تا ۰۶: سود وصول شد؛ رویداد نامطمئن A بدون انتخاب اعمال نمی‌شود، با انتخاب جایزهٔ ۲۰٪
s = P.roll(X, st0, '2024-01-06');
ok(s.recv.length === 0 && near(s.cash, -20000 + 50000), `وصول سود در روز پرداخت (نقد ${s.cash})`);
ok(s.hold.A1 === 1000 && s.log.some(e => e.t === 'unsure'), 'نامطمئن بی‌انتخاب اعمال نشد');
const uk = s.log.find(e => e.t === 'unsure').key;
const s2 = P.roll(X, st0, '2024-01-06', { unsure: new Set([uk]) });
ok(s2.hold.A1 === 1200, `نامطمئن با انتخاب: A = ۱۲۰۰ (${s2.hold.A1})`);

// ۴) ارزش‌گذاری ۰۶: A ۱۰۰۰×۱۲۰۰ + B ۱۵۰×۴۵۰۰ + نقد ۳۰٬۰۰۰
const V = P.value(X, s, '2024-01-06');
ok(near(V.stock, 1000 * 1200 + 150 * 4500) && near(V.nav, V.stock + 30000), `ارزش کل ${V.nav}`);

// ۵) سفارش‌ها در ۰۵ (B بی‌معامله ⇒ منجمد) به وزن ۵۰/۵۰
const s5 = P.roll(X, st0, '2024-01-05');
const o = P.orders(X, s5, { A1: 0.5, B1: 0.5 }, '2024-01-05', { costBp: 100 });
ok(o.frozen.includes('B1') && !o.orders.some(x => x.c === 'B1'), 'نماد بی‌معامله منجمد ماند');
const inv = o.invest, tqA = Math.floor((inv - 150 * 4000) / 1200);              // B منجمد با ارزش فعلی‌اش؛ باقی سرمایه به نمادهای قابل‌معامله (فقط A)
ok(o.after.hold.A1 === tqA && o.after.hold.B1 === 150, `موجودی هدف A = ${tqA} (${o.after.hold.A1})`);
ok(o.after.cash >= -1, `نقد پس از اجرا منفی نیست (${o.after.cash.toFixed(0)})`);
ok(near(o.after.cash, o.V.cash - o.buy + o.sell - o.fee), 'نقد پس از اجرا = نقد − خرید + فروش − هزینه');
ok(near(o.fee, (o.buy + o.sell) * 0.01 / 2), 'هزینه = نصف رفت‌وبرگشت روی کل معاملات');

// ۶) شروع از نقد: هیچ سهمی بیش از سرمایه خریده نمی‌شود
const o2 = P.orders(X, { date: '2024-01-06', hold: {}, cash: 1e7, recv: [] }, { A1: 0.7, B1: 0.3 }, '2024-01-06', {});
ok(o2.buy <= 1e7 && o2.after.cash >= 0 && o2.orders.every(x => x.side === 'buy'), `ساخت از نقد: خرید ${o2.buy}، نقد باقی ${o2.after.cash}`);

// ۷) انحراف: موجودی واقعی = برنامه ⇒ سهم فعال صفر؛ نصف B ⇒ مثبت
const dv0 = P.deviation(X, o2.after.hold, { hold: o2.after.hold }, '2024-01-06'), half = { ...o2.after.hold, B1: Math.floor(o2.after.hold.B1 / 2) };
const dv1 = P.deviation(X, o2.after.hold, { hold: half }, '2024-01-06');
ok(near(dv0.active, 0) && dv1.active > 0.05, `سهم فعال ۰ و ${dv1.active.toFixed(3)}`);

// ۸) تاریخ غیرمعاملاتی: قیمت آخرین روز معاملاتی پیش از آن
ok(P.pxAt(X, 0, '2024-01-10') === 1200 && Number.isNaN(P.pxAt(X, 0, '2023-12-01')), 'قیمت روز غیرمعاملاتی و پیش از داده');

// ۹) حق‌تقدم پذیره‌نویسی‌شده تا ثبت فروختنی نیست؛ کسری نقد گزارش می‌شود؛ هزینهٔ نامتقارن
const s9 = P.roll(X, st0, '2024-01-04');
ok(s9.pend.length === 1 && s9.pend[0].n === 20 && s9.log.some(e => e.t === 'short'), 'سهم حق‌تقدم در انتظار ثبت و کسری نقد ثبت شد');
const o9 = P.orders(X, s9, { A1: 1.0 }, '2024-01-04', { costBuyBp: 37, costSellBp: 88 });
ok(o9.after.hold.B1 === 20, `فقط سهم‌های قابل‌فروش B فروخته شد (باقی ${o9.after.hold.B1})`);
ok(near(o9.fee, o9.buy * 0.0037 + o9.sell * 0.0088), 'هزینه = خرید × ۳۷ + فروش × ۸۸ واحد پایه');
const s9b = P.roll(X, st0, '2024-03-10');
ok(s9b.pend.length === 0, 'پس از ۶۰ روز سهم حق‌تقدم آزاد شد');

console.log(fail ? `${fail} آزمون شکست خورد` : 'همهٔ آزمون‌ها موفق');
process.exit(fail ? 1 : 0);
