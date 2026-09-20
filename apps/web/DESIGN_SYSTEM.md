# HSAAI Design System — Official Style Guide v1.0

> المرجع الرسمي الوحيد للهوية: `index.html` (معرض الهوية الرسمي).
> هذا الدليل يلزم كل صفحة ومكوّن داخل `apps/web`. الهدف: أن تبدو كل الصفحات أجزاء من منصة مؤسسية واحدة.

## 1. Design Tokens (Single Source of Truth)

معرّفة في `tailwind.config.ts` (كلاسات Tailwind) و `styles/globals.css` (CSS variables).

| Token | Value | Tailwind class | الاستخدام |
|---|---|---|---|
| Primary Gold | `#F4C430` | `bg-hsa-yellow` / `text-hsa-yellow` | أزرار رئيسية، Active states، خط تحت عناوين الأقسام |
| Dark Gold | `#A67C00` | `bg-hsa-gold-dark` / `text-hsa-gold` | hover للأزرار، الأرقام الكبيرة/KPI، نص accent على أبيض |
| Soft Gold | `#FDF4E3` | `bg-hsa-soft` | خلفيات Badges، عناصر القائمة النشطة، فقاعات المساعد |
| Main Black | `#111111` | `text-hsa-black` / `bg-hsa-black` | نصوص رئيسية، العناوين |
| Dark Black | `#1A1A1A` | `bg-hsa-black-soft` | Footer، أسطح داكنة فقط |
| Main BG | `#FAFAF9` | `bg-hsa-bg` | خلفية التطبيق |
| White | `#FFFFFF` | `bg-white` | البطاقات والجداول |
| Border | `#E7E5E4` | `border-hsa-border` | كل الحدود Hairline |
| Secondary Text | `#64748B` | `text-hsa-secondary` | الأوصاف، التلميحات، التواريخ |

