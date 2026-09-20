# ابدأ هنا — HSAAI_v1

**نسخة المشروع حتى آخر تعديل:2026-09-19. الحالة: B – PRODUCTION CANDIDATE – BLOCKERS REMAIN.**

تحتوي الحزمة جميع ملفات المصدر السابقة مع الإصلاحات الجديدة والتقارير. اسمv1 هو اسم التنزيل المطلوب؛ إصدار الشيفرة4.0.0-rc.2، ولم يُرجع المشروع لنسخة أقدم.

| Check | Result |
|---|---|
| Backend (2026-09-19) | 690 PASS / 0 FAIL / 0 SKIPPED |
| Frontend (2026-09-14; unchanged source) | 38 PASS / 0 FAIL / 0 SKIPPED; production build PASS |
| E2E (2026-09-14; not rerun) | 2 PASS / 0 FAIL / 11 SKIPPED; public UI only |
| Python coverage (2026-09-19) | 41.92% → 54.78% → 56.56%; target80% FAIL |
| Focused security regression | 209 PASS; subset of backend total |
| PDF clauses | 5/1482 PASS;864 PARTIAL;510 FAIL;103 BLOCKED;58 context rows |
| Docker build/runtime | BLOCKED / BLOCKED |
| Containers healthy | 0/33 observed;22 optional;2 jobs |
| Database / AI full chain | PARTIAL / NOT VALIDATED in production |
| Frontend ↔ Backend / Monitoring | NOT TESTED as a complete runtime |
| Security | NOT APPROVED; observed C0/H3/M53/L57 |
| Kubernetes | Static previous PASS; real deployment NOT AVAILABLE |
| Production health check | NOT TESTED |
| Release | B – PRODUCTION CANDIDATE – BLOCKERS REMAIN |

أهم التغييرات: عزل بيانات CoE/FinOps والتكاملات حسب المؤسسة ومساحة العمل؛ إصلاح حفظ حقولJSON وحساب التكلفة؛ محدد طلبات يرفض المرور عند تعطل Redis في الإنتاج مع حدود ذاكرة؛ حجب التفاصيل الحساسة في أخطاء الموصلات. أُضيف92اختبارًا حقيقيًا.

قبل أي ترحيل احتفظ بنسخة قاعدة البيانات ومفتاح التشفير والملح. الترحيل0009 إضافي؛ تبقى السجلات القديمة ضمنdefault/default إلى أن تُراجع ملكيتها وتُسند صراحة، ولا يجوز نسبتها تلقائيًا إلى مؤسسة. يجب اختبار الترحيل وسياساتRLS على PostgreSQL قبل النشر.

اقرأ FINAL_PRODUCTION_READINESS_REPORT.md وRELEASE_MANIFEST.md ثم docs/reports/FINAL_TEST_SUMMARY.md وSECURITY_VALIDATION_REPORT.md وCONTINUATION_20260919.md. دليل التشغيل: docs/operations/PRODUCTION_HANDOVER_RUNBOOK_AR.md.

المتبقي: التغطية80%، ثغراتPII/ACL فيRAG، اعتماد بيانات الترحيل، متطلباتPDF الناقصة، التشغيل الفعليDocker/Kubernetes والهوية والنماذج والمراقبة والتعافي. لا توجد موافقة إنتاج. نتائج الواجهة والمتصفح بتاريخ2026-09-14 محفوظة ولم تُعد في هذه الجولة.

بعد فك الضغط في مجلد جديد نفّذ `sha256sum -c SHA256SUMS.txt`. لا تستبدل ملفات أسرار أو قواعد بيانات موجودة. التقارير السابقة محفوظة في history؛ التقارير الجذرية الحالية لها الأولوية.
