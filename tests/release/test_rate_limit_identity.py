"""Untrusted headers must never choose a new quota bucket."""
import pytest
from starlette.requests import Request
from common.security.rate_limit import SlidingWindowRateLimiter


def req(headers=(),state=None):
    return Request({'type':'http','method':'GET','path':'/data','headers':list(headers),'client':('127.0.0.1',2222),'server':('test',80),'scheme':'http','query_string':b'','state':state or {}})

@pytest.mark.asyncio
async def test_rotating_forged_identity_headers_do_not_bypass_limit(monkeypatch):
    for key,value in {'RATE_LIMIT_REDIS_URL':'','RATE_LIMIT_PER_USER':'3','RATE_LIMIT_BURST':'0'}.items():monkeypatch.setenv(key,value)
    limiter=SlidingWindowRateLimiter();results=[]
    for i in range(5):
        headers=[(key,str(i).encode()) for key in [b'x-user-id',b'x-tenant-id',b'x-forwarded-for',b'x-api-key']]
        results.append((await limiter.check(req(headers)))[0])
    assert results==[True,True,True,False,False]


def test_only_server_verified_identity_is_accepted(monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_REDIS_URL','')
    limiter=SlidingWindowRateLimiter()
    ids=limiter._get_identifiers(req([(b'x-user-id',b'forged')],{'claims':{'sub':'real','tenant_id':'tenant'},'verified_api_key_id':'key-id'}))
    assert ids=={'user':'real','tenant':'tenant','api_key':'key-id','ip':'127.0.0.1'}
