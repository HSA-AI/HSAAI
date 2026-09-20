# تقرير تطوير RAG المتقدم في HSAAI

تمت إضافة طبقة RAG محسّنة إلى النسخة المختبرة من HSAAI، مع الحفاظ على بنية المشروع الحالية.

## الميزات التي تمت إضافتها

1. **OCR**
   - دعم OCR للصور: PNG / JPG / JPEG / TIFF.
   - دعم OCR لملفات PDF الممسوحة ضوئيًا عند عدم وجود نص قابل للاستخراج.
   - يعتمد على: `tesseract-ocr`, `tesseract-ocr-ara`, `tesseract-ocr-eng`, `poppler-utils`, `pytesseract`, `pdf2image`, `Pillow`.

2. **Citation System**
   - كل نتيجة تحتوي على: اسم الملف، رقم الصفحة إن وجد، رقم المقطع، بداية ونهاية النص.
   - Endpoint جديد: `/v1/answer` يرجع `sources` منظمة للاستشهادات.

3. **Streaming Responses**
   - Endpoint جديد: `/v1/answer/stream` باستخدام `text/event-stream`.
   - API Gateway يدعم تمرير الـ SSE من RAG Engine.

4. **Better Chunking**
   - تقسيم ذكي للجمل العربية والإنجليزية.
   - Overlap مضبوط.
   - حفظ offsets للمصدر.
   - حفظ heading عند توفره.

5. **Hybrid Search**
   - بحث Semantic بالـ embeddings.
   - بحث Lexical باستخدام BM25.
   - وضع `hybrid` يجمع بين الاثنين.

6. **Re-ranking**
   - إعادة ترتيب النتائج حسب semantic + BM25 + proximity.
   - مناسب للبحث العربي داخل وثائق المؤسسة.

7. **Arabic Embedding Optimization**
   - تطبيع الحروف العربية: أ/إ/آ، ة، ى، التشكيل، التطويل.
   - Tokenization عربي/إنجليزي مخصص.

8. **Source Highlighting**
   - Endpoint جديد: `/v1/highlight`.
   - واجهة Knowledge تعرض الكلمات المطابقة باستخدام highlight.

## الملفات الجديدة أو المعدلة

- `services/rag_engine/chunking.py`
- `services/rag_engine/reranker.py`
- `services/rag_engine/loaders.py`
- `services/rag_engine/main.py`
- `services/rag_engine/requirements.txt`
- `services/rag_engine/Dockerfile`
- `services/api_gateway/main.py`
- `services/backend_core/rag/proxy_router.py`
- `apps/web/services/rag.service.ts`
- `apps/web/app/knowledge/page.tsx`
- `tests/unit/test_advanced_rag_features.py`

## نتائج الفحص

- `pytest`: نجح، 8 اختبارات.
- `validate_project_structure.py`: نجح.
- `verify_internal_only.py`: نجح.
- `validate_yaml_files.py`: نجح.
- `production_release_gate.sh`: نجح.
- TypeScript check للواجهة: نجح عبر `tsc --noEmit`.

## ملاحظة مهمة للتشغيل

لكي يعمل OCR فعليًا داخل Docker يجب إعادة بناء حاوية RAG Engine:

```bash
docker compose -f docker-compose.production.yml build rag_engine
docker compose -f docker-compose.production.yml up -d
```

إذا كنت تشغل الخدمة بدون Docker على Ubuntu، ثبّت:

```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng poppler-utils
```

ثم ثبّت متطلبات Python في `services/rag_engine/requirements.txt`.
