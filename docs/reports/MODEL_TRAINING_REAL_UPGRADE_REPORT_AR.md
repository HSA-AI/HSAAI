# تقرير تطوير تدريب النماذج الفعلي - HSAAI

## الهدف
رفع وحدة Model Training من Placeholder فقط إلى بنية تشغيل فعلية قابلة لتدريب LoRA/QLoRA محلياً داخل المؤسسة، مع الحفاظ على الوضع الافتراضي الآمن Simulation.

## الملفات التي تم إنشاؤها

### داخل `services/model_training`
- `schemas.py` — أنواع بيانات التدريب والحالات والقدرات.
- `storage.py` — تخزين Jobs وLogs محلياً على الملفات.
- `adapters/base.py` — واجهة Adapter عامة للتدريب.
- `adapters/lora_runner.py` — Adapter فعلي يشغل LoRA/QLoRA عبر subprocess عند تفعيل Real Mode.
- `trainer/local_trainer.py` — Trainer فعلي يستخدم Transformers + PEFT + Datasets.
- `requirements-training.txt` — اعتمادات اختيارية للتدريب الحقيقي على GPU.
- `configs/lora.qwen.sample.json` — مثال Job لتدريب LoRA.
- `configs/qlora.qwen.sample.json` — مثال Job لتدريب QLoRA.
- `README_REAL_TRAINING_AR.md` — تعليمات التشغيل الفعلي.

## الملفات التي تم تعديلها
- `services/model_training/main.py` — تحويل الخدمة إلى API كاملة لإدارة وتشغيل التدريب.
- `apps/web/modules/training/training.types.ts` — إضافة حالات التشغيل الفعلي وحقول maxSeqLength/outputDir.
- `apps/web/modules/training/training.adapter.ts` — إضافة FastApiTrainingAdapter بجانب MockTrainingAdapter.
- `apps/web/modules/training/training.service.ts` — ربط الواجهة بخدمة FastAPI عند توفر `MODEL_TRAINING_SERVICE_URL`.
- `apps/web/app/api/training/jobs/*` — تحويل API routes إلى async وربطها بالـ adapter الحقيقي.
- `apps/web/app/admin/model-training/page.tsx` — لوحة تدريب متصلة بالـ API مع Create/Cancel/Logs.
- `docker-compose.hsa-internal.yml` — ربط frontend بالشبكة الداخلية وإضافة متغيرات خدمة التدريب.
- `.env.hsa-internal.example` — إضافة إعدادات Real/Simulation mode.

## ما الذي أصبح جاهزاً الآن
- إنشاء Training Job من الواجهة.
- إرسال Job إلى خدمة FastAPI عند ضبط `MODEL_TRAINING_SERVICE_URL`.
- تشغيل Simulation آمن افتراضياً.
- تشغيل subprocess حقيقي للتدريب عند ضبط `MODEL_TRAINING_EXECUTION_MODE=real`.
- دعم برمجي لـ LoRA و QLoRA عبر PEFT.
- حفظ Jobs وLogs محلياً.
- Cancel يحاول إيقاف PID الخاص بعملية التدريب.
- لا يوجد أي اعتماد على OpenAI أو Claude أو Gemini أو DeepSeek.

## ما يزال يحتاج بيئة فعلية
- GPU Server داخلي.
- CUDA/PyTorch متوافقان.
- تحميل النموذج الأساسي داخل `/data/models`.
- Dataset JSONL حقيقي داخل `/data/training/datasets`.
- ضبط batch size وmax sequence حسب VRAM.
- اختبار طويل للتدريب على بيانات المؤسسة.

## أوامر تشغيل الخدمة محلياً
```bash
cd services/model_training
pip install -r requirements.txt
pip install -r requirements-training.txt
MODEL_TRAINING_EXECUTION_MODE=simulation uvicorn main:app --host 0.0.0.0 --port 8093
```

للتشغيل الفعلي:
```bash
MODEL_TRAINING_EXECUTION_MODE=real uvicorn main:app --host 0.0.0.0 --port 8093
```

## إنشاء Job من API
```bash
curl -X POST http://localhost:8093/v1/training/jobs \
  -H "Content-Type: application/json" \
  -d @services/model_training/configs/lora.qwen.sample.json
```

## ربط الواجهة بالخدمة
في `.env` الخاص بالواجهة:
```bash
MODEL_TRAINING_SERVICE_URL=http://localhost:8093
```

ثم:
```bash
cd apps/web
npm install
npm run dev
```

## ملاحظة مهمة
الوضع الافتراضي يبقى Simulation حتى لا يبدأ أي حمل GPU بالخطأ. التدريب الحقيقي لا يعمل إلا عند تفعيل `MODEL_TRAINING_EXECUTION_MODE=real` وتوفير بيئة GPU واعتمادات التدريب.
