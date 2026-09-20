# تقرير قبول إنتاجي عملي لمنصة HSAAI

هذا التقرير ليس إعلان جاهزية نظري. الاعتماد الإنتاجي لا يتم إلا بعد تشغيل السكربت:

```bash
./scripts/production_acceptance_check.sh
```

## ما الذي يتحقق منه السكربت؟

1. صحة ملف Docker Compose.
2. بناء وتشغيل الخدمات.
3. صحة API Gateway والواجهة.
4. صحة Backend / Auth / Orchestrator / RAG / LLM Gateway.
5. توفر نموذج Ollama المحلي وسحبه عند عدم وجوده.
6. إرسال رسالة حقيقية إلى `/v1/chat` عبر API Gateway.
7. رفع ملف نصي إلى `/v1/rag/documents/upload`.
8. البحث عن marker داخل Qdrant بعد الفهرسة.
9. حفظ أدلة JSON في `/tmp/hsaai_acceptance`.

## معيار النجاح

تعتبر النسخة مقبولة تقنيًا للتجربة الداخلية عندما يظهر:

```text
PASS: HSAAI compose, chat, local LLM gateway, RAG upload/search and health checks completed.
```

## ملاحظات مهمة

- في بيئة الإنتاج يجب ضبط `AUTH_REQUIRED=true` و `ALLOW_DEV_AUTH=false`.
- في بيئة التطوير يمكن استخدام `docker-compose.dev.yml` مع `AUTH_REQUIRED=false` لتسهيل الاختبار.
- لا يعتبر وجود الملفات أو التقارير كافيًا دون تشغيل هذا الاختبار وتوثيق مخرجاته.
