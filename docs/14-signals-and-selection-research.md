# ۱۴ — معیارهای انتخاب و الگوریتم‌های ساخت پرتفوی: پژوهش، پیاده‌سازی و آزمون

> **جایگاه فصل.** فصل ۴ و ۵ سه فاکتور هدف (مومنتوم، حداقل نوسان، کیفیت) را با یک معیار ساده برای هرکدام تعریف کردند و آن‌ها را با «پنجک‌بندی هم‌وزن» آزمودند. این فصل هر دو تصمیم را باز می‌کند: (الف) **معیار انتخاب** (Signal) چه تعریف‌هایی می‌تواند داشته باشد و کدام‌یک در بورس و فرابورس ایران شواهد آماری دارد؛ (ب) **الگوریتم انتخاب و وزن‌دهی** (Construction) چه خانواده‌هایی دارد و هرکدام چه چیزی را بهینه می‌کند. همهٔ مدل‌های این فصل در نمای «میز پژوهش» (Lab) قابل ساخت، اجرا و مقایسه‌اند؛ کد در `tools/signals.py`، `tools/construction.py`، `tools/research_stats.py` و `tools/factor_engine.py` است.
>
> **قاعدهٔ خواندن.** هر عدد تجربی این فصل از اجرای همین کد روی دادهٔ مخزن می‌آید و تاریخ و نسخهٔ جهان آن ذکر می‌شود. عددی که از حافظه است **[راستی‌آزمایی نشده]** و عددی که نیازمند تأیید بیرونی است **[تأیید لازم]** علامت دارد. ادبیات مرجع در بخش ۱۴.۱۱ است.

---

## ۱۴.۱ چارچوب: سه لایهٔ تصمیم و چرا باید جدا آزموده شوند

یک استراتژی فاکتوری از سه تصمیم مستقل ساخته می‌شود و خلط آن‌ها رایج‌ترین منبع نتیجه‌گیری غلط است:

| لایه | سؤال | خروجی | نمونه در این فصل |
|---|---|---|---|
| ۱. **معیار** (Signal) | کدام ویژگی سهم، بازدهٔ مقطعی آینده را پیش‌بینی می‌کند؟ | امتیاز Z هر سهم در هر ماه | مومنتوم ۱۲−۱، نوسان یانگ–ژانگ، ROE |
| ۲. **ترکیب** (Combination) | چند معیار را چگونه به یک امتیاز تبدیل کنیم؟ | امتیاز ترکیبی | میانگین برابر، وزن‌دهی با IC، Fama–MacBeth |
| ۳. **ساخت** (Construction) | با امتیاز چه پرتفوی‌ای بسازیم؟ | وزن هدف و سفارش | پنجک هم‌وزن، بافر، MSCI-tilt، ERC، MVO با قید TE |

**چرا جدا؟** ضریب اطلاعات (IC) فقط کیفیت معیار را می‌سنجد؛ پنجک هم‌وزن بالایی ممکن است بازده اضافه نداشته باشد در حالی که IC معنادار است (اتفاقاً در نتایج ما برای نوسان همین رخ می‌دهد، §۱۴.۸). برعکس، یک الگوریتم خوب می‌تواند معیار ضعیف را بهتر از معیار قوی با ساخت بد کند. قانون بنیادی مدیریت فعال این رابطه را صریح می‌کند:

`IR ≈ TC · IC · √BR`

که در آن BR تعداد تصمیم‌های مستقل در سال (Breadth)، IC همبستگی رتبه‌ای امتیاز و بازده، و **TC (Transfer Coefficient)** نسبت به‌کارگیری امتیاز در وزن‌های واقعی است (Grinold & Kahn 2000؛ Clarke, de Silva & Thorley 2002). قید فقط‌خرید، سقف وزن، هزینه و گردش TC را کم می‌کنند: بنابراین الگوریتم ساخت را باید با **TC و IR خالص** سنجید، نه فقط با IC.

**اصل آزمون:** (۱) هر معیار تنها با IC و Fama–MacBeth ارزیابی می‌شود (مستقل از ساخت)؛ (۲) هر الگوریتم با یک معیار ثابت مقایسه می‌شود؛ (۳) فقط پس از آن، ترکیب‌ها؛ (۴) هر انتخاب بین N گزینه با آزمون‌های چندگانه (§۱۴.۷) جریمه می‌شود.

---

## ۱۴.۲ داده و قراردادها

### ۱۴.۲.۱ جهان و واجدیت
- **جهان:** همهٔ سهام بورس و فرابورس با قیمت (۷۱۹ نماد با بازده؛ فصل ۲ مورد ۰). عضویت در «شاخص كل» لازم نیست. حق‌تقدم، صندوق و اوراق خارج‌اند.
- **واجدیت قیمتی در روز ریبالانس a:** دست‌کم ۸۰٪ روزهای ۲۵۲ روز اخیر داده، ۵۰٪ روزها با بازدهٔ غیرصفر، بازدهٔ روز a موجود، و داده در روز بعد و پایان دوره (برای محاسبهٔ بازده). **اعتراف به نگاه به آینده‌ی جزئی:** شرط «داده در پایان دوره» نمادهایی را که در همان ماه متوقف یا حذف می‌شوند کنار می‌گذارد؛ این سوگیری بقای کوچک بازده همه‌ی سبدها را کمی بالا می‌برد و در مقایسهٔ نسبی اثر ناچیز دارد.
- **فیلتر نقدشوندگی اختیاری (`min_adv`)**: حداقل میانگین ارزش معاملات روزانهٔ ۶۳ روز؛ برای فرابورس مهم است.

