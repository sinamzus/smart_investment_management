# ۱۰ — منابع، پارامترهای نیازمند راستی‌آزمایی و تصمیم‌های باز

## ۱۰.۱ تصمیم‌های گرفته‌شده

| تصمیم | تاریخ |
|-------|-------|
| فاکتورهای هدف: Momentum، Min Vol، Quality (برگرفته از سه صندوق فاکتوری بزرگ iShares)؛ فهرست ۷ فاکتور کنار گذاشته شد | ۲۰۲۶-۱۰-۱۵ |
| مراجع اصلی: شاخص کل رسمی و شاخص کل هم‌وزن رسمی | ۲۰۲۶-۱۰-۱۵ |
| مخزن‌ها جدا؛ برداشتن کد جمع‌آوری TSE مجاز | ۲۰۲۶-۱۰-۱۵ |
| سند همیشه همراه تغییر روش به‌روز شود (`CLAUDE.md`، `CHANGELOG.md`) | ۲۰۲۶-۱۰-۱۵ |
| تاریخ واقعی پرداخت سود: از نامه‌های متن‌دار ن-۱۳ کدال (بدون OCR جدید) با تاریخ مؤثر = سجامی؛ مدل‌ها از توزیع تجربی تأخیر استفاده می‌کنند نه L = ۹۰ ثابت؛ تاریخ پرداخت از کدال ن-۱۳ و رونوشت کارگزاری فارابی (۷۶۶ رویداد)، با وزن جریان سود شاخص؛ رهاورد۳۶۵ کنار (DPS پریمیوم) (7f) | ۲۰۲۶-۱۰-۱۷ |

## ۱۰.۱.۱ تصمیم‌های باز (نیازمند پاسخ شما)

