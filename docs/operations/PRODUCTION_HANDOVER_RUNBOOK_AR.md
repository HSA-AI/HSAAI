# دليل استلام وتشغيل HSAAI_v1

هذه حزمة مرشحة 4.0.0-rc.2. اسم الأرشيف الذي طلبه المالك HSAAI_v1.zip لا يعني الرجوع إلى شيفرة الإصدار الأول. يبدأ القرار من `START_HERE_AR.md` و`FINAL_PRODUCTION_READINESS_REPORT.md`. التقارير السابقة محفوظة كسجل تاريخي.

## 1. الاستلام والحفاظ على البيانات

تحقق من SHA-256 الخارجي، ثم من `HSAAI/SHA256SUMS.txt` داخل الحزمة. فك الضغط في مجلد جديد. لا تستبدل ملفات نشر أو قواعد بيانات قائمة. خذ نسخًا من PostgreSQL وQdrant وMinIO ومجلد `/data` وملف ملح التشفير قبل الترحيل. احتفظ بمفتاح تشفير البيانات والملح الأصليين؛ تغيير أحدهما يعطل فك تشفير البيانات القديمة. لا تشغّل مولد أسرار جديد فوق إعداد نشر قائم.

```bash
sha256sum -c HSAAI_v1.zip.sha256
unzip HSAAI_v1.zip -d hsaai-v1-review
cd hsaai-v1-review/HSAAI
sha256sum -c SHA256SUMS.txt
```

## 2. بيئة قبول معزولة

استخدم مضيف Linux بصلاحيات تشغيل Docker Engine 24+ وCompose v2 ومساحة للنماذج والبيانات. خطة المستخدم: Ubuntu 24.04، ذاكرة 32GB حد أدنى و64GB أو أكثر موصى بها، و200GB SSD أو أكثر. هذه مواصفات تخطيطية لم تُختبر عليها السعة. يلزم Cluster حقيقي، سجل صور، DNS وTLS، مزود تخزين وIngress، وهوية Keycloak ومستخدمون تجريبيون في مستأجرين ومساحات عمل مختلفة. اختبارات GPU تحتاج بطاقة NVIDIA وبرنامج تشغيل وContainer Toolkit متوافقين.

```bash
docker version
docker compose version
docker info
kubectl version --client
kubectl config current-context
nvidia-smi
```

شغّل الأمر الأخير عند استخدام GPU. عدم وجود GPU لا يعفي تشغيل النموذج فعليًا على CPU إن كان هذا نمط التسليم المتفق عليه.

## 3. إعداد الإنتاج

المسار المرجعي هو `docker-compose.production.yml` في الجذر. الملفات البديلة محفوظة، ولا يُجمع بعضها عشوائيًا مع هذا المسار. اختر اسمي DNS مملوكين للشركة ومفعّلًا عليهما HTTPS، ثم أدخلهما دون مسار:

```bash
read -r -p 'Application HTTPS origin: ' HSAAI_APP_ORIGIN
read -r -p 'Identity HTTPS origin: ' HSAAI_IDENTITY_ORIGIN
python3 scripts/configure_production.py \
  --app-url "$HSAAI_APP_ORIGIN" \
  --identity-url "$HSAAI_IDENTITY_ORIGIN" \
  --output-dir deployment/generated-v1
export HSAAI_ENV_FILE="$PWD/deployment/generated-v1/.env.production"
python3 scripts/validate_environment.py --env-file "$HSAAI_ENV_FILE"
```

المولد يرفض الكتابة فوق إعداد سابق. يولّد مفاتيح عشوائية وملف إعداد بصلاحية 0600 دون مستخدمين أو كلمات مرور اختبارية في Realm. احتفظ بالمجلد خارج Git والحزمة. تضبط الإعدادات DEBUG=false وPKCE وSecure cookies وaudience والتحقق الإلزامي من الهوية. أضف اعتمادات الموصلات المعتمدة فقط. `HSAAI_ROLE_CLIENT_IDS` يحدد عملاء OAuth الذين تُقبل أدوارهم؛ أدوار عملاء آخرين لا تُمنح صلاحيات HSAAI. Outlook باستخدام app-only يحتاج `OUTLOOK_SENDER_UPN`، ولا يعتمد على `/me`.

