# النشر والترقية والقبول

## نطاق التشغيل

المسار المرجعي الحالي هو docker-compose.production.yml المستقل. يحتوي 57 تعريف خدمة، منها مهمة ترحيل تنتهي بعد الإنجاز؛ بعض الوحدات المتقدمة والتدريب تحت profile extended. ملف docker-compose.yml يحوي 56 تعريفًا للتطوير. الملفات الأقدم محفوظة، ولا يُنصح بدمجها مع الملف المرجعي دون مراجعة.

لا تُشغّل هذه الخطوات على قاعدة إنتاج قائمة مباشرة. ابدأ بنسخة اختبار معزولة ونسخة احتياطية قابلة للاستعادة. لا تستخدم down -v أو حذف volumes، ولا تعيد توليد الإعدادات فوق ملف سابق.

## تجهيز بيئة الشركة

استخدم خادم Linux بصلاحيات التشغيل اللازمة، Docker Engine 24+ وCompose v2، Node22.12+ وPython3.12. اختبارات GPU تحتاج بطاقة NVIDIA وتعريفها وNVIDIA Container Toolkit. لا يكفي نجاح npm build لإثبات تشغيل مجموعة الخدمات.

```bash
python scripts/configure_production.py \
  --app-url https://AI_COMPANY_DOMAIN \
  --identity-url https://IDENTITY_COMPANY_DOMAIN \
  --output-dir deployment/generated
python scripts/validate_environment.py --env-file deployment/generated/.env.production
docker compose --env-file deployment/generated/.env.production -f docker-compose.production.yml config -q
```

استبدل النطاقين بنطاقات الشركة. المولد يرفض الكتابة فوق إعداد سابق، وينشئ أسرارًا منفصلة. خزّن الملف في مدير أسرار؛ لا ترفعه إلى Git. أمثلة .env تحتوي placeholders عمدًا ولا تصلح للتشغيل كما هي.

اضبط DNS وTLS ووكيل عكسي موثوقًا لنطاق التطبيق ونطاق الهوية. منافذ Compose المنشورة مرتبطة بالـloopback؛ ضع الوكيل على المضيف أو شبكة معتمدة. البوابة الداخلية على 8000 والواجهة على 3000 وKeycloak على منفذه المنشور في Compose. شبكة الإنتاج مغلقة عن الخروج؛ جهز الصور والأوزان قبل تفعيلها. أي وصول إلى SAP/LDAP/SMTP أو خدمات مؤسسية خارج هذه الشبكة يحتاج تصميم شبكة معتمدًا يسمح بالوجهات المطلوبة فقط.

ملف Keycloak المُولد يحدد callback دقيقًا ويضيف role names وtenant_id/workspace_id mappers. أنشئ مستخدمي الشركة وأدوارهم، واجعل خصائص المستأجر ومساحة العمل قابلة للتعديل من مسؤولي الهوية فقط. لا يُنشئ المولد مستخدمًا إداريًا ولا كلمة مرور تجريبية. اختبر PKCE، انتهاء الجلسة، refresh، logout وتدوير مفاتيح JWKS.

## النماذج والتخزين

جهز نموذج Ollama المحدد في LOCAL_LLM_MODEL، وافتراضي التكوين qwen2.5:7b-instruct، داخل volume النموذج. جهز sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 داخل HF cache على embedding_models:/models. البعد 384 يجب أن يطابق مجموعة Qdrant. لا تغير نموذج embedding لمجموعة قائمة دون إعادة فهرسة معزولة وخطة انتقال.

RAG لا يدعم اختيار Ollama كموفر embedding في هذه الشيفرة؛ أُصلحت الإعدادات لتستخدم sentence-transformers. تنزيل الأوزان ليس تلقائيًا في الإنتاج المغلق. عند تفعيل ENABLE_MULTI_MODEL_ROUTING=true، جهز جميع النماذج التي تشير إليها قواعد التوجيه. النتائج التجريبية لا تحل محل نموذج فعلي.

## قاعدة البيانات والترقية

على volumes جديدة، ينشئ init.sql قواعد البيانات المرافقة والأدوار، ثم يضبط zz-runtime-roles.sh أسرار حسابي hsaai_admin للترحيلات وhsaai_app للتطبيق. حساب التطبيق NOSUPERUSER/NOBYPASSRLS. يستخدم Keycloak وMLflow حسابين مستقلين لا يملكان صلاحيات إدارة قاعدة المنصة. مهمة db-migrate تطبق Alembic، وينتظرها backend-core ثم يتحقق من revision وصلاحيات حسابه دون الاحتفاظ ببيانات دخول الترحيل.