1. **اهداف کمّی:** حد پذیرش TE، گردش ماهانه/سالانه، ظرفیت هدف (AUM)، افق نگهداری.
2. **قیود مقرراتی صندوق** (سقف ناشر، مالکیت، ترکیب): متن اساسنامه/امیدنامه مرجع.
3. **ساختار کارمزد واقعی نهاد:** جدول کارمزد و تخفیف‌های توافقی با کارگزار، مالیات برای هر ابزار.
4. **دسترسی به مشتقه:** آتی/اختیار سهام و شاخص.
5. **مرجع بازده بدون ریسک** و روش محاسبه بازده واقعی (CPI/ارز مرجع).
6. **محدودهٔ داده تاریخی:** از چه سالی بک‌تست؟
7a. **تأیید ماهیت نمادهای رقم‌دار** («سخزر3» و مشابه) و فهرست دقیق نمادهای شاخص هم‌وزن رسمی (فقط بورس؟ شامل صندوق‌ها؟) از بورس.
7f. **تاریخ واقعی پرداخت سود نقدی (حل‌شده در بخش اصلی؛ تکمیل پوشش باز):** ماکت سرمایه‌پذیر (فصل ۳ §۳٫۵) اکنون با **توزیع واقعی تأخیر** (۷۶۶ رویداد کدال + فارابی؛ ۳۳۵ تا با روز استحقاق و وزن شاخص؛ میانگین وزنی ۵۷ روز برای K و ۷۸ برای EW) کار می‌کند؛ هزینه ≈ ۰٫۵۵٪ در سال برای K (با L = ۹۰ ثابت ≈ ۰٫۹۱٪). **وضعیت (۲۰۲۶-۱۰-۱۷):** بخش اصلی حل شد؛ تکمیل پوشش (سال‌های قدیمی‌تر، جدول سپرده‌گذاری مرکزی) باز است. **یافته‌های کدال (۲۰۲۶-۱۰-۱۶، از اجرای probe روی سیستم کاربر):** (۱) API جست‌وجو `search.codal.ir/api/search/v2/q` کار می‌کند (پاسخ JSON با `Letters`، `LetterCode`، `Url`، `HasHtml`، `HasAttachment`). (۲) نوع نامه‌ها: `LetterType=30` = «زمان‌بندی پرداخت سود» (ن-۱۳)، `LetterType=20` = «تصمیمات مجمع عمومی عادی سالیانه» (ن-۵۲). (۳) تصمیمات مجمع HTML ساختاریافته دارد: `SessionDate` (تاریخ مجمع) و «سود نقدی هر سهم (ریال)» — مثلاً وبملت ۱۴۰۴: مجمع ۱۴۰۵/۰۴/۳۱، ۴۶ ریال؛ **ولی تاریخ پرداخت در آن نیست.** (۴) تنها نمونهٔ دیده‌شدهٔ ن-۱۳ فقط پیوست دارد (`Attachment.aspx`، `HasHtml=false`)؛ استخراج تاریخ پرداخت ممکن است نیازمند خواندن PDF/Excel با قالب‌های متفاوت باشد — **هنوز معلوم نیست.** (۵) **محدودیت نرخ:** حدود ۱۳۰ درخواست با فاصلهٔ ۰٫۴ ثانیه IP کاربر را برای مدت طولانی به 429 و قطع اتصال برد. قاعدهٔ کار: `--collect` با فاصلهٔ ≥ ۸ ثانیه، ذخیرهٔ هر فایل یک بار (قابل‌ادامه) و **توقف فوری روی 429** (تکرار، مسدودی را طولانی‌تر می‌کند). **اجرای `--collect 30 --years 5` (۴۸۲ درخواست با فاصلهٔ ۸ ثانیه، بدون 429) انجام شد:** ۱۶۲ نامهٔ تصمیمات مجمع و ۲۲۸ نامهٔ زمان‌بندی پرداخت سود برای ۳۰ نماد بزرگ. **اعتبارسنجی متقاطع:** سود هر سهم مصوب مجمع در کدال با تعدیل قیمت TSETMC (U − A در `price_adjust.csv`) در **۷۶ از ۷۶** مورد قابل تطبیق دقیقاً برابر است و تعدیل ۰ تا ۵ روز بعد از تاریخ مجمع است ⇒ لایهٔ دادهٔ سود نقدی سازگار است. (تاریخ مجمع باید از متن «زمان و محل برگزاری … مورخ» خوانده شود؛ فیلد پنهان `SessionDate` مال مجمع دیگری است.) **همهٔ ۲۲۸ نامهٔ ن-۱۳ فقط پیوست دارند** (`DownloadFile.aspx?id=…`)؛ گام بعد `--attachments` (≈ ۳۰ دقیقه) و سپس استخراج تاریخ پرداخت از فایل‌ها. **پیوست‌ها رسید (۲۱۹ PDF، ۱۵ تصویر):** فقط حدود ۶۵ PDF متن دارند و بقیه اسکن‌شده‌اند. مسیر OCR به تصمیم مالک پروژه **متوقف** شد (فقط ۱۸ متن OCR که پیش از آن در کش مانده بود استفاده می‌شود و با method=ocr علامت دارد). **اجرای `tools/parse_dividend_payments.py` (۲۰۲۶-۱۰-۱۷، بدون OCR جدید):** از ۲۳۹ پیوست ۷۶ تا متن PDF و ۱۸ تا متن OCRِ کش دارند (۹۴)؛ سال مالی و تاریخ انتشار هر نامه از *عنوان* نامه در `list_30.json` می‌آید (نه از متن)، تاریخ مجمع/DPS از `codal_agm.csv`، روز استحقاق از تعدیل TSETMC (U − A = DPS). تاریخ‌ها از متن (نوع ۱۴۰۴/۰۸/۲۳ یا «۵ مرداد ۱۴۰۵») با فیلتر بازهٔ مجمع+۲ تا مجمع+۴۰۰ روز، حذف تاریخ مجمع و سربرگ نامه، و حذف خط‌های مطالبات سنواتی گرفته می‌شود؛ گروه سهامدار از کلیدواژهٔ همان خط و دو خط مجاور. **نتیجه: ۳۶ از ۷۴ رویداد سود نقدی (۱۶ نماد) تاریخ سجامی دارند:** تأخیر از استحقاق میانه ۴۳، میانگین ۶۰، چارک‌ها ۱۳ تا ۹۴، بازه ۰ تا ۲۳۲ روز؛ حقوقی میانه ۱۱۶، غیرسجامی ۷۸. **تصمیم:** تاریخ مؤثر برای صندوق = تاریخ سجامی (تاریخ «صندوق» جدا از جدول‌های pdftotext پرحاشیه است؛ lag_fund به‌عنوان حساسیت می‌ماند)؛ ماکت SIM، Dividend Lab (گزینهٔ «توزیع واقعی تأخیر») و تجزیهٔ پرتفوی صندوق‌ها از این توزیع استفاده می‌کنند و L = ۹۰ ثابت فقط سناریوی حساسیت است.
**یافتهٔ منفی (اصلاح پیشنهاد قبلی):** برگهٔ «درآمد سود سهام» در صورت‌وضعیت پورتفوی صندوق‌ها *تاریخ دریافت* نمی‌دهد؛ درآمد در تاریخ مجمع (ستون «تاریخ تشکیل مجمع»، تعداد سهام متعلقه در آن روز، DPS) به‌صورت تعهدی شناسایی می‌شود و «هزینهٔ تنزیل» فقط تنزیل مطالبه است؛ برگهٔ مطالبات سود سهام هم در فایل نیست. پس از این منبع تاریخ پرداخت درنمی‌آید.
**باز (تکمیل پوشش):** (الف) پوشش وزنی جریان سود «كل» با تاریخ پرداخت: ۲۰۲۳ ۱۴٪، ۲۰۲۴ ۳۲٪، ۲۰۲۵ ۵۲٪، ۲۰۲۶ ۴۹٪ (`dividend_payment_coverage.csv`)؛ فارابی بیشتر ۱۴۰۴–۱۴۰۵ را دارد؛ ۴۳۱ رویداد از ۷۶۶ تا روز استحقاق ندارند (خارج از پانل ۴۲۹ نماد یا استحقاق دیرتر از ۱۲ روز)؛ (ب) تفکیک گروه‌ها در جدول‌ها پرحاشیه است؛ (ج) **رهاورد۳۶۵ منبع نیست (۲۰۲۶-۱۰-۱۷، گزارش مالک پروژه):** لیست DPS آن فقط برای کاربر پریمیوم است. ضبط شبکه نشان داد سایت صفحه‌های `/dps` و `/asset/<id>/dps` و API زیر `/api/v2/` دارد، ولی محتوایی از آن دیده نشد. **(د) منبع جایگزین پیدا و اجرا شد (جست‌وجوی منابع، ۲۰۲۶-۱۰-۱۷): سایت پشتیبانی کارگزاری فارابی (`help.irfarabi.com`)** نامه‌های ن-۱۳ کدال را برای *همهٔ نمادها* به جدول/متن HTML تبدیل می‌کند: ۱۵۹ پست در دستهٔ «سود نقدی» (۱۴۰۲ تا ۱۴۰۵؛ پست‌های ماهانه/هفتگی با ستون‌های نماد، سجامی/غیرسجامی، زمان مجمع، DPS، تاریخ واریز، نحوهٔ پرداخت، و پست تجمیعی به‌روزشونده برای ۱۴۰۴–۱۴۰۵). API عمومی وردپرس آن بدون پریمیوم و بدون OCR کل محتوا را می‌دهد (۴–۵ درخواست). `tools/fetch_farabi_dividends.py` و `tools/parse_farabi_dividends.py` نوشته شدند (اجرا روی دادهٔ واقعی: ۲۰۵ پست، ۱۴۸۱ ردیف، ۶۱۳ نماد، ۷۴۷ ردیف سجامی با تاریخ؛ `tools/merge_dividend_payments.py` آن‌ها را با کدال ادغام و به روز استحقاق و وزن شاخص وصل می‌کند ← `dividend_payment_events.csv`: ۷۶۶ رویداد، ۳۳۵ تا با استحقاق/وزن). **اعتبارسنجی با کدال:** از ۱۰ رویداد مشترک ۶ دقیقاً یکی، ۲ تا ≤ ۷ روز، ۲ تا خطای پارسر کدال (فارابی درست). **نتیجه:** میانهٔ بدون وزن ۹۶ روز ولی وزن‌شده با جریان سود «كل» ۵۷ و هم‌وزن ۷۸ روز. ملاحظات: بعضی ردیف‌ها فقط «شهریور ماه» دارند (دقت ±۱۵ روز؛ pay_kind=month) یا «از …»؛ منبع رونوشت شخص ثالث از کدال است [راستی‌آزمایی نشده] — با ۳۶ رویداد کدال خودمان اعتبارسنجی متقاطع می‌شود. **منابع دیگر بررسی‌شده:** (۱) سپرده‌گذاری مرکزی (`csdiran.ir`) جدول «گزارش‌های توزیع سود» (ناشر، نماد، تاریخ) در صفحهٔ اول دارد و گزارش هفتگی پرداخت از طریق سجام را با نام ناشران منتشر می‌کند — تاریخ *واقعی واریز* (هفته) نه برنامه؛ جدول با جاوااسکریپت بارگذاری می‌شود و آدرس داده هنوز دیده نشده (ضبط شبکهٔ مرورگر لازم است: `tools/fetch_rahavard_dividends.py --capture csdi --goto https://csdiran.ir/`)؛ (۲) رهاورد۳۶۵: صفحه‌های `/reports/<id>` آینهٔ نامه‌های کدال (از جمله «سجام | زمانبندی پرداخت سود») به‌صورت تصویر است (`/api/v2/report/images/<id>/file`) ⇒ OCR لازم؛ (۳) نبض‌بورس و خبرگزاری‌ها (گزارش‌های هفتگی/خوش‌حساب‌ترین نمادها) ثانویه‌اند. **تصمیم: تکمیل پوشش از فارابی (و در صورت لزوم جدول سپرده‌گذاری مرکزی) پیگیری می‌شود؛** تا آن موقع مدل‌ها از ۳۶ رویداد کدال و توزیع تجربی استفاده می‌کنند. ابزار `tools/fetch_rahavard_dividends.py` (ضبط پاسخ‌های شبکه با مرورگر یا HAR) برای داده‌های دیگرِ رهاورد نگه داشته شد.
7e. **باقی‌مانده پس از جهان کامل و قاعدهٔ ۸:** هم‌وزن TR-type ۴٫۵٪ کمتر و PR-type ۴٫۹٪ بیشتر از رسمی؛ صنایع ۳۱ و ۲۳ و ۵۴ **حل شد** (خطای مقیاس/تیغهٔ سری رسمی؛ ← فصل ۳ §۳٫۴)؛ صنعت ۶۷ و ۳۹ هم بعد از دریافت قیمت «بورس» و «وصندوق» و رفع باگ عضویت حل شد؛ صنایع ۱۷، ۳۸ و ۵۸ با سهام حذف‌شده حل شدند (TE ۱۰٫۱←۰٫۱، ۴٫۰←۰٫۲، ۳٫۱←۱٫۱٪)؛ صنایع ۵۶/۳۹/۴۰/۷۳ با تاریخچهٔ عوض‌شدن صنعت شرکت‌ها حل شدند (۵۶: ۴٫۲←۰٫۷٪؛ `fit_sector_history.py`)؛ باقی‌مانده فقط ۳۴ خودرو (۳٫۲٪؛ فرضیه‌های تأخیر رویداد/سهام شناور/حذف توقف/فرابورس رد شد؛ خطای پراکنده) و ۴۹/۷۰/۴۲ (≈۱٫۶–۲٫۲٪)؛ سهام واقعاً حذف‌شده (غیر عضو فعلی شاخص) هنوز بررسی نشده.
7d. **سهام خارج از MarketWatch (حل‌شده):** پالایشگاه‌ها با `--search` پیدا شدند (جست‌وجو کار می‌کند) و ناهنجاری ۲۰۱۵-۰۳-۱۷ را حل کردند. هنوز باید با `fetch_index_constituents.py --add-missing` همهٔ سهام جاافتاده (حداقل ده‌ها در ۷ صنعت بدون نماد) پیدا شود؛ سپس رانش ۱٪ سالانهٔ «شاخص كل» دوباره بررسی شود.
7c. **روش‌نامهٔ رسمی ریبالانس شاخص هم‌وزن:** داده با «فصلی» می‌خواند (بهترین: آغاز فصل شمسی)؛ تأیید قطعی و قاعدهٔ ورود نمادهای جدید لازم است. (شاخص‌های «كل» و «هم‌وزن» هر دو در حد ~۱ تا ۲٪ سطح بازتولید شدند: فصل ۳.)
7b. **جدول رویدادهای سرمایه‌ای** (سود نقدی با تاریخ استحقاق/پرداخت و مبلغ، افزایش سرمایه) — **منبع اصلی خود TSETMC** (`tools/fetch_corporate_actions.py`)؛ کدال فقط برای تکمیل/اعتبارسنجی — لازم برای توضیح فرق سطح تجمعی بازسازی‌شده با «بازده کل» رسمی و برای بازسازی شاخص ارزش‌وزن (همچنین **تعداد سهام تاریخی** — منبع پیدا شد: `GetInstrumentShareChange`؛ دریافت همهٔ نمادها منتظر `--collect-shares`).
7. **روش‌نامهٔ رسمی شاخص‌ها** — سری‌های روزانهٔ پنج شاخص دریافت و در `data/indices/` است (فصل ۳، بخش ۳.۴). هنوز باید تأیید شود که «شاخص كل» و «هم‌وزن» سود نقدی را لحاظ می‌کنند، و علت روزهای تخت (مه ۲۰۲۶) و ردیف‌های پنجشنبه/جمعه روشن شود. TEDPIX از TSETMC معیوب است؛ منبع جایگزین لازم است.
7g. **NAV صندوق‌های شاخصی (باز؛ نیازمند اجرا روی سیستم کاربر):** `python tools/fetch_index_funds.py --log funds_log.txt` سپس commit/push. خروجی: `data/funds/funds.csv`، `nav_<نماد>.csv` (ابطال، صدور، آماری، خالص دارایی)، `price_<نماد>.csv.gz`، و پاسخ‌های خام در `data/raw/funds/`. مسیرهای فیپیران و سایت رایان صندوق‌ها از حافظه‌اند [راستی‌آزمایی نشده]؛ اگر خودکار جواب نداد، پاسخ خام را بفرستید یا با `--site نماد=آدرس` سایت صندوق را بدهید. بعد از دریافت، `python tools/build_ui_funds.py` نمای Index Funds را پر می‌کند. **اجرای اول (۲۰۲۶-۱۰-۱۷، سیستم کاربر):** قیمت بازار هر ۸ صندوق رسید (۲۲۳ تا ۲۸۲۴ روز). نام شاخص ۳۰ شرکت تأیید شد: «شاخص 30 شرکت بزرگ». **NAV نیامد:** اتصال به `fund.fipiran.ir` در دست‌دادن TLS قطع شد (`SSLEOFError`) — مثل TSETMC در ابتدا، یعنی میزبان در پراکسی/فیلتر سیستم کاربر باید استثنا شود. TSETMC فقط NAV لحظه‌ای را می‌دهد (`GetETFByInsCode`: `pRedTran` ابطال، `pSubTran` صدور) نه تاریخچه. گام بعد: `python tools/fetch_index_funds.py --diag --log diag_funds.txt` (چند ثانیه؛ میزبان‌ها و مسیرهای محتمل تاریخچهٔ NAV را آزمون می‌کند)، پس از استثنا کردن `fund.fipiran.ir` و `fipiran.ir`.
**یافتهٔ دور دوم (`--diag`/`--diag2`):** `fund.fipiran.ir` اصلاً resolve نمی‌شود؛ سایت واقعی `fipiran.ir` است و بستهٔ جاوااسکریپت آن `baseURL="/services"` دارد. مسیرهای صندوق از همان بسته استخراج شد: `GET /services/fund/fundlistbrief` و `fundlistissue` (فهرست با `regNo`)، `GET /services/efficiency/fundefficiencylist?showAll=true&regNos=<regNo>` (سری روزانه با کلیدهای `dailyEfficiency` و `priceEfficiency`)، `GET /services/chart/fundefficiencychart?regno=&showAll=true&groupId=`، و `GET /services/fund/getfundIssue?regno=&date=YYYY-MM-DD` (NAV ابطال/صدور یک روز). **یعنی فیپیران سطح NAV تاریخی را به‌صورت سری نمی‌دهد؛ بازده روزانهٔ NAV را می‌دهد** و `fetch_index_funds.py` همین را می‌گیرد (`ret_daily`). مقیاس (درصد یا کسر) خودکار تشخیص داده می‌شود و تعریف دقیق `dailyEfficiency` (NAV ابطال یا آماری؟) باید با پاسخ خام تأیید شود [تأیید لازم]. پریمیوم بازار نسبت به NAV در این مسیر محاسبه نمی‌شود (نیازمند سطح NAV است). TSETMC قدیمی `ETFHistory.aspx` فقط پوستهٔ خالی است و مسیرهای حدسی `cdn.tsetmc.com/api/Fund/*History` ۴۰۴ دادند.
**اجرای سوم (۲۰۲۶-۱۰-۱۷):** `chart/fundefficiencychart` جواب داد (`fundefficiencylist` 401/timeout). ۵ از ۸ صندوق NAV (بازده روزانه) گرفتند؛ نتایج در فصل ۳ §۳٫۶. **تطبیق نام اشتباه بود** (هوشمند با «بازارگردانی هوشمند آبان» که صندوق دیگری است؛ کیان و وبازار پیدا نشدند)؛ حالا نام فیپیران ثابت است (`FIPIRAN_NAMES`) و «مشترک شاخصی کار آفرین» (صدور/ابطال، بدون نماد) اضافه شد. **اجرای چهارم:** کیان، وبازار، هوشمند NAV گرفتند ⇒ ۸ صندوق بورسی کامل. «کارآفرین» (صدور و ابطال) در تلاش دوم آمد ⇒ ۹ صندوق. گام‌های بازبینی (تعریف `dailyEfficiency`، پرتفوی ماهانهٔ صندوق‌ها، مرجع هم تراز و فیروزه) باز است.
7h. **پرتفوی ماهانهٔ صندوق‌های شاخصی از کدال (در جریان؛ نیازمند اجرا روی سیستم کاربر):** **probe کاردان انجام شد (۲۰۲۶-۱۰-۱۷):** نامهٔ ماهانه «صورت وضعیت پورتفوی صندوق سرمایه گذاری دوره ۱ ماهه منتهی به …» (۲۳۰ نامه از ۱۳۹۴؛ بدون HTML؛ پیوست Excel) با برگه‌های «سهام» (نام شرکت، تعداد، قیمت، **درصد به کل دارایی‌ها**)، «سپرده»، «درآمد سود سهام» (سود هر سهم در ماه) و غیره. `tools/parse_fund_portfolio.py` برگهٔ سهام را به `data/funds/holdings_<نماد>.csv` تبدیل می‌کند (تطبیق نام کدال به نماد با نام TSETMC و `ALIASES`). **اجرای ۲۴ ماه (۲۰۲۶-۱۰-۱۷):** پرتفوی ۸ صندوق رسید؛ parser برای قالب‌های مختلف (xlsx/xls/zip، سرستون، واحد کسر یا درصد، تطبیق نام با قیمت) تکمیل شد و نتایج در فصل ۳ §۳٫۶ است: تأخیر سود ≤ ۰٫۳٪ از خطا، صندوق‌ها نمونه‌ای از شاخص‌اند (۳۹ تا ۳۴۰ سهم). **کارآفرین (صدور و ابطال): نماد کدال پیدا نشد** — `--find` با ۲۱ شکل نام (مشترک/شاخصی/پسوند ۱ تا ۳/…) همه Total=0 داد؛ کدال جست‌وجوی Symbol را دقیق انجام می‌دهد و این صندوق احتمالاً با نماد بورسی ثبت نشده. راه‌حل: نماد یا آدرس صفحهٔ شرکت را از codal.ir (کادر جست‌وجو) بدهید، یا پرتفوی ماهانه را از سایت خود صندوق (سامانهٔ رایان) بگیرید؛ تا آن موقع کارآفرین فقط تحلیل NAV دارد. **حل مسیر (۲۰۲۶-۱۰-۱۷، از ضبط مرورگر کاربر):** کارآفرین صندوق مشترک صدور و ابطال بدون نماد بورسی است (مشترک شاخصی کار آفرین، کد TSETMC سایت ۱۰۸۳۵، `fundCode=KBF3`، مدیر کارگزاری بانک کارآفرین، شروع ۱۳۸۹/۱۲/۲۲). سایت خودش (`karafarinindexfund.ir`، پلتفرم رایان‌همافزا) API عمومی دارد: NAV روزانهٔ صدور/ابطال/آماری (`navPerShare`، `nav`، `dailyNav`)، ساختار دارایی روزانه به تفکیک سهام/سپرده/… (`dailyAssetStructure`)، و فهرست ۲۵۶ گزارش (`articles/financialReport`) که ۱۰۶ تای آن *صورت وضعیت پرتفوی* ماهانه به‌شکل PDF است (`/FundData/Articles/<شناسه>.pdf`؛ دورهٔ مالی صندوق روز ۲۱ هر ماه تمام می‌شود). ضبط کدال نشان داد صندوق در جست‌وجوی کدال نماد ندارد. **انجام شد (۲۰۲۶-۱۰-۱۷):** ۳۶ PDF دریافت شد (متنی؛ OCR لازم نبود) و `tools/parse_karafarin_portfolio.py` آن‌ها را به `holdings_کارآفرین.csv` تبدیل کرد (۳۶ ماه از ۱۴۰۲/۰۷/۲۱ تا ۱۴۰۵/۰۶/۲۱؛ سهام میانگین ۹۰٪ دارایی؛ ≈ ۶۰ نماد؛ ۹۹٫۵٪ وزن تطبیق‌یافته؛ حق‌تقدم و اختیار معامله ناشناخته می‌ماند). نتیجهٔ تجزیه: ترکیب پرتفو ۱۸٪، نقد ۱۱٪، تأخیر سود ۰٫۱٪، باقیمانده ۷۱٪ — هم‌سو با بقیهٔ صندوق‌ها. **باز:** ۷۰ پرتفوی قدیمی‌تر (۲۰۱۸ تا ۲۰۲۳) هنوز دریافت نشده (`--n 106`)؛ حق‌تقدم‌ها بی‌نماد. **فیروزه حل شد** (ردیف‌های «نقل از/به صفحه» و ستون درصد کهنه). باز: پرتفوی کارآفرین (نماد کدال معلوم نیست؛ `python tools/fetch_fund_portfolio.py --find "مشترک شاخصی کار آفرین" --log find_karafarin.txt`، سپس `--collect 24 --symbols <نماد>`)، و تطبیق ۲۴۳ نام باقیمانده (`data/funds/holdings_unmatched.csv`). **نخستین یافته (۲ ماه کاردان، شهریور ۱۴۰۵ و مرداد):** فقط **۳۸ سهم** و ≈ ۹۷٪ سرمایه‌گذاری‌شده در سهام، در حالی که «شاخص كل» بیش از ۴۰۰ عضو دارد ⇒ صندوق شاخص را نمونه‌ای از سهام می‌خرد، که با TE ۶–۹٪ جور است؛ برای تأیید به ماه‌های بیشتر و صندوق‌های دیگر نیاز است. **گام بعد:** `python tools/fetch_fund_portfolio.py --collect 24 --log collect_port.txt` (۸ صندوق × ۲۴ ماه × ۲ درخواست با فاصلهٔ ۸ ثانیه ≈ یک ساعت؛ قابل‌ادامه؛ روی 429 می‌ایستد)، سپس `python tools/parse_fund_portfolio.py` و `python tools/build_ui_funds.py`، و push. شرح قبلی: برای جداکردن «ترکیب پرتفو» از «زمان‌بندی سود» (فصل ۳ §۳٫۶). آزمون داده‌محور بدون پرتفو نشان داد فاصلهٔ پرداخت سود < ۵٪ واریانس خطا را توضیح می‌دهد؛ ریشه باید در پرتفوی واقعی، NAV یا کارمزد باشد. گام‌ها: (۱) `python tools/fetch_fund_portfolio.py --probe کاردان --log probe_port.txt` (فهرست نامه‌ها، گروه LetterCode، نمونهٔ HTML/پیوست) و push؛ (۲) من parser می‌نویسم (خروجی `data/funds/holdings_<نماد>.csv`: date,symbol,weight_pct)؛ (۳) `python tools/fetch_fund_portfolio.py --collect 12` برای هر ۸ صندوق؛ (۴) `python tools/build_ui_funds.py`. قاعدهٔ کدال: فاصلهٔ ۸ ثانیه، توقف روی 429.
8. **پایگاه داده اجرایی** این مخزن (SQLite/Parquet/Postgres) و محل اجرای جمع‌آوری (TSETMC از IP دیتاسنتر مسدود است، طبق یادداشت مخزن دیگر).