### ۱۴.۲.۲ زمان‌بندی (Timing) — بدون نگاه به آینده
- **ریبالانس:** آخرین روز معاملاتی هر ماه شمسی (روز a). هر معیار فقط داده تا بستهٔ روز a را می‌بیند.
- **سبد:** از بستهٔ a خریداری و تا بستهٔ آخرین روز ماه بعد نگه داشته می‌شود. **تأخیر اجرا (`delay`)**: صفر یعنی معامله در بستهٔ روز a (ایده‌آل)، یک یعنی بستهٔ روز بعد (قابل‌اجرا در عمل). حساسیت نتایج به delay جزء خروجی‌هاست.
- **بنیادی:** هر سال مالی از «تاریخ اعلام اولین EPS ۱۲‌ماهه» (در نبود آن: پایان سال مالی + ۱۲۰ روز [تأیید لازم]) به بعد و فقط تا ۵۴۰ روز بعد قابل‌استفاده است. تاریخ ستون جدول رهاورد برای انتشار به‌کار نمی‌رود (فصل ۴ §۴٫۳).

### ۱۴.۲.۳ جهت و نرمال‌سازی
- **جهت قرارداد:** امتیاز بالاتر = بازده مورد انتظار بیشتر *بر پایهٔ ادبیات*؛ مثلاً «نوسان کم» یعنی منفیِ نوسان. علامت تجربی را IC نشان می‌دهد؛ جهت‌ها را عوض نمی‌کنیم تا «کشف علامت معکوس» جزء نتیجه باشد نه ساخته‌شدن معیار پس از دیدن داده.
- **Winsorize ۱–۹۹٪ مقطعی** و استاندارد کردن: `z = (x − μ_t)/σ_t` در هر ماه فقط روی واجدان (فصل ۵ §۵٫۲).
- **خنثی‌سازی صنعتی:** کسر میانگین Z درون صنعت (دست‌کم ۶ سهم؛ وگرنه دست‌نخورده). هدف: جدا کردن اثر انتخاب سهم از اثر شرط‌بندی صنعتی. ایران ۴۸ صنعت دارد و برخی صنایع (خودرو، بانک، پتروشیمی) ضربهٔ مشترک زیاد دارند.
- **IC** = همبستگی رتبه‌ای اسپیرمن Z با بازده ماه بعد؛ **t نیوی‌وست** با ۳ وقفه؛ ICIR = میانگین IC ÷ انحراف معیار × √۱۲.

### ۱۴.۲.۴ هزینه و گردش
گردش یک‌طرفهٔ ماهانه `½ Σ|w_target − w_drift|`؛ هزینه = گردش × هزینهٔ رفت‌وبرگشت (پیش‌فرض ۱۰۰ bp [تأیید لازم]؛ ورودی UI). بازده خالص = ناخالص − هزینه. گردش سالانه = مجموع گردش ماهانه ÷ سال.

---

## ۱۴.۳ تاکسونومی معیارها

کتابخانه ۵۰ معیار در شش خانواده دارد (`tools/signals.py`؛ فهرست کامل در نمای «معیارها»). برای هر خانواده: تعریف، مبنای نظری، ویژگی‌های بازار ایران و محدودیت داده.

### ۱۴.۳.۱ مومنتوم و خانوادهٔ روند/بازگشت
**ایده:** واکنش کم/دیر به اطلاعات و رفتار گله‌ای باعث ماندگاری روند می‌شود (Jegadeesh & Titman 1993؛ Daniel, Hirshleifer & Subrahmanyam 1998؛ Barberis, Shleifer & Vishny 1998).

| معیار | تعریف | نکته |
|---|---|---|
| `mom_12_1`، `mom_9_1`، `mom_6_1`، `mom_3_1` | Σ ln(1+r) در پنجره منهای ۲۱ روز اخیر | حذف ماه اخیر برای کاهش اثر بازگشت کوتاه‌مدت |
| `mom_12_0` | بدون حذف ماه اخیر | مبنای مقایسه |
| `mom_intermediate` | ماه ۱۲ تا ۷ | Novy-Marx (2012): مومنتوم «میانی» قوی‌تر از اخیر است |
| `mom_riskadj` | مومنتوم ÷ σ همان پنجره | Barroso & Santa-Clara (2015): مدیریت ریسک سقوط مومنتوم |
| `mom_resid` | مجموع باقیماندهٔ مدل بازار ÷ (σ باقیمانده·√n) | Blitz, Huij & Martens (2011): حذف اثر بتا و روند بازار |
| `high52` | قیمت ÷ اوج ۵۲ هفته | George & Hwang (2004): لنگر ذهنی |
| `mom_industry` | میانگین مومنتوم صنعت | Moskowitz & Grinblatt (1999) |
| `mom_up_days` | سهم روزهای مثبت | پیوستگی روند؛ ساده‌شدهٔ Da, Gurun & Warachka (2014) |
| `rev_1m`، `rev_1w` | منفی بازده ۲۱ و ۵ روز | بازگشت کوتاه‌مدت (Jegadeesh 1990؛ Lehmann 1990) |
| `max_lottery` | منفی میانگین ۳ بازدهٔ بیشینهٔ ماه | Bali, Cakici & Whitelaw (2011) |

