# HSAAI — سجل الإصلاحات الدقيقة (Demo Runtime Fixes)
**الإصدار:** HSAAI_v3_UI_Corrected_v3_FIXED
**التاريخ:** 2026-09-06
**المبدأ:** إصلاحات موثّقة بأقل تغيير ممكن على كود المشروع الأصلي — دون حذف أو إعادة تسمية أو تغيير للهوية البصرية.

---

## ملخص تنفيذي

فُحص المشروع بالكامل (بنية، واجهة Next.js 15، خدمات FastAPI، قاعدة البيانات، المصادقة، الحوكمة) ثم شُغِّل في بيئة عرض بدون Docker (dockerless demo) بثلاث عمليات خفيفة بدل 56 حاوية. أثناء التشغيل الفعلي اكتُشفت أخطاء كانت تُعطّل العرض بالكامل، وتم إصلاحها جميعًا. كل إصلاح موثّق داخل الكود نفسه بتعليق `FIX (...)`.

**النتيجة:** بيئة عرض تعمل 100% — تسجيل دخول OIDC كامل (PKCE + JWT RS256)، محادثة حية، مركز معرفة، وكل الصفحات الرئيسية مُصيّرة بمحتوى عربي واقعي.

---

## الإصلاحات العشرة

### D-1 — إنشاء `scripts/mock-keycloak.js` (ملف مفقود موثّق)
**الملف:** `scripts/mock-keycloak.js` *(جديد — بنية تحتية للعرض فقط)*
**المشكلة:** ملف `services/_demo_oidc_shim.py` يوثّق في ديباجة أنه يعتمد على `scripts/mock-keycloak.js` كمزوّد هوية تجريبي — لكن الملف غير موجود في الأرشيف. كل محاولة تشغيل dockerless تفشل عند اكتشاف `/v1/keycloak/config` بـ ECONNREFUSED على المنفذ 9080.
**الإصلاح:** تنفيذ المزوّد كاملًا كما وُصف: نقاط OIDC (auth / token مع PKCE S256 / certs JWKS / userinfo / logout)، رموز RS256، مستخدم عرض «مدير النظام» بأدوار `hsaai_admin` و`ai_user` و`ai_admin` و`audit_viewer`، وواجهة دخول بهوية HSAAI الذهبية.

### D-2 — جسر عقد البوابة في `services/_demo_oidc_shim.py`
**الملف:** `services/_demo_oidc_shim.py` *(بنية تحتية للعرض — ليس كود منتج)*
**المشكلة:** واجهة الويب تنادي `POST {API_BASE}/v1/chat` بينما الخلفية تخدم `/chat` (بادئة `/v1` من مسؤولية api_gateway في نشر Docker فقط). بدون الجسر: صفحة المحادثة ترجع 404 في بيئة dockerless.
**الإصلاح:** إضافة `/v1/chat` (يحوّل الكوكي httpOnly إلى رأس `Authorization: Bearer` كما تفعل البوابة تمامًا) + `/v1/auth/logout` + `/v1/auth/refresh`.

### D-3 — بروكسيات Next.js المفقودة لمسارات الواجهة الداخلية
**الملفات:** `apps/web/app/api/knowledge-hub/[...path]/route.ts` و`apps/web/app/api/smart-responses/[...path]/route.ts` و`apps/web/app/api/smart-responses/route.ts` *(جديدة)*
**المشكلة:** صفحات «مركز المعرفة» و«الردود الذكية» تنادي مسارات Next داخلية `/api/knowledge-hub/*` و`/api/smart-responses/*` — لكن معالجات المسارات هذه لم تكن موجودة إطلاقًا (يوجد فقط `app/api/auth/*`). النتيجة: 404 على كل تحميل، جداول فارغة، وأزرار معطلة.
**الإصلاح:** بروكسي catch-all يحوّل الطلب إلى موجّه الخلفية المقابل (`/v1/knowledge-hub/*` و`/v1/smart-responses/*`) مع تحويل الكوكي إلى رأس Authorization — بنفس نمط `lib/server-auth.ts` الموجود في المشروع.

### P0-1 — مطابق الردود الذكية يقبل كائنات ORM
**الملف:** `services/backend_core/smart_responses/matcher.py`
**المشكلة:** `find_best_match` كان يقرأ `template.get("patterns")` بينما الخدمة تمرر كائنات `SmartResponseTemplate` (ORM) وتقرأ النتيجة بوصول خصائص (`match.template`) — النتيجة: `AttributeError` على **كل** طلب محادثة → `/v1/chat` يرجع 500 دائمًا.
**الإصلاح:** المُطابق يقبل الآن ORM أو dict، ويعيد `MatchResult` dataclass بوصول خصائص. سلوك العتبات والتطابق دون تغيير.