## ۱۰.۲ پارامترهای نیازمند راستی‌آزمایی [تأیید لازم]

این‌ها در سند به‌صراحت بدون عدد قطعی آمده‌اند و باید از منابع رسمی تکمیل شوند:

| موضوع | مرجع پیشنهادی | تاریخ‌دار؟ |
|-------|----------------|------------|
| جدول کارمزدها (کارگزاری، بورس، سپرده‌گذاری، نظارت) به تفکیک ابزار و بازار | اطلاعیه‌های سازمان بورس و شرکت بورس؛ قرارداد کارگزاری | بله |
| مالیات فروش سهام، صندوق، حق تقدم | قانون مالیات‌های مستقیم و بخشنامه‌ها | بله |
| حدود نوسان قیمت روزانه و تغییرات | اطلاعیه‌های شرکت بورس | بله |
| قواعد حراج گشایش/پایانی و تعیین قیمت پایانی | دستورالعمل معاملات | بله |
| سیکل تسویه (T+n) | شرکت سپرده‌گذاری | بله |
| قاعده تاریخ استحقاق سود و پرداخت، تعدیل قیمت | دستورالعمل اجرایی ناشران؛ شرکت بورس | بله |
| قاعده تعدیل قیمت افزایش سرمایه/حق تقدم | شرکت بورس | بله |
| محاسبه شاخص کل، هم‌وزن، بازده نقدی، آزاد شناور | روش‌نامه‌های شرکت بورس | بله |
| ضوابط ترکیب دارایی صندوق‌های سرمایه‌گذاری | دستورالعمل‌های سازمان بورس | بله |
| مزایای ابزارهای صندوقی، بازارگردانی | همان | بله |
| فروش استقراضی و ابزارهای معادل | دستورالعمل‌ها | بله |

