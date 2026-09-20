# إصلاح ظهور أيقونة HSAAI Assistant

## سبب المشكلة
كانت أيقونة المساعد موجودة كملف صورة داخل المشروع، لكن صفحة المعاينة `preview/index.html` لم تكن تحتوي على زر عائم ثابت Floating Assistant Button، ولم يكن هناك مسار دردشة HTML مستقل يفتح محادثة جديدة.

## ما تم إصلاحه
- إضافة مجلد `preview/assets`.
- نسخ أيقونة HSAAI Assistant إلى:
  - `preview/assets/hsaai-assistant-circle.png`
- نسخ شعار HSAAI إلى:
  - `preview/assets/hsaai-logo.png`
- إضافة ملف CSS مستقل:
  - `preview/assets/style.css`
- تعديل الصفحة الرئيسية:
  - `preview/index.html`
- إضافة زر عائم أسفل الشاشة:
  - Floating Assistant Button
- ربط الزر بـ:
  - `chat.html?new=1`
- إضافة صفحة دردشة HTML مستقلة:
  - `preview/chat.html`

## طريقة الاختبار
افتح:
`preview/index.html`

يجب أن تظهر أيقونة HSAAI Assistant أسفل يسار الشاشة.

عند الضغط عليها يتم فتح:
`preview/chat.html?new=1`

## ملاحظة
هذه معاينة HTML مستقلة. في تشغيل Next.js الحقيقي يوجد مكوّن:
`apps/web/components/assistant/floating-assistant.tsx`

وهو مضاف في:
`apps/web/app/layout.tsx`
