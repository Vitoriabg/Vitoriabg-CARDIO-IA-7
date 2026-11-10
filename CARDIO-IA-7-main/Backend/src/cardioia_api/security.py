import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from pwdlib import PasswordHash

PASSWORDS = PasswordHash.recommended()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def issue_token(username, settings):
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": username, "iss": "cardioia", "aud": "cardioia-ui",
                       "iat": now, "exp": now + timedelta(seconds=settings.token_ttl),
                       "jti": uuid4().hex}, settings.jwt_secret, algorithm="HS256")


def read_token(token, settings):
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], issuer="cardioia",
                      audience="cardioia-ui", options={"require": ["sub", "exp", "iat", "jti"]})["sub"]
