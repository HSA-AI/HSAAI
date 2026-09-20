"""HTTP contract tests use MockTransport: no messages or writes leave this process."""
import json
from urllib.parse import parse_qs
from unittest.mock import AsyncMock
import httpx
import pytest
from backend_core.enterprise_integrations import real_connectors as m
from backend_core.enterprise_integrations import phase5_connectors as p5

CASES=[
 ('SharePointConnector','list_files',[],'files'),('SharePointConnector','download_file',['doc'],'content'),('SharePointConnector','search_files',['policy'],'results'),
 ('PowerBIConnector','list_dashboards',[],'dashboards'),('PowerBIConnector','list_reports',[],'reports'),('PowerBIConnector','list_datasets',[],'datasets'),
 ('OutlookConnector','send_mail',[['test@example.invalid'],'subject','body'],'sent'),('OutlookConnector','list_calendar_events',[],'events'),
 ('ITSMConnector','create_ticket',['issue','description'],'ticket_id'),('ITSMConnector','get_ticket',['123'],'ticket'),('ITSMConnector','list_tickets',[],'tickets'),
 ('DMSConnector','search_documents',['policy'],'results'),('DMSConnector','get_document',['123'],'document'),('DMSConnector','get_document_versions',['123'],'versions'),
 ('SuccessFactorsConnector','get_employee',['123'],'employee'),('SuccessFactorsConnector','list_employees',[],'employees'),('SuccessFactorsConnector','get_leave_balances',['123'],'balances'),
]

@pytest.fixture
def peers(monkeypatch):
    m._token_cache.clear()
    for prefix in ['SHAREPOINT','POWERBI','OUTLOOK','SUCCESSFACTORS']:
        for key,value in [('TENANT_ID','tenant'),('CLIENT_ID','client'),('CLIENT_SECRET','synthetic-unit-secret')]:monkeypatch.setenv(f'{prefix}_{key}',value)
    for prefix in ['ITSM','DMS','SUCCESSFACTORS']:
        monkeypatch.setenv(prefix+'_BASE_URL','https://peer.example.invalid')
        monkeypatch.setenv(prefix+'_API_KEY','synthetic-key')
    monkeypatch.setenv('SUCCESSFACTORS_COMPANY_ID','company')
    monkeypatch.setenv('OUTLOOK_SENDER_UPN','sender@example.invalid')
    monkeypatch.setenv('SHAREPOINT_SITE_ID','site');monkeypatch.setenv('SHAREPOINT_DRIVE_ID','drive')
    monkeypatch.setattr(m,'_get_ms_graph_token',AsyncMock(return_value='verified-oauth'))
    monkeypatch.setattr(m.SuccessFactorsConnector,'_get_token',AsyncMock(return_value='verified-oauth'))

@pytest.mark.parametrize('cls,method,args,key',CASES)
@pytest.mark.parametrize('outcome',['success','http_error','timeout'])
@pytest.mark.asyncio
async def test_adapters_contracts(peers,monkeypatch,cls,method,args,key,outcome):
    seen=[]
    record={'id':'123','name':'Policy','subject':'Review','displayName':'Operations','bodyPreview':'agenda','start':{},'end':{}}
    data={'id':'123','value':[record],'tickets':[record],'documents':[record],'versions':[record],'count':1,'d':{'results':[record]}}
    def peer(req):
        seen.append(req)
        if outcome=='timeout':raise httpx.ConnectTimeout('peer unavailable',request=req)
        return httpx.Response(503,text='secret-upstream-body') if outcome=='http_error' else httpx.Response(200,json=data)
    real_client=httpx.AsyncClient
    monkeypatch.setattr(m.httpx,'AsyncClient',lambda **kw:real_client(transport=httpx.MockTransport(peer),**kw))
    connector=getattr(m,cls)()
    if outcome=='timeout':
        with pytest.raises(httpx.ConnectTimeout):await getattr(connector,method)(*args)
    else:
        result=await getattr(connector,method)(*args)
        assert key in result
        if outcome=='http_error':assert result['error']=='Upstream HTTP 503' and 'secret-upstream' not in str(result)
        else:assert result[key] and 'error' not in result
    assert len(seen)==1 and seen[0].headers['authorization'].startswith('Bearer ')

