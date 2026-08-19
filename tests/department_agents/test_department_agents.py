from backend_core.department_agents.service import normalize_arabic, resolve_department_agent, score_agent, list_agents


def test_arabic_normalization_unifies_common_forms():
    assert normalize_arabic('إجازةً') == 'اجازه'
    assert normalize_arabic('أهلاً وسهلاً') == 'اهلا وسهلا'


def test_route_hr_agent_for_leave_question():
    claims = {'sub': 'u1', 'roles': ['ai_user'], 'department': 'human_resources'}
    agent = resolve_department_agent('كم رصيد الإجازة السنوية للموظف؟', claims, db=None)
    assert agent.key == 'hr'
    assert agent.score > 0


def test_restricted_finance_agent_falls_back_for_ai_user():
    claims = {'sub': 'u1', 'roles': ['ai_user'], 'department': 'it'}
    agent = resolve_department_agent('اعرض تقرير المصروفات والميزانية', claims, db=None)
    assert agent.key == 'general'
    assert agent.reason.startswith('blocked_by_role')


def test_executive_agent_for_kpi_question():
    claims = {'sub': 'manager1', 'roles': ['department_manager'], 'department': 'executive'}
    agent = resolve_department_agent('أريد ملخص تنفيذي عن مؤشرات الأداء KPI', claims, db=None)
    assert agent.key == 'executive'