## ۱۰.۳ کارهای بعدی در حوزهٔ ادبیات

1. **مرور سیستماتیک ادبیات فارسی** (مدل‌های فاما-فرنچ، حرکت، نقدشوندگی، صندوق‌های شاخصی/ETF در ایران) با ارزیابی روش‌شناسی هر مقاله.
2. **مطالعهٔ روش‌نامه‌های شاخص‌های رسمی بورس و فرابورس** و ثبت تفاوت‌ها با استاندارد جهانی.
3. **مطالعهٔ ادبیات «نبود فروش استقراضی» و آنومالی‌ها** (Miller 1977؛ Stambaugh, Yu & Yuan 2012) برای تفسیر نتایج Long-only.
4. **مطالعهٔ موردی صندوق‌های شاخصی موجود** در ایران و خارج از آن (ترکیب، کارمزد، TE).

## ۱۰.۴ کتاب‌شناسی (به ترتیب موضوعی)

### الف) مبانی و فاکتورها
- Sharpe, W. (1964). Capital asset prices. *Journal of Finance*.
- Fama, E. & French, K. (1992). The cross-section of expected stock returns. *Journal of Finance*.
- Fama, E. & French, K. (1993). Common risk factors in the returns on stocks and bonds. *Journal of Financial Economics*.
- Fama, E. & French, K. (2015). A five-factor asset pricing model. *Journal of Financial Economics*.
- Fama, E. & French, K. (2012). Size, value, and momentum in international stock returns. *Journal of Financial Economics*.
- Carhart, M. (1997). On persistence in mutual fund performance. *Journal of Finance*.
- Jegadeesh, N. & Titman, S. (1993). Returns to buying winners and selling losers. *Journal of Finance*.
- Asness, C., Moskowitz, T. & Pedersen, L. (2013). Value and momentum everywhere. *Journal of Finance*.
- Frazzini, A. & Pedersen, L. (2014). Betting against beta. *Journal of Financial Economics*.
- Ang, A., Hodrick, R., Xing, Y. & Zhang, X. (2006). The cross-section of volatility and expected returns. *Journal of Finance*.
- Novy-Marx, R. (2013). The other side of value: the gross profitability premium. *Journal of Financial Economics*.
- Asness, C., Frazzini, A. & Pedersen, L. (2019). Quality minus junk. *Review of Accounting Studies*.
- Hou, K., Xue, C. & Zhang, L. (2015). Digesting anomalies: an investment approach. *Review of Financial Studies*.
- Amihud, Y. (2002). Illiquidity and stock returns. *Journal of Financial Markets*.
- Pástor, Ľ. & Stambaugh, R. (2003). Liquidity risk and expected stock returns. *Journal of Political Economy*.
- Daniel, K. & Moskowitz, T. (2016). Momentum crashes. *Journal of Financial Economics*.
- Barroso, P. & Santa-Clara, P. (2015). Momentum has its moments. *Journal of Financial Economics*.
- Israel, R. & Moskowitz, T. (2013). The role of shorting, firm size, and time on market anomalies. *Journal of Financial Economics*.
- Lewellen, J. (2015). The cross-section of expected stock returns. *Critical Finance Review*.
- Fama, E. & MacBeth, J. (1973). Risk, return, and equilibrium. *Journal of Political Economy*.
- Bender, J., Briand, R., Melas, D. & Subramanian, R. (2013). Foundations of factor investing. MSCI Research.
- Bender, J. & Wang, T. (2016). Can the whole be more than the sum of the parts? Bottom-up versus top-down multifactor portfolio construction. *Journal of Portfolio Management*.
- Ilmanen, A. (2011). *Expected Returns*. Wiley.
- Ang, A. (2014). *Asset Management: A Systematic Approach to Factor Investing*. Oxford.

