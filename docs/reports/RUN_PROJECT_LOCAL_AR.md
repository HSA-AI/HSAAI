# دليل تشغيل واختبار HSAAI محليًا

هذا الدليل يحل مشكلتين ظهرتا أثناء الاختبار داخل بيئة ChatGPT:

1. عدم توفر Docker Compose.
2. عدم توفر `node_modules` لتشغيل واجهة Next.js من المتصفح.

الحل النهائي يكون بتشغيل المشروع على جهازك أو سيرفر فعلي تتوفر فيه المتطلبات.

---

## 1) المتطلبات المطلوبة

ثبت التالي على الجهاز:

- Docker Desktop أو Docker Engine
- Docker Compose v2
- Node.js إصدار 20 أو 22
- Python 3.11 أو أحدث
- Git اختياري

### فحص المتطلبات

افتح Terminal أو PowerShell داخل مجلد المشروع وشغل:

```bash
node -v
npm -v
python --version
docker --version
docker compose version
```

إذا ظهر رقم إصدار لكل أمر، فالمتطلبات الأساسية جاهزة.

---

## 2) تشغيل واجهة Next.js فقط

ادخل إلى مجلد الواجهة:

```bash
cd apps/web
npm install
npm run dev
```

ثم افتح المتصفح على:

```text
http://localhost:3000
```

زر **HSAAI Assistant** يجب أن يفتح:

```text
/chat?new=1
```

### في حال ظهر خطأ node_modules

هذا طبيعي عند أول تشغيل. الحل:

```bash
cd apps/web
npm install
```

ثم:

```bash
npm run dev
```

---

## 3) تشغيل الواجهة كنسخة Production

```bash
cd apps/web
npm install
npm run build
npm run start
```

ثم افتح:

```text
http://localhost:3000
```

---

## 4) تشغيل Docker Compose كامل

من جذر المشروع شغل:

```bash
docker compose -f docker-compose.production.yml up -d --build
```

ثم افحص الخدمات:

```bash
docker compose -f docker-compose.production.yml ps
```

لعرض السجلات:

```bash
docker compose -f docker-compose.production.yml logs -f
```

لإيقاف التشغيل:

```bash
docker compose -f docker-compose.production.yml down
```

---

## 5) تشغيل نسخة التطوير عبر Docker

إذا أردت بيئة أخف للتجربة:

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

ثم:

```bash
docker compose -f docker-compose.dev.yml ps
```

---

## 6) فحص المشروع قبل التشغيل

من جذر المشروع:

```bash
python scripts/validate_project_structure.py
python scripts/verify_internal_only.py
python scripts/validate_yaml_files.py
bash scripts/production_release_gate.sh
pytest -q
```

النتيجة المتوقعة:

```text
OK / passed
```

---

## 7) اختبار RAG و API بعد التشغيل

بعد تشغيل Docker Compose، افحص صحة API Gateway:

```bash
curl http://localhost:8080/health
```

وافحص الخدمات حسب المنافذ المعرفة في `docker-compose.production.yml`.

إذا لم يعمل `curl` على Windows، افتح الرابط من المتصفح أو استخدم PowerShell:

```powershell
Invoke-WebRequest http://localhost:8080/health
```

---

## 8) حل أشهر المشاكل

### Docker غير معروف

السبب: Docker غير مثبت أو غير مضاف إلى PATH.

الحل: ثبت Docker Desktop ثم أعد تشغيل الجهاز.

### docker compose لا يعمل

استخدم الصيغة الجديدة:

```bash
docker compose version
```

وليس:

```bash
docker-compose version
```

### منفذ مستخدم مسبقًا

إذا ظهر أن المنفذ 3000 أو 8080 مستخدم، أغلق التطبيق الآخر أو غير المنفذ.

### npm install بطيء

استخدم شبكة مستقرة. يمكن تنفيذ:

```bash
npm cache clean --force
npm install
```

### مشكلة صلاحيات في Linux

نفذ:

```bash
sudo docker compose -f docker-compose.production.yml up -d --build
```

أو أضف المستخدم إلى مجموعة Docker.

---

## 9) اختبار الجوال

بعد تشغيل الواجهة على الكمبيوتر:

1. تأكد أن الهاتف والكمبيوتر على نفس شبكة Wi-Fi.
2. اعرف IP الكمبيوتر.
3. افتح من الهاتف:

```text
http://COMPUTER-IP:3000
```

مثال:

```text
http://192.168.1.10:3000
```

---

## 10) الحكم النهائي

إذا نجحت هذه الخطوات، تصبح النسخة قابلة للاختبار الكامل من المتصفح و Docker على جهازك.

بيئة ChatGPT لا تحتوي على Docker ولا `node_modules`، لذلك لا يمكن تشغيل المتصفح الحقيقي داخلها، لكن المشروع نفسه جاهز للتشغيل في بيئة محلية أو سيرفر فعلي.