### P0-2 — تصنيف النية: دالة async تُستدعى بدون await
**الملف:** `services/backend_core/intent_detection/service.py`
**المشكلة:** `_llm_classify` معرفة `async` لكن مستدعيها `detect_intent` (متزامن بالكامل) يناديها بدون await → `AttributeError: 'coroutine' object has no attribute 'get'` → 500 على كل محادثة.
**الإصلاح:** تحويلها إلى استدعاء httpx متزامن يطابق سلسلة الاستدعاء؛ المسار الآمن (إرجاع None عند غياب البوابة) محفوظ حرفيًا.

### P0-3 — حفظ الرسائل بدون tenant_id (قيد NOT NULL)
**الملف:** `services/backend_core/memory/store.py` + `services/backend_core/core/engine.py`
**المشكلة:** عمود `messages.tenant_id` في المخطط NOT NULL، لكن `save_message` لا تقبله ولا تمرره → `IntegrityError` على كل INSERT رسالة (SQLite وPostgreSQL سواء).
**الإصلاح:** وسيط اختياري `tenant_id="default"` يحفظ التوافق مع كل المستدعين، مع تمريره من المحرك.

### P0-4 — بحث RAG غير متزامن في سلسلة متزامنة
**الملف:** `services/backend_core/rag/search.py`
**المشكلة:** `search_docs` كانت `async` ومستدعيها يستهلك النتيجة في حلقة تكرار مباشرة → `TypeError: 'coroutine' object is not iterable` → 500.
**الإصلاح:** تحويل إلى httpx متزامن مع نفس المسار الآمن (إرجاع قائمة فارغة عند غياب محرك RAG).

### P0-5 — منسّق المحادثة غير المتزامن + وصول dict بخصائص
**الملف:** `services/backend_core/core/engine.py`
**المشكلة (3 أخطاء متراكبة):** (أ) `_call_orchestrator` كانت async والنتيجة تُفكّ متزامنًا؛ (ب) `intent_result.intent` على dict؛ (ج) `intent_result.score` على dict — ثلاثتها تكسر `/v1/chat`.
**الإصلاح:** تحويل المنسّق إلى متزامن + وصول dict آمن مع بدائل — مع الحفاظ على مسار التراجع النصي العربي عند غياب المنسّق.

### P0-6 — الوكيل الداخلي للبحث نفس النمط
**الملف:** `services/backend_core/core/engine.py` (`_search_rag_engine`)
**المشكلة والسلوك:** كما في P0-4 — حُوّلت إلى متزامنة. (ضُمّت في الإصلاح رقم 5 داخل الملف.)

### R-1 — CORS يرفض أصل المتصفح الفعلي + رأس X-Requested-With
**الملف:** `services/backend_core/main.py`
**المشكلة (خطآن):** (أ) القائمة الافتراضية تسمح بـ `localhost:3000` فقط بينما المتصفح يفتح `127.0.0.1:3000` → رفض preflight → فشل صامت في فحص الجلسة وإعادة توجيه إلى `keycloak:8080` غير قابل للحل (chrome-error). (ب) عميل الواجهة (services/api.ts) يرسل `X-Requested-With` على كل طلب axios — والرأس غير مسموح → 400 على كل preflight.
**الإصلاح:** إضافة أصول 127.0.0.1 إلى الافتراضي + إضافة `X-Requested-With` إلى allow_headers. (لا يزال wildcard مرفوضًا كما في التصميم الأمني الأصلي.)

---

## بنية التشغيل التجريبي (demo-runtime/)

```
demo-runtime/
├── start.sh        # إقلاع العمليات الثلاث (IdP 9080 / الخلفية 8080 / الويب 3000)
├── stop.sh         # إيقاف نظيف
├── seed_demo.py    # بيانات العرض العربية (مساحات معرفة، وثائق، ردود ذكية، سجل تدقيق)
└── logs/           # سجلات العمليات
```

**التشغيل:**
```bash
bash demo-runtime/start.sh      # ثم فتح http://127.0.0.1:3000
python3 demo-runtime/seed_demo.py   # بيانات العرض (مرة واحدة)
```

**الاعتماديات:** Node.js 18+ وPython 3.12 مع `services/backend_core/requirements.txt` و`npm install` داخل `apps/web`.

## ما لم يُغيَّر (التزامًا بقواعد المشروع)
- لا حذف ملفات، لا إعادة تسمية، لا تغيير للشعار أو الألوان أو الخطوط.
- كود المنتج (`services/backend_core` عدا الإصلاحات الموثّقة أعلاه) و`apps/web` كما هو.
- `docker-compose.yml` والمسارات الإنتاجية كما هي — الإصلاحات كلها متوافقة مع النشر الكامل (قيم البيئة الافتراضية الجديدة تتضمن أصل 127.0.0.1 فقط كإضافة، والرأس المضاف يوسع السماح دون فتح ثغرة).
