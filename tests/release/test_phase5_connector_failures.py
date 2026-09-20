"""Explicit HTTP transport unit tests: no real messages leave this process."""
import json
import time
from urllib.parse import parse_qs
from unittest.mock import AsyncMock
import httpx
import pytest
from backend_core.enterprise_integrations import phase5_connectors as module
from backend_core.enterprise_integrations import real_connectors

CASES=[("OracleERPConnector","get_invoice",["invoice-3"]),("Dynamics365Connector","get_account",["account-4"]),("SalesforceConnector","get_opportunity",["opportunity-5"]),("WorkdayConnector","get_worker",["worker-6"]),("GoogleDriveConnector","list_files",["folder-7"]),("TeamsConnector","send_message",["team-8","channel-9","synthetic message"]),("SlackConnector","post_message",["channel-10","synthetic message"]),("ConfluenceConnector","get_page",["page-11"]),("RESTConnector","request",["GET","/items"]),("GraphQLConnector","query",["query { items { id } }"])]

@pytest.fixture
def environment(monkeypatch):
    real_connectors._token_cache.clear()
    for prefix in ["ORACLE","DYNAMICS","SF","WORKDAY","TEAMS","CONFLUENCE"]:
        for name in ["BASE_URL","LOGIN_URL"]:monkeypatch.setenv(prefix+"_"+name,"https://provider.example.invalid")
        for name in ["USERNAME","PASSWORD","TENANT_ID","CLIENT_ID","CLIENT_SECRET","API_TOKEN"]:monkeypatch.setenv(prefix+"_"+name,"synthetic-unit-value")
    monkeypatch.setenv("SLACK_BOT_TOKEN","synthetic-slack-token");monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON","synthetic-service-account-path")
    monkeypatch.setattr(module.GoogleDriveConnector,"_get_token",AsyncMock(return_value="synthetic-google-token"));monkeypatch.setattr(module.asyncio,"sleep",AsyncMock())

def connector(name):
    if name=="RESTConnector":return module.RESTConnector({"base_url":"https://provider.example.invalid","auth_token":"synthetic-token"})
    if name=="GraphQLConnector":return module.GraphQLConnector({"endpoint":"https://provider.example.invalid/graphql","auth_token":"synthetic-token"})
    return getattr(module,name)()

@pytest.mark.parametrize("name,method,args",CASES)
@pytest.mark.parametrize("outcome",["success","http_error","timeout"])
@pytest.mark.asyncio
async def test_connectors_handle_provider_results_and_redact_failures(environment,monkeypatch,caplog,name,method,args,outcome):
    seen=[]
    def peer(request):
        seen.append(request)
        if request.url.path.endswith("/token"):return httpx.Response(200,json={"access_token":"synthetic-oauth-token","instance_url":"https://provider.example.invalid","expires_in":3600})
        if outcome=="timeout":raise httpx.ConnectTimeout("sensitive-password-sentinel",request=request)
        if outcome=="http_error":return httpx.Response(401,text="sensitive-password-sentinel")
        return httpx.Response(200,json={"ok":True,"record":"business-record"})
    client_class=httpx.AsyncClient;monkeypatch.setattr(module.httpx,"AsyncClient",lambda **kw:client_class(transport=httpx.MockTransport(peer),**kw))
    instance=connector(name);instance.cb.failure_count=2;result=await getattr(instance,method)(*args)
    requests=[req for req in seen if not req.url.path.endswith("/token")];assert all(req.headers.get("authorization") for req in requests)
    if outcome=="success":
        assert result=={"ok":True,"record":"business-record"} and instance.cb.failure_count==0 and instance.cb.state=="closed" and len(requests)==1
    else:
        assert result["error"]=="Connector request failed" and instance.cb.failure_count==3
        assert len(requests)==(4 if outcome=="timeout" else 1) and "sensitive-password-sentinel" not in json.dumps(result)+caplog.text

@pytest.mark.parametrize("name,method,args",CASES)
@pytest.mark.asyncio
async def test_open_circuit_prevents_all_outbound_calls(environment,monkeypatch,name,method,args):
    instance=connector(name);instance.cb.state="open";instance.cb.last_failure=time.time()
    client=AsyncMock(side_effect=AssertionError("Open circuit must not send requests"));monkeypatch.setattr(module.httpx,"AsyncClient",client)
    assert await getattr(instance,method)(*args)=={"error":"Circuit breaker open"};client.assert_not_called()

@pytest.mark.parametrize("header,expected",[("999999999",3),("-5",0),("nan",1),("inf",1),("bad-date",1)])
@pytest.mark.asyncio
async def test_retry_after_is_finite_bounded_and_does_not_hide_final_success(monkeypatch,header,expected):
    sleep=AsyncMock();monkeypatch.setattr(module.asyncio,"sleep",sleep);request=httpx.Request("GET","https://provider.example.invalid")
    error=httpx.HTTPStatusError("upstream-private-body",request=request,response=httpx.Response(429,headers={"Retry-After":header},request=request))
    call=AsyncMock(side_effect=[error,{"recovered":True}]);assert await module.retry_with_backoff(call,max_delay=3)=={"recovered":True}
    sleep.assert_awaited_once_with(expected);assert call.await_count==2

@pytest.mark.asyncio
async def test_persistent_retryable_failure_is_raised_with_exact_attempt_bound(monkeypatch):
    sleep=AsyncMock();monkeypatch.setattr(module.asyncio,"sleep",sleep);call=AsyncMock(side_effect=httpx.ReadTimeout("unavailable"))
    with pytest.raises(httpx.ReadTimeout):await module.retry_with_backoff(call,max_retries=2,base_delay=.5)
    assert call.await_count==3 and [item.args[0] for item in sleep.await_args_list]==[.5,1]

def test_circuit_recovers_after_cooldown_and_success(monkeypatch):
    clock=[100.0];monkeypatch.setattr(module.time,"time",lambda:clock[0]);circuit=module.CircuitBreakerState(threshold=2,reset_timeout=10)
    circuit.record_failure();assert circuit.can_attempt();circuit.record_failure();assert not circuit.can_attempt()
    clock[0]+=11;assert circuit.can_attempt() and circuit.state=="half-open";circuit.record_success();assert circuit.state=="closed" and circuit.failure_count==0

@pytest.mark.asyncio
async def test_dynamics_cache_isolates_resource_audiences(environment,monkeypatch):
    seen=[]
    def peer(request):
        scope=parse_qs(request.content.decode())["scope"][0];seen.append(scope);return httpx.Response(200,json={"access_token":scope})
    client_class=httpx.AsyncClient;monkeypatch.setattr(module.httpx,"AsyncClient",lambda **kw:client_class(transport=httpx.MockTransport(peer),**kw))
    first,second=module.Dynamics365Connector(),module.Dynamics365Connector();second.base_url="https://second.example.invalid"
    a,b=await first._get_token(),await second._get_token();assert a!=b and len(seen)==2
    assert await first._get_token()==a and len(seen)==2
