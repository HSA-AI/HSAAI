HSAAI - Full File Structure
Source ZIP: HSAAI.zip

└── HSAAI/
    ├── .github/
    │   └── workflows/
    │       ├── ci.yml
    │       ├── docker-build.yml
    │       └── security-scan.yml
    ├── .pytest_cache/
    │   ├── v/
    │   │   └── cache/
    │   │       ├── lastfailed
    │   │       └── nodeids
    │   ├── .gitignore
    │   ├── CACHEDIR.TAG
    │   └── README.md
    ├── ai_orchestrator/
    │   ├── __pycache__/
    │   │   ├── __init__.cpython-313.pyc
    │   │   └── main.cpython-313.pyc
    │   ├── __init__.py
    │   └── main.py
    ├── api_gateway/
    │   ├── __pycache__/
    │   │   ├── __init__.cpython-313.pyc
    │   │   └── main.cpython-313.pyc
    │   ├── __init__.py
    │   └── main.py
    ├── apps/
    │   └── web/
    │       ├── app/
    │       │   ├── admin/
    │       │   │   └── page.tsx
    │       │   ├── agents/
    │       │   │   └── page.tsx
    │       │   ├── chat/
    │       │   │   └── page.tsx
    │       │   ├── dashboard/
    │       │   │   └── page.tsx
    │       │   ├── governance/
    │       │   │   └── page.tsx
    │       │   ├── integrations/
    │       │   │   └── page.tsx
    │       │   ├── knowledge/
    │       │   │   └── page.tsx
    │       │   ├── settings/
    │       │   │   └── page.tsx
    │       │   ├── workflows/
    │       │   │   └── page.tsx
    │       │   ├── workspace/
    │       │   │   └── page.tsx
    │       │   ├── layout.tsx
    │       │   └── page.tsx
    │       ├── components/
    │       │   ├── assistant/
    │       │   │   ├── floating-assistant.tsx
    │       │   │   └── README.md
    │       │   ├── branding/
    │       │   │   ├── brand-hero.tsx
    │       │   │   ├── brand-mark.tsx
    │       │   │   ├── official-badge.tsx
    │       │   │   └── README.md
    │       │   ├── chat/
    │       │   │   ├── chat-window.tsx
    │       │   │   └── README.md
    │       │   ├── dashboard/
    │       │   │   ├── ai-usage-chart.tsx
    │       │   │   ├── analytics-cards.tsx
    │       │   │   └── README.md
    │       │   ├── enterprise/
    │       │   │   ├── command-center.tsx
    │       │   │   └── security-posture.tsx
    │       │   ├── integrations/
    │       │   │   └── README.md
    │       │   ├── knowledge/
    │       │   │   └── README.md
    │       │   ├── layout/
    │       │   │   ├── app-shell.tsx
    │       │   │   ├── README.md
    │       │   │   ├── sidebar.tsx
    │       │   │   └── topbar.tsx
    │       │   ├── pwa/
    │       │   │   └── register-service-worker.tsx
    │       │   └── ui/
    │       │       ├── button.tsx
    │       │       ├── card.tsx
    │       │       ├── input.tsx
    │       │       └── textarea.tsx
    │       ├── lib/
    │       │   ├── brand.ts
    │       │   └── utils.ts
    │       ├── providers/
    │       │   └── providers.tsx
    │       ├── public/
    │       │   ├── brand/
    │       │   │   ├── hsa-logo.jpg
    │       │   │   ├── hsaai-assistant-brand.json
    │       │   │   ├── hsaai-assistant-circle-128.png
    │       │   │   ├── hsaai-assistant-circle-256.png
    │       │   │   ├── hsaai-assistant-circle-512.png
    │       │   │   ├── hsaai-assistant-circle-64.png
    │       │   │   ├── hsaai-assistant-circle.png
    │       │   │   ├── hsaai-assistant-circle.svg
    │       │   │   └── hsaai-assistant-circle.webp
    │       │   ├── hsaai-assistant-circle.png
    │       │   ├── hsaai_official_logo.png
    │       │   ├── manifest.webmanifest
    │       │   └── sw.js
    │       ├── services/
    │       │   ├── api.ts
    │       │   ├── chat.service.ts
    │       │   └── rag.service.ts
    │       ├── store/
    │       │   └── workspace.store.ts
    │       ├── styles/
    │       │   └── globals.css
    │       ├── .npmrc
    │       ├── Dockerfile
    │       ├── next-env.d.ts
    │       ├── next.config.mjs
    │       ├── package-lock.json
    │       ├── package.json
    │       ├── postcss.config.mjs
    │       ├── tailwind.config.ts
    │       ├── tsconfig.json
    │       └── tsconfig.tsbuildinfo
    ├── backend/
    │   ├── __pycache__/
    │   │   └── __init__.cpython-313.pyc
    │   ├── security/
    │   │   ├── __pycache__/
    │   │   │   ├── __init__.cpython-313.pyc
    │   │   │   └── internal_only.cpython-313.pyc
    │   │   ├── __init__.py
    │   │   └── internal_only.py
    │   └── __init__.py
    ├── deployment/
    │   ├── compose/
    │   │   └── docker-compose.internal.yml
    │   └── kubernetes/
    │       └── network-policies/
    │           ├── allow-internal-services.yaml
    │           └── default-deny-egress.yaml
    ├── docs/
    │   ├── api/
    │   │   └── OPENAPI_CONTRACTS.md
    │   ├── architecture/
    │   │   ├── ADMIN_CONSOLE_SPEC.md
    │   │   ├── ENTERPRISE_REPOSITORY_MAP_AR.md
    │   │   ├── FINAL_10_OF_10_IMPROVEMENTS.md
    │   │   ├── FINAL_10_OF_10_README.md
    │   │   ├── PROJECT_STRUCTURE_AR.md
    │   │   └── RAG_PRODUCTION_DESIGN.md
    │   ├── deliverables/
    │   │   ├── expanded/
    │   │   │   ├── HSAAI_Brand_Identity_Updated_Documents.zip
    │   │   │   ├── HSAAI_Expanded_Enterprise_Integration_Guide_30_Pages_Package.zip
    │   │   │   ├── HSAAI_Expanded_Operations_Runbook_30_Pages_Package.zip
    │   │   │   └── HSAAI_Expanded_Overview_40_Pages_Package.zip
    │   │   ├── HSAAI_Book3_Enterprise_Integration_Final.zip
    │   │   ├── HSAAI_Brand_Identity_Updated_Documents.zip
    │   │   ├── HSAAI_Complete_Technical_Books_Final.zip
    │   │   └── HSAAI_Documents_Rewritten_Professional_Word.zip
    │   ├── governance/
    │   │   ├── 00_EXECUTIVE_OVERVIEW_AR.md
    │   │   ├── 01_BUSINESS_CASE_AR.md
    │   │   ├── 02_DIGITAL_TRANSFORMATION_CHARTER_AR.md
    │   │   ├── 03_PILOT_PLAN_AR.md
    │   │   ├── 04_DATA_GOVERNANCE_POLICY_AR.md
    │   │   ├── 05_AI_USAGE_POLICY_AR.md
    │   │   ├── 06_AI_GOVERNANCE_COMMITTEE_AR.md
    │   │   ├── 07_KPI_DASHBOARD_SPEC_AR.md
    │   │   ├── 08_CHANGE_MANAGEMENT_PLAN_AR.md
    │   │   ├── 09_ENTERPRISE_READINESS_CHECKLIST_AR.md
    │   │   └── 10_DEPLOYMENT_DECISION_MATRIX_AR.md
    │   ├── integration/
    │   │   ├── FILE_SERVER_ACL_RAG_GUIDE.md
    │   │   ├── SAP_INTEGRATION_GUIDE.md
    │   │   └── WINDOWS_AD_INTEGRATION_GUIDE.md
    │   ├── operations/
    │   │   ├── BACKUP_RESTORE_DR.md
    │   │   ├── INCIDENT_RESPONSE_RUNBOOK.md
    │   │   ├── LOCAL_LLM_OPERATIONS.md
    │   │   ├── NO_ERROR_RELEASE_CHECKLIST_AR.md
    │   │   ├── PRODUCTION_ACCEPTANCE_CHECKLIST.md
    │   │   ├── PRODUCTION_RUNBOOK.md
    │   │   └── ROLLBACK_PLAN.md
    │   ├── reports/
    │   │   └── .env.internal.example
    │   ├── security/
    │   │   ├── ACCESS_CONTROL_MATRIX.md
    │   │   ├── DATA_CLASSIFICATION_MATRIX.md
    │   │   ├── HSAAI_INTERNAL_ONLY_DEPLOYMENT_AR.md
    │   │   └── SECURITY_THREAT_MODEL.md
    │   └── ui/
    │       ├── legacy-pages/
    │       │   ├── admin_legacy/
    │       │   │   └── page.tsx
    │       │   └── chat_legacy/
    │       │       └── page.tsx
    │       ├── HSA_OFFICIAL_BRANDING.md
    │       ├── HSAAI_ASSISTANT_BRAND_GUIDELINES_AR.md
    │       └── HSAAI_FLOATING_ASSISTANT_AR.md
    ├── infrastructure/
    │   ├── docker/
    │   │   ├── docker-compose.dev.yml
    │   │   ├── docker-compose.hsa-internal.yml
    │   │   └── docker-compose.production.yml
    │   ├── helm/
    │   │   ├── templates/
    │   │   │   ├── NOTES.txt
    │   │   │   └── secret.yaml
    │   │   ├── Chart.yaml
    │   │   ├── values-production.yaml
    │   │   └── values.yaml
    │   ├── keycloak/
    │   │   └── hsaai-realm.json
    │   ├── kubernetes/
    │   │   ├── base/
    │   │   │   ├── network-policies/
    │   │   │   │   ├── allow-internal-services.yaml
    │   │   │   │   └── default-deny-egress.yaml
    │   │   │   ├── ai-orchestrator.yaml
    │   │   │   ├── analytics.yaml
    │   │   │   ├── api-gateway.yaml
    │   │   │   ├── auth-service.yaml
    │   │   │   ├── backend.yaml
    │   │   │   ├── document-ai.yaml
    │   │   │   ├── frontend.yaml
    │   │   │   ├── hpa.yaml
    │   │   │   ├── ingress.yaml
    │   │   │   ├── llm-gateway.yaml
    │   │   │   ├── multi-agents.yaml
    │   │   │   ├── persistent-volumes.yaml
    │   │   │   ├── production-secrets.example.yaml
    │   │   │   ├── rag-engine.yaml
    │   │   │   ├── voice-ai.yaml
    │   │   │   └── workflow-engine.yaml
    │   │   ├── network-policies/
    │   │   │   ├── allow-internal-services.yaml
    │   │   │   ├── default-deny-egress.yaml
    │   │   │   └── hsaai-internal-only-network-policy.yaml
    │   │   └── overlays/
    │   │       ├── production/
    │   │       │   └── kustomization.yaml
    │   │       └── staging/
    │   │           └── kustomization.yaml
    │   ├── monitoring/
    │   │   ├── grafana-dashboard.json
    │   │   ├── otel-collector.yaml
    │   │   └── prometheus.yml
    │   └── secrets/
    │       ├── README.md
    │       └── secrets.example.env
    ├── llm_gateway/
    │   ├── __pycache__/
    │   │   ├── __init__.cpython-313.pyc
    │   │   └── main.cpython-313.pyc
    │   ├── __init__.py
    │   └── main.py
    ├── packages/
    │   ├── common/
    │   │   ├── config/
    │   │   │   ├── __init__.py
    │   │   │   └── backend_config.py
    │   │   ├── logging/
    │   │   │   ├── __init__.py
    │   │   │   └── README.md
    │   │   ├── schemas/
    │   │   │   ├── __init__.py
    │   │   │   └── backend_schemas.py
    │   │   ├── security/
    │   │   │   ├── __init__.py
    │   │   │   ├── audit.py
    │   │   │   ├── encryption.py
    │   │   │   ├── internal_only.py
    │   │   │   ├── rbac.py
    │   │   │   └── tenant_guard.py
    │   │   ├── utils/
    │   │   │   ├── __init__.py
    │   │   │   └── README.md
    │   │   └── __init__.py
    │   ├── governance/
    │   │   ├── audit/
    │   │   │   ├── audit.py
    │   │   │   └── README.md
    │   │   ├── policies/
    │   │   │   └── README.md
    │   │   ├── rbac/
    │   │   │   ├── rbac.py
    │   │   │   └── README.md
    │   │   ├── tenant_guard/
    │   │   │   ├── README.md
    │   │   │   └── tenant_guard.py
    │   │   ├── __init__.py
    │   │   ├── models.py
    │   │   └── router.py
    │   ├── integrations/
    │   │   ├── analytics/
    │   │   │   ├── __init__.py
    │   │   │   ├── bi_gateway.py
    │   │   │   └── README.md
    │   │   ├── connectors/
    │   │   │   ├── __init__.py
    │   │   │   └── hsa_integrations.py
    │   │   ├── documents/
    │   │   │   ├── __init__.py
    │   │   │   ├── README.md
    │   │   │   └── sharepoint_connector.py
    │   │   ├── hr/
    │   │   │   ├── __init__.py
    │   │   │   ├── hr_connector.py
    │   │   │   └── README.md
    │   │   ├── identity/
    │   │   │   ├── __init__.py
    │   │   │   ├── keycloak_ad_federation.py
    │   │   │   └── README.md
    │   │   ├── itsm/
    │   │   │   ├── __init__.py
    │   │   │   ├── README.md
    │   │   │   └── service_desk_connector.py
    │   │   ├── sap/
    │   │   │   ├── __init__.py
    │   │   │   ├── bydesign_client.py
    │   │   │   ├── README.md
    │   │   │   └── s4hana_client.py
    │   │   ├── security/
    │   │   │   ├── __init__.py
    │   │   │   ├── policies.py
    │   │   │   └── README.md
    │   │   ├── windows_server/
    │   │   │   ├── __init__.py
    │   │   │   ├── acl_mapper.py
    │   │   │   ├── active_directory_connector.py
    │   │   │   ├── event_log_reader.py
    │   │   │   ├── file_server_connector.py
    │   │   │   ├── README.md
    │   │   │   └── winrm_client.py
    │   │   ├── __init__.py
    │   │   ├── catalog.py
    │   │   └── router.py
    │   └── __init__.py
    ├── scripts/
    │   ├── backup_postgres.sh
    │   ├── backup_qdrant.sh
    │   ├── production_release_gate.sh
    │   ├── smoke_test.sh
    │   ├── validate_project_structure.py
    │   ├── validate_yaml_files.py
    │   └── verify_internal_only.py
    ├── services/
    │   ├── ai_orchestrator/
    │   │   ├── __init__.py
    │   │   ├── Dockerfile
    │   │   ├── hsaai_profile.py
    │   │   ├── main.py
    │   │   └── requirements.txt
    │   ├── analytics/
    │   │   ├── __init__.py
    │   │   ├── Dockerfile
    │   │   ├── main.py
    │   │   └── requirements.txt
    │   ├── api_gateway/
    │   │   ├── __pycache__/
    │   │   │   └── main.cpython-313.pyc
    │   │   ├── __init__.py
    │   │   ├── Dockerfile
    │   │   ├── main.py
    │   │   └── requirements.txt
    │   ├── auth_service/
    │   │   ├── __init__.py
    │   │   ├── Dockerfile
    │   │   ├── main.py
    │   │   └── requirements.txt
    │   ├── backend_core/
    │   │   ├── admin/
    │   │   │   ├── __init__.py
    │   │   │   └── dashboard.py
    │   │   ├── agents/
    │   │   │   └── router.py
    │   │   ├── auth/
    │   │   │   └── middleware.py
    │   │   ├── branding/
    │   │   │   ├── __init__.py
    │   │   │   ├── config.py
    │   │   │   └── router.py
    │   │   ├── chat/
    │   │   │   ├── __init__.py
    │   │   │   └── router.py
    │   │   ├── connectors/
    │   │   │   ├── __init__.py
    │   │   │   └── hsa_integrations.py
    │   │   ├── core/
    │   │   │   ├── __init__.py
    │   │   │   └── engine.py
    │   │   ├── db/
    │   │   │   ├── __init__.py
    │   │   │   ├── database.py
    │   │   │   └── models.py
    │   │   ├── enterprise/
    │   │   │   ├── __init__.py
    │   │   │   └── hsaai_profile.py
    │   │   ├── governance/
    │   │   │   ├── __init__.py
    │   │   │   ├── models.py
    │   │   │   └── router.py
    │   │   ├── integrations/
    │   │   │   ├── analytics/
    │   │   │   │   ├── __init__.py
    │   │   │   │   └── bi_gateway.py
    │   │   │   ├── documents/
    │   │   │   │   ├── __init__.py
    │   │   │   │   └── sharepoint_connector.py
    │   │   │   ├── hr/
    │   │   │   │   ├── __init__.py
    │   │   │   │   └── hr_connector.py
    │   │   │   ├── identity/
    │   │   │   │   ├── __init__.py
    │   │   │   │   └── keycloak_ad_federation.py
    │   │   │   ├── itsm/
    │   │   │   │   ├── __init__.py
    │   │   │   │   └── service_desk_connector.py
    │   │   │   ├── sap/
    │   │   │   │   ├── __init__.py
    │   │   │   │   ├── bydesign_client.py
    │   │   │   │   └── s4hana_client.py
    │   │   │   ├── security/
    │   │   │   │   ├── __init__.py
    │   │   │   │   └── policies.py
    │   │   │   ├── windows_server/
    │   │   │   │   ├── __init__.py
    │   │   │   │   ├── acl_mapper.py
    │   │   │   │   ├── active_directory_connector.py
    │   │   │   │   ├── event_log_reader.py
    │   │   │   │   ├── file_server_connector.py
    │   │   │   │   └── winrm_client.py
    │   │   │   ├── __init__.py
    │   │   │   ├── catalog.py
    │   │   │   └── router.py
    │   │   ├── llm/
    │   │   │   └── router.py
    │   │   ├── memory/
    │   │   │   ├── __init__.py
    │   │   │   └── store.py
    │   │   ├── rag/
    │   │   │   ├── __pycache__/
    │   │   │   │   └── proxy_router.cpython-313.pyc
    │   │   │   ├── __init__.py
    │   │   │   ├── citation_policy.py
    │   │   │   ├── ingest.py
    │   │   │   ├── proxy_router.py
    │   │   │   ├── retriever.py
    │   │   │   └── search.py
    │   │   ├── roles/
    │   │   │   └── permissions.py
    │   │   ├── security/
    │   │   │   ├── __init__.py
    │   │   │   ├── audit.py
    │   │   │   ├── encryption.py
    │   │   │   ├── internal_only.py
    │   │   │   ├── rbac.py
    │   │   │   └── tenant_guard.py
    │   │   ├── websocket/
    │   │   │   ├── __init__.py
    │   │   │   └── ws.py
    │   │   ├── __init__.py
    │   │   ├── config.py
    │   │   ├── Dockerfile
    │   │   ├── main.py
    │   │   ├── requirements.txt
    │   │   └── schemas.py
    │   ├── document_ai/
    │   │   ├── __init__.py
    │   │   ├── Dockerfile
    │   │   ├── main.py
    │   │   └── requirements.txt
    │   ├── llm_gateway/
    │   │   ├── Dockerfile
    │   │   ├── main.py
    │   │   └── requirements.txt
    │   ├── multi_agents/
    │   │   ├── __init__.py
    │   │   ├── agents.py
    │   │   ├── Dockerfile
    │   │   ├── main.py
    │   │   └── requirements.txt
    │   ├── rag_engine/
    │   │   ├── __pycache__/
    │   │   │   ├── __init__.cpython-313.pyc
    │   │   │   ├── chunking.cpython-313.pyc
    │   │   │   ├── embedding.cpython-313.pyc
    │   │   │   ├── loaders.cpython-313.pyc
    │   │   │   ├── main.cpython-313.pyc
    │   │   │   └── reranker.cpython-313.pyc
    │   │   ├── __init__.py
    │   │   ├── chunking.py
    │   │   ├── Dockerfile
    │   │   ├── embedding.py
    │   │   ├── loaders.py
    │   │   ├── main.py
    │   │   ├── requirements.txt
    │   │   └── reranker.py
    │   ├── voice_ai/
    │   │   ├── __init__.py
    │   │   ├── Dockerfile
    │   │   ├── main.py
    │   │   └── requirements.txt
    │   └── workflow_engine/
    │       ├── __init__.py
    │       ├── Dockerfile
    │       ├── main.py
    │       └── requirements.txt
    ├── storage/
    │   ├── audit_logs/
    │   ├── local_models/
    │   ├── local_uploads/
    │   ├── audit_logs.gitkeep
    │   ├── local_models.gitkeep
    │   ├── local_uploads.gitkeep
    │   └── README.md
    ├── tests/
    │   ├── e2e/
    │   │   └── README.md
    │   ├── integration/
    │   │   ├── __pycache__/
    │   │   │   └── test_service_contracts.cpython-313-pytest-9.0.2.pyc
    │   │   └── test_service_contracts.py
    │   ├── load/
    │   │   └── locustfile.py
    │   ├── security/
    │   │   ├── __pycache__/
    │   │   │   └── test_internal_only_config.cpython-313-pytest-9.0.2.pyc
    │   │   └── test_internal_only_config.py
    │   └── unit/
    │       ├── __pycache__/
    │       │   ├── test_advanced_rag_features.cpython-313-pytest-9.0.2.pyc
    │       │   └── test_project_structure.cpython-313-pytest-9.0.2.pyc
    │       ├── test_advanced_rag_features.py
    │       └── test_project_structure.py
    ├── .env.example
    ├── .env.hsa-internal.example
    ├── .env.production.example
    ├── .gitignore
    ├── ADVANCED_RAG_OCR_CITATIONS_REPORT_AR.md
    ├── CHANGELOG.md
    ├── check_local_requirements.sh
    ├── docker-compose.dev.yml
    ├── docker-compose.hsa-internal.yml
    ├── docker-compose.production.yml
    ├── FINAL_NO_ERRORS_RELEASE_REPORT_AR.md
    ├── FIX_ALL_ISSUES_REPORT_AR.md
    ├── HSAAI_ASSISTANT_NEW_CHAT_FIX_AR.md
    ├── LICENSE
    ├── LOCAL_EXECUTION_TEST_REPORT_AR.md
    ├── Makefile
    ├── PRODUCTION_GATE_FINAL_FIX_REPORT_AR.md
    ├── PRODUCTION_GATE_FIX_REPORT_AR.md
    ├── README.md
    ├── README_AR.md
    ├── RELEASE_NOTES.md
    ├── REORGANIZATION_MANIFEST.json
    ├── REORGANIZATION_REPORT_AR.md
    ├── RESPONSIVE_OPTIMIZATION_REPORT_AR.md
    ├── run_docker_production.sh
    ├── run_docker_production_windows.bat
    ├── RUN_PROJECT_LOCAL_AR.md
    ├── run_web_dev.sh
    ├── run_web_dev_windows.bat
    ├── run_web_prod.sh
    └── VERSION