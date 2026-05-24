from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient
from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)

# JWKS client — fetches and caches Supabase's public keys automatically
# Used for ES256 tokens (new projects created after May 2025)
_jwks_client = PyJWKClient(
    f"{settings.supabase_url}/auth/v1/.well-known/jwks.json",
    cache_keys=True,
)


def _decode_token(token: str) -> dict:
    """
    Decode a Supabase JWT regardless of whether it's HS256 or ES256.
    - ES256: verify using public key from JWKS endpoint
    - HS256: verify using the JWT secret from .env
    """
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "HS256")

    if alg == "ES256":
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )
    else:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict | None:
    """Returns decoded JWT payload if valid token present, else None (anonymous)."""
    if not credentials:
        return None
    try:
        return _decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {e}")


def require_auth(user: dict | None = Depends(get_current_user)) -> dict:
    """Use on any endpoint that requires login."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user