جهّز TLS على reverse proxy/DNS العام؛ لا تنشر المنافذ الداخلية لقواعد البيانات وواجهات الإدارة. راجع ملفات `/data` ومجلد النماذج وأذونات المستخدم غير الجذر. ثبّت النموذج ونسخته وأوزانه قبل اختبار AI؛ لا تعتبر وجود اسم النموذج تحميلًا ناجحًا.

## 4. بناء وتشغيل Docker والتحقق

```bash
docker compose --env-file "$HSAAI_ENV_FILE" -f docker-compose.production.yml config -q
docker compose --env-file "$HSAAI_ENV_FILE" -f docker-compose.production.yml build
docker compose --env-file "$HSAAI_ENV_FILE" -f docker-compose.production.yml up -d
docker compose --env-file "$HSAAI_ENV_FILE" -f docker-compose.production.yml ps -a
docker compose --env-file "$HSAAI_ENV_FILE" -f docker-compose.production.yml logs --tail=100
docker stats --no-stream
```

يوجد 33 خدمة مستمرة ضمن الوضع الافتراضي ومهمتان مؤقتتان (`db-migrate`, `minio-init`) و22 خدمة موسعة ضمن profiles. نجاح المهمة المؤقتة يعني exit 0؛ لا تُحسب ضمن عدد healthy. تحقق من كل خدمة في `docs/reports/evidence/production-service-inventory.json`: الحاوية، Health، السجلات، عدد إعادة التشغيل، DNS الداخلي، الاتصال بالتبعيات، ملكية الملفات والقراءة والكتابة. بعض صور البنية التحتية لا تملك healthcheck صريحًا في Compose؛ يجب إكمالها واختبارها قبل القبول. لا توقف Health Checks لإخفاء عطل.

## 5. قواعد البيانات والترحيلات

وظيفة `db-migrate` تستخدم حساب الترحيل، والخلفية تستخدم `hsaai_app` دون تجاوز RLS. يرفض بدء الخلفية schema قديمة أو دورًا يتجاوز RLS. راجع جميع الترحيلات حتى `0008_knowledge_permission_scope`، بما فيها 0006 استكمال schema و0007 حقول الموافقات و0008 نطاق صلاحيات المعرفة. قيم `default` القديمة تحتاج مراجعة ملكية ومهاجرة معتمدة إلى مستأجري الشركة؛ لا تعيّن ملكية افتراضية اعتباطية.

على قاعدة قبول جديدة: شغّل الترحيلات مرتين، تحقق من القيود والفهارس، seed، القراءة والكتابة، حساب التطبيق، منع الوصول بين مستأجرين، ومطابقة Alembic head. اختبر PostgreSQL وRedis وQdrant وNeo4j وMinIO وMLflow/Keycloak وأي مخزن فعلي. ملفات backup موجودة تحت `scripts/backup_postgres.sh`, `scripts/backup_qdrant.sh`, `scripts/restore_postgres_drill.sh`. افحص متغيراتها قبل استخدامها، واستعد النسخة إلى قاعدة منفصلة؛ لا تستخدم استعادة تجريبية فوق بيانات الشركة.

## 6. الاختبارات وSSO وAI

```bash
python3 -m venv .venv-qa
. .venv-qa/bin/activate
python -m pip install -r requirements-validation.txt
python -m pytest tests
cd apps/web
npm ci
npm run lint
npm run type-check
npm test
npm run build
cd ../..
```

أمر pytest يفشل حاليًا بسبب بوابة 80%، حتى مع نجاح الاختبارات. لا تخفّض البوابة ولا تغيّر مصادر coverage. الاختبارات وحدات وعقود محلية؛ حدود HTTP/LLM المقلدة معلنة داخل الاختبارات.

لتشغيل الاختبارات الـ13 عبر النظام الحقيقي، اضبط `HSAAI_E2E_BASE_URL`، `HSAAI_E2E_REGULAR_USERNAME`, `HSAAI_E2E_REGULAR_PASSWORD`, `HSAAI_E2E_ADMIN_USERNAME`, `HSAAI_E2E_ADMIN_PASSWORD` في secret manager/بيئة جلسة خاصة، ثم `HSAAI_E2E_REQUIRED=true`. عندها غياب الاعتمادات ينتج فشلًا، ولا يتحول إلى Skip. لا تسجل كلمات المرور أو access tokens في ملفات الأدلة.

