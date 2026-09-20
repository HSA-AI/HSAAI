# تقرير تثبيت هوية HSAAI البصرية

## الهدف
تنفيذ مرحلة **Brand Integration & Design Preservation** بعد مراجعة ملف HSAAI الأصلي، لضمان أن الواجهة تستخدم شعار المشروع وألوانه الرسمية بدل أي ألوان مؤقتة ظهرت أثناء التطوير.

## الهوية المعتمدة

| العنصر | القيمة الرسمية |
|---|---|
| الشعار الأساسي | `apps/web/public/hsaai_official_logo.png` |
| شعار HSA المرجعي | `apps/web/public/brand/hsa-logo.jpg` |
| أيقونة المساعد | `apps/web/public/brand/hsaai-assistant-circle.png` |
| HSA Yellow | `#F0CF3A` |
| HSA Black | `#050505` |
| HSA Gold | `#C7A833` |
| Enterprise Slate | `#0F172A` |
| Soft Yellow | `#FFF7CC` |

## الملفات المعدلة

| الملف | التعديل |
|---|---|
| `apps/web/lib/brand.ts` | تثبيت `logoPath` على الشعار الرسمي وإبقاء الشعار المرجعي كـ `legacyLogoPath` |
| `apps/web/tailwind.config.ts` | إضافة semantic brand colors: `hsa-surface`, `hsa-muted` مع إبقاء ألوان HSA الأصلية |
| `apps/web/styles/globals.css` | إضافة utilities رسمية: `hsa-brand-surface`, `hsa-brand-panel`, `hsa-brand-chip`, `hsa-brand-action` |
| صفحات `apps/web/app/*` | إزالة الألوان الخارجة عن الهوية مثل cyan/emerald واستبدالها بـ `hsa-yellow/hsa-gold` |
| مكونات `apps/web/components/*` | توحيد badges/status/action colors مع هوية HSA |
| `scripts/qa/brand_identity_audit.py` | إضافة فحص تلقائي للشعار، الألوان، والألفاظ اللونية غير المعتمدة |

## المشاكل التي تم حلها

| المشكلة | التأثير | الحل |
|---|---|---|
| وجود ألوان خارج الهوية مثل cyan وemerald | تشتت بصري وخروج عن شخصية HSAAI | استبدالها بـ HSA Yellow / HSA Gold |
| استخدام hex قديم `#F1BC38` | اختلاف طفيف عن اللون الرسمي | استبداله بالـ token الرسمي `hsa-yellow` |
| استخدام خلفيات سوداء hard-coded في بعض الصفحات | ضعف قابلية التحكم المركزي | ربطها بـ `hsa-black` و`enterprise-slate` |
| عدم وجود فحص تلقائي للهوية | قد تتكرر أخطاء الهوية لاحقًا | إضافة `brand_identity_audit.py` |

## أمر التحقق

```bash
python scripts/qa/brand_identity_audit.py
```

## النتيجة
تم توحيد الواجهة حول شعار HSAAI الرسمي وألوان HSA الأصلية. النسخة الآن أقرب إلى **Brand-Locked UI** ويمكن البناء عليها قبل التسليم أو العرض.
