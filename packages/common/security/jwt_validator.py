"""
HSAAI JWT Security Validator (Phase 32)
=========================================
Validates JWT tokens with defense against:
  - Algorithm confusion (none, HS256 with RSA key)
  - Algorithm downgrade
  - Expired tokens
  - Forged tokens
  - Missing claims
  - Invalid issuer/audience

Usage:
    from packages.common.security.jwt_validator import JWTValidator

    validator = JWTValidator(
        jwks_url="https://keycloak:8443/realms/hsaai/protocol/openid-connect/certs",
        issuer="https://keycloak:8443/realms/hsaai",
        audience="hsaai-api",
    )
    claims = await validator.verify(token)
"""
import os
import time
import json
import logging
import httpx
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger("hsaai.jwt_validator")


@dataclass
class JWTClaims:
    """Validated JWT claims."""
    sub: str  # subject (user ID)
    iss: str  # issuer
    aud: str  # audience
    exp: int  # expiration time
    iat: int  # issued at
    nbf: int  # not before
    tenant_id: str
    roles: List[str]
    email: Optional[str] = None
    name: Optional[str] = None


class JWTValidationError(Exception):
    """Raised when JWT validation fails."""


class JWTValidator:
    """
    JWT validator with security hardening.
    """

    # ─── REJECTED ALGORITHMS ─────────────────────────────────────
    FORBIDDEN_ALGORITHMS = {"none", "None", "NONE", "HS256", "HS384", "HS512"}

    def __init__(
        self,
        jwks_url: str,
        issuer: str,
        audience: str,
        clock_skew_seconds: int = 30,
        cache_ttl_seconds: int = 300,
    ):
        self.jwks_url = jwks_url
        self.issuer = issuer
        self.audience = audience
        self.clock_skew = clock_skew_seconds
        self.cache_ttl = cache_ttl_seconds
        self._jwks_cache: Optional[Dict] = None
        self._jwks_cached_at: float = 0

    async def _fetch_jwks(self) -> Dict:
        """Fetch JWKS (JSON Web Key Set) with caching."""
        now = time.time()
        if self._jwks_cache and (now - self._jwks_cached_at) < self.cache_ttl:
            return self._jwks_cache

        async with httpx.AsyncClient(timeout=10, verify=True) as client:
            resp = await client.get(self.jwks_url)
            resp.raise_for_status()
            self._jwks_cache = resp.json()
            self._jwks_cached_at = now
            logger.debug("JWKS fetched and cached")
            return self._jwks_cache

    async def verify(self, token: str) -> JWTClaims:
        """
        Verify a JWT token. Returns validated claims or raises JWTValidationError.
        """
        # 1. Decode header (without verification) to check algorithm
        try:
            header_b64, payload_b64, signature_b64 = token.split(".")
        except ValueError:
            raise JWTValidationError("Invalid token format (expected 3 parts)")

        header = self._decode_base64json(header_b64)
        payload = self._decode_base64json(payload_b64)

        # 2. Reject forbidden algorithms
        algorithm = header.get("alg", "")
        if algorithm in self.FORBIDDEN_ALGORITHMS:
            raise JWTValidationError(
                f"Forbidden algorithm: {algorithm}. Only RS256/RS384/RS512/ES256 allowed."
            )

        # 3. Verify signature (SECURITY FIX v2.1 P0): Previously the actual
        # jose_jwt.decode() call was commented out — tokens were NOT signature-
        # verified, only structurally inspected. This contradicted the RS256
        # verification claim. Now we perform full signature verification via
        # python-jose with the JWKS public key.
        try:
            jwks = await self._fetch_jwks()
            kid = header.get("kid")
            if not kid:
                raise JWTValidationError("Missing 'kid' in header")
            matching_keys = [k for k in jwks.get("keys", []) if k.get("kid") == kid]
            if not matching_keys:
                raise JWTValidationError(f"No JWKS key matches kid: {kid}")
            # FIX v2.1 (P0): Actually verify the signature — uncommented and active.
            try:
                from jose import jwt as jose_jwt
            except ImportError as import_err:
                raise JWTValidationError(
                    "python-jose not installed — cannot verify JWT signatures. "
                    "Install with: pip install python-jose[cryptography]"
                ) from import_err
            # Decode and verify signature + claims in one call.
            verified_payload = jose_jwt.decode(
                token,
                matching_keys[0],
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
            # Use the verified payload from jose (it has checked signature + claims).
            payload = verified_payload
        except httpx.HTTPError as e:
            raise JWTValidationError(f"JWKS fetch failed: {e}")

        # 4. Validate required claims
        required_claims = ["sub", "iss", "aud", "exp", "iat"]
        for claim in required_claims:
            if claim not in payload:
                raise JWTValidationError(f"Missing required claim: {claim}")

        # 5. Validate issuer
        if payload["iss"] != self.issuer:
            raise JWTValidationError(
                f"Invalid issuer: {payload['iss']} (expected: {self.issuer})"
            )

        # 6. Validate audience
        aud = payload["aud"]
        if isinstance(aud, list):
            if self.audience not in aud:
                raise JWTValidationError(f"Audience {self.audience} not in {aud}")
        elif aud != self.audience:
            raise JWTValidationError(f"Invalid audience: {aud} (expected: {self.audience})")

        # 7. Validate expiration (with clock skew)
        now = int(time.time())
        if payload["exp"] + self.clock_skew < now:
            raise JWTValidationError(
                f"Token expired at {datetime.fromtimestamp(payload['exp'], tz=timezone.utc)}"
            )

        # 8. Validate issued at (reject future tokens)
        if payload["iat"] - self.clock_skew > now:
            raise JWTValidationError(
                f"Token issued in future: iat={payload['iat']}, now={now}"
            )

        # 9. Validate not-before (if present)
        if "nbf" in payload and payload["nbf"] - self.clock_skew > now:
            raise JWTValidationError(f"Token not yet valid: nbf={payload['nbf']}")

        # 10. Extract HSAAI-specific claims
        tenant_id = payload.get("tenant_id") or payload.get("tenant") or "default"
        roles = payload.get("roles", [])
        if isinstance(roles, str):
            roles = [roles]

        return JWTClaims(
            sub=payload["sub"],
            iss=payload["iss"],
            aud=payload["aud"] if isinstance(payload["aud"], str) else payload["aud"][0],
            exp=payload["exp"],
            iat=payload["iat"],
            nbf=payload.get("nbf", payload["iat"]),
            tenant_id=tenant_id,
            roles=roles,
            email=payload.get("email"),
            name=payload.get("name"),
        )

    def _decode_base64json(self, b64: str) -> Dict:
        """Decode a base64url-encoded JSON string."""
        import base64
        # Add padding
        padding = 4 - len(b64) % 4
        if padding != 4:
            b64 += "=" * padding
        try:
            decoded = base64.urlsafe_b64decode(b64)
            return json.loads(decoded)
        except Exception as e:
            raise JWTValidationError(f"Failed to decode base64 JSON: {e}")


# ─── PENETRATION TEST SCENARIOS ───────────────────────────────────
class JWTPenetrationTests:
    """
    Penetration test scenarios for JWT validation.
    These are runnable tests, not just documentation.
    """

    @staticmethod
    async def test_none_algorithm_rejected(validator: JWTValidator) -> bool:
        """Test: 'none' algorithm should be rejected."""
        # Forge a token with alg=none
        import base64
        header = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(b'{"sub":"admin","iss":"test","aud":"test","exp":9999999999,"iat":1}').rstrip(b"=").decode()
        forged = f"{header}.{payload}."
        try:
            await validator.verify(forged)
            return False  # FAIL: should have rejected
        except JWTValidationError:
            return True  # PASS: rejected

    @staticmethod
    async def test_hs256_confusion_rejected(validator: JWTValidator) -> bool:
        """Test: HS256 with RSA public key should be rejected."""
        import base64
        header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(b'{"sub":"admin","iss":"test","aud":"test","exp":9999999999,"iat":1}').rstrip(b"=").decode()
        forged = f"{header}.{payload}.fake_signature"
        try:
            await validator.verify(forged)
            return False
        except JWTValidationError:
            return True

    @staticmethod
    async def test_expired_token_rejected(validator: JWTValidator) -> bool:
        """Test: Expired tokens should be rejected."""
        import base64
        header = base64.urlsafe_b64encode(b'{"alg":"RS256","typ":"JWT","kid":"test"}').rstrip(b"=").decode()
        # exp = 1 (1970)
        payload = base64.urlsafe_b64encode(b'{"sub":"user","iss":"test","aud":"test","exp":1,"iat":1}').rstrip(b"=").decode()
        expired = f"{header}.{payload}.signature"
        try:
            await validator.verify(expired)
            return False
        except JWTValidationError:
            return True