### ب) اعتبار آماری و چندگانگی
- Harvey, C., Liu, Y. & Zhu, H. (2016). …and the cross-section of expected returns. *Review of Financial Studies*.
- McLean, R. D. & Pontiff, J. (2016). Does academic research destroy stock return predictability? *Journal of Finance*.
- Hou, K., Xue, C. & Zhang, L. (2020). Replicating anomalies. *Review of Financial Studies*.
- Harvey, C. & Liu, Y. (2015). Backtesting. *Journal of Portfolio Management*.
- Bailey, D. & López de Prado, M. (2014). The deflated Sharpe ratio. *Journal of Portfolio Management*.
- Bailey, D., Borwein, J., López de Prado, M. & Zhu, Q. (2014). Pseudo-mathematics and financial charlatanism. *Notices of the AMS*.
- López de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley.
- White, H. (2000). A reality check for data snooping. *Econometrica*.
- Hansen, P. (2005). A test for superior predictive ability. *Journal of Business & Economic Statistics*.
- Lo, A. (2002). The statistics of Sharpe ratios. *Financial Analysts Journal*.
- Ledoit, O. & Wolf, M. (2008). Robust performance hypothesis testing with the Sharpe ratio. *Journal of Empirical Finance*.
- Newey, W. & West, K. (1987). A simple, positive semi-definite, heteroskedasticity and autocorrelation consistent covariance matrix. *Econometrica*.
- Politis, D. & Romano, J. (1994). The stationary bootstrap. *Journal of the American Statistical Association*.
- Patton, A. & Timmermann, A. (2010). Monotonicity in asset returns. *Journal of Financial Economics*.
- MacKinlay, A. C. (1997). Event studies in economics and finance. *Journal of Economic Literature*.

