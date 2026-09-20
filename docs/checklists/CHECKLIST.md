# HSAAI Validation Checklist

## 1. Install dependencies

```bash
cd apps/web
npm install
```

## 2. Run development server

```bash
npm run dev
```

Open the local URL and validate these pages:

- `/admin/model-training`
- `/admin/model-providers`
- `/admin/local-models`
- `/agent-builder`
- `/workflow-builder`
- `/admin/models`
- `/dashboard`
- `/knowledge`

## 3. Validate API routes

```bash
curl http://localhost:3000/api/training/jobs
curl http://localhost:3000/api/model-providers
curl http://localhost:3000/api/local-models
curl http://localhost:3000/api/agent-builder
curl http://localhost:3000/api/workflow-builder
```

## 4. Run build

```bash
npm run build
```

## 5. Run lint

```bash
npm run lint
```

## 6. Run type/test check

```bash
npm run type-check
npm run test
```

## Acceptance rule

Do not mark this project as production-ready until all of the following pass on the target machine:

- `npm install`
- `npm run build`
- `npm run lint`
- `npm run dev`
- manual page checks
- API route checks

## Current implementation note

The new AI platform control-plane modules are architectural placeholders and simulations. They do not execute real LoRA, QLoRA, vLLM, GPU inference, heavy model uploads, or real workflow execution yet.

## Model Training Real-Ready Validation

- [ ] تشغيل خدمة التدريب: `cd services/model_training && pip install -r requirements.txt && uvicorn main:app --port 8093`
- [ ] فحص الصحة: `curl http://localhost:8093/health`
- [ ] فحص القدرات: `curl http://localhost:8093/v1/capabilities`
- [ ] تجربة Simulation Job: `curl -X POST http://localhost:8093/v1/training/jobs -H "Content-Type: application/json" -d @configs/lora.qwen.sample.json`
- [ ] ضبط `MODEL_TRAINING_SERVICE_URL=http://localhost:8093` في واجهة Next.js.
- [ ] فتح `/admin/model-training` والتأكد من ظهور Jobs وLogs.
- [ ] للتشغيل الحقيقي فقط: تثبيت `requirements-training.txt` على GPU Server داخلي.
- [ ] للتشغيل الحقيقي فقط: ضبط `MODEL_TRAINING_EXECUTION_MODE=real`.
- [ ] للتشغيل الحقيقي فقط: التأكد من وجود النموذج المحلي وDataset JSONL.
