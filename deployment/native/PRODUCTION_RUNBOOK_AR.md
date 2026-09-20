# HSAAI — دليل التشغيل الإنتاجي (Native Deployment Runbook) — v3.0.0

> هذه الوثيقة موجهة لمشغّل المنصة (Ops/SRE). تغطي التثبيت من الصفر، الأسرار، الجاهزية، النسخ الاحتياطي/الاستعادة، الترقية، واستكشاف الأخطاء — للنشر المحلي الأصلي (بلا Docker) على Linux.

---

## 0) متى تستخدم هذا المسار؟

| السيناريو | المسار المناسب |
|---|---|
| Sandbox/بيئة مقيدة بلا root ولا systemd ولا Docker | **هذا المسار (Native)** — عبر `hsaai-ctl` |
| مضيف إنتاجي VM/VPS لديه root + systemd | Native + وحدات systemd: `deployment/production/install-systemd-units.sh` |
| مضيف Docker قادر والستاك الكامل (33 خدمة، 32GB+ RAM) | `docker-compose.yml` الأصلي كما هو |

---

## 1) التثبيت من الصفر (10 دقائق تقريبًا)

```bash
# 1. فعّل بيئة المسارات (اكتشاف تلقائي — لا مسارات مثبتة يدويًا)
source deployment/native/hsaai-env.sh

# 2. نزّل وفكّ ثنائيات النظام إلى rootfs المستخدم (بلا root)
bash deployment/native/setup-runtime.sh          # يحتاج deb_urls.txt (راجع رسالة الخطأ إن غاب)

# 3. بيئة الواجهة الخلفية + تبعيات الواجهة الأمامية
python3 -m venv .venv-backend && .venv-backend/bin/pip install -r services/backend_core/requirements.txt
cd apps/web && npm install && npm run build && cd ../..

# 4. طبقة البيانات لأول مرة (تُنشأ في $RUNTIME/data)
mkdir -p "$HSAOI_DATA/sockets"
initdb -D "$HSAOI_DATA/pgdata" -U hsaai --auth-local=scram-sha-256 --auth-host=scram-sha-256
#   ثم عدّل postgresql.conf: unix_socket_directories='$HSAOI_DATA/sockets'

# 5. الأسرار (إلزامي في الإنتاج)
bash deployment/native/generate-secrets.sh

# 6. فحص الجاهزية قبل البدء
bash deployment/native/preflight-check.sh

# 7. ابدأ المنصة وشارّ
bash deployment/native/hsaai-ctl start all
curl -s http://127.0.0.1:8000/ready
```

---

## 2) الأسرار وبيئة التشغيل

- ملف واحد: `<project>/.env.native` — يُولّد بـ `generate-secrets.sh` بصلاحيات `600` ولا يُطبع محتواه أبدًا.
- `hsaai-ctl` يقرؤه تلقائيًا إن وُجد: `HSAAI_DB_PASSWORD`، `HSAAI_CLIENT_SECRET`، `DESKTOP_API_TOKEN`، `HSAAI_APP_ENV=production`.
- **بدون** الملف تعمل المنصة بقيم تطوير افتراضية للتوافق — لا تقبل هذا في إنتاج.
- تدوير كلمة قاعدة البيانات على عنقود قائم:
  ```bash
  psql -h 127.0.0.1 -U hsaai -d hsaai -c "ALTER USER hsaai PASSWORD '<الجديد>';"
  bash deployment/native/hsaai-ctl restart backend
  ```
- أضِف `.env.native` إلى `.gitignore` (يفحصها preflight وينبّه إن غاب).
- على المضيف systemd تُنسخ الأسرار إلى `/etc/hsaai/hsaai.env` (600) تلقائيًا من المثبّت.

---

## 3) العمليات اليومية

```bash
bash deployment/native/hsaai-ctl status                 # حالة 8 خدمات
bash deployment/native/hsaai-ctl {start|stop|restart} all
bash deployment/native/hsaai-ctl restart backend        # خدمة واحدة
curl -s http://127.0.0.1:8000/ready | python3 -m json.tool
tail -f "$HSAOI_LOGS/backend-core.log"                  # سجلات كل خدمة في $HSAOI_LOGS
```

فحوص الصحة: `pg_isready` / `redis-cli ping` / `qdrant /healthz` / `backend /health و /ready` / `web /login` / `idp /health` / `gateway /health` / `noVNC /vnc.html`.

---

## 4) النسخ الاحتياطي والاستعادة

