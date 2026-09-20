# RUNBOOK-09 — فشل OIDC / PKCE

تاريخ التحديث: 2026-09-14. الأثر: عدم تمكن المستخدمين من تسجيل الدخول؛ لا تعطّل المصادقة كحل.

1. افحص الخدمات المرجعية:

```bash
docker compose --env-file "$HSAAI_ENV_FILE" -f docker-compose.production.yml ps web auth-service keycloak
docker compose --env-file "$HSAAI_ENV_FILE" -f docker-compose.production.yml logs --tail=100 web auth-service keycloak
```

2. تأكد أن origin الظاهر للمتصفح HTTPS يطابق `APP_PUBLIC_URL` وأن callback المسموح في Keycloak هو هذا الـorigin متبوعًا بـ`/api/auth/callback` حرفيًا. افحص proxy headers وDNS دون طباعة cookies أو authorization codes.
3. ابدأ تسجيل الدخول من `/api/auth/start` في جلسة جديدة، وتأكد في المتصفح أن cookies الخاصة بـstate/verifier تصل إلى callback (HttpOnly وSecure، scope مناسب). لا تخلط localhost واسم الشركة أثناء التدفق؛ الـcookies مرتبطة بالمضيف.
4. عند `invalid_grant`: افحص تطابق PKCE challenge مع verifier، استخدام الكود مرة واحدة، تطابق redirect URI، وصحة وقت الخوادم. عميل `hsaai-frontend` عام باستخدام PKCE؛ لا تُضف سر عميل عشوائيًا لتعويض خطأ verifier.
5. عند 401 بعد الدخول: افحص issuer وaudience وJWKS الداخلي وclaims `sub`, `exp`, `tenant_id`, `workspace_id` وأدوار HSAAI المسموح بها. لا تقبل `alg=none` أو token منتهيًا لإصلاح العرض.
6. عند HTTP 500 من `/v1/keycloak/config` أو `/v1/auth/me`: تحقق من وصول Next.js إلى API Gateway وauth-service وKeycloak. هذه الحالة رُصدت في اختبار الواجهة المحلي عند غياب Backend؛ لا تثبت عطلًا في PKCE ذاته.
7. أعد اختبارات login/logout/refresh للمستخدم العادي والأدمن ورفض state غير مطابق وتوكن منتهٍ. وثّق وقت الحادث ومعرف الطلب والحالة فقط دون أسرار.

التصعيد: مهندس المناوبة ثم مالك الهوية/التطبيق. لا يوجد اتصال فعلي بفريق الشركة أو قناة إنذار مُثبت في هذه الحزمة؛ توثيق القنوات مسؤولية الاستلام.
