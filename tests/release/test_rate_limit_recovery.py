"""Bounded quotas and real Redis concurrency, outage, restart acceptance."""
import asyncio
import socket
import subprocess
import time
from pathlib import Path
import httpx
import pytest
import redis
import redislite
from fastapi import FastAPI
from starlette.requests import Request
from common.security import rate_limit as module

def request(user="one",path="/data"):
    return Request({"type":"http","method":"GET","path":path,"headers":[],"client":("127.0.0.1",2222),"server":("test",80),"scheme":"http","query_string":b"","state":{"claims":{"sub":user,"tenant_id":"company-a"}}})

@pytest.fixture(autouse=True)
def configuration(monkeypatch):
    for key,value in {"APP_ENV":"test","RATE_LIMIT_REDIS_URL":"","RATE_LIMIT_FAILURE_MODE":"closed","RATE_LIMIT_PER_USER":"3","RATE_LIMIT_PER_TENANT":"1000","RATE_LIMIT_PER_IP":"1000","RATE_LIMIT_BURST":"0","RATE_LIMIT_MAX_IDENTITIES":"6"}.items():monkeypatch.setenv(key,value)

@pytest.mark.asyncio
async def test_denied_requests_do_not_grow_memory_or_reset_active_quota():
    limiter=module.SlidingWindowRateLimiter();results=[await limiter.check(request()) for _ in range(100)]
    assert all(r[0] for r in results[:3]) and all(not r[0] and r[1]=="rate_limit_user" and 1<=r[2]<=60 for r in results[3:])
    assert len(limiter._memory["rate_limit:user:one"])==3 and len(limiter._memory)==3

@pytest.mark.asyncio
async def test_identity_pressure_is_bounded_without_evicting_active_clients(monkeypatch):
    clock=[100.0];monkeypatch.setattr(module.time,"monotonic",lambda:clock[0]);limiter=module.SlidingWindowRateLimiter()
    for i in range(50):await limiter.check(request(str(i)))
    assert len(limiter._memory)==limiter.max_identities and "rate_limit:user:0" in limiter._memory
    assert await limiter.check(request("new"))==(False,"rate_limit_capacity",60)
    clock[0]+=61;assert (await limiter.check(request("new")))[0] and len(limiter._memory)==3

@pytest.mark.parametrize("setting,value",[("RATE_LIMIT_MAX_IDENTITIES","0"),("RATE_LIMIT_FAILURE_MODE","open"),("RATE_LIMIT_PER_USER","0"),("RATE_LIMIT_BURST","-1")])
def test_invalid_rate_configuration_is_rejected(monkeypatch,setting,value):
    monkeypatch.setenv(setting,value)
    with pytest.raises(ValueError):module.SlidingWindowRateLimiter()

@pytest.mark.asyncio
async def test_production_requires_redis_and_keeps_health_probes_working(monkeypatch):
    monkeypatch.setenv("APP_ENV","production");limiter=module.SlidingWindowRateLimiter()
    assert await limiter.check(request())==(False,"rate_limit_unavailable",1)
    assert await limiter.check(request(path="/health"))==(True,None,None)
    monkeypatch.setenv("RATE_LIMIT_FAILURE_MODE","memory")
    with pytest.raises(ValueError,match="fail closed"):module.SlidingWindowRateLimiter()

@pytest.mark.asyncio
async def test_redis_exception_details_never_leak_and_memory_fallback_is_explicit(monkeypatch,caplog):
    class BrokenRedis:
        def eval(self,*args):raise redis.ConnectionError("private-password-sentinel https://secret.example/token")
    limiter=module.SlidingWindowRateLimiter();limiter._redis=BrokenRedis()
    assert await limiter.check(request())==(False,"rate_limit_unavailable",1)
    assert "private-password-sentinel" not in caplog.text and "secret.example" not in caplog.text
    monkeypatch.setenv("RATE_LIMIT_FAILURE_MODE","memory");limiter=module.SlidingWindowRateLimiter();limiter._redis=BrokenRedis()
    assert (await limiter.check(request()))[0] and limiter._memory

@pytest.mark.asyncio
async def test_http_outage_returns_503_and_never_invokes_endpoint(monkeypatch):
    monkeypatch.setenv("APP_ENV","production");monkeypatch.setattr(module,"_limiter",None)
    app=FastAPI();module.setup_rate_limiting(app);called=[]
    @app.get("/data")
    def data():called.append(True);return {"ok":True}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:response=await client.get("/data")
    assert response.status_code==503 and response.headers["retry-after"]=="1" and response.json()["error"]=="RATE_LIMIT_UNAVAILABLE" and not called

@pytest.fixture
def real_redis(tmp_path):
    binary=Path(redislite.__file__).parent/"bin/redis-server"
    with socket.socket() as sock:sock.bind(("127.0.0.1",0));port=sock.getsockname()[1]
    client=redis.Redis(host="127.0.0.1",port=port,socket_timeout=1,socket_connect_timeout=1);processes=[]
    def start():
        process=subprocess.Popen([str(binary),"--bind","127.0.0.1","--port",str(port),"--save","","--appendonly","no","--dir",str(tmp_path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(process)
        for _ in range(100):
            try:
                if client.ping():return process
            except redis.ConnectionError:time.sleep(.03)
        raise AssertionError("Isolated Redis failed to start")
    try:process=start();yield f"redis://127.0.0.1:{port}/0",client,process,start
    finally:
        client.close()
        for process in processes:
            if process.poll() is None:process.terminate();process.wait(timeout=5)

@pytest.mark.asyncio
async def test_real_redis_limits_are_atomic_and_recover_after_restart(real_redis,monkeypatch):
    url,client,process,restart=real_redis
    monkeypatch.setenv("RATE_LIMIT_REDIS_URL",url);monkeypatch.setenv("APP_ENV","production");monkeypatch.setenv("RATE_LIMIT_PER_USER","7")
    limiter=module.SlidingWindowRateLimiter()
    try:
        results=await asyncio.gather(*(limiter.check(request()) for _ in range(80)))
        assert sum(result[0] for result in results)==7 and client.zcard("rate_limit:user:one")==7 and 0<client.ttl("rate_limit:user:one")<=61
        process.terminate();process.wait(timeout=5)
        assert await limiter.check(request("after-outage"))==(False,"rate_limit_unavailable",1) and not limiter._memory
        restart();assert (await limiter.check(request("after-outage")))[0]
    finally:limiter._redis.close()
