"""Canary rollout preserves the stable release and truthful quality averages."""
import pytest
from backend_core import agent_marketplace as m

@pytest.fixture
def rollout(tmp_path,monkeypatch):
    monkeypatch.setenv('AGENT_MARKETPLACE_FILE',str(tmp_path/'market.json'))
    market=m.AgentMarketplace();agent=market.create_custom_agent('A','Analyst',m.AgentCategory.CUSTOM,'Finance','owner','policy',[],[],['ai_user'])
    v1=agent.versions[0];v1.status=m.AgentStatus.STAGING;market.promote_to_production(agent.agent_id,v1.version_id,'manager',canary=False)
    v2=m.AgentVersion(version_number=2,status=m.AgentStatus.STAGING);agent.versions.append(v2)
    return market,agent,v1,v2


def test_canary_keeps_previous_production_until_full_rollout(rollout):
    market,agent,v1,v2=rollout;market.promote_to_production(agent.agent_id,v2.version_id,'manager',canary=True)
    assert v1.status==m.AgentStatus.PRODUCTION and agent.current_version==v1.version_id
    assert market.list_agents(status=m.AgentStatus.CANARY)==[agent]
    market.increase_canary(agent.agent_id,v2.version_id,100)
    assert v1.status==m.AgentStatus.RETIRED and v2.status==m.AgentStatus.PRODUCTION and agent.current_version==v2.version_id


def test_canary_rollback_retires_canary_and_retains_stable(rollout):
    market,agent,v1,v2=rollout;market.promote_to_production(agent.agent_id,v2.version_id,'manager',canary=True)
    assert market.rollback(agent.agent_id).version_id==v1.version_id
    assert v2.status==m.AgentStatus.RETIRED and v1.status==m.AgentStatus.PRODUCTION


def test_metrics_average_is_weighted_by_execution_count(rollout):
    market,agent,v1,v2=rollout
    market.update_metrics(agent.agent_id,v1.version_id,{'total_executions':2,'avg_satisfaction':0.8,'avg_latency_ms':100})
    market.update_metrics(agent.agent_id,v1.version_id,{'total_executions':1,'avg_satisfaction':0.2,'avg_latency_ms':400})
    assert v1.metrics['total_executions']==3 and v1.metrics['avg_satisfaction']==pytest.approx(0.6)
    assert v1.metrics['avg_latency_ms']==pytest.approx(200)


def test_archived_version_metrics_cannot_rollback_current_release(rollout):
    market,agent,v1,v2=rollout;market.promote_to_production(agent.agent_id,v2.version_id,'manager',canary=False)
    market.update_metrics(agent.agent_id,v1.version_id,{'total_executions':101,'hallucination_count':90,'avg_satisfaction':0.1})
    assert agent.get_production_version().version_id==v2.version_id