**ویژگی‌های ایران:** (الف) حد نوسان روزانه (سقف/کف قیمت) و «صف خرید/فروش»، بازده روزانه را قطع می‌کند و روند را چند روز پیاپی «صف‌نشینی» می‌کند؛ بنابراین مومنتوم خامِ بازده قسمتی انعکاس نقدشوندگی است نه اطلاعات (فصل ۱۱ §۱۱٫۳). (ب) تورم بالا باعث می‌شود بازدهٔ اسمی سهام همبستگی بالایی با نرخ ارز و تورم داشته باشد؛ مومنتوم باقیمانده نسبت به بازار این مؤلفه را حذف می‌کند. (ج) در `max_lottery`، سقف نوسان MAX را اشباع می‌کند (بسیاری از سهام سقف را لمس می‌کنند) و به همین علت میانگین سه بازدهٔ بیشینه به‌جای یک بازده به‌کار می‌رود.

### ۱۴.۳.۲ ریسک و نوسان
**ایده:** سهام پرریسک به‌دلیل ترجیح بخت‌آزمایی و قید اهرم سرمایه‌گذاران، گران‌قیمت و کم‌بازده‌اند (Black 1972؛ Frazzini & Pedersen 2014؛ Baker, Bradley & Wurgler 2011؛ Blitz & van Vliet 2007). «حداقل نوسان» یک ایده نیست؛ **خانواده‌ای از برآوردگرهای ریسک** است و انتخاب برآوردگر مسئلهٔ آماری مستقلی است:

| خانواده | معیارها | مزیت | ضعف در ایران |
|---|---|---|---|
| انحراف معیار بازده | `vol_252`، `vol_126`، `vol_63`، `vol_ewma` | ساده، شفاف | روزهای صفر و قفل قیمتی نوسان را کم‌برآورد می‌کنند |
| ریسک نزولی | `downside_dev`، `cvar_5`، `mdd_252` | حساس به دم چپ (Sortino & Price 1994؛ Acerbi & Tasche 2002) | نمونه محدود در دم؛ cvar با ۲۵۲ روز بر ~۱۲ مشاهده بنا می‌شود |
| برآوردگر بازه‌ای (OHLC) | `vol_parkinson`، `vol_gk`، `vol_rs`، `vol_yz` | کارایی آماری تا ~۵–۸ برابر close-to-close در شرایط ایده‌آل (Parkinson 1980؛ Garman & Klass 1980؛ Rogers & Satchell 1991؛ Yang & Zhang 2000) | **روزهای قفل (High=Low) برآورد را صفر می‌کنند**؛ لذا فقط وقتی ≥۴۰٪ روزها بازه دارند محاسبه می‌شوند |
| بتا | `beta_ols`، `beta_shrunk`، `beta_dimson` | BAB (Frazzini & Pedersen 2014) | معاملات ناهمزمان بتا را کم‌برآورد می‌کند؛ Dimson (1979) با وقفه/پیش‌رو اصلاح می‌کند (Scholes & Williams 1977 جایگزین) |
| ایدیوسینکراتیک | `idio_vol` | Ang et al. (2006): ریسک غیرسیستماتیک با بازده منفی | بازار هم‌وزن به‌جای شاخص کل تعریف می‌شود |
| ممان‌های بالاتر | `neg_skew` | بخت‌آزمایی (Boyer, Mitton & Vorkink 2010) | حد نوسان چولگی را قطع می‌کند |

**اصل برآوردگر بازه‌ای.** اگر قیمت حرکت براونی بدون دریفت باشد، `E[(ln H/L)²] = 4 ln 2 · σ²` (پارکینسون)؛ گارمن–کلاس افزودن `ln(C/O)` را برای حذف سوگیری می‌کند؛ راجرز–ساچل دریفت را هم مجاز می‌داند؛ یانگ–ژانگ شکاف شبانه (`ln O_t/C_{t−1}`) را هم دخیل می‌کند و ترکیب بهینه واریانس را با ضریب `k = 0.34/(1.34+(n+1)/(n−1))` می‌دهد. این فرض‌ها (پیوستگی مسیر) در بازاری با حد نوسان و توقف نماد نقض می‌شود؛ پس نتیجهٔ این برآوردگرها باید با close-to-close مقایسه شود، نه جایگزین آن.

### ۱۴.۳.۳ نقدشوندگی و اندازه
**ایده:** سهام کم‌نقد برای جبران هزینه، بازده مورد انتظار بیشتری می‌دهند (Amihud & Mendelson 1986؛ Amihud 2002؛ Pástor & Stambaugh 2003). اندازهٔ کوچک (Banz 1981) نماینده‌ای از همین پریمیوم است.
- `size` (منفی ln ارزش بازار)، `amihud` (`mean |r|/ارزش معامله`)، `adv_low`، `turnover_low` (Datar, Naik & Radcliffe 1998)، `zero_days` (Lesmond, Ogden & Trzcinka 1999)، `price_low`.
- **هشدار ظرفیت:** این معیارها همان نمادهایی را انتخاب می‌کنند که هزینهٔ اجرایشان بالاست؛ بنابراین بازده ناخالص آن‌ها بدون مدل اثر بازار (فصل ۶) گمراه‌کننده است. در میز پژوهش، هر سبد با «ارزش معاملات روزانهٔ نمادها نسبت به اندازهٔ سفارش» (ADV) هم گزارش می‌شود.