### پ) ساخت شاخص و وزن‌دهی
- Arnott, R., Hsu, J. & Moore, P. (2005). Fundamental indexation. *Financial Analysts Journal*.
- Hsu, J. (2004). Cap-weighted portfolios are sub-optimal portfolios. *Journal of Investment Management*.
- Haugen, R. & Baker, N. (1991). The efficient market inefficiency of capitalization-weighted stock portfolios. *Journal of Portfolio Management*.
- DeMiguel, V., Garlappi, L. & Uppal, R. (2009). Optimal versus naive diversification. *Review of Financial Studies*.
- Plyakha, Y., Uppal, R. & Vilkov, G. (2012/2014). Why does an equal-weighted portfolio outperform value- and price-weighted portfolios? SSRN.
- Clarke, R., de Silva, H. & Thorley, S. (2006). Minimum-variance portfolios in the U.S. equity market. *Journal of Portfolio Management*.
- Choueifaty, Y. & Coignard, Y. (2008). Toward maximum diversification. *Journal of Portfolio Management*.
- Maillard, S., Roncalli, T. & Teiletche, J. (2010). The properties of equally weighted risk contribution portfolios. *Journal of Portfolio Management*.
- Ledoit, O. & Wolf, M. (2004). A well-conditioned estimator for large-dimensional covariance matrices. *Journal of Multivariate Analysis*.
- Blume, M. & Stambaugh, R. (1983). Biases in computed returns: an application to the size effect. *Journal of Financial Economics*.
- Chen, H., Noronha, G. & Singal, V. (2004). The price response to S&P 500 index additions and deletions. *Journal of Finance*.
- Madhavan, A. (2003). The Russell reconstitution effect. *Financial Analysts Journal*.
- Petajisto, A. (2011). The index premium and its hidden cost for index funds. *Journal of Empirical Finance*.
- Cremers, M. & Petajisto, A. (2009). How active is your fund manager? *Review of Financial Studies*.
- IOSCO (2013). *Principles for Financial Benchmarks*.
- CFA Institute. *Global Investment Performance Standards (GIPS)*.

