"""Authenticated smoke against a dedicated acceptance workspace; never logs tokens."""
import json,os,urllib.request,urllib.error
base=os.environ['API_URL'].rstrip('/');token=os.environ['HSAAI_ACCEPTANCE_TOKEN']
def call(path,payload=None,auth=True):
 headers={'Content-Type':'application/json'}
 if auth:headers['Authorization']='Bearer '+token
 request=urllib.request.Request(base+path,data=json.dumps(payload).encode() if payload is not None else None,headers=headers)
 with urllib.request.urlopen(request,timeout=180) as response:return json.load(response)
assert call('/ready',auth=False)['status']=='ready'
try:
 call('/v1/chat',{'message':'Unauthenticated acceptance probe'},auth=False)
 raise AssertionError('Anonymous chat was accepted')
except urllib.error.HTTPError as exc:assert exc.code in (401,403),exc.code
assert call('/v1/llm/generate',{'prompt':'أجب بكلمة واحدة: جاهز','max_tokens':32}).get('text'),'No model response'
print(json.dumps({'health':'passed','anonymous_access':'denied','real_model_response':'passed','scope':'API and inference smoke; RAG, SSO, cross-tenant, load and DR checks are separate'},ensure_ascii=False))
