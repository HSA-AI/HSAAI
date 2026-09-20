# ملاحظات إصدار HSAAI v3.0.0 — النسخة الجاهزة للإنتاج

**التاريخ:** 2026-08-28
**الحالة:** مُتحقق منها تشغيليًا (8/8 خدمات تعمل + اختبارات قبول ناجحة) — وليس إصدارًا نظريًا

---

## ما الجديد في v3؟

v2 كانت «النسخة المصححة». **v3 هي النسخة الجاهزة للإنتاج**: نفس المنصة العاملة + طبقة عمليات إنتاج كاملة أُضيفت بناءً على تدقيق V3 الهندسي.

### 1. إصلاحات جوهرية (Fixed)

| العيب | الأثر قبل v3 | الإصلاح |
|---|---|---|
| **توكن البوابة اليتيم** | `hsaai-ctl` يبدأ بوابة سطح المكتب بلا `DESKTOP_API_TOKEN` → البوابة تولّد توكن عشوائي لا يعرفه أي عميل → **401 دائم لكل عميل API** | التوكن يُثبَّت من ملف (`chmod 600`) ويُولّد تلقائيًا عند أول تشغيل؛ مُختبر بدورة حياة كاملة (إنشاء→حذف→404 + رفض 401) |
| **مسارات مثبتة يدويًا** | `hsaai-env.sh` و`setup-runtime.sh` يعملان فقط على مسار جهاز محدد | اكتشاف ذاتي لجذر المشروع + اشتقاق `RUNTIME/DATA/LOGS` مع متغيرات تجاوز — الحزمة تعمل على أي تخطيط حساب Linux |
| **سباق تركيز اختبار الإدخال** | أول ضغطة بعد النقر عبر VNC تُبتلع | ضبط تركيز قبل الكتابة — **PASS مُعاد التحقق منه** |

### 2. أدوات إنتاج جديدة (Added)

- **أسرار خارجية:** `generate-secrets.sh` → `.env.native` بصلاحيات 600 (قيم قوية عشوائية، لا تُطبع أبدًا، لا تُلتزم بـ Git). `hsaai-ctl` يقرؤه تلقائيًا: `HSAAI_DB_PASSWORD` / `HSAAI_CLIENT_SECRET` / `DESKTOP_API_TOKEN` / `HSAAI_APP_ENV=production`.
- **فحص جاهزية تمهيدي:** `preflight-check.sh` — الثنائيات، بيئات التشغيل، المنافذ، القرص، صلاحيات الأسرار، حارس `.gitignore`. يُنهي التشغيل برمز غير صفري عند فشل حرج.
- **نسخ احتياطي/استعادة متسقة:** `backup-native.sh` (pg_dump متسق MVCC + Redis BGSAVE + Qdrant snapshot API + ملف manifest + احتفاظ 14 نسخة) و`restore-native.sh` (مع `--drop` للاستعادة الكاملة).
- **وحدات systemd للمضيف الإنتاجي:** `deployment/production/install-systemd-units.sh` — 7 وحدات محصّنة (`NoNewPrivileges`, `ProtectSystem=strict`, `PrivateTmp`, `PrivateDevices`, ملف أسرار `/etc/hsaai/hsaai.env` بصلاحيات 600، إعادة تشغيل تلقائية).
- **دليل تشغيل عربي كامل:** `deployment/native/PRODUCTION_RUNBOOK_AR.md` — من الصفر حتى التشغيل، تدوير الأسرار، العمليات اليومية، النسخ/الاستعادة، الترقية/التراجع، قائمة أمان، مصفوفة استكشاف أخطاء، معايير قبول.
- **قالب بيئة آمن:** `env.native.example` — أسماء متغيرات فقط بقيم `<REPLACE_ME>`.

### 3. التحقق الحي عند الإصدار

- 8/8 خدمات UP بعد إعادة تشغيل كاملة؛ `/ready = ready` (PostgreSQL ok + Qdrant ok)
- 59 جدولًا في PostgreSQL 17.11؛ `/login` = 200؛ مفاتيح OIDC JWKS (RSA) تُخدم
- Redis 8.0.2 → PONG مع AOF
- دورة حياة بوابة سطح المكتب كاملة: إنشاء جلسة → snapshot.png حي → حذف → 404 → توكن خاطئ 401
- سلسلة إدخال حقيقية عبر VNC → **PASS** (ملف فعلي على القرص من كتابة عبر سطح المكتب)
- لقطة `ffmpeg x11grab` تُظهر سطح مكتب X11 حقيقي (xterm + xclock)

---

## التشغيل السريع (بعد فك الضغط)

```bash
cd HSAAI
bash deployment/native/preflight-check.sh     # جاهزية البيئة
bash deployment/native/generate-secrets.sh    # الأسرار (إلزامي في الإنتاج)
bash deployment/native/hsaai-ctl start all    # تشغيل المنصة
bash deployment/native/hsaai-ctl status       # 8/8 UP
curl -s http://127.0.0.1:8000/ready           # status: ready
```

الدليل الكامل: `deployment/native/PRODUCTION_RUNBOOK_AR.md`

---

## القيود الموثقة (بشفافية — لا ادعاءات)

- **Docker Engine غير مدعوم** في البيئات المقيدة (بلا CAP_SYS_ADMIN/cgroups كتابة/docker.sock) — استخدم النشر Native هنا، أو `docker-compose.yml` الأصلي على مضيف Docker قادر.
- **الستاك الكامل (33 خدمة)** يتطلب 32GB+ RAM وGPU للاستدلال المحلي — هذه الحزمة تشغّل النواة الإنتاجية (8 خدمات) بموارد 4GB.
- **الاستدلال الذكي الفعلي** يحتاج مفتاح API خارجي أو مضيف GPU — البنية جاهزة والتزويد «يحتاج إلى توفيره من المضيف».
- **Demo IdP** بديل محلي كامل OIDC/PKCE لـ Keycloak (الذي يتطلب Docker) — استبدله بـ Keycloak حقيقي في الإنتاج المؤسسي.
