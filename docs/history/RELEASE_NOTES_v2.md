# HSAAI v2.0.0 — ملاحظات الإصدار | Release Notes

> **الإصدار 2.0.0** · 2026-08-28 · النسخة المصححة والتحقق منها فعليًا على منصة تشغيل حقيقية
> This release was verified by actually booting the platform and exercising every
> major flow end-to-end — not by code review alone.

---

## 1) ملخص تنفيذي

تم إصلاح جميع العيوب المكتشفة (C-01…C-09 و H-01…H-02)، وإضافة مسار نشر **native بلا
Docker** (لبيئات الحاويات التي تمنع Docker Engine)، وتشغيل المنصة كاملةً والتحقق منها:
دخول مؤسسي عبر OIDC/PKCE → لوحة القيادة → المحادثة → المعرفة → الوكلاء → سطح المكتب
البعيد الحقيقي → الصلاحيات (RBAC) → التدقيق. كما أُنتج **فيديو عرض عربي رسمي** بالهوية
البصرية للمنصة.

## 2) الإصلاحات الحرجة

| المعرّف | العيب | الإصلاح |
|--------|-------|---------|
| C-01 | `IndentationError` في `packages/common/imagination` يمنع تحميل الوحدة | تغليف السلاسل النصية المتعددة بأقواس |
| C-02 | `alembic` غير معلن في متطلبات backend مع `USE_ALEMBIC=true` | إضافة `alembic==1.14.0` |
| C-03 | FK غير صالح `department_agent_runs.agent_key` يفشل على PostgreSQL نظيفة | قيد UNIQUE في النماذج + ترحيل 0001 + ترحيل اصطلاحي `0005_dagent_key_unique` |
| C-04 | مسارات `/data` مضمّلة تتعطل خارج Docker | fallback إلى `HSAAI_HOME/data` مع متغيرات تجاوز |
| C-05 | `/ready` يعيد 500 دائمًا (استدعاء async بدون await) | جعل المعالج async وانتظار فحص Qdrant |
| C-06 | تدفق OIDC مكسور: استدعاء دالة client من Route Handler سيرفري | عميل سيرفري — الدخول الكامل يعمل (`/v1/auth/me` يستجيب) |
| C-07 | عدم تطابق `redirect_uri` في تبادل التوكن | اشتقاق من ترويسات التحويل |
| C-08 | علم `Secure` للكوكيز يمنع الدخول على HTTP المحلي | قابل للضبط عبر `HSAAI_COOKIE_SECURE` |
| C-09 | أصل التحويل بعد callback ثابت على `0.0.0.0` | اشتقاق من ترويسات الطلب |
| H-01 | منفذ auth في المتصفح يشير إلى Keycloak `:8080` | محاذاة إلى `:8000` |
| H-02 | ازدواج تثبيت `redis` في المتطلبات | حذف المكرر |

## 3) الإضافات

- **مزود هوية تجريبي** `deployment/native/mock-keycloak.js` — OIDC/PKCE كامل
  (JWKS، رمز تفويض، password grant، صفحة دخول مؤسسية) بديلًا عن Keycloak الذي
  يتطلب Docker في هذه البيئة. مستخدمو العرض: `demo.admin` / `demo.user`
  (بيانات عرض فقط — لا أسرار حقيقية في المستودع).
- **hsaai-ctl محمول v2** — يكتشف موقعه ذاتيًا ويعمل من شجرة الحزمة
  (`deployment/native/`) أو من بيئة تشغيل حية (`scripts/`).
- **بوابة سطح المكتب** `desktop_gateway.py` على المنفذ 8600 — REST API لإدارة
  الجلسات (Phase 6) محمية بمصادقة، مع `test-desktop-input.py` لاختبار الإدخال.
- **فيديو العرض العربي** — ماستر عربي كامل (~6 دقائق) + نسخة تنفيذية (~85 ثانية)،
  تسجيلات شاشة حقيقية للمنصة العاملة، تعليق صوتي عربي فصيح، ترجمة عربية محروقة
  + ملف SRT، بالهوية الرسمية (أصفر `#F0CF3A` / ذهبي `#C7A833` / أسود `#050505`).

## 4) التشغيل السريع (native، بلا Docker)

```bash
# 1) تجهيز بيئة التشغيل (مرة واحدة — ينزّل ويفكك الحزم في runtime/rootfs)
bash deployment/native/setup-runtime.sh

# 2) تهيئة قاعدة البيانات والخدمات
source deployment/native/hsaai-env.sh
bash deployment/native/hsaai-ctl start          # 8 خدمات: idp postgres redis qdrant backend web desktop gateway

# 3) التحقق
bash deployment/native/hsaai-ctl status
curl http://127.0.0.1:8000/ready                 # backend
curl http://127.0.0.1:6333/healthz               # qdrant

# 4) الوصول
#   الويب:        http://localhost:3000        (دخول: demo.admin / Hsaai@Demo2026)
#   سطح المكتب:   http://localhost:6080/vnc.html
#   بوابة الجلسات: http://localhost:8600/health

# الإيقاف / إعادة التشغيل
bash deployment/native/hsaai-ctl stop
bash deployment/native/hsaai-ctl restart
```

## 5) ما لم يُنفّذ (بشفافية)

- **Docker Engine**: غير مدعوم في بيئة التشغيل الحالية (حاوية بلا
  `CAP_SYS_ADMIN`/`CAP_NET_ADMIN`، بلا namespaces للشبكة/PID، بلا
  `docker.sock`، وrootless غير ممكن — kernel قديم وبلا newuidmap/FUSE).
  `docker-compose.yml` الأصلي محفوظ دون تعديل للنشر على مضيف يدعم Docker.
- **استدلال LLM حقيقي**: يتطلب مفاتيح مزودين — إجابات المحادثة في العرض موسومة DEMO.
- **Keycloak**: بديلته مزود الهية التجريبي المحلي (متوافق OIDC/PKCE)؛ يُستبدل
  بمتغير `KEYCLOAK_*` في الإنتاج.

## 6) محتويات الحزمة

شجرة المشروع كاملة كما هي، مع إصدار `VERSION=2.0.0`، و`CHANGELOG.md` محدَّث،
و`RELEASE_NOTES_v2.md`، و`FIXES_v0.6.1.md`، و`deployment/native/` كاملًا
(سكربتات التشغيل + مزود الهوية التجريبي + بوابة سطح المكتب + اختبارات الإدخال).
