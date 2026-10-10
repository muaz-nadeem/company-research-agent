import os
from functools import lru_cache

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()


@lru_cache(maxsize=1)
def _get_supabase_admin():
    """Lazy-init Supabase admin client (uses service_role key)."""
    from supabase import create_client  # noqa: PLC0415

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise HTTPException(
            status_code=500,
            detail="SUPABASE_URL or SUPABASE_SERVICE_KEY not configured",
        )
    return create_client(url, key)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> dict:
    """Verify Supabase access token by calling Supabase Auth.

    Works for both legacy HS256 tokens and modern asymmetric (ES256/RS256)
    tokens because Supabase itself validates the signature.
    """
    token = credentials.credentials
    try:
        sb = _get_supabase_admin()
        result = sb.auth.get_user(token)
        user = getattr(result, "user", None)
        if not user or not getattr(user, "id", None):
            raise HTTPException(status_code=401, detail="Invalid session")
        return {
            "user_id": user.id,
            "email": getattr(user, "email", "") or "",
        }
    except HTTPException:
        raise
    except Exception as exc:
        msg = str(exc) or "Invalid session"
        if "expired" in msg.lower():
            raise HTTPException(
                status_code=401, detail="Session expired — please sign in again"
            )
        print(f"[auth] Token verification failed: {type(exc).__name__}")
        raise HTTPException(status_code=401, detail="Invalid session. Please sign in again.")