### ۱۴.۳.۴ ارزش، سود تقسیمی و سرمایه‌گذاری
- `ep` (EPS ۱۲‌ماهه ÷ قیمت، با تعدیل رقیق‌شدگی): Basu (1977)؛ Fama & French (1992). B/P فعلاً نیست: ترازنامه از رهاورد دریافت نمی‌شود (فصل ۴ §۴٫۳).
- `div_yield` (مجموع بازده سود نقدی روز استحقاق در ۲۵۲ روز، از `r_TR − r_PR`): Fama & French (1988).
- `net_issue` (−Δ ln تعداد سهام): Pontiff & Woodgate (2008). **سوگیری شناخته:** افزایش سرمایهٔ جایزه و نقدی در `GetInstrumentShareChange` تفکیک نمی‌شود؛ پس این معیار ترکیبی از انتشار نقدی و تقسیم سهام جایزه است.
- **تورم و ارزش:** در محیط تورمی، دارایی‌های ثابت با تجدید ارزیابی عقب‌تر از ارزش جایگزینی ثبت می‌شوند؛ B/P ایران ارزش‌گذاری را مخدوش می‌کند، E/P کمتر (ولی نه کاملاً) به این مشکل دچار است.

### ۱۴.۳.۵ کیفیت (Quality)
**ایده:** شرکت‌های سودآور، کم‌اهرم و باثبات به‌طور سیستماتیک ارزان‌تر از ارزش ذاتی قیمت‌گذاری می‌شوند (Novy-Marx 2013؛ Asness, Frazzini & Pedersen 2019؛ Piotroski 2000؛ Sloan 1996 برای کیفیت سود).
- از نسبت‌های سالانهٔ رهاورد: `q_roe`، `q_roa`، `q_net_margin`، `q_op_margin`، `q_low_da`، `q_low_de`، `q_current`، `q_asset_turn`، `q_int_cov`، `q_roe_stab`، `q_droe`.
- **محدودیت‌ها:** (۱) تاریخچه فقط از ۱۳۹۹؛ (۲) فقط نمادهای دریافت‌شده؛ (۳) نسخهٔ نهایی نسبت‌ها نه نسخهٔ اعلام‌شدهٔ اولیه؛ (۴) حسابداری تورمی و تجدید ارزیابی ROE و D/E را مخدوش می‌کند؛ (۵) **سوگیری بقا:** شرکت‌هایی که امروز در رهاورد نیستند (حذف‌شده‌ها) داده ندارند.
- جریان نقد عملیاتی و اقلام تعهدی (Accruals) نیازمند صورت جریان وجوه نقد است که دریافت نشده است.

### ۱۴.۳.۶ آنچه پیاده نشد و دلیل
| معیار | دلیل |
|---|---|
| جریان حقیقی/حقوقی (قدرت خریدار حقیقی، ورود پول هوشمند) | داده در فایل‌های قیمتی مخزن نیست (ClientType در TSETMC جداست)؛ از مهم‌ترین معیارهای بومی است و گام بعدی جمع‌آوری است |
| صف خرید/فروش و حجم در صف | نیازمند داده درون‌روزی/دفتر سفارش (فصل ۶) |
| B/P، جریان نقد، Accruals | نبود ترازنامه و صورت جریان وجوه نقد |
| مومنتوم سری زمانی | با هدف انتخاب مقطعی نمی‌خواند؛ برای تخصیص کل پرتفوی است |
| یادگیری ماشین (Gu, Kelly & Xiu 2020) | ridge/FM پیاده شده؛ شبکه/درخت بدون داده بنیادی غنی‌تر از نظر آماری ایمن نیست |

---

## ۱۴.۴ ترکیب معیارها

دو معماری کلاسیک: **یکپارچه (Integrated)**: ابتدا امتیازهای Z ترکیب می‌شوند و بعد پرتفوی از امتیاز ترکیبی ساخته می‌شود؛ **ترکیبی/سبدی (Mixed, sleeves)**: برای هر معیار پرتفوی جدا ساخته و بعد وزن‌ها جمع می‌شوند. ادبیات (Fitzgibbons et al. 2016؛ Bender & Wang 2016؛ Clarke, de Silva & Thorley 2008) نشان می‌دهد سبد یکپارچه معمولاً به‌دلیل جلوگیری از «خنثی شدن» معیارهای ناهمسو (سهام مومنتومی که ارزان نیستند) بازده/ریسک بهتری می‌دهد. میز پژوهش روش یکپارچه را پیاده می‌کند.

| روش (`combine`) | فرمول | استفاده |
|---|---|---|
| `equal` | `S = Σ w_k z_k` با وزن دلخواه کاربر | ساده و مقاوم؛ مبنای مقایسه |
| `rank` | میانگین رتبهٔ درصدی | مقاوم به دم‌های پهن |
| `ic` | `w_k ∝ mean(IC_k)` روی ۳۶ ماه گذشته (علامت‌دار) | تطبیق با تغییر رژیم؛ نویزپذیر |
| `icir` | `w_k ∝ IC_k/σ(IC_k)` | وزن بیشتر به معیار پایدارتر |
| `fm` | وزن = میانگین ۳۶ ماه شیب‌های چندمتغیرهٔ Fama–MacBeth | هم‌خطی را کنترل می‌کند |
| `ridge` | همان با جریمهٔ L2 بیشتر | در معیارهای هم‌خط |

همهٔ وزن‌های تطبیقی فقط از ماه‌های **قبل** از تاریخ ریبالانس می‌آیند (بدون نگاه به آینده). IC ماه j فقط وقتی معلوم است که بازده ماه j بسته شده باشد، یعنی در ریبالانس j+1.

