# HSAAI Model Training - تشغيل تدريب فعلي محلي

هذه الوحدة لم تعد Placeholder فقط. أصبحت تحتوي على Adapter فعلي قابل لتشغيل LoRA/QLoRA محلياً عبر PEFT/Transformers عندما تتوفر بيئة GPU داخل المؤسسة.

## أوضاع التشغيل

### 1) Simulation Mode - الافتراضي الآمن
```bash
MODEL_TRAINING_EXECUTION_MODE=simulation
```
يسجل Job وخطة التدريب والـ logs بدون تشغيل GPU.

### 2) Real Mode - تشغيل فعلي
```bash
MODEL_TRAINING_EXECUTION_MODE=real
pip install -r requirements.txt
pip install -r requirements-training.txt
uvicorn main:app --host 0.0.0.0 --port 8093
```

## إنشاء Job فعلي
```bash
curl -X POST http://localhost:8093/v1/training/jobs \
  -H "Content-Type: application/json" \
  -d @configs/lora.qwen.sample.json
```

## المتطلبات الحقيقية
- GPU Server داخلي.
- CUDA متوافق مع PyTorch.
- نموذج أساس محفوظ محلياً داخل `/data/models`.
- Dataset بصيغة JSONL محفوظ محلياً.
- عدم استخدام أي API خارجي.

## صيغة Dataset مقترحة
```jsonl
{"text":"<instruction>اكتب سياسة مختصرة...</instruction>\n<answer>...</answer>"}
{"prompt":"ما سياسة الإجازات؟","response":"..."}
```

## ما الذي أصبح فعلياً؟
- API لإنشاء وتشغيل Jobs.
- Adapter يشغل subprocess حقيقي عند تفعيل Real Mode.
- Trainer يستخدم Transformers + PEFT.
- دعم LoRA و QLoRA من ناحية التنفيذ البرمجي.
- Logs محفوظة لكل Job.
- Cancel يحاول إيقاف عملية التدريب.

## ما الذي يحتاج بيئة خارج هذا الملف؟
- تثبيت CUDA و GPU Drivers.
- تحميل النموذج المحلي.
- تجهيز Dataset حقيقي.
- اختبار ذاكرة GPU وضبط batch/sequence length.
