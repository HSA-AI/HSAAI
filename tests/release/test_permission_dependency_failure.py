"""Missing permission provider must fail closed even in contract-safe imports."""
import builtins
import pytest
from fastapi import HTTPException
from backend_core.enterprise_os import router as mod

def test_permission_import_failure_is_denied(monkeypatch):
    original=builtins.__import__
    def unavailable(name,*args,**kwargs):
        if name=='backend_core.security.rbac':raise ImportError('isolated dependency failure')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',unavailable)
    dependency=mod._permission_dependency('agents:write')
    with pytest.raises(HTTPException) as err:dependency()
    assert err.value.status_code==503