اختبر login/logout/refresh، JWT تالف ومنتهي، RBAC/ABAC، الأدمن والمستخدم العادي، فصل المستأجر ومساحة العمل، وتسجيل التدقيق. نفّذ المسار الكامل: رفع سياسة اختبارية → مراجعة مستقلة → فهرسة فعلية → embedding → استرجاع متجهات ضمن النطاق → نموذج محلي → إجابة بمراجع → عرض المتصفح. كرر مع نموذج/متجهات/قاعدة غير متاحة، وتحقق من timeout/retry ومن عدم إصدار نجاح مصطنع. طبقة phase5 تبلغ الفشل عند تعطل النموذج؛ مسار Enterprise OS القديم يعلن `routed` أو `awaiting_approval` ولا يدّعي تنفيذ أداة. اعتماد الموافقة لا يعني تنفيذ الإجراء بالفعل؛ يلزم ربط executor واختبار استئناف موثوق بعد إعادة التشغيل.

## 7. Kubernetes

المسار الأساسي `infrastructure/kubernetes/overlays/production`، ومسار Helm بديل. لا تطبّق الاثنين على نفس الموارد. جهّز namespaces، external secrets، registry/images بـtag 4.0.0-rc.2 أو digests مثبتة، StorageClass/PVC، Ingress/TLS وموارد الهوية/النماذج/قواعد البيانات حسب البيئة. قيم الأمثلة ليست إعداد شركة صالحًا للتطبيق المباشر.

```bash
helm lint infrastructure/helm
helm template hsaai infrastructure/helm > deployment/rendered-review.yaml
kubectl apply --dry-run=server -k infrastructure/kubernetes/overlays/production
kubectl apply -k infrastructure/kubernetes/overlays/production
kubectl get pods -A
kubectl get svc -A
kubectl get deployments -A
kubectl get events -A
```

نفّذ apply الحقيقي على Cluster القبول المعزول بعد مراجعة الإعداد. تحقق من rollout، startup/readiness/liveness، PDB، استعادة Pod، الأذونات الشبكية، Resource requests/limits، autoscaling والتخزين. YAML/Helm الناجح محليًا لا يثبت النشر.

## 8. المراقبة والأعطال والأداء

تحقق من Prometheus targets، Grafana dashboards، Loki logs، Tempo/OTEL traces، قواعد الإنذار ووصول إشعار إلى قناة اختبار مصرح بها. راقب readiness وتغير حالة التبعيات. اختبر إيقاف قاعدة البيانات ثم Redis وQdrant وخدمة AI والخلفية، واحدة تلو الأخرى على بيئة القبول فقط، ثم أعد تشغيل كل خدمة وتحقق من الاستعادة وبقاء البيانات وعدم تكرار الأدوات أو الموافقات. سجّل p50/p95/p99 والأخطاء تحت الحمل مع CPU/RAM واستخدام GPU. حدود 1,000 و10,000 مستخدم الواردة في PDF تحتاج سيناريوهات وسعة فعلية؛ قياس `/api/health` المحلي لا يثبتها.

## 9. إعادة بناء نظيفة والاعتماد

```bash
docker compose --env-file "$HSAAI_ENV_FILE" -f docker-compose.production.yml down
docker compose --env-file "$HSAAI_ENV_FILE" -f docker-compose.production.yml build --no-cache
docker compose --env-file "$HSAAI_ENV_FILE" -f docker-compose.production.yml up -d
python -m pytest tests
```

لا تضف `-v` إلى down؛ حافظ على volumes. أعد اختبارات التكامل والمتصفح والنسخ والاستعادة والمسح الأمني للصور والتبعيات الفعلية، وليس بيئة QA فقط. أغلق Findings المرتفعة وبنود PDF الإلزامية والتغطية قبل توقيع القبول. لا يجوز إخفاء البنود البحثية والعالمية في PDF باعتبارها غير مطلوبة دون تعديل رسمي للمتطلبات من المالك.