@pytest.mark.parametrize('cls,method,args,key', [CASES[i] for i in [0,3,6,8,11]])
@pytest.mark.asyncio
async def test_unconfigured_connectors_do_not_call_network(monkeypatch,cls,method,args,key):
    for name in list(__import__('os').environ):
        if name.startswith(('SHAREPOINT_','POWERBI_','OUTLOOK_','ITSM_','DMS_')):monkeypatch.delenv(name)
    client=AsyncMock(side_effect=AssertionError('No network allowed'));monkeypatch.setattr(m.httpx,'AsyncClient',client)
    result=await getattr(getattr(m,cls)(),method)(*args)
    assert 'not configured' in result['error'] and not result[key]
    client.assert_not_called()

@pytest.mark.asyncio
async def test_oauth_cache_isolates_audience_and_expires(monkeypatch):
    m._token_cache.clear();seen=[]
    def peer(req):
        form=parse_qs(req.content.decode());seen.append(form)
        return httpx.Response(200,json={'access_token':form['scope'][0],'expires_in':3600})
    real=httpx.AsyncClient;monkeypatch.setattr(m.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(peer),**kw))
    graph=await m._get_ms_graph_token('t','c','secret')
    power=await m._get_ms_graph_token('t','c','secret',scope='https://analysis.windows.net/powerbi/api/.default')
    assert graph!=power and len(seen)==2
    assert await m._get_ms_graph_token('t','c','secret')==graph and len(seen)==2
    key=next(k for k in m._token_cache if k.endswith('https://graph.microsoft.com/.default'))
    m._token_cache[key]=(graph,0)
    assert await m._get_ms_graph_token('t','c','secret')==graph and len(seen)==3

@pytest.mark.parametrize('status',[503,400,'timeout'])
@pytest.mark.asyncio
async def test_sap_retry_preserves_csrf_and_client_errors(monkeypatch,status):
    obj=m.SAPS4HANAConnector();obj._get_token=AsyncMock(return_value='token');seen=[]
    monkeypatch.setattr('asyncio.sleep',AsyncMock())
    def peer(req):
        seen.append(req)
        if len(seen)==1:
            if status=='timeout':raise httpx.ConnectError('down',request=req)
            return httpx.Response(status,json={'error':'down'})
        return httpx.Response(200,json={'saved':True})
    real=httpx.AsyncClient;monkeypatch.setattr(m.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(peer),**kw))
    if status==400:
        with pytest.raises(httpx.HTTPStatusError):await obj._request_with_retry('POST','https://sap.example.invalid/resource',headers={'X-CSRF-Token':'csrf'},json={'value':7})
        assert len(seen)==1
    else:
        assert await obj._request_with_retry('POST','https://sap.example.invalid/resource',headers={'X-CSRF-Token':'csrf'},json={'value':7})=={'saved':True}
        assert len(seen)==2
    assert all(r.headers['X-CSRF-Token']=='csrf' and json.loads(r.content)=={'value':7} for r in seen)

@pytest.mark.parametrize('auth,header,expected',[('bearer','authorization','Bearer token'),('basic','authorization','Basic dTpw'),('api_key','x-api-key','key')])
@pytest.mark.asyncio
async def test_rest_auth_and_query_encoding(monkeypatch,auth,header,expected):
    seen=[]
    def peer(req):seen.append(req);return httpx.Response(200,json={'rows':[7]})
    real=httpx.AsyncClient;monkeypatch.setattr(p5.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(peer),**kw))
    obj=p5.RESTConnector({'base_url':'https://rest.example.invalid','auth_type':auth,'auth_token':'token','api_key':'key','username':'u','password':'p'})
    assert await obj.request('GET','/rows',params={'q':'A & B'})=={'rows':[7]}
    assert seen[0].headers[header]==expected and seen[0].url.params['q']=='A & B'
    obj.cb.state='open';obj.cb.last_failure=__import__('time').time()
    assert 'error' in await obj.request('GET','/rows') and len(seen)==1

@pytest.mark.asyncio
async def test_graphql_variables_are_json_not_interpolated(monkeypatch):
    seen=[]
    def peer(req):seen.append(req);return httpx.Response(200,json={'data':{'id':'123'}})
    real=httpx.AsyncClient;monkeypatch.setattr(p5.httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(peer),**kw))
    obj=p5.GraphQLConnector({'endpoint':'https://graphql.example.invalid','auth_token':'token'})
    query='query($id:ID!){item(id:$id){id}}';variables={'id':'1" attack'}
    assert await obj.query(query,variables)=={'data':{'id':'123'}}
    assert json.loads(seen[0].content)=={'query':query,'variables':variables}