### ت) ریبالانس و ساخت پرتفوی
- Perold, A. & Sharpe, W. (1988). Dynamic strategies for asset allocation. *Financial Analysts Journal*.
- Grinold, R. & Kahn, R. (2000). *Active Portfolio Management*. McGraw-Hill.
- Gârleanu, N. & Pedersen, L. (2013). Dynamic trading with predictable returns and transaction costs. *Journal of Finance*.
- Moreira, A. & Muir, T. (2017). Volatility-managed portfolios. *Journal of Finance*.
- Faber, M. (2007). A quantitative approach to tactical asset allocation. *Journal of Wealth Management*.
- Daryanani, G. (2008). Opportunistic rebalancing. *Journal of Financial Planning*.

### ث) اجرا و هزینه
- Perold, A. (1988). The implementation shortfall. *Journal of Portfolio Management*.
- Almgren, R. & Chriss, N. (2000). Optimal execution of portfolio transactions. *Journal of Risk*.
- Almgren, R., Thum, C., Hauptmann, E. & Li, H. (2005). Direct estimation of equity market impact. *Risk*.
- Tóth, B., Lempérière, Y., Deremble, C., de Lataillade, J., Kockelkoren, J. & Bouchaud, J.-P. (2011). Anomalous price impact and the critical nature of liquidity in financial markets. *Physical Review X*.
- Kyle, A. (1985). Continuous auctions and insider trading. *Econometrica*.
- Frazzini, A., Israel, R. & Moskowitz, T. (2018). Trading costs. SSRN.
- Novy-Marx, R. & Velikov, M. (2016). A taxonomy of anomalies and their trading costs. *Review of Financial Studies*.
- Lesmond, D., Ogden, J. & Trzcinka, C. (1999). A new estimate of transaction costs. *Review of Financial Studies*.
- Roll, R. (1984). A simple implicit measure of the effective bid–ask spread. *Journal of Finance*.
- Corwin, S. & Schultz, P. (2012). A simple way to estimate bid–ask spreads from daily high and low prices. *Journal of Finance*.
- Scholes, M. & Williams, J. (1977). Estimating betas from nonsynchronous data. *Journal of Financial Economics*.
- Dimson, E. (1979). Risk measurement when shares are subject to infrequent trading. *Journal of Financial Economics*.

