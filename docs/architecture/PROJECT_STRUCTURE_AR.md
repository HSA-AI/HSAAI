# هيكل مشروع HSAAI الداخلي

هذا هو الشكل المعتمد لتسليم مشروع HSAAI كمنصة ذكاء اصطناعي داخلية خاصة بالشركة:

```text
HSAAI/
├─ backend/                   # الخدمة الخلفية الأساسية
├─ api_gateway/               # بوابة API
├─ ai_orchestrator/           # المحرك الموحد لتوجيه الرسائل للنماذج والوكلاء
├─ llm_gateway/               # خدمة النماذج اللغوية المحلية (Internal LLM)
├─ rag_engine/                # البحث في الوثائق الداخلية (RAG)
├─ multi_agents/              # الوكلاء الذكيون (HR, Finance, Executive, Knowledge, IT)
├─ auth_service/              # المصادقة والتوثيق عبر Keycloak أو AD
├─ frontend/                  # واجهة المستخدم (Next.js + React)
├─ document_ai/               # تحليل المستندات الداخلية (OCR / Text extraction)
├─ voice_ai/                  # TTS / STT داخلي
├─ analytics/                 # لوحة بيانات وتحليلات استخدام
├─ monitoring/                # Prometheus / Grafana / OTEL
├─ deployment/                # ملفات Docker / Kubernetes / Compose / Security / Tests
├─ scripts/                   # سكربتات تحقق وتشغيل داخلي
├─ docs/                      # وثائق التشغيل، دليل المستخدم، Blueprint داخلي
├─ .env.hsa-internal.example  # إعدادات بيئة التشغيل الداخلي
└─ docker-compose.hsa-internal.yml
```

## ملاحظات تنظيمية

- ملفات Kubernetes وInfrastructure نُقلت إلى `deployment/` لتوحيد ملفات النشر.
- ملفات التقارير والإعدادات الإضافية محفوظة داخل `docs/reports/`.
- اختبارات المشروع محفوظة داخل `deployment/tests/`.
- `workflow_engine` و`connectors` محفوظة داخل `backend/` لأنها منطق خلفي داخلي.