**قواعد صارمة:**
- ممنوع: بنفسجي، أزرق قوي، gradients مبالغ فيها، glassmorphism، neon/cyberpunk، ظلال قوية.
- Gold يستخدم كـ accent فقط — ليس لون خلفيات رئيسي.
- نص ذهبي على أبيض: استخدم `text-hsa-gold` (داكن #A67C00) للقراءة؛ `text-hsa-yellow` فقط على خلفيات داكنة.
- زر ذهبي: نص `text-hsa-black`، hover: `bg-hsa-gold-dark` + `text-white`.

## 2. Typography — v2 (IBM Plex superfamily)

> ملفات النظام: `styles/fonts.css` (@font-face محلية WOFF2) + `styles/globals.css` (CSS variables) + `tailwind.config.ts` (tokens).

### الخطوط
| الاستخدام | الخط | ملاحظة |
|---|---|---|
| العربية + الإنجليزية | **IBM Plex Sans Arabic** | حروفه اللاتينية هي IBM Plex Sans نفسها → عائلة واحدة، baseline واحد، وزن بصري متطابق للغتين |
| الكود / API / IDs / Tokens | **IBM Plex Mono** | يُطبَّق تلقائياً على `pre/code/kbd/samp` عبر globals.css — لا تحدد `font-mono` يدوياً إلا للنص التقني غير الملفوف بكود |

الخطوط محلية (WOFF2 في `public/fonts/`) — لا طلبات خارجية لـGoogle، `font-display: swap`، و`unicode-range` يضمن تحميل كل صفحة للأقسام الفرعية التي تعرضها فقط (صفحة عربية لا تجلب ملف اللاتيني والعكس).

### الأوزان — أربعة فقط (ممنوع ما عداها)
| Token | الوزن | الاستخدام |
|---|---|---|
| `font-normal` | 400 | النصوص |
| `font-medium` | 500 | تلميحات، عناصر ثانوية |
| `font-semibold` | 600 | أزرار، روابط، labels، badges، عناوين جانبية |
| `font-bold` | 700 | عناوين H1–H3، أرقام KPI |

> ⚠️ `font-black` (900) و`font-extrabold` (800) ممنوعان: IBM Plex Sans Arabic ليس فيهما وزن حقيقي. كلاساهما تُحوالان إلى 700 كشبكة أمان في tailwind.config — لا تستخدمهما في كود جديد.

### المقياس (Type Scale) — استخدم الـtoken بدل الأحجام اليدوية
| Token | الحجم | line-height | الاستخدام |
|---|---|---|---|
| `text-display` | fluid 30→48px | 1.2 | Hero الرئيسي فقط |
| `text-h1` | fluid 24→36px | 1.25 | عنوان الصفحة (PageHeader) |
| `text-h2` / `text-2xl` | 24px | 1.3 | عنوان قسم رئيسي |
| `text-h3` / `text-xl` | 20px | 1.4 | عنوان كارت |
| `text-h4` / `text-lg` | 18px | 1.45 | عنوان فرعي |
| `text-base` | 16px | 1.65 | نصوص قراءة |
| `text-sm` | 14px | 1.6 | الافتراضي للواجهة |
| `text-xs` | 12px | 1.55 | تلميحات، captions |
| `text-micro` | 11px | 1.5 | badges، labels دقيقة |
| `text-nano` | 10px | 1.45 | meta مصغّرة جداً |
| `text-body-lg` | 15px | 1.7 | رسائل الشات (اقرأ أدناه) |

- Headings fluid عبر `clamp()` — لا حاجة لـ`sm:`/`lg:` لكل عنوان.
- **ممنوع** أحجام يدوية `text-[Npx]` جديدة. الاستثناء الوحيد: `text-[16px]` لحقول الإدخال على الموبايل (يمنع iOS من تكبير الشاشة عند الكتابة).

### قواعد العربية (RTL) — إلزامية
- **ممنوع letter-spacing على العربية** — يكسر اتصال الحروف. شبكة أمان في globals.css تُصفّر كل `tracking-*` تحت `[dir="rtl"]` (تُستثنى جزر `dir="ltr"`).
- `uppercase` على العربية ليس لها أثر — تُترك على labels اللاتينية فقط أو مع `dir="ltr"`.
- line-heights المقياس مضبوطة للعربية (أعلى من الافتراضي اللاتيني) — لا تضغطها بـ`leading-none` على نصوص عربية.
- نصوص لاتينية بحتة داخل صفحة عربية (أسماء منتجات، taglines): أضف `dir="ltr"` للعنصر.
- الكود والـAPI paths داخل نص عربي: `<code>` يعمل كجزيرة LTR معزولة تلقائياً.

### الأرقام والبيانات (Dashboard)
- أرقام KPI: `text-3xl font-bold tabular-nums text-hsa-gold` (مدمج في `KpiCard`).
- الجداول: `.hsa-table` تفعّل `tabular-nums` تلقائياً لسهولة المسح البصري.
- لا تستخدم Mono للنصوص العادية — للقيم التقنية فقط (IDs، endpoints، JSON، logs).

## 3. المكوّنات الجاهزة (استخدمها — لا تكرر CSS)

كلها في `components/ui/` و `components/enterprise/page-state.tsx`:

| المكوّن | الاستيراد | ملاحظات |
|---|---|---|
| `Button` | `@/components/ui/button` | `variant="primary" \| "secondary" \| "ghost"` |
| `Card` | `@/components/ui/card` | `hoverable` يضيف رفع خفيف عند hover |
| `Badge` | `@/components/ui/badge` | `tone="gold" \| "neutral" \| "ok" \| "warn" \| "error" \| "info"` |
| `KpiCard` | `@/components/ui/kpi-card` | KPI برقم ذهبي + أيقونة + delta |
| `PageHeader` | `@/components/ui/page-header` | eyebrow + title + description + actions |
| `Input` / `Textarea` | `@/components/ui/input` `textarea` | حدود موحدة + focus ذهبي |
| `EmptyState` / `LoadingState` / `ErrorState` | `@/components/enterprise/page-state` | حالات فارغة/تحميل/خطأ موحدة |
| `PlatformFooter` | `@/components/layout/platform-footer` | داخل AppShell تلقائياً |
| CSS classes | `globals.css` | `.hsa-card` `.hsa-card-hover` `.hsa-section-title` `.hsa-badge` `.hsa-status-*` `.hsa-btn-*` `.hsa-input` `.hsa-table` |

## 4. قواعد الصفحات

### التخطيط
- كل صفحات التطبيق (عدا `/login` و `/chat`) تستخدم `<AppShell>` من `@/components/layout/app-shell` — يوفر Sidebar + Topbar + Breadcrumbs + Footer.
- الصفحات المستقلة القديمة يجب لفّها بـ AppShell: احتفظ بمنطق الصفحة (hooks, fetch, state) وحوّل الجذر إلى `<AppShell>...</AppShell>`.
- `/chat` يبقى بشاشة كاملة بقائمة جانبية خاصة (نمط ChatGPT) لكن بالهوية الفاتحة.
- `/login` مستقلة: خلفية `bg-hsa-bg`، شريط ذهبي علوي 1px، بطاقة بيضاء.

### الكروت
- `Card` أو `.hsa-card`: أبيض، حد `#E7E5E4`، radius 12–16px، ظل خفيف جداً، hover رفع خفيف.

### الجداول
- استخدم `.hsa-table` على `<table>`: رأس `bg-hsa-bg`، صفوف hover `bg-hsa-soft/40`، حدود hairline.
- الحالة النشطة/المحددة: `bg-hsa-soft` + `text-hsa-gold`.

### Charts (Recharts)
- خط/أعمدة: `stroke="#A67C00"`, fill `#F4C430` بتدرج شفاف، شبكة `#E7E5E4`, نص محاور `#64748B`.
- غلّف الرسم البياني بـ `dir="ltr"` مع بقاء باقي الصفحة RTL.

### النماذج
- `Input`/`Textarea` الجاهزة، التسميات `text-xs font-semibold text-hsa-secondary`.
- الأزرار: primary ذهبي للإجراء الرئيسي فقط.

### الحالات
- تحميل: `LoadingState`، فراغ: `EmptyState` مع زر إجراء، خطأ: `ErrorState`. ممنوع اختراع حالات جديدة.

## 5. RTL / LTR

- الجذر `dir="rtl"`. الصفحة تعمل RTL-first. لا تستخدم `ml-`/`mr-`/`pl-`/`pr-`/`left-`/`right-` في CSS جديد — استخدم المنطقية: `ms-` `me-` `ps-` `pe-` `start-` `end-`.
- أيقونات الأسهم الاتجاهية: `ArrowLeft` في RTL (الاتجاه نحو التقدم).
- عند تفعيل الإنجليزية يقلب i18n الاتجاه تلقائياً — يجب ألا ينكسر شيء.

## 6. Icons

- `lucide-react` فقط، `size={16..20}`, داخل حاوية `rounded-xl bg-hsa-soft text-hsa-gold` أو `bg-hsa-bg text-hsa-secondary`.

## 7. Accessibility (إلزامي)

- كل زر/رابط أيقونة يحتاج `aria-label` عربي معبّر.
- عناوين الهرم: `h1` واحدة لكل صفحة ثم `h2`/`h3`.
- `role="alert"` للأخطاء، `role="status"` للتحميل، `aria-current="page"` للعنصر النشط.
- التباين: نص أساسي #111111، ثانوي #64748B (كلاهما AA على أبيض).
- focus ظاهر: لا تحذف `focus-visible` الافتراضي.

## 8. Responsive

- Mobile-first. breakpoints: `sm:640 md:768 lg:1024 xl:1280`.
- شبكات KPI: `grid-cols-2 lg:grid-cols-4` (وليس 4 دائماً).
- جداول عريضة على الهاتف: لفّها بـ `overflow-x-auto`.
- ممنوع horizontal scroll — تأكد أن أي grid large ينكسر على الشاشات الصغيرة.