**هشدار هم‌خطی.** معیارهای یک خانواده همبستگی رتبه‌ای بالا دارند (مثلاً `vol_252` و `vol_126` ≈ ۰٫۹۵)؛ ترکیب خانواده‌ها با وزن برابر روی معیارها در عمل خانواده‌ای با تعداد معیار بیشتر را بزرگ‌تر وزن می‌دهد. ماتریس همبستگی معیارها در نمای «معیارها» است و انتخاب معیار برای ترکیب باید از هر خانواده یکی باشد.

---

## ۱۴.۵ الگوریتم‌های انتخاب و وزن‌دهی

الگوریتم‌ها به شش دسته تقسیم می‌شوند؛ جدول پارامترها و مرجع هر الگوریتم در UI (Lab ← ساخت) آمده است.

### ۱۴.۵.۱ دسته‌ای (Sort-based)
- **`quantile`** — G گروه برابر؛ گروه k هم‌وزن (Fama & French 1992). ساده‌ترین؛ برای تشخیص یکنوایی.
- **`topfrac` / `topn`** — بالاترین سهم/تعداد با **بافر**: ورود اگر رتبهٔ درصدی ≤ `entry`، ماندن تا ≤ `exit`. بافر گردش را به‌شدت کم می‌کند (روش استاندارد شاخص‌های MSCI/FTSE). مثال: ورود ۲۰٪ و خروج ۳۰٪.

### ۱۴.۵.۲ امتیازی (Score-based)
- **`score_tilt`**: `w ∝ exp(λ z)` روی همهٔ واجدان؛ λ=۰ هم‌وزن است. پیوسته و بدون مرز مصنوعی پنجک؛ گردش آرام‌تر.
- **`rank_weight`**: `w ∝ max(rank − ۰٫۵, ۰)` (Asness, Moskowitz & Pedersen 2013، نسخهٔ فقط‌خرید).
- **`msci_tilt`**: `w ∝ w_cap · (1+z)` برای z>0 و `w_cap/(1−z)` برای z<0 (Z برش‌خورده در ±۳)، سپس سقف وزن؛ روش شاخص‌های فاکتوری MSCI **[راستی‌آزمایی نشده — جزئیات سقف و ضریب از روش‌نامه باید تطبیق شود]**.

### ۱۴.۵.۳ مبتنی بر ریسک (Risk-based) روی مجموعهٔ برتر
هر یک مجموعهٔ برتر (top fraction با بافر) را انتخاب و فقط **وزن‌ها** را از ریسک می‌گیرد:
- **`inv_vol`**: `w ∝ 1/σ`.
- **`min_var`**: `min w'Σw` با `w ≥ 0`, `Σw=1`, سقف وزن (Clarke, de Silva & Thorley 2006).
- **`max_div`**: بیشینه‌کردن نسبت تنوع `DR = w'σ/√(w'Σw)` (Choueifaty & Coignard 2008).
- **`erc`**: سهم ریسک هر نماد برابر؛ فرمول محدب `min ½ y'Σy − (1/n) Σ ln y_i` و بازنرمال‌سازی (Maillard, Roncalli & Teiletche 2010).
- **`hrp`**: خوشه‌بندی سلسله‌مراتبی با فاصلهٔ `√(½(1−ρ))`، شبه‌قطری‌سازی و تقسیم دوبخشی بازگشتی (López de Prado 2016)؛ بدون وارونه‌سازی Σ.

**چرا ساده‌ترین معمولاً برنده است؟** DeMiguel, Garlappi & Uppal (2009) نشان دادند ۱/N در برابر ۱۴ مدل بهینه‌سازی در نمونهٔ بیرونی به‌سختی شکست می‌خورد، چون خطای برآورد Σ و μ از مزیت نظری بهینه‌سازی بیشتر است. این دلیل استفادهٔ ما از Σ انقباضی و سقف وزن است و دلیل اینکه نتیجهٔ هر الگوریتم بهینه‌ساز باید با «هم‌وزن همان مجموعه» مقایسه شود.

### ۱۴.۵.۴ بهینه‌سازی با قید (Constrained optimization)
**`mvo_te`:** 
`max α'w − (λ/2) w'Σw − τ‖w − w₀‖₁`  s.t. `Σw=1, 0≤w≤w_max, ‖Σ^{½}(w − b)‖ ≤ TE_max`  
با `α = IC · σ · z` (Grinold & Kahn 2000) و `b` پرتفوی مرجع (هم‌وزن واجدان). جملهٔ ℓ₁ هزینهٔ معاملاتی خطی را تقریب می‌زند و گردش را مهار می‌کند (Gârleanu & Pedersen 2013). حل با cvxpy (CLARABEL). برای سرعت و پایداری فقط ۳۵۰ نمادِ نقدشونده‌تر وارد بهینه‌سازی می‌شوند.

### ۱۴.۵.۵ اصطکاک
- **ریبالانس جزئی (`partial = κ`):** `w ← w_drift + κ (w_target − w_drift)`. Gârleanu & Pedersen (2013) نشان می‌دهند وقتی بازده قابل‌پیش‌بینی و هزینه وجود دارد، مسیر بهینه حرکت جزئی به سمت «پرتفوی هدف» است.
- **فاصلهٔ ریبالانس (`rebalance_every`):** هر k ماه؛ ماه‌های میانی فقط رانش.
- **سقف وزن (`max_w`):** تکرارشونده؛ مازاد بین بقیه به نسبت تقسیم می‌شود.