على قاعدة قديمة، لا يعاد تشغيل init.sql تلقائيًا. راجع الأدوار والملكية والصلاحيات؛ يجب أن يمتلك حساب الترحيل الجداول القديمة حتى يستطيع تعديلها. اختبر النقل على نسخة مستعادة أولًا. لا تستخدم alembic stamp لتجاوز ترحيل فاشل. الترحيل 0006 يضيف 32 جدولًا مفقودًا ويكمل extra_metadata مع الحفاظ على metadata القديمة، ويطبق RLS على الجداول ذات tenant_id؛ لا يحذف بيانات. الرجوع عنه يتطلب خطة استعادة معتمدة.

```bash
docker compose --env-file deployment/generated/.env.production -f docker-compose.production.yml build
docker compose --env-file deployment/generated/.env.production -f docker-compose.production.yml up -d
docker compose --env-file deployment/generated/.env.production -f docker-compose.production.yml ps
```

شغّل scripts/verify_database.py بمتغير DATABASE_URL لحساب hsaai_app وRUN_MIGRATIONS_ON_STARTUP=false وPYTHONPATH=.:services:packages على قاعدة الاختبار. يفحص المخطط وصلاحية الحساب وRLS ورفض القراءة والكتابة عبر المستأجرين؛ يتراجع عن سجلات الاختبار ولا يثبتها.

## Kubernetes وHelm

استبدل REPLACE_ORGANIZATION، النطاقات ووسوم الصور بصور مفحوصة مثبتة عبر digest. جهز PostgreSQL وRedis وQdrant وOllama وKeycloak وOTel في hsaai-data أو عدل الأسماء والسياسات وفق التصميم. القوالب لا توفر هذه الخدمات المدارة تلقائيًا، ولا تُثبت خاصية HA بحد ذاتها.

أنشئ namespace والتكوين وhsaai-secrets لحساب التشغيل، وhsaai-migration-secret منفصلًا يحوي DATABASE_URL لحساب الترحيل. جهز documents-data ومخزن embedding-models، ونفذ مهمة release-prerequisites.yaml قبل قبول حركة التشغيل. الـPVC الفارغ لا يحتوي أوزانًا. راجع صلاحيات UID1000 ومسارات /data و/models.

```bash
helm lint infrastructure/helm
helm template hsaai infrastructure/helm --namespace hsaai > rendered-hsaai.yaml
kubectl kustomize infrastructure/kubernetes/overlays/production > rendered-kustomize.yaml
```

استخدم أحد مساري Helm/Kustomize في النشر بعد تعديل إعداداته والتحقق منه. حُصر RAG وagent-runtime في نسخة واحدة لأن هناك حالة SQLite/ذاكرة محلية؛ نقلهما إلى عدة replicas يتطلب مخزن حالة موزعًا واختبارًا. إعادة إنشاء هذه الوحدات تستلزم نافذة صيانة، ولا يصح ادعاء انعدام التوقف لها.

## مصفوفة قبول التشغيل

| الاختبار | دليل القبول المطلوب |
|---|---|
| بناء وتشغيل الخدمات | سجلات build وأسماء الصور وdigests وحالة health/ready لكل خدمة |
| المصادقة | مستخدمون فعليون، أدوار مختلفة، تدوير مفاتيح، جلسة منتهية، منع تجاوز المصادقة |
| عزل البيانات | مستأجران ومساحتان؛ رفع/بحث/حذف/ذاكرة/cache/سجلات؛ لا تسرب |
| RAG عربي | مستندات نصية وممسوحة، صفحات ومراجع صحيحة، رفض الإجابة دون مصدر |
| الاستدلال | نموذج فعلي؛ بث وإلغاء وتزامن وقياس زمن أول رمز |
| الوكلاء والتكاملات | إجراءات قراءة أولًا، موافقة بشرية قبل أي أثر خارجي، أثر تدقيق |
| الأداء | أحمال 1,000 و10,000 وفق PDF على موارد مناسبة، نتائج وأهداف متفق عليها |
| الأمان | صور وتبعيات/SAST واختبار اختراق مستقل، إغلاق النتائج الحرجة |
| التغطية | بلوغ 80% مع بقاء الإخفاقات والتخطي ظاهرة |
| التعافي | استعادة إلى قاعدة منفصلة، مقارنة عدد السجلات، قياس RPO/RTO |
| الواجهة | RTL، الوضعان، هاتف ولوحة مفاتيح وقارئ شاشة وتباين |

scripts/production_acceptance_check.sh يحتاج API_URL للبوابة الداخلية ورمزًا قصير العمر في HSAAI_ACCEPTANCE_TOKEN؛ هو smoke للاستدلال والوصول فقط. استخدم scripts/restore_postgres_drill.sh مع قاعدة جديدة يبدأ اسمها hsaai_restore_*. لا يشغّل أي منهما وحده قبول المنصة بالكامل.

تبقى قرارات الأعمال والمدفوعات والنشر وتعديل بيانات الشركة خاضعة لصلاحيات وموافقات بشرية. يوثق توقيع القبول مالك المنصة والأمن والبيانات والتشغيل مع تاريخ التنفيذ وأرقام الصور ونتائج الاختبارات.