```bash
# نسخ متسق أونلاين (pg_dump متسق بـ MVCC + BGSAVE لـ Redis + snapshot API لـ Qdrant)
bash deployment/native/backup-native.sh                 # الافتراضي: $RUNTIME/backups/<timestamp>/
bash deployment/native/backup-native.sh /mnt/backups    # قرص خارجي/شبكة

# استعادة (أوقف backend أولاً إن رغبت باتساق تام، ثم)
bash deployment/native/restore-native.sh <backup_dir> --drop
bash deployment/native/hsaai-ctl restart backend
```

- مدة الاحتفاظ: آخر 14 نسخة (تلقائيًا). جدول نسخ يومي مقترح عبر cron للمضيف الخارجي.
- اختبر الاستعادة دوريًا على بيئة ملحقة — نسخة غير مُختبرة ليست نسخة احتياطية.

---

## 5) الترقية (نسخة جديدة من الكود)

```bash
bash deployment/native/hsaai-ctl stop backend web
# حدّث الكود (git pull أو فك الحزمة الجديدة فوق القديمة مع الاحتفاظ بـ .env.native)
USE_ALEMBIC=true .venv-backend/bin/alembic upgrade head     # ترحيلات مُراجعة يدويًا فقط
cd apps/web && npm ci && npm run build && cd ../..
bash deployment/native/hsaai-ctl start all
curl -s http://127.0.0.1:8000/ready
```

التراجع: أعد فك النسخة السابقة + `alembic downgrade` إذا اقتضى الأمر (راجع سجل الترحيلات قبل أي downgrade).

---

## 6) قائمة أمان الإنتاج (مراجعة قبل التشغيل الفعلي)

- [ ] `.env.native` موجود بصلاحيات 600 وغير ملتزم بـ Git
- [ ] `HSAAI_APP_ENV=production` (وليس development)
- [ ] قواعد البيانات تستمع على `127.0.0.1` حصرًا (preflight يفحص المنافذ)
- [ ] `x11vnc` مقيد بـ localhost والوصول للبشر عبر noVNC خلف مصادقة/عكس وكيل TLS
- [ ] التوكن `desktop-gateway-token.txt` بصلاحيات 600 (البوابة ترفض 401 بدونه)
- [ ] لا منفذ إداري/بيانات مكشوف على واجهة عامة: 5432/6379/6333/5999/8600 داخلية
- [ ] نسخ احتياطي مجدول + استعادة مُختبرة
- [ ] سجلات تُجمَّع خارجيًا (rsyslog/vector → SIEM) مع تدوير
- [ ] تحديثات أمنية للـ rootfs دوريًا (أعد setup-runtime.sh لجلب تصحيحات Debian)
- [ ] Keycloak الحقيقي (بدل demo IdP) عند الانتقال لإنتاج مؤسسي فعلي

---

## 7) استكشاف الأخطاء

| العَرَض | الفحص | العلاج الشائع |
|---|---|---|
| `hsaai-ctl status` = DOWN لخدمة | `tail -50 $HSAOI_LOGS/<service>.log` | منفذ مشغول؟ ذاكرة؟ مكتبات LD_LIBRARY_PATH؟ |
| backend يفشل بالإقلاع | `.venv-backend/bin/python -c "import _demo_oidc_shim"` | بيئة venv تالفة → أعد إنشاءها |
| `401 invalid or missing X-API-Token` | توكن العميل ≠ `runtime/desktop-gateway-token.txt` | مرّر `DESKTOP_API_TOKEN` الصحيح (ctl يثبته تلقائيًا) |
| `/ready` يرجع database down | `pg_isready -h 127.0.0.1 -p 5432` | postgres متوقف؟ كلمة المرور بعد تدوير غير محدّثة في `.env.native`؟ |
| سطح المكتب أسود | `ps aux | grep Xvfb` | `hsaai-ctl restart desktop` ثم تحقق من `$HSAOI_LOGS/desktop-*.log` |
| نفاد القرص | `df -h $HSAOI_DATA` | نظّف `$RUNTIME/logs` القديمة + قلّص الاحتفاظ بالنسخ |

---

## 8) معايير القبول بعد أي نشر/ترقية

1. `hsaai-ctl status` → 8/8 UP.
2. `curl /ready` → `status: ready` مع database ok + qdrant ok.
3. `GET /login` → 200، ودخول OIDC كامل يعمل.
4. `preflight-check.sh` → لا FAIL (تحذيرات مقبولة إن كانت مبررة وموثقة).
5. `test-desktop-input.py` → PASS (اختبار إدخال حقيقي عبر VNC).
6. نسخة احتياطية ناجحة + استعادة ناجحة على بيئة اختبار.
