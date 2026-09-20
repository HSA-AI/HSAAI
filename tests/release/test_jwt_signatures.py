"""Real RSA signature and claim regressions for the JWT implementation."""
import json,time
import pytest,jwt
from cryptography.hazmat.primitives.asymmetric import rsa

@pytest.mark.asyncio
@pytest.mark.parametrize('fault',[None,'signature','expiry','audience','missing_exp'])
async def test_real_signature_and_required_claims(monkeypatch,fault):
    from backend_core.security import rbac
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    public=json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()));public['kid']='release-test'
    async def jwks():return {'keys':[public]}
    monkeypatch.setattr(rbac,'_fetch_jwks_async',jwks)
    monkeypatch.setattr(rbac,'KEYCLOAK_ISSUER','https://identity.example/realms/hsaai')
    monkeypatch.setattr(rbac,'KEYCLOAK_AUDIENCE','hsaai-api');monkeypatch.setattr(rbac,'VERIFY_KEYCLOAK_AUDIENCE',True)
    claims={'iss':rbac.KEYCLOAK_ISSUER,'aud':rbac.KEYCLOAK_AUDIENCE,'sub':'test-user','exp':int(time.time())+60,'tenant_id':'a','workspace_id':'w'}
    if fault=='signature':key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    if fault=='expiry':claims['exp']=int(time.time())-60
    if fault=='audience':claims['aud']='other-service'
    if fault=='missing_exp':claims.pop('exp')
    token=jwt.encode(claims,key,algorithm='RS256',headers={'kid':'release-test'})
    if fault:
        with pytest.raises(jwt.InvalidTokenError):await rbac._verify_with_keycloak_jwks_async(token)
    else:assert (await rbac._verify_with_keycloak_jwks_async(token))['sub']=='test-user'