### ۱۴.۵.۶ برآورد کوواریانس
همهٔ الگوریتم‌های ریسکی از Σ یکسان استفاده می‌کنند: **بازدهٔ ۵روزهٔ غیرهم‌پوشان ۵۰۴ روز اخیر** (کاهش اثر معاملات ناهمزمان، چون در بازار کم‌عمق همبستگی روزانه کم‌برآورد می‌شود)، **انقباض Ledoit–Wolf** (Ledoit & Wolf 2004) به‌سمت ماتریس هم‌بستگی ثابت، و تبدیل به مقیاس ماهانه (×۵۲/۱۲). نمونهٔ ~۱۰۰ مشاهده برای ۲۰۰ نماد بدون انقباض شرط‌بندی ناپایدار می‌دهد (نسبت نماد به مشاهده ≥ ۱).

---

## ۱۴.۶ فرایند تحقیق: از ایده تا استقرار

۱. **ثبت پیشین (pre-registration):** پیش از دیدن نتیجه، فهرست معیارها، پنجره‌ها و الگوریتم‌ها تعیین می‌شود؛ تعداد کل آزمایش‌ها (N) برای تصحیح چندگانه ثبت می‌شود. *در این پروژه N همهٔ ترکیب‌های اجراشده در شبکهٔ پژوهش است (§۱۴.۸).*
۲. **IC و Fama–MacBeth** برای هر معیار با خنثی‌سازی صنعتی و بدون آن.
۳. **ترکیب** از هر خانواده بهترین/پایدارترین.
۴. **ساخت** با ۲–۳ الگوریتم ساده و یک بهینه‌ساز.
۵. **آزمون‌های سخت:** DSR، PBO، Reality Check/SPA؛ تقسیم نیم‌نمونه؛ حساسیت به هزینه، تأخیر و جهان (فقط بورس / بورس+فرابورس).
۶. **استقرار** فقط اگر حکم از آستانه‌ها عبور کند (§۱۴.۷٫۵) و ظرفیت (ADV) پذیرفتنی باشد؛ سپس رصد زنده و فهرست اقدام (نمای Plan).

---

## ۱۴.۷ روش‌شناسی ارزیابی آماری

### ۱۴.۷.۱ IC و ICIR
`IC_t = ρ_s(z_{i,t}, r_{i,t+1})` اسپیرمن؛ میانگین، t نیوی‌وست، ICIR؛ **IC چند افقی** (۳، ۶، ۱۲ ماه) برای زوال سیگنال؛ **IC خنثی‌شده** (Z و بازده هر دو منهای میانگین صنعت).

### ۱۴.۷.۲ Fama–MacBeth
هر ماه `r_{i,t+1} = γ_{0t} + γ_{1t} z_{it} + Σ γ_{kt} c_{kit} + ε`؛ شیب میانگین `γ̄₁` = پریمیوم واحد-Z؛ t نیوی‌وست. کنترل‌ها: اندازه و بتا (Fama & French). FM تفاوت اصلی با پنجک‌بندی را نشان می‌دهد: همهٔ مقطع را استفاده می‌کند، نه فقط دم‌ها.

### ۱۴.۷.۳ مرتب‌سازی (Sorts) و یکنوایی
بازده سالانهٔ دهک‌ها (خالص)، **اسپیرمن رتبهٔ دهک با بازده**، تعداد جفت‌های صعودی متوالی و آمارهٔ t تفاوت دهک بالا و پایین. (تست‌های رسمی یکنوایی مانند Patton & Timmermann 2010 پیاده نشده؛ شاخص ما توصیفی است.)

### ۱۴.۷.۴ پایداری و بوت‌استرپ
نیمهٔ اول/دوم نمونه، بازده فعال هر سال شمسی، پنجره‌های ۱۲ ماههٔ غلتان (درصد پنجره‌های مثبت و بدترین)، **بوت‌استرپ ایستای بلوکی** (Politis & Romano 1994؛ بلوک متوسط ۳ ماه) برای فاصلهٔ ۹۵٪ میانگین بازده فعال و احتمال مثبت‌بودن.

### ۱۴.۷.۵ آزمون‌های چندگانه و بیش‌برازش
با حدود N آزمایش، بهترین t به‌طور طبیعی بالاست.
- **آستانهٔ t:** Harvey, Liu & Zhu (2016) با بررسی صدها فاکتور آستانهٔ t ≈ ۳٫۰ را پیشنهاد می‌کنند **[راستی‌آزمایی نشده — عدد از حافظه]**؛ Bonferroni برای N آزمون آستانهٔ `Φ⁻¹(1−α/2N)` را می‌دهد و در UI گزارش می‌شود؛ **BHY** نرخ کشف نادرست را کنترل می‌کند.
- **Deflated Sharpe Ratio** (Bailey & López de Prado 2014): احتمال اینکه Sharpe واقعی مثبت باشد پس از اصلاح برای N آزمایش، چولگی و کشیدگی: `DSR = Φ((SR̂ − SR₀)√(T−1) / √(1 − γ₃SR̂ + ((γ₄−1)/4)SR̂²))` با `SR₀ = √V[SR] ((1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(Ne)))` و γ ثابت اویلر.
- **PBO / CSCV** (Bailey, Borwein, López de Prado & Zhu 2017): نمونه به S بلوک تقسیم می‌شود؛ برای هر ترکیب نیمی-نیمی بهترین استراتژی درون‌نمونه یافته و رتبهٔ آن بیرون‌نمونه سنجیده می‌شود؛ PBO = احتمال اینکه رتبهٔ بیرون‌نمونه زیر میانه باشد. PBO > ۰٫۵ یعنی انتخاب بر پایهٔ بک‌تست از شانس بدتر است.
- **White Reality Check** (2000) و **SPA** (Hansen 2005): آیا بهترین از N استراتژی را می‌توان از مرجع بهتر دانست؟ بوت‌استرپ ایستای ۱۰۰۰ تکراری.

