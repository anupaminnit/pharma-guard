"""
Azure AD JWT authentication for FastAPI.

For local demo: set AUTH_ENABLED=false in .env — all endpoints are open.
For production: configure Azure AD tenant and register the app in Entra ID.

Required env vars (production only):
    AZURE_TENANT_ID     — Azure AD tenant ID
    AZURE_CLIENT_ID     — Application (client) ID registered in Entra ID
    AUTH_ENABLED        — "true" | "false" (default: "true")

Frontend uses @azure/msal-react for PKCE OAuth2 flow. Token is stored in
memory (not localStorage) to prevent XSS theft.
"""

from __future__ import annotations

import os
from typing import Optional
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer

# python-jose for JWT validation
try:
    from jose import JWTError, jwt
    from jose.backends import RSAKey
    HAS_JOSE = True
except ImportError:
    HAS_JOSE = False

from dotenv import load_dotenv
load_dotenv()

AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "true").lower() == "true"
TENANT_ID    = os.environ.get("AZURE_TENANT_ID", "")
CLIENT_ID    = os.environ.get("AZURE_CLIENT_ID", "")

JWKS_URI     = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
ISSUER       = f"https://sts.windows.net/{TENANT_ID}/"

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/authorize",
    tokenUrl=f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
    auto_error=False,
)


@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    """Fetch Azure AD public keys (cached in memory, restart to refresh)."""
    import httpx
    response = httpx.get(JWKS_URI, timeout=10)
    response.raise_for_status()
    return response.json()


def _validate_token(token: str) -> dict:
    """Validate the Azure AD JWT and return the decoded claims."""
    if not HAS_JOSE:
        raise HTTPException(status_code=500, detail="python-jose not installed")

    jwks = _get_jwks()
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token header")

    # Find the matching key by kid
    rsa_key = {}
    for key in jwks.get("keys", []):
        if key.get("kid") == unverified_header.get("kid"):
            rsa_key = {k: key[k] for k in ("kty", "kid", "use", "n", "e")}
            break

    if not rsa_key:
        raise HTTPException(status_code=401, detail="Public key not found")

    try:
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=ISSUER,
        )
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Token validation failed: {exc}")

    return payload


# ── Dependency ────────────────────────────────────────────────────────────────

class CurrentUser:
    """Lightweight user representation from JWT claims."""
    def __init__(self, oid: str, email: str, name: str, roles: list[str]):
        self.oid   = oid
        self.email = email
        self.name  = name
        self.roles = roles

    def has_role(self, *roles: str) -> bool:
        return any(r in self.roles for r in roles)


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> Optional[CurrentUser]:
    """
    FastAPI dependency. Returns CurrentUser or None (if AUTH_ENABLED=false).

    Inject into endpoints:
        async def my_endpoint(user: CurrentUser = Depends(require_auth)):
    """
    if not AUTH_ENABLED:
        # Demo mode — return a synthetic admin user
        return CurrentUser(
            oid="demo-user",
            email="demo@pharma-guard.local",
            name="Demo User",
            roles=["admin"],
        )

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = _validate_token(token)
    return CurrentUser(
        oid=claims.get("oid", ""),
        email=claims.get("preferred_username") or claims.get("email", ""),
        name=claims.get("name", ""),
        roles=claims.get("roles", []),
    )


def require_role(*allowed_roles: str):
    """
    FastAPI dependency factory for role-based access control.

    Usage:
        @app.post("/api/admin/rules")
        async def create_rule(user: CurrentUser = Depends(require_role("admin", "regulatory_affairs"))):
            ...
    """
    async def _check(user: Optional[CurrentUser] = Depends(get_current_user)) -> CurrentUser:
        if user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        if allowed_roles and not user.has_role(*allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {list(allowed_roles)}",
            )
        return user

    return _check


# Convenience aliases
require_auth = require_role()          # any authenticated user
require_reviewer = require_role("qa_reviewer", "regulatory_affairs", "admin")
require_admin = require_role("admin")