### ج) اتریبیوشن
- Brinson, G., Hood, R. & Beebower, G. (1986). Determinants of portfolio performance. *Financial Analysts Journal*.
- Brinson, G. & Fachler, N. (1985). Measuring non-US equity portfolio performance. *Journal of Portfolio Management*.
- Carino, D. (1999). Combining attribution effects over time. *Journal of Performance Measurement*.

### چ) بازارهای نوظهور و مرزی
- Rouwenhorst, K. G. (1999). Local return factors and turnover in emerging stock markets. *Journal of Finance*.
- Griffin, J., Ji, X. & Martin, J. S. (2003). Momentum investing and business cycle risk: evidence from pole to pole. *Journal of Finance*.
- Bekaert, G. & Harvey, C. (1997). Emerging equity market volatility. *Journal of Financial Economics*.
- Hou, K., Karolyi, G. A. & Kho, B.-C. (2011). What factors drive global stock returns? *Review of Financial Studies*.
- Miller, E. (1977). Risk, uncertainty, and divergence of opinion. *Journal of Finance*.
- Stambaugh, R., Yu, J. & Yuan, Y. (2012). The short of it: investor sentiment and anomalies. *Journal of Financial Economics*.

> **یادداشت صداقت علمی:** فهرست بالا از حافظهٔ دانشی تهیه شده و ارجاع‌های دقیق (سال، نشریه، عنوان کامل) پیش از انتشار رسمی باید با پایگاه‌های علمی راستی‌آزمایی شود.

## ۱۰.۵ واژه‌نامه (فارسی ↔ انگلیسی)

| فارسی | انگلیسی |
|-------|---------|
| قیمت مبنا | Base / reference price |
| قیمت پایانی | Closing (VWAP-type) price |
| تعدیل قیمت | Price adjustment |
| بازده کل | Total return |
| شاخص قیمتی | Price index |
| شاخص بازده نقدی و قیمت | Dividend & price (total return) index |
| شناوری آزاد | Free float |
| ریبالانس | Rebalancing |
| خطای ردیابی | Tracking error |
| تفاوت ردیابی | Tracking difference |
| صف خرید/فروش | Buy/sell queue (limit-locked) |
| حد نوسان | Price limit |
| اثر بازار | Market impact |
| نقدشوندگی | Liquidity |
| ظرفیت | Capacity |
| سوگیری بقا | Survivorship bias |
| نگاه به آینده | Look-ahead bias |
| ضریب اطلاعات | Information coefficient (IC) |
| نسبت اطلاعات | Information ratio (IR) |
| اتریبیوشن | Performance attribution |
| بازگشت به میانگین | Mean reversion |
| حرکت | Momentum |
| ارزش | Value |
| کیفیت | Quality |
| نوسان کم | Low volatility |