### ۱۴.۷.۶ حکم (Verdict)
قاعدهٔ پیشین، نه پس از دیدن نتیجه:
- **«استقرار»**: |t خالص| ≥ ۳، علامت بازده فعال در هر دو نیمه یکسان، بازهٔ بوت‌استرپ ۹۵٪ صفر را شامل نشود، اسپیرمن دهک‌ها ≥ ۰٫۶.
- **«شاهد ضعیف»**: |t خالص| ≥ ۲ و دو نیمه هم‌علامت.
- **«بدون برتری معنادار»**: در غیر این صورت.
حکم هرگز به‌تنهایی سبد را مجاز نمی‌کند؛ DSR/PBO و ظرفیت نیز باید بررسی شوند.

### ۱۴.۷.۷ پوسیدگی پس از انتشار و رژیم
McLean & Pontiff (2016) نشان دادند بازده ناهنجاری‌ها بعد از انتشار به‌طور محسوس کم می‌شود **[راستی‌آزمایی نشده — درصد دقیق از حافظه]**؛ پس نیم‌نمونهٔ دوم را باید سخت‌گیرانه‌تر خواند. Daniel & Moskowitz (2016) سقوط مومنتوم پس از بحران را مستند کرده‌اند؛ ۱۳۹۷–۱۳۹۹ برای ایران نمونهٔ مشابه (جهش ارز) است.

---

## ۱۴.۸ نتایج تجربی (اجرای ۲۰۲۶-۱۰-۱۷)

> تکمیل پس از اجرای شبکهٔ پژوهش: جدول «باغ‌وحش معیارها» (IC و FM)، مقایسهٔ الگوریتم‌ها، ترکیب‌ها و حکم‌ها.

---

## ۱۴.۹ تصمیم‌ها و توصیه‌ها

> تکمیل پس از ۱۴.۸.

---

## ۱۴.۱۰ محدودیت‌ها و گام‌های بعد

۱. جریان حقیقی/حقوقی و صف خرید/فروش (جمع‌آوری TSETMC).
۲. صورت‌های مالی کامل (ترازنامه، جریان وجوه نقد) و نسخه‌های اولیهٔ اعلام‌شده (کدال).
۳. مدل اجرا برای اندازهٔ سفارش واقعی (فصل ۶): اثر بازار، صف، حد نوسان.
۴. فروش استقراضی عملاً در دسترس نیست؛ لذا همهٔ نتایج فقط‌خرید (long-only) و نسبت به هم‌وزن واجدان‌اند.
۵. بهینه‌سازی با قید صنعتی و نقدشوندگی پویا؛ آزمون سبک‌های ML با داده بنیادی غنی‌تر.

---

## ۱۴.۱۱ مراجع

