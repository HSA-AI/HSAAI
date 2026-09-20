#!/usr/bin/env python3
"""Build a conservative clause matrix, retaining every source page character."""
from pathlib import Path
import argparse,collections,hashlib,json,re,unicodedata


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--extracted-text',required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[2];out=root/'docs/reports';e=out/'evidence'
    parts=re.split(r'=== PAGE (\d+) ===\n',Path(args.extracted_text).read_text())
    pages={int(parts[i]):unicodedata.normalize('NFKC',parts[i+1]).strip() for i in range(1,len(parts),2)}
    assert set(pages)==set(range(1,101)), 'All 100 PDF pages are required'
    starts=[(1,1),(8,2),(15,3),(25,4),(35,5),(45,6),(55,7),(64,8),(73,9),(83,10),(90,11)]
    components=[
        (r'docker|container|image|compose','Docker','docker-compose.production.yml; services/*/Dockerfile','DOCKER_VALIDATION_REPORT.md'),
        (r'kubernetes|helm|namespace|ingress|configmap|statefulset|deployment|pvc|autoscal|replicas|readiness|liveness','Kubernetes','infrastructure/kubernetes/; infrastructure/helm/','KUBERNETES_VALIDATION_REPORT.md'),
        (r'prometheus|grafana|loki|telemetry|trac|metrics|alert|monitor|observab|logging|logs','Observability','infrastructure/monitoring/; services/backend_core/phase5/observability.py','OBSERVABILITY_VALIDATION.md'),
        (r'postgres|redis|qdrant|weaviate|neo4j|database|migration|schema|index|backup|restore|recovery|قواعد البیانات','Databases','alembic/; services/rag_engine/','DATABASE_VALIDATION_REPORT.md'),
        (r'auth|rbac|abac|sso|mfa|oauth|jwt|keycloak|permission|tenant|security|encryption|secret|vulnerab|firewall|zero.?trust|audit|governance|compliance|soc ?2|iso|gdpr|الحوكم|أمان|أمن','Security / identity','packages/common/security/; services/auth_service/; services/governance/','SECURITY_VALIDATION_REPORT.md'),
        (r'frontend|ui/?ux|design|theme|css|tailwind|color|button|card|spacing|typography|font|responsive|sidebar|navigation|screen|keyboard|contrast|overflow|animation|bundle|rendering|component|wcag|dashboard|الألوان|الھویة|التصمیم|الشعار','Frontend','apps/web/','FRONTEND_VALIDATION_REPORT.md'),
        (r'pytest|unit test|integration test|api test|e2e|test coverage|quality assurance|testing|qa|load test|performance test|benchmark','QA','tests/; apps/web/','FINAL_TEST_SUMMARY.md'),
        (r'ci/cd|pipeline|github|gitlab|argocd|registry|supply chain|signing','CI/CD','.github/workflows/; infrastructure/','PRODUCTION_ACCEPTANCE_MATRIX.md'),
        (r'billing|stripe|subscription|pricing|invoice|finops|saas|organization|user management','SaaS / billing','services/backend_core/enterprise_os/','PDF_REQUIREMENTS_MATRIX.md'),
        (r'llm|model|embedding|rag|retriev|search|prompt|ocr|knowledge|memory|context|vector|inference|reasoning|المعرفة','AI / RAG','services/rag_engine/; services/llm_gateway/; services/model_training/','AI_VALIDATION_REPORT.md'),
        (r'agent|workflow|approval|tool|orchestrat|negotiation|الوكلاء|وكلاء|قرار','Agents / workflow','services/workflow_engine/; services/multi_agents/; services/backend_core/approvals/','AI_VALIDATION_REPORT.md'),
        (r'cloud|aws|azure|google cloud|vpc|subnet|region|global|edge|sovereign|federat|network|99\.99|zero.data.loss','Cloud / federation','infrastructure/; services/federation_hub/','KUBERNETES_VALIDATION_REPORT.md'),
        (r'doc|readme|guide|manual|report|roadmap|blueprint|تقریر|توثیق|وثائق|خطة','Documentation','docs/; START_HERE_AR.md','PRODUCTION_ACCEPTANCE_MATRIX.md'),
    ]
    roles=re.compile(r'^-?\s*(?:principal|senior|enterprise|devops|kubernetes|cybersecurity|qa|cloud|site reliability|security operations|infrastructure automation|ai|full.stack|product|ux|ui|frontend|backend|research|machine learning|data|distributed systems|global|chief|software|solution|saas).*?(?:engineer|architect|lead|designer|manager|researcher|scientist|officer|specialist|expert|director)(?:\s*\(?sre\(?)?\s*$',re.I)
    rows=[];context='Project acceptance'
    for page,text in pages.items():
        axis=max(a for p,a in starts if page>=p)
        positions=sorted({0,*[m.start() for m in re.finditer(r'(?<!\S)(?=-\s|#{1,3}\s|✔|✅|\d+\.\s)',text)]});fragments=[]
        for index,(start,end) in enumerate(zip(positions,positions[1:]+[len(text)]),1):
            raw=text[start:end];fragments.append(raw);quote=re.sub(r'\s+',' ',raw).strip();clean=quote.strip('- #').strip();norm=clean.lower()
            if quote.startswith('#'):context=clean
            comp='Enterprise platform / axis '+str(axis);source='evidence/architecture-inventory.json';report='PRODUCTION_ACCEPTANCE_MATRIX.md'
            for pattern,c,src,rep in components:
                if re.search(pattern,norm,re.I):comp,source,report=c,src,rep;break
            kind='requirement';current=final='PARTIAL';proof=source+'; '+report
            missing='Complete and validate this behavior in the integrated stack. Source/configuration presence alone is not acceptance evidence.'
            if roles.fullmatch(clean) or clean in {'','---','أنشئ','یشمل','مثال','المھام','یدعم'}:
                kind='context';current=final='NOT APPLICABLE';missing='Role/list context retained; evaluate the associated feature clauses.';proof='PDF context only.'
            elif re.search(r'docker compose (build|up)|runtime stability|zero downtime|high availability|auto scaling|disaster recovery|global deployment|gpu cluster|cuda|load balancing|live monitoring|real.time monitoring|10,?000|1,?000|99\.99|zero data loss',norm):
                current=final='BLOCKED';proof+='; evidence/runtime-attempts.json';missing='Requires actual engine/cluster/GPU/load/failure-recovery execution; no authorized working target is available here.'
            elif axis in {7,8,9,10}:
                current=final='FAIL';missing='Frontier/global AI program is not completed or accepted. Finish engineering, data/evaluation, infrastructure and human oversight; no impossibility waiver is asserted.'
            elif axis in {5,6} and re.search(r'billing|subscription|stripe|payment|autonomous company|ai company|ai ceo|digital employee|marketplace.*global|saa?s|iso ?27001|soc ?2|gdpr|registration|customer onboarding',norm):
                current=final='FAIL';missing='Complete and validate the specified SaaS/autonomy/business/compliance capability. Existing prototypes are insufficient.'
            elif re.search(r'unit tests?',norm) and len(clean)<35:
                current=final='PASS';proof='evidence/backend-tests-final.xml; evidence/frontend-tests.json';missing='None for this unit-test facet; coverage/integration gates remain separate blockers.'
            elif page>=90 and norm in {'css variables','tailwind tokens','theme provider','production build','lint','build','test','npm run build','npm run lint','npm test'}:
                current=final='PASS';proof='evidence/final-validation.json; apps/web/';missing='None for this frontend facet; no whole-platform approval implied.'
            elif comp in {'Kubernetes','Cloud / federation','Docker'}:
                current=final='BLOCKED';proof+='; evidence/runtime-attempts.json';missing='Static checks do not prove actual image build, server dry-run or runtime deployment.'
            elif re.search(r'frontend.*backend|end.to.end|integration tests?|sso|mfa|keycloak',norm):
                current=final='BLOCKED';missing='Requires the real identity provider, service stack, test users, model and databases.'
            elif page==98 and 'overflow' in norm:
                proof='evidence/browser-visual-validation.json';missing='Login tested at 390/768/1440; authenticated pages still need validation.'
            rows.append(dict(id=f'PDF-P{page:03d}-R{index:02d}',page=page,axis=axis,kind=kind,source_start=start,source_end=end,raw=raw,requirement=quote,context=context,component=comp,current_status=current,evidence=proof,missing_work=missing,final_status=final))
        assert ''.join(fragments)==text, f'Lost PDF text at page {page}'
    summary=dict(pages=100,rows=len(rows),requirements=sum(x['kind']=='requirement' for x in rows),statuses=dict(collections.Counter(x['final_status'] for x in rows)),source_reconstruction='PASS for all 100 pages',pdf_sha256=hashlib.sha256((root/'docs/release/reference/requirements.pdf').read_bytes()).hexdigest())
    (e/'pdf-source-pages.json').write_text(json.dumps(pages,ensure_ascii=False,indent=2));(e/'pdf-requirements.json').write_text(json.dumps(dict(summary=summary,rows=rows),ensure_ascii=False,indent=2))
    text=f'''# PDF_REQUIREMENTS_MATRIX — جميع صفحات المرجع\n\nتم الاحتفاظ بالنص الكامل للصفحات المئة وربط كل مقطع بإزاحاته الأصلية في `evidence/pdf-requirements.json`. تحقق إعادة تركيب كل صفحة: PASS. لا توجد نقطة محذوفة؛ البنود المكررة باقية، وقد يحتفظ المقطع بالشرح والسياق المتصل به.\n\nعدد المقاطع {len(rows)}، منها {summary['requirements']} مقطع متطلبات والبقية سياق أدوار أو مقدمة قائمة. الأعداد تخص المقاطع، وليست ادعاءً بأنها ميزات مستقلة.\n\nPASS: إثبات للبند المحدد فقط. PARTIAL: تنفيذ/إعداد جزئي أو تحقق محدود. FAIL: تنفيذ غير مكتمل. BLOCKED: يحتاج بيئة أو تبعية غير متاحة. NOT TESTED: لم يختبر. NOT APPLICABLE: سياق لا يمثل ميزة مستقلة. المتطلبات المستقبلية والبحثية ليست معفاة، ولا تدّعي هذه المصفوفة استحالتها تقنيًا. وجود ملف ليس إثباتًا لعمل الميزة.\n\nالمرجع يحتوي أحد عشر برنامجًا، بما فيها SaaS والفوترة والذكاء العالمي والمراحل البحثية وتصميم الواجهة. لا تجتاز الحزمة القبول الإلزامي للـPDF حاليًا.\n\n| ID | PDF Requirement | Component | Current Status | Evidence | Missing Work | Final Status |\n|---|---|---|---|---|---|---|\n'''
    def cell(value):return str(value).replace('|','\\|').replace('\n',' ')
    text+='\n'.join('| '+' | '.join(cell(x[k]) for k in ['id','requirement','component','current_status','evidence','missing_work','final_status'])+' |' for x in rows)+'\n'
    (out/'PDF_REQUIREMENTS_MATRIX.md').write_text(text);print(json.dumps(summary))

if __name__=='__main__':main()
