# دليل هوية أيقونة HSAAI Assistant

## 1. الهدف

تمت إضافة أيقونة دائرية رسمية باسم **HSAAI Assistant** لتكون نقطة الدخول السريعة للمساعد الذكي الداخلي داخل منصة HSAAI. تظهر الأيقونة لجميع الموظفين في الشاشة الرئيسية وصفحات المنصة، وتفتح نافذة محادثة مختصرة للاستفسارات اليومية.

## 2. الملفات المضافة

```text
frontend/public/brand/hsaai-assistant-circle.svg
frontend/public/brand/hsaai-assistant-circle.png
frontend/public/brand/hsaai-assistant-circle.webp
frontend/public/brand/hsaai-assistant-circle-512.png
frontend/public/brand/hsaai-assistant-circle-256.png
frontend/public/brand/hsaai-assistant-circle-128.png
frontend/public/brand/hsaai-assistant-circle-64.png
frontend/public/brand/hsaai-assistant-brand.json
```

## 3. ملفات الواجهة المرتبطة

```text
frontend/lib/brand.ts
frontend/components/assistant/floating-assistant.tsx
frontend/app/layout.tsx
```

## 4. مواصفات الهوية

| العنصر | القيمة |
|---|---|
| اسم الأيقونة | HSAAI Assistant |
| الاستخدام | زر عائم للمساعد الذكي الداخلي |
| اللون الأساسي | #F0CF3A |
| اللون الداكن | #050505 |
| الشكل | دائرة رسمية |
| النمط | مؤسسي، آمن، تقني، داخلي |

## 5. قواعد الاستخدام

- تستخدم الأيقونة داخل الزر العائم فقط أو داخل رأس نافذة المحادثة.
- لا يتم تغيير ألوان الأيقونة خارج هوية HSAAI.
- لا تستخدم الأيقونة كبديل للشعار الرئيسي للمنصة.
- يجب أن تبقى الأيقونة واضحة في الوضع الليلي والواجهات الداكنة.
- يفضل استخدام نسخة PNG داخل React ونسخة SVG عند الحاجة إلى المتجهات.

## 6. الربط البرمجي

تم تعريف مسار الأيقونة داخل:

```ts
brand.assistant.iconPath
```

وتم استخدامها داخل:

```tsx
FloatingAssistant
```

بذلك يمكن تغيير الأيقونة لاحقاً من ملف الهوية دون تعديل مكون الزر العائم.
