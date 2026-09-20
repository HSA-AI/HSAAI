"""Exercise actual file persistence and state transitions without claiming clustered durability."""
import pytest
from backend_core import mdm as d
from backend_core import agent_marketplace as a

@pytest.mark.parametrize('strategy,values,expected',[
 ('first_non_empty',['','B'],'B'),('last_updated',['A','B'],'B'),('prefer_source:sap',['A','B'],'B'),('prefer_source:missing',['A','B'],'A'),
 ('longest_value',['Al','Alice'],'Alice'),('highest_clearance',['internal','restricted'],'restricted'),('highest_risk',['low','critical'],'critical'),
 ('max_value',[2,7],7),('min_value',[2,7],2),('sum_values',[2,7],9),('unknown',['A','B'],'A'),
])
def test_survivorship_rules(strategy,values,expected):
    inputs=[{'value':v,'source_system':src,'ingested_at':str(i)} for i,(v,src) in enumerate(zip(values,['hr_system','sap']))]
    assert d.apply_survivorship(strategy,inputs)['value']==expected


def test_survivorship_empty_union():
    assert d.apply_survivorship('first_non_empty',[]) is None
    assert d.apply_survivorship('first_non_empty',[{'value':''}])=={'value':''}
    result=d.apply_survivorship('union_values',[{'value':'a'},{'value':'b'},{'value':'a'}])
    assert set(result['value'])=={'a','b'} and result['source_system']=='aggregated'

@pytest.fixture
def mdm(tmp_path,monkeypatch):
    monkeypatch.setenv('MDM_STORAGE_FILE',str(tmp_path/'mdm.json'))
    return d.MDMService()


def test_merge_conflict_resolution_and_reload(mdm):
    first=mdm.ingest(d.SourceSystem.HR_SYSTEM,d.EntityType.EMPLOYEE,'h1',{'employee_id':'E1','full_name':'Ali','email':'old@example.invalid'})
    merged=mdm.ingest(d.SourceSystem.ACTIVE_DIRECTORY,d.EntityType.EMPLOYEE,'a1',{'employee_id':'E1','full_name':'Ali Anam','email':'new@example.invalid'})
    assert merged.golden_id==first.golden_id and merged.merge_count==2
    assert merged.attributes['email']['source']=='active_directory' and merged.attributes['full_name']['value']=='Ali Anam'
    conflict=next(c for c in mdm.list_conflicts() if c.attribute_name=='email')
    mdm.resolve_conflict(conflict.conflict_id,'approved@example.invalid','reviewer','checked')
    restored=d.MDMService().get_golden(d.EntityType.EMPLOYEE,'E1')
    assert restored.attributes['email']['value']=='approved@example.invalid' and restored.source_record_ids==merged.source_record_ids
    with pytest.raises(ValueError):mdm.resolve_conflict('missing','x','user')

@pytest.mark.parametrize('entity',list(d.EntityType))
def test_entity_namespaces_and_list(mdm,entity):
    result=mdm.ingest(d.SourceSystem.SAP,entity,'source', {f'{entity.value}_id':'same','name':'Sample'})
    assert mdm.get_golden(entity,'same').golden_id==result.golden_id
    assert [r.golden_id for r in mdm.list_golden(entity)]==[result.golden_id]
    assert mdm.get_golden(entity,'missing') is None

@pytest.fixture
def market(tmp_path,monkeypatch):
    monkeypatch.setenv('AGENT_MARKETPLACE_FILE',str(tmp_path/'market.json'))
    return a.AgentMarketplace()


def build(market):
    template=market.list_templates()[0]
    return market.create_agent_from_template(template['template_id'],'Finance','creator')


def promote(market,agent,version,canary=False):
    market.test_agent(agent.agent_id,version.version_id,'tester')
    market.promote_to_staging(agent.agent_id,version.version_id,'manager')
    return market.promote_to_production(agent.agent_id,version.version_id,'manager',canary=canary)


def test_lifecycle_and_reload(market):
    agent=build(market);version=agent.versions[0]
    promote(market,agent,version,canary=True)
    assert version.status==a.AgentStatus.CANARY and version.canary_percentage==5
    for percentage in [25,50,100]:market.increase_canary(agent.agent_id,version.version_id,percentage)
    restored=a.AgentMarketplace().get_agent(agent.agent_id)
    assert restored.get_production_version().version_id==version.version_id
    assert market.get_metrics(agent.agent_id)['canary_percentage']==100
    assert market.retire_agent(agent.agent_id,'manager') and not agent.current_version

@pytest.mark.parametrize('operation',['staging','production','canary'])
def test_invalid_lifecycle_order(market,operation):
    agent=build(market);vid=agent.versions[0].version_id
    with pytest.raises(ValueError):
        if operation=='staging':market.promote_to_staging(agent.agent_id,vid,'x')
        elif operation=='production':market.promote_to_production(agent.agent_id,vid,'x')
        else:market.increase_canary(agent.agent_id,vid,25)
    assert agent.versions[0].status==a.AgentStatus.DRAFT

@pytest.mark.parametrize('method',['test_agent','promote_to_staging','promote_to_production','increase_canary'])
@pytest.mark.parametrize('missing',['agent','version'])
def test_missing_agent_or_version(market,method,missing):
    agent=build(market);aid='missing' if missing=='agent' else agent.agent_id
    with pytest.raises(ValueError):getattr(market,method)(aid,'missing',25 if method=='increase_canary' else 'reviewer')


def test_custom_versions_and_rollback_persist(market):
    agent=market.create_custom_agent('Analyst','Audit',a.AgentCategory.CUSTOM,'Finance','creator','Review evidence',[],[],['auditor'])
    v1=agent.versions[0];promote(market,agent,v1)
    v2=a.AgentVersion(version_number=2,name='Improved');agent.versions.append(v2);promote(market,agent,v2)
    assert v1.status==a.AgentStatus.RETIRED and agent.get_production_version()==v2
    assert market.rollback(agent.agent_id).version_id==v1.version_id
    assert a.AgentMarketplace().get_agent(agent.agent_id).current_version==v1.version_id
