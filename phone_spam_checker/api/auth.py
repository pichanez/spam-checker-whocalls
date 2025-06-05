import jwt
from jwt import PyJWTError
from datetime import datetime, timedelta
from fastapi import HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from phone_spam_checker.config import settings

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


def _create_token() -> str:
    expires = datetime.utcnow() + timedelta(hours=settings.token_ttl_hours)
    payload = {"sub": "api", "exp": expires}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


async def login(api_key: str = Security(api_key_header)) -> dict:
    if not settings.api_key or api_key != settings.api_key:
        raise HTTPException(status_code=403, detail="Forbidden")
    return {"access_token": _create_token()}


async def get_token(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
    except PyJWTError:
        raise HTTPException(status_code=403, detail="Invalid token")
    return credentials.credentials