- Acerbi, C. & Tasche, D. (2002). On the coherence of expected shortfall. *J. Banking & Finance*.
- Amihud, Y. (2002). Illiquidity and stock returns. *J. Financial Markets*.
- Amihud, Y. & Mendelson, H. (1986). Asset pricing and the bid-ask spread. *JFE*.
- Ang, A., Hodrick, R., Xing, Y. & Zhang, X. (2006). The cross-section of volatility and expected returns. *JF*.
- Asness, C., Frazzini, A. & Pedersen, L. (2019). Quality minus junk. *Review of Accounting Studies*.
- Asness, C., Moskowitz, T. & Pedersen, L. (2013). Value and momentum everywhere. *JF*.
- Bailey, D. & López de Prado, M. (2014). The deflated Sharpe ratio. *J. Portfolio Management*.
- Bailey, D., Borwein, J., López de Prado, M. & Zhu, Q. (2017). The probability of backtest overfitting. *J. Computational Finance*.
- Baker, M., Bradley, B. & Wurgler, J. (2011). Benchmarks as limits to arbitrage. *FAJ*.
- Bali, T., Cakici, N. & Whitelaw, R. (2011). Maxing out: stocks as lotteries. *JFE*.
- Banz, R. (1981). The relationship between return and market value of common stocks. *JFE*.
- Barberis, N., Shleifer, A. & Vishny, R. (1998). A model of investor sentiment. *JFE*.
- Barroso, P. & Santa-Clara, P. (2015). Momentum has its moments. *JFE*.
- Basu, S. (1977). Investment performance of common stocks in relation to their price-earnings ratios. *JF*.
- Bender, J. & Wang, T. (2016). Can the whole be more than the sum of the parts? *J. Portfolio Management*.
- Black, F. (1972). Capital market equilibrium with restricted borrowing. *J. Business*.
- Blitz, D. & van Vliet, P. (2007). The volatility effect. *J. Portfolio Management*.
- Blitz, D., Huij, J. & Martens, M. (2011). Residual momentum. *J. Empirical Finance*.
- Boyer, B., Mitton, T. & Vorkink, K. (2010). Expected idiosyncratic skewness. *RFS*.
- Choueifaty, Y. & Coignard, Y. (2008). Toward maximum diversification. *J. Portfolio Management*.
- Clarke, R., de Silva, H. & Thorley, S. (2002). Portfolio constraints and the fundamental law of active management. *FAJ*.
- Clarke, R., de Silva, H. & Thorley, S. (2006). Minimum-variance portfolios in the U.S. equity market. *J. Portfolio Management*.
- Clarke, R., de Silva, H. & Thorley, S. (2008). Portfolio construction and the multifactor… *(عنوان دقیق [تأیید لازم])*.
- Corwin, S. & Schultz, P. (2012). A simple way to estimate bid-ask spreads from daily high and low prices. *JF*.
- Da, Z., Gurun, U. & Warachka, M. (2014). Frog in the pan: continuous information and momentum. *RFS*.
- Daniel, K. & Moskowitz, T. (2016). Momentum crashes. *JFE*.
- Daniel, K., Hirshleifer, D. & Subrahmanyam, A. (1998). Investor psychology and security market under- and overreactions. *JF*.
- Datar, V., Naik, N. & Radcliffe, R. (1998). Liquidity and stock returns: an alternative test. *J. Financial Markets*.
- DeMiguel, V., Garlappi, L. & Uppal, R. (2009). Optimal versus naive diversification. *RFS*.
- Dimson, E. (1979). Risk measurement when shares are subject to infrequent trading. *JFE*.
- Fama, E. & French, K. (1988). Dividend yields and expected stock returns. *JFE*.
- Fama, E. & French, K. (1992). The cross-section of expected stock returns. *JF*.
- Fama, E. & MacBeth, J. (1973). Risk, return and equilibrium. *JPE*.
- Fitzgibbons, S., Friedman, J., Pomorski, L. & Serban, L. (2016). Long-only style investing: don't just mix, integrate. *J. Investing*.
- Frazzini, A. & Pedersen, L. (2014). Betting against beta. *JFE*.
- Gârleanu, N. & Pedersen, L. (2013). Dynamic trading with predictable returns and transaction costs. *JF*.
- Garman, M. & Klass, M. (1980). On the estimation of security price volatilities from historical data. *J. Business*.
- George, T. & Hwang, C.-Y. (2004). The 52-week high and momentum investing. *JF*.
- Grinold, R. & Kahn, R. (2000). *Active Portfolio Management*. McGraw-Hill.
- Gu, S., Kelly, B. & Xiu, D. (2020). Empirical asset pricing via machine learning. *RFS*.
- Hansen, P. (2005). A test for superior predictive ability. *J. Business & Economic Statistics*.
- Harvey, C., Liu, Y. & Zhu, H. (2016). … and the cross-section of expected returns. *RFS*.
- Harvey, C. & Siddique, A. (2000). Conditional skewness in asset pricing tests. *JF*.
- Hou, K., Xue, C. & Zhang, L. (2020). Replicating anomalies. *RFS*.
- Jegadeesh, N. (1990). Evidence of predictable behavior of security returns. *JF*.
- Jegadeesh, N. & Titman, S. (1993). Returns to buying winners and selling losers. *JF*.
- Jensen, T., Kelly, B. & Pedersen, L. (2023). Is there a replication crisis in finance? *JF*.
- Ledoit, O. & Wolf, M. (2004). A well-conditioned estimator for large-dimensional covariance matrices. *J. Multivariate Analysis*.
- Lehmann, B. (1990). Fads, martingales, and market efficiency. *QJE*.
- Lesmond, D., Ogden, J. & Trzcinka, C. (1999). A new estimate of transaction costs. *RFS*.
- López de Prado, M. (2016). Building diversified portfolios that outperform out of sample. *J. Portfolio Management*.
- Maillard, S., Roncalli, T. & Teiletche, J. (2010). The properties of equally weighted risk contribution portfolios. *J. Portfolio Management*.
- McLean, D. & Pontiff, J. (2016). Does academic research destroy stock return predictability? *JF*.
- Moskowitz, T. & Grinblatt, M. (1999). Do industries explain momentum? *JF*.
- Newey, W. & West, K. (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica*.
- Novy-Marx, R. (2012). Is momentum really momentum? *JFE*.
- Novy-Marx, R. (2013). The other side of value: the gross profitability premium. *JFE*.
- Parkinson, M. (1980). The extreme value method for estimating the variance of the rate of return. *J. Business*.
- Pástor, L. & Stambaugh, R. (2003). Liquidity risk and expected stock returns. *JPE*.
- Patton, A. & Timmermann, A. (2010). Monotonicity in asset returns. *JFE*.
- Piotroski, J. (2000). Value investing: the use of historical financial statement information to separate winners from losers. *J. Accounting Research*.
- Politis, D. & Romano, J. (1994). The stationary bootstrap. *JASA*.
- Pontiff, J. & Woodgate, A. (2008). Share issuance and cross-sectional returns. *JF*.
- Rogers, L. & Satchell, S. (1991). Estimating variance from high, low and closing prices. *Annals of Applied Probability*.
- Scholes, M. & Williams, J. (1977). Estimating betas from nonsynchronous data. *JFE*.
- Sloan, R. (1996). Do stock prices fully reflect information in accruals and cash flows about future earnings? *The Accounting Review*.
- Sortino, F. & Price, L. (1994). Performance measurement in a downside risk framework. *J. Investing*.
- White, H. (2000). A reality check for data snooping. *Econometrica*.
- Yang, D. & Zhang, Q. (2000). Drift-independent volatility estimation based on high, low, open and close prices. *J. Business*.
