# تقرير تشغيل محلي فعلي - HSAAI

تاريخ الاختبار: 2026-05-30

## بيئة الاختبار

- Node.js: متوفر
- npm: متوفر
- Docker: غير متوفر في بيئة الاختبار الحالية
- Docker Compose: غير متوفر في بيئة الاختبار الحالية

## تثبيت متطلبات واجهة Next.js

تمت محاولة تشغيل:

```bash
npm install
```

وظهر تعارض peer dependency بين React 19 و Recharts 2.x.

تمت المعالجة بإضافة ملف:

```bash
apps/web/.npmrc
```

ويحتوي على:

```bash
legacy-peer-deps=true
audit=false
fund=false
```

بعد ذلك نجح تثبيت الحزم باستخدام npm.

## تشغيل واجهة Next.js

تم تشغيل:

```bash
npm run dev
```

ونجح التشغيل على:

```bash
http://localhost:3000
```

## الصفحات التي تم اختبارها

تم اختبار الصفحات التالية وكانت ترجع HTTP 200:

- `/`
- `/chat?new=1`
- `/dashboard`
- `/agents`
- `/knowledge`
- `/settings`

## زر HSAAI Assistant

تم التأكد أن صفحة الشات متاحة عبر:

```bash
/chat?new=1
```

## Docker Compose

لم يتم تشغيل Docker Compose داخل هذه البيئة لأن أمر Docker غير متوفر:

```bash
docker: command not found
```

هذا قيد بيئة تشغيل وليس خطأ مؤكدًا في ملفات المشروع.

## الحكم

- واجهة Next.js تعمل محليًا بعد تثبيت الحزم.
- تم حل مشكلة تثبيت npm عبر `.npmrc`.
- Docker Compose يحتاج جهاز أو سيرفر يحتوي Docker Desktop / Docker Engine.

## أوامر التشغيل الموصى بها على جهاز المستخدم

```bash
cd apps/web
npm install
npm run dev
```

ثم افتح:

```bash
http://localhost:3000
```

لتشغيل Docker بعد تثبيته:

```bash
docker compose -f docker-compose.production.yml up -d --build
```
